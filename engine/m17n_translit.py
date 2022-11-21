# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2015-2016 Mike FABIAN <mfabian@redhat.com>
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

'''A module to do transliteration using m17n-lib.
'''

from typing import Dict
from typing import List
from typing import Tuple
from typing import Iterable
from typing import Any
import sys
import ctypes

# pylint: disable=invalid-name
# pylint: disable=too-few-public-methods
# pylint: disable=missing-class-docstring
# pylint: disable=protected-access
class libm17n__MSymbolStruct(ctypes.Structure):
    pass
libm17n__MSymbol = ctypes.POINTER(libm17n__MSymbolStruct)
class libm17n__MPlist(ctypes.Structure):
    pass
class libm17n__MConverter(ctypes.Structure):
    pass
class libm17n__MInputMethod(ctypes.Structure):
    pass
class libm17n__MInputContext(ctypes.Structure):
    pass
class libm17n__MText(ctypes.Structure):
    pass
libm17n__MSymbolStruct._fields_ = [
    ('managing_key', ctypes.c_uint),
    ('name', ctypes.c_char_p),
    ('length', ctypes.c_int),
    ('plist', libm17n__MPlist),
    ('next', ctypes.POINTER(libm17n__MSymbolStruct))]
# pylint: enable=invalid-name
# pylint: enable=too-few-public-methods
# pylint: enable=missing-class-docstring
# pylint: enable=protected-access

# pylint: disable=invalid-name
libm17n__lib = None
libm17n__msymbol = None
libm17n__mplist = None
libm17n__mconv_buffer_converter = None
libm17n__mconv_reset_converter = None
libm17n__mconv_rebind_buffer = None
libm17n__mconv_encode = None
libm17n__minput_open_im = None
libm17n__minput_create_ic = None
libm17n__minput_reset_ic = None
libm17n__minput_filter = None
libm17n__minput_lookup = None
libm17n__mtext = None
libm17n__mtext_len = None
libm17n__Mcoding_utf_8 = None

_utf8_converter = None

libm17n__minput_get_variable = None
libm17n__mplist_key = None
libm17n__mplist_value = None
libm17n__mplist_next = None
libm17n__msymbol_name = None
libm17n__mplist_add = None
libm17n__mplist_length = None
libm17n__mconv_decode_buffer = None
libm17n__minput_config_variable = None
libm17n__minput_save_config = None
# pylint: enable=invalid-name

def mtext_to_string(mtext_pointer: Any) -> str:
    '''Return the text contained in an MText object as a Python string

    :param mtext_pointer: pointer to the MText object to get the text from
    :type mtext_pointer: pointer to an libm17n MText object
    '''
    libm17n__mconv_reset_converter(_utf8_converter) # type: ignore
    # one Unicode character cannot have more than 6 UTF-8 bytes
    # (actually not more than 4 ...)
    bufsize = (libm17n__mtext_len(mtext_pointer) + 1) * 6 # type: ignore
    conversion_buffer = bytes(bufsize)
    libm17n__mconv_rebind_buffer( # type: ignore
        _utf8_converter,
        ctypes.c_char_p(conversion_buffer),
        ctypes.c_int(bufsize))
    libm17n__mconv_encode(_utf8_converter, mtext_pointer) # type: ignore
    # maybe not all of the buffer was really used for the conversion,
    # cut of the unused part:
    conversion_buffer = conversion_buffer[0:conversion_buffer.find(b'\x00')]
    return conversion_buffer.decode('utf-8')

def init() -> None:
    '''Open libm17n and fill global variables for functions and
    variables from libm17n
    '''
    # pylint: disable=invalid-name
    # pylint: disable=global-statement
    global libm17n__lib
    libm17n__lib = ctypes.CDLL('libm17n.so.0', mode = ctypes.RTLD_GLOBAL)
    libm17n__lib.m17n_init()
    global libm17n__mplist
    libm17n__mplist = libm17n__lib.mplist
    libm17n__mplist.argtypes = []
    libm17n__mplist.restype = ctypes.POINTER(libm17n__MPlist)
    global libm17n__mconv_buffer_converter
    libm17n__mconv_buffer_converter = libm17n__lib.mconv_buffer_converter
    libm17n__mconv_buffer_converter.argtypes = [
        libm17n__MSymbol, ctypes.c_char_p, ctypes.c_int]
    libm17n__mconv_buffer_converter.restype = ctypes.POINTER(
        libm17n__MConverter)
    global libm17n__mconv_reset_converter
    libm17n__mconv_reset_converter = libm17n__lib.mconv_reset_converter
    libm17n__mconv_reset_converter.argtypes = [
        ctypes.POINTER(libm17n__MConverter)]
    libm17n__mconv_reset_converter.restype = ctypes.c_int
    global libm17n__mconv_rebind_buffer
    libm17n__mconv_rebind_buffer = libm17n__lib.mconv_rebind_buffer
    libm17n__mconv_rebind_buffer.argtypes = [
        ctypes.POINTER(libm17n__MConverter), ctypes.c_char_p, ctypes.c_int]
    libm17n__mconv_rebind_buffer.restype = ctypes.POINTER(libm17n__MConverter)
    global libm17n__mconv_encode
    libm17n__mconv_encode = libm17n__lib.mconv_encode
    libm17n__mconv_encode.argtypes = [
        ctypes.POINTER(libm17n__MConverter), ctypes.POINTER(libm17n__MText)]
    libm17n__mconv_encode.restype = ctypes.c_int
    global libm17n__msymbol
    libm17n__msymbol = libm17n__lib.msymbol
    libm17n__msymbol.argtypes = [ctypes.c_char_p]
    libm17n__msymbol.restype = libm17n__MSymbol
    global libm17n__minput_open_im
    libm17n__minput_open_im = libm17n__lib.minput_open_im
    libm17n__minput_open_im.argtypes = [
        libm17n__MSymbol, libm17n__MSymbol, ctypes.c_void_p]
    libm17n__minput_open_im.restype = ctypes.POINTER(libm17n__MInputMethod)
    global libm17n__minput_create_ic
    libm17n__minput_create_ic = libm17n__lib.minput_create_ic
    libm17n__minput_create_ic.argtypes = [
        ctypes.POINTER(libm17n__MInputMethod), ctypes.c_void_p]
    libm17n__minput_create_ic.restype = ctypes.POINTER(libm17n__MInputContext)
    global libm17n__minput_reset_ic
    libm17n__minput_reset_ic = libm17n__lib.minput_reset_ic
    libm17n__minput_reset_ic.argtypes = [
        ctypes.POINTER(libm17n__MInputContext)]
    global libm17n__minput_filter
    libm17n__minput_filter = libm17n__lib.minput_filter
    libm17n__minput_filter.argtypes = [
        ctypes.POINTER(libm17n__MInputContext),
        libm17n__MSymbol,
        ctypes.c_void_p]
    libm17n__minput_filter.restype = ctypes.c_int
    global libm17n__minput_lookup
    libm17n__minput_lookup = libm17n__lib.minput_lookup
    libm17n__minput_lookup.argtypes = [
        ctypes.POINTER(libm17n__MInputContext),
        libm17n__MSymbol,
        ctypes.c_void_p,
        ctypes.POINTER(libm17n__MText)]
    libm17n__minput_lookup.restype = ctypes.c_int
    global libm17n__mtext
    libm17n__mtext = libm17n__lib.mtext
    libm17n__mtext.argtypes = []
    libm17n__mtext.restype = ctypes.POINTER(libm17n__MText)
    global libm17n__mtext_len
    libm17n__mtext_len = libm17n__lib.mtext_len
    libm17n__mtext_len.argtypes = [ctypes.POINTER(libm17n__MText)]
    libm17n__mtext_len.restype = ctypes.c_int
    global libm17n__Mcoding_utf_8
    libm17n__Mcoding_utf_8 = libm17n__MSymbol.in_dll(
        ctypes.pythonapi, 'Mcoding_utf_8')
    global _utf8_converter
    _utf8_converter = libm17n__mconv_buffer_converter(
        libm17n__Mcoding_utf_8, ctypes.c_char_p(None), ctypes.c_int(0))
    global libm17n__minput_get_variable
    libm17n__minput_get_variable = libm17n__lib.minput_get_variable
    libm17n__minput_get_variable.argtypes = [
        libm17n__MSymbol, libm17n__MSymbol, libm17n__MSymbol]
    libm17n__minput_get_variable.restype = ctypes.POINTER(libm17n__MPlist)
    global libm17n__mplist_key
    libm17n__mplist_key = libm17n__lib.mplist_key
    libm17n__mplist_key.argtypes = [ctypes.POINTER(libm17n__MPlist)]
    libm17n__mplist_key.restype = libm17n__MSymbol
    global libm17n__mplist_value
    libm17n__mplist_value = libm17n__lib.mplist_value
    libm17n__mplist_value.argtypes = [ctypes.POINTER(libm17n__MPlist)]
    libm17n__mplist_value.restype = ctypes.c_void_p
    global libm17n__mplist_next
    libm17n__mplist_next = libm17n__lib.mplist_next
    libm17n__mplist_next.argtypes = [ctypes.POINTER(libm17n__MPlist)]
    libm17n__mplist_next.restype = ctypes.POINTER(libm17n__MPlist)
    global libm17n__msymbol_name
    libm17n__msymbol_name = libm17n__lib.msymbol_name
    libm17n__msymbol_name.argtypes = [libm17n__MSymbol]
    libm17n__msymbol_name.restype = ctypes.c_char_p
    global libm17n__mplist_add
    libm17n__mplist_add = libm17n__lib.mplist_add
    libm17n__mplist_add.argtypes = [
        ctypes.POINTER(libm17n__MPlist), libm17n__MSymbol, ctypes.c_void_p]
    libm17n__mplist_add.restype = ctypes.POINTER(libm17n__MPlist)
    global libm17n__mplist_length
    libm17n__mplist_length = libm17n__lib.mplist_length
    libm17n__mplist_length.argtypes = [ctypes.POINTER(libm17n__MPlist)]
    libm17n__mplist_length.restype = ctypes.c_int
    global libm17n__mconv_decode_buffer
    libm17n__mconv_decode_buffer = libm17n__lib.mconv_decode_buffer
    libm17n__mconv_decode_buffer.argtypes = [
        libm17n__MSymbol, ctypes.c_char_p, ctypes.c_int]
    libm17n__mconv_decode_buffer.restype = ctypes.POINTER(libm17n__MText)
    global libm17n__minput_config_variable
    libm17n__minput_config_variable = libm17n__lib.minput_config_variable
    libm17n__minput_config_variable.argtypes = [
        libm17n__MSymbol, libm17n__MSymbol, libm17n__MSymbol, ctypes.POINTER(libm17n__MPlist)]
    libm17n__minput_config_variable.restype = ctypes.c_int
    global libm17n__minput_save_config
    libm17n__minput_save_config = libm17n__lib.minput_save_config
    libm17n__minput_save_config.argtypes = []
    libm17n__minput_save_config.restype = ctypes.c_int
    # pylint: enable=invalid-name
    # pylint: enable=global-statement

def fini() -> None:
    '''Cleanup'''
    libm17n__lib.m17n_fini() # type: ignore

class __ModuleInitializer: # pylint: disable=too-few-public-methods,invalid-name
    def __init__(self) -> None:
        init()

    def __del__(self) -> None:
        return

__module_init = __ModuleInitializer()


class Transliterator:
    '''A class for transliterators using libm17n

    If initializing the transliterator fails, for example because a
    non-existing input method was given as the argument, a ValueError
    is raised:

    Examples:

    Russian transliteration:

    >>> trans = Transliterator('ru-translit')
    >>> trans.transliterate(list('y'))
    'ы'
    >>> trans.transliterate(list('yo'))
    'ё'
    >>> trans.transliterate(list('yo y'))
    'ё ы'

    Marathi transliteration:

    >>> trans = Transliterator('mr-itrans')
    >>> trans.transliterate(list('praviN'))
    'प्रविण्'
    >>> trans.transliterate(list('namaste'))
    'नमस्ते'

    Hindi transliteration:

    >>> trans = Transliterator('hi-itrans')
    >>> trans.transliterate(list('namaste'))
    'नमस्ते'

    >>> trans.transliterate(list('. '))
    '। '

    Hindi-Inscript2 uses the AltGr key a lot, 'G-4' is
    the MSymbol name for AltGr-4 and it transliterates
    to something different than just '4':

    >>> trans = Transliterator('hi-inscript2')
    >>> trans.transliterate(['4', 'G-4'])
    '४₹'

    >>> trans = Transliterator('hi-inscript2')
    >>> trans.transliterate(['G-p'])
    'ज़'

    AltGr-3 ('G-3') is not used though in Hindi-Inscript2.
    Therefore, 'G-3' transliterates just as 'G-3':

    >>> trans = Transliterator('hi-inscript2')
    >>> trans.transliterate(['3', 'G-3'])
    '३G-3'

    In mr-inscript2, 'G-1' transliterates to U+200D ZERO WIDTH JOINER
    ('\xe2\x80\x8d' in UTF-8 encoding):

    >>> trans = Transliterator('mr-inscript2')
    >>> trans.transliterate(['j', 'd', 'G-1', '/']).encode('utf-8')
    b'\xe0\xa4\xb0\xe0\xa5\x8d\xe2\x80\x8d\xe0\xa4\xaf'

    >>> trans = Transliterator('t-latn-post')
    >>> trans.transliterate(list('gru"n'))
    'grün'

    >>> trans = Transliterator('NoIME')
    >>> trans.transliterate(['a', 'b', 'c', 'C-c', 'G-4', 'C-α', 'G-α'])
    'abcC-cG-4C-αG-α'

    >>> trans = Transliterator('ko-romaja')
    >>> trans.transliterate(list('annyeonghaseyo'))
    '안녕하세요'

    >>> trans = Transliterator('si-wijesekera')
    >>> trans.transliterate(list('vksIal kjSka '))
    'ඩනිෂ්ක නවීන් '

    '''
    def __init__(self, ime: str) -> None:
        '''Initialize the input method to use for the transliteration

        Raises ValueError if something fails.

        :param ime: Full name of the m17n input method, for example
                    “hi-inscript2” or “t-latn-post”. There is one
                    special input method name “NoIME”. The input method
                    “NoIME” is just a dummy which does not do transliteration
                    at all, it only joins the list of Msymbol names to
                    a string.
        '''
        self._dummy = False
        if ime == 'NoIME':
            self._dummy = True
            return
        self._language = ime.split('-')[0]
        self._name = '-'.join(ime.split('-')[1:])
        self._im = libm17n__minput_open_im( # type: ignore
            libm17n__msymbol(ctypes.c_char_p(self._language.encode('utf-8'))), # type: ignore
            libm17n__msymbol(ctypes.c_char_p(self._name.encode('utf-8'))), # type: ignore
            ctypes.c_void_p(None))
        try:
            _im_contents = self._im.contents
        except ValueError as error: # NULL pointer access
            raise ValueError('minput_open_im() failed') from error
        self._ic = libm17n__minput_create_ic(self._im, ctypes.c_void_p(None)) # type: ignore
        try:
            _ic_contents = self._ic.contents
        except ValueError as error: # NULL pointer access
            raise ValueError('minput_create_ic() failed') from error

    def transliterate(self, msymbol_list: Iterable[str]) -> str:
        '''Transliterate a list of Msymbol names

        :param msymbol_list: A list of strings which are interpreted
                             as the names of Msymbols to transliterate.
                             If the input method has the special name “NoIME”,
                             no transliteration is done, the list of
                             Msymbols is just joined to a single string.
        :type msymbol_list: A list of strings
        :return: The transliteration
        :rtype: string
        '''
        if not isinstance(msymbol_list, list):
            raise ValueError('Argument of transliterate() must be a list.')
        if self._dummy:
            return ''.join(msymbol_list)
        libm17n__minput_reset_ic(self._ic) # type: ignore
        output = ''
        for symbol in msymbol_list + ['nil']:
            _symbol = libm17n__msymbol(symbol.encode('utf-8')) # type: ignore
            retval = libm17n__minput_filter( # type: ignore
                self._ic, _symbol, ctypes.c_void_p(None))
            if retval == 0:
                _mt = libm17n__mtext() # type: ignore
                retval = libm17n__minput_lookup( # type: ignore
                    self._ic, _symbol, ctypes.c_void_p(None), _mt)
                if libm17n__mtext_len(_mt) > 0: # type: ignore
                    output += mtext_to_string(_mt)
                if retval and symbol != 'nil':
                    output += symbol
        return output

    def get_variables(self) -> List[Tuple[str, str, str]]:
        # pylint: disable=line-too-long
        '''
        Gets the optional variables of this transliterator input method

        Examples:

        >>> trans = Transliterator('NoIME')
        >>> trans.get_variables()
        []
        >>> trans = Transliterator('si-wijesekera')
        >>> trans.get_variables()
        [('use-surrounding-text', 'Surrounding text vs. preedit.\\nIf 1, try to use surrounding text.  Otherwise, use preedit.', '0')]
        >>> trans = Transliterator('t-unicode')
        >>> trans.get_variables()
        [('prompt', 'Preedit prompt\\nPrompt string shown in the preedit area while typing hexadecimal numbers.', 'U+')]
        '''
        # pylint: enable=line-too-long
        variables_list: List[Tuple[str, str, str]] = []
        if self._dummy:
            return variables_list
        plist = libm17n__minput_get_variable( # type: ignore
            libm17n__msymbol(self._language.encode('utf-8')), # type: ignore
            libm17n__msymbol(self._name.encode('utf-8')), # type: ignore
            libm17n__msymbol('nil'.encode('utf-8'))) # type: ignore
        while bool(plist): # NULL pointers have a False boolean value
            key = libm17n__mplist_key(plist) # type: ignore
            if not bool(key): # NULL pointers have a False boolean value
                break
            if b'plist' != libm17n__msymbol_name(key.contents): # type: ignore
                break
            ptr = ctypes.cast(libm17n__mplist_value(plist), # type: ignore
                            ctypes.POINTER(libm17n__MPlist))
            key = ctypes.cast(libm17n__mplist_value(ptr), # type: ignore
                              ctypes.POINTER(libm17n__MSymbolStruct))
            if not bool(key): # NULL pointers have a False boolean value
                break
            variable_name = libm17n__msymbol_name( # type: ignore
                key.contents).decode('utf-8')
            ptr = libm17n__mplist_next(ptr) # type: ignore
            variable_description_pointer = ctypes.cast(
                libm17n__mplist_value(ptr), # type: ignore
                ctypes.POINTER(libm17n__MText))
            variable_description = ''
            if bool(variable_description_pointer):
                variable_description = mtext_to_string(
                    variable_description_pointer)
            # Next item in the list is STATUS (we don’t use this)
            ptr = libm17n__mplist_next(ptr) # type: ignore
            mvalue = libm17n__mplist_next(ptr) # type: ignore
            key = libm17n__mplist_key(mvalue) # type: ignore
            if not bool(key):
                break
            key_name = libm17n__msymbol_name(key.contents) # type: ignore
            variable_value = ''
            if key_name == b'symbol':
                variable_value = libm17n__msymbol_name( # type: ignore
                    ctypes.cast(
                        libm17n__mplist_value(mvalue), # type: ignore
                        ctypes.POINTER(libm17n__MSymbolStruct)).contents
                ).decode('utf-8')
            elif key_name == b'mtext':
                variable_value = mtext_to_string(
                    ctypes.cast(libm17n__mplist_value(mvalue), # type: ignore
                            ctypes.POINTER(libm17n__MText)))
            elif key_name == b'integer':
                if libm17n__mplist_value(mvalue) is None: # type: ignore
                    variable_value = '0'
                else:
                    variable_value = str(
                        libm17n__mplist_value(mvalue)) # type: ignore
            elif key_name == b't':
                variable_value = ''
            variables_list.append((variable_name,
                                   variable_description,
                                   variable_value))
            plist = libm17n__mplist_next(plist) # type: ignore
        return variables_list

    def set_variables(self, variables: Dict[str, str]) -> None:
        '''
        Sets the optional variables of this transliterator input method

        Raises ValueError if something fails.

        Examples:

        >>> trans = Transliterator('NoIME')
        >>> trans.set_variables([])

        Only two >> from here on to avoid executing these Examples
        accidentally as doctests and accidentally do real changes
        to the user config file ~/.m17n.d/config.mic:

        >> trans = Transliterator('bn-national-jatiya')
        >> trans.set_variables({'use-automatic-vowel-forming': '1'})

        Setting empty strings as values sets the default values
        (i.e. it removes the setting from the user config file to
        use the global default instead):

        >> trans = Transliterator('bn-national-jatiya')
        >> trans.set_variables({'use-automatic-vowel-forming': ''})

        >> trans = Transliterator('t-unicode')
        >> trans.set_variables({'prompt': 'U+'})

        >> trans = Transliterator('ja-anthy')
        >> trans.set_variables({'input-mode': 'hiragana', 'zen-han': 'hankaku'})
        '''
        if self._dummy or not variables:
            return
        for variable_name, variable_value in variables.items():
            plist = libm17n__minput_get_variable( # type: ignore
                libm17n__msymbol(self._language.encode('utf-8')), # type: ignore
                libm17n__msymbol(self._name.encode('utf-8')), # type: ignore
                libm17n__msymbol(variable_name.encode('utf-8'))) # type: ignore
            if not bool(plist):
                raise ValueError('minput_get_variable() returned NULL')
            key = libm17n__mplist_key(plist) # type: ignore
            if not bool(key):
                raise ValueError('mplist_key(plist) returned NULL')
            if b'plist' != libm17n__msymbol_name(key.contents): # type: ignore
                raise ValueError('msymbol_name(key.contents) is not b"plist"')
            ptr = ctypes.cast(libm17n__mplist_value(plist), # type: ignore
                              ctypes.POINTER(libm17n__MPlist))
            ptr = libm17n__mplist_next(ptr) # type: ignore
            ptr = libm17n__mplist_next(ptr) # type: ignore
            mvalue = libm17n__mplist_next(ptr) # type: ignore
            key = libm17n__mplist_key(mvalue) # type: ignore
            if not bool(key):
                raise ValueError('mplist_key(mvalue) returned NULL')
            key_name = libm17n__msymbol_name(key.contents) # type: ignore
            new_value_plist = libm17n__mplist() # type: ignore
            # If variable_value is the empty string '' the newly
            # created empty new_value_plist is not filled and used
            # empty in minput_config_variable() which cancels any
            # configuration and customization of the variable, and the
            # default value is assigned to the variable.
            if variable_value:
                if key_name == b'symbol':
                    libm17n__mplist_add( # type: ignore
                        new_value_plist,
                        libm17n__msymbol('symbol'.encode('utf-8')), # type: ignore
                        libm17n__msymbol(variable_value.encode('utf-8'))) # type: ignore
                elif key_name == b'mtext':
                    mtext = libm17n__mconv_decode_buffer( # type: ignore
                        libm17n__Mcoding_utf_8,
                        ctypes.c_char_p(variable_value.encode('utf-8')),
                        len(variable_value.encode('utf-8')))
                    libm17n__mplist_add( # type: ignore
                        new_value_plist,
                        libm17n__msymbol('mtext'.encode('utf-8')), # type: ignore
                        mtext)
                elif key_name == b'integer':
                    try:
                        int_value = int(variable_value, 10)
                        libm17n__mplist_add( # type: ignore
                            new_value_plist,
                            libm17n__msymbol('integer'.encode('utf-8')), # type: ignore
                            int_value)
                    except ValueError:
                        new_value_plist = libm17n__mplist() # type: ignore
                else:
                    # This should never happen:
                    raise ValueError(
                        'Variable type is not Msymbol, Minteger, or Mtext')
            retval = libm17n__minput_config_variable( # type: ignore
                libm17n__msymbol(self._language.encode('utf-8')), # type: ignore
                libm17n__msymbol(self._name.encode('utf-8')), # type: ignore
                libm17n__msymbol(variable_name.encode('utf-8')), # type: ignore
                new_value_plist)
            # If the operation was successful, minput_config_variable()
            # returns 0, otherwise -1.
            if retval:
                raise ValueError(
                    f'minput_config_variable() failed with retval = {retval}')
            retval = libm17n__minput_save_config() # type: ignore
            # minput_save_config() returns:
            # - If the operation was successful, 1 is returned
            # - If the per-user customization file is currently locked,
            #   0 is returned.  In that case, the caller may wait for a
            #   while and try again.
            # - If the configuration file is not writable, -1 is returned.
            if retval == 1:
                continue
            if retval == 0:
                raise ValueError(
                    f'minput_save_config() failed with retval = {retval} '
                    '(per-user customization file is locked).')
            if retval == -1:
                raise ValueError(
                    f'minput_save_config() failed with retval = {retval} '
                    '(configuration file not writeable).')
            raise ValueError(
                f'minput_save_config() failed with retval = {retval} '
                '(unknown error, should never happen)')
        return

if __name__ == "__main__":
    import doctest
    (FAILED, _ATTEMPTED) = doctest.testmod()
    sys.exit(FAILED)
