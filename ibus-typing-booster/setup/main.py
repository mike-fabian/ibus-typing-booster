# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 2012-2013 Anish Patil <apatil@redhat.com>
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


from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango
from gi.repository import IBus
from gi.repository import GLib
from pref import DictPref
from pkginstall import InstallPkg
from os import path

class SetupUI:
    def __init__(self):
        filename = path.join(path.dirname(__file__),"setup.glade")
        self.builder = Gtk.Builder()
        self.builder.add_from_file(filename)
        event_handler = EventHander()
        self.builder.connect_signals(event_handler)
        if IBus.get_address() == None:
            self.__run_message_dialog(("ibus is not running."), Gtk.MessageType.ERROR)
            self.builder.connect_signals(event_handler)
            return

        self.config = IBus.Bus().get_config()
        maindialog = self.builder.get_object("dialog1")
        maindialog.set_title('Preferences for ibus-typing-booster')
        maindialog.show()
        choose_lang = self.builder.get_object("choose_lang")
        choose_lang.set_active(0)
        choose_lang.connect('changed', event_handler.changeSrcLang)
        install_button = self.builder.get_object("button1")
        install_button.connect('clicked', event_handler.onInstallClicked)
        close_button = self.builder.get_object("button2")
        close_button.connect('clicked', event_handler.onCloseClicked)
        chkbox = self.builder.get_object("checkbutton1")
        chkbox.connect('clicked', event_handler.onCheck)
        if self.variant_to_value(self.config.get_value('Key','Tab')) == True:
            chkbox.set_active(True)

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


class EventHander:
    def __init__(self):
        self.lang = 'English'

    def onDeleteDialog(self, *args):
        Gtk.main_quit()

    def onCloseClicked(self, *args):
        Gtk.main_quit()

    def changeSrcLang(self,widget):
        model = widget.get_model()
        index = widget.get_active()
        if index > -1:
            self.lang = model[index][0]

    def onInstallClicked(self,widget):
        hunspell_dict = DictPref().get_hunspell_dict(self.lang)
        InstallPkg(hunspell_dict)

    def onCheck(self,widget):
        try:
            if widget.get_active():
                SetupUi.config.set_value('key','Tab',GLib.Variant.new_boolean(True))
            else:
                SetupUi.config.set_value('key','Tab',GLib.Variant.new_boolean(False))
        except:
            #Future on error need to check local db
            pass

SetupUi = SetupUI()

if __name__ == '__main__':
    Gtk.main()

