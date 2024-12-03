# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2012-2013 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012-2018 Mike FABIAN <mfabian@redhat.com>
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
The setup tool for ibus typing booster.
'''

from typing import Tuple
from typing import List
from typing import Dict
from typing import Union
from typing import Any
import sys
import os
import html
import signal
import argparse
import locale
import copy
import logging
import logging.handlers
from time import strftime
import dbus # type: ignore
import dbus.service # type: ignore

# pylint: disable=wrong-import-position
from gi import require_version # type: ignore
require_version('Gio', '2.0')
from gi.repository import Gio # type: ignore
require_version('GLib', '2.0')
from gi.repository import GLib

# set_prgname before importing other modules to show the name in warning
# messages when import modules are failed. E.g. Gtk.
GLib.set_application_name('Typing Booster Preferences')
# This makes gnome-shell load the .desktop file when running under Wayland:
GLib.set_prgname('ibus-setup-typing-booster')

require_version('Gdk', '3.0')
from gi.repository import Gdk
require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf
require_version('Gtk', '3.0')
from gi.repository import Gtk
require_version('Pango', '1.0')
from gi.repository import Pango
require_version('IBus', '1.0')
from gi.repository import IBus
# pylint: enable=wrong-import-position

IMPORT_LIBVOIKKO_SUCCESSFUL = False
try:
    # pylint: disable=unused-import
    import libvoikko # type: ignore
    # pylint: enable=unused-import
    IMPORT_LIBVOIKKO_SUCCESSFUL = True
except (ImportError,):
    pass

# pylint: disable=import-error
sys.path = [sys.path[0]+'/../engine'] + sys.path
import m17n_translit
import tabsqlitedb
import itb_util
import itb_sound
import itb_emoji
import itb_version
# pylint: enable=import-error

from pkginstall import InstallPackages
from i18n import _, init as i18n_init

LOGGER = logging.getLogger('ibus-typing-booster')

GTK_VERSION = (Gtk.get_major_version(),
               Gtk.get_minor_version(),
               Gtk.get_micro_version())

M17N_DB_INFO = None

def parse_args() -> Any:
    '''
    Parse the command line arguments.
    '''
    parser = argparse.ArgumentParser(
        description='ibus-typing-booster setup tool')
    parser.add_argument(
        '-n', '--engine-name',
        action='store',
        type=str,
        dest='engine_name',
        default='typing-booster',
        help=('Set the name of the engine, for example “typing-booster” '
              'for the regular multilingual typing booster or '
              '“tb:<language>:<name>” for special typing booster '
              'engines defaulting to emulating ibus-m17n a specific '
              'm17n input method. For example “tb:hi:itrans” would be '
              'a special typing-booster engine emulating “m17n:hi:itrans”.'))
    parser.add_argument(
        '-q', '--no-debug',
        action='store_true',
        default=False,
        help=('Do not write log file '
              '~/.local/share/ibus-typing-booster/setup-debug.log, '
              'default: %(default)s'))
    engine_name = parser.parse_args().engine_name
    if (engine_name != 'typing-booster'
        and not itb_util.M17N_ENGINE_NAME_PATTERN.search(engine_name)):
        print('Invalid engine name.\n')
        parser.print_help()
        sys.exit(1)
    return parser.parse_args()

_ARGS = parse_args()

class SetupUI(Gtk.Window): # type: ignore
    '''
    User interface of the setup tool
    '''
    def __init__( # pylint: disable=too-many-statements
            self, engine_name: str = 'typing-booster') -> None:
        self._engine_name = engine_name
        if not self._engine_name:
            self._engine_name = 'typing-booster'
        title = '🚀 ' + _('Preferences for ibus-typing-booster')
        user_db_file = 'user.db'
        schema_path = '/org/freedesktop/ibus/engine/typing-booster/'
        self._m17n_ime_lang = ''
        self._m17n_ime_name = ''
        if self._engine_name != 'typing-booster':
            title = '🚀 ' + self._engine_name + ' ' + _('Preferences')
            match = itb_util.M17N_ENGINE_NAME_PATTERN.search(self._engine_name)
            if not match:
                raise ValueError('Invalid engine name.')
            self._m17n_ime_lang = match.group('lang')
            self._m17n_ime_name = match.group('name')
            user_db_file = (
                f'user-{self._m17n_ime_lang}-{self._m17n_ime_name}.db')
            schema_path = ('/org/freedesktop/ibus/engine/tb/'
                           f'{self._m17n_ime_lang}/{self._m17n_ime_name}/')

        Gtk.Window.__init__(self, title=title)
        self.set_title(title)
        self.set_name('TypingBoosterPreferences')
        self.set_modal(True)
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(
            b'''
            #TypingBoosterPreferences {
            }
            row { /* This is for listbox rows */
                border-style: groove;
                border-width: 0.05px;
            }
            ''')
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.tabsqlitedb = tabsqlitedb.TabSqliteDb(user_db_file=user_db_file)

        self._gsettings = Gio.Settings(
            schema='org.freedesktop.ibus.engine.typing-booster',
            path=schema_path)
        self._settings_dict = self._init_settings_dict()

        self._allowed_autosettings: Dict[str, Dict[str, str]] = {}
        schema_source: Gio.SettingsSchemaSource = (
            Gio.SettingsSchemaSource.get_default())
        schema: Gio.SettingsSchema = schema_source.lookup(
            'org.freedesktop.ibus.engine.typing-booster', True)
        for key in schema.list_keys():
            value_type = schema.get_key(key).get_value_type().dup_string()
            if key in ('dictionaryinstalltimestamp',
                       'inputmethodchangetimestamp'):
                continue
            if value_type in ('i', 'u', 'x', 't'):
                # int32, uint32, int64, uint64
                value_hint = 'int'
            elif value_type == 'd':
                value_hint = 'float'
            elif value_type == 'b':
                value_hint = 'bool'
            elif value_type == 's':
                value_hint = 'str'
            else:
                continue
            self._allowed_autosettings[key] = {
                'value_type': value_type, 'value_hint': value_hint}

        self.connect('destroy-event', self._on_destroy_event)
        self.connect('delete-event', self._on_delete_event)

        self._main_container = Gtk.Box()
        self._main_container.set_orientation(Gtk.Orientation.VERTICAL)
        self._main_container.set_spacing(0)
        self.add(self._main_container) # pylint: disable=no-member
        self._notebook = Gtk.Notebook()
        self._notebook.set_visible(True)
        self._notebook.set_can_focus(False)
        self._notebook.set_scrollable(True)
        self._notebook.set_hexpand(True)
        self._notebook.set_vexpand(True)
        self._main_container.add(self._notebook)
        self._dialog_action_area = Gtk.Box()
        self._dialog_action_area.set_orientation(Gtk.Orientation.HORIZONTAL)
        self._dialog_action_area.set_visible(True)
        self._dialog_action_area.set_can_focus(False)
        self._dialog_action_area.set_hexpand(True)
        self._dialog_action_area.set_vexpand(False)
        self._main_container.add(self._dialog_action_area)
        self._about_button = Gtk.Button(label=_('About'))
        self._about_button.connect('clicked', self._on_about_button_clicked)
        self._dialog_action_area.add(self._about_button)
        empty_hexpanding_label = Gtk.Label()
        empty_hexpanding_label.set_hexpand(True)
        self._dialog_action_area.add(empty_hexpanding_label)
        self._restore_all_defaults_button = Gtk.Button()
        self._restore_all_defaults_button_label = Gtk.Label()
        self._restore_all_defaults_button_label.set_text(
            _('Restore all defaults'))
        self._restore_all_defaults_button.add(
            self._restore_all_defaults_button_label)
        self._restore_all_defaults_button.connect(
            'clicked', self._on_restore_all_defaults_button_clicked)
        self._dialog_action_area.add(self._restore_all_defaults_button)
        empty_hexpanding_label = Gtk.Label()
        empty_hexpanding_label.set_hexpand(True)
        self._dialog_action_area.add(empty_hexpanding_label)
        self._close_button = Gtk.Button()
        self._close_button_label = Gtk.Label()
        self._close_button_label.set_text_with_mnemonic(_('_Close'))
        self._close_button.add(self._close_button_label)
        self._close_button.connect('clicked', self._on_close_clicked)
        self._dialog_action_area.add(self._close_button)

        grid_border_width = 10
        grid_row_spacing = 1
        grid_column_spacing = 10

        self._dictionaries_and_input_methods_vbox = Gtk.Box()
        self._dictionaries_and_input_methods_vbox.set_orientation(
            Gtk.Orientation.VERTICAL)
        self._dictionaries_and_input_methods_vbox.set_spacing(0)
        margin = 10
        self._dictionaries_and_input_methods_vbox.set_margin_start(margin)
        self._dictionaries_and_input_methods_vbox.set_margin_end(margin)
        self._dictionaries_and_input_methods_vbox.set_margin_top(margin)
        self._dictionaries_and_input_methods_vbox.set_margin_bottom(margin)
        self._dictionaries_and_input_methods_label = Gtk.Label()
        self._dictionaries_and_input_methods_label.set_text(
            # Translators: This is the label of a tab in the setup
            # tool. Here the user can setup the dictionaries for the
            # languages he wants to use and the input methods to use
            # to be able to type all the languages he is interested
            # in.
            _('Dictionaries and input methods'))

        self._options_grid = Gtk.Grid()
        self._options_grid.set_visible(True)
        self._options_grid.set_can_focus(False)
        self._options_grid.set_border_width(grid_border_width)
        self._options_grid.set_row_spacing(grid_row_spacing)
        self._options_grid.set_column_spacing(grid_column_spacing)
        self._options_grid.set_row_homogeneous(False)
        self._options_grid.set_column_homogeneous(False)
        self._options_grid.set_hexpand(True)
        self._options_grid.set_vexpand(False)
        self._options_label = Gtk.Label()
        # Translators: This is the label of a tab in the setup tool.
        # Here the user can set up some options which influence the
        # behaviour of ibus-typing-booster.
        self._options_label.set_text(_('Options'))

        self._custom_shortcuts_grid = Gtk.Grid()
        self._custom_shortcuts_grid.set_visible(True)
        self._custom_shortcuts_grid.set_can_focus(False)
        self._custom_shortcuts_grid.set_border_width(grid_border_width)
        self._custom_shortcuts_grid.set_row_spacing(grid_row_spacing)
        self._custom_shortcuts_grid.set_column_spacing(grid_column_spacing)
        self._custom_shortcuts_grid.set_row_homogeneous(False)
        self._custom_shortcuts_grid.set_column_homogeneous(True)
        self._custom_shortcuts_label = Gtk.Label()
        # Translators: This is a label of a tab in the setup tool.
        # Here the user can create custom shortcuts. For example if
        # the user wants that whenever he types “rotfl” that “rolling
        # on the floor laughing” is shown as a high priority
        # candidate, he can define such a custom shortcut here.
        self._custom_shortcuts_label.set_text(_('Custom shortcuts'))

        self._keybindings_vbox = Gtk.Box()
        self._keybindings_vbox.set_orientation(Gtk.Orientation.VERTICAL)
        self._keybindings_vbox.set_spacing(0)
        margin = 10
        self._keybindings_vbox.set_margin_start(margin)
        self._keybindings_vbox.set_margin_end(margin)
        self._keybindings_vbox.set_margin_top(margin)
        self._keybindings_vbox.set_margin_bottom(margin)
        self._keybindings_label = Gtk.Label()
        # Translators: This is the label of a tab in the setup tool.
        # Here the user can customize the key bindings to execute
        # certain commands of ibus-typing-booster. For example
        # which key to use to request completion, which key to
        # use to move to the next completion candidate etc...
        self._keybindings_label.set_text(_('Key bindings'))

        self._appearance_grid = Gtk.Grid()
        self._appearance_grid.set_visible(True)
        self._appearance_grid.set_can_focus(False)
        self._appearance_grid.set_border_width(grid_border_width)
        self._appearance_grid.set_row_spacing(grid_row_spacing)
        self._appearance_grid.set_column_spacing(grid_column_spacing)
        self._appearance_grid.set_row_homogeneous(False)
        self._appearance_grid.set_column_homogeneous(False)
        self._appearance_grid.set_hexpand(True)
        self._appearance_grid.set_vexpand(False)
        self._appearance_label = Gtk.Label()
        # Translators: This is the label of a tab in the setup tool.
        # Here the user can set up some options which influence how
        # ibus-typing-booster looks like, i.e. something like whether
        # extra info should be shown on top of the candidate list and
        # how many entries one page of the candidate list should have.
        # Also one can choose here which colours to use for different
        # types of candidates (candidates from the user database, from
        # dictionaries, or from spellchecking) and/or whether
        # diffent types of candidates should be marked with labels.
        self._appearance_label.set_text(_('Appearance'))

        self._speech_recognition_grid = Gtk.Grid()
        self._speech_recognition_grid.set_visible(True)
        self._speech_recognition_grid.set_can_focus(False)
        self._speech_recognition_grid.set_border_width(grid_border_width)
        self._speech_recognition_grid.set_row_spacing(grid_row_spacing)
        self._speech_recognition_grid.set_column_spacing(grid_column_spacing)
        self._speech_recognition_grid.set_row_homogeneous(False)
        self._speech_recognition_grid.set_column_homogeneous(False)
        self._speech_recognition_grid.set_hexpand(True)
        self._speech_recognition_grid.set_vexpand(False)
        self._speech_recognition_label = Gtk.Label()
        # Translators: This is the label of a tab in the setup tool.
        # Here the user can set up some options related to speech
        # recognition.
        self._speech_recognition_label.set_text(_('Speech recognition'))

        self._autosettings_vbox = Gtk.Box()
        self._autosettings_vbox.set_orientation(
            Gtk.Orientation.VERTICAL)
        self._autosettings_vbox.set_spacing(0)
        margin = 10
        self._autosettings_vbox.set_margin_start(margin)
        self._autosettings_vbox.set_margin_end(margin)
        self._autosettings_vbox.set_margin_top(margin)
        self._autosettings_vbox.set_margin_bottom(margin)
        self._autosettings_label = Gtk.Label()
        # Translators: This is the label of a tab in the setup tool.
        # Here the user can set up whether some settings should change
        # automatically to specific values depending on which window
        # (or which browser tab) gets the focus.
        self._autosettings_label.set_text(_('Autosettings'))

        self._notebook.append_page(
            self._dictionaries_and_input_methods_vbox,
            self._dictionaries_and_input_methods_label)
        self._notebook.append_page(
            self._options_grid,
            self._options_label)
        self._notebook.append_page(
            self._custom_shortcuts_grid,
            self._custom_shortcuts_label)
        self._notebook.append_page(
            self._keybindings_vbox,
            self._keybindings_label)
        self._notebook.append_page(
            self._appearance_grid,
            self._appearance_label)
        self._notebook.append_page(
            self._speech_recognition_grid,
            self._speech_recognition_label)
        self._notebook.append_page(
            self._autosettings_vbox,
            self._autosettings_label)

        _options_grid_row = -1

        self._tab_enable_checkbutton = Gtk.CheckButton(
            # Translators: If this option is on, suggestions are not
            # shown by default. Typing a key is then necessary to show
            # the list of suggestions. The key to use for this can be
            # changed in the key bindings settings. By default it is
            # the Tab key. After a commit the suggestions are hidden
            # again until the next key bound to this command is typed.
            label=_('Enable suggestions by key (Default is the Tab key)'))
        self._tab_enable_checkbutton.set_tooltip_text(
            _('If this option is on, suggestions are not '
              'shown by default. Typing a key is then '
              'necessary to show the list of suggestions. '
              'The key to use for this can be changed in '
              'the key bindings settings. By default it is '
              'the Tab key. After a commit the suggestions '
              'are hidden again until the next key bound to '
              'this command is typed.'))
        self._tab_enable_checkbutton.connect(
            'clicked', self._on_tab_enable_checkbutton)
        self._tab_enable_checkbutton.set_active(
            self._settings_dict['tabenable']['user'])
        _options_grid_row += 1
        self._options_grid.attach(
            self._tab_enable_checkbutton, 0, _options_grid_row, 2, 1)

        self._inline_completion_label = Gtk.Label()
        self._inline_completion_label.set_text(
            # Translators: Whether the best completion is first shown
            # inline in the preedit instead of showing a full
            # candidate list. The inline candidate can be selected by
            # typing Tab and then committed as usual, for example by
            # typing Space or Control+Space. Typing Tab again moves to
            # the next candidate and opens the full candidate list.
            _('Use inline completion'))
        self._inline_completion_label.set_tooltip_text(
            _('Whether the best completion is first shown inline '
              'in the preedit instead of showing a full candidate '
              'list. The inline candidate can be selected by typing '
              'Tab and then committed as usual, for example by '
              'typing Space or Control+Space. Typing Tab again '
              'moves to the next candidate and opens the full '
              'candidate list.'))
        self._inline_completion_label.set_xalign(0)
        self._inline_completion_combobox = Gtk.ComboBox()
        self._inline_completion_store = Gtk.ListStore(str, int)
        self._inline_completion_store.append(
            [_('No'), 0])
        self._inline_completion_store.append(
            [_('Yes, with fallback to popup'), 1])
        self._inline_completion_store.append(
            [_('Yes, without fallback to popup'), 2])
        self._inline_completion_combobox.set_model(
            self._inline_completion_store)
        renderer_text = Gtk.CellRendererText()
        self._inline_completion_combobox.pack_start(
            renderer_text, True)
        self._inline_completion_combobox.add_attribute(
            renderer_text, "text", 0)
        for i, item in enumerate(self._inline_completion_store):
            if self._settings_dict['inlinecompletion']['user'] == item[1]:
                self._inline_completion_combobox.set_active(i)
        self._inline_completion_combobox.connect(
            'changed', self._on_inline_completion_combobox_changed)
        _options_grid_row += 1
        self._options_grid.attach(
            self._inline_completion_label, 0, _options_grid_row, 1, 1)
        self._options_grid.attach(
            self._inline_completion_combobox, 1, _options_grid_row, 1, 1)

        self._auto_capitalize_checkbutton = Gtk.CheckButton(
            # Translators: Whether to automatically capitalize after
            # punctuation.
            label=_('Auto capitalize'))
        self._auto_capitalize_checkbutton.set_tooltip_text(
            _('Automatically capitalize after punctuation.'))
        self._auto_capitalize_checkbutton.connect(
            'clicked', self._on_auto_capitalize_checkbutton)
        self._auto_capitalize_checkbutton.set_active(
            self._settings_dict['autocapitalize']['user'])
        _options_grid_row += 1
        self._options_grid.attach(
            self._auto_capitalize_checkbutton, 0, _options_grid_row, 2, 1)

        self._auto_select_candidate_label = Gtk.Label()
        self._auto_select_candidate_label.set_text(
            # Translators: What you type will automatically be
            # corrected to the best candidate by selecting the best
            # candidate automatically. If this option is off you have
            # to select a candidate manually by using the key binding
            # to select the next candidate. If this option is on and
            # you do not want to use the automatically selected
            # candidate, you can use the key binding for the “cancel”
            # command which will deselect all candidates.
            _('Automatically select the best candidate'))
        self._auto_select_candidate_label.set_tooltip_text(
            _('What you type will automatically be corrected to the best '
              'candidate by selecting the best candidate automatically. If '
              'this option is off you have to select a candidate manually '
              'by using the key binding to select the next candidate. '
              'If this option is on and you do not want to use the '
              'automatically selected candidate, you can use the key binding '
              'for the “cancel” command which will deselect all '
              'candidates.'))
        self._auto_select_candidate_label.set_xalign(0)
        self._auto_select_candidate_combobox = Gtk.ComboBox()
        self._auto_select_candidate_store = Gtk.ListStore(str, int)
        self._auto_select_candidate_store.append(
            [_('No'), 0])
        self._auto_select_candidate_store.append(
            [_('Yes, but only when extremely likely'), 1])
        self._auto_select_candidate_store.append(
            [_('Yes, always'), 2])
        self._auto_select_candidate_combobox.set_model(
            self._auto_select_candidate_store)
        renderer_text = Gtk.CellRendererText()
        self._auto_select_candidate_combobox.pack_start(
            renderer_text, True)
        self._auto_select_candidate_combobox.add_attribute(
            renderer_text, "text", 0)
        for i, item in enumerate(self._auto_select_candidate_store):
            if self._settings_dict['autoselectcandidate']['user'] == item[1]:
                self._auto_select_candidate_combobox.set_active(i)
        self._auto_select_candidate_combobox.connect(
            'changed', self._on_auto_select_candidate_combobox_changed)
        _options_grid_row += 1
        self._options_grid.attach(
            self._auto_select_candidate_label, 0, _options_grid_row, 1, 1)
        self._options_grid.attach(
            self._auto_select_candidate_combobox, 1, _options_grid_row, 1, 1)

        self._add_space_on_commit_checkbutton = Gtk.CheckButton(
            # Translators: Add a space if a candidate from the
            # candidate list is committed by clicking it
            # with the mouse.
            label=_('Add a space when committing by mouse click'))
        self._add_space_on_commit_checkbutton.set_tooltip_text(
            _('Add a space if a candidate from the candidate '
              'list is committed by clicking it '
              'with the mouse.'))
        self._add_space_on_commit_checkbutton.connect(
            'clicked', self._on_add_space_on_commit_checkbutton)
        self._add_space_on_commit_checkbutton.set_active(
            self._settings_dict['addspaceoncommit']['user'])
        _options_grid_row += 1
        self._options_grid.attach(
            self._add_space_on_commit_checkbutton, 0, _options_grid_row, 2, 1)

        self._remember_last_used_preedit_ime_checkbutton = Gtk.CheckButton(
            # Translators: If more then one input method is used at
            # the same time, one of them is used for the preedit.
            # Which input method is used for the preedit can be
            # changed via the menu or via shortcut keys. If this
            # option is enabled, such a change is remembered even if
            # the session is restarted.
            label=_('Remember last used preedit input method'))
        self._remember_last_used_preedit_ime_checkbutton.set_tooltip_text(
            _('If more then one input method is used at the same '
              'time, one of them is used for the preedit. '
              'Which input method is used for the preedit can '
              'be changed via the menu or via shortcut keys. '
              'If this option is enabled, such a change is '
              'remembered even if the session is restarted.'))
        self._remember_last_used_preedit_ime_checkbutton.connect(
            'clicked', self._on_remember_last_used_preedit_ime_checkbutton)
        self._remember_last_used_preedit_ime_checkbutton.set_active(
            self._settings_dict['rememberlastusedpreeditime']['user'])
        _options_grid_row += 1
        self._options_grid.attach(
            self._remember_last_used_preedit_ime_checkbutton,
            0, _options_grid_row, 2, 1)

        self._remember_input_mode_checkbutton = Gtk.CheckButton(
            # Translators: If more then one input method is used at
            # the same time, one of them is used for the preedit.
            # Which input method is used for the preedit can be
            # changed via the menu or via shortcut keys. If this
            # option is enabled, such a change is remembered even if
            # the session is restarted.
            label=_('Remember input mode'))
        self._remember_input_mode_checkbutton.set_tooltip_text(
            _('If this option is enabled, the last used input mode (on/off) '
              'is remembered even if the session is restarted.'))
        self._remember_input_mode_checkbutton.connect(
            'clicked', self._on_remember_input_mode_checkbutton)
        self._remember_input_mode_checkbutton.set_active(
            self._settings_dict['rememberinputmode']['user'])
        _options_grid_row += 1
        self._options_grid.attach(
            self._remember_input_mode_checkbutton,
            0, _options_grid_row, 2, 1)

        self._emoji_predictions_checkbutton = Gtk.CheckButton(
            # Translators: Whether Unicode symbols and emoji should be
            # included in the predictions. Emoji are pictographs like
            # ☺♨⛵…. Unicode symbols are other symbols like
            # mathematical symbols (∀∑∯…), arrows (←↑↔…), currency
            # symbols (€₹₺…), braille patterns (⠥⠩…), and many other
            # symbols. These are technically not emoji but
            # nevertheless useful symbols.
            label=_('Unicode symbols and emoji predictions'))
        self._emoji_predictions_checkbutton.set_tooltip_text(
            _('Whether Unicode symbols and emoji should be '
              'included in the predictions. Emoji are pictographs '
              'like ☺♨⛵…. Unicode symbols are other symbols like '
              'mathematical symbols (∀∑∯…), arrows (←↑↔…), currency '
              'symbols (€₹₺…), braille patterns (⠥⠩…), and many '
              'other symbols. These are technically not emoji but '
              'nevertheless useful symbols.'))
        self._emoji_predictions_checkbutton.connect(
            'clicked', self._on_emoji_predictions_checkbutton)
        self._emoji_predictions_checkbutton.set_active(
            self._settings_dict['emojipredictions']['user'])
        _options_grid_row += 1
        self._options_grid.attach(
            self._emoji_predictions_checkbutton, 0, _options_grid_row, 2, 1)

        self._off_the_record_checkbutton = Gtk.CheckButton(
            # Translators: While “Off the record” mode is on, learning
            # from user input is disabled. If learned user input is
            # available, predictions are usually much better than
            # predictions using only dictionaries. Therefore, one
            # should use this option sparingly. Only if one wants to
            # avoid saving secret user input to disk it might make
            # sense to use this option temporarily.
            label=_('Off the record mode'))
        self._off_the_record_checkbutton.set_tooltip_text(
            _('While “Off the record” mode is on, learning from '
              'user input is disabled. If learned user input is '
              'available, predictions are usually much better '
              'than predictions using only dictionaries. '
              'Therefore, one should use this option sparingly. '
              'Only if one wants to avoid saving secret user '
              'input to disk it might make sense to use this '
              'option temporarily.'))
        self._off_the_record_checkbutton.connect(
            'clicked', self._on_off_the_record_checkbutton)
        self._off_the_record_checkbutton.set_active(
            self._settings_dict['offtherecord']['user'])
        _options_grid_row += 1
        self._options_grid.attach(
            self._off_the_record_checkbutton, 0, _options_grid_row, 2, 1)

        self._record_mode_label = Gtk.Label()
        self._record_mode_label.set_text(
            # Translators: A combo box to select which kind of input
            # should be recorded in the user database.
            _('Record mode'))
        self._record_mode_label.set_tooltip_text(
            _('Selects which kind of input should be recorded in the user '
              'database: “Everything”: Every typed word is added to the user '
              'database or its frequency updated if it is already there. '
              '“Correctly spelled or previously recorded”: A typed word is only '
              'added to the user database if it is likely to be correctly '
              'spelled. If a word is already in the user database its '
              'frequency is updated no matter how it is spelled.  “Correctly '
              'spelled”: A typed word is only added to the database or its '
              'frequency updated in the database if it is likely to be '
              'correctly spelled.  “Nothing”: Do not record any input at all '
              'in the user database.'))
        self._record_mode_label.set_xalign(0)
        self._record_mode_combobox = Gtk.ComboBox()
        self._record_mode_store = Gtk.ListStore(str, int)
        self._record_mode_store.append(
            [_('Everything'), 0])
        self._record_mode_store.append(
            [_('Correctly spelled or previously recorded'), 1])
        self._record_mode_store.append(
            [_('Correctly spelled'), 2])
        self._record_mode_store.append(
            [_('Nothing'), 3])
        self._record_mode_combobox.set_model(
            self._record_mode_store)
        renderer_text = Gtk.CellRendererText()
        self._record_mode_combobox.pack_start(
            renderer_text, True)
        self._record_mode_combobox.add_attribute(
            renderer_text, "text", 0)
        self._record_mode = self._settings_dict['recordmode']['user']
        for i, item in enumerate(self._record_mode_store):
            if self._settings_dict['recordmode']['user'] == item[1]:
                self._record_mode_combobox.set_active(i)
        self._record_mode_combobox.connect(
            'changed', self._on_record_mode_combobox_changed)
        _options_grid_row += 1
        self._options_grid.attach(
            self._record_mode_label, 0, _options_grid_row, 1, 1)
        self._options_grid.attach(
            self._record_mode_combobox, 1, _options_grid_row, 1, 1)

        self._avoid_forward_key_event_checkbutton = Gtk.CheckButton(
            # Translators: Avoid the function forward_key_event() in
            # case it is not implemented or has a broken
            # implementation.  This workaround was necessary for older
            # versions of Qt5 and for Qt4 and some older versions of
            # Wayland.  *But* it causes problems when XIM is
            # used. I.e. the XIM module of Qt4 will not work well when
            # this workaround is enabled and input via XIM into X11
            # programs like xterm will not work well either.  So this
            # option should be used only when absolutely necessary.
            #
            # “forward_key_event()” is the name of a function in the
            # ibus API and should probably not be translated, therefore
            # I didn’t put it into the translatable string but used %s.
            label=_('Avoid using the %s function')
            % 'forward_key_event()') # pylint: disable=consider-using-f-string
        self._avoid_forward_key_event_checkbutton.set_tooltip_text(
            # Translators: Avoid the function forward_key_event() in
            # case it is not implemented or has a broken
            # implementation.  This workaround was necessary for older
            # versions of Qt5 and for Qt4 and some older versions of
            # Wayland.  *But* it causes problems when XIM is
            # used. I.e. the XIM module of Qt4 will not work well when
            # this workaround is enabled and input via XIM into X11
            # programs like xterm will not work well either.  So this
            # option should be used only when absolutely necessary.
            #
            # “forward_key_event()” is the name of a function in the
            # ibus API and should probably not be translated, therefore
            # I didn’t put it into the translatable string but used %s.
            #
            # This is a tooltip shown when the mouse hovers over that
            # option.
            _('Use a workaround if the %s function is broken. '
              'Enable this option only if absolutely necessary, '
              'it can also cause problems, especially when XIM is used.')
            % 'forward_key_event()') # pylint: disable=consider-using-f-string
        self._avoid_forward_key_event_checkbutton.connect(
            'clicked', self._on_avoid_forward_key_event_checkbutton)
        self._avoid_forward_key_event_checkbutton.set_active(
            self._settings_dict['avoidforwardkeyevent']['user'])
        _options_grid_row += 1
        self._options_grid.attach(
            self._avoid_forward_key_event_checkbutton,
            0, _options_grid_row, 2, 1)

        self._arrow_keys_reopen_preedit_checkbutton = Gtk.CheckButton(
            # Translators: Whether it is allowed to reopen a preedit
            # when the cursor reaches a word boundary after moving it.
            # Enabling this option is useful to correct already
            # committed words.
            label=_('Enable reopening preedits'))
        self._arrow_keys_reopen_preedit_checkbutton.set_tooltip_text(
            _('Whether it is allowed to put a word back into a preedit when '
              'the cursor moves to the end or the beginning of a word. '
              'Enabling this option is useful to correct already '
              'committed words.'))
        self._arrow_keys_reopen_preedit_checkbutton.connect(
            'clicked', self._on_arrow_keys_reopen_preedit_checkbutton)
        self._arrow_keys_reopen_preedit_checkbutton.set_active(
            self._settings_dict['arrowkeysreopenpreedit']['user'])
        _options_grid_row += 1
        self._options_grid.attach(
            self._arrow_keys_reopen_preedit_checkbutton,
            0, _options_grid_row, 2, 1)

        self._disable_in_terminals_checkbutton = Gtk.CheckButton(
            # Translators: Whether ibus-typing-booster should be disabled in terminals
            # (gnome-terminal, xfce4-terminal, ...)
            label=_('Disable in terminals'))
        self._disable_in_terminals_checkbutton.set_tooltip_text(
            _('Whether ibus-typing-booster should be disabled in terminals.'))
        self._disable_in_terminals_checkbutton.connect(
            'clicked', self._on_disable_in_terminals_checkbutton)
        self._disable_in_terminals_checkbutton.set_active(
            self._settings_dict['disableinterminals']['user'])
        _options_grid_row += 1
        self._options_grid.attach(
            self._disable_in_terminals_checkbutton,
            0, _options_grid_row, 2, 1)

        self._ascii_digits_checkbutton = Gtk.CheckButton(
            # Translators: Whether language specific digits should be
            # converted to ASCII digits
            label=_('Convert language specific digits to ASCII digits'))
        self._ascii_digits_checkbutton.set_tooltip_text(
            _('Some input methods produce language specific digits by '
              'default. If one never wants to use such language specific '
              'digits but prefers western (ASCII) digits always, one can set '
              'this option to convert language specific digits produced '
              'by input methods always to ASCII digits.'))
        self._ascii_digits_checkbutton.connect(
            'clicked', self._on_ascii_digits_checkbutton)
        self._ascii_digits_checkbutton.set_active(
            self._settings_dict['asciidigits']['user'])
        _options_grid_row += 1
        self._options_grid.attach(
            self._ascii_digits_checkbutton,
            0, _options_grid_row, 2, 1)

        self._emoji_trigger_characters_label = Gtk.Label()
        self._emoji_trigger_characters_label.set_text(
            # Translators: The characters in this list trigger an
            # emoji and Unicode symbol lookup even if the option
            # “Unicode symbols and emoji predictions” is off.
            _('Emoji trigger characters:'))
        self._emoji_trigger_characters_label.set_tooltip_text(
            _('The characters in this list trigger an emoji and Unicode '
              'symbol lookup even if the option '
              '“Unicode symbols and emoji predictions” is off.'))
        self._emoji_trigger_characters_label.set_xalign(0)
        self._emoji_trigger_characters_entry = Gtk.Entry()
        self._emoji_trigger_characters_entry.set_text(
            self._settings_dict['emojitriggercharacters']['user'])
        self._emoji_trigger_characters_entry.connect(
            'notify::text', self._on_emoji_trigger_characters_entry)
        _options_grid_row += 1
        self._options_grid.attach(
            self._emoji_trigger_characters_label, 0, _options_grid_row, 1, 1)
        self._options_grid.attach(
            self._emoji_trigger_characters_entry, 1, _options_grid_row, 1, 1)

        self._auto_commit_characters_label = Gtk.Label()
        self._auto_commit_characters_label.set_text(
            # Translators: The characters in this list cause the
            # preedit to be committed automatically, followed by a
            # space. For example, if “.” is an auto commit character,
            # this saves you typing a space manually after the end of
            # a sentence. You can freely edit this list, a reasonable
            # value might be “.,;:?!)”. You should not add characters
            # to that list which are needed by your input method, for
            # example if you use Latin-Pre (t-latn-pre) it would be a
            # bad idea to add “.” to that list because it would
            # prevent you from typing “.s” to get “ṡ”. You can also
            # disable this feature completely by making the list empty
            # (which is the default).
            _('Auto commit characters:'))
        self._auto_commit_characters_label.set_tooltip_text(
            _('The characters in this list cause the preedit '
              'to be committed automatically, followed by '
              'a space.  For example, if “.” is an auto '
              'commit character, this saves you typing a '
              'space manually after the end of a sentence. '
              'You can freely edit this list, a reasonable '
              'value might be “.,;:?!)”. You should not add '
              'characters to that list which are needed by '
              'your input method, for example if you use '
              'Latin-Pre (t-latn-pre) it would be a bad idea '
              'to add “.” to that list because it would prevent '
              'you from typing “.s” to get “ṡ”. You can also '
              'disable this feature completely by making the '
              'list empty (which is the default).'))
        self._auto_commit_characters_label.set_xalign(0)
        self._auto_commit_characters_entry = Gtk.Entry()
        self._auto_commit_characters_entry.set_text(
            self._settings_dict['autocommitcharacters']['user'])
        self._auto_commit_characters_entry.connect(
            'notify::text', self._on_auto_commit_characters_entry)
        _options_grid_row += 1
        self._options_grid.attach(
            self._auto_commit_characters_label, 0, _options_grid_row, 1, 1)
        self._options_grid.attach(
            self._auto_commit_characters_entry, 1, _options_grid_row, 1, 1)

        self._min_chars_completion_label = Gtk.Label()
        self._min_chars_completion_label.set_text(
            # Translators: Show no suggestions when less than this
            # number of characters have been typed.
            _('Minimum number of chars for completion:'))
        self._min_chars_completion_label.set_tooltip_text(
            _('Show no suggestions when less than this number '
              'of characters have been typed.'))
        self._min_chars_completion_label.set_xalign(0)
        self._min_char_complete_adjustment = Gtk.SpinButton()
        self._min_char_complete_adjustment.set_visible(True)
        self._min_char_complete_adjustment.set_can_focus(True)
        self._min_char_complete_adjustment.set_increments(1.0, 1.0)
        self._min_char_complete_adjustment.set_range(0.0, 9.0)
        if self._settings_dict['mincharcomplete']['user'] is not None:
            self._min_char_complete_adjustment.set_value(
                int(self._settings_dict['mincharcomplete']['user']))
        else:
            self._min_char_complete_adjustment.set_value(1)
        self._min_char_complete_adjustment.connect(
            'value-changed',
            self._on_min_char_complete_adjustment_value_changed)
        _options_grid_row += 1
        self._options_grid.attach(
            self._min_chars_completion_label, 0, _options_grid_row, 1, 1)
        self._options_grid.attach(
            self._min_char_complete_adjustment, 1, _options_grid_row, 1, 1)

        self._error_sound_checkbutton = Gtk.CheckButton(
            # Translators: A checkbox where one can choose whether a
            # sound is played on error
            label=_('Play sound file on error'))
        self._error_sound_checkbutton.set_tooltip_text(
            _('Here you can choose whether a sound file is played '
              'if an error occurs.'))
        self._error_sound_checkbutton.set_hexpand(False)
        self._error_sound_checkbutton.set_vexpand(False)
        self._error_sound_checkbutton.set_active(
            self._settings_dict['errorsound']['user'])
        self._error_sound_checkbutton.connect(
            'clicked', self._on_error_sound_checkbutton)
        self._error_sound_file_button = Gtk.Button()
        self._error_sound_file_button_box = Gtk.Box()
        self._error_sound_file_button_label = Gtk.Label()
        self._error_sound_file_button_label.set_text(
            self._settings_dict['errorsoundfile']['user'])
        self._error_sound_file_button_label.set_use_markup(True)
        self._error_sound_file_button_label.set_max_width_chars(
            40)
        self._error_sound_file_button_label.set_line_wrap(False)
        self._error_sound_file_button_label.set_ellipsize(
            Pango.EllipsizeMode.START)
        self._error_sound_file_button_box.add(
            self._error_sound_file_button_label)
        self._error_sound_file_button.add(self._error_sound_file_button_box)
        self._error_sound_file_button.connect(
            'clicked', self._on_error_sound_file_button)
        _options_grid_row += 1
        self._options_grid.attach(
            self._error_sound_checkbutton, 0, _options_grid_row, 1, 1)
        self._options_grid.attach(
            self._error_sound_file_button, 1, _options_grid_row, 1, 1)

        self._debug_level_label = Gtk.Label()
        self._debug_level_label.set_text(
            # Translators: When the debug level is greater than 0,
            # debug information may be printed to the log file and
            # debug information may also be shown graphically.
            _('Debug level:'))
        self._debug_level_label.set_tooltip_text(
            _('When greater than 0, debug information may be '
              'printed to the log file and debug information '
              'may also be shown graphically.'))
        self._debug_level_label.set_xalign(0)
        self._debug_level_adjustment = Gtk.SpinButton()
        self._debug_level_adjustment.set_visible(True)
        self._debug_level_adjustment.set_can_focus(True)
        self._debug_level_adjustment.set_increments(1.0, 1.0)
        self._debug_level_adjustment.set_range(0.0, 255.0)
        self._debug_level_adjustment.set_value(
            int(self._settings_dict['debuglevel']['user']))
        self._debug_level_adjustment.connect(
            'value-changed',
            self._on_debug_level_adjustment_value_changed)
        _options_grid_row += 1
        self._options_grid.attach(
            self._debug_level_label, 0, _options_grid_row, 1, 1)
        self._options_grid.attach(
            self._debug_level_adjustment, 1, _options_grid_row, 1, 1)

        self._learn_from_file_button = Gtk.Button(
            # Translators: A button used to popup a file selector to
            # choose a text file and learn your writing style by
            # reading that text file.
            label=_('Learn from text file'))
        self._learn_from_file_button.set_tooltip_text(
            _('Learn your style by reading a text file'))
        self._learn_from_file_button.set_hexpand(True)
        self._learn_from_file_button.set_vexpand(False)
        self._learn_from_file_button.connect(
            'clicked', self._on_learn_from_file_clicked)
        _options_grid_row += 1
        self._options_grid.attach(
            self._learn_from_file_button, 0, _options_grid_row, 1, 1)

        self._delete_learned_data_button = Gtk.Button(
            # Translators: A button used to delete all personal
            # language data learned from typing or from reading files.
            label=_('Delete learned data'))
        self._delete_learned_data_button.set_tooltip_text(
            _('Delete all personal language data learned from '
              'typing or from reading files'))
        self._delete_learned_data_button.set_hexpand(True)
        self._delete_learned_data_button.set_vexpand(False)
        self._delete_learned_data_button.connect(
            'clicked', self._on_delete_learned_data_clicked)
        self._options_grid.attach(
            self._delete_learned_data_button, 1, _options_grid_row, 1, 1)

        self._dictionaries_label = Gtk.Label()
        self._dictionaries_label.set_text(
            # Translators: This is the header of the list of
            # dictionaries which are currently set up to be used by
            # ibus-typing-booster.
            '<b>' +_('Use dictionaries for the following languages:') + '</b>')
        self._dictionaries_label.set_use_markup(True)
        margin = 5
        self._dictionaries_label.set_margin_start(margin)
        self._dictionaries_label.set_margin_end(margin)
        self._dictionaries_label.set_margin_top(margin)
        self._dictionaries_label.set_margin_bottom(margin)
        self._dictionaries_label.set_hexpand(False)
        self._dictionaries_label.set_vexpand(False)
        self._dictionaries_label.set_xalign(0)
        self._dictionaries_and_input_methods_vbox.add(
            self._dictionaries_label)
        self._dictionaries_scroll = Gtk.ScrolledWindow()
        self._dictionaries_and_input_methods_vbox.add(
            self._dictionaries_scroll)
        self._dictionaries_action_area = Gtk.Box()
        self._dictionaries_action_area.set_orientation(
            Gtk.Orientation.HORIZONTAL)
        self._dictionaries_action_area.set_can_focus(False)
        self._dictionaries_and_input_methods_vbox.add(
            self._dictionaries_action_area)
        self._dictionaries_add_button = Gtk.Button()
        self._dictionaries_add_button_label = Gtk.Label()
        self._dictionaries_add_button_label.set_text(
            '<span size="xx-large"><b>+</b></span>')
        self._dictionaries_add_button_label.set_use_markup(True)
        self._dictionaries_add_button.add(
            self._dictionaries_add_button_label)
        self._dictionaries_add_button.set_tooltip_text(
            _('Add a dictionary'))
        self._dictionaries_add_button.connect(
            'clicked', self._on_dictionaries_add_button_clicked)
        self._dictionaries_remove_button = Gtk.Button()
        self._dictionaries_remove_button_label = Gtk.Label()
        self._dictionaries_remove_button_label.set_text(
            '<span size="xx-large"><b>−</b></span>')
        self._dictionaries_remove_button_label.set_use_markup(True)
        self._dictionaries_remove_button.add(
            self._dictionaries_remove_button_label)
        self._dictionaries_remove_button.set_tooltip_text(
            _('Remove a dictionary'))
        self._dictionaries_remove_button.connect(
            'clicked', self._on_dictionaries_remove_button_clicked)
        self._dictionaries_remove_button.set_sensitive(False)
        self._dictionaries_up_button = Gtk.Button()
        self._dictionaries_up_button_label = Gtk.Label()
        self._dictionaries_up_button_label.set_text(
            '<span size="xx-large"><b>↑</b></span>')
        self._dictionaries_up_button_label.set_use_markup(True)
        self._dictionaries_up_button.add(self._dictionaries_up_button_label)
        self._dictionaries_up_button.set_tooltip_text(
            _('Move dictionary up'))
        self._dictionaries_up_button.connect(
            'clicked', self._on_dictionaries_up_button_clicked)
        self._dictionaries_up_button.set_sensitive(False)
        self._dictionaries_down_button = Gtk.Button()
        self._dictionaries_down_button_label = Gtk.Label()
        self._dictionaries_down_button_label.set_text(
            '<span size="xx-large"><b>↓</b></span>')
        self._dictionaries_down_button_label.set_use_markup(True)
        self._dictionaries_down_button.add(
            self._dictionaries_down_button_label)
        self._dictionaries_down_button.set_tooltip_text(
            _('Move dictionary down'))
        self._dictionaries_down_button.connect(
            'clicked', self._on_dictionaries_down_button_clicked)
        self._dictionaries_down_button.set_sensitive(False)
        self._dictionaries_install_missing_button = Gtk.Button(
            # Translators: A button used to try to install the
            # dictionaries which are setup here but not installed
            label=_('Install missing dictionaries'))
        self._dictionaries_install_missing_button.set_tooltip_text(
            _('Install the dictionaries which are '
              'setup here but not installed'))
        self._dictionaries_install_missing_button.connect(
            'clicked', self._on_install_missing_dictionaries)
        self._dictionaries_default_button = Gtk.Button()
        self._dictionaries_default_button_label = Gtk.Label()
        self._dictionaries_default_button_label.set_text(
            _('Set to default'))
        self._dictionaries_default_button.add(
            self._dictionaries_default_button_label)
        dictionaries_default_button_tooltip_text = (
            # Translators: Tooltip for a button used to set the list of
            # dictionaries to the default for the current locale.
            _('Set dictionaries to the default for the current locale.')
            + f' (LC_CTYPE={itb_util.get_effective_lc_ctype()} '
            f'→ {itb_util.dictionaries_str_to_list("")})')
        if self._engine_name != 'typing-booster':
            dictionaries_default_button_tooltip_text = '→ None'
        self._dictionaries_default_button.set_tooltip_text(
            dictionaries_default_button_tooltip_text)
        self._dictionaries_default_button.connect(
            'clicked', self._on_dictionaries_default_button_clicked)
        self._dictionaries_default_button.set_sensitive(True)
        self._dictionaries_action_area.add(self._dictionaries_add_button)
        self._dictionaries_action_area.add(self._dictionaries_remove_button)
        self._dictionaries_action_area.add(self._dictionaries_up_button)
        self._dictionaries_action_area.add(self._dictionaries_down_button)
        self._dictionaries_action_area.add(
            self._dictionaries_install_missing_button)
        self._dictionaries_action_area.add(
            self._dictionaries_default_button)
        self._dictionaries_listbox_selected_dictionary_name = ''
        self._dictionaries_listbox_selected_dictionary_index = -1
        self._dictionary_names: List[str] = []
        dictionary = self._settings_dict['dictionary']['user']
        self._dictionary_names = itb_util.dictionaries_str_to_list(dictionary)
        if ','.join(self._dictionary_names) != dictionary:
            # Value changed due to normalization or getting the locale
            # defaults, save it back to settings:
            self._gsettings.set_value(
                'dictionary',
                GLib.Variant.new_string(','.join(self._dictionary_names)))
        self._dictionaries_listbox = None
        self._dictionaries_add_listbox = None
        self._dictionaries_add_listbox_dictionary_names: List[str] = []
        self._dictionaries_add_popover = None
        self._dictionaries_add_popover_scroll = None
        self._fill_dictionaries_listbox()

        self._input_methods_label = Gtk.Label()
        self._input_methods_label.set_text(
            # Translators: This is the header of the list of input
            # methods which are currently set up to be used by
            # ibus-typing-booster.
            '<b>' + _('Use the following input methods:') + '</b>')
        self._input_methods_label.set_use_markup(True)
        margin = 5
        self._input_methods_label.set_margin_start(margin)
        self._input_methods_label.set_margin_end(margin)
        self._input_methods_label.set_margin_top(margin)
        self._input_methods_label.set_margin_bottom(margin)
        self._input_methods_label.set_hexpand(False)
        self._input_methods_label.set_vexpand(False)
        self._input_methods_label.set_xalign(0)
        self._dictionaries_and_input_methods_vbox.add(
            self._input_methods_label)
        self._input_methods_scroll = Gtk.ScrolledWindow()
        self._dictionaries_and_input_methods_vbox.add(
            self._input_methods_scroll)
        self._input_methods_action_area = Gtk.Box()
        self._input_methods_action_area.set_orientation(
            Gtk.Orientation.HORIZONTAL)
        self._input_methods_action_area.set_can_focus(False)
        self._dictionaries_and_input_methods_vbox.add(
            self._input_methods_action_area)
        self._input_methods_add_button = Gtk.Button()
        self._input_methods_add_button_label = Gtk.Label()
        self._input_methods_add_button_label.set_text(
            '<span size="xx-large"><b>+</b></span>')
        self._input_methods_add_button_label.set_use_markup(True)
        self._input_methods_add_button.add(
            self._input_methods_add_button_label)
        self._input_methods_add_button.set_tooltip_text(
            _('Add an input method'))
        self._input_methods_add_button.connect(
            'clicked', self._on_input_methods_add_button_clicked)
        self._input_methods_add_button.set_sensitive(False)
        self._input_methods_remove_button = Gtk.Button()
        self._input_methods_remove_button_label = Gtk.Label()
        self._input_methods_remove_button_label.set_text(
            '<span size="xx-large"><b>−</b></span>')
        self._input_methods_remove_button_label.set_use_markup(True)
        self._input_methods_remove_button.add(
            self._input_methods_remove_button_label)
        self._input_methods_remove_button.set_tooltip_text(
            _('Remove an input method'))
        self._input_methods_remove_button.connect(
            'clicked', self._on_input_methods_remove_button_clicked)
        self._input_methods_remove_button.set_sensitive(False)
        self._input_methods_up_button = Gtk.Button()
        self._input_methods_up_button_label = Gtk.Label()
        self._input_methods_up_button_label.set_text(
            '<span size="xx-large"><b>↑</b></span>')
        self._input_methods_up_button_label.set_use_markup(True)
        self._input_methods_up_button.add(
            self._input_methods_up_button_label)
        self._input_methods_up_button.set_tooltip_text(
            _('Move input method up'))
        self._input_methods_up_button.connect(
            'clicked', self._on_input_methods_up_button_clicked)
        self._input_methods_up_button.set_sensitive(False)
        self._input_methods_down_button = Gtk.Button()
        self._input_methods_down_button_label = Gtk.Label()
        self._input_methods_down_button_label.set_text(
            '<span size="xx-large"><b>↓</b></span>')
        self._input_methods_down_button_label.set_use_markup(True)
        self._input_methods_down_button.add(
            self._input_methods_down_button_label)
        self._input_methods_down_button.set_tooltip_text(
            _('Move input method down'))
        self._input_methods_down_button.connect(
            'clicked', self._on_input_methods_down_button_clicked)
        self._input_methods_down_button.set_sensitive(False)
        self._input_methods_help_button = Gtk.Button(
            # Translators: A button to display some help showing how
            # to use the input method selected in the list of input
            # methods.
            label=_('Input Method Help'))
        self._input_methods_help_button.set_tooltip_text(
            _('Display some help showing how to use the '
              'input method selected above.'))
        self._input_methods_help_button.connect(
            'clicked', self._on_input_methods_help_button_clicked)
        self._input_methods_help_button.set_sensitive(False)
        self._input_methods_options_button = Gtk.Button()
        self._input_methods_options_button_label = Gtk.Label()
        self._input_methods_options_button_label.set_text(
            '<span size="xx-large">🛠️️</span>') # Hammer and wrench
        self._input_methods_options_button_label.set_use_markup(True)
        self._input_methods_options_button.add(
            self._input_methods_options_button_label)
        self._input_methods_options_button.set_tooltip_text(
            # Translators: Tooltip for a button to set some advanced
            # options for the input method currently selected in the
            # list of input methods.
            _('Options for the input method selected above.'))
        self._input_methods_options_button.connect(
            'clicked', self._on_input_methods_options_button_clicked)
        self._input_methods_options_button.set_sensitive(False)
        self._input_methods_default_button = Gtk.Button()
        self._input_methods_default_button_label = Gtk.Label()
        self._input_methods_default_button_label.set_text(
            _('Set to default'))
        self._input_methods_default_button.add(
            self._input_methods_default_button_label)
        input_methods_default_button_tooltip_text = (
            # Translators: Tooltip for a button used to set the list of
            # input methods to the default for the current locale.
            _('Set input methods to the default for the current locale.')
            + f' (LC_CTYPE={itb_util.get_effective_lc_ctype()} '
            f'→ {itb_util.input_methods_str_to_list("")}')
        if self._engine_name != 'typing-booster':
            input_methods_default_button_tooltip_text = (
                f'→ {self._m17n_ime_lang}-{self._m17n_ime_name}')
        self._input_methods_default_button.set_tooltip_text(
            input_methods_default_button_tooltip_text)
        self._input_methods_default_button.connect(
            'clicked', self._on_input_methods_default_button_clicked)
        self._input_methods_default_button.set_sensitive(True)
        self._input_methods_action_area.add(self._input_methods_add_button)
        self._input_methods_action_area.add(self._input_methods_remove_button)
        self._input_methods_action_area.add(self._input_methods_up_button)
        self._input_methods_action_area.add(self._input_methods_down_button)
        self._input_methods_action_area.add(self._input_methods_options_button)
        self._input_methods_action_area.add(self._input_methods_help_button)
        self._input_methods_action_area.add(self._input_methods_default_button)
        self._input_methods_listbox_selected_ime_name = ''
        self._input_methods_listbox_selected_ime_index = -1
        self._current_imes: List[str] = []
        inputmethod = self._settings_dict['inputmethod']['user']
        self._current_imes = itb_util.input_methods_str_to_list(inputmethod)
        if ','.join(self._current_imes) != inputmethod:
            # Value changed due to normalization or getting the locale
            # defaults, save it back to settings:
            self._gsettings.set_value(
                'inputmethod',
                GLib.Variant.new_string(','.join(self._current_imes)))
        self._input_methods_listbox = None
        self._input_methods_add_listbox = None
        self._input_methods_add_listbox_imes: List[str] = []
        self._input_methods_add_popover = None
        self._input_methods_add_popover_scroll = None
        self._input_methods_options_popover = None
        self._fill_input_methods_listbox()

        _shortcuts_grid_row = -1

        self._shortcut_label = Gtk.Label()
        self._shortcut_label.set_text(_('Enter shortcut here:'))
        self._shortcut_label.set_hexpand(False)
        self._shortcut_label.set_vexpand(False)
        self._shortcut_label.set_xalign(0)
        _shortcuts_grid_row += 1
        self._custom_shortcuts_grid.attach(
            self._shortcut_label, 0, _shortcuts_grid_row, 3, 1)

        self._shortcut_entry = Gtk.Entry()
        self._shortcut_entry.set_visible(True)
        self._shortcut_entry.set_can_focus(True)
        self._shortcut_entry.set_hexpand(False)
        self._shortcut_entry.set_vexpand(False)
        _shortcuts_grid_row += 1
        self._custom_shortcuts_grid.attach(
            self._shortcut_entry, 0, _shortcuts_grid_row, 3, 1)
        self._shortcut_entry.set_text('')
        self._shortcut_entry.connect(
            'notify::text', self._on_shortcut_entry)

        self._shortcut_expansion_label = Gtk.Label()
        self._shortcut_expansion_label.set_text(
            _('Enter shortcut expansion here:'))
        self._shortcut_expansion_label.set_hexpand(False)
        self._shortcut_expansion_label.set_vexpand(False)
        self._shortcut_expansion_label.set_xalign(0)
        _shortcuts_grid_row += 1
        self._custom_shortcuts_grid.attach(
            self._shortcut_expansion_label, 0, _shortcuts_grid_row, 3, 1)

        self._shortcut_expansion_scroll = Gtk.ScrolledWindow()
        self._shortcut_expansion_scroll.set_can_focus(False)
        self._shortcut_expansion_scroll.set_hexpand(False)
        self._shortcut_expansion_scroll.set_vexpand(True)
        self._shortcut_expansion_scroll.set_shadow_type(Gtk.ShadowType.IN)
        self._shortcut_expansion_textview_buffer = Gtk.TextBuffer()
        self._shortcut_expansion_textview = Gtk.TextView()
        self._shortcut_expansion_textview.set_buffer(
            self._shortcut_expansion_textview_buffer)
        self._shortcut_expansion_textview.set_visible(True)
        self._shortcut_expansion_textview.set_can_focus(True)
        self._shortcut_expansion_textview.set_hexpand(False)
        self._shortcut_expansion_textview.set_vexpand(False)
        self._shortcut_expansion_scroll.add(self._shortcut_expansion_textview)
        _shortcuts_grid_row += 1
        self._custom_shortcuts_grid.attach(
            self._shortcut_expansion_scroll, 0, _shortcuts_grid_row, 3, 3)
        self._shortcut_expansion_textview_buffer.connect(
            'notify::text', self._on_shortcut_expansion_textview_buffer)
        _shortcuts_grid_row += 4

        self._shortcut_clear_button = Gtk.Button(
            label=_('Clear input'))
        self._shortcut_clear_button.set_receives_default(False)
        self._shortcut_clear_button.set_hexpand(False)
        self._shortcut_clear_button.set_vexpand(False)
        self._custom_shortcuts_grid.attach(
            self._shortcut_clear_button, 0, _shortcuts_grid_row, 1, 1)
        self._shortcut_clear_button.connect(
            'clicked', self._on_shortcut_clear_clicked)
        self._shortcut_clear_button.set_sensitive(False)

        self._shortcut_delete_button = Gtk.Button(
            label=_('Delete shortcut'))
        self._shortcut_delete_button.set_receives_default(False)
        self._shortcut_delete_button.set_hexpand(False)
        self._shortcut_delete_button.set_vexpand(False)
        self._custom_shortcuts_grid.attach(
            self._shortcut_delete_button, 1, _shortcuts_grid_row, 1, 1)
        self._shortcut_delete_button.connect(
            'clicked', self._on_shortcut_delete_clicked)
        self._shortcut_delete_button.set_sensitive(False)

        self._shortcut_add_button = Gtk.Button(
            label=_('Add shortcut'))
        self._shortcut_add_button.set_receives_default(False)
        self._shortcut_add_button.set_hexpand(False)
        self._shortcut_add_button.set_vexpand(False)
        self._custom_shortcuts_grid.attach(
            self._shortcut_add_button, 2, _shortcuts_grid_row, 1, 1)
        self._shortcut_add_button.connect(
            'clicked', self._on_shortcut_add_clicked)
        self._shortcut_add_button.set_sensitive(False)

        self._shortcut_search_entry = Gtk.SearchEntry()
        self._shortcut_search_entry.set_can_focus(True)
        self._shortcut_search_entry.set_visible(True)
        self._shortcut_search_entry.set_halign(Gtk.Align.FILL)
        self._shortcut_search_entry.set_hexpand(False)
        self._shortcut_search_entry.set_vexpand(False)
        self._shortcut_search_entry.connect(
            'search-changed', self._on_shortcut_search_entry_changed)
        _shortcuts_grid_row += 1
        self._custom_shortcuts_grid.attach(
            self._shortcut_search_entry, 0, _shortcuts_grid_row, 3, 1)

        self._shortcut_treeview_scroll = Gtk.ScrolledWindow()
        self._shortcut_treeview_scroll.set_can_focus(False)
        self._shortcut_treeview_scroll.set_hexpand(False)
        self._shortcut_treeview_scroll.set_vexpand(True)
        self._shortcut_treeview_scroll.set_shadow_type(Gtk.ShadowType.IN)
        self._shortcut_treeview = Gtk.TreeView()
        self._shortcut_treeview_model = Gtk.ListStore(str, str)
        self._shortcut_treeview.set_model(self._shortcut_treeview_model)
        self._fill_shortcut_treeview_model('')
        shortcut_treeview_column_0 = Gtk.TreeViewColumn(
            # Translators: Column heading of the table listing the
            # existing shortcuts
            _('Shortcut'),
            Gtk.CellRendererText(),
            text=0)
        shortcut_treeview_column_0.set_sort_column_id(0)
        self._shortcut_treeview.append_column(shortcut_treeview_column_0)
        shortcut_treeview_column_1 = Gtk.TreeViewColumn(
            # Translators: Column heading of the table listing the
            # existing shortcuts
            _('Shortcut expansion'),
            Gtk.CellRendererText(),
            text=1)
        shortcut_treeview_column_1.set_sort_column_id(1)
        self._shortcut_treeview.append_column(shortcut_treeview_column_1)
        self._shortcut_treeview.get_selection().connect(
            'changed', self._on_shortcut_selected)
        self._shortcut_treeview_scroll.add(self._shortcut_treeview)
        _shortcuts_grid_row += 1
        self._custom_shortcuts_grid.attach(
            self._shortcut_treeview_scroll, 0, _shortcuts_grid_row, 3, 10)

        self._keybindings_label = Gtk.Label()
        self._keybindings_label.set_text(
            '<b>' + _('Current key bindings:') + '</b>')
        self._keybindings_label.set_use_markup(True)
        self._keybindings_label.set_margin_start(margin)
        self._keybindings_label.set_margin_end(margin)
        self._keybindings_label.set_margin_top(margin)
        self._keybindings_label.set_margin_bottom(margin)
        self._keybindings_label.set_hexpand(False)
        self._keybindings_label.set_vexpand(False)
        self._keybindings_label.set_xalign(0)
        self._keybindings_treeview_scroll = Gtk.ScrolledWindow()
        self._keybindings_treeview_scroll.set_can_focus(False)
        self._keybindings_treeview_scroll.set_hexpand(False)
        self._keybindings_treeview_scroll.set_vexpand(True)
        self._keybindings_treeview_scroll.set_shadow_type(Gtk.ShadowType.IN)
        self._keybindings_treeview = Gtk.TreeView()
        self._keybindings_treeview_model = Gtk.ListStore(str, str)
        self._keybindings_treeview.set_model(self._keybindings_treeview_model)
        for command in sorted(self._settings_dict['keybindings']['user']):
            self._keybindings_treeview_model.append(
                (command,
                 repr(self._settings_dict['keybindings']['user'][command])))
        keybindings_treeview_column_0 = Gtk.TreeViewColumn(
            # Translators: Column heading of the table listing the
            # existing key bindings
            _('Command'),
            Gtk.CellRendererText(),
            text=0)
        keybindings_treeview_column_0.set_sort_column_id(0)
        self._keybindings_treeview.append_column(keybindings_treeview_column_0)
        keybindings_treeview_column_1 = Gtk.TreeViewColumn(
            # Translators: Column heading of the table listing the
            # existing key bindings
            _('Key bindings'),
            Gtk.CellRendererText(),
            text=1)
        keybindings_treeview_column_1.set_sort_column_id(1)
        self._keybindings_treeview.append_column(keybindings_treeview_column_1)
        self._keybindings_treeview.get_selection().connect(
            'changed', self._on_keybindings_treeview_row_selected)
        self._keybindings_treeview.connect(
            'row-activated', self._on_keybindings_treeview_row_activated)
        self._keybindings_treeview_scroll.add(self._keybindings_treeview)
        self._keybindings_vbox.add(
            self._keybindings_label)
        self._keybindings_vbox.add(
            self._keybindings_treeview_scroll)
        self._keybindings_action_area = Gtk.Box()
        self._keybindings_action_area.set_orientation(
            Gtk.Orientation.HORIZONTAL)
        self._keybindings_action_area.set_can_focus(False)
        self._keybindings_vbox.add(
            self._keybindings_action_area)
        self._keybindings_edit_button = Gtk.Button()
        self._keybindings_edit_button_label = Gtk.Label()
        self._keybindings_edit_button_label.set_text(
            _('Edit'))
        self._keybindings_edit_button.add(
            self._keybindings_edit_button_label)
        self._keybindings_edit_button.set_tooltip_text(
            _('Edit the key bindings for the selected command'))
        self._keybindings_edit_button.set_sensitive(False)
        self._keybindings_edit_button.connect(
            'clicked', self._on_keybindings_edit_button_clicked)
        self._keybindings_default_button = Gtk.Button()
        self._keybindings_default_button_label = Gtk.Label()
        self._keybindings_default_button_label.set_text(
            _('Set to default'))
        self._keybindings_default_button.add(
            self._keybindings_default_button_label)
        self._keybindings_default_button.set_tooltip_text(
            _('Set default key bindings for the selected command'))
        self._keybindings_default_button.set_sensitive(False)
        self._keybindings_default_button.connect(
            'clicked', self._on_keybindings_default_button_clicked)
        self._keybindings_all_default_button = Gtk.Button()
        self._keybindings_all_default_button_label = Gtk.Label()
        self._keybindings_all_default_button_label.set_text(
            _('Set all to default'))
        self._keybindings_all_default_button.add(
            self._keybindings_all_default_button_label)
        self._keybindings_all_default_button.set_tooltip_text(
            _('Set default key bindings for all commands'))
        self._keybindings_all_default_button.set_sensitive(True)
        self._keybindings_all_default_button.connect(
            'clicked', self._on_keybindings_all_default_button_clicked)
        self._keybindings_action_area.add(self._keybindings_edit_button)
        self._keybindings_action_area.add(self._keybindings_default_button)
        self._keybindings_action_area.add(self._keybindings_all_default_button)
        self._keybindings_selected_command = ''
        self._keybindings_edit_popover_selected_keybinding = ''
        self._keybindings_edit_popover_listbox = None
        self._keybindings_edit_popover = None
        self._keybindings_edit_popover_scroll = None
        self._keybindings_edit_popover_add_button = None
        self._keybindings_edit_popover_remove_button = None
        self._keybindings_edit_popover_default_button = None

        _appearance_grid_row = -1

        self._show_number_of_candidates_checkbutton = Gtk.CheckButton(
            # Translators: Checkbox to choose whether to display how
            # many candidates there are and which one is selected on
            # top of the list of candidates.
            label=_('Display total number of candidates'))
        self._show_number_of_candidates_checkbutton.set_tooltip_text(
            _('Display how many candidates there are and which '
              'one is selected on top of the list of candidates.'))
        self._show_number_of_candidates_checkbutton.connect(
            'clicked', self._on_show_number_of_candidates_checkbutton)
        self._show_number_of_candidates_checkbutton.set_active(
            self._settings_dict['shownumberofcandidates']['user'])

        self._show_status_info_in_auxiliary_text_checkbutton = Gtk.CheckButton(
            # Translators: Checkbox to choose whether to show above
            # the candidate list whether “Emoji prediction” mode and
            # “Off the record” mode are on or off and show which input
            # method is currently used for the preedit. The auxiliary
            # text is an optional line of text displayed above the
            # candidate list.
            label=_('Show status info in auxiliary text'))
        self._show_status_info_in_auxiliary_text_checkbutton.set_tooltip_text(
            _('Show in the auxiliary text whether “Emoji prediction”  '
              'mode and “Off the record”  mode are on or off '
              'and show which input method is currently used '
              'for the preedit. The auxiliary text is an '
              'optional line of text displayed above the '
              'candidate list.'))
        self._show_status_info_in_auxiliary_text_checkbutton.connect(
            'clicked', self._on_show_status_info_in_auxiliary_text_checkbutton)
        self._show_status_info_in_auxiliary_text_checkbutton.set_active(
            self._settings_dict['showstatusinfoinaux']['user'])

        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._show_number_of_candidates_checkbutton,
            0, _appearance_grid_row, 1, 1)
        self._appearance_grid.attach(
            self._show_status_info_in_auxiliary_text_checkbutton,
            1, _appearance_grid_row, 1, 1)

        self._page_size_label = Gtk.Label()
        # Translators: Here one can choose how many suggestion
        # candidates to show in one page of the candidate list.
        self._page_size_label.set_text(_('Candidate window page size:'))
        self._page_size_label.set_tooltip_text(
            _('How many suggestion candidates to show in '
              'one page of the candidate list.'))
        self._page_size_label.set_xalign(0)
        self._page_size_adjustment = Gtk.SpinButton()
        self._page_size_adjustment.set_visible(True)
        self._page_size_adjustment.set_can_focus(True)
        self._page_size_adjustment.set_increments(1.0, 1.0)
        self._page_size_adjustment.set_range(1.0, 9.0)
        self._page_size_adjustment.set_value(
            int(self._settings_dict['pagesize']['user']))
        self._page_size_adjustment.connect(
            'value-changed', self._on_page_size_adjustment_value_changed)
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._page_size_label, 0, _appearance_grid_row, 1, 1)
        self._appearance_grid.attach(
            self._page_size_adjustment, 1, _appearance_grid_row, 1, 1)

        self._lookup_table_orientation_label = Gtk.Label()
        self._lookup_table_orientation_label.set_text(
            # Translators: A combobox to choose whether the candidate
            # window should be drawn horizontally or vertically.
            _('Candidate window orientation'))
        self._lookup_table_orientation_label.set_tooltip_text(
            _('Whether the candidate window should be '
              'drawn horizontally or vertically.'))
        self._lookup_table_orientation_label.set_xalign(0)
        self._lookup_table_orientation_combobox = Gtk.ComboBox()
        self._lookup_table_orientation_store = Gtk.ListStore(str, int)
        self._lookup_table_orientation_store.append(
            [_('Horizontal'), IBus.Orientation.HORIZONTAL])
        self._lookup_table_orientation_store.append(
            [_('Vertical'), IBus.Orientation.VERTICAL])
        self._lookup_table_orientation_store.append(
            [_('System default'), IBus.Orientation.SYSTEM])
        self._lookup_table_orientation_combobox.set_model(
            self._lookup_table_orientation_store)
        renderer_text = Gtk.CellRendererText()
        self._lookup_table_orientation_combobox.pack_start(
            renderer_text, True)
        self._lookup_table_orientation_combobox.add_attribute(
            renderer_text, "text", 0)
        for i, item in enumerate(self._lookup_table_orientation_store):
            if self._settings_dict['lookuptableorientation']['user'] == item[1]:
                self._lookup_table_orientation_combobox.set_active(i)
        self._lookup_table_orientation_combobox.connect(
            "changed",
            self._on_lookup_table_orientation_combobox_changed)
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._lookup_table_orientation_label,
            0, _appearance_grid_row, 1, 1)
        self._appearance_grid.attach(
            self._lookup_table_orientation_combobox,
            1, _appearance_grid_row, 1, 1)

        self._candidates_delay_milliseconds_label = Gtk.Label()
        self._candidates_delay_milliseconds_label.set_text(
            # Translators: Here one can choose how many milliseconds
            # the system needs to be idle after pressing a key before
            # candidates are displayed
            _('Candidate window delay in milliseconds:'))
        self._candidates_delay_milliseconds_label.set_tooltip_text(
            # Translators: A tooltip explaining the meaning of the
            # “Candidate window delay in milliseconds:” option.
            _('How long to wait after the last key press before '
              'candidates are displayed.'))
        self._candidates_delay_milliseconds_label.set_xalign(0)
        self._candidates_delay_milliseconds_adjustment = Gtk.SpinButton()
        self._candidates_delay_milliseconds_adjustment.set_visible(True)
        self._candidates_delay_milliseconds_adjustment.set_can_focus(True)
        self._candidates_delay_milliseconds_adjustment.set_increments(
            10.0, 100.0)
        self._candidates_delay_milliseconds_adjustment.set_range(
            0.0, float(itb_util.UINT32_MAX))
        self._candidates_delay_milliseconds_adjustment.set_value(
            int(self._settings_dict['candidatesdelaymilliseconds']['user']))
        self._candidates_delay_milliseconds_adjustment.connect(
            'value-changed',
            self._on_candidates_delay_milliseconds_adjustment_value_changed)
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._candidates_delay_milliseconds_label,
            0, _appearance_grid_row, 1, 1)
        self._appearance_grid.attach(
            self._candidates_delay_milliseconds_adjustment,
            1, _appearance_grid_row, 1, 1)

        self._preedit_underline_label = Gtk.Label()
        self._preedit_underline_label.set_text(
            # Translators: A combobox to choose the style of
            # underlining for the preedit.
            _('Preedit underline'))
        self._preedit_underline_label.set_tooltip_text(
            _('Which style of underlining to use for the preedit.'))
        self._preedit_underline_label.set_xalign(0)
        self._preedit_underline_combobox = Gtk.ComboBox()
        self._preedit_underline_store = Gtk.ListStore(str, int)
        self._preedit_underline_store.append(
            # Translators: This is the setting to use no underline
            # at all for the preedit.
            [_('None'), IBus.AttrUnderline.NONE])
        self._preedit_underline_store.append(
            # Translators: This is the setting to use a single
            # underline for the preedit.
            [_('Single'), IBus.AttrUnderline.SINGLE])
        self._preedit_underline_store.append(
            # Translators: This is the setting to use a double
            # underline for the preedit.
            [_('Double'), IBus.AttrUnderline.DOUBLE])
        self._preedit_underline_store.append(
            # Translators: This is the setting to use a low
            # underline for the preedit.
            [_('Low'), IBus.AttrUnderline.LOW])
        self._preedit_underline_combobox.set_model(
            self._preedit_underline_store)
        renderer_text = Gtk.CellRendererText()
        self._preedit_underline_combobox.pack_start(
            renderer_text, True)
        self._preedit_underline_combobox.add_attribute(
            renderer_text, "text", 0)
        for i, item in enumerate(self._preedit_underline_store):
            if self._settings_dict['preeditunderline']['user'] == item[1]:
                self._preedit_underline_combobox.set_active(i)
        self._preedit_underline_combobox.connect(
            "changed",
            self._on_preedit_underline_combobox_changed)
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._preedit_underline_label, 0, _appearance_grid_row, 1, 1)
        self._appearance_grid.attach(
            self._preedit_underline_combobox, 1, _appearance_grid_row, 1, 1)

        self._preedit_style_only_when_lookup_checkbutton = Gtk.CheckButton(
            # Translators: Checkbox to choose whether a preedit style
            # like underlining will only be used if lookup is
            # enabled. The lookup can be disabled because one uses the
            # option to enable lookup only when a key is pressed or
            # because one uses the option to require a minimum number
            # of characters before a lookup is done.
            label=_('Use preedit style only if lookup is enabled'))
        self._preedit_style_only_when_lookup_checkbutton.set_tooltip_text(
            _('If this option is on, a preedit style like underlining '
              'will only be used if lookup is enabled. '
              'The lookup can be disabled because one uses the option '
              'to enable lookup only when a key is pressed or '
              'because one uses the option to require a minimum '
              'number of characters before a lookup is done.'))
        self._preedit_style_only_when_lookup_checkbutton.connect(
            'clicked', self._on_preedit_style_only_when_lookup_checkbutton)
        self._preedit_style_only_when_lookup_checkbutton.set_active(
            self._settings_dict['preeditstyleonlywhenlookup']['user'])
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._preedit_style_only_when_lookup_checkbutton,
            0, _appearance_grid_row, 2, 1)

        self._color_preedit_spellcheck_checkbutton = Gtk.CheckButton(
            # Translators: A checkbox where one can choose whether
            # spellchecking is done on the contents of the preedit and
            # a custom color is used to indicate when the preedit
            # might contain a spelling error.
            label=_('Preedit spellchecking'))
        self._color_preedit_spellcheck_checkbutton.set_tooltip_text(
            _('Here you can choose whether spellchecking is done '
              'on the contents of the preedit and a custom color '
              'is used to indicate when the preedit might contain '
              'a spelling error.'))
        self._color_preedit_spellcheck_checkbutton.set_hexpand(False)
        self._color_preedit_spellcheck_checkbutton.set_vexpand(False)
        self._color_preedit_spellcheck_checkbutton.set_active(
            self._settings_dict['colorpreeditspellcheck']['user'])
        self._color_preedit_spellcheck_checkbutton.connect(
            'clicked', self._on_color_preedit_spellcheck_checkbutton)
        self._color_preedit_spellcheck_rgba_colorbutton = Gtk.ColorButton()
        margin = 0
        self._color_preedit_spellcheck_rgba_colorbutton.set_margin_start(
            margin)
        self._color_preedit_spellcheck_rgba_colorbutton.set_margin_end(
            margin)
        self._color_preedit_spellcheck_rgba_colorbutton.set_margin_top(
            margin)
        self._color_preedit_spellcheck_rgba_colorbutton.set_margin_bottom(
            margin)
        self._color_preedit_spellcheck_rgba_colorbutton.set_hexpand(False)
        self._color_preedit_spellcheck_rgba_colorbutton.set_vexpand(False)
        self._color_preedit_spellcheck_rgba_colorbutton.set_title(
            # Translators: Used in the title bar of the colour chooser
            # dialog window where one can choose a custom colour for
            # the spellchecking in the preedit.
            _('Choose color for preedit spellchecking'))
        self._color_preedit_spellcheck_rgba_colorbutton.set_tooltip_text(
            _('Here you can specify which color to use for '
              'the preedit when the preedit might contain a '
              'spelling error. This setting only has an '
              'effect if the preedit spellchecking is enabled.'))
        gdk_rgba = Gdk.RGBA()
        gdk_rgba.parse(
            self._settings_dict['colorpreeditspellcheckstring']['user'])
        self._color_preedit_spellcheck_rgba_colorbutton.set_rgba(gdk_rgba)
        self._color_preedit_spellcheck_rgba_colorbutton.set_sensitive(
            self._settings_dict['colorpreeditspellcheck']['user'])
        self._color_preedit_spellcheck_rgba_colorbutton.connect(
            'color-set', self._on_color_preedit_spellcheck_color_set)
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._color_preedit_spellcheck_checkbutton,
            0, _appearance_grid_row, 1, 1)
        self._appearance_grid.attach(
            self._color_preedit_spellcheck_rgba_colorbutton,
            1, _appearance_grid_row, 1, 1)

        self._color_inline_completion_checkbutton = Gtk.CheckButton(
            # Translators: A checkbox where one can choose whether a
            # custom color is used for suggestions shown inline.
            label=_('Use color for inline completion'))
        self._color_inline_completion_checkbutton.set_tooltip_text(
            _('Here you can choose whether a custom color '
              'is used for a suggestion shown inline.'))
        self._color_inline_completion_checkbutton.set_hexpand(False)
        self._color_inline_completion_checkbutton.set_vexpand(False)
        self._color_inline_completion_checkbutton.set_active(
            self._settings_dict['colorinlinecompletion']['user'])
        self._color_inline_completion_checkbutton.connect(
            'clicked', self._on_color_inline_completion_checkbutton)
        self._color_inline_completion_rgba_colorbutton = Gtk.ColorButton()
        margin = 0
        self._color_inline_completion_rgba_colorbutton.set_margin_start(
            margin)
        self._color_inline_completion_rgba_colorbutton.set_margin_end(
            margin)
        self._color_inline_completion_rgba_colorbutton.set_margin_top(
            margin)
        self._color_inline_completion_rgba_colorbutton.set_margin_bottom(
            margin)
        self._color_inline_completion_rgba_colorbutton.set_hexpand(False)
        self._color_inline_completion_rgba_colorbutton.set_vexpand(False)
        self._color_inline_completion_rgba_colorbutton.set_title(
            # Translators: Used in the title bar of the colour chooser
            # dialog window where one can choose a custom colour for
            # inline completion.
            _('Choose color for inline completion'))
        self._color_inline_completion_rgba_colorbutton.set_tooltip_text(
            _('Here you can specify which color to use for '
              'inline completion. This setting only has an '
              'effect if the use of color for inline completion '
              'is enabled and inline completion is enabled.'))
        gdk_rgba = Gdk.RGBA()
        gdk_rgba.parse(
            self._settings_dict['colorinlinecompletionstring']['user'])
        self._color_inline_completion_rgba_colorbutton.set_rgba(gdk_rgba)
        self._color_inline_completion_rgba_colorbutton.set_sensitive(
            self._settings_dict['colorinlinecompletion']['user'])
        self._color_inline_completion_rgba_colorbutton.connect(
            'color-set', self._on_color_inline_completion_color_set)
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._color_inline_completion_checkbutton,
            0, _appearance_grid_row, 1, 1)
        self._appearance_grid.attach(
            self._color_inline_completion_rgba_colorbutton,
            1, _appearance_grid_row, 1, 1)

        self._color_compose_preview_checkbutton = Gtk.CheckButton(
            # Translators: A checkbox where one can choose whether a
            # custom color is used for the compose preview.
            label=_('Use color for compose preview'))
        self._color_compose_preview_checkbutton.set_tooltip_text(
            _('Here you can choose whether a custom color '
              'is used for the compose preview.'))
        self._color_compose_preview_checkbutton.set_hexpand(False)
        self._color_compose_preview_checkbutton.set_vexpand(False)
        self._color_compose_preview_checkbutton.set_active(
            self._settings_dict['colorcomposepreview']['user'])
        self._color_compose_preview_checkbutton.connect(
            'clicked', self._on_color_compose_preview_checkbutton)
        self._color_compose_preview_rgba_colorbutton = Gtk.ColorButton()
        margin = 0
        self._color_compose_preview_rgba_colorbutton.set_margin_start(
            margin)
        self._color_compose_preview_rgba_colorbutton.set_margin_end(
            margin)
        self._color_compose_preview_rgba_colorbutton.set_margin_top(
            margin)
        self._color_compose_preview_rgba_colorbutton.set_margin_bottom(
            margin)
        self._color_compose_preview_rgba_colorbutton.set_hexpand(False)
        self._color_compose_preview_rgba_colorbutton.set_vexpand(False)
        self._color_compose_preview_rgba_colorbutton.set_title(
            # Translators: Used in the title bar of the colour chooser
            # dialog window where one can choose a custom colour for
            # the compose preview.
            _('Choose color for compose preview'))
        self._color_compose_preview_rgba_colorbutton.set_tooltip_text(
            _('Here you can specify which color to use for '
              'the compose preview.'))
        gdk_rgba = Gdk.RGBA()
        gdk_rgba.parse(
            self._settings_dict['colorcomposepreviewstring']['user'])
        self._color_compose_preview_rgba_colorbutton.set_rgba(gdk_rgba)
        self._color_compose_preview_rgba_colorbutton.set_sensitive(
            self._settings_dict['colorcomposepreview']['user'])
        self._color_compose_preview_rgba_colorbutton.connect(
            'color-set', self._on_color_compose_preview_color_set)
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._color_compose_preview_checkbutton,
            0, _appearance_grid_row, 1, 1)
        self._appearance_grid.attach(
            self._color_compose_preview_rgba_colorbutton,
            1, _appearance_grid_row, 1, 1)

        self._color_userdb_checkbutton = Gtk.CheckButton(
            # Translators: A checkbox where one can choose whether a
            # custom color is used for suggestions coming from the
            # user database.
            label=_('Use color for user database suggestions'))
        self._color_userdb_checkbutton.set_tooltip_text(
            _('Here you can choose whether a custom color is used '
              'for candidates in the lookup table which come '
              'from the user database.'))
        self._color_userdb_checkbutton.set_hexpand(False)
        self._color_userdb_checkbutton.set_vexpand(False)
        self._color_userdb_checkbutton.set_active(
            self._settings_dict['coloruserdb']['user'])
        self._color_userdb_checkbutton.connect(
            'clicked', self._on_color_userdb_checkbutton)
        self._color_userdb_rgba_colorbutton = Gtk.ColorButton()
        margin = 0
        self._color_userdb_rgba_colorbutton.set_margin_start(margin)
        self._color_userdb_rgba_colorbutton.set_margin_end(margin)
        self._color_userdb_rgba_colorbutton.set_margin_top(margin)
        self._color_userdb_rgba_colorbutton.set_margin_bottom(margin)
        self._color_userdb_rgba_colorbutton.set_hexpand(False)
        self._color_userdb_rgba_colorbutton.set_vexpand(False)
        self._color_userdb_rgba_colorbutton.set_title(
            # Translators: Used in the title bar of the colour chooser
            # dialog window where one can choose a custom colour for
            # suggestions from the user database.
            _('Choose color for user database suggestions'))
        self._color_userdb_rgba_colorbutton.set_tooltip_text(
            _('Here you can specify which color to use for '
              'candidates in the lookup table which come '
              'from the user database. This setting only '
              'has an effect if the use of color for '
              'candidates from the user database is enabled.'))
        gdk_rgba = Gdk.RGBA()
        gdk_rgba.parse(self._settings_dict['coloruserdbstring']['user'])
        self._color_userdb_rgba_colorbutton.set_rgba(gdk_rgba)
        self._color_userdb_rgba_colorbutton.set_sensitive(
            self._settings_dict['coloruserdb']['user'])
        self._color_userdb_rgba_colorbutton.connect(
            'color-set', self._on_color_userdb_color_set)
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._color_userdb_checkbutton, 0, _appearance_grid_row, 1, 1)
        self._appearance_grid.attach(
            self._color_userdb_rgba_colorbutton, 1, _appearance_grid_row, 1, 1)

        self._color_spellcheck_checkbutton = Gtk.CheckButton(
            # Translators: A checkbox where one can choose whether a
            # custom color is used for spellchecking suggestions.
            label=_('Use color for spellchecking suggestions'))
        self._color_spellcheck_checkbutton.set_tooltip_text(
            _('Here you can choose whether a custom color '
              'is used for candidates in the lookup table '
              'which come from spellchecking.'))
        self._color_spellcheck_checkbutton.set_hexpand(False)
        self._color_spellcheck_checkbutton.set_vexpand(False)
        self._color_spellcheck_checkbutton.set_active(
            self._settings_dict['colorspellcheck']['user'])
        self._color_spellcheck_checkbutton.connect(
            'clicked', self._on_color_spellcheck_checkbutton)
        self._color_spellcheck_rgba_colorbutton = Gtk.ColorButton()
        margin = 0
        self._color_spellcheck_rgba_colorbutton.set_margin_start(margin)
        self._color_spellcheck_rgba_colorbutton.set_margin_end(margin)
        self._color_spellcheck_rgba_colorbutton.set_margin_top(margin)
        self._color_spellcheck_rgba_colorbutton.set_margin_bottom(margin)
        self._color_spellcheck_rgba_colorbutton.set_hexpand(False)
        self._color_spellcheck_rgba_colorbutton.set_vexpand(False)
        self._color_spellcheck_rgba_colorbutton.set_title(
            # Translators: Used in the title bar of the colour chooser
            # dialog window where one can choose a custom colour for
            # spellchecking suggestions.
            _('Choose color for spellchecking suggestions'))
        self._color_spellcheck_rgba_colorbutton.set_tooltip_text(
            _('Here you can specify which color to use for '
              'candidates in the lookup table which come '
              'from spellchecking. This setting only has '
              'an effect if the use of color for candidates '
              'from spellchecking is enabled.'))
        gdk_rgba = Gdk.RGBA()
        gdk_rgba.parse(self._settings_dict['colorspellcheckstring']['user'])
        self._color_spellcheck_rgba_colorbutton.set_rgba(gdk_rgba)
        self._color_spellcheck_rgba_colorbutton.set_sensitive(
            self._settings_dict['colorspellcheck']['user'])
        self._color_spellcheck_rgba_colorbutton.connect(
            'color-set', self._on_color_spellcheck_color_set)
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._color_spellcheck_checkbutton,
            0, _appearance_grid_row, 1, 1)
        self._appearance_grid.attach(
            self._color_spellcheck_rgba_colorbutton,
            1, _appearance_grid_row, 1, 1)

        self._color_dictionary_checkbutton = Gtk.CheckButton(
            # Translators: A checkbox where one can choose whether a
            # custom color is used for suggestions coming from a
            # dictionary.
            label=_('Use color for dictionary suggestions'))
        self._color_dictionary_checkbutton.set_tooltip_text(
            _('Here you can choose whether a custom color is '
              'used for candidates in the lookup table '
              'which come from a dictionary.'))
        self._color_dictionary_checkbutton.set_hexpand(False)
        self._color_dictionary_checkbutton.set_vexpand(False)
        self._color_dictionary_checkbutton.set_active(
            self._settings_dict['colordictionary']['user'])
        self._color_dictionary_checkbutton.connect(
            'clicked', self._on_color_dictionary_checkbutton)
        self._color_dictionary_rgba_colorbutton = Gtk.ColorButton()
        margin = 0
        self._color_dictionary_rgba_colorbutton.set_margin_start(margin)
        self._color_dictionary_rgba_colorbutton.set_margin_end(margin)
        self._color_dictionary_rgba_colorbutton.set_margin_top(margin)
        self._color_dictionary_rgba_colorbutton.set_margin_bottom(margin)
        self._color_dictionary_rgba_colorbutton.set_hexpand(False)
        self._color_dictionary_rgba_colorbutton.set_vexpand(False)
        self._color_dictionary_rgba_colorbutton.set_title(
            # Translators: Used in the title bar of the colour chooser
            # dialog window where one can choose a custom colour for
            # suggestions from a dictionary.
            _('Choose color for dictionary suggestions'))
        self._color_dictionary_rgba_colorbutton.set_tooltip_text(
            _('Here you can specify which color to use for '
              'candidates in the lookup table which come '
              'from a dictionary. This setting only has '
              'an effect if the use of color for candidates '
              'from a dictionary is enabled.'))
        gdk_rgba = Gdk.RGBA()
        gdk_rgba.parse(self._settings_dict['colordictionarystring']['user'])
        self._color_dictionary_rgba_colorbutton.set_rgba(gdk_rgba)
        self._color_dictionary_rgba_colorbutton.set_sensitive(
            self._settings_dict['colordictionary']['user'])
        self._color_dictionary_rgba_colorbutton.connect(
            'color-set', self._on_color_dictionary_color_set)
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._color_dictionary_checkbutton,
            0, _appearance_grid_row, 1, 1)
        self._appearance_grid.attach(
            self._color_dictionary_rgba_colorbutton,
            1, _appearance_grid_row, 1, 1)

        self._label_userdb_checkbutton = Gtk.CheckButton(
            # Translators: A checkbox where one can choose whether a
            # label is used to mark suggestions coming from the user
            # database in the candidate list.
            label=_('Use label for user database suggestions'))
        self._label_userdb_checkbutton.set_tooltip_text(
            _('Here you can choose whether a label is used '
              'for candidates in the lookup table which '
              'come from the user database.'))
        self._label_userdb_checkbutton.set_hexpand(False)
        self._label_userdb_checkbutton.set_vexpand(False)
        self._label_userdb_checkbutton.set_active(
            self._settings_dict['labeluserdb']['user'])
        self._label_userdb_checkbutton.connect(
            'clicked', self._on_label_userdb_checkbutton)
        self._label_userdb_entry = Gtk.Entry()
        self._label_userdb_entry.set_visible(True)
        self._label_userdb_entry.set_can_focus(True)
        self._label_userdb_entry.set_hexpand(False)
        self._label_userdb_entry.set_vexpand(False)
        self._label_userdb_entry.set_text(
            self._settings_dict['labeluserdbstring']['user'])
        self._label_userdb_entry.connect(
            'notify::text', self._on_label_userdb_entry)
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._label_userdb_checkbutton, 0, _appearance_grid_row, 1, 1)
        self._appearance_grid.attach(
            self._label_userdb_entry, 1, _appearance_grid_row, 1, 1)

        self._label_spellcheck_checkbutton = Gtk.CheckButton(
            # Translators: A checkbox where one can choose whether a
            # label is used to mark suggestions coming from spellchecking
            # in the candidate list.
            label=_('Use label for spellchecking suggestions'))
        self._label_spellcheck_checkbutton.set_tooltip_text(
            _('Here you can choose whether a label is used '
              'for candidates in the lookup table which '
              'come from spellchecking.'))
        self._label_spellcheck_checkbutton.set_hexpand(False)
        self._label_spellcheck_checkbutton.set_vexpand(False)
        self._label_spellcheck_checkbutton.set_active(
            self._settings_dict['labelspellcheck']['user'])
        self._label_spellcheck_checkbutton.connect(
            'clicked', self._on_label_spellcheck_checkbutton)
        self._label_spellcheck_entry = Gtk.Entry()
        self._label_spellcheck_entry.set_visible(True)
        self._label_spellcheck_entry.set_can_focus(True)
        self._label_spellcheck_entry.set_hexpand(False)
        self._label_spellcheck_entry.set_vexpand(False)
        self._label_spellcheck_entry.set_text(
            self._settings_dict['labelspellcheckstring']['user'])
        self._label_spellcheck_entry.connect(
            'notify::text', self._on_label_spellcheck_entry)
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._label_spellcheck_checkbutton, 0, _appearance_grid_row, 1, 1)
        self._appearance_grid.attach(
            self._label_spellcheck_entry, 1, _appearance_grid_row, 1, 1)

        self._label_dictionary_checkbutton = Gtk.CheckButton(
            # Translators: A checkbox where one can choose whether a
            # label is used to mark suggestions coming from a
            # dictionary in the candidate list.
            label=_('Use label for dictionary suggestions'))
        self._label_dictionary_checkbutton.set_tooltip_text(
            _('Here you can choose whether a label is used '
              'for candidates in the lookup table which '
              'come from a dictionary.'))
        self._label_dictionary_checkbutton.set_hexpand(False)
        self._label_dictionary_checkbutton.set_vexpand(False)
        self._label_dictionary_checkbutton.set_active(
            self._settings_dict['labeldictionary']['user'])
        self._label_dictionary_checkbutton.connect(
            'clicked', self._on_label_dictionary_checkbutton)
        self._label_dictionary_entry = Gtk.Entry()
        self._label_dictionary_entry.set_visible(True)
        self._label_dictionary_entry.set_can_focus(True)
        self._label_dictionary_entry.set_hexpand(False)
        self._label_dictionary_entry.set_vexpand(False)
        self._label_dictionary_entry.set_text(
            self._settings_dict['labeldictionarystring']['user'])
        self._label_dictionary_entry.connect(
            'notify::text', self._on_label_dictionary_entry)
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._label_dictionary_checkbutton, 0, _appearance_grid_row, 1, 1)
        self._appearance_grid.attach(
            self._label_dictionary_entry, 1, _appearance_grid_row, 1, 1)

        self._flag_dictionary_checkbutton = Gtk.CheckButton(
            # Translators: A checkbox where one can choose whether a
            # flags are added to mark suggestions coming from a
            # dictionary in the candidate list.
            label=_('Use flags for dictionary suggestions'))
        self._flag_dictionary_checkbutton.set_tooltip_text(
            _('Here you can choose whether flags are used for candidates in '
              'the lookup table which come from a dictionary.'))
        self._flag_dictionary_checkbutton.set_hexpand(False)
        self._flag_dictionary_checkbutton.set_vexpand(False)
        self._flag_dictionary_checkbutton.set_active(
            self._settings_dict['flagdictionary']['user'])
        self._flag_dictionary_checkbutton.connect(
            'clicked', self._on_flag_dictionary_checkbutton)
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._flag_dictionary_checkbutton, 0, _appearance_grid_row, 2, 1)

        self._label_busy_checkbutton = Gtk.CheckButton(
            # Translators: A checkbox where one can choose whether a
            # label is used to show when ibus-typing-booster is busy.
            label=_('Use a label to indicate busy state'))
        self._label_busy_checkbutton.set_tooltip_text(
            _('Here you can choose whether a label is used '
              'to indicate when ibus-typing-booster is busy.'))
        self._label_busy_checkbutton.set_hexpand(False)
        self._label_busy_checkbutton.set_vexpand(False)
        self._label_busy_checkbutton.set_active(
            self._settings_dict['labelbusy']['user'])
        self._label_busy_checkbutton.connect(
            'clicked', self._on_label_busy_checkbutton)
        self._label_busy_entry = Gtk.Entry()
        self._label_busy_entry.set_visible(True)
        self._label_busy_entry.set_can_focus(True)
        self._label_busy_entry.set_hexpand(False)
        self._label_busy_entry.set_vexpand(False)
        self._label_busy_entry.set_text(
            self._settings_dict['labelbusystring']['user'])
        self._label_busy_entry.connect(
            'notify::text', self._on_label_busy_entry)
        _appearance_grid_row += 1
        self._appearance_grid.attach(
            self._label_busy_checkbutton, 0, _appearance_grid_row, 1, 1)
        self._appearance_grid.attach(
            self._label_busy_entry, 1, _appearance_grid_row, 1, 1)

        self._google_application_credentials_label = Gtk.Label()
        self._google_application_credentials_label.set_text(
            # Translators:
            _('Set “Google application credentials” .json file:'))
        self._google_application_credentials_label.set_tooltip_text(
            _('Full path of the “Google application credentials” .json file.'))
        self._google_application_credentials_label.set_xalign(0)
        self._speech_recognition_grid.attach(
            self._google_application_credentials_label, 0, 0, 1, 1)
        if not self._settings_dict['googleapplicationcredentials']['user']:
            self._settings_dict['googleapplicationcredentials'][
                'user'] = _('File not yet set.')
        self._google_application_credentials_button = Gtk.Button()
        self._google_application_credentials_button_box = Gtk.Box()
        self._google_application_credentials_button_label = Gtk.Label()
        self._google_application_credentials_button_label.set_text(
            self._settings_dict['googleapplicationcredentials']['user'])
        self._google_application_credentials_button_label.set_use_markup(True)
        self._google_application_credentials_button_label.set_max_width_chars(
            40)
        self._google_application_credentials_button_label.set_line_wrap(False)
        self._google_application_credentials_button_label.set_ellipsize(
            Pango.EllipsizeMode.START)
        self._google_application_credentials_button_box.add(
            self._google_application_credentials_button_label)
        self._google_application_credentials_button.add(
            self._google_application_credentials_button_box)
        self._speech_recognition_grid.attach(
            self._google_application_credentials_button, 1, 0, 1, 1)
        self._google_application_credentials_button.connect(
            'clicked', self._on_google_application_credentials_button)

        autosettings_label = Gtk.Label()
        autosettings_label.set_text(
            # Translators: This is the header of the list of settings
            # changed automatically depending on the which window has
            # focus:
            '<b>' + _('Autosettings') + '</b>')
        autosettings_label.set_use_markup(True)
        margin = 5
        autosettings_label.set_margin_start(margin)
        autosettings_label.set_margin_end(margin)
        autosettings_label.set_margin_top(margin)
        autosettings_label.set_margin_bottom(margin)
        autosettings_label.set_hexpand(False)
        autosettings_label.set_vexpand(False)
        autosettings_label.set_xalign(0)
        self._autosettings_vbox.add(autosettings_label)
        self._autosettings_scroll = Gtk.ScrolledWindow()
        self._autosettings_scroll.set_hexpand(True)
        self._autosettings_scroll.set_vexpand(True)
        self._autosettings_scroll.set_kinetic_scrolling(False)
        self._autosettings_scroll.set_overlay_scrolling(True)
        self._autosettings_scroll.set_shadow_type(Gtk.ShadowType.IN)
        self._autosettings_vbox.add(self._autosettings_scroll)
        autosettings_action_area = Gtk.Box()
        autosettings_action_area.set_orientation(
            Gtk.Orientation.HORIZONTAL)
        autosettings_action_area.set_can_focus(False)
        self._autosettings_vbox.add(autosettings_action_area)
        self._autosettings_add_button =  Gtk.Button()
        autosettings_add_button_label = Gtk.Label()
        autosettings_add_button_label.set_text(
            '<span size="xx-large"><b>+</b></span>')
        autosettings_add_button_label.set_use_markup(True)
        self._autosettings_add_button.add(autosettings_add_button_label)
        # Translators: This is a button to add an autosetting.
        # “Autosettings” are settings which may change automatically
        # to specific values depending on which window (or which
        # browser tab) gets the focus.
        self._autosettings_add_button.set_tooltip_text(_('Add an autosetting'))
        self._autosettings_add_button.connect(
            'clicked', self._on_autosettings_add_button_clicked)
        self._autosettings_add_button.set_sensitive(True)
        self._autosettings_remove_button =  Gtk.Button()
        autosettings_remove_button_label = Gtk.Label()
        autosettings_remove_button_label.set_text(
            '<span size="xx-large"><b>-</b></span>')
        autosettings_remove_button_label.set_use_markup(True)
        self._autosettings_remove_button.add(autosettings_remove_button_label)
        # Translators: This is a button to remove an autosetting.
        # “Autosettings” are settings which may change automatically
        # to specific valueS depending on which window (or which
        # browser tab) gets the focus.
        self._autosettings_remove_button.set_tooltip_text(_('Remove an autosetting'))
        self._autosettings_remove_button.connect(
            'clicked', self._on_autosettings_remove_button_clicked)
        self._autosettings_remove_button.set_sensitive(False)
        self._autosettings_up_button =  Gtk.Button()
        autosettings_up_button_label = Gtk.Label()
        autosettings_up_button_label.set_text(
            '<span size="xx-large"><b>↑</b></span>')
        autosettings_up_button_label.set_use_markup(True)
        self._autosettings_up_button.add(autosettings_up_button_label)
        # Translators: This is a button to move an autosetting up in the
        # order the autosettings are applied. “Up” means it is applied
        # earlier. The order in which autosettings
        # are applied is important because settings applied later might
        # override settings applied earlier.
        # “Autosettings” are settings which may change automatically
        # to specific valueS depending on which window (or which
        # browser tab) gets the focus.
        self._autosettings_up_button.set_tooltip_text(_('Move an autosetting up'))
        self._autosettings_up_button.connect(
            'clicked', self._on_autosettings_up_button_clicked)
        self._autosettings_up_button.set_sensitive(False)
        self._autosettings_down_button =  Gtk.Button()
        autosettings_down_button_label = Gtk.Label()
        autosettings_down_button_label.set_text(
            '<span size="xx-large"><b>↓</b></span>')
        autosettings_down_button_label.set_use_markup(True)
        self._autosettings_down_button.add(autosettings_down_button_label)
        # Translators: This is a button to move an autosetting down in the
        # order the autosettings are applied. “Down” means it is applied
        # later. The order in which autosettings
        # are applied is important because settings applied later might
        # override settings applied earlier.
        # “Autosettings” are settings which may change automatically
        # to specific valueS depending on which window (or which
        # browser tab) gets the focus.
        self._autosettings_down_button.set_tooltip_text(_('Move an autosetting down'))
        self._autosettings_down_button.connect(
            'clicked', self._on_autosettings_down_button_clicked)
        self._autosettings_down_button.set_sensitive(False)
        autosettings_action_area.add(self._autosettings_add_button)
        autosettings_action_area.add(self._autosettings_remove_button)
        autosettings_action_area.add(self._autosettings_up_button)
        autosettings_action_area.add(self._autosettings_down_button)
        self._autosettings_selected_index = -1
        self._autosettings_treeview = None
        self._autosettings_add_listbox = None
        self._autosettings_add_listbox_settings: List[str] = []
        self._autosettings_add_popover = None
        self._autosettings_add_popover_scroll = None
        self._fill_autosettings_treeview()

        self.show_all() # pylint: disable=no-member

        self._notebook.set_current_page(0) # Has to be after show_all()

        if not self._settings_dict[
                'keybindings']['user']['toggle_input_mode_on_off']:
            self._remember_input_mode_checkbutton.hide()

        self._gsettings.connect('changed', self._on_gsettings_value_changed)

    def _init_settings_dict(self) -> Dict[str, Any]:
        '''Initialize a dictionary with the default and user settings for all
        settings keys.

        The default settings start with the defaults from the
        gsettings schema. Some of these generic default values may be
        overridden by more specific default settings for the specific engine.
        After this possible modification for a specific engine we have the final default
        settings for this specific typing booster input method.

        The user settings start with a copy of these final default settings,
        then they are possibly modified by user gsettings.

        Keeping a copy of the default settings in the settings dictionary
        makes it easy to revert some or all settings to the defaults.
        '''
        settings_dict: Dict[str, Any] = {}
        set_functions = {
            'disableinterminals': self.set_disable_in_terminals,
            'asciidigits': self.set_ascii_digits,
            'avoidforwardkeyevent': self.set_avoid_forward_key_event,
            'addspaceoncommit': self.set_add_space_on_commit,
            'arrowkeysreopenpreedit': self.set_arrow_keys_reopen_preedit,
            'emojipredictions': self.set_emoji_prediction_mode,
            'offtherecord': self.set_off_the_record_mode,
            'recordmode': self.set_record_mode,
            'emojitriggercharacters': self.set_emoji_trigger_characters,
            'autocommitcharacters': self.set_auto_commit_characters,
            'googleapplicationcredentials':
            self.set_google_application_credentials,
            'tabenable': self.set_tab_enable,
            'inlinecompletion': self.set_inline_completion,
            'autocapitalize': self.set_auto_capitalize,
            'rememberlastusedpreeditime':
            self.set_remember_last_used_preedit_ime,
            'rememberinputmode': self.set_remember_input_mode,
            'pagesize': self.set_page_size,
            'candidatesdelaymilliseconds':
            self.set_candidates_delay_milliseconds,
            'lookuptableorientation': self.set_lookup_table_orientation,
            'preeditunderline': self.set_preedit_underline,
            'preeditstyleonlywhenlookup':
            self.set_preedit_style_only_when_lookup,
            'mincharcomplete': self.set_min_char_complete,
            'errorsound': self.set_error_sound,
            'errorsoundfile': self.set_error_sound_file,
            'soundbackend': self.set_sound_backend,
            'debuglevel': self.set_debug_level,
            'shownumberofcandidates': self.set_show_number_of_candidates,
            'showstatusinfoinaux': self.set_show_status_info_in_auxiliary_text,
            'autoselectcandidate': self.set_auto_select_candidate,
            'colorpreeditspellcheck': self.set_color_preedit_spellcheck,
            'colorpreeditspellcheckstring':
            self.set_color_preedit_spellcheck_string,
            'colorinlinecompletion': self.set_color_inline_completion,
            'colorinlinecompletionstring':
            self.set_color_inline_completion_string,
            'colorcomposepreview': self.set_color_compose_preview,
            'colorcomposepreviewstring': self.set_color_compose_preview_string,
            'coloruserdb': self.set_color_userdb,
            'coloruserdbstring': self.set_color_userdb_string,
            'colorspellcheck': self.set_color_spellcheck,
            'colorspellcheckstring': self.set_color_spellcheck_string,
            'colordictionary': self.set_color_dictionary,
            'colordictionarystring': self.set_color_dictionary_string,
            'labeluserdb': self.set_label_userdb,
            'labeluserdbstring': self.set_label_userdb_string,
            'labelspellcheck': self.set_label_spellcheck,
            'labelspellcheckstring': self.set_label_spellcheck_string,
            'labeldictionary': self.set_label_dictionary,
            'labeldictionarystring': self.set_label_dictionary_string,
            'flagdictionary': self.set_flag_dictionary,
            'labelbusy': self.set_label_busy,
            'labelbusystring': self.set_label_busy_string,
            'inputmethod': self.set_current_imes,
            'dictionary': self.set_dictionary_names,
            'keybindings': self.set_keybindings,
            'dictionaryinstalltimestamp': self._reload_dictionaries,
            'inputmethodchangetimestamp': self._reload_input_methods,
            'autosettings': self.set_autosettings,
        }

        schema_source: Gio.SettingsSchemaSource = (
            Gio.SettingsSchemaSource.get_default())
        schema: Gio.SettingsSchema = schema_source.lookup(
            'org.freedesktop.ibus.engine.typing-booster', True)
        special_defaults = {
            'dictionary': 'None',  # special dummy dictionary
            'inputmethod': f'{self._m17n_ime_lang}-{self._m17n_ime_name}',
            'tabenable': True,
            'offtherecord': True,
            'preeditunderline': 0,
        }
        for key in schema.list_keys():
            if key == 'keybindings': # keybindings are special!
                default_value = itb_util.variant_to_value(
                    self._gsettings.get_default_value('keybindings'))
                if self._engine_name != 'typing-booster':
                    default_value['toggle_input_mode_on_off'] = []
                    default_value['enable_lookup'] = []
                    default_value['commit_and_forward_key'] = ['Left']
                # copy the updated default keybindings, i.e. the
                # default keybindings for this specific engine, into
                # the user keybindings:
                user_value = copy.deepcopy(default_value)
                user_gsettings = itb_util.variant_to_value(
                    self._gsettings.get_user_value(key))
                if not user_gsettings:
                    user_gsettings = {}
                itb_util.dict_update_existing_keys(user_value, user_gsettings)
            else:
                default_value = itb_util.variant_to_value(
                    self._gsettings.get_default_value(key))
                if self._engine_name != 'typing-booster':
                    default_value = special_defaults.get(key, default_value)
                user_value = itb_util.variant_to_value(
                    self._gsettings.get_user_value(key))
                if user_value is None:
                    user_value = default_value
            if key in set_functions:
                settings_dict[key] = {
                    'default': default_value,
                    'user': user_value,
                    'set_function': set_functions[key]}
        return settings_dict

    def _fill_dictionaries_listbox_row(self, name: str) -> Tuple[str, bool]:
        '''
        Formats the text of a line in the listbox of configured dictionaries

        Returns a tuple consisting of the formatted line of text
        and a Boolean indicating whether the hunspell dictionary
        is missing.

        :param name: Name of the hunspell dictionary
        '''
        missing_dictionary = False
        flag = itb_util.get_flag(name)
        row = name + ' ' + flag
        if itb_util.is_right_to_left_messages():
            # Add U+200E LEFT-TO-RIGHT MARK to name and flag:
            row = chr(0x200F) + name + ' ' + chr(0x200F) + flag + ' '
        language_description = itb_util.locale_language_description(name)
        if language_description:
            row += ' ' + language_description
        row += ':  '
        row_item = ' ' + _('Spell checking') + ' '
        if name.split('_')[0] != 'fi':
            (dic_path,
             dummy_aff_path) = itb_util.find_hunspell_dictionary(name)
            if dic_path:
                row_item += '✔️'
            else:
                row_item += '❌'
                missing_dictionary = True
        else:
            if IMPORT_LIBVOIKKO_SUCCESSFUL:
                row_item += '✔️'
            else:
                row_item += '❌'
                missing_dictionary = True
        row += itb_util.bidi_embed(row_item)
        row_item = ' ' + _('Emoji') + ' '
        if itb_emoji.find_cldr_annotation_path(name):
            row_item += '✔️'
        else:
            row_item += '❌'
        row += itb_util.bidi_embed(row_item)
        if self._settings_dict['keybindings']['user']['speech_recognition']:
            row_item = ' ' + _('Speech recognition') + ' '
            if name in itb_util.GOOGLE_SPEECH_TO_TEXT_LANGUAGES:
                row_item += '✔️'
            else:
                row_item += '❌'
            row += itb_util.bidi_embed(row_item)
        return (row, missing_dictionary)

    def _fill_dictionaries_listbox(self) -> None:
        '''
        Fill the dictionaries listbox with the list of dictionaries read
        from dconf.
        '''
        for child in self._dictionaries_scroll.get_children():
            self._dictionaries_scroll.remove(child)
        self._dictionaries_listbox = Gtk.ListBox()
        if self._dictionaries_listbox is None:
            LOGGER.debug('self._dictionaries_listbox is None')
            return
        self._dictionaries_scroll.add(self._dictionaries_listbox)
        self._dictionaries_listbox_selected_dictionary_name = ''
        self._dictionaries_listbox_selected_dictionary_index = -1
        self._dictionaries_listbox.set_visible(True)
        self._dictionaries_listbox.set_vexpand(True)
        self._dictionaries_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._dictionaries_listbox.set_activate_on_single_click(True)
        self._dictionaries_listbox.connect(
            'row-selected', self._on_dictionary_selected)
        missing_dictionaries = False
        if list(self._dictionary_names) != ['None']:
            for name in self._dictionary_names:
                label = Gtk.Label()
                (text,
                 missing_dictionary) = self._fill_dictionaries_listbox_row(
                     name)
                if missing_dictionary:
                    missing_dictionaries = True
                label.set_text(html.escape(text))
                label.set_use_markup(True)
                label.set_xalign(0)
                margin = 1
                label.set_margin_start(margin)
                label.set_margin_end(margin)
                label.set_margin_top(margin)
                label.set_margin_bottom(margin)
                self._dictionaries_listbox.insert(label, -1)
        self._dictionaries_listbox.show_all()
        self._dictionaries_install_missing_button.set_sensitive(
            missing_dictionaries)
        self._dictionaries_add_button.set_sensitive(
            len(self._dictionary_names)
            < itb_util.MAXIMUM_NUMBER_OF_DICTIONARIES)

    @staticmethod
    def _fill_input_methods_listbox_row(ime: str) -> str:
        '''
        Formats the text of a line in the listbox of configured input methods

        Returns the formatted line of text.

        :param ime: Name of the input method
        '''
        row = ime
        if itb_util.is_right_to_left_messages():
            # start the row with U+200E LEFT-TO-RIGHT MARK
            row = chr(0x200F) + ime
        # add some spaces for nicer formatting:
        row += ' ' * (20 - len(ime))
        title = ''
        if M17N_DB_INFO is not None:
            title = M17N_DB_INFO.get_title(ime)
        if title:
            row += '\t' + '(' + title + ')'
        try:
            dummy = m17n_translit.Transliterator(ime)
            row += '\t' + '✔️'
        except ValueError as open_error:
            row += '\t' + '❌ ' + str(open_error)
        return row

    def _fill_input_methods_listbox(self) -> None:
        '''
        Fill the input methods listbox with the list of input methods read
        from dconf.
        '''
        for child in self._input_methods_scroll.get_children():
            self._input_methods_scroll.remove(child)
        self._input_methods_listbox = Gtk.ListBox()
        if self._input_methods_listbox is None:
            LOGGER.debug('self._input_methods_listbox is None')
            return
        self._input_methods_scroll.add(self._input_methods_listbox)
        self._input_methods_listbox_selected_ime_name = ''
        self._input_methods_listbox_selected_ime_index = -1
        self._input_methods_listbox.set_visible(True)
        self._input_methods_listbox.set_vexpand(True)
        self._input_methods_listbox.set_selection_mode(
            Gtk.SelectionMode.SINGLE)
        self._input_methods_listbox.set_activate_on_single_click(True)
        self._input_methods_listbox.connect(
            'row-selected', self._on_input_method_selected)
        for ime in self._current_imes:
            label = Gtk.Label()
            label.set_text(html.escape(
                self._fill_input_methods_listbox_row(ime)))
            label.set_use_markup(True)
            label.set_xalign(0)
            margin = 1
            label.set_margin_start(margin)
            label.set_margin_end(margin)
            label.set_margin_top(margin)
            label.set_margin_bottom(margin)
            icon_size = 48
            try:
                pixbuf = Gtk.IconTheme.get_default( # pylint: disable=no-member
                ).load_icon('image-missing', icon_size, 0)
            except (GLib.GError,) as error:
                LOGGER.exception(
                    'Exception when loading "image-missing" icon %s: %s',
                    error.__class__.__name__, error)
                pixbuf = GdkPixbuf.Pixbuf()
            icon_file = M17N_DB_INFO.get_icon(ime)
            if icon_file:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    icon_file, icon_size, icon_size, True)
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            hbox = Gtk.Box()
            hbox.set_orientation(Gtk.Orientation.HORIZONTAL)
            hbox.set_spacing(10)
            hbox.add(image)
            hbox.add(label)
            self._input_methods_listbox.insert(hbox, -1)
        self._input_methods_listbox.show_all()
        self._input_methods_add_button.set_sensitive(
            len(self._current_imes) < itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS)

    def _fill_autosettings_treeview(self) -> None:
        '''
        Fill the autosettings treeview with the autosettings read from dconf
        '''
        # In case a previously created treeview exists already, set
        # the selection mode to NONE in order to avoid that selection
        # changed events still get called while the previously created
        # treeview and its model are destroyed:
        if self._autosettings_treeview is not None:
            self._autosettings_treeview.get_selection().set_mode(
            Gtk.SelectionMode.NONE)
        for child in self._autosettings_scroll.get_children():
            self._autosettings_scroll.remove(child)
        self._autosettings_treeview = Gtk.TreeView()
        if self._autosettings_treeview is None:
            LOGGER.debug('self._autosettings_treeview is None')
            return
        self._autosettings_treeview.get_selection().set_mode(
            Gtk.SelectionMode.NONE)
        self._autosettings_treeview.set_can_focus(True)
        self._autosettings_treeview.set_has_tooltip(True)
        self._autosettings_treeview.set_grid_lines(Gtk.TreeViewGridLines.BOTH)
        autosettings_treeview_model = Gtk.ListStore(str, str, str, str)
        self._autosettings_treeview.set_model(autosettings_treeview_model)
        autosettings_user = self._settings_dict['autosettings']['user']
        for (setting, value, regexp) in autosettings_user:
            value_hint = ''
            if (setting in self._allowed_autosettings
                and 'value_hint' in self._allowed_autosettings[setting]):
                value_hint = self._allowed_autosettings[setting]['value_hint']
            autosettings_treeview_model.append((
                setting, value, regexp, value_hint))
        autosettings_treeview_column_0 = Gtk.TreeViewColumn(
            # Translators: Column heading of the table listing
            # the automatic settings
            _('Setting'),
            Gtk.CellRendererText(),
            text=0)
        self._autosettings_treeview.append_column(
            autosettings_treeview_column_0)
        autosettings_value_renderer = Gtk.CellRendererText()
        autosettings_treeview_column_1 = Gtk.TreeViewColumn(
            # Translators: Column heading of the table listing
            # the automatic settings
            _('Value'),
            autosettings_value_renderer,
            text=1)
        self._autosettings_treeview.append_column(
            autosettings_treeview_column_1)
        autosettings_value_renderer.set_property('editable', True)
        def set_placeholder_text( # pylint: disable=unused-argument
                column: Gtk.TreeViewColumn,
                cell: Gtk.CellRendererText,
                model: Gtk.TreeModel,
                row_iter: Gtk.TreeIter,
                data=None) -> None:
            placeholder_text: str = model.get_value(row_iter, 3)
            cell.set_property('placeholder-text', placeholder_text)
        autosettings_treeview_column_1.set_cell_data_func(
            autosettings_value_renderer, set_placeholder_text)
        autosettings_value_renderer.connect(
            'edited',
            self._on_autosettings_treeview_value_edited,
            autosettings_treeview_model)
        autosettings_regexp_renderer = Gtk.CellRendererText()
        autosettings_treeview_column_2 = Gtk.TreeViewColumn(
            # Translators: Column heading of the table listing
            # the automatic settings
            _('Regular expression'),
            autosettings_regexp_renderer,
            text=2)
        self._autosettings_treeview.append_column(
            autosettings_treeview_column_2)
        autosettings_regexp_renderer.set_property('editable', True)
        autosettings_regexp_renderer.connect(
            'edited',
            self._on_autosettings_treeview_regexp_edited,
            autosettings_treeview_model)
        self._autosettings_scroll.add(self._autosettings_treeview)
        self._autosettings_treeview.get_selection().connect(
            'changed', self._on_autosettings_treeview_row_selected)
        self._autosettings_treeview.connect(
            'row-activated', self._on_autosettings_treeview_row_activated)
        self._autosettings_treeview.get_selection().set_mode(
            Gtk.SelectionMode.SINGLE)
        index = self._autosettings_selected_index
        LOGGER.debug('Selecting index %s', index)
        tree_path = Gtk.TreePath.new_from_indices([index])
        # Triggers a call to self._on_autosettings_treeview_row_selected()
        # which fixes up the state of the buttons:
        self._autosettings_treeview.get_selection().select_path(tree_path)
        self._autosettings_treeview.show()

    @staticmethod
    def __run_message_dialog(
            message: str,
            message_type: Gtk.MessageType = Gtk.MessageType.INFO) -> None:
        '''Run a dialog to show an error or warning message'''
        dialog = Gtk.MessageDialog(
            flags=Gtk.DialogFlags.MODAL,
            message_type=message_type,
            buttons=Gtk.ButtonsType.OK,
            message_format=message)
        dialog.run()
        dialog.destroy()

    def _run_are_you_sure_dialog(self, message: str) -> Any:
        '''
        Run a dialog to show a “Are you sure?” message.

        Returns Gtk.ResponseType.OK or Gtk.ResponseType.CANCEL
        :rtype: Gtk.ResponseType (enum)
        '''
        confirm_question = Gtk.Dialog(
            title=_('Are you sure?'),
            parent=self)
        confirm_question.add_button(_('_Cancel'), Gtk.ResponseType.CANCEL)
        confirm_question.add_button(_('_OK'), Gtk.ResponseType.OK)
        box = confirm_question.get_content_area()
        label = Gtk.Label()
        label.set_text(
            '<span size="large" color="#ff0000"><b>'
            + html.escape(message)
            + '</b></span>')
        label.set_use_markup(True)
        label.set_max_width_chars(40)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_xalign(0)
        margin = 10
        label.set_margin_start(margin)
        label.set_margin_end(margin)
        label.set_margin_top(margin)
        label.set_margin_bottom(margin)
        box.add(label)
        confirm_question.show_all()
        response = confirm_question.run()
        confirm_question.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration()
        return response

    def check_instance(self) -> bool:
        '''
        Check whether another instance of the setup tool is running already
        '''
        if (dbus.SessionBus().request_name("org.ibus.typingbooster")
                != dbus.bus.REQUEST_NAME_REPLY_PRIMARY_OWNER):
            self.__run_message_dialog(
                _("Another instance of this app is already running."),
                Gtk.MessageType.ERROR)
            sys.exit(1)
        else:
            return False

    @staticmethod
    def _on_delete_event(*_args: Any) -> None:
        '''
        The window has been deleted, probably by the window manager.
        '''
        Gtk.main_quit()

    @staticmethod
    def _on_destroy_event(*_args: Any) -> None:
        '''
        The window has been destroyed.
        '''
        Gtk.main_quit()

    @staticmethod
    def _on_close_clicked(*_args: Any) -> None:
        '''
        The button to close the dialog has been clicked.
        '''
        Gtk.main_quit()

    # pylint: disable=unused-argument
    @staticmethod
    def _reload_dictionaries(
            value: Any, update_gsettings: bool = False) -> None:
        '''(re)load all dictionaries

        Called when a dictionary has been updated or installed.

        :param value: ignored
        :param update_gsettings: ignored
        '''
        LOGGER.info('A dictionary has been updated or installed.\n'
                    'ibus-typing-booster will (re)load all dictionaries.\n'
                    'But here in the setup tool there is nothing to do.')
    # pylint: enable=unused-argument

    # pylint: disable=unused-argument
    @staticmethod
    def _reload_input_methods(
            value: Any, update_gsettings: bool = False) -> None:
        '''(re)load all input methods

        Called when an input method has been changed,
        usually because an optional variable of an input method was changed.

        :param value: ignored
        :param update_gsettings: ignored
        '''
        LOGGER.info('A input method has been changed.\n'
                    'ibus-typing-booster will (re)load all input methods.\n'
                    'But here in the setup tool there is nothing to do.')
    # pylint: enable=unused-argument

    def _on_gsettings_value_changed(
            self, _settings: Gio.Settings, key: str) -> None:
        '''
        Called when a value in the settings has been changed.

        :param settings: The settings object
        :param key: The key of the setting which has changed
        '''
        value = itb_util.variant_to_value(self._gsettings.get_value(key))
        LOGGER.info('Settings changed: key=%s value=%s\n', key, value)
        if key in self._settings_dict:
            set_function = self._settings_dict[key]['set_function']
            if set_function:
                set_function(value, update_gsettings=False)
            return
        LOGGER.error('Unknown key=%s', key)
        return

    @staticmethod
    def _on_about_button_clicked(_button: Gtk.Button) -> None:
        '''
        The “About” button has been clicked

        :param _button: The “About” button
        '''
        itb_util.ItbAboutDialog()

    def _on_restore_all_defaults_button_clicked(
            self, _button: Gtk.Button) -> None:
        '''
        Restore all default settings
        '''
        self._restore_all_defaults_button.set_sensitive(False)
        response = self._run_are_you_sure_dialog(
            # Translators: This is the text in the centre of a small
            # dialog window, trying to confirm whether the user is
            # really sure to restore all default settings.
            _('Do you really want to restore all default settings?'))
        if response == Gtk.ResponseType.OK:
            LOGGER.info('Restoring all defaults.')
            for key, value in self._settings_dict.items():
                if key in ('googleapplicationcredentials',
                           'inputmethodchangetimestamp',
                           'dictionaryinstalltimestamp'):
                    LOGGER.info('Skipping reset of gsettings key=%s', key)
                    continue
                LOGGER.info('Resetting gsettings key=%s', key)
                value['set_function'](value['default'], update_gsettings=True)
                # Call it again with update_gsettings=False to make
                # sure the active state of checkbuttons etc.  is
                # updated immediately:
                value['set_function'](value['default'], update_gsettings=False)
        else:
            LOGGER.info('Restore all defaults cancelled.')
        self._restore_all_defaults_button.set_sensitive(True)

    def _on_color_preedit_spellcheck_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to do spellchecking on the
        contents of the preedit.

        :param widget: The check button clicked
        '''
        self.set_color_preedit_spellcheck(
            widget.get_active(), update_gsettings=True)

    def _on_color_preedit_spellcheck_color_set(
            self, widget: Gtk.ColorButton) -> None:
        '''
        A color has been set to indicate spelling errors in the preedit

        :param widget: The color button where a color was set
        '''
        self.set_color_preedit_spellcheck_string(
            widget.get_rgba().to_string(), update_gsettings=True)

    def _on_color_inline_completion_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to use color for inline completion
        has been clicked.

        :param widget: The check button clicked
        '''
        self.set_color_inline_completion(
            widget.get_active(), update_gsettings=True)

    def _on_color_inline_completion_color_set(
            self, widget: Gtk.ColorButton) -> None:
        '''
        A color has been set for the inline completion

        :param widget: The color button where a color was set
        '''
        self.set_color_inline_completion_string(
            widget.get_rgba().to_string(), update_gsettings=True)

    def _on_color_compose_preview_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to use color for the compose preview
        has been clicked.

        :param widget: The check button clicked
        '''
        self.set_color_compose_preview(
            widget.get_active(), update_gsettings=True)

    def _on_color_compose_preview_color_set(
            self, widget: Gtk.ColorButton) -> None:
        '''
        A color has been set for the compose preview

        :param widget: The color button where a color was set
        '''
        self.set_color_compose_preview_string(
            widget.get_rgba().to_string(), update_gsettings=True)

    def _on_color_userdb_checkbutton(self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to use color for candidates from the user
        database has been clicked.

        :param widget: The check button clicked
        '''
        self.set_color_userdb(widget.get_active(), update_gsettings=True)

    def _on_color_userdb_color_set(self, widget: Gtk.ColorButton) -> None:
        '''
        A color has been set for the candidates from the user database.

        :param widget: The color button where a color was set
        '''
        self.set_color_userdb_string(
            widget.get_rgba().to_string(), update_gsettings=True)

    def _on_color_spellcheck_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to use color for candidates from spellchecking
        has been clicked.

        :param widget: The check button clicked
        '''
        self.set_color_spellcheck(widget.get_active(), update_gsettings=True)

    def _on_color_spellcheck_color_set(self, widget: Gtk.ColorButton) -> None:
        '''
        A color has been set for the candidates from spellchecking

        :param widget: The color button where a color was set
        '''
        self.set_color_spellcheck_string(
            widget.get_rgba().to_string(), update_gsettings=True)

    def _on_color_dictionary_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to use color for candidates from a dictionary
        has been clicked.

        :param widget: The check button clicked
        '''
        self.set_color_dictionary(widget.get_active(), update_gsettings=True)

    def _on_color_dictionary_color_set(self, widget: Gtk.ColorButton) -> None:
        '''
        A color has been set for the candidates from a dictionary

        :param widget: The color button where a color was set
        '''
        self.set_color_dictionary_string(
            widget.get_rgba().to_string(), update_gsettings=True)

    def _on_label_userdb_checkbutton(self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to use a label for candidates from the
        user database has been clicked.

        :param widget: The check button clicked
        '''
        self.set_label_userdb(widget.get_active(), update_gsettings=True)

    def _on_label_userdb_entry(
            self, widget: Gtk.Entry, _property_spec: Any) -> None:
        '''
        The label for candidates from the user database has been changed.
        '''
        self.set_label_userdb_string(
            widget.get_text(), update_gsettings=True)

    def _on_label_spellcheck_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to use a label for candidates from
        spellchecking has been clicked.

        :param widget: The check button clicked
        '''
        self.set_label_spellcheck(widget.get_active(), update_gsettings=True)

    def _on_label_spellcheck_entry(
            self, widget: Gtk.Entry, _property_spec: Any) -> None:
        '''
        The label for candidates from spellchecking has been changed.
        '''
        self.set_label_spellcheck_string(
            widget.get_text(), update_gsettings=True)

    def _on_label_dictionary_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to use a label for candidates from a dictionary
        has been clicked.

        :param widget: The check button clicked
        '''
        self.set_label_dictionary(widget.get_active(), update_gsettings=True)

    def _on_label_dictionary_entry(
            self, widget: Gtk.Entry, _property_spec: Any) -> None:
        '''
        The label for candidates from a dictionary has been changed.
        '''
        self.set_label_dictionary_string(
            widget.get_text(), update_gsettings=True)

    def _on_flag_dictionary_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to use flags for candidates from a dictionary
        has been clicked.

        :param widget: The check button clicked
        '''
        self.set_flag_dictionary(widget.get_active(), update_gsettings=True)

    def _on_label_busy_checkbutton(self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to use a label to indicate when
        ibus-typing-booster is busy.

        :param widget: The check button clicked
        '''
        self.set_label_busy(widget.get_active(), update_gsettings=True)

    def _on_label_busy_entry(
            self, widget: Gtk.Entry, _property_spec: Any) -> None:
        '''
        The label to indicate when ibus-typing-booster is busy
        '''
        self.set_label_busy_string(
            widget.get_text(), update_gsettings=True)

    def _on_tab_enable_checkbutton(self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to show candidates only when
        requested with the tab key or not has been clicked.
        '''
        self.set_tab_enable(
            widget.get_active(), update_gsettings=True)

    def _on_inline_completion_combobox_changed(
            self, widget: Gtk.ComboBox) -> None:
        '''
        A change of the inline completion mode has been requested
        with the combobox.
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            mode = model[tree_iter][1]
            self.set_inline_completion(
                mode, update_gsettings=True)

    def _on_record_mode_combobox_changed(
            self, widget: Gtk.ComboBox) -> None:
        '''
        A change of the record mode has been requested
        with the combobox.
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            mode = model[tree_iter][1]
            self.set_record_mode(
                mode, update_gsettings=True)

    def _on_auto_capitalize_checkbutton(self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to automatically capitalize after punctation.
        '''
        self.set_auto_capitalize(
            widget.get_active(), update_gsettings=True)

    def _on_show_number_of_candidates_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to show the number of candidates
        on top of the lookup table has been clicked.
        '''
        self.set_show_number_of_candidates(
            widget.get_active(), update_gsettings=True)

    def _on_show_status_info_in_auxiliary_text_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to show status in the auxiliary text,
        has been clicked.
        '''
        self.set_show_status_info_in_auxiliary_text(
            widget.get_active(), update_gsettings=True)

    def _on_preedit_style_only_when_lookup_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to style the preedit only when
        lookup is enabled has been clicked.
        '''
        self.set_preedit_style_only_when_lookup(
            widget.get_active(), update_gsettings=True)

    def _on_auto_select_candidate_combobox_changed(
            self, widget: Gtk.ComboBox) -> None:
        '''
        A change of the auto select mode has been requested
        with the combobox.
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            mode = model[tree_iter][1]
            self.set_auto_select_candidate(
                mode, update_gsettings=True)

    def _on_add_space_on_commit_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to add a space when committing by
        label or mouse click.
        '''
        self.set_add_space_on_commit(
            widget.get_active(), update_gsettings=True)

    def _on_remember_last_used_preedit_ime_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to remember the last used input method
        for the preëdit has been clicked.
        '''
        self.set_remember_last_used_preedit_ime(
            widget.get_active(), update_gsettings=True)

    def _on_remember_input_mode_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''The checkbutton whether to remember the last used input mode.'''
        self.set_remember_input_mode(
            widget.get_active(), update_gsettings=True)

    def _on_emoji_predictions_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to predict emoji as well or not
        has been clicked.
        '''
        self.set_emoji_prediction_mode(
            widget.get_active(), update_gsettings=True)

    def _on_off_the_record_checkbutton(self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to use “Off the record” mode, i.e. whether to
        learn from user data by saving user input to the user database
        or not, has been clicked.
        '''
        self.set_off_the_record_mode(
            widget.get_active(), update_gsettings=True)

    def _on_avoid_forward_key_event_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to avoid forward_key_event() has been clicked.
        '''
        self.set_avoid_forward_key_event(
            widget.get_active(), update_gsettings=True)

    def _on_arrow_keys_reopen_preedit_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether arrow keys are allowed to reopen
        a preëdit, has been clicked.
        '''
        self.set_arrow_keys_reopen_preedit(
            widget.get_active(), update_gsettings=True)

    def _on_disable_in_terminals_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to disable Typing Booster in terminals
        has been clicked.
        '''
        self.set_disable_in_terminals(
            widget.get_active(), update_gsettings=True)

    def _on_ascii_digits_checkbutton(
            self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to convert language specific
        digits to ASCII digits has been clicked.
        '''
        self.set_ascii_digits(
            widget.get_active(), update_gsettings=True)

    def _on_emoji_trigger_characters_entry(
            self, widget: Gtk.Entry, _property_spec: Any) -> None:
        '''
        The list of characters triggering emoji and Unicode symbol lookup
        '''
        self.set_emoji_trigger_characters(
            widget.get_text(), update_gsettings=True)

    def _on_auto_commit_characters_entry(
            self, widget: Gtk.Entry, _property_spec: Any) -> None:
        '''
        The list of characters triggering an auto commit has been changed.
        '''
        self.set_auto_commit_characters(
            widget.get_text(), update_gsettings=True)

    def _on_google_application_credentials_button(
            self, _widget: Gtk.Button) -> None:
        '''
        The button to select the full path of the Google application
        credentials .json file has been clicked.
        '''
        self._google_application_credentials_button.set_sensitive(False)
        filename = ''
        chooser = Gtk.FileChooserDialog(
            title=_('Set “Google application credentials” .json file:'),
            parent=self,
            action=Gtk.FileChooserAction.OPEN)
        chooser.add_button(_('_Cancel'), Gtk.ResponseType.CANCEL)
        chooser.add_button(_('_OK'), Gtk.ResponseType.OK)
        response = chooser.run()
        if response == Gtk.ResponseType.OK:
            filename = chooser.get_filename()
        chooser.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration()
        if filename:
            self._google_application_credentials_button_label.set_text(
                filename)
            self.set_google_application_credentials(
                filename, update_gsettings=True)
        self._google_application_credentials_button.set_sensitive(True)

    def _on_page_size_adjustment_value_changed(
            self, _widget: Gtk.SpinButton) -> None:
        '''
        The page size of the lookup table has been changed.
        '''
        self.set_page_size(
            self._page_size_adjustment.get_value(), update_gsettings=True)

    def _on_candidates_delay_milliseconds_adjustment_value_changed(
            self, _widget: Gtk.SpinButton) -> None:
        '''
        The delay of the candidates has been changed.
        '''
        self.set_candidates_delay_milliseconds(
            self._candidates_delay_milliseconds_adjustment.get_value(),
            update_gsettings=True)

    def _on_lookup_table_orientation_combobox_changed(
            self, widget: Gtk.ComboBox) -> None:
        '''
        A change of the lookup table orientation has been requested
        with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            orientation = model[tree_iter][1]
            self.set_lookup_table_orientation(
                orientation, update_gsettings=True)

    def _on_preedit_underline_combobox_changed(
            self, widget: Gtk.ComboBox) -> None:
        '''
        A change of the preedit underline style has been requested
        with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            underline_mode = model[tree_iter][1]
            self.set_preedit_underline(
                underline_mode, update_gsettings=True)

    def _on_min_char_complete_adjustment_value_changed(
            self, _widget: Gtk.SpinButton) -> None:
        '''
        The value for the mininum number of characters before
        completion is attempted has been changed.
        '''
        self.set_min_char_complete(
            self._min_char_complete_adjustment.get_value(),
            update_gsettings=True)

    def _on_error_sound_checkbutton(self, widget: Gtk.CheckButton) -> None:
        '''
        The checkbutton whether to play a sound file on error.

        :param widget: The check button clicked
        '''
        self.set_error_sound(widget.get_active(), update_gsettings=True)

    def _on_error_sound_file_button(
            self, _widget: Gtk.Button) -> None:
        '''
        The button to select the .wav sound file to be played on error.
        '''
        self._error_sound_file_button.set_sensitive(False)
        filename = ''
        chooser = Gtk.FileChooserDialog(
            title=_('Select .wav sound file:'),
            parent=self,
            action=Gtk.FileChooserAction.OPEN)
        chooser.add_button(_('_Cancel'), Gtk.ResponseType.CANCEL)
        chooser.add_button(_('_OK'), Gtk.ResponseType.OK)
        chooser.set_current_folder(os.path.dirname(
            self._settings_dict['errorsoundfile']['user']))
        response = chooser.run()
        if response == Gtk.ResponseType.OK:
            filename = chooser.get_filename()
        chooser.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration()
        if filename:
            self._error_sound_file_button_label.set_text(
                filename)
            self.set_error_sound_file(
                filename, update_gsettings=True)
        self._error_sound_file_button.set_sensitive(True)

    def _on_debug_level_adjustment_value_changed(
            self, _widget: Gtk.SpinButton) -> None:
        '''
        The value for the debug level has been changed.
        '''
        self.set_debug_level(
            self._debug_level_adjustment.get_value(),
            update_gsettings=True)


    def _on_autosetting_to_add_selected(
            self, _listbox: Gtk.ListBox, listbox_row: Gtk.ListBoxRow) -> None:
        '''
        Signal handler for selecting an autosetting to add

        :param _listbox: The list box used to select the setting to add
        :param listbox_row: A row containing a setting name
        '''
        index = listbox_row.get_index()
        setting = self._autosettings_add_listbox_settings[index]
        if self._autosettings_add_popover is None:
            LOGGER.debug('self._autosettings_add_popover is None')
            return
        if GTK_VERSION >= (3, 22, 0):
            self._autosettings_add_popover.popdown()
        self._autosettings_add_popover.hide()
        if not setting or setting not in self._allowed_autosettings:
            return
        self.set_autosettings(
            [(setting, '', '')] + self._settings_dict['autosettings']['user'],
            update_gsettings=True)
        # self.set_autosettings has reset
        # self._autosettings_selected_index = -1 and reset the
        # sensitivity of the buttons accordingly, set the correct
        # index again and fill the treeview again to get the correct
        # button state:
        self._autosettings_selected_index = 0
        self._fill_autosettings_treeview()

    def _on_dictionary_to_add_selected(
            self, _listbox: Gtk.ListBox, listbox_row: Gtk.ListBoxRow) -> None:
        '''
        Signal handler for selecting a dictionary to add

        :param _listbox: The list box used to select the dictionary to add
        :param listbox_row: A row containing a dictionary name
        '''
        index = listbox_row.get_index()
        name = self._dictionaries_add_listbox_dictionary_names[index]
        if self._dictionaries_add_popover is None:
            LOGGER.debug('self._dictionaries_add_popover is None')
            return
        if GTK_VERSION >= (3, 22, 0):
            self._dictionaries_add_popover.popdown()
        self._dictionaries_add_popover.hide()
        if not name or name in self._dictionary_names:
            return
        self.set_dictionary_names(
            [name] + [x for x in self._dictionary_names if x != 'None'],
            update_gsettings=True)
        self._dictionaries_listbox_selected_dictionary_index = 0
        self._dictionaries_listbox_selected_dictionary_name = name
        self._dictionaries_listbox.select_row(
            self._dictionaries_listbox.get_row_at_index(0))

    def _fill_dictionaries_add_listbox(self, filter_text: str) -> None:
        '''
        Fill the listbox of dictionaries to choose from

        :param filter_text: The filter text to limit the dictionaries
                            listed. Only dictionaries which contain
                            all the words from the filter text as substrings
                            (ignoring case and accents) are listed.
        '''
        self._dictionaries_add_listbox_dictionary_names = []
        if self._dictionaries_add_popover_scroll is None:
            LOGGER.debug('self._dictionaries_add_popover_scroll is None')
            return
        for child in self._dictionaries_add_popover_scroll.get_children():
            self._dictionaries_add_popover_scroll.remove(child)
        self._dictionaries_add_listbox = Gtk.ListBox()
        self._dictionaries_add_popover_scroll.add(
            self._dictionaries_add_listbox)
        self._dictionaries_add_listbox.set_visible(True)
        self._dictionaries_add_listbox.set_vexpand(True)
        self._dictionaries_add_listbox.set_selection_mode(
            Gtk.SelectionMode.SINGLE)
        self._dictionaries_add_listbox.set_activate_on_single_click(True)
        self._dictionaries_add_listbox.connect(
            'row-selected', self._on_dictionary_to_add_selected)
        rows = []
        for name in sorted(itb_util.SUPPORTED_DICTIONARIES):
            if name in self._dictionary_names:
                continue
            filter_words = itb_util.remove_accents(filter_text.lower()).split()
            text_to_match = itb_util.locale_text_to_match(name)
            if all(filter_word in text_to_match for filter_word in filter_words):
                self._dictionaries_add_listbox_dictionary_names.append(name)
                rows.append(self._fill_dictionaries_listbox_row(name)[0])
        for row in rows:
            label = Gtk.Label()
            label.set_text(html.escape(row))
            label.set_use_markup(True)
            label.set_xalign(0)
            margin = 1
            label.set_margin_start(margin)
            label.set_margin_end(margin)
            label.set_margin_top(margin)
            label.set_margin_bottom(margin)
            self._dictionaries_add_listbox.insert(label, -1)
        self._dictionaries_add_popover.show_all()

    def _on_dictionaries_search_entry_changed(
            self, search_entry: Gtk.SearchEntry) -> None:
        '''
        Signal handler for changed text in the dictionaries search entry

        :param search_entry: The search entry
        '''
        filter_text = search_entry.get_text()
        self._fill_dictionaries_add_listbox(filter_text)

    def _on_dictionaries_add_button_clicked(self, *_args: Any) -> None:
        '''
        Signal handler called when the “add” button to add another
        dictionary has been clicked.
        '''
        if (len(self._dictionary_names)
            >= itb_util.MAXIMUM_NUMBER_OF_DICTIONARIES):
            # Actually this should never happen because the button to add
            # a dictionary should not be sensitive if the maximum number
            # of dictionaries is already reached.
            #
            # Probably it is better not to make this message translatable
            # in order not to create extra work for the translators to
            # translate a message which should never be displayed anyway.
            self.__run_message_dialog(
                'The maximum number of dictionaries '
                f'is {itb_util.MAXIMUM_NUMBER_OF_DICTIONARIES}.',
                message_type=Gtk.MessageType.ERROR)
            return
        self._dictionaries_add_popover = Gtk.Popover()
        if self._dictionaries_add_popover is None:
            LOGGER.debug('self._dictionaries_add_popover is None')
            return
        self._dictionaries_add_popover.set_relative_to(
            self._dictionaries_add_button)
        self._dictionaries_add_popover.set_position(Gtk.PositionType.RIGHT)
        self._dictionaries_add_popover.set_vexpand(True)
        self._dictionaries_add_popover.set_hexpand(True)
        dictionaries_add_popover_vbox = Gtk.Box()
        dictionaries_add_popover_vbox.set_orientation(
            Gtk.Orientation.VERTICAL)
        margin = 12
        dictionaries_add_popover_vbox.set_margin_start(margin)
        dictionaries_add_popover_vbox.set_margin_end(margin)
        dictionaries_add_popover_vbox.set_margin_top(margin)
        dictionaries_add_popover_vbox.set_margin_bottom(margin)
        dictionaries_add_popover_vbox.set_spacing(margin)
        dictionaries_add_popover_label = Gtk.Label()
        dictionaries_add_popover_label.set_text(_('Add dictionary'))
        dictionaries_add_popover_label.set_visible(True)
        dictionaries_add_popover_label.set_halign(Gtk.Align.FILL)
        dictionaries_add_popover_vbox.add(
            dictionaries_add_popover_label)
        dictionaries_add_popover_search_entry = Gtk.SearchEntry()
        dictionaries_add_popover_search_entry.set_can_focus(True)
        dictionaries_add_popover_search_entry.set_visible(True)
        dictionaries_add_popover_search_entry.set_halign(Gtk.Align.FILL)
        dictionaries_add_popover_search_entry.set_hexpand(False)
        dictionaries_add_popover_search_entry.set_vexpand(False)
        dictionaries_add_popover_search_entry.connect(
            'search-changed', self._on_dictionaries_search_entry_changed)
        dictionaries_add_popover_vbox.add(
            dictionaries_add_popover_search_entry)
        self._dictionaries_add_popover_scroll = Gtk.ScrolledWindow()
        self._dictionaries_add_popover_scroll.set_hexpand(True)
        self._dictionaries_add_popover_scroll.set_vexpand(True)
        self._dictionaries_add_popover_scroll.set_kinetic_scrolling(False)
        self._dictionaries_add_popover_scroll.set_overlay_scrolling(True)
        self._fill_dictionaries_add_listbox('')
        dictionaries_add_popover_vbox.add(
            self._dictionaries_add_popover_scroll)
        self._dictionaries_add_popover.add(dictionaries_add_popover_vbox)
        if GTK_VERSION >= (3, 22, 0):
            self._dictionaries_add_popover.popup()
        self._dictionaries_add_popover.show_all()

    def _on_dictionaries_remove_button_clicked(self, *_args: Any) -> None:
        '''
        Signal handler called when the “remove” button for
        an input method has been clicked.
        '''
        index = self._dictionaries_listbox_selected_dictionary_index
        if not 0 <= index < len(self._dictionary_names):
            # This should not happen, one should not be able
            # to click the remove button in this case, just return:
            return
        dictionary_names = (self._dictionary_names[:index]
                            + self._dictionary_names[index + 1:])
        if not dictionary_names:
            # List of dictionaries has been made empty by the user. Set
            # it to the empty dummy dictionary 'None' (there is a
            # special button to get the locale default):
            dictionary_names = ['None']
        self.set_dictionary_names(dictionary_names, update_gsettings=True)
        self._dictionaries_listbox_selected_dictionary_index = -1
        self._dictionaries_listbox_selected_dictionary_name = ''
        if self._dictionaries_listbox:
            self._dictionaries_listbox.unselect_all()

    def _on_dictionaries_up_button_clicked(self, *_args: Any) -> None:
        '''
        Signal handler called when the “up” button for a dictionary
        has been clicked.

        Increases the priority of the selected dictionary.
        '''
        index = self._dictionaries_listbox_selected_dictionary_index
        if not 0 < index < len(self._dictionary_names):
            # This should not happen, one should not be able
            # to click the up button in this case, just return:
            return
        self.set_dictionary_names(
            self._dictionary_names[:index - 1]
            + [self._dictionary_names[index]]
            + [self._dictionary_names[index - 1]]
            + self._dictionary_names[index + 1:],
            update_gsettings=True)
        self._dictionaries_listbox_selected_dictionary_index = index - 1
        self._dictionaries_listbox_selected_dictionary_name = (
            self._dictionary_names[index - 1])
        if self._dictionaries_listbox is None:
            LOGGER.debug('self._dictionaries_listbox is None')
            return
        self._dictionaries_listbox.select_row(
            self._dictionaries_listbox.get_row_at_index(index - 1))

    def _on_dictionaries_down_button_clicked(self, *_args: Any) -> None:
        '''
        Signal handler called when the “down” button for a dictionary
        has been clicked.

        Lowers the priority of the selected dictionary.
        '''
        index = self._dictionaries_listbox_selected_dictionary_index
        if not 0 <= index < len(self._dictionary_names) - 1:
            # This should not happen, one should not be able
            # to click the down button in this case, just return:
            return
        self.set_dictionary_names(
            self._dictionary_names[:index]
            + [self._dictionary_names[index + 1]]
            + [self._dictionary_names[index]]
            + self._dictionary_names[index + 2:],
            update_gsettings=True)
        self._dictionaries_listbox_selected_dictionary_index = index + 1
        self._dictionaries_listbox_selected_dictionary_name = (
            self._dictionary_names[index + 1])
        if self._dictionaries_listbox is None:
            LOGGER.debug('self._dictionaries_listbox is None')
            return
        self._dictionaries_listbox.select_row(
            self._dictionaries_listbox.get_row_at_index(index + 1))

    def _on_install_missing_dictionaries(self, *_args: Any) -> None:
        '''
        Signal handler called when the “Install missing dictionaries”
        button is clicked.

        Tries to install the appropriate dictionary packages.
        '''
        missing_dictionary_packages = set()
        for name in self._dictionary_names:
            if name.split('_')[0] == 'fi':
                missing_dictionary_packages.add('python3-libvoikko')
            else:
                (dic_path,
                 dummy_aff_path) = itb_util.find_hunspell_dictionary(name)
                if not dic_path:
                    if (itb_util.distro_id() in
                        ('opensuse',
                         'opensuse-leap',
                         'opensuse-tumbleweed',
                         'sled',
                         'sles')):
                        missing_dictionary_packages.add(
                            'myspell-' + name)
                    else:
                        missing_dictionary_packages.add(
                            'hunspell-' + name.split('_')[0])
        InstallPackages(missing_dictionary_packages)
        self._fill_dictionaries_listbox()
        if missing_dictionary_packages:
            # Write a timestamp to dconf to trigger the callback
            # for changed dconf values in the engine and reload
            # the dictionaries:
            self._gsettings.set_value(
                'dictionaryinstalltimestamp',
                GLib.Variant.new_string(strftime('%Y-%m-%d %H:%M:%S')))

    def _on_dictionaries_default_button_clicked(self, *_args: Any) -> None:
        '''Signal handler called when the “Set to default” button for the
        dictionaries is clicked.

        Sets the dictionaries to the default for the current locale.

        '''
        if self._engine_name == 'typing-booster':
            self.set_dictionary_names(itb_util.dictionaries_str_to_list(''))
            return
        self.set_dictionary_names(self._settings_dict['dictionary']['default'])

    def _on_dictionary_selected(
            self, _listbox: Gtk.ListBox, listbox_row: Gtk.ListBoxRow) -> None:
        '''
        Signal handler called when a dictionary is selected

        :param _listbox: The listbox used to select dictionaries
        :param listbox_row: A row containing the dictionary name
        '''
        if listbox_row:
            index = listbox_row.get_index()
            self._dictionaries_listbox_selected_dictionary_index = index
            self._dictionaries_listbox_selected_dictionary_name = (
                self._dictionary_names[index])
            self._dictionaries_remove_button.set_sensitive(True)
            self._dictionaries_up_button.set_sensitive(index > 0)
            self._dictionaries_down_button.set_sensitive(
                index < len(self._dictionary_names) - 1)
        else:
            # all rows have been unselected
            self._dictionaries_listbox_selected_dictionary_name = ''
            self._dictionaries_listbox_selected_dictionary_index = -1
            self._dictionaries_remove_button.set_sensitive(False)
            self._dictionaries_up_button.set_sensitive(False)
            self._dictionaries_down_button.set_sensitive(False)

    def _on_input_method_to_add_selected(
            self, _listbox: Gtk.ListBox, listbox_row: Gtk.ListBoxRow) -> None:
        '''
        Signal handler for selecting an input method to add

        :param _listbox: The list box used to select
                              the input method to add
        :param listbox_row: A row containing an input method name
        '''
        index = listbox_row.get_index()
        ime = self._input_methods_add_listbox_imes[index]
        if self._input_methods_add_popover is None:
            LOGGER.debug('self._input_methods_add_popover is None')
            return
        if GTK_VERSION >= (3, 22, 0):
            self._input_methods_add_popover.popdown()
        self._input_methods_add_popover.hide()
        if not ime or ime in self._current_imes:
            return
        self.set_current_imes(
            [ime] + self._current_imes, update_gsettings=True)
        self._input_methods_listbox_selected_ime_index = 0
        self._input_methods_listbox_selected_ime_name = ime
        self._input_methods_listbox.select_row(
            self._input_methods_listbox.get_row_at_index(0))

    def _fill_input_methods_add_listbox(self, filter_text: str) -> None:
        '''
        Fill the listbox of input methods to choose from

        :param filter_text: The filter text to limit the input methods
                            listed. Only input methods which contain
                            the filter text as a substring
                            (ignoring case and accents) are listed.
                            The language part of the input method is
                            expanded using itb_util.locale_text_to_match()
                            into the full name of the language, in English,
                            the endonym, and in the language of the current
                            locale and all words from filter_text have to
                            match something in there.
        '''
        self._input_methods_add_listbox_imes = []
        if self._input_methods_add_popover_scroll is None:
            LOGGER.debug('self._input_methods_add_popover_scroll is None')
            return
        for child in self._input_methods_add_popover_scroll.get_children():
            self._input_methods_add_popover_scroll.remove(child)
        self._input_methods_add_listbox = Gtk.ListBox()
        self._input_methods_add_popover_scroll.add(
            self._input_methods_add_listbox)
        self._input_methods_add_listbox.set_visible(True)
        self._input_methods_add_listbox.set_vexpand(True)
        self._input_methods_add_listbox.set_selection_mode(
            Gtk.SelectionMode.SINGLE)
        self._input_methods_add_listbox.set_activate_on_single_click(True)
        self._input_methods_add_listbox.connect(
            'row-selected', self._on_input_method_to_add_selected)
        rows = []
        images = {}
        for ime in M17N_DB_INFO.get_imes():
            if ime in self._current_imes:
                continue
            filter_words = itb_util.remove_accents(filter_text.lower()).split()
            row = self._fill_input_methods_listbox_row(ime)
            text_to_match = row.replace(' ', '').lower()
            ime_language = ime.split('-')[0]
            text_to_match += ' ' + itb_util.locale_text_to_match(ime_language)
            if all(filter_word in text_to_match for filter_word in filter_words):
                self._input_methods_add_listbox_imes.append(ime)
                rows.append(row)
                images[row] = Gtk.Image.new_from_file(
                    M17N_DB_INFO.get_icon(ime))
        for row in rows:
            label = Gtk.Label()
            label.set_text(html.escape(row))
            label.set_use_markup(True)
            label.set_xalign(0)
            margin = 1
            label.set_margin_start(margin)
            label.set_margin_end(margin)
            label.set_margin_top(margin)
            label.set_margin_bottom(margin)
            hbox = Gtk.Box()
            hbox.set_orientation(Gtk.Orientation.HORIZONTAL)
            hbox.set_spacing(10)
            images[row].set_pixel_size(48)
            hbox.add(images[row])
            hbox.add(label)
            self._input_methods_add_listbox.insert(hbox, -1)
        self._input_methods_add_popover.show_all()

    def _on_input_methods_search_entry_changed(
            self, search_entry: Gtk.SearchEntry) -> None:
        '''
        Signal handler for changed text in the input methods search entry

        :param search_entry: The search entry
        '''
        filter_text = search_entry.get_text()
        self._fill_input_methods_add_listbox(filter_text)

    def _on_input_methods_add_button_clicked(self, *_args: Any) -> None:
        '''
        Signal handler called when the “add” button to add another
        input method has been clicked.
        '''
        if len(self._current_imes) >= itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS:
            # Actually this should never happen because the button to add
            # an input method should not be sensitive if the maximum number
            # of input methods is  already reached.
            #
            # Probably it is better not to make this message translatable
            # in order not to create extra work for the translators to
            # translate a message which should never be displayed anyway.
            self.__run_message_dialog(
                'The maximum number of input methods '
                f'is {itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS}.',
                message_type=Gtk.MessageType.ERROR)
            return
        self._input_methods_add_popover = Gtk.Popover()
        if self._input_methods_add_popover is None:
            LOGGER.debug('self._input_methods_add_popover is None')
            return
        self._input_methods_add_popover.set_relative_to(
            self._input_methods_add_button)
        self._input_methods_add_popover.set_position(Gtk.PositionType.RIGHT)
        self._input_methods_add_popover.set_vexpand(True)
        self._input_methods_add_popover.set_hexpand(True)
        input_methods_add_popover_vbox = Gtk.Box()
        input_methods_add_popover_vbox.set_orientation(
            Gtk.Orientation.VERTICAL)
        margin = 12
        input_methods_add_popover_vbox.set_margin_start(margin)
        input_methods_add_popover_vbox.set_margin_end(margin)
        input_methods_add_popover_vbox.set_margin_top(margin)
        input_methods_add_popover_vbox.set_margin_bottom(margin)
        input_methods_add_popover_vbox.set_spacing(margin)
        input_methods_add_popover_label = Gtk.Label()
        input_methods_add_popover_label.set_text(_('Add input method'))
        input_methods_add_popover_label.set_visible(True)
        input_methods_add_popover_label.set_halign(Gtk.Align.FILL)
        input_methods_add_popover_vbox.add(
            input_methods_add_popover_label)
        input_methods_add_popover_search_entry = Gtk.SearchEntry()
        input_methods_add_popover_search_entry.set_can_focus(True)
        input_methods_add_popover_search_entry.set_visible(True)
        input_methods_add_popover_search_entry.set_halign(Gtk.Align.FILL)
        input_methods_add_popover_search_entry.set_hexpand(False)
        input_methods_add_popover_search_entry.set_vexpand(False)
        input_methods_add_popover_search_entry.connect(
            'search-changed', self._on_input_methods_search_entry_changed)
        input_methods_add_popover_vbox.add(
            input_methods_add_popover_search_entry)
        self._input_methods_add_popover_scroll = Gtk.ScrolledWindow()
        self._input_methods_add_popover_scroll.set_hexpand(True)
        self._input_methods_add_popover_scroll.set_vexpand(True)
        self._input_methods_add_popover_scroll.set_kinetic_scrolling(False)
        self._input_methods_add_popover_scroll.set_overlay_scrolling(True)
        self._fill_input_methods_add_listbox('')
        input_methods_add_popover_vbox.add(
            self._input_methods_add_popover_scroll)
        self._input_methods_add_popover.add(input_methods_add_popover_vbox)
        if GTK_VERSION >= (3, 22, 0):
            self._input_methods_add_popover.popup()
        self._input_methods_add_popover.show_all()

    def _on_input_methods_remove_button_clicked(self, *_args: Any) -> None:
        '''
        Signal handler called when the “remove” button for
        an input method has been clicked.
        '''
        index = self._input_methods_listbox_selected_ime_index
        if not 0 <= index < len(self._current_imes):
            # This should not happen, one should not be able
            # to click the remove button in this case, just return:
            return
        current_imes = (self._current_imes[:index]
                        + self._current_imes[index + 1:])
        if not current_imes:
            # List of input methods has been made empty by the user
            # set it to the native keyboard input method NoIME (there
            # is a special button to get the locale default):
            current_imes = ['NoIME']
        self.set_current_imes(current_imes, update_gsettings=True)
        self._input_methods_listbox_selected_ime_index = -1
        self._input_methods_listbox_selected_ime_name = ''
        if self._input_methods_listbox is None:
            LOGGER.debug('self._input_methods_listbox is None')
            return
        self._input_methods_listbox.unselect_all()

    def _on_input_methods_up_button_clicked(self, *_args: Any) -> None:
        '''
        Signal handler called when the “up” button for an input method
        has been clicked.

        Increases the priority of the selected input method.
        '''
        index = self._input_methods_listbox_selected_ime_index
        if not 0 < index < len(self._current_imes):
            # This should not happen, one should not be able
            # to click the up button in this case, just return:
            return
        self.set_current_imes(
            self._current_imes[:index - 1]
            + [self._current_imes[index]]
            + [self._current_imes[index - 1]]
            + self._current_imes[index + 1:],
            update_gsettings=True)
        self._input_methods_listbox_selected_ime_index = index - 1
        self._input_methods_listbox_selected_ime_name = (
            self._current_imes[index - 1])
        if self._input_methods_listbox is None:
            LOGGER.debug('self._input_methods_listbox is None')
            return
        self._input_methods_listbox.select_row(
            self._input_methods_listbox.get_row_at_index(index - 1))

    def _on_input_methods_down_button_clicked(self, *_args: Any) -> None:
        '''
        Signal handler called when the “down” button for an input method
        has been clicked.

        Lowers the priority of the selected input method.
        '''
        index = self._input_methods_listbox_selected_ime_index
        if not 0 <= index < len(self._current_imes) - 1:
            # This should not happen, one should not be able
            # to click the down button in this case, just return:
            return
        self.set_current_imes(
            self._current_imes[:index]
            + [self._current_imes[index + 1]]
            + [self._current_imes[index]]
            + self._current_imes[index + 2:],
            update_gsettings=True)
        self._input_methods_listbox_selected_ime_index = index + 1
        self._input_methods_listbox_selected_ime_name = (
            self._current_imes[index + 1])
        if self._input_methods_listbox is None:
            LOGGER.debug('self._input_methods_listbox is None')
            return
        self._input_methods_listbox.select_row(
            self._input_methods_listbox.get_row_at_index(index + 1))

    def _on_input_methods_options_button_clicked(
            self, _button: Gtk.Button) -> None:
        '''
        Called when the button to set options for the currently selected
        input method has been clicked.
        '''
        if not self._input_methods_listbox_selected_ime_name:
            return
        ime = self._input_methods_listbox_selected_ime_name
        LOGGER.debug('Option setup for %s', ime)
        variables: List[Tuple[str, str, str]] = []
        try:
            trans = m17n_translit.Transliterator(ime)
            variables = trans.get_variables()
        except ValueError as error:
            LOGGER.exception(
                'Exception when opening ime %s: %s: %s',
                ime, error.__class__.__name__, error)
        if not variables:
            return
        self._input_methods_options_popover = Gtk.Popover()
        if self._input_methods_options_popover is None:
            LOGGER.debug('self._input_methods_options_popover is None')
            return
        self._input_methods_options_popover.set_relative_to(
            self._input_methods_options_button)
        self._input_methods_options_popover.set_position(Gtk.PositionType.TOP)
        self._input_methods_options_popover.set_vexpand(True)
        self._input_methods_options_popover.set_hexpand(True)
        vbox = Gtk.Box()
        vbox.set_orientation(Gtk.Orientation.VERTICAL)
        margin = 12
        vbox.set_margin_start(margin)
        vbox.set_margin_end(margin)
        vbox.set_margin_top(margin)
        vbox.set_margin_bottom(margin)
        vbox.set_spacing(margin)
        hbox = Gtk.Box()
        hbox.set_orientation(Gtk.Orientation.HORIZONTAL)
        hbox.set_spacing(10)
        label = Gtk.Label()
        label.set_text(html.escape(self._fill_input_methods_listbox_row(ime)))
        margin = 1
        label.set_margin_start(margin)
        label.set_margin_end(margin)
        label.set_margin_top(margin)
        label.set_margin_bottom(margin)
        if M17N_DB_INFO is not None:
            image = Gtk.Image.new_from_file(M17N_DB_INFO.get_icon(ime))
            image.set_pixel_size(48)
            hbox.add(image)
        hbox.add(label)
        vbox.add(hbox)
        scroll = Gtk.ScrolledWindow()
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.set_kinetic_scrolling(False)
        scroll.set_overlay_scrolling(True)
        treeview = Gtk.TreeView()
        treeview.set_can_focus(True)
        treeview.set_has_tooltip(True)
        treeview.set_grid_lines(Gtk.TreeViewGridLines.BOTH)
        treeview_model = Gtk.ListStore(str, str, str)
        treeview.set_model(treeview_model)
        for (name, description, value) in variables:
            treeview_model.append((name, description, value))
        treeview_column_0 = Gtk.TreeViewColumn(
            # Translators: Column heading of the table listing the variables
            # for the currently selected input method
            _('Variable'),
            Gtk.CellRendererText(),
            text=0)
        treeview_column_0.set_sort_column_id(0)
        treeview.append_column(treeview_column_0)
        value_renderer = Gtk.CellRendererText()
        treeview_column_2 = Gtk.TreeViewColumn(
            # Translators: Column heading of the table listing the variables
            # for the currently selected input method
            _('Value'),
            value_renderer,
            text=2)
        treeview_column_2.set_sort_column_id(2)
        treeview.append_column(treeview_column_2)
        value_renderer.set_property('editable', True)
        value_renderer.connect(
            'edited',
            self._on_input_methods_options_popover_treeview_value_edited,
            treeview_model)
        treeview.connect(
            'query-tooltip',
            self._on_input_methods_options_popover_treeview_query_tooltip)
        scroll.add(treeview)
        vbox.add(scroll)
        self._input_methods_options_popover.add(vbox)
        if GTK_VERSION >= (3, 22, 0):
            self._input_methods_options_popover.popup()
        self._input_methods_options_popover.show_all()

    def _on_input_methods_options_popover_treeview_value_edited(
            self,
            _cell: Gtk.CellRendererText,
            path: str,
            new_edited_value: str,
            model: Gtk.ListStore) -> None:
        '''
        Called when the value of an m17n input method variable has
        been edited in the treeview
        '''
        ime = self._input_methods_listbox_selected_ime_name
        old_variables: List[Tuple[str, str, str]] = []
        try:
            trans = m17n_translit.Transliterator(ime)
            old_variables = trans.get_variables()
        except ValueError as error:
            LOGGER.exception(
                'Exception when opening ime %s: %s: %s',
                ime, error.__class__.__name__, error)
        if not old_variables:
            LOGGER.debug('Could not find any variables for ime %s', ime)
            return
        iterator = model.get_iter(path)
        old_name = model.get_value(iterator, 0)
        old_value = model.get_value(iterator, 2)
        try:
            trans.set_variables({old_name: new_edited_value})
        except ValueError as error:
            LOGGER.exception(
                'Exception when setting %s to %s: %s: %s',
                old_name, new_edited_value,
                error.__class__.__name__, error)
            LOGGER.debug('Trying to set default value now ...')
            try:
                trans.set_variables({old_name: ''})
            except ValueError as error2:
                LOGGER.exception(
                    'Exception when setting %s to %s: %s: %s',
                    old_name, '',
                    error.__class__.__name__, error2)
                LOGGER.debug('Giving up and returning.')
                return
        variables = trans.get_variables()
        if variables == old_variables:
            LOGGER.debug('No variables were changed when saving, returning.')
            return
        for (name, _description, value) in variables:
            if name != old_name:
                continue
            if value == old_value:
                LOGGER.debug(
                    'Value not changed, should never happen here, returning.')
                return
            if value != new_edited_value:
                LOGGER.debug(
                    'Tried to set %s to %s but actual result was %s',
                    name, new_edited_value, value)
            model.set_value(iterator, 2, value)
            LOGGER.info('Successfully changed value to %s', value)
            LOGGER.debug(
                'Tell typing booster to reload all input methods.')
            self._gsettings.set_value(
                'inputmethodchangetimestamp',
                GLib.Variant.new_string(strftime('%Y-%m-%d %H:%M:%S')))

    @classmethod
    def _on_input_methods_options_popover_treeview_query_tooltip(
            cls,
            treeview: Gtk.TreeView,
            x_pos: int,
            y_pos: int,
            keyboard_tip: bool,
            tooltip: Gtk.Tooltip) -> bool:
        '''
        Called to show the descriptions of the m17n input method variables
        as tooltips.
        '''
        (is_treeview_row_at_coordinates, x_pos, y_pos,
         model, path, iterator) = treeview.get_tooltip_context(
             x_pos, y_pos, keyboard_tip)
        if not is_treeview_row_at_coordinates:
            return False
        description = model.get_value(iterator, 1)
        tooltip.set_text(description)
        treeview.set_tooltip_row(tooltip, path)
        return True

    def _on_input_methods_help_button_clicked(
            self, _button: Gtk.Button) -> None:
        '''
        Show a help window for the input method selected in the
        listbox.
        '''
        if not self._input_methods_listbox_selected_ime_name:
            return
        ime = self._input_methods_listbox_selected_ime_name
        path = ''
        title = ''
        description = ''
        content = ''
        if M17N_DB_INFO is not None:
            path = M17N_DB_INFO.get_path(ime)
            title = M17N_DB_INFO.get_title(ime)
            description = M17N_DB_INFO.get_description(ime)
            content = M17N_DB_INFO.get_content(ime)
        window_title = ime
        if title:
            window_title += '   ' + title
        if path:
            window_title += '   ' + path
        window_contents = ''
        if description:
            window_contents = description
        if content:
            window_contents += (
                '\n\n'
                '##############################'
                '##############################'
                '\n'
                'Complete file implementing the '
                'input method follows here:\n'
                '##############################'
                '##############################'
                '\n'
                + content)
        HelpWindow(
            parent=self,
            title=window_title,
            contents=window_contents)

    def _on_input_methods_default_button_clicked(self, *_args: Any) -> None:
        '''Signal handler called when the “Set to default”
        button for the input methods is clicked.

        Sets the input methods to the default for the current locale.
        '''
        if self._engine_name == 'typing-booster':
            self.set_current_imes(itb_util.input_methods_str_to_list(''))
            return
        self.set_current_imes(self._settings_dict['inputmethod']['default'])

    def _on_input_method_selected(
            self, _listbox: Gtk.ListBox, listbox_row: Gtk.ListBoxRow) -> None:
        '''
        Signal handler called when an input method is selected

        :param _listbox: The listbox used to select input methods
        :param listbox_row: A row containing the input method name
        '''
        if listbox_row:
            index = listbox_row.get_index()
            self._input_methods_listbox_selected_ime_index = index
            self._input_methods_listbox_selected_ime_name = (
                self._current_imes[index])
            self._input_methods_remove_button.set_sensitive(True)
            self._input_methods_up_button.set_sensitive(
                0 < index < len(self._current_imes))
            self._input_methods_down_button.set_sensitive(
                0 <= index < len(self._current_imes) - 1)
            self._input_methods_help_button.set_sensitive(True)
            variables = []
            try:
                trans = m17n_translit.Transliterator(
                    self._input_methods_listbox_selected_ime_name)
                variables = trans.get_variables()
            except ValueError as error:
                LOGGER.exception(
                    'Exception when opening ime %s: %s: %s',
                    self._input_methods_listbox_selected_ime_name,
                    error.__class__.__name__, error)
            self._input_methods_options_button.set_sensitive(False)
            if variables:
                self._input_methods_options_button.set_sensitive(True)
        else:
            # all rows have been unselected
            self._input_methods_listbox_selected_ime_name = ''
            self._input_methods_listbox_selected_ime_index = -1
            self._input_methods_remove_button.set_sensitive(False)
            self._input_methods_up_button.set_sensitive(False)
            self._input_methods_down_button.set_sensitive(False)
            self._input_methods_help_button.set_sensitive(False)
            self._input_methods_options_button.set_sensitive(False)

    # pylint: disable=no-self-use
    def _on_autosettings_treeview_row_activated(
            self,
            treeview: Gtk.TreeView,
            treepath: Gtk.TreePath,
            column: Gtk.TreeViewColumn) -> None:
        '''
        Signal handler for activating a row in the autosettings treeview

        :param treeview: The autosettings treeview
        :param treepath: The path of the activated row in the treeview
        :param column: The column of the activated row in the treeview
        '''
        # Currently we do not do anything when a row is activated:
        LOGGER.debug('%s %s %s', treeview, treepath, column)
    # pylint: enable=no-self-use

    def _on_autosettings_treeview_row_selected(
            self, selection: Gtk.TreeSelection) -> None:
        '''A row in the autosettings treeview has been selected'''
        (_list_store, tree_path_list) = selection.get_selected_rows()
        if (len(tree_path_list) == 1
            and tree_path_list[0].get_depth() == 1
            and len(tree_path_list[0].get_indices()) == 1):
            index = tree_path_list[0].get_indices()[0]
            self._autosettings_selected_index = index
            self._autosettings_remove_button.set_sensitive(True)
            self._autosettings_up_button.set_sensitive(index > 0)
            self._autosettings_down_button.set_sensitive(
                index < len(self._settings_dict['autosettings']['user']) - 1)
        else:
            self._autosettings_selected_index = -1
            self._autosettings_remove_button.set_sensitive(False)
            self._autosettings_up_button.set_sensitive(False)
            self._autosettings_down_button.set_sensitive(False)

    def _on_autosettings_treeview_value_edited(
            self,
            _cell: Gtk.CellRendererText,
            path: str,
            new_edited_value: str,
            model: Gtk.ListStore) -> None:
        '''
        Called when the value of an autosetting has been edited in the treeview
        '''
        LOGGER.debug('path=%s, new_edited_value=%s', path, new_edited_value)
        if ':' in path:
            LOGGER.debug('":" found in path, should never happen')
            return
        try:
            index = int(path)
        except (TypeError, ValueError):
            LOGGER.debug('Cannot convert path to integer, should never happen')
        autosettings_user = self._settings_dict['autosettings']['user']
        if not 0 <= index < len(autosettings_user):
            LOGGER.debug('index out of range')
            return
        iterator = model.get_iter(path)
        old_setting = model.get_value(iterator, 0)
        old_value = model.get_value(iterator, 1)
        old_regexp = model.get_value(iterator, 2)
        if old_value == new_edited_value:
            LOGGER.debug('Value not changed')
            return
        if old_setting in self._allowed_autosettings:
            value_type = self._allowed_autosettings[old_setting]['value_type']
            if value_type in ('i', 'x'): # int32, int64
                try:
                    value_integer = int(new_edited_value)
                    new_edited_value = str(value_integer)
                except (ValueError,) as error:
                    LOGGER.exception(
                        'Exception converting string to integer %s: %s',
                        error.__class__.__name__, error)
                    new_edited_value = ''
            elif value_type in ('u', 't'): # uint32, uint64
                try:
                    value_integer = max(0, int(new_edited_value))
                    new_edited_value = str(value_integer)
                except (ValueError,) as error:
                    LOGGER.exception(
                        'Exception converting string to integer %s: %s',
                        error.__class__.__name__, error)
                    new_edited_value = ''
            elif value_type == 'd': # double
                try:
                    value_float = float(new_edited_value)
                    new_edited_value = str(value_float)
                except (ValueError,) as error:
                    LOGGER.exception(
                        'Exception converting string to float %s: %s',
                        error.__class__.__name__, error)
                    new_edited_value = ''
            elif value_type == 'b':
                if new_edited_value.lower().strip() in ('true', 'false'):
                    new_edited_value = new_edited_value.lower().strip()
                else:
                    new_edited_value = ''
        model.set_value(iterator, 1, new_edited_value)
        new_autosettings = autosettings_user['user'][:]
        new_autosettings[index] = (old_setting, new_edited_value, old_regexp)
        self.set_autosettings(new_autosettings)

    def _on_autosettings_treeview_regexp_edited(
            self,
            _cell: Gtk.CellRendererText,
            path: str,
            new_edited_regexp: str,
            model: Gtk.ListStore) -> None:
        '''
        Called when the value of an autosetting has been edited in the treeview
        '''
        LOGGER.debug('path=%s, new_edited_value=%s', path, new_edited_regexp)
        if ':' in path:
            LOGGER.debug('":" found in path, should never happen')
            return
        try:
            index = int(path)
        except (TypeError, ValueError):
            LOGGER.debug('Cannot convert path to integer, should never happen')
        autosettings_user = self._settings_dict['autosettings']['user']
        if not 0 <= index < len(autosettings_user):
            LOGGER.debug('index out of range')
            return
        iterator = model.get_iter(path)
        old_setting = model.get_value(iterator, 0)
        old_value = model.get_value(iterator, 1)
        old_regexp = model.get_value(iterator, 2)
        if old_regexp == new_edited_regexp:
            LOGGER.debug('Regexp not changed')
            return
        model.set_value(iterator, 2, new_edited_regexp)
        new_autosettings = autosettings_user[:]
        new_autosettings[index] = (old_setting, old_value, new_edited_regexp)
        self.set_autosettings(new_autosettings)

    def _fill_autosettings_add_listbox(self, filter_text: str) -> None:
        '''
        Fill the listbox of autosettings to choose from

        :param filter_text: The filter text to limit the autosettings
                            listed. Only autosettings which contain
                            all the words from the filter text as substrings
                            (ignoring case and accents) are listed.
        '''
        self._autosettings_add_listbox_settings = []
        if self._autosettings_add_popover_scroll is None:
            LOGGER.debug('self._autosettings_add_popover_scroll is None')
            return
        for child in self._autosettings_add_popover_scroll.get_children():
            self._autosettings_add_popover_scroll.remove(child)
        self._autosettings_add_listbox = Gtk.ListBox()
        self._autosettings_add_popover_scroll.add(
            self._autosettings_add_listbox)
        self._autosettings_add_listbox.set_visible(True)
        self._autosettings_add_listbox.set_vexpand(True)
        self._autosettings_add_listbox.set_selection_mode(
            Gtk.SelectionMode.SINGLE)
        self._autosettings_add_listbox.set_activate_on_single_click(True)
        self._autosettings_add_listbox.connect(
            'row-selected', self._on_autosetting_to_add_selected)
        rows = []
        for setting in sorted(self._allowed_autosettings):
            filter_words = itb_util.remove_accents(filter_text.lower()).split()
            text_to_match = setting
            if all(filter_word in text_to_match for filter_word in filter_words):
                self._autosettings_add_listbox_settings.append(setting)
                rows.append(setting)
        for row in rows:
            label = Gtk.Label()
            label.set_text(html.escape(row))
            label.set_use_markup(True)
            label.set_xalign(0)
            margin = 1
            label.set_margin_start(margin)
            label.set_margin_end(margin)
            label.set_margin_top(margin)
            label.set_margin_bottom(margin)
            self._autosettings_add_listbox.insert(label, -1)
        self._autosettings_add_popover.show_all()

    def _on_autosettings_search_entry_changed(
            self, search_entry: Gtk.SearchEntry) -> None:
        '''
        Signal handler for changed text in the autosettings search entry

        :param search_entry: The search entry
        '''
        filter_text = search_entry.get_text()
        self._fill_autosettings_add_listbox(filter_text)

    def _on_autosettings_add_button_clicked(self, *_args: Any) -> None:
        '''
        Signal handler called when the “add” button to add
        an autosetting is clicked
        '''
        self._autosettings_add_popover = Gtk.Popover()
        if self._autosettings_add_popover is None:
            LOGGER.debug('self._autosettings_add_popover is None')
            return
        self._autosettings_add_popover.set_relative_to(
            self._autosettings_add_button)
        self._autosettings_add_popover.set_position(Gtk.PositionType.RIGHT)
        self._autosettings_add_popover.set_vexpand(True)
        self._autosettings_add_popover.set_hexpand(True)
        autosettings_add_popover_vbox = Gtk.Box()
        autosettings_add_popover_vbox.set_orientation(
            Gtk.Orientation.VERTICAL)
        margin = 12
        autosettings_add_popover_vbox.set_margin_start(margin)
        autosettings_add_popover_vbox.set_margin_end(margin)
        autosettings_add_popover_vbox.set_margin_top(margin)
        autosettings_add_popover_vbox.set_margin_bottom(margin)
        autosettings_add_popover_vbox.set_spacing(margin)
        autosettings_add_popover_label = Gtk.Label()
        autosettings_add_popover_label.set_text(_('Add an autosetting'))
        autosettings_add_popover_label.set_visible(True)
        autosettings_add_popover_label.set_halign(Gtk.Align.FILL)
        autosettings_add_popover_vbox.add(
            autosettings_add_popover_label)
        autosettings_add_popover_search_entry = Gtk.SearchEntry()
        autosettings_add_popover_search_entry.set_can_focus(True)
        autosettings_add_popover_search_entry.set_visible(True)
        autosettings_add_popover_search_entry.set_halign(Gtk.Align.FILL)
        autosettings_add_popover_search_entry.set_hexpand(False)
        autosettings_add_popover_search_entry.set_vexpand(False)
        autosettings_add_popover_search_entry.connect(
            'search-changed', self._on_autosettings_search_entry_changed)
        autosettings_add_popover_vbox.add(
            autosettings_add_popover_search_entry)
        self._autosettings_add_popover_scroll = Gtk.ScrolledWindow()
        self._autosettings_add_popover_scroll.set_hexpand(True)
        self._autosettings_add_popover_scroll.set_vexpand(True)
        self._autosettings_add_popover_scroll.set_kinetic_scrolling(False)
        self._autosettings_add_popover_scroll.set_overlay_scrolling(True)
        self._fill_autosettings_add_listbox('')
        autosettings_add_popover_vbox.add(
            self._autosettings_add_popover_scroll)
        self._autosettings_add_popover.add(autosettings_add_popover_vbox)
        if GTK_VERSION >= (3, 22, 0):
            self._autosettings_add_popover.popup()
        self._autosettings_add_popover.show_all()

    def _on_autosettings_remove_button_clicked(self, *_args: Any) -> None:
        '''
        Signal handler called when the “remove” button to remove
        an autosetting is clicked
        '''
        index = self._autosettings_selected_index
        LOGGER.debug('remove index %s', index)
        autosettings_user = self._settings_dict['autosettings']['user']
        if not 0 <= index < len(autosettings_user):
            # This should not happen, one should not be able
            # to click the remove button in this case, just return:
            return
        self._autosettings_selected_index = -1
        self.set_autosettings(
            autosettings_user[:index] + autosettings_user[index + 1:],
            update_gsettings=True)

    def _on_autosettings_up_button_clicked(self, *_args: Any) -> None:
        '''
        Signal handler called when the “up” button to move
        an autosetting up is clicked
        '''
        index = self._autosettings_selected_index
        autosettings_user = self._settings_dict['autosettings']['user']
        if not 0 < index < len(autosettings_user):
            # This should not happen, one should not be able
            # to click the up button in this case, just return:
            return
        self.set_autosettings(
            autosettings_user[:index - 1]
            + [autosettings_user[index]]
            + [autosettings_user[index - 1]]
            + autosettings_user[index + 1:],
            update_gsettings=True)
        # self.set_autosettings has reset
        # self._autosettings_selected_index = -1 and reset the
        # sensitivity of the buttons accordingly, set the correct
        # index again and fill the treeview again to get the correct
        # button state:
        self._autosettings_selected_index = index - 1
        self._fill_autosettings_treeview()

    def _on_autosettings_down_button_clicked(self, *_args: Any) -> None:
        '''
        Signal handler called when the “down” button to move
        an autosetting down is clicked
        '''
        index = self._autosettings_selected_index
        autosettings_user = self._settings_dict['autosettings']['user']
        if not 0 <= index < len(autosettings_user) - 1:
            # This should not happen, one should not be able
            # to click the down button in this case, just return:
            return
        self.set_autosettings(
            autosettings_user[:index]
            + [autosettings_user[index + 1]]
            + [autosettings_user[index]]
            + autosettings_user[index + 2:],
            update_gsettings=True)
        # self.set_autosettings has reset
        # self._autosettings_selected_index = -1 and reset the
        # sensitivity of the buttons accordingly, set the correct
        # index again and fill the treeview again to get the correct
        # button state:
        self._autosettings_selected_index = index + 1
        self._fill_autosettings_treeview()

    def _set_shortcut_button_sensitivity(self) -> None:
        '''Adjust the sensitivity values of the “Clear”, “Delete”, and “Add”
        buttons.
        '''
        shortcut = self._shortcut_entry.get_text()
        buffer = self._shortcut_expansion_textview.get_buffer()
        expansion = buffer.get_text(buffer.get_start_iter(),
                                    buffer.get_end_iter(),
                                    False)
        LOGGER.debug('shortcut=“%s” expansion=“%s”', shortcut, expansion)
        if shortcut.strip() and expansion.strip():
            self._shortcut_clear_button.set_sensitive(True)
            self._shortcut_delete_button.set_sensitive(True)
            self._shortcut_add_button.set_sensitive(True)
        elif shortcut or expansion:
            self._shortcut_clear_button.set_sensitive(True)
            self._shortcut_delete_button.set_sensitive(False)
            self._shortcut_add_button.set_sensitive(False)
        else:
            self._shortcut_clear_button.set_sensitive(False)
            self._shortcut_delete_button.set_sensitive(False)
            self._shortcut_add_button.set_sensitive(False)

    def _on_shortcut_entry(
            self, _widget: Gtk.Entry, _property_spec: Any) -> None:
        '''The contents of the shortcut entry line has changed'''
        self._set_shortcut_button_sensitivity()

    def _on_shortcut_expansion_textview_buffer(
            self, _buffer: Gtk.TextBuffer, _param_spec: Any) -> None:
        '''
        The contents of the buffer of the shortcut expansion textview changed
        '''
        self._set_shortcut_button_sensitivity()

    def _on_shortcut_clear_clicked(self, _button: Gtk.Button) -> None:
        '''
        The button to clear the entry fields for defining
        a custom shortcut has been clicked.
        '''
        self._shortcut_entry.set_text('')
        expansion_buffer = self._shortcut_expansion_textview.get_buffer()
        expansion_buffer.set_text('')
        self._shortcut_treeview.get_selection().unselect_all()
        self._shortcut_search_entry.set_text('')
        self._fill_shortcut_treeview_model('')

    def _on_shortcut_delete_clicked(self, _button: Gtk.Button) -> None:
        '''
        The button to delete a custom shortcut has been clicked.
        '''
        shortcut = self._shortcut_entry.get_text().strip()
        expansion_buffer = self._shortcut_expansion_textview.get_buffer()
        shortcut_expansion = (
            expansion_buffer.get_text(
                expansion_buffer.get_start_iter(),
                expansion_buffer.get_end_iter(),
                False).strip())
        if shortcut and shortcut_expansion:
            model = self._shortcut_treeview_model
            iterator = model.get_iter_first()
            while iterator:
                if (model.get_value(iterator, 0) == shortcut
                        and
                        model.get_value(iterator, 1) == shortcut_expansion):
                    self.tabsqlitedb.remove_phrase(
                        input_phrase=shortcut,
                        phrase=shortcut_expansion)
                    if not model.remove(iterator):
                        iterator = None
                else:
                    iterator = model.iter_next(iterator)
        self._shortcut_entry.set_text('')
        expansion_buffer.set_text('')
        self._shortcut_treeview.get_selection().unselect_all()
        self._shortcut_search_entry.set_text('')
        self._fill_shortcut_treeview_model('')

    def _on_shortcut_add_clicked(self, _button: Gtk.Button) -> None:
        '''The button to add a custom shortcut has been clicked.'''
        self._shortcut_treeview.get_selection().unselect_all()
        shortcut = self._shortcut_entry.get_text().strip()
        expansion_buffer = self._shortcut_expansion_textview.get_buffer()
        shortcut_expansion = (
            expansion_buffer.get_text(
                expansion_buffer.get_start_iter(),
                expansion_buffer.get_end_iter(),
                False).strip())
        if shortcut and shortcut_expansion:
            model = self._shortcut_treeview_model
            iterator = model.get_iter_first()
            shortcut_existing = False
            while iterator:
                if (model.get_value(iterator, 0) == shortcut
                        and
                        model.get_value(iterator, 1) == shortcut_expansion):
                    shortcut_existing = True
                iterator = model.iter_next(iterator)
            if not shortcut_existing:
                LOGGER.info(
                    'defining shortcut: “%s” -> “%s”',
                    shortcut, shortcut_expansion)
                self.tabsqlitedb.define_user_shortcut(
                    input_phrase=shortcut,
                    phrase=shortcut_expansion,
                    user_freq=itb_util.SHORTCUT_USER_FREQ)
                model.append((shortcut, shortcut_expansion))
            self._shortcut_entry.set_text('')
            expansion_buffer.set_text('')
            self._shortcut_treeview.get_selection().unselect_all()
            self._shortcut_search_entry.set_text('')
            self._fill_shortcut_treeview_model('')

    def _fill_shortcut_treeview_model(self, filter_text: str) -> None:
        '''
        Fill the model of the shortcuts treeview

        :param filter_text: The filter text to limit the shortcuts
                            listed. Only shortcuts which contain
                            all the words from the filter text as substrings
                            (ignoring case and accents) are listed.

        '''
        # Clearing the model seems to cause a selection changed event for
        # each item cleared, unselect_all() is apparently not enough to avoid this.
        # But it can be avoided by set_mode(Gtk.SelectionMode.NONE)
        self._shortcut_treeview.get_selection().unselect_all()
        self._shortcut_treeview.get_selection().set_mode(Gtk.SelectionMode.NONE)
        self._shortcut_treeview_model.clear()
        self._shortcut_treeview.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
        current_shortcuts: List[Tuple[str, str]] = (
            self.tabsqlitedb.list_user_shortcuts())
        filter_words = itb_util.remove_accents(filter_text.lower()).split()
        for shortcut in current_shortcuts:
            text_to_match = (
                itb_util.remove_accents(shortcut[0]).lower()
                + ' ' + itb_util.remove_accents(shortcut[1]).lower())
            if all(filter_word in text_to_match for filter_word in filter_words):
                self._shortcut_treeview_model.append(shortcut)

    def _on_shortcut_search_entry_changed(
            self, search_entry: Gtk.SearchEntry) -> None:
        '''
        Signal handler for changed text in the shortcut search entry

        :param search_entry: The search entry
        '''
        filter_text = search_entry.get_text()
        self._fill_shortcut_treeview_model(filter_text)

    def _on_shortcut_selected(self, selection: Gtk.TreeSelection) -> None:
        '''
        A row in the list of shortcuts has been selected.
        '''
        (model, iterator) = selection.get_selected()
        if iterator:
            shortcut = model[iterator][0]
            shortcut_expansion = model[iterator][1]
            self._shortcut_entry.set_text(shortcut)
            expansion_buffer = self._shortcut_expansion_textview.get_buffer()
            expansion_buffer.set_text(shortcut_expansion)

    def _on_keybindings_treeview_row_activated(
            self,
            _treeview: Gtk.TreeView,
            treepath: Gtk.TreePath,
            _treeviewcolumn: Gtk.TreeViewColumn) -> None:
        '''
        A row in the treeview listing the key bindings has been activated.

        :param treeview: The treeview listing the key bindings
        :param treepath: The path to the activated row
        :param treeviewcolumn: A column in the treeview listing the
                               key bindings
        '''
        model = self._keybindings_treeview_model
        iterator = model.get_iter(treepath)
        command = model[iterator][0]
        if command != self._keybindings_selected_command:
            # This should not happen, if a row is activated it should
            # already be selected,
            # i.e. on_keybindings_treeview_row_selected() should have
            # been called already and this should have set
            # self._keybindings_selected_command
            LOGGER.error(
                'Unexpected error, command = "%s" '
                'self._keybindings_selected_command = "%s"\n',
                command,
                self._keybindings_selected_command)
            return
        self._create_and_show_keybindings_edit_popover()

    def _on_keybindings_treeview_row_selected(
            self, selection: Gtk.TreeSelection) -> None:
        '''
        A row in the treeview listing the key bindings has been selected.
        '''
        (model, iterator) = selection.get_selected()
        if iterator:
            self._keybindings_selected_command = model[iterator][0]
            self._keybindings_default_button.set_sensitive(True)
            self._keybindings_edit_button.set_sensitive(True)
        else:
            # all rows have been unselected
            self._keybindings_selected_command = ''
            self._keybindings_default_button.set_sensitive(False)
            self._keybindings_edit_button.set_sensitive(False)

    def _on_keybindings_edit_listbox_row_selected(
            self, _listbox: Gtk.ListBox, listbox_row: Gtk.ListBoxRow) -> None:
        '''
        Signal handler for selecting one of the key bindings
        for a certain command

        :param _listbox: The list box used to select a key binding
        :param listbox_row: A row containing a key binding
        '''
        if  listbox_row:
            self._keybindings_edit_popover_selected_keybinding = (
                listbox_row.get_child().get_text().split(' ')[0])
            if self._keybindings_edit_popover_remove_button:
                self._keybindings_edit_popover_remove_button.set_sensitive(
                    True)
        else:
            # all rows have been unselected
            self._keybindings_edit_popover_selected_keybinding = ''
            if self._keybindings_edit_popover_remove_button:
                self._keybindings_edit_popover_remove_button.set_sensitive(
                    False)

    def _on_keybindings_edit_popover_add_button_clicked(
            self, *_args: Any) -> None:
        '''
        Signal handler called when the “Add” button to add
        a key binding has been clicked.
        '''
        key_input_dialog = itb_util.ItbKeyInputDialog(parent=self)
        response = key_input_dialog.run()
        key_input_dialog.destroy()
        if response == Gtk.ResponseType.OK:
            keyval, state = key_input_dialog.e
            key = itb_util.KeyEvent(keyval, 0, state)
            keybinding = itb_util.keyevent_to_keybinding(key)
            command = self._keybindings_selected_command
            if (keybinding
                not in self._settings_dict['keybindings']['user'][command]):
                self._settings_dict['keybindings']['user'][command].append(
                    keybinding)
                self._fill_keybindings_edit_popover_listbox()
                self.set_keybindings(
                    self._settings_dict['keybindings']['user'])

    def _on_keybindings_edit_popover_remove_button_clicked(
            self, *_args: Any) -> None:
        '''
        Signal handler called when the “Remove” button to remove
        a key binding has been clicked.
        '''
        keybinding = self._keybindings_edit_popover_selected_keybinding
        command = self._keybindings_selected_command
        if (keybinding and command
            and
            keybinding in self._settings_dict['keybindings']['user'][command]):
            self._settings_dict['keybindings']['user'][command].remove(
                keybinding)
            self._fill_keybindings_edit_popover_listbox()
            self.set_keybindings(self._settings_dict['keybindings']['user'])

    def _on_keybindings_edit_popover_default_button_clicked(
            self, *_args: Any) -> None:
        '''
        Signal handler called when the “Default” button to set
        the keybindings to the default has been clicked.
        '''
        default_keybindings = self._settings_dict['keybindings']['default']
        command = self._keybindings_selected_command
        if command and command in default_keybindings:
            new_keybindings = self._settings_dict['keybindings']['user']
            new_keybindings[command] = default_keybindings[command]
            self._fill_keybindings_edit_popover_listbox()
            self.set_keybindings(new_keybindings)

    def _fill_keybindings_edit_popover_listbox(self) -> None:
        '''
        Fill the edit listbox to with the key bindings of the currently
        selected command
        '''
        if self._keybindings_edit_popover_scroll is None:
            LOGGER.debug('self._keybindings_edit_popover_scroll is None')
            return
        for child in self._keybindings_edit_popover_scroll.get_children():
            self._keybindings_edit_popover_scroll.remove(child)
        self._keybindings_edit_popover_listbox = Gtk.ListBox()
        self._keybindings_edit_popover_scroll.add(
            self._keybindings_edit_popover_listbox)
        self._keybindings_edit_popover_listbox.set_visible(True)
        self._keybindings_edit_popover_listbox.set_vexpand(True)
        self._keybindings_edit_popover_listbox.set_selection_mode(
            Gtk.SelectionMode.SINGLE)
        self._keybindings_edit_popover_listbox.set_activate_on_single_click(
            True)
        self._keybindings_edit_popover_listbox.connect(
            'row-selected', self._on_keybindings_edit_listbox_row_selected)
        for keybinding in self._settings_dict['keybindings']['user'][
                self._keybindings_selected_command]:
            label = Gtk.Label()
            label.set_text(html.escape(keybinding))
            label.set_use_markup(True)
            label.set_xalign(0)
            margin = 1
            label.set_margin_start(margin)
            label.set_margin_end(margin)
            label.set_margin_top(margin)
            label.set_margin_bottom(margin)
            self._keybindings_edit_popover_listbox.insert(label, -1)
        self._keybindings_edit_popover_remove_button.set_sensitive(False)
        self._keybindings_edit_popover_listbox.show_all()

    def _create_and_show_keybindings_edit_popover(self) -> None:
        '''
        Create and show the popover to edit the key bindings for a command
        '''
        self._keybindings_edit_popover = Gtk.Popover()
        if self._keybindings_edit_popover is None:
            LOGGER.debug('self._keybindings_edit_popover is None')
            return
        self._keybindings_edit_popover.set_relative_to(
            self._keybindings_edit_button)
        self._keybindings_edit_popover.set_position(Gtk.PositionType.RIGHT)
        self._keybindings_edit_popover.set_vexpand(True)
        self._keybindings_edit_popover.set_hexpand(True)
        keybindings_edit_popover_vbox = Gtk.Box()
        keybindings_edit_popover_vbox.set_orientation(
            Gtk.Orientation.VERTICAL)
        margin = 12
        keybindings_edit_popover_vbox.set_margin_start(margin)
        keybindings_edit_popover_vbox.set_margin_end(margin)
        keybindings_edit_popover_vbox.set_margin_top(margin)
        keybindings_edit_popover_vbox.set_margin_bottom(margin)
        keybindings_edit_popover_vbox.set_spacing(margin)
        keybindings_edit_popover_label = Gtk.Label()
        keybindings_edit_popover_label.set_text(
            _('Edit key bindings for command “%s”')
            %self._keybindings_selected_command)
        keybindings_edit_popover_label.set_use_markup(True)
        keybindings_edit_popover_label.set_visible(True)
        keybindings_edit_popover_label.set_halign(Gtk.Align.FILL)
        keybindings_edit_popover_vbox.add(
            keybindings_edit_popover_label)
        self._keybindings_edit_popover_scroll = Gtk.ScrolledWindow()
        self._keybindings_edit_popover_scroll.set_hexpand(True)
        self._keybindings_edit_popover_scroll.set_vexpand(True)
        self._keybindings_edit_popover_scroll.set_kinetic_scrolling(False)
        self._keybindings_edit_popover_scroll.set_overlay_scrolling(True)
        keybindings_edit_popover_vbox.add(
            self._keybindings_edit_popover_scroll)
        keybindings_edit_popover_button_box = Gtk.Box()
        keybindings_edit_popover_button_box.set_orientation(
            Gtk.Orientation.HORIZONTAL)
        keybindings_edit_popover_button_box.set_can_focus(False)
        keybindings_edit_popover_vbox.add(
            keybindings_edit_popover_button_box)
        self._keybindings_edit_popover_add_button = Gtk.Button()
        keybindings_edit_popover_add_button_label = Gtk.Label()
        keybindings_edit_popover_add_button_label.set_text(
            '<span size="xx-large"><b>+</b></span>')
        keybindings_edit_popover_add_button_label.set_use_markup(True)
        self._keybindings_edit_popover_add_button.add(
            keybindings_edit_popover_add_button_label)
        self._keybindings_edit_popover_add_button.set_tooltip_text(
            _('Add a key binding'))
        self._keybindings_edit_popover_add_button.connect(
            'clicked', self._on_keybindings_edit_popover_add_button_clicked)
        self._keybindings_edit_popover_add_button.set_sensitive(True)
        self._keybindings_edit_popover_remove_button = Gtk.Button()
        keybindings_edit_popover_remove_button_label = Gtk.Label()
        keybindings_edit_popover_remove_button_label.set_text(
            '<span size="xx-large"><b>-</b></span>')
        keybindings_edit_popover_remove_button_label.set_use_markup(True)
        self._keybindings_edit_popover_remove_button.add(
            keybindings_edit_popover_remove_button_label)
        self._keybindings_edit_popover_remove_button.set_tooltip_text(
            _('Remove selected key binding'))
        self._keybindings_edit_popover_remove_button.connect(
            'clicked', self._on_keybindings_edit_popover_remove_button_clicked)
        self._keybindings_edit_popover_remove_button.set_sensitive(False)
        self._keybindings_edit_popover_default_button = Gtk.Button()
        keybindings_edit_popover_default_button_label = Gtk.Label()
        keybindings_edit_popover_default_button_label.set_text(
            _('Set to default'))
        keybindings_edit_popover_default_button_label.set_use_markup(True)
        self._keybindings_edit_popover_default_button.add(
            keybindings_edit_popover_default_button_label)
        self._keybindings_edit_popover_default_button.set_tooltip_text(
            _('Set default key bindings for the selected command'))
        self._keybindings_edit_popover_default_button.connect(
            'clicked',
            self._on_keybindings_edit_popover_default_button_clicked)
        self._keybindings_edit_popover_default_button.set_sensitive(True)
        keybindings_edit_popover_button_box.add(
            self._keybindings_edit_popover_add_button)
        keybindings_edit_popover_button_box.add(
            self._keybindings_edit_popover_remove_button)
        keybindings_edit_popover_button_box.add(
            self._keybindings_edit_popover_default_button)
        self._keybindings_edit_popover.add(keybindings_edit_popover_vbox)
        self._fill_keybindings_edit_popover_listbox()
        if GTK_VERSION >= (3, 22, 0):
            self._keybindings_edit_popover.popup()
        self._keybindings_edit_popover.show_all()

    def _on_keybindings_edit_button_clicked(self, *_args: Any) -> None:
        '''
        Signal handler called when the “edit” button to edit the
        key bindings for a command has been clicked.
        '''
        self._create_and_show_keybindings_edit_popover()

    def _on_keybindings_default_button_clicked(self, *_args: Any) -> None:
        '''
        Signal handler called when the “Set to default” button to reset the
        key bindings for a command to the default has been clicked.
        '''
        default_keybindings = self._settings_dict['keybindings']['default']
        command = self._keybindings_selected_command
        if command and command in default_keybindings:
            new_keybindings = self._settings_dict['keybindings']['user']
            new_keybindings[command] = default_keybindings[command]
            self.set_keybindings(new_keybindings)

    def _on_keybindings_all_default_button_clicked(self, *_args: Any) -> None:
        '''
        Signal handler called when the “Set all to default” button to reset the
        all key bindings top their defaults has been clicked.
        '''
        self._keybindings_all_default_button.set_sensitive(False)
        response = self._run_are_you_sure_dialog(
            # Translators: This is the text in the centre of a small
            # dialog window, trying to confirm whether the user is
            # really sure to reset the key bindings for *all* commands
            # to their defaults. This cannot be reversed so the user
            # should be really sure he wants to do that.
            _('Do you really want to set the key bindings for '
              'all commands to their defaults?'))
        if response == Gtk.ResponseType.OK:
            default_keybindings = self._settings_dict['keybindings']['default']
            self.set_keybindings(default_keybindings)
        self._keybindings_all_default_button.set_sensitive(True)

    def _on_learn_from_file_clicked(self, _widget: Gtk.Button) -> None:
        '''
        The button to learn from a user supplied text file
        has been clicked.
        '''
        self._learn_from_file_button.set_sensitive(False)
        filename = ''
        chooser = Gtk.FileChooserDialog(
            title=_('Open File ...'),
            parent=self,
            action=Gtk.FileChooserAction.OPEN)
        chooser.add_button(_('_Cancel'), Gtk.ResponseType.CANCEL)
        chooser.add_button(_('_OK'), Gtk.ResponseType.OK)
        response = chooser.run()
        if response == Gtk.ResponseType.OK:
            filename = chooser.get_filename()
        chooser.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration()
        if filename and os.path.isfile(filename):
            if self.tabsqlitedb.read_training_data_from_file(filename):
                dialog = Gtk.MessageDialog(
                    parent=self,
                    flags=Gtk.DialogFlags.MODAL,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    message_format=(
                        _("Learned successfully from file %(filename)s.")
                        %{'filename': filename}))
            else:
                dialog = Gtk.MessageDialog(
                    parent=self,
                    flags=Gtk.DialogFlags.MODAL,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    message_format=(
                        _("Learning from file %(filename)s failed.")
                        %{'filename': filename}))
            dialog.run()
            dialog.destroy()
        self._learn_from_file_button.set_sensitive(True)

    def _on_delete_learned_data_clicked(self, _widget: Gtk.Button) -> None:
        '''
        The button requesting to delete all data learned from
        user input or text files has been clicked.
        '''
        self._delete_learned_data_button.set_sensitive(False)
        response = self._run_are_you_sure_dialog(
            # Translators: This is the text in the centre of a small
            # dialog window, trying to confirm whether the user is
            # really sure to to delete all the data
            # ibus-typing-booster has learned from what the user has
            # typed or from text files the user has given as input to
            # learn from. If the user has used ibus-typing-booster for
            # a long time, predictions are much better than in the
            # beginning because of the learning from user
            # input. Deleting this learned data cannot be reversed. So
            # the user should be really sure he really wants to do that.
            _('Do you really want to delete all language '
              'data learned from typing or reading files?'))
        if response == Gtk.ResponseType.OK:
            self.tabsqlitedb.remove_all_phrases()
        self._delete_learned_data_button.set_sensitive(True)

    def set_avoid_forward_key_event(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to avoid forward_key_event() or not

        :param mode: Whether to avoid forward_key_event() or not
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['avoidforwardkeyevent']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'avoidforwardkeyevent',
                GLib.Variant.new_boolean(mode))
        else:
            self._avoid_forward_key_event_checkbutton.set_active(mode)

    def set_arrow_keys_reopen_preedit(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether the arrow keys are allowed to reopen a preëdit

        :param mode: Whether arrow keys can reopen a preëdit
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['arrowkeysreopenpreedit']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'arrowkeysreopenpreedit',
                GLib.Variant.new_boolean(mode))
        else:
            self._arrow_keys_reopen_preedit_checkbutton.set_active(mode)

    def set_disable_in_terminals(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether the to disable Typing Booster in terminals

        :param mode: Whether to disable Typing Booster in terminals
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['disableinterminals']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'disableinterminals',
                GLib.Variant.new_boolean(mode))
        else:
            self._disable_in_terminals_checkbutton.set_active(mode)

    def set_ascii_digits(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether the to convert language specific digits to ASCII digits

        :param mode: Whether to convert language specific digits
                     to ASCII digits
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['asciidigits']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'asciidigits',
                GLib.Variant.new_boolean(mode))
        else:
            self._ascii_digits_checkbutton.set_active(mode)

    def set_emoji_prediction_mode(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the emoji prediction mode

        :param mode: Whether to switch emoji prediction on or off
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['emojipredictions']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'emojipredictions',
                GLib.Variant.new_boolean(mode))
        else:
            self._emoji_predictions_checkbutton.set_active(mode)

    def set_off_the_record_mode(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Off the record” mode

        :param mode: Whether to prevent saving input to the
                     user database or not
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['offtherecord']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'offtherecord',
                GLib.Variant.new_boolean(mode))
        else:
            self._off_the_record_checkbutton.set_active(mode)

    def set_emoji_trigger_characters(
            self,
            emoji_trigger_characters: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the emoji trigger characters

        :param emoji_trigger_characters: The characters which trigger a commit
                                         with an extra space
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)',
            emoji_trigger_characters, update_gsettings)
        if not isinstance(emoji_trigger_characters, str):
            return
        self._settings_dict[
            'emojitriggercharacters']['user'] = emoji_trigger_characters
        if update_gsettings:
            self._gsettings.set_value(
                'emojitriggercharacters',
                GLib.Variant.new_string(emoji_trigger_characters))
        else:
            self._emoji_trigger_characters_entry.set_text(
                emoji_trigger_characters)

    def set_auto_commit_characters(
            self,
            auto_commit_characters: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the auto commit characters

        :param auto_commit_characters: The characters which trigger a commit
                                       with an extra space
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)',
            auto_commit_characters, update_gsettings)
        if not isinstance(auto_commit_characters, str):
            return
        self._settings_dict[
            'autocommitcharacters']['user'] = auto_commit_characters
        if update_gsettings:
            self._gsettings.set_value(
                'autocommitcharacters',
                GLib.Variant.new_string(auto_commit_characters))
        else:
            self._auto_commit_characters_entry.set_text(
                auto_commit_characters)

    def set_google_application_credentials(
            self,
            path: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the path of the Google application credentials file

        :param path: Full path of the Google application credentials
                     .json file.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', path, update_gsettings)
        if not isinstance(path, str):
            return
        self._settings_dict['googleapplicationcredentials']['user'] = path
        if update_gsettings:
            self._gsettings.set_value(
                'googleapplicationcredentials',
                GLib.Variant.new_string(path))
        else:
            self._google_application_credentials_button_label.set_text(
                path)

    def set_color_preedit_spellcheck(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to do spellchecking on the contents of the preedit

        :param mode: Whether to do spellchecking on the contents of the preedit
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['colorpreeditspellcheck']['user'] = mode
        self._color_preedit_spellcheck_rgba_colorbutton.set_sensitive(mode)
        if update_gsettings:
            self._gsettings.set_value(
                'colorpreeditspellcheck',
                GLib.Variant.new_boolean(mode))
        else:
            self._color_preedit_spellcheck_checkbutton.set_active(mode)

    def set_color_preedit_spellcheck_string(
            self,
            color_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the color to indicate spelling errors in the preedit

        :param color_string: Color to indicate spelling errors in the preedit
                            - Standard name from the X11 rgb.txt
                            - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                         or ”#rrrrggggbbbb”
                            - RGB color: “rgb(r,g,b)”
                            - RGBA color: “rgba(r,g,b,a)”
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', color_string, update_gsettings)
        if not isinstance(color_string, str):
            return
        self._settings_dict[
            'colorpreeditspellcheckstring']['user'] = color_string
        if update_gsettings:
            self._gsettings.set_value(
                'colorpreeditspellcheckstring',
                GLib.Variant.new_string(color_string))
        else:
            gdk_rgba = Gdk.RGBA()
            gdk_rgba.parse(color_string)
            self._color_preedit_spellcheck_rgba_colorbutton.set_rgba(gdk_rgba)

    def set_color_inline_completion(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use color for inline completion

        :param mode: Whether to use color for inline completion
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['colorinlinecompletion']['user'] = mode
        self._color_inline_completion_rgba_colorbutton.set_sensitive(mode)
        if update_gsettings:
            self._gsettings.set_value(
                'colorinlinecompletion',
                GLib.Variant.new_boolean(mode))
        else:
            self._color_inline_completion_checkbutton.set_active(mode)

    def set_color_inline_completion_string(
            self,
            color_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the color for inline completion

        :param color_string: The color for inline completion
                            - Standard name from the X11 rgb.txt
                            - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                         or ”#rrrrggggbbbb”
                            - RGB color: “rgb(r,g,b)”
                            - RGBA color: “rgba(r,g,b,a)”
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', color_string, update_gsettings)
        if not isinstance(color_string, str):
            return
        self._settings_dict[
            'colorinlinecompletionstring']['user'] = color_string
        if update_gsettings:
            self._gsettings.set_value(
                'colorinlinecompletionstring',
                GLib.Variant.new_string(color_string))
        else:
            gdk_rgba = Gdk.RGBA()
            gdk_rgba.parse(color_string)
            self._color_inline_completion_rgba_colorbutton.set_rgba(gdk_rgba)

    def set_color_compose_preview(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use color for the compose preview

        :param mode: Whether to use color for the compose preview
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['colorcomposepreview']['user'] = mode
        self._color_compose_preview_rgba_colorbutton.set_sensitive(mode)
        if update_gsettings:
            self._gsettings.set_value(
                'colorcomposepreview',
                GLib.Variant.new_boolean(mode))
        else:
            self._color_compose_preview_checkbutton.set_active(mode)

    def set_color_compose_preview_string(
            self,
            color_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the color for the compose preview

        :param color_string: The color for the compose preview
                            - Standard name from the X11 rgb.txt
                            - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                         or ”#rrrrggggbbbb”
                            - RGB color: “rgb(r,g,b)”
                            - RGBA color: “rgba(r,g,b,a)”
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', color_string, update_gsettings)
        if not isinstance(color_string, str):
            return
        self._settings_dict[
            'colorcomposepreviewstring']['user'] = color_string
        if update_gsettings:
            self._gsettings.set_value(
                'colorcomposepreviewstring',
                GLib.Variant.new_string(color_string))
        else:
            gdk_rgba = Gdk.RGBA()
            gdk_rgba.parse(color_string)
            self._color_compose_preview_rgba_colorbutton.set_rgba(gdk_rgba)

    def set_color_userdb(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use color for user database suggestions

        :param mode: Whether to use color for user database suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['coloruserdb']['user'] = mode
        self._color_userdb_rgba_colorbutton.set_sensitive(mode)
        if update_gsettings:
            self._gsettings.set_value(
                'coloruserdb',
                GLib.Variant.new_boolean(mode))
        else:
            self._color_userdb_checkbutton.set_active(mode)

    def set_color_userdb_string(
            self,
            color_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the color for user database suggestions

        :param color_string: The color for user database suggestions
                            - Standard name from the X11 rgb.txt
                            - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                         or ”#rrrrggggbbbb”
                            - RGB color: “rgb(r,g,b)”
                            - RGBA color: “rgba(r,g,b,a)”
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', color_string, update_gsettings)
        if not isinstance(color_string, str):
            return
        self._settings_dict['coloruserdbstring']['user'] = color_string
        if update_gsettings:
            self._gsettings.set_value(
                'coloruserdbstring',
                GLib.Variant.new_string(color_string))
        else:
            gdk_rgba = Gdk.RGBA()
            gdk_rgba.parse(color_string)
            self._color_userdb_rgba_colorbutton.set_rgba(gdk_rgba)

    def set_color_spellcheck(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use color for spellchecking suggestions

        :param mode: Whether to use color for spellchecking suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['colorspellcheck']['user'] = mode
        self._color_spellcheck_rgba_colorbutton.set_sensitive(mode)
        if update_gsettings:
            self._gsettings.set_value(
                'colorspellcheck',
                GLib.Variant.new_boolean(mode))
        else:
            self._color_spellcheck_checkbutton.set_active(mode)

    def set_color_spellcheck_string(
            self,
            color_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the color for spellchecking suggestions

        :param color_string: The color for spellchecking suggestions
                            - Standard name from the X11 rgb.txt
                            - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                         or ”#rrrrggggbbbb”
                            - RGB color: “rgb(r,g,b)”
                            - RGBA color: “rgba(r,g,b,a)”
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', color_string, update_gsettings)
        if not isinstance(color_string, str):
            return
        self._settings_dict['colorspellcheckstring']['user'] = color_string
        if update_gsettings:
            self._gsettings.set_value(
                'colorspellcheckstring',
                GLib.Variant.new_string(color_string))
        else:
            gdk_rgba = Gdk.RGBA()
            gdk_rgba.parse(color_string)
            self._color_spellcheck_rgba_colorbutton.set_rgba(gdk_rgba)

    def set_color_dictionary(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use color for dictionary suggestions

        :param mode: Whether to use color for dictionary suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['colordictionary']['user'] = mode
        self._color_dictionary_rgba_colorbutton.set_sensitive(mode)
        if update_gsettings:
            self._gsettings.set_value(
                'colordictionary',
                GLib.Variant.new_boolean(mode))
        else:
            self._color_dictionary_checkbutton.set_active(mode)

    def set_color_dictionary_string(
            self,
            color_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the color for dictionary suggestions

        :param color_string: The color for dictionary suggestions
                            - Standard name from the X11 rgb.txt
                            - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                         or ”#rrrrggggbbbb”
                            - RGB color: “rgb(r,g,b)”
                            - RGBA color: “rgba(r,g,b,a)”
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', color_string, update_gsettings)
        if not isinstance(color_string, str):
            return
        self._settings_dict['colordictionarystring']['user'] = color_string
        if update_gsettings:
            self._gsettings.set_value(
                'colordictionarystring',
                GLib.Variant.new_string(color_string))
        else:
            gdk_rgba = Gdk.RGBA()
            gdk_rgba.parse(color_string)
            self._color_dictionary_rgba_colorbutton.set_rgba(gdk_rgba)

    def set_label_userdb(
            self, mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use a label for user database

        :param mode: Whether to use a label for user database suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['labeluserdb']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'labeluserdb',
                GLib.Variant.new_boolean(mode))
        else:
            self._label_userdb_checkbutton.set_active(mode)

    def set_label_userdb_string(
            self,
            label_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the label for user database suggestions

        :param label_string: The label for user database suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', label_string, update_gsettings)
        if not isinstance(label_string, str):
            return
        self._settings_dict['labeluserdbstring']['user'] = label_string
        if update_gsettings:
            self._gsettings.set_value(
                'labeluserdbstring',
                GLib.Variant.new_string(label_string))
        else:
            self._label_userdb_entry.set_text(label_string)

    def set_label_spellcheck(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use a label for spellchecking suggestions

        :param mode: Whether to use a label for spellchecking suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['labelspellcheck']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'labelspellcheck',
                GLib.Variant.new_boolean(mode))
        else:
            self._label_spellcheck_checkbutton.set_active(mode)

    def set_label_spellcheck_string(
            self,
            label_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the label for spellchecking suggestions

        :param label_string: The label for spellchecking suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', label_string, update_gsettings)
        if not isinstance(label_string, str):
            return
        self._settings_dict['labelspellcheckstring']['user'] = label_string
        if update_gsettings:
            self._gsettings.set_value(
                'labelspellcheckstring',
                GLib.Variant.new_string(label_string))
        else:
            self._label_spellcheck_entry.set_text(label_string)

    def set_label_dictionary(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use a label for dictionary suggestions

        :param mode: Whether to use a label for dictionary suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['labeldictionary']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'labeldictionary',
                GLib.Variant.new_boolean(mode))
        else:
            self._label_dictionary_checkbutton.set_active(mode)

    def set_label_dictionary_string(
            self,
            label_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the label for dictionary suggestions

        :param label_string: The label for dictionary suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', label_string, update_gsettings)
        if not isinstance(label_string, str):
            return
        self._settings_dict['labeldictionarystring']['user'] = label_string
        if update_gsettings:
            self._gsettings.set_value(
                'labeldictionarystring',
                GLib.Variant.new_string(label_string))
        else:
            self._label_dictionary_entry.set_text(label_string)

    def set_flag_dictionary(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use flags for dictionary suggestions

        :param mode: Whether to use flags for dictionary suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['flagdictionary']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'flagdictionary',
                GLib.Variant.new_boolean(mode))
        else:
            self._flag_dictionary_checkbutton.set_active(mode)

    def set_label_busy(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use a label to indicate busy state

        :param mode: Whether to use a label to indicate busy state
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['labelbusy']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'labelbusy',
                GLib.Variant.new_boolean(mode))
        else:
            self._label_busy_checkbutton.set_active(mode)

    def set_label_busy_string(
            self,
            label_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the label used to indicate busy state

        :param label_string: The label to indicate busy state
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', label_string, update_gsettings)
        if not isinstance(label_string, str):
            return
        self._settings_dict['labelbusystring']['user'] = label_string
        if update_gsettings:
            self._gsettings.set_value(
                'labelbusystring',
                GLib.Variant.new_string(label_string))
        else:
            self._label_busy_entry.set_text(label_string)

    def set_tab_enable(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Tab enable” mode

        :param mode: Whether to show a candidate list only when typing Tab
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['tabenable']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'tabenable',
                GLib.Variant.new_boolean(mode))
        else:
            self._tab_enable_checkbutton.set_active(mode)

    def set_inline_completion(
            self,
            mode: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Use inline completion” mode

        :param mode: Whether a completion is first shown inline in the preëdit
                     instead of using a combobox to show a candidate list.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = int(mode)
        self._settings_dict['inlinecompletion']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'inlinecompletion',
                GLib.Variant.new_int32(mode))
        else:
            for i, item in enumerate(self._inline_completion_store):
                if mode == item[1]:
                    self._inline_completion_combobox.set_active(i)

    def set_record_mode(
            self,
            mode: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Record mode”

        :param mode: Specifies how much to record
                     0: Everything
                     1: Correctly spelled or previously recorded words
                     2: Correctly spelled words
                     3: Nothing
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = int(mode)
        self._settings_dict['recordmode']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'recordmode',
                GLib.Variant.new_int32(mode))
        else:
            for i, item in enumerate(self._record_mode_store):
                if mode == item[1]:
                    self._record_mode_combobox.set_active(i)

    def set_auto_capitalize(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Auto capitalize” mode

        :param mode: Whether to automatically capitalize after punctuation.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['autocapitalize']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'autocapitalize',
                GLib.Variant.new_boolean(mode))
        else:
            self._auto_capitalize_checkbutton.set_active(mode)

    def set_remember_last_used_preedit_ime(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Remember last used preëdit ime” mode

        :param mode: Whether to remember the input method used last for
                     the preëdit
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['rememberlastusedpreeditime']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'rememberlastusedpreeditime',
                GLib.Variant.new_boolean(mode))
        else:
            self._remember_last_used_preedit_ime_checkbutton.set_active(mode)

    def set_remember_input_mode(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Remember input mode” mode

        :param mode: Whether to remember the input mode used last
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['rememberinputmode']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'rememberinputmode',
                GLib.Variant.new_boolean(mode))
        else:
            self._remember_input_mode_checkbutton.set_active(mode)

    def set_page_size(
            self,
            page_size: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the page size of the lookup table

        :param page_size: The page size of the lookup table
                          1 <= page_size <= 9
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', page_size, update_gsettings)
        page_size = int(page_size)
        if 1 <= page_size <= 9:
            self._settings_dict['pagesize']['user'] = page_size
            if update_gsettings:
                self._gsettings.set_value(
                    'pagesize',
                    GLib.Variant.new_int32(page_size))
            else:
                self._page_size_adjustment.set_value(int(page_size))

    def set_candidates_delay_milliseconds(
            self,
            milliseconds: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the delay of the candidates in milliseconds

        :param milliseconds: delay of the candidates in milliseconds
                             0 <= milliseconds <= itb_util.UINT32_MAX
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', milliseconds, update_gsettings)
        milliseconds = int(milliseconds)
        if 0 <= milliseconds <= itb_util.UINT32_MAX:
            self._settings_dict[
                'candidatesdelaymilliseconds']['user'] = milliseconds
            if update_gsettings:
                self._gsettings.set_value(
                    'candidatesdelaymilliseconds',
                    GLib.Variant.new_uint32(milliseconds))
            else:
                self._candidates_delay_milliseconds_adjustment.set_value(
                    int(milliseconds))

    def set_lookup_table_orientation(
            self,
            orientation: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the page size of the lookup table

        :param orientation: The orientation of the lookup table
                            0 <= orientation <= 2
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', orientation, update_gsettings)
        orientation = int(orientation)
        if 0 <= orientation <= 2:
            self._settings_dict['lookuptableorientation']['user'] = orientation
            if update_gsettings:
                self._gsettings.set_value(
                    'lookuptableorientation',
                    GLib.Variant.new_int32(orientation))
            else:
                for i, item in enumerate(self._lookup_table_orientation_store):
                    if orientation == item[1]:
                        self._lookup_table_orientation_combobox.set_active(i)

    def set_preedit_underline(
            self,
            underline_mode: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the underline mode of the preedit

        :param underline_mode: The underline mode to be used for the preedit
                              0 <= underline_mode <= 3
                              IBus.AttrUnderline.NONE    = 0,
                              IBus.AttrUnderline.SINGLE  = 1,
                              IBus.AttrUnderline.DOUBLE  = 2,
                              IBus.AttrUnderline.LOW     = 3,
                              IBus.AttrUnderline.ERROR   = 4,
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', underline_mode, update_gsettings)
        underline_mode = int(underline_mode)
        if 0 <= underline_mode < IBus.AttrUnderline.ERROR:
            self._settings_dict['preeditunderline']['user'] = underline_mode
            if update_gsettings:
                self._gsettings.set_value(
                    'preeditunderline',
                    GLib.Variant.new_int32(underline_mode))
            else:
                for i, item in enumerate(self._preedit_underline_store):
                    if underline_mode == item[1]:
                        self._preedit_underline_combobox.set_active(i)

    def set_min_char_complete(
            self,
            min_char_complete: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the minimum number of characters to try completion

        :param min_char_complete: The minimum number of characters
                                  to type before completion is tried.
                                  1 <= min_char_complete <= 9
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', min_char_complete, update_gsettings)
        min_char_complete = int(min_char_complete)
        if 0 <= min_char_complete <= 9:
            self._settings_dict['mincharcomplete']['user'] = min_char_complete
            if update_gsettings:
                self._gsettings.set_value(
                    'mincharcomplete',
                    GLib.Variant.new_int32(min_char_complete))
            else:
                self._min_char_complete_adjustment.set_value(
                    int(min_char_complete))

    def set_error_sound(
            self,
            error_sound: bool,
            update_gsettings: bool = True) -> None:
        '''Sets the whether to play a sound on error.

        :param error_sound: Whether to play a sound on error
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', error_sound, update_gsettings)
        error_sound = bool(error_sound)
        self._settings_dict['errorsound']['user'] = error_sound
        if update_gsettings:
            self._gsettings.set_value(
                'errorsound',
                GLib.Variant.new_boolean(error_sound))
        else:
            self._error_sound_checkbutton.set_active(error_sound)

    def set_error_sound_file(
            self,
            path: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the path of file containing the sound to play on error.

        :param path: Full path of the .wav file containing the error sound.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', path, update_gsettings)
        if not isinstance(path, str):
            return
        self._settings_dict['errorsoundfile']['user'] = path
        if update_gsettings:
            self._gsettings.set_value(
                'errorsoundfile',
                GLib.Variant.new_string(path))
        else:
            self._error_sound_file_button_label.set_text(path)
        error_sound_object = itb_sound.SoundObject(
            os.path.expanduser(self._settings_dict['errorsoundfile']['user']),
            audio_backend=self._settings_dict['soundbackend']['user'])
        if error_sound_object:
            try:
                error_sound_object.play()
                error_sound_object.wait_done()
            except Exception as error: # pylint: disable=broad-except
                LOGGER.exception('Playing error sound failed: %s: %s',
                                 error.__class__.__name__, error)

    def set_sound_backend(
            self,
            sound_backend: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the sound backend to use

        :param sound_backend: The name of sound backend to use
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the dconf key changed
                                 to avoid endless loops when the dconf
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', sound_backend, update_gsettings)
        if not isinstance(sound_backend, str):
            return
        self._settings_dict['soundbackend']['user'] = sound_backend
        if update_gsettings:
            self._gsettings.set_value(
                'soundbackend',
                GLib.Variant.new_string(sound_backend))
        error_sound_object = itb_sound.SoundObject(
            os.path.expanduser(self._settings_dict['errorsoundfile']['user']),
            audio_backend=self._settings_dict['soundbackend']['user'])
        if error_sound_object:
            try:
                error_sound_object.play()
                error_sound_object.wait_done()
            except Exception as error: # pylint: disable=broad-except
                LOGGER.exception('Playing error sound failed: %s: %s',
                                 error.__class__.__name__, error)

    def set_debug_level(
            self,
            debug_level: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the debug level

        :param debug_level: The debug level
                            0 <= debug_level <= 255
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', debug_level, update_gsettings)
        debug_level = int(debug_level)
        if 0 <= debug_level <= 255:
            self._settings_dict['debuglevel']['user'] = debug_level
            if update_gsettings:
                self._gsettings.set_value(
                    'debuglevel',
                    GLib.Variant.new_int32(debug_level))
            else:
                self._debug_level_adjustment.set_value(
                    int(debug_level))

    def set_show_number_of_candidates(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Show number of candidates” mode

        :param mode: Whether to show the number of candidates
                     in the auxiliary text
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['shownumberofcandidates']['user'] = mode
        self._show_number_of_candidates_checkbutton.set_active(mode)
        if update_gsettings:
            self._gsettings.set_value(
                'shownumberofcandidates',
                GLib.Variant.new_boolean(mode))

    def set_show_status_info_in_auxiliary_text(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Show status info in auxiliary text” mode

        :param mode: Whether to show status information in the
                     auxiliary text.
                     Currently the status information which can be
                     displayed there is whether emoji mode and
                     off-the-record mode are on or off
                     and which input method is currently used for
                     the preëdit text.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['showstatusinfoinaux']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'showstatusinfoinaux',
                GLib.Variant.new_boolean(mode))
        else:
            self._show_status_info_in_auxiliary_text_checkbutton.set_active(
                mode)

    def set_preedit_style_only_when_lookup(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Use preedit style only if lookup is enabled” mode

        :param mode: Whether a preedit style like underlining should
                     be enabled only when lookup is enabled.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['preeditstyleonlywhenlookup']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'preeditstyleonlywhenlookup',
                GLib.Variant.new_boolean(mode))
        else:
            self._preedit_style_only_when_lookup_checkbutton.set_active(mode)

    def set_auto_select_candidate(
            self,
            mode: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Automatically select the best candidate” mode

        :param mode: Whether to automatically select the best candidate
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = int(mode)
        self._settings_dict['autoselectcandidate']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'autoselectcandidate',
                GLib.Variant.new_int32(mode))
        else:
            for i, item in enumerate(self._auto_select_candidate_store):
                if mode == item[1]:
                    self._auto_select_candidate_combobox.set_active(i)

    def set_add_space_on_commit(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Add a space when committing by label or mouse” mode

        :param mode: Whether to add a space when committing by label or mouse
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', mode, update_gsettings)
        mode = bool(mode)
        self._settings_dict['addspaceoncommit']['user'] = mode
        if update_gsettings:
            self._gsettings.set_value(
                'addspaceoncommit',
                GLib.Variant.new_boolean(mode))
        else:
            self._add_space_on_commit_checkbutton.set_active(mode)

    def set_current_imes(
            self,
            imes: Union[str, List[str], Any],
            update_gsettings: bool = True) -> None:
        '''Set current list of input methods

        :param imes: List of input methods
                     If a single string is used, it should contain
                     the names of the input methods separated by commas.
                     If the string is empty, the default input
                     methods for the current locale are set.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.debug('imes=“%s” type(imes)=%s update_gsettings=%s',
                     imes, type(imes), update_gsettings)
        if isinstance(imes, str):
            imes = itb_util.input_methods_str_to_list(imes)
        if imes == self._current_imes: # nothing to do
            return
        self._current_imes = imes
        self._fill_input_methods_listbox()
        if update_gsettings:
            self._gsettings.set_value(
                'inputmethod',
                GLib.Variant.new_string(','.join(imes)))
        else:
            # unselect all rows:
            self._input_methods_listbox_selected_ime_name = ''
            self._input_methods_listbox_selected_ime_index = -1
            self._input_methods_remove_button.set_sensitive(False)
            self._input_methods_up_button.set_sensitive(False)
            self._input_methods_down_button.set_sensitive(False)
            self._input_methods_help_button.set_sensitive(False)


    def set_dictionary_names(
            self,
            dictionary_names: Union[str, List[str], Any],
            update_gsettings: bool = True) -> None:
        '''Set current dictionary names

        :param dictionary_names: List of names of dictionaries to use
                                 If a single string is used, it should contain
                                 the names of the dictionaries separated
                                 by commas.
                                 If the string is empty, the default
                                 dictionaries for the current locale are set.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.debug('dictionary_names=%s type(dictionary_names)=%s',
                     dictionary_names, type(dictionary_names))
        if isinstance(dictionary_names, str):
            dictionary_names = itb_util.dictionaries_str_to_list(
                dictionary_names)
        if dictionary_names == self._dictionary_names: # nothing to do
            return
        self._dictionary_names = dictionary_names
        self._fill_dictionaries_listbox()
        if update_gsettings:
            self._gsettings.set_value(
                'dictionary',
                GLib.Variant.new_string(','.join(dictionary_names)))
        else:
            # unselect all rows:
            self._dictionaries_listbox_selected_dictionary_name = ''
            self._dictionaries_listbox_selected_dictionary_index = -1
            self._dictionaries_remove_button.set_sensitive(False)
            self._dictionaries_up_button.set_sensitive(False)
            self._dictionaries_down_button.set_sensitive(False)

    def set_autosettings(
            self,
            autosettings: Union[List[Tuple[str, str, str]], Any],
            update_gsettings: bool = True) -> None:
        '''Set the current automatic settings

        :param autosettings: The automatic settings to use
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.debug('autosettings=%s', autosettings)
        if not isinstance(autosettings, list):
            return
        self._settings_dict['autosettings']['user'] = autosettings
        if update_gsettings:
            self._fill_autosettings_treeview()
            variant_array = GLib.Variant.new_array(GLib.VariantType('as'), [
                    GLib.Variant.new_array(GLib.VariantType('s'), [
                        GLib.Variant.new_string(x) for x in autosetting])
                    for autosetting in autosettings
                ])
            self._gsettings.set_value(
                'autosettings',
                variant_array)
        else:
            LOGGER.debug('Unselecting all rows and updating button status')
            self._autosettings_selected_index = -1
            self._fill_autosettings_treeview()

    def set_keybindings(
            self,
            keybindings: Union[Dict[str, List[str]], Any],
            update_gsettings: bool = True) -> None:
        '''Set current key bindings

        :param keybindings: The key bindings to use
                            Commands which do not already
                            exist in the current key bindings dictionary
                            will be ignored.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.info(
            '(%s, update_gsettings = %s)', keybindings, update_gsettings)
        if not isinstance(keybindings, dict):
            return
        keybindings = copy.deepcopy(keybindings)
        user_keybindings = self._settings_dict['keybindings']['user']
        # Update the default settings with the possibly changed settings:
        itb_util.dict_update_existing_keys(user_keybindings, keybindings)
        # update the tree model
        model = self._keybindings_treeview_model
        iterator = model.get_iter_first()
        while iterator:
            for command in user_keybindings:
                if model.get_value(iterator, 0) == command:
                    model.set_value(iterator, 1,
                                    repr(user_keybindings[command]))
            iterator = model.iter_next(iterator)
        # Show the checkbutton in the options tab to choose whether to
        # remember the input mode only when there is a keybinding to
        # toggle the input mode:
        if user_keybindings['toggle_input_mode_on_off']:
            self._remember_input_mode_checkbutton.show()
        else:
            self._remember_input_mode_checkbutton.hide()
        if update_gsettings:
            variant_dict = GLib.VariantDict(GLib.Variant('a{sv}', {}))
            for command in sorted(user_keybindings):
                variant_array = GLib.Variant.new_array(
                    GLib.VariantType('s'),
                    [GLib.Variant.new_string(x)
                     for x in user_keybindings[command]])
                variant_dict.insert_value(command, variant_array)
            self._gsettings.set_value(
                'keybindings',
                variant_dict.end())

class HelpWindow(Gtk.Window): # type: ignore
    '''
    A window to show help

    :param parent: The parent object
    :param title: Title of the help window
    :param contents: Contents of the help window
    '''
    def __init__(self,
                 parent: Gtk.Window = None,
                 title: str = '',
                 contents: str = '') -> None:
        Gtk.Window.__init__(self, title=title)
        if parent:
            self.set_parent(parent)
            self.set_transient_for(parent)
            # to receive mouse events for scrolling and for the close
            # button
            self.set_modal(True)
        self.set_destroy_with_parent(False)
        self.set_default_size(600, 500)
        self.vbox = Gtk.Box()
        self.vbox.set_orientation(Gtk.Orientation.VERTICAL)
        self.vbox.set_spacing(0)
        self.add(self.vbox)
        self.text_buffer = Gtk.TextBuffer()
        self.text_buffer.insert_at_cursor(contents)
        self.text_view = Gtk.TextView()
        self.text_view.set_buffer(self.text_buffer)
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_view.set_justification(Gtk.Justification.LEFT)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.scrolledwindow = Gtk.ScrolledWindow()
        self.scrolledwindow.set_hexpand(True)
        self.scrolledwindow.set_vexpand(True)
        self.scrolledwindow.add(self.text_view)
        self.vbox.pack_start(self.scrolledwindow, True, True, 0)
        self.close_button = Gtk.Button()
        self.close_button_label = Gtk.Label()
        self.close_button_label.set_text_with_mnemonic(_('_Close'))
        self.close_button.add(self.close_button_label)
        self.close_button.set_hexpand(True)
        self.close_button.set_halign(Gtk.Align.END)
        self.close_button.connect("clicked", self._on_close_button_clicked)
        self.hbox = Gtk.Box(spacing=0)
        self.hbox.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.hbox.set_spacing(0)
        self.hbox.add(self.close_button)
        self.vbox.pack_start(self.hbox, False, False, 5)
        self.show_all()

    def _on_close_button_clicked(self, _button: Gtk.Button) -> None:
        '''
        Close the input method help window when the close button is clicked
        '''
        self.destroy()

if __name__ == '__main__':
    if _ARGS.no_debug:
        log_handler_null = logging.NullHandler()
    else:
        if (not os.access(
                os.path.expanduser('~/.local/share/ibus-typing-booster'),
                os.F_OK)):
            os.system('mkdir -p ~/.local/share/ibus-typing-booster')
        logfile = os.path.expanduser(
            '~/.local/share/ibus-typing-booster/setup-debug.log')
        log_handler_time_rotate = logging.handlers.TimedRotatingFileHandler(
            logfile,
            when='H',
            interval=6,
            backupCount=7,
            encoding='UTF-8',
            delay=False,
            utc=False,
            atTime=None)
        log_formatter = logging.Formatter(
            '%(asctime)s %(filename)s '
            'line %(lineno)d %(funcName)s %(levelname)s: '
            '%(message)s')
        log_handler_time_rotate.setFormatter(log_formatter)
        LOGGER.setLevel(logging.DEBUG)
        LOGGER.addHandler(log_handler_time_rotate)
        LOGGER.info('*** ibus-typing-booster %s setup starting ***',
                    itb_version.get_version())

    # Workaround for
    # https://bugzilla.gnome.org/show_bug.cgi?id=622084
    # Bug 622084 - Ctrl+C does not exit gtk app
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        LOGGER.exception("IBUS-WARNING **: Using the fallback 'C' locale")
        locale.setlocale(locale.LC_ALL, 'C')
    i18n_init()
    if IBus.get_address() is None:
        DIALOG = Gtk.MessageDialog(
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=_('ibus is not running.'))
        DIALOG.run()
        DIALOG.destroy()
        sys.exit(1)
    M17N_DB_INFO = itb_util.M17nDbInfo()
    ENGINE_NAME = _ARGS.engine_name
    LOGGER.info('engine name “%s”', ENGINE_NAME)
    SETUP_UI = SetupUI(engine_name=_ARGS.engine_name)
    Gtk.main()
