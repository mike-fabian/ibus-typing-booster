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

from gi import require_version # type: ignore
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore
require_version('Gdk', '3.0')
from gi.repository import Gdk

sys.path.insert(0, "../engine")
import itb_util
sys.path.pop(0)

@unittest.skipIf(Gdk.Display.open('') == None, 'Display cannot be opened.')
class KeyvalsToKeycodesTestCase(unittest.TestCase):
    def setUp(self):
        self._keyvals_to_keycodes = itb_util.KeyvalsToKeycodes()

    def tearDown(self):
        pass

    def test_dummy(self):
        self.assertEqual(True, True)

    def test_left(self):
        # This test would fail if the Left key is remapped to a
        # different hardware key, but probably nobody remaps Left
        self.assertEqual(
            113, self._keyvals_to_keycodes.keycode(IBus.KEY_Left))
        self.assertEqual(
            105, self._keyvals_to_keycodes.ibus_keycode(IBus.KEY_Left))

    def test_backspace(self):
        # This test would fail if the BackSpace key is remapped to a
        # different hardware key, but probably nobody remaps BackSpace
        self.assertEqual(
            22, self._keyvals_to_keycodes.keycode(IBus.KEY_BackSpace))
        self.assertEqual(
            14, self._keyvals_to_keycodes.ibus_keycode(IBus.KEY_BackSpace))

    def test_a(self):
        # Do not test whether 'a' is mapped ot a specific hardware key
        # as this depends on the keyboard layout. But testing whether
        # it is mapped “somewhere” should be OK:
        self.assertTrue(
            len(self._keyvals_to_keycodes.ibus_keycodes(IBus.KEY_a)))
        self.assertTrue(
            self._keyvals_to_keycodes.ibus_keycodes(IBus.KEY_a)[0])

    def test_keyval_zero(self):
        # for the keyval 0, the returned lists of keycodes should
        # be empty and the keycode should be 0:
        self.assertEqual([], self._keyvals_to_keycodes.keycodes(0))
        self.assertEqual(0, self._keyvals_to_keycodes.keycode(0))
        self.assertEqual([], self._keyvals_to_keycodes.ibus_keycodes(0))
        self.assertEqual(0, self._keyvals_to_keycodes.ibus_keycode(0))

    def test_print_stuff_to_test_log(self):
        # Print information about the keval <-> keycode mapping to the
        # test log:
        print(self._keyvals_to_keycodes)

if __name__ == '__main__':
    unittest.main()
