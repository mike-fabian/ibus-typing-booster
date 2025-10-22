#!/usr/bin/python3
'''
Test cases for the graphical Gtk tests.

 'init' has one array which is [keysym, keycode, modifier] and to be run
 before the main tests. E.g.
 Ctrl-space to enable Hiragana mode

 'tests' cases are the main test cases.
 'preedit' case runs to create a preedit text.
 'lookup' case runs to update a lookup table.
 'commit' case runs to commit the preedit text.
 'result' case is the expected output.
 'preedit', 'lookup', 'commit' can choose the type of either 'string' or 'keys'
 'string' type is a string sequence which does not need modifiers
'''

from gi import require_version
# pylint: disable=wrong-import-position
require_version('IBus', '1.0')
from gi.repository import IBus
# pylint: enable=wrong-import-position

TestCases = {
    #'init': [IBus.KEY_j, 0, IBus.ModifierType.CONTROL_MASK],
    'tests': [
                { 'preedit': { 'string': 'defaut' },
                  'lookup': { 'keys': [[IBus.KEY_Tab, 0, 0]] },
                  'commit': { 'keys': [[IBus.KEY_space, 0, 0]] },
                  'result': { 'string': 'défaut ' }
                },
                { 'preedit': { 'string': 'applesau' },
                  'lookup': { 'keys': [[IBus.KEY_Tab, 0, 0]]
                            },
                  'commit': { 'keys': [[IBus.KEY_Return, 0, 0]] },
                  'result': { 'string': 'applesauce' }
                },
                { 'preedit': { 'keys': [[IBus.KEY_Multi_key, 0, 0],
                                        [IBus.KEY_e, 0, 0],
                                        [IBus.KEY_apostrophe, 0, 0]]
                             },
                  'commit': { 'keys': [[IBus.KEY_space, 0, 0]] },
                  'result': { 'string': 'é ' }
                },
                { 'preedit': { 'keys': [[IBus.KEY_dead_acute, 0, 0],
                                        [IBus.KEY_e, 0, 0]]
                             },
                  'commit': { 'keys': [[IBus.KEY_space, 0, 0]] },
                  'result': { 'string': 'é ' }
                },
             ]

}
