# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2015-2025 Mike FABIAN <mfabian@redhat.com>
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
A module with utilites to use ollama
'''

from typing import Callable
from typing import Optional
from typing import List
from typing import Dict
from typing import Union
from typing import Any
from types import FrameType
import sys
import os
import signal
import argparse
import locale
import threading
import gettext
import logging

from gi import require_version # type: ignore
# pylint: disable=wrong-import-position
require_version('GLib', '2.0')
from gi.repository import GLib # type: ignore
# pylint: enable=wrong-import-position

# set_prgname before importing other modules to show the name in warning
# messages when import modules are failed. E.g. Gtk.
GLib.set_application_name('Ollama Pull')

# pylint: disable=wrong-import-position
require_version('Gtk', '3.0')
from gi.repository import Gtk
# pylint: enable=wrong-import-position

import itb_ollama

LOGGER = logging.getLogger('ibus-typing-booster')

GLIB_MAIN_LOOP: Optional[GLib.MainLoop] = None

DOMAINNAME = 'ibus-typing-booster'
_: Callable[[str], str] = lambda a: gettext.dgettext(DOMAINNAME, a)
N_: Callable[[str], str] = lambda a: a

def str2bool(v: Union[bool, str]) -> bool:
    '''
    Convert a string to a boolean for argparse.
    '''
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', '1'):
        return True
    if v.lower() in ('no', 'false', 'f', '0'):
        return False
    raise argparse.ArgumentTypeError('Boolean value expected.')

def parse_args() -> Any:
    '''
    Parse the command line arguments.
    '''
    parser = argparse.ArgumentParser(
        description='UI to show progress while pulling a ollama model.')
    parser.add_argument(
        '-m', '--model',
        nargs='?',
        type=str,
        action='store',
        default=None,
        help=('Choose the model to pull. '
              'default: "%(default)s"'))
    parser.add_argument(
        '-d', '--debug',
        nargs='?',
        type=str2bool,
        action='store',
        const=True, # if -d or --debug with no value assume True
        default=False,
        help=('Print some debug output to stdout. '
              'default: %(default)s'))
    return parser.parse_args()

_ARGS = parse_args()

class OllamaPullUI(Gtk.Window): # type: ignore
    '''
    UI to show progress while pulling a ollama model.
    '''
    def __init__(self, model: str = '') -> None:
        self._model = model
        if self._model == '':
            raise ValueError('Model name should not be empty.')
        self._thread: Optional[threading.Thread] = None
        self._stop_event: threading.Event = threading.Event()
        self._status = ''
        self._status_labels: List[Gtk.Label] = []
        self._status_progress_bars: List[Gtk.ProgressBar] = []
        title = f'📥 {self._model}'
        Gtk.Window.__init__(self, title=title)
        self.set_title(title)
        self.set_name('Ollama Pull')
        self.set_modal(True)
        self.connect('destroy-event', self.__class__._on_destroy_event)
        self.connect('delete-event', self.__class__._on_delete_event)
        self._main_container = Gtk.Box()
        self._main_container.set_orientation(Gtk.Orientation.VERTICAL)
        self._main_container.set_spacing(0)
        self._main_container.set_hexpand(True)
        self._main_container.set_vexpand(True)
        self.add(self._main_container) # pylint: disable=no-member
        self._progress_grid = Gtk.Grid()
        self._progress_grid.set_visible(True)
        self._progress_grid.set_can_focus(False)
        self._progress_grid.set_border_width(5)
        self._progress_grid.set_row_spacing(5)
        self._progress_grid.set_column_spacing(10)
        self._progress_grid.set_row_homogeneous(False)
        self._progress_grid.set_column_homogeneous(False)
        self._progress_grid.set_hexpand(True)
        self._progress_grid.set_vexpand(False)
        self._row = -1
        self._main_container.add(self._progress_grid)
        self._dialog_action_area = Gtk.Box()
        self._dialog_action_area.set_orientation(Gtk.Orientation.HORIZONTAL)
        self._dialog_action_area.set_visible(True)
        self._dialog_action_area.set_can_focus(False)
        self._dialog_action_area.set_hexpand(True)
        self._dialog_action_area.set_vexpand(False)
        self._dialog_action_area.set_spacing(0)
        self._main_container.add(self._dialog_action_area)
        empty_hexpanding_label = Gtk.Label()
        empty_hexpanding_label.set_hexpand(True)
        empty_hexpanding_label.set_vexpand(False)
        self._dialog_action_area.add(empty_hexpanding_label)
        self._cancel_button = Gtk.Button()
        self._cancel_button_label = Gtk.Label()
        self._cancel_button_label.set_text_with_mnemonic(_('_Cancel'))
        self._cancel_button.add(self._cancel_button_label)
        self._cancel_button.connect('clicked', self._on_cancel_clicked)
        self._dialog_action_area.add(self._cancel_button)
        self._close_button = Gtk.Button()
        self._close_button_label = Gtk.Label()
        self._close_button_label.set_text_with_mnemonic(_('_Close'))
        self._close_button.add(self._close_button_label)
        self._close_button.connect('clicked', self._on_close_clicked)
        self._dialog_action_area.add(self._close_button)
        self.show_all() # pylint: disable=no-member
        self._close_button.hide()
        GLib.timeout_add(200, self._check_for_interrupt)
        GLib.idle_add(self._pull)

    def _pull(self) -> None:
        '''Pull the requested model'''
        ollama_client = itb_ollama.ItbOllamaClient()
        if self._stop_event:
            self._stop_event.clear()
        self._thread = threading.Thread(
            daemon=True,
            target=ollama_client.pull,
            args=(self._model, self._pull_progress_idle_add, self._stop_event))
        self._thread.start()

    def _pull_progress_idle_add(self, progress: Dict[str, Any]) -> None:
        '''Schedule an update of the progress of pulling the ollama model'''
        GLib.idle_add(lambda:
                      self._pull_progress(progress))

    def _pull_progress(self, progress: Dict[str, Any]) -> None:
        '''Show the progress of pulling the ollama model'''
        error = progress.get('error', None)
        total = progress.get('total', None)
        completed = progress.get('completed', None)
        status = progress.get('status', None)
        if error is not None:
            LOGGER.error('Error pulling %r: %r', self._model, error)
            error_label = Gtk.Label()
            error_label.set_text(error)
            error_label.set_xalign(0)
            self._progress_grid.attach(
                error_label, 0, self._row, 1, 1)
            error_label.show()
            return
        if status is not None and status != self._status:
            self._status = status
            self._row += 1
            self._status_labels.append(Gtk.Label())
            self._status_labels[self._row].set_xalign(0)
            self._progress_grid.attach(
                self._status_labels[self._row],
                0, self._row, 1, 1)
            self._status_labels[self._row].show()
            self._status_progress_bars.append(Gtk.ProgressBar())
            self._status_progress_bars[self._row].set_show_text(False)
            self._status_progress_bars[self._row].set_pulse_step(0)
            # Width 150px, natural height
            self._status_progress_bars[self._row].set_size_request(150, -1)
            self._status_progress_bars[self._row].set_vexpand(True)
            self._status_progress_bars[self._row].set_valign(Gtk.Align.CENTER)
            self._status_progress_bars[self._row].set_margin_start(10)
            self._status_progress_bars[self._row].set_margin_end(10)
            self._progress_grid.attach(
                self._status_progress_bars[self._row],
                1, self._row, 1, 1)
            self._status_progress_bars[self._row].hide()
        if total is not None and completed is not None:
            fraction = float(completed / total) if total > 0.0 else 0.0
            status_text = status if status is not None else ''
            total_text = f'{total} B'
            if total > 1024**3:
                total_text = f'{total / 1024**3:.1f} GB'
            elif total > 1024**2:
                total_text = f'{total / 1024**2:.1f} MB'
            elif total > 1024:
                total_text = f'{total / 1024:.1f} kB'
            LOGGER.info('%r: %r (%.1f%%)',
                status_text, total_text, 100 * fraction)
            if self._status_labels[self._row] is not None:
                self._status_labels[self._row].set_text(
                    f'{status_text}: {total_text} ({100 * fraction:.1f}%)')
            if self._status_progress_bars[self._row] is not None:
                self._status_progress_bars[self._row].show()
                self._status_progress_bars[self._row].set_fraction(fraction)
        elif status is not None:
            LOGGER.info('%r', status)
            if self._status_labels[self._row] is not None:
                self._status_labels[self._row].set_text(status)
        if status == 'success':
            self._cancel_button.hide()
            self._close_button.show()

    @staticmethod
    def _quit() -> None:
        '''Quit the GLib main loop'''
        LOGGER.info('Quit GLib main loop')
        if GLIB_MAIN_LOOP is not None:
            GLIB_MAIN_LOOP.quit()
        else:
            raise RuntimeError('GLIB_MAIN_LOOP not initialized!')

    def _on_delete_event(self, *_args: Any) -> None:
        '''The window has been deleted, probably by the window manager.'''
        LOGGER.info('Window deleted by the window manager.')
        self._cancel_pull()
        self.__class__._quit() # pylint: disable=protected-access

    def _on_destroy_event(self, *_args: Any) -> None:
        '''The window has been destroyed.'''
        LOGGER.info('Window destroyed.')
        self._cancel_pull()
        self.__class__._quit() # pylint: disable=protected-access

    def _cancel_pull(self) -> None:
        '''Cancel a running pull'''
        if not self._thread:
            LOGGER.info('No thread, cannot cancel.')
            return
        if not self._stop_event:
            LOGGER.info('No stop event, cannot cancel.')
            return
        if self._thread.is_alive():
            self._stop_event.set()
            self._thread.join()
            self._pull_progress({'status': 'cancelled'})
        self._stop_event.clear()
        self._thread = None
        self._cancel_button.hide()
        self._close_button.show()

    def _on_cancel_clicked(self, *_args: Any) -> None:
        '''The button to cancel has been clicked.'''
        LOGGER.info('Cancel button clicked.')
        self._cancel_pull()

    def _on_close_clicked(self, *_args: Any) -> None:
        '''The close button has been clicked.'''
        LOGGER.info('Close clicked.')
        self._cancel_pull()
        self.__class__._quit() # pylint: disable=protected-access

    def _check_for_interrupt(self) -> bool:
        '''Checks for interrupts. Is called by GLib.timeout_add()'''
        if SIGNAL_HANDLER.interrupt_requested:
            LOGGER.info('Interrupt requested, shutting down...')
            self._cancel_pull()
            self.__class__._quit() # pylint: disable=protected-access
            return False # stop repeating
        return True # keep running

class SignalHandler:
    '''Thread-safe signal handler for interrupt requests (e.g., Ctrl+C).

    This class provides a safe way to check and set an interrupt flag
    from multiple threads.  It is designed to work with GLib’s signal
    handling (e.g., `GLib.unix_signal_add()`) while preventing race
    conditions during access.

    Attributes:
        interrupt_requested (bool):
            Read-only property indicating whether an interrupt
            (e.g., SIGINT/Ctrl+C) was triggered. Thread-safe.
    '''
    def __init__(self) -> None:
        '''Init the signal handler class.'''
        self._interrupt_requested: bool = False
        self._lock = threading.Lock()

    @property
    def interrupt_requested(self) -> bool:
        '''Check if an interrupt was requested with thread-safe
        read-only access.
        '''
        with self._lock:
            return self._interrupt_requested

    def handle_sigint(self, *_args: Any) -> bool:
        ''' Callback for Ctrl+C (SIGINT).

        :return: bool: True to keep the handler alive,
                       False to remove it.
        '''
        LOGGER.info('SIGINT')
        with self._lock:
            self._interrupt_requested = True
        return True

    def handle_sigterm(self, *_args: Any) -> bool:
        ''' Callback for Ctrl+C (SIGTERM).

        :return: bool: True to keep the handler alive,
                       False to remove it.
        '''
        LOGGER.info('SIGTERM')
        with self._lock:
            self._interrupt_requested = True
        return True

SIGNAL_HANDLER: SignalHandler = SignalHandler()

def quit_glib_main_loop(
        signum: int, _frame: Optional[FrameType] = None) -> None:
    '''Signal handler for signals from Python’s signal module

    :param signum: The signal number
    :param _frame:  Almost never used (it’s for debugging).
    '''
    if signum is not None:
        try:
            signal_name = signal.Signals(signum).name
        except ValueError: # In case signum isn't in Signals enum
            signal_name = str(signum)
        LOGGER.info('Received signal %s (%s), exiting...', signum, signal_name)
    if GLIB_MAIN_LOOP is not None:
        GLIB_MAIN_LOOP.quit()
    else:
        raise RuntimeError('GLIB_MAIN_LOOP not initialized!')


if __name__ == '__main__':
    if not _ARGS.debug:
        LOG_HANDLER_NULL = logging.NullHandler()
    else:
        LOG_HANDLER_STREAM = logging.StreamHandler(stream=sys.stdout)
        LOG_FORMATTER = logging.Formatter(
            '%(asctime)s %(filename)s '
            'line %(lineno)d %(funcName)s %(levelname)s: '
            '%(message)s')
        LOG_HANDLER_STREAM.setFormatter(LOG_FORMATTER)
        LOGGER.setLevel(logging.DEBUG)
        LOGGER.addHandler(LOG_HANDLER_STREAM)

    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        LOGGER.error("IBUS-WARNING **: Using the fallback 'C' locale")
        locale.setlocale(locale.LC_ALL, 'C')

    LOCALEDIR = os.getenv('IBUS_LOCALEDIR')
    gettext.bindtextdomain(DOMAINNAME, LOCALEDIR)

    if _ARGS.model is not None:
        OLLAMA_PULL_UI = OllamaPullUI(model=_ARGS.model)
        GLIB_MAIN_LOOP = GLib.MainLoop()
        # signal.signal(signal.SIGTERM, quit_glib_main_loop) # kill <pid>
        # Ctrl+C (optional, can also use try/except KeyboardInterrupt)
        # signal.signal(signal.SIGINT, quit_glib_main_loop)
        GLib.unix_signal_add(
            GLib.PRIORITY_DEFAULT,
            signal.SIGTERM,
            SIGNAL_HANDLER.handle_sigterm, # kill <pid>
            None)
        GLib.unix_signal_add(
            GLib.PRIORITY_DEFAULT,
            signal.SIGINT,
            SIGNAL_HANDLER.handle_sigint, # Keyboard interrupt
            None)
        try:
            GLIB_MAIN_LOOP.run()
        except KeyboardInterrupt:
            # SIGNINT (Control+C) received
            LOGGER.info('Control+C pressed, exiting ...')
            GLIB_MAIN_LOOP.quit()
