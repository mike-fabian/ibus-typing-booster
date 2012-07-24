# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 2012-2013 Anish Patil <apatil@redhat.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# $Id: $
#


from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango
from pref import DictPref
from pkginstall import InstallPkg

class SetupUI:
    def __init__(self):
        filename = "setup.glade"
        self.builder = Gtk.Builder()
        self.builder.add_from_file(filename)
        event_handler = EventHander()
        self.builder.connect_signals(event_handler)
        maindialog = self.builder.get_object("dialog1")
        maindialog.show()
        choose_lang = self.builder.get_object("choose_lang")
        choose_lang.set_active(0)
        choose_lang.connect('changed', event_handler.changeSrcLang)
        install_button = self.builder.get_object("button1")
        install_button.connect('clicked', event_handler.onInstallClicked)
        close_button = self.builder.get_object("button2")
        close_button.connect('clicked', event_handler.onCloseClicked)


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

if __name__ == '__main__':
    Setup_Ui = SetupUI()
    Gtk.main()

