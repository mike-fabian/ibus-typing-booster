#!/usr/bin/python3

# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2019 Mike FABIAN <mfabian@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

'''
This file implements test cases for miscellaneous stuff in tabsqlitedb.py.
'''

from typing import Dict
from typing import Union
from typing import Callable
import sys
import os
import gzip
import logging
import unittest
import unicodedata

from gi import require_version # type: ignore
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore

LOGGER = logging.getLogger('ibus-typing-booster')

IMPORT_DISTRO_SUCCESSFUL = False
try:
    import distro # type: ignore
    IMPORT_DISTRO_SUCCESSFUL = True
except (ImportError,):
    IMPORT_DISTRO_SUCCESSFUL = False

sys.path.insert(0, "../engine")
import itb_util
import tabsqlitedb
sys.path.pop(0)

class TabSqliteDbTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def init_database(
            self,
            user_db_file=':memory:',
            dictionary_names=('en_US',)) -> None:
        self.database = tabsqlitedb.TabSqliteDb(user_db_file=user_db_file)
        self.database.hunspell_obj.set_dictionary_names(dictionary_names)

    def read_training_data_from_file(self, filename) -> bool:
        if '/' not in filename:
            path = os.path.join(os.path.dirname(__file__), filename)
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            path += '.gz'
        if not os.path.isfile(path):
            return False
        return self.database.read_training_data_from_file(path)

    def simulate_typing_file(
            self,
            path,
            verbose=True) -> Dict[str, Union[int, float]]:
        stats: Dict[str, Union[int, float]] = {
            'typed': 0, 'committed': 0, 'saved': 0, 'percent': 0.0}
        if '/' not in path:
            path = os.path.join(os.path.dirname(__file__), path)
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            path += '.gz'
        if not os.path.isfile(path):
            self.assertFalse(True)
            return stats
        open_function: Callable = open
        if path.endswith('.gz'):
            open_function = gzip.open
        with open_function(
                path, mode='rt', encoding='UTF-8') as file_handle:
            lines = file_handle.readlines()
        p_token = ''
        pp_token = ''
        total_length_typed = 0
        total_length_committed = 0
        total_length_saved = 0
        total_percent_saved = 0.0
        current_line = 0
        total_lines = len(lines)
        for line in lines:
            current_line += 1
            for token in itb_util.tokenize(line):
                length_typed = 0
                length_saved = 0
                percent_saved = 0.0
                for i in range(1, len(token)):
                    candidates = self.database.select_words(
                        token[:i], p_phrase=p_token, pp_phrase=pp_token)
                    if candidates and candidates[0][0] == token:
                        length_typed = i
                        break
                    if i == len(token) - 1:
                        length_typed = len(token)
                length_saved = length_typed - len(token)
                percent_saved = 100.0 * length_saved / len(token)
                total_length_typed += length_typed
                total_length_committed += len(token)
                total_length_saved += length_saved
                total_percent_saved = (
                    100.0 * total_length_saved / total_length_committed)
                if verbose:
                    LOGGER.info(
                        'line %s/%s: %s -> %s %s %2.1f%% '
                        'total: %s -> %s %s %2.1f%%',
                        current_line,
                        total_lines,
                        token[:length_typed],
                        token,
                        length_saved,
                        percent_saved,
                        total_length_typed,
                        total_length_committed,
                        total_length_saved,
                        total_percent_saved)
        stats['typed'] = total_length_typed
        stats['committed'] = total_length_committed
        stats['saved'] = total_length_saved
        stats['percent'] = total_percent_saved
        return stats

    def test_dummy(self):
        self.assertEqual(True, True)

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('en_US')[0],
        'Skipping because no en_US hunspell dictionary could be found.')
    def test_empty_database_only_dictionary(self):
        self.init_database(
            user_db_file=':memory:', dictionary_names=['en_US'])
        self.assertEqual(
            'Baltimore',
            self.database.select_words(
                'baltim', p_phrase='foo', pp_phrase='bar')[0][0])

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('en_US')[0],
        'Skipping because no en_US hunspell dictionary could be found.')
    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('fr_FR')[0],
        'Skipping because no fr_FR hunspell dictionary could be found.')
    @unittest.skipUnless(
        IMPORT_DISTRO_SUCCESSFUL
        and distro.id() == 'fedora',
        'Skipping on other distros then Fedora, '
        'French dictionary might be too different on other distributions.')
    def test_english_poem(self) -> None:
        training_file = 'the_road_not_taken.txt'
        self.init_database(
            user_db_file=':memory:',dictionary_names=['fr_FR'])
        stats = self.simulate_typing_file(training_file, verbose=False)
        LOGGER.info('stats=%s', repr(stats))
        # -2.5% saved when typing the English poem with the fr_FR dictionary:
        self.assertEqual(-2.5, round(stats['percent'], 1))
        # Set the en_US dictionary and see whether the result is better:
        self.database.hunspell_obj.set_dictionary_names(['en_US'])
        stats = self.simulate_typing_file(training_file, verbose=False)
        LOGGER.info('stats=%s', repr(stats))
        # -9.3% saved when typing the English poem with the en_US dictionary:
        self.assertEqual(-9.3, round(stats['percent'], 1))
        self.assertEqual(
            'undergrad',
            self.database.select_words(
                'undergr', p_phrase='in', pp_phrase='the')[0][0])
        self.assertEqual(0, self.database.number_of_rows_in_database())
        self.assertEqual(
            True, self.read_training_data_from_file(training_file))
        # Now the database should have rows:
        self.assertEqual(148, self.database.number_of_rows_in_database())
        # Now that the training data has been read into the database
        # the result should change:
        self.assertEqual(
            'undergrowth',
            self.database.select_words(
                'undergr', p_phrase='in', pp_phrase='the')[0][0])
        stats = self.simulate_typing_file(training_file, verbose=False)
        LOGGER.info('stats=%s', repr(stats))
        # -51.3% saved when typing the English poem with the trained database
        # and the en_US dictionary:
        self.assertEqual(-51.3, round(stats['percent'], 1))
        # Set the fr_FR dictionary and see whether that makes the result worse:
        self.database.hunspell_obj.set_dictionary_names(['fr_FR'])
        stats = self.simulate_typing_file(training_file, verbose=False)
        LOGGER.info('stats=%s', repr(stats))
        # -51.3% saved when typing the English poem with the trained database
        # and the fr_FR dictionary. When the database is trained so well,
        # the dictionary almost doesn’t matter anymore:
        self.assertEqual(-51.3, round(stats['percent'], 1))

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('en_US')[0],
        'Skipping because no en_US hunspell dictionary could be found.')
    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('fr_FR')[0],
        'Skipping because no fr_FR hunspell dictionary could be found.')
    @unittest.skipUnless(
        IMPORT_DISTRO_SUCCESSFUL
        and distro.id() == 'fedora',
        'Skipping on other distros then Fedora, '
        'French dictionary might be too different on other distributions.')
    def test_french_poem(self) -> None:
        training_file = 'chant_d_automne.txt'
        self.init_database(
            user_db_file=':memory:',dictionary_names=['en_US'])
        stats = self.simulate_typing_file(training_file, verbose=False)
        LOGGER.info('stats=%s', repr(stats))
        # -2.3% saved when typing the French poem with the en_US dictionary:
        self.assertEqual(-2.3, round(stats['percent'], 1))
        # Set the fr_FR dictionary and see whether the result is better:
        self.database.hunspell_obj.set_dictionary_names(['fr_FR'])
        stats = self.simulate_typing_file(training_file, verbose=False)
        LOGGER.info('stats=%s', repr(stats))
        # -7.3% saved on Fedora 35 when typing the French poem with
        # the fr_FR dictionary. On openSUSE Tumbleweed (2021-11-23)
        # it is -8.2%.
        self.assertEqual(-7.3, round(stats['percent'], 1))
        self.assertEqual(
            'plonge',
            self.database.select_words(
                'plong', p_phrase='nous', pp_phrase='Bientôt')[0][0])
        self.assertEqual(0, self.database.number_of_rows_in_database())
        self.assertEqual(
            True, self.read_training_data_from_file(training_file))
        # Now the database should have rows:
        self.assertEqual(224, self.database.number_of_rows_in_database())
        # Now that the training data has been read into the database
        # the result should change:
        self.assertEqual(
            'plongerons',
            self.database.select_words(
                'plong', p_phrase='nous', pp_phrase='Bientôt')[0][0])
        stats = self.simulate_typing_file(training_file, verbose=False)
        LOGGER.info('stats=%s', repr(stats))
        # -37.6% saved when typing the French poem with the trained database
        # and the fr_FR dictionary:
        self.assertEqual(-37.6, round(stats['percent'], 1))
        # Set the fr_FR dictionary and see whether that makes the result worse:
        self.database.hunspell_obj.set_dictionary_names(['en_US'])
        stats = self.simulate_typing_file(training_file, verbose=False)
        LOGGER.info('stats=%s', repr(stats))
        # -37.6% saved when typing the French poem with the trained database
        # and the en_US dictionary. When the database is trained so well,
        # the dictionary almost doesn’t matter anymore:
        self.assertEqual(-37.6, round(stats['percent'], 1))

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('fr_FR')[0],
        'Skipping because no fr_FR hunspell dictionary could be found.')
    @unittest.skipUnless(
        IMPORT_DISTRO_SUCCESSFUL
        and distro.id() == 'fedora',
        'Skipping on other distros then Fedora, '
        'French dictionary might be too different on other distributions.')
    def test_french_book(self) -> None:
        training_file = 'victor_hugo_notre_dame_de_paris.txt'
        self.init_database(
            user_db_file=':memory:',dictionary_names=['fr_FR'])
        self.assertEqual(0, self.database.number_of_rows_in_database())
        if not self.read_training_data_from_file(training_file):
            self.skipTest('Training file %s not available' % training_file)
        # Now the database should have rows:
        self.assertEqual(156245, self.database.number_of_rows_in_database())
        self.database.cleanup_database(thread=False)
        self.assertEqual(50000, self.database.number_of_rows_in_database())
        stats = self.simulate_typing_file(training_file, verbose=True)
        LOGGER.info('stats=%s', repr(stats))
        # -27% saved when typing the French poem with the trained database
        # and the fr_FR dictionary:
        self.assertEqual(-24, round(stats['percent'], 0))

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    unittest.main()
