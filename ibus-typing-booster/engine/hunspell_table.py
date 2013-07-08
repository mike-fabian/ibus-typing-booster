# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 2011-2013 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012-2013 Mike FABIAN <mfabian@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#  This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#  You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

__all__ = (
    "tabengine",
)

import os
import string
import unicodedata
import curses.ascii
import re
from gi.repository import IBus
from gi.repository import GLib
import itb_util

debug_level = int(0)

try:
    from gi.repository import Translit
    Transliterator = Translit.Transliterator
except:
    import traceback
    traceback.print_exc()

from gettext import dgettext
_  = lambda a : dgettext ("ibus-typing-booster", a)
N_ = lambda a : a

def variant_to_value(variant):
    if type(variant) != GLib.Variant:
        return variant
    type_string = variant.get_type_string()
    if type_string == 's':
        return variant.get_string()
    elif type_string == 'i':
        return variant.get_int32()
    elif type_string == 'b':
        return variant.get_boolean()
    elif type_string == 'as':
        # In the latest pygobject3 3.3.4 or later, g_variant_dup_strv
        # returns the allocated strv but in the previous release,
        # it returned the tuple of (strv, length)
        if type(GLib.Variant.new_strv([]).dup_strv()) == tuple:
            return variant.dup_strv()[0]
        else:
            return variant.dup_strv()
    else:
        print 'error: unknown variant type:', type_string
    return variant

def argb(a, r, g, b):
    return ((a & 0xff)<<24) + ((r & 0xff) << 16) + ((g & 0xff) << 8) + (b & 0xff)

def rgb(r, g, b):
    return argb(255, r, g, b)

class KeyEvent:
    def __init__(self, keyval, is_press, state):
        self.code = keyval
        self.mask = state
        if not is_press:
            self.mask |= IBus.ModifierType.RELEASE_MASK
    def __str__(self):
        return "%s 0x%08x" % (IBus.keyval_name(self.code), self.mask)


class editor(object):
    '''Hold user inputs chars and preedit string'''

    def __init__ (self, config, database):
        self.db = database
        self._config = config
        self._name = self.db.ime_properties.get('name')
        self._config_section = "engine/typing-booster/%s" % self._name
        self._min_char_complete = variant_to_value(self._config.get_value(
            self._config_section,
            'mincharcomplete'))
        if self._min_char_complete == None:
            self._min_char_complete = 1 # default
        if self._min_char_complete < 1:
            self._min_char_complete = 1 # minimum
        if self._min_char_complete > 9:
            self._min_char_complete = 9 # maximum
        self._typed_string = u''
        self._typed_string_cursor = 0
        self._typed_string_when_update_candidates_was_last_called = u''
        self._transliterated_string = u''
        self._p_phrase = u''
        self._pp_phrase = u''
        # self._candidates: hold candidates selected from database and hunspell
        self._candidates = []
        self._lookup_table = IBus.LookupTable.new(
            page_size=tabengine._page_size,
            cursor_pos=0,
            cursor_visible=False,
            round=True)
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)

        self._m17ndb = 'm17n'
        self.trans = None

        self._supported_imes = []
        if self.db.ime_properties.get('m17n_mim_name') != None:
            self._supported_imes.append(self.db.ime_properties.get('m17n_mim_name'))
        self._other_ime = self.db.ime_properties.get('other_ime').lower() == u'true'
        if self._other_ime:
            imes = self.db.ime_properties.get('imes').split(',')
            for item in imes:
                mim_name = item.split(':')[1]
                if not mim_name in self._supported_imes:
                    self._supported_imes.append(mim_name)
        if self._other_ime:
            # Several imes are selectable, try to get the selected one from dconf:
            self._current_ime = variant_to_value(self._config.get_value(
                    self._config_section,
                    'inputmethod'))
            if self._current_ime == None or not self._current_ime in self._supported_imes:
                # There is no ime set in dconf or an unsupported ime,
                # fall back to the “main” ime from the config file
                # or if that one does not exist either to the first of
                # the supported imes:
                self._current_ime = self.db.ime_properties.get('m17n_mim_name')
                if self._current_ime == None:
                    self._current_ime = self._supported_imes[0]
        else:
            # There is only one ime, get it from the config file:
            self._current_ime = self.db.ime_properties.get('m17n_mim_name')
        if self._current_ime == None or self._current_ime == 'NoIme':
            # Not using m17n transliteration:
            self.trans_m17n_mode = False
        else:
            # using m17n transliteration
            self.trans_m17n_mode = True
            try:
                #self.trans = Translit.Transliterator.get(self._m17ndb, self._current_ime)
                self.trans = Transliterator.get(self._m17ndb, self._current_ime)
            except:
                import traceback
                traceback.print_exc()

    def is_empty(self):
        return len(self._typed_string) == 0

    def clear_input(self):
        '''Clear all input'''
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)
        self._candidates = []
        self._typed_string = u''
        self._typed_string_cursor = 0
        self._typed_string_when_update_candidates_was_last_called = u''
        self._transliterated_string = u''

    def update_transliterated_string(self):
        if self.trans_m17n_mode:
            self._transliterated_string = self.trans.transliterate(
                self._typed_string)[0].decode('UTF-8')
        else:
            self._transliterated_string = self._typed_string

    def get_transliterated_string(self):
        return self._transliterated_string

    def insert_string_at_cursor(self, string_to_insert):
        '''Insert typed string at cursor position'''
        self._typed_string = self._typed_string[:self._typed_string_cursor] \
                             +string_to_insert \
                             +self._typed_string[self._typed_string_cursor:]
        self._typed_string_cursor += len(string_to_insert)
        self.update_transliterated_string()
        self.update_candidates ()

    def remove_string_before_cursor(self):
        '''Remove typed string before cursor'''
        if self._typed_string_cursor > 0:
            self._typed_string = self._typed_string[self._typed_string_cursor:]
            self._typed_string_cursor = 0
            self.update_transliterated_string()
            self.update_candidates()

    def remove_string_after_cursor(self):
        '''Remove typed string after cursor'''
        if self._typed_string_cursor < len(self._typed_string):
            self._typed_string = self._typed_string[:self._typed_string_cursor]
            self.update_transliterated_string()
            self.update_candidates()

    def remove_character_before_cursor(self):
        '''Remove typed character before cursor'''
        if self._typed_string_cursor > 0:
            self._typed_string = self._typed_string[:self._typed_string_cursor-1] \
                                 +self._typed_string[self._typed_string_cursor:]
            self._typed_string_cursor -= 1
            self.update_transliterated_string()
            self.update_candidates()

    def remove_character_after_cursor(self):
        '''Remove typed character after cursor'''
        if self._typed_string_cursor < len(self._typed_string):
            self._typed_string = self._typed_string[:self._typed_string_cursor] \
                                 +self._typed_string[self._typed_string_cursor+1:]
            self.update_transliterated_string()
            self.update_candidates()

    def get_caret (self):
        '''
        Get caret position in preëdit string

        The preëdit contains the transliterated string, the caret
        position can only be approximated from the cursor position in
        the typed string.

        For example, if the type string is “gru"n” and the
        transliteration method used is “Latin Postfix”, this
        transliterates to “grün”. Now if the cursor position in the
        typed string is “3”, then the cursor is between the “u”
        and the “"”.  In the transliterated string, this would be in the
        middle of the “ü”. But the caret cannot be shown there of course.

        So the caret position is approximated by transliterating the
        string up to the cursor, i.e. transliterating “gru” which
        gives “gru” and return the length of that
        transliteration as the caret position. Therefore, the caret
        is displayed after the “ü” instead of in the middle of the “ü”.

        This has the effect that when typing “arrow left” over a
        preëdit string “grün” which has been typed as “gru"n”
        using Latin Postfix translation, one needs to type “arrow
        left” two times to get over the “ü”.

        If the cursor is at position 3 in the input string “gru"n”,
        and one types an “a” there, the input string becomes
        “grua"n” and the transliterated string, i.e. the preëdit,
        becomes “gruän”, which might be a bit surprising, but that
        is at least consistent and better then nothing at the moment.

        This problem is certainly worse in languages like Marathi where
        these length differences between the input and the transliteration
        are worse.

        But until this change, the code to move around and edit in
        the preëdit did not work at all. Now it works fine if
        no transliteration is used and works better than nothing
        even if transliteration is used.
        '''
        if self.trans_m17n_mode:
            transliterated_string_up_to_cursor = self.trans.transliterate(
                self._typed_string[:self._typed_string_cursor])[0].decode('UTF-8')
        else:
            transliterated_string_up_to_cursor = self._typed_string[:self._typed_string_cursor]
        transliterated_string_up_to_cursor = unicodedata.normalize(
            'NFC', transliterated_string_up_to_cursor)
        return len(transliterated_string_up_to_cursor)

    def arrow_left (self):
        '''
        Move cursor left in the typed string.
        '''
        if self._typed_string_cursor > 0:
            self._typed_string_cursor -= 1

    def arrow_right (self):
        '''
        Move cursor right in the typed string.
        '''
        if self._typed_string_cursor < len(self._typed_string):
            self._typed_string_cursor += 1

    def control_arrow_left (self):
        '''
        Move cursor to the beginning of the typed string
        '''
        self._typed_string_cursor = 0

    def control_arrow_right (self):
        '''
        Move cursor to the end of the typed string
        '''
        self._typed_string_cursor = len(self._typed_string)

    def append_candidate_to_lookup_table(self, phrase=u'', user_freq=0):
        '''append candidate to lookup_table'''
        if not phrase:
            return
        phrase = unicodedata.normalize('NFC', phrase)
        transliterated_string = unicodedata.normalize('NFC', self._transliterated_string)
        attrs = IBus.AttrList ()
        if not phrase.startswith(transliterated_string):
            # this is a candidate which does not start exactly
            # as the transliterated user input, i.e. it is a suggestion
            # for a spelling correction:
            if debug_level > 0:
                phrase = phrase + u' ✓'
            attrs.append(IBus.attr_foreground_new(rgb(0xff,0x00,0x00), 0, len(phrase)))
        elif user_freq > 10:
            # this is a frequently used phrase:
            attrs.append(IBus.attr_foreground_new(rgb(0xff,0x7f,0x00), 0, len(phrase)))
        else:
            # this is a system phrase that has been used less then 10 times or maybe never:
            attrs.append(IBus.attr_foreground_new(rgb(0x00,0x00,0x00), 0, len(phrase)))
        if debug_level > 0:
            phrase += u' ' + str(user_freq)
            attrs.append(IBus.attr_foreground_new(
                rgb(0x00,0xff,0x00), len(phrase) - len(str(user_freq)), len(phrase)))
        text = IBus.Text.new_from_string(phrase)
        i = 0
        while attrs.get(i) != None:
            attr = attrs.get(i)
            text.append_attribute(attr.get_attr_type(),
                                  attr.get_value(),
                                  attr.get_start_index(),
                                  attr.get_end_index())
            i += 1
        self._lookup_table.append_candidate(text)
        self._lookup_table.set_cursor_visible(False)

    def update_candidates (self):
        '''Update lookuptable'''
        if self._typed_string == self._typed_string_when_update_candidates_was_last_called:
            # The input did not change since we came here last, do nothing and leave
            # candidates and lookup table unchanged:
            return True
        self._typed_string_when_update_candidates_was_last_called = self._typed_string[:]
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)
        self._candidates = []
        prefix_length = 0
        prefix = u''
        if self._transliterated_string:
            stripped_transliterated_string = itb_util.lstrip_token(self._transliterated_string)
            if len(stripped_transliterated_string) >= self._min_char_complete:
                prefix_length = len(self._transliterated_string) - len(stripped_transliterated_string)
                if prefix_length:
                    prefix = self._transliterated_string[0:prefix_length]
                try:
                    self._candidates = self.db.select_words(stripped_transliterated_string, p_phrase=self._p_phrase, pp_phrase=self._pp_phrase)
                except:
                    import traceback
                    traceback.print_exc()
        if self._candidates:
            if prefix:
                self._candidates = map(lambda x: (prefix+x[0], x[1]), self._candidates)
            map(lambda x:
                self.append_candidate_to_lookup_table(phrase=x[0], user_freq=x[1]),
                self._candidates)
        return True

    def arrow_down(self):
        '''Process Arrow Down Key Event
        Move Lookup Table cursor down'''
        if not self._lookup_table.cursor_visible:
            self._lookup_table.set_cursor_visible(True)
            return True
        else:
            res = self._lookup_table.cursor_down()
            self.update_candidates ()
            if not res and self._candidates:
                return True
            return res

    def arrow_up(self):
        '''Process Arrow Up Key Event
        Move Lookup Table cursor up'''
        self._lookup_table.set_cursor_visible(True)
        res = self._lookup_table.cursor_up()
        self.update_candidates ()
        if not res and self._candidates:
            return True
        return res

    def page_down(self):
        '''Process Page Down Key Event
        Move Lookup Table page down'''
        self._lookup_table.set_cursor_visible(True)
        res = self._lookup_table.page_down()
        self.update_candidates ()
        if not res and self._candidates:
            return True
        return res

    def page_up(self):
        '''Process Page Up Key Event
        move Lookup Table page up'''
        self._lookup_table.set_cursor_visible(True)
        res = self._lookup_table.page_up()
        self.update_candidates ()
        if not res and self._candidates:
            return True
        return res

    def get_string_from_lookup_table_current_page(self, index):
        '''
        Get the candidate at “index” in the currently visible
        page of the lookup table. The topmost candidate
        has the index 0 and has the label “1.”.
        '''
        if not self._candidates:
            return u''
        cursor_pos = self._lookup_table.get_cursor_pos()
        cursor_in_page = self._lookup_table.get_cursor_in_page()
        current_page_start = cursor_pos - cursor_in_page
        real_index = current_page_start + index
        if real_index >= len (self._candidates):
            # the index given is out of range
            return u''
        return self._candidates[real_index][0]

    def get_string_from_lookup_table_cursor_pos(self):
        '''
        Get the candidate at the current cursor position in the lookup
        table.
        '''
        if not self._candidates:
            return u''
        index = self._lookup_table.get_cursor_pos()
        if index >= len (self._candidates):
            # the index given is out of range
            return u''
        return self._candidates[index][0]

    def alt_number (self,index):
        '''Remove the phrase selected with Alt+Number from the user database.

        The index parameter should start from 0.

        The removal is done independent of the input phrase, all
        rows in the user database for that phrase are deleted.

        It does not matter either whether this is a user defined
        phrase or a phrase which can be found in the hunspell
        dictionaries.  In both cases, it is removed from the user
        database.

        In case of a system phrase, which can be found in the hunspell
        dictionaries, this means that the phrase could still appear in
        the suggestions after removing it from the user database
        because it still can be suggested by the hunspell
        dictionaries. But it becomes less likely because removing a
        system phrase from the user database resets its user frequency
        to 0 again.

        So the user can always type Alt+Number on a phrase he does not
        want the phrase to be suggested wich such a high priority, no
        matter whether it is a system phrase or a user defined phrase.
        '''
        cursor_pos = self._lookup_table.get_cursor_pos()
        cursor_in_page = self._lookup_table.get_cursor_in_page()
        current_page_start = cursor_pos - cursor_in_page
        real_index = current_page_start + index
        if  len (self._candidates) > real_index:
            # this index is valid
            can = self._candidates[real_index]
            self.db.remove_phrase(phrase=can[0], database='user_db', commit=True)
            # call update_candidates() to get a new SQL query.  The
            # input has not really changed, therefore we must clear
            # the remembered list of transliterated characters to
            # force update_candidates() to really do something and not
            # return immediately:
            self._typed_string_when_update_candidates_was_last_called = u''
            self.update_candidates()
            return True
        else:
            return False

    def get_cursor_pos (self):
        '''get lookup table cursor position'''
        return self._lookup_table.get_cursor_pos()

    def get_lookup_table (self):
        '''Get lookup table'''
        return self._lookup_table

    def push_context(self, phrase):
        self._pp_phrase = self._p_phrase
        self._p_phrase = phrase

    def clear_context(self):
        self._pp_phrase = u''
        self._p_phrase = u''

########################
### Engine Class #####
####################
class tabengine (IBus.Engine):
    '''The IM Engine for Tables'''

    def __init__ (self, bus, obj_path, db ):
        super(tabengine,self).__init__ (connection=bus.get_connection(),object_path=obj_path)
        global debug_level
        try:
            debug_level = int(os.getenv('IBUS_TYPING_BOOSTER_DEBUG_LEVEL'))
        except:
            debug_level = int(0)
        self._bus = bus
        self.db = db
        self._name = self.db.ime_properties.get('name')
        self._config_section = "engine/typing-booster/%s" % self._name
        self._config = self._bus.get_config ()
        self._config.connect('value-changed', self.__config_value_changed_cb)

        tabengine._page_size = variant_to_value(self._config.get_value(
                self._config_section,
                'pagesize'))
        if tabengine._page_size == None:
            tabengine._page_size = self.db.ime_properties.get('page_size')
        if tabengine._page_size == None:
            tabengine._page_size = 6 # reasonable default page size
        if tabengine._page_size < 1:
            tabengine._page_size = 1 # minimum page size supported
        if tabengine._page_size > 9:
            tabengine._page_size = 9 # maximum page size supported

        self._show_number_of_candidates = variant_to_value(self._config.get_value(
                self._config_section,
                'shownumberofcandidates'))
        if self._show_number_of_candidates == None:
            self._show_number_of_candidates = False

        self._icon_dir = '%s%s%s%s' % (os.getenv('IBUS_HUNSPELL_TABLE_LOCATION'),
                os.path.sep, 'icons', os.path.sep)
        # 0 = english input mode
        # 1 = table input mode
        self._mode = 1

        self._status = self.db.ime_properties.get('status_prompt').encode('utf8')

        self._page_down_keys = [IBus.KEY_Page_Down, IBus.KEY_KP_Page_Down]
        self._page_up_keys = [IBus.KEY_Page_Up, IBus.KEY_KP_Page_Up]

        self._editor = editor(self._config, self.db)
        self.is_lookup_table_enabled_by_tab = False
        self._tab_enable = variant_to_value(self._config.get_value (
            self._config_section,
            "tabenable"))
        if self._tab_enable == None:
            self._tab_enable = self.db.ime_properties.get('tab_enable').lower() == u'true'
        self._commit_happened_after_focus_in = False
        self.reset ()

    def reset (self):
        self._editor.clear_input()
        self._update_ui ()

    def do_destroy(self):
        self.reset ()
        self.do_focus_out ()
        super(tabengine,self).destroy()

    def _change_mode (self):
        '''Shift input mode, TAB -> EN -> TAB
        '''
        self.reset ()
        self._update_ui ()

    def _update_preedit (self):
        '''Update Preedit String in UI'''
        # editor.get_caret() should also use NFC!
        _str = unicodedata.normalize('NFC', self._editor.get_transliterated_string())
        if _str == u'':
            super(tabengine, self).update_preedit_text(IBus.Text.new_from_string(u''), 0, False)
        else:
            attrs = IBus.AttrList()
            attrs.append(IBus.attr_foreground_new(rgb(0x0e,0x0e,0xa0), 0, len(_str)))
            attrs.append(IBus.attr_underline_new(IBus.AttrUnderline.SINGLE, 0, len(_str)))
            text = IBus.Text.new_from_string(_str)
            i = 0
            while attrs.get(i) != None:
                attr = attrs.get(i)
                text.append_attribute(attr.get_attr_type(),
                                      attr.get_value(),
                                      attr.get_start_index(),
                                      attr.get_end_index())
                i += 1
            super(tabengine, self).update_preedit_text(text, self._editor.get_caret(), True)

    def _update_aux (self):
        '''Update Aux String in UI'''
        aux_string = u'(%d / %d)' % (self._editor._lookup_table.get_cursor_pos() + 1,
                                   self._editor._lookup_table.get_number_of_candidates())
        if aux_string:
            # Colours do not work at the moment in the auxiliary text!
            # Needs fix in ibus.
            attrs = IBus.AttrList()
            attrs.append(IBus.attr_foreground_new(rgb(0x95,0x15,0xb5),0,len(aux_string)))
            if debug_level > 0:
                context = u' ' + self._editor._pp_phrase + u' ' + self._editor._p_phrase
                aux_string += context
                attrs.append(IBus.attr_foreground_new(
                    rgb(0x00,0xff,0x00),len(aux_string)-len(context), len(aux_string)))
            text = IBus.Text.new_from_string(aux_string)
            i = 0
            while attrs.get(i) != None:
                attr = attrs.get(i)
                text.append_attribute(attr.get_attr_type(),
                                      attr.get_value(),
                                      attr.get_start_index(),
                                      attr.get_end_index())
                i += 1
            visible = True
            if self._editor._lookup_table.get_number_of_candidates() == 0 \
                    or self._show_number_of_candidates == False \
                    or (self._tab_enable and not self.is_lookup_table_enabled_by_tab):
                visible = False
            super(tabengine, self).update_auxiliary_text(text, visible)
        else:
            self.hide_auxiliary_text()

    def _update_lookup_table (self):
        '''Update Lookup Table in UI'''
        if self._editor.is_empty ():
            self.hide_lookup_table()
            return
        # Also make sure to hide lookup table if there are
        # no candidates to display. On f17, this makes no
        # difference but gnome-shell in f18 will display
        # an empty suggestion popup if the number of candidates
        # is zero!
        if len(self._editor._candidates) == 0:
            self.hide_lookup_table()
            return
        if self._tab_enable:
            if self.is_lookup_table_enabled_by_tab:
                self.update_lookup_table(self._editor.get_lookup_table(), True)
            else:
                self.hide_lookup_table()
        else:
            self.update_lookup_table(self._editor.get_lookup_table(), True)

    def _update_ui (self):
        '''Update User Interface'''
        self._update_lookup_table ()
        self._update_preedit ()
        self._update_aux ()

    def commit_string (self, commit_phrase, input_phrase=u''):
        if not input_phrase:
            input_phrase = self._editor.get_transliterated_string()
        # commit always in NFC:
        commit_phrase = unicodedata.normalize('NFC', commit_phrase)
        super(tabengine,self).commit_text(IBus.Text.new_from_string(commit_phrase))
        self._editor.clear_input()
        self._update_ui ()
        self._commit_happened_after_focus_in = True
        if self.client_capabilities & IBus.Capabilite.SURROUNDING_TEXT:
            # If a character ending a sentence is committed (possibly
            # followed by whitespace) remove trailing white space
            # before the committed string. For example if commit_phrase is “!”,
            # and the context before is “word ”, make the result “word!”.
            # And if the commit_phrase is “! ” and the context before is “word ”
            # make the result “word! ”.
            pattern_sentence_end = re.compile(r'^[.,;:?!][\s]*$', re.UNICODE)
            if pattern_sentence_end.search(commit_phrase):
                surrounding_text = self.get_surrounding_text()
                text = surrounding_text[0].get_text().decode('UTF-8')
                cursor_pos = surrounding_text[1]
                anchor_pos = surrounding_text[2]
                # The commit_phrase is *not* yet in the surrounding text, it will
                # show up there only when the next key event is processed:
                pattern = re.compile(r'(?P<white_space>[\s]+)$', re.UNICODE)
                match = pattern.search(text[:cursor_pos])
                if match:
                    nchars = len(match.group('white_space'))
                    # when the “delete surrounding text” happens,
                    # the commit_phrase *is* already in the
                    # surrounding text. Therefore, the offset is not
                    # only -nchars but -(nchars +
                    # len(commit_phrase)):
                    offset =  -(nchars + len(commit_phrase))
                    self.delete_surrounding_text(offset, nchars)
        stripped_input_phrase = itb_util.strip_token(input_phrase)
        stripped_commit_phrase = itb_util.strip_token(commit_phrase)
        self.db.check_phrase_and_update_frequency(
            input_phrase=stripped_input_phrase,
            phrase=stripped_commit_phrase,
            p_phrase=self._editor._p_phrase,
            pp_phrase=self._editor._pp_phrase)
        self._editor.push_context(stripped_commit_phrase)

    def get_context(self):
        if not (self.client_capabilities & IBus.Capabilite.SURROUNDING_TEXT):
            # If getting the surrounding text is not supported, leave
            # the context as it is, i.e. rely on remembering what was
            # typed last.
            return
        surrounding_text = self.get_surrounding_text()
        text = surrounding_text[0].get_text().decode('UTF-8')
        cursor_pos = surrounding_text[1]
        anchor_pos = surrounding_text[2]
        if not surrounding_text:
            return
        if not self._commit_happened_after_focus_in:
            # Before the first commit or cursor movement, the
            # surrounding text is probably from the previously
            # focused window (bug!), don’t use it.
            return
        tokens = map(itb_util.strip_token, itb_util.tokenize(text[:cursor_pos]))
        if len(tokens):
            self._editor._p_phrase = tokens[-1]
        if len(tokens) > 1:
            self._editor._pp_phrase = tokens[-2]

    def do_process_key_event(self, keyval, keycode, state):
        '''Process Key Events
        Key Events include Key Press and Key Release,
        modifier means Key Pressed
        '''
        key = KeyEvent(keyval, state & IBus.ModifierType.RELEASE_MASK == 0, state)
        # ignore NumLock mask
        key.mask &= ~IBus.ModifierType.MOD2_MASK

        result = self._process_key_event (key)
        return result

    def _process_key_event (self, key):
        '''Internal method to process key event

        Returns True if the key event has been completely handled by
        ibus-typing-booster and should not be passed through anymore.
        Returns False if the key event has not been handled completely
        and is passed through.

        '''

        if key.mask & IBus.ModifierType.RELEASE_MASK:
            return True

        if self._editor.is_empty ():
            # This is the first character typed since the last commit
            # there is nothing in the preëdit yet.
            if key.code < 32:
                # If the first character of a new word is a control
                # character, return False to pass the character through as is,
                # it makes no sense trying to complete something
                # starting with a control character:
                return False
            if key.code == IBus.KEY_space:
                # if the first character is a space, just pass it through
                # it makes not sense trying to complete:
                return False
            if  key.code >= 32 and (not (key.mask & (IBus.ModifierType.MOD1_MASK | IBus.ModifierType.CONTROL_MASK))):
                typed_character = IBus.keyval_to_unicode(key.code).decode('UTF-8')
                # If the first character typed is a character which is
                # very unlikely to be part of a word
                # (e.g. punctuation, a symbol, ..), we might want to
                # avoid completion and commit something immediately:
                if typed_character and unicodedata.category(typed_character) in itb_util.categories_to_trigger_immediate_commit:
                    if not self._editor.trans_m17n_mode:
                        # Do not just pass the character through,
                        # commit it properly.  For example if it is a
                        # “.” we might want to remove whitespace
                        # between the “.” and the previous word and this is
                        # done in commit_string().
                        self.commit_string(typed_character, input_phrase = typed_character)
                        return True
                    # If transliteration is used, we may need to
                    # handle a punctuation or symbol character. For
                    # example, “.c” is transliterated to “ċ” in
                    # the “t-latn-pre” transliteration method,
                    # therefore we cannot just pass it through. Just
                    # add it to the input so far and see what comes
                    # next:
                    self._editor.insert_string_at_cursor(typed_character)
                    self._update_ui()
                    return True
                if typed_character and unicodedata.digit(typed_character, -1) != -1:
                    if not self._editor.trans_m17n_mode:
                        # If a digit has been typed and no transliteration
                        # is used, we can pass it through
                        return False
                    # If a digit has been typed and we use
                    # transliteration, we may want to convert it to
                    # native digits. For example, with mr-inscript we
                    # want “3” to be converted to “३”. So we try
                    # to transliterate and commit the result:
                    transliterated_digit = self._editor.trans.transliterate(
                        typed_character)[0].decode('utf8')
                    self.commit_string(transliterated_digit, input_phrase=transliterated_digit)
                    return True

        if key.code == IBus.KEY_Escape:
            if self._editor.is_empty():
                return False
            self.reset ()
            self._update_ui ()
            return True

        if key.code in (IBus.KEY_Down, IBus.KEY_KP_Down):
            if self._editor.is_empty():
                return False
            res = self._editor.arrow_down ()
            self._update_ui ()
            return res

        if key.code in (IBus.KEY_Up, IBus.KEY_KP_Up):
            if self._editor.is_empty():
                return False
            res = self._editor.arrow_up ()
            self._update_ui ()
            return res

        if key.code in self._page_down_keys and self._editor._candidates:
            res = self._editor.page_down()
            self._update_ui ()
            return res

        if key.code in self._page_up_keys and self._editor._candidates:
            res = self._editor.page_up ()
            self._update_ui ()
            return res

        if key.code in (IBus.KEY_Left, IBus.KEY_KP_Left) and key.mask & IBus.ModifierType.CONTROL_MASK:
            if self._editor.is_empty():
                return False
            self._editor.control_arrow_left()
            self._update_ui()
            return True

        if key.code in (IBus.KEY_Right, IBus.KEY_KP_Right) and key.mask & IBus.ModifierType.CONTROL_MASK:
            if self._editor.is_empty():
                return False
            self._editor.control_arrow_right()
            self._update_ui()
            return True

        if key.code in (IBus.KEY_Left, IBus.KEY_KP_Left):
            if self._editor.is_empty():
                return False
            self._editor.arrow_left()
            self._update_ui()
            return True

        if key.code in (IBus.KEY_Right, IBus.KEY_KP_Right):
            if self._editor.is_empty():
                return False
            res = self._editor.arrow_right ()
            self._update_ui ()
            return res

        if key.code == IBus.KEY_BackSpace and key.mask & IBus.ModifierType.CONTROL_MASK:
            if self._editor.is_empty():
                return False
            self._editor.remove_string_before_cursor()
            self._update_ui()
            return True

        if key.code == IBus.KEY_BackSpace:
            if self._editor.is_empty():
                return False
            self._editor.remove_character_before_cursor()
            self._update_ui()
            return True

        if key.code == IBus.KEY_Delete  and key.mask & IBus.ModifierType.CONTROL_MASK:
            if self._editor.is_empty():
                return False
            self._editor.remove_string_after_cursor()
            self._update_ui()
            return True

        if key.code == IBus.KEY_Delete:
            if self._editor.is_empty():
                return False
            self._editor.remove_character_after_cursor()
            self._update_ui()
            return True

        if key.code >= IBus.KEY_1 and key.code <= IBus.KEY_9 and self._editor._candidates and key.mask & IBus.ModifierType.CONTROL_MASK:
            res = self._editor.alt_number (key.code - IBus.KEY_1)
            self._update_ui ()
            return res

        if key.code >= IBus.KEY_1 and key.code <= IBus.KEY_9 and self._editor._candidates and key.mask & IBus.ModifierType.MOD1_MASK:
            res = self._editor.alt_number (key.code - IBus.KEY_1)
            self._update_ui ()
            return res

        if key.code >= IBus.KEY_1 and key.code <= IBus.KEY_9 and self._editor._candidates:
            phrase = self._editor.get_string_from_lookup_table_current_page(key.code - IBus.KEY_1)
            if phrase:
                self.commit_string(phrase + u' ')
            return True

        if key.code == IBus.KEY_Tab:
            if self._tab_enable:
                # toggle whether the lookup table should be displayed
                # or not
                if self.is_lookup_table_enabled_by_tab == True:
                    self.is_lookup_table_enabled_by_tab = False
                else:
                    self.is_lookup_table_enabled_by_tab = True
                # update the ui here to see the effect immediately
                # do not wait for the next keypress:
                self._update_ui()
                return True
            else:
                if self._editor._candidates:
                    phrase = self._editor.get_string_from_lookup_table_cursor_pos()
                    if phrase:
                        self.commit_string(phrase + u' ')
                    return True
                else:
                    input_phrase = self._editor.get_transliterated_string()
                    if input_phrase:
                        self.commit_string(input_phrase + u' ', input_phrase = input_phrase)
                    return True
            return True

        if key.code in (IBus.KEY_Return, IBus.KEY_KP_Enter, IBus.KEY_space):
            if self._editor.is_empty():
                return False
            input_phrase = self._editor.get_transliterated_string()
            if not input_phrase:
                return False
            if not self._editor._candidates:
                self.commit_string(input_phrase, input_phrase = input_phrase)
                return False
            phrase = self._editor.get_string_from_lookup_table_cursor_pos()
            if not phrase:
                return False
            if self._editor._lookup_table.cursor_visible:
                # something is selected in the lookup table, commit
                # the selected phrase
                self.commit_string(phrase, input_phrase = input_phrase)
            else:
                # nothing is selected in the lookup table, commit the
                # input_phrase
                self.commit_string(input_phrase, input_phrase = input_phrase)
            return False

        # We pass all other hotkeys through:
        if key.mask & (IBus.ModifierType.CONTROL_MASK|IBus.ModifierType.MOD1_MASK):
            return False

        if key.mask & IBus.ModifierType.MOD1_MASK:
            return False

        if IBus.keyval_to_unicode(key.code):
            if self._editor.is_empty():
                # first key typed, we will try to complete something now
                # get the context if possible
                self.get_context()
            typed_character = IBus.keyval_to_unicode(key.code).decode('UTF-8')
            self._editor.insert_string_at_cursor(typed_character)
            if typed_character and unicodedata.category(typed_character) in itb_util.categories_to_trigger_immediate_commit:
                input_phrase = self._editor.get_transliterated_string()
                if input_phrase and input_phrase[-1] == typed_character and not self._editor.trans_m17n_mode:
                    self.commit_string(input_phrase + u' ', input_phrase = input_phrase)
            self._update_ui()
            return True

        return False

    def do_focus_in (self):
        self._editor.clear_context()
        self._commit_happened_after_focus_in = False
        self._update_ui ()

    def do_focus_out (self):
        self._editor.clear_context()
        self.reset()
        return

    def do_enable (self):
        # Tell the input-context that the engine will utilize
        # surrounding-text:
        self.get_surrounding_text()
        self.do_focus_in()

    def do_disable (self):
        self.reset()

    def do_page_up (self):
        if self._editor.page_up ():
            self._update_ui ()
            return True
        return True

    def do_page_down (self):
        if self._editor.page_down ():
            self._update_ui ()
            return True
        return False

    def config_section_normalize(self, section):
        # This function replaces _: with - in the dconf
        # section and converts to lower case to make
        # the comparison of the dconf sections work correctly.
        # I avoid using .lower() here because it is locale dependent,
        # when using .lower() this would not achieve the desired
        # effect of comparing the dconf sections case insentively
        # in some locales, it would fail for example if Turkish
        # locale (tr_TR.UTF-8) is set.
        return re.sub(r'[_:]', r'-', section).translate(
            string.maketrans(string.ascii_uppercase, string.ascii_lowercase).decode('ISO-8859-1'))

    def __config_value_changed_cb(self, config, section, name, value):
        if self.config_section_normalize(self._config_section) != self.config_section_normalize(section):
            return
        print "config value %(n)s for engine %(en)s changed" %{'n': name, 'en': self._name}
        value = variant_to_value(value)
        if name == "tabenable":
            if value == 1:
                self._tab_enable = True
            else:
                self._tab_enable = False
            return
        if name == "pagesize":
            if value >= 1 and value <= 9:
                tabengine._page_size = value
                self._editor._lookup_table = IBus.LookupTable.new(
                    page_size=tabengine._page_size,
                    cursor_pos=0,
                    cursor_visible=False,
                    round=True)
                self.reset()
            return
        if name == "mincharcomplete":
            if value >= 1 and value <= 9:
                self._editor._min_char_complete = value
                self.reset()
            return
        if name == "shownumberofcandidates":
            if value == True:
                self._show_number_of_candidates = True
            else:
                self._show_number_of_candidates = False
            self.reset()
            return
        if name == "inputmethod":
            if value in self._editor._supported_imes:
                self._editor._current_ime = value
                if value != 'NoIme':
                    print "Switching to transliteration using  ime=%s" %value
                    self._editor.trans_m17n_mode = True
                    self._editor.trans = Transliterator.get(self._editor._m17ndb, value)
                else:
                    print "Switching off transliteration."
                    self._editor.trans_m17n_mode = False
            else:
                print "error: trying to set unsupported ime: ", value
            self.reset()
            return
        if name == "dictionaryinstalltimestamp":
            # The dictionary has bin updated or installed, (re)load it:
            print "Reloading dictionary ..."
            self.db.hunspell_obj.load_dictionary()
            self.reset()
            return
