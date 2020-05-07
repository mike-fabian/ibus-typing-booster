#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2020 Takao Fujiwara <takao.fujiwara1@gmail.com>
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
This file implements the test cases using GTK GUI
'''
# “Wrong continued indentation”: pylint: disable=bad-continuation
# pylint: disable=attribute-defined-outside-init
# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=global-statement
# pylint: disable=wrong-import-order
# pylint: disable=wrong-import-position

import argparse
import os
import signal
import sys
import unittest

from gi import require_version as gi_require_version
gi_require_version('GLib', '2.0')
gi_require_version('Gdk', '3.0')
gi_require_version('Gio', '2.0')
gi_require_version('Gtk', '3.0')
gi_require_version('IBus', '1.0')
from gi.repository import GLib
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import Gtk
from gi.repository import IBus

# Get more verbose output in the test log:
os.environ['IBUS_TYPING_BOOSTER_DEBUG_LEVEL'] = '255'

sys.path.insert(0, "../engine")
IMPORT_HUNSPELL_SUCCESSFUL = False
try:
    import hunspell_table
    IMPORT_HUNSPELL_SUCCESSFUL = True
except (ImportError,):
    pass
IMPORT_TABSQLITEDB_SUCCESSFUL = False
try:
    import tabsqlitedb
    IMPORT_TABSQLITEDB_SUCCESSFUL = True
except (ImportError,):
    pass
sys.path.pop(0)

DONE_EXIT = True

from gtkcases import TestCases

# Need to flush the output against Gtk.main()
def printflush(sentence):
    try:
        print(sentence, flush=True)
    except IOError:
        pass

def printerr(sentence):
    try:
        print(sentence, flush=True, file=sys.stderr)
    except IOError:
        pass

@unittest.skipIf(Gdk.Display.open('') is None, 'Display cannot be opened.')
class SimpleGtkTestCase(unittest.TestCase):
    global DONE_EXIT
    ENGINE_PATH = '/com/redhat/IBus/engines/typing_booster/Test/Engine'

    @classmethod
    def setUpClass(cls):
        cls._flag = False
        IBus.init()
        cls._gsettings = Gio.Settings(
            schema='org.freedesktop.ibus.engine.typing-booster')
        cls._orig_dictionary = cls._gsettings.get_string('dictionary')
        signums = [getattr(signal, s, None) for s in
                   'SIGINT SIGTERM SIGHUP'.split()]
        for signum in filter(None, signums):
            original_handler = signal.getsignal(signum)
            GLib.unix_signal_add(GLib.PRIORITY_HIGH,
                                 signum,
                                 cls.signal_handler,
                                 (signum, original_handler))
    @classmethod
    def tearDownClass(cls):
        cls._gsettings.set_string('dictionary', cls._orig_dictionary)

    @classmethod
    def signal_handler(cls, user_data):
        (signum, original_handler) = user_data
        cls.tearDownClass()
        Gtk.main_quit()
        signal.signal(signum, original_handler)
        cls._flag = True
        assert False, 'signal received: ' + str(signum)

    def setUp(self):
        self.__id = 0
        self.__rerun = False
        self.__test_index = 0
        self.__preedit_index = 0
        self.__lookup_index = 0
        self.__inserted_text = ''
        self.__commit_done = False
        self.__reset_coming = False
        self._gsettings.set_string('dictionary', 'fr_FR,en_US')

    def register_ibus_engine(self):
        self.__bus = IBus.Bus()
        if not self.__bus.is_connected():
            self.fail('ibus-daemon is not running')
            return False
        self.__bus.get_connection().signal_subscribe(
            'org.freedesktop.DBus',
            'org.freedesktop.DBus',
            'NameOwnerChanged',
            '/org/freedesktop/DBus',
            None,
            0,
            self.__bus_signal_cb,
            self.__bus)
        self.__factory = IBus.Factory(
            object_path=IBus.PATH_FACTORY,
            connection=self.__bus.get_connection())
        self.__factory.connect('create-engine', self.__create_engine_cb)
        self.__component = IBus.Component(
            name='org.freedesktop.IBus.TypingBooster.Test',
            description='Test Typing Booster Component',
            version='1.0',
            license='GPL',
            author=('Mike FABIAN <mfabian@redonat.com>, '
                    + 'Anish Patil <anish.developer@gmail.com>'),
            homepage='http://mike-fabian.github.io/ibus-typing-booster',
            command_line='',
            textdomain='ibus-typing-booster')
        desc = IBus.EngineDesc(
            name='testTyping-booster',
            longname='Test Typing Booster',
            description='Test a completion input method to speedup typing.',
            language='t',
            license='GPL',
            author=('Mike FABIAN <mfabian@redonat.com>, '
                    + 'Anish Patil <anish.developer@gmail.com>'),
            icon='',
            symbol='T')
        self.__component.add_engine(desc)
        self.__bus.register_component(self.__component)
        self.__bus.request_name('org.freedesktop.IBus.TypingBooster.Test', 0)
        return True

    def __bus_signal_cb(self, connection, sender_name, object_path,
                        interface_name, signal_name, parameters,
                        user_data):
        if signal_name == 'NameOwnerChanged':
            pass
        if signal_name == 'UpdateLookupTable':
            table = self.__engine.get_lookup_table()
            if table.get_number_of_candidates() == 0:
                return
            self.__lookup_test()

    def __create_engine_cb(self, factory, engine_name):
        if engine_name != 'testTyping-booster':
            return None
        if (not IMPORT_HUNSPELL_SUCCESSFUL
            or not IMPORT_TABSQLITEDB_SUCCESSFUL):
            with self.subTest(i='create-engine'):
                self.fail('NG: ibus-typing-booster not installed?')
            Gtk.main_quit()
            return None
        self.__id += 1
        object_path = '%s/%d' % (self.ENGINE_PATH, self.__id)
        database = tabsqlitedb.TabSqliteDb(user_db_file=':memory:')
        self.__engine = hunspell_table.TypingBoosterEngine(
            self.__bus,
            object_path,
            database)
        self.__engine.connect('focus-in', self.__engine_focus_in)
        self.__engine.connect('focus-out', self.__engine_focus_out)
        # Need to connect 'reset' after TypingBoosterEngine._clear_input()
        # is called.
        self.__engine.connect_after('reset', self.__engine_reset)
        self.__bus.get_connection().signal_subscribe(
            None,
            IBus.INTERFACE_ENGINE,
            'UpdateLookupTable',
            object_path,
            None,
            0,
            self.__bus_signal_cb,
            self.__bus)
        return self.__engine

    def __engine_focus_in(self, _engine):
        if self.__test_index == len(TestCases['tests']):
            if DONE_EXIT:
                Gtk.main_quit()
            return
        # Workaround because focus-out resets the preedit text
        # ibus_bus_set_global_engine() calls bus_input_context_set_engine()
        # twice and it causes bus_engine_proxy_focus_out()
        if self.__rerun:
            self.__rerun = False
            self.__main_test()

    def __engine_focus_out(self, _engine):
        self.__rerun = True
        self.__test_index = 0
        self.__entry.set_text('')

    def __engine_reset(self, _engine):
        if self.__reset_coming:
            self.__reset_coming = False
            self.__main_test()

    def __entry_focus_in_event_cb(self, entry, event):
        if self.__test_index == len(TestCases['tests']):
            if DONE_EXIT:
                Gtk.main_quit()
            return False
        self.__bus.set_global_engine_async('testTyping-booster',
                                           -1, None, self.__set_engine_cb)
        return False

    def __set_engine_cb(self, _object, res):
        with self.subTest(i=self.__test_index):
            if not self.__bus.set_global_engine_async_finish(res):
                self.fail('set engine failed.')
            return
        # rerun always happen?
        #self.__main_test()

    def __get_test_condition_length(self, tag):
        tests = TestCases['tests'][self.__test_index]
        try:
            cases = tests[tag]
        except KeyError:
            return -1
        case_type = list(cases.keys())[0]
        return len(cases[case_type])

    def __entry_preedit_changed_cb(self, entry, preedit_str):
        if len(preedit_str) == 0:
            return
        if self.__test_index == len(TestCases['tests']):
            if DONE_EXIT:
                Gtk.main_quit()
            return
        self.__preedit_index += 1
        if self.__preedit_index != self.__get_test_condition_length('preedit'):
            return
        if self.__get_test_condition_length('lookup') > 0:
            return
        self.__run_cases('commit')

    def __main_test(self):
        self.__preedit_index = 0
        self.__lookup_index = 0
        self.__commit_done = False
        self.__run_cases('preedit')

    def __lookup_test(self):
        lookup_length = self.__get_test_condition_length('lookup')
        # Need to return again even if all the lookup is finished
        # until the final Engine.update_preedit() is called.
        if self.__lookup_index > lookup_length:
            return
        self.__run_cases('lookup',
                         self.__lookup_index,
                         self.__lookup_index + 1)
        if self.__lookup_index < lookup_length:
            self.__lookup_index += 1
            return
        self.__lookup_index += 1
        self.__run_cases('commit')

    def __run_cases(self, tag, start=-1, end=-1):
        tests = TestCases['tests'][self.__test_index]
        if tests is None:
            return
        try:
            cases = tests[tag]
        except KeyError:
            return
        case_type = list(cases.keys())[0]
        i = 0
        if case_type == 'string':
            printflush('test step: %s sequences: "%s"'
                       % (tag, str(cases['string'])))
            for character in cases['string']:
                if start >= 0 and i < start:
                    i += 1
                    continue
                if 0 <= end <= i:
                    break
                self.__typing(ord(character), 0, 0)
                i += 1
        if case_type == 'keys':
            if start == -1 and end == -1:
                printflush('test step: %s sequences: %s'
                           % (tag, str(cases['keys'])))
            for key in cases['keys']:
                if start >= 0 and i < start:
                    i += 1
                    continue
                if 0 <= end <= i:
                    break
                if start != -1 or end != -1:
                    printflush('test step: %s sequences: [0x%X, 0x%X, 0x%X]'
                               % (tag, key[0], key[1], key[2]))
                self.__typing(key[0], key[1], key[2])
                i += 1

    def __typing(self, keyval, keycode, modifiers):
        self.__engine.emit('process-key-event', keyval, keycode, modifiers)
        modifiers |= IBus.ModifierType.RELEASE_MASK
        self.__engine.emit('process-key-event', keyval, keycode, modifiers)

    def __buffer_inserted_text_cb(self, buffer, position, chars, nchars):
        tests = TestCases['tests'][self.__test_index]
        cases = tests['commit']
        case_type = list(cases.keys())[0]
        if case_type == 'keys':
            # space key is sent separatedly later
            if cases['keys'][0] == [IBus.KEY_space, 0, 0]:
                self.__inserted_text += chars
                if chars != ' ':
                    return
            # Return key emits 'reset' signal in GTK and it calls
            # TypingBoosterEngine._clear_input().
            elif cases['keys'][0] == [IBus.KEY_Return, 0, 0] or \
                 cases['keys'][0] == [IBus.KEY_KP_Enter, 0, 0] or \
                 cases['keys'][0] == [IBus.KEY_ISO_Enter, 0, 0] or \
                 cases['keys'][0] == [IBus.KEY_Escape, 0, 0]:
                self.__inserted_text = chars
                self.__reset_coming = True
        else:
            self.__inserted_text = chars
        cases = tests['result']
        if cases['string'] == self.__inserted_text:
            printflush('OK: %d "%s"'
                       % (self.__test_index, self.__inserted_text))
        else:
            if DONE_EXIT:
                Gtk.main_quit()
            with self.subTest(i=self.__test_index):
                self.fail('NG: %d "%s" "%s"'
                          % (self.__test_index, str(cases['string']),
                             self.__inserted_text))
        self.__inserted_text = ''
        self.__test_index += 1
        if self.__test_index == len(TestCases['tests']):
            if DONE_EXIT:
                Gtk.main_quit()
            return
        self.__commit_done = True
        self.__entry.set_text('')
        if not self.__reset_coming:
            self.__main_test()

    def create_window(self):
        window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.__entry = entry = Gtk.Entry()
        window.connect('destroy', Gtk.main_quit)
        entry.connect('focus-in-event', self.__entry_focus_in_event_cb)
        entry.connect('preedit-changed', self.__entry_preedit_changed_cb)
        buffer = entry.get_buffer()
        buffer.connect('inserted-text', self.__buffer_inserted_text_cb)
        window.add(entry)
        window.show_all()

    def main(self): # pylint: disable=no-self-use
        # Some ATK relative warnings are called during launching GtkWindow.
        flags = GLib.log_set_always_fatal(GLib.LogLevelFlags.LEVEL_CRITICAL)
        Gtk.main()
        GLib.log_set_always_fatal(flags)

    def test_typing(self):
        if not self.register_ibus_engine():
            sys.exit(-1)
        self.create_window()
        self.main()
        if self._flag:
            self.fail('NG: signal failure')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-k', '--keep', action='store_true',
                        help='keep this GtkWindow after test is done')
    parser.add_argument('-F', '--unittest-failfast', action='store_true',
                        help='stop on first fail or error in unittest')
    parser.add_argument('-H', '--unittest-help', action='store_true',
                        help='show unittest help message and exit')
    args, unittest_args = parser.parse_known_args()
    sys.argv[1:] = unittest_args
    if args.keep:
        global DONE_EXIT
        DONE_EXIT = False
    if args.unittest_failfast:
        sys.argv.append('-f')
    if args.unittest_help:
        sys.argv.append('-h')
        unittest.main()

    unittest.main()

if __name__ == '__main__':
    main()
