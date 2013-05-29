# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 2011-2012 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012 Mike FABIAN <mfabian@redhat.com>
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
import keysym2ucs
from keysym2ucs import keysym2ucs
from keysym2ucs import keysym2unichr
import re
from gi.repository import IBus
from gi.repository import GLib

try:
    from gi.repository import Translit
    Transliterator = Translit.Transliterator
except ImportError:
    # Load libtranslit through ctypes, instead of gi. Maybe the code
    # below could be removed once ibus-table switches to pygobject3.
    import ctypes

    class Transliterator(object):
        __libtranslit = ctypes.CDLL("libtranslit.so.0",
                                    mode=ctypes.RTLD_GLOBAL)

        __get = __libtranslit.translit_transliterator_get
        __get.argtypes = [ctypes.c_char_p,
                          ctypes.c_char_p]
        __get.restype = ctypes.c_void_p

        __transliterate = __libtranslit.translit_transliterator_transliterate
        __transliterate.argtypes = [ctypes.c_void_p,
                                    ctypes.c_char_p,
                                    ctypes.c_void_p]
        __transliterate.restype = ctypes.c_char_p

        def __init__(self, trans):
            self.__trans = trans

        @staticmethod
        def get(backend, name):
            return Transliterator(Transliterator.__get(backend, name))

        def transliterate(self, _input):
            endpos = ctypes.c_ulong()
            # _input needs to be in UTF-8, if we get Python’s Unicode
            # type here, convert to UTF-8 first:
            if type(_input) == type(u''):
                _input = _input.encode('utf8')
            # the return value “output” is also UTF-8 encoded:
            output = Transliterator.__transliterate(self.__trans,
                                                    _input,
                                                    ctypes.byref(endpos))
            return (output, endpos.value)
except:
   # print "Please install Translit library to use m17n input methods"
    pass


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
        self._chars = []
        #self._t_chars: hold total input for table mode for input check
        self._t_chars = []
        # self._tabkey_list: hold tab_key objects transform from user input chars
        self._tabkey_list = []
        self._tabkey_list_when_update_candidates_was_last_called = []
        # self._strings: hold preedit strings
        self._strings = []
        # self._cursor: the caret position in preedit phrases
        self._cursor = [0,0]
        # self._candidates: hold candidates selected from database and hunspell
        self._candidates = []
        self._lookup_table = IBus.LookupTable.new(
            page_size=tabengine._page_size,
            cursor_pos=0,
            cursor_visible=False,
            round=True)
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)

        # self._caret: caret position in lookup_table
        self._caret = 0

        self._typed_chars = []
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

    def clear (self):
        '''Remove data holded'''
        self.clear_input()
        self._t_chars = []
        self._strings = []
        self._cursor = [0,0]

    def is_empty (self):
        return len(self._t_chars) == 0

    def clear_input (self):
        '''
        Remove input characters held for Table mode,
        '''
        self._chars = []
        self._tabkey_list = []
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)
        self._candidates = []
        self._typed_chars = []

    def add_input (self,c):
        '''add input character'''
        self._typed_chars.append(c)
        self._typed_chars = list(unicodedata.normalize('NFC', ''.join(self._typed_chars)))
        if self.trans_m17n_mode:
            trans_chars = self.trans.transliterate(''.join(self._typed_chars))[0].decode('utf8')
        else:
            trans_chars = ''.join(self._typed_chars)

        self._chars = list(trans_chars)
        self._tabkey_list = list(trans_chars)
        self._t_chars = list(trans_chars)
        res = self.update_candidates ()
        return res

    def pop_input (self):
        '''remove and display last input char held'''
        _c =''
        if self._chars:
            if self._typed_chars:
                self._typed_chars.pop()
            _c = self._chars.pop()
            if self._tabkey_list:
                self._tabkey_list.pop()
            if not self._tabkey_list:
                if  self._typed_chars:
                     self._typed_chars = []
        self._t_chars.pop()
        self.update_candidates ()
        return _c

    def get_input_chars (self):
        '''get characters held'''
        return self._chars

    def get_input_chars_string (self):
        '''Get valid input char string'''
        return u''.join(self._t_chars)

    def get_all_input_strings (self):
        '''Get all uncommited input characters, used in English mode or direct commit'''
        return  u''.join(self._chars)

    def split_phrase (self):
        '''Split current phrase into two phrases'''
        _head = u''
        _end = u''
        try:
            _head = self._strings[self._cursor[0]][:self._cursor[1]]
            _end = self._strings[self._cursor[0]][self._cursor[1]:]
            self._strings.pop(self._cursor[0])
            self._strings.insert(self._cursor[0],_head)
            self._strings.insert(self._cursor[0]+1,_end)
            self._cursor[0] +=1
            self._cursor[1] = 0
        except:
            pass

    def remove_before_string (self):
        '''Remove string before cursor'''
        if self._cursor[1] != 0:
            self.split_phrase()
        if self._cursor[0] > 0:
            self._strings.pop(self._cursor[0]-1)
            self._cursor[0] -= 1
        else:
            pass
        # if we remove all characters in preedit string, we need to clear the self._t_chars
        if self._cursor == [0,0]:
            self._t_chars =[]

    def remove_after_string (self):
        '''Remove string after cursor'''
        if self._cursor[1] != 0:
            self.split_phrase()
        if self._cursor[0] >= len (self._strings):
            pass
        else:
            self._strings.pop(self._cursor[0])

    def remove_before_char (self):
        '''Remove character before cursor'''
        if self._cursor[1] > 0:
            _str = self._strings[ self._cursor[0] ]
            self._strings[ self._cursor[0] ] = _str[ : self._cursor[1]-1] + _str[ self._cursor[1] :]
            self._cursor[1] -= 1
        else:
            if self._cursor[0] == 0:
                pass
            else:
                if len ( self._strings[self._cursor[0] - 1] ) == 1:
                    self.remove_before_string()
                else:
                    self._strings[self._cursor[0] - 1] = self._strings[self._cursor[0] - 1][:-1]
        # if we remove all characters in preedit string, we need to clear the self._t_chars
        if self._cursor == [0,0]:
            self._t_chars =[]

    def remove_after_char (self):
        '''Remove character after cursor'''
        if self._cursor[1] == 0:
            if self._cursor[0] == len ( self._strings):
                pass
            else:
                if len( self._strings[ self._cursor[0] ]) == 1:
                    self.remove_after_string ()
                else:
                    self._strings[ self._cursor[0] ] = self._strings[ self._cursor[0] ][1:]
        else:
            if ( self._cursor[1] + 1 ) == len( self._strings[ self._cursor[0] ] ) :
                self.split_phrase ()
                self.remove_after_string ()
            else:
                string = self._strings[ self._cursor[0] ]
                self._strings[ self._cursor[0] ] = string[:self._cursor[1]] + string[ self._cursor[1] + 1 : ]

    def get_preedit_strings (self):
        '''Get preedit strings'''
        input_chars = self.get_input_chars ()
        if input_chars:
            _candi = u''.join(input_chars)
        else:
            _candi = u''
        if self._strings:
            res = u''
            _cursor = self._cursor[0]
            res = u''.join(self._strings[:_cursor] + [_candi] + self._strings[_cursor:])
            return res
        else:
            return _candi

    def add_caret (self, addstr):
        '''add length to caret position'''
        self._caret += len(addstr)

    def get_caret (self):
        '''Get caret position in preedit strings'''
        self._caret = 0
        if self._cursor[0] and self._strings:
            map (self.add_caret,self._strings[:self._cursor[0]])
        self._caret += self._cursor[1]
        _candi = u''.join(self.get_input_chars())
        self._caret += len( _candi )
        return self._caret

    def arrow_left (self):
        '''Process Arrow Left Key Event.
        Update cursor data when move caret left'''
        if self.get_preedit_strings ():
            if not self.get_input_chars():
                if self._cursor[1] > 0:
                    self._cursor[1] -= 1
                else:
                    if self._cursor[0] > 0:
                        self._cursor[1] = len (self._strings[self._cursor[0]-1]) - 1
                        self._cursor[0] -= 1
                    else:
                        self._cursor[0] = len(self._strings)
                        self._cursor[1] = 0
                self.update_candidates ()
            return True
        else:
            return False

    def arrow_right (self):
        '''Process Arrow Right Key Event.
        Update cursor data when move caret right'''
        if self.get_preedit_strings ():
            if not self.get_input_chars():
                if self._cursor[1] == 0:
                    if self._cursor[0] == len (self._strings):
                        self._cursor[0] = 0
                    else:
                        self._cursor[1] += 1
                else:
                    self._cursor[1] += 1
                if self._cursor[1] == len(self._strings[ self._cursor[0] ]):
                    self._cursor[0] += 1
                    self._cursor[1] = 0
                self.update_candidates ()
            return True
        else:
            return False

    def control_arrow_left (self):
        '''Process Control + Arrow Left Key Event.
        Update cursor data when move caret to string left'''
        if self.get_preedit_strings ():
            if not self.get_input_chars():
                if self._cursor[1] == 0:
                    if self._cursor[0] == 0:
                        self._cursor[0] = len (self._strings) - 1
                    else:
                        self._cursor[0] -= 1
                else:
                    self._cursor[1] = 0
                self.update_candidates ()
            return True
        else:
            return False

    def control_arrow_right (self):
        '''Process Control + Arrow Right Key Event.
        Update cursor data when move caret to string right'''
        if self.get_preedit_strs ():
            if not self.get_input_chars():
                if self._cursor[1] == 0:
                    if self._cursor[0] == len (self._strings):
                        self._cursor[0] = 1
                    else:
                        self._cursor[0] += 1
                else:
                    self._cursor[0] += 1
                    self._cursor[1] = 0
                self.update_candidates ()
            return True
        else:
            return False

    def ap_candidate (self, candi):
        '''append candidate to lookup_table'''
        _phrase= candi[0]
        attrs = IBus.AttrList ()
        if not _phrase.startswith(self.get_input_chars_string()):
            # this is a candidate which does not start exactly
            # with the characters typed, i.e. it is a suggestion
            # for a spelling correction:
            attrs.append(IBus.attr_foreground_new(rgb(0xff,0x00,0x00), 0, len(_phrase)))
        elif candi[1] > 10:
            # this is a frequently used phrase:
            attrs.append(IBus.attr_foreground_new(rgb(0xff,0x7f,0x00), 0, len(_phrase)))
        else:
            # this is a system phrase that has been used less then 10 times or maybe never:
            attrs.append(IBus.attr_foreground_new(rgb(0x00,0x00,0x00), 0, len(_phrase)))
        text = IBus.Text.new_from_string(_phrase)
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
        if self._tabkey_list == self._tabkey_list_when_update_candidates_was_last_called:
            # The input did not change since we came here last, do nothing and leave
            # candidates and lookup table unchanged:
            return True
        self._tabkey_list_when_update_candidates_was_last_called = self._tabkey_list[:]
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)
        if self._tabkey_list:
            try:
                self._candidates = self.db.select_words(u''.join(self._tabkey_list))
            except:
                import traceback
                traceback.print_exc()
        else:
            self._candidates =[]
        if self._candidates:
            map(self.ap_candidate, self._candidates)
        return True

    def commit_to_preedit (self):
        '''Add selected phrase in lookup table to preedit string'''
        try:
            if self._candidates:
                self._strings.insert(self._cursor[0], self._candidates[self.get_cursor_pos()][0])
                self._cursor [0] += 1
            self.clear_input()
            self.update_candidates ()
        except:
            import traceback
            traceback.print_exc()

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

    def number (self, index):
        '''
        Commit a candidate in the lookup table which was selected by
        typing a number. The index parameter should start from 0.
        '''
        cursor_pos = self._lookup_table.get_cursor_pos()
        cursor_in_page = self._lookup_table.get_cursor_in_page()
        current_page_start = cursor_pos - cursor_in_page
        real_index = current_page_start + index
        if real_index >= len (self._candidates):
            # the index given is out of range we do not commit anything
            return False
        self._lookup_table.set_cursor_pos(real_index)
        self.commit_to_preedit ()
        return True

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
            self.db.remove_phrase(phrase=can[0], database='user_db', commit=False)
            self.db.remove_phrase(phrase=can[0], database='mudb', commit=True)
            # sync user database immediately after removing
            # phrases:
            self.db.sync_usrdb()
            # call update_candidates() to get a new SQL query:
            self.update_candidates ()
            return True
        else:
            return False

    def get_cursor_pos (self):
        '''get lookup table cursor position'''
        return self._lookup_table.get_cursor_pos()

    def get_lookup_table (self):
        '''Get lookup table'''
        return self._lookup_table

    def backspace (self):
        '''Process backspace Key Event'''
        if self.get_input_chars():
            self.pop_input ()
            return True
        elif self.get_preedit_strings ():
            self.remove_before_char ()
            return True
        else:
            return False

    def control_backspace (self):
        '''Process control+backspace Key Event'''
        if self.get_input_chars():
            self.clear_input()
            return True
        elif self.get_preedit_strings ():
            self.remove_before_string ()
            return True
        else:
            return False

    def delete (self):
        '''Process delete Key Event'''
        if self.get_input_chars():
            return True
        elif self.get_preedit_strings ():
            self.remove_after_char ()
            return True
        else:
            return False

    def control_delete (self):
        '''Process control+delete Key Event'''
        if self.get_input_chars ():
            return True
        elif self.get_preedit_strings ():
            self.remove_after_string ()
            return True
        else:
            return False

    def space (self):
        '''Process space Key Event
        return (KeyProcessResult,whethercommit,commitstring)'''
        self._typed_chars = []
        if self._t_chars :
            # user has input sth
            istr = self.get_all_input_strings ()
            if self._lookup_table.cursor_visible:
                self.commit_to_preedit()
                self._lookup_table.set_cursor_visible(True)
            else:
                self.commit_to_preedit()
            pstr = self.get_preedit_strings ()
            return (True,pstr,istr)
        else:
            return (False,u'',u'')

########################
### Engine Class #####
####################
class tabengine (IBus.Engine):
    '''The IM Engine for Tables'''

    # colors
#    _phrase_color             = 0xffffff
#    _user_phrase_color         = 0xffffff
#    _new_phrase_color         = 0xffffff

    def __init__ (self, bus, obj_path, db ):
        super(tabengine,self).__init__ (connection=bus.get_connection(),object_path=obj_path)
        self._bus = bus
        self.db = db
        # config
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

        # this is the backend sql db we need for our IME
        # we receive this db from IMEngineFactory
        #self.db = tabsqlitedb.tabsqlitedb( name = dbname )

        self._icon_dir = '%s%s%s%s' % (os.getenv('IBUS_HUNSPELL_TABLE_LOCATION'),
                os.path.sep, 'icons', os.path.sep)
        # 0 = english input mode
        # 1 = table input mode
        self._mode = 1

        self._status = self.db.ime_properties.get('status_prompt').encode('utf8')
        self._valid_input_chars = list(self.db.ime_properties.get('valid_input_chars').decode('utf8'))

        self._page_down_keys = [IBus.KEY_Page_Down, IBus.KEY_KP_Page_Down]
        self._page_up_keys = [IBus.KEY_Page_Up, IBus.KEY_KP_Page_Up]

        # Containers we used:
        self._editor = editor(self._config, self.db)
        # some other vals we used:
        # self._prev_key: hold the key event last time.
        self._prev_key = None
        self._prev_char = None
        self._double_quotation_state = False
        self._single_quotation_state = False
        self.is_lookup_table_enabled_by_tab = False
        self._tab_enable = variant_to_value(self._config.get_value (
            self._config_section,
            "tabenable"))
        if self._tab_enable == None:
            self._tab_enable = self.db.ime_properties.get('tab_enable').lower() == u'true'
        # the commit phrases length
        self._len_list = [0]
        self._on = False
        self.reset ()

    def reset (self):
        self._editor.clear ()
        self._double_quotation_state = False
        self._single_quotation_state = False
        self._prev_key = None
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
        _str = self._editor.get_preedit_strings ()
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
            if self._tab_enable:
                # if everything has been cleared from the editor
                # for example by backspace, disable a tab enabled
                # lookup table again:
                self.is_lookup_table_enabled_by_tab = False
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


    def commit_string (self,string):
        if self._tab_enable:
            # after each commit, disable a tab enabled lookup
            # table again, i.e. one needs to press tab again
            # while typing the next word to show the lookup table
            # again:
            self.is_lookup_table_enabled_by_tab = False
        self._editor.clear ()
        self._update_ui ()
        super(tabengine,self).commit_text(IBus.Text.new_from_string(string))
#        self._prev_char = string[-1]

    def _match_hotkey (self, key, code, mask):

        if key.code == code and key.mask == mask:
            if self._prev_key and key.code == self._prev_key.code and key.mask & IBus.ModifierType.RELEASE_MASK:
                return True
            if not key.mask & IBus.ModifierType.RELEASE_MASK:
                return True

        return False

    def do_process_key_event(self, keyval, keycode, state):
        '''Process Key Events
        Key Events include Key Press and Key Release,
        modifier means Key Pressed
        '''
        key = KeyEvent(keyval, state & IBus.ModifierType.RELEASE_MASK == 0, state)
        # ignore NumLock mask
        key.mask &= ~IBus.ModifierType.MOD2_MASK

        result = self._process_key_event (key)
        self._prev_key = key
        return result

    def _process_key_event (self, key):
        '''Internal method to process key event'''

        if key.mask & IBus.ModifierType.RELEASE_MASK:
            return True

        if self._editor.is_empty ():
            # we have not input anything
            if  key.code >= 32 and key.code <= 127 and ( keysym2unichr(key.code) not in self._valid_input_chars ) \
                    and (not (key.mask & (IBus.ModifierType.MOD1_MASK | IBus.ModifierType.CONTROL_MASK))):
                if key.code == IBus.KEY_space:
                    self.commit_string (keysym2unichr (key.code))
                    return True
                if curses.ascii.ispunct(key.code):
                    if not self._editor.trans_m17n_mode:
                        # If no transliteration is used, we can commit
                        # punctuation characters immediately:
                        self.commit_string(keysym2unichr(key.code))
                        return True
                    # If transliteration is used, we cannot commit
                    # punctuation characters immediately. For example,
                    # “.c” is transliterated to “ċ” in the
                    # “t-latn-pre” transliteration method, therefore
                    # we cannot commit immediately. Just add it to the
                    # input so far and see what comes next:
                    res = self._editor.add_input(keysym2unichr(key.code))
                    self._update_ui()
                    return True
                if curses.ascii.isdigit(key.code):
                    if not self._editor.trans_m17n_mode:
                        # If a digit has been typed and no transliteration
                        # is used, we can commit immediately:
                        self.commit_string(keysym2unichr (key.code))
                        return True
                    # If a digit has been typed and we use
                    # transliteration, we may want to convert it
                    # to native digits. For example, with
                    # mr-inscript we want “3” to be converted to
                    # “३”. So we try to transliterate before we commit:
                    self.commit_string(
                        self._editor.trans.transliterate(keysym2unichr(key.code))[0].decode('utf8'))
                    return True
            elif (key.code < 32 or key.code > 127) and (keysym2unichr(key.code) not in self._valid_input_chars):
                return False

        if key.code == IBus.KEY_Escape:
            self.reset ()
            self._update_ui ()
            return True

        elif key.code in (IBus.KEY_Return, IBus.KEY_KP_Enter):
            commit_string = self._editor.get_all_input_strings ()
            self.commit_string (commit_string )
            return False

        elif key.code in (IBus.KEY_Down, IBus.KEY_KP_Down) :
            res = self._editor.arrow_down ()
            self._update_ui ()
            return res

        elif key.code in (IBus.KEY_Up, IBus.KEY_KP_Up):
            res = self._editor.arrow_up ()
            self._update_ui ()
            return res

        elif key.code in (IBus.KEY_Left, IBus.KEY_KP_Left) and key.mask & IBus.ModifierType.CONTROL_MASK:
            res = self._editor.control_arrow_left ()
            self._update_ui ()
            return res

        elif key.code in (IBus.KEY_Right, IBus.KEY_KP_Right) and key.mask & IBus.ModifierType.CONTROL_MASK:
            res = self._editor.control_arrow_right ()
            self._update_ui ()
            return res

        elif key.code in (IBus.KEY_Left, IBus.KEY_KP_Left):
            res = self._editor.arrow_left ()
            self._update_ui ()
            return res

        elif key.code in (IBus.KEY_Right, IBus.KEY_KP_Right):
            res = self._editor.arrow_right ()
            self._update_ui ()
            return res

        elif key.code == IBus.KEY_BackSpace and key.mask & IBus.ModifierType.CONTROL_MASK:
            res = self._editor.control_backspace ()
            self._update_ui ()
            return res

        elif key.code == IBus.KEY_BackSpace:
            res = self._editor.backspace ()
            self._update_ui ()
            return res

        elif key.code == IBus.KEY_Delete  and key.mask & IBus.ModifierType.CONTROL_MASK:
            res = self._editor.control_delete ()
            self._update_ui ()
            return res

        elif key.code == IBus.KEY_Delete:
            res = self._editor.delete ()
            self._update_ui ()
            return res

        elif key.code >= IBus.KEY_1 and key.code <= IBus.KEY_9 and self._editor._candidates and key.mask & IBus.ModifierType.CONTROL_MASK:
            res = self._editor.number (key.code - IBus.KEY_1)
            self._update_ui ()
            return res

        elif key.code >= IBus.KEY_1 and key.code <= IBus.KEY_9 and self._editor._candidates and key.mask & IBus.ModifierType.MOD1_MASK:
            res = self._editor.alt_number (key.code - IBus.KEY_1)
            self._update_ui ()
            return res

        elif key.code == IBus.KEY_space:
            in_str = self._editor.get_all_input_strings()
            sp_res = self._editor.space ()
            #return (KeyProcessResult,whethercommit,commitstring)
            if sp_res[0]:
                if self._editor._lookup_table.cursor_visible:
                    if sp_res[1]:
                        self.commit_string (sp_res[1]+ " ")
                        self.db.check_phrase (sp_res[1], in_str)
                    else:
                        self.commit_string (in_str+ " ")
                        self.db.check_phrase (in_str, in_str)
                else:
                    if sp_res[1].lower() == in_str.lower():
                        self.commit_string (sp_res[1]+ " ")
                        self.db.check_phrase (sp_res[1], in_str)
                    else:
                        self.commit_string (in_str+ " ")
                        self.db.check_phrase (in_str, in_str)
            else:
                if sp_res[1] == u' ':
                    self.commit_string ((" "))

            self._update_ui ()
            return True
        # now we ignore all else hotkeys
        elif key.mask & (IBus.ModifierType.CONTROL_MASK|IBus.ModifierType.MOD1_MASK):
            return False

        elif key.mask & IBus.ModifierType.MOD1_MASK:
            return False

        elif keysym2unichr(key.code) in self._valid_input_chars or \
                (keysym2unichr(key.code) in u'abcdefghijklmnopqrstuvwxyz!@#$%^&*()-_+=\|}]{[:;/>.<,~`?\'"' ):
            self._editor.add_input(keysym2unichr(key.code))
            self._update_ui ()
            return True

        elif key.code in self._page_down_keys \
                and self._editor._candidates:
            res = self._editor.page_down()
            self._update_ui ()
            return res

        elif key.code in self._page_up_keys \
                and self._editor._candidates:
            res = self._editor.page_up ()
            self._update_ui ()
            return res

        elif key.code >= IBus.KEY_1 and key.code <= IBus.KEY_9 and self._editor._candidates:
            input_keys = self._editor.get_all_input_strings ()
            res = self._editor.number (key.code - IBus.KEY_1)
            if res:
                commit_string = self._editor.get_preedit_strings ()
                self.commit_string (commit_string+ " ")
                self._update_ui ()
                # modify freq info
                self.db.check_phrase (commit_string, input_keys)
            return True

        elif key.code <= 127:
            comm_str = self._editor.get_all_input_strings ()
            self._editor.clear ()
            self.commit_string (comm_str + keysym2unichr (key.code))
            return True

        elif key.code == IBus.KEY_Tab:
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
                    self._editor.commit_to_preedit ()
                    commit_string = self._editor.get_preedit_strings ()
                    self.commit_string(commit_string + " " )
                else:
                    commit_string = self._editor.get_all_input_strings ()
                    self.commit_string(commit_string + " ")
                    return True
            return True

        return False

    def do_focus_in (self):
        if self._on:
            self._update_ui ()

    def do_focus_out (self):
        self.reset()
        self.db.sync_usrdb()
        return

    def do_enable (self):
        self._on = True
        self.do_focus_in()

    def do_disable (self):
        self.reset()
        self._on = False

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
            string.maketrans(string.ascii_uppercase, string.ascii_lowercase ))

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
