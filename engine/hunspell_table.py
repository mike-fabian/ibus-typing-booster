# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2011-2013 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012-2016 Mike FABIAN <mfabian@redhat.com>
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

__all__ = (
    "tabengine",
)

import os
import sys
import string
import unicodedata
import re
import time
from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus
from gi.repository import GLib
from m17n_translit import Transliterator
import itb_util
import itb_emoji

DEBUG_LEVEL = int(0)

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
        print('error: unknown variant type: %s' %type_string)
    return variant

def argb(a, r, g, b):
    return (((a & 0xff)<<24)
            + ((r & 0xff) << 16)
            + ((g & 0xff) << 8)
            + (b & 0xff))

def rgb(r, g, b):
    return argb(255, r, g, b)

class KeyEvent:
    def __init__(self, keyval, keycode, state):
        self.val = keyval
        self.code = keycode
        self.state = state
        self.name = IBus.keyval_name(self.val)
        self.unicode = IBus.keyval_to_unicode(self.val)
        self.msymbol = self.unicode
        self.control = 0 != self.state & IBus.ModifierType.CONTROL_MASK
        self.mod1 = 0 != self.state & IBus.ModifierType.MOD1_MASK
        self.mod5 = 0 != self.state & IBus.ModifierType.MOD5_MASK
        self.release = 0 != self.state & IBus.ModifierType.RELEASE_MASK
        if itb_util.is_ascii(self.msymbol):
            if self.control:
                self.msymbol = 'C-' + self.msymbol
            if self.mod1:
                self.msymbol = 'A-' + self.msymbol
            if self.mod5:
                self.msymbol = 'G-' + self.msymbol
    def __str__(self):
        return (
            "val=%s code=%s state=0x%08x name='%s' unicode='%s' msymbol='%s' "
            % (self.val,
               self.code,
               self.state,
               self.name,
               self.unicode,
               self.msymbol)
            + "control=%s mod1=%s mod5=%s release=%s\n"
            % (self.control,
               self.mod1,
               self.mod5,
               self.release))

class editor(object):
    '''Hold user inputs chars and preedit string'''

    def __init__ (self, config, database, lookup_table, tab_enable = False):
        if DEBUG_LEVEL > 1:
            sys.stderr.write("editor __init__(config=%s, database=%s)\n"
                             %(config, database))
        self.db = database
        self._config = config
        self._name = self.db.ime_properties.get('name')
        self._config_section = "engine/typing-booster/%s" % self._name
        self._emoji_predictions = variant_to_value(self._config.get_value(
            self._config_section,
            'emojipredictions'))
        if self._emoji_predictions == None:
            self._emoji_predictions = True # default
        self._tab_enable = tab_enable
        self._min_char_complete = variant_to_value(self._config.get_value(
            self._config_section,
            'mincharcomplete'))
        if self._min_char_complete == None:
            self._min_char_complete = 1 # default
        if self._min_char_complete < 1:
            self._min_char_complete = 1 # minimum
        if self._min_char_complete > 9:
            self._min_char_complete = 9 # maximum
        self._typed_string = []
        self._typed_string_cursor = 0
        self._p_phrase = ''
        self._pp_phrase = ''
        # self._candidates: hold candidates selected from database and hunspell
        self._candidates = []
        self._lookup_table = lookup_table
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)

        self._add_direct_input = variant_to_value(self._config.get_value(
            self._config_section,
            'adddirectinput'))
        if self._add_direct_input == None:
            self._add_direct_input = False
        dictionary = variant_to_value(self._config.get_value(
            self._config_section,
            'dictionary'))
        if dictionary:
            # There is a dictionary setting in dconf, use that instead
            # of the default dictionary from the config file:
            self.db.hunspell_obj.set_dictionary_names(
                [x.strip() for x in dictionary.split(',')])
        self._dictionary_names = self.db.hunspell_obj.get_dictionary_names()
        if self._add_direct_input == True:
            # if direct input is used as well, add the British English
            # dictionary unless it is already there:
            if 'en_GB' not in self._dictionary_names:
                self._dictionary_names.append('en_GB')
                self.db.hunspell_obj.set_dictionary_names(
                    self._dictionary_names)
                # write changed default dictionary list to dconf:
                self._config.set_value(
                    self._config_section,
                    'dictionary',
                    GLib.Variant.new_string(','.join(self._dictionary_names)))
        if  self._emoji_predictions:
            if DEBUG_LEVEL > 1:
                sys.stderr.write('Instantiate EmojiMatcher(languages = %s\n'
                                 %self._dictionary_names)
            self.emoji_matcher = itb_emoji.EmojiMatcher(
                languages = self._dictionary_names)
            if DEBUG_LEVEL > 1:
                sys.stderr.write('EmojiMatcher() instantiated.\n')
        else:
            self.emoji_matcher = None
        self._supported_imes = []
        imes = self.db.ime_properties.get('imes').split(',')
        for item in imes:
            mim_name = item.split(':')[1]
            if not mim_name in self._supported_imes:
                self._supported_imes.append(mim_name)
        if self._supported_imes == []:
            self._supported_imes = ['NoIme']
        # The number of current imes needs to be limited to some fixed
        # maximum number because of the property menu to select the preëdit
        # ime. Unfortunately the number of sub-properties for such a menu
        # cannot be changed, as a workaround a fixed number can be used
        # and unused entries can be hidden.
        self._current_imes_max = 10
        self._current_imes = []
        # Try to get the selected input methods from dconf:
        inputmethod = variant_to_value(self._config.get_value(
                self._config_section,
                'inputmethod'))
        if inputmethod:
            inputmethods = [x.strip() for x in inputmethod.split(',')]
            for ime in inputmethods:
                self._current_imes.append(ime)
        if self._current_imes == []:
            # There is no ime set in dconf, fall
            # back to the first of the supported imes:
            self._current_imes = [self._supported_imes[0]]
            if self._add_direct_input and 'NoIme' not in self._current_imes:
                self._current_imes.append('NoIme')
            # No imes were found in dconf, write the default:
            self._config.set_value(
                self._config_section,
                'inputmethod',
                GLib.Variant.new_string(','.join(self._current_imes)))
        self._transliterated_strings = {}
        self._transliterators = {}
        self.init_transliterators()

    def init_transliterators(self):
        self._transliterators = {}
        for ime in self._current_imes:
            # using m17n transliteration
            try:
                if DEBUG_LEVEL > 1:
                    sys.stderr.write(
                        "instantiating Transliterator(%(ime)s)\n"
                        %{'ime': ime})
                self._transliterators[ime] = Transliterator(ime)
            except ValueError as e:
                sys.stderr.write('Error initializing Transliterator: %s' %e)
                import traceback
                traceback.print_exc()
        self.update_transliterated_strings()

    def is_empty(self):
        return len(self._typed_string) == 0

    def clear_input(self):
        '''Clear all input'''
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)
        self._candidates = []
        self._typed_string = []
        self._typed_string_cursor = 0
        for ime in self._current_imes:
            self._transliterated_strings[ime] = ''

    def update_transliterated_strings(self):
        self._transliterated_strings = {}
        for ime in self._current_imes:
            self._transliterated_strings[ime] = (
                self._transliterators[ime].transliterate(
                    self._typed_string))
            if ime in ['ko-romaja', 'ko-han2']:
                self._transliterated_strings[ime] = unicodedata.normalize(
                    'NFKD', self._transliterated_strings[ime])
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "update_transliterated_strings() self._typed_string=%s\n"
                %self._typed_string)
            sys.stderr.write(
                "update_transliterated_strings() "
                + "self._transliterated_strings=%s\n"
                %self._transliterated_strings)

    def get_transliterators(self):
        '''Get current dictionary of transliterator objects'''
        return self._transliterators

    def get_transliterated_strings(self):
        return self._transliterated_strings

    def get_typed_string(self):
        return self._typed_string

    def get_typed_string_cursor(self):
        return self._typed_string_cursor

    def set_typed_string_cursor(self, cursor):
        self._typed_string_cursor = cursor

    def insert_string_at_cursor(self, string_to_insert):
        '''Insert typed string at cursor position'''
        if DEBUG_LEVEL > 1:
            sys.stderr.write("insert_string_at_cursor() string_to_insert=%s\n"
                             %string_to_insert)
            sys.stderr.write("insert_string_at_cursor() "
                             + "self._typed_string=%s\n"
                             %self._typed_string)
            sys.stderr.write("insert_string_at_cursor() "
                             + "self._typed_string_cursor=%s\n"
                             %self._typed_string_cursor)
        self._typed_string = self._typed_string[:self._typed_string_cursor] \
                             +string_to_insert \
                             +self._typed_string[self._typed_string_cursor:]
        self._typed_string_cursor += len(string_to_insert)
        self.update_transliterated_strings()

    def remove_string_before_cursor(self):
        '''Remove typed string before cursor'''
        if self._typed_string_cursor > 0:
            self._typed_string = self._typed_string[self._typed_string_cursor:]
            self._typed_string_cursor = 0
            self.update_transliterated_strings()

    def remove_string_after_cursor(self):
        '''Remove typed string after cursor'''
        if self._typed_string_cursor < len(self._typed_string):
            self._typed_string = self._typed_string[:self._typed_string_cursor]
            self.update_transliterated_strings()

    def remove_character_before_cursor(self):
        '''Remove typed character before cursor'''
        if self._typed_string_cursor > 0:
            self._typed_string = (
                self._typed_string[:self._typed_string_cursor-1]
                +self._typed_string[self._typed_string_cursor:])
            self._typed_string_cursor -= 1
            self.update_transliterated_strings()

    def remove_character_after_cursor(self):
        '''Remove typed character after cursor'''
        if self._typed_string_cursor < len(self._typed_string):
            self._typed_string = (
                self._typed_string[:self._typed_string_cursor]
                +self._typed_string[self._typed_string_cursor+1:])
            self.update_transliterated_strings()

    def get_caret (self):
        '''
        Get caret position in preëdit string

        The preëdit contains the transliterated string, the caret
        position can only be approximated from the cursor position in
        the typed string.

        For example, if the typed string is “gru"n” and the
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
        preedit_ime = self._current_imes[0]
        transliterated_string_up_to_cursor = (
            self._transliterators[preedit_ime].transliterate(
                self._typed_string[:self._typed_string_cursor]))
        if preedit_ime in ['ko-romaja', 'ko-han2']:
            transliterated_string_up_to_cursor = unicodedata.normalize(
                'NFKD', transliterated_string_up_to_cursor)
        transliterated_string_up_to_cursor = unicodedata.normalize(
            'NFC', transliterated_string_up_to_cursor)
        return len(transliterated_string_up_to_cursor)

    def append_candidate_to_lookup_table(
            self, phrase = '', user_freq = 0, comment = '',
            from_user_db = False, spell_checking = False):
        '''append candidate to lookup_table'''
        if not phrase:
            return
        phrase = unicodedata.normalize('NFC', phrase)
        attrs = IBus.AttrList ()
        if comment:
            phrase += ' ' + comment
        if DEBUG_LEVEL > 0:
            if spell_checking: # spell checking suggestion
                phrase = phrase + ' ✓'
                if  DEBUG_LEVEL > 1:
                    attrs.append(IBus.attr_foreground_new(
                        rgb(0xff, 0x00, 0x00), 0, len(phrase)))
            elif from_user_db:
                # This was found in the user database.  So it is
                # possible to delete it with a key binding or
                # mouse-click, if the user desires. Mark it
                # differently to show that it is deletable:
                phrase = phrase + ' ⭐'
                if  DEBUG_LEVEL > 1:
                    attrs.append(IBus.attr_foreground_new(
                        rgb(0xff, 0x7f, 0x00), 0, len(phrase)))
            else:
                # This is a (possibly accent insensitive) match in a
                # hunspell dictionary or an emoji matched by
                # EmojiMatcher.
                if  DEBUG_LEVEL > 1:
                    attrs.append(IBus.attr_foreground_new(
                        rgb(0x00, 0x00, 0x00), 0, len(phrase)))
        if DEBUG_LEVEL > 1:
            phrase += ' ' + str(user_freq)
            attrs.append(IBus.attr_foreground_new(
                rgb(0x00, 0xff, 0x00),
                len(phrase) - len(str(user_freq)),
                len(phrase)))
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
        if DEBUG_LEVEL > 1:
            sys.stderr.write("update_candidates() self._typed_string=%s\n"
                             %self._typed_string)
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)
        self._candidates = []
        phrase_frequencies = {}
        for ime in self._current_imes:
            if self._transliterated_strings[ime]:
                candidates = []
                prefix_length = 0
                prefix = ''
                stripped_transliterated_string = (
                    itb_util.lstrip_token(self._transliterated_strings[ime]))
                if ((len(stripped_transliterated_string)
                     >= self._min_char_complete)
                    or self._tab_enable):
                    prefix_length = (
                        len(self._transliterated_strings[ime])
                        - len(stripped_transliterated_string))
                    if prefix_length:
                        prefix = (
                            self._transliterated_strings[ime][0:prefix_length])
                    try:
                        candidates = self.db.select_words(
                            stripped_transliterated_string,
                            p_phrase=self._p_phrase,
                            pp_phrase=self._pp_phrase)
                    except:
                        import traceback
                        traceback.print_exc()
                if candidates and prefix:
                    candidates = [(prefix+x[0], x[1]) for x in candidates]
                for x in candidates:
                    if x[0] in phrase_frequencies:
                        phrase_frequencies[x[0]] = max(
                            phrase_frequencies[x[0]], x[1])
                    else:
                        phrase_frequencies[x[0]] = x[1]
        phrase_candidates = self.db.best_candidates(phrase_frequencies)
        if self._emoji_predictions:
            emoji_scores = {}
            for ime in self._current_imes:
                if (self._transliterated_strings[ime]
                    and ((len(self._transliterated_strings[ime])
                          >= self._min_char_complete)
                         or self._tab_enable)):
                    emoji_candidates = self.emoji_matcher.candidates(
                        self._transliterated_strings[ime])
                    for x in emoji_candidates:
                        if (x[0] not in emoji_scores
                            or x[2] > emoji_scores[x[0]][0]):
                            emoji_scores[x[0]] = (x[2], x[1])
            phrase_candidates_emoji_name = []
            for x in phrase_candidates:
                if x[0] in emoji_scores:
                    phrase_candidates_emoji_name.append((
                        x[0], x[1], emoji_scores[x[0]][1],
                        x[1] > 0, x[1] < 0))
                    # avoid duplicates in the lookup table:
                    del emoji_scores[x[0]]
                else:
                    phrase_candidates_emoji_name.append((
                        x[0], x[1], self.emoji_matcher.name(x[0]),
                        x[1] > 0, x[1] < 0))
            emoji_candidates = []
            for (key, value) in sorted(
                    emoji_scores.items(),
                    key=lambda x: (
                        - x[1][0],   # score
                        - len(x[0]), # length of emoji string
                        x[1][1]      # name of emoji
                    ))[:20]:
                emoji_candidates.append((key, value[0], value[1]))
            page_size = self._lookup_table.get_page_size()
            phrase_candidates_top = phrase_candidates_emoji_name[:page_size-1]
            phrase_candidates_rest = phrase_candidates_emoji_name[page_size-1:]
            emoji_candidates_top = emoji_candidates[:page_size]
            emoji_candidates_rest = emoji_candidates[page_size:]
            for x in phrase_candidates_top:
                self._candidates.append((x[0], x[1], x[2], x[3], x[4]))
            for x in emoji_candidates_top:
                self._candidates.append((x[0], x[1], x[2], False, False))
            for x in phrase_candidates_rest:
                self._candidates.append((x[0], x[1], x[2], x[3], x[4]))
            for x in emoji_candidates_rest:
                self._candidates.append((x[0], x[1], x[2], False, False))
        else:
            for x in phrase_candidates:
                self._candidates.append((x[0], x[1], '', x[1] > 0, x[1] < 0))
        for x in self._candidates:
            self.append_candidate_to_lookup_table(
                phrase = x[0], user_freq = x[1], comment = x[2],
                from_user_db = x[3], spell_checking = x[4])
        return True

    def arrow_down(self):
        '''Process Arrow Down Key Event
        Move Lookup Table cursor down'''
        if not self._lookup_table.cursor_visible:
            self._lookup_table.set_cursor_visible(True)
            return True
        elif self._lookup_table.cursor_down():
            return True
        return False

    def arrow_up(self):
        '''Process Arrow Up Key Event
        Move Lookup Table cursor up'''
        self._lookup_table.set_cursor_visible(True)
        if self._lookup_table.cursor_up():
            return True
        return False

    def page_down(self):
        '''Process Page Down Key Event
        Move Lookup Table page down'''
        self._lookup_table.set_cursor_visible(True)
        if self._lookup_table.page_down():
            return True
        return False

    def page_up(self):
        '''Process Page Up Key Event
        move Lookup Table page up'''
        self._lookup_table.set_cursor_visible(True)
        if self._lookup_table.page_up():
            return True
        return False

    def set_lookup_table_cursor_pos_in_current_page(self, index):
        '''Sets the cursor in the lookup table to index in the current page

        Returns True if successful, False if not.

        The topmost candidate has the index 0 and the label “1”.
        '''
        page_size = self._lookup_table.get_page_size()
        if index > page_size:
            return False
        page, dummy_pos_in_page = divmod(self._lookup_table.get_cursor_pos(),
                                         page_size)
        new_pos = page * page_size + index
        if new_pos > self._lookup_table.get_number_of_candidates():
            return False
        self._lookup_table.set_cursor_pos(new_pos)
        return True

    def get_string_from_lookup_table_cursor_pos(self):
        '''
        Get the candidate at the current cursor position in the lookup
        table.
        '''
        if not self._candidates:
            return ''
        index = self._lookup_table.get_cursor_pos()
        if index >= len (self._candidates):
            # the index given is out of range
            return ''
        return self._candidates[index][0]

    def get_string_from_lookup_table_current_page(self, index):
        '''
        Get the candidate at “index” in the currently visible
        page of the lookup table. The topmost candidate
        has the index 0 and has the label “1.”.
        '''
        if not self.set_lookup_table_cursor_pos_in_current_page(index):
            return ''
        return self.get_string_from_lookup_table_cursor_pos()

    def remove_candidate_from_user_database(self, index):
        '''Remove the candidate shown at index in the candidate list
        from the user database.

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

        So the user can always try to delete a phrase if he does not
        want the phrase to be suggested wich such a high priority, no
        matter whether it is a system phrase or a user defined phrase.
        '''
        if not self.set_lookup_table_cursor_pos_in_current_page(index):
            return False
        phrase = self.get_string_from_lookup_table_cursor_pos()
        if not phrase:
            return False
        self.db.remove_phrase(
            phrase=phrase, database='user_db', commit=True)
        return True

    def get_cursor_pos (self):
        '''get lookup table cursor position'''
        return self._lookup_table.get_cursor_pos()

    def get_lookup_table (self):
        '''Get lookup table'''
        return self._lookup_table

    def set_lookup_table (self, lookup_table):
        '''Set lookup table'''
        self._lookup_table = lookup_table

    def get_p_phrase(self):
        '''Get previous word'''
        return self._p_phrase

    def get_pp_phrase(self):
        '''Get word before previous word'''
        return self._pp_phrase

    def get_supported_imes(self):
        '''Get list of supported input methods

        It is important to return a copy, we do not want to change
        the private member variable directly.'''
        return self._supported_imes[:]

    def get_current_imes_max(self):
        '''Get maximum allowed number of current imes'''
        return self._current_imes_max

    def get_current_imes(self):
        '''Get current list of input methods

        It is important to return a copy, we do not want to change
        the private member variable directly.'''
        return self._current_imes[:]

    def set_current_imes(self, imes):
        '''Set current list of input methods'''
        if set(imes) != set(self._current_imes):
            # Input methods have been added or removed from the list
            # of current input methods. Initialize the
            # transliterators. If only the order of the input methods
            # has changed, initialising the transliterators is not
            # necessary (and neither is updating the transliterated
            # strings necessary).
            self._current_imes = imes
            self.init_transliterators()
        else:
            self._current_imes = imes

    def push_context(self, phrase):
        self._pp_phrase = self._p_phrase
        self._p_phrase = phrase

    def clear_context(self):
        self._pp_phrase = ''
        self._p_phrase = ''

########################
### Engine Class #####
####################
class tabengine (IBus.Engine):
    '''The IM Engine for Tables'''

    def __init__ (self, bus, obj_path, db ):
        global DEBUG_LEVEL
        try:
            DEBUG_LEVEL = int(os.getenv('IBUS_TYPING_BOOSTER_DEBUG_LEVEL'))
        except (TypeError, ValueError):
            DEBUG_LEVEL = int(0)
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "tabengine.__init__(bus=%s, obj_path=%s, db=%s)\n"
                % (bus, obj_path, db))
        super(tabengine, self).__init__(
            connection=bus.get_connection(), object_path=obj_path)
        self._input_purpose = 0
        self._has_input_purpose = False
        if hasattr(IBus, 'InputPurpose'):
            self._has_input_purpose = True
        self._lookup_table_is_invalid = False
        self._lookup_table_shows_related_candidates = False
        self._bus = bus
        self.db = db
        self._setup_pid = 0
        self._name = self.db.ime_properties.get('name')
        self._config_section = "engine/typing-booster/%s" % self._name
        self._config = self._bus.get_config ()
        self._config.connect('value-changed', self.__config_value_changed_cb)

        self._page_size = variant_to_value(self._config.get_value(
                self._config_section,
                'pagesize'))
        if self._page_size == None:
            self._page_size = 6 # reasonable default page size
        if self._page_size < 1:
            self._page_size = 1 # minimum page size supported
        if self._page_size > 9:
            self._page_size = 9 # maximum page size supported

        self._show_number_of_candidates = variant_to_value(
            self._config.get_value(
                self._config_section,
                'shownumberofcandidates'))
        if self._show_number_of_candidates == None:
            self._show_number_of_candidates = False

        self._use_digits_as_select_keys = variant_to_value(
            self._config.get_value(
                self._config_section,
                'usedigitsasselectkeys'))
        if self._use_digits_as_select_keys == None:
            self._use_digits_as_select_keys = True

        self._icon_dir = '%s%s%s%s' % (
            os.getenv('IBUS_HUNSPELL_TABLE_LOCATION'),
            os.path.sep, 'icons', os.path.sep)

        self._status = self.db.ime_properties.get(
            'status_prompt').encode('utf8')

        self.is_lookup_table_enabled_by_tab = False
        self._tab_enable = variant_to_value(self._config.get_value (
            self._config_section,
            "tabenable"))
        if self._tab_enable == None:
            self._tab_enable = False

        self._editor = editor(
            self._config,
            self.db,
            IBus.LookupTable.new(
                page_size = self._page_size,
                cursor_pos = 0,
                cursor_visible = False,
                round = True),
            tab_enable = self._tab_enable)

        self._remember_last_used_preedit_ime = False
        self._remember_last_used_preedit_ime = variant_to_value(
            self._config.get_value(
                self._config_section,
                "rememberlastusedpreeditime"))
        if self._remember_last_used_preedit_ime == None:
            self._remember_last_used_preedit_ime = False

        self._commit_happened_after_focus_in = False

        self._prop_dict = {}
        self.main_prop_list = []
        self.preedit_ime_menu = {}
        self.preedit_ime_properties = {}
        self.preedit_ime_sub_properties_prop_list = []
        self.update_preedit_ime_menu_dicts()
        self._setup_property = None
        self._init_properties()

        sys.stderr.write(
            '--- Initialized and ready for input: %s ---\n'
            %time.strftime('%Y-%m-%d: %H:%M:%S'))
        self.reset()

    def get_current_imes_max(self):
        '''Get maximum allowed number of current imes from editor'''
        return self._editor.get_current_imes_max()

    def get_current_imes(self):
        '''Get current list of input methods from editor'''
        return self._editor.get_current_imes()

    def set_current_imes(self, imes):
        '''Set current list of input methods in editor'''
        if imes == self.get_current_imes(): # nothing to do
            return
        if len(imes) > self.get_current_imes_max():
            sys.stderr.write(
                'Trying to set more than the allowed maximum of %s '
                %self.get_current_imes_max()
                + 'input methods.\n'
                + 'Trying to set: %s\n' %imes
                + 'Really setting: %s\n' %imes[:self.get_current_imes_max()])
            imes = imes[:self.get_current_imes_max()]
        if self._remember_last_used_preedit_ime:
            self._config.set_value(
                self._config_section,
                'inputmethod',
                GLib.Variant.new_string(','.join(imes)))
        self._editor.set_current_imes(imes)
        self.update_preedit_ime_menu_dicts()
        self._init_or_update_property_menu_preedit_ime(
            self.preedit_ime_menu, current_mode = 0)
        if not self._editor.is_empty():
            self._update_ui()

    def update_preedit_ime_menu_dicts(self):
        self.preedit_ime_properties = {}
        current_imes = self.get_current_imes()
        current_imes_max = self.get_current_imes_max()
        for i in range(0, current_imes_max):
            if i < len(current_imes):
                self.preedit_ime_properties[
                    'PreeditIme.' + str(i)
                ] = {'number': i,
                     'symbol': current_imes[i],
                     'label': current_imes[i],
                     'tooltip': _('Switch preedit input method to %(ime)s') %{
                         'ime': current_imes[i]}}
            else:
                self.preedit_ime_properties[
                    'PreeditIme.'+str(i)
                ] = {'number': i, 'symbol': '', 'label': '', 'tooltip': ''}
        self.preedit_ime_menu = {
            'key': 'PreeditIme',
            'label': _('Preedit input method'),
            'tooltip': _('Switch preedit input method'),
            'shortcut_hint': '(Ctrl+ArrowUp, Ctrl+ArrowDown)',
            'sub_properties': self.preedit_ime_properties}

    def _init_or_update_property_menu_preedit_ime(self, menu, current_mode=0):
        key = menu['key']
        sub_properties = menu['sub_properties']
        for prop in sub_properties:
            if sub_properties[prop]['number'] == int(current_mode):
                symbol = sub_properties[prop]['symbol']
                label = '%(label)s (%(symbol)s) %(shortcut_hint)s' % {
                    'label': menu['label'],
                    'symbol': symbol,
                    'shortcut_hint': menu['shortcut_hint']}
                tooltip = '%(tooltip)s\n%(shortcut_hint)s' % {
                    'tooltip': menu['tooltip'],
                    'shortcut_hint': menu['shortcut_hint']}
        if len(self.get_current_imes()) > 1:
            visible = True
        else:
            visible = False
        self._init_or_update_sub_properties_preedit_ime(
            sub_properties, current_mode=current_mode)
        if not key in self._prop_dict: # initialize property
            self._prop_dict[key] = IBus.Property(
                key = key,
                prop_type = IBus.PropType.MENU,
                label = IBus.Text.new_from_string(label),
                symbol = IBus.Text.new_from_string(symbol),
                tooltip = IBus.Text.new_from_string(tooltip),
                sensitive = visible,
                visible= visible,
                state = IBus.PropState.UNCHECKED,
                sub_props = self.preedit_ime_sub_properties_prop_list)
            self.main_prop_list.append(self._prop_dict[key])
        else:  # update the property
            self._prop_dict[key].set_label(
                IBus.Text.new_from_string(label))
            self._prop_dict[key].set_symbol(
                IBus.Text.new_from_string(symbol))
            self._prop_dict[key].set_tooltip(
                IBus.Text.new_from_string(tooltip))
            self._prop_dict[key].set_sensitive(visible)
            self._prop_dict[key].set_visible(visible)
            self.update_property(self._prop_dict[key]) # important!

    def _init_or_update_sub_properties_preedit_ime(
            self, modes, current_mode=0):
        if not self.preedit_ime_sub_properties_prop_list:
            update = False
            self.preedit_ime_sub_properties_prop_list = IBus.PropList()
        else:
            update = True
        number_of_current_imes = len(self._editor.get_current_imes())
        for mode in sorted(modes, key=lambda x: (modes[x]['number'])):
            if modes[mode]['number'] < number_of_current_imes:
                visible = True
            else:
                visible = False
            if modes[mode]['number'] == int(current_mode):
                state = IBus.PropState.CHECKED
            else:
                state = IBus.PropState.UNCHECKED
            label = modes[mode]['label']
            tooltip = modes[mode]['tooltip']
            if not update: # initialize property
                self._prop_dict[mode] = IBus.Property(
                    key = mode,
                    prop_type = IBus.PropType.RADIO,
                    label = IBus.Text.new_from_string(label),
                    tooltip = IBus.Text.new_from_string(tooltip),
                    sensitive = visible,
                    visible = visible,
                    state = state,
                    sub_props = None)
                self.preedit_ime_sub_properties_prop_list.append(
                    self._prop_dict[mode])
            else: # update property
                self._prop_dict[mode].set_label(
                    IBus.Text.new_from_string(label))
                self._prop_dict[mode].set_tooltip(
                    IBus.Text.new_from_string(tooltip))
                self._prop_dict[mode].set_sensitive(visible)
                self._prop_dict[mode].set_visible(visible)
                self.update_property(self._prop_dict[mode]) # important!

    def _init_properties(self):
        self._prop_dict = {}
        self.main_prop_list = IBus.PropList()

        self._init_or_update_property_menu_preedit_ime(
            self.preedit_ime_menu, current_mode = 0)

        self._setup_property = IBus.Property(
            key = 'setup',
            label = IBus.Text.new_from_string(_('Setup')),
            icon = 'gtk-preferences',
            tooltip = IBus.Text.new_from_string(
                _('Configure ibus-typing-booster “%(name)s”') %{
                    'name': self._name.replace('typing-booster:', '')}),
            sensitive = True,
            visible = True)
        self.main_prop_list.append(self._setup_property)
        self.register_properties(self.main_prop_list)

    def do_property_activate(
            self, ibus_property, prop_state = IBus.PropState.UNCHECKED):
        '''
        Handle clicks on properties
        '''
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "do_property_activate() property=%(p)s prop_state=%(ps)s\n"
                % {'p': property, 'ps': prop_state})
        if ibus_property == "setup":
            self._start_setup()
            return
        if prop_state != IBus.PropState.CHECKED:
            # If the mouse just hovered over a menu button and
            # no sub-menu entry was clicked, there is nothing to do:
            return
        if ibus_property.startswith(self.preedit_ime_menu['key']+'.'):
            number = self.preedit_ime_properties[ibus_property]['number']
            if number != 0:
                # If number 0 has been clicked, there is nothing to
                # do, the first one is already the preedit input
                # method
                imes = self.get_current_imes()
                self.set_current_imes(
                    [imes[number]] + imes[number+1:] + imes[:number] )
            return

    def _start_setup(self):
        if self._setup_pid != 0:
            pid, dummy_state = os.waitpid(self._setup_pid, os.P_NOWAIT)
            if pid != self._setup_pid:
                # If the last setup tool started from here is still
                # running the pid returned by the above os.waitpid()
                # is 0. In that case just return, don’t start a
                # second setup tool.
                return
            self._setup_pid = 0
        setup_cmd = os.path.join(
            os.getenv('IBUS_HUNSPELL_LIB_LOCATION'),
            'ibus-setup-typing-booster')
        config_file = self._name.replace('typing-booster:', '') + '.conf'
        self._setup_pid = os.spawnl(
            os.P_NOWAIT,
            setup_cmd,
            'ibus-setup-typing-booster',
            '--config-file %s' %config_file)

    def reset (self):
        self._editor.clear_input()
        self._update_ui ()

    def do_destroy(self):
        self.reset ()
        self.do_focus_out ()
        super(tabengine, self).destroy()

    def _update_preedit (self):
        '''Update Preedit String in UI'''
        # editor.get_caret() should also use NFC!
        _str = unicodedata.normalize(
            'NFC', self._editor.get_transliterated_strings()[
                self.get_current_imes()[0]])
        if _str == '':
            super(tabengine, self).update_preedit_text(
                IBus.Text.new_from_string(''), 0, False)
        else:
            attrs = IBus.AttrList()
            attrs.append(IBus.attr_underline_new(
                IBus.AttrUnderline.SINGLE, 0, len(_str)))
            text = IBus.Text.new_from_string(_str)
            i = 0
            while attrs.get(i) != None:
                attr = attrs.get(i)
                text.append_attribute(attr.get_attr_type(),
                                      attr.get_value(),
                                      attr.get_start_index(),
                                      attr.get_end_index())
                i += 1
            super(tabengine, self).update_preedit_text(
                text, self._editor.get_caret(), True)

    def _update_aux (self):
        '''Update Aux String in UI'''
        aux_string = ''
        if self._show_number_of_candidates:
            aux_string = '(%d / %d) ' % (
                self._editor.get_lookup_table().get_cursor_pos() + 1,
                self._editor.get_lookup_table().get_number_of_candidates())
        preedit_ime = self.get_current_imes()[0]
        if preedit_ime != 'NoIme':
            aux_string += preedit_ime + ' '
        if self._editor._emoji_predictions:
            aux_string += '☺ '
        # Colours do not work at the moment in the auxiliary text!
        # Needs fix in ibus.
        attrs = IBus.AttrList()
        attrs.append(IBus.attr_foreground_new(
            rgb(0x95, 0x15, 0xb5),
            0,
            len(aux_string)))
        if DEBUG_LEVEL > 0:
            context = (
                'Context: ' + self._editor.get_pp_phrase()
                + ' ' + self._editor.get_p_phrase())
            aux_string += context
            attrs.append(IBus.attr_foreground_new(
                rgb(0x00, 0xff, 0x00),
                len(aux_string)-len(context),
                len(aux_string)))
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
        if (self._editor.get_lookup_table().get_number_of_candidates() == 0
            or (self._tab_enable
                and not self.is_lookup_table_enabled_by_tab)
            or not aux_string):
            visible = False
        super(tabengine, self).update_auxiliary_text(text, visible)
        self._current_auxiliary_text = text

    def _update_lookup_table (self):
        '''Update Lookup Table in UI'''
        # Also make sure to hide lookup table if there are
        # no candidates to display. On f17, this makes no
        # difference but gnome-shell in f18 will display
        # an empty suggestion popup if the number of candidates
        # is zero!
        if (self._editor.is_empty()
            or self._editor.get_lookup_table().get_number_of_candidates() == 0
            or (self._tab_enable and not self.is_lookup_table_enabled_by_tab)):
            self.hide_lookup_table()
        else:
            self.update_lookup_table(self._editor.get_lookup_table(), True)

    def _update_lookup_table_and_aux(self):
        self._update_lookup_table()
        self._update_aux()
        self._lookup_table_is_invalid = False

    def _update_candidates_and_lookup_table_and_aux(self):
        self._editor.update_candidates()
        self._update_lookup_table_and_aux()

    def _update_ui(self):
        '''Update User Interface'''
        self._update_preedit()
        if self._editor.is_empty():
            # Hide lookup table again if preëdit became empty and
            # suggestions are only enabled by Tab key:
            self.is_lookup_table_enabled_by_tab = False
        if (self._editor.is_empty()
            or (self._tab_enable and not self.is_lookup_table_enabled_by_tab)):
            # If the lookup table would be hidden anyway, there is no
            # point in updating the candidates, save some time by making
            # sure the lookup table and the auxiliary text are really
            # hidden and return immediately:
            self.hide_lookup_table()
            self._current_auxiliary_text = IBus.Text.new_from_string('')
            super(tabengine, self).update_auxiliary_text(
                self._current_auxiliary_text, False)
            return
        self._lookup_table_shows_related_candidates = False
        if self._lookup_table_is_invalid:
            return
        self._lookup_table_is_invalid = True
        # Don’t show the lookup table if it is invalid anway
        self._editor.get_lookup_table().clear()
        self._editor.get_lookup_table().set_cursor_visible(False)
        self.hide_lookup_table()
        # Show an hourglass with moving sand in the auxiliary text to
        # indicate that the lookup table is being updated:
        super(tabengine, self).update_auxiliary_text(
            IBus.Text.new_from_string('⏳'), True)
        GLib.idle_add(self._update_candidates_and_lookup_table_and_aux)

    def _lookup_related_candidates(self):
        # We might end up here by typing a shortcut key like
        # AltGr+F12.  This should also work when suggestions are only
        # enabled by Tab and are currently disabled.  Typing such a
        # shortcut key explicitly requests looking up related
        # candidates, so it should have the same effect as Tab and
        # enable the lookup table:
        if (self._tab_enable and not self.is_lookup_table_enabled_by_tab):
            self.is_lookup_table_enabled_by_tab = True
        phrase  = ''
        if (self._editor.get_lookup_table().get_number_of_candidates()
            and  self._editor.get_lookup_table().cursor_visible):
            phrase = self._editor.get_string_from_lookup_table_cursor_pos()
        else:
            phrase  = self._editor.get_transliterated_strings()[
                self.get_current_imes()[0]]
        if not phrase:
            return
        # Hide lookup table and show an hourglass with moving sand in
        # the auxiliary text to indicate that the lookup table is
        # being updated. Don’t clear the lookup table here because we
        # might want to show it quickly again if nothing related is
        # found:
        if self._editor.get_lookup_table().get_number_of_candidates():
            self.hide_lookup_table()
        super(tabengine, self).update_auxiliary_text(
            IBus.Text.new_from_string('⏳'), True)
        related_candidates = []
        # Try to find similar emoji even if emoji predictions are
        # turned off.  Even when they are turned off, an emoji might
        # show up in the candidate list because it was found in the
        # user database. But when emoji predictions are turned off,
        # it is possible that they never been turned on in this session
        # and then the emoji matcher has not been initialized. Or,
        # the languages have been changed while emoji matching was off.
        # So make sure that the emoji matcher is available for the
        # correct list of languages before searching for similar
        # emoji:
        if (not self._editor.emoji_matcher
            or
            self._editor.emoji_matcher.get_languages()
            != self._editor._dictionary_names):
            self._editor.emoji_matcher = itb_emoji.EmojiMatcher(
                languages = self._editor._dictionary_names)
        related_candidates = self._editor.emoji_matcher.similar(phrase)
        try:
            import itb_nltk
            for x in itb_nltk.synonyms(phrase, keep_original = False):
                related_candidates.append((x, '[synonym]', 0))
            for x in itb_nltk.hypernyms(phrase, keep_original = False):
                related_candidates.append((x, '[hypernym]', 0))
            for x in itb_nltk.hyponyms(phrase, keep_original = False):
                related_candidates.append((x, '[hyponym]', 0))
        except (ImportError, LookupError):
            pass
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                '_lookup_related_candidates():'
                +  ' related_candidates of “%s” = %s\n'
                %(phrase, related_candidates))
        if not related_candidates:
            # Nothing related found, show the original lookup table
            # and original auxiliary text again:
            if self._current_auxiliary_text:
                super(tabengine, self).update_auxiliary_text(
                    self._current_auxiliary_text, True)
            else:
                super(tabengine, self).update_auxiliary_text(
                    IBus.Text.new_from_string(''), False)
            if self._editor.get_lookup_table().get_number_of_candidates():
                self.update_lookup_table(self._editor.get_lookup_table(), True)
            return
        self._editor._candidates = []
        self._editor.get_lookup_table().clear()
        self._editor.get_lookup_table().set_cursor_visible(False)
        for x in related_candidates:
            self._editor._candidates.append((x[0], x[2], x[1]))
            self._editor.append_candidate_to_lookup_table(
                phrase = x[0], user_freq = x[2], comment = x[1])
        self._update_lookup_table_and_aux()
        self._lookup_table_shows_related_candidates = True

    def has_transliteration(self, msymbol_list):
        transliterators = self._editor.get_transliterators()
        for ime in self.get_current_imes():
            if transliterators[ime].transliterate(
                    msymbol_list) != ''.join(msymbol_list):
                if DEBUG_LEVEL > 1:
                    sys.stderr.write(
                        "has_transliteration(%s) == True\n" %msymbol_list)
                return True
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "has_transliteration(%s) == False\n" %msymbol_list)
        return False

    def commit_string (self, commit_phrase, input_phrase = ''):
        # If the suggestions are only enabled by Tab key, i.e. the
        # lookup table is not shown until Tab has been typed, hide
        # the lookup table again after each commit. That means
        # that after each commit, when typing continues the
        # lookup table is first hidden again and one has to type
        # Tab again to show it.
        self.is_lookup_table_enabled_by_tab = False
        if not input_phrase:
            input_phrase = self._editor.get_transliterated_strings()[
                self.get_current_imes()[0]]
        # commit always in NFC:
        commit_phrase = unicodedata.normalize('NFC', commit_phrase)
        super(tabengine, self).commit_text(
            IBus.Text.new_from_string(commit_phrase))
        self._editor.clear_input()
        self._update_ui ()
        self._commit_happened_after_focus_in = True
        if self.client_capabilities & IBus.Capabilite.SURROUNDING_TEXT:
            # If a character ending a sentence is committed (possibly
            # followed by whitespace) remove trailing white space
            # before the committed string. For example if
            # commit_phrase is “!”, and the context before is “word ”,
            # make the result “word!”.  And if the commit_phrase is “!
            # ” and the context before is “word ” make the result
            # “word! ”.
            pattern_sentence_end = re.compile(r'^[.,;:?!][\s]*$')
            if pattern_sentence_end.search(commit_phrase):
                surrounding_text = self.get_surrounding_text()
                text = surrounding_text[0].get_text()
                cursor_pos = surrounding_text[1]
                anchor_pos = surrounding_text[2]
                if DEBUG_LEVEL > 1:
                    sys.stderr.write(
                        'Removing whitespace before sentence end char. '
                        + 'surrounding_text = '
                        + '[text = "%s", cursor_pos = %s, anchor_pos = %s]'
                        %(text, cursor_pos, anchor_pos) + '\n')
                # The commit_phrase is *not* yet in the surrounding text,
                # it will show up there only when the next key event is
                # processed:
                pattern = re.compile(r'(?P<white_space>[\s]+)$')
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
                    if DEBUG_LEVEL > 1:
                        surrounding_text = self.get_surrounding_text()
                        text = surrounding_text[0].get_text()
                        cursor_pos = surrounding_text[1]
                        anchor_pos = surrounding_text[2]
                        sys.stderr.write(
                            'Removed whitespace before sentence end char. '
                            + 'surrounding_text = '
                            + '[text = "%s", cursor_pos = %s, anchor_pos = %s]'
                            %(text, cursor_pos, anchor_pos) + '\n')
        stripped_input_phrase = itb_util.strip_token(input_phrase)
        stripped_commit_phrase = itb_util.strip_token(commit_phrase)
        self.db.check_phrase_and_update_frequency(
            input_phrase=stripped_input_phrase,
            phrase=stripped_commit_phrase,
            p_phrase=self._editor.get_p_phrase(),
            pp_phrase=self._editor.get_pp_phrase())
        self._editor.push_context(stripped_commit_phrase)

    def get_context(self):
        if not (self.client_capabilities & IBus.Capabilite.SURROUNDING_TEXT):
            # If getting the surrounding text is not supported, leave
            # the context as it is, i.e. rely on remembering what was
            # typed last.
            return
        surrounding_text = self.get_surrounding_text()
        text = surrounding_text[0].get_text()
        cursor_pos = surrounding_text[1]
        dummy_anchor_pos = surrounding_text[2]
        if not surrounding_text:
            return
        if not self._commit_happened_after_focus_in:
            # Before the first commit or cursor movement, the
            # surrounding text is probably from the previously
            # focused window (bug!), don’t use it.
            return
        tokens = ([
            itb_util.strip_token(x)
            for x in itb_util.tokenize(text[:cursor_pos])])
        if len(tokens):
            self._editor._p_phrase = tokens[-1]
        if len(tokens) > 1:
            self._editor._pp_phrase = tokens[-2]

    def _toggle_emoji_predictions(self):
        '''Toggles whether emoji predictions are shown or not

        As this is saved to dconf, this setting is rememembered, i.e.
        it has the same effect as changing this setting with the setup
        tool.

        '''
        emoji_predictions = not variant_to_value(self._config.get_value(
            self._config_section,
            'emojipredictions'))
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "_process_key_event() set emoji predictions to %s\n"
                %emoji_predictions)
        self._config.set_value(
            self._config_section,
            'emojipredictions',
            GLib.Variant.new_boolean(emoji_predictions))

    def do_candidate_clicked(self, index, button, state):
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                'do_candidate_clicked() index = %s button = %s state = %s\n'
                %(index, button, state))
        if not self._editor.set_lookup_table_cursor_pos_in_current_page(index):
            return
        self._editor._lookup_table.set_cursor_visible(True)
        if button == 1 and (state & IBus.ModifierType.CONTROL_MASK):
            self._editor.remove_candidate_from_user_database(index)
            self._update_ui()
            return
        if button == 1:
            phrase = self._editor.get_string_from_lookup_table_cursor_pos()
            if phrase:
                self.commit_string(phrase + ' ')
            return
        if button == 3 and (state & IBus.ModifierType.CONTROL_MASK):
            self._toggle_emoji_predictions()
            return
        if button == 3:
            self._lookup_related_candidates()
            return

    def do_process_key_event(self, keyval, keycode, state):
        '''Process Key Events
        Key Events include Key Press and Key Release,
        modifier means Key Pressed
        '''
        if (self._has_input_purpose
            and self._input_purpose
            in [IBus.InputPurpose.PASSWORD, IBus.InputPurpose.PIN]):
            return False
        key = KeyEvent(keyval, keycode, state)
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "process_key_event() "
                "KeyEvent object: %s" % key)

        result = self._process_key_event (key)
        return result

    def _process_key_event (self, key):
        '''Internal method to process key event

        Returns True if the key event has been completely handled by
        ibus-typing-booster and should not be passed through anymore.
        Returns False if the key event has not been handled completely
        and is passed through.

        '''
        # Ignore key release events
        if key.state & IBus.ModifierType.RELEASE_MASK:
            return False

        if self._editor.is_empty ():
            if DEBUG_LEVEL > 1:
                sys.stderr.write(
                    "_process_key_event() self._editor.is_empty(): "
                    "KeyEvent object: %s\n" % key)
            # This is the first character typed since the last commit
            # there is nothing in the preëdit yet.
            if key.val < 32:
                # If the first character of a new word is a control
                # character, return False to pass the character through as is,
                # it makes no sense trying to complete something
                # starting with a control character:
                return False
            if key.val == IBus.KEY_space and not key.mod5:
                # if the first character is a space, just pass it through
                # it makes not sense trying to complete (“not key.mod5” is
                # checked here because AltGr+Space is the key binding to
                # insert a literal space into the preëdit):
                return False
            if key.val in (IBus.KEY_BackSpace,):
                # When the end of a word is reached again by typing backspace,
                # try to get that word back into preedit:
                if not (self.client_capabilities
                        & IBus.Capabilite.SURROUNDING_TEXT):
                    return False
                surrounding_text = self.get_surrounding_text()
                text = surrounding_text[0].get_text()
                cursor_pos = surrounding_text[1]
                dummy_anchor_pos = surrounding_text[2]
                if not surrounding_text:
                    return False
                if not self._commit_happened_after_focus_in:
                    # Before the first commit or cursor movement, the
                    # surrounding text is probably from the previously
                    # focused window (bug!), don’t use it.
                    return False
                pattern = re.compile(
                    r'(^|.*[\s]+)(?P<token>[\S]+)[\s]$')
                match = pattern.match(text[:cursor_pos])
                if not match:
                    return False
                # The pattern has matched, i.e. left of the cursor is
                # a single whitespace and left of that a token was
                # found.  Delete the whitespace and the token from the
                # application, get the context to the left of the
                # token, put the token into the preedit again and
                # update the candidates. Do not pass the backspace
                # back to the application because the whitespace has
                # already been deleted.
                token = match.group('token')
                self.delete_surrounding_text(-1-len(token), 1+len(token))
                self.get_context()
                self._editor.insert_string_at_cursor(list(token))
                self._update_ui()
                return True
            if key.val >= 32 and not key.control:
                # If the first character typed is a character which is
                # very unlikely to be part of a word
                # (e.g. punctuation, a symbol, ..), we might want to
                # avoid completion and commit something immediately:
                if (len(key.msymbol) == 1
                    and unicodedata.category(key.msymbol)
                    in itb_util.CATEGORIES_TO_TRIGGER_IMMEDIATE_COMMIT):
                    if self.get_current_imes()[0] == 'NoIme':
                        # Do not just pass the character through,
                        # commit it properly.  For example if it is a
                        # “.” we might want to remove whitespace
                        # between the “.” and the previous word and this is
                        # done in commit_string().
                        self.commit_string(
                            key.msymbol, input_phrase = key.msymbol)
                        return True
                    # If transliteration is used, we may need to
                    # handle a punctuation or symbol character. For
                    # example, “.c” is transliterated to “ċ” in
                    # the “t-latn-pre” transliteration method,
                    # therefore we cannot just pass it through. Just
                    # add it to the input so far and see what comes
                    # next:
                    self._editor.insert_string_at_cursor([key.msymbol])
                    self._update_ui()
                    return True
                if (self._use_digits_as_select_keys
                    and key.msymbol
                    in ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9')):
                    # If digits are used as keys to select candidates
                    # it is not possibly to type them while the preëdit
                    # is non-empty and candidates are displayed.
                    # In that case we have to make it possible to
                    # type digits here where the preëdit is still empty.
                    # If digits are not used to select candidates, they
                    # can be treated just like any other input keys.
                    if self.get_current_imes()[0] == 'NoIme':
                        # If a digit has been typed and no transliteration
                        # is used, we can pass it through
                        return False
                    # If a digit has been typed and we use
                    # transliteration, we may want to convert it to
                    # native digits. For example, with mr-inscript we
                    # want “3” to be converted to “३”. So we try
                    # to transliterate and commit the result:
                    transliterated_digit = self._editor.get_transliterators()[
                        self.get_current_imes()[0]
                    ].transliterate([key.msymbol])
                    self.commit_string(
                        transliterated_digit,
                        input_phrase=transliterated_digit)
                    return True

        if key.val == IBus.KEY_Escape:
            if self._editor.is_empty():
                return False
            if self._editor.get_lookup_table().cursor_visible:
                # A candidate is selected in the lookup table.
                # Deselect it and show the first page of the candidate
                # list:
                self._editor.get_lookup_table().set_cursor_visible(False)
                self._editor.get_lookup_table().set_cursor_pos(0)
                self._update_lookup_table_and_aux()
                return True
            if self._lookup_table_shows_related_candidates:
                # Force an update to the original lookup table:
                self._update_ui()
            else:
                self.reset()
                self._update_ui()
            return True

        if key.val in (IBus.KEY_Down, IBus.KEY_KP_Down) and key.control:
            # remove the first ime from the list and append it to the end.
            imes = self.get_current_imes()
            self.set_current_imes(imes[1:] + imes[:1])
            return True

        if key.val in (IBus.KEY_Up, IBus.KEY_KP_Up) and key.control:
            # remove the last ime in the list and add it in front:
            imes = self.get_current_imes()
            self.set_current_imes(imes[-1:] + imes[:-1])
            return True

        if key.val in (IBus.KEY_Down, IBus.KEY_KP_Down):
            if self._editor.is_empty():
                return False
            res = self._editor.arrow_down()
            self._update_lookup_table_and_aux()
            return res

        if key.val in (IBus.KEY_Up, IBus.KEY_KP_Up):
            if self._editor.is_empty():
                return False
            res = self._editor.arrow_up()
            self._update_lookup_table_and_aux()
            return res

        if (key.val in [IBus.KEY_Page_Down, IBus.KEY_KP_Page_Down]
            and self._editor.get_lookup_table().get_number_of_candidates()):
            res = self._editor.page_down()
            self._update_lookup_table_and_aux()
            return res

        if (key.val in [IBus.KEY_Page_Up, IBus.KEY_KP_Page_Up]
            and self._editor.get_lookup_table().get_number_of_candidates()):
            res = self._editor.page_up ()
            self._update_lookup_table_and_aux()
            return res

        if key.val == IBus.KEY_BackSpace and key.control:
            if self._editor.is_empty():
                return False
            if self._editor.get_typed_string_cursor() > 0:
                self.is_lookup_table_enabled_by_tab = False
            self._editor.remove_string_before_cursor()
            self._update_ui()
            return True

        if key.val == IBus.KEY_BackSpace:
            if self._editor.is_empty():
                return False
            if self._editor.get_typed_string_cursor() > 0:
                self.is_lookup_table_enabled_by_tab = False
            self._editor.remove_character_before_cursor()
            self._update_ui()
            return True

        if key.val == IBus.KEY_Delete and key.control:
            if self._editor.is_empty():
                return False
            if (self._editor.get_typed_string_cursor()
                < len(self._editor.get_typed_string())):
                self.is_lookup_table_enabled_by_tab = False
            self._editor.remove_string_after_cursor()
            self._update_ui()
            return True

        if key.val == IBus.KEY_Delete:
            if self._editor.is_empty():
                return False
            if (self._editor.get_typed_string_cursor()
                < len(self._editor.get_typed_string())):
                self.is_lookup_table_enabled_by_tab = False
            self._editor.remove_character_after_cursor()
            self._update_ui()
            return True

        # Select a candidate to commit or remove:
        if (self._editor.get_lookup_table().get_number_of_candidates()
            and not key.mod1 and not key.mod5):
            # key.mod1 (= Alt) and key.mod5 (= AltGr) should not be set
            # here because:
            #
            # - in case of the digits these are used for input, not to select
            #   (e.g. mr-inscript2 transliterates AltGr-4 to “₹”)
            #
            # - in case of the F1-F9 keys I want to reserve the Alt and AltGr
            #   modifiers for possible future extensions.
            index = -1
            if self._use_digits_as_select_keys:
                if key.val >= IBus.KEY_1 and key.val <= IBus.KEY_9:
                    index = key.val - IBus.KEY_1
                if key.val >= IBus.KEY_KP_1 and key.val <= IBus.KEY_KP_9:
                    index = key.val - IBus.KEY_KP_1
            if key.val >= IBus.KEY_F1 and key.val <= IBus.KEY_F9:
                index = key.val - IBus.KEY_F1
            if index >= 0 and index < self._page_size:
                if key.control:
                    # Remove the candidate from the user database
                    res = self._editor.remove_candidate_from_user_database(
                        index)
                    self._update_ui()
                    return res
                else:
                    # Commit a candidate:
                    phrase = (
                        self._editor.get_string_from_lookup_table_current_page(
                            index))
                    if phrase:
                        self.commit_string(phrase + ' ')
                    return True

        if (key.val == IBus.KEY_F6 and key.mod5): # AltGr+F6
            self._toggle_emoji_predictions()
            return True

        if (key.val == IBus.KEY_F12 and key.mod5 # AltGr+F12
            and not self._editor.is_empty()):
            self._lookup_related_candidates()
            return True

        if (key.val == IBus.KEY_F10 and key.mod5): # AltGr+F10
            self._start_setup()
            return True

        if (key.val == IBus.KEY_Tab
            and self._tab_enable
            and not self.is_lookup_table_enabled_by_tab
            and not self._editor.is_empty()):
            self.is_lookup_table_enabled_by_tab = True
            # update the ui here to see the effect immediately
            # do not wait for the next keypress:
            self._update_ui()
            return True

        # These keys may trigger a commit:
        if (key.msymbol not in ('G- ',)
            and (key.val in (IBus.KEY_space, IBus.KEY_Tab,
                             IBus.KEY_Return, IBus.KEY_KP_Enter,
                             IBus.KEY_Right, IBus.KEY_KP_Right,
                             IBus.KEY_Left, IBus.KEY_KP_Left)
                 or (len(key.msymbol) == 3
                     and key.msymbol[:2] in ('A-', 'C-', 'G-')
                     and not self.has_transliteration([key.msymbol])))):
                # See:
                # https://bugzilla.redhat.com/show_bug.cgi?id=1351748
                # If the user types a modifier key combination, it
                # might have a transliteration in some input methods.
                # For example, AltGr-4 (key.msymbol = 'G-4')
                # transliterates to ₹ when the “hi-inscript2” input
                # method is used.  But trying to handle all modifier
                # key combinations as input is not nice because it
                # prevents the use of such key combinations for other
                # purposes.  C-c is usually used for for copying, C-v
                # for pasting for example. If the user has typed a
                # modifier key combination, check whether any of the
                # current input methods actually transliterates it to
                # something. If none of the current input methods uses
                # it, the key combination can be passed through to be
                # used for its original purpose.  If the preëdit is
                # non empty, commit the preëdit first before passing
                # the modifier key combination through. (Passing
                # something like C-a through without committing the
                # preëdit would be quite confusing, C-a usually goes
                # to the beginning of the current line, leaving the
                # preëdit open while moving would be strange).
                #
                # 'G- ' (AltGr-Space) is prevented from triggering
                # a commit here, because it is used to enter spaces
                # into the preëdit, if possible.
            if self._editor.is_empty():
                return False
            if (key.val in (IBus.KEY_Right, IBus.KEY_KP_Right)
                and (self._editor.get_typed_string_cursor()
                     < len(self._editor.get_typed_string()))):
                if key.control:
                    # Move cursor to the end of the typed string
                    self._editor.set_typed_string_cursor(
                        len(self._editor.get_typed_string()))
                else:
                    self._editor.set_typed_string_cursor(
                        self._editor.get_typed_string_cursor() + 1)
                self._update_preedit()
                self._update_lookup_table_and_aux()
                return True
            if (key.val in (IBus.KEY_Left, IBus.KEY_KP_Left)
                and self._editor.get_typed_string_cursor() > 0):
                if key.control:
                    # Move cursor to the beginning of the typed string
                    self._editor.set_typed_string_cursor(0)
                else:
                    self._editor.set_typed_string_cursor(
                        self._editor.get_typed_string_cursor() - 1)
                self._update_preedit()
                self._update_lookup_table_and_aux()
                return True
            # This key does not only a cursor movement in the preëdit,
            # it really triggers a commit.
            if DEBUG_LEVEL > 1:
                sys.stderr.write('_process_key_event() commit triggered.\n')
            # We need to transliterate
            # the preëdit again here, because adding the commit key to
            # the input might influence the transliteration. For example
            # When using hi-itrans, “. ” translates to “। ”
            # (See: https://bugzilla.redhat.com/show_bug.cgi?id=1353672)
            input_phrase = self._editor.get_transliterators()[
                self.get_current_imes()[0]].transliterate(
                    self._editor.get_typed_string() + [key.msymbol])
            # If the transliteration now ends with the commit key, cut
            # it off because the commit key is passed to the
            # application later anyway and we do not want to pass it
            # twice:
            if len(key.msymbol) and input_phrase.endswith(key.msymbol):
                input_phrase = input_phrase[:-len(key.msymbol)]
            if not input_phrase:
                return False
            if not self._editor.get_lookup_table().get_number_of_candidates():
                self.commit_string(input_phrase, input_phrase = input_phrase)
                # See comment below why forward_key_event() and “return True”
                # is used here instead of “return False” (Does not work in Qt
                # or X11 applications when using “return False”)
                self.forward_key_event(key.val, key.code, key.state)
                return True
            phrase = self._editor.get_string_from_lookup_table_cursor_pos()
            if not phrase:
                return False
            if self._editor.get_lookup_table().cursor_visible:
                # something is selected in the lookup table, commit
                # the selected phrase
                commit_string = phrase
            else:
                # nothing is selected in the lookup table, commit the
                # input_phrase
                commit_string = input_phrase
            self.commit_string(commit_string, input_phrase = input_phrase)
            if key.val in (IBus.KEY_Left, IBus.KEY_KP_Left):
                # After committing, the cursor is at the right side of
                # the committed string. When the string has been
                # committed because of arrow-left or
                # control-arrow-left, the cursor has to be moved to
                # the left side of the string. This should be done in
                # a way which works even when surrounding text is not
                # supported. We can do it by forwarding as many
                # arrow-left events to the application as the
                # committed string has characters. Because it might
                # have been control-arrow-left, we need to clear the
                # CONTROL_MASK:
                for dummy_char in commit_string:
                    self.forward_key_event(
                        key.val, key.code,
                        key.state & ~IBus.ModifierType.CONTROL_MASK)
            # Forward the key event which triggered the commit here
            # and return True instead of trying to pass that key event
            # to the application by returning False. Doing it by
            # returning false works correctly in GTK applications but
            # not in Qt or X11 applications. When “return False” is
            # used, the key event which triggered the commit here
            # arrives in Qt or X11 *before* the committed
            # string. I.e. when typing “word ” the space which
            # triggered the commit gets to application first and the
            # applications receives “ word”.
            # See: https://bugzilla.redhat.com/show_bug.cgi?id=1291238
            self.forward_key_event(key.val, key.code, key.state)
            return True

        if key.unicode:
            # If the suggestions are only enabled by Tab key, i.e. the
            # lookup table is not shown until Tab has been typed, hide
            # the lookup table again when characters are added to the
            # preëdit:
            self.is_lookup_table_enabled_by_tab = False
            if self._editor.is_empty():
                # first key typed, we will try to complete something now
                # get the context if possible
                self.get_context()
            if (key.msymbol in ('G- ',)
                and not self.has_transliteration([key.msymbol])):
                self._editor.insert_string_at_cursor([' '])
            else:
                self._editor.insert_string_at_cursor([key.msymbol])
            if (len(key.msymbol) == 1
                and unicodedata.category(key.msymbol)
                in itb_util.CATEGORIES_TO_TRIGGER_IMMEDIATE_COMMIT):
                input_phrase = (
                    self._editor.get_transliterated_strings()[
                        self.get_current_imes()[0]])
                if (input_phrase
                    and input_phrase[-1] == key.msymbol
                    and self.get_current_imes()[0] == 'NoIme'):
                    self.commit_string(
                        input_phrase + ' ', input_phrase = input_phrase)
            self._update_ui()
            return True

        # What kind of key was this??
        #
        # The unicode character for this key is apparently the empty
        # string.  And apparently it was not handled as a select key
        # or other special key either.  So whatever this was, we
        # cannot handle it, just pass it through to the application by
        # returning “False”.
        return False

    def do_focus_in(self):
        self.register_properties(self.main_prop_list)
        self._editor.clear_context()
        self._commit_happened_after_focus_in = False
        self._update_ui()

    def do_focus_out(self):
        if self._has_input_purpose:
            self._input_purpose = 0
        self._editor.clear_context()
        self.reset()
        return

    def do_set_content_type(self, purpose, dummy_hints):
        if self._has_input_purpose:
            self._input_purpose = purpose

    def do_enable (self):
        # Tell the input-context that the engine will utilize
        # surrounding-text:
        self.get_surrounding_text()
        self.do_focus_in()

    def do_disable (self):
        self.reset()

    def do_page_up (self):
        if self._editor.page_up ():
            self._update_lookup_table_and_aux()
            return True
        return True

    def do_page_down (self):
        if self._editor.page_down ():
            self._update_lookup_table_and_aux()
            return True
        return False

    def config_section_normalize(self, section):
        '''
        This function replaces _: with - in the dconf
        section and converts to lower case to make
        the comparison of the dconf sections work correctly.
        I avoid using .lower() here because it is locale dependent,
        when using .lower() this would not achieve the desired
        effect of comparing the dconf sections case insentively
        in some locales, it would fail for example if Turkish
        locale (tr_TR.UTF-8) is set.
        '''
        return re.sub(r'[_:]', r'-', section).translate(
            ''.maketrans(
                string.ascii_uppercase,
                string.ascii_lowercase))

    def __config_value_changed_cb(self, config, section, name, value):
        if (self.config_section_normalize(self._config_section)
            != self.config_section_normalize(section)):
            return
        print("config value %(n)s for engine %(en)s changed"
              %{'n': name, 'en': self._name})
        value = variant_to_value(value)
        if name == "emojipredictions":
            if value == 1:
                self._editor._emoji_predictions = True
                if (not self._editor.emoji_matcher
                    or
                    self._editor.emoji_matcher.get_languages()
                    != self._editor._dictionary_names):
                    self._editor.emoji_matcher = itb_emoji.EmojiMatcher(
                        languages = self._editor._dictionary_names)
            else:
                self._editor._emoji_predictions = False
            self._update_ui()
            return
        if name == "tabenable":
            if value == 1:
                self._tab_enable = True
                self._editor._tab_enable = True
            else:
                self._tab_enable = False
                self._editor._tab_enable = False
            return
        if name == "rememberlastusedpreeditime":
            if value == 1:
                self._remember_last_used_preedit_ime = True
            else:
                self._remember_last_used_preedit_ime = False
            return
        if name == "pagesize":
            if value >= 1 and value <= 9:
                self._page_size = value
                self._editor.set_lookup_table(
                    IBus.LookupTable.new(
                        page_size = self._page_size,
                        cursor_pos = 0,
                        cursor_visible = False,
                        round = True))
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
        if name == "usedigitsasselectkeys":
            if value == True:
                self._use_digits_as_select_keys = True
            else:
                self._use_digits_as_select_keys = False
            self.reset()
            return
        if name == "inputmethod":
            imes = [x.strip() for x in value.split(',')]
            self.set_current_imes(imes)
            return
        if name == "dictionary":
            self._editor._dictionary_names = [
                x.strip() for x in value.split(',')]
            self.db.hunspell_obj.set_dictionary_names(
                self._editor._dictionary_names)
            if self._editor._emoji_predictions:
                if (not self._editor.emoji_matcher
                    or
                    self._editor.emoji_matcher.get_languages()
                    != self._editor._dictionary_names):
                    self._editor.emoji_matcher = itb_emoji.EmojiMatcher(
                        languages=self._editor._dictionary_names)
            if not self._editor.is_empty():
                self._update_ui()
            return
        if name == "adddirectinput":
            imes = self.get_current_imes()
            dictionary_names = self.db.hunspell_obj.get_dictionary_names()
            self._editor._add_direct_input = value
            if value == True:
                if 'NoIme' not in imes:
                    imes.append('NoIme')
                if 'en_GB' not in dictionary_names:
                    dictionary_names.append('en_GB')
            else:
                imes = [x for x in imes if x != 'NoIme']
                if not imes:
                    imes = ['NoIme']
                # always keep the first dictionary, i.e. always keep
                # the original one from the config file
                dictionary_names = (
                    [dictionary_names[0]]
                    + [x for x in dictionary_names[1:] if x != 'en_GB'])
            self.db.hunspell_obj.set_dictionary_names(dictionary_names)
            self._editor._dictionary_names = dictionary_names
            self._config.set_value(
                self._config_section,
                'dictionary',
                GLib.Variant.new_string(','.join(dictionary_names)))
            self.set_current_imes(imes)
            self._config.set_value(
                self._config_section,
                'inputmethod',
                GLib.Variant.new_string(','.join(imes)))
            return
        if name == "dictionaryinstalltimestamp":
            # A dictionary has been updated or installed,
            # (re)load all dictionaries:
            print("Reloading dictionaries ...")
            self.db.hunspell_obj.init_dictionaries()
            self.reset()
            return
