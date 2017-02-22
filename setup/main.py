# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2012-2013 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012-2016 Mike FABIAN <mfabian@redhat.com>
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
import signal
import argparse
import locale
from time import strftime
import dbus
import dbus.service
import dbus.glib

from gi import require_version
require_version('Gtk', '3.0')
from gi.repository import Gtk
require_version('IBus', '1.0')
from gi.repository import IBus
from gi.repository import GLib
from pkginstall import InstallPkg
from i18n import DOMAINNAME, _, init as i18n_init

sys.path = [sys.path[0]+'/../engine'] + sys.path
import tabsqlitedb
import itb_util

import version

def parse_args():
    '''
    Parse the command line arguments.
    '''
    parser = argparse.ArgumentParser(
        description='ibus-typing-booster setup tool')
    parser.add_argument(
        '-c', '--config-file',
        nargs='?',
        type=str,
        action='store',
        default='',
        help=('Set the file name of config file for the ime engine, '
              + 'default: %(default)s'))
    parser.add_argument(
        '-q', '--no-debug',
        action='store_true',
        default=False,
        help=('Do not redirect stdout and stderr to '
              + '~/.local/share/ibus-typing-booster/setup-debug.log, '
              + 'default: %(default)s'))
    return parser.parse_args()

_ARGS = parse_args()

class SetupUI:
    '''
    User interface of the setup tool
    '''
    def __init__(self, bus):
        filename = path.join(path.dirname(__file__), "setup.glade")
        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(DOMAINNAME)
        self.builder.add_from_file(filename)
        event_handler = EventHandler()
        self.builder.connect_signals(event_handler)
        if not self.check_instance():
            dummy_service = SetupService()
        # Try to figure out the config file name:
        self.config_file = None
        if _ARGS.config_file:
            # If the config file is specified on the command line, use that:
            self.config_file = _ARGS.config_file
        else:
            # If the config file is not specified on the command line,
            # try to get it from the environment. This is necessary
            # in gnome-shell on Fedora 18 because the setup tool is
            # called without command line options there but the
            # environment variable IBUS_ENGINE_NAME is set:
            try:
                ibus_engine_name = os.environ['IBUS_ENGINE_NAME']
                if ibus_engine_name.startswith('typing-booster:'):
                    self.config_file = (
                        ibus_engine_name.replace('typing-booster:', '')
                        + '.conf')
                else:
                    self.__run_message_dialog(
                        _('Unknown format of engine name: '
                          + 'IBUS_ENGINE_NAME=%(name)s')
                        %{'name': ibus_engine_name},
                        Gtk.MessageType.WARNING)
            except:
                self.__run_message_dialog(
                    _("IBUS_ENGINE_NAME environment variable is not set."),
                    Gtk.MessageType.WARNING)
        if self.config_file is None:
            self.__run_message_dialog(
                _('Cannot determine the config file for this engine. '
                  + 'Please use the --config-file option.'),
                Gtk.MessageType.ERROR)
            sys.exit(1)
            return
        self.config_file_full_path = (
            '/usr/share/ibus-typing-booster/hunspell-tables/'
            + self.config_file)
        if not os.path.isfile(self.config_file_full_path):
            self.__run_message_dialog(
                _("Config file %(file)s does not exist.")
                %{'file': self.config_file_full_path},
                Gtk.MessageType.ERROR)
            sys.exit(1)
            return

        self.tabsqlitedb = tabsqlitedb.tabsqlitedb(
            config_filename=self.config_file_full_path)
        self.name = self.tabsqlitedb.ime_properties.get('name')
        self.config_section = "engine/typing-booster/%s" % self.name
        self.hunspell_dict_package = self.tabsqlitedb.ime_properties.get(
            'hunspell_dict_package')
        self.symbol = self.tabsqlitedb.ime_properties.get('symbol')

        self.bus = bus
        self.config = self.bus.get_config()
        maindialog = self.builder.get_object("main_dialog")
        maindialog.set_title(
            _("Preferences for ibus-typing-booster \"%(symbol)s\"")
            %{'symbol': self.symbol})
        # https://tronche.com/gui/x/icccm/sec-4.html#WM_CLASS
        # gnome-shell seems to use the first argument of set_wmclass()
        # to find the .desktop file.  If the .desktop file can be
        # found, the name shown by gnome-shell in the top bar comes
        # from that .desktop file and the icon to show is also read
        # from that .desktop file. If the .desktop file cannot be
        # found, the second argument of set_wmclass() is shown by
        # gnome-shell in the top bar.
        maindialog.set_wmclass('ibus-setup-typing-booster', 'Typing Booster Preferences')
        maindialog.show()

        name_version = self.builder.get_object("name_version_label")
        name_version.set_markup(
            '<span font_size="large"><b>ibus-typing-booster %s</b></span>'
            %version.get_version())

        self.shortcut_entry = self.builder.get_object(
            "shortcut_entry")
        self.shortcut_expansion_entry = self.builder.get_object(
            "shortcut_expansion_entry")
        shortcut_clear_button = self.builder.get_object(
            "shortcut_clear_button")
        shortcut_clear_button.connect(
            'clicked', event_handler.on_shortcut_clear_clicked)
        shortcut_delete_button = self.builder.get_object(
            "shortcut_delete_button")
        shortcut_delete_button.connect(
            'clicked', event_handler.on_shortcut_delete_clicked)
        shortcut_add_button = self.builder.get_object(
            "shortcut_add_button")
        shortcut_add_button.connect(
            'clicked', event_handler.on_shortcut_add_clicked)
        self.shortcut_treeview = self.builder.get_object(
            "shortcut_treeview")
        self.shortcut_treeview_model = Gtk.ListStore(str, str)
        self.shortcut_treeview.set_model(self.shortcut_treeview_model)
        current_shortcuts = self.tabsqlitedb.list_user_shortcuts()
        for i, shortcut in enumerate(current_shortcuts):
            self.shortcut_treeview_model.append(shortcut)
        self.shortcut_treeview.append_column(
            Gtk.TreeViewColumn(
                # Translators: Column heading of the table listing the existing shortcuts
                _('Shortcut'),
                Gtk.CellRendererText(),
                text=0))
        self.shortcut_treeview.append_column(
            Gtk.TreeViewColumn(
                # Translators: Column heading of the table listing the existing shortcuts
                _('Shortcut expansion'),
                Gtk.CellRendererText(),
                text=1))
        self.shortcut_treeview.get_selection().connect(
            'changed', event_handler.on_shortcut_selected)

        self.install_dictionary_button = self.builder.get_object(
            "install_dictionary_button")
        self.install_dictionary_button.connect(
            'clicked', event_handler.on_install_dictionary_clicked)
        self.learn_from_file_button = self.builder.get_object(
            "learn_from_file_button")
        self.learn_from_file_button.connect(
            'clicked', event_handler.on_learn_from_file_clicked)
        self.delete_learned_data_button = self.builder.get_object(
            "delete_learned_data_button")
        self.delete_learned_data_button.connect(
            'clicked', event_handler.on_delete_learned_data_clicked)

        close_button = self.builder.get_object("close_button")
        close_button.connect('clicked', event_handler.onCloseClicked)

        tab_enable_checkbox = self.builder.get_object("tab_enable_checkbox")
        self.tab_enable = itb_util.variant_to_value(
            self.config.get_value(self.config_section, 'tabenable'))
        if self.tab_enable is None:
            self.tab_enable = False
        if  self.tab_enable is True:
            tab_enable_checkbox.set_active(True)
        tab_enable_checkbox.connect(
            'clicked', event_handler.on_tab_enable_checkbox)

        show_number_of_candidates_checkbox = self.builder.get_object(
            "show_number_of_candidates_checkbox")
        self.show_number_of_candidates = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'shownumberofcandidates'))
        if self.show_number_of_candidates is None:
            self.show_number_of_candidates = False
        if  self.show_number_of_candidates is True:
            show_number_of_candidates_checkbox.set_active(True)
        show_number_of_candidates_checkbox.connect(
            'clicked', event_handler.on_show_number_of_candidates_checkbox)

        use_digits_as_select_keys_checkbox = self.builder.get_object(
            "use_digits_as_select_keys_checkbox")
        self.use_digits_as_select_keys = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'usedigitsasselectkeys'))
        if self.use_digits_as_select_keys is None:
            self.use_digits_as_select_keys = True
        if self.use_digits_as_select_keys is True:
            use_digits_as_select_keys_checkbox.set_active(True)
        use_digits_as_select_keys_checkbox.connect(
            'clicked', event_handler.on_use_digits_as_select_keys_checkbox)

        emoji_predictions_checkbox = self.builder.get_object(
            "emoji_predictions_checkbox")
        self.emoji_predictions = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'emojipredictions'))
        if self.emoji_predictions is None:
            self.emoji_predictions = True
        if self.emoji_predictions is True:
            emoji_predictions_checkbox.set_active(True)
        emoji_predictions_checkbox.connect(
            'clicked', event_handler.on_emoji_predictions_checkbox)

        off_the_record_checkbox = self.builder.get_object(
            "off_the_record_checkbox")
        self.off_the_record = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'offtherecord'))
        if self.off_the_record is None:
            self.off_the_record = False
        if self.off_the_record is True:
            off_the_record_checkbox.set_active(True)
        off_the_record_checkbox.connect(
            'clicked', event_handler.on_off_the_record_checkbox)

        show_status_info_in_auxiliary_text_checkbox = self.builder.get_object(
            "show_status_info_in_auxiliary_text_checkbox")
        self.show_status_info_in_auxiliary_text = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'showstatusinfoinaux'))
        if self.show_status_info_in_auxiliary_text is None:
            self.show_status_info_in_auxiliary_text = True
        if self.show_status_info_in_auxiliary_text is True:
            show_status_info_in_auxiliary_text_checkbox.set_active(True)
        show_status_info_in_auxiliary_text_checkbox.connect(
            'clicked',
            event_handler.on_show_status_info_in_auxiliary_text_checkbox)

        add_direct_input_checkbox = self.builder.get_object(
            "add_direct_input_checkbox")
        self.add_direct_input = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'adddirectinput'))
        if self.add_direct_input is None:
            self.add_direct_input = False
        if  self.add_direct_input is True:
            add_direct_input_checkbox.set_active(True)
        add_direct_input_checkbox.connect(
            'clicked', event_handler.on_add_direct_input_checkbox)

        remember_last_used_preedit_ime_checkbox = self.builder.get_object(
            "remember_last_used_preedit_ime_checkbox")
        self.remember_last_used_predit_ime = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'rememberlastusedpreeditime'))
        if self.remember_last_used_predit_ime is None:
            self.remember_last_used_predit_ime = False
        if  self.remember_last_used_predit_ime is True:
            remember_last_used_preedit_ime_checkbox.set_active(True)
        remember_last_used_preedit_ime_checkbox.connect(
            'clicked',
            event_handler.on_remember_last_used_preedit_ime_checkbox)

        auto_commit_characters_entry = self.builder.get_object(
            "auto_commit_characters_entry")
        self.auto_commit_characters = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'autocommitcharacters'))
        if not self.auto_commit_characters:
            self.auto_commit_characters = ''
        auto_commit_characters_entry.set_text(self.auto_commit_characters)
        auto_commit_characters_entry.connect(
            'notify::text', event_handler.on_auto_commit_characters_entry)

        self.page_size_adjustment = self.builder.get_object(
            "page_size_adjustment")
        self.page_size = itb_util.variant_to_value(self.config.get_value(
            self.config_section, 'pagesize'))
        if self.page_size:
            self.page_size_adjustment.set_value(int(self.page_size))
        else:
            self.page_size_adjustment.set_value(6)
        self.page_size_adjustment.connect(
            'value-changed',
            event_handler.on_page_size_adjustment_value_changed)

        self.min_char_complete_adjustment = self.builder.get_object(
            "min_char_complete_adjustment")
        self.min_char_complete = itb_util.variant_to_value(
            self.config.get_value(self.config_section, 'mincharcomplete'))
        if self.min_char_complete:
            self.min_char_complete_adjustment.set_value(
                int(self.min_char_complete))
        else:
            self.min_char_complete_adjustment.set_value(1)
        self.min_char_complete_adjustment.connect(
            'value-changed',
            event_handler.on_min_char_complete_adjustment_value_changed)

        self.lookup_table_orientation_combobox = self.builder.get_object(
            "lookup_table_orientation_combobox")
        lookup_table_orientation_store = Gtk.ListStore(str, int)
        lookup_table_orientation_store.append(
            [_('Horizontal'), IBus.Orientation.HORIZONTAL])
        lookup_table_orientation_store.append(
            [_('Vertical'), IBus.Orientation.VERTICAL])
        lookup_table_orientation_store.append(
            [_('System default'), IBus.Orientation.SYSTEM])
        self.lookup_table_orientation_combobox.set_model(
            lookup_table_orientation_store)
        renderer_text = Gtk.CellRendererText()
        self.lookup_table_orientation_combobox.pack_start(
            renderer_text, True)
        self.lookup_table_orientation_combobox.add_attribute(
            renderer_text, "text", 0)
        lookup_table_orientation = itb_util.variant_to_value(
            self.config.get_value(
                self.config_section, 'lookuptableorientation'))
        if lookup_table_orientation is None:
            lookup_table_orientation = IBus.Orientation.VERTICAL
        for i, item in enumerate(lookup_table_orientation_store):
            if lookup_table_orientation == item[1]:
                self.lookup_table_orientation_combobox.set_active(i)
        self.lookup_table_orientation_combobox.connect(
            "changed",
            event_handler.on_lookup_table_orientation_combobox_changed)

        self.ime_combobox = self.builder.get_object("input_method_combobox")
        self.input_method_help_button = self.builder.get_object(
            "input_method_help_button")
        ime_store = Gtk.ListStore(str, str)
        self.supported_imes = []
        imes = self.tabsqlitedb.ime_properties.get('imes').split(',')
        if not imes:
            imes = ['Native Keyboard:NoIme']
        for item in imes:
            ime_store.append([item.split(':')[0], item.split(':')[1]])
            self.supported_imes.append(item.split(':')[1])
        self.ime_combobox.set_model(ime_store)
        self.ime_combobox.pack_start(renderer_text, True)
        self.ime_combobox.add_attribute(renderer_text, "text", 0)
        self.current_imes = []
        inputmethod = itb_util.variant_to_value(self.config.get_value(
            self.config_section, 'inputmethod'))
        if inputmethod:
            inputmethods = [x.strip() for x in inputmethod.split(',')]
            for ime in inputmethods:
                self.current_imes.append(ime)
        if self.current_imes == []:
            # There is no ime set in dconf, use the first value from
            # the combobox as the default:
            self.current_imes = [ime_store[0][1]]
            if self.add_direct_input and 'NoIme' not in self.current_imes:
                self.current_imes.append('NoIme')
        if len(self.current_imes) == 1:
            self.main_ime = self.current_imes[0]
        else:
            self.main_ime = (
                [x for x in self.current_imes if x in self.supported_imes][0])
        combobox_has_ime = False
        for i, dummy_item in enumerate(ime_store):
            if ime_store[i][1] == self.main_ime:
                self.ime_combobox.set_active(i)
                combobox_has_ime = True
        if combobox_has_ime is False:
            # the combobox did not have the ime from the settings
            # take the ime from the first row of
            # the combobox as the fallback:
            self.main_ime = ime_store[0][1]
            self.ime_combobox.set_active(0)
        self.ime_combobox.connect(
            "changed", event_handler.on_ime_combobox_changed)
        if len(ime_store) < 2:
            self.ime_combobox.set_sensitive(False)
        self.input_method_help_button.connect(
            'clicked', event_handler.on_input_method_help_button_clicked)
        if self.main_ime == 'NoIme':
            self.input_method_help_button.set_sensitive(False)

    def __run_message_dialog(self, message, message_type=Gtk.MessageType.INFO):
        '''Run a dialog to show an error or warning message'''
        dialog = Gtk.MessageDialog(
            parent=self.builder.get_object('main_dialog'),
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

class InputMethodHelpWindow(Gtk.Window):
    '''
    A window to show help for an input method

    :param parent: The parent object
    :type parent: Gtk.Dialog object
    :param title: Window title of the help window
    :type title: string
    :param description: description of the m17n input method
    :type description: string
    :param long_description: full contents of the file
                             implementing the m17n input method
    :type long_description: string
    '''
    def __init__(self, parent=None,
                 title='', description='', long_description=''):
        Gtk.Window.__init__(self, title=title)
        self.set_parent(parent)
        self.set_transient_for(parent)
        self.set_destroy_with_parent(False)
        self.set_default_size(600, 500)
        self.vbox = Gtk.VBox(spacing=0)
        self.add(self.vbox)
        self.text_buffer = Gtk.TextBuffer()
        self.text_buffer.insert_at_cursor(description)
        self.text_buffer.insert_at_cursor(
            '\n\n'
            + '############################################################'
            + '\n')
        self.text_buffer.insert_at_cursor(
            'Complete file implementing the input method follows here:\n')
        self.text_buffer.insert_at_cursor(
            '############################################################'
            + '\n')
        self.text_buffer.insert_at_cursor(long_description)
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

    def on_close_button_clicked(self, dummy_widget):
        '''
        Close the input method help window when the close buttonis clicked
        '''
        self.destroy()

class EventHandler:
    '''
    Event handler class to pass to Gtk.builder().connect_signals

    Needs to implement at least the two methods
        onDeleteDialog()
        onCloseClicked()
    '''
    # “Method could be a function”: pylint: disable=no-self-use
    def __init__(self):
        self.lang = 'English'

    def onDeleteDialog(self, *dummy_args): # “Invalid name” pylint: disable=C0103
        '''
        The dialog has been deleted, probably by the window manager
        '''
        Gtk.main_quit()

    def onCloseClicked(self, *dummy_args): # “Invalid name” pylint: disable=invalid-name
        '''
        The button to close the dialog has been clicked.
        '''
        Gtk.main_quit()

    def on_shortcut_clear_clicked(self, dummy_widget):
        '''
        The button to clear the entry fields for defining
        a custom shortcut has been clicked.
        '''
        SETUP_UI.shortcut_entry.set_text('')
        SETUP_UI.shortcut_expansion_entry.set_text('')
        SETUP_UI.shortcut_treeview.get_selection().unselect_all()

    def on_shortcut_delete_clicked(self, dummy_widget):
        '''
        The button to delete a custom shortcut has been clicked.
        '''
        shortcut = SETUP_UI.shortcut_entry.get_text().strip()
        shortcut_expansion = (
            SETUP_UI.shortcut_expansion_entry.get_text().strip())
        SETUP_UI.shortcut_entry.set_text('')
        SETUP_UI.shortcut_expansion_entry.set_text('')
        SETUP_UI.shortcut_treeview.get_selection().unselect_all()
        if shortcut and shortcut_expansion:
            model = SETUP_UI.shortcut_treeview_model
            iterator = model.get_iter_first()
            while iterator:
                if (model.get_value(iterator, 0) == shortcut
                        and
                        model.get_value(iterator, 1) == shortcut_expansion):
                    SETUP_UI.tabsqlitedb.remove_phrase(
                        input_phrase=shortcut,
                        phrase=shortcut_expansion)
                    if not model.remove(iterator):
                        iterator = None
                else:
                    iterator = model.iter_next(iterator)

    def on_shortcut_add_clicked(self, dummy_widget):
        '''
        The button to add a custom shortcut has been clicked.
        '''
        SETUP_UI.shortcut_treeview.get_selection().unselect_all()
        shortcut = SETUP_UI.shortcut_entry.get_text().strip()
        shortcut_expansion = (
            SETUP_UI.shortcut_expansion_entry.get_text().strip())
        if shortcut and shortcut_expansion:
            model = SETUP_UI.shortcut_treeview_model
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
                SETUP_UI.tabsqlitedb.check_phrase_and_update_frequency(
                    input_phrase=shortcut,
                    phrase=shortcut_expansion,
                    user_freq_increment=itb_util.SHORTCUT_USER_FREQ)
                model.append((shortcut, shortcut_expansion))
            SETUP_UI.shortcut_entry.set_text('')
            SETUP_UI.shortcut_expansion_entry.set_text('')
            SETUP_UI.shortcut_treeview.get_selection().unselect_all()

    def on_shortcut_selected(self, selection):
        '''
        A row in the list of shortcuts has been selected.
        '''
        (model, iterator) = selection.get_selected()
        if iterator:
            shortcut = model[iterator][0]
            shortcut_expansion = model[iterator][1]
            SETUP_UI.shortcut_entry.set_text(shortcut)
            SETUP_UI.shortcut_expansion_entry.set_text(shortcut_expansion)

    def on_install_dictionary_clicked(self, dummy_widget):
        '''
        The button to install the main dictionary for this engine
        has been clicked.
        '''
        SETUP_UI.install_dictionary_button.set_sensitive(False)
        InstallPkg(SETUP_UI.hunspell_dict_package)
        # Write a timestamp to dconf to trigger the callback
        # for changed dconf values in the engine and reload
        # the dictionary:
        SETUP_UI.config.set_value(
            SETUP_UI.config_section,
            'dictionaryinstalltimestamp',
            GLib.Variant.new_string(strftime('%Y-%m-%d %H:%M:%S')))
        SETUP_UI.install_dictionary_button.set_sensitive(True)

    def on_learn_from_file_clicked(self, dummy_widget):
        '''
        The button to learn from a user supplied text file
        has been clicked.
        '''
        SETUP_UI.learn_from_file_button.set_sensitive(False)
        filename = u''
        chooser = Gtk.FileChooserDialog(
            _('Open File ...'), SETUP_UI.builder.get_object('main_dialog'),
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
            if SETUP_UI.tabsqlitedb.read_training_data_from_file(filename):
                dialog = Gtk.MessageDialog(
                    parent=SETUP_UI.builder.get_object('main_dialog'),
                    flags=Gtk.DialogFlags.MODAL,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    message_format=(
                        _("Learned successfully from file %(filename)s.")
                        %{'filename': filename}))
            else:
                dialog = Gtk.MessageDialog(
                    parent=SETUP_UI.builder.get_object('main_dialog'),
                    flags=Gtk.DialogFlags.MODAL,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    message_format=(
                        _("Learning from file %(filename)s failed.")
                        %{'filename': filename}))
            dialog.run()
            dialog.destroy()
        SETUP_UI.learn_from_file_button.set_sensitive(True)

    def on_delete_learned_data_clicked(self, dummy_widget):
        '''
        The button requesting to delete all data learned from
        user input or text files has been clicked.
        '''
        SETUP_UI.delete_learned_data_button.set_sensitive(False)
        confirm_question = Gtk.Dialog(
            title=_('Are you sure?'),
            parent=SETUP_UI.builder.get_object('main_dialog'),
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
            SETUP_UI.tabsqlitedb.remove_all_phrases()
        SETUP_UI.delete_learned_data_button.set_sensitive(True)

    def on_tab_enable_checkbox(self, widget):
        '''
        The checkbox whether to show candidates only when
        requested with the tab key or not has been clicked.
        '''
        if widget.get_active():
            SETUP_UI.tab_enable = True
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'tabenable',
                GLib.Variant.new_boolean(True))
        else:
            SETUP_UI.tab_enable = False
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'tabenable',
                GLib.Variant.new_boolean(False))

    def on_show_number_of_candidates_checkbox(self, widget):
        '''
        The checkbox whether to show the number of candidates
        on top of the lookup table has been clicked.
        '''
        if widget.get_active():
            SETUP_UI.show_number_of_candidates = True
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'shownumberofcandidates',
                GLib.Variant.new_boolean(True))
        else:
            SETUP_UI.show_number_of_candidates = False
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'shownumberofcandidates',
                GLib.Variant.new_boolean(False))

    def on_use_digits_as_select_keys_checkbox(self, widget):
        '''
        The checkbox whether to use the digits 1 … 9 as select
        keys has been clicked.
        '''
        if widget.get_active():
            SETUP_UI.use_digits_as_select_keys = True
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'usedigitsasselectkeys',
                GLib.Variant.new_boolean(True))
        else:
            SETUP_UI.use_digits_as_select_keys = False
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'usedigitsasselectkeys',
                GLib.Variant.new_boolean(False))

    def on_emoji_predictions_checkbox(self, widget):
        '''
        The checkbox whether to predict emoji as well or not
        has been clicked.
        '''
        if widget.get_active():
            SETUP_UI.emoji_predictions = True
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'emojipredictions',
                GLib.Variant.new_boolean(True))
        else:
            SETUP_UI.emoji_predictions = False
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'emojipredictions',
                GLib.Variant.new_boolean(False))

    def on_off_the_record_checkbox(self, widget):
        '''
        The checkbox whether to use “Off the record” mode, i.e. whether to
        learn from user data by saving user input to the user database
        or not, has been clicked.
        '''
        if widget.get_active():
            SETUP_UI.off_the_record = True
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'offtherecord',
                GLib.Variant.new_boolean(True))
        else:
            SETUP_UI.off_the_record = False
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'offtherecord',
                GLib.Variant.new_boolean(False))

    def on_show_status_info_in_auxiliary_text_checkbox(self, widget):
        '''
        The checkbox whether to show status in the auxiliary text,
        has been clicked.
        '''
        if widget.get_active():
            SETUP_UI.show_status_info_in_auxiliary_text = True
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'showstatusinfoinaux',
                GLib.Variant.new_boolean(True))
        else:
            SETUP_UI.show_status_info_in_auxiliary_text = False
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'showstatusinfoinaux',
                GLib.Variant.new_boolean(False))

    def on_add_direct_input_checkbox(self, widget):
        '''
        The checkbox whether to add direct input, i.e.  whether to add
        native keyboard input and the British English dictionary, has
        been clicked.
        '''
        if widget.get_active():
            SETUP_UI.add_direct_input = True
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'adddirectinput',
                GLib.Variant.new_boolean(True))
        else:
            SETUP_UI.add_direct_input = False
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'adddirectinput',
                GLib.Variant.new_boolean(False))

    def on_remember_last_used_preedit_ime_checkbox(self, widget):
        '''
        The checkbox whether to remember the last used input method
        for the preëdit has been clicked.
        '''
        if widget.get_active():
            SETUP_UI.remember_last_used_predit_ime = True
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'rememberlastusedpreeditime',
                GLib.Variant.new_boolean(True))
        else:
            SETUP_UI.remember_last_used_predit_ime = False
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'rememberlastusedpreeditime',
                GLib.Variant.new_boolean(False))

    def on_auto_commit_characters_entry(self, widget, dummy_property_spec):
        '''
        The list of characters triggering an auto commit has been changed.
        '''
        SETUP_UI.auto_commit_characters = widget.get_text()
        SETUP_UI.config.set_value(
            SETUP_UI.config_section,
            'autocommitcharacters',
            GLib.Variant.new_string(SETUP_UI.auto_commit_characters))

    def on_page_size_adjustment_value_changed(self, dummy_widget):
        '''
        The page size of the lookup table has been changed.
        '''
        page_size = SETUP_UI.page_size_adjustment.get_value()
        SETUP_UI.config.set_value(
            SETUP_UI.config_section,
            'pagesize',
            GLib.Variant.new_int32(page_size))

    def on_min_char_complete_adjustment_value_changed(self, dummy_widget):
        '''
        The value for the mininum number of characters before
        completion is attempted has been changed.
        '''
        min_char_complete = (
            SETUP_UI.min_char_complete_adjustment.get_value())
        SETUP_UI.config.set_value(
            SETUP_UI.config_section,
            'mincharcomplete',
            GLib.Variant.new_int32(min_char_complete))

    def on_lookup_table_orientation_combobox_changed(self, widget):
        '''
        A change of the lookup table orientation has been requested
        with the combobox
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter != None:
            model = widget.get_model()
            orientation = model[tree_iter][1]
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'lookuptableorientation',
                GLib.Variant.new_int32(orientation))

    def on_ime_combobox_changed(self, widget):
        '''
        A change of the active input method has been requested
        with the combobox.
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter != None:
            model = widget.get_model()
            main_ime = model[tree_iter][1]
            # Remove all supported imes and 'NoIme' from the current imes.
            # This is to keep additional imes which might have been added
            # setting the dconf key directly instead of using this setup tool.
            SETUP_UI.current_imes = [
                x for x in SETUP_UI.current_imes if (
                    x not in SETUP_UI.supported_imes and x != 'NoIme')]
            SETUP_UI.current_imes = [main_ime] + SETUP_UI.current_imes
            if ('NoIme' not in SETUP_UI.current_imes
                    and SETUP_UI.add_direct_input is True):
                SETUP_UI.current_imes.append('NoIme')
            SETUP_UI.config.set_value(
                SETUP_UI.config_section,
                'inputmethod',
                GLib.Variant.new_string(','.join(SETUP_UI.current_imes)))
            if main_ime == 'NoIme':
                SETUP_UI.input_method_help_button.set_sensitive(False)
            else:
                SETUP_UI.input_method_help_button.set_sensitive(True)

    def on_input_method_help_button_clicked(self, dummy_widget):
        '''
        Show a help window for the input method selected in the
        combobox.
        '''
        tree_iter = SETUP_UI.ime_combobox.get_active_iter()
        if tree_iter != None:
            model = SETUP_UI.ime_combobox.get_model()
            ime_name = model[tree_iter][1]
        if not ime_name or ime_name == 'NoIme':
            return
        mim_file_names = {'t-latn-post': 'latn-post',
                          't-latn-pre': 'latn-pre',
                          'ne-inscript2': 'ne-inscript2-deva',
                          'si-transliteration': 'si-trans'}
        if ime_name in mim_file_names:
            mim_file = mim_file_names[ime_name]+'.mim'
        else:
            mim_file = ime_name+'.mim'
        mim_file_contents = None
        try:
            mim_file_contents = open(
                '/usr/share/m17n/%(mim)s' %{'mim': mim_file},
                mode='r',
                encoding='UTF-8',
                errors='ignore'
            ).read()
        except:
            import traceback
            traceback.print_exc()
        if mim_file_contents:
            description_pattern = re.compile(
                r'\([\s]*description[\s]*"(?P<description>.+?)(?<!\\)"[\s]*\)',
                re.DOTALL|re.MULTILINE|re.UNICODE)
            match = description_pattern.search(mim_file_contents)
            description = u''
            if match:
                description = match.group('description').replace('\\"', '"')
            win = InputMethodHelpWindow(
                parent=SETUP_UI.builder.get_object('main_dialog'),
                title=mim_file,
                description=description,
                long_description=mim_file_contents)
            win.show_all()

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
