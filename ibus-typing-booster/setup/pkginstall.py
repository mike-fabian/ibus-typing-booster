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

import gi
from gi.repository import Gio, GLib

class InstallPkg(object):
    def __init__(self,pkg):
        bus_type = Gio.BusType.SESSION
        flags = 0
        iface_info = None
        # Creating proxies does not do any blocking I/O, and never fails
        proxy = Gio.DBusProxy.new_for_bus_sync(
            bus_type,
            flags,
            iface_info,
            'org.freedesktop.PackageKit',
            '/org/freedesktop/PackageKit',
            'org.freedesktop.PackageKit.Modify',
            None)
        try:
            # The default timeout is approximately 25 seconds.
            # This is too short here, the call to InstallPackageNames
            # would usually return too early then before the package
            # has completed installing. Then the callback to reload
            # the dictionary would be called to early and would not
            # be able to load the dictionary.
            # So I use a very long timeout here to make sure
            # InstallPackageNames does not return before either the
            # dictionary is really installed or the user cancels:
            proxy.set_default_timeout(0x7fffffff) # timeout in milliseconds
            proxy.InstallPackageNames("(uass)", 0, [pkg], "show-confirm-search,hide-finished")
        except GLib.GError as e:
            print("GError: " + str(e))

