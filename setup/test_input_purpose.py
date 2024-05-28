# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2020 Mike FABIAN <mfabian@redhat.com>
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
A test program to test input purpose and hints
'''

from typing import Dict
from typing import Any
import sys
import signal
import logging
import logging.handlers

# pylint: disable=wrong-import-position
from gi import require_version # type: ignore
require_version('Gtk', '3.0')
from gi.repository import Gtk # type: ignore
# pylint: enable=wrong-import-position

# pylint: disable=import-error
sys.path = [sys.path[0]+'/../engine'] + sys.path
import itb_util
# pylint: enable=import-error

LOGGER = logging.getLogger('ibus-typing-booster')

class InputPurposeTest(Gtk.Window): # type: ignore
    '''
    User interface of the setup tool
    '''
    def __init__(self) -> None:
        Gtk.Window.__init__(self, title='Input Purpose Test')
        self.set_name('InputPurposeTest')
        self.set_modal(False)
        self.set_title('Input Purpose Test')
        self.connect('destroy-event', self.on_destroy_event)
        self.connect('delete-event', self.on_delete_event)

        self._main_container = Gtk.Box()
        self._main_container.set_orientation(Gtk.Orientation.VERTICAL)
        self._main_container.set_spacing(0)
        self.add(self._main_container) # pylint: disable=no-member

        margin = 5

        self._input_purpose = itb_util.InputPurpose.FREE_FORM
        self._input_purpose_combobox = Gtk.ComboBox()
        self._input_purpose_combobox.set_margin_start(margin)
        self._input_purpose_combobox.set_margin_end(margin)
        self._input_purpose_combobox.set_margin_top(margin)
        self._input_purpose_combobox.set_margin_bottom(margin)
        self._input_purpose_store = Gtk.ListStore(str, int)
        for purpose in list(itb_util.InputPurpose):
            self._input_purpose_store.append([purpose.name, purpose])
        self._input_purpose_combobox.set_model(self._input_purpose_store)
        renderer_text = Gtk.CellRendererText()
        self._input_purpose_combobox.pack_start(renderer_text, True)
        self._input_purpose_combobox.add_attribute(renderer_text, "text", 0)
        for i, item in enumerate(self._input_purpose_store):
            if self._input_purpose == item[1]:
                self._input_purpose_combobox.set_active(i)
        self._input_purpose_combobox.connect(
            'changed', self.on_input_purpose_combobox_changed)

        self._main_container.add(self._input_purpose_combobox)

        self._input_hints = itb_util.InputHints.NONE

        self._input_hints_checkbuttons: Dict[str, Gtk.CheckButton] = {}
        for hint in itb_util.InputHints:
            if hint.name is None or hint.name == 'NONE':
                continue
            self._input_hints_checkbuttons[hint.name] = Gtk.CheckButton(
                label=hint.name)
            self._input_hints_checkbuttons[hint.name].set_margin_start(margin)
            self._input_hints_checkbuttons[hint.name].set_margin_end(margin)
            self._input_hints_checkbuttons[hint.name].set_margin_top(margin)
            self._input_hints_checkbuttons[hint.name].set_margin_bottom(margin)
            self._input_hints_checkbuttons[hint.name].set_active(False)
            self._input_hints_checkbuttons[hint.name].set_hexpand(False)
            self._input_hints_checkbuttons[hint.name].set_vexpand(False)
            self._input_hints_checkbuttons[hint.name].connect(
                'clicked', self.on_checkbutton, hint)
            self._main_container.add(self._input_hints_checkbuttons[hint.name])

        self._test_entry = Gtk.Entry()
        self._test_entry.set_margin_start(margin)
        self._test_entry.set_margin_end(margin)
        self._test_entry.set_margin_top(margin)
        self._test_entry.set_margin_bottom(margin)
        self._test_entry.set_visible(True)
        self._test_entry.set_can_focus(True)
        self._test_entry.set_hexpand(False)
        self._test_entry.set_vexpand(False)
        self._test_entry.set_input_purpose(self._input_purpose)
        self._test_entry.set_input_hints(self._input_hints)
        self._test_entry.connect('notify::text', self.on_test_entry)

        self._main_container.add(self._test_entry)

        self._test_text_view = Gtk.TextView()
        self._test_text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        margin = 10
        self._test_text_view.set_margin_start(margin)
        self._test_text_view.set_margin_end(margin)
        self._test_text_view.set_margin_top(margin)
        self._test_text_view.set_margin_bottom(margin)
        self._test_text_view_buffer = Gtk.TextBuffer()
        self._test_text_view.set_buffer(self._test_text_view_buffer)
        self._test_text_view.set_visible(True)
        self._test_text_view.set_can_focus(True)
        self._test_text_view.set_hexpand(False)
        self._test_text_view.set_vexpand(True)
        self._test_text_view.set_input_purpose(self._input_purpose)
        self._test_text_view.set_input_hints(self._input_hints)
        self._test_text_view_buffer.connect(
            'changed', self.on_test_text_view_buffer_changed)

        self._main_container.add(self._test_text_view)

        self.show_all() # pylint: disable=no-member

    def on_delete_event(self, *_args: Any) -> None: # pylint: disable=no-self-use
        '''
        The window has been deleted, probably by the window manager.
        '''
        Gtk.main_quit()

    def on_destroy_event(self, *_args: Any) -> None: # pylint: disable=no-self-use
        '''
        The window has been destroyed.
        '''
        Gtk.main_quit()

    def on_test_entry( # pylint: disable=no-self-use
            self, widget: Gtk.Entry, _property_spec: Any) -> None:
        '''
        Called when something in the test entry has changed
        '''
        LOGGER.info('Test entry contains: “%s”', widget.get_text())

    def on_test_text_view_buffer_changed( # pylint: disable=no-self-use
            self, widget: Gtk.TextBuffer) -> None:
        '''
        Called when something in the test entry has changed
        '''
        LOGGER.info('Test text view contains: “%s”',
                    widget.get_text(
                        widget.get_start_iter(),
                        widget.get_end_iter(),
                        True))

    def on_input_purpose_combobox_changed(
            self, widget: Gtk.ComboBox) -> None:
        '''
        The combobox to choose the input purpose has been changed.
        '''
        tree_iter = widget.get_active_iter()
        if tree_iter is not None:
            model = widget.get_model()
            self._input_purpose = model[tree_iter][1]
            if self._input_purpose not in list(itb_util.InputPurpose):
                LOGGER.info(
                    'self._input_purpose = %s (Unknown)',
                    self._input_purpose)
                return
            for input_purpose in list(itb_util.InputPurpose):
                if self._input_purpose == input_purpose:
                    LOGGER.info(
                        'self._input_purpose = %s (%s)',
                        self._input_purpose, str(input_purpose))
                    self._test_entry.set_input_purpose(self._input_purpose)
                    self._test_text_view.set_input_purpose(self._input_purpose)
                    input_purpose_entry = (
                        self._test_entry.get_input_purpose())
                    input_purpose_text_view = (
                        self._test_text_view.get_input_purpose())
                    LOGGER.info(
                        'Input purpose changed to %s (%s)',
                        input_purpose_entry, str(input_purpose_entry))
                    if input_purpose_entry != input_purpose_text_view:
                        LOGGER.error(
                            'input_purpose_entry != '
                            'input_purpose_text_view: %s %s',
                            input_purpose_entry, input_purpose_text_view)
                    if input_purpose_entry != self._input_purpose:
                        LOGGER.error(
                            'input_purpose_entry != '
                            'self._input_purpose: %s %s',
                            input_purpose_entry, self._input_purpose)

    def on_checkbutton(
            self, widget: Gtk.CheckButton, hint: int) -> None:
        '''
        One of the check buttons to activate or deactivate an input hint
        has been clicked.
        '''
        LOGGER.info('Clicked checkbutton %s %s', widget, hint)
        if widget.get_active():
            self._input_hints |= hint
        else:
            self._input_hints &= ~hint
        self._test_entry.set_input_hints(Gtk.InputHints(self._input_hints))
        self._test_text_view.set_input_hints(Gtk.InputHints(self._input_hints))
        input_hints_entry = self._test_entry.get_input_hints()
        input_hints_text_view = self._test_text_view.get_input_hints()
        LOGGER.info('New value of self._input_hints=%s',
                    format(int(input_hints_entry), '016b'))
        if int(input_hints_entry) != int(self._input_hints):
            LOGGER.error(
                'input_hints_entry != self._input_hints: %s %s',
                input_hints_entry, self._input_hints)
        if int(input_hints_entry) != int(input_hints_text_view):
            LOGGER.error(
                'input_hints_entry != input_hints_text_view: %s %s',
                input_hints_entry, input_hints_text_view)
        for input_hint in list(itb_util.InputHints):
            if self._input_hints & input_hint:
                LOGGER.info(
                    'hint: %s %s',
                    str(hint), format(int(hint), '016b'))

if __name__ == '__main__':
    LOG_HANDLER_STREAM = logging.StreamHandler(stream=sys.stdout)
    LOG_FORMATTER = logging.Formatter(
        '%(asctime)s %(filename)s '
        'line %(lineno)d %(funcName)s %(levelname)s: '
        '%(message)s')
    LOG_HANDLER_STREAM.setFormatter(LOG_FORMATTER)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER_STREAM)
    LOGGER.info('********** STARTING **********')

    # https://bugzilla.gnome.org/show_bug.cgi?id=622084
    # Bug 622084 - Ctrl+C does not exit gtk app
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    INPUT_PURPOSE_TEST = InputPurposeTest()
    Gtk.main()
