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
from typing import TYPE_CHECKING
import os
import glob
import sys
import re
import logging
import tempfile
import shutil
import unittest
import importlib
from unittest import mock

# pylint: disable=wrong-import-position
from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus
require_version('GLib', '2.0')
from gi.repository import GLib # type: ignore
# pylint: enable=wrong-import-position

LOGGER = logging.getLogger('ibus-typing-booster')

# Get more verbose output in the test log:
os.environ['IBUS_TYPING_BOOSTER_DEBUG_LEVEL'] = '255'

# pylint: disable=import-error
from mock_engine import MockEngine
from mock_engine import MockLookupTable
from mock_engine import MockProperty
from mock_engine import MockPropList
from mock_engine import mock_glib_idle_add
from mock_engine import mock_glib_timeout_add
# pylint: enable=import-error

import testutils # pylint: disable=import-error

# Avoid failing test cases because of stuff in the users M17NDIR ('~/.m17n.d'):
# The environments needs to be changed *before* `import m17n_translit`
# since libm17n reads it at load time!
_ORIG_M17NDIR = os.environ.pop('M17NDIR', None)
_TEMPDIR = tempfile.TemporaryDirectory() # pylint: disable=consider-using-with
os.environ['M17NDIR'] = _TEMPDIR.name

# pylint: disable=wrong-import-order
sys.path.insert(0, "../engine")
# pylint: disable=import-error
from itb_gtk import Gdk # type: ignore
if TYPE_CHECKING:
    # These imports are only for type checkers (mypy). They must not be
    # executed at runtime because itb_gtk controls the Gtk/Gdk versions.
    # pylint: disable=reimported
    from gi.repository import Gdk  # type: ignore
    # pylint: enable=reimported
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
    glib_idle_add_patcher = mock.patch.object(
        GLib, 'idle_add', new=mock_glib_idle_add)
    glib_timeout_add_patcher = mock.patch.object(
        GLib, 'timeout_add', new=mock_glib_timeout_add)
    ibus_engine = IBus.Engine
    ibus_lookup_table = IBus.LookupTable
    ibus_property = IBus.Property
    ibus_prop_list = IBus.PropList
    glib_idle_add = GLib.idle_add
    glib_timeout_add = GLib.timeout_add

    _tempdir: Optional[tempfile.TemporaryDirectory] = None # type: ignore[type-arg]
    # Python 3.12+: _tempdir: Optional[tempfile.TemporaryDirectory[str]] = None
    _orig_m17ndir: Optional[str] = None
    _m17ndir: Optional[str] = None
    _m17n_config_file: Optional[str] = None
    _orig_xcomposefile: Optional[str] = None

    orig_disable_in_terminals = False
    orig_ascii_digits = False
    orig_word_prediction_mode = True
    orig_emoji_prediction_mode = False
    orig_unicode_data_all_mode = False
    orig_off_the_record_mode = False
    orig_record_mode = 0
    orig_emoji_trigger_characters = '_'
    orig_emoji_style = 'emoji'
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
    orig_ibus_keymap = 'in'

    @classmethod
    def setUpClass(cls) -> None:
        cls._tempdir = _TEMPDIR
        cls._orig_m17ndir = _ORIG_M17NDIR
        cls._m17ndir = cls._tempdir.name
        cls._m17n_config_file = os.path.join(cls._m17ndir, 'config.mic')
        # Copy test input methods into M17NDIR
        for mim_path in glob.glob(os.path.join(os.path.dirname(__file__), '*.mim')):
            shutil.copy(mim_path, cls._m17ndir)
        # Avoid failing test cases because of stuff in the users '~/.XCompose' file.
        cls._orig_xcomposefile = os.environ.pop('XCOMPOSEFILE', None)
        os.environ['XCOMPOSEFILE'] = os.path.join(cls._tempdir.name, 'XCompose')
        shutil.copy('XCompose', cls._tempdir.name)
        # List contents of Temporary directory used for m17n files and XCompose:
        m17n_dir_files = [os.path.join(cls._m17ndir, name)
                          for name in os.listdir(cls._m17ndir)]
        for path in m17n_dir_files:
            LOGGER.info('M17NDIR content: %r', path)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._orig_m17ndir is not None:
            os.environ['M17NDIR'] = cls._orig_m17ndir
        else:
            _value = os.environ.pop('M17NDIR', None)
        if cls._orig_xcomposefile is not None:
            os.environ['XCOMPOSEFILE'] = cls._orig_xcomposefile
        else:
            _value = os.environ.pop('XCOMPOSEFILE', None)
        if cls._tempdir is not None:
            cls._tempdir.cleanup()

    @property
    def m17n_config_file(self) -> str:
        assert self.__class__._m17n_config_file is not None # pylint: disable=protected-access
        return self.__class__._m17n_config_file # pylint: disable=protected-access

    def setUp(self) -> None:
        # Patch the IBus stuff with the mock classes:
        self.__class__.engine_patcher.start()
        self.__class__.lookup_table_patcher.start()
        self.__class__.property_patcher.start()
        self.__class__.prop_list_patcher.start()
        self.__class__.glib_idle_add_patcher.start()
        self.__class__.glib_timeout_add_patcher.start()
        assert IBus.Engine is not self.__class__.ibus_engine
        assert IBus.Engine is MockEngine # type: ignore[comparison-overlap]
        assert IBus.LookupTable is not self.__class__.ibus_lookup_table
        assert IBus.LookupTable is MockLookupTable # type: ignore[comparison-overlap]
        assert IBus.Property is not self.__class__.ibus_property
        assert IBus.Property is MockProperty # type: ignore[comparison-overlap]
        assert IBus.PropList is not self.__class__.ibus_prop_list
        assert IBus.PropList is MockPropList # type: ignore[comparison-overlap]
        assert GLib.idle_add is not self.__class__.glib_idle_add
        assert GLib.idle_add is mock_glib_idle_add
        assert GLib.timeout_add is not self.__class__.glib_timeout_add
        assert GLib.timeout_add is mock_glib_timeout_add
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
        self.__class__.engine_patcher.stop()
        self.__class__.lookup_table_patcher.stop()
        self.__class__.property_patcher.stop()
        self.__class__.prop_list_patcher.stop()
        self.__class__.glib_idle_add_patcher.stop()
        self.__class__.glib_timeout_add_patcher.stop()
        assert IBus.Engine is self.__class__.ibus_engine
        assert IBus.Engine is not MockEngine # type: ignore[comparison-overlap]
        assert IBus.LookupTable is self.__class__.ibus_lookup_table
        assert IBus.LookupTable is not MockLookupTable # type: ignore[comparison-overlap]
        assert IBus.Property is self.__class__.ibus_property
        assert IBus.Property is not MockProperty # type: ignore[comparison-overlap]
        assert IBus.PropList is self.__class__.ibus_prop_list
        assert IBus.PropList is not MockPropList # type: ignore[comparison-overlap]
        assert GLib.idle_add is self.__class__.glib_idle_add
        assert GLib.idle_add is not mock_glib_idle_add
        assert GLib.timeout_add is self.__class__.glib_timeout_add
        assert GLib.timeout_add is not mock_glib_timeout_add

    def backup_original_settings(self) -> None:
        if self.engine is None:
            return
        self.orig_disable_in_terminals = (
            self.engine.get_disable_in_terminals())
        self.orig_ascii_digits = (
            self.engine.get_ascii_digits())
        self.orig_word_prediction_mode = (
            self.engine.get_word_prediction_mode())
        self.orig_emoji_prediction_mode = (
            self.engine.get_emoji_prediction_mode())
        self.orig_unicode_data_all_mode = (
            self.engine.get_unicode_data_all_mode())
        self.orig_off_the_record_mode = (
            self.engine.get_off_the_record_mode())
        self.orig_record_mode = (
            self.engine.get_record_mode())
        self.orig_emoji_trigger_characters = (
            self.engine.get_emoji_trigger_characters())
        self.orig_emoji_style = (
            self.engine.get_emoji_style())
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
        self.engine.set_word_prediction_mode(
            self.orig_word_prediction_mode,
            update_gsettings=False)
        self.engine.set_emoji_prediction_mode(
            self.orig_emoji_prediction_mode,
            update_gsettings=False)
        self.engine.set_unicode_data_all_mode(
            self.orig_unicode_data_all_mode,
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
        self.engine.set_emoji_style(
            self.orig_emoji_style,
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

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('en_US')[0],
        'Skipping because no en_US hunspell dictionary could be found.')
    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
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
        self.assertEqual(self.engine._tab_enable, False) # normal default
        self.assertEqual(self.engine._word_predictions, False)
        self.assertEqual(self.engine._emoji_predictions, False)
        self.assertEqual(self.engine._off_the_record, True)
        self.assertEqual(self.engine._preedit_underline, 0)
        self.assertEqual(self.engine._keybindings['toggle_input_mode_on_off'], [])
        self.assertEqual(self.engine._keybindings['enable_lookup'], ['Tab', 'ISO_Left_Tab']) # normal default
        self.assertEqual(self.engine._keybindings['commit_and_forward_key'],
                         ['Left', 'Control+Left'])
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

    def test_tb_zh_py(self) -> None:
        self.init_engine(engine_name='tb:zh:py')
        if self.engine is None:
            self.skipTest('Failed to init engine.')
        self.assertEqual(self.engine._engine_name, 'tb:zh:py')
        self.assertEqual(self.engine._dictionary_names, ['None'])
        self.assertEqual(self.engine._current_imes, ['zh-py'])
        self.assertEqual(self.engine._tab_enable, False) # normal default
        self.assertEqual(self.engine._word_predictions, False)
        self.assertEqual(self.engine._emoji_predictions, False)
        self.assertEqual(self.engine._off_the_record, True)
        self.assertEqual(self.engine._preedit_underline, 0)
        self.assertEqual(self.engine._keybindings['toggle_input_mode_on_off'], [])
        self.assertEqual(self.engine._keybindings['enable_lookup'],
                         ['Tab', 'ISO_Left_Tab']) # normal default
        self.assertEqual(self.engine._keybindings['commit_and_forward_key'],
                         ['Left', 'Control+Left'])
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '爱')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 0)
        # There should be candidates now
        self.assertNotEqual([], self.engine._candidates)
        # One `>` commits:
        self.engine.do_process_key_event(IBus.KEY_greater, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '>')
        self.assertEqual(self.engine.mock_committed_text, '爱')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 1)
        # There should be no candidates now
        self.assertEqual([], self.engine._candidates)
        # The single `>` did not switch to fullwidth mode and
        # it gets early committed in _handle_m17n_candidates()
        # when the following `a` is typed.
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '啊')
        self.assertEqual(self.engine.mock_committed_text, '爱>')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 2)
        # There should be candidates now
        self.assertNotEqual([], self.engine._candidates)
        # One `>` commits:
        self.engine.do_process_key_event(IBus.KEY_greater, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '>')
        self.assertEqual(self.engine.mock_committed_text, '爱>啊')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 3)
        # There should be no candidates now
        self.assertEqual([], self.engine._candidates)
        # The second `>` switches to fullwidth-mode (`>>` should
        # switch to fullwidth-mode) and because this just did the mode switch
        # the `>>` should disappear input and not show up in the preedit:
        self.engine.do_process_key_event(IBus.KEY_greater, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '爱>啊')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 3)
        # There should be no candidates now
        self.assertEqual([], self.engine._candidates)
        # Fullwidth a:
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '爱>啊ａ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 4)
        # There should be no candidates now
        self.assertEqual([], self.engine._candidates)
        # Fullwidth space
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '爱>啊ａ\u3000')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 5)
        # There should be no candidates now
        self.assertEqual([], self.engine._candidates)
        # Fullwidth b:
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '爱>啊ａ\u3000ｂ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 6)
        # There should be no candidates now
        self.assertEqual([], self.engine._candidates)
        # One `<` does not exit fullwidth mode, it is shown in fullwidth
        # in the preedit:
        self.engine.do_process_key_event(IBus.KEY_less, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '＜')
        self.assertEqual(self.engine.mock_committed_text, '爱>啊ａ\u3000ｂ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 6)
        # There should be no candidates now
        self.assertEqual([], self.engine._candidates)
        # When the following `c` is typed, '＜ｃ' gets
        # early committed in _process_key_event()
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '爱>啊ａ\u3000ｂ＜ｃ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 8)
        # Exit fullwidth mode with `<<`:
        self.engine.do_process_key_event(IBus.KEY_less, 0, 0)
        # The first `<` did not switch yet, so it is still shown in
        # fullwidth in the preedit:
        self.assertEqual(self.engine.mock_preedit_text, '＜')
        self.assertEqual(self.engine.mock_committed_text, '爱>啊ａ\u3000ｂ＜ｃ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 8)
        self.engine.do_process_key_event(IBus.KEY_less, 0, 0)
        # The second `<` does the switch and the preedit becomes empty
        # because the `<<` did just the mode switch:
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '爱>啊ａ\u3000ｂ＜ｃ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 8)
        # There should be no candidates now
        self.assertEqual([], self.engine._candidates)
        # a produces a Chinese character again:
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '啊')
        self.assertEqual(self.engine.mock_committed_text, '爱>啊ａ\u3000ｂ＜ｃ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 8)
        # There should be candidates now
        self.assertNotEqual([], self.engine._candidates)
        # `Z` commits:
        self.engine.do_process_key_event(IBus.KEY_Z, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '爱>啊ａ\u3000ｂ＜ｃ啊')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 9)
        # There should be no candidates now
        self.assertEqual([], self.engine._candidates)
        # `Za` should switch to single-fullwidth-mode (i.e. fullwidth-mode
        # just for the next character) That does not work at the moment
        # because each transliteration in m17n_translit.py is finallized
        # by appending Mnil, that counts as the next character. So the mode
        # switch by `Z` does not survive the commit. That is hard to fix
        # but maybe not so important.
        # Currently, the `a` produces a Chinese character again:
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '啊')
        self.assertEqual(self.engine.mock_committed_text, '爱>啊ａ\u3000ｂ＜ｃ啊')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 9)
        # There should be candidates now
        self.assertNotEqual([], self.engine._candidates)
        # Commit with a space:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '爱>啊ａ\u3000ｂ＜ｃ啊啊')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 10)
        # There should be no candidates now
        self.assertEqual([], self.engine._candidates)
        # `Za` when there is no pending input commits a fullwidth a immediately:
        self.engine.do_process_key_event(IBus.KEY_Z, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '爱>啊ａ\u3000ｂ＜ｃ啊啊ａ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 11)
        # There should be no candidates now
        self.assertEqual([], self.engine._candidates)
        # `Z ` when there is no pending input commits a fullwidth space immediately
        self.engine.do_process_key_event(IBus.KEY_Z, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '爱>啊ａ\u3000ｂ＜ｃ啊啊ａ\u3000')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 12)

    def test_tb_ko_romaja(self) -> None:
        self.init_engine(engine_name='tb:ko:romaja')
        if self.engine is None:
            self.skipTest('Failed to init engine.')
        self.assertEqual(self.engine._engine_name, 'tb:ko:romaja')
        self.assertEqual(self.engine._dictionary_names, ['None'])
        self.assertEqual(self.engine._current_imes, ['ko-romaja'])
        self.assertEqual(self.engine._tab_enable, False) # normal default
        self.assertEqual(self.engine._word_predictions, False)
        self.assertEqual(self.engine._emoji_predictions, False)
        self.assertEqual(self.engine._off_the_record, True)
        self.assertEqual(self.engine._preedit_underline, 0)
        self.assertEqual(self.engine._keybindings['toggle_input_mode_on_off'], [])
        self.assertEqual(self.engine._keybindings['enable_lookup'],
                         ['Tab', 'ISO_Left_Tab']) # normal default
        self.assertEqual(self.engine._keybindings['commit_and_forward_key'],
                         ['Left', 'Control+Left'])
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '하')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 0)
        # `I` commits and switches from normal syllable mode to
        # isolated jamo mode:
        self.engine.do_process_key_event(IBus.KEY_I, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '하')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 1)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 2)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ㅏ')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 2)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 4)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 5)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ㅏ')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 5)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 6)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ㅣ')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 6)
        # `I` commits and switches from back to normal syllable mode from
        # isolated jamo mode:
        self.engine.do_process_key_event(IBus.KEY_I, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 7)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ㅎ')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 7)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '하')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 7)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '해')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 7)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '핸')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 7)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ핺')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 8)
        # `Z Za` inserts a fullwidth space and a fullwidth a:
        self.engine.do_process_key_event(IBus.KEY_Z, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ핺')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 8)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ핺\u3000')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 9)
        self.engine.do_process_key_event(IBus.KEY_Z, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ핺\u3000')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 9)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ핺\u3000ａ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 10)
        # `>>` switches to fullwidth mode:
        self.engine.do_process_key_event(IBus.KEY_greater, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '>')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ핺\u3000ａ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 10)
        self.engine.do_process_key_event(IBus.KEY_greater, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ핺\u3000ａ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 10)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ핺\u3000ａａ　ｂ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 13)
        # `<<` switches back to normal mode:
        self.engine.do_process_key_event(IBus.KEY_less, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '＜') # still in fullwidth mode!
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ핺\u3000ａａ　ｂ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 13)
        self.engine.do_process_key_event(IBus.KEY_less, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ핺\u3000ａａ　ｂ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 13)
        self.engine.do_process_key_event(IBus.KEY_H, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ㅎ')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ핺\u3000ａａ　ｂ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 13)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '하')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ핺\u3000ａａ　ｂ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 13)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '한')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ핺\u3000ａａ　ｂ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 13)
        # `G` starts a new syllable (`g` would add to the syllable)
        self.engine.do_process_key_event(IBus.KEY_G, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ㄱ')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ핺\u3000ａａ　ｂ한')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 14)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '하ㅎㅏ ㅎㅐㅣ핺\u3000ａａ　ｂ한ㄱ ')
        self.assertEqual(self.engine.mock_committed_text_cursor_pos, 16)

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    # Activate this to see a lot of logging when running the tests
    # manually:
    # LOGGER.addHandler(LOG_HANDLER)
    unittest.main()
