# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2011-2013 Anish Patil <apatil@redhat.com>
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

import os
import sys
import optparse
import time
from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus
from gi.repository import GLib
import re
from signal import signal, SIGTERM, SIGINT

import factory
import tabsqlitedb

DEBUG_LEVEL = int(0)
try:
    DEBUG_LEVEL = int(os.getenv('IBUS_TYPING_BOOSTER_DEBUG_LEVEL'))
except (TypeError, ValueError):
    DEBUG_LEVEL = int(0)

try:
    CONFIG_FILE_DIR = os.path.join(
        os.getenv('IBUS_TYPING_BOOSTER_LOCATION'),
        'hunspell-tables')
    ICON_DIR = os.path.join(
        os.getenv('IBUS_TYPING_BOOSTER_LOCATION'),
        'icons')
except:
    CONFIG_FILE_DIR = "/usr/share/ibus-typing-booster/hunspell-tables"
    ICON_DIR = "/usr/share/ibus-typing-booster/icons"


OPT = optparse.OptionParser()

OPT.set_usage ('%prog')
OPT.add_option('--daemon', '-d',
        action = 'store_true',dest = 'daemon',default=False,
        help = 'Run as daemon, default: %default')
OPT.add_option('--ibus', '-i',
        action = 'store_true',dest = 'ibus',default = False,
        help = 'Set the IME icon file, default: %default')
OPT.add_option('--xml', '-x',
        action = 'store_true',dest = 'xml',default = False,
        help = 'output the engines xml part, default: %default')
OPT.add_option('--no-debug', '-n',
        action = 'store_false',dest = 'debug',default = True,
        help = 'redirect stdout and stderr to '
               + '~/.local/share/ibus-typing-booster/debug.log, '
               + 'default: %default')
OPT.add_option('--profile', '-p',
        action = 'store_true', dest = 'profile', default = False,
        help = 'print profiling information into the debug log. '
               + 'Works only together with --debug.')

(OPTIONS, ARGS) = OPT.parse_args()

if (not OPTIONS.xml) and OPTIONS.debug:
    if not os.access(
            os.path.expanduser('~/.local/share/ibus-typing-booster'),
            os.F_OK):
        os.system('mkdir -p ~/.local/share/ibus-typing-booster')
    LOGFILE = os.path.expanduser(
        '~/.local/share/ibus-typing-booster/debug.log')
    sys.stdout = open(LOGFILE, mode='a', buffering=1)
    sys.stderr = open(LOGFILE, mode='a', buffering=1)
    print('--- Starting: %s ---' %time.strftime('%Y-%m-%d: %H:%M:%S'))

if OPTIONS.profile:
    import cProfile, pstats
    PROFILE = cProfile.Profile()

class IMApp:
    def __init__(self, exec_by_ibus):
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "IMApp.__init__(exec_by_ibus=%s)\n"
                % exec_by_ibus)
        self.__mainloop = GLib.MainLoop()
        self.__bus = IBus.Bus()
        self.__bus.connect("disconnected", self.__bus_destroy_cb)
        self.__factory = factory.EngineFactory(
            self.__bus,
            config_file_dir = CONFIG_FILE_DIR)
        self.destroyed = False
        if exec_by_ibus:
            self.__bus.request_name(
                "org.freedesktop.IBus.IbusTypingBooster", 0)
        else:
            self.__component = IBus.Component(
                name="org.freedesktop.IBus.IbusTypingBooster",
                description="Table Component",
                version="0.1.0",
                license="GPL",
                author="Anish Patil <apatill@redhat.com>",
                homepage="http://mike-fabian.github.io/ibus-typing-booster",
                textdomain="ibus-typing-booster")
            # now we get IME info from self.__factory.db
            name = self.__factory.db.ime_properties.get("name")
            longname = self.__factory.db.ime_properties.get("ime_name")
            description = self.__factory.db.ime_properties.get("description")
            language = self.__factory.db.ime_properties.get("language")
            credit = self.__factory.db.ime_properties.get("credit")
            author = self.__factory.db.ime_properties.get("author")
            icon = self.__factory.db.ime_properties.get("icon")
            if icon:
                icon = os.path.join (ICON_DIR, icon)
                if not os.access( icon, os.F_OK):
                    icon = ''
            layout = self.__factory.db.ime_properties.get("layout")
            symbol = self.__factory.db.ime_properties.get("symbol")

            engine = IBus.EngineDesc(name=name,
                                     longname=longname,
                                     description=description,
                                     language=language,
                                     license=credit,
                                     author=author,
                                     icon=icon,
                                     layout=layout,
                                     symbol=symbol)
            self.__component.add_engine(engine)
            self.__bus.register_component(self.__component)


    def run(self):
        if DEBUG_LEVEL > 1:
            sys.stderr.write("IMApp.run()\n")
        if OPTIONS.profile:
            PROFILE.enable()
        self.__mainloop.run()
        self.__bus_destroy_cb()

    def quit(self):
        if DEBUG_LEVEL > 1:
            sys.stderr.write("IMApp.quit()\n")
        self.__bus_destroy_cb()

    def __bus_destroy_cb(self, bus=None):
        if DEBUG_LEVEL > 1:
            sys.stderr.write("IMApp.__bus_destroy_cb(bus=%s)\n" % bus)
        if self.destroyed:
            return
        print("finalizing:)")
        self.__factory.do_destroy()
        self.destroyed = True
        self.__mainloop.quit()
        if OPTIONS.profile:
            PROFILE.disable()
            stats = pstats.Stats(PROFILE)
            stats.strip_dirs()
            stats.sort_stats('cumulative')
            stats.print_stats('tabsqlite', 25)
            stats.print_stats('hunspell_suggest', 25)
            stats.print_stats('hunspell_table', 25)
            stats.print_stats('itb_emoji', 25)

def cleanup (ima_ins):
    ima_ins.quit()
    sys.exit()

def indent(elem, level=0):
    '''Use to format xml Element pretty :)'''
    i = "\n" + level*"    "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "    "
        for e in elem:
            indent(e, level+1)
            if not e.tail or not e.tail.strip():
                e.tail = i + "    "
        if not e.tail or not e.tail.strip():
            e.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def main():
    if OPTIONS.xml:
        from xml.etree.ElementTree import Element, SubElement, tostring
        # Find all config files in CONFIG_FILE_DIR, extract the ime
        # properties and print the xml file for the engines
        confs = [x for x in os.listdir(CONFIG_FILE_DIR) if x.endswith('.conf')]

        egs = Element('engines')

        for conf in confs:
            _ime_properties = tabsqlitedb.ImeProperties(
                os.path.join(CONFIG_FILE_DIR,conf))
            _engine = SubElement (egs,'engine')

            _name = SubElement (_engine, 'name')
            _name.text = _ime_properties.get('name')

            _longname = SubElement (_engine, 'longname')
            _longname.text = ''
            try:
                _longname.text = _ime_properties.get('ime_name')
            except:
                pass
            if not _longname.text:
                _longname.text = _name.text

            _language = SubElement (_engine, 'language')
            _langs = _ime_properties.get ('language')
            if _langs:
                _langs = _langs.split (',')
                if len (_langs) == 1:
                    _language.text = _langs[0].strip()
                else:
                    # we ignore the place
                    _language.text = _langs[0].strip().split('_')[0]

            _license = SubElement (_engine, 'license')
            _license.text = _ime_properties.get ('license')

            _author = SubElement (_engine, 'author')
            _author.text  = _ime_properties.get ('author')

            _icon = SubElement (_engine, 'icon')
            _icon_basename = _ime_properties.get ('icon')
            if _icon_basename:
                _icon.text = os.path.join (ICON_DIR, _icon_basename)

            _layout = SubElement (_engine, 'layout')
            _layout.text = _ime_properties.get ('layout')

            _desc = SubElement (_engine, 'description')
            _desc.text = _ime_properties.get ('description')

            _symbol = SubElement(_engine,'symbol')
            _symbol.text = _ime_properties.get('symbol')

            _setup = SubElement(_engine,'setup')
            _setup.text = _ime_properties.get('setup')

        # now format the xmlout pretty
        indent (egs)
        egsout = tostring(egs, encoding='utf8', method='xml').decode('utf-8')
        patt = re.compile('<\?.*\?>\n')
        egsout = patt.sub('', egsout)
        sys.stdout.buffer.write((egsout+'\n').encode('utf-8'))
        return 0

    if OPTIONS.daemon :
        if os.fork():
            sys.exit()

    ima = IMApp(OPTIONS.ibus)
    signal (SIGTERM, lambda signum, stack_frame: cleanup(ima))
    signal (SIGINT, lambda signum, stack_frame: cleanup(ima))
    try:
        ima.run()
    except KeyboardInterrupt:
        ima.quit()

if __name__ == "__main__":
    main()

