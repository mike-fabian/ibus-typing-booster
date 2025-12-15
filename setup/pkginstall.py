# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2025 Mike FABIAN <mfabian@redhat.com>
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
pkginstall.py – Install missing dictionaries for ibus-typing-booster

Uses pkcon (PackageKit) via Gio.Subprocess with a Gtk3 progress dialog.
Works asynchronously and integrates smoothly with the main GTK mainloop.
'''
from typing import Set
from typing import Dict
from typing import List
from typing import Any
from typing import Optional
from typing import Callable
from typing import TYPE_CHECKING
# pylint: disable=wrong-import-position
import sys
if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal
# pylint: enable=wrong-import-position
import os
import re
import signal
import locale
import logging
from gi import require_version
# pylint: disable=wrong-import-position
require_version('GLib', '2.0')
require_version('Gio', '2.0')
from gi.repository import GLib # type: ignore
from gi.repository import Gio # type: ignore
# pylint: enable=wrong-import-position
from i18n import _, init as i18n_init
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
# pylint: disable=import-error, wrong-import-order
from itb_gtk import Gtk # type: ignore
if TYPE_CHECKING:
    # These imports are only for type checkers (mypy). They must not be
    # executed at runtime because itb_gtk controls the Gtk/Gdk versions.
    # pylint: disable=reimported
    from gi.repository import Gtk  # type: ignore
    # pylint: enable=reimported
from g_compat_helpers import (
    add_child,
    show_all,
)
# pylint: enable=import-error, wrong-import-order
InstallStatus = Literal['success', 'cancelled', 'failure']
OutputCallback = Callable[[str], None]
CompleteCallback = Callable[[InstallStatus], None]

LOGGER = logging.getLogger('ibus-typing-booster')

def install_packages_async(
    packages: Optional[Set[str]] = None,
    on_output: Optional[OutputCallback] = None,
    on_complete: Optional[CompleteCallback] = None,
) -> Optional[Gio.Subprocess]:
    '''Install packages asynchronously using pkcon and GLib subprocess APIs.'''
    if not packages:
        LOGGER.info('No packages to install.')
        if on_complete:
            on_complete('success')
        return None
    args = ['pkcon', 'install', '-y'] + list(packages)
    LOGGER.info('Running command: %s', ' '.join(args))
    proc = Gio.Subprocess.new(
        args,
        Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
    stdout_reader = Gio.DataInputStream.new(proc.get_stdout_pipe())
    stderr_reader = Gio.DataInputStream.new(proc.get_stderr_pipe())

    def read_stdout_line(
        _stream: Gio.DataInputStream,
        res: Gio.AsyncResult,
        _data: Optional[Any] = None
    ) -> None:
        try:
            line, _len = stdout_reader.read_line_finish(res)
            if line:
                text = line.decode('utf-8', errors='replace').strip()
                LOGGER.debug('[pkcon] %s', text)
                if on_output:
                    GLib.idle_add(on_output, text)
                stdout_reader.read_line_async(
                    GLib.PRIORITY_DEFAULT, None, read_stdout_line, None)
        except GLib.Error as err:
            LOGGER.debug('stdout finished: %s', err)

    def read_stderr_line(
        _stream: Gio.DataInputStream,
        res: Gio.AsyncResult,
        _data: Optional[Any] = None
    ) -> None:
        try:
            line, _len = stderr_reader.read_line_finish(res)
            if line:
                text = line.decode('utf-8', errors='replace').strip()
                LOGGER.warning('[pkcon:stderr] %s', text)
                if on_output:
                    GLib.idle_add(on_output, text)
                stderr_reader.read_line_async(
                    GLib.PRIORITY_DEFAULT, None, read_stderr_line, None)
        except GLib.Error as err:
            LOGGER.debug('stderr finished: %s', err)

    stdout_reader.read_line_async(
        GLib.PRIORITY_DEFAULT, None, read_stdout_line, None)
    stderr_reader.read_line_async(
        GLib.PRIORITY_DEFAULT, None, read_stderr_line, None)

    def on_finish(
        _proc: Gio.Subprocess,
        res: Gio.AsyncResult,
        _data: Optional[Any] = None
    ) -> None:
        try:
            success = _proc.wait_check_finish(res)
        except GLib.Error as err:
            LOGGER.error('pkcon failed: %s', err)
            success = False
        LOGGER.info('pkcon finished, success=%s', success)
        if on_complete:
            GLib.idle_add(on_complete, 'success' if success else 'failed')

    proc.wait_check_async(None, on_finish, None)
    return proc

def install_packages_sequentially_async(
    packages: Set[str],
    on_output: Optional[OutputCallback] = None,
    on_complete: Optional[CompleteCallback] = None,
) -> Callable[[], None]:
    '''Install packages sequentially using pkcon, one by one.

    This avoids the 'already installed' fatal error that breaks multi-install.
    '''
    package_list: List[str] = sorted(packages)
    results: Dict[str, bool] = {}
    current_proc: Optional[Gio.Subprocess] = None
    cancelled: bool = False

    def cancel() -> None:
        '''Cancel the current pkcon process'''
        nonlocal current_proc, cancelled
        cancelled = True
        if current_proc:
            try:
                pid = current_proc.get_identifier()
                LOGGER.info("Cancelling pkcon (pid=%r)...", pid)
                current_proc.send_signal(signal.SIGTERM)
            except GLib.Error as err:
                LOGGER.warning("Failed to send SIGTERM to pkcon: %s", err)
        if on_complete:
            on_complete('cancelled')

    def install_next(index: int = 0) -> None:
        '''Install the next package'''
        nonlocal current_proc
        if cancelled:
            LOGGER.info('Installation cancelled before package #%d', index)
            return
        if index >= len(package_list):
            success = all(results.values())
            LOGGER.info('All installations done: %s', results)
            if on_complete:
                on_complete('success' if success else 'failure')
            return
        pkg = package_list[index]
        LOGGER.info('Installing package %s (%d/%d)', pkg, index + 1, len(package_list))
        if on_output:
            on_output(f'Installing {pkg}...')

        def handle_output(line: str) -> None:
            '''Call on_output and prefix each line for clarity'''
            if on_output:
                on_output(f'[{pkg}] {line}')

        def handle_complete(status: InstallStatus) -> None:
            '''Called when one package is completed

            Puts easily parsable lines into the output to make it
            easy for dialog to update the progress.
            '''
            results[pkg] = status == 'success'
            if on_output:
                on_output(f'{pkg} {"✔️" if status == "success" else "⚠️"}')
            install_next(index + 1)

        current_proc = install_packages_async(
            {pkg}, on_output=handle_output, on_complete=handle_complete)

    install_next()
    return cancel

def install_packages_with_dialog(
    parent: Optional[Gtk.Window],
    packages: Set[str],
    on_complete: Optional[CompleteCallback] = None
) -> None:
    '''Show a transient GTK dialog to install packages asynchronously.'''
    dialog = Gtk.Dialog(
        title='📦 ' + _('Install missing dictionaries'),
        transient_for=parent,
        modal=True,
        destroy_with_parent=True)
    dialog.set_default_size(480, 320)
    vbox = dialog.get_content_area()
    top_label = Gtk.Label(label='')
    top_label.set_xalign(0)
    add_child(vbox, top_label)
    textview = Gtk.TextView()
    textview.set_editable(False)
    textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    textbuffer = textview.get_buffer()
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_vexpand(True)
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    add_child(scrolled, textview)
    add_child(vbox, scrolled)
    progressbar = Gtk.ProgressBar()
    progressbar.set_show_text(True)
    progressbar.set_text('0%')
    add_child(vbox, progressbar)
    action_area = Gtk.Box()
    action_area.set_orientation(Gtk.Orientation.HORIZONTAL)
    action_area.set_halign(Gtk.Align.END)
    action_area.set_valign(Gtk.Align.CENTER)
    action_area.set_can_focus(False)
    action_area.set_hexpand(True)
    action_area.set_vexpand(False)
    action_area.set_spacing(0)
    add_child(vbox, action_area)
    cancel_button = Gtk.Button.new_with_mnemonic(_('_Cancel'))
    add_child(action_area, cancel_button)
    close_button = Gtk.Button.new_with_mnemonic(_('_Close'))
    add_child(action_area, close_button)
    show_all(dialog)
    close_button.hide()

    package_index = 0
    package_count = len(packages)
    phase_percent = 0
    summed_phase_percent = 0
    total_percent = 0
    percent_re = re.compile(r'(\d{1,3})\s*$')
    cancel_func: Optional[Callable[[], None]] = None

    def append_line(line: str) -> None:
        '''Append a line to the textbuffer showing detailed progress'''
        nonlocal phase_percent, summed_phase_percent, total_percent, package_index
        end = textbuffer.get_end_iter()
        textbuffer.insert(end, line + '\n')
        textview.scroll_mark_onscreen(textbuffer.get_insert())
        # Parse percentage value (locale-independent)
        match = percent_re.search(line)
        if match:
            try:
                percent = int(match.group(1))
                if 0 <= percent <= 100:
                    if percent > phase_percent:
                        summed_phase_percent += percent - phase_percent
                    phase_percent = percent
                    progressbar.set_fraction(
                        (total_percent + summed_phase_percent) / (package_count * 200))
                    progressbar.set_text(
                        f'{int((total_percent + summed_phase_percent) / (package_count * 2))}%')
                    return
            except ValueError:
                pass
        # Detect per-package completion (From messages I emit myself)
        if '✔️' in line or '⚠️' in line:
            # Count this package as fully processed
            package_index += 1
            summed_phase_percent = 0
            total_percent = package_index * 200
            progressbar.set_fraction(total_percent / (package_count * 200))
            progressbar.set_text(f'{int(total_percent / (package_count * 2))}%')
            text = top_label.get_text()
            # In Python < 3.12, f-string expression part cannot include a backslash
            newline = '\n'
            top_label.set_text(f'{text + newline if text else ""}{line}')

    def finish(status: InstallStatus) -> None:
        '''Installation of all packages finished or cancelled.'''
        if status == 'success':
            progressbar.set_fraction(1.0)
            progressbar.set_text('100%')
        elif status == 'cancelled':
            end = textbuffer.get_end_iter()
            textbuffer.insert(end, '⚠️ Installation cancelled by user.\n')
        else: # 'failed'
            end = textbuffer.get_end_iter()
            textbuffer.insert(end, '❌ There were some failures.\n')
        cancel_button.hide()
        close_button.show()
        if on_complete:
            on_complete(status)

    def on_cancel(_button: Gtk.Button) -> None:
        '''Cancel button clicked'''
        nonlocal cancel_func
        if cancel_func is not None and callable(cancel_func):
            cancel_func()
        cancel_button.hide()
        close_button.show()

    def on_close(_button: Gtk.Button) -> None:
        '''Close button clicked'''
        if glib_main_loop is not None and glib_main_loop.is_running():
            glib_main_loop.quit()
        dialog.destroy()

    cancel_button.connect('clicked', on_cancel)
    close_button.connect('clicked', on_close)
    cancel_func = install_packages_sequentially_async(
        packages, on_output=append_line, on_complete=finish)
    glib_main_loop: Optional[GLib.MainLoop] = None
    # If a GLib main loop is already running (e.g. from setup UI),
    # don’t start another one; just return control to it.
    if GLib.main_depth() > 0: # pylint: disable=no-value-for-parameter
        # There’s already a running loop
        return
    # Otherwise (standalone testing), run our own main loop
    glib_main_loop = GLib.MainLoop()
    glib_main_loop.run()
    dialog.destroy()

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)

    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        LOGGER.exception("IBUS-WARNING **: Using the fallback 'C' locale")
        locale.setlocale(locale.LC_ALL, 'C')
    i18n_init()

    missing = {'hunspell-de', 'hunspell-fr'}

    def finish_test(status: InstallStatus) -> None:
        '''Called when the installation completes'''
        if status == 'success':
            LOGGER.info('Install completed without errors.')
        elif status == 'cancelled':
            LOGGER.info('⚠️ Installation cancelled by user.')
        else: # 'failure'
            LOGGER.info('❌ There were some failures.')

    install_packages_with_dialog(None, missing, on_complete=finish_test)
