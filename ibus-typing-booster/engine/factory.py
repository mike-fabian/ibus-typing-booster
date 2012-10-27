# -*- coding: utf-8 -*-
# vim:et sw=4 sts=4 sw=4
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 2011-2012 Anish Patil <apatil@redhat.com>
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


import ibus
from ibus.exception import *
import hunspell_table 
import tabsqlitedb
import os
import dbus
#import _config as config
from re import compile as re_compile

path_patt = re_compile(r'[^a-zA-Z0-9_/]')

from gettext import dgettext
_  = lambda a : dgettext ("ibus-typing-booster", a)
N_ = lambda a : a

engine_base_path = "/com/redhat/IBus/engines/table/%s/engine/"


class EngineFactory (ibus.EngineFactoryBase):
    """Table IM Engine Factory"""
    def __init__ (self, bus, db="", icon=""):
        if db:
            self.db = tabsqlitedb.tabsqlitedb(filename=db)
        else:
            self.db = None
        self.dbdict = {}
        self.enginedict = {}
        self.bus = bus
        #engine.Engine.CONFIG_RELOADED(bus)
        super(EngineFactory,self).__init__ (bus)
        self.engine_id=0
        try:
            bus = dbus.Bus()
            user = os.path.basename( os.path.expanduser('~') )
            self._sm_bus = bus.get_object ("org.ibus.table.SpeedMeter.%s"\
                    % user, "/org/ibus/table/SpeedMeter")
            self._sm =  dbus.Interface(self._sm_bus,\
                    "org.ibus.table.SpeedMeter") 
        except:
            self._sm = None

    def create_engine(self, engine_name):
        # because we need db to be past to Engine
        # the type (engine_name) == dbus.String
        name = engine_name.encode ('utf8')
        self.engine_path = engine_base_path % path_patt.sub ('_', name)
        try:
            db_dir = "/usr/share/ibus-typing-booster/hunspell-tables"
            if name in self.dbdict:
                self.db = self.dbdict[name]
            else:
                self.db = tabsqlitedb.tabsqlitedb(filename=name+'.conf')
                self.dbdict[name] = self.db
            if name in self.enginedict:
                engine = self.enginedict[name]
            else:
                engine = hunspell_table.tabengine(self.bus, self.engine_path \
                        + str(self.engine_id), self.db)
                self.enginedict[name] = engine
                self.engine_id += 1
            #return engine.get_dbus_object()
            return engine
        except:
            print "failed to create engine %s" % engine_name
            import traceback
            traceback.print_exc ()
            raise IBusException("Cannot create engine %s" % engine_name)

    def do_destroy (self):
        '''Destructor, which finish some task for IME'''
        # 
        ## we need to sync the temp userdb in memory to the user_db on disk
        for _db in self.dbdict:
            self.dbdict[_db].sync_usrdb ()
        ##print "Have synced user db\n"
        try:
            self._sm.Quit()
        except:
            pass
        super(EngineFactory,self).do_destroy()


