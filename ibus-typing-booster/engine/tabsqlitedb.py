# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 2011-2012 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012 Mike FABIAN <mfabian@redhat.com>
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
import sqlite3
import uuid
import time
import re
import hunspell_suggest

user_database_version = '0.61'

patt_r = re.compile(r'c([ea])(\d):(.*)')
patt_p = re.compile(r'p(-{0,1}\d)(-{0,1}\d)')

class ImeProperties:
    def __init__(self, configfile_path=None):
        '''
        configfile_path is the full path to the config file, for example
        “/usr/share/ibus-typing-booster/hunspell-tables/en_US.conf”
        '''
        self.ime_property_cache = {}
        if configfile_path.find('typing-booster:') > 0:
            configfile_path=configfile_path.replace(
                'typing-booster:','')
        if os.path.exists(configfile_path) and os.path.isfile(configfile_path):
            comment_patt = re.compile('^#')
            for line in file(configfile_path):
                if not comment_patt.match(line):
                    attr,val = line.strip().split ('=', 1)
                    self.ime_property_cache[attr.strip()]= val.strip()
        else:
            sys.stderr.write("Error: ImeProperties: No such file: %s" %configfile_path)

    def get(self, key):
        if key in self.ime_property_cache:
            return self.ime_property_cache[key]
        else:
            return None

class tabsqlitedb:
    '''Phrase databases for ibus-typing-booster

    The phrases tables in the databases have columns with the names:

    “id”, “mlen”, “clen”, “input_phrase”, “phrase”, “freq”, “user_freq”

    There are 3 databases, sysdb, userdb, mudb.

    Overview over the meaning of values in the “freq” and “user_freq” columns:

              freq                   user_freq
    sysdb      1                     0

    user_db    0 system phrase       >= 1
              -1 user phrase         >= 1
    mudb
               2 new system phrase   >= 1
               1 old system phrase   >= 1
              -2 new user phrase     >= 1
              -3 old user phrase     >= 1

    sysdb: “Database” with the suggestions from the hunspell dictionaries
        user_freq = 0 always.
        freq      = 1 always.

        Actually there is no Sqlite3 database called “sysdb”, these
        are the suggestions coming from hunspell_suggest, i.e. from
        grepping the hunspell dictionaries and from pyhunspell. But
        these suggestions are supplied as tuples or lists in the same
        form as the database rows (Historic note: ibus-typing-booster
        started as a fork of ibus-table, in ibus-table “sysdb” is a
        Sqlite3 database which is installed systemwide and readonly
        for the user)

    user_db: Database on disk where the phrases learned from the user are stored
        user_freq >= 1: The number of times the user has used this phrase
        freq = -1: user defined phrase, hunspell_suggest does not suggest
                   a phrase like this.
        freq = 0:  system phrase, hunspell_suggest does suggest
                   such a phrase.

        (Note: If the hunspell dictionary is updated, what could be suggested
        by hunspell might change. Is it necessary to update the contents
        of user_db then to reflect this?)

        Data is written to user_db only when ibus-typing-booster exits.
        Until then, the data learned from the user is stored only in mudb.

    mudb: Database in memory where the phrases learned from the user are stored
        user_freq >= 1: The number of times the user has used this phrase
        freq =  2: new system phrase, i.e. this phrase originally came from
                   hunspell_suggest during the current session, it did not
                   come from user_db.
        freq =  1: old system phrase, i.e. this phrase came from user_db
                   but  was marked there with “freq = 0”, i.e. it is a
                   phrase which could be suggest by hunspell_suggest.
        freq = -2: new user phrase, i.e. this is a phrase which hunspell_suggest
                   cannot suggest and which was typed by the user in the current
                   session.
        freq = -3: old user phrase, i.e. this is also a phrase which hunspell_suggest
                   cannot suggest. But it was already typed by the user in a previous
                   session and has been saved on exit of ibus-typing-booster
                   to user_db. The current session got it from user_db.
    '''
    def __init__(self, name = 'table.db', user_db = None, filename = None ):
        # use filename when you are creating db from source
        # use name when you are using db
        self._phrase_table_column_names = ['id', 'mlen', 'clen', 'input_phrase', 'phrase','freq','user_freq']

        self.old_phrases=[]

        self._conf_file_path = "/usr/share/ibus-typing-booster/hunspell-tables/"

        self.ime_properties = ImeProperties(self._conf_file_path+filename)

        # share variables in this class:
        self._mlen = int(self.ime_properties.get("max_key_length"))

        self._m17ndb = 'm17n'
        self._m17n_mim_name = ""
        self.lang_chars = self.ime_properties.get('lang_chars')
        if self.lang_chars != None:
            self.lang_chars = self.lang_chars.decode('utf8')
        else:
            self.lang_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

        self.encoding = self.ime_properties.get('encoding')

        self.hunspell_obj = hunspell_suggest.Hunspell(
            lang=self.ime_properties.get('languages'),
            dict_name=self.ime_properties.get("hunspell_dict"),
            aff_name=self.ime_properties.get("hunspell_dict").replace('.dic', '.aff'),
            encoding=self.encoding,
            lang_chars=self.lang_chars)

        self.startchars = self.get_start_chars ()
        user_db = self.ime_properties.get("name")+'-user.db'
        # user database:
        if user_db != None:
            home_path = os.getenv ("HOME")
            tables_path = path.join (home_path, ".local/share/.ibus",  "hunspell-tables")
            if not path.isdir (tables_path):
                os.makedirs (tables_path)
            user_db = path.join (tables_path, user_db)
            if not path.exists(user_db):
                sys.stderr.write("The user database %(udb)s does not exist yet.\n" %{'udb': user_db})
            else:
                try:
                    desc = self.get_database_desc (user_db)
                    if desc == None \
                        or desc["version"] != user_database_version \
                        or self.get_number_of_columns_of_phrase_table(user_db) != len(self._phrase_table_column_names):
                        sys.stderr.write("The user database %(udb)s seems to be incompatible.\n" %{'udb': user_db})
                        if desc == None:
                            sys.stderr.write("There is no version information in the database.\n")
                        elif desc["version"] != user_database_version:
                            sys.stderr.write("The version of the database does not match (too old or too new?).\n")
                            sys.stderr.write("ibus-typing-booster wants version=%s\n" %user_database_version)
                            sys.stderr.write("But the  database actually has version=%s\n" %desc["version"])
                        elif self.get_number_of_columns_of_phrase_table(user_db) != len(self._phrase_table_column_names):
                            sys.stderr.write("The number of columns of the database does not match.\n")
                            sys.stderr.write("ibus-typing-booster expects %(col)s columns.\n"
                                %{'col': len(self._phrase_table_column_names)})
                            sys.stderr.write("But the database actually has %(col)s columns.\n"
                                %{'col': self.get_number_of_columns_of_phrase_table(user_db)})
                        sys.stderr.write("Trying to recover the phrases from the old, incompatible database.\n")
                        self.old_phrases = self.extract_user_phrases( user_db )
                        new_name = "%s.%d" %(user_db, os.getpid())
                        sys.stderr.write("Renaming the incompatible database to \"%(name)s\".\n" %{'name': new_name})
                        os.rename(user_db, new_name)
                        sys.stderr.write("Creating a new, empty database \"%(name)s\".\n"  %{'name': user_db})
                        self.init_user_db(user_db)
                        sys.stderr.write("If user phrases were successfully recovered from the old,\n")
                        sys.stderr.write("incompatible database, they will be used to initialize the new database.\n")
                    else:
                        sys.stderr.write("Compatible database %(db)s found.\n" %{'db': user_db})
                except:
                    import traceback
                    traceback.print_exc()
        else:
            user_db = ":memory:"

        # open user phrase database
        try:
            sys.stderr.write("Connect to the database %(name)s.\n" %{'name': user_db})
            self.db = sqlite3.connect(user_db)
            self.db.execute('PRAGMA page_size = 8192; ')
            self.db.execute('PRAGMA cache_size = 20000; ')
            self.db.execute('PRAGMA temp_store = MEMORY; ')
            self.db.execute('PRAGMA synchronous = OFF; ')
            self.db.execute('ATTACH DATABASE "%s" AS user_db;' % user_db)
        except:
            sys.stderr.write("Could not open the database %(name)s.\n" %{'name': user_db})
            new_name = "%s.%d" %(user_db, os.getpid())
            sys.stderr.write("Renaming the incompatible database to \"%(name)s\".\n" %{'name': new_name})
            os.rename(user_db, new_name)
            sys.stderr.write("Creating a new, empty database \"%(name)s\".\n"  %{'name': user_db})
            self.init_user_db(user_db)
            self.db.execute('ATTACH DATABASE "%s" AS user_db;' % user_db)
        self.create_tables("user_db")
        if self.old_phrases:
            # (mlen, phrase, freq, user_freq)
            phrases = filter(lambda x: x[0] > 1, self.old_phrases)
            phrases = map(lambda x: [x[1]] + list(x[1:]), phrases)
            map(self.u_add_phrase, phrases)
            self.db.commit()

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
        #    import traceback
        #    traceback.print_exc ()

        # try create all hunspell-tables in user database
        self.create_indexes ("user_db",commit=False)
        self.generate_userdb_desc ()

        # attach mudb for working process
        mudb = ":memory:"
        self.db.execute ('ATTACH DATABASE "%s" AS mudb;' % mudb )
        self.create_tables ("mudb")

    def __parse_conf_file(self,conf_file="/usr/share/ibus-typing-booster/hunspell-tables/en_US.conf"):
        key_val_dict = {}
        if conf_file.find('typing-booster:') > 0 :
            conf_file=conf_file.replace('typing-booster:','')
        comment_patt = re.compile('^#')
        for line in file(conf_file):
            if not comment_patt.match(line):
                attr,val = line.strip().split ('=', 1)
                key_val_dict[attr.strip()]= val.strip()
        return key_val_dict

    def update_phrase (self, entry, database='user_db'):
        '''update phrase freqs'''
        input_phrase, phrase, freq, user_freq = entry
        sqlstr = '''UPDATE %(database)s.phrases
                    SET user_freq = %(user_freq)s
                    WHERE mlen = %(mlen)s
                    AND clen = %(clen)s
                    AND input_phrase = "%(input_phrase)s"
                    AND phrase = "%(phrase)s";
        ''' %{'database':database,
              'user_freq': user_freq,
              'mlen': len(input_phrase),
              'clen': len(phrase),
              'input_phrase': input_phrase,
              'phrase': phrase}
        self.db.execute(sqlstr)
        self.db.commit()

    def sync_usrdb (self):
        # we need to update the user_db
        #print 'sync userdb'
        mudata = self.db.execute ('SELECT * FROM mudb.phrases;').fetchall()
        data_u = filter ( lambda x: x[-2] in [1,-3], mudata)
        data_a = filter ( lambda x: x[-2]==2, mudata)
        data_n = filter ( lambda x: x[-2]==-2, mudata)
        data_u = map (lambda x: (x[3],x[-3],x[-2],x[-1] ), data_u)
        data_a = map (lambda x: (x[3],x[-3],0,x[-1] ), data_a)
        data_n = map (lambda x: (x[3],x[-3],-1,x[-1] ), data_n)
        map (self.update_phrase, data_u)
        #print self.db.execute('select * from user_db.phrases;').fetchall()
        map (self.u_add_phrase,data_a)
        map (self.u_add_phrase,data_n)
        self.db.commit ()

    def create_tables (self, database):
        '''Create table for the phrases.'''
        try:
            self.db.execute( 'PRAGMA cache_size = 20000; ' )
            # increase the cache size to speedup sqlite enquiry
        except:
            pass
        sqlstr = '''CREATE TABLE IF NOT EXISTS %s.phrases
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mlen INTEGER, clen INTEGER,
                    input_phrase TEXT, phrase TEXT,
                    freq INTEGER, user_freq INTEGER);''' % database
        self.db.execute(sqlstr)
        self.db.commit()

    def get_start_chars (self):
        '''return possible start chars of IME'''
        try:
            return self.ime_properties.get('start_chars')
        except:
            return ''

    def u_add_phrase (self,nphrase):
        '''Add a phrase to userdb'''
        self.add_phrase (nphrase,database='user_db',commit=False)

    def add_phrase (self, aphrase, database = 'main',commit=True):
        '''
        Add phrase to database, phrase is a object of
        (input_phrase, phrase, freq ,user_freq)
        '''
        try:
            input_phrase,phrase,freq,user_freq = aphrase
        except:
            input_phrase,phrase,freq = aphrase
            user_freq = 0

        select_sqlstr= '''
        SELECT * FROM %(database)s.phrases
        WHERE input_phrase = :input_phrase AND phrase = :phrase
        ;'''  %{'database': database}
        select_sqlargs = {'input_phrase': input_phrase, 'phrase': phrase}
        if self.db.execute(select_sqlstr, select_sqlargs).fetchall():
            # there is already such a phrase, i.e. add_phrase was called
            # in error, do nothing to avoid duplicate entries.
            return

        insert_sqlstr = '''
        INSERT INTO %(database)s.phrases
        (mlen, clen, input_phrase, phrase, freq, user_freq)
        VALUES ( :mlen, :clen, :input_phrase, :phrase, :freq, :user_freq)
        ;''' %{'database': database}
        insert_sqlargs = {'mlen': len(input_phrase), 'clen': len(phrase),
                          'input_phrase': input_phrase, 'phrase': phrase,
                          'freq': freq, 'user_freq': user_freq}
        try:
            self.db.execute (insert_sqlstr, insert_sqlargs)
            if commit:
                self.db.commit()
        except Exception:
            import traceback
            traceback.print_exc()

    def optimize_database (self, database='main'):
        sqlstr = '''
            CREATE TABLE tmp AS SELECT * FROM %(database)s.phrases;
            DELETE FROM %(database)s.phrases;
            INSERT INTO %(database)s.phrases SELECT * FROM tmp ORDER BY
            input_phrase, mlen ASC, user_freq DESC, freq DESC, id ASC;
            DROP TABLE tmp;''' %{'database':database,}
        self.db.executescript (sqlstr)
        self.db.executescript ("VACUUM;")
        self.db.commit()

    def drop_indexes(self, database):
        '''Drop the index in database to reduce it's size'''
        sqlstr = '''
            DROP INDEX IF EXISTS %(database)s.phrases_index_p;
            DROP INDEX IF EXISTS %(database)s.phrases_index_i;
            VACUUM;
            ''' % { 'database':database }

        self.db.executescript (sqlstr)
        self.db.commit()

    def create_indexes(self, database, commit=True):
        sqlstr = '''
            CREATE INDEX IF NOT EXISTS %(database)s.phrases_index_p ON phrases
            (input_phrase, mlen ASC, freq DESC, id ASC);
            CREATE INDEX IF NOT EXISTS %(database)s.phrases_index_i ON phrases
            (phrase, mlen ASC);''' %{'database':database}
        self.db.executescript (sqlstr)
        if commit:
            self.db.commit()

    def select_words(self, input_phrase):
        '''
        Get phrases from database by tab_key objects
        ( which should be equal or less than the max key length)
        This method is called in hunspell_table.py by passing UserInput held data
        Returns a list of matches where each match is a tuple
        in the form of a database row, i.e. returns something like
        [(id, mlen, clen, input_phrase, phrase, freq, user_freq), ...]
        '''
        if type(input_phrase) != type(u''):
            input_phrase = input_phrase.decode('utf8')
        # limit length of input phrase to max key length
        # (Now that the  input_phrase is stored in a single
        # column of type TEXT in sqlite3, this limit can be set as high
        # as the maximum string length in sqlite3
        # (by default 10^9, see http://www.sqlite.org/limits.html))
        input_phrase = input_phrase[:self._mlen]
        sqlstr = '''SELECT * FROM user_db.phrases WHERE phrase LIKE "%(input_phrase)s%%"
                    UNION ALL
                    SELECT  * FROM mudb.phrases WHERE phrase LIKE "%(input_phrase)s%%"
                    ORDER BY user_freq DESC, freq DESC, id ASC, mlen ASC
                    limit 1000;''' %{'input_phrase': input_phrase}
        result = self.db.execute(sqlstr).fetchall()
        hunspell_list = self.hunspell_obj.suggest(input_phrase)
        for ele in hunspell_list:
            result.append(tuple(ele))

        usrdb={}
        mudb={}
        sysdb={}
        map(lambda x: sysdb.update([(x[3:-2],x[:])]), filter(lambda x: not x[-1], result))
        map(lambda x: usrdb.update([(x[3:-2], x[:])]), filter(lambda x: (x[-2] in [0,-1]) and x[-1], result))
        map(lambda x: mudb.update([(x[3:-2], x[:])]), filter(lambda x: (x[-2] not in [0,-1]) and x[-1], result))

        _cand = mudb.values()
        map(_cand.append, filter(lambda x: x, map(lambda key: key not in mudb and usrdb[key], usrdb)))
        map(_cand.append, filter(lambda x: x, map(lambda key: key not in mudb and key not in usrdb and sysdb[key], sysdb)))
        _cand.sort(cmp=(lambda x,y:
                        -(cmp(x[-1], y[-1]))    # user_freq descending
                        or (cmp(x[1], y[1]))    # len(input_phrase) ascending
                        or -(cmp(x[-2], y[-2])) # freq descending
                        or (cmp(x[0], y[0]))    # id ascending
                    ))
        return _cand[:]


    def get_all_values(self,d_name='main',t_name='inks'):
        sqlstr = 'SELECT * FROM '+d_name+'.'+t_name+';'
        _result = self.db.execute( sqlstr).fetchall()
        return _result

    def get_phrase_table_column_names (self):
        '''get a list of phrase table columns name'''
        return self._phrase_table_column_names[:]

    def generate_userdb_desc (self):
        try:
            sqlstring = 'CREATE TABLE IF NOT EXISTS user_db.desc (name PRIMARY KEY, value);'
            self.db.executescript (sqlstring)
            sqlstring = 'INSERT OR IGNORE INTO user_db.desc  VALUES (?, ?);'
            self.db.execute (sqlstring, ('version', user_database_version))
            sqlstring = 'INSERT OR IGNORE INTO user_db.desc  VALUES (?, DATETIME("now", "localtime"));'
            self.db.execute (sqlstring, ("create-time", ))
            self.db.commit ()
        except:
            import traceback
            traceback.print_exc ()

    def init_user_db (self,db_file):
        if not path.exists (db_file):
            db = sqlite3.connect (db_file)
            db.execute('PRAGMA page_size = 4096;')
            db.execute( 'PRAGMA cache_size = 20000;' )
            db.execute( 'PRAGMA temp_store = MEMORY; ' )
            db.execute( 'PRAGMA synchronous = OFF; ' )
            db.commit()

    def get_database_desc(self, db_file):
        if not path.exists(db_file):
            return None
        try:
            db = sqlite3.connect(db_file)
            desc = {}
            for row in db.execute("SELECT * FROM desc;").fetchall():
                desc[row[0]] = row[1]
            return desc
        except:
            return None

    def get_number_of_columns_of_phrase_table(self, db_file):
        '''
        Get the number of columns in the 'phrases' table in
        the database in db_file.

        Determines the number of columns by parsing this:

        sqlite> select sql from sqlite_master where name='phrases';
CREATE TABLE phrases (id INTEGER PRIMARY KEY AUTOINCREMENT,                mlen INTEGER, clen INTEGER, input_phrase TEXT, phrase TEXT, freq INTEGER, user_freq INTEGER)
        sqlite>

        This result could be on a single line, as above, or on multiple
        lines.
        '''
        if not path.exists (db_file):
            return 0
        try:
            db = sqlite3.connect (db_file)
            tp_res = db.execute(
                "select sql from sqlite_master where name='phrases';"
            ).fetchall()
            # Remove possible line breaks from the string where we
            # want to match:
            str = ' '.join(tp_res[0][0].splitlines())
            res = re.match(r'.*\((.*)\)', str)
            if res:
                tp = res.group(1).split(',')
                return len(tp)
            else:
                return 0
        except:
            return 0

    def check_phrase(self, phrase, input_phrase=None, database='main'):
        '''Check word freq and user_freq
        '''
        if type(phrase) != type(u''):
            phrase = phrase.decode('utf8')
        if type(input_phrase) != type(u''):
            input_phrase = input_phrase.decode('utf8')

        if len(phrase) < 4:
            return

        sqlstr = '''
                SELECT * FROM user_db.phrases WHERE phrase = "%(phrase)s" and input_phrase = "%(input_phrase)s"
                UNION ALL
                SELECT * FROM mudb.phrases WHERE phrase = "%(phrase)s" and input_phrase = "%(input_phrase)s"
                ORDER BY user_freq DESC, freq DESC, id ASC;''' %{'phrase': phrase, 'input_phrase': input_phrase}
        result = self.db.execute(sqlstr).fetchall()
        # If phrase is among the suggestions of self.hunspell_obj.suggest(input_phrase)
        # append it to results:
        filter(lambda x: x[-3] == phrase and result.append(tuple(x)),
               self.hunspell_obj.suggest(input_phrase))
        if len(result) == 0:
            # The phrase was neither found in user_db nor mudb nor
            # does hunspell_obj.suggest(input_phrase) suggest such
            # a phrase. Therefore, it is a completely new, user
            # defined phrase and we add it into mudb:
            self.add_phrase((input_phrase,phrase,-2,1), database = 'mudb')

        sysdb = {}
        usrdb = {}
        mudb = {}
        map(lambda x: sysdb.update([(x[3:-2],x[:])]), filter(lambda x: not x[-1], result))
        map(lambda x: usrdb.update([(x[3:-2], x[:])]), filter(lambda x: (x[-2] in [0,-1]) and x[-1], result))
        map(lambda x: mudb.update([(x[3:-2], x[:])]), filter(lambda x: (x[-2] not in [0,-1]) and x[-1], result))

        # we remove the keys already contained in mudb{} from usrdb{}
        map(usrdb.pop, filter(lambda key: key in mudb, usrdb.keys()))
        # we remove the keys already contained in mudb{} or usrdb{} from sysdb{}
        map(sysdb.pop, filter(lambda key: key in mudb or key in usrdb, sysdb.keys()))

        map(lambda res: self.add_phrase((res[0],phrase,(-3 if usrdb[res][-2] == -1 else 1),usrdb[res][-1]+1), database = 'mudb'), usrdb.keys())
        map(lambda res: self.add_phrase((res[0],phrase,2,1), database = 'mudb'), sysdb.keys())

        map(lambda key:
            self.update_phrase((mudb[key][3], mudb[key][4], mudb[key][5], mudb[key][6]+1),
                               database='mudb'),
            mudb.keys())

    def remove_phrase (self,phrase,database='user_db'):
        '''
        Remove phrase from database.
        phrase should be a tuple like a row in the database, i.e.
        like the result lines of a "select * from phrases;"
        Like (id, mlen,clen,input_phrase,phrase,freq,user_freq)
        '''
        id, mlen, clen, input_phrase, phrase, freq, user_freq = phrase

        delete_sqlstr = '''
        DELETE FROM %(database)s.phrases
        WHERE input_phrase = :input_phrase AND phrase = :phrase
        ;''' %{'database': database}
        delete_sqlargs = {'input_phrase': input_phrase, 'phrase': phrase}
        self.db.execute(delete_sqlstr, delete_sqlargs)
        self.db.commit()

    def extract_user_phrases(self, udb, only_defined=False):
        '''extract user phrases from database'''
        try:
            db = sqlite3.connect(udb)
        except:
            return None
        if only_defined:
            _phrases = db.execute(\
                    "SELECT clen, phrase, freq, sum(user_freq)\
                    FROM phrases \
                    WHERE freq=-1 AND mlen != 0 \
                    GROUP BY clen,phrase;").fetchall()
        else:
            _phrases = db.execute(\
                    "SELECT clen, phrase, freq, sum(user_freq)\
                    FROM phrases\
                    WHERE mlen !=0 \
                    GROUP BY clen,phrase;").fetchall()
        db.commit()
        return _phrases[:]
