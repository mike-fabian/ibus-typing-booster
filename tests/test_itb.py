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


from typing import Any
from typing import Optional
from typing import TYPE_CHECKING
import os
import glob
import sys
import logging
import unicodedata
import tempfile
import shutil
import unittest
import importlib
import importlib.util
from unittest import mock

# pylint: disable=wrong-import-position
from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus
require_version('GLib', '2.0')
from gi.repository import GLib # type: ignore
# pylint: enable=wrong-import-position

LOGGER = logging.getLogger('ibus-typing-booster')

IMPORT_DISTRO_SUCCESSFUL = False
try:
    import distro
    IMPORT_DISTRO_SUCCESSFUL = True
except (ImportError,):
    IMPORT_DISTRO_SUCCESSFUL = False

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

IS_ENCHANT_AVAILABLE = importlib.util.find_spec('enchant') is not None

# pylint: disable=missing-function-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=invalid-name

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
        # are applied to TypingBoosterEngine:
        sys.path.insert(0, "../engine")
        importlib.reload(hunspell_table)
        sys.path.pop(0)
        self.bus = IBus.Bus()
        self.database = tabsqlitedb.TabSqliteDb(user_db_file=':memory:')
        self.engine = hunspell_table.TypingBoosterEngine(
            self.bus,
            '/com/redhat/IBus/engines/typing_booster/typing_booster/engine/0',
            self.database,
            engine_name='typing-booster',
            unit_test=True)
        self.backup_original_settings()
        self.set_default_settings()
        self._compose_sequences = itb_util.ComposeSequences()

    def tearDown(self) -> None:
        self.restore_original_settings()
        del self.engine
        if self.database is not None:
            self.database.database.close()
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
        self.assertEqual(True, True)

    @unittest.expectedFailure
    def test_expected_failure(self) -> None:
        self.assertEqual(False, True)

    def test_get_label(self) -> None:
        self.assertEqual(self.engine.get_lookup_table().get_label(9), '9.')
        self.engine.get_lookup_table().set_label(
            9, IBus.Text.new_from_string('9'))
        self.assertEqual(self.engine.get_lookup_table().get_label(9), '9')

    def test_single_char_commit_with_space(self) -> None:
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'a ')

    def test_single_char_commit_with_arrow_right(self) -> None:
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Right, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'b')

    def test_char_space_period_space(self) -> None:
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_period, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'a . ')

    def test_direct_input(self) -> None:
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'a" ')

    def test_latn_post(self) -> None:
        self.engine.set_current_imes(
            ['t-latn-post', 'NoIME'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'ä ')

    def test_te_rts_tab(self) -> None:
        '''https://github.com/mike-fabian/ibus-typing-booster/issues/708

        `Tab` needs to work as input, it is used in some m17n-db input methods.
        '''
        _dummy_trans = self.get_transliterator_or_skip('te-rts')
        self.engine.set_current_imes(
            ['te-rts'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine.mock_preedit_text, 'మ్')
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine.mock_preedit_text, 'ం\t')

    def test_shift_space_latn_post(self) -> None:
        '''https://github.com/mike-fabian/ibus-typing-booster/issues/524'''
        _dummy_trans = self.get_transliterator_or_skip('t-latn-post')
        self.engine.set_current_imes(
            ['t-latn-post', 'NoIME'], update_gsettings=False)
        self.engine.do_process_key_event(
            IBus.KEY_space, 0, IBus.ModifierType.SHIFT_MASK)
        self.assertEqual(self.engine.mock_committed_text, ' ')
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, ' ')
        self.assertEqual(self.engine.mock_preedit_text, 'a')
        self.engine.do_process_key_event(
            IBus.KEY_space, 0, IBus.ModifierType.SHIFT_MASK)
        self.assertEqual(self.engine.mock_committed_text, ' a ')
        self.assertEqual(self.engine.mock_preedit_text, '')

    def test_shift_space_mr_itrans(self) -> None:
        '''https://github.com/mike-fabian/ibus-typing-booster/issues/524'''
        _dummy_trans = self.get_transliterator_or_skip('mr-itrans')
        self.engine.set_current_imes(
            ['mr-itrans', 'NoIME'], update_gsettings=False)
        self.engine.do_process_key_event(
            IBus.KEY_space, 0, IBus.ModifierType.SHIFT_MASK)
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine.mock_preedit_text, '\u200c')
        self.engine.do_process_key_event(IBus.KEY_k, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine.mock_preedit_text, '\u200cक')
        self.engine.do_process_key_event(
            IBus.KEY_space, 0, IBus.ModifierType.SHIFT_MASK)
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine.mock_preedit_text, '\u200cक\u200c')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '\u200cक\u200c ')

    def test_hi_itrans_full_stop_space(self) -> None:
        ''' https://bugzilla.redhat.com/show_bug.cgi?id=1353672 '''
        self.engine.set_current_imes(
            ['hi-itrans', 'mr-itrans', 'NoIME'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_period, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '.')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '। ')

    def test_hi_itrans_commit_to_preedit(self) -> None:
        ''' https://github.com/mike-fabian/ibus-typing-booster/issues/457
        hi-itrans uses S-C-Return as a commit-key.
        '''
        self.engine.set_current_imes(
            ['hi-itrans', 'mr-itrans', 'NoIME'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'न्')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(
            IBus.KEY_Return, 0,
            IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'न्')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_T, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'न्ट्')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(
            IBus.KEY_Return, 0,
            IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'न्ट्')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'न्ट् ')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'अ')
        self.assertEqual(self.engine.mock_committed_text, 'न्ट् ')
        self.engine.do_process_key_event(
            IBus.KEY_Return, 0,
            IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'न्ट् अ\r')

    def test_mr_itrans_no_commit_to_preedit(self) -> None:
        ''' https://github.com/mike-fabian/ibus-typing-booster/issues/457
        mr-itrans does **not** define a commit-key.
        '''
        self.engine.set_current_imes(
            ['mr-itrans', 'hi-itrans', 'NoIME'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'न्')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(
            IBus.KEY_Return, 0,
            IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'न्\r')
        self.engine.do_process_key_event(IBus.KEY_T, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ट्')
        self.assertEqual(self.engine.mock_committed_text, 'न्\r')
        self.engine.do_process_key_event(
            IBus.KEY_Return, 0,
            IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'न्\rट्\r')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'न्\rट्\r ')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'अ')
        self.assertEqual(self.engine.mock_committed_text, 'न्\rट्\r ')
        self.engine.do_process_key_event(
            IBus.KEY_Return, 0,
            IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'न्\rट्\r अ\r')

    def test_autocommit_characters(self) -> None:
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.set_auto_commit_characters('.', update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_semicolon, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_period, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'a;. b ')

    def test_push_context(self) -> None:
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

    def test_set_page_size(self) -> None:
        self.engine.set_page_size(
            3, update_gsettings=False)
        self.assertEqual(
            self.engine.get_lookup_table().get_page_size(),
            3)
        self.engine.set_page_size(
            5, update_gsettings=False)
        self.assertEqual(
            self.engine.get_lookup_table().get_page_size(),
            5)

    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_record_mode(self) -> None:
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.set_record_mode(0, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_f, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_p, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual(self.engine._candidates, [])
        self.assertEqual(
            0,
            self.database.phrase_exists('citsiligarfilacrepus'))
        self.assertEqual(self.engine.mock_preedit_text, 'citsiligarfilacrepus')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'citsiligarfilacrepus ')
        self.assertEqual(
            1,
            self.database.phrase_exists('citsiligarfilacrepus'))
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_f, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_p, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'citsiligarfilacrepus')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(
            2,
            self.database.phrase_exists('citsiligarfilacrepus'))
        self.engine.set_record_mode(1, update_gsettings=False)
        # Previously recorded phrase failing spellcheck should still be recorded:
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_f, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_p, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'citsiligarfilacrepus')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(
            3,
            self.database.phrase_exists('citsiligarfilacrepus'))
        # New phrase failing spellcheck cannot be recorded:
        self.assertEqual(
            0,
            self.database.phrase_exists('ilacrepus'))
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_p, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ilacrepus')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(
            0,
            self.database.phrase_exists('ilacrepus'))
        # New phrase passing spellcheck can be recorded:
        self.assertEqual(
            0,
            self.database.phrase_exists('hello'))
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'hello')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(
            1,
            self.database.phrase_exists('hello'))
        self.engine.set_record_mode(2, update_gsettings=False)
        #  Previously recorded phrase failing spellcheck cannot be recorded
        self.assertEqual(
            3,
            self.database.phrase_exists('citsiligarfilacrepus'))
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_f, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_p, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'citsiligarfilacrepus')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(
            3,
            self.database.phrase_exists('citsiligarfilacrepus'))
        # Existing phrase passing spellcheck can be recorded:
        self.assertEqual(
            1,
            self.database.phrase_exists('hello'))
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'hello')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(
            2,
            self.database.phrase_exists('hello'))
        # New phrase passing spellcheck can be recorded:
        self.assertEqual(
            0,
            self.database.phrase_exists('world'))
        self.engine.do_process_key_event(IBus.KEY_w, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_d, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'world')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(
            1,
            self.database.phrase_exists('world'))
        # Check that multiple word were recorded:
        self.assertEqual(
            1,
            self.database.phrase_exists('hello world'))
        # Misspelled word is not recorded
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'hellllo')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(
            0,
            self.database.phrase_exists('hellllo'))
        # Record another correctly spelled word:
        self.engine.do_process_key_event(IBus.KEY_w, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_d, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'world')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(
            2,
            self.database.phrase_exists('world'))
        self.assertEqual(
            1,
            self.database.phrase_exists('hello world'))
        # Check that the misspelled 'hellllo' was not recorded
        # in the multiple word recording:
        self.assertEqual(
            0,
            self.database.phrase_exists('hellllo world'))

    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_complete_word_from_us_english_dictionary(self) -> None:
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
        self.assertEqual(self.engine._candidates[0].phrase, 'cerulean')
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'cerulean ')

    def test_ascii_digits(self) -> None:
        self.engine.set_current_imes(
            ['hi-itrans', 'NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['hi_IN', 'en_GB'], update_gsettings=False)
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
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '०१२३४५६७८९')
        self.engine.set_ascii_digits(True, update_gsettings=False)
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
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '०१२३४५६७८९0123456789')
        # Remove all digits from the key bindings:
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
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
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
        self.assertEqual(self.engine.mock_preedit_text, 'नमस्ते0123456789')
        self.assertEqual(self.engine.mock_committed_text, '०१२३४५६७८९0123456789')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '०१२३४५६७८९0123456789नमस्ते0123456789 ')
        self.engine.set_ascii_digits(False, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
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
        self.assertEqual(self.engine.mock_preedit_text, 'नमस्ते०१२३४५६७८९')
        self.assertEqual(self.engine.mock_committed_text, '०१२३४५६७८९0123456789नमस्ते0123456789 ')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '०१२३४५६७८९0123456789नमस्ते0123456789 नमस्ते०१२३४५६७८९ ')

    def test_complete_with_empty_input(self) -> None:
        '''Test completion when something has just been committed with
        follwing white space and no new characters have been typed
        yet.
        '''
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_T, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_E, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_period, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(
            self.engine.mock_committed_text,
            'This is an English sentence. ')
        self.engine.do_process_key_event(IBus.KEY_T, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_E, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(
            self.engine.mock_committed_text,
            'This is an English sentence. '
            'This is an English ')
        self.assertEqual(self.engine._candidates, [])
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_period, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(
            self.engine.mock_committed_text,
            'This is an English sentence. '
            'This is an English sentence. ')
        self.engine.set_min_char_complete(0, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_T, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_E, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(
            self.engine.mock_committed_text,
            'This is an English sentence. '
            'This is an English sentence. '
            'This is an English ')
        self.assertEqual(self.engine._candidates[0].phrase, 'sentence')

    def test_commit_command_keybinding(self) -> None:
        '''Test binding a key to the “commit” command
        https://github.com/mike-fabian/ibus-typing-booster/issues/320
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
        # committing with space adds a space by default
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'test ')
        # Now set the option to commit by space
        self.engine.set_keybindings({
            'commit': ['space'],
        }, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'test')
        self.assertEqual(self.engine.mock_committed_text, 'test ')
        # Now committing with space should not add a space anymore:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'test test')

    def test_commit_and_forward_key_command_keybinding(self) -> None:
        '''Test binding a key to the “commit_and_forward_key” command'''
        # not yet implemented:
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        # Set the option to commit by grave
        self.engine.set_keybindings({
            'commit_and_forward_key': ['grave'],
        }, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'test')
        self.assertEqual(self.engine.mock_committed_text, '')
        # Now committing with grave, it should commit **and** add a `:
        self.engine.do_process_key_event(IBus.KEY_grave, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'test`')

    def test_commit_with_arrows(self) -> None:
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
        IS_ENCHANT_AVAILABLE,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_emoji_related_tab_enable_cursor_visible_escape(self) -> None:
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
        self.assertEqual(self.engine._candidates[0].phrase, 'Camel')
        self.assertEqual(self.engine._candidates[1].phrase, 'camel')
        self.assertEqual(self.engine._candidates[5].phrase, '🐫')
        self.assertEqual(self.engine._candidates[5].comment, 'bactrian camel')
        self.engine.do_candidate_clicked(5, 3, 0)
        self.assertEqual(self.engine._candidates[0].phrase, '🐫')
        self.assertEqual(self.engine._candidates[1].phrase, '🐪')
        self.assertEqual(
            self.engine.get_lookup_table().is_cursor_visible(),
            False)
        self.engine.do_process_key_event(IBus.KEY_Down, 0, 0)
        self.assertEqual(
            self.engine.get_lookup_table().is_cursor_visible(),
            True)
        self.engine.do_process_key_event(IBus.KEY_Down, 0, 0)
        self.assertEqual(
            self.engine.get_lookup_table().is_cursor_visible(),
            True)
        self.assertEqual(
            self.engine.get_string_from_lookup_table_cursor_pos(),
            '🐪')
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        self.assertEqual(
            self.engine.get_lookup_table().is_cursor_visible(),
            False)
        self.assertEqual(
            self.engine.get_lookup_table().get_cursor_pos(),
            0)
        self.assertEqual(
            self.engine.get_string_from_lookup_table_cursor_pos(),
            '🐫')
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        self.assertEqual(
            self.engine.get_lookup_table().is_cursor_visible(),
            False)
        self.assertEqual(
            self.engine.get_lookup_table().get_cursor_pos(),
            0)
        self.assertEqual(self.engine._candidates[0].phrase, 'Camel')
        self.assertEqual(self.engine._candidates[1].phrase, 'camel')
        self.assertEqual(self.engine._candidates[5].phrase, '🐫')
        self.assertEqual(self.engine._candidates[5].comment, 'bactrian camel')
        self.engine.do_process_key_event(IBus.KEY_Down, 0, 0)
        self.assertEqual(
            self.engine.get_lookup_table().is_cursor_visible(),
            True)
        self.assertEqual(
            self.engine.get_string_from_lookup_table_cursor_pos(),
            'Camel')
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        self.assertEqual(
            self.engine.get_lookup_table().is_cursor_visible(),
            False)
        self.assertEqual(
            self.engine.get_lookup_table().get_cursor_pos(),
            0)
        self.assertEqual(
            self.engine.get_string_from_lookup_table_cursor_pos(),
            'Camel')
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
    def test_marathi_and_british_english(self) -> None:
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
    def test_korean(self) -> None:
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
        #candidates = [unicodedata.normalize('NFC', x.phrase)
        #              for x in self.engine._candidates]
        candidates = [x.phrase for x in self.engine._candidates]
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
        #candidates = [unicodedata.normalize('NFC', x.phrase)
        #              for x in self.engine._candidates]
        candidates = [x.phrase for x in self.engine._candidates]
        self.assertEqual(True, '안녕하세요' in candidates)
        self.assertEqual('안녕하세요', candidates[0])

    def test_accent_insensitive_matching_german_dictionary(self) -> None:
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
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
        self.assertEqual(self.engine.mock_preedit_text, 'Alpengluhen')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine._candidates[0].phrase, 'Alpenglühen')
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'Alpenglühen ')
        # Now try to input NFD:
        self.engine.do_process_key_event(IBus.KEY_A, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_p, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        # U+0308 COMBINING DIAERESIS
        self.engine.do_process_key_event(0x01000308, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        # The preedit text also contains the NFD:
        self.assertEqual(self.engine.mock_preedit_text, 'Alpenglu\u0308hen')
        # And the transliterated string which will be committed is in NFD:
        self.assertEqual(self.engine._transliterated_strings['NoIME'],
                         'Alpenglu\u0308hen')
        self.assertEqual(self.engine.mock_committed_text, 'Alpengl\u00fchen ')
        # Now commit with space:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine._transliterated_strings['NoIME'], '')
        self.assertEqual(self.engine.mock_committed_text,
                         'Alpengl\u00fchen Alpenglu\u0308hen ')

    @unittest.skipUnless(
        IS_ENCHANT_AVAILABLE,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('de_DE')[0],
        'Skipping because no de_DE hunspell dictionary could be found.')
    def test_accent_insensitive_matching_german_database(self) -> None:
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
                                  self.engine._candidates[0].phrase),
            'Glühwürmchen')
        # user_freq must be 0 because this word has not been found in
        # the user database, it is only a candidate because it is a
        # valid word according to hunspell:
        self.assertEqual(self.engine._candidates[0].user_freq, 0)
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
                                  self.engine._candidates[0].phrase),
            'Glühwürmchen')
        # But now user_freq must be > 0 because the last commit
        # added this word to the user database:
        self.assertTrue(self.engine._candidates[0].user_freq > 0)
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
                                  self.engine._candidates[0].phrase),
            'Glühwürmchen')
        # Commit with F1:
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(
            self.engine.mock_committed_text,
            'Glühwürmchen Glühwürmchen Glühwürmchen ')

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('fr_FR')[0],
        'Skipping because no fr_FR hunspell dictionary could be found.')
    def test_accent_insensitive_matching_french_dictionary(self) -> None:
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
                                  self.engine._candidates[0].phrase),
            'différemment')
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'différemment ')

    @unittest.skipUnless(
        IS_ENCHANT_AVAILABLE,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_emoji_triggered_by_underscore(self) -> None:
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
        self.assertEqual(self.engine._candidates[0].phrase, 'Camel')
        self.assertEqual(self.engine._candidates[1].phrase, 'camel')
        self.assertEqual(False, self.engine._candidates[5].phrase == '🐫')
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'Camel ')
        # Now again with a leading underscore an emoji should match.
        self.engine.do_process_key_event(IBus.KEY_underscore, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.assertEqual(self.engine._candidates[0].phrase, '_Camel')
        self.assertEqual(self.engine._candidates[1].phrase, '_camel')
        self.assertEqual(self.engine._candidates[5].phrase, '🐫')
        self.assertEqual(self.engine._candidates[5].comment, 'bactrian camel')
        self.engine.do_process_key_event(IBus.KEY_F6, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'Camel 🐫 ')

    @unittest.skipUnless(
        IS_ENCHANT_AVAILABLE,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('cs_CZ')[0],
        'Skipping because no Czech hunspell dictionary could be found.')
    @unittest.skipUnless(
        testutils.enchant_sanity_test(language='cs_CZ', word='Praha'),
        'Skipping because python3-enchant seems broken for cs_CZ.')
    @unittest.skipUnless(
        testutils.enchant_working_as_expected(),
        'Skipping because of an unexpected change in the enchant behaviour.')
    def test_selecting_non_existing_candidates(self) -> None:
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
        self.assertTrue(
            ('Barcelona', 0, '', False, False), self.engine._candidates[0])
        self.assertTrue(len(self.engine._candidates) <= 3)
        self.engine.do_process_key_event(IBus.KEY_4, 0, 0)
        # Nothing should be committed:
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine.mock_preedit_text, 'Barcelona4')
        self.engine.do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Barcelona')
        self.assertTrue(
            ('Barcelona', 0, '', False, False), self.engine._candidates[0])
        self.engine.do_process_key_event(IBus.KEY_1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'Barcelona ')
        self.assertEqual(self.engine.mock_preedit_text, '')

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('en_US')[0],
        'Skipping because no en_US hunspell dictionary could be found.')
    def test_auto_capitalize(self) -> None:
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
        self.assertEqual(self.engine._candidates[0].phrase, 'test')
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
        self.assertEqual(self.engine._candidates[0].phrase, 'test')
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
        self.assertEqual(self.engine._candidates[0].phrase, 'Test')
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
        self.assertEqual(self.engine._candidates[0].phrase, 'Test')
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
        self.assertEqual(self.engine._candidates[0].phrase, 'Test')
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
        self.assertEqual(self.engine._candidates[0].phrase, 'hello')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'test test. Test test . Test , hello ')
        self.engine.do_process_key_event(IBus.KEY_semicolon, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text,
                         'test test. Test test . Test , hello ; ')
        self.assertEqual(self.engine._candidates, [])
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'hello')
        self.assertEqual(self.engine.mock_committed_text,
                         'test test. Test test . Test , hello ; ')
        self.assertEqual(self.engine._candidates[0].phrase, 'hello')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'test test. Test test . Test , hello ; hello ')
        # https://github.com/mike-fabian/ibus-typing-booster/issues/773
        # in Greek, ';' is used as the question mark, therefore capitalization
        # is used after ';' in Greek:
        self.engine.set_dictionary_names(
            ['el_GR', 'en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_semicolon, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'test test. Test test . Test , hello ; hello ; ')
        self.assertEqual(self.engine._candidates, [])
        self.engine.do_process_key_event(IBus.KEY_h, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Hello')
        self.assertEqual(self.engine.mock_committed_text,
                         'test test. Test test . Test , hello ; hello ; ')
        self.assertEqual(self.engine._candidates[0].phrase, 'Hello')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'test test. Test test . Test , hello ; hello ; Hello ')

    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_no_commit_by_index_when_using_inline_completion(self) -> None:
        '''Test to avoid committing by index when using inline completion
        https://github.com/mike-fabian/ibus-typing-booster/issues/325
        '''
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        # Switch on inline completion without fallback to popup:
        self.engine.set_inline_completion(2, update_gsettings=False)
        self.assertEqual(2, self.engine.get_inline_completion())
        self.engine.do_process_key_event(IBus.KEY_A, 0, 0)
        self.assertEqual(True, self.engine._lookup_table.hidden)
        self.assertEqual(self.engine._candidates[0].phrase, 'A')
        self.assertEqual(True, len(self.engine._candidates) >= 3)
        # No commit by index should be possible now because the lookup
        # table is hidden:
        self.engine.do_process_key_event(IBus.KEY_4, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine.mock_preedit_text, 'A4')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'A4 ')
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.engine.do_process_key_event(IBus.KEY_w, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(True, self.engine._lookup_table.hidden)
        self.assertEqual(self.engine._candidates[0].phrase, 'winter')
        self.assertEqual(True, len(self.engine._candidates) >= 3)
        # No commit by index should be possible now because the lookup
        # table is hidden:
        self.engine.do_process_key_event(IBus.KEY_1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'A4 ')
        self.assertEqual(self.engine.mock_preedit_text, 'wint1')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'A4 wint1 ')
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.engine.do_process_key_event(IBus.KEY_A, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.assertEqual(True, self.engine._lookup_table.hidden)
        self.assertEqual(self.engine._candidates[0].phrase, 'Autumn')
        self.assertEqual(True, len(self.engine._candidates) >= 3)
        self.assertEqual(self.engine.mock_committed_text, 'A4 wint1 ')
        # Preedit text shows inline completion:
        self.assertEqual(self.engine.mock_preedit_text, 'Autumn')
        # Accept the inline completion with Tab:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'A4 wint1 ')
        # Preedit text contents unchanged, only colour may change:
        self.assertEqual(self.engine.mock_preedit_text, 'Autumn')
        # Lookup table is still hidden:
        self.assertEqual(True, self.engine._lookup_table.hidden)
        # Show lookup table by typing Tab again:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.assertEqual(False, self.engine._lookup_table.hidden)
        self.assertEqual(self.engine.mock_committed_text, 'A4 wint1 ')
        # Preedit text is shortened to “Autum” again because the
        # lookup table is shown now and the second candidate, which is
        # probably “Autumnal”. But better don’t check the second
        # candidate to avoid making the test too much dependent on
        # dictionary contents.
        self.assertEqual(self.engine.mock_preedit_text, 'Autum')
        # Commit the first candidate “Autumn” by typing 1, this should
        # be possible now as the lookup table is visible now:
        self.engine.do_process_key_event(IBus.KEY_1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'A4 wint1 Autumn ')
        self.assertEqual(self.engine.mock_preedit_text, '')

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('en_US')[0],
        'Skipping because no en_US hunspell dictionary could be found.')
    def test_add_space_on_commit(self) -> None:
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
        self.assertEqual(self.engine._candidates[0].phrase, 'test')
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
        self.assertEqual(self.engine._candidates[0].phrase, 'test')
        self.engine.do_process_key_event(IBus.KEY_1, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        # No space should be added now:
        self.assertEqual(self.engine.mock_committed_text, 'test test')

    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_tab_enable_key_binding_changed(self) -> None:
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
        self.assertEqual(self.engine._candidates[0].phrase, 'cerulean')
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'test\tcerulean ')

    def test_hi_inscript2_rupee_symbol(self) -> None:
        _dummy_trans = self.get_transliterator_or_skip('hi-inscript2')
        self.engine.set_current_imes(
            ['hi-inscript2'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['hi_IN'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_4, 0, IBus.ModifierType.MOD5_MASK)
        self.assertEqual(self.engine.mock_preedit_text, '₹')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, '₹ ')

    def test_russian_keyboard_use_ibus_keymap_false(self) -> None:
        self.engine.set_current_imes(['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(['None'], update_gsettings=False)
        self.engine.set_use_ibus_keymap(False, update_gsettings=False)
        # key sequence 1: Cyrillic_en (y on US keymap)
        self.engine.do_process_key_event(IBus.KEY_Cyrillic_en, 21, 0)
        self.assertNotEqual(self.engine._prev_key, None)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, True) # type: ignore
        self.assertEqual(self.engine.mock_preedit_text, 'н')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_Cyrillic_en, 21,
                                         IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, True) # type: ignore
        self.assertEqual(self.engine.mock_preedit_text, 'н')
        self.assertEqual(self.engine.mock_committed_text, '')
        # key sequence 2: Alt_R+4
        self.engine.do_process_key_event(IBus.KEY_Alt_R, 100, 0)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine.mock_preedit_text, 'н')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_4, 5,
                                         IBus.ModifierType.MOD1_MASK)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        # A commit is triggered and a press event of Alt_R+4 is passed
        # through, what happens with that depends on the applications,
        # in gedit for example nothing happens. The
        # MockEngine.forward_key_event() inserts the Unicode value of
        # the key, i.e. '4':
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'н4')
        self.assertEqual(self.engine._prev_key.val, IBus.KEY_4) # type: ignore
        self.engine.do_process_key_event(IBus.KEY_4, 5,
                                         IBus.ModifierType.MOD1_MASK
                                         | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        # Another key with the Unicode value of '4' is passed through:
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'н44')
        self.engine.do_process_key_event(IBus.KEY_Alt_R, 100,
                                         IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'н44')
        # key sequence 3: Shift_R+Alt_R+Cyrillic_CHE (X on US keymap)
        self.engine.do_process_key_event(IBus.KEY_Shift_R, 54, 0)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'н44')
        self.engine.do_process_key_event(IBus.KEY_Alt_R, 100,
                                         IBus.ModifierType.SHIFT_MASK)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'н44')
        self.engine.do_process_key_event(IBus.KEY_Cyrillic_CHE, 45,
                                         IBus.ModifierType.SHIFT_MASK
                                         | IBus.ModifierType.MOD1_MASK)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        # A commit is triggered and a press key event of
        # Shift_R+Alt_R+Cyrillic_CHE is passed trough:
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'н44Ч')
        self.engine.do_process_key_event(IBus.KEY_Cyrillic_CHE, 45,
                                         IBus.ModifierType.SHIFT_MASK
                                         | IBus.ModifierType.MOD1_MASK
                                         | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        # Another key with the Unicode value of 'Ч is passed through:
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'н44ЧЧ')
        self.engine.do_process_key_event(IBus.KEY_Alt_R, 100,
                                         IBus.ModifierType.SHIFT_MASK
                                         | IBus.ModifierType.MOD1_MASK
                                         | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'н44ЧЧ')
        self.engine.do_process_key_event(IBus.KEY_Shift_R, 54,
                                         IBus.ModifierType.SHIFT_MASK
                                         | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'н44ЧЧ')

    def test_russian_keyboard_use_ibus_keymap_true_keymap_in(self) -> None:
        self.engine.set_current_imes(['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(['None'], update_gsettings=False)
        self.engine.set_use_ibus_keymap(True, update_gsettings=False)
        self.engine.set_ibus_keymap('in', update_gsettings=False)
        # key sequence 1: Cyrillic_en (y on US keymap)
        self.engine.do_process_key_event(IBus.KEY_Cyrillic_en, 21, 0)
        self.assertNotEqual(self.engine._prev_key, None)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, True) # type: ignore
        self.assertEqual(self.engine.mock_preedit_text, 'y')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_Cyrillic_en, 21,
                                         IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, True) # type: ignore
        self.assertEqual(self.engine.mock_preedit_text, 'y')
        self.assertEqual(self.engine.mock_committed_text, '')
        # key sequence 2: Alt_R+4
        self.engine.do_process_key_event(IBus.KEY_Alt_R, 100, 0)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._prev_key.name, 'ISO_Level3_Shift') # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x80)
        self.assertEqual(self.engine.mock_preedit_text, 'y')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_4, 5,
                                         IBus.ModifierType.MOD1_MASK)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._prev_key.name, '4') # type: ignore
        self.assertEqual(self.engine._prev_key.mod1, False) # type: ignore
        self.assertEqual(self.engine._prev_key.mod5, True) # type: ignore
        # A commit is triggered and a press event of ISO_Level3_Shift+4 is passed
        # through, what happens with that depends on the applications,
        # in gedit for example nothing happens. The
        # MockEngine.forward_key_event() inserts the Unicode value of
        # the key, i.e. '4':
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'y4')
        self.assertEqual(self.engine._prev_key.val, IBus.KEY_4) # type: ignore
        # The commit of a **digit** has reset the translated key state:
        self.assertEqual(self.engine._translated_key_state, 0)
        self.engine.do_process_key_event(IBus.KEY_4, 5,
                                         IBus.ModifierType.MOD1_MASK
                                         | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._prev_key.name, '4') # type: ignore
        self.assertEqual(self.engine._prev_key.mod1, False) # type: ignore
        self.assertEqual(self.engine._prev_key.mod5, False) # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0)
        # Another key with the Unicode value of '4' is passed through:
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'y44')
        self.engine.do_process_key_event(IBus.KEY_Alt_R, 100,
                                         IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'y44')
        # key sequence 3: Shift_R+Alt_R+Cyrillic_CHE (X on US keymap)
        self.engine.do_process_key_event(IBus.KEY_Shift_R, 54, 0)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x1)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'y44')
        self.engine.do_process_key_event(IBus.KEY_Alt_R, 100,
                                         IBus.ModifierType.SHIFT_MASK)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._prev_key.name, 'ISO_Level3_Shift') # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x81)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'y44')
        self.engine.do_process_key_event(IBus.KEY_Cyrillic_CHE, 45,
                                         IBus.ModifierType.SHIFT_MASK
                                         | IBus.ModifierType.MOD1_MASK)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._prev_key.mod1, False) # type: ignore
        self.assertEqual(self.engine._prev_key.mod5, True) # type: ignore
        self.assertEqual(self.engine._prev_key.name, 'X') # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x81)
        # A commit is triggered and a press key event of
        # Shift_R+Alt_R+X is passed trough:
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'y44X')
        # This commit of a **non** digit has **not** reset the translated key state:
        self.assertEqual(self.engine._translated_key_state, 0x81)
        self.engine.do_process_key_event(IBus.KEY_Cyrillic_CHE, 45,
                                         IBus.ModifierType.SHIFT_MASK
                                         | IBus.ModifierType.MOD1_MASK
                                         | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._prev_key.name, 'X') # type: ignore
        self.assertEqual(self.engine._prev_key.mod1, False) # type: ignore
        self.assertEqual(self.engine._prev_key.mod5, True) # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x81)
        # Another key with the Unicode value of 'X' is passed through:
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'y44XX')
        self.engine.do_process_key_event(IBus.KEY_Alt_R, 100,
                                         IBus.ModifierType.SHIFT_MASK
                                         | IBus.ModifierType.MOD1_MASK
                                         | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._prev_key.name, 'ISO_Level3_Shift') # type: ignore
        self.assertEqual(self.engine._prev_key.mod1, False) # type: ignore
        self.assertEqual(self.engine._prev_key.mod5, True) # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x1)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'y44XX')
        self.engine.do_process_key_event(IBus.KEY_Shift_R, 54,
                                         IBus.ModifierType.SHIFT_MASK
                                         | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._prev_key.name, 'Shift_R') # type: ignore
        self.assertEqual(self.engine._prev_key.mod1, False) # type: ignore
        self.assertEqual(self.engine._prev_key.mod5, False) # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'y44XX')

    def test_russian_keyboard_use_ibus_keymap_true_keymap_in_hi_inscript2(self) -> None:
        _dummy_trans = self.get_transliterator_or_skip('hi-inscript2')
        self.engine.set_current_imes(['hi-inscript2'], update_gsettings=False)
        self.engine.set_dictionary_names(['None'], update_gsettings=False)
        self.engine.set_use_ibus_keymap(True, update_gsettings=False)
        self.engine.set_ibus_keymap('in', update_gsettings=False)
        # key sequence 1: Cyrillic_en (y on US keymap)
        self.engine.do_process_key_event(IBus.KEY_Cyrillic_en, 21, 0)
        self.assertNotEqual(self.engine._prev_key, None)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, True) # type: ignore
        self.assertEqual(self.engine.mock_preedit_text, 'ब')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_Cyrillic_en, 21,
                                         IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, True) # type: ignore
        self.assertEqual(self.engine.mock_preedit_text, 'ब')
        self.assertEqual(self.engine.mock_committed_text, '')
        # key sequence 2: Alt_R+4
        self.engine.do_process_key_event(IBus.KEY_Alt_R, 100, 0)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._prev_key.name, 'ISO_Level3_Shift') # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x80)
        self.assertEqual(self.engine.mock_preedit_text, 'ब')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_4, 5,
                                         IBus.ModifierType.MOD1_MASK)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, True) # type: ignore
        self.assertEqual(self.engine._prev_key.name, '4') # type: ignore
        self.assertEqual(self.engine._prev_key.msymbol, 'G-4') # type: ignore
        self.assertEqual(self.engine._prev_key.mod1, False) # type: ignore
        self.assertEqual(self.engine._prev_key.mod5, True) # type: ignore
        self.assertEqual(self.engine.mock_preedit_text, 'ब₹')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine._prev_key.val, IBus.KEY_4) # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x80)
        self.engine.do_process_key_event(IBus.KEY_4, 5,
                                         IBus.ModifierType.MOD1_MASK
                                         | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, True) # type: ignore
        self.assertEqual(self.engine._prev_key.name, '4') # type: ignore
        self.assertEqual(self.engine._prev_key.msymbol, 'G-4') # type: ignore
        self.assertEqual(self.engine._prev_key.mod1, False) # type: ignore
        self.assertEqual(self.engine._prev_key.mod5, True) # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x80)
        self.assertEqual(self.engine.mock_preedit_text, 'ब₹')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_Alt_R, 100,
                                         IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ब₹')
        self.assertEqual(self.engine.mock_committed_text, '')
        # key sequence 3: Shift_R+Alt_R+Cyrillic_CHE (X on US keymap)
        self.engine.do_process_key_event(IBus.KEY_Shift_R, 54, 0)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x1)
        self.assertEqual(self.engine.mock_preedit_text, 'ब₹')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_Alt_R, 100,
                                         IBus.ModifierType.SHIFT_MASK)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._prev_key.name, 'ISO_Level3_Shift') # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x81)
        self.assertEqual(self.engine.mock_preedit_text, 'ब₹')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_Cyrillic_CHE, 45,
                                         IBus.ModifierType.SHIFT_MASK
                                         | IBus.ModifierType.MOD1_MASK)
        self.assertEqual(self.engine._prev_key.release, False) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, True) # type: ignore
        self.assertEqual(self.engine._prev_key.mod1, False) # type: ignore
        self.assertEqual(self.engine._prev_key.mod5, True) # type: ignore
        self.assertEqual(self.engine._prev_key.name, 'X') # type: ignore
        self.assertEqual(self.engine._prev_key.msymbol, 'G-X') # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x81)
        self.assertEqual(self.engine.mock_preedit_text, 'ब₹ॐ')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(self.engine._translated_key_state, 0x81)
        self.engine.do_process_key_event(IBus.KEY_Cyrillic_CHE, 45,
                                         IBus.ModifierType.SHIFT_MASK
                                         | IBus.ModifierType.MOD1_MASK
                                         | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, True) # type: ignore
        self.assertEqual(self.engine._prev_key.name, 'X') # type: ignore
        self.assertEqual(self.engine._prev_key.msymbol, 'G-X') # type: ignore
        self.assertEqual(self.engine._prev_key.mod1, False) # type: ignore
        self.assertEqual(self.engine._prev_key.mod5, True) # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x81)
        self.assertEqual(self.engine.mock_preedit_text, 'ब₹ॐ')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_Alt_R, 100,
                                         IBus.ModifierType.SHIFT_MASK
                                         | IBus.ModifierType.MOD1_MASK
                                         | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._prev_key.name, 'ISO_Level3_Shift') # type: ignore
        self.assertEqual(self.engine._prev_key.mod1, False) # type: ignore
        self.assertEqual(self.engine._prev_key.mod5, True) # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x1)
        self.assertEqual(self.engine.mock_preedit_text, 'ब₹ॐ')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_Shift_R, 54,
                                         IBus.ModifierType.SHIFT_MASK
                                         | IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._prev_key.release, True) # type: ignore
        self.assertEqual(self.engine._prev_key.handled, False) # type: ignore
        self.assertEqual(self.engine._prev_key.name, 'Shift_R') # type: ignore
        self.assertEqual(self.engine._prev_key.mod1, False) # type: ignore
        self.assertEqual(self.engine._prev_key.mod5, False) # type: ignore
        self.assertEqual(self.engine._translated_key_state, 0x0)
        self.assertEqual(self.engine.mock_preedit_text, 'ब₹ॐ')
        self.assertEqual(self.engine.mock_committed_text, '')
        # A space with keycode 0 cannot be translated to the IBus keymap but is
        # used as is:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine._prev_key.translated, False) # type: ignore
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ब₹ॐ ')
        self.engine.do_process_key_event(IBus.KEY_space, 57, 0)
        # With the right keycode 57, the space could be translated but as
        # the result is identical, the untranslated key is used:
        self.assertEqual(self.engine._prev_key.translated, False) # type: ignore
        self.assertEqual(self.engine.mock_committed_text, 'ब₹ॐ  ')

    def test_digits_used_in_keybindings(self) -> None:
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

    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_commit_candidate_1_without_space(self) -> None:
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
        self.assertEqual(self.engine._candidates[0].phrase, 'cerulean')
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'cerulean ')
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_l, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.assertEqual(self.engine._candidates[0].phrase, 'cerulean')
        self.engine.do_process_key_event(IBus.KEY_Right, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'cerulean cerulean')

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('en_US')[0],
        'Skipping because no en_US hunspell dictionary could be found.')
    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_toggle_candidate_case_mode(self) -> None:
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
        self.assertEqual(self.engine._candidates[0].phrase, 'cerulean')
        # Shift_L goes to 'capitalize':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._candidates[0].phrase, 'Cerulean')
        # The next Shift_L goes to 'upper':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._candidates[0].phrase, 'CERULEAN')
        # Shift_R goes back to 'capitalize':
        self.engine.do_process_key_event(IBus.KEY_Shift_R, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_R, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine._candidates[0].phrase, 'Cerulean')
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'Cerulean ')

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('en_US')[0],
        'Skipping because no en_US hunspell dictionary could be found.')
    def test_toggle_case_mode_then_return(self) -> None:
        '''
        For https://github.com/mike-fabian/ibus-typing-booster/issues/558
        '''
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'test')
        # Shift_L goes to 'capitalize':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'Test')
        self.engine.do_process_key_event(IBus.KEY_Return, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'Test\r')
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'test')
        # Shift_L goes to 'capitalize':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'TEST')
        self.engine.do_process_key_event(IBus.KEY_Return, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'Test\rTEST\r')

    def test_toggle_case_mode_for_multiple_words(self) -> None:
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, IBus.ModifierType.MOD5_MASK)
        self.engine.do_process_key_event(IBus.KEY_G, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_y, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'in Germany')
        # there should be no candidates now:
        self.assertEqual(self.engine._candidates, [])
        # Shift_L goes to 'capitalize':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        # Even though there are no candidates now, the case mode
        # change should still be done, see:
        # https://github.com/mike-fabian/ibus-typing-booster/issues/640
        self.assertEqual(self.engine.mock_preedit_text, 'In Germany')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'In Germany ')
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, IBus.ModifierType.MOD5_MASK)
        self.engine.do_process_key_event(IBus.KEY_G, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_y, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'in Germany')
        # there should be a candidate now:
        self.assertEqual(self.engine._candidates[0].phrase, 'In Germany')
        # Shift_L goes to 'capitalize':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        # Now the first letter of the preedit should be capitalized
        # and the rest unchanged:
        self.assertEqual(self.engine.mock_preedit_text, 'In Germany')
        self.assertEqual(self.engine._candidates[0].phrase, 'In Germany')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'In Germany In Germany ')
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, IBus.ModifierType.MOD5_MASK)
        self.engine.do_process_key_event(IBus.KEY_G, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_y, 0, 0)
        # there should be at least one candidate now:
        self.assertEqual(self.engine._candidates[0].phrase, 'In Germany')
        # Shift_L goes to 'capitalize':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        # The next Shift_L goes to 'upper':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'IN GERMANY')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'In Germany In Germany IN GERMANY ')
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, IBus.ModifierType.MOD5_MASK)
        self.engine.do_process_key_event(IBus.KEY_G, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_y, 0, 0)
        # there should be two candidates now:
        self.assertEqual(self.engine._candidates[0].phrase, 'IN GERMANY')
        self.assertEqual(self.engine._candidates[1].phrase, 'In Germany')
        # Shift_L goes to 'capitalize':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        # The next Shift_L goes to 'upper':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        # Shift_R goes back to 'capitalize':
        self.engine.do_process_key_event(IBus.KEY_Shift_R, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_R, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'In Germany')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'In Germany In Germany IN GERMANY In Germany ')
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, IBus.ModifierType.MOD5_MASK)
        self.engine.do_process_key_event(IBus.KEY_G, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_y, 0, 0)
        # there should be two candidates now:
        self.assertEqual(self.engine._candidates[0].phrase, 'In Germany')
        self.assertEqual(self.engine._candidates[1].phrase, 'IN GERMANY')
        # Shift_R goes to 'previous' from 'orig', i.e. to 'lower':
        self.engine.do_process_key_event(IBus.KEY_Shift_R, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_R, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'in germany')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'In Germany In Germany IN GERMANY In Germany in germany ')

    def test_toggle_case_mode_without_candidates(self) -> None:
        '''
        For https://github.com/mike-fabian/ibus-typing-booster/issues/640
        '''
        self.engine.set_current_imes(
            ['NoIME', 't-latn-post'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['None'], update_gsettings=False)
        self.assertEqual(self.engine.get_dictionary_names(), ['None'])
        self.engine.set_tab_enable(True, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'test')
        # There is no dictionary **and** tab_enable is set to
        # True. One of these settings should already be enough to
        # produce no candidates here, both are set then certainly
        # there should be no candidates now:
        self.assertTrue(len(self.engine._candidates) == 0)
        # Shift_L goes to 'capitalize':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'Test')

    def test_case_mode_and_compose_preedit(self) -> None:
        '''https://github.com/mike-fabian/ibus-typing-booster/issues/717

        The current case mode should not have an influence on the
        Compose preedit.
        '''
        self.engine.set_current_imes(['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'test')
        # Shift_L goes to 'capitalize':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'Test')
        # Next Shift_L goes to 'upper':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'TEST')
        self.engine.do_process_key_event(IBus.KEY_Left, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Left, 0, 0)
        self.assertEqual(2, self.engine.mock_preedit_text_cursor_pos)
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        # The “a” in “TEaST” should not be upper cased:
        self.assertEqual(self.engine.mock_preedit_text, 'TEaST')
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        # Typing the double quote has finished the compose sequence
        # and produced an “ä“ which should then become upper cased
        # as the current case mode is 'upper':
        self.assertEqual(self.engine.mock_preedit_text, 'TEÄST')

    def test_case_mode_and_rfc1345(self) -> None:
        '''https://github.com/mike-fabian/ibus-typing-booster/issues/717

        The current case mode should not have an influence on an unfinished
        m17n transliteration.
        '''
        self.engine.set_current_imes(['t-rfc1345'], update_gsettings=False)
        self.engine.set_dictionary_names(['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'test')
        # Shift_L goes to 'capitalize':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'Test')
        # Next Shift_L goes to 'upper':
        self.engine.do_process_key_event(IBus.KEY_Shift_L, 0, 0)
        self.engine.do_process_key_event(
            IBus.KEY_Shift_L, 0, IBus.ModifierType.RELEASE_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'TEST')
        self.engine.do_process_key_event(IBus.KEY_ampersand, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        # The 'c' in the unfinished m17n transliteration should
        # not be upper cased:
        self.assertEqual(self.engine.mock_preedit_text, 'TEST&c')
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        # Typing the 'o' has finished the m17n transliteration:
        self.assertEqual(self.engine.mock_preedit_text, 'TEST℅')
        self.engine.do_process_key_event(IBus.KEY_ampersand, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        # Again we have an unfinished transliteration, the 'c'
        # should not be upper cased:
        self.assertEqual(self.engine.mock_preedit_text, 'TEST℅&c')
        self.engine.do_process_key_event(IBus.KEY_x, 0, 0)
        # Typing the 'x' finished the transliteration and the result
        # was '&cx'. This finished result gets upper cased because
        # of the current case mode:
        self.assertEqual(self.engine.mock_preedit_text, 'TEST℅&CX')

    def test_sinhala_wijesekara(self) -> None:
        _dummy_trans = self.get_transliterator_or_skip('si-wijesekara')
        self.engine.set_current_imes(
            ['si-wijesekara', 'NoIME'], update_gsettings=False)
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

    def test_vietnamese_telex(self) -> None:
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
        self.assertEqual(self.engine._m17n_trans_parts.candidates, ['o', 'ó', 'ò', 'ỏ', 'õ', 'ọ'])
        self.assertEqual(self.engine._m17n_trans_parts.candidate_show, 0)
        self.assertFalse(self.engine._lookup_table.state
                         == hunspell_table.LookupTableState.M17N_CANDIDATES)
        # self._lookup_table_hidden is probably False here
        # because there will probably be candidates from the
        # vi_VN dictionary.
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine._m17n_trans_parts.candidates, ['ô', 'ố', 'ồ', 'ổ', 'ỗ', 'ộ'])
        self.assertEqual(self.engine._m17n_trans_parts.candidate_show, 0)
        self.assertFalse(self.engine._lookup_table.state
                         == hunspell_table.LookupTableState.M17N_CANDIDATES)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.assertEqual(self.engine._m17n_trans_parts.candidates, [])
        self.assertEqual(self.engine._m17n_trans_parts.candidate_show, 0)
        self.assertFalse(self.engine._lookup_table.state
                         == hunspell_table.LookupTableState.M17N_CANDIDATES)
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

    def test_compose_early_commit(self) -> None:
        ''' https://github.com/mike-fabian/ibus-typing-booster/issues/662 '''
        _dummy_trans = self.get_transliterator_or_skip('t-rfc1345')
        self.engine.set_current_imes(['t-rfc1345'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_x, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'x')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'x·')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'xa')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'xä')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'xäb')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'xäb ')
        # Now make predictions impossible:
        self.engine.set_word_prediction_mode(False, update_gsettings=False)
        self.engine.set_emoji_prediction_mode(False, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_x, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'xäb x')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '·')
        self.assertEqual(self.engine.mock_committed_text, 'xäb x')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'a')
        self.assertEqual(self.engine.mock_committed_text, 'xäb x')
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'xäb xä')
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'xäb xäb')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'xäb xäb ')

    def test_unicode_data_all(self) -> None:
        '''https://github.com/mike-fabian/ibus-typing-booster/issues/667'''
        _dummy_trans = self.get_transliterator_or_skip('t-rfc1345')
        self.engine.set_emoji_prediction_mode(True, update_gsettings=False)
        self.engine.set_current_imes(['t-rfc1345'], update_gsettings=False)
        self.engine.set_dictionary_names(['en_US'], update_gsettings=False)
        # With unicode_data_all_mode set to False,
        # 'bathtub' should find 🛁 U+1F6C1 BATHTUB but
        # **not** 𐃅 U+100C5 LINEAR B IDEOGRAM B225 BATHTUB
        self.engine.set_unicode_data_all_mode(False, update_gsettings=False)
        for char in 'bathtub':
            if char == '_':
                char = 'underscore'
            self.engine.do_process_key_event(getattr(IBus, f'KEY_{char}'), 0, 0)
        candidate_set = {x.phrase for x in self.engine._candidates}
        self.assertTrue('🛁' in candidate_set) # 🛁 U+1F6C1 BATHTUB
        self.assertTrue('𐃅' not in candidate_set) # 𐃅 U+100C5 LINEAR B IDEOGRAM B225 BATHTUB
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        self.assertEqual('', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        # With unicode_data_all_mode set to True,
        # 'bathtub' should find both 🛁 U+1F6C1
        # BATHTUB **and** 𐃅 U+100C5 LINEAR B IDEOGRAM B225 BATHTUB
        self.engine.set_unicode_data_all_mode(True, update_gsettings=False)
        for char in 'bathtub':
            if char == '_':
                char = 'underscore'
            self.engine.do_process_key_event(getattr(IBus, f'KEY_{char}'), 0, 0)
        candidate_set = {x.phrase for x in self.engine._candidates}
        self.assertTrue('🛁' in candidate_set) # 🛁 U+1F6C1 BATHTUB
        self.assertTrue('𐃅' in candidate_set) # 𐃅 U+100C5 LINEAR B IDEOGRAM B225 BATHTUB
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        self.assertEqual('', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        # With unicode_data_all_mode set to True,
        # 'linear_ideogram_bathtub' should not find 🛁 U+1F6C1
        # BATHTUB but  𐃅 U+100C5 LINEAR B IDEOGRAM B225 BATHTUB
        self.engine.set_unicode_data_all_mode(True, update_gsettings=False)
        for char in 'linear_ideogram_bathtub':
            if char == '_':
                char = 'underscore'
            self.engine.do_process_key_event(getattr(IBus, f'KEY_{char}'), 0, 0)
        candidate_set = {x.phrase for x in self.engine._candidates}
        self.assertTrue('🛁'  not in candidate_set) # 🛁 U+1F6C1 BATHTUB
        self.assertTrue('𐃅' in candidate_set) # 𐃅 U+100C5 LINEAR B IDEOGRAM B225 BATHTUB
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        self.assertEqual('', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)

    def test_compose_transliterated_hi_inscript2(self) -> None:
        '''
        Test case for compose sequence using transliteration,
        see: https://github.com/mike-fabian/ibus-typing-booster/issues/654
        /usr/share/X11/locale/en_US.UTF-8/Compose contains:

        <Multi_key> <U093C> <U0930> : "ऱ" U0931 # DEVANAGARI LETTER RRA

        So typing <Multi_key> + ']' + 'j' should produce
        ऱ U+0931 DEVANAGARI LETTER RRA because 'hi-inscript2' transliterates
        ']' to ़ U+093C DEVANAGARI SIGN NUKTA
        'j' to र U+0930 DEVANAGARI LETTER RA
        '''
        _dummy_trans = self.get_transliterator_or_skip('hi-inscript2')
        self.engine.set_current_imes(
            ['hi-inscript2'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '·')
        self.engine.do_process_key_event(IBus.KEY_bracketright, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '\u093c')
        self.engine.do_process_key_event(IBus.KEY_j, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '\u0931')

    def test_compose_and_latn_post(self) -> None:
        self.engine.set_current_imes(
            ['t-latn-post', 'NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_T, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Tr·')
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Tr"')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Trä')
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_dead_diaeresis, 0, 0)
        # /usr/share/X11/locale/en_US.UTF-8/Compose contains:
        # <dead_diaeresis> <space> : "\""  quotedbl # QUOTATION MARK
        # That defines the preedit representation changes to be
        # " U+0022 QUOTATION MARK instead of the
        # ¨ U+00A8 DIAERESIS hardcoded in Typing Booster.
        self.assertEqual(self.engine.mock_preedit_text, 'Tränen"')
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Tränenü')
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Tränenüberstr·')
        self.engine.do_process_key_event(IBus.KEY_diaeresis, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Tränenüberstr¨')
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
        self.assertEqual(self.engine.mock_preedit_text, 'grüs')
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
        self.assertEqual(self.engine.mock_preedit_text, '·')
        self.engine.do_process_key_event(IBus.KEY_S, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'S')
        self.engine.do_process_key_event(IBus.KEY_S, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ẞ')

    def test_keys_which_select_with_shift(self) -> None:
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_g, 0, 0)
        self.assertFalse(self.engine.get_lookup_table().is_cursor_visible())
        self.assertEqual('testing', self.engine.mock_preedit_text)
        self.assertEqual(7, self.engine.mock_preedit_text_cursor_pos)
        self.assertEqual('', self.engine.mock_committed_text)
        self.assertEqual(0, self.engine.mock_committed_text_cursor_pos)
        self.engine.do_process_key_event(IBus.KEY_Left, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Left, 0, 0)
        self.assertFalse(self.engine.get_lookup_table().is_cursor_visible())
        self.assertEqual('testing', self.engine.mock_preedit_text)
        self.assertEqual(5, self.engine.mock_preedit_text_cursor_pos)
        self.assertEqual('', self.engine.mock_committed_text)
        self.assertEqual(0, self.engine.mock_committed_text_cursor_pos)
        self.engine.do_process_key_event(IBus.KEY_Left, 0, IBus.ModifierType.SHIFT_MASK)
        self.assertFalse(self.engine.get_lookup_table().is_cursor_visible())
        self.assertEqual('', self.engine.mock_preedit_text)
        self.assertEqual(0, self.engine.mock_preedit_text_cursor_pos)
        self.assertEqual('testing', self.engine.mock_committed_text)
        self.assertEqual(4, self.engine.mock_committed_text_cursor_pos)

    def test_compose_completions(self) -> None:
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual('·', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        self.engine.do_process_key_event(IBus.KEY_minus, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_minus, 0, 0)
        self.assertEqual('--', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        self.engine.do_process_key_event(IBus.KEY_x, 0, 0)
        # Beep! No other change.
        self.assertEqual('--', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        self.assertEqual(0, len(self.engine._candidates))
        # Request completions:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.assertEqual(3, len(self.engine._candidates))
        self.engine.do_process_key_event(IBus.KEY_x, 0, 0)
        # Beep! Completion lookup cancelled:
        self.assertEqual(0, len(self.engine._candidates))
        # Request completion:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.assertEqual(3, len(self.engine._candidates))
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        # Completion lookup cancelled (no Beep):
        self.assertEqual(0, len(self.engine._candidates))
        # Request completion:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.assertEqual(3, len(self.engine._candidates))
        candidates = []
        for candidate in self.engine._candidates:
            candidates.append(candidate.phrase)
        self.assertEqual(['­', '—', '–'], candidates)
        # Commit to preedit:
        self.engine.do_process_key_event(IBus.KEY_3, 0, 0)
        self.assertEqual('–', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        self.assertEqual(0, len(self.engine._candidates))
        # Really commit:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual('', self.engine.mock_preedit_text)
        self.assertEqual('– ', self.engine.mock_committed_text)
        self.assertEqual(0, len(self.engine._candidates))
        # Start new compose sequence
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual('·', self.engine.mock_preedit_text)
        self.assertEqual('– ', self.engine.mock_committed_text)
        self.engine.do_process_key_event(IBus.KEY_minus, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_minus, 0, 0)
        self.assertEqual('--', self.engine.mock_preedit_text)
        self.assertEqual('– ', self.engine.mock_committed_text)
        self.assertEqual(0, len(self.engine._candidates))
        # Request completion:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.assertEqual(3, len(self.engine._candidates))
        candidates = []
        for candidate in self.engine._candidates:
            candidates.append(candidate.phrase)
        self.assertEqual(['­', '—', '–'], candidates)
        # Select first candidate:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        # Cancel selection:
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        # Lookup table still there:
        self.assertEqual(3, len(self.engine._candidates))
        # Cancel lookup:
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        # Lookup table gone:
        self.assertEqual(0, len(self.engine._candidates))
        # Request completion:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.assertEqual(3, len(self.engine._candidates))
        candidates = []
        for candidate in self.engine._candidates:
            candidates.append(candidate.phrase)
        self.assertEqual(['­', '—', '–'], candidates)
        # Select second candidate:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_x, 0, 0)
        # As a candidate is selected, x commits to preedit and
        # appends:
        self.assertEqual('—x', self.engine.mock_preedit_text)
        self.assertEqual('– ', self.engine.mock_committed_text)
        # There are probably some candidates now, '—x' might show
        # completions.
        # Commit with space now:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual('', self.engine.mock_preedit_text)
        self.assertEqual('– —x ', self.engine.mock_committed_text)
        self.assertEqual(0, len(self.engine._candidates))
        # Start new compose sequence
        self.engine.do_process_key_event(IBus.KEY_dead_grave, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_dead_circumflex, 0, 0)
        self.assertEqual('`^', self.engine.mock_preedit_text)
        self.assertEqual('– —x ', self.engine.mock_committed_text)
        # Request completion:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.assertTrue(0 < len(self.engine._candidates))
        candidates = []
        for candidate in self.engine._candidates:
            candidates.append(candidate.phrase)
        self.assertTrue('ầ' in candidates)
        # Finish the sequence:
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual('ầ', self.engine.mock_preedit_text)
        self.assertEqual('– —x ', self.engine.mock_committed_text)
        # Commit with space now:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual('', self.engine.mock_preedit_text)
        self.assertEqual('– —x ầ ', self.engine.mock_committed_text)

    def test_compose_do_not_throw_away_invalid_sequences(self) -> None:
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_G, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.assertEqual('Gr', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual('Gr·', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        self.engine.do_process_key_event(IBus.KEY_quotedbl, 0, 0)
        self.assertEqual('Gr"', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        # Now typing “slash” should not add anything to the compose
        # sequence because “<Multi_key> <quotedbl> <slash>” is an
        # invalid sequence, the slash should be ignored (maybe with an
        # error beep) and the preedit stay the same (The original
        # X11 behaviour would be to throw the whole compose sequence
        # silently away and produce nothing):
        self.engine.do_process_key_event(IBus.KEY_slash, 0, 0)
        self.assertEqual('Gr"', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        # Now complete the compose sequence by typing a valid
        # continuation:
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual('Grö', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        # Start a new compose sequence
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual('Grö·', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual('Grös', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        # Invalid continuation, error beep, no change:
        self.engine.do_process_key_event(IBus.KEY_x, 0, 0)
        self.assertEqual('Grös', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        # Valid continuation:
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual('Größ', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        # Finish the word and commit with space:
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual('', self.engine.mock_preedit_text)
        self.assertEqual('Größe ', self.engine.mock_committed_text)
        # Start a new compose sequence
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual('·', self.engine.mock_preedit_text)
        self.assertEqual('Größe ', self.engine.mock_committed_text)
        self.engine.do_process_key_event(IBus.KEY_minus, 0, 0)
        self.assertEqual('-', self.engine.mock_preedit_text)
        self.assertEqual('Größe ', self.engine.mock_committed_text)
        self.engine.do_process_key_event(IBus.KEY_minus, 0, 0)
        self.assertEqual('--', self.engine.mock_preedit_text)
        self.assertEqual('Größe ', self.engine.mock_committed_text)
        # Invalid continuation, error beep, no change:
        self.engine.do_process_key_event(IBus.KEY_x, 0, 0)
        self.assertEqual('--', self.engine.mock_preedit_text)
        self.assertEqual('Größe ', self.engine.mock_committed_text)
        # Finish the sequence with a valid continuation:
        self.engine.do_process_key_event(IBus.KEY_minus, 0, 0)
        self.assertEqual('—', self.engine.mock_preedit_text)
        self.assertEqual('Größe ', self.engine.mock_committed_text)
        # commit with arrow right:
        self.engine.do_process_key_event(IBus.KEY_Right, 0, 0)
        self.assertEqual('', self.engine.mock_preedit_text)
        self.assertEqual('Größe —', self.engine.mock_committed_text)

    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_backspace_left_when_candidate_manually_selected(self) -> None:
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_C, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_d, 0, 0)
        self.assertEqual('Cassand', self.engine.mock_preedit_text)
        self.assertEqual(7, self.engine.mock_preedit_text_cursor_pos)
        self.assertEqual('Cassandra', self.engine._candidates[0].phrase)
        # Tab should select the first candidate, i.e. “Cassandra” now:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        # When Backspace is typed, “Cassandra” is put into the preedit
        # and then the Backspace is applied, leaving “Cassandr”:
        self.engine.do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual('Cassandr', self.engine.mock_preedit_text)
        self.assertEqual(8, self.engine.mock_preedit_text_cursor_pos)
        self.assertEqual('Cassandra', self.engine._candidates[0].phrase)
        # Tab should again select the first candidate, which should
        # still be “Cassandra” now:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        # When Control+Left is typed, “Cassandra” is put into the
        # preedit and then the Control+Left is applied, moving
        # the cursor to the beginning of the preedit:
        self.engine.do_process_key_event(
            IBus.KEY_Left, 0, IBus.ModifierType.CONTROL_MASK)
        self.assertEqual('Cassandra', self.engine.mock_preedit_text)
        self.assertEqual(0, self.engine.mock_preedit_text_cursor_pos)
        self.assertEqual('Cassandra', self.engine._candidates[0].phrase)
        # Tab should select again the first candidate, which should
        # still be “Cassandra” now:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        # When Left (without Control!) is typed, “Cassandra” is put
        # into the preedit and then the Left is applied,
        # moving the cursor one character left from the end of the
        # candidate which had been selected:
        self.engine.do_process_key_event(
            IBus.KEY_Left, 0, 0)
        self.assertEqual('Cassandra', self.engine.mock_preedit_text)
        self.assertEqual(8, self.engine.mock_preedit_text_cursor_pos)
        self.assertEqual('Cassandra', self.engine._candidates[0].phrase)

    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_start_compose_when_candidate_selected(self) -> None:
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        # Use off the record mode to avoid the learning so
        # we can type the same string twice and get the same
        # candidate on the second try:
        self.engine.set_off_the_record_mode(
            True, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.assertEqual('tastin', self.engine.mock_preedit_text)
        self.assertEqual('tasting', self.engine._candidates[0].phrase)
        # Tab should select the first candidate, i.e. “tasting” now:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        # Typing an “s” should then replace the typed string
        # in the preedit with the selection, move the cursor to the
        # end and then add the “s”:
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual('tastings', self.engine.mock_preedit_text)
        # Commit with space:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual('', self.engine.mock_preedit_text)
        self.assertEqual([], self.engine._candidates)
        self.assertEqual('tastings ', self.engine.mock_committed_text)
        # Repeat the same typing of “tastin”:
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_t, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.assertEqual('tastin', self.engine.mock_preedit_text)
        self.assertEqual('tasting', self.engine._candidates[0].phrase)
        # Tab should select the first candidate, i.e. “tasting” now:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        # Now type “ß” using compose, this should also replace the
        # typed string in the preedit with the selection, move the
        # cursor to the end and then add the “ß”:
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual('tasting·', self.engine.mock_preedit_text)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual('tastings', self.engine.mock_preedit_text)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.assertEqual('tastingß', self.engine.mock_preedit_text)

    def test_compose_sequences_khmer_digraphs(self) -> None:
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(0x010017FF, 0, 0)
        self.assertEqual(
            'ាំ', # ា U+17B6 KHMER VOWEL SIGN AA ំ U+17C6 KHMER SIGN NIKAHIT
            self.engine.mock_preedit_text)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ាំ ')
        self.engine.do_process_key_event(0x010017FE, 0, 0)
        self.assertEqual(
            'ោះ', # ោ U+17C4 KHMER VOWEL SIGN OO ះ U+17C7 KHMER SIGN REAHMUK
            self.engine.mock_preedit_text)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ាំ ោះ ')
        self.engine.do_process_key_event(0x010017FD, 0, 0)
        self.assertEqual(
            'េះ', # េ U+17C1 KHMER VOWEL SIGN E ះ U+17C7 KHMER SIGN REAHMUK
            self.engine.mock_preedit_text)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ាំ ោះ េះ ')
        self.engine.do_process_key_event(0x010017FC, 0, 0)
        self.assertEqual(
            'ុំ', # ុ U+17BB KHMER VOWEL SIGN U ំ U+17C6 KHMER SIGN NIKAHIT
            self.engine.mock_preedit_text)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ាំ ោះ េះ ុំ ')
        self.engine.do_process_key_event(0x010017FB, 0, 0)
        self.assertEqual(
            'ុះ', # ុ U+17BB KHMER VOWEL SIGN U ះ U+17C7 KHMER SIGN REAHMUK
            self.engine.mock_preedit_text)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ាំ ោះ េះ ុំ ុះ ')

    def test_compose_sequences_arabic_lam_alef(self) -> None:
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(0x0100FEFB, 0, 0)
        self.assertEqual(
            'لا', # ل U+0644 ARABIC LETTER LAM ا U+0627 ARABIC LETTER ALEF U+0627
            self.engine.mock_preedit_text)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'لا ')
        self.engine.do_process_key_event(0x0100FEF7, 0, 0)
        self.assertEqual(
            'لأ', # ل U+0644 ARABIC LETTER LAM أ U+0623 ARABIC LETTER ALEF WITH HAMZA ABOVE
            self.engine.mock_preedit_text)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'لا لأ ')
        self.engine.do_process_key_event(0x0100FEF9, 0, 0)
        self.assertEqual(
            'لإ', # ل U+0644 ARABIC LETTER LAM إ U+0625 ARABIC LETTER ALEF WITH HAMZA BELOW
            self.engine.mock_preedit_text)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'لا لأ لإ ')
        self.engine.do_process_key_event(0x0100FEF5, 0, 0)
        self.assertEqual(
            'لآ', # ل U+0644 ARABIC LETTER LAM آ U+0622 ARABIC LETTER ALEF WITH MADDA ABOVE
            self.engine.mock_preedit_text)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'لا لأ لإ لآ ')

    def test_compose_sequences_arabic_multi_key(self) -> None:
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.engine.do_process_key_event(0x01000654, 0, 0)
        self.engine.do_process_key_event(0x010006D5, 0, 0)
        self.assertEqual(
            'ۀ', # U+06C0 ARABIC LETTER HEH WITH YEH ABOVE
            self.engine.mock_preedit_text)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ۀ ')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.engine.do_process_key_event(0x01000653, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Arabic_alef, 0, 0)
        self.assertEqual(
            'آ', # U+0622 ARABIC LETTER ALEF WITH MADDA ABOVE
            self.engine.mock_preedit_text)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ۀ آ ')

    def test_compose_sequences_containing_code_points(self) -> None:
        compose_result = self._compose_sequences.compose([IBus.KEY_Multi_key, IBus.KEY_macron, 0x010001EA])
        if compose_result != '':
            self.skipTest(
                'Compose file too old, older than '
                'https://gitlab.freedesktop.org/xorg/lib/libx11/-/commit/af2b6dfab1616dc85be9c9b196e4c56d00447851 '
                f'self._compose_sequences.compose([IBus.KEY_Multi_key, IBus.KEY_macron, 0x010001EA]) = {compose_result}'
            )
        compose_result = self._compose_sequences.compose([IBus.KEY_Multi_key, IBus.KEY_less, IBus.KEY_slash])
        if compose_result != "≮": # U+226E NOT LESS-THAN
            self.skipTest(
                'Compose file too old, older than '
                'https://gitlab.freedesktop.org/xorg/lib/libx11/-/commit/03ba0140940cc76524d83096a47309f5c398541f '
                f'self._compose_sequences.compose([IBus.KEY_Multi_key, IBus.KEY_less, IBus.KEY_slash]) = {compose_result}'
            )
        self.engine.set_current_imes(
            ['t-latn-pre', 'NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_US'], update_gsettings=False)

        self.engine.do_process_key_event(IBus.KEY_dead_macron, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '¯')
        self.engine.do_process_key_event(0x010001EB, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭ')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ǭ ')
        self.engine.mock_committed_text = ''

        self.engine.do_process_key_event(IBus.KEY_dead_macron, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '¯')
        self.engine.do_process_key_event(IBus.KEY_dead_ogonek, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '¯˛')
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭ')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ǭ ')
        self.engine.mock_committed_text = ''

        self.engine.do_process_key_event(IBus.KEY_dead_macron, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '¯')
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '¯·')
        self.engine.do_process_key_event(IBus.KEY_semicolon, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '¯·;')
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭ')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ǭ ')
        self.engine.mock_committed_text = ''

        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '·')
        self.engine.do_process_key_event(IBus.KEY_macron, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '¯')
        self.engine.do_process_key_event(IBus.KEY_dead_ogonek, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '¯˛')
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭ')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ǭ ')
        self.engine.mock_committed_text = ''

        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '·')
        self.engine.do_process_key_event(IBus.KEY_macron, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '¯')
        self.engine.do_process_key_event(IBus.KEY_semicolon, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '¯;')
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭ')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ǭ ')
        self.engine.mock_committed_text = ''

        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '·')
        self.engine.do_process_key_event(IBus.KEY_underscore, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '_')
        self.engine.do_process_key_event(IBus.KEY_dead_ogonek, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '_˛')
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭ')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ǭ ')
        self.engine.mock_committed_text = ''

        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '·')
        self.engine.do_process_key_event(IBus.KEY_underscore, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '_')
        self.engine.do_process_key_event(IBus.KEY_semicolon, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '_;')
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǭ')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ǭ ')
        self.engine.mock_committed_text = ''

        self.engine.do_process_key_event(IBus.KEY_dead_caron, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ˇ')
        self.engine.do_process_key_event(IBus.KEY_EZH, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Ǯ')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'Ǯ ')
        self.engine.mock_committed_text = ''

        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '·')
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'c')
        self.engine.do_process_key_event(IBus.KEY_EZH, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Ǯ')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'Ǯ ')
        self.engine.mock_committed_text = ''

        self.engine.do_process_key_event(IBus.KEY_dead_caron, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ˇ')
        self.engine.do_process_key_event(IBus.KEY_ezh, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǯ')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ǯ ')
        self.engine.mock_committed_text = ''

        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '·')
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'c')
        self.engine.do_process_key_event(IBus.KEY_ezh, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ǯ')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ǯ ')
        self.engine.mock_committed_text = ''

        self.engine.do_process_key_event(IBus.KEY_Multi_key,0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '·')
        self.engine.do_process_key_event(0x01002276, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '≶')
        self.engine.do_process_key_event(IBus.KEY_slash, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '≸')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '≸ ')
        self.engine.mock_committed_text = ''

        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '·')
        self.engine.do_process_key_event(0x01000654, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '\u0654')
        self.engine.do_process_key_event(IBus.KEY_Arabic_yeh, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '\u0626')
        self.assertEqual(self.engine.mock_preedit_text, 'ئ')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '\u0626 ')
        self.assertEqual(self.engine.mock_committed_text, 'ئ ')
        self.engine.mock_committed_text = ''

        # <Multi_key> <U093C> <U0915> : "क़" U0958 # DEVANAGARI LETTER QA
        self.engine.do_process_key_event(IBus.KEY_Multi_key, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '·')
        self.engine.do_process_key_event(0x0100093C, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '\u093C')
        self.engine.do_process_key_event(0x01000915, 0, 0)
        self.assertEqual(
            self.engine.mock_preedit_text,
            itb_util.normalize_nfc_and_composition_exclusions('\u0958'))
        self.assertEqual(
            self.engine.mock_preedit_text,
            itb_util.normalize_nfc_and_composition_exclusions('क़'))
        self.assertEqual(
            self.engine.mock_preedit_text,
            itb_util.normalize_nfc_and_composition_exclusions('\u0915\u093C'))
        self.assertEqual(
            self.engine.mock_preedit_text,
            itb_util.normalize_nfc_and_composition_exclusions('क़'))
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        # On commit the text is not only converted to NFC but also
        # recomposes the composition exclusions
        # See: https://github.com/mike-fabian/ibus-typing-booster/issues/531
        # https://www.unicode.org/Public/16.0.0/ucd/CompositionExclusions.txt
        self.assertEqual(self.engine.mock_committed_text,
                         '\u0958 ')
        self.engine.mock_committed_text = ''

    def test_compose_combining_chars_in_preedit_representation(self) -> None:
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
        testutils.get_libvoikko_version() >= '4.3',
        "Skipping, requires python3-libvoikko version >= 4.3.")
    @unittest.skipIf(
        testutils.init_libvoikko_error(),
        f'Skipping, {testutils.init_libvoikko_error()}')
    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_voikko(self) -> None:
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
        self.assertEqual(self.engine._candidates[0].phrase, 'kissa')
        self.assertEqual(self.engine._candidates[0].user_freq, -1)
        self.assertEqual(self.engine._candidates[0].comment, '')
        self.assertEqual(self.engine._candidates[0].from_user_db, False)
        self.assertEqual(self.engine._candidates[0].spell_checking, True)
        self.assertEqual(self.engine._candidates[1].phrase, 'kissaa')
        self.assertEqual(self.engine._candidates[1].user_freq, -2)
        self.assertEqual(self.engine._candidates[1].comment, '')
        self.assertEqual(self.engine._candidates[1].from_user_db, False)
        self.assertEqual(self.engine._candidates[1].spell_checking, True)
        self.assertEqual(self.engine._candidates[2].phrase, 'kisassa')
        self.assertEqual(self.engine._candidates[2].user_freq, -3)
        self.assertEqual(self.engine._candidates[2].comment, '')
        self.assertEqual(self.engine._candidates[2].from_user_db, False)
        self.assertEqual(self.engine._candidates[2].spell_checking, True)
        self.assertEqual(self.engine._candidates[3].phrase, 'kisussa')
        self.assertEqual(self.engine._candidates[3].user_freq, -4)
        self.assertEqual(self.engine._candidates[3].comment, '')
        self.assertEqual(self.engine._candidates[3].from_user_db, False)
        self.assertEqual(self.engine._candidates[3].spell_checking, True)
        self.assertEqual(self.engine._candidates[4].phrase, 'Kiassa')
        self.assertEqual(self.engine._candidates[4].user_freq, -5)
        self.assertEqual(self.engine._candidates[4].comment, '')
        self.assertEqual(self.engine._candidates[4].from_user_db, False)
        self.assertEqual(self.engine._candidates[4].spell_checking, True)

    @unittest.skipUnless(
        testutils.get_libvoikko_version() >= '4.3',
        "Skipping, requires python3-libvoikko version >= 4.3.")
    @unittest.skipIf(
        testutils.init_libvoikko_error(),
        f'Skipping, {testutils.init_libvoikko_error()}')
    @unittest.skipUnless(
        IS_ENCHANT_AVAILABLE,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        testutils.enchant_sanity_test(language='cs_CZ', word='Praha'),
        'Skipping because python3-enchant seems broken for cs_CZ.')
    @unittest.skipUnless(
        testutils.enchant_working_as_expected(),
        'Skipping because of an unexpected change in the enchant behaviour.')
    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_voikko_en_GB_fi_FI(self) -> None:
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
        candidate_phrases_found = set()
        candidate_phrases = set(
            ('kiss', 'kissa', 'Kiassa', 'kissaa', 'kisassa', 'kisussa'))
        for candidate in self.engine._candidates:
            if candidate.phrase in candidate_phrases:
                self.assertTrue(candidate.user_freq < 0)
                self.assertEqual(candidate.comment, '')
                self.assertEqual(candidate.from_user_db, False)
                self.assertEqual(candidate.spell_checking, True)
                candidate_phrases_found.add(candidate.phrase)
        self.assertTrue(candidate_phrases_found == candidate_phrases)

    def test_control_alpha(self) -> None:
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

    def test_appending_to_selected_candidate_with_accents(self) -> None:
        '''Test case for
        https://github.com/mike-fabian/ibus-typing-booster/issues/234
        '''
        self.engine.set_current_imes(
            ['NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_GB'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_d, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_p, 0, 0)
        self.engine.do_process_key_event(0x00E2, 0, 0) # â
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(
            ['d', 'i', 's', 'c', 'r', 'e', 'p', 'â', 'n', 'c', 'i', 'a'],
            self.engine._typed_string)
        self.assertEqual('discrepância', self.engine.mock_preedit_text)
        self.assertEqual('', self.engine.mock_committed_text)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(
            [],
            self.engine._typed_string)
        self.assertEqual('', self.engine.mock_preedit_text)
        self.assertEqual('discrepância ', self.engine.mock_committed_text)
        self.engine.do_process_key_event(IBus.KEY_d, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_r, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_e, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_p, 0, 0)
        self.engine.do_process_key_event(0x00E2, 0, 0) # â
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_c, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(
            ['d', 'i', 's', 'c', 'r', 'e', 'p', 'â', 'n', 'c', 'i'],
            self.engine._typed_string)
        self.assertEqual('discrepânci', self.engine.mock_preedit_text)
        self.assertEqual('discrepância ', self.engine.mock_committed_text)
        self.assertEqual('discrepância',
                         self.engine._candidates[0].phrase)
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_comma, 0, 0)
        self.assertEqual(
            ['d', 'i', 's', 'c', 'r', 'e', 'p', 'â', 'n', 'c', 'i', 'a', ','],
            self.engine._typed_string)
        self.assertEqual('discrepância,', self.engine.mock_preedit_text)
        self.assertEqual('discrepância ', self.engine.mock_committed_text)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(
            [],
            self.engine._typed_string)
        self.assertEqual('', self.engine.mock_preedit_text)
        self.assertEqual('discrepância discrepância, ', self.engine.mock_committed_text)

    def test_m17n_unicode_improved(self) -> None:
        '''Test case for for handling space with the improved version
        of unicode.mim, see:
        https://github.com/mike-fabian/ibus-typing-booster/issues/281
        '''
        _dummy_trans = self.get_transliterator_or_skip('t-unicode')
        self.engine.set_current_imes(
            ['t-unicode'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['en_GB'], update_gsettings=False)
        # Set the key bindings so that digits do not commit:
        self.engine.set_keybindings({
            'commit_candidate_1': [],
            'commit_candidate_1_plus_space': [],
            'commit_candidate_2': [],
            'commit_candidate_2_plus_space': [],
            'commit_candidate_3': [],
            'commit_candidate_3_plus_space': [],
            'commit_candidate_4': [],
            'commit_candidate_4_plus_space': [],
            'commit_candidate_5': [],
            'commit_candidate_5_plus_space': [],
            'commit_candidate_6': [],
            'commit_candidate_6_plus_space': [],
            'commit_candidate_7': [],
            'commit_candidate_7_plus_space': [],
            'commit_candidate_8': [],
            'commit_candidate_8_plus_space': [],
            'commit_candidate_9': [],
            'commit_candidate_9_plus_space': [],
        }, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_u, 0,
                                         IBus.ModifierType.CONTROL_MASK)
        self.engine.do_process_key_event(IBus.KEY_0, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_9, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_7, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_2, 0, 0)
        if self.engine.mock_preedit_text != 'U+0972':
            # The original version of unicode.mim already commits
            # after 4 hex digits, i.e. we already get ॲ committed
            # here.
            self.skipTest(
                'The improved version of unicode.mim is not installed.')
        # With the improved version we need a space to convert the
        # code point to the Unicode charater and the result should not
        # be committed but just added to the preedit:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ॲ')
        self.assertEqual(self.engine.mock_committed_text, '')
        # We can add more stuff to the preedit:
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'ॲa')
        self.assertEqual(self.engine.mock_committed_text, '')
        # And finally commit:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'ॲa ')

    def test_lsymbol(self) -> None:
        _dummy_trans = self.get_transliterator_or_skip('t-lsymbol')
        self.engine.set_current_imes(
            ['t-lsymbol', 'NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['None'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_slash, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_colon, 0, 0)
        self.assertEqual(self.engine._typed_string, ['a', '/', ':'])
        self.assertEqual(self.engine.mock_preedit_text, 'a/:')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_parenright, 0, 0)
        self.assertEqual(len(self.engine._candidates), 20)
        self.assertEqual(self.engine._typed_string, ['a', '/', ':', ')'])
        self.assertEqual(self.engine.mock_preedit_text, 'a☺\uFE0F')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual(len(self.engine._candidates), 1)
        self.assertEqual(self.engine._candidates[0].phrase, '/:')
        self.assertEqual(self.engine._typed_string, ['a', '/', ':'])
        self.assertEqual(self.engine.mock_preedit_text, 'a/:')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_parenright, 0, 0)
        self.assertEqual(len(self.engine._candidates), 20)
        self.assertEqual(self.engine._typed_string, ['a', '/', ':', ')'])
        self.assertEqual(self.engine.mock_preedit_text, 'a☺\uFE0F')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        # `b` key just adds a 'b' to the typed string as nothing was
        # **manually** selected in the lookup table (the first
        # candidate was *automatically* selected). This is
        # intentional, just typing along without manually choosing
        # candidates should preserve the typed string until a commit
        # happens!
        #
        #There should be no candidates now:
        self.assertEqual(len(self.engine._candidates), 0)
        # And the preedit and typed string have just the 'b' added:
        self.assertEqual(self.engine._typed_string, ['a', '/', ':', ')', 'b'])
        self.assertEqual(self.engine.mock_preedit_text, 'a☺\uFE0Fb')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual(len(self.engine._candidates), 20)
        self.assertEqual(self.engine._typed_string, ['a', '/', ':', ')'])
        self.assertEqual(self.engine.mock_preedit_text, 'a☺\uFE0F')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual(len(self.engine._candidates), 1)
        self.assertEqual(self.engine._typed_string, ['a', '/', ':'])
        self.assertEqual(self.engine.mock_preedit_text, 'a/:')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_parenright, 0, 0)
        # But adding the ')' makes the m17n sequence complete again
        # and produces candidates again:
        self.assertEqual(len(self.engine._candidates), 20)
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        # The 'b' is added to the preedit again and the candidates
        # disappear again:
        self.assertEqual(len(self.engine._candidates), 0)
        self.assertEqual(self.engine._typed_string, ['a', '/', ':', ')', 'b'])
        self.assertEqual(self.engine.mock_preedit_text, 'a☺\uFE0Fb')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        # The space has committed:
        self.assertEqual(self.engine._typed_string, [])
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'a☺\uFE0Fb ')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_slash, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_colon, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_parenright, 0, 0)
        # Candidates back:
        self.assertEqual(len(self.engine._candidates), 20)
        self.assertEqual(self.engine._typed_string, ['a', '/', ':', ')'])
        self.assertEqual(self.engine.mock_preedit_text, 'a☺\uFE0F')
        self.assertEqual(self.engine.mock_committed_text, 'a☺\uFE0Fb ')
        self.assertEqual(self.engine._candidates[0].phrase, '☺\uFE0F')
        self.assertEqual(self.engine._candidates[1].phrase, '😃')
        self.assertEqual(self.engine._candidates[5].phrase, '😇')
        self.engine.do_process_key_event(IBus.KEY_F6, 0, 0)
        # F6 commits the 6th candidate to preedit and typed string:
        self.assertEqual(self.engine._typed_string, ['a', '😇'])
        self.assertEqual(self.engine.mock_preedit_text, 'a😇')
        self.assertEqual(self.engine.mock_committed_text, 'a☺\uFE0Fb ')
        self.assertEqual(len(self.engine._candidates), 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_slash, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_colon, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_parenright, 0, 0)
        # Candidates back:
        self.assertEqual(len(self.engine._candidates), 20)
        self.assertEqual(self.engine._typed_string, ['a', '😇', 'a', '/', ':', ')'])
        self.assertEqual(self.engine.mock_preedit_text, 'a😇a☺\uFE0F')
        self.assertEqual(self.engine.mock_committed_text, 'a☺\uFE0Fb ')
        self.assertEqual(self.engine._candidates[0].phrase, '☺\uFE0F')
        self.assertEqual(self.engine._candidates[1].phrase, '😃')
        self.assertEqual(self.engine._candidates[5].phrase, '😇')
        # Escape to cancel the **automatic** selection of the first candidate
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        # Candidates should still be there:
        self.assertEqual(len(self.engine._candidates), 20)
        # Tab to select the first candidate **manually**:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        # Candidates should still be there:
        self.assertEqual(len(self.engine._candidates), 20)
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        # Because the candidate is now **manually** selected, the 'b'
        # does **not** just add to the the typed string but first
        # copies the selected candidate into the typed string.
        # I.e. this does **not** preserve the typed string, which is
        # intentional!  There should be no candidates now:
        self.assertEqual(len(self.engine._candidates), 0)
        self.assertEqual(self.engine._typed_string, ['a', '😇', 'a', '☺', '\uFE0F', 'b'])
        self.assertEqual(self.engine.mock_preedit_text, 'a😇a☺\uFE0Fb')
        self.assertEqual(self.engine.mock_committed_text, 'a☺\uFE0Fb ')
        # commit with space
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(len(self.engine._candidates), 0)
        self.assertEqual(self.engine._typed_string, [])
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'a☺\uFE0Fb a😇a☺\uFE0Fb ')
        # `/ space` produces a single candidate with t-lsymbol,
        # U+200C ZERO WIDTH NON-JOINER:
        self.engine.do_process_key_event(IBus.KEY_slash, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(len(self.engine._candidates), 1)
        self.assertEqual(self.engine._candidates[0].phrase, '\u200C')
        self.assertEqual(self.engine._typed_string, ['/', ' '])
        self.assertEqual(self.engine.mock_preedit_text, '\u200C')
        self.assertEqual(self.engine.mock_committed_text, 'a☺\uFE0Fb a😇a☺\uFE0Fb ')
        # commit with space
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(len(self.engine._candidates), 0)
        self.assertEqual(self.engine._typed_string, [])
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'a☺\uFE0Fb a😇a☺\uFE0Fb \u200C ')
        # `a / space` should also produce a single candidate with
        # t-lsymbol, U+200C ZERO WIDTH NON-JOINER:
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_slash, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(len(self.engine._candidates), 1)
        self.assertEqual(self.engine._candidates[0].phrase, '\u200C')
        self.assertEqual(self.engine._typed_string, ['a', '/', ' '])
        self.assertEqual(self.engine.mock_preedit_text, 'a\u200C')
        self.assertEqual(self.engine.mock_committed_text, 'a☺\uFE0Fb a😇a☺\uFE0Fb \u200C ')
        # commit with space
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(len(self.engine._candidates), 0)
        self.assertEqual(self.engine._typed_string, [])
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(
            self.engine.mock_committed_text, 'a☺\uFE0Fb a😇a☺\uFE0Fb \u200C a\u200C ')

    def test_zh_py(self) -> None:
        _dummy_trans = self.get_transliterator_or_skip('zh-py')
        self.engine.set_current_imes(
            ['zh-py', 'NoIME'], update_gsettings=False)
        # There are sequences starting with `a` and `x` in zh-py. But
        # there is no sequence starting with `xa`. zh-py does not
        # commit the `x` when the `a` is typed but keeps it in
        # preedit.
        #
        # In that case the m17n preedit has a different length then
        # the candidates which makes it a particularly interesting
        # test case. Typing Booster should do the same as ibus-m17n in
        # this case as well.
        self.engine.do_process_key_event(IBus.KEY_x, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(len(self.engine._candidates), 8)
        self.assertEqual(self.engine._candidates[0].phrase, '啊')
        self.assertEqual(self.engine._candidates[1].phrase, '呵')
        self.assertEqual(self.engine._typed_string, ['x', 'a'])
        self.assertEqual(self.engine.mock_preedit_text, 'x啊')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(len(self.engine._candidates), 97)
        self.assertEqual(self.engine._candidates[0].phrase, '爱')
        self.assertEqual(self.engine._candidates[1].phrase, '愛')
        self.assertEqual(self.engine._typed_string, ['x', 'a', 'i'])
        self.assertEqual(self.engine.mock_preedit_text, 'x爱')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual(len(self.engine._candidates), 8)
        self.assertEqual(self.engine._candidates[0].phrase, '啊')
        self.assertEqual(self.engine._candidates[1].phrase, '呵')
        self.assertEqual(self.engine._typed_string, ['x', 'a'])
        self.assertEqual(self.engine.mock_preedit_text, 'x啊')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(len(self.engine._candidates), 97)
        self.assertEqual(self.engine._candidates[0].phrase, '爱')
        self.assertEqual(self.engine._candidates[1].phrase, '愛')
        self.assertEqual(self.engine._typed_string, ['x', 'a', 'i'])
        self.assertEqual(self.engine.mock_preedit_text, 'x爱')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(len(self.engine._candidates), 97)
        self.assertEqual(self.engine._candidates[0].phrase, '爱')
        self.assertEqual(self.engine._candidates[1].phrase, '愛')
        self.assertEqual(self.engine._typed_string, ['x', 'a', 'i', 'a', 'i'])
        self.assertEqual(self.engine.mock_preedit_text, 'x爱爱')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual(len(self.engine._candidates), 97)
        self.assertEqual(self.engine._candidates[0].phrase, '爱')
        self.assertEqual(self.engine._candidates[1].phrase, '愛')
        self.assertEqual(self.engine._typed_string, ['x', 'a', 'i'])
        self.assertEqual(self.engine.mock_preedit_text, 'x爱')
        self.assertEqual(self.engine.mock_committed_text, '')
        # Escape to cancel the **automatic** selection of the first candidate
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        # Candidates should still be there:
        self.assertEqual(len(self.engine._candidates), 97)
        # Tab to select the first candidate **manually**:
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        # Candidates should still be there:
        self.assertEqual(len(self.engine._candidates), 97)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        # Because the candidate is now **manually** selected, the 'a'
        # does **not** just add to the the typed string but first
        # copies the selected candidate into the typed string.
        # I.e. this does **not** preserve the typed string, which is
        # intentional!
        self.assertEqual(len(self.engine._candidates), 8)
        self.assertEqual(self.engine._candidates[0].phrase, '啊')
        self.assertEqual(self.engine._candidates[1].phrase, '呵')
        self.assertEqual(self.engine._typed_string, ['x', '爱', 'a'])
        self.assertEqual(self.engine.mock_preedit_text, 'x爱啊')
        self.assertEqual(self.engine.mock_committed_text, '')
        # commit “to preedit” with space:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(len(self.engine._candidates), 0)
        self.assertEqual(self.engine._typed_string, ['x', '爱', '啊'])
        self.assertEqual(self.engine.mock_preedit_text, 'x爱啊')
        self.assertEqual(self.engine.mock_committed_text, '')
        # “really” commit with a second space:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(len(self.engine._candidates), 0)
        self.assertEqual(self.engine._typed_string, [])
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'x爱啊')

    def test_zh_tonepy(self) -> None:
        _dummy_trans = self.get_transliterator_or_skip('zh-tonepy')
        self.engine.set_current_imes(
            ['zh-tonepy', 'NoIME'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(len(self.engine._candidates), 1)
        self.assertEqual(self.engine._candidates[0].phrase, 'a')
        self.assertEqual(self.engine._typed_string, ['a'])
        self.assertEqual(self.engine.mock_preedit_text, 'a')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_2, 0, 0)
        self.assertEqual(len(self.engine._candidates), 1)
        self.assertEqual(self.engine._candidates[0].phrase, '嗄')
        self.assertEqual(self.engine._typed_string, ['a', '2'])
        self.assertEqual(self.engine.mock_preedit_text, '嗄')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual(len(self.engine._candidates), 1)
        self.assertEqual(self.engine._candidates[0].phrase, 'a')
        self.assertEqual(self.engine._typed_string, ['a'])
        self.assertEqual(self.engine.mock_preedit_text, 'a')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(len(self.engine._candidates), 1)
        self.assertEqual(self.engine._candidates[0].phrase, 'ai')
        self.assertEqual(self.engine._typed_string, ['a', 'i'])
        self.assertEqual(self.engine.mock_preedit_text, 'ai')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_4, 0, 0)
        self.assertEqual(len(self.engine._candidates), 53)
        self.assertEqual(self.engine._candidates[0].phrase, '爱')
        self.assertEqual(self.engine._candidates[1].phrase, '愛')
        self.assertEqual(self.engine._typed_string, ['a', 'i', '4'])
        self.assertEqual(self.engine.mock_preedit_text, '爱')
        self.assertEqual(self.engine.mock_committed_text, '')
        # Select second candiate with Tab
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.assertEqual(len(self.engine._candidates), 53)
        self.assertEqual(self.engine._candidates[0].phrase, '爱')
        self.assertEqual(self.engine._candidates[1].phrase, '愛')
        self.assertEqual(self.engine._typed_string, ['a', 'i', '4'])
        self.assertEqual(self.engine.mock_preedit_text, '爱') # Unchanged!
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(len(self.engine._candidates), 1)
        self.assertEqual(self.engine._candidates[0].phrase, 'a')
        self.assertEqual(self.engine._typed_string, ['愛', 'a'])
        self.assertEqual(self.engine.mock_preedit_text, '愛a')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_4, 0, 0)
        self.assertEqual(len(self.engine._candidates), 53)
        self.assertEqual(self.engine._candidates[0].phrase, '爱')
        self.assertEqual(self.engine._candidates[1].phrase, '愛')
        self.assertEqual(self.engine._typed_string, ['愛', 'a', 'i', '4'])
        self.assertEqual(self.engine.mock_preedit_text, '愛爱')
        self.assertEqual(self.engine.mock_committed_text, '')
        # commit “to preedit” with space:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(len(self.engine._candidates), 0)
        self.assertEqual(self.engine._typed_string, ['愛', '爱'])
        self.assertEqual(self.engine.mock_preedit_text, '愛爱')
        self.assertEqual(self.engine.mock_committed_text, '')
        # “really” commit with a second space:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(len(self.engine._candidates), 0)
        self.assertEqual(self.engine._typed_string, [])
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '愛爱')

    def test_zh_cangjie(self) -> None:
        _dummy_trans = self.get_transliterator_or_skip('zh-cangjie')
        self.engine.set_current_imes(
            ['zh-cangjie', 'NoIME'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(len(self.engine._candidates), 2)
        self.assertEqual(self.engine._candidates[0].phrase, '日')
        self.assertEqual(self.engine._candidates[1].phrase, '曰')
        self.assertEqual(self.engine._typed_string, ['a'])
        self.assertEqual(self.engine.mock_preedit_text, '日')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(len(self.engine._candidates), 2)
        self.assertEqual(self.engine._candidates[0].phrase, '昌')
        self.assertEqual(self.engine._candidates[1].phrase, '昍')
        self.assertEqual(self.engine._typed_string, ['a', 'a'])
        self.assertEqual(self.engine.mock_preedit_text, '昌')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.assertEqual(len(self.engine._candidates), 2)
        self.assertEqual(self.engine._candidates[0].phrase, '昌')
        self.assertEqual(self.engine._candidates[1].phrase, '昍')
        self.assertEqual(self.engine._typed_string, ['a', 'a'])
        self.assertEqual(self.engine.mock_preedit_text, '昌')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(len(self.engine._candidates), 2)
        self.assertEqual(self.engine._candidates[0].phrase, '日')
        self.assertEqual(self.engine._candidates[1].phrase, '曰')
        self.assertEqual(self.engine._typed_string, ['昍', 'a'])
        self.assertEqual(self.engine.mock_preedit_text, '昍日')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(len(self.engine._candidates), 2)
        self.assertEqual(self.engine._candidates[0].phrase, '昌')
        self.assertEqual(self.engine._candidates[1].phrase, '昍')
        self.assertEqual(self.engine._typed_string, ['昍', 'a', 'a'])
        self.assertEqual(self.engine.mock_preedit_text, '昍昌')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(len(self.engine._candidates), 1)
        self.assertEqual(self.engine._candidates[0].phrase, '晶')
        self.assertEqual(self.engine._typed_string, ['昍', 'a', 'a', 'a'])
        self.assertEqual(self.engine.mock_preedit_text, '昍晶')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(len(self.engine._candidates), 2)
        self.assertEqual(self.engine._candidates[0].phrase, '𣊫')
        self.assertEqual(self.engine._candidates[1].phrase, '𣊭')
        self.assertEqual(self.engine._typed_string, ['昍', 'a', 'a', 'a', 'a'])
        self.assertEqual(self.engine.mock_preedit_text, '昍𣊫')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual(len(self.engine._candidates), 1)
        self.assertEqual(self.engine._candidates[0].phrase, '晶')
        self.assertEqual(self.engine._typed_string, ['昍', 'a', 'a', 'a'])
        self.assertEqual(self.engine.mock_preedit_text, '昍晶')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(len(self.engine._candidates), 2)
        self.assertEqual(self.engine._candidates[0].phrase, '𣊫')
        self.assertEqual(self.engine._candidates[1].phrase, '𣊭')
        self.assertEqual(self.engine._typed_string, ['昍', 'a', 'a', 'a', 'a'])
        self.assertEqual(self.engine.mock_preedit_text, '昍𣊫')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_Tab, 0, 0)
        self.assertEqual(len(self.engine._candidates), 2)
        self.assertEqual(self.engine._candidates[0].phrase, '𣊫')
        self.assertEqual(self.engine._candidates[1].phrase, '𣊭')
        self.assertEqual(self.engine._typed_string, ['昍', 'a', 'a', 'a', 'a'])
        self.assertEqual(self.engine.mock_preedit_text, '昍𣊫')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.assertEqual(len(self.engine._candidates), 2)
        self.assertEqual(self.engine._candidates[0].phrase, '日')
        self.assertEqual(self.engine._candidates[1].phrase, '曰')
        self.assertEqual(self.engine._typed_string, ['昍', '𣊭', 'a'])
        self.assertEqual(self.engine.mock_preedit_text, '昍𣊭日')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_F2, 0, 0)
        self.assertEqual(len(self.engine._candidates), 0)
        self.assertEqual(self.engine._typed_string, ['昍', '𣊭', '曰'])
        self.assertEqual(self.engine.mock_preedit_text, '昍𣊭曰')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(len(self.engine._candidates), 0)
        self.assertEqual(self.engine._typed_string, [])
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '昍𣊭曰')

    @unittest.skipUnless(
        IMPORT_DISTRO_SUCCESSFUL
        and distro.id() == 'fedora'
        and distro.version() >= '34',
        'Skipping, initializing ja-anthy sometimes segfaults on Alpine Linux. '
        'Although using ja-anthy on Alpine Linux seems to work fine, only adding '
        'ja-anthy and removing it again several times seems to cause crashes on '
        'Alpine Linux. I have no time to investigate that now and '
        'I think it is good enough to test ja-anthy an Fedora at the moment.')
    def test_ja_anthy_aki_aki_aki_aki_simple(self) -> None:
        _dummy_trans = self.get_transliterator_or_skip('ja-anthy')
        self.engine.set_current_imes(
            ['ja-anthy', 'NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['None'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_k, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(
            self.engine._typed_string,
            ['a', 'k', 'i'])
        self.assertEqual(self.engine.mock_preedit_text, 'あき')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(
            self.engine._typed_string,
            ['a', 'k', 'i', ' ']
            + itb_util.ANTHY_HENKAN_WIDE)
        self.assertEqual(self.engine.mock_preedit_text, '秋')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertTrue(len(self.engine._candidates) > 5)
        self.assertEqual(self.engine._candidates[0].phrase, '秋')
        self.assertEqual(self.engine._candidates[1].phrase, '空き')
        # Commit to preedit with Return
        self.engine.do_process_key_event(IBus.KEY_Return, 0, 0)
        self.assertEqual(self.engine._typed_string, ['秋'])
        self.assertEqual(self.engine.mock_preedit_text, '秋')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_k, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(self.engine._typed_string,
                         ['秋', 'a', 'k', 'i'])
        self.assertEqual(self.engine.mock_preedit_text, '秋あき')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(
            self.engine._typed_string,
            ['秋', 'a', 'k', 'i', ' ']
            + itb_util.ANTHY_HENKAN_WIDE)
        self.assertEqual(self.engine.mock_preedit_text, '秋秋')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertTrue(len(self.engine._candidates) > 5)
        self.assertEqual(self.engine._candidates[0].phrase, '秋')
        self.assertEqual(self.engine._candidates[1].phrase, '空き')
        # No commit, continue typing
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_k, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(self.engine._typed_string,
                         ['秋', 'a', 'k', 'i', ' ',  'a', 'k', 'i'])
        self.assertEqual(self.engine.mock_preedit_text, '秋秋あき')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(
            self.engine._typed_string,
            ['秋', 'a', 'k', 'i', ' ',  'a', 'k', 'i', ' ']
            + itb_util.ANTHY_HENKAN_WIDE)
        self.assertEqual(self.engine.mock_preedit_text, '秋秋秋')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertTrue(len(self.engine._candidates) > 5)
        self.assertEqual(self.engine._candidates[0].phrase, '秋')
        self.assertEqual(self.engine._candidates[1].phrase, '空き')
        # Select second candidate manually:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '秋秋秋') # unchanged!
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertTrue(len(self.engine._candidates) > 5)
        self.assertEqual(self.engine._candidates[0].phrase, '秋')
        self.assertEqual(self.engine._candidates[1].phrase, '空き')
        # Continue typing
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_k, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.assertEqual(
            self.engine._typed_string,
            ['秋', 'a', 'k', 'i', ' ',  '空',  'き', 'a', 'k', 'i'])
        self.assertEqual(self.engine.mock_preedit_text, '秋秋空きあき')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(
            self.engine._typed_string,
            ['秋', 'a', 'k', 'i', ' ',  '空',  'き', 'a', 'k', 'i', ' ']
            + itb_util.ANTHY_HENKAN_WIDE)
        self.assertEqual(self.engine.mock_preedit_text, '秋秋空き秋')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertTrue(len(self.engine._candidates) > 5)
        self.assertEqual(self.engine._candidates[0].phrase, '秋')
        self.assertEqual(self.engine._candidates[1].phrase, '空き')
        # Commit to Preedit with Return:
        self.engine.do_process_key_event(IBus.KEY_Return, 0, 0)
        self.assertEqual(
            self.engine._typed_string,
            ['秋', 'a', 'k', 'i', ' ',  '空',  'き', '秋'])
        self.assertEqual(self.engine.mock_preedit_text, '秋秋空き秋')
        self.assertEqual(self.engine.mock_committed_text, '')
        # Really commit with a second Return:
        self.engine.do_process_key_event(IBus.KEY_Return, 0, 0)
        self.assertEqual(self.engine._typed_string, [])
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '秋秋空き秋')
        # Third Return adds a new line:
        self.engine.do_process_key_event(IBus.KEY_Return, 0, 0)
        self.assertEqual(self.engine._typed_string, [])
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '秋秋空き秋\r')

    @unittest.skipUnless(
        IMPORT_DISTRO_SUCCESSFUL
        and distro.id() == 'fedora'
        and distro.version() >= '34',
        'Skipping, initializing ja-anthy sometimes segfaults on Alpine Linux. '
        'Although using ja-anthy on Alpine Linux seems to work fine, only adding '
        'ja-anthy and removing it again several times seems to cause crashes on '
        'Alpine Linux. I have no time to investigate that now and '
        'I think it is good enough to test ja-anthy an Fedora at the moment.')
    def test_ja_anthy_wide_henkan_region(self) -> None:
        '''When typing すいみんぶそく and then space for henkan,
        in ibus-anthy, ibus-kkc, ibus-m17n with the henkan region is
        shorter than the whole input, usually one gets
        睡眠不足 in the preedit with the henkan region only
        covering 睡眠.

        With these input methods, it is no problem that the henkan
        region does not cover everything as the henkan region can be
        moved, widened, and narrowed.

        But in Typing Booster, I was not yet able to widen, and narrow
        the henkan region reliably.

        Maybe I’ll try again later, maybe it’s possible to do better.

        But for the moment, I make the henkan region always maximal
        immediately at henkan. I.e. if typing すいみんぶそく and then
        henkan, the henkan region is maximally widened to cover all of
        睡眠不足.

        This is not optimal but better than having a henkan region
        with an unpredictable width and position (unpredictable
        because it seems to depend on previous usage of the anthy
        library). If the henkan region is not where one wants it
        and cannot be changed, that is really bad. So it is better
        to make the henkan region cover everything, that gives
        predictable results at least.

        If one wants a shorter henkan region, the only way in Typing
        Booster is to do henkan on shorter kana input.

        '''
        _dummy_trans = self.get_transliterator_or_skip('ja-anthy')
        self.engine.set_current_imes(
            ['ja-anthy', 'NoIME'], update_gsettings=False)
        self.engine.set_dictionary_names(
            ['None'], update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_i, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_n, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_b, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_s, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_o, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_k, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.assertEqual(
            self.engine._typed_string,
            ['s', 'u', 'i', 'm', 'i', 'n', 'b', 'u', 's', 'o', 'k', 'u'])
        self.assertEqual(self.engine.mock_preedit_text, 'すいみんぶそく')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(
            self.engine._typed_string,
            ['s', 'u', 'i', 'm', 'i', 'n', 'b', 'u', 's', 'o', 'k', 'u', ' ']
            + itb_util.ANTHY_HENKAN_WIDE)
        # When doing henkan on such a wide input, there are not many
        # choices:
        self.assertEqual(len(self.engine._candidates), 3)
        self.assertEqual(self.engine._candidates[0].phrase, '睡眠不足')
        self.assertEqual(self.engine._candidates[1].phrase, 'すいみんぶそく')
        self.assertEqual(self.engine._candidates[2].phrase, 'スイミンブソク')
        self.engine.do_process_key_event(IBus.KEY_Return, 0, 0)
        self.assertEqual(len(self.engine._candidates), 0)
        self.assertEqual(self.engine.mock_preedit_text, '睡眠不足')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.assertEqual(
            self.engine._typed_string,
            ['睡', '眠', '不', '足'])
        self.engine.do_process_key_event(IBus.KEY_Return, 0, 0)
        self.assertEqual(len(self.engine._candidates), 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, '睡眠不足')
        self.assertEqual(
            self.engine._typed_string,
            [])

    def test_temporary_emoji_predictions(self) -> None:
        self.engine.set_emoji_prediction_mode(False, update_gsettings=False)
        self.engine.set_word_prediction_mode(False, update_gsettings=False)
        self.engine.set_dictionary_names(['en_US'], update_gsettings=False)
        self.engine.set_keybindings({
            'commit_candidate_1': ['F1'],
            'trigger_emoji_predictions': ['F13'],
        }, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_F13, 0, 0)
        for char in 'dromedary':
            self.engine.do_process_key_event(getattr(IBus, f'KEY_{char}'), 0, 0)
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, '🐪')
        self.assertFalse(self.engine._temporary_emoji_predictions)

    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_temporary_word_predictions(self) -> None:
        self.engine.set_emoji_prediction_mode(False, update_gsettings=False)
        self.engine.set_word_prediction_mode(False, update_gsettings=False)
        self.engine.set_dictionary_names(['en_US'], update_gsettings=False)
        self.engine.set_keybindings({
            'commit_candidate_1': ['F1'],
            'trigger_word_predictions': ['F13'],
        }, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_F13, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_k, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_m, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_q, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_u, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_a, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_F1, 0, 0)
        self.assertEqual(self.engine.mock_committed_text, 'kumquat')
        self.assertFalse(self.engine._temporary_word_predictions)

    def test_cancel_temporary_predictions(self) -> None:
        self.engine.set_emoji_prediction_mode(False, update_gsettings=False)
        self.engine.set_word_prediction_mode(False, update_gsettings=False)
        self.engine.set_keybindings({
            'cancel': ['Escape'],
            'trigger_emoji_predictions': ['F13'],
            'trigger_word_predictions': ['F14'],
        }, update_gsettings=False)
        self.engine.do_process_key_event(IBus.KEY_F13, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_F14, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        self.assertFalse(self.engine._temporary_emoji_predictions)
        self.assertFalse(self.engine._temporary_word_predictions)

    def test_issue_712_mim(self) -> None:
        ''' https://github.com/mike-fabian/ibus-typing-booster/issues/712 '''
        _dummy_trans = self.get_transliterator_or_skip('t-test-issue-712')
        self.engine.set_current_imes(
            ['t-test-issue-712'], update_gsettings=False)
        # C-x has a transliteration:
        self.engine.do_process_key_event(
            IBus.KEY_x, 0, IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'control-x')
        self.assertEqual(self.engine.mock_committed_text, '')
        # C-c has no transliteration and triggers a commit:
        self.engine.do_process_key_event(
            IBus.KEY_c, 0, IBus.ModifierType.CONTROL_MASK)
        # If doing this in a “real” program, usually no 'c' will
        # appear in the text of the application because the Control-c
        # is interpreted as a keyboard shortcut. But here in the test
        # we get a 'c' committed (with the control bit in the “states”
        # list).
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'control-xc')
        self.assertEqual(self.engine.mock_committed_text_states[-1],
                         IBus.ModifierType.CONTROL_MASK)
        # A-x has a transliteration:
        self.engine.do_process_key_event(
            IBus.KEY_x, 0, IBus.ModifierType.MOD1_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'alt-x')
        self.assertEqual(self.engine.mock_committed_text, 'control-xc')
        # A-c has no transliteration and triggers a commit:
        self.engine.do_process_key_event(
            IBus.KEY_c, 0, IBus.ModifierType.MOD1_MASK)
        # If doing this in a “real” program, usually no 'c' will
        # appear in the text of the application because the Alt-c is
        # interpreted as a keyboard shortcut. But here in the test we
        # get a 'c' committed (with the MOD1 bit in the “states”
        # list).
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'control-xcalt-xc')
        self.assertEqual(self.engine.mock_committed_text_states[-1],
                         IBus.ModifierType.MOD1_MASK)
        # s-x has a transliteration:
        self.engine.do_process_key_event(
            IBus.KEY_x, 0,
            IBus.ModifierType.SUPER_MASK
            | IBus.ModifierType.MOD4_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'super-x')
        self.assertEqual(self.engine.mock_committed_text, 'control-xcalt-xc')
        # s-e has a transliteration:
        self.engine.do_process_key_event(
            IBus.KEY_e, 0,
            IBus.ModifierType.SUPER_MASK
            | IBus.ModifierType.MOD4_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'super-xsuper-e')
        self.assertEqual(self.engine.mock_committed_text, 'control-xcalt-xc')
        # s-c has no transliteration and triggers a commit:
        self.engine.do_process_key_event(
            IBus.KEY_c, 0,
            IBus.ModifierType.SUPER_MASK
            | IBus.ModifierType.MOD4_MASK)
        # If doing this in a “real” program, usually a 'c' will
        # appear in the text of the application as well.
        # At least when typing into gedit in a Gnome Wayland session
        # on Fedora 42, typing `Super+c` will insert a 'c' into gedit.
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'control-xcalt-xcsuper-xsuper-ec')
        self.assertEqual(self.engine.mock_committed_text_states[-1],
            IBus.ModifierType.SUPER_MASK
            | IBus.ModifierType.MOD4_MASK)
        # ((S-C-A-G-s-F12) "😭")
        self.engine.do_process_key_event(
            IBus.KEY_F12, 0,
            IBus.ModifierType.SHIFT_MASK
            | IBus.ModifierType.CONTROL_MASK
            | IBus.ModifierType.MOD1_MASK
            | IBus.ModifierType.MOD5_MASK
            | IBus.ModifierType.MOD4_MASK
            | IBus.ModifierType.SUPER_MASK)
        self.assertEqual(self.engine.mock_preedit_text, '😭')
        self.assertEqual(self.engine.mock_committed_text,
                         'control-xcalt-xcsuper-xsuper-ec')
        # S-C-A-G-s-F13 is not transliterated and triggers a commit:
        self.engine.do_process_key_event(
            IBus.KEY_F13, 0,
            IBus.ModifierType.SHIFT_MASK
            | IBus.ModifierType.CONTROL_MASK
            | IBus.ModifierType.MOD1_MASK
            | IBus.ModifierType.MOD5_MASK
            | IBus.ModifierType.MOD4_MASK
            | IBus.ModifierType.SUPER_MASK)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text,
                         'control-xcalt-xcsuper-xsuper-ec😭')

    def test_issue_707_mim(self) -> None:
        ''' https://github.com/mike-fabian/ibus-typing-booster/issues/707 '''
        _dummy_trans = self.get_transliterator_or_skip('t-test-issue-707')
        self.engine.set_current_imes(
            ['t-test-issue-707'], update_gsettings=False)
        self.engine.do_process_key_event(
            IBus.KEY_u, 0, IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'prompt:')
        self.assertEqual(self.engine.mock_committed_text, '')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, ' ')
        self.engine.do_process_key_event(
            IBus.KEY_u, 0, IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'prompt:')
        self.assertEqual(self.engine.mock_committed_text, ' ')
        for char in 'foo':
            self.engine.do_process_key_event(getattr(IBus, f'KEY_{char}'), 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'bar')
        self.assertEqual(self.engine.mock_committed_text, ' ')
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, ' bar ')

    def test_issue_704_mim(self) -> None:
        ''' https://github.com/mike-fabian/ibus-typing-booster/issues/704 '''
        _dummy_trans = self.get_transliterator_or_skip('t-test-issue-704')
        self.engine.set_current_imes(
            ['t-test-issue-704'], update_gsettings=False)
        self.engine.do_process_key_event(
            IBus.KEY_Escape, 0, IBus.ModifierType.CONTROL_MASK)
        self.assertEqual(self.engine.mock_preedit_text, 'foo')
        self.assertEqual(self.engine.mock_committed_text, '')
        # This Escape clears the existing preedit:
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        self.engine.do_process_key_event(IBus.KEY_Escape, 0, 0)
        # Now that the preedit is empty, the Escape key is handled as
        # input as t-test-issue-704 transliterates it to 'Escape\n':
        self.assertEqual(self.engine.mock_preedit_text, 'Escape\n')
        self.assertEqual(self.engine.mock_committed_text, '')
        for char in 'foo':
            self.engine.do_process_key_event(getattr(IBus, f'KEY_{char}'), 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'Escape\nbar')
        self.assertEqual(self.engine.mock_committed_text, '')
        # There 'space' still commits:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'Escape\nbar ')
        # 'BackSpace' is transliterated by t-test-issue-704:
        self.engine.do_process_key_event(IBus.KEY_BackSpace, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, 'BackSpace\n')
        self.assertEqual(self.engine.mock_committed_text, 'Escape\nbar ')
        # And 'space' still commits:
        self.engine.do_process_key_event(IBus.KEY_space, 0, 0)
        self.assertEqual(self.engine.mock_preedit_text, '')
        self.assertEqual(self.engine.mock_committed_text, 'Escape\nbar BackSpace\n ')

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    # Activate this to see a lot of logging when running the tests
    # manually:
    # LOGGER.addHandler(LOG_HANDLER)
    unittest.main()
