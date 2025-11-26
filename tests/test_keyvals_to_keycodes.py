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
from typing import TYPE_CHECKING
import sys
import logging
import unittest

LOGGER = logging.getLogger('ibus-typing-booster')

# pylint: disable=wrong-import-position
from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus
# pylint: enable=wrong-import-position

sys.path.insert(0, "../engine")
# pylint: disable=import-error, wrong-import-position
from itb_gtk import Gdk # type: ignore
if TYPE_CHECKING:
    # These imports are only for type checkers (mypy). They must not be
    # executed at runtime because itb_gtk controls the Gtk/Gdk versions.
    # pylint: disable=reimported
    from gi.repository import Gdk  # type: ignore
    # pylint: enable=reimported
import itb_util
# pylint: enable=import-error, wrong-import-position
sys.path.pop(0)

# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring

@unittest.skipIf(Gdk.Display.open('') is None, 'Display cannot be opened.')
class KeyvalsToKeycodesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._keyvals_to_keycodes = itb_util.KeyvalsToKeycodes()

    def tearDown(self) -> None:
        pass

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_left(self) -> None:
        # This test would fail if the Left key is remapped to a
        # different hardware key, but probably nobody remaps Left
        self.assertEqual(
            113, self._keyvals_to_keycodes.keycode(IBus.KEY_Left))
        self.assertEqual(
            105, self._keyvals_to_keycodes.ibus_keycode(IBus.KEY_Left))

    def test_backspace(self) -> None:
        # This test would fail if the BackSpace key is remapped to a
        # different hardware key, but probably nobody remaps BackSpace
        self.assertEqual(
            22, self._keyvals_to_keycodes.keycode(IBus.KEY_BackSpace))
        self.assertEqual(
            14, self._keyvals_to_keycodes.ibus_keycode(IBus.KEY_BackSpace))

    def test_a(self) -> None:
        # Do not test whether 'a' is mapped ot a specific hardware key
        # as this depends on the keyboard layout. But testing whether
        # it is mapped “somewhere” should be OK:
        self.assertTrue(
            len(self._keyvals_to_keycodes.ibus_keycodes(IBus.KEY_a)))
        self.assertTrue(
            self._keyvals_to_keycodes.ibus_keycodes(IBus.KEY_a)[0])

    def test_keyval_zero(self) -> None:
        # for the keyval 0, the returned lists of keycodes should
        # be empty and the keycode should be 0:
        self.assertEqual([], self._keyvals_to_keycodes.keycodes(0))
        self.assertEqual(0, self._keyvals_to_keycodes.keycode(0))
        self.assertEqual([], self._keyvals_to_keycodes.ibus_keycodes(0))
        self.assertEqual(0, self._keyvals_to_keycodes.ibus_keycode(0))

    def test_print_stuff_to_test_log(self) -> None:
        # Print information about the keval <-> keycode mapping to the
        # test log:
        print(self._keyvals_to_keycodes)

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    unittest.main()
