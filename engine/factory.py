# -*- coding: utf-8 -*-
# vim:et sw=4 sts=4 sw=4
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 2011-2013 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012-2013 Mike FABIAN <mfabian@redhat.com>
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


from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus
import hunspell_table
import tabsqlitedb
import re
import os
import sys

from gettext import dgettext
_  = lambda a : dgettext ("ibus-typing-booster", a)
N_ = lambda a : a

DEBUG_LEVEL = int(0)

class EngineFactory (IBus.Factory):
    """Table IM Engine Factory"""
    def __init__(self, bus, db="", icon=""):
        global DEBUG_LEVEL
        try:
            DEBUG_LEVEL = int(os.getenv('IBUS_TYPING_BOOSTER_DEBUG_LEVEL'))
        except (TypeError, ValueError):
            DEBUG_LEVEL = int(0)
        if DEBUG_LEVEL > 1:
            sys.stderr.write("EngineFactory.__init__(bus=%s, db=%s, icon=%s)\n"
                             % (bus, db, icon))
        if db:
            self.db = tabsqlitedb.tabsqlitedb(config_filename=db)
        else:
            self.db = None
        self.dbdict = {}
        self.enginedict = {}
        self.bus = bus
        #engine.Engine.CONFIG_RELOADED(bus)
        super(EngineFactory, self).__init__(
            connection=bus.get_connection(), object_path=IBus.PATH_FACTORY)
        self.engine_id = 0

    def do_create_engine(self, engine_name):
        if DEBUG_LEVEL > 1:
            sys.stderr.write("EngineFactory.do_create_engine(engine_name=%s)\n"
                             % engine_name)
        engine_base_path = "/com/redhat/IBus/engines/table/%s/engine/"
        path_patt = re.compile(r'[^a-zA-Z0-9_/]')
        engine_path = engine_base_path % path_patt.sub ('_', engine_name)
        try:
            if engine_name in self.dbdict:
                self.db = self.dbdict[engine_name]
            else:
                self.db = tabsqlitedb.tabsqlitedb(
                    config_filename=engine_name+'.conf')
                self.dbdict[engine_name] = self.db
            if engine_name in self.enginedict:
                engine = self.enginedict[engine_name]
            else:
                engine = hunspell_table.tabengine(
                    self.bus, engine_path + str(self.engine_id), self.db)
                self.enginedict[engine_name] = engine
                self.engine_id += 1
            return engine
        except:
            print("failed to create engine %s" %engine_name)
            import traceback
            traceback.print_exc ()
            raise Exception("Cannot create engine %s" % engine_name)

    def do_destroy (self):
        '''Destructor, which finish some task for IME'''
        if DEBUG_LEVEL > 1:
            sys.stderr.write("EngineFactory.do_destroy()\n")
        for _db in self.dbdict:
            self.dbdict[_db].sync_usrdb()
        super(EngineFactory, self).destroy()


