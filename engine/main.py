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
'''
Main program of ibus-typing-booster
'''
from typing import Any
from typing import Union
import os
import sys
import argparse
import re
import logging
import logging.handlers
from signal import signal, SIGTERM, SIGINT
# pylint: disable=wrong-import-position
from gi import require_version # type: ignore
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore
require_version('GLib', '2.0')
from gi.repository import GLib
# pylint: enable=wrong-import-position

import itb_version

LOGGER = logging.getLogger('ibus-typing-booster')

DEBUG_LEVEL = int(0)
try:
    DEBUG_LEVEL = int(str(os.getenv('IBUS_TYPING_BOOSTER_DEBUG_LEVEL')))
except (TypeError, ValueError):
    DEBUG_LEVEL = int(0)

if os.getenv('IBUS_TYPING_BOOSTER_LOCATION'):
    ICON_DIR = os.path.join(
        str(os.getenv('IBUS_TYPING_BOOSTER_LOCATION')),
        'icons')
else:
    ICON_DIR = os.path.join(
        itb_version.get_prefix(), 'share/ibus-typing-booster/icons')

if os.getenv('IBUS_TYPING_BOOSTER_LIB_LOCATION'):
    SETUP_TOOL = os.path.join(
        str(os.getenv('IBUS_TYPING_BOOSTER_LIB_LOCATION')),
        'ibus-setup-typing-booster')
else:
    SETUP_TOOL = os.path.join(
        itb_version.get_prefix(),
        'libexec/ibus-setup-typing-booster')

def parse_args() -> Any:
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
        help='Do not write log file '
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
    import io
    _PROFILE = cProfile.Profile()

if _ARGS.xml:
    from xml.etree.ElementTree import Element, SubElement, tostring
else:
    # Avoid importing factory when the --xml option is used because
    # factory imports other stuff which imports Gtk and that needs a
    # display.
    #
    # But by moving the import of factory here, it is possible to
    # use the --xml option in an environment where there is no
    # display without getting an error message like this:
    #
    #    $ env -u DISPLAY python3 main.py --xml
    #    Unable to init server: Could not connect: Connection refused
    #
    # The --xml option is used by “ibus write-cache” which is used
    # during rpm updates and then there is often no display and
    # the above error message appears.
    #
    # See: https://bugzilla.redhat.com/show_bug.cgi?id=1711646
    import factory

class IMApp:
    '''Input method application class'''
    def __init__(self, exec_by_ibus: bool) -> None:
        if DEBUG_LEVEL > 1:
            LOGGER.debug('IMApp.__init__(exec_by_ibus=%s)\n', exec_by_ibus)
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
                version=itb_version.get_version(),
                license="GPL",
                author=("Mike FABIAN <mfabian@redhat.com>, "
                        + "Anish Patil <anish.developer@gmail.com>"),
                homepage="http://mike-fabian.github.io/ibus-typing-booster",
                textdomain="ibus-typing-booster")
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

    def run(self) -> None:
        '''Run the input method application'''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('IMApp.run()\n')
        if _ARGS.profile:
            _PROFILE.enable()
        self.__mainloop.run()
        self.__bus_destroy_cb()

    def quit(self) -> None:
        '''Quit the input method application'''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('IMApp.quit()\n')
        self.__bus_destroy_cb()

    def __bus_destroy_cb(self, bus: Any = None) -> None:
        if DEBUG_LEVEL > 1:
            LOGGER.debug('IMApp.__bus_destroy_cb(bus=%s)\n', bus)
        if self.destroyed:
            return
        LOGGER.info('finalizing:)')
        self.__factory.do_destroy()
        self.destroyed = True
        self.__mainloop.quit()
        if _ARGS.profile:
            _PROFILE.disable()
            stats_stream = io.StringIO()
            stats = pstats.Stats(_PROFILE, stream=stats_stream)
            stats.strip_dirs()
            stats.sort_stats('cumulative')
            stats.print_stats('tabsqlite', 25)
            stats.print_stats('hunspell_suggest', 25)
            stats.print_stats('hunspell_table', 25)
            stats.print_stats('itb_util', 25)
            stats.print_stats('itb_emoji', 25)
            LOGGER.info('Profiling info:\n%s', stats_stream.getvalue())

def cleanup(ima_ins: IMApp) -> None:
    '''
    Clean up when the input method application was killed by a signal
    '''
    ima_ins.quit()
    sys.exit()

def indent(element: Any, level: int = 0) -> None:
    '''Use to format xml Element pretty :)'''
    i = "\n" + level*"    "
    if element:
        if not element.text or not element.text.strip():
            element.text = i + "    "
        last_subelement = None
        for subelement in element:
            last_subelement = subelement
            indent(subelement, level+1)
            if not subelement.tail or not subelement.tail.strip():
                subelement.tail = i + "    "
        if (last_subelement
            and (not last_subelement.tail or not last_subelement.tail.strip())):
            last_subelement.tail = i
    else:
        if level and (not element.tail or not element.tail.strip()):
            element.tail = i

def write_xml() -> None:
    '''
    Writes the XML to describe the engine(s) to standard output.
    '''
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

        _icon_prop_key = SubElement(_engine, 'icon_prop_key')
        _icon_prop_key.text = 'InputMode'

    # now format the xmlout pretty
    indent(egs)
    egsout = tostring(egs, encoding='utf8', method='xml').decode('utf-8')
    patt = re.compile(r'<\?.*\?>\n')
    egsout = patt.sub('', egsout)
    sys.stdout.buffer.write((egsout+'\n').encode('utf-8'))

def main() -> None:
    '''Main program'''
    if _ARGS.xml:
        write_xml()
        return

    log_handler: Union[
        logging.NullHandler, logging.handlers.TimedRotatingFileHandler] = (
            logging.NullHandler())
    if not _ARGS.no_debug:
        if not os.access(
                os.path.expanduser('~/.local/share/ibus-typing-booster'),
                os.F_OK):
            os.system('mkdir -p ~/.local/share/ibus-typing-booster')
        logfile = os.path.expanduser(
            '~/.local/share/ibus-typing-booster/debug.log')
        log_handler = logging.handlers.TimedRotatingFileHandler(
            logfile,
            when='midnight',
            interval=1,
            backupCount=7,
            encoding='UTF-8',
            delay=False,
            utc=False,
            atTime=None)
    log_formatter = logging.Formatter(
        '%(asctime)s %(filename)s '
        'line %(lineno)d %(funcName)s %(levelname)s: '
        '%(message)s')
    log_handler.setFormatter(log_formatter)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(log_handler)
    LOGGER.info('********** STARTING **********')

    IBus.init()
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
    return

if __name__ == "__main__":
    main()
