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
This file implements the test cases for the unit tests of ibus-typing-booster emulating ibus-m17n
'''


from typing import Any
from typing import Optional
from typing import Dict
from typing import List
import os
import sys
import re
import logging
import unittest
import importlib
from unittest import mock

# pylint: disable=wrong-import-position
from gi import require_version # type: ignore
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore
require_version('Gdk', '3.0')
from gi.repository import Gdk
# pylint: enable=wrong-import-position

LOGGER = logging.getLogger('ibus-typing-booster')

# Get more verbose output in the test log:
os.environ['IBUS_TYPING_BOOSTER_DEBUG_LEVEL'] = '255'

# pylint: disable=import-error
from mock_engine import MockEngine
from mock_engine import MockLookupTable
from mock_engine import MockProperty
from mock_engine import MockPropList
# pylint: enable=import-error

# pylint: disable=wrong-import-order
sys.path.insert(0, "../engine")
# pylint: disable=import-error
import hunspell_table
import tabsqlitedb
import itb_util
import m17n_translit
# pylint: enable=import-error
sys.path.pop(0)
# pylint: enable=wrong-import-order

# pylint: disable=missing-function-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=invalid-name

@unittest.skipIf(Gdk.Display.open('') is None, 'Display cannot be opened.')
class ItbM17nEmuTestCase(unittest.TestCase):
    '''
    Test cases for ibus-typing-booster emulating ibus-m17n
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

    orig_disable_in_terminals = False
    orig_ascii_digits = False
    orig_emoji_prediction_mode = False
    orig_off_the_record_mode = False
    orig_record_mode = 0
    orig_emoji_trigger_characters = '_'
    orig_auto_commit_characters = ''
    orig_tab_enable = False
    orig_inline_completion = 0
    orig_auto_capitalize = False
    orig_auto_select_candidate = 0
    orig_remember_last_used_preedit_ime = False
    orig_page_size = 6
    orig_lookup_table_orientation = 1
    orig_min_char_complete = 1
    orig_show_number_of_candidates = False
    orig_show_status_info_in_auxiliary_text = False
    orig_add_space_on_commit = True
    orig_current_imes: List[str] = []
    orig_dictionary_names: List[str] = []
    orig_avoid_forward_key_event = False
    orig_keybindings: Dict[str, List[str]] = {}
    orig_use_ibus_keymap = False
    orig_ibus_keykmap = 'in'

    def setUp(self) -> None:
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
        self.database: Optional[tabsqlitedb.TabSqliteDb] = None
        self.engine: Optional[hunspell_table.TypingBoosterEngine] = None

    def tearDown(self) -> None:
        if self.engine is not None:
            self.restore_original_settings()
        self.engine = None
        if self.database is not None:
            self.database.database.close()
        self.database = None
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

    def backup_original_settings(self) -> None:
        if self.engine is None:
            return
        self.orig_disable_in_terminals = (
            self.engine.get_disable_in_terminals())
        self.orig_ascii_digits = (
            self.engine.get_ascii_digits())
        self.orig_emoji_prediction_mode = (
            self.engine.get_emoji_prediction_mode())
        self.orig_off_the_record_mode = (
            self.engine.get_off_the_record_mode())
        self.orig_record_mode = (
            self.engine.get_record_mode())
        self.orig_emoji_trigger_characters = (
            self.engine.get_emoji_trigger_characters())
        self.orig_auto_commit_characters = (
            self.engine.get_auto_commit_characters())
        self.orig_tab_enable = (
            self.engine.get_tab_enable())
        self.orig_inline_completion = (
            self.engine.get_inline_completion())
        self.orig_auto_capitalize = (
            self.engine.get_auto_capitalize())
        self.orig_auto_select_candidate = (
            self.engine.get_auto_select_candidate())
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
        self.orig_avoid_forward_key_event = (
            self.engine.get_avoid_forward_key_event())
        self.orig_keybindings = (
            self.engine.get_keybindings())
        self.orig_use_ibus_keymap = (
            self.engine.get_use_ibus_keymap())
        self.orig_ibus_keymap = (
            self.engine.get_ibus_keymap())

    def restore_original_settings(self) -> None:
        if self.engine is None:
            return
        self.engine.set_disable_in_terminals(
            self.orig_disable_in_terminals,
            update_gsettings=False)
        self.engine.set_ascii_digits(
            self.orig_ascii_digits,
            update_gsettings=False)
        self.engine.set_emoji_prediction_mode(
            self.orig_emoji_prediction_mode,
            update_gsettings=False)
        self.engine.set_off_the_record_mode(
            self.orig_off_the_record_mode,
            update_gsettings=False)
        self.engine.set_record_mode(
            self.orig_record_mode,
            update_gsettings=False)
        self.engine.set_emoji_trigger_characters(
            self.orig_emoji_trigger_characters,
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
        self.engine.set_auto_select_candidate(
            self.orig_auto_select_candidate,
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
        self.engine.set_avoid_forward_key_event(
            self.orig_avoid_forward_key_event,
            update_gsettings=False)
        self.engine.set_keybindings(
            self.orig_keybindings,
            update_gsettings=False)
        self.engine.set_use_ibus_keymap(
            self.orig_use_ibus_keymap,
            update_gsettings=False)
        self.engine.set_ibus_keymap(
            self.orig_ibus_keymap,
            update_gsettings=False)

    def set_default_settings(self) -> None:
        if self.engine is None:
            return
        for key in self.engine._settings_dict:
            if 'set_function' in self.engine._settings_dict[key]:
                self.engine._settings_dict[key]['set_function'](
                    self.engine._settings_dict[key]['default'],
                    update_gsettings=False)
        return

    def init_engine(self, engine_name: str = 'typing-booster') -> None:
        self.database = tabsqlitedb.TabSqliteDb(user_db_file=':memory:')
        engine_path = ('/com/redhat/IBus/engines/typing_booster/'
                       f"{re.sub(r'[^a-zA-Z0-9_/]', '_', engine_name)}"
                       '/engine/')
        if engine_name != 'typing-booster':
            match = itb_util.M17N_ENGINE_NAME_PATTERN.search(engine_name)
            if not match:
                raise ValueError('Invalid engine name.')
            m17n_ime_lang = match.group('lang')
            m17n_ime_name = match.group('name')
            self.get_transliterator_or_skip(f'{m17n_ime_lang}-{m17n_ime_name}')
        engine_id = 0
        self.engine = hunspell_table.TypingBoosterEngine(
            self.bus,
            engine_path + str(engine_id),
            self.database,
            engine_name=engine_name,
            unit_test=True)
        if self.engine is None:
            self.skipTest('Failed to init engine.')
        self.backup_original_settings()
        self.set_default_settings()

    def get_transliterator_or_skip(self, ime: str) -> Optional[Any]:
        try:
            sys.stderr.write(f'ime "{ime}" ... ')
            trans = m17n_translit.Transliterator(ime)
        except ValueError as error:
            trans = None
            self.skipTest(error)
        except Exception as error: # pylint: disable=broad-except
            sys.stderr.write('Unexpected exception!')
            trans = None
            self.skipTest(error)
        return trans

    def test_dummy(self) -> None:
        self.init_engine()
        self.assertEqual(True, True)

    @unittest.expectedFailure
    def test_expected_failure(self) -> None:
        self.init_engine()
        self.assertEqual(False, True)

    def test_typing_booster_normal(self) -> None:
        self.init_engine(engine_name='typing-booster')
        if self.engine is None:
            self.skipTest('Failed to init engine.')
        self.engine.set_current_imes(
            ['t-latn-post', 'NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        # Normal typing booster should have some candidates now:
        self.assertNotEqual([], self.engine._candidates)
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'ä ')

    def test_tb_t_latn_post(self) -> None:
        self.init_engine(engine_name='tb:t:latn-post')
        if self.engine is None:
            self.skipTest('Failed to init engine.')
        self.assertEqual(self.engine._engine_name, 'tb:t:latn-post')
        self.assertEqual(self.engine._dictionary_names, ['None'])
        self.assertEqual(self.engine._current_imes, ['t-latn-post'])
        self.assertEqual(self.engine._tab_enable, True)
        self.assertEqual(self.engine._off_the_record, True)
        self.assertEqual(self.engine._preedit_underline, 0)
        self.assertEqual(self.engine._keybindings['toggle_input_mode_on_off'], [])
        self.assertEqual(self.engine._keybindings['enable_lookup'], [])
        self.assertEqual(self.engine._keybindings['commit_and_forward_key'], ['Left'])
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'a')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 0)
        # Restricted typing booster should have *no* candidates now:
        self.assertEqual([], self.engine._candidates)
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ä')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ä ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 2)
        # Type more and commit with 'Left':
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'n')
        self.assertEqual(self.engine.mock_committed_text, 'ä ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 2)
        self.engine.do_process_key_event(IBus.KEY_asciitilde, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ñ')
        self.assertEqual(self.engine.mock_committed_text, 'ä ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 2)
        self.engine.do_process_key_event(IBus.KEY_Left, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ä ñ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 2)
        # Type more and commit with space again:
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'a')
        self.assertEqual(self.engine.mock_committed_text, 'ä ñ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 2)
        self.engine.do_process_key_event(IBus.KEY_slash, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'å')
        self.assertEqual(self.engine.mock_committed_text, 'ä ñ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 2)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ä å ñ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 4)

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    # Activate this to see a lot of logging when running the tests
    # manually:
    # LOGGER.addHandler(LOG_HANDLER)
    unittest.main()
