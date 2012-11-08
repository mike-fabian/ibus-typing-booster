# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 2012-2013 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012 Mike FABIAN <mfabian@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#  This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#  You should have received a copy of the GNU General Public License 
# along with this program.  If not, see <http://www.gnu.org/licenses/>


import sys
import os
from os import path
import optparse
import locale
from i18n import DOMAINNAME, _, N_, init as i18n_init

sys.path = [sys.path[0]+'/../engine'] + sys.path
import tabsqlitedb

opt = optparse.OptionParser()
opt.set_usage ('%prog [options]')
opt.add_option('-c', '--config-file',
        action = 'store',type = 'string',dest = 'config_file',default = '',
        help = 'Set the file name of config file for the ime engine, default: %default')
opt.add_option( '-q', '--no-debug',
        action = 'store_false',dest = 'debug',default = True,
        help = 'redirect stdout and stderr to ~/.local/share/.ibus/ibus-typing-booster/setup-debug.log, default: %default')

(options, args) = opt.parse_args()

if options.debug:
    if not os.access ( os.path.expanduser('~/.local/share/.ibus/ibus-typing-booster'), os.F_OK):
        os.system ('mkdir -p ~/.local/share/.ibus/ibus-typing-booster')
    logfile = os.path.expanduser('~/.local/share/.ibus/ibus-typing-booster/setup-debug.log')
    sys.stdout = open (logfile,'a',0)
    sys.stderr = open (logfile,'a',0)
    from time import strftime
    print '--- ', strftime('%Y-%m-%d: %H:%M:%S'), ' ---'

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango
from gi.repository import IBus
from gi.repository import GLib
from pkginstall import InstallPkg

class SetupUI:
    def __init__(self):
        filename = path.join(path.dirname(__file__),"setup.glade")
        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(DOMAINNAME)
        self.builder.add_from_file(filename)
        event_handler = EventHandler()
        self.builder.connect_signals(event_handler)

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
                    self.config_file = ibus_engine_name.replace('typing-booster:','') + '.conf'
                else:
                    self.__run_message_dialog(
                        _("Unknown format of engine name: IBUS_ENGINE_NAME=%(name)s")
                        %{'name': ibus_engine_name},
                        Gtk.MessageType.WARNING)
            except:
                self.__run_message_dialog(
                    _("IBUS_ENGINE_NAME environment variable is not set."),
                    Gtk.MessageType.WARNING)
        if self.config_file == None:
            self.__run_message_dialog(
                _("Cannot determine the config file for this engine. Please use the --config-file option."),
                Gtk.MessageType.ERROR)
            sys.exit(1)
            return
        config_file_full_path = "/usr/share/ibus-typing-booster/hunspell-tables/" + self.config_file
        if not os.path.isfile(config_file_full_path):
            self.__run_message_dialog(
                _("Config file %(file)s does not exist.")
                %{'file': config_file_full_path},
                Gtk.MessageType.ERROR)
            sys.exit(1)
            return

        self.db = tabsqlitedb.tabsqlitedb (filename=self.config_file)
        self.name = self.db.get_ime_property('name')
        self.config_section = "engine/typing-booster/%s" % self.name
        self.hunspell_dict_package = self.db.get_ime_property('hunspell_dict_package')
        self.symbol = self.db.get_ime_property('symbol')
        if IBus.get_address() == None:
            self.__run_message_dialog(_("ibus is not running."), Gtk.MessageType.ERROR)
            sys.exit(1)
            return

        self.config = IBus.Bus().get_config()
        maindialog = self.builder.get_object("dialog1")
        maindialog.set_title(_("Preferences for ibus-typing-booster \"%(symbol)s\"") %{'symbol': self.symbol})
        maindialog.show()
        install_button = self.builder.get_object("button1")
        install_button.connect('clicked', event_handler.onInstallClicked)
        close_button = self.builder.get_object("button2")
        close_button.connect('clicked', event_handler.onCloseClicked)
        chkbox = self.builder.get_object("checkbutton1")
        self.tab_enable = self.variant_to_value(self.config.get_value(self.config_section, 'tabenable'))
        if self.tab_enable == None:
            self.tab_enable = self.db.get_ime_property('tab_enable').lower() == u'true'
        if  self.tab_enable == True:
            chkbox.set_active(True)
        chkbox.connect('clicked', event_handler.onCheck)
        self.page_size_adjustment = self.builder.get_object("page_size_adjustment")
        self.page_size = self.variant_to_value(self.config.get_value(self.config_section, 'pagesize'))
        if self.page_size == None:
            self.page_size = self.db.get_ime_property('page_size')
        if self.page_size != None:
            self.page_size_adjustment.set_value(int(self.page_size))
        else:
            self.page_size_adjustment.set_value(6)
        self.page_size_adjustment.connect('value-changed', event_handler.onPageSizeAdjustmentValueChanged)

    def __run_message_dialog(self, message, type=Gtk.MessageType.INFO):
        dlg = Gtk.MessageDialog(parent=self.builder.get_object('main'),
                                flags=Gtk.DialogFlags.MODAL,
                                message_type=type,
                                buttons=Gtk.ButtonsType.OK,
                                message_format=message)
        dlg.run()
        dlg.destroy()


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


class EventHandler:
    def __init__(self):
        self.lang = 'English'

    def onDeleteDialog(self, *args):
        Gtk.main_quit()

    def onCloseClicked(self, *args):
        Gtk.main_quit()

    def onInstallClicked(self,widget):
        InstallPkg(SetupUi.hunspell_dict_package)

    def onCheck(self,widget):
        if widget.get_active():
            SetupUi.tab_enable = True
            SetupUi.config.set_value(SetupUi.config_section,'tabenable',GLib.Variant.new_boolean(True))
        else:
            SetupUi.tab_enable = False
            SetupUi.config.set_value(SetupUi.config_section,'tabenable',GLib.Variant.new_boolean(False))

    def onPageSizeAdjustmentValueChanged(self,widget):
        self.page_size = SetupUi.page_size_adjustment.get_value()
        SetupUi.config.set_value(SetupUi.config_section,'pagesize',GLib.Variant.new_int32(self.page_size))

if __name__ == '__main__':
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        print >> sys.stderr, "IBUS-WARNING **: Using the fallback 'C' locale"
        locale.setlocale(locale.LC_ALL, 'C')
    i18n_init()
    SetupUi = SetupUI()
    Gtk.main()

