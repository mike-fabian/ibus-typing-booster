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


import sys
import os
from os import path
import re
import signal
import optparse
import locale
from time import strftime
from i18n import DOMAINNAME, _, N_, init as i18n_init
import dbus, dbus.service, dbus.glib
from gi import require_version
require_version('Gtk', '3.0')
from gi.repository import Gtk
require_version('IBus', '1.0')
from gi.repository import IBus
from gi.repository import GLib
from pkginstall import InstallPkg

sys.path = [sys.path[0]+'/../engine'] + sys.path
import tabsqlitedb

import version

opt = optparse.OptionParser()
opt.set_usage ('%prog [options]')
opt.add_option(
    '-c', '--config-file',
    action = 'store',
    type = 'string',
    dest = 'config_file',
    default = '',
    help = ('Set the file name of config file for the ime engine, '
            + 'default: %default'))
opt.add_option(
    '-q', '--no-debug',
    action = 'store_false',
    dest = 'debug',
    default = True,
    help = ('redirect stdout and stderr to '
            + '~/.local/share/ibus-typing-booster/setup-debug.log, '
            + 'default: %default'))

(options, args) = opt.parse_args()

if options.debug:
    if (not os.access(
            os.path.expanduser('~/.local/share/ibus-typing-booster'),
            os.F_OK)):
        os.system ('mkdir -p ~/.local/share/ibus-typing-booster')
    logfile = os.path.expanduser(
        '~/.local/share/ibus-typing-booster/setup-debug.log')
    sys.stdout = open(logfile, mode='a', buffering=1)
    sys.stderr = open(logfile, mode='a', buffering=1)
    print('--- %s ---' %strftime('%Y-%m-%d: %H:%M:%S'))

class SetupUI:
    def __init__(self, bus):
        filename = path.join(path.dirname(__file__),"setup.glade")
        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(DOMAINNAME)
        self.builder.add_from_file(filename)
        event_handler = EventHandler()
        self.builder.connect_signals(event_handler)
        if not self.check_instance():
            service = SetupService()
        # Try to figure out the config file name:
        self.config_file = None
        if options.config_file:
            # If the config file is specified on the command line, use that:
            self.config_file = options.config_file
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
        if self.config_file == None:
            self.__run_message_dialog(
                _('Cannot determine the config file for this engine. '
                  + 'Please use the --config-file option.'),
                Gtk.MessageType.ERROR)
            sys.exit(1)
            return
        config_file_full_path = (
            '/usr/share/ibus-typing-booster/hunspell-tables/'
            + self.config_file)
        if not os.path.isfile(config_file_full_path):
            self.__run_message_dialog(
                _("Config file %(file)s does not exist.")
                %{'file': config_file_full_path},
                Gtk.MessageType.ERROR)
            sys.exit(1)
            return

        self.tabsqlitedb = tabsqlitedb.tabsqlitedb(
            config_filename = self.config_file)
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
        maindialog.show()

        name_version = self.builder.get_object("name_version_label")
        name_version.set_markup(
            '<span font_size="large"><b>ibus-typing-booster %s</b></span>'
            %version.get_version())

        self.install_dictionary_button = self.builder.get_object(
            "install_dictionary_button")
        self.install_dictionary_button.connect(
            'clicked', event_handler.onInstallDictionaryClicked)
        self.learn_from_file_button = self.builder.get_object(
            "learn_from_file_button")
        self.learn_from_file_button.connect(
            'clicked', event_handler.onLearnFromFileClicked)
        self.delete_learned_data_button = self.builder.get_object(
            "delete_learned_data_button")
        self.delete_learned_data_button.connect(
            'clicked', event_handler.onDeleteLearnedDataClicked)

        close_button = self.builder.get_object("close_button")
        close_button.connect('clicked', event_handler.onCloseClicked)

        tab_enable_checkbox = self.builder.get_object("tab_enable_checkbox")
        self.tab_enable = self.variant_to_value(
            self.config.get_value(self.config_section, 'tabenable'))
        if self.tab_enable == None:
            self.tab_enable = False
        if  self.tab_enable == True:
            tab_enable_checkbox.set_active(True)
        tab_enable_checkbox.connect(
            'clicked', event_handler.onTabEnableCheckbox)

        show_number_of_candidates_checkbox = self.builder.get_object(
            "show_number_of_candidates_checkbox")
        self.show_number_of_candidates = self.variant_to_value(
            self.config.get_value(
                self.config_section, 'shownumberofcandidates'))
        if self.show_number_of_candidates == None:
            self.show_number_of_candidates = False
        if  self.show_number_of_candidates == True:
            show_number_of_candidates_checkbox.set_active(True)
        show_number_of_candidates_checkbox.connect(
            'clicked', event_handler.onShowNumberOfCandidatesCheckbox)

        use_digits_as_select_keys_checkbox = self.builder.get_object(
            "use_digits_as_select_keys_checkbox")
        self.use_digits_as_select_keys = self.variant_to_value(
            self.config.get_value(
                self.config_section, 'usedigitsasselectkeys'))
        if self.use_digits_as_select_keys == None:
            self.use_digits_as_select_keys = True
        if self.use_digits_as_select_keys == True:
            use_digits_as_select_keys_checkbox.set_active(True)
        use_digits_as_select_keys_checkbox.connect(
            'clicked', event_handler.onUseDigitsAsSelectKeysCheckbox)

        emoji_predictions_checkbox = self.builder.get_object(
            "emoji_predictions_checkbox")
        self.emoji_predictions = self.variant_to_value(
            self.config.get_value(
                self.config_section, 'emojipredictions'))
        if self.emoji_predictions == None:
            self.emoji_predictions = True
        if self.emoji_predictions == True:
            emoji_predictions_checkbox.set_active(True)
        emoji_predictions_checkbox.connect(
            'clicked', event_handler.onEmojiPredictionsCheckbox)

        off_the_record_checkbox = self.builder.get_object(
            "off_the_record_checkbox")
        self.off_the_record = self.variant_to_value(
            self.config.get_value(
                self.config_section, 'offtherecord'))
        if self.off_the_record == None:
            self.off_the_record = False
        if self.off_the_record == True:
            off_the_record_checkbox.set_active(True)
        off_the_record_checkbox.connect(
            'clicked', event_handler.onOffTheRecordCheckbox)

        add_direct_input_checkbox = self.builder.get_object(
            "add_direct_input_checkbox")
        self.add_direct_input = self.variant_to_value(
            self.config.get_value(
                self.config_section, 'adddirectinput'))
        if self.add_direct_input == None:
            self.add_direct_input = False
        if  self.add_direct_input == True:
            add_direct_input_checkbox.set_active(True)
        add_direct_input_checkbox.connect(
            'clicked', event_handler.onAddDirectInputCheckbox)

        remember_last_used_preedit_ime_checkbox = self.builder.get_object(
            "remember_last_used_preedit_ime_checkbox")
        self.remember_last_used_predit_ime = self.variant_to_value(
            self.config.get_value(
                self.config_section, 'rememberlastusedpreeditime'))
        if self.remember_last_used_predit_ime == None:
            self.remember_last_used_predit_ime = False
        if  self.remember_last_used_predit_ime == True:
            remember_last_used_preedit_ime_checkbox.set_active(True)
        remember_last_used_preedit_ime_checkbox.connect(
            'clicked', event_handler.onRememberLastUsedPreeditImeCheckbox)

        auto_commit_characters_entry = self.builder.get_object(
            "auto_commit_characters_entry")
        self.auto_commit_characters = self.variant_to_value(
            self.config.get_value(
                self.config_section, 'autocommitcharacters'))
        if not self.auto_commit_characters:
            self.auto_commit_characters = ''
        auto_commit_characters_entry.set_text(self.auto_commit_characters)
        auto_commit_characters_entry.connect(
            'notify::text', event_handler.onAutoCommitCharactersEntry)

        self.page_size_adjustment = self.builder.get_object(
            "page_size_adjustment")
        self.page_size = self.variant_to_value(self.config.get_value(
            self.config_section, 'pagesize'))
        if self.page_size:
            self.page_size_adjustment.set_value(int(self.page_size))
        else:
            self.page_size_adjustment.set_value(6)
        self.page_size_adjustment.connect(
            'value-changed', event_handler.onPageSizeAdjustmentValueChanged)

        self.min_char_complete_adjustment = self.builder.get_object(
            "min_char_complete_adjustment")
        self.min_char_complete = self.variant_to_value(
            self.config.get_value(self.config_section, 'mincharcomplete'))
        if self.min_char_complete:
            self.min_char_complete_adjustment.set_value(
                int(self.min_char_complete))
        else:
            self.min_char_complete_adjustment.set_value(1)
        self.min_char_complete_adjustment.connect(
            'value-changed',
            event_handler.onMinCharCompleteAdjustmentValueChanged)

        self.ime_combobox = self.builder.get_object("input_method_combobox")
        ime_label = self.builder.get_object("input_method_label")
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
        renderer_text = Gtk.CellRendererText()
        self.ime_combobox.pack_start(renderer_text, True)
        self.ime_combobox.add_attribute(renderer_text, "text", 0)
        self.current_imes = []
        inputmethod = self.variant_to_value(self.config.get_value(
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
        for i in range(len(ime_store)):
            if ime_store[i][1] == self.main_ime:
                self.ime_combobox.set_active(i)
                combobox_has_ime = True
        if combobox_has_ime == False:
            # the combobox did not have the ime from the settings
            # take the ime from the first row of
            # the combobox as the fallback:
            self.main_ime = ime_store[0][1]
            self.ime_combobox.set_active(0)
        self.ime_combobox.connect(
            "changed", event_handler.onImeComboboxChanged)
        if len(ime_store) < 2:
            self.ime_combobox.set_sensitive(False)
        self.input_method_help_button.connect(
            'clicked', event_handler.onInputMethodHelpButtonClicked)
        if self.main_ime == 'NoIme':
            self.input_method_help_button.set_sensitive(False)

    def __run_message_dialog(self, message, message_type=Gtk.MessageType.INFO):
        dlg = Gtk.MessageDialog(
            parent = self.builder.get_object('main_dialog'),
            flags = Gtk.DialogFlags.MODAL,
            message_type = message_type,
            buttons = Gtk.ButtonsType.OK,
            message_format = message)
        dlg.run()
        dlg.destroy()

    def check_instance(self):
        if (dbus.SessionBus().request_name("org.ibus.typingbooster")
            != dbus.bus.REQUEST_NAME_REPLY_PRIMARY_OWNER):
            self.__run_message_dialog(
                _("Another instance of this app is already running."),
                Gtk.MessageType.ERROR)
            sys.exit(1)
        else:
            return False

    def variant_to_value(self, variant):
        if type(variant) != GLib.Variant:
            return variant
        if variant.get_type_string() == 's':
            return variant.get_string()
        elif variant.get_type_string() == 'i':
            return variant.get_int32()
        elif variant.get_type_string() == 'b':
            return variant.get_boolean()
        elif variant.get_type_string() == 'as':
            return variant.dup_strv()[0]
        else:
            return variant

class InputMethodHelpWindow(Gtk.Window):
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

    def on_close_button_clicked(self, widget):
        self.destroy()

class EventHandler:
    def __init__(self):
        self.lang = 'English'

    def onDeleteDialog(self, *args):
        Gtk.main_quit()

    def onCloseClicked(self, *args):
        Gtk.main_quit()

    def onInstallDictionaryClicked(self, widget):
        SetupUi.install_dictionary_button.set_sensitive(False)
        InstallPkg(SetupUi.hunspell_dict_package)
        # Write a timestamp to dconf to trigger the callback
        # for changed dconf values in the engine and reload
        # the dictionary:
        SetupUi.config.set_value(
            SetupUi.config_section,
            'dictionaryinstalltimestamp',
            GLib.Variant.new_string(strftime('%Y-%m-%d %H:%M:%S')))
        SetupUi.install_dictionary_button.set_sensitive(True)

    def onLearnFromFileClicked(self, widget):
        SetupUi.learn_from_file_button.set_sensitive(False)
        filename = u''
        chooser = Gtk.FileChooserDialog(
            _('Open File ...'), SetupUi.builder.get_object('main_dialog'),
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
            if SetupUi.tabsqlitedb.read_training_data_from_file(filename):
                dialog = Gtk.MessageDialog(
                    parent=SetupUi.builder.get_object('main_dialog'),
                    flags=Gtk.DialogFlags.MODAL,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    message_format= (
                        _("Learned successfully from file %(filename)s.")
                        %{'filename': filename}))
            else:
                dialog = Gtk.MessageDialog(
                    parent=SetupUi.builder.get_object('main_dialog'),
                    flags=Gtk.DialogFlags.MODAL,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    message_format= (
                        _("Learning from file %(filename)s failed.")
                        %{'filename': filename}))
            dialog.run()
            dialog.destroy()
        SetupUi.learn_from_file_button.set_sensitive(True)

    def onDeleteLearnedDataClicked(self, widget):
        SetupUi.delete_learned_data_button.set_sensitive(False)
        confirm_question = Gtk.Dialog(
            title=_('Are you sure?'),
            parent=SetupUi.builder.get_object('main_dialog'),
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
            SetupUi.tabsqlitedb.remove_all_phrases()
        SetupUi.delete_learned_data_button.set_sensitive(True)

    def onTabEnableCheckbox(self, widget):
        if widget.get_active():
            SetupUi.tab_enable = True
            SetupUi.config.set_value(
                SetupUi.config_section,
                'tabenable',
                GLib.Variant.new_boolean(True))
        else:
            SetupUi.tab_enable = False
            SetupUi.config.set_value(
                SetupUi.config_section,
                'tabenable',
                GLib.Variant.new_boolean(False))

    def onShowNumberOfCandidatesCheckbox(self, widget):
        if widget.get_active():
            SetupUi.show_number_of_candidates = True
            SetupUi.config.set_value(
                SetupUi.config_section,
                'shownumberofcandidates',
                GLib.Variant.new_boolean(True))
        else:
            SetupUi.show_number_of_candidates = False
            SetupUi.config.set_value(
                SetupUi.config_section,
                'shownumberofcandidates',
                GLib.Variant.new_boolean(False))

    def onUseDigitsAsSelectKeysCheckbox(self, widget):
        if widget.get_active():
            SetupUi.use_digits_as_select_keys = True
            SetupUi.config.set_value(
                SetupUi.config_section,
                'usedigitsasselectkeys',
                GLib.Variant.new_boolean(True))
        else:
            SetupUi.use_digits_as_select_keys = False
            SetupUi.config.set_value(
                SetupUi.config_section,
                'usedigitsasselectkeys',
                GLib.Variant.new_boolean(False))

    def onEmojiPredictionsCheckbox(self, widget):
        if widget.get_active():
            SetupUi.emoji_predictions = True
            SetupUi.config.set_value(
                SetupUi.config_section,
                'emojipredictions',
                GLib.Variant.new_boolean(True))
        else:
            SetupUi.emoji_predictions = False
            SetupUi.config.set_value(
                SetupUi.config_section,
                'emojipredictions',
                GLib.Variant.new_boolean(False))

    def onOffTheRecordCheckbox(self, widget):
        if widget.get_active():
            SetupUi.off_the_record = True
            SetupUi.config.set_value(
                SetupUi.config_section,
                'offtherecord',
                GLib.Variant.new_boolean(True))
        else:
            SetupUi.off_the_record = False
            SetupUi.config.set_value(
                SetupUi.config_section,
                'offtherecord',
                GLib.Variant.new_boolean(False))

    def onAddDirectInputCheckbox(self, widget):
        if widget.get_active():
            SetupUi.add_direct_input = True
            SetupUi.config.set_value(
                SetupUi.config_section,
                'adddirectinput',
                GLib.Variant.new_boolean(True))
        else:
            SetupUi.add_direct_input = False
            SetupUi.config.set_value(
                SetupUi.config_section,
                'adddirectinput',
                GLib.Variant.new_boolean(False))

    def onRememberLastUsedPreeditImeCheckbox(self, widget):
        if widget.get_active():
            SetupUi.remember_last_used_predit_ime = True
            SetupUi.config.set_value(
                SetupUi.config_section,
                'rememberlastusedpreeditime',
                GLib.Variant.new_boolean(True))
        else:
            SetupUi.remember_last_used_predit_ime = False
            SetupUi.config.set_value(
                SetupUi.config_section,
                'rememberlastusedpreeditime',
                GLib.Variant.new_boolean(False))

    def onAutoCommitCharactersEntry(self, widget, property_spec):
        SetupUi.auto_commit_characters = widget.get_text()
        SetupUi.config.set_value(
            SetupUi.config_section,
            'autocommitcharacters',
            GLib.Variant.new_string(SetupUi.auto_commit_characters))

    def onPageSizeAdjustmentValueChanged(self, widget):
        self.page_size = SetupUi.page_size_adjustment.get_value()
        SetupUi.config.set_value(
            SetupUi.config_section,
            'pagesize',
            GLib.Variant.new_int32(self.page_size))

    def onMinCharCompleteAdjustmentValueChanged(self, widget):
        self.min_char_complete = (
            SetupUi.min_char_complete_adjustment.get_value())
        SetupUi.config.set_value(
            SetupUi.config_section,
            'mincharcomplete',
            GLib.Variant.new_int32(self.min_char_complete))

    def onImeComboboxChanged(self, widget):
        tree_iter = widget.get_active_iter()
        if tree_iter != None:
            model = widget.get_model()
            main_ime = model[tree_iter][1]
            # Remove all supported imes and 'NoIme' from the current imes.
            # This is to keep additional imes which might have been added
            # setting the dconf key directly instead of using this setup tool.
            SetupUi.current_imes = [
                x for x in SetupUi.current_imes if (
                    x not in SetupUi.supported_imes and x != 'NoIme')]
            SetupUi.current_imes = [main_ime] + SetupUi.current_imes
            if ('NoIme' not in SetupUi.current_imes
                and SetupUi.add_direct_input == True):
                SetupUi.current_imes.append('NoIme')
            SetupUi.config.set_value(
                SetupUi.config_section,
                'inputmethod',
                GLib.Variant.new_string(','.join(SetupUi.current_imes)))
            if main_ime == 'NoIme':
                SetupUi.input_method_help_button.set_sensitive(False)
            else:
                SetupUi.input_method_help_button.set_sensitive(True)

    def onInputMethodHelpButtonClicked(self, widget):
        tree_iter = SetupUi.ime_combobox.get_active_iter()
        if tree_iter != None:
            model = SetupUi.ime_combobox.get_model()
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
                mode = 'r',
                encoding = 'UTF-8',
                errors = 'ignore'
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
                parent=SetupUi.builder.get_object('main_dialog'),
                title=mim_file,
                description=description,
                long_description = mim_file_contents)
            win.show_all()

class SetupService(dbus.service.Object):
    def __init__(self):
        bus_name = dbus.service.BusName(
            'org.ibus.typingbooster', bus = dbus.SessionBus())
        dbus.service.Object.__init__(self, bus_name, '/org/ibus/typingbooster')

if __name__ == '__main__':
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
    if IBus.get_address() == None:
        dlg = Gtk.MessageDialog(
            flags = Gtk.DialogFlags.MODAL,
            message_type = Gtk.MessageType.ERROR,
            buttons = Gtk.ButtonsType.OK,
            message_format = _('ibus is not running.'))
        dlg.run()
        dlg.destroy()
        sys.exit(1)
    SetupUi = SetupUI(IBus.Bus())
    Gtk.main()
