# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2017 Mike FABIAN <mfabian@redhat.com>
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
An emoji picker for ibus typing booster.
'''

from typing import Any
from typing import List
from typing import Tuple
from typing import Iterable
from typing import Dict
from typing import Optional
from typing import Union
from typing import TYPE_CHECKING
from types import FrameType
import sys
import os
import re
import threading
import ast
import signal
import argparse
import locale
import time
import gettext
import unicodedata
import html
import logging
import logging.handlers

from gi import require_version
# pylint: disable=wrong-import-position
require_version('GLib', '2.0')
from gi.repository import GLib # type: ignore
require_version('Pango', '1.0')
from gi.repository import Pango # type: ignore
# pylint: enable=wrong-import-position

# set_prgname before importing other modules to show the name in warning
# messages when import modules are failed. E.g. Gtk.
GLib.set_application_name('Emoji Picker')
# This makes gnome-shell load the .desktop file when running under Wayland:
GLib.set_prgname('emoji-picker')

# pylint: disable=wrong-import-position,wrong-import-order,ungrouped-imports
from itb_gtk import Gdk, Gtk, GTK_MAJOR # type: ignore
if TYPE_CHECKING:
    # These imports are only for type checkers (mypy). They must not be
    # executed at runtime because itb_gtk controls the Gtk/Gdk versions.
    # pylint: disable=reimported
    from gi.repository import Gtk, Gdk  # type: ignore
    # pylint: enable=reimported
from gi.repository import GObject # type: ignore
# pylint: enable=wrong-import-position,wrong-import-order,ungrouped-imports
import itb_emoji
import itb_util
import itb_pango
import itb_version
from g_compat_helpers import (
    is_wayland,
    add_child,
    clear_children,
    children_of,
    forward_key_event_to_entry,
    emoji_flowbox_get_labels,
    show_all,
    set_label_wrap_mode,
    get_preferred_width,
    get_preferred_height,
    get_window_size,
    get_toplevel_window,
    PopupKind,
    PopupManager,
    create_popover,
    clickable_event_box_compat_get_gtk_label,
    ClickableEventBoxCompat,
    FakeEventKey,
    HeaderBarCompat,
    CompatButton,
    connect_focus_signal,
    grab_focus_without_selecting,
)

LOGGER = logging.getLogger('ibus-typing-booster')

GLIB_MAIN_LOOP: Optional[GLib.MainLoop] = None

DOMAINNAME = 'ibus-typing-booster'

def _(text: str) -> str:
    '''Gettext translation function.'''
    return gettext.dgettext(DOMAINNAME, text)

def N_(text: str) -> str: # pylint: disable=invalid-name
    '''Mark string for translation without actually translating.

    Used by gettext tools to extract strings that need translation.
    '''
    return text

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
        description='An emoji picker for ibus-typing-booster')
    parser.add_argument(
        '-l', '--languages',
        nargs='?',
        type=str,
        action='store',
        default='',
        help=('Set a list of languages to be used when browsing '
              'or searching for emoji. For example: '
              '"emoji-picker -l de:fr:ja" '
              'would use German, French, and Japanese. '
              'If empty, the locale settings are used to '
              'determine the languages.'))
    parser.add_argument(
        '-f', '--font',
        nargs='?',
        type=str,
        action='store',
        default=None,
        help=('Set a font to display emoji. '
              'If not specified, the font is read from the config file. '
              'To use the system default font specify "emoji". '
              'default: "%(default)s"'))
    parser.add_argument(
        '-s', '--fontsize',
        nargs='?',
        type=float,
        action='store',
        default=None,
        help=('Set a fontsize to display emoji. '
              'If not specified, the fontsize is read from the config file. '
              'If that fails 24 is used as a fall back fontsize. '
              'default: "%(default)s"'))
    parser.add_argument(
        '-m', '--modal',
        nargs='?',
        type=str2bool,
        action='store',
        const=True, # if -m or --modal with no value, assume True
        default=False,
        help=('Make the window of emoji-picker modal. '
              'default: %(default)s'))
    parser.add_argument(
        '-a', '--all',
        nargs='?',
        type=str2bool,
        action='store',
        const=True, # if -a or --all with no value, assume True
        default=True,
        help=('Load all Unicode characters. '
              'Makes all Unicode characters accessible, '
              'even normal letters. '
              'Slows the search down and is usually not needed. '
              'default: %(default)s'))
    parser.add_argument(
        '--unikemet',
        nargs='?',
        type=str2bool,
        action='store',
        const=True, # if --unikemet with no value, assume True
        default=True,
        help=('Load the Unikemet.txt file for Egyptian Hieroglyphs. '
              'default: %(default)s'))
    parser.add_argument(
        '--match-limit',
        nargs='?',
        type=int,
        action='store',
        default=1_000,
        help=('Limit for the number of results for searches. '
              'default: %(default)s'))
    parser.add_argument(
        '--fallback',
        nargs='?',
        type=str2bool,
        action='store',
        const=True, # if --fallback with no value, assume True
        default=None,
        help=('Whether to use fallback fonts when rendering emoji. '
              'If True, pango will use fallback fonts as necessary. '
              'If False, pango will use only glyphs from '
              'the closest matching font on the system. No fallback '
              'will be done to other fonts on the system that '
              'might contain the glyhps needed to render an emoji. '
              'default: "%(default)s"')
        )
    parser.add_argument(
        '--spellcheck',
        nargs='?',
        type=str2bool,
        action='store',
        const=True, # if --spellcheck with no value, assume True
        default=False,
        help=('Whether to add spellchecking suggestions automatically to search strings'
              'default: %(default)s'))
    parser.add_argument(
        '--emoji-unicode-min',
        nargs='?',
        type=str,
        action='store',
        default='0.0',
        help=('Load only emoji which were added to Unicode '
              'not earlier than this Unicode version. '
              'default: %(default)s'))
    # Guess current Unicode version:
    unicode_versions = (
        ('20180605', '11.0'),
        ('20190305', '12.0'),
        ('20190507', '12.1'),
        ('20200701', '13.0'),
        ('20200915', '13.1'),
        ('20210914', '14.0'),
        ('20220913', '15.0'),
        ('20230912', '15.1'),
        ('20240910', '16.0'),
        ('20250909', '17.0'),
    )
    current_date = time.strftime('%Y%m%d')
    current_unicode_version = '16.0'
    for (date, version) in unicode_versions:
        if current_date > date:
            current_unicode_version = version
    parser.add_argument(
        '--emoji-unicode-max',
        nargs='?',
        type=str,
        action='store',
        default=current_unicode_version,
        help=('Load only emoji which were added to Unicode '
              'not later than this Unicode version. '
              'default: %(default)s'))
    parser.add_argument(
        '-d', '--debug',
        nargs='?',
        type=str2bool,
        action='store',
        const=True, # if -d or --debug with no value assume True
        default=False,
        help=('Print some debug output to stdout. '
              'default: %(default)s'))
    parser.add_argument(
        '--version',
        action='store_true',
        default=False,
        help=('Output version information and exit. '
              'default: %(default)s'))
    return parser.parse_args()

_ARGS = parse_args()

class EmojiPickerUI(Gtk.Window): # type: ignore
    '''
    User interface of the emoji picker
    '''
    def __init__(self,
                 languages: Iterable[str] = ('en_US',),
                 modal: bool = False,
                 unicode_data_all: bool = False,
                 unikemet: bool = True,
                 emoji_unicode_min: str = '0.0',
                 emoji_unicode_max: str = '100.0',
                 font: Optional[str] = None,
                 fontsize: Optional[float] = None,
                 fallback: Optional[bool] = None,
                 match_limit: int = 1_000,
                 spellcheck: bool = True) -> None:
        Gtk.Window.__init__(self, title='🚀 ' + _('Emoji Picker'))

        self.set_name('EmojiPicker')
        css= f'''
            #EmojiPicker {{
            }}
            flowbox {{
            }}
            flowboxchild {{
                border-style: groove;
                border-width: 0.05px;
            }}
            row {{ /* This is for listbox rows */
                border-style: groove;
                border-width: 0.05px;
            }}
            .font {{
                padding: 2px 2px;
            }}
            popover {{
                border: 0;
                border-radius: 0;
                outline: none;
                background-color: {'transparent' if is_wayland() else '@theme_bg_color'};
            }}
            '''
        style_provider = Gtk.CssProvider()
        if GTK_MAJOR >= 4:
            style_provider.load_from_data(css, len(css)) # Gtk4 wants string
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), # pylint: disable=no-value-for-parameter
                style_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        else:
            style_provider.load_from_data(css.encode('UTF-8')) # Gtk3 wants bytes
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(), # pylint: disable=no-value-for-parameter
                style_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.set_default_size(700, 400)
        self._modal = modal
        self.set_modal(self._modal)
        available_fonts = self._list_font_names()
        self._font = 'emoji'
        if available_fonts:
            self._font = available_fonts[0]
        self._fontsize = 24.0
        self._fallback = True
        self._popup_manager = PopupManager()
        self._font_popover: Optional[Gtk.Popover] = None
        self._font_popover_scroll: Optional[Gtk.ScrolledWindow] = None
        self._font_popover_listbox: Optional[Gtk.ListBox] = None
        self._options_file = os.path.join(
            itb_util.xdg_save_data_path('emoji-picker'),
            'options')
        self._read_options()
        if font is not None:
            self._font = font
        if fontsize is not None:
            self._fontsize = fontsize
        if fallback is not None:
            self._fallback = bool(fallback)
        self._save_options()
        if GTK_MAJOR >= 4:
            self.connect('close-request', self.on_close)
        else:
            self.connect('delete-event', self.on_close)
        if GTK_MAJOR < 4:
            self.connect('key-press-event', self.on_main_window_key_press_event)
        else:
            controller = Gtk.EventControllerKey.new() # pylint: disable=no-value-for-parameter
            controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            controller.connect(
                'key-pressed', self.on_main_window_key_pressed_gtk4)
            self.add_controller(controller) # pylint: disable=no-member
        self._languages = languages
        self._emoji_unicode_min = emoji_unicode_min
        self._emoji_unicode_max = emoji_unicode_max
        self._match_limit = match_limit
        self._spellcheck = spellcheck
        self._unicode_data_all = unicode_data_all
        self._unikemet = unikemet
        self._emoji_matcher = itb_emoji.EmojiMatcher(
            languages=self._languages,
            unicode_data_all=self._unicode_data_all,
            unikemet=self._unikemet,
            emoji_unicode_min=self._emoji_unicode_min,
            emoji_unicode_max=self._emoji_unicode_max,
            variation_selector='emoji')
        self._gettext_translations: Dict[str, Any] = {}
        for language in itb_util.expand_languages(self._languages):
            mo_file = gettext.find(DOMAINNAME, languages=[language])
            if (mo_file
                    and
                    '/' + language  + '/LC_MESSAGES/' + DOMAINNAME + '.mo'
                    in mo_file):
                # Get the gettext translation instance only if a
                # translation file for this *exact* language was
                # found.  Ignore it if only a fallback was found. For
                # example, if “de_DE” was requested and only “de” was
                # found, ignore it.
                try:
                    self._gettext_translations[language] = gettext.translation(
                        DOMAINNAME, languages=[language])
                except (OSError, ):
                    self._gettext_translations[language] = None
            else:
                self._gettext_translations[language] = None

        self._currently_selected_label: Optional[Tuple[str, str, str]] = None
        self._query_string = ''
        self._emoji_selected_popover: Optional[Gtk.Popover] = None
        self._emoji_info_popover: Optional[Gtk.Popover] = None
        self._skin_tone_popover: Optional[Gtk.Popover] = None
        self._skin_tone_selected_popover: Optional[Gtk.Popover] = None
        self._skin_tone_popover_originated_from_emoji_label: Optional[Gtk.Label] = None

        self._main_container = Gtk.Box()
        self._main_container.set_orientation(Gtk.Orientation.VERTICAL)
        self._main_container.set_spacing(0)
        add_child(self, self._main_container)
        self._header_bar = HeaderBarCompat()
        self._header_bar.set_hexpand(True)
        self._header_bar.set_vexpand(False)
        self._main_menu_popover: Optional[Gtk.Popover] = None
        self._main_menu_button = CompatButton(icon_name='open-menu-symbolic')
        self._header_bar.pack_start(self._main_menu_button)
        self._main_menu_button.connect(
            'clicked', self.on_main_menu_button_clicked)
        self._toggle_search_button = CompatButton(
            icon_name='edit-find-symbolic', tooltip_text=_('Search for emoji'))
        self._toggle_search_button.connect(
            'clicked', self.on_toggle_search_button_clicked)
        self._header_bar.pack_start(self._toggle_search_button)
        self._font_button = CompatButton(
            label=self._font, icon_name='preferences-desktop-font',
            tooltip_text=_('Set the font to display emoji'))
        self._font_button.connect('clicked', self.on_font_button_clicked)
        self._header_bar.pack_start(self._font_button)
        self._fontsize_spin_button = Gtk.SpinButton()
        self._fontsize_spin_button.set_numeric(True)
        self._fontsize_spin_button.set_can_focus(True)
        self._fontsize_spin_button.set_tooltip_text(
            _('Set font size'))
        grab_focus_without_selecting(self._fontsize_spin_button)
        connect_focus_signal(self._fontsize_spin_button,
                             self.on_fontsize_spin_button_grab_focus)
        self._fontsize_adjustment = Gtk.Adjustment()
        self._fontsize_adjustment.set_lower(1)
        self._fontsize_adjustment.set_upper(10000)
        self._fontsize_adjustment.set_value(self._fontsize)
        self._fontsize_adjustment.set_step_increment(1)
        self._fontsize_spin_button.set_adjustment(self._fontsize_adjustment)
        self._fontsize_adjustment.connect(
            'value-changed', self.on_fontsize_adjustment_value_changed)
        self._header_bar.pack_start(self._fontsize_spin_button)
        self._fallback_check_button = Gtk.CheckButton()
        # Translators: This is a checkbox which enables or disables
        # the pango font fallback. If font fallback is off, only the
        # font selected in the font menu is used to display emoji
        # (if possible, this may not always work, sometimes other fonts
        # may be used even if font fallback is off).
        # If font fallback is on, other fonts will be tried for emoji
        # or parts of emoji sequences which cannot be displayed in the
        # selected font.
        self._fallback_check_button.set_label(_('Fallback'))
        self._fallback_check_button.set_tooltip_text(
            _('Whether to use font fallback for emoji or parts of emoji '
              + 'sequences which cannot be displayed using the '
              + 'selected font.'))
        self._fallback_check_button.set_active(self._fallback)
        self._fallback_check_button.connect(
            'toggled', self.on_fallback_check_button_toggled)
        self._header_bar.pack_start(self._fallback_check_button)
        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_show_text(True)
        self._progress_bar.set_pulse_step(0)
        self._progress_bar.set_size_request(150, -1) # Width 150px, natural height
        self._progress_bar.set_vexpand(True)
        self._progress_bar.set_valign(Gtk.Align.CENTER)
        self._progress_bar.set_margin_start(10)
        self._progress_bar.set_margin_end(10)
        self._header_bar.pack_end(self._progress_bar)
        self._progress_bar.set_visible(False)
        self.set_titlebar(self._header_bar)

        self._search_timeout_source_id: int = 0
        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_hexpand(False)
        self._search_entry.set_vexpand(False)
        self._search_entry.set_can_focus(True)
        grab_focus_without_selecting(self._search_entry)
        self._search_bar = Gtk.SearchBar()
        self._search_bar.set_hexpand(False)
        self._search_bar.set_vexpand(False)
        self._search_bar.set_show_close_button(False)
        self._search_bar.set_search_mode(False) # invisible by default
        add_child(self._search_bar, self._search_entry)
        self._search_bar.connect_entry(self._search_entry)
        self._search_entry.connect(
            'search-changed', self.on_search_entry_search_changed)
        connect_focus_signal(self._search_entry, self.on_search_entry_grab_focus)

        browse_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        add_child(self._main_container, browse_paned)
        browse_paned.set_wide_handle(True)
        browse_paned.set_hexpand(True)
        browse_paned.set_vexpand(True)

        self._browse_treeview_scroll = Gtk.ScrolledWindow()
        self._browse_treeview = Gtk.TreeView()
        # If the treeview can focus, it reacts to key events.
        # One search in the treeview by typing into a built-in popup,
        # but it seems very limited and not very useful.
        # It also interferes badly with the search entry, so better
        # switch that off:
        self._browse_treeview.set_can_focus(False)
        self._browse_treeview.set_activate_on_single_click(True)
        self._browse_treeview.set_vexpand(True)
        self._browse_treeview.get_selection().connect(
            'changed', self.on_label_selected)
        self._browse_treeview.connect(
            'row-activated', self.on_row_activated)
        add_child(self._browse_treeview_scroll, self._browse_treeview)

        self._flowbox_scroll = Gtk.ScrolledWindow()
        self._flowbox_scroll.set_hexpand(True)
        self._flowbox_scroll.set_vexpand(True)
        if GTK_MAJOR < 4:
            self._flowbox_scroll.set_capture_button_press(False)
        self._flowbox_scroll.set_kinetic_scrolling(False)
        self._flowbox_scroll.set_overlay_scrolling(True)
        self._flowbox = Gtk.FlowBox()
        add_child(self._flowbox_scroll, self._flowbox)

        self._left_pane = Gtk.Box()
        self._left_pane.set_orientation(Gtk.Orientation.VERTICAL)
        self._left_pane.set_spacing(0)
        self._left_pane.set_homogeneous(False)
        add_child(self._left_pane, self._search_bar)
        add_child(self._left_pane, self._browse_treeview_scroll)

        self._right_pane = Gtk.Box()
        self._right_pane.set_orientation(Gtk.Orientation.VERTICAL)
        self._right_pane.set_spacing(0)
        self._right_pane.set_homogeneous(False)
        add_child(self._right_pane, self._flowbox_scroll)

        if GTK_MAJOR >= 4:
            # pylint: disable=no-member
            browse_paned.set_start_child(self._left_pane)
            browse_paned.set_end_child(self._right_pane)
            browse_paned.set_resize_start_child(True)
            browse_paned.set_resize_end_child(True)
            # pylint: enable=no-member
        else:
            browse_paned.pack1(self._left_pane, resize=True, shrink=True)
            browse_paned.pack2(self._right_pane, resize=True, shrink=True)

        self._browse_treeview_model = Gtk.TreeStore(str, str, str, str)
        self._browse_treeview.set_model(self._browse_treeview_model)

        self._recently_used_label = '🕒 ' + _('Recently used')
        _dummy_recent_iter = self._browse_treeview_model.append(
            None,
            [self._recently_used_label, '', '', self._recently_used_label])

        self._recently_used_emoji: Dict[str, Dict[str, float]] = {}
        self._recently_used_emoji_file = os.path.join(
            itb_util.xdg_save_data_path('emoji-picker'),
            'recently-used')
        self._recently_used_emoji_maximum = 100
        self._read_recently_used()

        self._emoji_by_label = self._emoji_matcher.emoji_by_label()
        expanded_languages = itb_util.expand_languages(self._languages)
        # 'en_001' and 'es_419' are not very useful in the treeview to
        # browse the languages, remove them from the list:
        expanded_languages = [
            lang
            for lang in expanded_languages
            if lang not in ('en_001', 'es_419')]
        first_language_with_categories = -1
        number_of_empty_languages = 0
        for language_index, language in enumerate(expanded_languages):
            language_empty = True
            if language in self._emoji_by_label:
                language_iter = self._browse_treeview_model.append(
                    None, [language, '', '', ''])
                if self._add_label_key_to_model(
                        'categories',
                        self._translate_key('Categories', language),
                        language, language_iter):
                    language_empty = False
                    if first_language_with_categories < 0:
                        first_language_with_categories = (
                            language_index - number_of_empty_languages)
                if self._add_label_key_to_model(
                        'ucategories',
                        self._translate_key('Unicode categories', language),
                        language, language_iter):
                    language_empty = False
                if self._add_label_key_to_model(
                        'keywords',
                        self._translate_key('Keywords', language),
                        language, language_iter):
                    language_empty = False
                if language_empty:
                    self._browse_treeview_model.remove(language_iter)
            if language_empty:
                number_of_empty_languages += 1

        if _ARGS.debug:
            LOGGER.debug(
                'expanded_languages  = %s\n'
                'first_language_with_categories = %s\n'
                'number_of_empty_languages = %s\n',
                itb_util.expand_languages(self._languages),
                first_language_with_categories,
                number_of_empty_languages)

        self._browse_treeview.append_column(
            Gtk.TreeViewColumn(
                'Browse', Gtk.CellRendererText(), text=0))
        self._browse_treeview.set_headers_visible(False)
        self._browse_treeview.collapse_all()
        if first_language_with_categories >= 0:
            # add one to take the “Recently used” entry into account:
            first_path_component = first_language_with_categories + 1
            self._browse_treeview.expand_row(
                Gtk.TreePath([first_path_component]), False)
            self._browse_treeview.expand_row(
                Gtk.TreePath([first_path_component, 0]), False)
            self._browse_treeview.set_cursor(
                Gtk.TreePath([first_path_component, 0, 0]),
                self._browse_treeview.get_column(0))

        self._browse_treeview.columns_autosize()

        show_all(self)

        (_minimum_width_search_entry,
         natural_width_search_entry) = get_preferred_width(self._search_entry)
        (_minimum_width_search_bar,
         natural_width_search_bar) = get_preferred_width(self._search_bar)
        if _ARGS.debug:
            LOGGER.debug(
                'natural_width_search_entry = %s '
                'natural_width_search_bar = %s\n',
                natural_width_search_entry,
                natural_width_search_bar)
        browse_paned.set_position(natural_width_search_bar)

    def _busy_start(self) -> None:
        ''' Show that this program is busy '''
        self._progress_bar.set_visible(True)
        # self.get_root_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
        # Gdk.flush()

    def _busy_fraction(self, fraction: float) -> None:
        ''' Set the percent of progress made when the program is busy '''
        self._progress_bar.set_fraction(fraction)

    def _busy_stop(self) -> None:
        ''' Stop showing that this program is busy '''
        self._progress_bar.set_visible(False)
        # self.get_root_window().set_cursor(Gdk.Cursor(Gdk.CursorType.ARROW))

    def _variation_selector_normalize_for_font(self, emoji: str) -> str:
        '''
        Normalize the variation selectors in the emoji sequence.

        Returns a new emoji sequences with variation selectors added
        or removed as appropriate for the current font.

        :param emoji: The emoji
        '''
        if self._font == 'text' or self._font.lower() == 'symbola':
            return self._emoji_matcher.variation_selector_normalize(
                emoji, 'text')
        if self._font == 'unqualified':
            return self._emoji_matcher.variation_selector_normalize(
                emoji, '')
        return self._emoji_matcher.variation_selector_normalize(
            emoji, 'emoji')

    def _browse_treeview_unselect_all(self) -> None:
        '''
        Unselect everything in the treeview for browsing the categories
        '''
        self._browse_treeview.get_selection().unselect_all()
        self._currently_selected_label = None

    def _add_label_key_to_model(
            self,
            label_key: str,
            label_key_display: str,
            language: str,
            language_iter: Any) -> bool:
        if label_key not in self._emoji_by_label[language]:
            return False
        labels = self._sort_labels(
            self._emoji_by_label[language][label_key],
            language)
        if not labels:
            return False
        label_key_iter = self._browse_treeview_model.append(
            language_iter, [label_key_display, '', '', ''])
        for label in labels:
            number_of_emoji = len(
                self._emoji_by_label[language][label_key][label])
            self._browse_treeview_model.append(
                label_key_iter,
                [label + ' ' + str(number_of_emoji),
                 language, label_key, label])
        return True

    @classmethod
    def _sort_labels(
            cls,
            labels: Dict[str, List[str]],
            language: str) -> List[str]:
        return sorted(
            labels,
            key=lambda x: (
                # For Japanese and Chinese: sort Chinese
                # characters before Hiragana and Latin:
                (language.startswith('ja') or language.startswith('zh'))
                and not unicodedata.name(x[0]).startswith('CJK'),
                language.startswith('ja')
                and not unicodedata.name(x[0]).startswith('HIRAGANA'),
                # sort Digits after non Digits:
                unicodedata.name(x[0]).startswith('DIGIT'),
                x.lower()))

    def _translate_key(self, key: str, language: str = 'en') -> str:
        _dummy_keys_to_translate = [
            N_('Categories'),
            N_('Unicode categories'),
            N_('Keywords'),
        ]
        if self._gettext_translations[language]:
            return str(self._gettext_translations[language].gettext(key))
        return key

    def _emoji_descriptions(self, emoji: str) -> List[str]:
        '''
        Return a description of the emoji

        The description shows the Unicode codepoint(s) of the emoji
        and the names of the emoji in all languages used.

        :param emoji: The emoji
        '''
        descriptions = []
        descriptions.append(
            ' '.join([f'U+{ord(character):04X}' for character in emoji]))
        fonts_description = _('Fonts used to render this emoji:')
        fallback = self._optimize_pango_fallback(emoji)
        for text, font_dict in itb_pango.get_fonts_used_for_text(
                self._font + ' ' + str(self._fontsize), emoji,
                fallback=fallback):
            fonts_description += '\n'
            code_points = ''
            for char in text:
                code_points += f' U+{ord(char):04X}'
            fonts_description += (
                f'<span font="{self._font}" '
                f'fallback="{str(fallback).lower()}" >'
                + text + '</span>'
                + f'<span fallback="true">{code_points}</span>')
            if _ARGS.debug:
                fonts_description += f': {font_dict}'
            else:
                fonts_description += f': {font_dict["font"]}'
        emoji_unqualified = emoji.replace('\uFE0E', '').replace('\uFE0F', '')
        if _ARGS.debug and emoji_unqualified != emoji:
            for text, font_dict in itb_pango.get_fonts_used_for_text(
                    self._font + ' ' + str(self._fontsize), emoji_unqualified,
                    fallback=fallback):
                fonts_description += '\n'
                code_points = ''
                for char in text:
                    code_points += f' U+{ord(char):04X}'
                fonts_description += (
                    f'<span font="{self._font}" '
                    f'fallback="{str(fallback).lower()}" >'
                    + text + '</span>'
                    + f'<span fallback="true">{code_points}</span>')
                fonts_description += f': {font_dict}'
        descriptions.append(fonts_description)
        for language in itb_util.expand_languages(self._languages):
            names = self._emoji_matcher.names(emoji, language=language)
            description = f'<b>{language}</b>'
            description_empty = True
            if names:
                description += '\n' + html.escape(', '.join(names))
                description_empty = False
            keywords = self._emoji_matcher.keywords(emoji, language=language)
            if keywords:
                description += (
                    '\n' + self._translate_key('Keywords', language) + ': '
                    + html.escape(', '.join(keywords)))
                description_empty = False
            categories = self._emoji_matcher.categories(
                emoji, language=language)
            if categories:
                description += (
                    '\n' + self._translate_key('Categories', language) + ': '
                    + html.escape(', '.join(categories)))
                description_empty = False
            if not description_empty:
                descriptions.append(description)
        if self._emoji_matcher.unicode_version(emoji):
            descriptions.append(
                _('Unicode Version:') + ' '
                + self._emoji_matcher.unicode_version(emoji))
        if self._emoji_matcher.emoji_version(emoji):
            descriptions.append(
                _('Emoji Version:') + ' '
                + self._emoji_matcher.emoji_version(emoji))
        if self._emoji_matcher.properties(emoji):
            descriptions.append(
                # Translators: Emoji properties from unicode.org like
                # “Emoji”, “Emoji_Presentation”, “Extended_Pictographic”,
                # “RGI_Emoji_ZWJ_Sequence”, ...
                _('Emoji properties:') + '\n'
                + ', '.join(self._emoji_matcher.properties(emoji)))
        if self._emoji_matcher.unicode_category(emoji):
            descriptions.append(
                # Translators: The Unicode category is something like
                # “So Symbol Other”, “Sm Symbol Math”, ...
                _('Unicode category:') + ' '
                + ' '.join(self._emoji_matcher.unicode_category(emoji)))
        if self._emoji_matcher.unicode_block(emoji):
            descriptions.append(
                # Translators: The Unicode block is something like
                # “Basic Latin”, “Cyrillic”, “Mathematical Operators”, ...
                # (see: https://en.wikipedia.org/wiki/Unicode_block)
                _('Unicode block:')
                + f' {self._emoji_matcher.unicode_block(emoji)}')
        if _ARGS.debug:
            descriptions.append(
                f'emoji_order = {self._emoji_matcher.emoji_order(emoji)}')
            descriptions.append(
                f'cldr_order = {self._emoji_matcher.cldr_order(emoji)}')
        return descriptions

    def _emoji_label_set_tooltip( # pylint: disable=no-self-use
            self,
            emoji: str,
            label: Gtk.Label) -> None:
        '''
        Set the tooltip for a label in the flowbox which shows an emoji

        :param emoji: The emoji
        :param label: The label used to show the emoji
        '''
        tooltip_text = _('Left click to copy') + '\n'
        if len(self._emoji_matcher.skin_tone_variants(emoji)) > 1:
            tooltip_text += (
                _('Long press or middle click for skin tones')  + '\n')
        tooltip_text += _('Right click for info')
        label.set_tooltip_text(tooltip_text)

    def _clear_flowbox(self) -> None:
        '''
        Clear the contents of the flowbox
        '''
        clear_children(self._flowbox_scroll)
        self._flowbox = Gtk.FlowBox()
        self._flowbox.get_style_context().add_class('view')
        add_child(self._flowbox_scroll, self._flowbox)
        self._flowbox.set_valign(Gtk.Align.START)
        self._flowbox.set_min_children_per_line(1)
        self._flowbox.set_max_children_per_line(100)
        self._flowbox.set_row_spacing(0)
        self._flowbox.set_column_spacing(0)
        self._flowbox.set_activate_on_single_click(True)
        self._flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flowbox.set_can_focus(True)
        self._flowbox.set_homogeneous(False)
        self._flowbox.set_hexpand(False)
        self._flowbox.set_vexpand(False)
        self._flowbox.connect('child-activated', self.on_emoji_selected)

    def _fill_flowbox_browse(self) -> None:
        '''
        Fill the flowbox with content according to the currently
        selected label in the browsing treeview.
        '''
        if self._currently_selected_label is None:
            LOGGER.debug('No label is currently selected')
            return
        (language, label_key, label) = self._currently_selected_label
        if _ARGS.debug:
            LOGGER.debug(
                'language = %s label_key = %s label = %s\n',
                language, label_key, label)
        self._busy_start()
        self._clear_flowbox()
        emoji_list = []
        is_recently_used = False
        sorted_recently_used = self._sorted_recently_used()
        if label == self._recently_used_label:
            is_recently_used = True
            emoji_list = sorted_recently_used
        if (language in self._emoji_by_label
                and label_key in self._emoji_by_label[language]
                and label in  self._emoji_by_label[language][label_key]):
            emoji_list = self._emoji_by_label[language][label_key][label]

        self._header_bar.set_title(label)
        if label:
            self._header_bar.set_subtitle(f'({len(emoji_list)})')
        else:
            self._header_bar.set_subtitle('')

        if not emoji_list:
            self._busy_stop()
            return

        for index, emoji in enumerate(emoji_list):
            self._busy_fraction(index/len(emoji_list))
            # Process pending events, replacement for:
            # while Gtk.events_pending():
            #     Gtk.main_iteration())
            while GLib.MainContext.default().iteration(False): # pylint: disable=no-value-for-parameter
                if SIGNAL_HANDLER.interrupt_requested:
                    LOGGER.info('Control+C pressed, exiting ...')
                    sys.exit(1)
            if self._currently_selected_label != (language, label_key, label):
                # If a new label has been selected, stop filling the flowbox
                # with contents for the old label:
                LOGGER.debug(
                    'Selected label changed: %r -> %r',
                    (language, label_key, label),
                    self._currently_selected_label)
                self._busy_stop()
                return
            emoji = self._variation_selector_normalize_for_font(emoji)
            if not is_recently_used:
                skin_tone_variants = self._emoji_matcher.skin_tone_variants(
                    emoji)
                if len(skin_tone_variants) > 1:
                    # For an emoji which can take a skin tone modifier,
                    # replace it by the most recently used variant.
                    # If no variant has been recently used, leave
                    # the base emoji as it is:
                    recently_used_index = len(sorted_recently_used)
                    for skin_tone_variant in skin_tone_variants:
                        if skin_tone_variant in sorted_recently_used:
                            recently_used_index = min(
                                recently_used_index,
                                sorted_recently_used.index(skin_tone_variant))
                    if recently_used_index < len(sorted_recently_used):
                        emoji = sorted_recently_used[recently_used_index]
            gtk_label = Gtk.Label()
            fallback = self._optimize_pango_fallback(emoji)
            # Make font for emoji large using pango markup
            text = (
                f'<span font="{self._font} {self._fontsize}" '
                f'fallback="{str(fallback).lower()}">'
                f'{html.escape(emoji)}</span>')
            if itb_util.is_invisible(emoji):
                text += (
                    f'<span fallback="false" font="{self._fontsize / 2}">'
                    f' U+{ord(emoji):04X} {self._emoji_matcher.name(emoji)}'
                    '</span>')
            gtk_label.set_text(text)
            gtk_label.set_use_markup(True)
            gtk_label.set_can_focus(False)
            gtk_label.set_selectable(False)
            gtk_label.set_hexpand(False)
            gtk_label.set_vexpand(False)
            gtk_label.set_xalign(0.5)
            gtk_label.set_yalign(0.5)
            # Gtk.Align.FILL, Gtk.Align.START, Gtk.Align.END,
            # Gtk.Align.CENTER, Gtk.Align.BASELINE
            gtk_label.set_halign(Gtk.Align.FILL)
            gtk_label.set_valign(Gtk.Align.FILL)
            margin = 0
            gtk_label.set_margin_start(margin)
            gtk_label.set_margin_end(margin)
            gtk_label.set_margin_top(margin)
            gtk_label.set_margin_bottom(margin)
            self._emoji_label_set_tooltip(emoji, gtk_label)
            event_box = ClickableEventBoxCompat()
            add_child(event_box, gtk_label)
            event_box.connect(
                'clicked', self.on_flowbox_event_box_button_press)
            event_box.connect(
                'released', self.on_flowbox_event_box_button_release)
            event_box.connect(
                'long-pressed', self.on_flowbox_event_box_long_press_pressed)
            self._flowbox.insert(event_box, -1)
            # showing after each insert shows some progress
            show_all(self._flowbox)

        show_all(self)
        self._busy_stop()

    def _read_options(self) -> None:
        '''
        Read the options for 'font' and 'fontsize' from  a file
        '''
        options_dict = {}
        if os.path.isfile(self._options_file):
            try:
                with open(self._options_file,
                          encoding='UTF-8') as options_file:
                    options_dict = ast.literal_eval(options_file.read())
            except (PermissionError, SyntaxError, IndentationError) as error:
                LOGGER.exception('Error when reading options: %s: %s',
                                 error.__class__.__name__, error)
            except Exception as error: # pylint: disable=broad-except
                LOGGER.exception(
                    'Unexpected error when reading options: %s: %s',
                    error.__class__.__name__, error)
            else: # no exception occured
                if _ARGS.debug:
                    LOGGER.debug(
                        'File %s has been read and evaluated.\n',
                        self._options_file)
            finally: # executes always
                if not isinstance(options_dict, dict):
                    if _ARGS.debug:
                        LOGGER.debug(
                            'Not a dict: repr(options_dict) = %s\n',
                            options_dict)
                    options_dict = {}
        if ('font' in options_dict
                and isinstance(options_dict['font'], str)):
            self._font = options_dict['font']
            if self._font == '':
                self._font = 'emoji'
        if ('fontsize' in options_dict
                and (isinstance(options_dict['fontsize'], (int, float)))):
            self._fontsize = options_dict['fontsize']
        if ('fallback' in options_dict
                and (isinstance(options_dict['fallback'], bool))):
            self._fallback = options_dict['fallback']

    def _save_options(self) -> None:
        '''
        Save the options for 'font' and 'fontsize' to a file
        '''
        options_dict = {
            'font': self._font,
            'fontsize': self._fontsize,
            'fallback': self._fallback,
            }
        with open(self._options_file,
                  mode='w',
                  encoding='UTF-8') as options_file:
            options_file.write(repr(options_dict))
            options_file.write('\n')

    def _sorted_recently_used(self) -> List[str]:
        '''
        Return a sorted list of recently used emoji
        '''
        return sorted(self._recently_used_emoji,
                      key=lambda x: (
                          - self._recently_used_emoji[x]['time'],
                          - self._recently_used_emoji[x]['count']))

    def _read_recently_used(self) -> None:
        '''
        Read the recently use emoji from a file
        '''
        recently_used_emoji = {}
        if os.path.isfile(self._recently_used_emoji_file):
            try:
                with open(self._recently_used_emoji_file,
                          encoding='UTF-8') as recently_used_file:
                    recently_used_emoji = ast.literal_eval(
                        recently_used_file.read())
            except (PermissionError, SyntaxError, IndentationError) as error:
                LOGGER.exception('Error reading recently used emoji: %s: %s',
                                 error.__class__.__name__, error)
            except Exception as error: # pylint: disable=broad-except
                LOGGER.exception(
                    'Unexpected error reading recently used emoji: %s: %s',
                    error.__class__.__name__, error)
            else: # no exception occured
                if _ARGS.debug:
                    LOGGER.debug(
                        'File %s has been read and evaluated.\n',
                        self._recently_used_emoji_file)
            finally: # executes always
                if not isinstance(recently_used_emoji, dict):
                    if _ARGS.debug:
                        LOGGER.debug(
                            'Not a dict: repr(recently_used_emoji) = %s\n',
                            recently_used_emoji)
                    recently_used_emoji = {}
        self._recently_used_emoji = {}
        for emoji, value in recently_used_emoji.items():
            # add or remove vs16 according to the current setting:
            if emoji:
                self._recently_used_emoji[
                    self._variation_selector_normalize_for_font(emoji)] = value
        if not self._recently_used_emoji:
            self._init_recently_used()
        self._cleanup_recently_used()

    def _cleanup_recently_used(self) -> None:
        '''
        Reduces the size of the recently used dictionary
        if it has become too big.
        '''
        if len(self._recently_used_emoji) > self._recently_used_emoji_maximum:
            for emoji in sorted(
                    self._recently_used_emoji,
                    key=lambda x: (
                        - self._recently_used_emoji[x]['time'],
                        - self._recently_used_emoji[x]['count'],
                    ))[self._recently_used_emoji_maximum:]:
                del self._recently_used_emoji[emoji]

    def _init_recently_used(self) -> None:
        '''
        Initialize the recently used emoji

        - Make the the recently used emoji empty
        - Save it to disk
        - Clear the flowbox if it is currently showing the recently used
        '''
        self._recently_used_emoji = {}
        self._save_recently_used_emoji()
        if (self._currently_selected_label ==
                ('', '', self._recently_used_label)):
            self._clear_flowbox()

    def on_clear_recently_used_button_clicked(
            self, _button: Gtk.Button) -> None:
        '''
        :param _button: The “Clear recently used” button
        '''
        if _ARGS.debug:
            LOGGER.debug('on_clear_recently_used_button_clicked()\n')
        self._popup_manager.popdown_current()
        self._init_recently_used()

    def _add_to_recently_used(self, emoji: str) -> None:
        '''
        Adds an emoji to the resently used dictionary.

        :param emoji: The emoji string
        '''
        if emoji in self._recently_used_emoji:
            self._recently_used_emoji[emoji]['count'] += 1
            self._recently_used_emoji[emoji]['time'] = time.time()
        else:
            self._recently_used_emoji[emoji] = {
                'count': 1, 'time': time.time()}
        self._cleanup_recently_used()
        # Better save always, on_delete_event() is not called
        # when the program is stopped using Control+C
        self._save_recently_used_emoji()

    def _save_recently_used_emoji(self) -> None:
        '''
        Save the list of recently used emoji
        '''
        with open(self._recently_used_emoji_file,
                  mode='w',
                  encoding='UTF-8') as recents_file:
            recents_file.write(repr(self._recently_used_emoji))
            recents_file.write('\n')

    def _set_clipboards(self, text: str) -> None: # pylint: disable=no-self-use
        '''
        Set the clipboard and the primary selection to “text”

        Works on both Gtk3 and Gtk4

        :param text: The text to set the clipboards to
        '''
        if GTK_MAJOR < 4:
            # pylint: disable=c-extension-no-member
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            primary = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
            # pylint: enable=c-extension-no-member
            clipboard.set_text(text, -1)
            primary.set_text(text, -1)
            # Store the current clipboard data somewhere so that
            # it will stay around after the application has quit:
            clipboard.store()
            primary.store()
        else:
            clipboard = self.get_clipboard()
            if clipboard is not None:
                # pylint: disable=c-extension-no-member
                content_provider = Gdk.ContentProvider.new_for_value(text)
                # pylint: enable=c-extension-no-member
                clipboard.set_content(content_provider)
            primary = self.get_primary_clipboard() # pylint: disable=no-member
            if primary is not None:
                # pylint: disable=c-extension-no-member
                content_provider = Gdk.ContentProvider.new_for_value(text)
                # pylint: enable=c-extension-no-member
                primary.set_content(content_provider)

    def _show_concise_emoji_description_in_header_bar(
            self, emoji: str) -> None:
        '''
        Show a concise description of an emoji in the header bar
        of the program.

        :param emoji: The emoji for which a description should be
                      shown in the header bar.
        '''
        title = emoji
        # Start the subtitle with the number of emoji in this flowbox
        subtitle =  f'({len(emoji_flowbox_get_labels(self._flowbox))})'
        # Display the names of the emoji in the first language
        # where names are available in the header bar title:
        for language in itb_util.expand_languages(self._languages):
            names = self._emoji_matcher.names(emoji, language=language)
            if names:
                title += f' {", ".join(names)}'
                break
        # Display the keywords of the emoji in the first language
        # where keywords are available in the header bar subtitle:
        for language in itb_util.expand_languages(self._languages):
            keywords = self._emoji_matcher.keywords(emoji, language=language)
            if keywords:
                subtitle += (
                    f' {self._translate_key("Keywords", language)}: {", ".join(keywords)}')
                break
        self._header_bar.set_title(title)
        self._header_bar.set_subtitle(subtitle)

    @staticmethod
    def print_profiling_information() -> None:
        '''
        Print some profiling information to the log.
        '''
        # pylint: disable=used-before-assignment
        PROFILE.disable()
        stats_stream = io.StringIO()
        stats = pstats.Stats(PROFILE, stream=stats_stream)
        # pylint: enable=used-before-assignment
        stats.strip_dirs()
        stats.sort_stats('cumulative')
        stats.print_stats('emoji_picker', 25)
        stats.print_stats('itb_emoji', 50)
        stats.print_stats('itb_pango', 25)
        LOGGER.info('Profiling info:\n%s', stats_stream.getvalue())
        LOGGER.info(
            'itb_util.remove_accents() cache info: %s',
            itb_util.remove_accents.cache_info())
        LOGGER.info(
            'itb_emoji.EmojiMatcher.variation_selector_normalize() cache info: %s',
            itb_emoji.EmojiMatcher.variation_selector_normalize.cache_info()) # pylint: disable=no-value-for-parameter
        LOGGER.info(
            'itb_emoji.EmojiMatcher.get_all_label_words() cache info: %s',
            itb_emoji.EmojiMatcher.get_all_label_words.cache_info()) # pylint: disable=no-value-for-parameter
        LOGGER.info(
            'itb_emoji._match_classic() cache info: %s',
            itb_emoji._match_classic.cache_info()) # pylint: disable=no-value-for-parameter, protected-access
        LOGGER.info(
            'itb_emoji._match_rapidfuzz() cache info: %s',
            itb_emoji._match_rapidfuzz.cache_info()) # pylint: disable=no-value-for-parameter, protected-access

    def on_close(self, *_args: Any) -> bool:
        ''' The window has been deleted, probably by the window manager. '''
        LOGGER.info('Window deleted by the window manager.')
        self._save_recently_used_emoji()
        if _ARGS.debug:
            self.__class__.print_profiling_information()
        if GLIB_MAIN_LOOP is not None:
            GLIB_MAIN_LOOP.quit()
        else:
            raise RuntimeError("GLIB_MAIN_LOOP not initialized!")
        # Gtk3 expects a boolean return value, Gtk4 ignores the return value:
        return False

    def on_main_window_key_pressed_gtk4(
            self,
            _controller: 'Gtk.EventControllerKey',
            keyval: int,
            keycode: int,
            state: 'Gdk.ModifierType',
    ) -> bool:
        '''
        Gtk4 key-pressed signal handler.

        Gtk4 no longer provides Gdk.EventKey objects for window-level
        key events, so this callback receives the raw keyval/keycode/state
        values from EventControllerKey.  To keep the Gtk3 and Gtk4 code paths
        unified, we wrap these values in a FakeEventKey instance and forward
        them to on_main_window_key_press_event(), which contains the common
        key handling logic.

        Returns:
            bool: True if the event was handled.
        '''
        return self.on_main_window_key_press_event(
            self, FakeEventKey(keyval, keycode, state))

    def on_main_window_key_press_event(
            self,
            _window: Gtk.Window,
            event_key: 'Gdk.EventKey', # pylint: disable=c-extension-no-member
    ) -> bool:
        '''
        Some key has been typed into the main window

        :param _window: The main window
        :param event_key:
        '''
        if _ARGS.debug:
            LOGGER.debug('keyval = %s\n', event_key.keyval)
        if self._fontsize_spin_button.has_focus():
            if _ARGS.debug:
                LOGGER.debug(
                    'self._fontsize_spin_button has focus\n')
            # if the fontsize spin button has focus, we do not want
            # to take it away from there by popping up the search bar.
            return False
        # https://developer.gnome.org/gdk3/stable/gdk3-Event-Structures.html#GdkEventKey
        # See /usr/include/gtk-3.0/gdk/gdkkeysyms.h for a list
        # of Gdk keycodes
        if (event_key.keyval in (
                Gdk.KEY_Tab,
                Gdk.KEY_Down, Gdk.KEY_KP_Down,
                Gdk.KEY_Up, Gdk.KEY_KP_Up,
                Gdk.KEY_Page_Down, Gdk.KEY_KP_Page_Down,
                Gdk.KEY_Page_Up, Gdk.KEY_KP_Page_Up)):
            self._search_bar.set_search_mode(False)
            return False
        if not event_key.string:
            return False
        self._search_bar.set_search_mode(True)
        show_all(self._search_bar)
        # The search entry needs to be realized to be able to
        # handle a key event. If it is not realized yet when
        # the key event arrives, one will get the message:
        #
        # Gtk-CRITICAL **: gtk_widget_event:
        # assertion 'WIDGET_REALIZED_FOR_EVENT (widget, event)' failed
        #
        # and the typed key will not appear in the search entry.
        #
        # The show_all(self._search_bar) realizes the search
        # entry, but only when the pending events are handled.
        # So we need to call Gtk.main_iteration() while events
        # are pending.
        #
        # But *only* if the search entry is not realized yet,
        # i.e. only if self._search_entry.get_window() returns “None”.
        # After the first key press it is realized and we must not do
        # this anymore. Continuing to handle the pending events here
        # when the search entry is already realized makes the keys
        # appear out of order in the search entry when typing
        # fast. For example, when typing “flow” fast one may get
        # “flwo”.
        if not self._search_entry.get_realized():
            # Process pending events, replacement for:
            # while Gtk.events_pending():
            #     Gtk.main_iteration())
            ctx = GLib.MainContext.default() # pylint: disable=no-value-for-parameter
            while ctx.pending():
                ctx.iteration(False)
                if SIGNAL_HANDLER.interrupt_requested:
                    LOGGER.info('Control+C pressed, exiting ...')
                    sys.exit(1)
        if GTK_MAJOR < 4:
            return bool(self._search_bar.handle_event(event_key))
        # Gtk4:
        return forward_key_event_to_entry(event_key, self._search_entry)

    def on_about_button_clicked(self, button: Gtk.Button) -> None:
        '''
        The “About” button has been clicked

        :param _button: The “About” button
        '''
        if _ARGS.debug:
            LOGGER.debug('on_about_button_clicked()\n')
        self._popup_manager.popdown_current()
        itb_util.ItbAboutDialog(parent=get_toplevel_window(button))

    def _fill_flowbox_with_search_results(self) -> None:
        '''
        Get the emoji candidates for the current query string
        and fill the flowbox with the results of the query.
        '''
        if _ARGS.debug:
            LOGGER.debug(
                '_fill_flowbox_with_search_results() query_string = %s\n',
                self._query_string)
        self._search_timeout_source_id = 0
        self._busy_start()
        self._clear_flowbox()
        query_string = self._query_string
        candidates = self._emoji_matcher.candidates(
            query_string,
            match_limit=self._match_limit,
            spellcheck=self._spellcheck)

        self._browse_treeview_unselect_all()
        self._header_bar.set_title(_('Search Results'))
        self._header_bar.set_subtitle(f'({(len(candidates))})')

        if not candidates:
            candidates = [itb_util.PredictionCandidate(
                phrase='∅',
                user_freq=1,
                comment=_('Search produced empty result.'))]

        for index, candidate in enumerate(candidates):
            self._busy_fraction(index/len(candidates))
            # Process pending events, replacement for:
            # while Gtk.events_pending():
            #     Gtk.main_iteration())
            while GLib.MainContext.default().iteration(False): # pylint: disable=no-value-for-parameter
                if SIGNAL_HANDLER.interrupt_requested:
                    LOGGER.info('Control+C pressed, exiting ...')
                    sys.exit(1)
            if self._query_string != query_string:
                # If the query string changed, stop filling the flowbox
                # with the results of the old query:
                LOGGER.debug(
                    'query string changed: %r -> %r',
                    query_string, self._query_string)
                self._busy_stop()
                return
            emoji = self._variation_selector_normalize_for_font(candidate.phrase)
            score = candidate.user_freq
            name = candidate.comment
            label = Gtk.Label()
            # Make font for emoji large using pango markup
            fallback = self._optimize_pango_fallback(emoji)
            text = (
                f'<span font="{self._font} {self._fontsize}" '
                f'fallback="{str(fallback).lower()}">'
                + html.escape(emoji)
                + '</span>'
                + f'<span font="{self._fontsize / 2}">'
                + ' ' + html.escape(name)
                + '</span>')
            if _ARGS.debug:
                text += (
                    f'<span font="{self._fontsize / 2}" foreground="red">'
                    + f' {score:0.2f}'
                    + '</span>')
            label.set_text(text)
            label.set_use_markup(True)
            label.set_can_focus(False)
            label.set_selectable(False)
            label.set_hexpand(False)
            label.set_vexpand(False)
            label.set_xalign(0)
            label.set_yalign(0.5)
            # Gtk.Align.FILL, Gtk.Align.START, Gtk.Align.END,
            # Gtk.Align.CENTER, Gtk.Align.BASELINE
            label.set_halign(Gtk.Align.FILL)
            label.set_valign(Gtk.Align.FILL)
            margin = 0
            label.set_margin_start(margin)
            label.set_margin_end(margin)
            label.set_margin_top(margin)
            label.set_margin_bottom(margin)
            self._emoji_label_set_tooltip(emoji, label)
            event_box = ClickableEventBoxCompat()
            add_child(event_box, label)
            event_box.connect(
                'clicked', self.on_flowbox_event_box_button_press)
            event_box.connect(
                'released', self.on_flowbox_event_box_button_release)
            event_box.connect(
                'long-pressed', self.on_flowbox_event_box_long_press_pressed)
            self._flowbox.insert(event_box, -1)
            # showing after each insert shows some progress
            show_all(self._flowbox)

        show_all(self)
        emoji_labels = emoji_flowbox_get_labels(self._flowbox)
        if emoji_labels:
            # Auto-select the first search result:
            self._emoji_label_selected(emoji_labels[0], show_popover=False)
        self._busy_stop()

    def on_fontsize_spin_button_grab_focus( # pylint: disable=no-self-use
            self,
            spin_button: Gtk.SpinButton,
            *_args: Any,
    ) -> bool:
        '''
        Signal handler called when the spin button to change
        the font size grabs focus

        :param spin_button: The spin button to change the font size
        '''
        if _ARGS.debug:
            LOGGER.debug(
                'on_fontsize_spin_button_grab_focus() spin_button = %s\n',
                repr(spin_button))
        grab_focus_without_selecting(spin_button)
        # The default signal handler would again select the contents
        # of the search entry. Therefore, we must prevent the default
        # signal handler from running:
        if GTK_MAJOR < 4:
            GObject.signal_stop_emission_by_name(spin_button, 'grab-focus')
        return True

    def on_search_entry_grab_focus( # pylint: disable=no-self-use
            self,
            search_entry: Gtk.SearchEntry,
            *_args: Any,
    ) -> bool:
        '''
        Signal handler called when the search entry grabs focus

        :param search_entry: The search entry
        '''
        if _ARGS.debug:
            LOGGER.debug(
                'on_search_entry_grab_focus() search_entry = %s\n',
                repr(search_entry))
        grab_focus_without_selecting(search_entry)
        # The default signal handler would again select the contents
        # of the search entry. Therefore, we must prevent the default
        # signal handler from running:
        if GTK_MAJOR < 4:
            GObject.signal_stop_emission_by_name(search_entry, 'grab-focus')
        return True

    def on_search_entry_search_changed(
            self,
            search_entry: Gtk.SearchEntry) -> None:
        '''
        Signal handler for changed text in the search entry

        :param search_entry: The search entry
        '''
        query_string = search_entry.get_text()
        if _ARGS.debug:
            LOGGER.debug(
                'on_search_entry_search_changed() query_string = %s\n',
                query_string)
        self._currently_selected_label = None # stop label processing
        if not self._search_bar.get_search_mode():
            # If the text in the search entry changes while
            # the search bar is invisible, ignore it.
            return
        if query_string.isspace():
            # Keep it possible to search for space like characters
            # when typing just white space characters, keep the last
            # white space character typed and search for that:
            query_string = query_string[-1:]
        else:
            # If the query_string contains non-whitespace characters,
            # strip it otherwise 'black cat ' would not be an exact match
            # for 'black cat'.
            query_string = query_string.strip()
        if query_string == self._query_string:
            if _ARGS.debug:
                LOGGER.debug(
                    'query string effectively unchanged (only whitespace change)')
            return
        self._query_string = query_string
        if self._search_timeout_source_id:
            GLib.source_remove(self._search_timeout_source_id)
            self._search_timeout_source_id = 0
        self._search_timeout_source_id = GLib.timeout_add(
            100, # 100 milliseconds, hardcoded for the moment
            self._fill_flowbox_with_search_results)

    def on_label_selected(
            self,
            selection: Gtk.TreeSelection) -> None:
        '''
        Signal handler for selecting a category in the list of categories

        :param selection: The selected row in the browsing treeview
        '''
        (model, iterator) = selection.get_selected()
        if not iterator:
            return
        if _ARGS.debug:
            LOGGER.debug(
                'model[iterator] = %s\n'
                'self._currently_selected_label = %s\n',
                model[iterator][:],
                repr(self._currently_selected_label))
        # stop search processing
        self._search_bar.set_search_mode(False)
        self._search_entry.set_text('')
        self._query_string = ''
        self._browse_treeview.grab_focus()
        language = model[iterator][1]
        label_key = model[iterator][2]
        label = model[iterator][3]
        if self._currently_selected_label == (language, label_key, label):
            return
        self._currently_selected_label = (language, label_key, label)
        GLib.idle_add(self._fill_flowbox_browse)

    def on_row_activated( # pylint: disable=no-self-use
            self,
            treeview: Gtk.TreeView,
            treepath: Gtk.TreePath,
            column: Gtk.TreeViewColumn) -> None:
        '''Signal handler for activating a row in the browsing treeview

        :param treeview: The browsing treeview
        :param treepath: The path of the activated row in the browsing treeview
        :param column: The column of the activated row in the browsing treeview
        '''
        if _ARGS.debug:
            LOGGER.debug(
                'on_row_activated() %s %s %s\n',
                repr(treeview), repr(treepath), repr(column))

    def _optimize_pango_fallback(self, emoji: str) -> bool:
        '''
        Which fallback value to use best in the pango markup for this emoji.

        If fallback is requested, pango may fall back to a different font,
        even if the currently selected font supports the emoji just fine.
        In that case, avoid the fallback.
        '''
        if not self._fallback:
            return False
        if not itb_pango.emoji_font_fallback_needed(self._font, emoji):
            return False
        return True

    def _parse_emoji_and_name_from_text( # pylint: disable=no-self-use
            self, text: str) -> Tuple[str, str]:
        '''
        Parse the emoji and its name out of the text of a label

        Returns a tuple of two strings of the form (emoji, name)

        :param text: The text with markup containing the emoji
                     and maybe its name
        '''
        emoji = ''
        name = ''
        pattern = re.compile(
            r'<span[^<]*?>(?P<emoji>[^<]+?)</span>'
            + r'(<span[^<]*?>(?P<name>[^<]+?)</span>)?')
        match = pattern.match(text)
        if match:
            emoji = html.unescape(match.group('emoji'))
            if match.group('name'):
                name = html.unescape(match.group('name'))
        if _ARGS.debug:
            LOGGER.debug(
                'text = %s emoji = %s name = %s\n',
                text, emoji, name)
        return (emoji, name)

    def _emoji_label_selected(
            self,
            emoji_label: Gtk.Label,
            show_popover: bool = True,
    ) -> bool:
        '''
        Called when an emoji label was selected in the flowbox.

        The emoji is then copied to the clipboard and a popover
        pops up for a short time to notify the user that the emoji
        has been copied to the clipboard.

        :param emoji_label: The Gtk.Label which contains the emoji
        '''
        # Use .get_label() instead of .get_text() to fetch the text
        # from the label widget including any embedded underlines
        # indicating mnemonics and Pango markup. The emoji is in
        # first <span>...</span>, and we want fetch only the emoji
        # here:
        text = emoji_label.get_label()
        if _ARGS.debug:
            LOGGER.debug('text = %s\n', text)
        (emoji, _name) = self._parse_emoji_and_name_from_text(text)
        if not emoji:
            # Gdk.EVENT_PROPAGATE is defined as False
            return bool(Gdk.EVENT_PROPAGATE)
        self._show_concise_emoji_description_in_header_bar(emoji)
        self._set_clipboards(emoji)
        self._add_to_recently_used(emoji)
        if not show_popover:
            return True # Gdk.EVENT_PROPAGATE is defined as False
        self._emoji_selected_popover = create_popover(
            pointing_to=emoji_label, position=Gtk.PositionType.TOP)
        popover = self._emoji_selected_popover
        popover.set_can_focus(True)
        label = Gtk.Label()
        label.set_text(_('Copied to clipboard!'))
        add_child(popover, label)
        self._popup_manager.popup(popover, PopupKind.EMOJI_SELECTED)
        GLib.timeout_add(
            500, lambda:
            self._popup_manager.popdown_current(kind=PopupKind.EMOJI_SELECTED))
        return True # Gdk.EVENT_PROPAGATE is defined as False

    def on_emoji_selected(
            self,
            _flowbox: Gtk.FlowBox,
            flowbox_child: Gtk.FlowBoxChild) -> Gdk.EVENT_PROPAGATE:
        '''
        Signal handler for selecting an emoji in the flowbox
        via the flowbox selection

        Not called if long press gestures are used to show the
        skin tone popovers. In that case, emoji selection is handled
        in on_flowbox_event_box_button_release() instead.

        :param _flowbox: The flowbox displaying the Emoji
        :param flowbox_child: The child object containing the selected emoji
        '''
        if _ARGS.debug:
            LOGGER.debug("on_emoji_selected()\n")
        if GTK_MAJOR >= 4:
            emoji_label = flowbox_child.get_child().get_first_child()
        else:
            emoji_label = flowbox_child.get_child().get_child()
        self._emoji_label_selected(emoji_label)
        return Gdk.EVENT_PROPAGATE

    def on_main_menu_button_clicked(self, button: Gtk.Button) -> None:
        '''
        The main menu button has been clicked

        :param _button: The main menu button
        '''
        if _ARGS.debug:
            LOGGER.debug('on_main_menu_button_clicked()\n')
        self._main_menu_popover = create_popover(
            pointing_to=button, position=Gtk.PositionType.BOTTOM)
        popover = self._main_menu_popover
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.set_can_focus(True)
        vbox = Gtk.Box()
        vbox.set_orientation(Gtk.Orientation.VERTICAL)
        vbox.set_spacing(0)
        clear_recently_used_button = Gtk.Button(label=_('Clear recently used'))
        clear_recently_used_button.connect(
            'clicked', self.on_clear_recently_used_button_clicked)
        add_child(vbox, clear_recently_used_button)
        if not self._modal:
            about_button = Gtk.Button(label=_('About'))
            about_button.connect('clicked', self.on_about_button_clicked)
            add_child(vbox, about_button)
        quit_button = Gtk.Button(label=_('Quit'))
        quit_button.connect('clicked', self.on_close)
        add_child(vbox, quit_button)
        add_child(popover, vbox)
        self._popup_manager.popup(popover, kind=PopupKind.MAIN_MENU)

    def on_toggle_search_button_clicked(self, _button: Gtk.Button) -> None:
        '''
        The search button in the header bar has been clicked

        :param _button: The search button
        '''
        if _ARGS.debug:
            LOGGER.debug('on_toggle_search_button_clicked()\n')
        self._search_bar.set_search_mode(
            not self._search_bar.get_search_mode())

    def _change_flowbox_font(self) -> None:
        '''
        Update the font and fontsize used in the current content
        of the flowbox.
        '''
        for label in emoji_flowbox_get_labels(self._flowbox):
            text = label.get_label()
            (emoji, name) = self._parse_emoji_and_name_from_text(text)
            if emoji:
                emoji = self._variation_selector_normalize_for_font(emoji)
                fallback = self._optimize_pango_fallback(emoji)
                new_text = (
                    f'<span font="{self._font} {self._fontsize}" '
                    f'fallback="{str(fallback).lower()}">'
                    + html.escape(emoji)
                    + '</span>')
                if name:
                    new_text += (
                        f'<span fallback="true" font="{self._fontsize / 2}">'
                        + html.escape(name)
                        + '</span>')
                label.set_text(new_text)
                label.set_use_markup(True)
        show_all(self._flowbox)

    def on_skin_tone_selected(
            self,
            _flowbox: Gtk.FlowBox,
            flowbox_child: Gtk.FlowBoxChild) -> None:
        '''
        Signal handler for selecting a skin tone emoji

        :param _flowbox: The flowbox displaying the skin tone emoji
        :param flowbox_child: The child object containing the selected emoji
        '''
        # Use .get_label() instead of .get_text() to fetch the text
        # from the label widget including any embedded underlines
        # indicating mnemonics and Pango markup. The emoji is in
        # first <span>...</span>, and we want fetch only the emoji
        # here:
        emoji_label = flowbox_child.get_child()
        text = emoji_label.get_label()
        if _ARGS.debug:
            LOGGER.debug('on_skin_tone_selected() text = %s\n', text)
        (emoji, _name) = self._parse_emoji_and_name_from_text(text)
        if not emoji:
            return
        self._show_concise_emoji_description_in_header_bar(emoji)
        self._set_clipboards(emoji)
        self._add_to_recently_used(emoji)
        # When an emoji with a different skin tone is selected in a
        # skin tone popover opened in a browse flowbox (not a search
        # results flowbox), replace the original emoji which was used
        # to open the popover immediately.
        if self._skin_tone_popover_originated_from_emoji_label is None:
            LOGGER.debug(
                'self._skin_tone_popover_originated_from_emoji_label is None')
            return
        orig_emoji_label = self._skin_tone_popover_originated_from_emoji_label
        text = orig_emoji_label.get_label()
        (old_emoji, old_name) = self._parse_emoji_and_name_from_text(text)
        if old_emoji and not old_name:
            # If the old emoji has a name, this is a line
            # in a search results flowbox and we do *not* want
            # to replace the emoji.
            fallback = self._optimize_pango_fallback(emoji)
            new_text = (
                f'<span font="{self._font} {self._fontsize}" '
                f'fallback="{str(fallback).lower()}">'
                + html.escape(emoji)
                + '</span>')
            orig_emoji_label.set_text(new_text)
            orig_emoji_label.set_use_markup(True)
        self._skin_tone_selected_popover = create_popover(
            pointing_to=orig_emoji_label, position=Gtk.PositionType.TOP)
        popover = self._skin_tone_selected_popover
        label = Gtk.Label()
        label.set_text(_('Copied to clipboard!'))
        add_child(popover, label)
        self._popup_manager.popup(popover, PopupKind.EMOJI_SELECTED)
        GLib.timeout_add(
            500, lambda:
            self._popup_manager.popdown_current(kind=PopupKind.EMOJI_SELECTED))

    def on_flowbox_event_box_long_press_pressed(
            self,
            event_box: 'ClickableEventBoxCompat',
    ) -> None:
        '''
        :param event_box: The event box containing the label with the emoji.
        '''
        if _ARGS.debug:
            LOGGER.debug(
                'on_flowbox_event_box_long_press_pressed() %r', event_box)
        self._show_skin_tone_popover(event_box)

    def on_flowbox_event_box_button_press( # pylint: disable=no-self-use
            self,
            event_box: 'ClickableEventBoxCompat',
            button: int,
    ) -> bool:
        '''Signal handler for button presses in flowbox children

        Does nothing because a button press could still turn into
        a long press. Only if the button release handler is called
        we know that it was not a long press. So call the
        short press button actions in the release handler!

        :param event_box: The event box containing the label with the emoji.
        :param button: The mouse button number (1, 2, 3)
        '''
        if _ARGS.debug:
            LOGGER.debug('event_box=%r button=%d', event_box, button)
        return bool(Gdk.EVENT_PROPAGATE)

    def on_flowbox_event_box_button_release(
            self,
            event_box: 'ClickableEventBoxCompat',
            button: int,
    ) -> bool:
        '''
        Signal handler for button release events on labels in the flowbox

        :param event_box: The event box containing the label with the emoji.
        :param button: The mouse button number (1, 2, 3)
        '''
        if _ARGS.debug:
            LOGGER.debug('event_box=%r button=%d', event_box, button)
        if button == 1:
            emoji_label = clickable_event_box_compat_get_gtk_label(event_box)
            self._emoji_label_selected(emoji_label)
        if button == 2:
            self._show_skin_tone_popover(event_box)
        if button == 3:
            self._show_emoji_info_popover(event_box)
        return bool(Gdk.EVENT_PROPAGATE)

    def _show_skin_tone_popover(
            self, event_box: 'Gtk.EventBox', # pylint: disable=c-extension-no-member
    ) -> None:
        '''
        Show a skin tone popover if there is an emoji in this event box
        which supports skin tones.

        If there is no emoji or it does not support skin tones, do nothing.

        :param event_box: The event box containing the label with the emoji.
                          The popover will be relative to this event box.
        '''
        emoji_label = clickable_event_box_compat_get_gtk_label(event_box)
        self._skin_tone_popover_originated_from_emoji_label = emoji_label
        text = emoji_label.get_label()
        (emoji, _name) = self._parse_emoji_and_name_from_text(text)
        if not emoji:
            return
        skin_tone_variants = []
        for skin_tone_variant in self._emoji_matcher.skin_tone_variants(emoji):
            skin_tone_variants.append(
                self._variation_selector_normalize_for_font(skin_tone_variant))
        if len(skin_tone_variants) <= 1:
            return
        self._skin_tone_popover = create_popover(
            pointing_to=emoji_label, position=Gtk.PositionType.TOP)
        popover = self._skin_tone_popover
        popover.set_vexpand(False)
        popover.set_hexpand(False)
        grid = Gtk.Grid()
        margin = 1
        grid.set_margin_start(margin)
        grid.set_margin_end(margin)
        grid.set_margin_top(margin)
        grid.set_margin_bottom(margin)
        flowbox = Gtk.FlowBox()
        flowbox.get_style_context().add_class('view')
        flowbox.set_valign(Gtk.Align.START)
        flowbox.set_min_children_per_line(3)
        flowbox.set_max_children_per_line(3)
        flowbox.set_row_spacing(0)
        flowbox.set_column_spacing(0)
        flowbox.set_activate_on_single_click(True)
        flowbox.set_selection_mode(
            Gtk.SelectionMode.NONE)
        flowbox.set_can_focus(False)
        flowbox.set_homogeneous(False)
        flowbox.set_hexpand(True)
        flowbox.set_vexpand(True)
        flowbox.connect('child-activated', self.on_skin_tone_selected)
        for skin_tone_variant in skin_tone_variants:
            label = Gtk.Label()
            fallback = self._optimize_pango_fallback(emoji)
            label.set_text(
                f'<span font="{self._font} {self._fontsize}" '
                f'fallback="{str(fallback).lower()}">'
                + html.escape(skin_tone_variant)
                + '</span>')
            label.set_use_markup(True)
            label.set_can_focus(False)
            label.set_selectable(False)
            label.set_hexpand(False)
            label.set_vexpand(False)
            label.set_xalign(0.5)
            label.set_yalign(0.5)
            # Gtk.Align.FILL, Gtk.Align.START, Gtk.Align.END,
            # Gtk.Align.CENTER, Gtk.Align.BASELINE
            label.set_halign(Gtk.Align.FILL)
            label.set_valign(Gtk.Align.FILL)
            margin = 0
            label.set_margin_start(margin)
            label.set_margin_end(margin)
            label.set_margin_top(margin)
            label.set_margin_bottom(margin)
            label.set_tooltip_text(_('Left click to copy'))
            label.set_can_focus(False)
            flowbox.insert(label, -1)
        scroll = Gtk.ScrolledWindow()
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.set_kinetic_scrolling(False)
        scroll.set_overlay_scrolling(True)
        add_child(scroll, flowbox)
        grid.attach(scroll, 0, 0, 1, 1)
        add_child(popover, grid)
        show_all(grid)
        (_min_width_flowbox, natural_width_flowbox) = get_preferred_width(flowbox)
        (_min_height_flowbox, natural_height_flowbox) = get_preferred_height(flowbox)
        (window_width, window_height) = get_window_size(self)
        grid.set_size_request(
            min(0.6 * window_width, natural_width_flowbox),
            min(0.6 * window_height, natural_height_flowbox))
        self._popup_manager.popup(popover, kind=PopupKind.SKIN_TONE)

    def _show_emoji_info_popover(
            self,
            event_box: 'Gtk.EventBox', # pylint: disable=c-extension-no-member
    ) -> None:
        '''
        Show an info popover if there is an emoji in this event box.

        If there is no emoji in the event box, do nothing.

        :param event_box: The event box containing the label with the emoji.
                          The popover will be relative to this event box.
        '''
        emoji_label = clickable_event_box_compat_get_gtk_label(event_box)
        text = emoji_label.get_label()
        (emoji, _name) = self._parse_emoji_and_name_from_text(text)
        if not emoji:
            return
        self._emoji_info_popover = create_popover(
            pointing_to=emoji_label, position=Gtk.PositionType.BOTTOM)
        popover = self._emoji_info_popover
        popover.set_vexpand(False)
        popover.set_hexpand(False)
        vbox = Gtk.Box()
        vbox.set_orientation(Gtk.Orientation.VERTICAL)
        vbox.set_vexpand(False)
        vbox.set_hexpand(False)
        margin = 0
        vbox.set_margin_start(margin)
        vbox.set_margin_end(margin)
        vbox.set_margin_top(margin)
        vbox.set_margin_bottom(margin)
        vbox.set_spacing(margin)
        scroll = Gtk.ScrolledWindow()
        add_child(vbox, scroll)
        listbox = Gtk.ListBox()
        listbox.set_visible(True)
        listbox.set_can_focus(False)
        listbox.set_vexpand(True)
        listbox.set_hexpand(False)
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        listbox.set_activate_on_single_click(True)
        add_child(scroll, listbox)
        label = Gtk.Label()
        label.set_hexpand(False)
        label.set_vexpand(False)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.START)
        fallback = self._optimize_pango_fallback(emoji)
        label.set_markup(
            f'<span font="{self._font} {self._fontsize * 3}" '
            f'fallback="{str(fallback).lower()}">'
            + html.escape(emoji)
            + '</span>')
        listbox.insert(label, -1)
        for description in self._emoji_descriptions(emoji):
            label_description = Gtk.Label()
            margin = 0
            label_description.set_margin_start(margin)
            label_description.set_margin_end(margin)
            label_description.set_margin_top(margin)
            label_description.set_margin_bottom(margin)
            label_description.set_selectable(True)
            label_description.set_hexpand(False)
            label_description.set_vexpand(False)
            label_description.set_halign(Gtk.Align.START)
            label_description.set_valign(Gtk.Align.START)
            set_label_wrap_mode(
                label_description, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
            label_description.set_markup(description)
            listbox.insert(label_description, -1)
        if (self._emoji_matcher.cldr_order(emoji) < 0xFFFFFFFF
                or self._emoji_matcher.properties(emoji)):
            linkbutton = Gtk.LinkButton.new_with_label(
                _('Lookup on emojipedia'))
            linkbutton.set_uri(
                'http://emojipedia.org/emoji/' + emoji + '/')
            linkbutton.set_halign(Gtk.Align.START)
            listbox.insert(linkbutton, -1)
        for row in children_of(listbox):
            row.set_activatable(False)
            row.set_selectable(False)
            row.set_can_focus(False)
        add_child(popover, vbox)
        show_all(vbox)
        (_min_width_vbox, natural_width_vbox) = get_preferred_width(vbox)
        (_min_height_vbox, natural_height_vbox) = get_preferred_height(vbox)
        (_min_width_listbox, natural_width_listbox) = get_preferred_width(listbox)
        (_min_height_listbox, natural_height_listbox) = get_preferred_height(listbox)
        (window_width, window_height) = get_window_size(self)
        popover.set_size_request(
            min(0.6 * window_width,
                natural_width_vbox + natural_width_listbox),
            min(0.6 * window_height,
                natural_height_vbox + natural_height_listbox))
        self._popup_manager.popup(popover, kind=PopupKind.EMOJI_INFO)

    def on_fontsize_adjustment_value_changed(
            self, adjustment: Gtk.Adjustment) -> None:
        '''
        The fontsize adjustment in the header bar has been changed

        :param adjustment: The adjustment used to change the fontsize
        '''
        value = adjustment.get_value()
        if _ARGS.debug:
            LOGGER.debug(
                'on_fontsize_adjustment_value_changed() value = %s\n', value)
        self._fontsize = value
        self._save_options()
        GLib.idle_add(self._change_flowbox_font)

    def on_fallback_check_button_toggled(
            self, check_button: Gtk.CheckButton) -> None:
        '''
        The fallback check button in the header bar has been toggled

        :param toggle_button: The check button used to select whether
                              fallback fonts should be used.
        '''
        self._fallback = check_button.get_active()
        if _ARGS.debug:
            LOGGER.debug(
                'on_fallback_check_button_toggled() self._fallback = %s\n',
                self._fallback)
        self._save_options()
        GLib.idle_add(self._change_flowbox_font)

    def _list_font_names(self) -> List[str]:
        '''
        Returns a list of font names available on the system
        '''
        # pylint: disable=line-too-long
        good_emoji_fonts = [
            # color fonts are marked with ' 🎨' in this list,
            # black and white fonts with ' 🙾'.
            'Noto Color Emoji 🎨',
            # https://github.com/C1710/blobmoji (Old “blob” style Google emoji,
            # fork of Noto Color Emoji)
            'Blobmoji 🎨',
            # “OpenMoji Color”: https://openmoji.org/
            # It is available in the “hfg-gmuend-openmoji-color-fonts”
            # package on Fedora.
            'OpenMoji Color 🎨',
            # “Twitter Color Emoji” is a font with SVG images in an
            # OpenType font.  One can get it from
            # https://github.com/13rac1/twemoji-color-font The latest
            # release is currently:
            # https://github.com/13rac1/twemoji-color-font/releases/download/v15.1.0/TwitterColorEmoji-SVGinOT-Linux-15.1.0.tar.gz
            # Just unpack the tarball in ~/.fonts/ I tested that it
            # works well (in colour!) on Fedora 40 and Fedora 41.
            'Twitter Color Emoji 🎨',
            'Twemoji 🎨', # color
            # https://github.com/toss/tossface/, https://toss.im/tossface
            # https://toss.im/tossface/copyright (free for personal use,
            # attribution required if used publicly)
            'Toss Face Font Web 🎨',
            'Apple Color Emoji 🎨',
            'Emoji Two 🎨',
            'Emoji One 🎨',
            'JoyPixels 🎨',
            'Segoe UI Emoji 🎨', # newer versions are in color
            # “OpenMoji Black” is available at: https://openmoji.org/
            'OpenMoji Black 🙾',
            'Symbola 🙾',
            'Noto Emoji 🙾',
            'Android Emoji 🙾',
            # 2001 era DoCoMo emojis from: https://meowni.ca/posts/og-emoji-font/
            'og-dcm-emoji 🙾'
        ]
        # pylint: enable=line-too-long
        available_good_emoji_fonts = [
            'emoji (' + _('System default') + ')',
            'text (' + _('System default') + ')',
            'unqualified (' + _('System default') + ')',
        ]
        available_good_emoji_fonts.append('')
        pango_context = self.get_pango_context()
        families = pango_context.list_families()
        names = sorted([family.get_name() for family in families])
        for font in good_emoji_fonts:
            name = font.split(' ', maxsplit=1)[0]
            if name in names:
                names.remove(name)
                available_good_emoji_fonts.append(font)
        available_good_emoji_fonts.append('')
        names = available_good_emoji_fonts + names
        return names

    def _fill_listbox_font(self, filter_text: str) -> None:
        '''
        Fill the listbox of fonts to choose from

        :param filter_text: The filter text to limit the
                            fonts listed. Only fonts which
                            contain the the filter text as
                            a substring (ignoring case and spaces)
                            are listed.
        '''
        if _ARGS.debug:
            LOGGER.debug(
                '_fill_listbox_font() filter_text = %s\n', filter_text)
        if self._font_popover_scroll is None:
            LOGGER.debug('self._font_popover_scroll is None')
            return
        clear_children(self._font_popover_scroll)
        self._font_popover_listbox = Gtk.ListBox()
        if self._font_popover_listbox is None:
            LOGGER.debug('self._font_popover_listbox is None')
            return
        add_child(self._font_popover_scroll, self._font_popover_listbox)
        self._font_popover_listbox.set_visible(True)
        self._font_popover_listbox.set_vexpand(True)
        self._font_popover_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._font_popover_listbox.set_activate_on_single_click(True)
        self._font_popover_listbox.connect(
            'row-selected', self.on_font_selected)
        fonts = [
            font
            for font in self._list_font_names()
            if filter_text.replace(' ', '').lower()
            in font.replace(' ', '').lower()]
        for font in fonts:
            label = Gtk.Label()
            label.set_text(font)
            label.set_xalign(0)
            margin = 1
            label.set_margin_start(margin)
            label.set_margin_end(margin)
            label.set_margin_top(margin)
            label.get_style_context().add_class('font')
            label.set_margin_bottom(margin)
            self._font_popover_listbox.insert(label, -1)
        if self._font_popover is None:
            LOGGER.debug('self._font_popover is None')
            return
        show_all(self._font_popover)

    def on_font_search_entry_search_changed(
            self, search_entry: Gtk.SearchEntry) -> None:
        '''
        Signal handler for changed text in the font search entry

        :param widget: The search entry
        '''
        filter_text = search_entry.get_text()
        if _ARGS.debug:
            LOGGER.debug(
                'on_font_search_entry_search_changed() filter_text = %s\n',
                filter_text)
        self._fill_listbox_font(filter_text)

    def on_font_selected(
            self,
            _listbox: Gtk.ListBox,
            listbox_row: Gtk.ListBoxRow) -> None:
        '''
        Signal handler for selecting a font

        :param _listbox: The list box used to select a font
        :param listbox_row: A row containing a font name
        '''
        font = listbox_row.get_child().get_text().split(' ')[0]
        if _ARGS.debug:
            LOGGER.debug('on_font_selected() font = %s\n', repr(font))
        if font == '':
            font = 'emoji'
        if font != self._font and font in ('emoji', 'text', 'unqualified'):
            self._fallback = True
            self._fallback_check_button.set_active(True)
        else:
            self._fallback = False
            self._fallback_check_button.set_active(False)
        self._popup_manager.popdown_current()
        self._font = font
        self._font_button.set_label(self._font)
        self._save_options()
        GLib.idle_add(self._change_flowbox_font)

    def on_font_button_clicked(self, button: Gtk.Button) -> None:
        '''
        The font button in the header bar has been clicked

        :param _button: The font button
        '''
        if _ARGS.debug:
            LOGGER.debug(
                'on_font_button_clicked()\n')
        self._font_popover = create_popover(
            pointing_to=button, position=Gtk.PositionType.BOTTOM)
        popover = self._font_popover
        (window_width, window_height) = get_window_size(self)
        desired_width = int(window_width * 0.2)
        desired_height = int(window_height * 0.9)
        popover.set_size_request(desired_width, desired_height)
        popover.set_can_focus(True)
        popover.set_vexpand(True)
        vbox = Gtk.Box()
        vbox.set_orientation(Gtk.Orientation.VERTICAL)
        margin = 12
        vbox.set_margin_start(margin)
        vbox.set_margin_end(margin)
        vbox.set_margin_top(margin)
        vbox.set_margin_bottom(margin)
        vbox.set_spacing(margin)
        label = Gtk.Label()
        label.set_text(_('Set Font'))
        label.set_visible(True)
        label.set_halign(Gtk.Align.FILL)
        add_child(vbox, label)
        search_entry = Gtk.SearchEntry()
        search_entry.set_can_focus(True)
        search_entry.set_visible(True)
        search_entry.set_halign(Gtk.Align.FILL)
        search_entry.set_hexpand(False)
        search_entry.set_vexpand(False)
        search_entry.connect(
            'search_changed', self.on_font_search_entry_search_changed)
        add_child(vbox, search_entry)
        self._font_popover_scroll = Gtk.ScrolledWindow()
        self._fill_listbox_font('')
        add_child(vbox, self._font_popover_scroll)
        add_child(popover, vbox)
        self._popup_manager.popup(popover, kind=PopupKind.FONT_SELECTION)
        search_entry.grab_focus()

def get_languages() -> List[str]:
    '''
    Return the list of languages.

    Get it from the command line option if that is used.
    If not, get it from the environment variables.
    '''
    if _ARGS.languages:
        return list(_ARGS.languages.split(':'))
    environment_variable = os.getenv('LANGUAGE')
    if not environment_variable:
        environment_variable = os.getenv('LC_ALL')
    if not environment_variable:
        environment_variable = os.getenv('LC_MESSAGES')
    if not environment_variable:
        environment_variable = os.getenv('LANG')
    if not environment_variable:
        return ['en_US']
    languages = []
    for language in environment_variable.split(':'):
        languages.append(re.sub(r'[.@].*', '', language))
    return languages

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
        '''Init the signal handler class.

        The threading.Lock() is unused at the moment as I don’t use
        threads now. But I might use threads in future.
        '''
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
        raise RuntimeError("GLIB_MAIN_LOOP not initialized!")

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
        LOGGER.info('********** STARTING **********')
        import cProfile
        import pstats
        import io
        PROFILE = cProfile.Profile()
        PROFILE.enable()

    itb_util.set_program_name('emoji-picker')

    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        LOGGER.error("IBUS-WARNING **: Using the fallback 'C' locale")
        locale.setlocale(locale.LC_ALL, 'C')

    LOCALEDIR = os.getenv("IBUS_LOCALEDIR")
    gettext.bindtextdomain(DOMAINNAME, LOCALEDIR)

    if _ARGS.version:
        print(itb_version.get_version())
        sys.exit(0)

    EMOJI_PICKER_UI = EmojiPickerUI(
        languages=get_languages(),
        font=_ARGS.font,
        fontsize=_ARGS.fontsize,
        fallback=_ARGS.fallback,
        modal=_ARGS.modal,
        unicode_data_all=_ARGS.all,
        unikemet=_ARGS.unikemet,
        emoji_unicode_min=_ARGS.emoji_unicode_min,
        emoji_unicode_max=_ARGS.emoji_unicode_max,
        match_limit=_ARGS.match_limit,
        spellcheck=_ARGS.spellcheck)
    GLIB_MAIN_LOOP = GLib.MainLoop()
    signal.signal(signal.SIGTERM, quit_glib_main_loop) # kill <pid>
    # Ctrl+C (optional, can also use try/except KeyboardInterrupt)
    signal.signal(signal.SIGINT, quit_glib_main_loop)
    # GLib.unix_signal_add(
    #     GLib.PRIORITY_DEFAULT,
    #     signal.SIGINT,
    #     SIGNAL_HANDLER.handle_sigint,
    #     None)
    try:
        GLIB_MAIN_LOOP.run()
    except KeyboardInterrupt:
        # SIGNINT (Control+C) received
        LOGGER.info('Control+C pressed, exiting ...')
        GLIB_MAIN_LOOP.quit()
