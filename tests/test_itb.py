#!/usr/bin/python3
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2016 Mike FABIAN <mfabian@redhat.com>
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
This file implements the test cases for the unit tests of ibus-typing-booster
'''

# pylint: disable=missing-function-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position

import os
import sys
import unicodedata
import unittest
import subprocess
import importlib
import mock

from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus
require_version('Gdk', '3.0')
from gi.repository import Gdk

# Get more verbose output in the test log:
os.environ['IBUS_TYPING_BOOSTER_DEBUG_LEVEL'] = '255'

from mock_engine import MockEngine
from mock_engine import MockLookupTable
from mock_engine import MockProperty
from mock_engine import MockPropList

sys.path.insert(0, "../engine")
# pylint: disable=import-error
import hunspell_table
import tabsqlitedb
import itb_util
from m17n_translit import Transliterator
# pylint: enable=import-error
sys.path.pop(0)

IMPORT_ENCHANT_SUCCESSFUL = False
IMPORT_HUNSPELL_SUCCESSFUL = False
try:
    import enchant
    IMPORT_ENCHANT_SUCCESSFUL = True
except (ImportError,):
    try:
        import hunspell
        IMPORT_HUNSPELL_SUCCESSFUL = True
    except (ImportError,):
        pass

IMPORT_LIBVOIKKO_SUCCESSFUL = False
try:
    import libvoikko
    IMPORT_LIBVOIKKO_SUCCESSFUL = True
except (ImportError,):
    pass

@unittest.skipIf(Gdk.Display.open('') is None, 'Display cannot be opened.')
class ItbTestCase(unittest.TestCase):
    '''
    Test cases for ibus-typing-booster
    '''
    engine_patcher = mock.patch.object(
        IBus, 'Engine', new=MockEngine)
    lookup_table_patcher = mock.patch.object(
        IBus, 'LookupTable', new=MockLookupTable)
    property_patcher = mock.patch.object(
        IBus, 'Property', new=MockProperty)
    prop_list_patcher = mock.patch.object(
        IBus, 'PropList', new=MockPropList)
    ibus_engine = IBus.Engine
    ibus_lookup_table = IBus.LookupTable
    ibus_property = IBus.Property
    ibus_prop_list = IBus.PropList

    def setUp(self):
        # Patch the IBus stuff with the mock classes:
        self.engine_patcher.start()
        self.lookup_table_patcher.start()
        self.property_patcher.start()
        self.prop_list_patcher.start()
        assert IBus.Engine is not self.ibus_engine
        assert IBus.Engine is MockEngine
        assert IBus.LookupTable is not self.ibus_lookup_table
        assert IBus.LookupTable is MockLookupTable
        assert IBus.Property is not self.ibus_property
        assert IBus.Property is MockProperty
        assert IBus.PropList is not self.ibus_prop_list
        assert IBus.PropList is MockPropList
        # Reload the hunspell_table module so that the patches
        # are applied to TypingBoosterEngine:
        sys.path.insert(0, "../engine")
        importlib.reload(hunspell_table)
        sys.path.pop(0)
        self.bus = IBus.Bus()
        self.database = tabsqlitedb.TabSqliteDb(user_db_file=':memory:')
        self.engine = hunspell_table.TypingBoosterEngine(
            self.bus,
            '/com/redhat/IBus/engines/table/typing_booster/engine/0',
            self.database,
            unit_test=True)
        self.backup_original_settings()
        self.set_default_settings()

    def tearDown(self):
        self.restore_original_settings()
        del self.engine
        # Remove the patches from the IBus stuff:
        self.engine_patcher.stop()
        self.lookup_table_patcher.stop()
        self.property_patcher.stop()
        self.prop_list_patcher.stop()
        assert IBus.Engine is self.ibus_engine
        assert IBus.Engine is not MockEngine
        assert IBus.LookupTable is self.ibus_lookup_table
        assert IBus.LookupTable is not MockLookupTable
        assert IBus.Property is self.ibus_property
        assert IBus.Property is not MockProperty
        assert IBus.PropList is self.ibus_prop_list
        assert IBus.PropList is not MockPropList

    def backup_original_settings(self):
        self.orig_emoji_prediction_mode = (
            self.engine.get_emoji_prediction_mode())
        self.orig_off_the_record_mode = (
            self.engine.get_off_the_record_mode())
        self.orig_auto_commit_characters = (
            self.engine.get_auto_commit_characters())
        self.orig_tab_enable = (
            self.engine.get_tab_enable())
        self.orig_inline_completion = (
            self.engine.get_inline_completion())
        self.orig_auto_capitalize = (
            self.engine.get_auto_capitalize())
        self.orig_remember_last_used_preedit_ime = (
            self.engine.get_remember_last_used_preedit_ime())
        self.orig_page_size = (
            self.engine.get_page_size())
        self.orig_lookup_table_orientation = (
            self.engine.get_lookup_table_orientation())
        self.orig_min_char_complete = (
            self.engine.get_min_char_complete())
        self.orig_show_number_of_candidates = (
            self.engine.get_show_number_of_candidates())
        self.orig_show_status_info_in_auxiliary_text = (
            self.engine.get_show_status_info_in_auxiliary_text())
        self.orig_add_space_on_commit = (
            self.engine.get_add_space_on_commit())
        self.orig_current_imes = (
            self.engine.get_current_imes())
        self.orig_dictionary_names = (
            self.engine.get_dictionary_names())
        self.orig_qt_im_module_workaround = (
            self.engine.get_qt_im_module_workaround())
        self.orig_keybindings = (
            self.engine.get_keybindings())

    def restore_original_settings(self):
        self.engine.set_emoji_prediction_mode(
            self.orig_emoji_prediction_mode,
            update_gsettings=False)
        self.engine.set_off_the_record_mode(
            self.orig_off_the_record_mode,
            update_gsettings=False)
        self.engine.set_auto_commit_characters(
            self.orig_auto_commit_characters,
            update_gsettings=False)
        self.engine.set_tab_enable(
            self.orig_tab_enable,
            update_gsettings=False)
        self.engine.set_inline_completion(
            self.orig_inline_completion,
            update_gsettings=False)
        self.engine.set_auto_capitalize(
            self.orig_auto_capitalize,
            update_gsettings=False)
        self.engine.set_remember_last_used_preedit_ime(
            self.orig_remember_last_used_preedit_ime,
            update_gsettings=False)
        self.engine.set_page_size(
            self.orig_page_size,
            update_gsettings=False)
        self.engine.set_lookup_table_orientation(
            self.orig_lookup_table_orientation,
            update_gsettings=False)
        self.engine.set_min_char_complete(
            self.orig_min_char_complete,
            update_gsettings=False)
        self.engine.set_show_number_of_candidates(
            self.orig_show_number_of_candidates,
            update_gsettings=False)
        self.engine.set_show_status_info_in_auxiliary_text(
            self.orig_show_status_info_in_auxiliary_text,
            update_gsettings=False)
        self.engine.set_add_space_on_commit(
            self.orig_add_space_on_commit,
            update_gsettings=False)
        self.engine.set_current_imes(
            self.orig_current_imes,
            update_gsettings=False)
        self.engine.set_dictionary_names(
            self.orig_dictionary_names,
            update_gsettings=False)
        self.engine.set_qt_im_module_workaround(
            self.orig_qt_im_module_workaround,
            update_gsettings=False)
        self.engine.set_keybindings(
            self.orig_keybindings,
            update_gsettings=False)

    def set_default_settings(self):
        self.engine.set_emoji_prediction_mode(
            False, update_gsettings=False)
        self.engine.set_off_the_record_mode(
            False, update_gsettings=False)
        self.engine.set_auto_commit_characters(
            '', update_gsettings=False)
        self.engine.set_tab_enable(
            False, update_gsettings=False)
        self.engine.set_inline_completion(
            False, update_gsettings=False)
        self.engine.set_auto_capitalize(
            False, update_gsettings=False)
        self.engine.set_remember_last_used_preedit_ime(
            False, update_gsettings=False)
        self.engine.set_page_size(
            6, update_gsettings=False)
        self.engine.set_min_char_complete(
            1, update_gsettings=False)
        self.engine.set_show_number_of_candidates(
            False, update_gsettings=False)
        self.engine.set_add_space_on_commit(
            True, update_gsettings=False)
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.set_qt_im_module_workaround(
            False, update_gsettings=False)
        self.engine.set_keybindings({
            'cancel': ['Escape'],
            'commit_candidate_1': [],
            'commit_candidate_1_plus_space': ['1', 'KP_1', 'F1'],
            'commit_candidate_2': [],
            'commit_candidate_2_plus_space': ['2', 'KP_2', 'F2'],
            'commit_candidate_3': [],
            'commit_candidate_3_plus_space': ['3', 'KP_3', 'F3'],
            'commit_candidate_4': [],
            'commit_candidate_4_plus_space': ['4', 'KP_4', 'F4'],
            'commit_candidate_5': [],
            'commit_candidate_5_plus_space': ['5', 'KP_5', 'F5'],
            'commit_candidate_6': [],
            'commit_candidate_6_plus_space': ['6', 'KP_6', 'F6'],
            'commit_candidate_7': [],
            'commit_candidate_7_plus_space': ['7', 'KP_7', 'F7'],
            'commit_candidate_8': [],
            'commit_candidate_8_plus_space': ['8', 'KP_8', 'F8'],
            'commit_candidate_9': [],
            'commit_candidate_9_plus_space': ['9', 'KP_9', 'F9'],
            'enable_lookup': ['Tab', 'ISO_Left_Tab'],
            'lookup_related': ['Mod5+F12'],
            'lookup_table_page_down': ['Page_Down', 'KP_Page_Down', 'KP_Next'],
            'lookup_table_page_up': ['Page_Up', 'KP_Page_Up', 'KP_Prior'],
            'next_dictionary': ['Mod1+Down', 'Mod1+KP_Down'],
            'next_input_method': ['Control+Down', 'Control+KP_Down'],
            'previous_dictionary': ['Mod1+Up', 'Mod1+KP_Up'],
            'previous_input_method': ['Control+Up', 'Control+KP_Up'],
            'select_next_candidate':
            ['Tab', 'ISO_Left_Tab', 'Down', 'KP_Down'],
            'select_previous_candidate':
            ['Shift+Tab', 'Shift+ISO_Left_Tab', 'Up', 'KP_Up'],
            'setup': ['Mod5+F10'],
            'speech_recognition': [],
            'toggle_emoji_prediction': ['Mod5+F6'],
            'toggle_input_mode_on_off': [],
            'toggle_off_the_record': ['Mod5+F9'],
        }, update_gsettings=False)

    def get_transliterator_or_skip(self, ime):
        try:
            sys.stderr.write('ime "%s" ... ' %ime)
            trans = Transliterator(ime)
        except ValueError as error:
            trans = None
            self.skipTest(error)
        except Exception as error:
            sys.stderr.write('Unexpected exception!')
            trans = None
            self.skipTest(error)
        return trans

    def test_dummy(self):
        self.assertEqual(True, True)

    @unittest.expectedFailure
    def test_expected_failure(self):
        self.assertEqual(False, True)

    def test_get_label(self):
        self.assertEqual(self.engine.get_lookup_table().get_label(9), '9.')
        self.engine.get_lookup_table().set_label(
            9, IBus.Text.new_from_string('9'))
        self.assertEqual(self.engine.get_lookup_table().get_label(9), '9')

    def test_single_char_commit_with_space(self):
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'a ')

    def test_single_char_commit_with_arrow_right(self):
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Right, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'b')

    def test_char_space_period_space(self):
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_period, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'a . ')

    def test_direct_input(self):
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'a" ')

    def test_latn_post(self):
        self.engine.set_current_imes(
            ['t-latn-post', 'NoIME'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'ä ')

    def test_autocommit_characters(self):
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.set_auto_commit_characters('.', update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_semicolon, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_period, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'a;. b ')

    def test_push_context(self):
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.set_auto_commit_characters('.', update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_d, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'a b c d ')
        self.assertEqual(self.engine._ppp_phrase, 'b')
        self.assertEqual(self.engine._pp_phrase, 'c')
        self.assertEqual(self.engine._p_phrase, 'd')

    def test_set_page_size(self):
        self.engine.set_page_size(
            3, update_gsettings=False)
        self.assertEqual(
            self.engine.get_lookup_table().mock_page_size,
            3)
        self.engine.set_page_size(
            5, update_gsettings=False)
        self.assertEqual(
            self.engine.get_lookup_table().mock_page_size,
            5)

    def test_complete_word_from_us_english_dictionary(self):
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.assertEqual(self.engine._candidates[0][0], 'cerulean')
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'cerulean ')

    def test_commit_with_arrows(self):
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_f, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'foo ')
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'foo ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 4)
        self.assertEqual(self.engine.mock_preedit_text, 'bar')
        self.assertEqual(self.engine.mock_preedit_text_cursor_pos, 3)
        self.assertEqual(self.engine.mock_preedit_text_visible, True)
        self.engine.do_process_key_event(IBus.KEY_Left, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Left, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Left, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'foo ')
        self.assertEqual(self.engine.mock_preedit_text, 'bar')
        self.assertEqual(self.engine.mock_preedit_text_cursor_pos, 0)
        self.assertEqual(self.engine.mock_preedit_text_visible, True)
        self.engine.do_process_key_event(IBus.KEY_Left, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'foo bar')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 3)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_preedit_text_cursor_pos, 0)
        self.assertEqual(self.engine.mock_preedit_text_visible, False)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'foo  bar')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 4)
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_z, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Left, 0,
                                         IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(self.engine.mock_committed_text, 'foo  bar')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 4)
        self.assertEqual(self.engine.mock_preedit_text, 'baz')
        self.assertEqual(self.engine.mock_preedit_text_cursor_pos, 0)
        self.assertEqual(self.engine.mock_preedit_text_visible, True)
        self.engine.do_process_key_event(IBus.KEY_Left, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'foo baz bar')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 3)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_preedit_text_cursor_pos, 0)
        self.assertEqual(self.engine.mock_preedit_text_visible, False)

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    def test_emoji_related_tab_enable_cursor_visible_escape(self):
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.set_emoji_prediction_mode(
            True, update_gsettings=False)
        self.engine.set_tab_enable(
            True, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.assertEqual(self.engine._candidates[0][0], 'camel')
        self.assertEqual(self.engine._candidates[5][0], '🐫')
        self.assertEqual(self.engine._candidates[5][2],
                         'bactrian camel')
        self.engine.do_candidate_clicked(5, 3, 0)
        self.assertEqual(self.engine._candidates[0][0], '🐫')
        self.assertEqual(self.engine._candidates[1][0], '🐪')
        self.assertEqual(
            self.engine.get_lookup_table().cursor_visible,
            False)
        self.engine.do_process_key_event(IBus.KEY_Down, 0, 0)
        self.assertEqual(
            self.engine.get_lookup_table().cursor_visible,
            True)
        self.engine.do_process_key_event(IBus.KEY_Down, 0, 0)
        self.assertEqual(
            self.engine.get_lookup_table().cursor_visible,
            True)
        self.assertEqual(
            self.engine.get_string_from_lookup_table_cursor_pos(),
            '🐪')
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        self.assertEqual(
            self.engine.get_lookup_table().cursor_visible,
            False)
        self.assertEqual(
            self.engine.get_lookup_table().get_cursor_pos(),
            0)
        self.assertEqual(
            self.engine.get_string_from_lookup_table_cursor_pos(),
            '🐫')
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        self.assertEqual(
            self.engine.get_lookup_table().cursor_visible,
            False)
        self.assertEqual(
            self.engine.get_lookup_table().get_cursor_pos(),
            0)
        self.assertEqual(self.engine._candidates[0][0], 'camel')
        self.assertEqual(self.engine._candidates[5][0], '🐫')
        self.assertEqual(self.engine._candidates[5][2],
                         'bactrian camel')
        self.engine.do_process_key_event(IBus.KEY_Down, 0, 0)
        self.assertEqual(
            self.engine.get_lookup_table().cursor_visible,
            True)
        self.assertEqual(
            self.engine.get_string_from_lookup_table_cursor_pos(),
            'camel')
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        self.assertEqual(
            self.engine.get_lookup_table().cursor_visible,
            False)
        self.assertEqual(
            self.engine.get_lookup_table().get_cursor_pos(),
            0)
        self.assertEqual(
            self.engine.get_string_from_lookup_table_cursor_pos(),
            'camel')
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        self.assertEqual(
            self.engine.get_lookup_table().get_number_of_candidates(),
            0)
        self.assertEqual(self.engine._candidates, [])
        self.assertEqual(self.engine.mock_preedit_text, 'camel')
        self.assertEqual(self.engine.mock_preedit_text_cursor_pos, 5)
        self.assertEqual(self.engine.mock_preedit_text_visible, True)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'camel ')
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_preedit_text_cursor_pos, 0)
        self.assertEqual(self.engine.mock_preedit_text_visible, False)

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('mr_IN')[0],
        "Skipping because no Marathi dictionary could be found. "
        + "On some systems like Ubuntu or Elementary OS it is not available.")
    def test_marathi_and_british_english(self):
        self.engine.set_current_imes(
            ['mr-itrans', 'NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['mr_IN', 'en_GB'], update_gsettings=False)
        self.assertEqual(
            self.engine.get_current_imes(), ['mr-itrans', 'NoIME'])
        self.assertEqual(
            self.engine.get_dictionary_names(), ['mr_IN', 'en_GB'])
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'गुरु')
        self.engine.do_process_key_event(IBus.KEY_Down, 0,
                                         IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'guru')
        self.engine.do_process_key_event(IBus.KEY_Down, 0,
                                         IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'गुरु')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'गुरु ')

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('ko_KR')[0],
        "Skipping because no Korean dictionary could be found. "
        + "On some systems like Arch Linux or FreeBSD it is not available.")
    def test_korean(self):
        self.engine.set_current_imes(
            ['ko-romaja'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['ko_KR'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_y, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_y, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '안녕하세이')
        candidates = [unicodedata.normalize('NFC', x[0])
                      for x in self.engine._candidates]
        self.assertEqual(True, '안녕하세요' in candidates)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '안녕하세요')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '안녕하세요 ')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_y, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_y, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '안녕하세이')
        candidates = [unicodedata.normalize('NFC', x[0])
                      for x in self.engine._candidates]
        self.assertEqual(True, '안녕하세요' in candidates)
        self.assertEqual('안녕하세요', candidates[0])

    def test_accent_insensitive_matching_german_dictionary(self):
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['de_DE'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_A, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_p, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.assertEqual(
            unicodedata.normalize('NFC',
                                  self.engine._candidates[0][0]),
            'Alpenglühen')
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'Alpenglühen ')

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    def test_accent_insensitive_matching_german_database(self):
        self.engine.set_current_imes(
            ['t-latn-post', 'NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['de_DE'], update_gsettings=False)
        # Type “Glühwürmchen”
        self.engine.do_process_key_event(IBus.KEY_G, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_w, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        # The German hunspell recognizes this as a correct word
        # (although it is not in the dictionary as a single word
        # it is created by rules). Therefore, it must be
        #  the first candidate here:
        self.assertEqual(
            unicodedata.normalize('NFC',
                                  self.engine._candidates[0][0]),
            'Glühwürmchen')
        # user_freq must be 0 because this word has not been found in
        # the user database, it is only a candidate because it is a
        # valid word according to hunspell:
        self.assertEqual(self.engine._candidates[0][1], 0)
        # Commit with F1:
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        # Type “Glühwürmchen” again:
        self.engine.do_process_key_event(IBus.KEY_G, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_w, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        # Again it should be the first candidate:
        self.assertEqual(
            unicodedata.normalize('NFC',
                                  self.engine._candidates[0][0]),
            'Glühwürmchen')
        # But now user_freq must be > 0 because the last commit
        # added this word to the user database:
        self.assertTrue(self.engine._candidates[0][1] > 0)
        # Commit with F1:
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(
            self.engine.mock_committed_text,
            'Glühwürmchen Glühwürmchen ')
        # Type “Gluhwurmchen” (without the accents):
        self.engine.do_process_key_event(IBus.KEY_G, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_w, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        # The first candidate should be “Glühwürmchen” again now
        # because the input phrases are added without accents into the
        # user database and before matching against the user database
        # accents are removed from the input phrase:
        self.assertEqual(
            unicodedata.normalize('NFC',
                                  self.engine._candidates[0][0]),
            'Glühwürmchen')
        # Commit with F1:
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(
            self.engine.mock_committed_text,
            'Glühwürmchen Glühwürmchen Glühwürmchen ')

    def test_accent_insensitive_matching_french_dictionary(self):
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['fr_FR'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_d, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_f, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_f, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.assertEqual(
            unicodedata.normalize('NFC',
                                  self.engine._candidates[0][0]),
            'différemment')
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'différemment ')

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    def test_emoji_triggered_by_underscore(self):
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.set_emoji_prediction_mode(
            False, update_gsettings=False)
        # Without a leading underscore, no emoji should match:
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.assertEqual(self.engine._candidates[0][0], 'camel')
        self.assertEqual(False, self.engine._candidates[5][0] == '🐫')
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'camel ')
        # Now again with a leading underscore an emoji should match.
        self.engine.do_process_key_event(IBus.KEY_underscore, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.assertEqual(self.engine._candidates[0][0], '_camel')
        self.assertEqual(self.engine._candidates[5][0], '🐫')
        self.assertEqual(self.engine._candidates[5][2],
                         'bactrian camel')
        self.engine.do_process_key_event(IBus.KEY_F6, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'camel 🐫 ')

    def test_selecting_non_existing_candidates(self):
        '''
        Test case for: https://bugzilla.redhat.com/show_bug.cgi?id=1630349

        Trying to use the 1-9 or F1-F9 keys to select candidates beyond
        the end of the candidate list should not cause ibus-typing-booster
        to stop working.
        '''
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_B, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine._candidates,
                         [('Barcelona', 0, '', False, False)])
        self.engine.do_process_key_event(IBus.KEY_2, 0, 0)
        # Nothing should be committed:
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine.mock_preedit_text, 'Barcelona2')
        self.engine.do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Barcelona')
        self.assertEqual(self.engine._candidates,
                         [('Barcelona', 0, '', False, False)])
        self.engine.do_process_key_event(IBus.KEY_1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'Barcelona ')
        self.assertEqual(self.engine.mock_preedit_text, '')

    def test_auto_capitalize(self):
        '''Test auto capitalization after punctuation
        '''
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.set_auto_capitalize(True, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'test')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine._candidates[0][0], 'test')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'test ')
        self.assertEqual(self.engine._candidates, [])
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'test')
        self.assertEqual(self.engine.mock_committed_text, 'test ')
        self.assertEqual(self.engine._candidates[0][0], 'test')
        self.engine.do_process_key_event(IBus.KEY_period, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'test test. ')
        self.assertEqual(self.engine._candidates, [])
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Test')
        self.assertEqual(self.engine.mock_committed_text, 'test test. ')
        self.assertEqual(self.engine._candidates[0][0], 'Test')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'test test. Test ')
        self.assertEqual(self.engine._candidates, [])
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'test')
        self.assertEqual(self.engine.mock_committed_text, 'test test. Test ')
        self.assertEqual(self.engine._candidates[0][0], 'test')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'test test. Test test ')
        self.assertEqual(self.engine._candidates, [])
        self.engine.do_process_key_event(IBus.KEY_period, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'test test. Test test . ')
        self.assertEqual(self.engine._candidates, [])
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Test')
        self.assertEqual(self.engine.mock_committed_text,
                         'test test. Test test . ')
        self.assertEqual(self.engine._candidates[0][0], 'Test')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'test test. Test test . Test ')
        self.engine.do_process_key_event(IBus.KEY_comma, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'test test. Test test . Test , ')
        self.assertEqual(self.engine._candidates, [])
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'hello')
        self.assertEqual(self.engine.mock_committed_text,
                         'test test. Test test . Test , ')
        self.assertEqual(self.engine._candidates[0][0], 'hello')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'test test. Test test . Test , hello ')

    def test_add_space_on_commit(self):
        '''Test new option to avoid adding spaces when committing by label
        (1-9 or F1-F9 key) or by mouse click.  See:
        https://github.com/mike-fabian/ibus-typing-booster/issues/39
        '''
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'test')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine._candidates[0][0], 'test')
        self.engine.do_process_key_event(IBus.KEY_1, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        # By default a space should be added:
        self.assertEqual(self.engine.mock_committed_text, 'test ')
        # Now set the option to avoid the extra space:
        self.engine.set_keybindings({
            'commit_candidate_1': ['1', 'KP_1'],
            'commit_candidate_1_plus_space': ['F1'],
        }, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'test')
        self.assertEqual(self.engine.mock_committed_text, 'test ')
        self.assertEqual(self.engine._candidates[0][0], 'test')
        self.engine.do_process_key_event(IBus.KEY_1, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        # No space should be added now:
        self.assertEqual(self.engine.mock_committed_text, 'test test')

    def test_tab_enable_key_binding_changed(self):
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.set_tab_enable(True, update_gsettings=False)
        self.engine.set_keybindings({
            'enable_lookup': ['Insert'], # changed from default Tab
        }, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        # Tab should trigger a commit now instead of enabling the
        # lookup (which is what Tab would do by default):
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.assertEqual(len(self.engine._candidates), 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'test\t')
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Insert, 0, 0)
        self.assertEqual(self.engine._candidates[0][0], 'cerulean')
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'test\tcerulean ')

    def test_hi_inscript2_rupee_symbol(self):
        dummy_trans = self.get_transliterator_or_skip('hi-inscript2')
        self.engine.set_current_imes(
            ['hi-inscript2'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['hi_IN'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_4, 0, IBus.ModifierType.MOD5_MASK)
        self.assertEqual(self.engine.mock_preedit_text, '₹')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, '₹ ')

    def test_digits_used_in_keybindings(self):
        self.engine.set_current_imes(
            ['hi-itrans'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['hi_IN'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_0, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_1, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_2, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_3, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_4, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_5, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_6, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_7, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_8, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_9, 0, 0)
        # As digits are used in the default key bindings,
        # the typed digits should be transliterated to
        # Hindi digits and committed immediately:
        self.assertEqual(len(self.engine._candidates), 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '०१२३४५६७८९')
        # Now remove all digits from the key bindings and type
        # the same digits again:
        self.engine.set_keybindings({
            'commit_candidate_1': [],
            'commit_candidate_1_plus_space': ['F1'],
            'commit_candidate_2': [],
            'commit_candidate_2_plus_space': ['F2'],
            'commit_candidate_3': [],
            'commit_candidate_3_plus_space': ['F3'],
            'commit_candidate_4': [],
            'commit_candidate_4_plus_space': ['F4'],
            'commit_candidate_5': [],
            'commit_candidate_5_plus_space': ['F5'],
            'commit_candidate_6': [],
            'commit_candidate_6_plus_space': ['F6'],
            'commit_candidate_7': [],
            'commit_candidate_7_plus_space': ['F7'],
            'commit_candidate_8': [],
            'commit_candidate_8_plus_space': ['F8'],
            'commit_candidate_9': [],
            'commit_candidate_9_plus_space': ['F9'],
        }, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_0, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_1, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_2, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_3, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_4, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_5, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_6, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_7, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_8, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_9, 0, 0)
        # The newly typed digits should be in the preedit now
        # and the committed text should still be unchanged:
        self.assertEqual(self.engine.mock_preedit_text, '०१२३४५६७८९')
        self.assertEqual(self.engine.mock_committed_text, '०१२३४५६७८९')
        # Commit:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         '०१२३४५६७८९०१२३४५६७८९ ')

    def test_commit_candidate_1_without_space(self):
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.set_keybindings({
            'commit_candidate_1': ['Right'],
        }, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.assertEqual(self.engine._candidates[0][0], 'cerulean')
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'cerulean ')
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.assertEqual(self.engine._candidates[0][0], 'cerulean')
        self.engine.do_process_key_event(IBus.KEY_Right, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'cerulean cerulean')

    def test_toggle_candidate_case(self):
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.assertEqual(self.engine._candidates[0][0], 'cerulean')
        # Shift_L goes to 'capitalize':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._candidates[0][0], 'Cerulean')
        # The next Shift_L goes to 'upper':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._candidates[0][0], 'CERULEAN')
        # Shift_R goes back to 'capitalize':
        self.engine.do_process_key_event(IBus.KEY_Shift_R, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_R, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._candidates[0][0], 'Cerulean')
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'Cerulean ')

    def test_sinhala_wijesekera(self):
        self.engine.set_current_imes(
            ['si-wijesekera', 'NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_v, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_k, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_I, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ඩනිෂ්ක')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ඩනිෂ්ක ')
        self.engine.do_process_key_event(IBus.KEY_k, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_j, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_S, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_k, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'නවීන්')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ඩනිෂ්ක නවීන් ')

    def test_vietnamese_telex(self):
        # See also https://fedoraproject.org/wiki/QA:Bogo
        #
        # Type "Khoong cos gif quis hown ddoocj laapj tuwj do"
        #
        # You will get the Vietnamese string "Không có gì quí hơn độc lập tự do".
        #
        # This works exactly the same with ibus-unikey, ibus-bogo, or
        # vi-telex used with ibus-m17n or ibus-typing-booster.
        self.engine.set_current_imes(
            ['vi-telex', 'NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['vi_VN'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_K, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Không')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'Không ')
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'có')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'Không có ')
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_f, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'gì')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'Không có gì ')
        self.engine.do_process_key_event(IBus.KEY_q, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'quí')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'Không có gì quí ')
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_w, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'hơn')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'Không có gì quí hơn ')
        self.engine.do_process_key_event(IBus.KEY_d, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_d, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_j, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'độc')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'Không có gì quí hơn độc ')
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_p, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_j, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'lập')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'Không có gì quí hơn độc lập ')
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_w, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_j, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'tự')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'Không có gì quí hơn độc lập tự ')
        self.engine.do_process_key_event(IBus.KEY_d, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'do')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'Không có gì quí hơn độc lập tự do ')

    def test_compose_and_latn_post(self):
        self.engine.set_current_imes(
            ['t-latn-post', 'NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_T, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Tr⎄')
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Tr⎄"')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Trä')
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_dead_diaeresis, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Tränen¨')
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Tränenü')
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Tränenüberstr⎄')
        self.engine.do_process_key_event(IBus.KEY_diaeresis, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Tränenüberstr⎄¨')
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Tränenüberströ')
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Tränenüberströmt')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'Tränenüberströmt ')
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        # Using t-latn-post here for the u:
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'grü')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'grü⎄s')
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'grüß')
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'grüßt')
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'grüßte')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'Tränenüberströmt grüßte ')
        self.engine.do_process_key_event(IBus.KEY_d, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'Tränenüberströmt grüßte das ')
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        # Using t-latn-post here for the ß:
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'gros')
        self.engine.do_process_key_event(IBus.KEY_slash, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'groß')
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'große')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'Tränenüberströmt grüßte das große ')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_S, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '⎄S')
        self.engine.do_process_key_event(IBus.KEY_S, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ẞ')

    def test_compose_sequences_containing_code_points(self):
        self.engine.set_current_imes(
            ['t-latn-pre', 'NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_dead_macron, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '¯')
        self.engine.do_process_key_event(0x01EB, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭ')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭ⎄')
        self.engine.do_process_key_event(IBus.KEY_macron, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭ⎄¯')
        self.engine.do_process_key_event(0x01EB, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭ')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭ⎄')
        self.engine.do_process_key_event(IBus.KEY_underscore, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭ⎄_')
        self.engine.do_process_key_event(0x01EB, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭ')
        self.engine.do_process_key_event(IBus.KEY_dead_macron, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭ¯')
        self.engine.do_process_key_event(IBus.KEY_dead_ogonek, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭ¯˛')
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭ')
        self.engine.do_process_key_event(IBus.KEY_dead_macron, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭ¯')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭ¯⎄')
        self.engine.do_process_key_event(IBus.KEY_semicolon, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭ¯⎄;')
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭ')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭ⎄')
        self.engine.do_process_key_event(IBus.KEY_macron, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭ⎄¯')
        self.engine.do_process_key_event(IBus.KEY_dead_ogonek, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭ⎄¯˛')
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭ')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭ⎄')
        self.engine.do_process_key_event(IBus.KEY_macron, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭ⎄¯')
        self.engine.do_process_key_event(IBus.KEY_semicolon, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭ⎄¯;')
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭ')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭ⎄')
        self.engine.do_process_key_event(IBus.KEY_underscore, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭ⎄_')
        self.engine.do_process_key_event(IBus.KEY_dead_ogonek, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭ⎄_˛')
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭǭ')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭǭ⎄')
        self.engine.do_process_key_event(IBus.KEY_underscore, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭǭ⎄_')
        self.engine.do_process_key_event(IBus.KEY_semicolon, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭǭ⎄_;')
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭǭǭ')
        self.engine.do_process_key_event(IBus.KEY_dead_caron, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭǭǭˇ')
        self.engine.do_process_key_event(IBus.KEY_EZH, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭǭǭǮ')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭǭǭǮ⎄')
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭǭǭǮ⎄c')
        self.engine.do_process_key_event(IBus.KEY_EZH, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭǭǭǮǮ')
        self.engine.do_process_key_event(IBus.KEY_dead_caron, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭǭǭǮǮˇ')
        self.engine.do_process_key_event(IBus.KEY_ezh, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭǭǭǮǮǯ')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭǭǭǮǮǯ⎄')
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭǭǭǮǮǯ⎄c')
        self.engine.do_process_key_event(IBus.KEY_ezh, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭǭǭǭǭǭǭǭǭǮǮǯǯ')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ǭǭǭǭǭǭǭǭǭǮǮǯǯ ')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '⎄')
        self.engine.do_process_key_event(0x2276, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '⎄≶')
        self.engine.do_process_key_event(0x0338, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '≸')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ǭǭǭǭǭǭǭǭǭǮǮǯǯ ≸ ')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '⎄')
        self.engine.do_process_key_event(0x093C, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '⎄़')
        self.engine.do_process_key_event(0x0915, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'क़')
        self.assertEqual(self.engine.mock_preedit_text, '\u0915\u093C')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'ǭǭǭǭǭǭǭǭǭǮǮǯǯ ≸ \u0915\u093C ')

    def test_compose_combining_chars_in_preedit_representation(self):
        self.engine.set_current_imes(
            ['t-latn-post', 'NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'a')
        self.engine.do_process_key_event(IBus.KEY_dead_belowdiaeresis, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'a\u00A0\u0324')
        self.assertEqual(self.engine.mock_preedit_text, 'a ̤')
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'aṳ')

    @unittest.skipUnless(
        IMPORT_LIBVOIKKO_SUCCESSFUL,
        "Skipping because this test requires python3-libvoikko to work.")
    def test_voikko(self):
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['fi_FI'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_k, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine._candidates, [
            ('kissa', -1, '', False, True),
            ('kissaa', -1, '', False, True),
            ('kisassa', -1, '', False, True),
            ('kisussa', -1, '', False, True)
        ])

    @unittest.skipUnless(
        IMPORT_LIBVOIKKO_SUCCESSFUL,
        "Skipping because this test requires python3-libvoikko to work.")
    def test_voikko_en_GB_fi_FI(self):
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_GB', 'fi_FI'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_k, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine._candidates, [
            ('kiss', -1, '', False, True),
            ('kissa', -1, '', False, True),
            ('kissaa', -1, '', False, True),
            ('kisassa', -1, '', False, True),
            ('kisussa', -1, '', False, True)
        ])

    def test_control_alpha(self):
        '''Test case for
        https://github.com/mike-fabian/ibus-typing-booster/issues/107

        Control+Greek_alpha shouild trigger a commit and forward
        the key to the application.
        '''
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_GB'], update_gsettings=False)
        self.engine.do_process_key_event(
            IBus.KEY_Greek_alpha, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'α')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(
            IBus.KEY_Greek_alpha, 0, IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'αα')

if __name__ == '__main__':
    unittest.main()
