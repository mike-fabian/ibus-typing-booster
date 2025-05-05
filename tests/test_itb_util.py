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
This file implements test cases for miscellaneous stuff in itb_util.py.
'''

import sys
import os
import logging
import unittest
import unicodedata

# pylint: disable=wrong-import-position
from gi import require_version # type: ignore
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore
# pylint: enable=wrong-import-position

LOGGER = logging.getLogger('ibus-typing-booster')

IMPORT_DISTRO_SUCCESSFUL = False
try:
    import distro
    IMPORT_DISTRO_SUCCESSFUL = True
except (ImportError,):
    IMPORT_DISTRO_SUCCESSFUL = False

IMPORT_LANGTABLE_SUCCESSFUL = False
try:
    # pylint: disable=unused-import
    import langtable # type: ignore
    # pylint: enable=unused-import
    IMPORT_LANGTABLE_SUCCESSFUL = True
except (ImportError,):
    IMPORT_LANGTABLE_SUCCESSFUL = False

IMPORT_PYCOUNTRY_SUCCESSFUL = False
try:
    # pylint: disable=unused-import
    import pycountry # type: ignore
    # pylint: enable=unused-import
    IMPORT_PYCOUNTRY_SUCCESSFUL = True
except (ImportError,):
    IMPORT_PYCOUNTRY_SUCCESSFUL = False

# pylint: disable=wrong-import-position
sys.path.insert(0, "../engine")
import itb_util # pylint: disable=import-error
sys.path.pop(0)
# pylint: enable=wrong-import-position

# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring

class ItbUtilTestCase(unittest.TestCase):
    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    @unittest.skipUnless(
        IMPORT_DISTRO_SUCCESSFUL
        and distro.id() == 'fedora'
        and distro.version() >= '34',
        'Skipping, requires new enough m17n-db package, '
        'might not be available on older distributions.')
    def test_default_input_methods_available(self) -> None:
        m17n_db_info = itb_util.M17nDbInfo()
        available_imes = m17n_db_info.get_imes()
        missing_imes_for_defaults = []
        for locale in itb_util.LOCALE_DEFAULTS:
            for ime in itb_util.LOCALE_DEFAULTS[locale]['inputmethods']:
                if ime not in available_imes:
                    missing_imes_for_defaults.append(ime)
        self.assertEqual([], missing_imes_for_defaults)

    @unittest.skipUnless(
        IMPORT_LANGTABLE_SUCCESSFUL or IMPORT_PYCOUNTRY_SUCCESSFUL,
        'Skipping, requires langtable or pycountry.')
    def test_locale_text_to_match(self) -> None:
        if 'LC_ALL' in os.environ:
            del os.environ['LC_ALL']
        os.environ['LC_MESSAGES'] = 'de_DE.UTF-8'
        text_to_match = itb_util.locale_text_to_match('fr_FR')
        if IMPORT_LANGTABLE_SUCCESSFUL:
            self.assertEqual(
                'fr_fr franzosisch (frankreich) francais (france) french (france)',
                text_to_match)
        elif IMPORT_PYCOUNTRY_SUCCESSFUL:
            self.assertEqual(
                'fr_fr french franzosisch francais france frankreich france',
                text_to_match)

    @unittest.skipUnless(
        IMPORT_LANGTABLE_SUCCESSFUL or IMPORT_PYCOUNTRY_SUCCESSFUL,
        'Skipping, requires langtable or pycountry.')
    def test_locale_language_description(self) -> None:
        if 'LC_ALL' in os.environ:
            del os.environ['LC_ALL']
        os.environ['LC_MESSAGES'] = 'de_DE.UTF-8'
        language_description = itb_util.locale_language_description('fr_FR')
        if IMPORT_LANGTABLE_SUCCESSFUL or IMPORT_PYCOUNTRY_SUCCESSFUL:
            self.assertEqual(
                'Französisch (Frankreich)',
                language_description)

    def test_is_right_to_left_messages(self) -> None:
        if 'LC_ALL' in os.environ:
            del os.environ['LC_ALL']
        os.environ['LC_MESSAGES'] = 'de_DE.UTF-8'
        self.assertEqual(itb_util.is_right_to_left_messages(), False)
        os.environ['LC_MESSAGES'] = 'ar_EG.UTF-8'
        self.assertEqual(itb_util.is_right_to_left_messages(), True)
        os.environ['LC_MESSAGES'] = 'C'
        self.assertEqual(itb_util.is_right_to_left_messages(), False)
        # Result should be False for an invalid locale:
        os.environ['LC_MESSAGES'] = 'nonsense'
        self.assertEqual(itb_util.is_right_to_left_messages(), False)
        # LC_ALL should have higher priority than LC_MESSAGES:
        os.environ['LC_MESSAGES'] = 'de_DE.UTF-8'
        os.environ['LC_ALL'] = 'ar_EG.UTF-8'
        self.assertEqual(itb_util.is_right_to_left_messages(), True)
        os.environ['LC_ALL'] = 'en_US.UTF-8'
        self.assertEqual(itb_util.is_right_to_left_messages(), False)
        os.environ['LC_ALL'] = 'C'
        self.assertEqual(itb_util.is_right_to_left_messages(), False)

    def test_remove_accents(self) -> None:
        self.assertEqual(
            itb_util.remove_accents('abcÅøßẞüxyz'),
            'abcAossSSuxyz')
        self.assertEqual(
            itb_util.remove_accents(
                unicodedata.normalize('NFD', 'abcÅøßẞüxyz')),
            'abcAossSSuxyz')
        self.assertEqual(
            unicodedata.normalize(
                'NFC',
                itb_util.remove_accents('abcÅøßẞüxyz', keep='åÅØø')),
            'abcÅøssSSuxyz')
        self.assertEqual(
            unicodedata.normalize(
                'NFC',
                itb_util.remove_accents(
                    unicodedata.normalize('NFD', 'abcÅøßẞüxyz'),
                    keep=unicodedata.normalize('NFD', 'åÅØø'))),
            'abcÅøssSSuxyz')
        self.assertEqual(
            unicodedata.normalize(
                'NFC',
                itb_util.remove_accents('alkoholförgiftning', keep='åÅÖö')),
            'alkoholförgiftning')
        self.assertEqual(
            unicodedata.normalize(
                'NFC',
                itb_util.remove_accents(
                    unicodedata.normalize('NFD', 'alkoholförgiftning'),
                    keep=unicodedata.normalize('NFD', 'åÅÖö'))),
            'alkoholförgiftning')

    def test_msymbol_for_return_and_escape(self) -> None:
        '''
        Return: https://github.com/mike-fabian/ibus-typing-booster/issues/457
        Escape: https://github.com/mike-fabian/ibus-typing-booster/issues/704
        '''
        key_event = itb_util.KeyEvent(
            IBus.KEY_Escape,
            0,
            0)
        self.assertEqual(key_event.msymbol, 'Escape')
        key_event = itb_util.KeyEvent(
            IBus.KEY_Escape,
            0,
            IBus.ModifierType.SHIFT_MASK)
        self.assertEqual(key_event.msymbol, 'S-Escape')
        key_event = itb_util.KeyEvent(
            IBus.KEY_Escape,
            0,
            IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(key_event.msymbol, 'C-Escape')
        key_event = itb_util.KeyEvent(
            IBus.KEY_Escape,
            0,
            IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(key_event.msymbol, 'S-C-Escape')
        key_event = itb_util.KeyEvent(
            IBus.KEY_Return,
            0,
            0)
        self.assertEqual(key_event.msymbol, 'Return')
        key_event = itb_util.KeyEvent(
            IBus.KEY_Return,
            0,
            IBus.ModifierType.SHIFT_MASK)
        self.assertEqual(key_event.msymbol, 'S-Return')
        key_event = itb_util.KeyEvent(
            IBus.KEY_Return,
            0,
            IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(key_event.msymbol, 'C-Return')
        key_event = itb_util.KeyEvent(
            IBus.KEY_Return,
            0,
            IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(key_event.msymbol, 'S-C-Return')

    def test_msymbol_for_tab_backspace_delete(self) -> None:
        ''' https://github.com/mike-fabian/ibus-typing-booster/issues/709 '''
        key_event = itb_util.KeyEvent(
            IBus.KEY_Tab,
            0,
            0)
        self.assertEqual(key_event.msymbol, 'Tab')
        key_event = itb_util.KeyEvent(
            IBus.KEY_BackSpace,
            0,
            0)
        self.assertEqual(key_event.msymbol, 'BackSpace')
        key_event = itb_util.KeyEvent(
            IBus.KEY_Delete,
            0,
            0)
        self.assertEqual(key_event.msymbol, 'Delete')

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    unittest.main()
