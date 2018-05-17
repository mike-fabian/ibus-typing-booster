# -*- coding: utf-8 -*-
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

import sys
import os
from os import path
import re
import html
import signal
import argparse
import locale
from time import strftime
import dbus
import dbus.service
import dbus.glib

from gi import require_version
require_version('GLib', '2.0')
from gi.repository import GLib

# set_prgname before importing other modules to show the name in warning
# messages when import modules are failed. E.g. Gtk.
GLib.set_application_name('Typing Booster Preferences')
# This makes gnome-shell load the .desktop file when running under Wayland:
GLib.set_prgname('ibus-setup-typing-booster')

require_version('Gdk', '3.0')
from gi.repository import Gdk
require_version('Gtk', '3.0')
from gi.repository import Gtk
require_version('IBus', '1.0')
from gi.repository import IBus
from pkginstall import InstallPkg
from i18n import DOMAINNAME, _, init as i18n_init

sys.path = [sys.path[0]+'/../engine'] + sys.path
import tabsqlitedb
import itb_util
import itb_emoji

import version

GTK_VERSION = (Gtk.get_major_version(),
               Gtk.get_minor_version(),
               Gtk.get_micro_version())

def parse_args():
    '''
    Parse the command line arguments.
    '''
    parser = argparse.ArgumentParser(
        description='ibus-typing-booster setup tool')
    parser.add_argument(
        '-q', '--no-debug',
        action='store_true',
        default=False,
        help=('Do not redirect stdout and stderr to '
              + '~/.local/share/ibus-typing-booster/setup-debug.log, '
              + 'default: %(default)s'))
    return parser.parse_args()

_ARGS = parse_args()

class SetupUI(Gtk.Window):
    '''
    User interface of the setup tool
    '''
    def __init__(self, bus):
        ## fixme: if not self.check_instance():
        ##    dummy_service = SetupService()
        dummy_service = SetupService()
        Gtk.Window.__init__(self, title='🚀 ' + _('Preferences'))
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

        self.tabsqlitedb = tabsqlitedb.tabsqlitedb()
        self.config_section = "engine/typing-booster"

        self.bus = bus
        self.config = self.bus.get_config()
        self.set_title('🚀 ' + _('Preferences for ibus-typing-booster'))
        # https://tronche.com/gui/x/icccm/sec-4.html#WM_CLASS
        # gnome-shell seems to use the first argument of set_wmclass()
        # to find the .desktop file.  If the .desktop file can be
        # found, the name shown by gnome-shell in the top bar comes
        # from that .desktop file and the icon to show is also read
        # from that .desktop file. If the .desktop file cannot be
        # found, the second argument of set_wmclass() is shown by
        # gnome-shell in the top bar.
        #
        # It only works like this when gnome-shell runs under Xorg
        # though, under Wayland things are different.
        self.set_wmclass('ibus-setup-typing-booster', 'Typing Booster Preferences')

        self.connect('destroy-event', self.on_destroy_event)
        self.connect('delete-event', self.on_delete_event)

        self._main_container = Gtk.VBox()
        self.add(self._main_container)
        self._notebook = Gtk.Notebook()
        self._notebook.set_visible(True)
        self._notebook.set_can_focus(False)
        self._notebook.set_scrollable(False)
        self._main_container.pack_start(self._notebook, True, True, 0)
        self._dialog_action_area = Gtk.ButtonBox()
        self._dialog_action_area.set_can_focus(False)
        self._dialog_action_area.set_layout(Gtk.ButtonBoxStyle.END)
        self._main_container.pack_end(self._dialog_action_area, True, True, 0)
        self._close_button = Gtk.Button(stock=Gtk.STOCK_CLOSE)
        self._close_button.connect('clicked', self.on_close_clicked)
        self._dialog_action_area.add(self._close_button)
        self._options_grid = Gtk.Grid()
        self._options_grid.set_visible(True)
        self._options_grid.set_can_focus(False)
        self._options_grid.set_border_width(6)
        self._options_grid.set_column_spacing(6)
        self._options_grid.set_row_homogeneous(True)
        self._options_grid.set_column_homogeneous(True)
        self._options_label = Gtk.Label(
            _('Options'))
        self._dictionaries_and_input_methods_vbox = Gtk.VBox()
        margin = 10
        self._dictionaries_and_input_methods_vbox.set_margin_start(margin)
        self._dictionaries_and_input_methods_vbox.set_margin_end(margin)
        self._dictionaries_and_input_methods_vbox.set_margin_top(margin)
        self._dictionaries_and_input_methods_vbox.set_margin_bottom(margin)
        self._dictionaries_and_input_methods_label = Gtk.Label(
            _('Dictionaries and input methods'))
        self._custom_shortcuts_grid = Gtk.Grid()
        self._custom_shortcuts_grid.set_visible(True)
        self._custom_shortcuts_grid.set_can_focus(False)
        self._custom_shortcuts_grid.set_border_width(6)
        self._custom_shortcuts_grid.set_column_spacing(6)
        self._custom_shortcuts_grid.set_row_homogeneous(True)
        self._custom_shortcuts_grid.set_column_homogeneous(True)
        self._custom_shortcuts_label = Gtk.Label(
            _('Custom shortcuts'))
        self._dictionaries_and_personal_data_grid = Gtk.Grid()
        self._dictionaries_and_personal_data_grid.set_visible(True)
        self._dictionaries_and_personal_data_grid.set_can_focus(False)
        self._dictionaries_and_personal_data_grid.set_border_width(6)
        self._dictionaries_and_personal_data_grid.set_column_spacing(6)
        self._dictionaries_and_personal_data_grid.set_row_spacing(6)
        self._dictionaries_and_personal_data_grid.set_row_homogeneous(True)
        self._dictionaries_and_personal_data_grid.set_column_homogeneous(True)
        self._dictionaries_and_personal_data_label = Gtk.Label(
            _('Personal data'))
        self._about_grid = Gtk.Grid()
        self._about_grid.set_visible(True)
        self._about_grid.set_can_focus(False)
        self._about_grid.set_margin_left(10)
        self._about_grid.set_margin_right(10)
        self._about_grid.set_margin_top(10)
        self._about_grid.set_margin_bottom(10)
        self._about_grid.set_border_width(6)
        self._about_grid.set_column_spacing(10)
        self._about_grid.set_row_spacing(10)
        self._about_grid.set_row_homogeneous(False)
        self._about_grid.set_column_homogeneous(True)
        self._about_label = Gtk.Label(
            _('About'))
        self._notebook.append_page(
            self._options_grid,
            self._options_label)
        self._notebook.append_page(
            self._dictionaries_and_input_methods_vbox,
            self._dictionaries_and_input_methods_label)
        self._notebook.append_page(
            self._custom_shortcuts_grid,
            self._custom_shortcuts_label)
        self._notebook.append_page(
            self._dictionaries_and_personal_data_grid,
            self._dictionaries_and_personal_data_label)
        self._notebook.append_page(
            self._about_grid,
            self._about_label)

        self._tab_enable_checkbutton = Gtk.CheckButton(
            _('Enable suggestions by Tab key'))
        self._tab_enable_checkbutton.set_tooltip_text(
            _('If this option is on, suggestions are not shown by default. Typing Tab is then necessary to show the list of suggestions. After a commit the suggestions are hidden again until the next Tab key is typed.'))
        self._tab_enable_checkbutton.connect(
            'clicked', self.on_tab_enable_checkbutton)
        self._options_grid.attach(
            self._tab_enable_checkbutton, 0, 0, 2, 1)
        self.tab_enable = itb_util.variant_to_value(
            self.config.get_value(self.config_section, 'tabenable'))
        if self.tab_enable is None:
            self.tab_enable = False
        if  self.tab_enable is True:
            self._tab_enable_checkbutton.set_active(True)

        self._show_number_of_candidates_checkbutton = Gtk.CheckButton(
            _('Display total number of candidates'))
        self._show_number_of_candidates_checkbutton.set_tooltip_text(
            _('Display how many candidates there are and which one is selected on top of the list of candidates.'))
        self._show_number_of_candidates_checkbutton.connect(
            'clicked', self.on_show_number_of_candidates_checkbutton)
        self._options_grid.attach(
            self._show_number_of_candidates_checkbutton, 0, 1, 2, 1)
        self.show_number_of_candidates = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'shownumberofcandidates'))
        if self.show_number_of_candidates is None:
            self.show_number_of_candidates = False
        if  self.show_number_of_candidates is True:
            self._show_number_of_candidates_checkbutton.set_active(True)

        self._show_status_info_in_auxiliary_text_checkbutton = Gtk.CheckButton(
            _('Show status info in auxiliary text'))
        self._show_status_info_in_auxiliary_text_checkbutton.set_tooltip_text(
            _('Show in the auxiliary text whether “Emoji prediction”  mode and “Off the record”  mode are on or off and show which input method is currently used for the preëdit. The auxiliary text is an optional line of text displayed above the candidate list.'))
        self._show_status_info_in_auxiliary_text_checkbutton.connect(
            'clicked', self.on_show_status_info_in_auxiliary_text_checkbutton)
        self._options_grid.attach(
            self._show_status_info_in_auxiliary_text_checkbutton, 0, 2, 2, 1)
        self.show_status_info_in_auxiliary_text = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'showstatusinfoinaux'))
        if self.show_status_info_in_auxiliary_text is None:
            self.show_status_info_in_auxiliary_text = False
        if self.show_status_info_in_auxiliary_text is True:
            self._show_status_info_in_auxiliary_text_checkbutton.set_active(True)

        self._use_digits_as_select_keys_checkbutton = Gtk.CheckButton(
            _('Use digits as select keys'))
        self._use_digits_as_select_keys_checkbutton.set_tooltip_text(
            _('Use the regular digits 1-9 as select keys. If that option is on, numbers can only by typed while no suggestions are shown. Therefore, completions for numbers cannot be suggested. And typing words containing numbers, like “A4” is more difficult as typing “4” would select the 4th suggestion. On the other hand, selecting suggestions using 1-9 is easier then using the always enabled select keys F1-F9 as the latter keys are farther away from the fingers.'))
        self._use_digits_as_select_keys_checkbutton.connect(
            'clicked', self.on_use_digits_as_select_keys_checkbutton)
        self._options_grid.attach(
            self._use_digits_as_select_keys_checkbutton, 0, 3, 2, 1)
        self.use_digits_as_select_keys = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'usedigitsasselectkeys'))
        if self.use_digits_as_select_keys is None:
            self.use_digits_as_select_keys = True
        if self.use_digits_as_select_keys is True:
            self._use_digits_as_select_keys_checkbutton.set_active(True)

        self._remember_last_used_preedit_ime_checkbutton = Gtk.CheckButton(
            _('Remember last used preedit input method'))
        self._remember_last_used_preedit_ime_checkbutton.set_tooltip_text(
            _('If more then one input method is used at the same time, one of them is used for the preedit.  Which input method is used for the preedit can be changed via the menu or via shortcut keys. If this option is enabled, such a change is remembered even if the session is restarted. '))
        self._remember_last_used_preedit_ime_checkbutton.connect(
            'clicked', self.on_remember_last_used_preedit_ime_checkbutton)
        self._options_grid.attach(
            self._remember_last_used_preedit_ime_checkbutton, 0, 4, 2, 1)
        self.remember_last_used_predit_ime = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'rememberlastusedpreeditime'))
        if self.remember_last_used_predit_ime is None:
            self.remember_last_used_predit_ime = False
        if  self.remember_last_used_predit_ime is True:
            self._remember_last_used_preedit_ime_checkbutton.set_active(True)

        self._emoji_predictions_checkbutton = Gtk.CheckButton(
            _('Unicode symbols and emoji predictions'))
        self._emoji_predictions_checkbutton.set_tooltip_text(
            _('Whether Unicode symbols and emoji should be included in the predictions. Emoji are pictographs like ☺♨⛵…. Unicode symbols are other symbols like mathematical symbols (∀∑∯…), arrows (←↑↔…), currency symbols (€₹₺…), braille patterns (⠥⠩…), and many other symbols. These are technically not emoji but nevertheless useful symbols.'))
        self._emoji_predictions_checkbutton.connect(
            'clicked', self.on_emoji_predictions_checkbutton)
        self._options_grid.attach(
            self._emoji_predictions_checkbutton, 0, 5, 2, 1)
        self.emoji_predictions = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'emojipredictions'))
        if self.emoji_predictions is None:
            self.emoji_predictions = True
        if self.emoji_predictions is True:
            self._emoji_predictions_checkbutton.set_active(True)

        self._off_the_record_checkbutton = Gtk.CheckButton(
            _('Off the record mode'))
        self._off_the_record_checkbutton.set_tooltip_text(
            _('While “Off the record” mode is on, learning from user input is disabled. If learned user input is available, predictions are usually much better than predictions using only dictionaries. Therefore, one should use this option sparingly. Only if one wants to avoid saving secret user input to disk it might make sense to use this option temporarily.'))
        self._off_the_record_checkbutton.connect(
            'clicked', self.on_off_the_record_checkbutton)
        self._options_grid.attach(
            self._off_the_record_checkbutton, 0, 6, 2, 1)
        self.off_the_record = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'offtherecord'))
        if self.off_the_record is None:
            self.off_the_record = False
        if self.off_the_record is True:
            self._off_the_record_checkbutton.set_active(True)

        self._qt_im_module_workaround_checkbutton = Gtk.CheckButton(
            _('Use a workaround for a bug in Qt im module'))
        self._qt_im_module_workaround_checkbutton.set_tooltip_text(
            _('Use a workaround for bugs in the input method modules of Qt4 and Qt5. Attention, although this workaround makes it work better when the Qt input modules are used, it causes problems when XIM is used. I.e. the XIM module of Qt4 will not work well when this workaround is enabled and input via XIM into X11 programs like xterm will not work well either.'))
        self._qt_im_module_workaround_checkbutton.connect(
            'clicked', self.on_qt_im_module_workaround_checkbutton)
        self._options_grid.attach(
            self._qt_im_module_workaround_checkbutton, 0, 7, 2, 1)
        self.qt_im_module_workaround = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'qtimmoduleworkaround'))
        if self.qt_im_module_workaround is None:
            self.qt_im_module_workaround = False
        if self.qt_im_module_workaround is True:
            self._qt_im_module_workaround_checkbutton.set_active(True)

        self._arrow_keys_reopen_preedit_checkbutton = Gtk.CheckButton(
            _('Arrow keys can reopen a preedit'))
        self._arrow_keys_reopen_preedit_checkbutton.set_tooltip_text(
            _('Whether it is allowed to reopen a preedit when the cursor reaches a word boundary after moving it with the arrow keys. Enabling this option is useful to correct already committed words. But it is quite buggy at the moment and how well it works depends on repetition speed of the arrow keys and system load. Because it is buggy, this option is off by default.'))
        self._arrow_keys_reopen_preedit_checkbutton.connect(
            'clicked', self.on_arrow_keys_reopen_preedit_checkbutton)
        self._options_grid.attach(
            self._arrow_keys_reopen_preedit_checkbutton, 0, 8, 2, 1)
        self.arrow_keys_reopen_preedit = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'arrowkeysreopenpreedit'))
        if self.arrow_keys_reopen_preedit is None:
            self.arrow_keys_reopen_preedit = False
        if self.arrow_keys_reopen_preedit is True:
            self._arrow_keys_reopen_preedit_checkbutton.set_active(True)

        self._auto_commit_characters_label = Gtk.Label(
            _('Auto commit characters:'))
        self._auto_commit_characters_label.set_tooltip_text(
            _('The characters in this list cause the preedit to be committed automatically, followed by a space.  For example, if “.” is an auto commit character, this saves you typing a space manually after the end of a sentence. You can freely edit this list, a reasonable value might be “.,;:?!)”. You should not add characters to that list which are needed by your input method, for example if you use Latin-Pre (t-latn-pre) it would be a bad idea to add “.” to that list because it would prevent you from typing “.s” to get “ṡ”. You can also disable this feature completely by making the list empty (which is the default).'))
        self._auto_commit_characters_label.set_xalign(0)
        self._options_grid.attach(
            self._auto_commit_characters_label, 0, 9, 1, 1)

        self._auto_commit_characters_entry = Gtk.Entry()
        self._auto_commit_characters_entry.connect(
            'notify::text', self.on_auto_commit_characters_entry)
        self._options_grid.attach(
            self._auto_commit_characters_entry, 1, 9, 1, 1)
        self.auto_commit_characters = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'autocommitcharacters'))
        if not self.auto_commit_characters:
            self.auto_commit_characters = ''
        self._auto_commit_characters_entry.set_text(self.auto_commit_characters)

        self._page_size_label = Gtk.Label(
            _('Candidate window page size:'))
        self._page_size_label.set_tooltip_text(
            _('How many suggestion candidates to show in one page of the candidate list.'))
        self._page_size_label.set_xalign(0)
        self._options_grid.attach(
            self._page_size_label, 0, 10, 1, 1)

        self._page_size_adjustment = Gtk.SpinButton()
        self._page_size_adjustment.set_visible(True)
        self._page_size_adjustment.set_can_focus(True)
        self._page_size_adjustment.set_increments(1.0, 1.0)
        self._page_size_adjustment.set_range(1.0, 9.0)
        self._options_grid.attach(
            self._page_size_adjustment, 1, 10, 1, 1)
        self.page_size = itb_util.variant_to_value(self.config.get_value(
            self.config_section, 'pagesize'))
        if self.page_size:
            self._page_size_adjustment.set_value(int(self.page_size))
        else:
            self._page_size_adjustment.set_value(6)
        self._page_size_adjustment.connect(
            'value-changed', self.on_page_size_adjustment_value_changed)

        self._lookup_table_orientation_label = Gtk.Label(
            _('Candidate window orientation'))
        self._lookup_table_orientation_label.set_tooltip_text(
            _('Whether the candidate window should be drawn horizontally or vertically.'))
        self._lookup_table_orientation_label.set_xalign(0)
        self._options_grid.attach(
            self._lookup_table_orientation_label, 0, 11, 1, 1)

        self._lookup_table_orientation_combobox = Gtk.ComboBox()
        lookup_table_orientation_store = Gtk.ListStore(str, int)
        lookup_table_orientation_store.append(
            [_('Horizontal'), IBus.Orientation.HORIZONTAL])
        lookup_table_orientation_store.append(
            [_('Vertical'), IBus.Orientation.VERTICAL])
        lookup_table_orientation_store.append(
            [_('System default'), IBus.Orientation.SYSTEM])
        self._lookup_table_orientation_combobox.set_model(
            lookup_table_orientation_store)
        renderer_text = Gtk.CellRendererText()
        self._lookup_table_orientation_combobox.pack_start(
            renderer_text, True)
        self._lookup_table_orientation_combobox.add_attribute(
            renderer_text, "text", 0)
        lookup_table_orientation = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'lookuptableorientation'))
        if lookup_table_orientation is None:
            lookup_table_orientation = IBus.Orientation.VERTICAL
        for i, item in enumerate(lookup_table_orientation_store):
            if lookup_table_orientation == item[1]:
                self._lookup_table_orientation_combobox.set_active(i)
        self._options_grid.attach(
            self._lookup_table_orientation_combobox, 1, 11, 1, 1)
        self._lookup_table_orientation_combobox.connect(
            "changed",
            self.on_lookup_table_orientation_combobox_changed)

        self._min_chars_completion_label = Gtk.Label(
            _('Minimum number of chars for completion:'))
        self._min_chars_completion_label.set_tooltip_text(
            _('Show no suggestions when less than this number of characters have been typed.'))
        self._min_chars_completion_label.set_xalign(0)
        self._options_grid.attach(
            self._min_chars_completion_label, 0, 12, 1, 1)

        self._min_char_complete_adjustment = Gtk.SpinButton()
        self._min_char_complete_adjustment.set_visible(True)
        self._min_char_complete_adjustment.set_can_focus(True)
        self._min_char_complete_adjustment.set_increments(1.0, 1.0)
        self._min_char_complete_adjustment.set_range(1.0, 9.0)
        self._options_grid.attach(
            self._min_char_complete_adjustment, 1, 12, 1, 1)
        self.min_char_complete = itb_util.variant_to_value(
            self.config.get_value(self.config_section, 'mincharcomplete'))
        if self.min_char_complete:
            self._min_char_complete_adjustment.set_value(
                int(self.min_char_complete))
        else:
            self._min_char_complete_adjustment.set_value(1)
        self._min_char_complete_adjustment.connect(
            'value-changed', self.on_min_char_complete_adjustment_value_changed)

        self._dictionaries_label = Gtk.Label()
        self._dictionaries_label.set_text(
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
        self._dictionaries_and_input_methods_vbox.pack_start(
            self._dictionaries_label, False, False, 0)
        self._dictionaries_scroll = Gtk.ScrolledWindow()
        self._dictionaries_and_input_methods_vbox.pack_start(
            self._dictionaries_scroll, True, True, 0)
        self._dictionaries_install_missing_button = Gtk.Button(
            _('Install missing dictionaries'))
        self._dictionaries_install_missing_button.set_tooltip_text(
            _('Install the dictionaries which are setup here but not installed'))
        self._dictionaries_install_missing_button.connect(
            'clicked', self.on_install_missing_dictionaries)
        self._dictionaries_action_area = Gtk.ButtonBox()
        self._dictionaries_action_area.set_can_focus(False)
        self._dictionaries_action_area.set_layout(Gtk.ButtonBoxStyle.START)
        self._dictionaries_and_input_methods_vbox.pack_start(
            self._dictionaries_action_area, False, False, 0)
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
            'clicked', self.on_dictionaries_add_button_clicked)
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
            'clicked', self.on_dictionaries_remove_button_clicked)
        self._dictionaries_remove_button.set_sensitive(False)
        self._dictionaries_up_button = Gtk.Button()
        self._dictionaries_up_button_label = Gtk.Label()
        self._dictionaries_up_button_label.set_text(
            '<span size="xx-large"><b>↑</b></span>')
        self._dictionaries_up_button_label.set_use_markup(True)
        self._dictionaries_up_button.add(self._dictionaries_up_button_label)
        self._dictionaries_up_button.set_tooltip_text(
            _('Move dictionary down'))
        self._dictionaries_up_button.connect(
            'clicked', self.on_dictionaries_up_button_clicked)
        self._dictionaries_up_button.set_sensitive(False)
        self._dictionaries_down_button = Gtk.Button()
        self._dictionaries_down_button_label = Gtk.Label()
        self._dictionaries_down_button_label.set_text(
            '<span size="xx-large"><b>↓</b></span>')
        self._dictionaries_down_button_label.set_use_markup(True)
        self._dictionaries_down_button.add(self._dictionaries_down_button_label)
        self._dictionaries_down_button.set_tooltip_text(
            _('Move dictionary up'))
        self._dictionaries_down_button.connect(
            'clicked', self.on_dictionaries_down_button_clicked)
        self._dictionaries_down_button.set_sensitive(False)
        self._dictionaries_action_area.add(self._dictionaries_add_button)
        self._dictionaries_action_area.add(self._dictionaries_remove_button)
        self._dictionaries_action_area.add(self._dictionaries_up_button)
        self._dictionaries_action_area.add(self._dictionaries_down_button)
        self._dictionaries_action_area.add(self._dictionaries_install_missing_button)
        self._fill_dictionaries_listbox()

        self._input_methods_label = Gtk.Label()
        self._input_methods_label.set_text(
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
        self._dictionaries_and_input_methods_vbox.pack_start(
            self._input_methods_label, False, False, 0)
        self._input_methods_scroll = Gtk.ScrolledWindow()
        self._dictionaries_and_input_methods_vbox.pack_start(
            self._input_methods_scroll, True, True, 0)
        self._input_methods_action_area = Gtk.ButtonBox()
        self._input_methods_action_area.set_can_focus(False)
        self._input_methods_action_area.set_layout(Gtk.ButtonBoxStyle.START)
        self._dictionaries_and_input_methods_vbox.pack_start(
            self._input_methods_action_area, False, False, 0)
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
            'clicked', self.on_input_methods_add_button_clicked)
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
            'clicked', self.on_input_methods_remove_button_clicked)
        self._input_methods_remove_button.set_sensitive(False)
        self._input_methods_up_button = Gtk.Button()
        self._input_methods_up_button_label = Gtk.Label()
        self._input_methods_up_button_label.set_text(
            '<span size="xx-large"><b>↑</b></span>')
        self._input_methods_up_button_label.set_use_markup(True)
        self._input_methods_up_button.add(
            self._input_methods_up_button_label)
        self._input_methods_up_button.set_tooltip_text(
            _('Move input method down'))
        self._input_methods_up_button.connect(
            'clicked', self.on_input_methods_up_button_clicked)
        self._input_methods_up_button.set_sensitive(False)
        self._input_methods_down_button = Gtk.Button()
        self._input_methods_down_button_label = Gtk.Label()
        self._input_methods_down_button_label.set_text(
            '<span size="xx-large"><b>↓</b></span>')
        self._input_methods_down_button_label.set_use_markup(True)
        self._input_methods_down_button.add(
            self._input_methods_down_button_label)
        self._input_methods_down_button.set_tooltip_text(
            _('Move input method up'))
        self._input_methods_down_button.connect(
            'clicked', self.on_input_methods_down_button_clicked)
        self._input_methods_down_button.set_sensitive(False)
        self._input_methods_help_button = Gtk.Button(
            _('Input Method Help'))
        self._input_methods_help_button.set_tooltip_text(
            _('Display some help showing how to use the input method selected above.'))
        self._input_methods_help_button.connect(
            'clicked', self.on_input_methods_help_button_clicked)
        self._input_methods_help_button.set_sensitive(False)
        self._input_methods_action_area.add(self._input_methods_add_button)
        self._input_methods_action_area.add(self._input_methods_remove_button)
        self._input_methods_action_area.add(self._input_methods_up_button)
        self._input_methods_action_area.add(self._input_methods_down_button)
        self._input_methods_action_area.add(self._input_methods_help_button)
        self._fill_input_methods_listbox()

        self._shortcut_label = Gtk.Label(
            _('Enter shortcut here:'))
        self._shortcut_label.set_hexpand(False)
        self._shortcut_label.set_vexpand(False)
        self._shortcut_label.set_xalign(0)
        self._custom_shortcuts_grid.attach(
            self._shortcut_label, 0, 0, 3, 1)

        self._shortcut_entry = Gtk.Entry()
        self._shortcut_entry.set_visible(True)
        self._shortcut_entry.set_can_focus(True)
        self._shortcut_entry.set_hexpand(False)
        self._shortcut_entry.set_vexpand(False)
        self._custom_shortcuts_grid.attach(
            self._shortcut_entry, 0, 1, 3, 1)

        self._shortcut_expansion_label = Gtk.Label(
            _('Enter shortcut expansion here:'))
        self._shortcut_expansion_label.set_hexpand(False)
        self._shortcut_expansion_label.set_vexpand(False)
        self._shortcut_expansion_label.set_xalign(0)
        self._custom_shortcuts_grid.attach(
            self._shortcut_expansion_label, 0, 2, 3, 1)

        self._shortcut_expansion_entry = Gtk.Entry()
        self._shortcut_expansion_entry.set_visible(True)
        self._shortcut_expansion_entry.set_can_focus(True)
        self._shortcut_expansion_entry.set_hexpand(False)
        self._shortcut_expansion_entry.set_vexpand(False)
        self._custom_shortcuts_grid.attach(
            self._shortcut_expansion_entry, 0, 3, 3, 1)

        self._shortcut_clear_button = Gtk.Button(
            _('Clear input'))
        self._shortcut_clear_button.set_receives_default(False)
        self._shortcut_clear_button.set_hexpand(False)
        self._shortcut_clear_button.set_vexpand(False)
        self._custom_shortcuts_grid.attach(
            self._shortcut_clear_button, 0, 4, 1, 1)
        self._shortcut_clear_button.connect(
            'clicked', self.on_shortcut_clear_clicked)

        self._shortcut_delete_button = Gtk.Button(
            _('Delete shortcut'))
        self._shortcut_delete_button.set_receives_default(False)
        self._shortcut_delete_button.set_hexpand(False)
        self._shortcut_delete_button.set_vexpand(False)
        self._custom_shortcuts_grid.attach(
            self._shortcut_delete_button, 1, 4, 1, 1)
        self._shortcut_delete_button.connect(
            'clicked', self.on_shortcut_delete_clicked)

        self._shortcut_add_button = Gtk.Button(
            _('Add shortcut'))
        self._shortcut_add_button.set_receives_default(False)
        self._shortcut_add_button.set_hexpand(False)
        self._shortcut_add_button.set_vexpand(False)
        self._custom_shortcuts_grid.attach(
            self._shortcut_add_button, 2, 4, 1, 1)
        self._shortcut_add_button.connect(
            'clicked', self.on_shortcut_add_clicked)

        self._shortcut_treeview_scroll = Gtk.ScrolledWindow()
        self._shortcut_treeview_scroll.set_can_focus(False)
        self._shortcut_treeview_scroll.set_hexpand(False)
        self._shortcut_treeview_scroll.set_vexpand(True)
        #self._shortcut_treeview_scroll.set_shadow_type(in)
        self._shortcut_treeview = Gtk.TreeView()
        self._shortcut_treeview_model = Gtk.ListStore(str, str)
        self._shortcut_treeview.set_model(self._shortcut_treeview_model)
        current_shortcuts = self.tabsqlitedb.list_user_shortcuts()
        for i, shortcut in enumerate(current_shortcuts):
            self._shortcut_treeview_model.append(shortcut)
        self._shortcut_treeview.append_column(
            Gtk.TreeViewColumn(
                # Translators: Column heading of the table listing the existing shortcuts
                _('Shortcut'),
                Gtk.CellRendererText(),
                text=0))
        self._shortcut_treeview.append_column(
            Gtk.TreeViewColumn(
                # Translators: Column heading of the table listing the existing shortcuts
                _('Shortcut expansion'),
                Gtk.CellRendererText(),
                text=1))
        self._shortcut_treeview.get_selection().connect(
            'changed', self.on_shortcut_selected)
        self._shortcut_treeview_scroll.add(self._shortcut_treeview)
        self._custom_shortcuts_grid.attach(
            self._shortcut_treeview_scroll, 0, 5, 3, 10)

        self._learn_from_file_button = Gtk.Button(
            _('Learn from text file'))
        self._learn_from_file_button.set_tooltip_text(
            _('Learn your style by reading a text file'))
        self._dictionaries_and_personal_data_grid.attach(
            self._learn_from_file_button, 0, 0, 1, 1)
        self._learn_from_file_button.connect(
            'clicked', self.on_learn_from_file_clicked)

        self._delete_learned_data_button = Gtk.Button(
            _('Delete learned data'))
        self._delete_learned_data_button.set_tooltip_text(
            _('Delete all personal language data learned from typing or from reading files'))
        self._dictionaries_and_personal_data_grid.attach(
            self._delete_learned_data_button, 0, 1, 1, 1)
        self._delete_learned_data_button.connect(
            'clicked', self.on_delete_learned_data_clicked)

        self._ibus_typing_booster_emoji_label = Gtk.Label()
        self._ibus_typing_booster_emoji_label.set_markup(
            '<span font="48">🚀</span>')
        self._ibus_typing_booster_emoji_label.set_hexpand(True)
        self._ibus_typing_booster_emoji_label.set_vexpand(False)
        self._about_grid.attach(
            self._ibus_typing_booster_emoji_label, 0, 0, 1, 1)

        self._name_version_label = Gtk.Label()
        self._name_version_label.set_markup(
            '<span font_size="large"><b>ibus-typing-booster %s</b></span>'
            %version.get_version())
        self._name_version_label.set_hexpand(True)
        self._name_version_label.set_vexpand(False)
        self._about_grid.attach(
            self._name_version_label, 0, 1, 1, 1)

        self._long_description_label = Gtk.Label()
        self._long_description_label.set_markup(
            _('A completion input method to speedup typing.'))
        self._long_description_label.set_hexpand(True)
        self._long_description_label.set_vexpand(False)
        self._about_grid.attach(
            self._long_description_label, 0, 2, 1, 1)

        self._home_page_label = Gtk.Label()
        self._home_page_label.set_markup(
            _('<b>Home page:</b>'))
        self._home_page_label.set_hexpand(True)
        self._home_page_label.set_vexpand(False)
        self._about_grid.attach(
            self._home_page_label, 0, 3, 1, 1)

        self._home_page_link_button = Gtk.LinkButton(
            'http://mike-fabian.github.io/ibus-typing-booster',
            'http://mike-fabian.github.io/ibus-typing-booster')
        self._about_grid.attach(
            self._home_page_link_button, 0, 4, 1, 1)

        self._documentation_link_button_label = Gtk.Label()
        self._documentation_link_button_label.set_markup(
            _('<b>Online documentation:</b>'))
        self._documentation_link_button_label.set_hexpand(True)
        self._documentation_link_button_label.set_vexpand(False)
        self._about_grid.attach(
            self._documentation_link_button_label, 0, 5, 1, 1)

        self._documentation_link_button = Gtk.LinkButton(
            'http://mike-fabian.github.io/ibus-typing-booster/documentation.html',
            'http://mike-fabian.github.io/ibus-typing-booster/documentation.html')
        self._about_grid.attach(
            self._documentation_link_button, 0, 6, 1, 1)

        self.show_all()

    def _fill_dictionaries_listbox_row(self, name):
        missing_dictionary = False
        row = name + ' ' # NO-BREAK SPACE as a separator
        # add some spaces for nicer formatting:
        row += ' ' * (20 - len(name))
        (dic_path,
         aff_path) = itb_util.find_hunspell_dictionary(name)
        row += '\t' + _('Spell checking') + ' '
        if dic_path:
            row += '✔️'
        else:
            row += '❌'
            missing_dictionary = True
        row += ' \t' + _('Emoji') + ' '
        if itb_emoji.find_cldr_annotation_path(name):
            row += '✔️'
        else:
            row += '❌'
        return (row, missing_dictionary)

    def _fill_dictionaries_listbox(self):
        '''
        Fill the dictionaries listbox with the list of dictionaries read
        from dconf.
        '''
        for child in self._dictionaries_scroll.get_children():
            self._dictionaries_scroll.remove(child)
        self._dictionaries_listbox = Gtk.ListBox()
        self._dictionaries_scroll.add(self._dictionaries_listbox)
        self._dictionaries_listbox_selected_dictionary_name = ''
        self._dictionaries_listbox_selected_dictionary_index = -1
        self._dictionaries_listbox.set_visible(True)
        self._dictionaries_listbox.set_vexpand(True)
        self._dictionaries_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._dictionaries_listbox.set_activate_on_single_click(True)
        self._dictionaries_listbox.connect(
            'row-selected', self.on_dictionary_selected)
        self._dictionary_names = []
        dictionary = itb_util.variant_to_value(self.config.get_value(
            self.config_section, 'dictionary'))
        if dictionary:
            names = [x.strip() for x in dictionary.split(',')]
            for name in names:
                self._dictionary_names.append(name)
        if self._dictionary_names == []:
            # There are no dictionaries set in dconf, get a default list of
            # dictionaries from the current effective value of LC_CTYPE:
            self._dictionary_names = itb_util.get_default_dictionaries(
                locale.getlocale(category=locale.LC_CTYPE)[0])
        missing_dictionaries = False
        for name in self._dictionary_names:
            label = Gtk.Label()
            (text,
             missing_dictionary) = self._fill_dictionaries_listbox_row(name)
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

    def _fill_input_methods_listbox_row(self, ime):
        row = ime + ' ' # NO-BREAK SPACE as a separator
        # add some spaces for nicer formatting:
        row += ' ' * (20 - len(ime))
        (path,
         title,
         description,
         full_contents,
         error) = itb_util.get_ime_help(ime)
        if title:
            row += '\t' + '(' + title + ')'
        if error:
            row += '\t' + '⚠️ ' + error
        return row

    def _fill_input_methods_listbox(self):
        '''
        Fill the input methods listbox with the list of input methods read
        from dconf.
        '''
        for child in self._input_methods_scroll.get_children():
            self._input_methods_scroll.remove(child)
        self._input_methods_listbox = Gtk.ListBox()
        self._input_methods_scroll.add(self._input_methods_listbox)
        self._input_methods_listbox_selected_ime_name = ''
        self._input_methods_listbox_selected_ime_index = -1
        self._input_methods_listbox.set_visible(True)
        self._input_methods_listbox.set_vexpand(True)
        self._input_methods_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._input_methods_listbox.set_activate_on_single_click(True)
        self._input_methods_listbox.connect(
            'row-selected', self.on_input_method_selected)
        self.current_imes = []
        inputmethod = itb_util.variant_to_value(self.config.get_value(
            self.config_section, 'inputmethod'))
        if inputmethod:
            inputmethods = [x.strip() for x in inputmethod.split(',')]
            for ime in inputmethods:
                self.current_imes.append(ime)
        if self.current_imes == []:
            # There is no ime set in dconf, get a default list of
            # input methods for the current effective value of LC_CTYPE:
            self.current_imes = itb_util.get_default_input_methods(
                locale.getlocale(category=locale.LC_CTYPE)[0])
        if len(self.current_imes) > itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS:
            sys.stderr.write(
                'Trying to set more than the allowed maximum of %s '
                %itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS
                + 'input methods.\n'
                + 'Trying to set: %s\n' %self.current_imes
                + 'Really setting: %s\n'
                %self.current_imes[:itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS])
            self.current_imes = (
                self.current_imes[:itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS])
            # Save reduced list of input methods back to config:
            self.config.set_value(
                self.config_section,
                'inputmethod',
                GLib.Variant.new_string(','.join(self.current_imes)))
        for ime in self.current_imes:
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
            self._input_methods_listbox.insert(label, -1)
        self._input_methods_listbox.show_all()
        self._input_methods_add_button.set_sensitive(
            len(self.current_imes) < itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS)

    def __run_message_dialog(self, message, message_type=Gtk.MessageType.INFO):
        '''Run a dialog to show an error or warning message'''
        dialog = Gtk.MessageDialog(
            flags=Gtk.DialogFlags.MODAL,
            message_type=message_type,
            buttons=Gtk.ButtonsType.OK,
            message_format=message)
        dialog.run()
        dialog.destroy()

    def check_instance(self):
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

    def on_delete_event(self, *dummy_args):
        '''
        The window has been deleted, probably by the window manager.
        '''
        Gtk.main_quit()

    def on_destroy_event(self, *dummy_args):
        '''
        The window has been destroyed.
        '''
        Gtk.main_quit()

    def on_close_clicked(self, *dummy_args):
        '''
        The button to close the dialog has been clicked.
        '''
        Gtk.main_quit()

    def on_tab_enable_checkbutton(self, widget):
        '''
        The checkbutton whether to show candidates only when
        requested with the tab key or not has been clicked.
        '''
        if widget.get_active():
            self.tab_enable = True
            self.config.set_value(
                self.config_section,
                'tabenable',
                GLib.Variant.new_boolean(True))
        else:
            self.tab_enable = False
            self.config.set_value(
                self.config_section,
                'tabenable',
                GLib.Variant.new_boolean(False))

    def on_show_number_of_candidates_checkbutton(self, widget):
        '''
        The checkbutton whether to show the number of candidates
        on top of the lookup table has been clicked.
        '''
        if widget.get_active():
            self.show_number_of_candidates = True
            self.config.set_value(
                self.config_section,
                'shownumberofcandidates',
                GLib.Variant.new_boolean(True))
        else:
            self.show_number_of_candidates = False
            self.config.set_value(
                self.config_section,
                'shownumberofcandidates',
                GLib.Variant.new_boolean(False))

    def on_show_status_info_in_auxiliary_text_checkbutton(self, widget):
        '''
        The checkbutton whether to show status in the auxiliary text,
        has been clicked.
        '''
        if widget.get_active():
            self.show_status_info_in_auxiliary_text = True
            self.config.set_value(
                self.config_section,
                'showstatusinfoinaux',
                GLib.Variant.new_boolean(True))
        else:
            self.show_status_info_in_auxiliary_text = False
            self.config.set_value(
                self.config_section,
                'showstatusinfoinaux',
                GLib.Variant.new_boolean(False))

    def on_use_digits_as_select_keys_checkbutton(self, widget):
        '''
        The checkbutton whether to use the digits 1 … 9 as select
        keys has been clicked.
        '''
        if widget.get_active():
            self.use_digits_as_select_keys = True
            self.config.set_value(
                self.config_section,
                'usedigitsasselectkeys',
                GLib.Variant.new_boolean(True))
        else:
            self.use_digits_as_select_keys = False
            self.config.set_value(
                self.config_section,
                'usedigitsasselectkeys',
                GLib.Variant.new_boolean(False))

    def on_remember_last_used_preedit_ime_checkbutton(self, widget):
        '''
        The checkbutton whether to remember the last used input method
        for the preëdit has been clicked.
        '''
        if widget.get_active():
            self.remember_last_used_predit_ime = True
            self.config.set_value(
                self.config_section,
                'rememberlastusedpreeditime',
                GLib.Variant.new_boolean(True))
        else:
            self.remember_last_used_predit_ime = False
            self.config.set_value(
                self.config_section,
                'rememberlastusedpreeditime',
                GLib.Variant.new_boolean(False))

    def on_emoji_predictions_checkbutton(self, widget):
        '''
        The checkbutton whether to predict emoji as well or not
        has been clicked.
        '''
        if widget.get_active():
            self.emoji_predictions = True
            self.config.set_value(
                self.config_section,
                'emojipredictions',
                GLib.Variant.new_boolean(True))
        else:
            self.emoji_predictions = False
            self.config.set_value(
                self.config_section,
                'emojipredictions',
                GLib.Variant.new_boolean(False))

    def on_off_the_record_checkbutton(self, widget):
        '''
        The checkbutton whether to use “Off the record” mode, i.e. whether to
        learn from user data by saving user input to the user database
        or not, has been clicked.
        '''
        if widget.get_active():
            self.off_the_record = True
            self.config.set_value(
                self.config_section,
                'offtherecord',
                GLib.Variant.new_boolean(True))
        else:
            self.off_the_record = False
            self.config.set_value(
                self.config_section,
                'offtherecord',
                GLib.Variant.new_boolean(False))

    def on_qt_im_module_workaround_checkbutton(self, widget):
        '''
        The checkbutton whether to use the workaround for the broken
        implementation of forward_key_event() in the Qt 4/5 input
        module, has been clicked.
        '''
        if widget.get_active():
            self.qt_im_module_workaround = True
            self.config.set_value(
                self.config_section,
                'qtimmoduleworkaround',
                GLib.Variant.new_boolean(True))
        else:
            self.qt_im_module_workaround = False
            self.config.set_value(
                self.config_section,
                'qtimmoduleworkaround',
                GLib.Variant.new_boolean(False))

    def on_arrow_keys_reopen_preedit_checkbutton(self, widget):
        '''
        The checkbutton whether arrow keys are allowed to reopen
        a preëdit, has been clicked.
        '''
        if widget.get_active():
            self.arrow_keys_reopen_preedit = True
            self.config.set_value(
                self.config_section,
                'arrowkeysreopenpreedit',
                GLib.Variant.new_boolean(True))
        else:
            self.arrow_keys_reopen_preedit = False
            self.config.set_value(
                self.config_section,
                'arrowkeysreopenpreedit',
                GLib.Variant.new_boolean(False))

    def on_auto_commit_characters_entry(self, widget, dummy_property_spec):
        '''
        The list of characters triggering an auto commit has been changed.
        '''
        self.auto_commit_characters = widget.get_text()
        self.config.set_value(
            self.config_section,
            'autocommitcharacters',
            GLib.Variant.new_string(self.auto_commit_characters))

    def on_page_size_adjustment_value_changed(self, dummy_widget):
        '''
        The page size of the lookup table has been changed.
        '''
        page_size = self._page_size_adjustment.get_value()
        self.config.set_value(
            self.config_section,
            'pagesize',
            GLib.Variant.new_int32(page_size))

    def on_lookup_table_orientation_combobox_changed(self, widget):
        '''
        A change of the lookup table orientation has been requested
        with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter != None:
            model = widget.get_model()
            orientation = model[tree_iter][1]
            self.config.set_value(
                self.config_section,
                'lookuptableorientation',
                GLib.Variant.new_int32(orientation))

    def on_min_char_complete_adjustment_value_changed(self, dummy_widget):
        '''
        The value for the mininum number of characters before
        completion is attempted has been changed.
        '''
        min_char_complete = (
            self._min_char_complete_adjustment.get_value())
        self.config.set_value(
            self.config_section,
            'mincharcomplete',
            GLib.Variant.new_int32(min_char_complete))

    def on_dictionary_to_add_selected(self, dummy_listbox, listbox_row):
        '''
        Signal handler for selecting a dictionary to add

        :param dummy_listbox: The list box used to select the dictionary to add
        :type dummy_listbox: Gtk.ListBox object
        :param listbox_row: A row containing a dictionary name
        :type listbox_row: Gtk.ListBoxRow object
        '''
        name = listbox_row.get_child().get_text().split(' ')[0]
        if GTK_VERSION >= (3, 22, 0):
            self._dictionaries_add_popover.popdown()
        self._dictionaries_add_popover.hide()
        if not name or name in self._dictionary_names:
            return
        self._dictionary_names = [name] + self._dictionary_names
        self.config.set_value(
            self.config_section,
            'dictionary',
            GLib.Variant.new_string(','.join(self._dictionary_names)))
        self._fill_dictionaries_listbox()
        self._dictionaries_listbox_selected_dictionary_index = 0
        self._dictionaries_listbox_selected_dictionary_name = name
        self._dictionaries_listbox.select_row(
            self._dictionaries_listbox.get_row_at_index(0))

    def _fill_dictionaries_add_listbox(self, filter_text):
        '''
        Fill the listbox of dictionaries to choose from

        :param filter_text: The filter text to limit the dictionaries
                            listed. Only dictionaries which contain
                            the filter text as a substring
                            (ignoring case and spaces) are listed.
        :type filter_text: String
        '''
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
            'row-selected', self.on_dictionary_to_add_selected)
        rows = []
        for name in sorted(itb_util.SUPPORTED_DICTIONARIES):
            if name in self._dictionary_names:
                continue
            if not (filter_text.replace(' ', '').lower()
                in name.replace(' ', '').lower()):
                continue
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

    def on_dictionaries_search_entry_changed(self, search_entry):
        '''
        Signal handler for changed text in the dictionaries search entry

        :param search_entry: The search entry
        :type search_entry: Gtk.SearchEntry object
        '''
        filter_text = search_entry.get_text()
        self._fill_dictionaries_add_listbox(filter_text)

    def on_dictionaries_add_button_clicked(self, *dummy_args):
        '''
        Signal handler called when the “add” button to add another
        dictionary has been clicked.
        '''
        self._dictionaries_add_popover = Gtk.Popover()
        self._dictionaries_add_popover.set_relative_to(
            self._dictionaries_add_button)
        self._dictionaries_add_popover.set_position(Gtk.PositionType.RIGHT)
        self._dictionaries_add_popover.set_vexpand(True)
        self._dictionaries_add_popover.set_hexpand(True)
        dictionaries_add_popover_vbox = Gtk.VBox()
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
        dictionaries_add_popover_vbox.pack_start(
            dictionaries_add_popover_label, False, False, 0)
        dictionaries_add_popover_search_entry = Gtk.SearchEntry()
        dictionaries_add_popover_search_entry.set_can_focus(True)
        dictionaries_add_popover_search_entry.set_visible(True)
        dictionaries_add_popover_search_entry.set_halign(Gtk.Align.FILL)
        dictionaries_add_popover_search_entry.set_hexpand(False)
        dictionaries_add_popover_search_entry.set_vexpand(False)
        dictionaries_add_popover_search_entry.connect(
            'search-changed', self.on_dictionaries_search_entry_changed)
        dictionaries_add_popover_vbox.pack_start(
            dictionaries_add_popover_search_entry, False, False, 0)
        self._dictionaries_add_popover_scroll = Gtk.ScrolledWindow()
        self._dictionaries_add_popover_scroll.set_hexpand(True)
        self._dictionaries_add_popover_scroll.set_vexpand(True)
        self._dictionaries_add_popover_scroll.set_kinetic_scrolling(False)
        self._dictionaries_add_popover_scroll.set_overlay_scrolling(True)
        self._fill_dictionaries_add_listbox('')
        dictionaries_add_popover_vbox.pack_start(
            self._dictionaries_add_popover_scroll, True, True, 0)
        self._dictionaries_add_popover.add(dictionaries_add_popover_vbox)
        if GTK_VERSION >= (3, 22, 0):
            self._dictionaries_add_popover.popup()
        self._dictionaries_add_popover.show_all()

    def on_dictionaries_remove_button_clicked(self, *dummy_args):
        '''
        Signal handler called when the “remove” button for
        an input method has been clicked.
        '''
        index = self._dictionaries_listbox_selected_dictionary_index
        if (not (index >= 0 and index < len(self._dictionary_names))):
            # This should not happen, one should not be able
            # to click the remove button in this case, just return:
            return
        self._dictionary_names = (
            self._dictionary_names[:index]
            + self._dictionary_names[index + 1:])
        self.config.set_value(
            self.config_section,
            'dictionary',
            GLib.Variant.new_string(','.join(self._dictionary_names)))
        self._fill_dictionaries_listbox()
        self._dictionaries_listbox_selected_dictionary_index = -1
        self._dictionaries_listbox_selected_dictionary_name = ''
        self._dictionaries_listbox.unselect_all()

    def on_dictionaries_up_button_clicked(self, *dummy_args):
        '''
        Signal handler called when the “up” button for a dictionary
        has been clicked.

        Increases the priority of the selected dictionary.
        '''
        index = self._dictionaries_listbox_selected_dictionary_index
        if (not (index > 0 and index < len(self._dictionary_names))):
            # This should not happen, one should not be able
            # to click the up button in this case, just return:
            return
        self._dictionary_names = (
            self._dictionary_names[:index - 1]
            + [self._dictionary_names[index]]
            + [self._dictionary_names[index - 1]]
            + self._dictionary_names[index + 1:])
        self.config.set_value(
            self.config_section,
            'dictionary',
            GLib.Variant.new_string(','.join(self._dictionary_names)))
        self._fill_dictionaries_listbox()
        self._dictionaries_listbox_selected_dictionary_index = index - 1
        self._dictionaries_listbox_selected_dictionary_name = (
            self._dictionary_names[index - 1])
        self._dictionaries_listbox.select_row(
            self._dictionaries_listbox.get_row_at_index(index - 1))

    def on_dictionaries_down_button_clicked(self, *dummy_args):
        '''
        Signal handler called when the “down” button for a dictionary
        has been clicked.

        Lowers the priority of the selected dictionary.
        '''
        index = self._dictionaries_listbox_selected_dictionary_index
        if (not (index >= 0 and index < len(self._dictionary_names) - 1)):
            # This should not happen, one should not be able
            # to click the down button in this case, just return:
            return
        self._dictionary_names = (
            self._dictionary_names[:index]
            + [self._dictionary_names[index + 1]]
            + [self._dictionary_names[index]]
            + self._dictionary_names[index + 2:])
        self.config.set_value(
            self.config_section,
            'dictionary',
            GLib.Variant.new_string(','.join(self._dictionary_names)))
        self._fill_dictionaries_listbox()
        self._dictionaries_listbox_selected_dictionary_index = index + 1
        self._dictionaries_listbox_selected_dictionary_name = (
            self._dictionary_names[index + 1])
        self._dictionaries_listbox.select_row(
            self._dictionaries_listbox.get_row_at_index(index + 1))

    def on_install_missing_dictionaries(self, *dummy_args):
        '''
        Signal handler called when the “Install missing dictionaries”
        button is clicked.

        Tries to install the appropriate dictionary packages.
        '''
        missing_dictionary_packages = set()
        for name in self._dictionary_names:
            (dic_path,
             aff_path) = itb_util.find_hunspell_dictionary(name)
            if not dic_path:
                missing_dictionary_packages.add(
                    'hunspell-' + name.split('_')[0])
        for package in missing_dictionary_packages:
            InstallPkg(package)
        self._fill_dictionaries_listbox()
        if missing_dictionary_packages:
            # Write a timestamp to dconf to trigger the callback
            # for changed dconf values in the engine and reload
            # the dictionaries:
            self.config.set_value(
                self.config_section,
                'dictionaryinstalltimestamp',
                GLib.Variant.new_string(strftime('%Y-%m-%d %H:%M:%S')))

    def on_dictionary_selected(self, dummy_listbox, listbox_row):
        '''
        Signal handler called when a dictionary is selected

        :param dummy_listbox: The listbox used to select dictionaries
        :type dummy_listbox: Gtk.ListBox object
        :param listbox_row: A row containing the dictionary name
        :type listbox_row: Gtk.ListBoxRow object
        '''
        if listbox_row:
            self._dictionaries_listbox_selected_dictionary_name = (
                listbox_row.get_child().get_text().split(' ')[0])
            self._dictionaries_listbox_selected_dictionary_index = (
                listbox_row.get_index())
            self._dictionaries_remove_button.set_sensitive(True)
            self._dictionaries_up_button.set_sensitive(
                self._dictionaries_listbox_selected_dictionary_index > 0)
            self._dictionaries_down_button.set_sensitive(
                self._dictionaries_listbox_selected_dictionary_index
                < len(self._dictionary_names) - 1)
        else:
            # all rows have been unselected
            self._dictionaries_listbox_selected_dictionary_name = ''
            self._dictionaries_listbox_selected_dictionary_index = -1
            self._dictionaries_remove_button.set_sensitive(False)
            self._dictionaries_up_button.set_sensitive(False)
            self._dictionaries_down_button.set_sensitive(False)

    def on_input_method_to_add_selected(self, dummy_listbox, listbox_row):
        '''
        Signal handler for selecting an input method to add

        :param dummy_listbox: The list box used to select the input method to add
        :type dummy_listbox: Gtk.ListBox object
        :param listbox_row: A row containing an input method name
        :type listbox_row: Gtk.ListBoxRow object
        '''
        ime = listbox_row.get_child().get_text().split(' ')[0]
        if GTK_VERSION >= (3, 22, 0):
            self._input_methods_add_popover.popdown()
        self._input_methods_add_popover.hide()
        if not ime or ime in self.current_imes:
            return
        self.current_imes = [ime] + self.current_imes
        self.config.set_value(
            self.config_section,
            'inputmethod',
            GLib.Variant.new_string(','.join(self.current_imes)))
        self._fill_input_methods_listbox()
        self._input_methods_listbox_selected_ime_index = 0
        self._input_methods_listbox_selected_ime_name = ime
        self._input_methods_listbox.select_row(
            self._input_methods_listbox.get_row_at_index(0))

    def _fill_input_methods_add_listbox(self, filter_text):
        '''
        Fill the listbox of input methods to choose from

        :param filter_text: The filter text to limit the input methods
                            listed. Only input methods which contain
                            the filter text as a substring
                            (ignoring case and spaces) are listed.
        :type filter_text: String
        '''
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
            'row-selected', self.on_input_method_to_add_selected)
        rows = []
        for ime in ['NoIme'] + sorted(itb_util.M17N_INPUT_METHODS):
            if ime in self.current_imes:
                continue
            row = self._fill_input_methods_listbox_row(ime)
            if (filter_text.replace(' ', '').lower()
                in row.replace(' ', '').lower()):
                rows.append(row)
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
            self._input_methods_add_listbox.insert(label, -1)
        self._input_methods_add_popover.show_all()

    def on_input_methods_search_entry_changed(self, search_entry):
        '''
        Signal handler for changed text in the input methods search entry

        :param search_entry: The search entry
        :type search_entry: Gtk.SearchEntry object
        '''
        filter_text = search_entry.get_text()
        self._fill_input_methods_add_listbox(filter_text)

    def on_input_methods_add_button_clicked(self, *dummy_args):
        '''
        Signal handler called when the “add” button to add another
        input method has been clicked.
        '''
        if len(self.current_imes) >= itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS:
            # Actually this should never happen because the button to add
            # an input method should not be sensitive if the maximum number
            # of input methods is  already reached.
            #
            # Probably it is better not to make this message translatable
            # in order not to create extra work for the translators to
            # translate a message which should never be displayed anyway.
            self.__run_message_dialog(
                'The maximum number of input methods is %s.'
                %itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS,
                message_type=Gtk.MessageType.ERROR)
            return
        self._input_methods_add_popover = Gtk.Popover()
        self._input_methods_add_popover.set_relative_to(
            self._input_methods_add_button)
        self._input_methods_add_popover.set_position(Gtk.PositionType.RIGHT)
        self._input_methods_add_popover.set_vexpand(True)
        self._input_methods_add_popover.set_hexpand(True)
        input_methods_add_popover_vbox = Gtk.VBox()
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
        input_methods_add_popover_vbox.pack_start(
            input_methods_add_popover_label, False, False, 0)
        input_methods_add_popover_search_entry = Gtk.SearchEntry()
        input_methods_add_popover_search_entry.set_can_focus(True)
        input_methods_add_popover_search_entry.set_visible(True)
        input_methods_add_popover_search_entry.set_halign(Gtk.Align.FILL)
        input_methods_add_popover_search_entry.set_hexpand(False)
        input_methods_add_popover_search_entry.set_vexpand(False)
        input_methods_add_popover_search_entry.connect(
            'search-changed', self.on_input_methods_search_entry_changed)
        input_methods_add_popover_vbox.pack_start(
            input_methods_add_popover_search_entry, False, False, 0)
        self._input_methods_add_popover_scroll = Gtk.ScrolledWindow()
        self._input_methods_add_popover_scroll.set_hexpand(True)
        self._input_methods_add_popover_scroll.set_vexpand(True)
        self._input_methods_add_popover_scroll.set_kinetic_scrolling(False)
        self._input_methods_add_popover_scroll.set_overlay_scrolling(True)
        self._fill_input_methods_add_listbox('')
        input_methods_add_popover_vbox.pack_start(
            self._input_methods_add_popover_scroll, True, True, 0)
        self._input_methods_add_popover.add(input_methods_add_popover_vbox)
        if GTK_VERSION >= (3, 22, 0):
            self._input_methods_add_popover.popup()
        self._input_methods_add_popover.show_all()

    def on_input_methods_remove_button_clicked(self, *dummy_args):
        '''
        Signal handler called when the “remove” button for
        an input method has been clicked.
        '''
        index = self._input_methods_listbox_selected_ime_index
        if (not (index >= 0 and index < len(self.current_imes))):
            # This should not happen, one should not be able
            # to click the remove button in this case, just return:
            return
        self.current_imes = (
            self.current_imes[:index]
            + self.current_imes[index + 1:])
        self.config.set_value(
            self.config_section,
            'inputmethod',
            GLib.Variant.new_string(','.join(self.current_imes)))
        self._fill_input_methods_listbox()
        self._input_methods_listbox_selected_ime_index = -1
        self._input_methods_listbox_selected_ime_name = ''
        self._input_methods_listbox.unselect_all()

    def on_input_methods_up_button_clicked(self, *dummy_args):
        '''
        Signal handler called when the “up” button for an input method
        has been clicked.

        Increases the priority of the selected input method.
        '''
        index = self._input_methods_listbox_selected_ime_index
        if (not (index > 0 and index < len(self.current_imes))):
            # This should not happen, one should not be able
            # to click the up button in this case, just return:
            return
        self.current_imes = (
            self.current_imes[:index - 1]
            + [self.current_imes[index]]
            + [self.current_imes[index - 1]]
            + self.current_imes[index + 1:])
        self.config.set_value(
            self.config_section,
            'inputmethod',
            GLib.Variant.new_string(','.join(self.current_imes)))
        self._fill_input_methods_listbox()
        self._input_methods_listbox_selected_ime_index = index - 1
        self._input_methods_listbox_selected_ime_name = (
            self.current_imes[index - 1])
        self._input_methods_listbox.select_row(
            self._input_methods_listbox.get_row_at_index(index - 1))

    def on_input_methods_down_button_clicked(self, *dummy_args):
        '''
        Signal handler called when the “down” button for an input method
        has been clicked.

        Lowers the priority of the selected input method.
        '''
        index = self._input_methods_listbox_selected_ime_index
        if (not (index >= 0 and index < len(self.current_imes) - 1)):
            # This should not happen, one should not be able
            # to click the down button in this case, just return:
            return
        self.current_imes = (
            self.current_imes[:index]
            + [self.current_imes[index + 1]]
            + [self.current_imes[index]]
            + self.current_imes[index + 2:])
        self.config.set_value(
            self.config_section,
            'inputmethod',
            GLib.Variant.new_string(','.join(self.current_imes)))
        self._fill_input_methods_listbox()
        self._input_methods_listbox_selected_ime_index = index + 1
        self._input_methods_listbox_selected_ime_name = self.current_imes[index + 1]
        self._input_methods_listbox.select_row(
            self._input_methods_listbox.get_row_at_index(index + 1))

    def on_input_methods_help_button_clicked(self, dummy_widget):
        '''
        Show a help window for the input method selected in the
        listbox.
        '''
        if not self._input_methods_listbox_selected_ime_name:
            return
        (path,
         title,
         description,
         full_contents,
         error) = itb_util.get_ime_help(
             self._input_methods_listbox_selected_ime_name)
        window_title = self._input_methods_listbox_selected_ime_name
        if title:
            window_title += '   ' + title
        if path:
            window_title += '   ' + path
        if error:
            window_contents = error
        else:
            window_contents = description
            if full_contents:
                window_contents += (
                    '\n\n'
                    + '############################################################'
                    + '\n'
                    + 'Complete file implementing the input method follows here:\n'
                    + '############################################################'
                    + '\n'
                    + full_contents)
        win = HelpWindow(
            parent=self,
            title=window_title,
            contents=window_contents),

    def on_input_method_selected(self, dummy_listbox, listbox_row):
        '''
        Signal handler called when an input method is selected

        :param dummy_listbox: The listbox used to select input methods
        :type dummy_listbox: Gtk.ListBox object
        :param listbox_row: A row containing the input method name
        :type listbox_row: Gtk.ListBoxRow object
        '''
        if listbox_row:
            self._input_methods_listbox_selected_ime_name = (
                listbox_row.get_child().get_text().split(' ')[0])
            index = listbox_row.get_index()
            self._input_methods_listbox_selected_ime_index = index
            self._input_methods_remove_button.set_sensitive(True)
            self._input_methods_up_button.set_sensitive(
                index > 0 and index < len(self.current_imes))
            self._input_methods_down_button.set_sensitive(
                index >= 0 and index < len(self.current_imes) - 1)
            self._input_methods_help_button.set_sensitive(True)
        else:
            # all rows have been unselected
            self._input_methods_listbox_selected_ime_name = ''
            self._input_methods_listbox_selected_ime_index = -1
            self._input_methods_remove_button.set_sensitive(False)
            self._input_methods_up_button.set_sensitive(False)
            self._input_methods_down_button.set_sensitive(False)
            self._input_methods_help_button.set_sensitive(False)

    def on_shortcut_clear_clicked(self, dummy_widget):
        '''
        The button to clear the entry fields for defining
        a custom shortcut has been clicked.
        '''
        self._shortcut_entry.set_text('')
        self._shortcut_expansion_entry.set_text('')
        self._shortcut_treeview.get_selection().unselect_all()

    def on_shortcut_delete_clicked(self, dummy_widget):
        '''
        The button to delete a custom shortcut has been clicked.
        '''
        shortcut = self._shortcut_entry.get_text().strip()
        shortcut_expansion = (
            self._shortcut_expansion_entry.get_text().strip())
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
        self._shortcut_expansion_entry.set_text('')
        self._shortcut_treeview.get_selection().unselect_all()

    def on_shortcut_add_clicked(self, dummy_widget):
        '''
        The button to add a custom shortcut has been clicked.
        '''
        self._shortcut_treeview.get_selection().unselect_all()
        shortcut = self._shortcut_entry.get_text().strip()
        shortcut_expansion = (
            self._shortcut_expansion_entry.get_text().strip())
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
                sys.stderr.write(
                    'defining shortcut: “%s” -> “%s”\n'
                    %(shortcut, shortcut_expansion))
                self.tabsqlitedb.check_phrase_and_update_frequency(
                    input_phrase=shortcut,
                    phrase=shortcut_expansion,
                    user_freq_increment=itb_util.SHORTCUT_USER_FREQ)
                model.append((shortcut, shortcut_expansion))
            self._shortcut_entry.set_text('')
            self._shortcut_expansion_entry.set_text('')
            self._shortcut_treeview.get_selection().unselect_all()

    def on_shortcut_selected(self, selection):
        '''
        A row in the list of shortcuts has been selected.
        '''
        (model, iterator) = selection.get_selected()
        if iterator:
            shortcut = model[iterator][0]
            shortcut_expansion = model[iterator][1]
            self._shortcut_entry.set_text(shortcut)
            self._shortcut_expansion_entry.set_text(shortcut_expansion)

    def on_learn_from_file_clicked(self, dummy_widget):
        '''
        The button to learn from a user supplied text file
        has been clicked.
        '''
        self._learn_from_file_button.set_sensitive(False)
        filename = ''
        chooser = Gtk.FileChooserDialog(
            _('Open File ...'),
            self,
            Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
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

    def on_delete_learned_data_clicked(self, dummy_widget):
        '''
        The button requesting to delete all data learned from
        user input or text files has been clicked.
        '''
        self._delete_learned_data_button.set_sensitive(False)
        confirm_question = Gtk.Dialog(
            title=_('Are you sure?'),
            parent=self,
            buttons=(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OK, Gtk.ResponseType.OK))
        box = confirm_question.get_content_area()
        box.add(Gtk.Label(
            _('Do you really want to delete all language \n'
              + 'data learned from typing or reading files?')))
        confirm_question.show_all()
        response = confirm_question.run()
        confirm_question.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration()
        if response == Gtk.ResponseType.OK:
            self.tabsqlitedb.remove_all_phrases()
        self._delete_learned_data_button.set_sensitive(True)

class HelpWindow(Gtk.Window):
    '''
    A window to show help

    :param parent: The parent object
    :type parent: Gtk.Window object
    :param title: Title of the help window
    :type title: String
    :param contents: Contents of the help window
    :type contents: String
    '''
    def __init__(self,
                 parent=None,
                 title='',
                 contents=''):
        Gtk.Window.__init__(self, title=title)
        if parent:
            self.set_parent(parent)
            self.set_transient_for(parent)
            # to receive mouse events for scrolling and for the close
            # button
            self.set_modal(True)
        self.set_destroy_with_parent(False)
        self.set_default_size(600, 500)
        self.vbox = Gtk.VBox(spacing=0)
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
        self.close_button = Gtk.Button(stock=Gtk.STOCK_CLOSE)
        self.close_button.connect("clicked", self.on_close_button_clicked)
        self.hbox = Gtk.HBox(spacing=0)
        self.hbox.pack_end(self.close_button, False, False, 0)
        self.vbox.pack_start(self.hbox, False, False, 5)
        self.show_all()

    def on_close_button_clicked(self, dummy_widget):
        '''
        Close the input method help window when the close button is clicked
        '''
        self.destroy()

class SetupService(dbus.service.Object):
    def __init__(self):
        bus_name = dbus.service.BusName(
            'org.ibus.typingbooster', bus=dbus.SessionBus())
        dbus.service.Object.__init__(self, bus_name, '/org/ibus/typingbooster')

if __name__ == '__main__':
    if not _ARGS.no_debug:
        if (not os.access(
                os.path.expanduser('~/.local/share/ibus-typing-booster'),
                os.F_OK)):
            os.system('mkdir -p ~/.local/share/ibus-typing-booster')
        LOGFILE = os.path.expanduser(
            '~/.local/share/ibus-typing-booster/setup-debug.log')
        sys.stdout = open(LOGFILE, mode='a', buffering=1)
        sys.stderr = open(LOGFILE, mode='a', buffering=1)
        print('--- %s ---' %strftime('%Y-%m-%d: %H:%M:%S'))

    # Workaround for
    # https://bugzilla.gnome.org/show_bug.cgi?id=622084
    # Bug 622084 - Ctrl+C does not exit gtk app
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        sys.stderr.write("IBUS-WARNING **: Using the fallback 'C' locale")
        locale.setlocale(locale.LC_ALL, 'C')
    i18n_init()
    if IBus.get_address() is None:
        DIALOG = Gtk.MessageDialog(
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            message_format=_('ibus is not running.'))
        DIALOG.run()
        DIALOG.destroy()
        sys.exit(1)
    SETUP_UI = SetupUI(IBus.Bus())
    Gtk.main()
