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
This file implements test cases for finding key codes for key values
'''

import sys
import os
import unittest

# pylint: disable=wrong-import-position
sys.path.insert(0, "../engine")
import itb_util # pylint: disable=import-error
sys.path.pop(0)
# pylint: enable=wrong-import-position

# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name

class M17nDbInfoTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._m17n_db_info = itb_util.M17nDbInfo()

    def tearDown(self) -> None:
        pass

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_NoIME_first(self) -> None:
        # 'NoIME' should be first in the list of input methods to make
        # it appear on top when adding input methods in the setup
        # tool. The list is sorted alphabetically, all other input
        # method names start with lower case letters, the sorting is
        # not locale specific, this should make 'NoIME' appear first:
        imes = self._m17n_db_info.get_imes()
        self.assertEqual('NoIME', imes[0])

    def test_t_latin_pre(self) -> None:
        self.assertEqual(
            'latn-pre.mim',
            os.path.basename(self._m17n_db_info.get_path('t-latn-pre')))
        self.assertEqual(
            'Latin-pre', self._m17n_db_info.get_title('t-latn-pre'))

    def test_t_math_latex(self) -> None:
        self.assertEqual(
            'math-latex.mim',
            os.path.basename(self._m17n_db_info.get_path('t-math-latex')))
        self.assertEqual(
            'Math: latex',
            self._m17n_db_info.get_title('t-math-latex'))
        self.assertEqual(
            'Mathematics input method using LaTeX command names.',
            self._m17n_db_info.get_description('t-math-latex'))

if __name__ == '__main__':
    unittest.main()
