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
import dbus


class InstallPkg:
    def __init__(self,pkg):
        try:
            bus = dbus.SessionBus()
            proxy = bus.get_object('org.freedesktop.PackageKit', '/org/freedesktop/PackageKit')
            iface = dbus.Interface(proxy, 'org.freedesktop.PackageKit.Modify')
            iface.InstallPackageNames(dbus.UInt32(0), [pkg], "show-confirm-search,hide-finished")
        except dbus.DBusException, e:
            print 'Unable to connect to dbus: %s' % str(e)


