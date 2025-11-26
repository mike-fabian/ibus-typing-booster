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
'''GTK 3/4 Compatibility Helpers

A collection of helper functions and classes to ease the transition
from Gtk3 to Gtk4.

This helper module should not call gi.require_version() for both Gtk,
Pango, ...

Instead, let the main application decide which version to load.  This
helper module should work with whichever version is loaded.
'''
from typing import (
    List,
    Tuple,
    Optional,
    Callable,
    Any,
    cast,
    overload,
    TYPE_CHECKING,
)
import html
import logging
import gettext
from enum import Enum, auto
from gi import require_version
require_version('GLib', '2.0')
require_version('Gio', '2.0')
# pylint: disable=wrong-import-position
from gi.repository import GLib # type: ignore
from gi.repository import Gio # type: ignore
from gi.repository import GdkPixbuf # type: ignore
from gi.repository import Pango # type: ignore
from itb_gtk import Gdk, Gtk, GTK_MAJOR, GTK_VERSION # type: ignore
# pylint: enable=wrong-import-position
if TYPE_CHECKING:
    # These imports are only for type checkers (mypy). They must not be
    # executed at runtime because itb_gtk controls the Gtk/Gdk versions.
    # pylint: disable=reimported
    from gi.repository import Gtk, Gdk  # type: ignore
    # pylint: enable=reimported
ResponseCallback = Callable[[], None]
ClickCallback = Callable[[Gtk.Widget, int, Any], None]
ReleaseCallback = Callable[[Gtk.Widget, int, Any], None]
LongPressCallback = Callable[[Gtk.Widget, Any], None]

LOGGER = logging.getLogger('ibus-typing-booster')

DOMAINNAME = 'ibus-typing-booster'

def _(text: str) -> str:
    '''Gettext translation function.'''
    return gettext.dgettext(DOMAINNAME, text)

def N_(text: str) -> str: # pylint: disable=invalid-name
    '''Mark string for translation without actually translating.

    Used by gettext tools to extract strings that need translation.
    '''
    return text

def is_wayland() -> bool:
    '''Test whether Wayland is used'''
    display = Gdk.Display.get_default() # pylint: disable=no-value-for-parameter
    return display is not None and "wayland" in display.get_name().lower()

def add_child(widget: Gtk.Widget, child: Gtk.Widget) -> None:
    '''Gtk3/4 compatible child insertion.'''
    if GTK_MAJOR >=4:
        # Gtk.Window, Gtk.Button, Gtk.Frame, Gtk.ScrolledWindow, etc.
        if hasattr(widget, 'set_child'):
            widget.set_child(child)
        # Gtk.Box
        elif hasattr(widget, 'append'):
            widget.append(child)
        else:
            raise TypeError(f'Don’t know how to add child to {type(widget).__name__}')
    else: # Gtk3
        if hasattr(widget, 'add'):
            widget.add(child)
        elif hasattr(widget, 'pack_start'):
            widget.pack_start(child, True, True, 0)
        else:
            raise TypeError(f'Don’t know how to add child to {type(widget).__name__}')

def set_border_width(widget: Gtk.Widget, width: int) -> None:
    '''Gtk3/4 compatible border width setting'''
    if GTK_MAJOR >=4:
        # Use padding instead of border-width for blank space around the widget:
        css = f'* {{ padding: {width}px; }}'
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode("utf-8"))
        widget.get_style_context().add_provider(
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
    else:
        widget.set_border_width(width)

def set_label_wrap_mode(label: Gtk.Label, wrap: bool = True,
                        wrap_mode: Pango.WrapMode = Pango.WrapMode.WORD) -> None:
    '''Set wrapping and wrap mode on a Gtk.Label, Gtk3/ Gtk4 compatible.'''
    if hasattr(label, 'set_wrap'): # Gtk4
        label.set_wrap(wrap)
    elif hasattr(label, 'set_line_wrap'): # Gtk3
        label.set_line_wrap(wrap)
    else:
        try:
            label.set_property('wrap', wrap)
        except Exception: # pylint: disable=broad-except
            pass
    if hasattr(label, 'set_wrap_mode'): # Gtk4
        label.set_wrap_mode(wrap_mode)
    elif hasattr(label, 'set_line_wrap_mode'): # Gtk3
        label.set_line_wrap_mode(wrap_mode)
    else:
        try:
            label.set_property('wrap-mode', wrap_mode)
        except Exception: # pylint: disable=broad-except
            pass

def clear_children(widget: Gtk.Widget) -> None:
    '''Remove all child widgets from `widget`, in a way that works
    for both Gtk3 and Gtk4.
    '''
    # Gtk3: containers have .get_children() and .remove()
    if hasattr(widget, 'get_children') and hasattr(widget, 'remove'):
        for child in widget.get_children():
            widget.remove(child)
        return
    # Gtk4: single-child containers use set_child()
    if hasattr(widget, 'get_child') and hasattr(widget, 'set_child'):
        child = widget.get_child()
        if child is not None:
            widget.set_child(None)
        return
    # Gtk4: multi-child containers without get_children() use first/next sibling
    if hasattr(widget, 'get_first_child') and hasattr(widget, 'get_next_sibling'):
        child = widget.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            child.unparent()
            child = next_child
        return
    # Fallback — nothing to do
    return

def children_of(widget: Gtk.Widget) -> List[Gtk.Widget]:
    '''Return iterable of logical children for Gtk3/Gtk4 (internal helper).'''
    if hasattr(widget, 'get_children'): # Gtk3 containers
        try:
            return list(widget.get_children())
        except Exception: # pylint: disable=broad-except
            pass
    # Gtk4 single-child widgets / scrolled windows
    if hasattr(widget, 'get_child'):
        try:
            child = widget.get_child()
            # Unwrap viewport if present
            if child is not None and isinstance(child, Gtk.Viewport):
                inner = child.get_child()
                return [inner] if inner is not None else []
            return [child] if child is not None else []
        except Exception: # pylint: disable=broad-except
            pass
    # Gtk4 multi-child sibling API
    if hasattr(widget, 'get_first_child') and hasattr(widget, 'get_next_sibling'):
        kids = []
        child = widget.get_first_child()
        while child is not None:
            kids.append(child)
            child = child.get_next_sibling()
        return kids
    return []

def show_all(widget: Optional[Gtk.Widget]) -> None:
    '''Make `widget` and all of its children visible (Gtk3-compatible show_all).

    Works on both Gtk3 and Gtk4.
    '''
    if widget is None:
        return
    # If Gtk3 provides show_all, prefer it (fast, well-tested)
    if hasattr(widget, 'show_all'):
        try:
            widget.show_all()
            return
        except Exception: # pylint: disable=broad-except
            # fall through to manual recursion
            pass
    # Set this widget visible if possible
    if hasattr(widget, 'set_visible'):
        try:
            widget.set_visible(True)
        except Exception: # pylint: disable=broad-except
            pass
    # Recurse into children
    for child in children_of(widget):
        show_all(child)

def icon_image_for_name(icon_name: str, icon_size: int = 48) -> Gtk.Image:
    '''Return a Gtk.Image for icon_name sized approximately `icon_size`.

    Works on both Gtk3 and Gtk4 by trying multiple fallbacks.
    '''
    # Try to load a pixbuf via IconTheme (Gtk3-friendly).
    try:
        theme = Gtk.IconTheme.get_default() # pylint: disable=no-value-for-parameter
        if theme is not None and hasattr(theme, 'load_icon'):
            pix = theme.load_icon(icon_name, icon_size, 0)
            if pix is not None:
                return Gtk.Image.new_from_pixbuf(pix)
    except Exception: # pylint: disable=broad-except
        pass
    try: # Try Gtk4 style first (no size argument)
        img = Gtk.Image.new_from_icon_name(icon_name)
        # Try to set pixel size on the Gtk.Image if available (Gtk4)
        if hasattr(img, 'set_pixel_size'):
            try:
                img.set_pixel_size(icon_size)
            except Exception: # pylint: disable=broad-except
                pass
        return img
    except Exception: # pylint: disable=broad-except
        pass
    try: # Gtk3 style with explicit IconSize constant
        img = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
        return img
    except Exception: # pylint: disable=broad-except
        pass
    return Gtk.Image() # Last resort: return an empty Image (no icon)

def image_from_file_scaled(path: str, size: int) -> Gtk.Widget:
    '''Load an image from a file and scale it'''
    pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
    if GTK_MAJOR >=4:
        # GTK4: use GtkPicture, which actually scales, GtkImage does not!
        texture = Gdk.Texture.new_for_pixbuf(pixbuf) # pylint: disable=c-extension-no-member
        pic = Gtk.Picture.new_for_paintable(texture) # pylint: disable=c-extension-no-member
        # or FIT
        pic.set_content_fit(Gtk.ContentFit.SCALE_DOWN) # pylint: disable=c-extension-no-member
        pic.set_size_request(size, size)
        return pic
    pixbuf = pixbuf.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
    return Gtk.Image.new_from_pixbuf(pixbuf)

def set_scrolled_shadow(widget: Gtk.ScrolledWindow, enable: bool = True) -> None:
    '''Add or remove css class `scrolled-shadow` to or from a scrolled window'''
    ctx = widget.get_style_context()
    if enable:
        ctx.add_class('scrolled-shadow')
    else:
        ctx.remove_class('scrolled-shadow')

def combobox_set_active(
    combobox: Gtk.ComboBox,
    liststore: Gtk.ListStore,
    index: Optional[int],
) -> None:
    '''Set the active index of a combo box with a list store (GTK 3/4 compatible).
    If `index` is `None`, unset the active item.'''
    if index is None:
        # Unset the active item
        combobox.set_active_iter(None)
        return
    if GTK_MAJOR >=4:
        liststore_iter = liststore.get_iter((index,))
        combobox.set_active_iter(liststore_iter)
        return
    combobox.set_active(index)

def get_toplevel_window(widget: Gtk.Widget) -> Gtk.Window:
    '''Get the top-level window of a widget (GTK 3/4 compatible)'''
    if GTK_MAJOR >=4:
        return widget.get_root()
    return widget.get_toplevel()

def connect_focus_signal(widget: Gtk.Widget, callback: Callable[..., Any]) -> None:
    '''
    Connects a callback to the appropriate focus signal for a widget,
    automatically handling differences between GTK3 and GTK4.

    In Gtk4, the 'notify::has-focus' signal is used to detect when a widget receives focus.
    In Gtk3, the 'grab-focus' signal is used for the same purpose.

    :param widget: The widget to which the focus signal should be connected.
    :param callback: The callback function to be called when the widget receives focus.
                     The callback should accept the widget and a GParamSpec parameter in GTK4.
    :return: None
    '''
    if GTK_MAJOR >= 4:
        widget.connect('notify::has-focus', callback)
    else:
        widget.connect('grab-focus', callback)

def grab_focus_without_selecting(widget: Gtk.Widget) -> None:
    '''
    Grabs focus for a widget without selecting its contents.
    Works for both Gtk.Entry and Gtk.SpinButton in Gtk3 and Gtk4.

    :param widget: The widget to grab focus (Gtk.Entry or Gtk.SpinButton).
    '''
    if hasattr(widget, 'grab_focus_without_selecting'):  # Gtk3
        widget.grab_focus_without_selecting()
    else:  # Gtk4
        widget.grab_focus()
        if isinstance(widget, Gtk.Entry):
            widget.select_region(0, 0)
        # For Gtk.SpinButton in GTK4, there is no select_region method,
        # so we don't need to do anything else.

def set_entry_text_preserve_cursor(entry: Gtk.Entry, new_text: str) -> None:
    '''Set the text of a Gtk.Entry while preserving the cursor position
    (Gtk 3/4 compatible)'''
    cursor_pos = entry.get_position()
    entry.set_text(new_text)
    if cursor_pos <= len(new_text):
        entry.set_position(cursor_pos)
        return
    entry.set_position(-1)

def get_window_size(window: Gtk.Window) -> Tuple[int, int]:
    '''Get the size of a window (Gtk 3/4 compatible)'''
    if GTK_MAJOR >=4:
        return (window.get_width(), window.get_height())
    return cast(Tuple[int, int], window.get_size())

def get_treeview_context(
        treeview: Gtk.TreeView,
        x: int,
        y: int,
        keyboard_tip: bool,
    ) -> Tuple[bool, Optional[Gtk.TreeModel], Optional[Gtk.TreePath], Optional[Gtk.TreeIter]]:
    '''
    Unified GTK3/Gtk4 wrapper around TreeView.get_tooltip_context()

    Returns:
        (ok, model, path, iter)

    Works with:
      • Gtk3 (returns 6-tuple in PyGObject)
      • Gtk4 <= 4.10 (returns 5-tuple)
      • Gtk4 >= 4.12 (returns 4-tuple)
    '''

    result = treeview.get_tooltip_context(x, y, keyboard_tip)
    if not result:
        return False, None, None, None

    if GTK_MAJOR < 4:
        # Gtk3 → always: is_row, x, y, model, path, iter
        is_row, _x, _y, model, path, itr = result
        if not is_row:
            return False, None, None, None
        return True, model, path, itr
    # GTK 4.x messy variants
    length = len(result)
    # Variant A: (is_row, x, y, iter)
    # Seen in some GTK 4.10+ builds
    if length == 4 and isinstance(result[3], Gtk.TreeIter):
        is_row, _x, _y, itr = result
        if not is_row:
            return False, None, None, None
        model = treeview.get_model()
        if model is None:
            return False, None, None, None
        path = model.get_path(itr)
        if path is None:
            return False, None, None, None
        return True, model, path, itr
    # Variant B: (is_row, x, y, path)
    if length == 4 and isinstance(result[3], Gtk.TreePath):
        is_row, _x, _y, path = result
        if not is_row:
            return False, None, None, None
        model = treeview.get_model()
        if model is None or path is None:
            return False, None, None, None
        itr = model.get_iter(path)
        if itr is None:
            return False, None, None, None
        return True, model, path, itr
    # Variant C: (is_row, x, y, model, path)
    if length == 5:
        is_row, _x, _y, model, path = result
        if not is_row or model is None or path is None:
            return False, None, None, None
        itr = model.get_iter(path)
        if itr is None:
            return False, None, None, None
        return True, model, path, itr
    # Unexpected format
    return False, None, None, None

@overload
def connect_fast_click( # GTK 3: 'clicked' → callback(button)
    button: Gtk.Widget,
    callback: Callable[[Gtk.Button], Any],
) -> None:
    ...

@overload
def connect_fast_click( # GTK 4: 'pressed' → callback(gesture, n_press, x, y)
    button: Gtk.Widget,
    callback: Callable[['Gtk.GestureClick', int, float, float], Any], # pylint: disable=c-extension-no-member
) -> None:
    ...

def connect_fast_click(
    button: Gtk.Widget,
    callback: Callable[..., Any],
) -> None:
    '''
    Connect a 'fast click' handler that preserves Gtk3/Gtk4 signal signatures.

    Unified implementation, the ovrload above are for precise type checking.

    Gtk 3:
        Connects to 'clicked', which emits (button)

    Gtk 4:
        Creates a GtkGestureClick, connects to 'pressed', which emits
        (gesture, n_press, x, y)

    The callback signature is preserved exactly, and type checkers
    will infer the correct signature depending on use.
    '''
    if GTK_MAJOR >=4:
        gesture = Gtk.GestureClick() # pylint: disable=c-extension-no-member
        gesture.set_button(0)
        gesture.connect(
            'pressed',
            callback,  # type checkers understand the expected signature
        )
        button.add_controller(gesture)
    else:
        # The 'clicked' signal passes a Gtk.Button instance
        button.connect(
            'clicked',
            callback,  # type checkers know this expects (button)
        )

def set_monospace(label: Gtk.Label) -> None:
    '''Make label use a monospace font (Gtk3 + Gtk4 compatible).'''
    font = Pango.FontDescription('Monospace')
    if GTK_MAJOR < 4:
        label.modify_font(font)
    else:
        attr = Pango.attr_font_desc_new(font)
        attrs = Pango.AttrList()
        attrs.insert(attr)
        label.set_attributes(attrs)

def _add_details_section(parent_box: Gtk.Box, details_text: str) -> None:
    '''
    Adds an expander containing details_text (monospace, scrollable)
    and a copy-to-clipboard button.

    Works in Gtk3 and Gtk4.
    '''

    if not details_text:
        return

    # Horizontal box: [▶ Details]     [Copy]
    header_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
    add_child(parent_box, header_box)
    header_box.set_halign(Gtk.Align.FILL)
    header_box.set_hexpand(True)
    expander = Gtk.Expander(label='Details')
    expander.set_expanded(False)
    add_child(header_box, expander)
    spacer = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
    add_child(header_box, spacer)
    spacer.set_hexpand(True)
    copy_btn = Gtk.Button(label='Copy')
    copy_btn.set_tooltip_text('Copy details to clipboard')
    add_child(header_box, copy_btn)

    def _on_copy_clicked(_: Gtk.Button) -> None:
        if GTK_MAJOR < 4:
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(details_text, -1)
        else:
            display = Gdk.Display.get_default() # pylint: disable=no-value-for-parameter
            clipboard = display.get_clipboard()
            clipboard.set_text(details_text)

    copy_btn.connect('clicked', _on_copy_clicked)
    scroll = Gtk.ScrolledWindow()
    scroll.set_hexpand(True)
    scroll.set_vexpand(True)
    label = Gtk.Label()
    label.set_xalign(0)
    label.set_yalign(0)
    label.set_selectable(True)
    label.set_use_markup(False)
    label.set_text(details_text)
    label.set_margin_top(4)
    label.set_margin_bottom(4)
    label.set_margin_start(4)
    label.set_margin_end(4)
    label.set_justify(Gtk.Justification.LEFT)
    label.set_max_width_chars(80)
    set_label_wrap_mode(label, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
    set_monospace(label)
    add_child(scroll, label)
    add_child(expander, scroll)

def get_preferred_width(widget: Gtk.Widget) -> Tuple[int, int]:
    '''
    Return (minimum, natural) width of a widget in a Gtk3/Gtk4 compatible way.
    '''
    if GTK_MAJOR < 4:
        return tuple(widget.get_preferred_width())
    min_size, nat_size, _, _ = widget.measure(Gtk.Orientation.HORIZONTAL, -1)
    return min_size, nat_size


def get_preferred_height(widget: Gtk.Widget) -> Tuple[int, int]:
    '''
    Return (minimum, natural) height of a widget in a Gtk3/Gtk4 compatible way.
    '''
    if GTK_MAJOR < 4:
        return tuple(widget.get_preferred_height())
    min_size, nat_size, _, _ = widget.measure(Gtk.Orientation.VERTICAL, -1)
    return min_size, nat_size

def forward_key_event_to_entry(event_key: 'Gdk.EventKey', entry: 'Gtk.Entry') -> bool:
    '''
    Forward a Gdk.EventKey into a Gtk.Entry (or Gtk.SearchEntry) in a way
    compatible with both GTK3 and GTK4.

    Handles:
      - character insertion
      - Backspace
      - Delete
      - Left/Right/Home/End cursor movement
    '''
    keyval = event_key.keyval
    text = event_key.string or ''
    pos = entry.get_position()
    # Special keys
    if keyval == Gdk.KEY_BackSpace:
        if pos > 0:
            entry.delete_text(pos - 1, pos)
            entry.set_position(pos - 1)
        return True
    if keyval == Gdk.KEY_Delete:
        entry.delete_text(pos, pos + 1)
        entry.set_position(pos)
        return True
    if keyval == Gdk.KEY_Left:
        if pos > 0:
            entry.set_position(pos - 1)
        return True
    if keyval == Gdk.KEY_Right:
        if pos < len(entry.get_text()):
            entry.set_position(pos + 1)
        return True
    if keyval == Gdk.KEY_Home:
        entry.set_position(0)
        return True
    if keyval == Gdk.KEY_End:
        entry.set_position(len(entry.get_text()))
        return True
    if text: # Normal text insertion:
        entry.insert_text(text, pos)
        entry.set_position(pos + len(text))
        return True
    return False # Let GTK handle anything else

class PopupKind(Enum):
    '''Enumerate the different possible types of popovers'''
    EMOJI_SELECTED = auto()
    SKIN_TONE = auto()
    EMOJI_INFO = auto()
    FONT_SELECTION = auto()
    MAIN_MENU = auto()
    ADD_DICTIONARY = auto()
    ADD_INPUT_METHOD = auto()
    INPUT_METHOD_OPTIONS = auto()
    ADD_AUTOSETTING = auto()

class PopupManager:
    '''
    Manages Gtk.Popover lifetimes safely across GTK3/GTK4.
    Tracks which kind of popup is currently active.
    '''
    def __init__(self) -> None:
        self._current: Optional[Gtk.Popover] = None
        self._kind: Optional[PopupKind] = None

    def popup(self, popover: Gtk.Popover, kind: PopupKind) -> None:
        '''
        Safely popup a popover after.
        If an old popover exists, pop it down first.

        This avoids GTK4 grab violations ('Tried to map a grabbing popup...')
        and works correctly on Wayland.
        '''
        old = self._current
        self._current = popover
        self._kind = kind
        if old is not None:
            self._popdown(old)

        def _popup_later() -> bool:
            if self._current is not popover:
                return False
            if GTK_VERSION >= (3, 22, 0):
                popover.popup()
            show_all(popover)
            return False

        GLib.idle_add(_popup_later)

    def popdown_current(self, kind: Optional[PopupKind] = None) -> None:
        '''Pops down the current popover if it is of the specified kind

        If kind is None, popdown the current popover no matter what kind it is.
        '''
        if kind is not None and self._kind != kind:
            return
        if self._current is not None:
            self._popdown(self._current)
            self._current = None
            self._kind = None

    def _popdown(self, popover: Gtk.Popover) -> None: # pylint: disable=no-self-use
        if GTK_VERSION >= (3, 22, 0):
            popover.popdown()
        popover.set_visible(False)

    def active_popup(self) -> Optional[PopupKind]:
        '''Returns the kind of the currently active popup, or None.'''
        return self._kind

    def is_active(self, kind: PopupKind) -> bool:
        '''Returns True if the given popup kind is currently active.'''
        return self._kind == kind

def create_popover(
        pointing_to: Gtk.Widget,
        position: Optional['Gtk.PositionType'] = None,
) -> Gtk.Popover:
    '''
    Create a Gtk.Popover correctly for both GTK3 and GTK4.

    - Gtk3: uses set_relative_to()
    - Gtk4: sets toplevel parent + pointing rectangle via compute_bounds()

    This helper avoids common Gtk4 pitfalls such as:
    - non-topmost parent warnings
    - grabbing popup freezes (Wayland)
    '''
    popover = Gtk.Popover()
    if GTK_MAJOR >= 4:
        toplevel = pointing_to.get_root()
        if toplevel is None:
            raise RuntimeError(
                'create_popover(): pointing_to widget has no root yet')
        popover.set_parent(toplevel)
        ok, grect = pointing_to.compute_bounds(toplevel)
        if ok:
            gdk_rect = Gdk.Rectangle()
            gdk_rect.x = int(grect.origin.x)
            gdk_rect.y = int(grect.origin.y)
            gdk_rect.width = int(grect.size.width)
            gdk_rect.height = int(grect.size.height)
            popover.set_pointing_to(gdk_rect)
    else:
        popover.set_relative_to(pointing_to)
    if position is not None:
        popover.set_position(position)
    return popover

def clickable_event_box_compat_get_gtk_label(
        event_box: 'ClickableEventBoxCompat') -> Gtk.Label:
    '''Returns the Gtk.Label child of a ClickableEventBoxCompat'''
    if GTK_MAJOR < 4:
        return event_box.get_child()
    return event_box.get_first_child()

def emoji_flowbox_get_labels(flowbox: Gtk.FlowBox) -> List[Gtk.Label]:
    '''Returns a list of (emoji)-labels in a Gtk.FlowBox as used in emoji_picker.py
    Compatible with both Gtk3 and Gtk4.
    '''
    if hasattr(flowbox, 'get_children'): # Gtk3
        # FlowBoxChild -> EventBox -> Label
        return [child.get_child().get_child() for child in flowbox.get_children()]
    # Gtk4: FlowBoxChild -> Box -> Label
    return [child.get_child().get_first_child() for child in children_of(flowbox)]

class ClickableEventBoxCompat(Gtk.Box if GTK_MAJOR >= 4 else Gtk.EventBox): # type: ignore[misc]
    '''
    A compatibility wrapper that provides EventBox-like clickable behavior
    in both Gtk3 and Gtk4, including unified signals:

        - 'clicked'      → callback(widget, button)
        - 'released'     → callback(widget, button)
        - 'long-pressed' → callback(widget)

    All differences between Gtk3 and Gtk4 event handling are hidden here.
    '''
    def __init__(self) -> None:
        if GTK_MAJOR < 4: # Gtk3 mode (Gtk.EventBox)
            super().__init__()
            self.set_above_child(True)
            self.set_can_focus(False)
            self.set_visible_window(True)
            self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                            Gdk.EventMask.BUTTON_RELEASE_MASK)
        else: # Gtk4 mode (Gtk.Box)
            super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
            self.set_sensitive(True)
            click = Gtk.GestureClick()  # pylint: disable=c-extension-no-member
            click.set_button(0)  # accept all buttons
            click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            click.connect('pressed', self._on_click_pressed)
            click.connect('released', self._on_click_released)
            self.add_controller(click) # pylint: disable=no-member
            longpress = Gtk.GestureLongPress()  # pylint: disable=c-extension-no-member
            longpress.set_touch_only(False)
            longpress.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            longpress.connect('pressed', self._on_longpress_gtk4)
            self.add_controller(longpress) # pylint: disable=no-member
        # Unified signal slots
        self._click_handlers: List[Tuple[ClickCallback, Tuple[Any, ...]]] = []
        self._release_handlers: List[Tuple[ReleaseCallback, Tuple[Any, ...]]] = []
        self._longpress_handlers: List[Tuple[LongPressCallback, Tuple[Any, ...]]] = []
        # Internal long-press tracking (Gtk3)
        self._gtk3_longpress_timer: Optional[int] = None
        self._gtk3_button_down: bool = False

    # Unified 'connect' interface
    def connect( # pylint: disable=arguments-differ
            self, signal_name: str, callback: Callable[..., Any], *user_data: Any,
    ) -> int:
        '''
        A unified connect() that works for all 3 events on
        Gtk3 and Gtk4 equally.
        '''
        if signal_name == 'clicked':
            self._click_handlers.append((callback, user_data))
            return 1
        if signal_name == 'released':
            self._release_handlers.append((callback, user_data))
            return 1
        if signal_name == 'long-pressed':
            self._longpress_handlers.append((callback, user_data))
            return 1
        return cast(int, super().connect(signal_name, callback, *user_data))

    if GTK_MAJOR < 4:
        def do_button_press_event(  # pylint: disable=arguments-differ
                self, event_button: 'Gdk.EventButton') -> bool:
            '''GTK3 button press → triggers click + schedules long press.'''
            button: int = event_button.button
            LOGGER.info('Gtk3 do_button_press_event button=%s', button)
            self._gtk3_button_down = True
            # Long press only for button 1 — matches GTK4 behaviour
            if button == 1:
                self._gtk3_longpress_timer = GLib.timeout_add(
                    500, self._gtk3_longpress_trigger)  # 500ms
            else:
                self._gtk3_longpress_timer = None
            for cb, user in self._click_handlers:
                cb(self, button, *user)
            return False

        def do_button_release_event(  # pylint: disable=arguments-differ
                self, event_button: 'Gdk.EventButton') -> bool:
            '''GTK3 button release → triggers release, cancels long press.'''
            button: int = event_button.button
            LOGGER.info('Gtk3 do_button_release_event button=%s', button)
            if self._gtk3_longpress_timer is not None:
                GLib.source_remove(self._gtk3_longpress_timer)
                self._gtk3_longpress_timer = None
            self._gtk3_button_down = False
            for cb, user in self._release_handlers:
                cb(self, button, *user)
            return False

        def _gtk3_longpress_trigger(self) -> bool:
            '''Timer callback for GTK3 long press.'''
            if self._gtk3_button_down:
                for cb, user in self._longpress_handlers:
                    cb(self, *user)
            self._gtk3_longpress_timer = None
            return False  # run once

    else:  # Gtk4 event handling
        def _on_click_pressed(
                self, gesture: 'Gtk.GestureClick', _n_press: int, _x: float, _y: float,
        ) -> None:
            button = gesture.get_current_button()
            for cb, user in self._click_handlers:
                cb(self, button, *user)

        def _on_click_released(
                self, gesture: 'Gtk.GestureClick', _n_press: int, _x: float, _y: float,
        ) -> None:
            button = gesture.get_current_button()
            for cb, user in self._release_handlers:
                cb(self, button, *user)

        def _on_longpress_gtk4(
                self, _gesture: 'Gtk.GestureLongPress', _x: float, _y: float,
        ) -> None:
            for cb, user in self._longpress_handlers:
                cb(self, *user)

class FakeEventKey: # pylint: disable=too-few-public-methods
    '''
    Minimal stand-in for Gdk.EventKey when running under GTK4.

    GTK3 delivers key-press-event callbacks with a Gdk.EventKey instance,
    which provides attributes such as .keyval, .hardware_keycode, .state,
    and .string.

    GTK4 does NOT provide Gdk.EventKey. Instead, Gtk.EventControllerKey
    emits (keyval, keycode, state) parameters. This class reconstructs
    the small subset of a GTK3 GdkEventKey that EmojiPickerUI expects,
    allowing the existing GTK3 key handling logic to run unchanged.
    '''
    def __init__(self, keyval: int, keycode: int, state: 'Gdk.ModifierType') -> None:
        self.keyval: int = keyval
        self.hardware_keycode: int = keycode
        self.state: 'Gdk.ModifierType' = state
        uc: int = Gdk.keyval_to_unicode(keyval)
        self.string: str = chr(uc) if uc else ''
        self.time: int = 0
        self.group: int = 0
        self.is_modifier: bool = False

class HeaderBarCompat(Gtk.HeaderBar): # type: ignore[misc]
    '''
    A GTK3/GTK4-compatible HeaderBar with working set_title(), set_subtitle()
    '''
    def __init__(self) -> None:
        super().__init__()
        if GTK_MAJOR >= 4:
            self.set_show_title_buttons(True) # pylint: disable=no-member
        else:
            self.set_show_close_button(True)
        self._title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._title_box.set_spacing(0 if GTK_MAJOR >= 4 else 1)
        self._title_box.set_halign(Gtk.Align.CENTER)
        self._title_box.set_valign(Gtk.Align.CENTER)
        self._title_box.set_hexpand(True)
        self._title_label = Gtk.Label()
        self._subtitle_label = Gtk.Label()
        for label in (self._title_label, self._subtitle_label):
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_hexpand(False)
            label.set_halign(Gtk.Align.CENTER)
            label.set_xalign(0.5)
            if GTK_MAJOR >= 4:
                self._title_box.append(label)
            else:
                self._title_box.pack_start(label, False, False, 0)
        if GTK_MAJOR >= 4:
            self.set_title_widget(self._title_box) # pylint: disable=no-member
        # Better do NOT use set_custom_title() for GTK3, because
        # native implementation is superior

    def set_title(self, text: str) -> None:  # pylint: disable=arguments-differ
        '''
        Set the header bar title (rendered bold). Empty string clears the title.
        Escaped using GLib.markup_escape_text().
        '''
        if GTK_MAJOR < 4:
            super().set_title(text)
            return
        escaped = GLib.markup_escape_text(text) if text else ''
        if escaped:
            self._title_label.set_markup(f'<b>{escaped}</b>')
            return
        self._title_label.set_text('')

    def set_subtitle(self, text: str) -> None:  # pylint: disable=arguments-differ
        '''
        Set the header bar subtitle (smaller text). Empty string clears it.
        Escaped using GLib.markup_escape_text().
        '''
        if GTK_MAJOR < 4:
            super().set_subtitle(text)
            return
        escaped = GLib.markup_escape_text(text) if text else ''
        if escaped:
            self._subtitle_label.set_markup(f'<small>{escaped}</small>')
            return
        self._subtitle_label.set_text('')

class MessageDialogCompat: # pylint: disable=too-few-public-methods
    '''
    Gtk3/Gtk4-compatible informational / warning / error dialog.

    Usage:
        MessageDialogCompat(
            parent=self,
            message='Operation completed successfully!',
            message_type=Gtk.MessageType.INFO,
            details='Stack trace or additional error details...',
            details_label='Details',
            title='Information',
            button_label='OK',
            on_close: close_function,
        ).show()
    '''

    ICONS = {
        Gtk.MessageType.INFO: 'dialog-information',
        Gtk.MessageType.WARNING: 'dialog-warning',
        Gtk.MessageType.ERROR: 'dialog-error',
        Gtk.MessageType.QUESTION: 'dialog-question',
        Gtk.MessageType.OTHER: 'dialog-information',
    }

    def __init__(
        self,
        *,
        parent: Optional[Gtk.Widget] = None,
        message: str,
        message_type: Gtk.MessageType = Gtk.MessageType.INFO,
        details: Optional[str] = None,
        details_label: str = 'Details',
        title: Optional[str] = None,
        button_label: str = '_OK',
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        self.parent = parent
        self.message = message
        self.message_type = message_type
        self.details = details
        self.details_label = details_label
        self.title = title or ''
        self.button_label = button_label
        self.on_close = on_close
        self.dialog = Gtk.Dialog(
            title=self.title,
            transient_for=self.parent,
            modal=True,
        )
        self.dialog.add_button(self.button_label, Gtk.ResponseType.OK)

        self._build_content()

    def _build_content(self) -> None:
        '''Builds the dialog UI for Gtk3 + Gtk4.'''
        content_area = self.dialog.get_content_area()
        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        outer.set_margin_top(12)
        outer.set_margin_bottom(12)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        icon_name = self.ICONS.get(self.message_type, 'dialog-information')
        if GTK_MAJOR >= 4:
            image = Gtk.Image.new_from_icon_name(icon_name)
            # add some reasonable sizing — Gtk4 icons are symbolic
            image.set_pixel_size(48)
        else:
            image = Gtk.Image.new_from_icon_name(
                icon_name, Gtk.IconSize.DIALOG)
        add_child(outer, image)
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        label = Gtk.Label()
        label.set_markup(f'<b>{html.escape(self.message)}</b>')
        label.set_xalign(0)
        label.set_max_width_chars(40)
        set_label_wrap_mode(label, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        add_child(text_box, label)
        if self.details:
            _add_details_section(text_box, self.details)
        add_child(outer, text_box)
        add_child(content_area, outer)
        show_all(content_area)

    def _on_response(self, dialog: Gtk.Dialog, _response: Gtk.ResponseType) -> None:
        dialog.destroy()
        if self.on_close:
            self.on_close()

    def show(self) -> None:
        '''
        Gtk3:
            Uses dialog.run() (blocks)
        Gtk4:
            Emulates run() by spinning a temporary GLib main loop
            until a response is received.
        '''
        if GTK_MAJOR < 4:
            response = self.dialog.run()
            self._on_response(self.dialog, response)
            return
        # Gtk4: emulate a blocking run()
        loop = GLib.MainLoop()

        def on_response(dialog: Gtk.Dialog, _response: Gtk.ResponseType) -> None:
            dialog.destroy()
            if self.on_close:
                self.on_close()
            loop.quit()

        self.dialog.connect("response", on_response)
        self.dialog.present()
        # Block until on_response calls loop.quit()
        loop.run()

class ConfirmDialogCompat: # pylint: disable=too-few-public-methods
    '''
    A Gtk3/Gtk4 compatible confirmation dialog with asynchronous callbacks.

    Usage:
        dlg = ConfirmDialogCompat(
            parent=self,
            question='Delete everything?',
            title='Confirm',
            ok_label='_OK',
            cancel_label='_Cancel',
            on_ok=callback,
            on_cancel=cancel_callback,
        )
        dlg.show()
    '''
    def __init__(
        self,
        *,
        parent: Gtk.Widget,
        question: str,
        title: str = 'Are you sure?',
        ok_label: str = '_OK',
        cancel_label: str = '_Cancel',
        on_ok: Optional[ResponseCallback] = None,
        on_cancel: Optional[ResponseCallback] = None,
    ) -> None:
        self.parent = parent
        self.question = question
        self.title = title
        self.ok_label = ok_label
        self.cancel_label = cancel_label
        self.on_ok = on_ok
        self.on_cancel = on_cancel
        self.dialog = Gtk.Dialog(
            title=self.title,
            transient_for=self.parent,
            modal=True,
        )
        self.dialog.add_button(self.cancel_label, Gtk.ResponseType.CANCEL)
        self.dialog.add_button(self.ok_label, Gtk.ResponseType.OK)
        self._add_message_label()

    def _add_message_label(self) -> None:
        '''Internal: add message label to content area, with wrapping + markup.'''
        box = self.dialog.get_content_area()

        label = Gtk.Label()
        label.set_markup(
            f'<span size="large" color="#ff0000"><b>{html.escape(self.question)}</b></span>'
        )
        label.set_max_width_chars(40)
        label.set_xalign(0)
        set_label_wrap_mode(
            label, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        margin = 10
        label.set_margin_start(margin)
        label.set_margin_end(margin)
        label.set_margin_top(margin)
        label.set_margin_bottom(margin)
        add_child(box, label)
        show_all(box)

    def _on_response(self, dialog: Gtk.Dialog, response_id: Gtk.ResponseType) -> None:
        '''Internal: Handles both Gtk3 and Gtk4 dialog results identically.'''
        dialog.destroy()
        if response_id == Gtk.ResponseType.OK:
            if self.on_ok:
                self.on_ok()
            return
        if self.on_cancel:
            self.on_cancel()

    def show(self) -> None:
        '''
        Gtk3:
            Blocks internally (dialog.run())
            Then triggers callbacks
        Gtk4:
            Fully asynchronous
        '''
        if GTK_MAJOR < 4:
            response = self.dialog.run() # Blocking
            self._on_response(self.dialog, response)
            return
        self.dialog.connect('response', self._on_response)
        self.dialog.present() # Non-blocking

class CompatButton(Gtk.Button): # type: ignore[misc]
    '''
    A Gtk.Button subclass that behaves like Gtk4's Gtk.Button even on Gtk3.
    Supports:
        - label=
        - child=
        - icon_name=
        - tooltip_text=
        - Gtk4 construction semantics
        - set_label() to update the label later

    If the button gets a label, use_markup is always set to True for the label.
    '''
    def __init__(
        self,
        label: Optional[str] = None,
        child: Optional[Gtk.Widget] = None,
        icon_name: Optional[str] = None,
        tooltip_text: Optional[str] = None,
        use_underline: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        # Call base constructor with only safe kwargs
        # Gtk4 will accept css_classes, css_name etc.
        super().__init__(**kwargs)
        self._label_widget: Optional[Gtk.Label] = None
        self._box: Optional[Gtk.Box] = None
        if child is not None:
            add_child(self, child)
        else:
            if label is not None or icon_name is not None:
                self._setup_common(label, icon_name, use_underline)
        if tooltip_text:
            self.set_tooltip_text(tooltip_text)

    def _setup_common(
        self,
        label: Optional[str],
        icon_name: Optional[str],
        use_underline: Optional[bool],
    ) -> None:
        self._box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        if icon_name is not None:
            if GTK_MAJOR >= 4:
                image = Gtk.Image.new_from_icon_name(icon_name)
                image.set_pixel_size(16)  # Default size
            else:
                image = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
            add_child(self._box, image)
        if label is not None:
            self._label_widget = Gtk.Label(label=label, use_markup=True)
            if use_underline is not None:
                self._label_widget.set_text_with_mnemonic(label)
            add_child(self._box, self._label_widget)
        add_child(self, self._box)

    def set_label(self, text: str) -> None: # pylint: disable=arguments-differ
        '''Set or update the label of the button.'''
        if self._label_widget is not None:
            self._label_widget.set_label(text)

def choose_file_open(
        *,
        parent: Gtk.Widget,
        title: Optional[str] = None,
        initial_folder: Optional[str] = None,
) -> Optional[str]:
    '''
    Cross-GTK3/Gtk4 file-open dialog.
    Blocks in Gtk3, async but wrapped to block in Gtk4.
    Returns the selected filename or None.
    '''
    if title is None:
        title = _('Open File ...')

    if GTK_MAJOR < 4:
        dialog = Gtk.FileChooserDialog(
            title=title,
            parent=parent,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("_OK", Gtk.ResponseType.OK)
        if initial_folder:
            try:
                dialog.set_current_folder(initial_folder)
            except Exception: # pylint: disable=broad-exception-caught
                pass  # Ignore invalid paths
        response = dialog.run()
        filename = None
        if response == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
        dialog.destroy()
        return filename

    # Gtk4: Use new async Gtk.FileDialog
    file_dialog = Gtk.FileDialog() # pylint: disable=c-extension-no-member
    file_dialog.set_title(title)
    if initial_folder:
        # NOTE: Gtk.FileDialog uses GFile for folders
        gfile = Gio.File.new_for_path(initial_folder)
        file_dialog.set_initial_folder(gfile)

    loop = GLib.MainLoop()
    result: Optional[str] = None

    def on_finish(
            dialog: Gtk.FileDialog, # pylint: disable=c-extension-no-member
            task: Gio.AsyncResult,
    ) -> None:
        nonlocal result
        try:
            gfile = dialog.open_finish(task)
            if gfile:
                result = gfile.get_path()
        except GLib.Error:
            result = None
        finally:
            loop.quit()

    file_dialog.open(parent, None, on_finish)
    loop.run()
    return result
