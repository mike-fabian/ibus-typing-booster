# -*- coding: utf-8 -*-
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

import sys
import os
import re
import signal
import argparse
import locale
import time
import gettext
import unicodedata
import html
import xdg.BaseDirectory

from gi import require_version
require_version('Gdk', '3.0')
from gi.repository import Gdk
require_version('Gtk', '3.0')
from gi.repository import Gtk
require_version('IBus', '1.0')
from gi.repository import IBus
from gi.repository import GLib
import itb_emoji
import version

GTK_VERSION = (Gtk.get_major_version(),
               Gtk.get_minor_version(),
               Gtk.get_micro_version())

DOMAINNAME = 'ibus-typing-booster'
_ = lambda a: gettext.dgettext(DOMAINNAME, a)
N_ = lambda a: a

def parse_args():
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
              + 'or searching for emoji. For example: '
              + '"emoji-picker -l de:fr:ja" '
              + 'would use German, French, and Japanese. '
              + 'If empty, the locale settings are used to '
              + 'determine the languages.'))
    parser.add_argument(
        '-f', '--font',
        nargs='?',
        type=str,
        action='store',
        default=None,
        help=('Set a font to display emoji. '
              + 'If not specified, the font is read from the config file. '
              + 'To use the system default font specify "". '
              + 'default: "%(default)s"'))
    parser.add_argument(
        '-s', '--fontsize',
        nargs='?',
        type=float,
        action='store',
        default=None,
        help=('Set a fontsize to display emoji. '
              + 'If not specified, the fontsize is read from the config file. '
              + 'If that fails 24 is used as a fall back fontsize. '
              + 'default: "%(default)s"'))
    parser.add_argument(
        '-m', '--modal',
        action='store_true',
        default=False,
        help=('Make the window of emoji-picker modal. '
              + 'default: %(default)s'))
    parser.add_argument(
        '-a', '--all',
        action='store_true',
        default=False,
        help=('Load all Unicode characters. '
              + 'Makes all Unicode characters accessible, '
              + 'even normal letters. '
              + 'Slows the search down and is usually not needed. '
              + 'default: %(default)s'))
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        default=False,
        help=('Print some debug output to stdout. '
              + 'default: %(default)s'))
    return parser.parse_args()

_ARGS = parse_args()

class EmojiPickerUI(Gtk.Window):
    '''
    User interface of the emoji picker
    '''
    def __init__(self,
                 languages=('en_US',),
                 modal=False,
                 unicode_data_all=False,
                 font=None,
                 fontsize=None):
        Gtk.Window.__init__(self, title='🚀 ' + _('Emoji Picker'))

        self.set_name('EmojiPicker')
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(
            b'#EmojiPicker { background-color: #FFFFFF; }')
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # https://tronche.com/gui/x/icccm/sec-4.html#WM_CLASS
        # gnome-shell seems to use the first argument of set_wmclass()
        # to find the .desktop file.  If the .desktop file can be
        # found, the name shown by gnome-shell in the top bar comes
        # from that .desktop file and the icon to show is also read
        # from that .desktop file. If the .desktop file cannot be
        # found, the second argument of set_wmclass() is shown by
        # gnome-shell in the top bar.
        self.set_wmclass('emoji-picker', 'Emoji Picker')
        self.set_default_size(700, 400)
        self._modal = modal
        self.set_modal(self._modal)
        self._font = 'Symbola'
        self._fontsize = 24
        self._options_file = os.path.join(
            xdg.BaseDirectory.save_data_path('emoji-picker'),
            'options')
        self._read_options()
        if not font is None:
            self._font = font
        if not fontsize is None:
            self._fontsize = fontsize
        self._save_options()
        self.connect('destroy-event', self.on_destroy_event)
        self.connect('delete-event', self.on_delete_event)
        self.connect('key-press-event', self.on_main_window_key_press_event)
        self._languages = languages
        self._emoji_matcher = itb_emoji.EmojiMatcher(
            languages=self._languages,
            unicode_data_all=unicode_data_all)
        self._gettext_translations = {}
        for language in itb_emoji._expand_languages(self._languages):
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

        self._currently_selected_label = None
        self._candidates_invalid = False
        self._query_string = ''
        self._emoji_selected_popover = None

        self._main_container = Gtk.VBox()
        self.add(self._main_container)
        self._header_bar = Gtk.HeaderBar()
        self._header_bar.set_hexpand(True)
        self._header_bar.set_vexpand(False)
        self._header_bar.set_show_close_button(True)
        self._header_bar.set_decoration_layout("menu:minimize,maximize,close")
        self._main_menu_button = Gtk.Button.new_from_icon_name(
            'open-menu-symbolic', Gtk.IconSize.BUTTON)
        self._header_bar.pack_start(self._main_menu_button)
        self._main_menu_popover = Gtk.Popover()
        self._main_menu_popover.set_relative_to(self._main_menu_button)
        self._main_menu_popover.set_position(Gtk.PositionType.BOTTOM)
        self._main_menu_popover_vbox = Gtk.VBox()
        self._main_menu_clear_recently_used_button = Gtk.Button(
            _('Clear recently used'))
        self._main_menu_clear_recently_used_button.connect(
            'clicked', self.on_clear_recently_used_button_clicked)
        self._main_menu_popover_vbox.pack_start(
            self._main_menu_clear_recently_used_button, False, False, 0)
        if not self._modal:
            self._main_menu_about_button = Gtk.Button(_('About'))
            self._main_menu_about_button.connect(
                'clicked', self.on_about_button_clicked)
            self._main_menu_popover_vbox.pack_start(
                self._main_menu_about_button, False, False, 0)
        self._main_menu_quit_button = Gtk.Button(_('Quit'))
        self._main_menu_quit_button.connect('clicked', self.on_delete_event)
        self._main_menu_popover_vbox.pack_start(
            self._main_menu_quit_button, False, False, 0)
        self._main_menu_popover.add(self._main_menu_popover_vbox)
        self._main_menu_button.connect(
            'clicked', self.on_main_menu_button_clicked)
        self._toggle_search_button = Gtk.Button.new_from_icon_name(
            'edit-find-symbolic', Gtk.IconSize.BUTTON)
        self._toggle_search_button.connect(
            'clicked', self.on_toggle_search_button_clicked)
        self._header_bar.pack_start(self._toggle_search_button)
        self._fontsize_spin_button = Gtk.SpinButton()
        self._fontsize_spin_button.set_numeric(True)
        self._fontsize_spin_button.set_can_focus(True)
        self._fontsize_adjustment = Gtk.Adjustment()
        self._fontsize_adjustment.set_lower(1)
        self._fontsize_adjustment.set_upper(10000)
        self._fontsize_adjustment.set_value(self._fontsize)
        self._fontsize_adjustment.set_step_increment(1)
        self._fontsize_spin_button.set_adjustment(self._fontsize_adjustment)
        self._fontsize_adjustment.connect(
            'value-changed', self.on_fontsize_adjustment_value_changed)
        self._header_bar.pack_start(self._fontsize_spin_button)
        self._spinner = Gtk.Spinner()
        self._header_bar.pack_end(self._spinner)
        self._main_container.pack_start(self._header_bar, False, False, 0)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_hexpand(False)
        self._search_entry.set_vexpand(False)
        self._search_entry.set_can_focus(True)
        self._search_bar = Gtk.SearchBar()
        self._search_bar.set_hexpand(False)
        self._search_bar.set_vexpand(False)
        self._search_bar.set_show_close_button(False)
        self._search_bar.set_search_mode(False) # invisible by default
        self._search_bar.add(self._search_entry)
        self._search_bar.connect_entry(self._search_entry)
        self._search_entry.connect(
            'search-changed', self.on_search_entry_search_changed)

        self._browse_paned = Gtk.HPaned()
        self._main_container.pack_start(self._browse_paned, True, True, 0)
        self._browse_paned.set_wide_handle(True)
        self._browse_paned.set_hexpand(True)
        self._browse_paned.set_vexpand(True)

        self._browse_treeview_scroll = Gtk.ScrolledWindow()
        self._browse_treeview = Gtk.TreeView()
        self._browse_treeview.set_activate_on_single_click(True)
        self._browse_treeview.set_vexpand(True)
        self._browse_treeview.get_selection().connect(
            'changed', self.on_label_selected)
        self._browse_treeview.connect(
            'row-activated', self.on_row_activated)
        self._browse_treeview_scroll.add(self._browse_treeview)

        self._flowbox_scroll = Gtk.ScrolledWindow()
        self._flowbox_scroll.set_hexpand(True)
        self._flowbox_scroll.set_vexpand(True)
        self._flowbox = Gtk.FlowBox()
        self._flowbox_scroll.add(self._flowbox)

        self._left_pane = Gtk.VBox()
        self._left_pane.set_homogeneous(False)
        self._left_pane.pack_start(self._search_bar, False, False, 0)
        self._left_pane.pack_start(self._browse_treeview_scroll, True, True, 0)

        self._right_pane = Gtk.VBox()
        self._right_pane.pack_start(self._flowbox_scroll, True, True, 0)

        self._browse_paned.pack1(
            self._left_pane, resize=True, shrink=True)
        self._browse_paned.pack2(
            self._right_pane, resize=True, shrink=True)

        self._browse_treeview_model = Gtk.TreeStore(str, str, str, str)
        self._browse_treeview.set_model(self._browse_treeview_model)

        self._recently_used_label = '🕒 ' + _('Recently used')
        dummy_recent_iter = self._browse_treeview_model.append(
            None,
            [self._recently_used_label, '', '', self._recently_used_label])

        self._recently_used_emoji = {}
        self._recently_used_emoji_file = os.path.join(
            xdg.BaseDirectory.save_data_path('emoji-picker'),
            'recently-used')
        self._recently_used_emoji_maximum = 100
        self._read_recently_used()

        self._emoji_by_label = self._emoji_matcher.emoji_by_label()
        expanded_languages = itb_emoji._expand_languages(self._languages)
        first_language_with_categories = -1
        number_of_empty_languages = 0
        for language_index, language in enumerate(expanded_languages):
            language_empty = True
            if language in self._emoji_by_label:
                language_iter = self._browse_treeview_model.append(
                    None, [language, '', '', ''])
                translated_label_keys = {
                    'Categories': _('Categories'),
                    'Unicode categories': _('Unicode categories'),
                    'Keywords': _('Keywords'),
                    }
                if self._gettext_translations[language]:
                    for label_key in translated_label_keys:
                        translated_label_keys[label_key] = (
                            self._gettext_translations[
                                language].gettext(label_key))
                if self._add_label_key_to_model(
                        'categories',
                        translated_label_keys['Categories'],
                        language, language_iter):
                    language_empty = False
                    if first_language_with_categories < 0:
                        first_language_with_categories = (
                            language_index - number_of_empty_languages)
                if self._add_label_key_to_model(
                        'ucategories',
                        translated_label_keys['Unicode categories'],
                        language, language_iter):
                    language_empty = False
                if self._add_label_key_to_model(
                        'keywords',
                        translated_label_keys['Keywords'],
                        language, language_iter):
                    language_empty = False
                if language_empty:
                    self._browse_treeview_model.remove(language_iter)
            if language_empty:
                number_of_empty_languages += 1

        if _ARGS.debug:
            sys.stdout.write(
                'expanded_languages  = %s\n'
                %itb_emoji._expand_languages(self._languages)
                + 'first_language_with_categories = %s\n'
                %first_language_with_categories
                + 'number_of_empty_languages = %s\n'
                %number_of_empty_languages)

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

        self.show_all()

        (dummy_minimum_width_search_entry,
         natural_width_search_entry) = self._search_entry.get_preferred_width()
        (dummy_minimum_width_search_bar,
         natural_width_search_bar) = self._search_bar.get_preferred_width()
        if _ARGS.debug:
            sys.stdout.write(
                'natural_width_search_entry = %s '
                %natural_width_search_entry
                + 'natural_width_search_bar = %s\n'
                %natural_width_search_bar)
        self._browse_paned.set_position(natural_width_search_bar)

        self._selection_clipboard = Gtk.Clipboard.get(
            Gdk.SELECTION_CLIPBOARD)
        self._selection_primary = Gtk.Clipboard.get(
            Gdk.SELECTION_PRIMARY)

    def _busy_start(self):
        '''
        Show that this program is busy
        '''
        self._spinner.start()
        # self.get_root_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
        # Gdk.flush()

    def _busy_stop(self):
        '''
        Stop showing that this program is busy
        '''
        self._spinner.stop()
        # self.get_root_window().set_cursor(Gdk.Cursor(Gdk.CursorType.ARROW))

    def _browse_treeview_unselect_all(self):
        '''
        Unselect everything in the treeview for browsing the categories
        '''
        self._browse_treeview.get_selection().unselect_all()
        self._currently_selected_label = None

    def _add_label_key_to_model(
            self, label_key, label_key_display, language, language_iter):
        if not label_key in self._emoji_by_label[language]:
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

    def _sort_labels(self, labels, language): # pylint: disable=no-self-use
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

    def _emoji_description(self, emoji):
        '''
        Return a description of the emoji

        The description shows the Unicode codpoint(s) of the emoji
        and the names of the emoji in all languages used.

        :param emoji: The emoji
        :type emoji: String
        :rtype: String
        '''
        description = ' '.join(['U+%X' %ord(character) for character in emoji])
        description += '\n'
        for language in itb_emoji._expand_languages(self._languages):
            name = self._emoji_matcher.name(emoji, language=language)
            if name:
                description += '%s   (%s)\n' %(name, language)
        if _ARGS.debug:
            description += (
                'emoji_order = %s' %self._emoji_matcher.emoji_order(emoji))
        return description

    def _emoji_label_set_tooltip(self, emoji, label):
        '''
        Set the tooltip for a label in the flowbox which shows an emoji

        :param emoji: The emoji
        :type emoji: String
        :param label: The label used to show the emoji
        :type label: Gtk.Label object
        '''
        description = self._emoji_description(emoji)
        if itb_emoji._is_invisible(emoji):
            label.set_tooltip_text(
                description + '\n\n' + _('Click to copy'))
        else:
            label.set_tooltip_markup(
                '<span font_desc="%s %s">'
                %(self._font, self._fontsize * 4)
                + html.escape(emoji)
                + '</span>\n\n'
                + html.escape(description + '\n\n' + _('Click to copy')))

    def _clear_flowbox(self):
        '''
        Clear the contents of the flowbox
        '''
        for child in self._flowbox_scroll.get_children():
            self._flowbox_scroll.remove(child)
        self._flowbox = Gtk.FlowBox()
        self._flowbox_scroll.add(self._flowbox)
        self._flowbox.set_valign(Gtk.Align.START)
        self._flowbox.set_min_children_per_line(1)
        self._flowbox.set_max_children_per_line(100)
        self._flowbox.set_row_spacing(0)
        self._flowbox.set_column_spacing(0)
        self._flowbox.set_activate_on_single_click(True)
        self._flowbox.set_can_focus(True)
        self._flowbox.set_homogeneous(False)
        self._flowbox.set_hexpand(False)
        self._flowbox.set_vexpand(False)
        self._flowbox.connect('child-activated', self.on_emoji_selected)

    def _fill_flowbox_browse(self):
        '''
        Fill the flowbox with content according to the currently
        selected label in the browsing treeview.
        '''
        (language, label_key, label) = self._currently_selected_label
        if _ARGS.debug:
            sys.stdout.write(
                '_fill_flowbox_browse() '
                + 'language = %s label_key = %s label = %s\n'
                %(language, label_key, label))
        emoji_list = []
        if label == self._recently_used_label:
            emoji_list = sorted(
                self._recently_used_emoji,
                key=lambda x: (
                    - self._recently_used_emoji[x]['time'],
                    - self._recently_used_emoji[x]['count'],
                ))
        if (language in self._emoji_by_label
                and label_key in self._emoji_by_label[language]
                and label in  self._emoji_by_label[language][label_key]):
            emoji_list = self._emoji_by_label[language][label_key][label]

        self._header_bar.set_title(label)
        if label:
            self._header_bar.set_subtitle(str(len(emoji_list)))
        else:
            self._header_bar.set_subtitle('')

        if not emoji_list:
            self._busy_stop()
            return

        for emoji in emoji_list:
            while Gtk.events_pending():
                Gtk.main_iteration()
            label = Gtk.Label()
            if itb_emoji._is_invisible(emoji):
                description = self._emoji_description(emoji)
                label.set_text('<span>%s</span>' %emoji + description)
            else:
                # Make font for emoji large using pango markup
                label.set_text(
                    '<span font="%s %s">'
                    %(self._font, self._fontsize)
                    + html.escape(emoji)
                    + '</span>')
            label.set_use_markup(True)
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
            self._emoji_label_set_tooltip(emoji, label)
            self._flowbox.insert(label, -1)

        self.show_all()
        self._busy_stop()

    def _read_options(self):
        '''
        Read the options for 'font' and 'fontsize' from  a file
        '''
        options_dict = {}
        if os.path.isfile(self._options_file):
            try:
                options_dict = eval(open(
                    self._options_file,
                    mode='r',
                    encoding='UTF-8').read())
            except (PermissionError, SyntaxError, IndentationError):
                import traceback
                traceback.print_exc()
            except Exception as exception:
                import traceback
                traceback.print_exc()
            else: # no exception occured
                if _ARGS.debug:
                    sys.stdout.write(
                        'File %s has been read and evaluated.\n'
                        %self._options_file)
            finally: # executes always
                if not isinstance(options_dict, dict):
                    if _ARGS.debug:
                        sys.stdout.write(
                            'Not a dict: repr(options_dict) = %s\n'
                            %options_dict)
                    options_dict = {}
        if ('font' in options_dict
                and isinstance(options_dict['font'], str)):
            self._font = options_dict['font']
        if ('fontsize' in options_dict
                and (isinstance(options_dict['fontsize'], int)
                     or isinstance(options_dict['fontsize'], float))):
            self._fontsize = options_dict['fontsize']

    def _save_options(self):
        '''
        Save the options for 'font' and 'fontsize' to a file
        '''
        options_dict = {
            'font': self._font,
            'fontsize': self._fontsize,
            }
        with open(self._options_file,
                  mode='w',
                  encoding='UTF-8') as options_file:
            options_file.write(repr(options_dict))
            options_file.write('\n')

    def _read_recently_used(self):
        '''
        Read the recently use emoji from a file
        '''
        if os.path.isfile(self._recently_used_emoji_file):
            try:
                self._recently_used_emoji = eval(open(
                    self._recently_used_emoji_file,
                    mode='r',
                    encoding='UTF-8').read())
            except (PermissionError, SyntaxError, IndentationError):
                import traceback
                traceback.print_exc()
            except Exception as exception:
                import traceback
                traceback.print_exc()
            else: # no exception occured
                if _ARGS.debug:
                    sys.stdout.write(
                        'File %s has been read and evaluated.\n'
                        %self._recently_used_emoji_file)
            finally: # executes always
                if not isinstance(self._recently_used_emoji, dict):
                    if _ARGS.debug:
                        sys.stdout.write(
                            'Not a dict: '
                            + 'repr(self._recently_used_emoji) = %s\n'
                            %self._recently_used_emoji)
                    self._recently_used_emoji = {}
        if not self._recently_used_emoji:
            self._init_recently_used()
        self._cleanup_recently_used()

    def _cleanup_recently_used(self):
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

    def _init_recently_used(self):
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

    def on_clear_recently_used_button_clicked(self, dummy_button):
        '''
        :param dummy_button: The “Clear recently used” button
        :type dummy_button: Gtk.Button object
        '''
        if _ARGS.debug:
            sys.stdout.write('on_clear_recently_used_button_clicked()\n')
        if GTK_VERSION >= (3, 22, 0):
            self._main_menu_popover.popdown()
        self._main_menu_popover.hide()
        self._init_recently_used()

    def _add_to_recently_used(self, emoji):
        '''
        Adds an emoji to the resently used dictionary.

        :param emoji: The emoji string
        :type emoji: String
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

    def _save_recently_used_emoji(self):
        '''
        Save the list of recently used emoji
        '''
        with open(self._recently_used_emoji_file,
                  mode='w',
                  encoding='UTF-8') as recents_file:
            recents_file.write(repr(self._recently_used_emoji))
            recents_file.write('\n')

    def on_delete_event(self, *dummy_args):
        '''
        The window has been deleted, probably by the window manager.
        '''
        self._save_recently_used_emoji()
        Gtk.main_quit()

    def on_destroy_event(self, *dummy_args):
        '''
        The window has been destroyed.
        '''
        self._save_recently_used_emoji()
        Gtk.main_quit()

    def on_main_window_key_press_event(self, dummy_window, event_key):
        '''
        Some key has been typed into the main window

        :param dummy_window: The main window
        :type dummy_window: Gtk.Window object
        :param event_key:
        :type event_key: Gdk.EventKey object
        '''
        if _ARGS.debug:
            sys.stdout.write(
                'on_main_window_key_press_event() '
                + 'keyval = %s\n'
                %event_key.keyval)
        if self._fontsize_spin_button.has_focus():
            if _ARGS.debug:
                sys.stdout.write(
                    'on_main_window_key_press_event(): '
                    + 'self._fontsize_spin_button has focus\n')
            # if the fontsize spin button has focus, we do not want
            # to take it away from there by popping up the search bar.
            return
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
            return
        if not event_key.string:
            return
        self._search_bar.set_search_mode(True)
        self._search_bar.show_all()
        # The search entry needs to be realized to be able to
        # handle a key event. If it is not realized yet when
        # the key event arrives, one will get the message:
        #
        # Gtk-CRITICAL **: gtk_widget_event:
        # assertion 'WIDGET_REALIZED_FOR_EVENT (widget, event)' failed
        #
        # and the typed key will not appear in the search entry.
        #
        # The self._search_bar.show_all() realizes the search
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
        if not self._search_entry.get_window():
            while Gtk.events_pending():
                Gtk.main_iteration()
        self._search_bar.handle_event(event_key)

    def on_close_aboutdialog( # pylint: disable=no-self-use
            self, about_dialog, dummy_response):
        '''
        The “About” dialog has been closed by the user

        :param about_dialog: The “About” dialog
        :type about_dialog: GtkDialog object
        :param dummy_response: The response when the “About” dialog was closed
        :type dummy_response: Gtk.ResponseType enum
        '''
        about_dialog.destroy()

    def on_about_button_clicked(self, dummy_button):
        '''
        The “About” button has been clicked

        :param dummy_button: The “About” button
        :type dummy_button: Gtk.Button object
        '''
        if _ARGS.debug:
            sys.stdout.write('on_about_button_clicked()\n')
        if GTK_VERSION >= (3, 22, 0):
            self._main_menu_popover.popdown()
        self._main_menu_popover.hide()
        aboutdialog = Gtk.AboutDialog()
        # An empty string in aboutdialog.set_logo_icon_name('')
        # prevents an ugly default icon to be shown. We don’t yet
        # have nice icons for ibus-typing-booster.
        aboutdialog.set_logo_icon_name('')
        aboutdialog.set_title(
            '🚀 ibus-typing-booster %s' %version.get_version())
        aboutdialog.set_program_name(
            '🚀 ibus-typing-booster')
        aboutdialog.set_version(version.get_version())
        aboutdialog.set_comments(
            'A completion input method to speedup typing')
        aboutdialog.set_copyright(
            'Copyright © 2017 Mike FABIAN')
        aboutdialog.set_authors([
            'Mike FABIAN <maiku.fabian@gmail.com>',
            'Anish Patil <anish.developer@gmail.com>',
            ])
        aboutdialog.set_translator_credits(
            # Translators: put your names here, one name per line.
            _('translator-credits'))
        # aboutdialog.set_artists('')
        aboutdialog.set_documenters([
            'Mike FABIAN <maiku.fabian@gmail.com>',
            ])
        aboutdialog.set_website(
            'http://mike-fabian.github.io/ibus-typing-booster')
        aboutdialog.set_website_label(
            'http://mike-fabian.github.io/ibus-typing-booster')
        aboutdialog.set_license('''
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
        aboutdialog.set_wrap_license(True)
        # overrides the above .set_license()
        aboutdialog.set_license_type(Gtk.License.GPL_3_0)
        aboutdialog.connect('response', self.on_close_aboutdialog)
        aboutdialog.set_transient_for(self)
        aboutdialog.show()

    def _fill_flowbox_with_search_results(self):
        '''
        Get the emoji candidates for the current query string
        and fill the flowbox with the results of the query.
        '''
        if _ARGS.debug:
            sys.stdout.write(
                '_fill_flowbox_with_search_results() query_string = %s\n'
                %self._query_string)
        candidates = self._emoji_matcher.candidates(
            self._query_string,
            match_limit=1000)

        self._browse_treeview_unselect_all()
        self._header_bar.set_title(_('Search Results'))
        self._header_bar.set_subtitle(str(len(candidates)))

        if not candidates:
            self._candidates_invalid = False
            self._busy_stop()
            return

        for candidate in candidates:
            # Do *not* do
            #
            # while Gtk.events_pending():
            #     Gtk.main_iteration()
            #
            # here. Although this will keep the spinner turning, it
            # will have the side effect that further key events maybe
            # added to the query string while the flowbox is being
            # filled. But then the on_search_entry_search_changed()
            # callback will think that nothing needs to be done
            # because self._candidates_invalid is True already.
            emoji = candidate[0]
            name = candidate[1]
            dummy_score = candidate[2]
            label = Gtk.Label()
            # Make font for emoji large using pango markup
            label.set_text(
                '<span font="%s %s">'
                %(self._font, self._fontsize)
                + html.escape(emoji)
                + '</span>'
                + '<span font="%s">'
                %(self._fontsize / 2)
                + ' ' + html.escape(name)
                + '</span>')
            label.set_use_markup(True)
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
            self._flowbox.insert(label, -1)

        self.show_all()
        self._candidates_invalid = False
        self._busy_stop()

    def on_search_entry_search_changed(self, search_entry):
        '''
        Signal handler for changed text in the search entry

        :param widget: The search entry
        :type widget: Gtk.SearchEntry object
        '''
        query_string = search_entry.get_text()
        if _ARGS.debug:
            sys.stdout.write(
                'on_search_entry_search_changed() query_string = %s\n'
                %query_string)
        if not self._search_bar.get_search_mode():
            # If the text in the search entry changes while
            # the search bar is invisible, ignore it.
            return
        self._query_string = query_string
        if self._candidates_invalid:
            if _ARGS.debug:
                sys.stdout.write(
                    'on_search_entry_search_changed() '
                    + 'self._candidates_invalid = %s\n'
                    %self._candidates_invalid)
            return
        self._candidates_invalid = True
        self._clear_flowbox()
        self._busy_start()
        GLib.idle_add(self._fill_flowbox_with_search_results)

    def on_label_selected(self, selection):
        '''
        Signal handler for selecting a category in the list of categories

        :param selection: The selected row in the browsing treeview
        :type selection: Gtk.TreeSelection object
        '''
        (model, iterator) = selection.get_selected()
        if not iterator:
            return
        if _ARGS.debug:
            sys.stdout.write(
                'on_label_selected(): model[iterator] = %s\n'
                %model[iterator][:]
                + 'self._currently_selected_label = %s\n'
                %repr(self._currently_selected_label))
        self._search_bar.set_search_mode(False)
        self._browse_treeview.grab_focus()
        language = model[iterator][1]
        label_key = model[iterator][2]
        label = model[iterator][3]
        if self._currently_selected_label != (language, label_key, label):
            self._currently_selected_label = (language, label_key, label)
            self._clear_flowbox()
            self._busy_start()
            GLib.idle_add(self._fill_flowbox_browse)

    def on_row_activated( # pylint: disable=no-self-use
            self, treeview, treepath, column):
        '''Signal handler for activating a row in the browsing treeview

        :param treeview: The browsing treeview
        :type treeview: Gtk.TreeView object
        :param treepath: The path of the activated row in the browsing treeview
        :type treepath: Gtk.TreePath object
        :param column: The column of the activated row in the browsing treeview
        :type column: Gtk.TreeViewColumn object
        '''
        if _ARGS.debug:
            sys.stdout.write(
                'on_row_activated() %s %s %s\n'
                %(repr(treeview), repr(treepath), repr(column)))

    def _emoji_selected_popover_popdown(self):
        '''
        Hide the popover again which was shown when an emoji was selected
        '''
        if self._emoji_selected_popover:
            if GTK_VERSION >= (3, 22, 0):
                self._emoji_selected_popover.popdown()
            self._emoji_selected_popover.hide()
            self._emoji_selected_popover = None
        return False

    def on_emoji_selected(self, dummy_flowbox, flowbox_child):
        '''
        Signal handler for selecting an emoji in the browser

        :param dummy_flowbox: The flowbox displaying the Emoji
        :type dummy_flowbox: Gtk.FlowBox object
        :param flowbox_child: The child object containing the selected emoji
        :type flowbox_child: Gtk.FlowBoxChild object
        '''
        # Use .get_label() instead of .get_text() to fetch the text
        # from the label widget including any embedded underlines
        # indicating mnemonics and Pango markup. The emoji is in
        # first <span>...</span>, and we want fetch only the emoji
        # here:
        text = flowbox_child.get_child().get_label()
        if _ARGS.debug:
            sys.stdout.write("on_emoji_selected() text = %s\n" %text)
        pattern = re.compile(r'<span[^<]*?>(?P<emoji>[^<]+?)</span>')
        match = pattern.match(text)
        if match:
            emoji = html.unescape(match.group('emoji'))
            if _ARGS.debug:
                sys.stdout.write(
                    'on_emoji_selected() repr(emoji) = %s\n' %repr(emoji))
        else:
            return
        self._selection_clipboard.set_text(emoji, -1)
        self._selection_primary.set_text(emoji, -1)
        self._add_to_recently_used(emoji)
        self._emoji_selected_popover = Gtk.Popover()
        self._emoji_selected_popover.set_relative_to(flowbox_child.get_child())
        self._emoji_selected_popover.set_position(Gtk.PositionType.TOP)
        rectangle = Gdk.Rectangle()
        rectangle.x = 0
        rectangle.y = 0
        rectangle.width = self._fontsize * 1.5
        rectangle.height = self._fontsize * 1.5
        self._emoji_selected_popover.set_pointing_to(rectangle)
        label = Gtk.Label(_('Copied to clipboard!'))
        self._emoji_selected_popover.add(label)
        if GTK_VERSION >= (3, 22, 0):
            self._emoji_selected_popover.popup()
        self._emoji_selected_popover.show_all()
        GLib.timeout_add(500, self._emoji_selected_popover_popdown)

    def on_main_menu_button_clicked(self, dummy_button):
        '''
        The main menu button has been clicked

        :param button: The main menu button
        :type button: Gtk.Button object
        '''
        if _ARGS.debug:
            sys.stdout.write('on_main_menu_button_clicked()\n')
        if GTK_VERSION >= (3, 22, 0):
            self._main_menu_popover.popup()
        self._main_menu_popover.show_all()

    def on_toggle_search_button_clicked(self, dummy_button):
        '''
        The search button in the header bar has been clicked

        :param dummy_button: The search button
        :type  dummy_button: Gtk.Button object
        '''
        if _ARGS.debug:
            sys.stdout.write('on_toggle_search_button_clicked()\n')
        self._search_bar.set_search_mode(
            not self._search_bar.get_search_mode())

    def _change_flowbox_font(self):
        '''
        Update the font and fontsize used in the current content
        of the flowbox.
        '''
        for flowbox_child in self._flowbox.get_children():
            label = flowbox_child.get_child()
            text = label.get_label()
            pattern = re.compile(
                r'<span[^<]*?>(?P<emoji>[^<]+?)</span>'
                + r'(<span[^<]*?>(?P<name>[^<]+?)</span>)?')
            match = pattern.match(text)
            if match:
                emoji = html.unescape(match.group('emoji'))
                new_text = (
                    '<span font="%s %s">'
                    %(self._font, self._fontsize)
                    + html.escape(emoji)
                    + '</span>')
                if match.group('name'):
                    name = html.unescape(match.group('name'))
                    new_text += (
                        '<span font="%s">'
                        %(self._fontsize / 2)
                        + html.escape(name)
                        + '</span>')
                label.set_text(new_text)
                label.set_use_markup(True)
                self._emoji_label_set_tooltip(emoji, label)
        self.show_all()
        self._busy_stop()

    def on_fontsize_adjustment_value_changed(self, adjustment):
        '''
        :param adjustment: The adjustment used to change the fontsize
        :type adjustment: Gtk.Adjustment object
        '''
        value = adjustment.get_value()
        if _ARGS.debug:
            sys.stdout.write(
                'on_fontsize_adjustment_value_changed() value = %s\n'
                %value)
        self._fontsize = value
        self._save_options()
        self._busy_start()
        GLib.idle_add(self._change_flowbox_font)

def get_languages():
    '''
    Return the list of languages.

    Get it from the command line option if that is used.
    If not, get it from the environment variables.
    '''
    if _ARGS.languages:
        return _ARGS.languages.split(':')
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

if __name__ == '__main__':
    if _ARGS.debug:
        sys.stdout.write('--- %s ---\n' %time.strftime('%Y-%m-%d: %H:%M:%S'))

    # Workaround for
    # https://bugzilla.gnome.org/show_bug.cgi?id=622084
    # Bug 622084 - Ctrl+C does not exit gtk app
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        sys.stderr.write("IBUS-WARNING **: Using the fallback 'C' locale")
        locale.setlocale(locale.LC_ALL, 'C')

    LOCALEDIR = os.getenv("IBUS_LOCALEDIR")
    gettext.bindtextdomain(DOMAINNAME, LOCALEDIR)
    gettext.bind_textdomain_codeset(DOMAINNAME, "UTF-8")

    if IBus.get_address() is None:
        DIALOG = Gtk.MessageDialog(
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            message_format=_('ibus is not running.'))
        DIALOG.run()
        DIALOG.destroy()
        sys.exit(1)

    EMOJI_PICKER_UI = EmojiPickerUI(
        languages=get_languages(),
        font=_ARGS.font,
        fontsize=_ARGS.fontsize,
        modal=_ARGS.modal,
        unicode_data_all=_ARGS.all)
    Gtk.main()
