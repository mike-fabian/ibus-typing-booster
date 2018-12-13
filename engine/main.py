# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2011-2013 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012-2018 Mike FABIAN <mfabian@redhat.com>
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
import argparse
import time
import re
from signal import signal, SIGTERM, SIGINT
from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus
from gi.repository import GLib

import factory
import tabsqlitedb
import version

DEBUG_LEVEL = int(0)
try:
    DEBUG_LEVEL = int(os.getenv('IBUS_TYPING_BOOSTER_DEBUG_LEVEL'))
except (TypeError, ValueError):
    DEBUG_LEVEL = int(0)

try:
    ICON_DIR = os.path.join(
        os.getenv('IBUS_TYPING_BOOSTER_LOCATION'),
        'icons')
except:
    ICON_DIR = os.path.join(
        version.get_prefix(), 'share/ibus-typing-booster/icons')

try:
    SETUP_TOOL = os.path.join(
        os.getenv('IBUS_TYPING_BOOSTER_LIB_LOCATION'),
        'ibus-setup-typing-booster')
except:
    SETUP_TOOL = os.path.join(
        version.get_prefix(),
        'libexec/ibus-setup-typing-booster')

def parse_args():
    '''Parse the command line arguments'''
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--daemon', '-d',
        action='store_true',
        dest='daemon',
        default=False,
        help='Run as daemon, default: %(default)s')
    parser.add_argument(
        '--ibus', '-i',
        action='store_true',
        dest='ibus',
        default=False,
        help='Set the IME icon file, default: %(default)s')
    parser.add_argument(
        '--xml', '-x',
        action='store_true',
        dest='xml',
        default=False,
        help='output the engines xml part, default: %(default)s')
    parser.add_argument(
        '--no-debug', '-n',
        action='store_true',
        dest='no_debug',
        default=False,
        help='Do not redirect stdout and stderr to '
        + '~/.local/share/ibus-typing-booster/debug.log, '
        + 'default: %(default)s')
    parser.add_argument(
        '--profile', '-p',
        action='store_true',
        dest='profile',
        default=False,
        help='print profiling information into the debug log. '
        + 'Works only when --no-debug is not used.')
    return parser.parse_args()

_ARGS = parse_args()

if _ARGS.profile:
    import cProfile
    import pstats
    _PROFILE = cProfile.Profile()

class IMApp:
    def __init__(self, exec_by_ibus):
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "IMApp.__init__(exec_by_ibus=%s)\n"
                % exec_by_ibus)
        self.__mainloop = GLib.MainLoop()
        self.__bus = IBus.Bus()
        self.__bus.connect("disconnected", self.__bus_destroy_cb)
        self.__factory = factory.EngineFactory(self.__bus)
        self.destroyed = False
        if exec_by_ibus:
            self.__bus.request_name(
                "org.freedesktop.IBus.IbusTypingBooster", 0)
        else:
            self.__component = IBus.Component(
                name="org.freedesktop.IBus.IbusTypingBooster",
                description="Typing Booster Component",
                version=version.get_version(),
                license="GPL",
                author=("Mike FABIAN <mfabian@redhat.com>, "
                        + "Anish Patil <anish.developer@gmail.com>"),
                homepage="http://mike-fabian.github.io/ibus-typing-booster",
                textdomain="ibus-typing-booster")
            # now we get IME info from self.__factory.db
            name = 'typing-booster'
            longname = 'Typing Booster'
            description = 'A completion input method to speedup typing.'
            language = 't'
            author = (
                'Mike FABIAN <mfabian@redhat.com>'
                + ', Anish Patil <anish.developer@gmail.com>')
            icon = os.path.join(ICON_DIR, 'ibus-typing-booster.svg')
            if not os.access(icon, os.F_OK):
                icon = ''
            layout = 'default'
            symbol = '🚀'

            engine = IBus.EngineDesc(name=name,
                                     longname=longname,
                                     description=description,
                                     language=language,
                                     license='GPL',
                                     author=author,
                                     icon=icon,
                                     layout=layout,
                                     symbol=symbol)
            self.__component.add_engine(engine)
            self.__bus.register_component(self.__component)

    def run(self):
        if DEBUG_LEVEL > 1:
            sys.stderr.write("IMApp.run()\n")
        if _ARGS.profile:
            _PROFILE.enable()
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
        if _ARGS.profile:
            _PROFILE.disable()
            stats = pstats.Stats(_PROFILE)
            stats.strip_dirs()
            stats.sort_stats('cumulative')
            stats.print_stats('tabsqlite', 25)
            stats.print_stats('hunspell_suggest', 25)
            stats.print_stats('hunspell_table', 25)
            stats.print_stats('itb_emoji', 25)

def cleanup(ima_ins):
    ima_ins.quit()
    sys.exit()

def indent(element, level=0):
    '''Use to format xml Element pretty :)'''
    i = "\n" + level*"    "
    if len(element):
        if not element.text or not element.text.strip():
            element.text = i + "    "
        for subelement in element:
            indent(subelement, level+1)
            if not subelement.tail or not subelement.tail.strip():
                subelement.tail = i + "    "
        if not subelement.tail or not subelement.tail.strip():
            subelement.tail = i
    else:
        if level and (not element.tail or not element.tail.strip()):
            element.tail = i

def main():
    '''Main program'''
    if not _ARGS.xml and not _ARGS.no_debug:
        if not os.access(
                os.path.expanduser('~/.local/share/ibus-typing-booster'),
                os.F_OK):
            os.system('mkdir -p ~/.local/share/ibus-typing-booster')
        logfile = os.path.expanduser(
            '~/.local/share/ibus-typing-booster/debug.log')
        sys.stdout = open(logfile, mode='a', buffering=1)
        sys.stderr = open(logfile, mode='a', buffering=1)
        print('--- Starting: %s ---' %time.strftime('%Y-%m-%d: %H:%M:%S'))

    if _ARGS.xml:
        from xml.etree.ElementTree import Element, SubElement, tostring

        egs = Element('engines')

        for language in ('t',):
            _engine = SubElement(egs, 'engine')

            _name = SubElement(_engine, 'name')
            _name.text = 'typing-booster'

            _longname = SubElement(_engine, 'longname')
            _longname.text = 'Typing Booster'

            _language = SubElement(_engine, 'language')
            _language.text = language

            _license = SubElement(_engine, 'license')
            _license.text = 'GPL'

            _author = SubElement(_engine, 'author')
            _author.text = (
                'Mike FABIAN <mfabian@redhat.com>'
                + ', Anish Patil <anish.developer@gmail.com>')

            _icon = SubElement(_engine, 'icon')
            _icon.text = os.path.join(ICON_DIR, 'ibus-typing-booster.svg')

            _layout = SubElement(_engine, 'layout')
            _layout.text = 'default'

            _desc = SubElement(_engine, 'description')
            _desc.text = 'A completion input method to speedup typing.'

            _symbol = SubElement(_engine, 'symbol')
            _symbol.text = '🚀'

            _setup = SubElement(_engine, 'setup')
            _setup.text = SETUP_TOOL

        # now format the xmlout pretty
        indent(egs)
        egsout = tostring(egs, encoding='utf8', method='xml').decode('utf-8')
        patt = re.compile('<\?.*\?>\n')
        egsout = patt.sub('', egsout)
        sys.stdout.buffer.write((egsout+'\n').encode('utf-8'))
        return 0

    if _ARGS.daemon:
        if os.fork():
            sys.exit()

    ima = IMApp(_ARGS.ibus)
    signal(SIGTERM, lambda signum, stack_frame: cleanup(ima))
    signal(SIGINT, lambda signum, stack_frame: cleanup(ima))
    try:
        ima.run()
    except KeyboardInterrupt:
        ima.quit()

if __name__ == "__main__":
    main()
