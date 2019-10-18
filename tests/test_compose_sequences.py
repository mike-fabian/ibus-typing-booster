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
import unittest

from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus

sys.path.insert(0, "../engine")
import itb_util
sys.path.pop(0)

class ComposeSequencesTestCase(unittest.TestCase):
    def setUp(self):
        self._compose_sequences = itb_util.ComposeSequences()

    def tearDown(self):
        pass

    def test_dummy(self):
        self.assertEqual(True, True)

    def test_preedit_representations(self):
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [IBus.KEY_Multi_key,
                 IBus.KEY_asciitilde,
                 IBus.KEY_dead_circumflex,
                 IBus.KEY_A]),
            '⎄~^A')
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [0x2276]),
            '≶')
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [IBus.KEY_Multi_key, 0x2276]),
            '⎄≶')
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [IBus.KEY_Multi_key, 0x093C]),
            '⎄़')
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [IBus.KEY_a, IBus.KEY_dead_belowdiaeresis]),
            'a\u00A0\u0324')

    def test_compose(self):
        # Valid sequence should return a composed result:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_asciitilde,
                 IBus.KEY_dead_circumflex,
                 IBus.KEY_A]),
            'Ẫ')
        # Incomplete sequence should return None:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_asciitilde,
                 IBus.KEY_dead_circumflex]),
            None)
        # Invalid sequence should return empty string:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_circumflex,
                 IBus.KEY_x]),
            '')
        # An empty should return an empty string:
        self.assertEqual(
            self._compose_sequences.compose([]), '')
        # Valid sequence, would give a different result in cs_CZ locale,
        # here is the result for non-cs_CZ locales:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_caron,
                 IBus.KEY_u]),
            'ǔ')

if __name__ == '__main__':
    unittest.main()
