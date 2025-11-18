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

from typing import Iterable
from typing import Dict
from typing import Union
from typing import Callable
from typing import Optional
from typing import Any
import sys
import os
import gzip
import tempfile
import logging
import unittest

LOGGER = logging.getLogger('ibus-typing-booster')

# pylint: disable=wrong-import-position
import testutils # pylint: disable=import-error
# pylint: enable=wrong-import-position

IMPORT_DISTRO_SUCCESSFUL = False
try:
    import distro
    IMPORT_DISTRO_SUCCESSFUL = True
except (ImportError,):
    IMPORT_DISTRO_SUCCESSFUL = False

# Avoid failing test cases because updated dictionaries in:
#
# - ~/.local/share/ibus-typing-booster/data
# - ~/.config/enchant/<backend>
#
# The environments needs to be changed *before* using `import tabsqlitedb`
# since it must be set before using `import enchant`!
_ORIG_HOME = os.environ.pop('HOME', None)
_TEMPDIR = tempfile.TemporaryDirectory() # pylint: disable=consider-using-with
os.environ['HOME'] = _TEMPDIR.name

# pylint: disable=wrong-import-order
# pylint: disable=wrong-import-position
sys.path.insert(0, "../engine")
# pylint: disable=import-error
import itb_util
import tabsqlitedb
# pylint: disable=import-error
sys.path.pop(0)
# pylint: enable=wrong-import-position
# pylint: enable=wrong-import-order

# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring

class TabSqliteDbTestCase(unittest.TestCase):
    '''Test cases for tabsqlitedb.py'''
    _tempdir: Optional[tempfile.TemporaryDirectory] = None # type: ignore[type-arg]
    _orig_home: Optional[str] = None

    @classmethod
    def setUpClass(cls) -> None:
        cls._tempdir = _TEMPDIR
        cls._orig_home = _ORIG_HOME
        os.environ['HOME'] = cls._tempdir.name

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._orig_home is not None:
            os.environ['HOME'] = cls._orig_home
        else:
            _value = os.environ.pop('HOME', None)
        if cls._tempdir is not None:
            cls._tempdir.cleanup()

    def setUp(self) -> None:
        self.database: tabsqlitedb.TabSqliteDb = tabsqlitedb.TabSqliteDb(
            user_db_file=':memory:')

    def tearDown(self) -> None:
        pass

    def init_database(
            self,
            user_db_file: str = ':memory:',
            dictionary_names: Iterable[str] = ('en_US',)) -> None:
        self.database = tabsqlitedb.TabSqliteDb(user_db_file=user_db_file)
        self.database.hunspell_obj.set_dictionary_names(
            list(dictionary_names))

    def read_training_data_from_file(self, filename: str) -> bool:
        path = filename
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
            path: str,
            verbose: bool = True) -> Dict[str, Union[int, float]]:
        stats: Dict[str, Union[int, float]] = {
            'typed': 0, 'committed': 0, 'saved': 0, 'percent': 0.0}
        if '/' not in path:
            path = os.path.join(os.path.dirname(__file__), path)
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            path += '.gz'
        if not os.path.isfile(path):
            self.assertFalse(True) # pylint: disable=redundant-unittest-assert
            return stats
        open_function: Callable[[Any], Any] = open
        if path.endswith('.gz'):
            open_function = gzip.open
        with open_function( # type: ignore
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
                    if candidates and candidates[0].phrase == token:
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

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('en_US')[0],
        'Skipping because no en_US hunspell dictionary could be found.')
    @unittest.skipUnless(
        testutils.enchant_sanity_test(language='cs_CZ', word='Praha'),
        'Skipping because python3-enchant seems broken for cs_CZ.')
    @unittest.skipUnless(
        testutils.enchant_working_as_expected(),
        'Skipping because of an unexpected change in the enchant behaviour.')
    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_empty_database_only_dictionary(self) -> None:
        self.init_database(
            user_db_file=':memory:', dictionary_names=['en_US'])
        print(self.database.select_words(
            'baltim', p_phrase='foo', pp_phrase='bar')[0].phrase)
        self.assertEqual(
            'Baltimore',
            self.database.select_words(
                'baltim', p_phrase='foo', pp_phrase='bar')[0].phrase)

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('en_US')[0],
        'Skipping because no en_US hunspell dictionary could be found.')
    @unittest.skipUnless(
        testutils.enchant_sanity_test(language='cs_CZ', word='Praha'),
        'Skipping because python3-enchant seems broken for cs_CZ.')
    @unittest.skipUnless(
        testutils.enchant_working_as_expected(),
        'Skipping because of an unexpected change in the enchant behaviour.')
    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_add_phrase_to_database_and_check_existance(self) -> None:
        self.init_database(
            user_db_file=':memory:', dictionary_names=['en_US'])
        self.assertEqual(
            0,
            self.database.phrase_exists('suoicodilaipxecitsiligarfilacrepus'))
        self.database.add_phrase(
            input_phrase='suoicodilaipxecitsiligarfilacrepus',
            phrase='suoicodilaipxecitsiligarfilacrepus',
            user_freq=1)
        candidates = self.database.select_words('suoicodilaipxecitsiligarfilacrepus')
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].phrase, 'suoicodilaipxecitsiligarfilacrepus')
        self.assertEqual(candidates[0].user_freq, 1.0)
        self.assertEqual(candidates[0].comment, '')
        self.assertEqual(candidates[0].from_user_db, False)
        self.assertEqual(candidates[0].spell_checking, False)
        self.assertEqual(
            1,
            self.database.phrase_exists('suoicodilaipxecitsiligarfilacrepus'))
        self.database.remove_phrase(
            input_phrase='suoicodilaipxecitsiligarfilacrepus',
            phrase='suoicodilaipxecitsiligarfilacrepus')
        self.assertEqual(
            0,
            self.database.phrase_exists('suoicodilaipxecitsiligarfilacrepus'))
        self.database.add_phrase(
            input_phrase='suoicodilaipxecitsiligarfilacrepus',
            phrase='suoicodilaipxecitsiligarfilacrepus',
            user_freq=4711)
        self.assertEqual(
            4711,
            self.database.phrase_exists('suoicodilaipxecitsiligarfilacrepus'))

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
    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
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
        # -9.4% saved when typing the English poem with the en_US dictionary:
        self.assertEqual(-9.4, round(stats['percent'], 1))
        self.assertEqual(
            'undergrad',
            self.database.select_words(
                'undergr', p_phrase='in', pp_phrase='the')[0].phrase)
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
                'undergr', p_phrase='in', pp_phrase='the')[0].phrase)
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
    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
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
        # -10.5% on Fedora 43 with hunspell-fr-7.0-1.fc43.noarch when
        # the results from select_words() are normalized to NFC.
        self.assertEqual(-10.5, round(stats['percent'], 1))
        self.assertEqual(
            'plonge',
            self.database.select_words(
                'plong', p_phrase='nous', pp_phrase='Bientôt')[0].phrase)
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
                'plong', p_phrase='nous', pp_phrase='Bientôt')[0].phrase)
        stats = self.simulate_typing_file(training_file, verbose=False)
        LOGGER.info('stats=%s', repr(stats))
        # -37.6% saved when typing the French poem with the trained database
        # and the fr_FR dictionary:
        # -50.0% saved when the results from select_words()
        # are normalized to NFC.
        self.assertEqual(-50.0, round(stats['percent'], 1))
        # Set the en_US dictionary and see whether that makes the result worse:
        self.database.hunspell_obj.set_dictionary_names(['en_US'])
        stats = self.simulate_typing_file(training_file, verbose=False)
        LOGGER.info('stats=%s', repr(stats))
        # -37.6% saved when typing the French poem with the trained database
        # and the en_US dictionary. When the database is trained so well,
        # the dictionary almost doesn’t matter anymore:
        # -50.0% saved when the results from select_words()
        # are normalized to NFC.
        self.assertEqual(-50.0, round(stats['percent'], 1))

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
            self.skipTest(f'Training file {training_file} not available')
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
