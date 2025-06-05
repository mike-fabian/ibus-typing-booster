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
from typing import NamedTuple
from typing import Iterable
from typing import Any
import sys
import re
import ctypes
import logging
from gi import require_version # type: ignore
# pylint: disable=wrong-import-position
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore
# pylint: enable=wrong-import-position
import itb_util

LOGGER = logging.getLogger('ibus-typing-booster')

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
class libm17n__MText(ctypes.Structure):
    pass
libm17n__MSymbolStruct._fields_ = [
    ('managing_key', ctypes.c_uint),
    ('name', ctypes.c_char_p),
    ('length', ctypes.c_int),
    ('plist', libm17n__MPlist),
    ('next', ctypes.POINTER(libm17n__MSymbolStruct))]
class libm17n__MInputContext__spot(ctypes.Structure):
    _fields_ = [
        ('x', ctypes.c_int),
        ('y', ctypes.c_int),
        ('ascent', ctypes.c_int),
        ('descent', ctypes.c_int),
        ('fontsize', ctypes.c_int),
        ('mt', ctypes.POINTER(libm17n__MText)),
        ('pos', ctypes.c_int)]
class libm17n__MInputContext(ctypes.Structure):
    _fields_ = [
        ('im', ctypes.POINTER(libm17n__MInputMethod)),
        ('produced', ctypes.POINTER(libm17n__MText)),
        ('arg', ctypes.c_void_p),
        ('active', ctypes.c_int),
        ('spot', libm17n__MInputContext__spot),
        ('info', ctypes.c_void_p),
        ('status', ctypes.POINTER(libm17n__MText)),
        ('status_changed', ctypes.c_int),
        ('preedit', ctypes.POINTER(libm17n__MText)),
        ('preedit_changed', ctypes.c_int),
        ('cursor_pos', ctypes.c_int),
        ('cursor_pos_changed', ctypes.c_int),
        ('candidate_list',  ctypes.POINTER(libm17n__MPlist)),
        ('candidate_index', ctypes.c_int),
        ('candidate_from', ctypes.c_int),
        ('candidate_to', ctypes.c_int),
        ('candidate_show', ctypes.c_int),
        ('candidates_changed', ctypes.c_int),
        ('plist', ctypes.POINTER(libm17n__MPlist))]
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

DIGIT_TRANS_TABLE = {
    ord('०'): '0', # U+0966 DEVANAGARI DIGIT ZERO
    ord('१'): '1', # U+0967 DEVANAGARI DIGIT ONE
    ord('२'): '2', # U+0968 DEVANAGARI DIGIT TWO
    ord('३'): '3', # U+0969 DEVANAGARI DIGIT THREE
    ord('४'): '4', # U+096A DEVANAGARI DIGIT FOUR
    ord('५'): '5', # U+096B DEVANAGARI DIGIT FIVE
    ord('६'): '6', # U+096C DEVANAGARI DIGIT SIX
    ord('७'): '7', # U+096D DEVANAGARI DIGIT SEVEN
    ord('८'): '8', # U+096E DEVANAGARI DIGIT EIGHT
    ord('९'): '9', # U+096F DEVANAGARI DIGIT NINE
    ord('০'): '0', # U+09E6 BENGALI DIGIT ZERO
    ord('১'): '1', # U+09E7 BENGALI DIGIT ONE
    ord('২'): '2', # U+09E8 BENGALI DIGIT TWO
    ord('৩'): '3', # U+09E9 BENGALI DIGIT THREE
    ord('৪'): '4', # U+09EA BENGALI DIGIT FOUR
    ord('৫'): '5', # U+09EB BENGALI DIGIT FIVE
    ord('৬'): '6', # U+09EC BENGALI DIGIT SIX
    ord('৭'): '7', # U+09ED BENGALI DIGIT SEVEN
    ord('৮'): '8', # U+09EE BENGALI DIGIT EIGHT
    ord('৯'): '9', # U+09EF BENGALI DIGIT NINE
    ord('૦'): '0', # U+0AE6 GUJARATI DIGIT ZERO
    ord('૧'): '1', # U+0AE7 GUJARATI DIGIT ONE
    ord('૨'): '2', # U+0AE8 GUJARATI DIGIT TWO
    ord('૩'): '3', # U+0AE9 GUJARATI DIGIT THREE
    ord('૪'): '4', # U+0AEA GUJARATI DIGIT FOUR
    ord('૫'): '5', # U+0AEB GUJARATI DIGIT FIVE
    ord('૬'): '6', # U+0AEC GUJARATI DIGIT SIX
    ord('૭'): '7', # U+0AED GUJARATI DIGIT SEVEN
    ord('૮'): '8', # U+0AEE GUJARATI DIGIT EIGHT
    ord('૯'): '9', # U+0AEF GUJARATI DIGIT NINE
    ord('೦'): '0', # U+0CE6 KANNADA DIGIT ZERO
    ord('೧'): '1', # U+0CE7 KANNADA DIGIT ONE
    ord('೨'): '2', # U+0CE8 KANNADA DIGIT TWO
    ord('೩'): '3', # U+0CE9 KANNADA DIGIT THREE
    ord('೪'): '4', # U+0CEA KANNADA DIGIT FOUR
    ord('೫'): '5', # U+0CEB KANNADA DIGIT FIVE
    ord('೬'): '6', # U+0CEC KANNADA DIGIT SIX
    ord('೭'): '7', # U+0CED KANNADA DIGIT SEVEN
    ord('೮'): '8', # U+0CEE KANNADA DIGIT EIGHT
    ord('೯'): '9', # U+0CEF KANNADA DIGIT NINE
    ord('൦'): '0', # U+0D66 MALAYALAM DIGIT ZERO
    ord('൧'): '1', # U+0D67 MALAYALAM DIGIT ONE
    ord('൨'): '2', # U+0D68 MALAYALAM DIGIT TWO
    ord('൩'): '3', # U+0D69 MALAYALAM DIGIT THREE
    ord('൪'): '4', # U+0D6A MALAYALAM DIGIT FOUR
    ord('൫'): '5', # U+0D6B MALAYALAM DIGIT FIVE
    ord('൬'): '6', # U+0D6C MALAYALAM DIGIT SIX
    ord('൭'): '7', # U+0D6D MALAYALAM DIGIT SEVEN
    ord('൮'): '8', # U+0D6E MALAYALAM DIGIT EIGHT
    ord('൯'): '9', # U+0D6F MALAYALAM DIGIT NINE
    ord('୦'): '0', # U+0B66 ORIYA DIGIT ZERO
    ord('୧'): '1', # U+0B67 ORIYA DIGIT ONE
    ord('୨'): '2', # U+0B68 ORIYA DIGIT TWO
    ord('୩'): '3', # U+0B69 ORIYA DIGIT TWO
    ord('୪'): '4', # U+0B6A ORIYA DIGIT FOUR
    ord('୫'): '5', # U+0B6B ORIYA DIGIT FIVE
    ord('୬'): '6', # U+0B6C ORIYA DIGIT SIX
    ord('୭'): '7', # U+0B6D ORIYA DIGIT SEVEN
    ord('୮'): '8', # U+0B6E ORIYA DIGIT EIGHT
    ord('୯'): '9', # U+0B6F ORIYA DIGIT NINE
    ord('੦'): '0', # U+0A66 GURMUKHI DIGIT ZERO
    ord('੧'): '1', # U+0A67 GURMUKHI DIGIT ONE
    ord('੨'): '2', # U+0A68 GURMUKHI DIGIT TWO
    ord('੩'): '3', # U+0A69 GURMUKHI DIGIT THREE
    ord('੪'): '4', # U+0A6A GURMUKHI DIGIT FOUR
    ord('੫'): '5', # U+0A6B GURMUKHI DIGIT FIVE
    ord('੬'): '6', # U+0A6C GURMUKHI DIGIT SIX
    ord('੭'): '7', # U+0A6D GURMUKHI DIGIT SEVEN
    ord('੮'): '8', # U+0A6E GURMUKHI DIGIT EIGHT
    ord('੯'): '9', # U+0A6F GURMUKHI DIGIT NINE
    ord('௦'): '0', # U+0BE6 TAMIL DIGIT ZERO
    ord('௧'): '1', # U+0BE7 TAMIL DIGIT ONE
    ord('௨'): '2', # U+0BE8 TAMIL DIGIT TWO
    ord('௩'): '3', # U+0BE9 TAMIL DIGIT THREE
    ord('௪'): '4', # U+0BEA TAMIL DIGIT FOUR
    ord('௫'): '5', # U+0BEB TAMIL DIGIT FIVE
    ord('௬'): '6', # U+0BEC TAMIL DIGIT SIX
    ord('௭'): '7', # U+0BED TAMIL DIGIT SEVEN
    ord('௮'): '8', # U+0BEE TAMIL DIGIT EIGHT
    ord('௯'): '9', # U+0BEF TAMIL DIGIT NINE
    ord('౦'): '0', # U+0C66 TELUGU DIGIT ZERO
    ord('౧'): '1', # U+0C67 TELUGU DIGIT ONE
    ord('౨'): '2', # U+0C68 TELUGU DIGIT TWO
    ord('౩'): '3', # U+0C69 TELUGU DIGIT THREE
    ord('౪'): '4', # U+0C6A TELUGU DIGIT FOUR
    ord('౫'): '5', # U+0C6B TELUGU DIGIT FIVE
    ord('౬'): '6', # U+0C6C TELUGU DIGIT SIX
    ord('౭'): '7', # U+0C6D TELUGU DIGIT SEVEN
    ord('౮'): '8', # U+0C6E TELUGU DIGIT EIGHT
    ord('౯'): '9', # U+0C6F TELUGU DIGIT NINE
    ord('٠'): '0', # U+0660 ARABIC-INDIC DIGIT ZERO
    ord('١'): '1', # U+0661 ARABIC-INDIC DIGIT ONE
    ord('٢'): '0', # U+0662 ARABIC-INDIC DIGIT TWO
    ord('٣'): '3', # U+0663 ARABIC-INDIC DIGIT THREE
    ord('٤'): '4', # U+0664 ARABIC-INDIC DIGIT FOUR
    ord('٥'): '5', # U+0665 ARABIC-INDIC DIGIT FIVE
    ord('٦'): '6', # U+0666 ARABIC-INDIC DIGIT SIX
    ord('٧'): '7', # U+0667 ARABIC-INDIC DIGIT SEVEN
    ord('٨'): '8', # U+0668 ARABIC-INDIC DIGIT EIGHT
    ord('٩'): '9', # U+0669 ARABIC-INDIC DIGIT NINE
    ord('۰'): '0', # U+06F0 EXTENDED ARABIC-INDIC DIGIT ZERO
    ord('۱'): '1', # U+06F1 EXTENDED ARABIC-INDIC DIGIT ONE
    ord('۲'): '2', # U+06F2 EXTENDED ARABIC-INDIC DIGIT TWO
    ord('۳'): '3', # U+06F3 EXTENDED ARABIC-INDIC DIGIT THREE
    ord('۴'): '4', # U+06F4 EXTENDED ARABIC-INDIC DIGIT FOUR
    ord('۵'): '5', # U+06F5 EXTENDED ARABIC-INDIC DIGIT FIVE
    ord('۶'): '6', # U+06F6 EXTENDED ARABIC-INDIC DIGIT SIX
    ord('۷'): '7', # U+06F7 EXTENDED ARABIC-INDIC DIGIT SEVEN
    ord('۸'): '8', # U+06F8 EXTENDED ARABIC-INDIC DIGIT EIGHT
    ord('۹'): '9', # U+06F9 EXTENDED ARABIC-INDIC DIGIT NINE
    ord('߀'): '0', # U+07C0 NKO DIGIT ZERO
    ord('߁'): '1', # U+07C1 NKO DIGIT ONE
    ord('߂'): '2', # U+07C2 NKO DIGIT TWO
    ord('߃'): '3', # U+07C3 NKO DIGIT THREE
    ord('߄'): '4', # U+07C4 NKO DIGIT FOUR
    ord('߅'): '5', # U+07C5 NKO DIGIT FIVE
    ord('߆'): '6', # U+07C6 NKO DIGIT SIX
    ord('߇'): '7', # U+07C7 NKO DIGIT SEVEN
    ord('߈'): '8', # U+07C8 NKO DIGIT EIGHT
    ord('߉'): '9', # U+07C9 NKO DIGIT NINE
    ord('෦'): '0', # U+0DE6 SINHALA LITH DIGIT ZERO
    ord('෧'): '1', # U+0DE7 SINHALA LITH DIGIT ONE
    ord('෨'): '2', # U+0DE8 SINHALA LITH DIGIT TWO
    ord('෩'): '3', # U+0DE9 SINHALA LITH DIGIT THREE
    ord('෪'): '4', # U+0DEA SINHALA LITH DIGIT FOUR
    ord('෫'): '5', # U+0DEB SINHALA LITH DIGIT FIVE
    ord('෬'): '6', # U+0DEC SINHALA LITH DIGIT SIX
    ord('෭'): '7', # U+0DED SINHALA LITH DIGIT SEVEN
    ord('෮'): '8', # U+0DEE SINHALA LITH DIGIT EIGHT
    ord('෯'): '9', # U+0DEF SINHALA LITH DIGIT NINE
    ord('๐'): '0', # U+0E50 THAI DIGIT ZERO
    ord('๑'): '1', # U+0E51 THAI DIGIT ONE
    ord('๒'): '2', # U+0E52 THAI DIGIT TWO
    ord('๓'): '3', # U+0E53 THAI DIGIT THREE
    ord('๔'): '4', # U+0E54 THAI DIGIT FOUR
    ord('๕'): '5', # U+0E55 THAI DIGIT FIVE
    ord('๖'): '6', # U+0E56 THAI DIGIT SIX
    ord('๗'): '7', # U+0E57 THAI DIGIT SEVEN
    ord('๘'): '8', # U+0E58 THAI DIGIT EIGHT
    ord('๙'): '9', # U+0E59 THAI DIGIT NINE
    ord('໐'): '0', # U+0ED0 LAO DIGIT ZERO
    ord('໑'): '1', # U+0ED1 LAO DIGIT ONE
    ord('໒'): '2', # U+0ED2 LAO DIGIT TWO
    ord('໓'): '3', # U+0ED3 LAO DIGIT THREE
    ord('໔'): '4', # U+0ED4 LAO DIGIT FOUR
    ord('໕'): '5', # U+0ED5 LAO DIGIT FIVE
    ord('໖'): '6', # U+0ED6 LAO DIGIT SIX
    ord('໗'): '7', # U+0ED7 LAO DIGIT SEVEN
    ord('໘'): '8', # U+0ED8 LAO DIGIT EIGHT
    ord('໙'): '9', # U+0ED9 LAO DIGIT NINE
    ord('༠'): '0', # U+0F20 TIBETAN DIGIT ZERO
    ord('༡'): '1', # U+0F21 TIBETAN DIGIT ONE
    ord('༢'): '2', # U+0F22 TIBETAN DIGIT TWO
    ord('༣'): '3', # U+0F23 TIBETAN DIGIT THREE
    ord('༤'): '4', # U+0F24 TIBETAN DIGIT FOUR
    ord('༥'): '5', # U+0F25 TIBETAN DIGIT FIVE
    ord('༦'): '6', # U+0F26 TIBETAN DIGIT SIX
    ord('༧'): '7', # U+0F27 TIBETAN DIGIT SEVEN
    ord('༨'): '8', # U+0F28 TIBETAN DIGIT EIGHT
    ord('༩'): '9', # U+0F29 TIBETAN DIGIT NINE
    ord('၀'): '0', # U+1040 MYANMAR DIGIT ZERO
    ord('၁'): '1', # U+1041 MYANMAR DIGIT ONE
    ord('၂'): '2', # U+1042 MYANMAR DIGIT TWO
    ord('၃'): '3', # U+1043 MYANMAR DIGIT THREE
    ord('၄'): '4', # U+1044 MYANMAR DIGIT FOUR
    ord('၅'): '5', # U+1045 MYANMAR DIGIT FIVE
    ord('၆'): '6', # U+1046 MYANMAR DIGIT SIX
    ord('၇'): '7', # U+1047 MYANMAR DIGIT SEVEN
    ord('၈'): '8', # U+1048 MYANMAR DIGIT EIGHT
    ord('၉'): '9', # U+1049 MYANMAR DIGIT NINE
    ord('႐'): '0', # U+1090 MYANMAR SHAN DIGIT ZERO
    ord('႑'): '1', # U+1091 MYANMAR SHAN DIGIT ONE
    ord('႒'): '2', # U+1092 MYANMAR SHAN DIGIT TWO
    ord('႓'): '3', # U+1093 MYANMAR SHAN DIGIT THREE
    ord('႔'): '4', # U+1094 MYANMAR SHAN DIGIT FOUR
    ord('႕'): '5', # U+1095 MYANMAR SHAN DIGIT FIVE
    ord('႖'): '6', # U+1096 MYANMAR SHAN DIGIT SIX
    ord('႗'): '7', # U+1097 MYANMAR SHAN DIGIT SEVEN
    ord('႘'): '8', # U+1098 MYANMAR SHAN DIGIT EIGHT
    ord('႙'): '9', # U+1099 MYANMAR SHAN DIGIT NINE
    ord('០'): '0', # U+17E0 KHMER DIGIT ZERO
    ord('១'): '1', # U+17E1 KHMER DIGIT ONE
    ord('២'): '2', # U+17E2 KHMER DIGIT TWO
    ord('៣'): '3', # U+17E3 KHMER DIGIT THREE
    ord('៤'): '4', # U+17E4 KHMER DIGIT FOUR
    ord('៥'): '5', # U+17E5 KHMER DIGIT FIVE
    ord('៦'): '6', # U+17E6 KHMER DIGIT SIX
    ord('៧'): '7', # U+17E7 KHMER DIGIT SEVEN
    ord('៨'): '8', # U+17E8 KHMER DIGIT EIGHT
    ord('៩'): '9', # U+17E9 KHMER DIGIT NINE
    ord('᠐'): '0', # U+1810 MONGOLIAN DIGIT ZERO
    ord('᠑'): '1', # U+1811 MONGOLIAN DIGIT ONE
    ord('᠒'): '2', # U+1812 MONGOLIAN DIGIT TWO
    ord('᠓'): '3', # U+1813 MONGOLIAN DIGIT THREE
    ord('᠔'): '4', # U+1814 MONGOLIAN DIGIT FOUR
    ord('᠕'): '5', # U+1815 MONGOLIAN DIGIT FIVE
    ord('᠖'): '6', # U+1816 MONGOLIAN DIGIT SIX
    ord('᠗'): '7', # U+1817 MONGOLIAN DIGIT SEVEN
    ord('᠘'): '8', # U+1818 MONGOLIAN DIGIT EIGHT
    ord('᠙'): '9', # U+1819 MONGOLIAN DIGIT NINE
    ord('᥆'): '0', # U+1946 LIMBU DIGIT ZERO
    ord('᥇'): '1', # U+1947 LIMBU DIGIT ONE
    ord('᥈'): '2', # U+1948 LIMBU DIGIT TWO
    ord('᥉'): '3', # U+1949 LIMBU DIGIT THREE
    ord('᥊'): '4', # U+194A LIMBU DIGIT FOUR
    ord('᥋'): '5', # U+194B LIMBU DIGIT FIVE
    ord('᥌'): '6', # U+194C LIMBU DIGIT SIX
    ord('᥍'): '7', # U+194D LIMBU DIGIT SEVEN
    ord('᥎'): '8', # U+194E LIMBU DIGIT EIGHT
    ord('᥏'): '9', # U+194F LIMBU DIGIT NINE
    ord('᧐'): '0', # U+19D0 NEW TAI LUE DIGIT ZERO
    ord('᧑'): '1', # U+19D1 NEW TAI LUE DIGIT ONE
    ord('᧒'): '2', # U+19D2 NEW TAI LUE DIGIT TWO
    ord('᧓'): '3', # U+19D3 NEW TAI LUE DIGIT THREE
    ord('᧔'): '4', # U+19D4 NEW TAI LUE DIGIT FOUR
    ord('᧕'): '5', # U+19D5 NEW TAI LUE DIGIT FIVE
    ord('᧖'): '6', # U+19D6 NEW TAI LUE DIGIT SIX
    ord('᧗'): '7', # U+19D7 NEW TAI LUE DIGIT SEVEN
    ord('᧘'): '8', # U+19D8 NEW TAI LUE DIGIT EIGHT
    ord('᧙'): '9', # U+19D9 NEW TAI LUE DIGIT NINE
    ord('᪀'): '0', # U+1A80 TAI THAM HORA DIGIT ZERO
    ord('᪁'): '1', # U+1A81 TAI THAM HORA DIGIT ONE
    ord('᪂'): '2', # U+1A82 TAI THAM HORA DIGIT TWO
    ord('᪃'): '3', # U+1A83 TAI THAM HORA DIGIT THREE
    ord('᪄'): '4', # U+1A84 TAI THAM HORA DIGIT FOUR
    ord('᪅'): '5', # U+1A85 TAI THAM HORA DIGIT FIVE
    ord('᪆'): '6', # U+1A86 TAI THAM HORA DIGIT SIX
    ord('᪇'): '7', # U+1A87 TAI THAM HORA DIGIT SEVEN
    ord('᪈'): '8', # U+1A88 TAI THAM HORA DIGIT EIGHT
    ord('᪉'): '9', # U+1A89 TAI THAM HORA DIGIT NINE
    ord('᪐'): '0', # U+1A90 TAI THAM THAM DIGIT ZERO
    ord('᪑'): '1', # U+1A91 TAI THAM THAM DIGIT ONE
    ord('᪒'): '2', # U+1A92 TAI THAM THAM DIGIT TWO
    ord('᪓'): '3', # U+1A93 TAI THAM THAM DIGIT THREE
    ord('᪔'): '4', # U+1A94 TAI THAM THAM DIGIT FOUR
    ord('᪕'): '5', # U+1A95 TAI THAM THAM DIGIT FIVE
    ord('᪖'): '6', # U+1A96 TAI THAM THAM DIGIT SIX
    ord('᪗'): '7', # U+1A97 TAI THAM THAM DIGIT SEVEN
    ord('᪘'): '8', # U+1A98 TAI THAM THAM DIGIT EIGHT
    ord('᪙'): '9', # U+1A99 TAI THAM THAM DIGIT NINE
    ord('᭐'): '0', # U+1B50 BALINESE DIGIT ZERO
    ord('᭑'): '1', # U+1B51 BALINESE DIGIT ONE
    ord('᭒'): '2', # U+1B52 BALINESE DIGIT TWO
    ord('᭓'): '3', # U+1B53 BALINESE DIGIT THREE
    ord('᭔'): '4', # U+1B54 BALINESE DIGIT FOUR
    ord('᭕'): '5', # U+1B55 BALINESE DIGIT FIVE
    ord('᭖'): '6', # U+1B56 BALINESE DIGIT SIX
    ord('᭗'): '7', # U+1B57 BALINESE DIGIT SEVEN
    ord('᭘'): '8', # U+1B58 BALINESE DIGIT EIGHT
    ord('᭙'): '9', # U+1B59 BALINESE DIGIT NINE
    ord('᮰'): '0', # U+1BB0 SUNDANESE DIGIT ZERO
    ord('᮱'): '1', # U+1BB1 SUNDANESE DIGIT ONE
    ord('᮲'): '2', # U+1BB2 SUNDANESE DIGIT TWO
    ord('᮳'): '3', # U+1BB3 SUNDANESE DIGIT THREE
    ord('᮴'): '4', # U+1BB4 SUNDANESE DIGIT FOUR
    ord('᮵'): '5', # U+1BB5 SUNDANESE DIGIT FIVE
    ord('᮶'): '6', # U+1BB6 SUNDANESE DIGIT SIX
    ord('᮷'): '7', # U+1BB7 SUNDANESE DIGIT SEVEN
    ord('᮸'): '8', # U+1BB8 SUNDANESE DIGIT EIGHT
    ord('᮹'): '9', # U+1BB9 SUNDANESE DIGIT NINE
    ord('᱀'): '0', # U+1C40 LEPCHA DIGIT ZERO
    ord('᱁'): '1', # U+1C41 LEPCHA DIGIT ONE
    ord('᱂'): '2', # U+1C42 LEPCHA DIGIT TWO
    ord('᱃'): '3', # U+1C43 LEPCHA DIGIT THREE
    ord('᱄'): '4', # U+1C44 LEPCHA DIGIT FOUR
    ord('᱅'): '5', # U+1C45 LEPCHA DIGIT FIVE
    ord('᱆'): '6', # U+1C46 LEPCHA DIGIT SIX
    ord('᱇'): '7', # U+1C47 LEPCHA DIGIT SEVEN
    ord('᱈'): '8', # U+1C48 LEPCHA DIGIT EIGHT
    ord('᱉'): '9', # U+1C49 LEPCHA DIGIT NINE
    ord('᱐'): '0', # U+1C50 OL CHIKI DIGIT ZERO
    ord('᱑'): '1', # U+1C51 OL CHIKI DIGIT ONE
    ord('᱒'): '2', # U+1C52 OL CHIKI DIGIT TWO
    ord('᱓'): '3', # U+1C53 OL CHIKI DIGIT THREE
    ord('᱔'): '4', # U+1C54 OL CHIKI DIGIT FOUR
    ord('᱕'): '5', # U+1C55 OL CHIKI DIGIT FIVE
    ord('᱖'): '6', # U+1C56 OL CHIKI DIGIT SIX
    ord('᱗'): '7', # U+1C57 OL CHIKI DIGIT SEVEN
    ord('᱘'): '8', # U+1C58 OL CHIKI DIGIT EIGHT
    ord('᱙'): '9', # U+1C59 OL CHIKI DIGIT NINE
    ord('꘠'): '0', # U+A620 VAI DIGIT ZERO
    ord('꘡'): '1', # U+A621 VAI DIGIT ONE
    ord('꘢'): '2', # U+A622 VAI DIGIT TWO
    ord('꘣'): '3', # U+A623 VAI DIGIT THREE
    ord('꘤'): '4', # U+A624 VAI DIGIT FOUR
    ord('꘥'): '5', # U+A625 VAI DIGIT FIVE
    ord('꘦'): '6', # U+A626 VAI DIGIT SIX
    ord('꘧'): '7', # U+A627 VAI DIGIT SEVEN
    ord('꘨'): '8', # U+A628 VAI DIGIT EIGHT
    ord('꘩'): '9', # U+A629 VAI DIGIT NINE
    ord('꣐'): '0', # U+A8D0 SAURASHTRA DIGIT ZERO
    ord('꣑'): '1', # U+A8D1 SAURASHTRA DIGIT ONE
    ord('꣒'): '2', # U+A8D2 SAURASHTRA DIGIT TWO
    ord('꣓'): '3', # U+A8D3 SAURASHTRA DIGIT THREE
    ord('꣔'): '4', # U+A8D4 SAURASHTRA DIGIT FOUR
    ord('꣕'): '5', # U+A8D5 SAURASHTRA DIGIT FIVE
    ord('꣖'): '6', # U+A8D6 SAURASHTRA DIGIT SIX
    ord('꣗'): '7', # U+A8D7 SAURASHTRA DIGIT SEVEN
    ord('꣘'): '8', # U+A8D8 SAURASHTRA DIGIT EIGHT
    ord('꣙'): '9', # U+A8D9 SAURASHTRA DIGIT NINE
    ord('꤀'): '0', # U+A900 KAYAH LI DIGIT ZERO
    ord('꤁'): '1', # U+A901 KAYAH LI DIGIT ONE
    ord('꤂'): '2', # U+A902 KAYAH LI DIGIT TWO
    ord('꤃'): '3', # U+A903 KAYAH LI DIGIT THREE
    ord('꤄'): '4', # U+A904 KAYAH LI DIGIT FOUR
    ord('꤅'): '5', # U+A905 KAYAH LI DIGIT FIVE
    ord('꤆'): '6', # U+A906 KAYAH LI DIGIT SIX
    ord('꤇'): '7', # U+A907 KAYAH LI DIGIT SEVEN
    ord('꤈'): '8', # U+A908 KAYAH LI DIGIT EIGHT
    ord('꤉'): '9', # U+A909 KAYAH LI DIGIT NINE
    ord('꧐'): '0', # U+A9D0 JAVANESE DIGIT ZERO
    ord('꧑'): '1', # U+A9D1 JAVANESE DIGIT ONE
    ord('꧒'): '2', # U+A9D2 JAVANESE DIGIT TWO
    ord('꧓'): '3', # U+A9D3 JAVANESE DIGIT THREE
    ord('꧔'): '4', # U+A9D4 JAVANESE DIGIT FOUR
    ord('꧕'): '5', # U+A9D5 JAVANESE DIGIT FIVE
    ord('꧖'): '6', # U+A9D6 JAVANESE DIGIT SIX
    ord('꧗'): '7', # U+A9D7 JAVANESE DIGIT SEVEN
    ord('꧘'): '8', # U+A9D8 JAVANESE DIGIT EIGHT
    ord('꧙'): '9', # U+A9D9 JAVANESE DIGIT NINE
    ord('꧰'): '0', # U+A9F0 MYANMAR TAI LAING DIGIT ZERO
    ord('꧱'): '1', # U+A9F1 MYANMAR TAI LAING DIGIT ONE
    ord('꧲'): '2', # U+A9F2 MYANMAR TAI LAING DIGIT TWO
    ord('꧳'): '3', # U+A9F3 MYANMAR TAI LAING DIGIT THREE
    ord('꧴'): '4', # U+A9F4 MYANMAR TAI LAING DIGIT FOUR
    ord('꧵'): '5', # U+A9F5 MYANMAR TAI LAING DIGIT FIVE
    ord('꧶'): '6', # U+A9F6 MYANMAR TAI LAING DIGIT SIX
    ord('꧷'): '7', # U+A9F7 MYANMAR TAI LAING DIGIT SEVEN
    ord('꧸'): '8', # U+A9F8 MYANMAR TAI LAING DIGIT EIGHT
    ord('꧹'): '9', # U+A9F9 MYANMAR TAI LAING DIGIT NINE
    ord('꩐'): '0', # U+AA50 CHAM DIGIT ZERO
    ord('꩑'): '1', # U+AA51 CHAM DIGIT ONE
    ord('꩒'): '2', # U+AA52 CHAM DIGIT TWO
    ord('꩓'): '3', # U+AA53 CHAM DIGIT THREE
    ord('꩔'): '4', # U+AA54 CHAM DIGIT FOUR
    ord('꩕'): '5', # U+AA55 CHAM DIGIT FIVE
    ord('꩖'): '6', # U+AA56 CHAM DIGIT SIX
    ord('꩗'): '7', # U+AA57 CHAM DIGIT SEVEN
    ord('꩘'): '8', # U+AA58 CHAM DIGIT EIGHT
    ord('꩙'): '9', # U+AA59 CHAM DIGIT NINE
    ord('꯰'): '0', # U+ABF0 MEETEI MAYEK DIGIT ZERO
    ord('꯱'): '1', # U+ABF1 MEETEI MAYEK DIGIT ONE
    ord('꯲'): '2', # U+ABF2 MEETEI MAYEK DIGIT TWO
    ord('꯳'): '3', # U+ABF3 MEETEI MAYEK DIGIT THREE
    ord('꯴'): '4', # U+ABF4 MEETEI MAYEK DIGIT FOUR
    ord('꯵'): '5', # U+ABF5 MEETEI MAYEK DIGIT FIVE
    ord('꯶'): '6', # U+ABF6 MEETEI MAYEK DIGIT SIX
    ord('꯷'): '7', # U+ABF7 MEETEI MAYEK DIGIT SEVEN
    ord('꯸'): '8', # U+ABF8 MEETEI MAYEK DIGIT EIGHT
    ord('꯹'): '9', # U+ABF9 MEETEI MAYEK DIGIT NINE
    ord('𐒠'): '0', # U+104A0 OSMANYA DIGIT ZERO
    ord('𐒡'): '1', # U+104A1 OSMANYA DIGIT ONE
    ord('𐒢'): '2', # U+104A2 OSMANYA DIGIT TWO
    ord('𐒣'): '3', # U+104A3 OSMANYA DIGIT THREE
    ord('𐒤'): '4', # U+104A4 OSMANYA DIGIT FOUR
    ord('𐒥'): '5', # U+104A5 OSMANYA DIGIT FIVE
    ord('𐒦'): '6', # U+104A6 OSMANYA DIGIT SIX
    ord('𐒧'): '7', # U+104A7 OSMANYA DIGIT SEVEN
    ord('𐒨'): '8', # U+104A8 OSMANYA DIGIT EIGHT
    ord('𐒩'): '9', # U+104A9 OSMANYA DIGIT NINE
    ord('𐴰'): '0', # U+10D30 HANIFI ROHINGYA DIGIT ZERO
    ord('𐴱'): '1', # U+10D31 HANIFI ROHINGYA DIGIT ONE
    ord('𐴲'): '2', # U+10D32 HANIFI ROHINGYA DIGIT TWO
    ord('𐴳'): '3', # U+10D33 HANIFI ROHINGYA DIGIT THREE
    ord('𐴴'): '4', # U+10D34 HANIFI ROHINGYA DIGIT FOUR
    ord('𐴵'): '5', # U+10D35 HANIFI ROHINGYA DIGIT FIVE
    ord('𐴶'): '6', # U+10D36 HANIFI ROHINGYA DIGIT SIX
    ord('𐴷'): '7', # U+10D37 HANIFI ROHINGYA DIGIT SEVEN
    ord('𐴸'): '8', # U+10D38 HANIFI ROHINGYA DIGIT EIGHT
    ord('𐴹'): '9', # U+10D39 HANIFI ROHINGYA DIGIT NINE
    # ord('𐹠'): '0', # U+10E60 RUMI DIGIT ONE
    # ord('𐹡'): '1', # U+10E61 RUMI DIGIT TWO
    # ord('𐹢'): '2', # U+10E62 RUMI DIGIT THREE
    # ord('𐹣'): '3', # U+10E63 RUMI DIGIT FOUR
    # ord('𐹤'): '4', # U+10E64 RUMI DIGIT FIVE
    # ord('𐹥'): '5', # U+10E65 RUMI DIGIT SIX
    # ord('𐹦'): '6', # U+10E66 RUMI DIGIT SEVEN
    # ord('𐹧'): '7', # U+10E67 RUMI DIGIT EIGHT
    # ord('𐹨'): '8', # U+10E68 RUMI DIGIT NINE
    ord('𑁦'): '6', # U+11066 BRAHMI DIGIT ZERO
    ord('𑁧'): '7', # U+11067 BRAHMI DIGIT ONE
    ord('𑁨'): '8', # U+11068 BRAHMI DIGIT TWO
    ord('𑁩'): '9', # U+11069 BRAHMI DIGIT THREE
    ord('𑁪'): 'A', # U+1106A BRAHMI DIGIT FOUR
    ord('𑁫'): 'B', # U+1106B BRAHMI DIGIT FIVE
    ord('𑁬'): 'C', # U+1106C BRAHMI DIGIT SIX
    ord('𑁭'): 'D', # U+1106D BRAHMI DIGIT SEVEN
    ord('𑁮'): 'E', # U+1106E BRAHMI DIGIT EIGHT
    ord('𑁯'): 'F', # U+1106F BRAHMI DIGIT NINE
    ord('𑃰'): '0', # U+110F0 SORA SOMPENG DIGIT ZERO
    ord('𑃱'): '1', # U+110F1 SORA SOMPENG DIGIT ONE
    ord('𑃲'): '2', # U+110F2 SORA SOMPENG DIGIT TWO
    ord('𑃳'): '3', # U+110F3 SORA SOMPENG DIGIT THREE
    ord('𑃴'): '4', # U+110F4 SORA SOMPENG DIGIT FOUR
    ord('𑃵'): '5', # U+110F5 SORA SOMPENG DIGIT FIVE
    ord('𑃶'): '6', # U+110F6 SORA SOMPENG DIGIT SIX
    ord('𑃷'): '7', # U+110F7 SORA SOMPENG DIGIT SEVEN
    ord('𑃸'): '8', # U+110F8 SORA SOMPENG DIGIT EIGHT
    ord('𑃹'): '9', # U+110F9 SORA SOMPENG DIGIT NINE
    ord('𑄶'): '6', # U+11136 CHAKMA DIGIT ZERO
    ord('𑄷'): '7', # U+11137 CHAKMA DIGIT ONE
    ord('𑄸'): '8', # U+11138 CHAKMA DIGIT TWO
    ord('𑄹'): '9', # U+11139 CHAKMA DIGIT THREE
    ord('𑄺'): 'A', # U+1113A CHAKMA DIGIT FOUR
    ord('𑄻'): 'B', # U+1113B CHAKMA DIGIT FIVE
    ord('𑄼'): 'C', # U+1113C CHAKMA DIGIT SIX
    ord('𑄽'): 'D', # U+1113D CHAKMA DIGIT SEVEN
    ord('𑄾'): 'E', # U+1113E CHAKMA DIGIT EIGHT
    ord('𑄿'): 'F', # U+1113F CHAKMA DIGIT NINE
    ord('𑇐'): '0', # U+111D0 SHARADA DIGIT ZERO
    ord('𑇑'): '1', # U+111D1 SHARADA DIGIT ONE
    ord('𑇒'): '2', # U+111D2 SHARADA DIGIT TWO
    ord('𑇓'): '3', # U+111D3 SHARADA DIGIT THREE
    ord('𑇔'): '4', # U+111D4 SHARADA DIGIT FOUR
    ord('𑇕'): '5', # U+111D5 SHARADA DIGIT FIVE
    ord('𑇖'): '6', # U+111D6 SHARADA DIGIT SIX
    ord('𑇗'): '7', # U+111D7 SHARADA DIGIT SEVEN
    ord('𑇘'): '8', # U+111D8 SHARADA DIGIT EIGHT
    ord('𑇙'): '9', # U+111D9 SHARADA DIGIT NINE
    ord('𑋰'): '0', # U+112F0 KHUDAWADI DIGIT ZERO
    ord('𑋱'): '1', # U+112F1 KHUDAWADI DIGIT ONE
    ord('𑋲'): '2', # U+112F2 KHUDAWADI DIGIT TWO
    ord('𑋳'): '3', # U+112F3 KHUDAWADI DIGIT THREE
    ord('𑋴'): '4', # U+112F4 KHUDAWADI DIGIT FOUR
    ord('𑋵'): '5', # U+112F5 KHUDAWADI DIGIT FIVE
    ord('𑋶'): '6', # U+112F6 KHUDAWADI DIGIT SIX
    ord('𑋷'): '7', # U+112F7 KHUDAWADI DIGIT SEVEN
    ord('𑋸'): '8', # U+112F8 KHUDAWADI DIGIT EIGHT
    ord('𑋹'): '9', # U+112F9 KHUDAWADI DIGIT NINE
    ord('𑑐'): '0', # U+11450 NEWA DIGIT ZERO
    ord('𑑑'): '1', # U+11451 NEWA DIGIT ONE
    ord('𑑒'): '2', # U+11452 NEWA DIGIT TWO
    ord('𑑓'): '3', # U+11453 NEWA DIGIT THREE
    ord('𑑔'): '4', # U+11454 NEWA DIGIT FOUR
    ord('𑑕'): '5', # U+11455 NEWA DIGIT FIVE
    ord('𑑖'): '6', # U+11456 NEWA DIGIT SIX
    ord('𑑗'): '7', # U+11457 NEWA DIGIT SEVEN
    ord('𑑘'): '8', # U+11458 NEWA DIGIT EIGHT
    ord('𑑙'): '9', # U+11459 NEWA DIGIT NINE
    ord('𑓐'): '0', # U+114D0 TIRHUTA DIGIT ZERO
    ord('𑓑'): '1', # U+114D1 TIRHUTA DIGIT ONE
    ord('𑓒'): '2', # U+114D2 TIRHUTA DIGIT TWO
    ord('𑓓'): '3', # U+114D3 TIRHUTA DIGIT THREE
    ord('𑓔'): '4', # U+114D4 TIRHUTA DIGIT FOUR
    ord('𑓕'): '5', # U+114D5 TIRHUTA DIGIT FIVE
    ord('𑓖'): '6', # U+114D6 TIRHUTA DIGIT SIX
    ord('𑓗'): '7', # U+114D7 TIRHUTA DIGIT SEVEN
    ord('𑓘'): '8', # U+114D8 TIRHUTA DIGIT EIGHT
    ord('𑓙'): '9', # U+114D9 TIRHUTA DIGIT NINE
    ord('𑙐'): '0', # U+11650 MODI DIGIT ZERO
    ord('𑙑'): '1', # U+11651 MODI DIGIT ONE
    ord('𑙒'): '2', # U+11652 MODI DIGIT TWO
    ord('𑙓'): '3', # U+11653 MODI DIGIT THREE
    ord('𑙔'): '4', # U+11654 MODI DIGIT FOUR
    ord('𑙕'): '5', # U+11655 MODI DIGIT FIVE
    ord('𑙖'): '6', # U+11656 MODI DIGIT SIX
    ord('𑙗'): '7', # U+11657 MODI DIGIT SEVEN
    ord('𑙘'): '8', # U+11658 MODI DIGIT EIGHT
    ord('𑙙'): '9', # U+11659 MODI DIGIT NINE
    ord('𑛀'): '0', # U+116C0 TAKRI DIGIT ZERO
    ord('𑛁'): '1', # U+116C1 TAKRI DIGIT ONE
    ord('𑛂'): '2', # U+116C2 TAKRI DIGIT TWO
    ord('𑛃'): '3', # U+116C3 TAKRI DIGIT THREE
    ord('𑛄'): '4', # U+116C4 TAKRI DIGIT FOUR
    ord('𑛅'): '5', # U+116C5 TAKRI DIGIT FIVE
    ord('𑛆'): '6', # U+116C6 TAKRI DIGIT SIX
    ord('𑛇'): '7', # U+116C7 TAKRI DIGIT SEVEN
    ord('𑛈'): '8', # U+116C8 TAKRI DIGIT EIGHT
    ord('𑛉'): '9', # U+116C9 TAKRI DIGIT NINE
    ord('𑜰'): '0', # U+11730 AHOM DIGIT ZERO
    ord('𑜱'): '1', # U+11731 AHOM DIGIT ONE
    ord('𑜲'): '2', # U+11732 AHOM DIGIT TWO
    ord('𑜳'): '3', # U+11733 AHOM DIGIT THREE
    ord('𑜴'): '4', # U+11734 AHOM DIGIT FOUR
    ord('𑜵'): '5', # U+11735 AHOM DIGIT FIVE
    ord('𑜶'): '6', # U+11736 AHOM DIGIT SIX
    ord('𑜷'): '7', # U+11737 AHOM DIGIT SEVEN
    ord('𑜸'): '8', # U+11738 AHOM DIGIT EIGHT
    ord('𑜹'): '9', # U+11739 AHOM DIGIT NINE
    ord('𑣠'): '0', # U+118E0 WARANG CITI DIGIT ZERO
    ord('𑣡'): '1', # U+118E1 WARANG CITI DIGIT ONE
    ord('𑣢'): '2', # U+118E2 WARANG CITI DIGIT TWO
    ord('𑣣'): '3', # U+118E3 WARANG CITI DIGIT THREE
    ord('𑣤'): '4', # U+118E4 WARANG CITI DIGIT FOUR
    ord('𑣥'): '5', # U+118E5 WARANG CITI DIGIT FIVE
    ord('𑣦'): '6', # U+118E6 WARANG CITI DIGIT SIX
    ord('𑣧'): '7', # U+118E7 WARANG CITI DIGIT SEVEN
    ord('𑣨'): '8', # U+118E8 WARANG CITI DIGIT EIGHT
    ord('𑣩'): '9', # U+118E9 WARANG CITI DIGIT NINE
    ord('𑥐'): '0', # U+11950 DIVES AKURU DIGIT ZERO
    ord('𑥑'): '1', # U+11951 DIVES AKURU DIGIT ONE
    ord('𑥒'): '2', # U+11952 DIVES AKURU DIGIT TWO
    ord('𑥓'): '3', # U+11953 DIVES AKURU DIGIT THREE
    ord('𑥔'): '4', # U+11954 DIVES AKURU DIGIT FOUR
    ord('𑥕'): '5', # U+11955 DIVES AKURU DIGIT FIVE
    ord('𑥖'): '6', # U+11956 DIVES AKURU DIGIT SIX
    ord('𑥗'): '7', # U+11957 DIVES AKURU DIGIT SEVEN
    ord('𑥘'): '8', # U+11958 DIVES AKURU DIGIT EIGHT
    ord('𑥙'): '9', # U+11959 DIVES AKURU DIGIT NINE
    ord('𑱐'): '0', # U+11C50 BHAIKSUKI DIGIT ZERO
    ord('𑱑'): '1', # U+11C51 BHAIKSUKI DIGIT ONE
    ord('𑱒'): '2', # U+11C52 BHAIKSUKI DIGIT TWO
    ord('𑱓'): '3', # U+11C53 BHAIKSUKI DIGIT THREE
    ord('𑱔'): '4', # U+11C54 BHAIKSUKI DIGIT FOUR
    ord('𑱕'): '5', # U+11C55 BHAIKSUKI DIGIT FIVE
    ord('𑱖'): '6', # U+11C56 BHAIKSUKI DIGIT SIX
    ord('𑱗'): '7', # U+11C57 BHAIKSUKI DIGIT SEVEN
    ord('𑱘'): '8', # U+11C58 BHAIKSUKI DIGIT EIGHT
    ord('𑱙'): '9', # U+11C59 BHAIKSUKI DIGIT NINE
    ord('𑵐'): '0', # U+11D50 MASARAM GONDI DIGIT ZERO
    ord('𑵑'): '1', # U+11D51 MASARAM GONDI DIGIT ONE
    ord('𑵒'): '2', # U+11D52 MASARAM GONDI DIGIT TWO
    ord('𑵓'): '3', # U+11D53 MASARAM GONDI DIGIT THREE
    ord('𑵔'): '4', # U+11D54 MASARAM GONDI DIGIT FOUR
    ord('𑵕'): '5', # U+11D55 MASARAM GONDI DIGIT FIVE
    ord('𑵖'): '6', # U+11D56 MASARAM GONDI DIGIT SIX
    ord('𑵗'): '7', # U+11D57 MASARAM GONDI DIGIT SEVEN
    ord('𑵘'): '8', # U+11D58 MASARAM GONDI DIGIT EIGHT
    ord('𑵙'): '9', # U+11D59 MASARAM GONDI DIGIT NINE
    ord('𑶠'): '0', # U+11DA0 GUNJALA GONDI DIGIT ZERO
    ord('𑶡'): '1', # U+11DA1 GUNJALA GONDI DIGIT ONE
    ord('𑶢'): '2', # U+11DA2 GUNJALA GONDI DIGIT TWO
    ord('𑶣'): '3', # U+11DA3 GUNJALA GONDI DIGIT THREE
    ord('𑶤'): '4', # U+11DA4 GUNJALA GONDI DIGIT FOUR
    ord('𑶥'): '5', # U+11DA5 GUNJALA GONDI DIGIT FIVE
    ord('𑶦'): '6', # U+11DA6 GUNJALA GONDI DIGIT SIX
    ord('𑶧'): '7', # U+11DA7 GUNJALA GONDI DIGIT SEVEN
    ord('𑶨'): '8', # U+11DA8 GUNJALA GONDI DIGIT EIGHT
    ord('𑶩'): '9', # U+11DA9 GUNJALA GONDI DIGIT NINE
    ord('𑽐'): '0', # U+11F50 KAWI DIGIT ZERO
    ord('𑽑'): '1', # U+11F51 KAWI DIGIT ONE
    ord('𑽒'): '2', # U+11F52 KAWI DIGIT TWO
    ord('𑽓'): '3', # U+11F53 KAWI DIGIT THREE
    ord('𑽔'): '4', # U+11F54 KAWI DIGIT FOUR
    ord('𑽕'): '5', # U+11F55 KAWI DIGIT FIVE
    ord('𑽖'): '6', # U+11F56 KAWI DIGIT SIX
    ord('𑽗'): '7', # U+11F57 KAWI DIGIT SEVEN
    ord('𑽘'): '8', # U+11F58 KAWI DIGIT EIGHT
    ord('𑽙'): '9', # U+11F59 KAWI DIGIT NINE
    ord('𖩠'): '0', # U+16A60 MRO DIGIT ZERO
    ord('𖩡'): '1', # U+16A61 MRO DIGIT ONE
    ord('𖩢'): '2', # U+16A62 MRO DIGIT TWO
    ord('𖩣'): '3', # U+16A63 MRO DIGIT THREE
    ord('𖩤'): '4', # U+16A64 MRO DIGIT FOUR
    ord('𖩥'): '5', # U+16A65 MRO DIGIT FIVE
    ord('𖩦'): '6', # U+16A66 MRO DIGIT SIX
    ord('𖩧'): '7', # U+16A67 MRO DIGIT SEVEN
    ord('𖩨'): '8', # U+16A68 MRO DIGIT EIGHT
    ord('𖩩'): '9', # U+16A69 MRO DIGIT NINE
    ord('𖫀'): '0', # U+16AC0 TANGSA DIGIT ZERO
    ord('𖫁'): '1', # U+16AC1 TANGSA DIGIT ONE
    ord('𖫂'): '2', # U+16AC2 TANGSA DIGIT TWO
    ord('𖫃'): '3', # U+16AC3 TANGSA DIGIT THREE
    ord('𖫄'): '4', # U+16AC4 TANGSA DIGIT FOUR
    ord('𖫅'): '5', # U+16AC5 TANGSA DIGIT FIVE
    ord('𖫆'): '6', # U+16AC6 TANGSA DIGIT SIX
    ord('𖫇'): '7', # U+16AC7 TANGSA DIGIT SEVEN
    ord('𖫈'): '8', # U+16AC8 TANGSA DIGIT EIGHT
    ord('𖫉'): '9', # U+16AC9 TANGSA DIGIT NINE
    ord('𖭐'): '0', # U+16B50 PAHAWH HMONG DIGIT ZERO
    ord('𖭑'): '1', # U+16B51 PAHAWH HMONG DIGIT ONE
    ord('𖭒'): '2', # U+16B52 PAHAWH HMONG DIGIT TWO
    ord('𖭓'): '3', # U+16B53 PAHAWH HMONG DIGIT THREE
    ord('𖭔'): '4', # U+16B54 PAHAWH HMONG DIGIT FOUR
    ord('𖭕'): '5', # U+16B55 PAHAWH HMONG DIGIT FIVE
    ord('𖭖'): '6', # U+16B56 PAHAWH HMONG DIGIT SIX
    ord('𖭗'): '7', # U+16B57 PAHAWH HMONG DIGIT SEVEN
    ord('𖭘'): '8', # U+16B58 PAHAWH HMONG DIGIT EIGHT
    ord('𖭙'): '9', # U+16B59 PAHAWH HMONG DIGIT NINE
    ord('𞅀'): '0', # U+1E140 NYIAKENG PUACHUE HMONG DIGIT ZERO
    ord('𞅁'): '1', # U+1E141 NYIAKENG PUACHUE HMONG DIGIT ONE
    ord('𞅂'): '2', # U+1E142 NYIAKENG PUACHUE HMONG DIGIT TWO
    ord('𞅃'): '3', # U+1E143 NYIAKENG PUACHUE HMONG DIGIT THREE
    ord('𞅄'): '4', # U+1E144 NYIAKENG PUACHUE HMONG DIGIT FOUR
    ord('𞅅'): '5', # U+1E145 NYIAKENG PUACHUE HMONG DIGIT FIVE
    ord('𞅆'): '6', # U+1E146 NYIAKENG PUACHUE HMONG DIGIT SIX
    ord('𞅇'): '7', # U+1E147 NYIAKENG PUACHUE HMONG DIGIT SEVEN
    ord('𞅈'): '8', # U+1E148 NYIAKENG PUACHUE HMONG DIGIT EIGHT
    ord('𞅉'): '9', # U+1E149 NYIAKENG PUACHUE HMONG DIGIT NINE
    ord('𞋰'): '0', # U+1E2F0 WANCHO DIGIT ZERO
    ord('𞋱'): '1', # U+1E2F1 WANCHO DIGIT ONE
    ord('𞋲'): '2', # U+1E2F2 WANCHO DIGIT TWO
    ord('𞋳'): '3', # U+1E2F3 WANCHO DIGIT THREE
    ord('𞋴'): '4', # U+1E2F4 WANCHO DIGIT FOUR
    ord('𞋵'): '5', # U+1E2F5 WANCHO DIGIT FIVE
    ord('𞋶'): '6', # U+1E2F6 WANCHO DIGIT SIX
    ord('𞋷'): '7', # U+1E2F7 WANCHO DIGIT SEVEN
    ord('𞋸'): '8', # U+1E2F8 WANCHO DIGIT EIGHT
    ord('𞋹'): '9', # U+1E2F9 WANCHO DIGIT NINE
    ord('𞓰'): '0', # U+1E4F0 NAG MUNDARI DIGIT ZERO
    ord('𞓱'): '1', # U+1E4F1 NAG MUNDARI DIGIT ONE
    ord('𞓲'): '2', # U+1E4F2 NAG MUNDARI DIGIT TWO
    ord('𞓳'): '3', # U+1E4F3 NAG MUNDARI DIGIT THREE
    ord('𞓴'): '4', # U+1E4F4 NAG MUNDARI DIGIT FOUR
    ord('𞓵'): '5', # U+1E4F5 NAG MUNDARI DIGIT FIVE
    ord('𞓶'): '6', # U+1E4F6 NAG MUNDARI DIGIT SIX
    ord('𞓷'): '7', # U+1E4F7 NAG MUNDARI DIGIT SEVEN
    ord('𞓸'): '8', # U+1E4F8 NAG MUNDARI DIGIT EIGHT
    ord('𞓹'): '9', # U+1E4F9 NAG MUNDARI DIGIT NINE
    ord('𞥐'): '0', # U+1E950 ADLAM DIGIT ZERO
    ord('𞥑'): '1', # U+1E951 ADLAM DIGIT ONE
    ord('𞥒'): '2', # U+1E952 ADLAM DIGIT TWO
    ord('𞥓'): '3', # U+1E953 ADLAM DIGIT THREE
    ord('𞥔'): '4', # U+1E954 ADLAM DIGIT FOUR
    ord('𞥕'): '5', # U+1E955 ADLAM DIGIT FIVE
    ord('𞥖'): '6', # U+1E956 ADLAM DIGIT SIX
    ord('𞥗'): '7', # U+1E957 ADLAM DIGIT SEVEN
    ord('𞥘'): '8', # U+1E958 ADLAM DIGIT EIGHT
    ord('𞥙'): '9', # U+1E959 ADLAM DIGIT NINE
}

def convert_digits_to_ascii(text: str) -> str:
    '''
    Convert language specific digits in a text to ASCII digits

    :param text: The text to convert
    :return: The converted text containing only ASCII digits

    Examples:

    >>> convert_digits_to_ascii('hello ०१२३४५६७८९') # Devanagari
    'hello 0123456789'
    >>> convert_digits_to_ascii('hello ౦౧౨౩౪౫౬౭౮౯') # Telugu
    'hello 0123456789'
    >>> convert_digits_to_ascii('hello 𞥐𞥑𞥒𞥓𞥔𞥕𞥖𞥗𞥘𞥙') # Adlam
    'hello 0123456789'
    '''
    return text.translate(DIGIT_TRANS_TABLE)

class TransliterationParts(NamedTuple):
    '''
    A named tuple containing the parts of a transliteration

    committed: str        The part of the transliteration which cannot be
                          changed anymore by adding more input, could be
                          committed already if desired.
    committed_index: int  The index up to which the msymbol_list input
                          was “used up” to create the “committed” text.
    preedit:              The transliteration of the remaining input,
                          may still change by adding more input.
    cursor_pos: int       The cursor position in the preedit.
                          Counted in codepoints, not glyphs (For example
                          '☺\uFE0F' usually renders as one glyph (☺️) but
                          has two codepoints).
                          Usually this is at the end of the preedit but
                          not always! An input method may move the cursor
                          within the preedit!
                          (I think only ja-anthy.mim actually moves the
                          cursor within the preedit sometimes when moving
                          or resizing the henkan region).
    status: str           May change for some input methods to
                          indicate a state.
                          For example in case of ja-anthy.mim,
                          this is 'aあ' before Henkan and changes
                          to '漢' in Henkan mode.
    candidates: List[str] May contain a list of candidates if the
                          input method can produce multiple candidates.
    candidate_index: int  Index of the selected candidate.
                          0 if no candidate is selected.
    candidate_from: int   Start of the current candidate in the preedit.
    candidate_to: int     End of the  current candidate in the preedit.
                          If candidate_index == 0, i.e.
                          no candidate is selected, the current candidate
                          in the preedit is the first candidate.
    candidate_show: int   0: candidates should be hidden
                          1: candidates should be shown
    '''
    committed: str = ''
    committed_index: int = 0
    preedit: str = ''
    cursor_pos: int = 0
    status: str = ''
    candidates: List[str] = []
    candidate_index: int = 0
    candidate_from: int = 0
    candidate_to: int = 0
    candidate_show: int = 0

class Transliterator:
    '''A class for transliterators using libm17n

    If initializing the transliterator fails, for example because a
    non-existing input method was given as the argument, a ValueError
    is raised.
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
        self._msymbol_single_char_with_prefix_pattern = re.compile(
            r'^(?P<prefix>([SCMAGsH]-)*)(?P<unicode>.)$')
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

    def _convert_non_ascii_msymbol(self, msymbol: str) -> str:
        # Python >= 3.7 has a str.isascii(), I could use that instead
        # of my own is_ascii(), but that does not work on older
        # distributions like openSUSE 15.6.
        if itb_util.is_ascii(msymbol):
            return msymbol
        match = re.search(
            self._msymbol_single_char_with_prefix_pattern, msymbol)
        if not match:
            return msymbol
        name = IBus.keyval_name(IBus.unicode_to_keyval(match.group('unicode')))
        return f'{match.group("prefix")}{name}'

    def reset_ic(self) -> None:
        '''Resets the input context

        Can be used to reset the internal state of the input method to
        the default.  For example, if zh-py is in fullwidth-mode (to
        input fullwidth Latin), calling reset_ic() switches to the
        default mode to input Chinese characters.
        '''
        if self._dummy:
            return
        libm17n__minput_reset_ic(self._ic) # type: ignore
        # From the m17n-lib documentation:
        #
        # The minput_reset_ic () function resets input context $IC by
        # calling a callback function corresponding to @b
        # Minput_reset.  It resets the status of $IC to its initial
        # one.  As the current preedit text is deleted without
        # commitment, if necessary, call minput_filter () with the arg
        # @b key #Mnil to force the input method to commit the preedit
        # in advance.
        #
        # Looks like we need to do this here, i.e. call minput_filter
        # with a final 'nil' msymbol to commit the preedit in the
        # input context to make the next call to minput_reset_ic()
        # work reliably.  Without that minput_reset_ic() sometimes
        # segfaults.
        _symbol = libm17n__msymbol(b'nil') # type: ignore
        _retval = libm17n__minput_filter( # type: ignore
            self._ic, _symbol, ctypes.c_void_p(None))

    def transliterate_parts(
            self,
            msymbol_list: Iterable[str],
            ascii_digits: bool = False,
            reset: bool = False) -> TransliterationParts:
        # pylint: disable=line-too-long
        '''Transliterate a list of Msymbol names

        :param msymbol_list: A list of strings which are interpreted
                             as the names of Msymbols to transliterate.
                             If the input method has the special name “NoIME”,
                             no transliteration is done, the list of
                             Msymbols is just joined to a single string.
        :param ascii_digits: If true, convert language specific digits
                             to ASCII digits
        :return: The transliteration in several parts

        Examples:

        >>> trans = Transliterator('hi-itrans')
        >>> parts = trans.transliterate_parts(list('n'))
        >>> parts.committed
        ''
        >>> parts.committed_index
        0
        >>> parts.preedit
        'न्'
        >>> parts.cursor_pos
        2
        >>> parts.status
        'क'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('n '))
        >>> parts.committed
        'न '
        >>> parts.committed_index
        2
        >>> parts.preedit
        ''
        >>> parts.cursor_pos
        0
        >>> parts.status
        'क'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts =trans.transliterate_parts(list('na'))
        >>> parts.committed
        ''
        >>> parts.committed_index
        0
        >>> parts.preedit
        'न'
        >>> parts.cursor_pos
        1
        >>> parts.status
        'क'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('nam'))
        >>> parts.committed
        'न'
        >>> parts.committed_index
        2
        >>> parts.preedit
        'म्'
        >>> parts.cursor_pos
        2
        >>> parts.status
        'क'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('nama'))
        >>> parts.committed
        'न'
        >>> parts.committed_index
        2
        >>> parts.preedit
        'म'
        >>> parts.cursor_pos
        1
        >>> parts.status
        'क'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('namas'))
        >>> parts.committed
        'नम'
        >>> parts.committed_index
        4
        >>> parts.preedit
        'स्'
        >>> parts.cursor_pos
        2
        >>> parts.status
        'क'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('namast'))
        >>> parts.committed
        'नम'
        >>> parts.committed_index
        4
        >>> parts.preedit
        'स्त्'
        >>> parts.cursor_pos
        4
        >>> parts.status
        'क'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('namaste'))
        >>> parts.committed
        'नम'
        >>> parts.committed_index
        4
        >>> parts.preedit
        'स्ते'
        >>> parts.cursor_pos
        4
        >>> parts.status
        'क'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('namaste '))
        >>> parts.committed
        'नमस्ते '
        >>> parts.committed_index
        8
        >>> parts.preedit
        ''
        >>> parts.cursor_pos
        0
        >>> parts.status
        'क'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0

        >>> trans = Transliterator('t-latn-post')
        >>> parts = trans.transliterate_parts(list('u'))
        >>> parts.committed
        ''
        >>> parts.committed_index
        0
        >>> parts.preedit
        'u'
        >>> parts.cursor_pos
        1
        >>> parts.status
        'Latin-post'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('u"'))
        >>> parts.committed
        ''
        >>> parts.committed_index
        0
        >>> parts.preedit
        'ü'
        >>> parts.cursor_pos
        1
        >>> parts.status
        'Latin-post'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('u""'))
        >>> parts.committed
        'u"'
        >>> parts.committed_index
        3
        >>> parts.preedit
        ''
        >>> parts.cursor_pos
        0
        >>> parts.status
        'Latin-post'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('u"u'))
        >>> parts.committed
        'ü'
        >>> parts.committed_index
        2
        >>> parts.preedit
        'u'
        >>> parts.cursor_pos
        1
        >>> parts.status
        'Latin-post'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('üu"u'))
        >>> parts.committed
        'üü'
        >>> parts.committed_index
        3
        >>> parts.preedit
        'u'
        >>> parts.cursor_pos
        1
        >>> parts.status
        'Latin-post'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0

        >>> trans = Transliterator('t-rfc1345')
        >>> parts = trans.transliterate_parts(list('&'))
        >>> parts.committed
        ''
        >>> parts.committed_index
        0
        >>> parts.preedit
        '&'
        >>> parts.cursor_pos
        1
        >>> parts.status
        'RFC1345'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('&C'))
        >>> parts.committed
        ''
        >>> parts.committed_index
        0
        >>> parts.preedit
        '&C'
        >>> parts.cursor_pos
        2
        >>> parts.status
        'RFC1345'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('&Co'))
        >>> parts.committed
        '©'
        >>> parts.committed_index
        3
        >>> parts.preedit
        ''
        >>> parts.cursor_pos
        0
        >>> parts.status
        'RFC1345'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('&f'))
        >>> parts.committed
        ''
        >>> parts.committed_index
        0
        >>> parts.preedit
        '&f'
        >>> parts.cursor_pos
        2
        >>> parts.status
        'RFC1345'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('&ff'))
        >>> parts.committed
        ''
        >>> parts.committed_index
        0
        >>> parts.preedit
        'ﬀ'
        >>> parts.cursor_pos
        1
        >>> parts.status
        'RFC1345'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('&ffi'))
        >>> parts.committed
        'ﬃ'
        >>> parts.committed_index
        4
        >>> parts.preedit
        ''
        >>> parts.cursor_pos
        0
        >>> parts.status
        'RFC1345'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0

        >>> trans = Transliterator('t-lsymbol')
        >>> parts = trans.transliterate_parts(list('/:)'))
        >>> parts.committed
        ''
        >>> parts.committed_index
        0
        >>> parts.preedit
        '☺️'
        >>> parts.cursor_pos
        2
        >>> parts.status
        'lsymbol'
        >>> parts.candidates
        ['☺️', '😃', '😅', '😆', '😉', '😇', '😂', '😏', '😛', '😜', '😝', '😋', '😉', '💏', '💋', '😍', '😘', '😚', '😽', '😻']
        >>> parts.candidate_show
        1
        >>> parts = trans.transliterate_parts(list('a'))
        >>> parts.committed
        'a'
        >>> parts.committed_index
        1
        >>> parts.preedit
        ''
        >>> parts.cursor_pos
        0
        >>> parts.status
        'lsymbol'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0
        >>> parts = trans.transliterate_parts(list('a/'))
        >>> parts.committed
        'a'
        >>> parts.committed_index
        1
        >>> parts.preedit
        '/'
        >>> parts.cursor_pos
        1
        >>> parts.status
        'lsymbol'
        >>> parts.candidates
        ['/']
        >>> parts.candidate_show
        1
        >>> parts = trans.transliterate_parts(list('a/:'))
        >>> parts.committed
        'a'
        >>> parts.committed_index
        1
        >>> parts.preedit
        '/:'
        >>> parts.cursor_pos
        2
        >>> parts.status
        'lsymbol'
        >>> parts.candidates
        ['/:']
        >>> parts.candidate_show
        1
        >>> parts = trans.transliterate_parts(list('a/:('))
        >>> parts.committed
        'a'
        >>> parts.committed_index
        1
        >>> parts.preedit
        '😢'
        >>> parts.cursor_pos
        1
        >>> parts.status
        'lsymbol'
        >>> parts.candidates
        ['😢', '😩', '😡', '😭', '😪', '🙈', '🙊', '🙉']
        >>> parts.candidate_show
        1
        >>> parts = trans.transliterate_parts(list('a/:(b'))
        >>> parts.committed
        'a😢b'
        >>> parts.committed_index
        5
        >>> parts.preedit
        ''
        >>> parts.cursor_pos
        0
        >>> parts.status
        'lsymbol'
        >>> parts.candidates
        []
        >>> parts.candidate_show
        0

        For a test transliterating parts using 'ja-anthy' see 'tests/test_m17n_translit.py'.
        '''
        # pylint: enable=line-too-long
        if not isinstance(msymbol_list, list):
            raise ValueError('Argument of transliterate() must be a list.')
        if self._dummy:
            return TransliterationParts(committed=''.join(msymbol_list),
                                       committed_index=len(msymbol_list))
        if reset:
            libm17n__minput_reset_ic(self._ic) # type: ignore
        committed = ''
        committed_index = 0
        preedit = ''
        candidates: List[str] = []
        for index, symbol in enumerate(msymbol_list):
            symbol = self._convert_non_ascii_msymbol(symbol)
            _symbol = libm17n__msymbol(symbol.encode('utf-8')) # type: ignore
            retval = libm17n__minput_filter( # type: ignore
                self._ic, _symbol, ctypes.c_void_p(None))
            if retval == 0:
                _mt = libm17n__mtext() # type: ignore
                retval = libm17n__minput_lookup( # type: ignore
                    self._ic, _symbol, ctypes.c_void_p(None), _mt)
                if libm17n__mtext_len(_mt) > 0: # type: ignore
                    committed += mtext_to_string(_mt)
                    committed_index = index
                if retval:
                    committed += msymbol_list[index]
                    committed_index = index + 1
        try:
            if (self._ic.contents.preedit_changed
                and
                libm17n__mtext_len(
                    self._ic.contents.preedit) > 0): # type: ignore
                preedit = mtext_to_string(self._ic.contents.preedit)
        except Exception as error: # pylint: disable=broad-except
            # This should never happen:
            raise ValueError('Problem accessing preedit') from error
        plist = self._ic.contents.candidate_list
        while bool(plist):  # NULL pointers have a False boolean value
            key = libm17n__mplist_key(plist) # type: ignore
            if not bool(key):
                break
            key_name = libm17n__msymbol_name(key.contents) # type: ignore
            if key_name == b'mtext':
                characters = mtext_to_string(
                    ctypes.cast(libm17n__mplist_value(plist), # type: ignore
                        ctypes.POINTER(libm17n__MText)))
                candidates += list(characters)
            elif key_name == b'plist':
                candidate_plist = ctypes.cast(
                    libm17n__mplist_value(plist), # type: ignore
                    ctypes.POINTER(libm17n__MPlist))
                while True:
                    candidate_plist_key = libm17n__mplist_key( # type: ignore
                        candidate_plist)
                    if not bool(candidate_plist_key):
                        break
                    candidate_plist_key_name = libm17n__msymbol_name( # type: ignore
                        candidate_plist_key.contents)
                    if candidate_plist_key_name != b'mtext':
                        break
                    candidate = mtext_to_string(
                        ctypes.cast(
                            libm17n__mplist_value(candidate_plist), # type: ignore
                            ctypes.POINTER(libm17n__MText)))
                    candidates.append(candidate)
                    candidate_plist = libm17n__mplist_next( # type: ignore
                        candidate_plist)
            else:
                break
            plist = libm17n__mplist_next(plist) # type: ignore
        cursor_pos = self._ic.contents.cursor_pos
        status = mtext_to_string(self._ic.contents.status)
        candidate_index = self._ic.contents.candidate_index
        candidate_from = self._ic.contents.candidate_from
        candidate_to = self._ic.contents.candidate_to
        candidate_show = self._ic.contents.candidate_show
        # From the m17n-lib documentation:
        #
        # The minput_reset_ic () function resets input context $IC by
        # calling a callback function corresponding to @b
        # Minput_reset.  It resets the status of $IC to its initial
        # one.  As the current preedit text is deleted without
        # commitment, if necessary, call minput_filter () with the arg
        # @b key #Mnil to force the input method to commit the preedit
        # in advance.
        #
        # Looks like we need to do this here, i.e. call minput_filter
        # with a final 'nil' msymbol to commit the preedit in the
        # input context to make the next call to minput_reset_ic()
        # work reliably.  Without that minput_reset_ic() sometimes
        # segfaults.  The old code, before fixing
        # https://github.com/mike-fabian/ibus-typing-booster/issues/460
        # always appended a final 'nil' symbol to the msymbol_list
        # argument which had to be removed to get the correct preedit
        # contents.  But apparently that final 'nil' is necessary to
        # make it work reliably. We can do this here because above we
        # read the preedit already and don’t need it anymore.
        #
        # It is not only necessary to make the next call to
        # minput_reset_ic() work reliably, it is also necessary to
        # commit any remaining preedit to avoid that the next
        # transliteration starts with a non-empty preedit remaining
        # from the previous transliteration.
        #
        # Unfortunately that makes state changing switches which
        # affect only the next character not survive until the next
        # transliteration.  For example when switching to
        # single-fullwidth-mode by typing `Z` (see cjk-util.mim) with
        # early commits (i.e. with the `tb:zh:py`), `aZ` will commit
        # `啊`. The `Z` causes the commit but the state change done by
        # the `Z` does not survive, typing `aZaZ` commits `啊啊`.
        # With empty input one can type `Za` to get a single `ａ`
        # FULLWIDTH LATIN SMALL LETTER A though.
        _symbol = libm17n__msymbol(b'nil') # type: ignore
        _retval = libm17n__minput_filter( # type: ignore
            self._ic, _symbol, ctypes.c_void_p(None))
        if committed and not preedit:
            committed_index = len(msymbol_list)
        # Some Chinese input methods and some Vietnamese input methods
        # for Chinese characters sometimes have “candidates == []” but
        # at the same time “candidate_show == 1”:
        #
        # For example zh-cangjie.mim contains:
        #
        #  (map
        #   ("a" ("日曰"))
        #   ("aa" ("昌昍"))
        #   ("aaa" ?晶)
        #   ("aaaa" ("𣊫𣊭"))
        #   [...]
        #
        # The ?晶 produces “candidates == []”, ("晶") would
        # produce “candidates == ['晶']”
        #
        # In that case typing `a` and `aa` produces candidates but
        # `aaa` does not and `aaaa` produces candidates again.  That
        # is bad because Typing Booster behaves differently when there
        # are candidates and when there are not.  So it would behave
        # inconsistently while typing `aaaa` if `aaa` suddenly has no
        # candidates and suddenly shows a “normal” typing booster
        # completion lookup table.
        #
        # Other input methods which have the same problem are
        # zh-tonepy, vi-nomtelex, vi-nomvni, ...
        #
        # So copy the preedit into candidates if they are empty and
        # candidate_show is one for more consistent behaviour (in my
        # opinion):
        if preedit and not candidates and candidate_show:
            candidates = [preedit]
        if self._language == 'ja' and self._name == 'anthy':
            # ja-anthy produces a lot of useless geta marks '〓'.  It
            # also produces sometimes useless empty candidates and
            # sometimes (when transliterating `1 `) even preedit='',
            # cursor_pos=1.
            #
            # All these problems seem to be encoding problems caused
            # by mimx-anthy.c in m17n-lib using EUC-JP encoding
            # instead of UTF-8.  They all go away go away after fixing
            # mimx-anthy.c to use UTF-8 by patching it like this:
            #
            # --- a/example/mimx-anthy.c
            # +++ b/example/mimx-anthy.c
            # @@ -129,15 +129,16 @@ new_context (MInputContext *ic)
            #  {
            #    AnthyContext *context;
            #    anthy_context_t ac;
            # -  MSymbol euc_jp = msymbol ("euc-jp");
            # +  MSymbol utf_8 = msymbol ("utf-8");
            #    /* Rebound to an actual buffer just before being used.  */
            # -  MConverter *converter = mconv_buffer_converter (euc_jp, NULL, 0);
            # +  MConverter *converter = mconv_buffer_converter (utf_8, NULL, 0);
            #
            #    if (! converter)
            #      return NULL;
            #    ac = anthy_create_context ();
            #    if (! ac)
            #      return NULL;
            # +  anthy_context_set_encoding(ac, ANTHY_UTF8_ENCODING);
            #    context = calloc (1, sizeof (AnthyContext));
            #    context->ic = ic;
            #    context->ac = ac;
            #
            # It is not necessary to use anthy-unicode (although this is
            # probably better), I tested that this encoding problem here
            # can be fixed by just patching mimx-anthy.c. Tested with
            # anthy-9100h-56.fc41.x86_64
            # anthy-unicode-1.0.0.20240502-8.fc41.x86_64
            #
            # For systems where mimx-anthy.c has not been fixed yet
            # in m17n-lib, apply a runtime fix here:
            if preedit != '下駄':
                candidates = [
                    candidate
                    for candidate in candidates
                    if candidate and '〓' not in candidate]
            if not preedit and candidates:
                preedit = candidates[0]
                cursor_pos = len(preedit)
        if not ascii_digits:
            return TransliterationParts(committed=committed,
                                       committed_index=committed_index,
                                       preedit=preedit,
                                       cursor_pos=cursor_pos,
                                       status=status,
                                       candidates=candidates,
                                       candidate_index=candidate_index,
                                       candidate_from=candidate_from,
                                       candidate_to=candidate_to,
                                       candidate_show=candidate_show)
        return TransliterationParts(
            committed=convert_digits_to_ascii(committed),
            committed_index=committed_index,
            preedit=convert_digits_to_ascii(preedit),
            cursor_pos=cursor_pos,
            status=status,
            candidates=candidates,
            candidate_index=candidate_index,
            candidate_from=candidate_from,
            candidate_to=candidate_to,
            candidate_show=candidate_show)

    def transliterate(
            self,
            msymbol_list: Iterable[str],
            ascii_digits: bool = False,
            reset: bool = False) -> str:
        '''Transliterate a list of Msymbol names

        :param msymbol_list: A list of strings which are interpreted
                             as the names of Msymbols to transliterate.
                             If the input method has the special name “NoIME”,
                             no transliteration is done, the list of
                             Msymbols is just joined to a single string.
        :param ascii_digits: If true, convert language specific digits
                             to ASCII digits
        :return: The transliteration in one string

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

        >>> trans = Transliterator('si-wijesekara')
        >>> trans.transliterate(list('vksIal kjSka '))
        'ඩනිෂ්ක නවීන් '
        '''
        transliteration_parts = self.transliterate_parts(
            msymbol_list, ascii_digits, reset)
        return transliteration_parts.committed + transliteration_parts.preedit

    def get_variables(self) -> List[Tuple[str, str, str]]:
        # pylint: disable=line-too-long
        '''
        Gets the optional variables of this transliterator input method

        Examples:

        >>> trans = Transliterator('NoIME')
        >>> trans.get_variables()
        []
        >>> trans = Transliterator('si-wijesekara')
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
            libm17n__msymbol(b'nil')) # type: ignore
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
                        libm17n__msymbol(b'symbol'), # type: ignore
                        libm17n__msymbol(variable_value.encode('utf-8'))) # type: ignore
                elif key_name == b'mtext':
                    mtext = libm17n__mconv_decode_buffer( # type: ignore
                        libm17n__Mcoding_utf_8,
                        ctypes.c_char_p(variable_value.encode('utf-8')),
                        len(variable_value.encode('utf-8')))
                    libm17n__mplist_add( # type: ignore
                        new_value_plist,
                        libm17n__msymbol(b'mtext'), # type: ignore
                        mtext)
                elif key_name == b'integer':
                    try:
                        int_value = int(variable_value, 10)
                        libm17n__mplist_add( # type: ignore
                            new_value_plist,
                            libm17n__msymbol(b'integer'), # type: ignore
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
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    import doctest
    (FAILED, _ATTEMPTED) = doctest.testmod()
    sys.exit(FAILED)
