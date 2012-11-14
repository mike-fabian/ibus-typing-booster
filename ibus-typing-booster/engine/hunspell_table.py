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
import ibus
#from ibus import Property
from ibus import keysyms
from ibus import modifier
from ibus import ascii
#import tabsqlitedb
import tabdict
import keysym2ucs
from keysym2ucs import keysym2ucs
from keysym2ucs import keysym2unichr
import re
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


patt_edit = re.compile (r'(.*)###(.*)###(.*)')
patt_uncommit = re.compile (r'(.*)@@@(.*)')

from gettext import dgettext
_  = lambda a : dgettext ("ibus-typing-booster", a)
N_ = lambda a : a

import dbus

class KeyEvent:
    def __init__(self, keyval, is_press, state):
        self.code = keyval
        self.mask = state
        if not is_press:
            self.mask |= modifier.RELEASE_MASK
    def __str__(self):
        return "%s 0x%08x" % (keysyms.keycode_to_name(self.code), self.mask)


class editor(object):
    '''Hold user inputs chars and preedit string'''

    def __init__ (self, config, phrase_table_index,valid_input_chars, max_key_length, database, parser = tabdict.parse, deparser = tabdict.deparse, max_length = 64):
        self.db = database
        self._config = config
        self._name = self.db.get_ime_property('name')
        self._config_section = "engine/typing-booster/%s" % self._name
        self._pt = phrase_table_index
        self._parser = parser
        self._deparser = deparser
        self._max_key_len = int(max_key_length)
        self._max_length = max_length
        self._valid_input_chars = valid_input_chars
        self._chars = [[],[],[]]
        #self._t_chars: hold total input for table mode for input check
        self._t_chars = []
        # self._u_chars: hold user input but not manual comitted chars
        self._u_chars = []
        # self._tabkey_list: hold tab_key objects transform from user input chars
        self._tabkey_list = []
        # self._strings: hold preedit strings
        self._strings = []
        # self._cursor: the caret position in preedit phrases 
        self._cursor = [0,0]
        # self._candidates: hold candidates selected from database [[now],[pre]]
        self._candidates = [[],[]]
        self._lookup_table = ibus.LookupTable (tabengine._page_size,-1,False)
        self._lookup_table.clean ()
        self._lookup_table.show_cursor(False)

#        tabengine.hide_lookup_table(tabengine)
#        self._lookup_table.set_cursor_pos_in_current_page(0)
        # self._py_mode: whether in pinyin mode
        self._py_mode = False
        # self._caret: caret position in lookup_table
        self._caret = 0
        # self._onechar: whether we only select single character
        self._onechar = self._config.get_value (self._config_section, "OneChar", False)
        self._first = 0 
        self.is_down_press = False

        self._typed_chars = []
        self._m17ndb = 'm17n'
        self.trans = None
        self.lang_chars = self.db.get_ime_property('lang_chars')
        if self.lang_chars != None:
            self.lang_chars = self.lang_chars.decode('utf8')
        else:
            self.lang_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        self.lang_dict = {}
        self.lang_dict['0'] = 0
        for index,char in enumerate(self.lang_chars):
            if char:
                self.lang_dict[char] = index + 1

        self._supported_imes = []
        if self.db.get_ime_property('m17n_mim_name') != None:
            self._supported_imes.append(self.db.get_ime_property('m17n_mim_name'))
        self._other_ime = self.db.get_ime_property('other_ime').lower() == u'true'
        if self._other_ime:
            imes = self.db.get_ime_property('imes').split(',')
            for item in imes:
                mim_name = item.split(':')[1]
                if not mim_name in self._supported_imes:
                    self._supported_imes.append(mim_name)
        if self._other_ime:
            # Several imes are selectable, try to get the selected one from dconf:
            self._current_ime = self._config.get_value(self._config_section, 'inputmethod', None)
            if self._current_ime == None or not self._current_ime in self._supported_imes:
                # There is no ime set in dconf or an unsupported ime,
                # fall back to the “main” ime from the config file
                # or if that one does not exist either to the first of
                # the supported imes:
                self._current_ime = self.db.get_ime_property('m17n_mim_name')
                if self._current_ime == None:
                    self._current_ime = self._supported_imes[0]
        else:
            # There is only one ime, get it from the config file:
            self._current_ime = self.db.get_ime_property('m17n_mim_name')
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
                print "error: could not get Transliterator"
                pass

    def clear (self):
        '''Remove data holded'''
        self.over_input ()
        self._t_chars = []
        self._strings = []
        self._typed_chars = []
        self._cursor = [0,0]
        self._py_mode = False
        self.update_candidates
    
    def is_empty (self):
        return len(self._t_chars) == 0

    def clear_input (self):
        '''
        Remove input characters held for Table mode,
        '''
        self._chars = [[],[],[]]
        self._tabkey_list = []
        self._lookup_table.clean()
        self._lookup_table.show_cursor(False)
        self._candidates = [[],[]]
        self._typed_chars = []

    def over_input (self):
        '''
        Remove input characters held for Table mode,
        '''
        self.clear_input ()
        self._u_chars = []
        self._typed_chars = []

    def set_parser (self, parser):
        '''change input parser'''
        self.clear ()
        self._parser = parser
        
    def add_input (self,c):
        '''add input character'''
        if self._chars[1]:
            self._chars[1].append (c)
        else:
            self._typed_chars.append(c)
            self._typed_chars = list(unicodedata.normalize('NFC', ''.join(self._typed_chars)))
            if self.trans_m17n_mode:
                trans_chars = self.trans.transliterate(''.join(self._typed_chars))[0].decode('utf8')
            else:
                trans_chars = ''.join(self._typed_chars)
            self._chars[0] = []
            self._tabkey_list = []
            self._t_chars = []
            for trans_char in trans_chars:
                self._chars[0].append(trans_char)
                self._tabkey_list += tabdict.other_lang_parser (trans_char,self.lang_dict)
                self._t_chars.append(trans_char)
        res = self.update_candidates ()
        return res

    def pop_input (self):
        '''remove and display last input char held'''
        _c =''
        if self._chars[1]:
            _c = self._chars[1].pop ()
        elif self._chars[0]:
            if self._typed_chars:
                self._typed_chars.pop()
            _c = self._chars[0].pop ()
            if self._tabkey_list:
                self._tabkey_list.pop()
            if not self._tabkey_list:
                if  self._typed_chars:
                     self._typed_chars = []
            if (not self._chars[0]) and self._u_chars:
                self._chars[0] = self._u_chars.pop()
                self._chars[1] = self._chars[1][:-1]
                self._tabkey_list = self._parser (self._chars[0])
                self._strings.pop (self._cursor[0] - 1 )
                self._cursor[0] -= 1
        self._t_chars.pop()
        self.update_candidates ()
        return _c
    
    def get_input_chars (self):
        '''get characters held, valid and invalid'''
        #return self._chars[0] + self._chars[1]
        return self._chars[0] 

    def get_input_chars_string (self):
        '''Get valid input char string'''
        return u''.join(map(str,self._t_chars))

    def get_all_input_strings (self):
        '''Get all uncommit input characters, used in English mode or direct commit'''
        #return  u''.join( map(u''.join, self._u_chars + [self._chars[0]] \
        #    + [self._chars[1]]) )
        return  u''.join( map(u''.join, self._u_chars + [self._chars[0]]) )

    
    def get_index(self,key):
        '''Get the index of key in database table'''
        return self._pt.index(key)

    def split_phrase (self):
        '''Splite current phrase into two phrase'''
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

    def get_invalid_input_chars (self):
        '''get invalid characters held'''
        return self._chars[1]

    def get_invalid_input_string (self):
        '''get invalid characters in string form'''
        return u''.join (self._chars[1])
        
    def get_preedit_strings (self):
        '''Get preedit strings'''
        if self._candidates[0]:
            _p_index = self.get_index ('phrase')
            #_candi = u'###' + self._candidates[0][ int (self._lookup_table.get_cursor_pos() ) ][ _p_index ] + u'###'
            input_chars = self.get_input_chars ()
            _candi = u''.join( ['###'] + map( str, input_chars) + ['###'] )
        else:
            input_chars = self.get_input_chars ()
            if input_chars:
                _candi = u''.join( ['###'] + map( str, input_chars) + ['###'] )
            else:
                _candi = u''
        if self._strings:
            res = u''
            _cursor = self._cursor[0]
            _luc = len (self._u_chars)
            if _luc:
                _candi = _candi == u'' and u'######' or _candi
                res =u''.join( self._strings[ : _cursor - _luc] +[u'@@@'] + self._strings[_cursor - _luc : _cursor ]  + [ _candi  ] + self\
._strings[ _cursor : ])
            else:
                res = u''.join( self._strings[ : _cursor ] + [ _candi  ] + self._strings[ _cursor : ])
            return res
        else:
            return _candi

    
    def get_strings (self):
        '''Get  strings'''
        if self._candidates[0]:
            _p_index = self.get_index ('phrase')
            _candi = u'###' + self._candidates[0][ int (self._lookup_table.get_cursor_pos() ) ][ _p_index ] + u'###'
            return _candi
        else:
            input_chars = self.get_input_chars ()
            if input_chars:
                _candi = u''.join( ['###'] + map( str, input_chars) + ['###'] )
            else:
                _candi = u''
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
        _candi = u''.join( map( str,self.get_input_chars()) )
        self._caret += len( _candi ) 
        return self._caret
    
    def arrow_left (self):
        '''Process Arrow Left Key Event.
        Update cursor data when move caret left'''
        if self.get_preedit_strings ():
            if not( self.get_input_chars () or self._u_chars ):
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
            if not( self.get_input_chars () or self._u_chars ):
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
            if not( self.get_input_chars () or self._u_chars ):
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
            if not( self.get_input_chars () or self._u_chars ):
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
        _p_index = self.get_index('phrase')
        # _tbks = u''.join( map(self._deparser , candi[ len(self._tabkey_list) : _p_index ] ) )
        _phrase = candi[_p_index]
        # further color implementation needed :)
        # here -2 is the pos of num, -1 is the pos of . 0 is the pos of string
        #attrs = ibus.AttrList ([ibus.AttributeForeground (0x8e2626, -2, 1)])
        attrs = ibus.AttrList ()
        # this is the part of tabkey
        #attrs.append( ibus.AttributeForeground ( 0x1973a2, 0, \
        #    len(_phrase) + len(_tbks)))
        if candi[-2] < 0:
            # this is a user defined phrase:
            attrs.append ( ibus.AttributeForeground (0x7700c3, 0, len(_phrase)) )
        elif candi[-1] > 0:
            # this is a sys phrase used by user:
            attrs.append ( ibus.AttributeForeground (0x000000, 0, len(_phrase)) )
        else:
            # this is a system phrase haven't been used:
            attrs.append ( ibus.AttributeForeground (0x000000, 0, len(_phrase)) )
        self._lookup_table.append_candidate ( ibus.Text(_phrase, attrs) )
        self._lookup_table.show_cursor (False)

    def filter_candidates (self, candidates):
        '''Filter candidates '''
        return candidates[:]
        

    def update_candidates (self):
        '''Update lookuptable'''
        # first check whether the IME have defined start_chars
        if self.db.startchars and ( len(self._chars[0]) == 1 )\
                and ( len(self._chars[1]) == 0 ) \
                and ( self._chars[0][0] not in self.db.startchars):
            self._u_chars.append ( self._chars[0][0] )
            self._strings.insert ( self._cursor[0], self._chars[0][0] )
            self._cursor [0] += 1
            self.clear_input()
        else:
            if (self._chars[0] == self._chars[2] and self._candidates[0]) \
                    or self._chars[1]:
                # if no change in valid input char or we have invalid input,
                # we do not do sql enquery
                pass
            else:
                # check whether last time we have only one candidate
                only_one_last = self.one_candidate()
                # do enquiry
                self._lookup_table.clean ()
                self._lookup_table.show_cursor (False)
                if self._tabkey_list:
#                    self._candidates[0] = self.db.select_words( self._tabkey_list, self._onechar )
                    try:
                        self._candidates[0] = self.db.select_words( self._tabkey_list, False )
                    except:
                        print "Exception in selecting the word from db"
                    self._chars[2] = self._chars[0][:]
                else:
                    self._candidates[0] =[]
                if self._candidates[0]:
                    self._candidates[0] = self.filter_candidates (self._candidates[0])
                if self._candidates[0]:
                    map ( self.ap_candidate,self._candidates[0] )
                self._candidates[1] = self._candidates[0]
            return True

    def commit_to_preedit (self):
        '''Add select phrase in lookup table to preedit string'''
        _p_index = self.get_index('phrase')
        try:
            if self._candidates[0]:
                self._strings.insert(self._cursor[0], self._candidates[0][ self.get_cursor_pos() ][_p_index])
                self._cursor [0] += 1
            self.over_input ()
            self.update_candidates ()
        except:
            print "exception"
            pass
    
    def auto_commit_to_preedit (self):
        '''Add select phrase in lookup table to preedit string'''
        _p_index = self.get_index('phrase')
        try:
            self._u_chars.append( self._chars[0][:] )
            self._strings.insert(self._cursor[0], self._candidates[0][ self.get_cursor_pos() ][_p_index])
            self._cursor [0] += 1
            self.clear_input()
            self.update_candidates ()
        except:
            pass

    def get_aux_strings (self):
        '''Get aux strings'''
        input_chars = self.get_input_chars ()
        if input_chars:
            #aux_string =  u' '.join( map( u''.join, self._u_chars + [self._chars[0]] ) )
            aux_string =   u''.join (self._chars[0]) 
            return aux_string

        aux_string = u''
        cstr = u''.join(self._strings)
        if self.db.user_can_define_phrase:
            if len (cstr ) > 1:
                aux_string += (u'\t#: ' + self.db.parse_phrase_to_tabkeys (cstr))
        return aux_string
    def arrow_down(self):
        '''Process Arrow Down Key Event
        Move Lookup Table cursor down'''
        self._first = self._first + 1
        self._lookup_table.show_cursor(True)
        self.is_down_press = True
        if self._first == 1:
            return True
        else:
            res = self._lookup_table.cursor_down()
            self.update_candidates ()
            if not res and self._candidates[0]:
                return True
            return res
    
    def arrow_up(self):
        '''Process Arrow Up Key Event
        Move Lookup Table cursor up'''
        self._lookup_table.show_cursor(True)
        res = self._lookup_table.cursor_up()
        self.update_candidates ()
        if not res and self._candidates[0]:
            return True
        return res
    
    def page_down(self):
        '''Process Page Down Key Event
        Move Lookup Table page down'''
        self._lookup_table.show_cursor(True)
        res = self._lookup_table.page_down()
        self.update_candidates ()
        if not res and self._candidates[0]:
            return True
        return res
    
    def page_up(self):
        self._lookup_table.show_cursor(True)
        '''Process Page Up Key Event
        move Lookup Table page up'''
        res = self._lookup_table.page_up()
        self.update_candidates ()
        if not res and self._candidates[0]:
            return True
        return res
    
    def number (self, index):
        '''Select the candidates in Lookup Table
        index should start from 0'''
        self._lookup_table.set_cursor_pos_in_current_page ( index )
        if index != self._lookup_table.get_cursor_pos_in_current_page ():
            # the index given is out of range we do not commit string
            return False
        self.commit_to_preedit ()
        return True

    def alt_number (self,index):
        '''Remove the candidates in Lookup Table from user_db index should start from 0'''
        cps = self._lookup_table.get_current_page_start()
        pos = cps + index
        if  len (self._candidates[0]) > pos:
            # this index is valid
            can = self._candidates[0][pos]
            if can[-2] < 0:
                # freq of this candidate is -1, means this a user phrase
                self.db.remove_phrase (can)
                # make update_candidates do sql enquiry
                self._chars[2].pop()
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

    def is_lt_visible (self):
        '''Check whether lookup table is visible'''
        return self._lookup_table.is_cursor_visible ()
    
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
            self.over_input ()
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

    def l_shift (self):
        '''Process Left Shift Key Event as immediately commit to preedit strings'''
        if self._chars[0]:
            _ic = self.get_strings ()
            if _ic:
                res = patt_edit.match (_ic)
                if res:
                    _ic = u''
                    ures = patt_uncommit.match (res.group(1))
                    if ures:
                        _ic = u''.join (ures.groups())
                    else:
                        _ic += res.group (1)
                    _ic += res.group(2)
                    _ic += res.group(3)
            self.commit_to_preedit ()
            return True
        else:
            return False
    
    def r_shift (self):
        '''Process Right Shift Key Event as changed between PinYin Mode and Table Mode'''
        if self._chars[0]:
            self.commit_to_preedit ()
        return True

    def space (self):
        '''Process space Key Event
        return (KeyProcessResult,whethercommit,commitstring)'''
        self._typed_chars = []
        if self._chars[1]:
            # we have invalid input, so do not commit 
            return (False,u'')
        if self._t_chars :
            _ic = self.get_strings ()
            if _ic:
                res = patt_edit.match (_ic)
                if res:
                    _ic = u''
                    ures = patt_uncommit.match (res.group(1))
                    if ures:
                        _ic = u''.join (ures.groups())
                    else:
                        _ic += res.group (1)
                    _ic += res.group(2)
                    _ic += res.group(3)
            # user has input sth
            istr = self.get_all_input_strings ()
            self.commit_to_preedit ()
            pstr = self.get_preedit_strings ()
            self.clear()
            return (True,pstr,istr)
        else:
            return (False,u'',u'')
    
    def one_candidate (self):
        '''Return true if there is only one candidate'''
        return len(self._candidates[0]) == 1

########################
### Engine Class #####
####################
class tabengine (ibus.EngineBase):
    '''The IM Engine for Tables'''
    
    # colors
#    _phrase_color             = 0xffffff
#    _user_phrase_color         = 0xffffff
#    _new_phrase_color         = 0xffffff

    def __init__ (self, bus, obj_path, db ):
        super(tabengine,self).__init__ (bus,obj_path)
        self._bus = bus
        self.db = db
        # config
        self._name = self.db.get_ime_property('name')
        self._config_section = "engine/typing-booster/%s" % self._name
        self._config = self._bus.get_config ()
        self._config.connect('value-changed', self.__config_value_changed_cb)

        tabengine._page_size = self._config.get_value(
            self._config_section,
            'pagesize',
            int(self.db.get_ime_property('page_size')))
        if tabengine._page_size == None:
            tabengine._page_size = 6 # reasonable default page size
        if tabengine._page_size < 1:
            tabengine._page_size = 1 # minimum page size supported
        if tabengine._page_size > 9:
            tabengine._page_size = 9 # maximum page size supported

        # this is the backend sql db we need for our IME
        # we receive this db from IMEngineFactory
        #self.db = tabsqlitedb.tabsqlitedb( name = dbname )
        
        # this is the parser which parses the input string to key object
        self._parser = tabdict.parse
        
        self._icon_dir = '%s%s%s%s' % (os.getenv('IBUS_HUNSPELL_TABLE_LOCATION'),
                os.path.sep, 'icons', os.path.sep)
        # 0 = english input mode
        # 1 = table input mode
        self._mode = 1
        # self._ime_py: True / False this IME support pinyin mode
 
        self._status = self.db.get_ime_property('status_prompt').encode('utf8')
        # now we check and update the valid input characters
        self._chars = self.db.get_ime_property('valid_input_chars').decode('utf8')
        self._valid_input_chars = []
        for _c in self._chars:
            self._valid_input_chars.append(_c)
        del self._chars

        # check whether we can use '=' and '-' for page_down/up
        self._page_down_keys = [keysyms.Page_Down, keysyms.KP_Page_Down]
        self._page_up_keys = [keysyms.Page_Up, keysyms.KP_Page_Up]
        if '=' not in self._valid_input_chars \
                and '-' not in self._valid_input_chars:
            self._page_down_keys.append (keysyms.equal)
            self._page_up_keys.append (keysyms.minus)
        
        self._pt = self.db.get_phrase_table_index ()
        self._ml = int(self.db.get_ime_property ('max_key_length'))
        
        # Containers we used:
        self._editor = editor(self._config, self._pt, self._valid_input_chars, self._ml, self.db)
        # some other vals we used:
        # self._prev_key: hold the key event last time.
        self._prev_key = None
        self._prev_char = None
        self._double_quotation_state = False
        self._single_quotation_state = False
        self.is_lookup_table_enabled_by_tab = False
        self._tab_enable = self._config.get_value (
            self._config_section,
            "tabenable",
            self.db.get_ime_property('tab_enable').lower() == u'true')
        # [EnMode,TabMode] we get TabMode properties from db
        self._full_width_letter = [
                self._config.get_value (self._config_section,
                    "EnDefFullWidthLetter",
                    False),
                self._config.get_value (self._config_section, 
                    "TabDefFullWidthLetter", 
                    self.db.get_ime_property('def_full_width_letter').lower() == u'true' )
                ]
        self._full_width_punct = [
                self._config.get_value (self._config_section,
                    "EnDefFullWidthPunct",
                    False),
                self._config.get_value (self._config_section, 
                    "TabDefFullWidthPunct", 
                    self.db.get_ime_property('def_full_width_punct').lower() == u'true' )
                ]
        # some properties we will involved, Property is taken from scim.
        #self._setup_property = Property ("setup", _("Setup"))
        try:
            self._auto_commit = self.db.get_ime_property('auto_commit').lower() == u'true'
        except:
            self._auto_commit = False
        self._auto_commit = self._config.get_value (self._config_section, "AutoCommit",
                self._auto_commit)
        # the commit phrases length
        self._len_list = [0]
        # connect to SpeedMeter
        #try:
        #    bus = dbus.SessionBus()
        #    user = os.path.basename( os.path.expanduser('~') )
        #    self._sm_bus = bus.get_object ("org.ibus.table.SpeedMeter.%s"\
        #            % user, "/org/ibus/table/SpeedMeter")
        #    self._sm =  dbus.Interface(self._sm_bus,\
        #            "org.ibus.table.SpeedMeter") 
        #except:
        #    self._sm = None
        #self._sm_on = False
        self._on = False
        self.reset ()

    def reset (self):
        self._editor.clear ()
        self._double_quotation_state = False
        self._single_quotation_state = False
        self._prev_key = None
        #self._editor._onechar = False    
        self._update_ui ()
    
    def do_destroy(self):
        self.reset ()
        self.focus_out ()
        #self.db.sync_usrdb ()
        super(tabengine,self).do_destroy()

    def _change_mode (self):
        '''Shift input mode, TAB -> EN -> TAB
        '''
        self.reset ()
        self._update_ui ()

    def _update_preedit (self):
        '''Update Preedit String in UI'''
        _str = self._editor.get_preedit_strings ()
        if _str == u'':
            super(tabengine, self).update_preedit_text(ibus.Text(u'',None), 0, False)
        else:
            attrs = ibus.AttrList()
            res = patt_edit.match (_str)
            if res:
                _str = u''
                ures = patt_uncommit.match (res.group(1))
                if ures:
                    _str=u''.join (ures.groups())
                    lc = len (ures.group(1) )
                    lu = len (ures.group(2) )
                    attrs.append (ibus.AttributeForeground(0x1b3f03,0,lc) )
                    attrs.append (ibus.AttributeForeground(0x0895a2,lc,lu) )
                    lg1 = len (_str)
                else:
                    _str += res.group (1)
                    lg1 = len ( res.group(1) )
                 #   attrs.append (ibus.AttributeForeground(0x1b3f03,0,lg1) )
                _str += res.group(2)
                _str += res.group(3)
                lg2 = len ( res.group(2) )
                lg3 = len ( res.group(3) )
                attrs.append( ibus.AttributeForeground(0x0e0ea0,lg1,lg2) )
                #attrs.append( ibus.AttributeForeground(0x1b3f03,lg1+lg2,lg3) )
            else:
                attrs.append( ibus.AttributeForeground(0x1b3f03,0,len(_str)) )
#            attrs = ibus.AttrList()
#            attrs.append(ibus.AttributeUnderline(ibus.ATTR_UNDERLINE_SINGLE, 0, len(_str)))


            super(tabengine, self).update_preedit_text(ibus.Text(_str, attrs), self._editor.get_caret(), True)
    
    def _update_aux (self):
        '''Update Aux String in UI'''
        '''
        _ic = self._editor.get_strings ()
        if _ic:
            res = patt_edit.match (_ic)
            if res:
                _ic = u''
                ures = patt_uncommit.match (res.group(1))
                if ures:
                    _ic = u''.join (ures.groups())
                else:
                    _ic += res.group (1)
                _ic += res.group(2)
                _ic += res.group(3)
        if _ic in self._editor._ap_dict:
            _ic =  self._editor.get_aux_strings()+self._editor._ap_dict[_ic]
        '''
        _ic = self._editor.get_aux_strings()
        ins_str = ''
        _ic = None
        if _ic:
            attrs = ibus.AttrList([ ibus.AttributeForeground(0x9515b5,0, len(_ic)) ])
            #attrs = [ scim.Attribute(0,len(_ic),scim.ATTR_FOREGROUND,0x5540c1)]

            super(tabengine, self).update_auxiliary_text(ibus.Text(_ic, attrs), True)
        else:
            self.hide_auxiliary_text()
            #self.update_aux_string (u'', None, False)

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
        if len(self._editor._candidates[0]) == 0:
            self.hide_lookup_table()
            return
        if self._tab_enable:
            if self.is_lookup_table_enabled_by_tab:
                self.update_lookup_table ( self._editor.get_lookup_table(), True, False )    
            else:
                self.hide_lookup_table()
        else:
            self.update_lookup_table ( self._editor.get_lookup_table(), True, False )    

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
        super(tabengine,self).commit_text ( ibus.Text(string) )
#        self._prev_char = string[-1]

    def _convert_to_full_width (self, c):
        return ibus.unichar_half_to_full (c)
    
    def _match_hotkey (self, key, code, mask):
        
        if key.code == code and key.mask == mask:
            if self._prev_key and key.code == self._prev_key.code and key.mask & modifier.RELEASE_MASK:
                return True
            if not key.mask & modifier.RELEASE_MASK:
                return True

        return False
    
    def process_key_event(self, keyval, keycode, state):
        '''Process Key Events
        Key Events include Key Press and Key Release,
        modifier means Key Pressed
        '''
        key = KeyEvent(keyval, state & modifier.RELEASE_MASK == 0, state)
        # ignore NumLock mask
        key.mask &= ~modifier.MOD2_MASK

        result = self._process_key_event (key)
        self._prev_key = key
        return result

    def _process_key_event (self, key):
        '''Internal method to process key event'''
        return self._table_mode_process_key_event (key)
        
    def _table_mode_process_key_event (self, key):
        '''Xingma Mode Process Key Event'''
        cond_letter_translate = lambda (c): \
            self._convert_to_full_width (c) if self._full_width_letter [self._mode] else c
        cond_punct_translate = lambda (c): \
            self._convert_to_full_width (c) if self._full_width_punct [self._mode] else c
        
        if key.mask & modifier.RELEASE_MASK:
            return True
        
        if self._editor.is_empty ():
            # we have not input anything
            if  key.code >= 32 and key.code <= 127 and ( keysym2unichr(key.code) not in self._valid_input_chars ) \
                    and (not key.mask & modifier.ALT_MASK + modifier.CONTROL_MASK):
                if key.code == keysyms.space:
                    self.commit_string (keysym2unichr (key.code))
                    return True
                if ascii.ispunct (key.code):
                    if self._editor.trans_m17n_mode:
                        res = self._editor.add_input ( keysym2unichr(key.code) )
                        self._update_ui ()
                        return True
                    self.commit_string (keysym2unichr (key.code))
                    return True
                if ascii.isdigit (key.code):
                    if self._editor.trans_m17n_mode:
                        key_code = self._editor.trans.transliterate(keysym2unichr (key.code))[0].decode('utf8')
                        self.commit_string (key_code)
                        return True
                    self.commit_string (keysym2unichr (key.code))
                    return True
            elif (key.code < 32 or key.code > 127) and (keysym2unichr(key.code) not in self._valid_input_chars):
                return False

        if key.code == keysyms.Escape:
            self.reset ()
            self._update_ui ()
            return True
        
        elif key.code in (keysyms.Return, keysyms.KP_Enter):
            commit_string = self._editor.get_all_input_strings ()
            self.commit_string (commit_string )
            return False
        
        elif key.code in (keysyms.Down, keysyms.KP_Down) :
            res = self._editor.arrow_down ()
            self._update_ui ()
            return res
        
        elif key.code in (keysyms.Up, keysyms.KP_Up):
            res = self._editor.arrow_up ()
            self._update_ui ()
            return res
        
        elif key.code in (keysyms.Left, keysyms.KP_Left) and key.mask & modifier.CONTROL_MASK:
            res = self._editor.control_arrow_left ()
            self._update_ui ()
            return res
        
        elif key.code in (keysyms.Right, keysyms.KP_Right) and key.mask & modifier.CONTROL_MASK:
            res = self._editor.control_arrow_right ()
            self._update_ui ()
            return res
        
        elif key.code in (keysyms.Left, keysyms.KP_Left):
            res = self._editor.arrow_left ()
            self._update_ui ()
            return res
        
        elif key.code in (keysyms.Right, keysyms.KP_Right):
            res = self._editor.arrow_right ()
            self._update_ui ()
            return res
        
        elif key.code == keysyms.BackSpace and key.mask & modifier.CONTROL_MASK:
            res = self._editor.control_backspace ()
            self._update_ui ()
            return res
        
        elif key.code == keysyms.BackSpace:
            res = self._editor.backspace ()
            self._update_ui ()
            return res
        
        elif key.code == keysyms.Delete  and key.mask & modifier.CONTROL_MASK:
            res = self._editor.control_delete ()
            self._update_ui ()
            return res
        
        elif key.code == keysyms.Delete:
            res = self._editor.delete ()
            self._update_ui ()
            return res

        elif key.code >= keysyms._1 and key.code <= keysyms._9 and self._editor._candidates[0] and key.mask & modifier.CONTROL_MASK:
            res = self._editor.number (key.code - keysyms._1)
            self._update_ui ()
            return res

        elif key.code >= keysyms._1 and key.code <= keysyms._9 and self._editor._candidates[0] and key.mask & modifier.ALT_MASK:
            res = self._editor.alt_number (key.code - keysyms._1)
            self._update_ui ()
            return res

        elif key.code == keysyms.space:
            self._editor._first = 0

            in_str = self._editor.get_all_input_strings()
            sp_res = self._editor.space ()
            #return (KeyProcessResult,whethercommit,commitstring)
            if sp_res[0]:
                if self._editor.is_down_press:
                    if sp_res[1]:
                        self._editor.is_down_press = False
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
        elif key.mask & modifier.CONTROL_MASK+modifier.ALT_MASK:
            return False

        elif key.mask & modifier.ALT_MASK:
            return False

        elif keysym2unichr(key.code) in self._valid_input_chars or \
                (keysym2unichr(key.code) in u'abcdefghijklmnopqrstuvwxyz!@#$%^&*()-_+=\|}]{[:;/>.<,~`?\'"' ):
            self._editor._first = 0
            if self._auto_commit and ( len(self._editor._chars[0]) == self._ml \
                    or len (self._editor._chars[0]) in self.db.pkeylens ):
                # it is time to direct commit
                sp_res = self._editor.space ()
                #return (whethercommit,commitstring)
                if sp_res[0]:
                    self.commit_string (sp_res[1])
                    #self.add_string_len(sp_res[1])
                    self.db.check_phrase (sp_res[1],sp_res[2])
                    
            res = self._editor.add_input ( keysym2unichr(key.code) )
            if not res:
                if ascii.ispunct (key.code):
                    key_char = keysym2unichr (key.code)
                else:
                    key_char = keysym2unichr (key.code)
                sp_res = self._editor.space ()
                #return (KeyProcessResult,whethercommit,commitstring)
                if sp_res[0]:
                    self.commit_string (sp_res[1] + key_char)
                    #self.add_string_len(sp_res[1])
                    self.db.check_phrase (sp_res[1],sp_res[2])
                    return True
                else:
                    self.commit_string ( key_char )
                    return True
            else:
                if self._auto_commit and self._editor.one_candidate () and \
                        (len(self._editor._chars[0]) == self._ml ):
                    return True

            self._update_ui ()
            return True
        
        elif key.code in self._page_down_keys \
                and self._editor._candidates[0]:
            res = self._editor.page_down()
            self._update_lookup_table ()
            return res

        elif key.code in self._page_up_keys \
                and self._editor._candidates[0]:
            res = self._editor.page_up ()
            self._update_lookup_table ()
            return res
        
        elif key.code >= keysyms._1 and key.code <= keysyms._9 and self._editor._candidates[0]:
            input_keys = self._editor.get_all_input_strings ()
            res = self._editor.number (key.code - keysyms._1)
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
        
        elif key.code == keysyms.Tab:
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
                if self._editor._candidates[0]:
                    self._editor.commit_to_preedit ()
                    commit_string = self._editor.get_preedit_strings ()
                    self.commit_string(commit_string + " " )
                else:
                    commit_string = self._editor.get_all_input_strings ()
                    self.commit_string(commit_string + " ")
                    return True
            return True

        return False
    
    # below for initial test
    def focus_in (self):
        if self._on:
            self._update_ui ()
            #try:
            #    if self._sm_on:
            #        self._sm.Show ()
            #    else:
            #        self._sm.Hide ()
            #except:
            #    pass
    
    def focus_out (self):
        #try:
        #    self._sm.Hide()
        #except:
        #    pass
        pass

    def enable (self):
        #try:
        #    self._sm.Reset()
        #except:
        #    pass
        self._on = True
        self.focus_in()

    def disable (self):
        self.reset()
        #try:
        #    self._sm.Hide()
        #except:
        #    pass
        self._on = False


    def lookup_table_page_up (self):
        if self._editor.page_up ():
            self._update_lookup_table ()
            return True
        return True

    def lookup_table_page_down (self):
        if self._editor.page_down ():
            self._update_lookup_table ()
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
        print "config value for engine %s changed" %self._name
        if name == "tabenable":
            if value == 1:
                self._tab_enable = True
            else:
                self._tab_enable = False
            return
        if name == "pagesize":
            if value >= 1 and value <= 9:
                tabengine._page_size = value
                self._editor._lookup_table = ibus.LookupTable (tabengine._page_size,-1,False)
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
