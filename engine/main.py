# vim:et sts=4 sw=4
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

import os
import sys
import optparse
from gi.repository import IBus
from gi.repository import GLib
import re
from signal import signal, SIGTERM, SIGINT

import factory
import tabsqlitedb

debug_level = int(0)
try:
    debug_level = int(os.getenv('IBUS_TYPING_BOOSTER_DEBUG_LEVEL'))
except (TypeError, ValueError):
    debug_level = int(0)

try:
    config_file_dir = os.path.join(
        os.getenv('IBUS_TYPING_BOOSTER_LOCATION'),
        'hunspell-tables')
    icon_dir = os.path.join(
        os.getenv('IBUS_TYPING_BOOSTER_LOCATION'),
        'icons')
except:
    config_file_dir = "/usr/share/ibus-typing-booster/hunspell-tables"
    icon_dir = "/usr/share/ibus-typing-booster/icons"


opt = optparse.OptionParser()

opt.set_usage ('%prog')
opt.add_option('--daemon', '-d',
        action = 'store_true',dest = 'daemon',default=False,
        help = 'Run as daemon, default: %default')
opt.add_option('--ibus', '-i',
        action = 'store_true',dest = 'ibus',default = False,
        help = 'Set the IME icon file, default: %default')
opt.add_option('--xml', '-x',
        action = 'store_true',dest = 'xml',default = False,
        help = 'output the engines xml part, default: %default')
opt.add_option('--no-debug', '-n',
        action = 'store_false',dest = 'debug',default = True,
        help = 'redirect stdout and stderr to '
               + '~/.local/share/ibus-typing-booster/debug.log, '
               + 'default: %default')
opt.add_option('--profile', '-p',
        action = 'store_true', dest = 'profile', default = False,
        help = 'print profiling information into the debug log. '
               + 'Works only together with --debug.')

(options, args) = opt.parse_args()

if (not options.xml) and options.debug:
    if not os.access(
            os.path.expanduser('~/.local/share/ibus-typing-booster'),
            os.F_OK):
        os.system('mkdir -p ~/.local/share/ibus-typing-booster')
    logfile = os.path.expanduser('~/.local/share/ibus-typing-booster/debug.log')
    sys.stdout = open(logfile, mode='a', buffering=1)
    sys.stderr = open(logfile, mode='a', buffering=1)
    from time import strftime
    print('--- %s ---' %strftime('%Y-%m-%d: %H:%M:%S'))

if options.profile:
    import cProfile, pstats
    profile = cProfile.Profile()

class IMApp:
    def __init__(self, dbfile, exec_by_ibus):
        if debug_level > 1:
            sys.stderr.write(
                "IMApp.__init__(dbfile=%s, exec_by_ibus=%s)\n"
                % (dbfile, exec_by_ibus))
        self.__mainloop = GLib.MainLoop()
        self.__bus = IBus.Bus()
        self.__bus.connect("disconnected", self.__bus_destroy_cb)
        self.__factory = factory.EngineFactory(self.__bus, dbfile)
        self.destroyed = False
        if exec_by_ibus:
            self.__bus.request_name("org.freedesktop.IBus.IbusTypingBooster", 0)
        else:
            self.__component = IBus.Component(
                name="org.freedesktop.IBus.IbusTypingBooster",
                description="Table Component",
                version="0.1.0",
                license="GPL",
                author="Anish Patil <apatill@redhat.com>",
                homepage="http://code.google.com/p/ibus/",
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
                icon = os.path.join (icon_dir, icon)
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
        if debug_level > 1:
            sys.stderr.write("IMApp.run()\n")
        if options.profile:
            profile.enable()
        self.__mainloop.run()
        self.__bus_destroy_cb()

    def quit(self):
        if debug_level > 1:
            sys.stderr.write("IMApp.quit()\n")
        self.__bus_destroy_cb()

    def __bus_destroy_cb(self, bus=None):
        if debug_level > 1:
            sys.stderr.write("IMApp.__bus_destroy_cb(bus=%s)\n" % bus)
        if self.destroyed:
            return
        print("finalizing:)")
        self.__factory.do_destroy()
        self.destroyed = True
        self.__mainloop.quit()
        if options.profile:
            profile.disable()
            p = pstats.Stats(profile)
            p.strip_dirs()
            p.sort_stats('cumulative')
            p.print_stats('tabsqlite', 25)
            p.print_stats('hunspell_suggest', 25)
            p.print_stats('hunspell_table', 25)

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
    if options.xml:
        from xml.etree.ElementTree import Element, SubElement, tostring
        # Find all config files in config_file_dir, extract the ime
        # properties and print the xml file for the engines
        confs = [x for x in os.listdir(config_file_dir) if x.endswith('.conf')]
        for conf in confs:
            str_dic = conf.replace('conf', 'dic')

        egs = Element('engines')

        for conf in confs:
            _ime_properties = tabsqlitedb.ImeProperties(
                os.path.join(config_file_dir,conf))
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
                _icon.text = os.path.join (icon_dir, _icon_basename)

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

    if options.daemon :
        if os.fork():
            sys.exit()

    ima = IMApp('', options.ibus)
    signal (SIGTERM, lambda signum, stack_frame: cleanup(ima))
    signal (SIGINT, lambda signum, stack_frame: cleanup(ima))
    try:
        ima.run()
    except KeyboardInterrupt:
        ima.quit()

if __name__ == "__main__":
    main()

