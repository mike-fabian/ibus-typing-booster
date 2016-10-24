# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2011-2013 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012-2016 Mike FABIAN <mfabian@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#  This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#  You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import os
import os.path as path
import sys
import codecs
import unicodedata
import sqlite3
import time
import re
import traceback
import itb_util
import hunspell_suggest

DEBUG_LEVEL = int(0)

user_database_version = '0.65'

class ImeProperties:
    def __init__(self, configfile_path=None):
        '''
        configfile_path is the full path to the config file, for example
        “/usr/share/ibus-typing-booster/hunspell-tables/en_US.conf”
        '''
        self.ime_property_cache = {}
        if os.path.exists(configfile_path) and os.path.isfile(configfile_path):
            comment_patt = re.compile('^#')
            with codecs.open(
                    configfile_path, mode='r', encoding='UTF-8') as file_handle:
                for line in file_handle:
                    if not comment_patt.match(line):
                        attr, val = line.strip().split ('=', 1)
                        self.ime_property_cache[attr.strip()]= val.strip()
        else:
            sys.stderr.write(
                "Error: ImeProperties: No such file: %s" %configfile_path)

    def get(self, key):
        if key in self.ime_property_cache:
            return self.ime_property_cache[key]
        else:
            return None

class tabsqlitedb:
    '''Phrase databases for ibus-typing-booster

    The phrases table in the database has columns with the names:

    “id”, “input_phrase”, “phrase”, “p_phrase”, “pp_phrase”, “user_freq”, “timestamp”

    There are 2 databases, sysdb, userdb.

    sysdb: “Database” with the suggestions from the hunspell dictionaries
        user_freq = 0 always.

        Actually there is no Sqlite3 database called “sysdb”, these
        are the suggestions coming from hunspell_suggest, i.e. from
        grepping the hunspell dictionaries and from pyhunspell.
        (Historic note: ibus-typing-booster started as a fork of
        ibus-table, in ibus-table “sysdb” is a Sqlite3 database
        which is installed systemwide and readonly for the user)

    user_db: Database on disk where the phrases learned from the user are stored
        user_freq >= 1: The number of times the user has used this phrase
    '''
    def __init__(self, config_filename = '', user_db_file = ''):
        global DEBUG_LEVEL
        try:
            DEBUG_LEVEL = int(os.getenv('IBUS_TYPING_BOOSTER_DEBUG_LEVEL'))
        except (TypeError, ValueError):
            DEBUG_LEVEL = int(0)
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "tabsqlitedb.__init__(config_filename = %s, user_db_file = %s)\n"
                %(config_filename, user_db_file))
        self.user_db_file = user_db_file
        if not self.user_db_file:
            self.user_db_file = path.join(
                os.getenv('HOME'), '.local/share/ibus-typing-booster/user.db')
        if (self.user_db_file != ':memory:'
            and not os.path.isdir(os.path.dirname(self.user_db_file))):
                os.makedirs(os.path.dirname(self.user_db_file))
        self._phrase_table_column_names = [
            'id',
            'input_phrase',
            'phrase',
            'p_phrase',
            'pp_phrase',
            'user_freq',
            'timestamp']

        self.old_phrases = []

        self.ime_properties = ImeProperties(config_filename)
        self._language = self.ime_properties.get('language')
        self._normalization_form_internal = 'NFD'

        dictionary_names = [
            x.replace('.dic', '').strip()
            for x in self.ime_properties.get("hunspell_dict").split(',')]
        self.hunspell_obj = hunspell_suggest.Hunspell(dictionary_names)

        if self.user_db_file != ':memory:':
            if not os.path.exists(self.user_db_file):
                sys.stderr.write(
                    "The user database %(udb)s does not exist yet.\n"
                    %{'udb': self.user_db_file})
            else:
                try:
                    desc = self.get_database_desc(self.user_db_file)
                    if (desc == None
                        or desc["version"] != user_database_version
                        or (self.get_number_of_columns_of_phrase_table(self.user_db_file)
                            != len(self._phrase_table_column_names))):
                        sys.stderr.write(
                            "The user database %(udb)s " %{'udb': self.user_db_file}
                            + "seems to be incompatible.\n")
                        if desc == None:
                            sys.stderr.write(
                                "There is no version information in "
                                + "the database.\n")
                        elif desc["version"] != user_database_version:
                            sys.stderr.write(
                                "The version of the database does not match "
                                + "(too old or too new?).\n")
                            sys.stderr.write(
                                "ibus-typing-booster wants version=%s\n"
                                %user_database_version)
                            sys.stderr.write(
                                "But the  database actually has version=%s\n"
                                %desc["version"])
                        elif (self.get_number_of_columns_of_phrase_table(
                                self.user_db_file)
                              != len(self._phrase_table_column_names)):
                            sys.stderr.write(
                                "The number of columns of the database "
                                + "does not match.\n")
                            sys.stderr.write(
                                "ibus-typing-booster expects %(col)s columns.\n"
                                %{'col': len(self._phrase_table_column_names)})
                            sys.stderr.write(
                                "But the database actually has "
                                + "%(col)s columns.\n"
                                %{'col':
                                  self.get_number_of_columns_of_phrase_table(
                                      self.user_db_file)})
                        sys.stderr.write(
                            "Trying to recover the phrases from the old, "
                            + "incompatible database.\n")
                        self.old_phrases = self.extract_user_phrases()
                        timestamp = time.strftime('-%Y-%m-%d_%H:%M:%S')
                        sys.stderr.write(
                            'Renaming the incompatible database to '
                            + '"%(name)s".\n' %{'name': self.user_db_file+timestamp})
                        if os.path.exists(self.user_db_file):
                            os.rename(self.user_db_file, self.user_db_file+timestamp)
                        if os.path.exists(self.user_db_file+'-shm'):
                            os.rename(self.user_db_file+'-shm', self.user_db_file+'-shm'+timestamp)
                        if os.path.exists(self.user_db_file+'-wal'):
                            os.rename(self.user_db_file+'-wal', self.user_db_file+'-wal'+timestamp)
                        sys.stderr.write(
                            "Creating a new, empty database \"%(name)s\".\n"
                            %{'name': self.user_db_file})
                        self.init_user_db()
                        sys.stderr.write(
                            "If user phrases were successfully recovered "
                            + "from the old,\n"
                            + "incompatible database, they will be used to "
                            + "initialize the new database.\n")
                    else:
                        sys.stderr.write(
                            "Compatible database %(db)s found.\n"
                            %{'db': self.user_db_file})
                except:
                    traceback.print_exc()

        # open user phrase database
        try:
            sys.stderr.write(
                "Connect to the database %(name)s.\n" %{'name': self.user_db_file})
            self.db = sqlite3.connect(self.user_db_file)
            self.db.execute('PRAGMA encoding = "UTF-8";')
            self.db.execute('PRAGMA case_sensitive_like = true;')
            self.db.execute('PRAGMA page_size = 4096; ')
            self.db.execute('PRAGMA cache_size = 20000;')
            self.db.execute('PRAGMA temp_store = MEMORY;')
            self.db.execute('PRAGMA journal_mode = WAL;')
            self.db.execute('PRAGMA journal_size_limit = 1000000;')
            self.db.execute('PRAGMA synchronous = NORMAL;')
            self.db.execute('ATTACH DATABASE "%s" AS user_db;' % self.user_db_file)
        except:
            sys.stderr.write(
                "Could not open the database %(name)s.\n" %{'name': self.user_db_file})
            timestamp = time.strftime('-%Y-%m-%d_%H:%M:%S')
            sys.stderr.write(
                "Renaming the incompatible database to \"%(name)s\".\n"
                %{'name': self.user_db_file+timestamp})
            if os.path.exists(self.user_db_file):
                os.rename(self.user_db_file, self.user_db_file+timestamp)
            if os.path.exists(self.user_db_file+'-shm'):
                os.rename(self.user_db_file+'-shm', self.user_db_file+'-shm'+timestamp)
            if os.path.exists(self.user_db_file+'-wal'):
                os.rename(self.user_db_file+'-wal', self.user_db_file+'-wal'+timestamp)
            sys.stderr.write(
                "Creating a new, empty database \"%(name)s\".\n"
                %{'name': self.user_db_file})
            self.init_user_db()
            self.db = sqlite3.connect(self.user_db_file)
            self.db.execute('PRAGMA encoding = "UTF-8";')
            self.db.execute('PRAGMA case_sensitive_like = true;')
            self.db.execute('PRAGMA page_size = 4096; ')
            self.db.execute('PRAGMA cache_size = 20000;')
            self.db.execute('PRAGMA temp_store = MEMORY;')
            self.db.execute('PRAGMA journal_mode = WAL;')
            self.db.execute('PRAGMA journal_size_limit = 1000000;')
            self.db.execute('PRAGMA synchronous = NORMAL;')
            self.db.execute('ATTACH DATABASE "%s" AS user_db;' % self.user_db_file)
        self.create_tables()
        if self.old_phrases:
            sqlargs = []
            for x in self.old_phrases:
                sqlargs.append(
                    {'input_phrase': x[0],
                     'phrase': x[0],
                     'p_phrase': '',
                     'pp_phrase': '',
                     'user_freq': x[1],
                     'timestamp': time.time()})
            sqlstr = '''
            INSERT INTO user_db.phrases (input_phrase, phrase, p_phrase, pp_phrase, user_freq, timestamp)
            VALUES (:input_phrase, :phrase, :p_phrase, :pp_phrase, :user_freq, :timestamp)
            ;'''
            try:
                self.db.executemany(sqlstr, sqlargs)
            except:
                traceback.print_exc()
            self.db.commit()
            self.db.execute('PRAGMA wal_checkpoint;')

        # do not call this always on intialization for the moment.
        # It makes the already slow “python engine/main.py --xml”
        # to list the engines even slower and may break the listing
        # of the engines completely if there is a problem with
        # optimizing the databases. Probably bring this back as an
        # option later if the code in self.optimize_database() is
        # improved to do anything useful.
        #try:
        #    self.optimize_database()
        #except:
        #    print "exception in optimize_database()"
        #    traceback.print_exc ()

        # try create all hunspell-tables in user database
        self.create_indexes(commit = False)
        self.generate_userdb_desc()

    def update_phrase(self, input_phrase = '', phrase = '',
                      p_phrase = '', pp_phrase = '',
                      user_freq=0, commit=True):
        '''
        update the user frequency of a phrase
        '''
        if not input_phrase or not phrase:
            return
        input_phrase = unicodedata.normalize(
            self._normalization_form_internal, input_phrase)
        phrase = unicodedata.normalize(
            self._normalization_form_internal, phrase)
        p_phrase = unicodedata.normalize(
            self._normalization_form_internal, p_phrase)
        pp_phrase = unicodedata.normalize(
            self._normalization_form_internal, pp_phrase)
        sqlstr = '''
        UPDATE user_db.phrases
        SET user_freq = :user_freq, timestamp = :timestamp
        WHERE input_phrase = :input_phrase
         AND phrase = :phrase AND p_phrase = :p_phrase AND pp_phrase = :pp_phrase
        ;'''
        sqlargs = {'user_freq': user_freq,
                   'input_phrase': input_phrase,
                   'phrase': phrase,
                   'p_phrase': p_phrase,
                   'pp_phrase': pp_phrase,
                   'timestamp': time.time()}
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "tabsqlitedb.update_phrase() sqlstr=%s\n" %sqlstr)
            sys.stderr.write(
                "tabsqlitedb.update_phrase() sqlargs=%s\n" %sqlargs)
        try:
            self.db.execute(sqlstr, sqlargs)
            if commit:
                self.db.commit()
        except:
            traceback.print_exc()

    def sync_usrdb (self):
        '''
        Trigger a checkpoint operation.
        '''
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "tabsqlitedb.sync_userdb() "
                + "commit and execute checkpoint ...\n")
        self.db.commit()
        self.db.execute('PRAGMA wal_checkpoint;')
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "tabsqlitedb.sync_userdb() "
                + "commit and execute checkpoint done.\n")

    def create_tables(self):
        '''Create table for the phrases.'''
        sqlstr = '''CREATE TABLE IF NOT EXISTS user_db.phrases
                    (id INTEGER PRIMARY KEY,
                    input_phrase TEXT, phrase TEXT, p_phrase TEXT, pp_phrase TEXT,
                    user_freq INTEGER, timestamp REAL);'''
        self.db.execute(sqlstr)
        self.db.commit()

    def add_phrase(self, input_phrase = '', phrase = '',
                   p_phrase = '', pp_phrase = '',
                   user_freq=0, commit=True):
        '''
        Add phrase to database
        '''
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "tabsqlitedb.add_phrase() "
                + "input_phrase=%s " % input_phrase.encode('UTF-8')
                + "phrase=%s " % phrase.encode('UTF-8')
                + "user_freq=%s " % user_freq
            )
        if not input_phrase or not phrase:
            return
        input_phrase = unicodedata.normalize(
            self._normalization_form_internal, input_phrase)
        phrase = unicodedata.normalize(
            self._normalization_form_internal, phrase)
        p_phrase = unicodedata.normalize(
            self._normalization_form_internal, p_phrase)
        pp_phrase = unicodedata.normalize(
            self._normalization_form_internal, pp_phrase)
        select_sqlstr = '''
        SELECT * FROM user_db.phrases
        WHERE input_phrase = :input_phrase
        AND phrase = :phrase AND p_phrase = :p_phrase AND pp_phrase = :pp_phrase
        ;'''
        select_sqlargs = {
            'input_phrase': input_phrase,
            'phrase': phrase,
            'p_phrase': p_phrase,
            'pp_phrase': pp_phrase}
        if self.db.execute(select_sqlstr, select_sqlargs).fetchall():
            # there is already such a phrase, i.e. add_phrase was called
            # in error, do nothing to avoid duplicate entries.
            return

        insert_sqlstr = '''
        INSERT INTO user_db.phrases
        (input_phrase, phrase, p_phrase, pp_phrase, user_freq, timestamp)
        VALUES (:input_phrase, :phrase, :p_phrase, :pp_phrase, :user_freq, :timestamp)
        ;'''
        insert_sqlargs = {'input_phrase': input_phrase,
                          'phrase': phrase,
                          'p_phrase': p_phrase,
                          'pp_phrase': pp_phrase,
                          'user_freq': user_freq,
                          'timestamp': time.time()}
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "tabsqlitedb.add_phrase() insert_sqlstr=%s\n" %insert_sqlstr)
            sys.stderr.write(
                "tabsqlitedb.add_phrase() insert_sqlargs=%s\n" %insert_sqlargs)
        try:
            self.db.execute (insert_sqlstr, insert_sqlargs)
            if commit:
                self.db.commit()
        except Exception:
            traceback.print_exc()

    def optimize_database (self):
        sqlstr = '''
            CREATE TABLE tmp AS SELECT * FROM %(database)s.phrases;
            DELETE FROM user_db.phrases;
            INSERT INTO user_db.phrases SELECT * FROM tmp ORDER BY
            input_phrase, user_freq DESC, id ASC;
            DROP TABLE tmp;'''
        self.db.executescript (sqlstr)
        self.db.executescript ("VACUUM;")
        self.db.commit()

    def drop_indexes(self):
        '''Drop the index in database to reduce it's size'''
        sqlstr = '''
            DROP INDEX IF EXISTS user_db.phrases_index_p;
            DROP INDEX IF EXISTS user_db.phrases_index_i;
            VACUUM;
            ''' % { 'database':database }

        self.db.executescript (sqlstr)
        self.db.commit()

    def create_indexes(self, commit=True):
        sqlstr = '''
        CREATE INDEX IF NOT EXISTS user_db.phrases_index_p ON phrases
        (input_phrase, id ASC);
        CREATE INDEX IF NOT EXISTS user_db.phrases_index_i ON phrases
        (phrase)
        ;'''
        self.db.executescript (sqlstr)
        if commit:
            self.db.commit()

    def best_candidates(self, phrase_frequencies):
        return sorted(phrase_frequencies.items(),
                      key=lambda x: (
                          -1*x[1],   # user_freq descending
                          len(x[0]), # len(phrase) ascending
                          x[0]       # phrase alphabetical
                      ))[:20]

    def select_words(self, input_phrase, p_phrase = '', pp_phrase = ''):
        '''
        Get phrases from database completing input_phrase.

        Returns a list of matches where each match is a tuple in the
        form of (phrase, user_freq), i.e. returns something like
        [(phrase, user_freq), ...]
        '''
        input_phrase = unicodedata.normalize(
            self._normalization_form_internal, input_phrase)
        p_phrase = unicodedata.normalize(
            self._normalization_form_internal, p_phrase)
        pp_phrase = unicodedata.normalize(
            self._normalization_form_internal, pp_phrase)
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "tabsqlitedb.select_words() "
                + "input_phrase=%s " % input_phrase.encode('UTF-8')
                + "p_phrase=%s " % p_phrase.encode('UTF-8')
                + "pp_phrase=%s\n" % pp_phrase.encode('UTF-8'))
        phrase_frequencies = {}
        phrase_frequencies.update([
            x for x in self.hunspell_obj.suggest(input_phrase)])
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "tabsqlitedb.select_words() hunspell: best_candidates=%s\n"
                %self.best_candidates(phrase_frequencies))
        # Now phrase_frequencies might contain something like this:
        #
        # {'code': 0, 'communicability': 0, 'cold': 0, 'colour': 0}

        # To quote a string to be used as a parameter when assembling
        # an sqlite statement with Python string operations, remove
        # all NUL characters, replace " with "" and wrap the whole
        # string in double quotes. Assembling sqlite statements using
        # parameters containing user input with python string operations
        # is not recommended because of the risk of SQL injection attacks
        # if the quoting is not done the right way. So it is better to use
        # the parameter substitution of the sqlite3 python interface.
        # But unfortunately that does not work when creating views,
        # (“OperationalError: parameters are not allowed in views”).
        quoted_input_phrase = input_phrase.replace(
            '\x00', '').replace('"', '""')
        self.db.execute('DROP VIEW IF EXISTS like_input_phrase_view;')
        sqlstr = '''
        CREATE TEMPORARY VIEW IF NOT EXISTS like_input_phrase_view AS
        SELECT * FROM user_db.phrases
        WHERE input_phrase LIKE "%(quoted_input_phrase)s%%"
        ;''' % {'quoted_input_phrase': quoted_input_phrase}
        self.db.execute(sqlstr)
        sqlargs = {'p_phrase': p_phrase, 'pp_phrase': pp_phrase}
        sqlstr = (
            'SELECT phrase, sum(user_freq) FROM like_input_phrase_view '
            + 'GROUP BY phrase;')
        try:
            # Get “unigram” data from user_db.
            #
            # Example: Let’s assume the user typed “co” and user_db contains
            #
            #     1|colou|colour|green|nice|1
            #     2|col|colour|yellow|ugly|2
            #     3|co|colour|green|awesome|1
            #     4|co|cold|||1
            #     5|conspirac|conspiracy|||5
            #     6|conspi|conspiracy|||1
            #     7|c|conspiracy|||1
            results_uni = self.db.execute(sqlstr, sqlargs).fetchall()
            # Then the result returned by .fetchall() is:
            #
            # [('colour', 4), ('cold', 1), ('conspiracy', 6)]
            #
            # (“c|conspiracy|1” is not selected because it doesn’t
            # match the user input “LIKE co%”! I.e. this is filtered
            # out by the VIEW created above already)
        except:
            traceback.print_exc()
        if not results_uni:
            # If no unigrams matched, bigrams and trigrams cannot
            # match either. We can stop here and return what we got
            # from hunspell.
            return self.best_candidates(phrase_frequencies)
        # Now normalize the unigram frequencies with the total count
        # (which is 11 in the above example), which gives us the
        # normalized result:
        # [('colour', 4/11), ('cold', 1/11), ('conspiracy', 6/11)]
        sqlstr = 'SELECT sum(user_freq) FROM like_input_phrase_view;'
        try:
            count = self.db.execute(sqlstr, sqlargs).fetchall()[0][0]
        except:
            traceback.print_exc()
        # Updating the phrase_frequency dictionary with the normalized
        # results gives: {'conspiracy': 6/11, 'code': 0,
        # 'communicability': 0, 'cold': 1/11, 'colour': 4/11}
        for x in results_uni:
            phrase_frequencies.update([(x[0], x[1]/float(count))])
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "tabsqlitedb.select_words() Unigram best_candidates=%s\n"
                %self.best_candidates(phrase_frequencies))
        if not p_phrase:
            # If no context for bigram matching is available, return
            # what we have so far:
            return self.best_candidates(phrase_frequencies)
        sqlstr = (
            'SELECT phrase, sum(user_freq) FROM like_input_phrase_view '
            + 'WHERE p_phrase = :p_phrase GROUP BY phrase;')
        try:
            results_bi = self.db.execute(sqlstr, sqlargs).fetchall()
        except:
            traceback.print_exc()
        if not results_bi:
            # If no bigram could be matched, return what we have so far:
            return self.best_candidates(phrase_frequencies)
        # get the total count of p_phrase to normalize the bigram frequencies:
        sqlstr = (
            'SELECT sum(user_freq) FROM like_input_phrase_view '
            + 'WHERE p_phrase = :p_phrase;')
        try:
            count_p_phrase = self.db.execute(sqlstr, sqlargs).fetchall()[0][0]
        except:
            traceback.print_exc()
        # Update the phrase frequency dictionary by using a linear
        # combination of the unigram and the bigram results, giving
        # both the weight of 0.5:
        for x in results_bi:
            phrase_frequencies.update(
                [(x[0],
                  0.5*x[1]/float(count_p_phrase)
                  +0.5*phrase_frequencies[x[0]])])
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "tabsqlitedb.select_words() Bigram best_candidates=%s\n"
                %self.best_candidates(phrase_frequencies))
        if not pp_phrase:
            # If no context for trigram matching is available, return
            # what we have so far:
            return self.best_candidates(phrase_frequencies)
        sqlstr = ('SELECT phrase, sum(user_freq) FROM like_input_phrase_view '
                  + 'WHERE p_phrase = :p_phrase '
                  + 'AND pp_phrase = :pp_phrase GROUP BY phrase;')
        try:
            results_tri = self.db.execute(sqlstr, sqlargs).fetchall()
        except:
            traceback.print_exc()
        if not results_tri:
            # if no trigram could be matched, return what we have so far:
            return self.best_candidates(phrase_frequencies)
        # get the total count of (p_phrase, pp_phrase) pairs to
        # normalize the bigram frequencies:
        sqlstr = (
            'SELECT sum(user_freq) FROM like_input_phrase_view '
            + 'WHERE p_phrase = :p_phrase AND pp_phrase = :pp_phrase;')
        try:
            count_pp_phrase_p_phrase = self.db.execute(
                sqlstr, sqlargs).fetchall()[0][0]
        except:
            traceback.print_exc()
        # Update the phrase frequency dictionary by using a linear
        # combination of the bigram and the trigram results, giving
        # both the weight of 0.5 (that makes the total weights: 0.25 *
        # unigram + 0.25 * bigram + 0.5 * trigram, i.e. the trigrams
        # get higher weight):
        for x in results_tri:
            phrase_frequencies.update(
                [(x[0],
                  0.5*x[1]/float(count_pp_phrase_p_phrase)
                  +0.5*phrase_frequencies[x[0]])])
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "tabsqlitedb.select_words() Trigram best_candidates=%s\n"
                %self.best_candidates(phrase_frequencies))
        return self.best_candidates(phrase_frequencies)

    def generate_userdb_desc (self):
        try:
            sqlstring = ('CREATE TABLE IF NOT EXISTS user_db.desc '
                         + '(name PRIMARY KEY, value);')
            self.db.executescript (sqlstring)
            sqlstring = 'INSERT OR IGNORE INTO user_db.desc  VALUES (?, ?);'
            self.db.execute (sqlstring, ('version', user_database_version))
            sqlstring = (
                'INSERT OR IGNORE INTO user_db.desc '
                + 'VALUES (?, DATETIME("now", "localtime"));')
            self.db.execute (sqlstring, ("create-time", ))
            self.db.commit ()
        except:
            traceback.print_exc ()

    def init_user_db(self):
        if self.user_db_file == ':memory:':
            return
        if not path.exists(self.user_db_file):
            db = sqlite3.connect(self.user_db_file)
            db.execute('PRAGMA encoding = "UTF-8";')
            db.execute('PRAGMA case_sensitive_like = true;')
            db.execute('PRAGMA page_size = 4096;')
            # a database containing the complete German Hunspell
            # dictionary has less then 6000 pages. 20000 pages
            # should be enough to cache the complete database
            # in most cases.
            db.execute('PRAGMA cache_size = 20000;')
            db.execute('PRAGMA temp_store = MEMORY; ')
            db.execute('PRAGMA journal_mode = WAL;')
            db.execute('PRAGMA journal_size_limit = 1000000;')
            db.execute('PRAGMA synchronous = NORMAL;')
            db.commit()

    def get_database_desc(self, db_file):
        '''Get the description of the database'''
        if not path.exists(db_file):
            return None
        try:
            db = sqlite3.connect(db_file)
            desc = {}
            for row in db.execute("SELECT * FROM desc;").fetchall():
                desc[row[0]] = row[1]
            db.close()
            return desc
        except:
            return None

    def get_number_of_columns_of_phrase_table(self, db_file):
        '''
        Get the number of columns in the 'phrases' table in
        the database in db_file.

        Determines the number of columns by parsing this:

        sqlite> select sql from sqlite_master where name='phrases';
CREATE TABLE phrases (id INTEGER PRIMARY KEY, input_phrase TEXT, phrase TEXT, p_phrase TEXT, pp_phrase TEXT, user_freq INTEGER, timestamp REAL)
        sqlite>

        This result could be on a single line, as above, or on multiple
        lines.
        '''
        if not path.exists(db_file):
            return None
        try:
            db = sqlite3.connect(db_file)
            tp_res = db.execute(
                "select sql from sqlite_master where name='phrases';"
            ).fetchall()
            # Remove possible line breaks from the string where we
            # want to match:
            string = ' '.join(tp_res[0][0].splitlines())
            res = re.match(r'.*\((.*)\)', string)
            if res:
                tp = res.group(1).split(',')
                return len(tp)
            else:
                return 0
        except:
            return 0

    def check_phrase_and_update_frequency(
            self, input_phrase = '', phrase = '', p_phrase = '',
            pp_phrase = '', commit=True):
        '''
        Check whether input_phrase and phrase are already in database. If
        they are in the database, increase the frequency by 1, if not
        add them.
        '''
        if not input_phrase:
            input_phrase = phrase
        if not phrase:
            return
        phrase = unicodedata.normalize(
            self._normalization_form_internal, phrase)
        p_phrase = unicodedata.normalize(
            self._normalization_form_internal, p_phrase)
        pp_phrase = unicodedata.normalize(
            self._normalization_form_internal, pp_phrase)
        input_phrase = unicodedata.normalize(
            self._normalization_form_internal, input_phrase)

        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "tabsqlitedb.check_phrase_and_update_frequency() "
                + "phrase=%(p)s, input_phrase=%(t)s\n"
                %{'p': phrase.encode('UTF-8'),
                  't': input_phrase.encode('UTF-8')})

        # There should never be more than 1 database row for the same
        # input_phrase *and* phrase. So the following query on
        # the database should match at most one database
        # row and the length of the result array should be 0 or
        # 1. So the “GROUP BY phrase” is actually redundant. It is
        # only a safeguard for the case when duplicate rows have been
        # added to the database accidentally (But in that case there
        # is a bug somewhere else which should be fixed).
        sqlstr = '''
        SELECT max(user_freq) FROM user_db.phrases
        WHERE input_phrase = :input_phrase
        AND phrase = :phrase AND p_phrase = :p_phrase AND pp_phrase = :pp_phrase
        GROUP BY phrase
        ;'''
        sqlargs = {'input_phrase': input_phrase,
                   'phrase': phrase,
                   'p_phrase': p_phrase,
                   'pp_phrase': pp_phrase}
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "tabsqlitedb.check_phrase_and_update_frequency() sqlstr=%s\n"
                %sqlstr)
            sys.stderr.write(
                "tabsqlitedb.check_phrase_and_update_frequency() sqlargs=%s\n"
                %sqlargs)
        result = self.db.execute(sqlstr, sqlargs).fetchall()
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "check_phrase_and_update_frequency() result=%s\n" %result)
        if len(result) > 0:
            # A match was found in user_db, increase user frequency by 1
            self.update_phrase(input_phrase = input_phrase,
                               phrase = phrase,
                               p_phrase = p_phrase,
                               pp_phrase = pp_phrase,
                               user_freq = result[0][0]+1,
                               commit=commit)
            return
        # The phrase was not found in user_db.
        # Add it as a new phrase, i.e. with user_freq = 1:
        self.add_phrase(input_phrase = input_phrase,
                        phrase = phrase,
                        p_phrase = p_phrase,
                        pp_phrase = pp_phrase,
                        user_freq = 1,
                        commit=commit)
        return

    def remove_phrase(self, input_phrase = '', phrase = '', commit = True):
        '''
        Remove all rows matching “input_phrase” and “phrase” from database.
        Or, if “input_phrase” is “None”, remove all rows matching “phrase”
        no matter for what input phrase from the database.
        '''
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "tabsqlitedb.remove_phrase() phrase=%(p)s\n"
                %{'p': phrase.encode('UTF-8')})
        if not phrase:
            return
        phrase = unicodedata.normalize(
            self._normalization_form_internal, phrase)
        if input_phrase:
            input_phrase = unicodedata.normalize(
                self._normalization_form_internal, input_phrase)
        if input_phrase:
            delete_sqlstr = '''
            DELETE FROM user_db.phrases
            WHERE input_phrase = :input_phrase AND phrase = :phrase
            ;'''
        else:
            delete_sqlstr = '''
            DELETE FROM user_db.phrases
            WHERE phrase = :phrase
            ;'''
        delete_sqlargs = {'input_phrase': input_phrase, 'phrase': phrase}
        self.db.execute(delete_sqlstr, delete_sqlargs)
        if commit:
            self.db.commit()

    def extract_user_phrases(self):
        '''extract user phrases from database'''
        try:
            db = sqlite3.connect(self.user_db_file)
            db.execute('PRAGMA wal_checkpoint;')
            phrases = db.execute(
                'SELECT phrase, sum(user_freq) FROM phrases GROUP BY phrase;'
            ).fetchall()
            db.close()
            phrases = [
                (unicodedata.normalize(
                    self._normalization_form_internal, x[0]), x[1])
                for x in
                phrases
            ]
            return phrases[:]
        except:
            traceback.print_exc()
            return []

    def read_training_data_from_file(self, filename):
        if not os.path.isfile(filename):
            return False
        rows = self.db.execute(
            'SELECT input_phrase, phrase, p_phrase, pp_phrase, '
            + 'user_freq, timestamp FROM phrases;').fetchall()
        p_token = ''
        pp_token = ''
        database_dict = {}
        for x  in rows:
            database_dict.update([((x[0], x[1], x[2], x[3]),
                                   {'input_phrase': x[0],
                                    'phrase': x[1],
                                    'p_phrase': x[2],
                                    'pp_phrase': x[3],
                                    'user_freq': x[4],
                                    'timestamp': x[5]}
                               )])
        with codecs.open(filename, encoding='UTF-8') as file_handle:
            lines = [
                unicodedata.normalize(self._normalization_form_internal, x)
                for x in file_handle.readlines()]
            for line in lines:
                for token in itb_util.tokenize(line):
                    key = (token, token, p_token, pp_token)
                    if key in database_dict:
                        database_dict[key]['user_freq'] += 1
                        database_dict[key]['timestamp'] = time.time()
                    else:
                        database_dict[key] = {'input_phrase': token,
                                              'phrase': token,
                                              'p_phrase': p_token,
                                              'pp_phrase': pp_token,
                                              'user_freq': 1,
                                              'timestamp': time.time()}
                    pp_token = p_token
                    p_token = token
        sqlargs = []
        for x in database_dict.keys():
            sqlargs.append(database_dict[x])
        sqlstr = '''
        INSERT INTO user_db.phrases (input_phrase, phrase, p_phrase, pp_phrase, user_freq, timestamp)
        VALUES (:input_phrase, :phrase, :p_phrase, :pp_phrase, :user_freq, :timestamp)
        ;'''
        try:
            self.db.execute('DELETE FROM phrases;')
            # Without the following commit, the self.db.executemany() fails
            # with “OperationalError: database is locked”.
            self.db.commit()
            self.db.executemany(sqlstr, sqlargs)
            self.db.commit()
            self.db.execute('PRAGMA wal_checkpoint;')
        except:
            traceback.print_exc()
            return False
        return True

    def remove_all_phrases(self):
        try:
            self.db.execute('DELETE FROM phrases;')
            self.db.commit()
            self.db.execute('PRAGMA wal_checkpoint;')
        except:
            traceback.print_exc()

    def dump_database(self):
        '''
        Dump the contents of the database to stderr

        (For debugging)
        '''
        try:
            sys.stderr.write('SELECT * FROM desc;\n')
            for row in self.db.execute("SELECT * FROM desc;").fetchall():
                sys.stderr.write('%s\n' %repr(row))
            sys.stderr.write('SELECT * FROM phrases;\n')
            for row in self.db.execute("SELECT * FROM phrases;").fetchall():
                sys.stderr.write('%s\n' %repr(row))
        except:
            import traceback
            traceback.print_exc()
            return
