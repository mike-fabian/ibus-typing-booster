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
import itb_emoji
import version

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
        default='',
        help=('Set a font to display emoji. '
              + 'If empty, the system settings are  used. '
              + 'default: "%(default)s"'))
    parser.add_argument(
        '-s', '--fontsize',
        nargs='?',
        type=int,
        action='store',
        default=16,
        help=('Set a fontsize to display emoji. '
              + 'default: "%(default)s"'))
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
                 font='',
                 fontsize=16):
        Gtk.Window.__init__(self, title='🚀 ' + _('Emoji Picker'))
        self.set_name('Emoji Picker')
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
        self.set_modal(modal)
        self._font = font
        self._fontsize = fontsize
        self.connect('destroy-event', self.on_destroy_event)
        self.connect('delete-event', self.on_delete_event)
        self._languages = languages
        self._emoji_matcher = itb_emoji.EmojiMatcher(languages=self._languages)
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

        self._notebook = Gtk.Notebook()
        self.add(self._notebook)

        self._page_browse = Gtk.Grid()

        self._browse_paned = Gtk.HPaned()
        self._browse_paned.set_wide_handle(True)
        self._browse_paned.set_hexpand(True)
        self._browse_paned.set_vexpand(True)
        self._browse_paned.set_position(180)

        self._browse_treeview_scroll = Gtk.ScrolledWindow()
        self._browse_treeview = Gtk.TreeView()
        self._browse_treeview.get_selection().connect(
            'changed', self.on_label_selected)
        self._browse_treeview.connect(
            'row-activated', self.on_row_activated)
        self._browse_treeview_scroll.add(self._browse_treeview)
        self._browse_flowbox_scroll = Gtk.ScrolledWindow()
        self._browse_flowbox_scroll.set_hexpand(True)
        self._browse_flowbox_scroll.set_vexpand(True)
        self._browse_flowbox_viewport = Gtk.Viewport()
        self._browse_flowbox_viewport.set_valign(Gtk.Align.START)
        self._browse_flowbox = Gtk.FlowBox()
        self._browse_flowbox_viewport.add(self._browse_flowbox)
        self._browse_flowbox_scroll.add(self._browse_flowbox_viewport)

        self._browse_paned.pack1(
            self._browse_treeview_scroll, resize=True, shrink=True)
        self._browse_paned.pack2(
            self._browse_flowbox_scroll, resize=True, shrink=True)
        self._page_browse.add(self._browse_paned)

        self._notebook.append_page(self._page_browse, Gtk.Label(_('Browse')))

        self._page_search = Gtk.Grid()
        self._page_search.set_border_width(6)
        self._page_search.set_row_spacing(6)
        self._page_search.set_column_spacing(6)
        self._notebook.append_page(self._page_search, Gtk.Label(_('Search')))
        self._search_entry = Gtk.Entry()
        self._search_entry.set_hexpand(True)
        self._search_entry.set_vexpand(False)
        self._search_entry.set_can_focus(True)
        self._page_search.add(self._search_entry)
        self._search_treeview_scroll = Gtk.ScrolledWindow()
        self._search_treeview_scroll.set_visible(True)
        self._search_treeview_scroll.set_hexpand(True)
        self._search_treeview_scroll.set_vexpand(True)
        self._search_treeview = Gtk.TreeView()
        self._search_treeview.set_visible(True)
        self._search_treeview.set_hexpand(True)
        self._search_treeview.set_vexpand(True)
        self._search_treeview.get_selection().connect(
            'changed', self.on_candidate_selected)
        self._search_treeview_scroll.add(self._search_treeview)
        self._search_treeview_model = Gtk.ListStore(str, str)
        self._search_treeview.set_model(self._search_treeview_model)
        self._search_treeview.append_column(Gtk.TreeViewColumn(
            'Candidates', Gtk.CellRendererText(), markup=0))
        # If the headers in the search treeview are visible, they must
        # be taken into account when calculating the index fo the
        # tooltip in on_search_treeview_query_tooltip().  The header
        # is not really useful anyway, better just don’t show it.
        self._search_treeview.set_headers_visible(False)
        self._search_treeview.set_property('has-tooltip', True)
        self._page_search.attach(self._search_treeview_scroll, 0, 1, 1, 10)
        self._search_entry.connect(
            'notify::text', self.on_search_entry_text_changed)
        self._search_treeview.connect(
            'query-tooltip', self.on_search_treeview_query_tooltip)
        self._notebook.connect('switch-page', self.on_switch_page)

        self._page_about = Gtk.VBox()

        self.about_emoji_label = Gtk.Label('<span font="48">🚀</span>')
        self.about_emoji_label.set_hexpand(True)
        self.about_emoji_label.set_vexpand(True)
        self.about_emoji_label.set_use_markup(True)
        self._page_about.add(self.about_emoji_label)

        self.about_name_version_label = Gtk.Label()
        self.about_name_version_label.set_hexpand(True)
        self.about_name_version_label.set_vexpand(True)
        self.about_name_version_label.set_use_markup(True)
        self.about_name_version_label.set_markup(
            '<span font_size="large"><b>ibus-typing-booster %s</b></span>'
            %version.get_version())
        self._page_about.add(self.about_name_version_label)

        self.about_long_description_label = Gtk.Label(
            _('A completion input method to speedup typing.'))
        self.about_name_version_label.set_hexpand(True)
        self.about_name_version_label.set_vexpand(True)
        self._page_about.add(self.about_long_description_label)

        self.about_home_page_label = Gtk.Label(_('<b>Home page:</b>'))
        self.about_home_page_label.set_hexpand(True)
        self.about_home_page_label.set_vexpand(True)
        self.about_home_page_label.set_use_markup(True)
        self._page_about.add(self.about_home_page_label)

        home_page_uri = 'http://mike-fabian.github.io/ibus-typing-booster'
        self.about_home_page_link_button = Gtk.LinkButton(label=home_page_uri)
        self.about_home_page_link_button.set_uri(home_page_uri)
        self.about_home_page_link_button.set_hexpand(True)
        self.about_home_page_link_button.set_vexpand(True)
        self._page_about.add(self.about_home_page_link_button)

        self.about_documentation_link_label = Gtk.Label(
            _('<b>Online documentation:</b>'))
        self.about_documentation_link_label.set_hexpand(True)
        self.about_documentation_link_label.set_vexpand(True)
        self.about_documentation_link_label.set_use_markup(True)
        self._page_about.add(self.about_documentation_link_label)

        documentation_uri = (
            'http://mike-fabian.github.io/ibus-typing-booster/'
            + 'documentation.html')
        self.about_documentation_link_button = Gtk.LinkButton(
            label=documentation_uri)
        self.about_documentation_link_button.set_uri(home_page_uri)
        self.about_documentation_link_button.set_hexpand(True)
        self.about_documentation_link_button.set_vexpand(True)
        self._page_about.add(self.about_documentation_link_button)

        self._notebook.append_page(self._page_about, Gtk.Label(_('About')))

        self._browse_treeview_model = Gtk.TreeStore(str, str, str, str)
        self._browse_treeview.set_model(self._browse_treeview_model)

        self._recently_used_emoji_file = os.path.join(
            xdg.BaseDirectory.save_data_path('emoji-picker'),
            'recently-used')
        self._recently_used_emoji_maximum = 100
        self._recently_used_emoji = {}
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
                            'Not a dict: repr(self._recently_used_emoji) = %s\n'
                            %self._recently_used_emoji)
                    self._recently_used_emoji = {}
        if not self._recently_used_emoji:
            self._add_to_recently_used('☺')
        self._cleanup_recently_used()

        dummy_recent_iter = self._browse_treeview_model.append(
            None, ['🕒 ' + _('Recently used'), 'dummy_language', '', ''])

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

        # self._fill_flowbox('en', 'categories', 'people')

        self._selection_clipboard = Gtk.Clipboard.get(
            Gdk.SELECTION_CLIPBOARD)
        self._selection_primary = Gtk.Clipboard.get(
            Gdk.SELECTION_PRIMARY)

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

    def _sort_labels(self, labels, language):
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

    def _fill_flowbox(self, language, label_key, label):
        if _ARGS.debug:
            sys.stdout.write(
                '_fill_flowbox() language = %s label_key = %s label = %s\n'
                %(language, label_key, label))
        emoji_list = []
        if language == 'dummy_language':
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
        if not emoji_list:
            return
        for child in self._browse_flowbox_viewport.get_children():
            self._browse_flowbox_viewport.remove(child)
        self._browse_flowbox = Gtk.FlowBox()
        self._browse_flowbox_viewport.add(self._browse_flowbox)
        self._browse_flowbox.set_min_children_per_line(1)
        self._browse_flowbox.set_max_children_per_line(100)
        self._browse_flowbox.set_row_spacing(0)
        self._browse_flowbox.set_column_spacing(0)
        self._browse_flowbox.set_activate_on_single_click(True)
        self._browse_flowbox.set_can_focus(True)
        self._browse_flowbox.set_homogeneous(True)
        self._browse_flowbox.set_hexpand(False)
        self._browse_flowbox.set_vexpand(False)
        self._browse_flowbox.connect('child-activated', self.on_emoji_selected)

        for emoji in emoji_list:
            description = self._emoji_description(emoji)
            label = Gtk.Label()
            if itb_emoji._is_invisible(emoji):
                label.set_text(description)
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
            margin = 1
            label.set_margin_start(margin)
            label.set_margin_end(margin)
            label.set_margin_top(margin)
            label.set_margin_bottom(margin)
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
            self._browse_flowbox.insert(label, -1)

        self.show_all()
        self.get_root_window().set_cursor(Gdk.Cursor(Gdk.CursorType.ARROW))

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

    def on_search_treeview_query_tooltip(
            self,
            dummy_treeview, mouse_x, mouse_y, dummy_keyboard_mode, tooltip):
        '''
        “query-tooltip” signal handler

        Returns True if the tooltip is to be shown, False if not.

        :param treeview: The search treeview
        :type dummy_treeview: Gtk.TreeView object
        :param mouse_x: The x coordinate of the mouse in the treeview
        :type mouse_x: Integer
        :param mouse_y: The y coordinate of the mouse in the treeview
        :type mouse_y: Integer
        :param dummy_keyboard_mode: I am not sure what this parameter means
        :type dummy_keyboard_mode: Boolean
        :param tooltip: The tooltip to be filled with content
        :type tooltip: Gtk.Tooltip object
        '''
        if _ARGS.debug:
            sys.stdout.write('on_search_treeview_query_tooltip()\n')
        path_at_pos = self._search_treeview.get_path_at_pos(mouse_x, mouse_y)
        if not path_at_pos:
            return False
        path, dummy_column, dummy_cell_x, dummy_cell_y = path_at_pos
        index = path.get_indices()[0]
        emoji = self._search_treeview_model[index][1]
        if _ARGS.debug:
            sys.stdout.write('on_search_treeview_query_tooltip() index = %s\n'
                             %index)
        description = self._emoji_description(emoji)
        if itb_emoji._is_invisible(emoji):
            tooltip.set_text(
                description + '\n\n' + _('Click to copy'))
        else:
            tooltip.set_markup(
                '<span font="%s %s">'
                %(self._font, self._fontsize * 4)
                + html.escape(emoji)
                + '</span>\n\n'
                + html.escape(description + '\n\n' + _('Click to copy')))
        return True

    def on_switch_page(self, dummy_notebook, dummy_page, page_number):
        '''
        Signal handler for switching a page in the notebook

        :param dummy_notebook: The notebook
        :type dummy_notebook: Gtk.Notebook object
        :param dummy_page: The page switched to
        :type dummy_page: Gtk.Widget object
        :param page_number: The number of the page switched to
        :type page_number: Integer
        '''
        if _ARGS.debug:
            sys.stdout.write('on_switch_page() page_number = %s\n'
                             %page_number)
        if page_number == 1:
            # This is the “Search” page
            self._search_entry.connect('draw', self.on_search_entry_draw)

    def on_search_entry_show(self, entry): # pylint: disable=no-self-use
        '''
        Signal handler for showing the search entry

        :param entry: The search entry
        :type entry: Gtk.Entry object
        '''
        if _ARGS.debug:
            sys.stdout.write('on_search_entry_show()\n')
        entry.grab_focus_without_selecting()

    def on_search_entry_draw( # pylint: disable=no-self-use
            self, entry, dummy_cairo_context):
        '''
        Signal handler for drawing the search entry

        :param entry: The search entry
        :type entry: Gtk.Entry object
        :param dummy_cairo_context: not used
        :type dummy_cairo_context: cairo.Context object
        '''
        if _ARGS.debug:
            sys.stdout.write('on_search_entry_draw()\n')
        entry.grab_focus_without_selecting()

    def on_search_entry_text_changed(self, widget, dummy_property_spec):
        '''
        Signal handler for changed text in the search entry

        :param widget: The search entry
        :type widget: Gtk.Entry object
        :param dummy_property_spec: not used
        '''
        query_string = widget.get_text()
        self._search_treeview_model = Gtk.ListStore(str, str)
        self._search_treeview.set_model(self._search_treeview_model)
        if not query_string:
            return
        if _ARGS.debug:
            sys.stdout.write(
                'on_search_entry_text_changed() query_string = %s\n'
                %query_string)
        for candidate in self._emoji_matcher.candidates(query_string):
            self._search_treeview_model.append(
                ('<span font="%s %s">'
                 %(self._font, self._fontsize)
                 + html.escape(candidate[0])
                 + '</span>'
                 + '<span font="%s">'
                 %self._fontsize
                 + ' ' + html.escape(candidate[1])
                 + '</span>',
                 candidate[0]))

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
                "on_label_selected(): model[iterator] = %s\n"
                %model[iterator][:])
        language = model[iterator][1]
        label_key = model[iterator][2]
        label = model[iterator][3]
        self._fill_flowbox(language, label_key, label)

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

    def on_emoji_selected(self, dummy_flowbox, flowbox_child):
        '''
        Signal handler for selecting an emoji in the browser

        :param dummy_flowbox: The flowbox displaying the Emoji
        :type dummy_flowbox: Gtk.FlowBox object
        :param flowbox_child: The child object containing the selected emoji
        :type flowbox_child: Gtk.FlowBoxChild object
        '''
        emoji = flowbox_child.get_child().get_text()
        # The label might contain some markup, for example
        # to change the font size for the emoji. Remove all
        # markup to get only the emoji itself:
        emoji = html.unescape(re.sub('<[^<]+?>', '', emoji))
        if _ARGS.debug:
            sys.stdout.write("on_emoji_selected() emoji = %s\n" %emoji)
        self._selection_clipboard.set_text(emoji, -1)
        self._selection_primary.set_text(emoji, -1)
        self._add_to_recently_used(emoji)

    def on_candidate_selected(self, selection):
        '''
        Signal handler for selecting a emoji in the search results

        :param selection: The selected row in the search results treeview
        :type selection: Gtk.TreeSelection object
        '''
        (model, iterator) = selection.get_selected()
        if not iterator:
            return
        if _ARGS.debug:
            sys.stdout.write(
                'on_candidate_activated() model[iterator] = %s\n'
                %model[iterator][:])
        emoji = model[iterator][1]
        self._selection_clipboard.set_text(emoji, -1)
        self._selection_primary.set_text(emoji, -1)
        self._add_to_recently_used(emoji)

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
        fontsize=_ARGS.fontsize)
    EMOJI_PICKER_UI.show_all()
    Gtk.main()
