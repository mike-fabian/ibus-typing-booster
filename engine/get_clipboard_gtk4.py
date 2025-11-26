# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2013-2018 Mike FABIAN <mfabian@redhat.com>
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
This helper uses GTK 4 to access the primary selection (mouse selection).
On Wayland, GTK 3 cannot access the primary selection at all, but GTK 4 can,
if built with support for the zwp_primary_selection_v1 protocol.

ibus-typing-booster uses GTK 3 and cannot safely mix GTK 3 and GTK 4 in the
same process. Therefore, this helper runs as a separate subprocess to
retrieve the primary selection text using GTK 4, even when the main program
is using GTK 3.
'''
from typing import Optional
from typing import TYPE_CHECKING
import sys
import os
from gi import require_version
# pylint: disable=wrong-import-position
require_version('GLib', '2.0')
require_version('Gio', '2.0')
from gi.repository import Gio, GLib # type: ignore
os.environ['ITB_GTK_VERSION'] = '4'
from itb_gtk import Gdk, Gtk  # type: ignore
if TYPE_CHECKING:
    # These imports are only for type checkers (mypy). They must not be
    # executed at runtime because itb_gtk controls the Gtk/Gdk versions.
    # pylint: disable=reimported
    from gi.repository import Gtk, Gdk  # type: ignore
    # pylint: enable=reimported
# pylint: enable=wrong-import-position

class ClipboardApp(Gtk.Application): # type: ignore[misc]
    '''Class used to read the clipboard'''
    def __init__(self) -> None:
        super().__init__(application_id="org.freedesktop.ibus.engine.typing_booster.GetSelection")
        self.window: Optional[Gtk.ApplicationWindow] = None
        self.display: Gdk.Display = Gdk.Display.get_default() # pylint: disable=no-value-for-parameter

    def do_activate(self) -> None: # pylint: disable=arguments-differ
        if 'wayland' in self.display.get_name().lower():
            # A window is needed so that zwp_primary_selection_v1
            # (mouse selection) works on Wayland. When there is no
            # visible window, GTK might delay registration of the
            # app’s data device manager or primary selection device,
            # especially if nothing is mapped on screen.
            self.window = Gtk.ApplicationWindow(application=self)
            self.window.set_default_size(1, 1)
            self.window.set_decorated(False)
            self.window.present() # Must be presented on Wayland
            # Delay clipboard read to allow Wayland registration
            GLib.timeout_add(200, self.try_read_clipboard)
        else:
            self.try_read_clipboard()

    def try_read_clipboard(self) -> bool:
        '''Method to read the clipboard and print the result'''
        clipboard: Gdk.Clipboard = self.display.get_primary_clipboard() # pylint: disable=c-extension-no-member

        def on_text_received(
                clipboard: 'Gdk.Clipboard', result: Gio.AsyncResult) -> None:
            try:
                text: Optional[str] = clipboard.read_text_finish(result)
                if text is not None:
                    print(text)
            except GLib.Error as error:
                print(f'Error reading primary selection: {error}',
                      file=sys.stderr)
            app.quit() # pylint: disable=possibly-used-before-assignment

        clipboard.read_text_async(None, on_text_received)
        return False # Do not repeat timeout

if __name__ == "__main__":
    app = ClipboardApp()
    app.run()
