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
import gettext
from gi import require_version
require_version('GLib', '2.0')
require_version('Gio', '2.0')
# pylint: disable=wrong-import-position
from gi.repository import GLib # type: ignore
from gi.repository import Gio # type: ignore
from gi.repository import GdkPixbuf # type: ignore
from gi.repository import Pango # type: ignore
from itb_gtk import Gdk, Gtk, GTK_MAJOR # type: ignore
# pylint: enable=wrong-import-position
if TYPE_CHECKING:
    # These imports are only for type checkers (mypy). They must not be
    # executed at runtime because itb_gtk controls the Gtk/Gdk versions.
    # pylint: disable=reimported
    from gi.repository import Gtk, Gdk  # type: ignore
    # pylint: enable=reimported
ResponseCallback = Callable[[], None]

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

def grab_focus_without_selecting(entry: Gtk.Entry) -> None:
    '''Gtk4 does not have grab_focus_without_selecting'''
    if hasattr(entry, "grab_focus_without_selecting"): # Gtk3
        entry.grab_focus_without_selecting()
    else: # Gtk4
        entry.grab_focus()
        entry.select_region(0, 0)

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
        self._is_gtk4 = GTK_MAJOR >= 4
        # Call base constructor with only safe kwargs
        # Gtk4 will accept css_classes, css_name etc.
        super().__init__(**kwargs)
        if child is None:
            if label is not None:
                child = Gtk.Label(label=label, use_markup=True)
                if use_underline is not None:
                    child.set_text_with_mnemonic(label)
            elif icon_name is not None:
                if self._is_gtk4:
                    child = Gtk.Image.new_from_icon_name(icon_name)
                else:
                    child = Gtk.Image.new_from_icon_name(icon_name,
                                                         Gtk.IconSize.BUTTON)
        if child is not None:
            if self._is_gtk4:
                self.set_child(child) # pylint: disable=no-member
            else:
                self.add(child) # pylint: disable=no-member
        if tooltip_text:
            self.set_tooltip_text(tooltip_text)

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
