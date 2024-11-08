# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2022 Mike FABIAN <mfabian@redhat.com>
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
'''Module to track the name of the program in the currently focused window

On Wayland desktops:
    Tries AT-SPI first and falls back to xprop
On X11 desktops:
    Uses only xprop

AT-SPI:

https://en.wikipedia.org/wiki/Assistive_Technology_Service_Provider_Interface

- AT-SPI seems to work reasonably well in Gnome Wayland, KDE (Plasma)
  Wayland, and in some other cases. It even works in most X11 desktops, even
  in i3 (But as getting the active window via AT-SPI can sometimes fail,
  it is better to use xprop for that on X11 desktops, xprop is very reliable
  on X11 desktops).

- Even in a Gnome Wayland or KDE (Plasma) Wayland session AT-SPI
  doesn‘t work for some old X11 programs like xterm, urxvt, ...
  But the fallback to xprop works in these cases.

- To make AT-SPI work with Firefox and google-chrome,
  GNOME_ACCESSIBILITY=1 needs to be set in the environment.

- To make AT-SPI work with Qt5, QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1
  needs to be set in the environment

- To make AT-SPI work with Qt4, QT_ACCESSIBILITY=1 needs to be set
  in the environment

In some cases, the name returned by AT-SPI may slightly differ
from from the name acquired by ibus with or by xprop.
For example in case of google-chrome:

- AT-SPI: 'Google Chrome'
- ibus focus id: 'google-chrome'
- xprop: 'google-chrome'

To test this module execute

    sleep 5 && python3 itb_active_window.py

in a terminal, and focus a different window and see whether
the information from that active window is fetched correctly

Then focus different windows and see whether the log output
seen in the terminal shows correctly which window is currently active
(This works only with AT-SPI).

'''

from typing import Any
from typing import Tuple
import sys
import os
import subprocess
import shutil
import threading
import logging
IMPORT_PYATSPI_SUCCESSFUL = False
try:
    import pyatspi # type: ignore
    IMPORT_PYATSPI_SUCCESSFUL = True
except (ImportError,):
    IMPORT_PYATSPI_SUCCESSFUL = False

LOGGER = logging.getLogger('ibus-typing-booster')

class AtspiMonitor:
    '''
    Class to monitor the program name in the currently focused window
    '''
    def __init__(self) -> None:
        '''Initialization'''
        self._active_program_name = ''
        self._active_window_title = ''
        self._events_registered = False
        if not IMPORT_PYATSPI_SUCCESSFUL:
            LOGGER.info('“import pyatspi” failed.')
            return
        try:
            pyatspi.Registry.registerEventListener(
                self._on_window_activate, 'window:activate')
            pyatspi.Registry.registerEventListener(
                self._on_window_deactivate, 'window:deactivate')
            self._events_registered = True
            LOGGER.info('AtspiMonitor events registered.')
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception('%s: %s ', error.__class__.__name__, error)


    def start(self) -> None:
        '''Starts the monitoring'''
        if self._events_registered:
            LOGGER.info('Starting AtspiMonitor.')
            pyatspi.Registry.start() # pylint: disable=no-value-for-parameter

    def get_active_window(self) -> Tuple[str, str]:
        '''
        Gets information about the currently active window.

        :return: A tuple (program_name, window_title) giving
                 information about the currently focused window.
        '''
        return (self._active_program_name, self._active_window_title)

    def _on_window_activate(self, event: Any) -> None:
        '''Called when a window gets activated.'''
        LOGGER.debug('%s', str(event))
        try:
            self._active_program_name = event.host_application.name
            self._active_window_title = event.source_name
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception('%s: %s', error.__class__.__name__, error)
        LOGGER.info('window activated: %s currently active: %s title: %s',
                    self._active_program_name,
                    self._active_program_name,
                    self._active_window_title)

    def _on_window_deactivate(self, event: Any) -> None:
        '''Called when a window gets deactivated.'''
        LOGGER.debug('%s', str(event))
        program_name = ''
        try:
            program_name = event.host_application.name
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception('%s: %s', error.__class__.__name__, error)
        # There are some windows where the 'window:activate',
        # 'window:deactivate' signals do not work, for example windows
        # containing old X11 programs like xterm behave like that.
        #
        # If the focus moves from a window where the signals work to a
        # window where they do not, only the 'window:deactivate'
        # occurs.
        #
        # Therefore, we may want to set self._active_program_name = ''
        # when a window is deactivated because we may not be able to
        # get the true name of the program in the window which is
        # activated next and it is better to have an empty string than
        # a wrong program name left over from the previously active
        # program.
        #
        # *But*, sometimes the 'window:deactivate' signal for the old
        # window occurs *after* the 'window:activate' signal of the
        # new window! Weird!  Therefore, set self._active_program_name
        # = '' only if the program name is still unchanged!
        #
        # Theoretically if there are two windows for the same program,
        # for example two 'soffice' windows (Libreoffice), moving from
        # one to the other could then reset the program name from
        # 'soffice' to '' if the 'window:deactivate' signal comes
        # last.
        #
        # Luckily, when testing this I never saw that the
        # 'window:deactivate' signal came last when moving the focus
        # between two windows for the same program, i.e. when moving
        # from 'soffice' to 'soffice' or from 'firefox' to 'firefox',
        # this never happened.  But when moving from 'soffice' to
        # 'gnome-terminal' or from 'firefox' to 'gnome-terminal', it
        # *always* happened. This might be just an accident, but I
        # don’t have a better idea for a workaround at the moment.
        if self._active_program_name == program_name:
            self._active_program_name = ''
            self._active_window_title = ''
        LOGGER.info('window deactivated: %s currently active: %s title: %s',
                    program_name,
                    self._active_program_name,
                    self._active_window_title)

_ACTIVE_WINDOW: Tuple[str, str] = ('', '')

def _get_active_window_atspi() -> None:
    '''
    Internal function to get information about the currently active window.

    :return: A tuple (program_name, window_title) giving
             information about the currently focused window.
    '''
    global _ACTIVE_WINDOW # pylint: disable=global-statement
    try:
        desktop = pyatspi.Registry.getDesktop(0) # pylint: disable=no-value-for-parameter
        for application in desktop:
            if application.getState().contains(pyatspi.STATE_DEFUNCT):
                continue
            for window in application:
                if window.get_state_set().contains(pyatspi.STATE_ACTIVE):
                    _ACTIVE_WINDOW = (application.name, window.name)
                    return
    except Exception as error: # pylint: disable=broad-except
        LOGGER.exception('%s: %s', error.__class__.__name__, error)
    _ACTIVE_WINDOW = ('', '')

def get_active_window_atspi() -> Tuple[str, str]:
    '''
    Get information about the currently active window.

    :return: A tuple (program_name, window_title) giving
             information about the currently focused window.
    '''
    global _ACTIVE_WINDOW # pylint: disable=global-statement
    _ACTIVE_WINDOW = ('', '')
    if not IMPORT_PYATSPI_SUCCESSFUL:
        return ('', '')
    active_window_thread = threading.Thread(
        daemon=True, target=_get_active_window_atspi)
    active_window_thread.start()
    active_window_thread.join(timeout=0.5)
    if active_window_thread.is_alive():
        LOGGER.error('timeout getting active window.')
        return ('', '')
    return _ACTIVE_WINDOW

def get_active_window_xprop() -> Tuple[str, str]:
    '''
    Gets information about the currently active window.

    :return: A tuple (program_name, window_title) giving
             information about the currently focused window.

    Works only in X11 sessions (and for some X11 programs like xterm,
    urxvt, ...  in Wayland sessions)
    '''
    program_name = ''
    window_title = ''
    if 'DISPLAY' not in os.environ or not os.environ['DISPLAY']:
        return (program_name, window_title)
    xprop_binary = shutil.which('xprop')
    if not xprop_binary:
        return (program_name, window_title)
    try:
        result = subprocess.run(
            [xprop_binary, '-root', '-f',
             '_NET_ACTIVE_WINDOW', '0x', ' $0', '_NET_ACTIVE_WINDOW'],
            check=True, encoding='utf-8', capture_output=True)
    except subprocess.CalledProcessError as error:
        LOGGER.exception(
            'Exception when calling xprop: %s: %s stderr: %s',
             error.__class__.__name__, error, error.stderr)
        return (program_name, window_title)
    # result now looks like in this example:
    #
    # '_NET_ACTIVE_WINDOW(WINDOW) 0x1e02d79'
    if len(result.stdout.split()) < 2:
        LOGGER.error('Unexpected xprop output for id of active window')
        return (program_name, window_title)
    window_id = result.stdout.split()[-1:][0]
    if window_id == '0x0':
        return (program_name, window_title)
    try:
        result = subprocess.run(
            [xprop_binary,
             '-id', window_id, '-f', 'WM_CLASS', '0s', 'WM_CLASS'],
            check=True, encoding='utf-8', capture_output=True)
    except subprocess.CalledProcessError as error:
        LOGGER.exception(
            'Exception when calling xprop: %s: %s stderr: %s',
             error.__class__.__name__, error,  error.stderr)
        return (program_name, window_title)
    # result now looks like in this example
    #
    # 'WM_CLASS(STRING) = "xfce4-terminal", "Xfce4-terminal"\n'
    if '=' not in result.stdout or ',' not in result.stdout:
        LOGGER.error(
            'Unexpected xprop output for program name of active window')
        return (program_name, window_title)
    program_name = result.stdout.split(
        '=', maxsplit=1)[1].split(',')[1].strip()[1:-1].lower()
    try:
        result = subprocess.run(
            [xprop_binary,
             '-id', window_id, '-f', '_NET_WM_NAME', '0t', '_NET_WM_NAME'],
            check=True, encoding='utf-8', capture_output=True)
    except subprocess.CalledProcessError as error:
        LOGGER.exception(
            'Exception when calling xprop: %s: %s stderr: %s',
             error.__class__.__name__, error, error.stderr)
        return (program_name, window_title)
    # result now looks like in this example
    #
    # '_NET_WM_NAME(UTF8_STRING) = "☺foo = "bar"\n'
    if '=' not in result.stdout:
        LOGGER.error('Unexpected xprop output for title of active window')
        return (program_name, window_title)
    window_title = result.stdout.split('=', maxsplit=1)[1].strip()[1:-1]
    return (program_name, window_title)


def get_active_window() -> Tuple[str, str]:
    '''
    Gets information about the currently active window.

    :return: A tuple (program_name, window_title) giving
             information about the currently focused window.

    Tries AT-SPI first, if that doesn’t work falls back to xprop.

    '''
    (program_name, window_title) = ('', '')
    if ('WAYLAND_DISPLAY' in os.environ
        and 'XDG_SESSION_TYPE' in os.environ
        and os.environ['XDG_SESSION_TYPE'].lower() == 'wayland'):
        (program_name, window_title) = get_active_window_atspi()
    if program_name:
        LOGGER.debug(
            'Got active window from AT-SPI: %s', (program_name, window_title))
        return (program_name, window_title)
    (program_name, window_title) = get_active_window_xprop()
    if program_name:
        LOGGER.debug(
            'Got active window from xprop: %s', (program_name, window_title))
    return (program_name, window_title)

if __name__ == "__main__":
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    LOGGER.info('%s', get_active_window())
    atspi_monitor = AtspiMonitor()
    atspi_monitor.start()
