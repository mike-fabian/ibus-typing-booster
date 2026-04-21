# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2013-2026 Mike FABIAN <mfabian@redhat.com>
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
Gui utility functions used in ibus-typing-booster

This module contains utility functions using Gtk or Gdk or doing
something with a display. Other utility functions which do not need
that should go into the itb_util_core module.
'''
from typing import Any
from typing import Tuple
from typing import List
from typing import Dict
from typing import Set
from typing import Optional
from typing import TYPE_CHECKING
# pylint: disable=wrong-import-position
import sys
from enum import Enum, Flag
import os
import functools
import logging
import shutil
import subprocess
import gettext
from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus
require_version('GLib', '2.0')
from gi.repository import GLib # type: ignore
from itb_gtk import Gdk, Gtk, GTK_MAJOR, GTK_VERSION # type: ignore
# For static type checking only: import real GI modules so mypy can resolve
if TYPE_CHECKING:
    # These imports are only for type checkers (mypy). They must not be
    # executed at runtime because itb_gtk controls the Gtk/Gdk versions.
    # pylint: disable=reimported
    from gi.repository import Gtk, Gdk  # type: ignore
    # pylint: enable=reimported
# pylint: enable=wrong-import-position

import itb_version
from itb_util_core import KEYBINDING_STATE_MASK

try:
    # Enable new improved regex engine instead of backwards compatible
    # v0.  regex.match('ß', 'SS', regex.IGNORECASE) matches only with
    # the improved version!  See also: https://pypi.org/project/regex/
    import regex # type: ignore
    regex.DEFAULT_VERSION = regex.VERSION1
    re = regex
    USING_REGEX = True
except ImportError:
    # Use standard “re” module as a fallback:
    import re
    USING_REGEX = False

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

@functools.lru_cache(maxsize=None)
def detect_terminal(input_purpose: int, im_client: str) -> bool:
    '''Detect whether the focus is on a terminal

    Checks input purpose first and if that is not set to TERMINAL,
    checks the program name in im_client to guess whether it is
    a terminal.
    '''
    if input_purpose in [InputPurpose.TERMINAL.value]:
        return True
    if not im_client:
        return False
    terminal_regexps = [
        '^xim:xterm:',
        '^QIBusInputContext:konsole:',
        '^xim:rxvt:',
        '^xim:urxvt:',
    ]
    for regexp in terminal_regexps:
        if re.compile(regexp).search(im_client):
            return True
    return False

def color_string_to_argb(color_string: str) -> int:
    '''
    Converts a color string to a 32bit  ARGB value

    :param color_string: The color to convert to 32bit ARGB
                         Can be expressed in the following ways:
                             - Standard name from the X11 rgb.txt
                             - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                          or ”#rrrrggggbbbb”
                             - RGB color: “rgb(r,g,b)”
                             - RGBA color: “rgba(r,g,b,a)”

    Examples:

    >>> print('%x' %color_string_to_argb('rgb(0xff, 0x10, 0x25)'))
    ffff1025

    >>> print('%x' %color_string_to_argb('#108040'))
    ff108040

    >>> print('%x' %color_string_to_argb('#fff000888'))
    ffff0088

    >>> print('%x' %color_string_to_argb('#ffff00008888'))
    ffff0088

    >>> print('%x' %color_string_to_argb('rgba(0xff, 0x10, 0x25, 0.5)'))
    7fff1025
    '''
    gdk_rgba = Gdk.RGBA()
    gdk_rgba.parse(color_string)
    return (((int(gdk_rgba.alpha * 0xff) & 0xff) << 24)
            + ((int(gdk_rgba.red * 0xff) & 0xff) << 16)
            + ((int(gdk_rgba.green * 0xff) & 0xff) << 8)
            + (int(gdk_rgba.blue * 0xff) & 0xff))

def get_primary_selection_text() -> str:
    '''Get the primary selection text'''
    if os.environ.get('XDG_SESSION_TYPE', '').lower() == 'x11':
        xclip_binary = shutil.which('xclip')
        if xclip_binary:
            try:
                result = subprocess.run(
                    [xclip_binary,
                     '-out', '-selection', 'primary', '-target', 'UTF8_STRING'],
                    capture_output=True,
                    text=True,
                    check=True)
                if result.stdout.strip():
                    LOGGER.info('Got primary selection with xclip.')
                    return result.stdout.strip()
            except Exception as xclip_error: # pylint: disable=broad-except
                LOGGER.exception('xclip failed: %s', xclip_error)
                return ''
        xsel_binary = shutil.which('xsel')
        if xsel_binary:
            try:
                result = subprocess.run(
                    [xsel_binary, '-p', '-o'],
                    capture_output=True,
                    text=True,
                    check=True)
                if result.stdout.strip():
                    LOGGER.info('Got primary selection with xsel.')
                    return result.stdout.strip()
            except Exception as xsel_error: # pylint: disable=broad-except
                LOGGER.exception('xsel failed: %s', xsel_error)
                return ''
    if os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland':
        wl_paste_binary = shutil.which('wl-paste')
        if wl_paste_binary:
            try:
                result = subprocess.run(
                    [wl_paste_binary, '-p'],
                    capture_output=True,
                    text=True,
                    check=True)
                if result.stdout.strip():
                    LOGGER.info('Got primary selection with wl-paste.')
                    return result.stdout.strip()
            except Exception as wl_paste_error: # pylint: disable=broad-except
                LOGGER.exception('wl-paste failed: %s', wl_paste_error)
                return ''
    # Run python helper script using Gtk4 to get the selection.
    try:
        result = subprocess.run(
            [sys.executable,
             os.path.join(os.path.dirname(__file__), 'get_clipboard_gtk4.py')],
            capture_output=True,
            text=True,
            check=True,
            timeout=1.0)
        if result.stdout.strip():
            LOGGER.info('Got primary selection with Gtk4.')
            return result.stdout.strip()
    except Exception as error: # pylint: disable=broad-except
        LOGGER.exception('Primary selection helper failed: %s', error)
    return ''

class InputPurpose(Enum):
    '''Compatibility class to handle InputPurpose the same way no matter
    what version of ibus is used.

    For example, older versions of ibus might not have
    IBus.InputPurpose.TERMINAL and then

        input_purpose == IBus.InputPurpose.TERMINAL

    will produce an exception. But when using this compatibility class

        input_purpose == InputPurpose.TERMINAL

    will just be False but not cause an exception.

    See also:

    https://docs.gtk.org/gtk3/enum.InputPurpose.html
    https://docs.gtk.org/gtk4/enum.InputPurpose.html

    Examples:

    >>> int(InputPurpose.PASSWORD)
    8

    >>> 8 == InputPurpose.PASSWORD
    True

    >>> int(InputPurpose.PIN)
    9

    >>> InputPurpose.PASSWORD <= InputPurpose.PIN
    True

    >>> InputPurpose.PASSWORD == Gtk.InputPurpose.PASSWORD
    True

    >>> InputPurpose.PASSWORD == IBus.InputPurpose.PASSWORD
    True
    '''
    def __new__(cls, attr: str) -> Any:
        obj = object.__new__(cls)
        if hasattr(Gtk, 'InputPurpose') and hasattr(Gtk.InputPurpose, attr):
            obj._value_ = int(getattr(Gtk.InputPurpose, attr))
        else:
            obj._value_ = -1
        return obj

    def __int__(self) -> int:
        return int(self._value_)

    def __eq__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputPurpose
            or other.__class__ is IBus.InputPurpose):
            return int(self) == int(other)
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) == other)
        return NotImplemented

    def __gt__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputPurpose
            or other.__class__ is IBus.InputPurpose):
            return int(self) > int(other)
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) > other)
        return NotImplemented

    def __lt__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputPurpose
            or other.__class__ is IBus.InputPurpose):
            return bool(int(self) < int(other))
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) < other)
        return NotImplemented

    def __ge__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputPurpose
            or other.__class__ is IBus.InputPurpose):
            return bool(int(self) >= int(other))
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) >= other)
        return NotImplemented

    def __le__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputPurpose
            or other.__class__ is IBus.InputPurpose):
            return bool(int(self) <= int(other))
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) <= other)
        return NotImplemented

    FREE_FORM = 'FREE_FORM'
    ALPHA = 'ALPHA'
    DIGITS = 'DIGITS'
    NUMBER = 'NUMBER'
    PHONE = 'PHONE'
    URL = 'URL'
    EMAIL = 'EMAIL'
    NAME = 'NAME'
    PASSWORD = 'PASSWORD'
    PIN = 'PIN'
    TERMINAL = 'TERMINAL'

class InputHints(Flag):
    '''Compatibility class to handle InputHints the same way no matter
    what version of ibus is used.

    For example, older versions of ibus might not have IBus.InputHints.PRIVATE
    (or maybe even do not have IBus.InputHints at all). Then

        input_hints & IBus.InputHints.PRIVATE

    will produce an exception. But when using this compatibility class

        input_hints & InputHints.PRIVATE

    will just be False but not cause an exception.

    See also:

    https://docs.gtk.org/gtk3/flags.InputHints.html
    https://docs.gtk.org/gtk4/flags.InputHints.html

    Examples:

    >>> int(InputHints.SPELLCHECK)
    1

    >>> InputHints.SPELLCHECK == 1
    True

    >>> InputHints.SPELLCHECK | 2
    3

    >>> 2 | InputHints.SPELLCHECK
    3

    >>> int(InputHints.NO_SPELLCHECK | InputHints.SPELLCHECK)
    3

    >>> 3 == InputHints.NO_SPELLCHECK | InputHints.SPELLCHECK
    True

    >>> 3 == InputHints.NO_SPELLCHECK | Gtk.InputHints.SPELLCHECK
    True

    >>> 3 == InputHints.NO_SPELLCHECK | IBus.InputHints.SPELLCHECK
    True

    >>> InputHints.SPELLCHECK == IBus.InputHints.SPELLCHECK
    True

    >>> InputHints.SPELLCHECK == Gtk.InputHints.SPELLCHECK
    True
    '''
    def __new__(cls, attr: str) -> Any:
        obj = object.__new__(cls)
        if hasattr(Gtk, 'InputHints') and hasattr(Gtk.InputHints, attr):
            obj._value_ = int(getattr(Gtk.InputHints, attr))
        else:
            obj._value_ = 0
        return obj

    def __int__(self) -> int:
        return int(self._value_)

    def __eq__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputHints
            or other.__class__ is IBus.InputHints):
            return bool(int(self) == int(other))
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) == other)
        return NotImplemented

    def __or__(self, other: Any) -> Any:
        if self.__class__ is other.__class__:
            return self.value | other.value
        if (other.__class__ is Gtk.InputHints
            or other.__class__ is IBus.InputHints):
            return int(self) | int(other)
        if other.__class__ is int:
            return int(self) | other
        return NotImplemented

    def __ror__(self, other: Any) -> Any:
        return self.__or__(other)

    def __and__(self, other: Any) -> Any:
        if self.__class__ is other.__class__:
            return self.value & other.value
        if (other.__class__ is Gtk.InputHints
            or other.__class__ is IBus.InputHints):
            return int(self) & int(other)
        if other.__class__ is int:
            return int(self) & other
        return NotImplemented

    def __rand__(self, other: Any) -> Any:
        return self.__and__(other)

    NONE = 'NONE'
    SPELLCHECK = 'SPELLCHECK'
    NO_SPELLCHECK = 'NO_SPELLCHECK'
    WORD_COMPLETION = 'WORD_COMPLETION'
    LOWERCASE = 'LOWERCASE'
    UPPERCASE_CHARS = 'UPPERCASE_CHARS'
    UPPERCASE_WORDS = 'UPPERCASE_WORDS'
    UPPERCASE_SENTENCES = 'UPPERCASE_SENTENCES'
    INHIBIT_OSK = 'INHIBIT_OSK'
    VERTICAL_WRITING = 'VERTICAL_WRITING'
    EMOJI = 'EMOJI'
    NO_EMOJI = 'NO_EMOJI'
    PRIVATE = 'PRIVATE'

class KeyvalsToKeycodes:
    '''Class to convert key values to key codes.

    Key values (Key symbols) are the codes which are sent whenever a
    key is pressed or released.

    Key codes are identifying numbers for physical keys.

    The mapping from key values to key codes is usually not bijective,
    a key value can be generated from different key codes (if that same value
    is mapped to different hardware keys in the keyboard layout)
    and a certain hardware key with a certain key code can generate different
    key values depending on which modifier was pressed.
    '''
    def __init__(self) -> None:
        self.keyvals_to_keycodes: Dict[int, List[int]] = {}
        display = Gdk.Display.get_default() # pylint: disable=no-value-for-parameter
        if not display:
            LOGGER.warning('Gdk.Display.get_default() returned %s', display)
            self._fallback_to_std_us_layout()
            return
        try:
            if GTK_MAJOR >= 4:
                self._init_gtk4(display)
            else:
                self._init_gtk3(display)
        except Exception as error: # pylint: disable=broad-exception-caught
            LOGGER.exception('Exception while initializing keymap: %s', error)
            self._fallback_to_std_us_layout()
            return
        if not self.keyvals_to_keycodes:
            LOGGER.warning('No keycodes found, falling back to standard US layout')
            self._fallback_to_std_us_layout()

    def _init_gtk4(self, display: Gdk.Display) -> None:
        '''Gtk4 implementation (no Gdk.Keymap exists).'''
        # GTK4: AltGr is represented as ALT_MASK.
        # The API deliberately abstracts keyboard layout details.
        # ALT_MASK is the only safe/effective representation of level-3 (AltGr)
        # translate_keyboard_state() still returns level-3 keyvals when needed.
        # If you want truly accurate physical-keyboard-layout access on Wayland,
        # there is no way through GTK.
        altgr_mods = Gdk.ModifierType.ALT_MASK # pylint: disable=no-member
        # Keycodes 1-7 were traditionally reserved for internal X
        # server use (e.g., fake keys for pointer buttons).  Keycodes
        # 8-255 were for physical keys
        for keycode in range(8, 256):
            # display.map_keycode(...) may return:
            #  - upstream GTK4: a list of Gdk.KeymapKey objects
            #  - compatibility wrapper (Fedora/RHEL): (success, keys, keyvals)
            #  - unexpected types: handle defensively
            result = display.map_keycode(keycode)
            try:
                result = display.map_keycode(keycode)
            except Exception as error: # pylint: disable=broad-exception-caught
                LOGGER.debug('display.map_keycode(%d) raised: %s', keycode, error)
                continue
            keys_list: List[Gdk.KeymapKey] = []
            keyvals_from_result: Optional[List[int]] = None
            # upstream GTK4: result is a list of Gdk.KeymapKey-like objects
            if isinstance(result, list):
                keys_list = result
                # also derive keyvals if available via attribute
                keyvals_from_result = None
            elif isinstance(result, tuple):
                # compatibility tuple: (success, keys, keyvals)
                if len(result) == 3:
                    success, keys_obj, keyvals_obj = result
                    if not success:
                        continue
                    keys_list = list(keys_obj) if keys_obj is not None else []
                    keyvals_from_result = (
                        list(keyvals_obj) if keyvals_obj is not None else None)
                else:
                    LOGGER.debug(
                        'display.map_keycode returned unexpected tuple shape: %r',
                        result)
                    continue
            else:
                LOGGER.debug(
                    'display.map_keycode returned unexpected type %r',
                    type(result))
                continue
            if not keys_list and not keyvals_from_result:
                continue
            # Base keyvals: try to get from objects or from keyvals_from_result
            base_keyvals: Set[int] = set()
            # If we have explicit keyvals provided by the compat tuple, use them
            if keyvals_from_result:
                for kv in keyvals_from_result:
                    if kv:
                        base_keyvals.add(int(kv))
            else:
                # Extract keyval attribute from each key object if present
                for k in keys_list:
                    if hasattr(k, 'keyval'):
                        try:
                            kv = int(getattr(k, 'keyval'))
                        except Exception: # pylint: disable=broad-exception-caught
                            continue
                        if kv:
                            base_keyvals.add(kv)
            if not base_keyvals: # Nothing meaningful for this keycode
                continue
            all_keyvals: Set[int] = set(base_keyvals)
            try:
                ok, keyval, *_ = display.translate_keyboard_state(
                    keycode, Gdk.ModifierType.SHIFT_MASK, 0)
            except Exception: # pylint: disable=broad-exception-caught
                ok = False
                keyval = 0
            if ok and keyval:
                all_keyvals.add(int(keyval))
            try:
                ok, keyval, *_ = display.translate_keyboard_state(
                    keycode, altgr_mods, 0)
            except Exception: # pylint: disable=broad-exception-caught
                ok = False
                keyval = 0
            if ok and keyval:
                all_keyvals.add(int(keyval))
            for keyval in all_keyvals:
                if keyval:
                    self.keyvals_to_keycodes.setdefault(
                        keyval, []).append(keycode)

    def _init_gtk3(self, display: Gdk.Display) -> None:
        '''Gtk3 implementation using Gdk.Keymap.'''
        keymap = Gdk.Keymap.get_for_display(display) # pylint: disable=c-extension-no-member
        if not keymap:
            LOGGER.warning('Could not get keymap')
            return
        # Checking AltGr state should not just check for Mod5,
        # that works only on Legacy X11 systems. Modern X11 and
        # Wayland systems use Mod1 + Level3 (1 << 16) instead:
        altgr_mods = (
            Gdk.ModifierType.MOD1_MASK | # pylint: disable=no-member
            Gdk.ModifierType(1 << 16) |
            Gdk.ModifierType.MOD5_MASK   # pylint: disable=no-member
        )
        # Keycodes 1-7 were traditionally reserved for internal X
        # server use (e.g., fake keys for pointer buttons).  Keycodes
        # 8-255 were for physical keys
        for keycode in range(8, 256):
            success, _keys, base_keyvals = keymap.get_entries_for_keycode(
                keycode)
            if not success:
                continue
            all_keyvals: Set[int] = set(base_keyvals or [])
            (success,
             keyval,
             _effective_group,
             _comsumed_modifiers,
             _locked_modifiers) = keymap.translate_keyboard_state(
                 keycode, Gdk.ModifierType.SHIFT_MASK, 0)
            if success:
                all_keyvals.add(keyval)
            (success,
             keyval,
             _effective_group,
             _consumed_modifiers,
             _locked_modifiers) = keymap.translate_keyboard_state(
                 keycode, altgr_mods, 0)
            if success and keyval:
                all_keyvals.add(keyval)
            for keyval in all_keyvals:
                if keyval:
                    self.keyvals_to_keycodes.setdefault(
                        keyval, []).append(keycode)

    def _fallback_to_std_us_layout(self) -> None:
        """Fallback mapping for when keycode detection fails"""
        # Gdk.Keymap.get_entries_for_keycode() seems to never find any
        # key codes on big endian platforms (s390x). Might be a bug in
        # that function. Until I figure out what the problem really
        # is, fall back to the standard us layout for the most
        # important key values:
        self._std_us_keyvals_to_keycodes = {
            IBus.KEY_Left: [113],
            IBus.KEY_BackSpace: [22],
            IBus.KEY_a: [38],
        # Add more fallbacks as needed
        }
        self.keyvals_to_keycodes.update(self._std_us_keyvals_to_keycodes)

    def keyvals(self) -> Set[int]:
        '''Returns the Set of keyvals available on the keyboard layout'''
        return set(self.keyvals_to_keycodes.keys())

    def keycodes(self, keyval: int) -> List[int]:
        '''Returns a list of key codes of the hardware keys which can generate
        the given key value on the current keyboard layout.

        :param keyval: A key value
        :return: A list of key codes of hardware keys, possibly empty
        '''
        if keyval in self.keyvals_to_keycodes:
            return self.keyvals_to_keycodes[keyval]
        return []

    def keycode(self, keyval: int) -> int:
        '''Returns one key code of one hardware key which can generate the
        given key value (there may be more than one, see the
        keycodes() function.

        :param keyval: A key value
        :return: One key code of a hardware key which can generate
                 the given key value, between 9 and 255
        '''
        keycodes = self.keycodes(keyval)
        if keycodes:
            return keycodes[0]
        return 0

    def ibus_keycodes(self, keyval: int) -> List[int]:
        '''Returns a list of ibus key codes of the hardware keys which can
        generate the given key value on the current keyboard layout.

        ibus key codes are calculated by subtracting 8 from the
        “normal” key codes.  The smallest possible keycode seems to be
        9 (usually mapped to Escape).  Therefore, after subtracting 8
        it is at least 1.

        :param keyval: A key value
        :return: A list of ibus key codes of hardware keys, possibly empty
                 The key codes are between 1 and 247
        '''
        if keyval in self.keyvals_to_keycodes:
            return [max(0, x - 8) for x in self.keyvals_to_keycodes[keyval]]
        return []

    def ibus_keycode(self, keyval: int) -> int:
        '''Returns one ibus key code of one hardware key which can generate
        the given key value (there may be more than one, see the
        ibus_keycodes() function)

        ibus key codes are calculated by subtracting 8 from the
        “normal” key codes.  The smallest possible keycode seems to be
        9 (usually mapped to Escape).  Therefore, after subtracting 8
        it is at least 1.

        :param keyval: A key value
        :return: One ibus key code of a hardware key which can generate
                 the given key value. It will be between 1 and 247.
        '''
        return max(0, self.keycode(keyval) - 8)

    def __str__(self) -> str:
        return_string = ''
        for keyval in sorted(self.keyvals_to_keycodes):
            return_string += (
                f'keyval: {keyval} '
                f'name: {IBus.keyval_name(keyval)} '
                f'keycodes: {self.keyvals_to_keycodes[keyval]}\n')
        return return_string

class ItbKeyInputDialog:
    '''
    Unified Gtk3/Gtk4 dialog for capturing a single key or key combination.
    API-compatible with the original Gtk3 MessageDialog version.
    '''
    def __init__(
            self,
            # Translators: This is used in the title bar of a dialog window
            # requesting that the user types a key to be used as a new
            # key binding for a command.
            title: str = _('Key input'),
            parent: Gtk.Window = None,
            parent_popover: Gtk.Popover = None) -> None:
        self.e: Optional[Tuple[int, int]] = None
        self._response: Optional[Gtk.ResponseType] = None
        if parent_popover:
            parent_popover.popdown()
        if GTK_MAJOR >= 4:
            self._build_gtk4(title, parent)
            return
        self._build_gtk3(title,parent)

    def _build_gtk3(self, title: str, parent: Gtk.Window) -> None:
        '''Build Gtk3 version of the dialog'''
        self.dialog = Gtk.MessageDialog(
            parent=parent,
            title=title,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE)
        self.dialog.add_button(_('Cancel'), Gtk.ResponseType.CANCEL)
        self.dialog.set_modal(True)
        self.dialog.set_markup(
            '<big><b>%s</b></big>' # pylint: disable=consider-using-f-string
            # Translators: This is from the dialog to enter a key or a
            # key combination to be used as a key binding for a
            # command.
            % _('Please press a key (or a key combination)'))
        self.dialog.format_secondary_text(
            # Translators: This is from the dialog to enter a key or a
            # key combination to be used as a key binding for a
            # command.
            _('The dialog will be closed when the key is released'))
        self.dialog.connect('key-press-event', self._on_key_press_gtk3)
        self.dialog.connect('key-release-event', self._on_key_release_gtk3)
        if parent:
            self.dialog.set_transient_for(parent)
        self.dialog.show()

    def _on_key_press_gtk3(
        self,
        _widget: Gtk.Widget,
        event: 'Gdk.EventKey', # pylint: disable=c-extension-no-member
    ) -> bool:
        '''Called when a key is pressed'''
        self.e = (event.keyval,
                  event.get_state() & KEYBINDING_STATE_MASK)
        return True

    def _on_key_release_gtk3(
        self,
        _widget: Gtk.Widget,
        _event: 'Gdk.EventKey', # pylint: disable=c-extension-no-member
    ) -> bool:
        '''Called when a key is released'''
        self.dialog.response(Gtk.ResponseType.OK)
        return True

    def _build_gtk4(self, title: str, parent: Gtk.Window) -> None:
        self.dialog = Gtk.Dialog(
            title=title,
            transient_for=parent,
            modal=True)
        self.dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        self.dialog.set_child(box)
        title_label = Gtk.Label()
        title_label.set_markup(
            '<big><b>%s</b></big>'  # pylint: disable=consider-using-f-string
            # Translators: This is from the dialog to enter a key or a
            # key combination to be used as a key binding for a
            # command.
            %_('Please press a key (or a key combination)'))
        title_label.set_xalign(0)
        box.append(title_label)
        sec_label = Gtk.Label(label=_(
            # Translators: This is from the dialog to enter a key or a
            # key combination to be used as a key binding for a
            # command.
            'The dialog will be closed when the key is released'))
        sec_label.set_xalign(0)
        sec_label.set_wrap(True)
        box.append(sec_label)
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(12)
        box.append(button_box)
        cancel_button = Gtk.Button(label=_('Cancel'))
        button_box.append(cancel_button)
        controller = Gtk.EventControllerKey()
        controller.connect('key-pressed', self._on_key_press_gtk4)
        controller.connect('key-released', self._on_key_release_gtk4)
        self.dialog.add_controller(controller)
        self.dialog.set_focusable(True)

        def on_dialog_mapped(dialog: Gtk.Dialog) -> None:
            '''Try to grab pointer and input'''
            dialog.grab_focus()
            default = dialog.get_default_widget()
            if default:
                default.grab_focus()

        def on_response(dialog: Gtk.Dialog, response_id: Gtk.ResponseType) -> None:
            '''Handle responses (cancel button, dialog close)'''
            self._response = response_id
            try:
                dialog.hide()
            except Exception: # pylint: disable=broad-exception-caught
                pass

        def on_cancel_clicked(_button: Gtk.Button) -> None:
            '''Called when the cancel button is clicked'''
            self._response = Gtk.ResponseType.CANCEL
            try:
                self.dialog.hide()
            except Exception: # pylint: disable=broad-exception-caught
                pass

        cancel_button.connect('clicked', on_cancel_clicked)
        self.dialog.connect('response', on_response)
        self.dialog.connect('map', on_dialog_mapped)
        self.dialog.present()

    def _on_key_press_gtk4(
            self,
            _controller: 'Gtk.EventControllerKey',
            keyval: int,
            _keycode: int,
            state: int,
    ) -> bool:
        '''Called when a key is pressed'''
        self.e = (keyval, state & KEYBINDING_STATE_MASK)
        return True

    def _on_key_release_gtk4(
            self,
            _controller: 'Gtk.EventControllerKey',
            _keyval: int,
            _keycode: int,
            _state: int,
    ) -> bool:
        '''Called when a key is released'''
        self._response = Gtk.ResponseType.OK
        try:
            self.dialog.hide()
        except Exception: # pylint: disable=broad-exception-caught
            pass
        return True

    def run(self) -> int:
        '''Gtk4 run() emulation'''
        if GTK_MAJOR < 4:
            return int(self.dialog.run())

        loop = GLib.MainLoop() # Manual mainloop until _response is set

        def _quit_when_ready() -> bool:
            if self._response is not None:
                loop.quit()
                return False
            return True

        GLib.timeout_add(20, _quit_when_ready)
        loop.run()

        if self._response is None:
            return int(Gtk.ResponseType.CANCEL)
        return int(self._response)

    def destroy(self) -> None:
        '''Common to Gtk3 and Gtk4'''
        try:
            self.dialog.destroy()
        except Exception: # pylint: disable=broad-exception-caught
            pass

class ItbAboutDialog(Gtk.AboutDialog): # type: ignore
    '''
    The “About” dialog for Typing Booster
    '''
    def  __init__(self, parent: Optional[Gtk.Window] = None) -> None:
        if GTK_MAJOR >= 4:
            Gtk.AboutDialog.__init__(self)
        else:
            Gtk.AboutDialog.__init__(self, parent=parent)
        if parent is not None:
            self.set_transient_for(parent)
            self.set_modal(True)
            self.set_destroy_with_parent(True)
        # An empty string in aboutdialog.set_logo_icon_name('')
        # prevents an ugly default icon to be shown. We don’t yet
        # have nice icons for ibus-typing-booster.
        self.set_logo_icon_name('')
        self.set_title(
            f'🚀 ibus-typing-booster {itb_version.get_version()}')
        self.set_program_name(
            '🚀 ibus-typing-booster')
        self.set_version(
            f'ibus-typing-booster-{itb_version.get_version()}'
            f', Gtk {".".join((str(i) for i in GTK_VERSION))}')
        self.set_comments(
            _('A completion input method to speedup typing.'))
        self.set_copyright(
            'Copyright © 2012–2025 Mike FABIAN')
        self.set_authors([
            'Mike FABIAN <maiku.fabian@gmail.com>',
            'Anish Patil <anish.developer@gmail.com>',
            ])
        self.set_translator_credits(
            # Translators: put your names here, one name per line.
            _('translator-credits'))
        # self.set_artists('')
        self.set_documenters([
            'Mike FABIAN <maiku.fabian@gmail.com>',
            ])
        self.set_website(
            'http://mike-fabian.github.io/ibus-typing-booster')
        self.set_website_label(
            _('Online documentation:')
            + ' ' + 'http://mike-fabian.github.io/ibus-typing-booster')
        self.set_license('''
        This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
        the Free Software Foundation, either version 3 of the License, or
        (at your option) any later version.

        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
        GNU General Public License for more details.

        You should have received a copy of the GNU General Public License
        along with this program.  If not, see <http://www.gnu.org/licenses/>
        ''')
        self.set_wrap_license(True)
        # overrides the above .set_license()
        self.set_license_type(Gtk.License.GPL_3_0)
        if GTK_MAJOR >= 4:
            self.connect('close-request', self.on_close_aboutdialog)
        else:
            self.connect('response', self.on_close_aboutdialog)
        self.show()
        self.present()

    def on_close_aboutdialog(self, *_args: Any) -> None:
        '''
        The “About” dialog has been closed by the user

        :param _about_dialog: The “About” dialog
        :param _response: The response when the “About” dialog was closed
        '''
        self.destroy()

if __name__ == "__main__":
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    import doctest
    (FAILED, _ATTEMPTED) = doctest.testmod()
    sys.exit(FAILED)
