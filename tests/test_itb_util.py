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
import locale
import unittest
import unicodedata

from gi import require_version # type: ignore
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore

sys.path.insert(0, "../engine")
import itb_util
sys.path.pop(0)

class ItbUtilTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        locale.resetlocale()

    def test_dummy(self):
        self.assertEqual(True, True)

    def test_is_right_to_left_messages(self):
        locale.setlocale(locale.LC_MESSAGES, 'de_DE.UTF-8')
        self.assertEqual(itb_util.is_right_to_left_messages(), False)
        locale.setlocale(locale.LC_MESSAGES, 'ar_EG.UTF-8')
        self.assertEqual(itb_util.is_right_to_left_messages(), True)
        locale.setlocale(locale.LC_MESSAGES, 'C')
        self.assertEqual(itb_util.is_right_to_left_messages(), False)
        # Result should be False for an invalid locale:
        try:
            locale.setlocale(locale.LC_MESSAGES, 'nonsense')
        except locale.Error:
            pass
        self.assertEqual(itb_util.is_right_to_left_messages(), False)
        # LC_ALL should have higher priority than LC_MESSAGES:
        locale.setlocale(locale.LC_MESSAGES, 'de_DE.UTF-8')
        locale.setlocale(locale.LC_ALL, 'ar_EG.UTF-8')
        self.assertEqual(itb_util.is_right_to_left_messages(), True)
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        self.assertEqual(itb_util.is_right_to_left_messages(), False)
        locale.setlocale(locale.LC_ALL, 'C')
        self.assertEqual(itb_util.is_right_to_left_messages(), False)

    def test_remove_accents(self):
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

if __name__ == '__main__':
    unittest.main()
