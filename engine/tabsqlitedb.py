# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2011-2013 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012-2018 Mike FABIAN <mfabian@redhat.com>
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
'''
Module for ibus-typing-booster to access the sqlite3 databases
'''

from typing import Dict
from typing import List
from typing import Tuple
from typing import Optional
from typing import Any
from typing import Callable
import os
import unicodedata
import sqlite3
import time
import re
import gzip
import logging
import itb_util
import hunspell_suggest

LOGGER = logging.getLogger('ibus-typing-booster')

DEBUG_LEVEL = int(0)

USER_DATABASE_VERSION = '0.65'

class TabSqliteDb:
    # pylint: disable=line-too-long
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
    # pylint: enable=line-too-long
    def __init__(self, user_db_file: str = '') -> None:
        global DEBUG_LEVEL # pylint: disable=global-statement
        try:
            DEBUG_LEVEL = int(str(os.getenv('IBUS_TYPING_BOOSTER_DEBUG_LEVEL')))
        except (TypeError, ValueError):
            DEBUG_LEVEL = int(0)
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'TabSqliteDb.__init__(user_db_file = %s)', user_db_file)
        self.user_db_file = user_db_file
        if not self.user_db_file and os.getenv('HOME'):
            self.user_db_file = os.path.join(
                str(os.getenv('HOME')), '.local/share/ibus-typing-booster/user.db')
        if not self.user_db_file:
            LOGGER.debug('Falling back to ":memory:" for user.db')
            self.user_db_file = ':memory:'
        if (self.user_db_file != ':memory:'
                and not os.path.isdir(os.path.dirname(self.user_db_file))):
            os.makedirs(os.path.dirname(self.user_db_file), exist_ok=True)
        self._phrase_table_column_names = [
            'id',
            'input_phrase',
            'phrase',
            'p_phrase',
            'pp_phrase',
            'user_freq',
            'timestamp']

        self._old_phrases: List[Tuple[str, str, int]] = []

        self.hunspell_obj = hunspell_suggest.Hunspell(())

        self._check_database_compatibility()
        self._check_database_readability()

        LOGGER.info(
            'Connect to the database %s.', self.user_db_file)
        self.database = self.sqlite3_connect_database(self.user_db_file)
        try:
            self.database.executescript(
                f'ATTACH DATABASE "{self.user_db_file}" AS user_db;')
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Could not attach the database %s. %s: %s '
                'This should never happen.',
                self.user_db_file, error.__class__.__name__, error)
        self.create_tables()
        self._restore_old_phrases()

        # try create all hunspell-tables in user database
        self.create_indexes(commit=False)
        self.generate_userdb_desc()

    def _restore_old_phrases(self) -> None:
        '''Restore phrases recovered from old database into new database'''
        if not self._old_phrases:
            return
        LOGGER.info('Restoring old phrases: %s', self._old_phrases)
        sqlargs = []
        for ophrase in self._old_phrases:
            sqlargs.append(
                {'input_phrase': ophrase[0],
                 'phrase': ophrase[1],
                 'p_phrase': '',
                 'pp_phrase': '',
                 'user_freq': ophrase[2],
                 'timestamp': time.time()})
        sqlstr = '''
        INSERT INTO user_db.phrases (input_phrase, phrase, p_phrase, pp_phrase, user_freq, timestamp)
        VALUES (:input_phrase, :phrase, :p_phrase, :pp_phrase, :user_freq, :timestamp)
        ;'''
        try:
            self.database.executemany(sqlstr, sqlargs)
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error inserting old phrases '
                'into the user database: %s: %s',
                error.__class__.__name__, error)
        self.database.commit()
        self.database.execute('PRAGMA wal_checkpoint;')

    def _check_database_compatibility(self) -> None:
        '''Check whether the database is compatible'''
        if self.user_db_file == ':memory:':
            LOGGER.info(
                ':memory: database is always newly created '
                ' and therefore always compatible.')
            return
        if not os.path.exists(self.user_db_file):
            LOGGER.info(
                'User database %s does not exist yet and will be created. '
                'A newly created database is always compatible.',
                self.user_db_file)
            return
        try:
            desc = self.get_database_desc(self.user_db_file)
            if (desc
                and
                desc['version'] == USER_DATABASE_VERSION
                and
                self.get_number_of_columns_of_phrase_table(self.user_db_file)
                == len(self._phrase_table_column_names)):
                LOGGER.info(
                    'Compatible database %s found.', self.user_db_file)
                return
            LOGGER.info('User database %s seems incompatible.',
                        self.user_db_file)
            # Log reason for incompatibility
            if not desc:
                LOGGER.info('No version information in the database')
            elif desc['version'] != USER_DATABASE_VERSION:
                LOGGER.info('The version of the database does not match '
                            '(too old or too new?).'
                            'ibus-typing-booster wants version=%s '
                            'but the database actually has version=%s.',
                            USER_DATABASE_VERSION, desc['version'])
            elif (self.get_number_of_columns_of_phrase_table(self.user_db_file)
                  != len(self._phrase_table_column_names)):
                LOGGER.info(
                    'The number of columns of the database does not match.'
                    'ibus-typing-booster expectes %s columns but the '
                    'database actually has %s columns.',
                    len(self._phrase_table_column_names),
                    self.get_number_of_columns_of_phrase_table(self.user_db_file))
            # Try to recover old phrases to use for initializing a new
            # database:
            self._old_phrases = self._extract_user_phrases()
            self._rename_incompatible_or_broken_database()
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error checking database compatibility: %s: %s',
                error.__class__.__name__, error)

    def _check_database_readability(self) -> None:
        '''Check whether all rows from the phrases table of the
        database are readable
        '''
        if self.user_db_file == ':memory:':
            LOGGER.info(
                ':memory: database is always newly created '
                ' and therefore always readable.')
            return
        if not os.path.exists(self.user_db_file):
            LOGGER.info(
                'User database %s does not exist yet and will be created. '
                'A newly created database is always readable.',
                self.user_db_file)
            return
        database = self.sqlite3_connect_database(self.user_db_file)
        try:
            database.execute('SELECT * FROM phrases;').fetchall()
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Error checking database readability: %s: %s',
                error.__class__.__name__, error)
            self._rename_incompatible_or_broken_database()
            return
        LOGGER.info('Database seems readable.')

    def _rename_incompatible_or_broken_database(self) -> None:
        '''
        Creates a backup copy of an incompatible or broken database

        Also creates a new empty database.
        '''
        timestamp = time.strftime('-%Y-%m-%d_%H:%M:%S')
        LOGGER.info('Renaming incompatible or broken database to "%s"',
                    self.user_db_file+timestamp)
        if os.path.exists(self.user_db_file):
            os.rename(self.user_db_file,
                      self.user_db_file+timestamp)
        if os.path.exists(self.user_db_file+'-shm'):
            os.rename(self.user_db_file+'-shm',
                      self.user_db_file+'-shm'+timestamp)
        if os.path.exists(self.user_db_file+'-wal'):
            os.rename(self.user_db_file+'-wal',
                      self.user_db_file+'-wal'+timestamp)
        LOGGER.info(
            'Creating a new, empty database "%s".', self.user_db_file)
        self.database = self.sqlite3_connect_database(self.user_db_file)

    def update_phrase(
            self,
            input_phrase: str = '',
            phrase: str = '',
            p_phrase: str = '',
            pp_phrase: str = '',
            user_freq: int = 0,
            commit: bool = True) -> None:
        '''
        update the user frequency of a phrase
        '''
        if not input_phrase or not phrase:
            return
        input_phrase = itb_util.remove_accents(input_phrase.lower())
        phrase = unicodedata.normalize(
            itb_util.NORMALIZATION_FORM_INTERNAL, phrase)
        p_phrase = itb_util.remove_accents(p_phrase.lower())
        pp_phrase = itb_util.remove_accents(pp_phrase.lower())
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
            LOGGER.debug('sqlstr=%s', sqlstr)
            LOGGER.debug('sqlargs=%s', sqlargs)
        try:
            self.database.execute(sqlstr, sqlargs)
            if commit:
                self.database.commit()
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error updating phrase in user_db: %s: %s',
                error.__class__.__name__, error)

    def sync_usrdb(self) -> None:
        '''Trigger a checkpoint operation.'''
        LOGGER.info('commit and execute checkpoint ...')
        try:
            self.database.commit()
            self.database.execute('PRAGMA wal_checkpoint;')
            LOGGER.info('commit and execute checkpoint done.')
        except sqlite3.OperationalError as error:
            LOGGER.exception(
                'Unexpected error syncing user database: %s: %s',
                error.__class__.__name__, error)

    def create_tables(self) -> None:
        '''Create table for the phrases.'''
        sqlstr = '''CREATE TABLE IF NOT EXISTS user_db.phrases
                    (id INTEGER PRIMARY KEY,
                    input_phrase TEXT, phrase TEXT, p_phrase TEXT, pp_phrase TEXT,
                    user_freq INTEGER, timestamp REAL);'''
        self.database.execute(sqlstr)
        self.database.commit()

    def add_phrase(
            self,
            input_phrase: str = '',
            phrase: str = '',
            p_phrase: str = '',
            pp_phrase: str = '',
            user_freq: int = 0,
            commit: bool = True) -> None:
        '''
        Add phrase to database
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'input_phrase=%r phrase=%r user_freq=%s ',
                input_phrase, phrase, user_freq)
        if not input_phrase or not phrase:
            return
        input_phrase = itb_util.remove_accents(input_phrase.lower())
        phrase = unicodedata.normalize(
            itb_util.NORMALIZATION_FORM_INTERNAL, phrase)
        p_phrase = itb_util.remove_accents(p_phrase.lower())
        pp_phrase = itb_util.remove_accents(pp_phrase.lower())
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
        if self.database.execute(select_sqlstr, select_sqlargs).fetchall():
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
            LOGGER.debug('insert_sqlstr=%s', insert_sqlstr)
            LOGGER.debug('insert_sqlargs=%s', insert_sqlargs)
        try:
            self.database.execute(insert_sqlstr, insert_sqlargs)
            if commit:
                self.database.commit()
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error adding phrase to database: %s: %s',
                error.__class__.__name__, error)

    def create_indexes(self, commit: bool = True) -> None:
        '''Create indexes for the database.'''
        sqlstr = '''
        CREATE INDEX IF NOT EXISTS user_db.phrases_index_p ON phrases
        (input_phrase, id ASC);
        CREATE INDEX IF NOT EXISTS user_db.phrases_index_i ON phrases
        (phrase)
        ;'''
        self.database.executescript(sqlstr)
        if commit:
            self.database.commit()

    @classmethod
    def best_candidates(
            cls,
            phrase_frequencies: Dict[str, float],
            title: bool = False) -> List[Tuple[str, float]]:
        '''Sorts the phrase_frequencies dictionary and returns the best
        candidates.

        Should *not* change the phrase_frequencies dictionary!
        '''
        candidates = sorted(phrase_frequencies.items(),
                            key=lambda x: (
                                -1*x[1],   # user_freq descending
                                len(x[0]), # len(phrase) ascending
                                x[0]       # phrase alphabetical
                            ))[:20]
        if not title:
            return candidates
        candidates_title = []
        phrases_title = set()
        for candidate in candidates:
            phrase = candidate[0]
            phrase_title = phrase[:1].title() + phrase[1:]
            if phrase_title in phrases_title:
                continue
            candidates_title.append((phrase_title, candidate[1]))
            phrases_title.add(phrase_title)
        return candidates_title

    def select_shortcuts(
            self,
            input_phrase: str) -> List[Tuple[str, float]]:
        '''
        Get shortcuts from database completing input_phrase.

        Returns a list of matches where each match is a tuple in the
        form of (phrase, user_freq), i.e. returns something like
        [(phrase, user_freq), ...]
        '''
        input_phrase = unicodedata.normalize(
            itb_util.NORMALIZATION_FORM_INTERNAL, input_phrase)
        if DEBUG_LEVEL > 1:
            LOGGER.debug('input_phrase=%s', input_phrase)
        phrase_frequencies: Dict[str, float] = {}
        sqlargs = {'input_phrase': input_phrase + '%',
                   'user_freq': itb_util.SHORTCUT_USER_FREQ}
        sqlstr = ('SELECT phrase, sum(user_freq) FROM user_db.phrases '
                  'WHERE input_phrase LIKE :input_phrase '
                  'AND user_freq >= :user_freq '
                  'GROUP BY phrase;')
        results_shortcuts: List[Tuple[str, int]] = []
        try:
            results_shortcuts = self.database.execute(
                sqlstr, sqlargs).fetchall()
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error fetching '
                'user shortcuts from database: %s: %s',
                 error.__class__.__name__, error)
        if results_shortcuts:
            phrase_frequencies.update(results_shortcuts)
        best_shortcut_candidates = self.best_candidates(phrase_frequencies)
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'best_shortcut_candidates=%s', best_shortcut_candidates)
        return best_shortcut_candidates

    def select_words_empty_input(
            self,
            p_phrase: str,
            pp_phrase: str) -> List[Tuple[str, float]]:
        '''Get phrases from database which occured previously with
        any input after the given context

        Returns a list of matches where each match is a tuple in the
        form of (phrase, user_freq), i.e. returns something like
        [(phrase, user_freq), ...]

        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'p_phrase=%s pp_phrase=%s', p_phrase, pp_phrase)
        phrase_frequencies: Dict[str, float] = {}
        if not p_phrase or not pp_phrase:
            return self.best_candidates(phrase_frequencies)
        p_phrase = itb_util.remove_accents(p_phrase.lower())
        pp_phrase = itb_util.remove_accents(pp_phrase.lower())
        sqlargs = {'p_phrase': p_phrase, 'pp_phrase': pp_phrase}
        sqlstr = ('SELECT phrase, sum(user_freq) FROM user_db.phrases '
                  'WHERE p_phrase = :p_phrase '
                  'AND pp_phrase = :pp_phrase GROUP BY phrase;')
        results = None
        try:
            results = self.database.execute(sqlstr, sqlargs).fetchall()
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error getting phrases for empty input '
                'with given context from user_db: %s: %s',
                error.__class__.__name__, error)
            results = None
        if not results:
            return self.best_candidates(phrase_frequencies)
        sqlstr = (
            'SELECT sum(user_freq) FROM user_db.phrases '
            'WHERE p_phrase = :p_phrase AND pp_phrase = :pp_phrase;')
        count_pp_phrase_p_phrase = 0
        try:
            count_pp_phrase_p_phrase = self.database.execute(
                sqlstr, sqlargs).fetchall()[0][0]
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error getting total count for empty input '
                'with given context from user_db: %s: %s',
                 error.__class__.__name__, error)
            count_pp_phrase_p_phrase = 0
        if not count_pp_phrase_p_phrase:
            return self.best_candidates(phrase_frequencies)
        for result in results:
            phrase_frequencies.update(
                [(result[0], result[1]/float(count_pp_phrase_p_phrase))])
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'Best candidates for empty input with given context=%s',
                self.best_candidates(phrase_frequencies))
        return self.best_candidates(phrase_frequencies)

    def select_words(
            self,
            input_phrase: str,
            p_phrase: str = '',
            pp_phrase: str = '') -> List[Tuple[str, float]]:
        '''
        Get phrases from database completing input_phrase.

        Returns a list of matches where each match is a tuple in the
        form of (phrase, user_freq), i.e. returns something like
        [(phrase, user_freq), ...]
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'input_phrase=%s p_phrase=%s pp_phrase=%s',
                input_phrase, p_phrase, pp_phrase)
        if not input_phrase:
            return self.select_words_empty_input(p_phrase, pp_phrase)
        phrase_frequencies: Dict[str, float] = {}
        input_phrase = unicodedata.normalize(
            itb_util.NORMALIZATION_FORM_INTERNAL, input_phrase)
        p_phrase = itb_util.remove_accents(p_phrase.lower())
        pp_phrase = itb_util.remove_accents(pp_phrase.lower())
        title_case = input_phrase.istitle()
        if ' ' not in input_phrase:
            # Get suggestions from hunspell dictionaries. But only
            # if input_phrase does not contain spaces. The hunspell
            # dictionaries contain only single words, not sentences.
            # Trying to complete an input_phrase which contains spaces
            # will never work and spell checking suggestions by hunspell
            # for input which contains spaces is almost always nonsense.
            phrase_frequencies.update(self.hunspell_obj.suggest(input_phrase))
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'hunspell: best_candidates=%s',
                self.best_candidates(phrase_frequencies, title=title_case))
        # Remove the accents *after* getting the hunspell candidates.
        # If the accents were removed before getting the hunspell candidates
        # an input phrase like “Glühwürmchen” would not be added as a
        # candidate because hunspell would get “Gluhwurmchen” then and would
        # not validate that as a correct word. And, because “Glühwürmchen”
        # is not in the German hunspell dictionary as a single word but
        # created by suffix and prefix rules, the accent insensitive match
        # in the German hunspell dictionary would not find it either.
        input_phrase = itb_util.remove_accents(input_phrase.lower())
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
        quoted_input_phrase = ''
        quoted_input_phrase = input_phrase.replace(
            '\x00', '').replace('"', '""')
        self.database.execute('DROP VIEW IF EXISTS like_input_phrase_view;')
        sqlstr = f'''
        CREATE TEMPORARY VIEW IF NOT EXISTS like_input_phrase_view AS
        SELECT * FROM user_db.phrases
        WHERE input_phrase LIKE "{quoted_input_phrase}%%"
        ;'''
        try:
            self.database.execute(sqlstr)
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error in creating database view: %s: %s',
                error.__class__.__name__, error)
        sqlargs = {'p_phrase': p_phrase, 'pp_phrase': pp_phrase}
        sqlstr = (
            'SELECT phrase, sum(user_freq) FROM like_input_phrase_view '
            'GROUP BY phrase;')
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
            results_uni = self.database.execute(sqlstr, sqlargs).fetchall()
            # Then the result returned by .fetchall() is:
            #
            # [('colour', 4), ('cold', 1), ('conspiracy', 6)]
            #
            # (“c|conspiracy|1” is not selected because it doesn’t
            # match the user input “LIKE co%”! I.e. this is filtered
            # out by the VIEW created above already)
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error getting “unigram” data from user_db: %s: %s',
                error.__class__.__name__, error)
        if not results_uni:
            # If no unigrams matched, bigrams and trigrams cannot
            # match either. We can stop here and return what we got
            # from hunspell.
            return self.best_candidates(phrase_frequencies, title=title_case)
        # Now normalize the unigram frequencies with the total count
        # (which is 11 in the above example), which gives us the
        # normalized result:
        # [('colour', 4/11), ('cold', 1/11), ('conspiracy', 6/11)]
        sqlstr = 'SELECT sum(user_freq) FROM like_input_phrase_view;'
        try:
            count = self.database.execute(sqlstr, sqlargs).fetchall()[0][0]
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error getting total unigram count '
                'from user_db: %s: %s',
                 error.__class__.__name__, error)
        # Updating the phrase_frequency dictionary with the normalized
        # results gives: {'conspiracy': 6/11, 'code': 0,
        # 'communicability': 0, 'cold': 1/11, 'colour': 4/11}
        for result_uni in results_uni:
            phrase_frequencies.update(
                [(result_uni[0], result_uni[1]/float(count))])
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'Unigram best_candidates=%s',
                self.best_candidates(phrase_frequencies, title=title_case))
        if not p_phrase:
            # If no context for bigram matching is available, return
            # what we have so far:
            return self.best_candidates(phrase_frequencies, title=title_case)
        sqlstr = (
            'SELECT phrase, sum(user_freq) FROM like_input_phrase_view '
            'WHERE p_phrase = :p_phrase GROUP BY phrase;')
        try:
            results_bi = self.database.execute(sqlstr, sqlargs).fetchall()
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error getting “bigram” data '
                'from user_db: %s: %s',
                error.__class__.__name__, error)
        if not results_bi:
            # If no bigram could be matched, return what we have so far:
            return self.best_candidates(phrase_frequencies, title=title_case)
        # get the total count of p_phrase to normalize the bigram frequencies:
        sqlstr = (
            'SELECT sum(user_freq) FROM like_input_phrase_view '
            'WHERE p_phrase = :p_phrase;')
        try:
            count_p_phrase = self.database.execute(
                sqlstr, sqlargs).fetchall()[0][0]
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error getting total bigram count '
                'from user_db: %s: %s',
                 error.__class__.__name__, error)
        # Update the phrase frequency dictionary by using a linear
        # combination of the unigram and the bigram results, giving
        # both the weight of 0.5:
        for result_bi in results_bi:
            phrase_frequencies.update(
                [(result_bi[0],
                  0.5*result_bi[1]/float(count_p_phrase)
                  +0.5*phrase_frequencies[result_bi[0]])])
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'Bigram best_candidates=%s',
                self.best_candidates(phrase_frequencies, title=title_case))
        if not pp_phrase:
            # If no context for trigram matching is available, return
            # what we have so far:
            return self.best_candidates(phrase_frequencies, title=title_case)
        sqlstr = ('SELECT phrase, sum(user_freq) FROM like_input_phrase_view '
                  'WHERE p_phrase = :p_phrase '
                  'AND pp_phrase = :pp_phrase GROUP BY phrase;')
        try:
            results_tri = self.database.execute(sqlstr, sqlargs).fetchall()
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error getting “trigram” data '
                'from user_db: %s: %s',
                 error.__class__.__name__, error)
        if not results_tri:
            # if no trigram could be matched, return what we have so far:
            return self.best_candidates(phrase_frequencies, title=title_case)
        # get the total count of (p_phrase, pp_phrase) pairs to
        # normalize the bigram frequencies:
        sqlstr = (
            'SELECT sum(user_freq) FROM like_input_phrase_view '
            'WHERE p_phrase = :p_phrase AND pp_phrase = :pp_phrase;')
        try:
            count_pp_phrase_p_phrase = self.database.execute(
                sqlstr, sqlargs).fetchall()[0][0]
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error getting total trigram count '
                'from user_db: %s: %s',
                 error.__class__.__name__, error)
        # Update the phrase frequency dictionary by using a linear
        # combination of the bigram and the trigram results, giving
        # both the weight of 0.5 (that makes the total weights: 0.25 *
        # unigram + 0.25 * bigram + 0.5 * trigram, i.e. the trigrams
        # get higher weight):
        for result_tri in results_tri:
            phrase_frequencies.update(
                [(result_tri[0],
                  0.5*result_tri[1]/float(count_pp_phrase_p_phrase)
                  +0.5*phrase_frequencies[result_tri[0]])])
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'Trigram best_candidates=%s',
                self.best_candidates(phrase_frequencies, title=title_case))
        return self.best_candidates(phrase_frequencies, title=title_case)

    def generate_userdb_desc(self) -> None:
        '''
        Add a description table to the user database

        This adds the database version and  the create time
        '''
        try:
            sqlstring = ('CREATE TABLE IF NOT EXISTS user_db.desc '
                         + '(name PRIMARY KEY, value);')
            self.database.executescript(sqlstring)
            sqlstring = 'INSERT OR IGNORE INTO user_db.desc  VALUES (?, ?);'
            self.database.execute(
                sqlstring, ('version', USER_DATABASE_VERSION))
            sqlstring = (
                'INSERT OR IGNORE INTO user_db.desc '
                + 'VALUES (?, DATETIME("now", "localtime"));')
            self.database.execute(sqlstring, ("create-time", ))
            self.database.commit()
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error adding description to user_db: %s: %s',
                 error.__class__.__name__, error)

    @classmethod
    def sqlite3_connect_database(cls, db_file: str) -> sqlite3.Connection:
        '''Connect to a database, creating it if it does not exist

        Also set our standard options for the database.
        '''
        # Creates the file db_file if it does not exist:
        database_connection = sqlite3.connect(db_file)
        # A database containing the complete German Hunspell
        # dictionary has less then 6000 pages. 20000 pages
        # should be enough to cache the complete database
        # in most cases.
        database_connection.executescript('''
        PRAGMA encoding = "UTF-8";
        PRAGMA case_sensitive_like = true;
        PRAGMA page_size = 4096;
        PRAGMA cache_size = 20000;
        PRAGMA temp_store = MEMORY;
        PRAGMA journal_mode = WAL;
        PRAGMA journal_size_limit = 1000000;
        PRAGMA synchronous = NORMAL;
        PRAGMA auto_vacuum = FULL;
        ''')
        database_connection.commit()
        database_connection.text_factory = (
            lambda x: x.decode(
                encoding='utf-8', errors='replace')) # or better 'ignore'?
        return database_connection

    @classmethod
    def get_database_desc(cls, db_file: str) -> Optional[Dict[str, str]]:
        '''Get the description of the database'''
        if not os.path.exists(db_file):
            return None
        try:
            database = cls.sqlite3_connect_database(db_file)
            desc = {}
            for row in database.execute("SELECT * FROM desc;").fetchall():
                desc[row[0]] = row[1]
            database.close()
            return desc
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error getting database description: %s: %s',
                 error.__class__.__name__, error)
            return None

    @classmethod
    def get_number_of_columns_of_phrase_table(
            cls, db_file: str) -> Optional[int]:
        # pylint: disable=line-too-long
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
        # pylint: enable=line-too-long
        if not os.path.exists(db_file):
            return None
        try:
            database = cls.sqlite3_connect_database(db_file)
            table_phrases_result = database.execute(
                "select sql from sqlite_master where name='phrases';"
            ).fetchall()
            # Remove possible line breaks from the string where we
            # want to match:
            string = ' '.join(table_phrases_result[0][0].splitlines())
            match = re.match(r'.*\((.*)\)', string)
            if match:
                table_phrases_columns = match.group(1).split(',')
                return len(table_phrases_columns)
            return 0
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error getting number of columns '
                'of database: %s: %s',
                 error.__class__.__name__, error)
            return 0

    def list_user_shortcuts(self) -> List[Tuple[str, str]]:
        '''Returns a list of user defined shortcuts from the user database.
        '''
        sqlstr = '''
        SELECT input_phrase, phrase FROM user_db.phrases WHERE user_freq >= :freq
        ;'''
        sqlargs = {'freq': itb_util.SHORTCUT_USER_FREQ}
        if DEBUG_LEVEL > 1:
            LOGGER.debug('sqlstr=%s', sqlstr)
            LOGGER.debug('sqlargs=%s', sqlargs)
        result = self.database.execute(sqlstr, sqlargs).fetchall()
        if DEBUG_LEVEL > 1:
            LOGGER.debug('result=%s', result)
        return result

    def define_user_shortcut(
            self,
            input_phrase: str = '',
            phrase: str = '',
            user_freq: int = itb_util.SHORTCUT_USER_FREQ,
            commit: bool = True) -> bool:
        '''
        Defines a new user shortcut

        :return: True on success, False on failure
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'input_phrase=%s phrase=%s user_freq=%s commit=%s',
                input_phrase, phrase, user_freq, commit)
        if (not input_phrase or not phrase
            or user_freq < itb_util.SHORTCUT_USER_FREQ):
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Not defining shortcut.')
            return False
        phrase = unicodedata.normalize(
            itb_util.NORMALIZATION_FORM_INTERNAL, phrase)
        # Contrary to add_phrase(), do *not* remove accents and do *not*
        # lower case input_phrase:
        input_phrase = unicodedata.normalize(
            itb_util.NORMALIZATION_FORM_INTERNAL, input_phrase)
        sqlargs = {'input_phrase': input_phrase,
                   'phrase': phrase,
                   'user_freq': user_freq,
                   'timestamp': time.time()}
        sqlstr = (
            'INSERT INTO user_db.phrases '
            '(input_phrase, phrase, p_phrase, pp_phrase, user_freq, timestamp)'
            'VALUES (:input_phrase, :phrase, "", "", :user_freq, :timestamp);')
        try:
            self.database.execute(sqlstr, sqlargs)
            if commit:
                self.database.commit()
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error defining shortcut: %s: %s',
                error.__class__.__name__, error)
            return False
        return True

    def check_shortcut_and_update_frequency(
            self,
            input_phrase: str = '',
            phrase: str = '',
            user_freq_increment: int = 1,
            commit: bool = True) -> bool:
        '''
        Check whether there are user defined shortcuts expanding to phrase.

        If yes, increase the frequency of each of them by user_freq_increment
        and return True, else return False
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'input_phrase=“%s” phrase=“%s” user_freq_increment=%s commit=%s',
                input_phrase, phrase, user_freq_increment, commit)
        input_phrase = input_phrase.strip()
        phrase = phrase.strip()
        if not input_phrase or not phrase:
            return False
        phrase = unicodedata.normalize(
            itb_util.NORMALIZATION_FORM_INTERNAL, phrase)
        input_phrase = unicodedata.normalize(
            itb_util.NORMALIZATION_FORM_INTERNAL, input_phrase)
        sqlargs = {'phrase': phrase,
                   'user_freq': itb_util.SHORTCUT_USER_FREQ,
                   'timestamp': time.time()}
        sqlstr = ('SELECT input_phrase, user_freq '
                  'FROM user_db.phrases '
                  'WHERE phrase = :phrase '
                  'AND user_freq >= :user_freq;')
        results = []
        try:
            results = self.database.execute(sqlstr, sqlargs).fetchall()
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error checking user shortcuts in user_db: %s: %s',
                 error.__class__.__name__, error)
        if not results:
            return False
        for (db_input_phrase, db_user_freq) in results:
            if input_phrase == db_input_phrase:
                if DEBUG_LEVEL > 1:
                    LOGGER.debug(
                        'Exactly matched shortcut: %s',
                        (db_input_phrase, phrase, db_user_freq))
            new_user_freq = db_user_freq + user_freq_increment
            if DEBUG_LEVEL > 1:
                LOGGER.debug(
                    'Increase shortcut frequency by: %s -> %s',
                    (db_input_phrase, phrase, db_user_freq),
                    (db_input_phrase, phrase, new_user_freq))
            sqlargs['user_freq'] = new_user_freq
            sqlargs['input_phrase'] = db_input_phrase
            sqlstr = (
                'UPDATE user_db.phrases '
                'SET user_freq = :user_freq, timestamp = :timestamp '
                'WHERE input_phrase = :input_phrase '
                'AND phrase = :phrase ;')
            try:
                self.database.execute(sqlstr, sqlargs)
                if commit:
                    self.database.commit()
            except Exception as error: # pylint: disable=broad-except
                LOGGER.exception(
                    'Unexpected error updating shortcut in user_db: %s: %s',
                    error.__class__.__name__, error)
        return True

    def check_phrase_and_update_frequency(
            self,
            input_phrase: str = '',
            phrase: str = '',
            p_phrase: str = '',
            pp_phrase: str = '',
            user_freq_increment: int = 1,
            commit: bool = True) -> None:
        '''
        Check whether input_phrase and phrase are already in database. If
        they are in the database, increase the frequency by 1, if not
        add them.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'input_phrase=“%s” phrase=“%s” p_phrase=“%s” pp_phrase=“%s” '
                'user_freq_increment=%s commit=%s',
                input_phrase, phrase, p_phrase, pp_phrase,
                user_freq_increment, commit)
        # Handle shortcuts before using strip_token to allow
        # punctuation in shortcuts and shortcut expansions:
        if input_phrase:
            if self.check_shortcut_and_update_frequency(
                    input_phrase=input_phrase,
                    phrase=phrase,
                    user_freq_increment=user_freq_increment,
                    commit=commit):
                return
        if not input_phrase:
            input_phrase = phrase
        if not phrase:
            return
        input_phrase = itb_util.strip_token(input_phrase)
        phrase = itb_util.strip_token(phrase)
        phrase = unicodedata.normalize(
            itb_util.NORMALIZATION_FORM_INTERNAL, phrase)
        p_phrase = itb_util.remove_accents(p_phrase.lower())
        pp_phrase = itb_util.remove_accents(pp_phrase.lower())
        input_phrase = itb_util.remove_accents(input_phrase.lower())

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
            LOGGER.debug(
                'TabSqliteDb.check_phrase_and_update_frequency() sqlstr=%s',
                sqlstr)
            LOGGER.debug(
                'TabSqliteDb.check_phrase_and_update_frequency() sqlargs=%s',
                sqlargs)
        result = self.database.execute(sqlstr, sqlargs).fetchall()
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'check_phrase_and_update_frequency() result=%s', result)
        if result:
            # A match was found in user_db, increase user frequency by
            # user_freq_increment (1 by default)
            self.update_phrase(input_phrase=input_phrase,
                               phrase=phrase,
                               p_phrase=p_phrase,
                               pp_phrase=pp_phrase,
                               user_freq=result[0][0]+user_freq_increment,
                               commit=commit)
            return
        # The phrase was not found in user_db.
        # Add it as a new phrase, i.e. with user_freq = user_freq_increment
        # (1 by default):
        self.add_phrase(input_phrase=input_phrase,
                        phrase=phrase,
                        p_phrase=p_phrase,
                        pp_phrase=pp_phrase,
                        user_freq=user_freq_increment,
                        commit=commit)
        return

    def phrase_exists(self, phrase: str) -> int:
        '''
        Checks if an entry for phrase already exists in the user database

        :param phrase: The phrase to check whether it is already recorded
        :return: 0 if not in the database. > 0 if in the database.
                 The value > 0 gives the sum(user_freq) in the database
                 for phrase.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('phrase=%r', phrase)
        if not phrase:
            return 0
        phrase = unicodedata.normalize(
            itb_util.NORMALIZATION_FORM_INTERNAL, phrase)
        select_sqlstr = '''
        SELECT sum(user_freq) FROM user_db.phrases WHERE phrase = :phrase ;
        '''
        select_sqlargs = {'phrase': phrase}
        retval = self.database.execute(select_sqlstr, select_sqlargs).fetchall()
        if retval[0][0] is None:
            return 0
        return int(retval[0][0])

    def remove_phrase(
            self,
            input_phrase: str = '',
            phrase: str = '',
            commit: bool = True) -> None:
        '''
        Remove all rows matching “input_phrase” and “phrase” from database.
        Or, if “input_phrase” is “None”, remove all rows matching “phrase”
        no matter for what input phrase from the database.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('phrase=%r', phrase)
        if not phrase:
            return
        phrase = unicodedata.normalize(
            itb_util.NORMALIZATION_FORM_INTERNAL, phrase)
        if input_phrase:
            input_phrase = unicodedata.normalize(
                itb_util.NORMALIZATION_FORM_INTERNAL, input_phrase)
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
        self.database.execute(delete_sqlstr, delete_sqlargs)
        if commit:
            self.database.commit()

    def _extract_user_phrases(self) -> List[Tuple[str, str, int]]:
        '''extract user phrases from database'''
        LOGGER.info(
            'Trying to recover phrases from old, incompatible database'
            'Phrases successfully recovered can be used to '
            'initialize a newly created database.')
        try:
            database = self.sqlite3_connect_database(self.user_db_file)
            database.execute('PRAGMA wal_checkpoint;')
            phrases = database.execute(
                'SELECT input_phrase, phrase, sum(user_freq) FROM phrases GROUP BY phrase;'
            ).fetchall()
            database.close()
            phrases = [
                (unicodedata.normalize(
                    itb_util.NORMALIZATION_FORM_INTERNAL, x[0]),
                 unicodedata.normalize(
                    itb_util.NORMALIZATION_FORM_INTERNAL, x[1]),
                 x[2])
                for x in
                phrases
            ]
            return phrases[:]
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error extracting user phrases: %s: %s',
                 error.__class__.__name__, error)
            return []

    def read_training_data_from_file(self, filename: str) -> bool:
        '''
        Read data to train the prediction from a text file.

        :param filename: Full path of the text file to read.
        '''
        if not os.path.isfile(filename):
            filename += '.gz'
            if not os.path.isfile(filename):
                return False
        open_function: Callable[[Any], Any] = open
        if filename.endswith('.gz'):
            open_function = gzip.open
        rows = self.database.execute(
            'SELECT input_phrase, phrase, p_phrase, pp_phrase, '
            + 'user_freq, timestamp FROM phrases;').fetchall()
        rows = sorted(rows, key = lambda x: (float(x[5]))) # sort by timestamp
        time_min = time.time()
        time_max = time.time()
        if rows:
            time_min = rows[0][5]
            time_max = rows[-1][5]
        # timestamp for added entries (timestamp of existing entries is kept):
        time_new = time_min + 0.20 * (time_max - time_min)
        LOGGER.info('Minimum timestamp in the database=%s',
                    time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time_min)))
        LOGGER.info('Maximum timestamp in the database=%s',
                    time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time_max)))
        LOGGER.info('New timestamp in the database=%s',
                    time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time_new)))
        p_token = ''
        pp_token = ''
        database_dict: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
        for row in rows:
            # itb_util.remove_accents() returns in NORMALIZATION_FORM_INTERNAL.
            # row[1] (“phrase”) should already be in NORMALIZATION_FORM_INTERNAL
            # but better convert it again here just to make sure.
            input_phrase = itb_util.remove_accents(row[0].lower())
            phrase = unicodedata.normalize(
                itb_util.NORMALIZATION_FORM_INTERNAL, row[1])
            p_phrase = itb_util.remove_accents(row[2].lower())
            pp_phrase = itb_util.remove_accents(row[3].lower())
            database_dict.update([((row[0], row[1], row[2], row[3]),
                                   {'input_phrase': input_phrase,
                                    'phrase': phrase,
                                    'p_phrase': p_phrase,
                                    'pp_phrase': pp_phrase,
                                    'user_freq': row[4],
                                    'timestamp': row[5]}
                                  )])
        lines = []
        try:
            with open_function( # type: ignore
                    filename, mode='rt', encoding='UTF-8') as file_handle:
                lines = [
                    unicodedata.normalize(
                        itb_util.NORMALIZATION_FORM_INTERNAL, line)
                    for line in file_handle.readlines()]
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error reading training data from file: %s: %s',
                 error.__class__.__name__, error)
            return False
        for line in lines:
            for token in itb_util.tokenize(line):
                key = (itb_util.remove_accents(token.lower()),
                       token,
                       itb_util.remove_accents(p_token.lower()),
                       itb_util.remove_accents(pp_token.lower()))
                if key in database_dict:
                    database_dict[key]['user_freq'] += 1
                else:
                    database_dict[key] = {
                        'input_phrase': itb_util.remove_accents(token.lower()),
                        'phrase': token,
                        'p_phrase': itb_util.remove_accents(p_token.lower()),
                        'pp_phrase': itb_util.remove_accents(pp_token.lower()),
                        'user_freq': 1,
                        'timestamp': time_new}
                pp_token = p_token
                p_token = token
        sqlargs = []
        for key, value in database_dict.items():
            sqlargs.append(value)
        sqlstr = '''
        INSERT INTO user_db.phrases (input_phrase, phrase, p_phrase, pp_phrase, user_freq, timestamp)
        VALUES (:input_phrase, :phrase, :p_phrase, :pp_phrase, :user_freq, :timestamp)
        ;'''
        try:
            self.database.execute('DELETE FROM phrases;')
            # Without the following commit, the
            # self.database.executemany() fails with
            # “OperationalError: database is locked”.
            self.database.commit()
            self.database.executemany(sqlstr, sqlargs)
            self.database.commit()
            self.database.execute('PRAGMA wal_checkpoint;')
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error writing training data to database: %s: %s',
                 error.__class__.__name__, error)
            return False
        return True

    def remove_all_phrases(self) -> None:
        '''
        Remove all phrases from the database, i.e. delete all the
        data learned from user input or text files.
        '''
        try:
            self.database.execute('DELETE FROM phrases;')
            self.database.commit()
            self.database.execute('PRAGMA wal_checkpoint;')
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error removing all phrases from database: %s: %s',
                 error.__class__.__name__, error)

    def dump_database(self) -> None:
        '''
        Dump the contents of the database to the log

        (For debugging)
        '''
        try:
            LOGGER.debug('SELECT * FROM desc;\n')
            for row in self.database.execute("SELECT * FROM desc;").fetchall():
                LOGGER.debug('%s', repr(row))
            LOGGER.debug('SELECT * FROM phrases;\n')
            for row in self.database.execute(
                    "SELECT * FROM phrases;").fetchall():
                LOGGER.debug('%s', repr(row))
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception('Unexpected error dumping database: %s: %s',
                              error.__class__.__name__, error)

    def number_of_rows_in_database(self) -> int:
        '''
        Return the current number of rows in the database

        (For debugging)
        '''
        try:
            return len(self.database.execute(
                "SELECT * FROM phrases;").fetchall())
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error getting number of database rows: %s: %s',
                error.__class__.__name__, error)
            return -1

    def cleanup_database(self, thread: bool = True) -> None:
        '''Cleanup user database by expiring entries which have not been
        used for a long time.

        :param thread: Whether this function is called in a different thread or not.

        Usually it is called in a thread started when Typing Booster
        has just finished starting up and is ready for input.

        But in unittest test cases it may be called with an in memory
        database without starting a thread. In that case a new
        database connection is not needed.

        '''
        if thread and self.user_db_file == ':memory:':
            LOGGER.info('Database cleanup not needed for memory database.')
            return
        LOGGER.info('Database cleanup starting ...')
        time_now = time.time()
         # id, input_phrase, phrase, p_phrase, pp_phrase, user_freq, timestamp
        rows: List[Tuple[int, str, str, str, str, int, float]] = []
        try:
            if thread:
                # SQLite objects created in a thread can only be used in
                # that same thread.  As the database cleanup is usually
                # called in a separate thread, get a new connection:
                database = self.sqlite3_connect_database(self.user_db_file)
            else:
                database = self.database
            rows = database.execute("SELECT * FROM phrases;").fetchall()
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception('Exception when accessing database: %s: %s',
                              error.__class__.__name__, error)
        if not rows:
            return
        rows = sorted(rows,
                      key = lambda x: (
                          x[5], # user_freq
                          x[6], # timestamp
                          x[0], # id
                      ))
        LOGGER.info('Total number of database rows to check=%s ', len(rows))
        index = len(rows)
        max_rows = 50000
        number_delete_above_max = 0
        rows_kept: List[Tuple[int, str, str, str, str, int, float]] = []
        for row in rows:
            user_freq = row[5]
            if (index > max_rows
                and user_freq < itb_util.SHORTCUT_USER_FREQ):
                LOGGER.info('1st pass: deleting %s %s',
                            repr(row),
                            time.strftime("%Y-%m-%d %H:%M:%S",
                                          time.gmtime(row[6])))
                number_delete_above_max += 1
                sqlstr_delete = 'DELETE from phrases WHERE id = :id;'
                sqlargs_delete = {'id': row[0]}
                try:
                    database.execute(sqlstr_delete, sqlargs_delete)
                except Exception as error: # pylint: disable=broad-except
                    LOGGER.exception(
                        '1st pass: exception deleting row '
                        'from database: %s: %s',
                         error.__class__.__name__, error)
            else:
                rows_kept.append(row)
            index -= 1
        LOGGER.info('1st pass: Number of rows deleted above maximum size=%s',
                    number_delete_above_max)
        # As the first pass above removes rows sorted by count and
        # then by timestamp, it will never remove rows with a higher
        # count even if they are extremely old. Therefore, a second
        # pass uses sorting only by timestamp in order to first decay and
        # eventually remove some rows which have not been used for a
        # long time as well, even if they have a higher count.
        # In this second pass, the 0.1% oldest rows are checked
        # and:
        #
        # - if user_freq == 1 remove the row
        # - if user_freq > 1 divide user_freq by 2 and update timestamp to “now”
        #
        # 0.1% is really not much but I want to be careful not to remove
        # too much when trying this out.
        #
        # sort kept rows by timestamp only instead of user_freq and timestamp:
        rows_kept = sorted(rows_kept,
                           key = lambda x: (
                               x[6], # timestamp
                               x[0], # id
                           ))
        index = len(rows_kept)
        LOGGER.info('1st pass: Number of rows kept=%s', index)
        index_decay = int(max_rows * 0.999)
        LOGGER.info('2nd pass: Index for decay=%s', index_decay)
        number_of_rows_to_decay = 0
        number_of_rows_to_delete = 0
        for row in rows_kept:
            user_freq = row[5]
            if (index > index_decay
                and user_freq < itb_util.SHORTCUT_USER_FREQ):
                if user_freq == 1:
                    LOGGER.info('2nd pass: deleting %s %s',
                                repr(row),
                                time.strftime("%Y-%m-%d %H:%M:%S",
                                              time.gmtime(row[6])))
                    number_of_rows_to_delete += 1
                    sqlstr_delete = 'DELETE from phrases WHERE id = :id;'
                    sqlargs_delete = {'id': row[0]}
                    try:
                        database.execute(sqlstr_delete, sqlargs_delete)
                    except Exception as error: # pylint: disable=broad-except
                        LOGGER.exception(
                            '2nd pass: exception deleting row '
                            'from database: %s: %s',
                             error.__class__.__name__, error)
                else:
                    LOGGER.info('2nd pass: decaying %s %s',
                                repr(row),
                                time.strftime("%Y-%m-%d %H:%M:%S",
                                              time.gmtime(row[6])))
                    number_of_rows_to_decay += 1
                    sqlstr_update = '''
                    UPDATE phrases
                    SET user_freq = :user_freq, timestamp = :timestamp
                    WHERE id = :id
                    ;'''
                    sqlargs_update = {'id': row[0],
                                      'user_freq': int(user_freq/2),
                                      'timestamp': time.time()}

                    try:
                        database.execute(sqlstr_update, sqlargs_update)
                    except Exception as error: # pylint: disable=broad-except
                        LOGGER.exception(
                            '2nd pass: exception decaying row '
                            'from database: %s: %s',
                             error.__class__.__name__, error)
            index -= 1
        LOGGER.info('Commit database and execute checkpoint ...')
        database.commit()
        database.execute('PRAGMA wal_checkpoint;')
        LOGGER.info('Rebuild database using VACUUM command ...')
        database.execute('VACUUM;')
        LOGGER.info('Number of database rows deleted=%s',
                     number_delete_above_max + number_of_rows_to_delete)
        LOGGER.info('Number of database rows decayed=%s',
                    number_of_rows_to_decay)
        LOGGER.info('Number of rows before cleanup=%s', len(rows))
        LOGGER.info('Number of rows remaining=%s',
                    len(rows_kept) - number_of_rows_to_delete)
        LOGGER.info('Time for database cleanup=%s seconds',
                    time.time() - time_now)
        LOGGER.info('Database cleanup finished.')
