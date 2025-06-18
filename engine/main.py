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
require_version('Gio', '2.0')
from gi.repository import Gio
require_version('GLib', '2.0')
from gi.repository import GLib
# pylint: enable=wrong-import-position

import itb_util
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
        # pylint: disable=possibly-used-before-assignment
        self.__factory = factory.EngineFactory(self.__bus)
        # pylint: enable=possibly-used-before-assignment
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
    if element is None:
        return
    if len(element):
        if not element.text or not element.text.strip():
            element.text = i + "    "
        last_subelement = None
        for subelement in element:
            last_subelement = subelement
            indent(subelement, level+1)
            if not subelement.tail or not subelement.tail.strip():
                subelement.tail = i + "    "
        if (last_subelement is not None
            and (not last_subelement.tail or not last_subelement.tail.strip())):
            last_subelement.tail = i
    else:
        if level and (not element.tail or not element.tail.strip()):
            element.tail = i

def write_xml() -> None:
    '''
    Writes the XML to describe the engine(s) to standard output.
    '''
    m17n_db_info = itb_util.M17nDbInfo()
    m17n_input_methods = set(m17n_db_info.get_imes())
    m17n_input_methods_skip = set([
        'NoIME',
    ])
    supported_input_methods = sorted(
        m17n_input_methods - m17n_input_methods_skip
    ) + ['typing-booster']

    indic_languages = (
        'as',
        'bn',
        'brx',
        'doi',
        'dra',
        'dv',
        'gu',
        'hi',
        'kn',
        'ks',
        'mai',
        'ml',
        'mni',
        'mr',
        'ne',
        'new',
        'or',
        'pa',
        'sa',
        'sat',
        'sd',
        'si',
        'ta',
        'te',
    )
    rank_patterns = [ # first matching regexp wins
        # Use higher ranks than ibus-m17n does for the same
        # input methods to have the “tb” input methods appear
        # with higher priority than the “m17n” input methods.
        #
        # Assign lower rank to Sinhala Samanala since it is a
	# non-keyboard input method in Sinhala.  (Not sure whether
	# this makes sense but ibus-m17n does it).
        (r'tb:si:samanala', 0),
        # Assign higher rank to all inscript2 engines since they
        # should be preferred over the inscript engines.
        # ibus-m17n uses rank 3 for these.
        (r'tb:[^:]+:.*inscript2.*', 4),
        # Assign higher rank to Indic engines which represent each
	# language. ibus-m17n uses rank 2 for these.
        (r'tb:te:inscript', 3),
        (r'tb:ta:tamil99', 3),
        (r'tb:si:wijesekara', 3),
        (r'tb:sd:inscript', 3),
        (r'tb:sa:harvard-kyoto', 3),
        (r'tb:pa:inscript', 3),
        (r'tb:or:inscript', 3),
        (r'tb:ne:rom', 3),
        (r'tb:mr:inscript', 3),
        (r'tb:ml:inscript', 3),
        (r'tb:mai:inscript', 3),
        (r'tb:ks:kbd', 3),
        (r'tb:kn:kgp', 3),
        (r'tb:hi:inscript', 3),
        (r'tb:gu:inscript', 3),
        (r'tb:bn:inscript', 3),
        (r'tb:as:inscript', 3),
        # Indic engines should be selected by default:
	# https://bugzilla.redhat.com/show_bug.cgi?id=640896
        # ibus-m17n uses rank 1 for these.
        (r'tb:(' + ('|').join(indic_languages) + r'):[^:]+', 2),
        # Arabic kbd engine should be selected by default:
        # https://bugzilla.redhat.com/show_bug.cgi?id=1076945
        # ibus-m17n uses rank 1 for the ar-kbd engine.
        (r'tb:ar:kbd', 2),
        (r'tb:ja:anthy', -1), # ja:anthy is superseded by ibus-anthy
        (r'tb:zh:py', -1), # zh:py is superseded by ibus-pinyin etc
        (r'tb:zh:py-gb', -1), # zh:py-gb is superseded by ibus-pinyin etc
        (r'tb:zh:py-b5', -1), # zh:py-b5 is superseded by ibus-pinyin etc
        (r'tb:ko:han2', -1), # ko:han2 is superseded by ibus-hangul
        (r'tb:ko:romaja', -1), # ko:romaja is superseded by ibus-hangul
    ]
    # Some Indic engines expect AltGr is automatically mapped
    ralt_switch_patterns = [
        r'tb:[^:]+:.*inscript.*',
        r'tb:si:.+',
    ]

    egs = Element('engines') # pylint: disable=possibly-used-before-assignment

    for ime in supported_input_methods:
        _engine = SubElement( # pylint: disable=possibly-used-before-assignment
            egs, 'engine')

        name = 'typing-booster'
        longname = 'Typing Booster'
        language = 't'
        engine_license = 'GPL'
        author = ('Mike FABIAN <mfabian@redhat.com>'
                  ', Anish Patil <anish.developer@gmail.com>')
        layout = 'default'
        # For something like “setxkbmap 'us(intl)'”, layout is “us”
        # and layout_variant is “intl”.
        layout_variant = ''
        layout_option = ''
        icon = os.path.join(ICON_DIR, 'ibus-typing-booster.svg')
        description = 'A completion input method to speedup typing.'
        symbol = '🚀'
        setup = SETUP_TOOL
        icon_prop_key = 'InputMode'
        rank = 0
        schema_path = '/org/freedesktop/ibus/engine/typing-booster/'
        if ime != 'typing-booster':
            m17n_lang, m17n_name = ime.split('-', maxsplit=1)
            name = f'tb:{m17n_lang}:{m17n_name}'
            schema_path = ('/org/freedesktop/ibus/engine/tb/'
                           f'{m17n_lang}/{m17n_name}/')
            rank = 0
            for pattern, pattern_rank in rank_patterns:
                if re.fullmatch(pattern, name):
                    rank = pattern_rank
                    break # first matching regexp wins
            layout = 'default'
            for pattern in ralt_switch_patterns:
                if re.fullmatch(pattern, name):
                    # I do this only to match the xml output of
                    # ibus-m17n, it does not seem to help though,
                    # i.e. it does not automatically make the right
                    # alt key work as ISO_Level3_Shift when switching
                    # from a keyboard layout like “English (US)” which
                    # does not haave this:
                    layout_option = 'lv3:ralt_switch'
                    break
            symbol = ''
            for pattern, pattern_symbol in itb_util.M17N_IME_SYMBOLS:
                if re.fullmatch(pattern, name):
                    symbol = pattern_symbol
                    break
            longname = f'{ime} (tb)'
            language = m17n_lang
            icon =  m17n_db_info.get_icon(ime)
            description = m17n_db_info.get_description(ime)
            setup = SETUP_TOOL + f' --engine-name {name}'
        gsettings = Gio.Settings(
            schema='org.freedesktop.ibus.engine.typing-booster',
            path=schema_path)
        user_symbol = itb_util.variant_to_value(
            gsettings.get_user_value('inputmodetruesymbol'))
        if user_symbol is not None:
            symbol = user_symbol

        _name = SubElement(_engine, 'name')
        _name.text = name
        _longname = SubElement(_engine, 'longname')
        _longname.text = longname
        _language = SubElement(_engine, 'language')
        _language.text = language
        _license = SubElement(_engine, 'license')
        _license.text = engine_license
        _author = SubElement(_engine, 'author')
        _author.text = author
        _icon = SubElement(_engine, 'icon')
        _icon.text = icon
        _layout = SubElement(_engine, 'layout')
        _layout.text = layout
        _layout_variant = SubElement(_engine, 'layout_variant')
        _layout_variant.text = layout_variant
        _layout_option = SubElement(_engine, 'layout_option')
        _layout_option.text = layout_option
        _desc = SubElement(_engine, 'description')
        _desc.text = description
        _symbol = SubElement(_engine, 'symbol')
        _symbol.text = symbol
        _setup = SubElement(_engine, 'setup')
        _setup.text = setup
        _icon_prop_key = SubElement(_engine, 'icon_prop_key')
        _icon_prop_key.text = icon_prop_key
        _rank = SubElement(_engine, 'rank')
        _rank.text = str(rank)

    # now format the xmlout pretty
    indent(egs)
    egsout = tostring( # pylint: disable=possibly-used-before-assignment
        egs, encoding='utf8', method='xml').decode('utf-8')
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
