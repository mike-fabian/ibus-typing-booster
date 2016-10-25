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

import sys
import ctypes

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

def mtext_to_string(mtext_pointer):
    '''Return the text contained in an MText object as a Python string

    :param mtext_pointer: pointer to the MText object to get the text from
    :type mtext_pointer: pointer to an libm17n MText object
    :rtype: string
    '''
    libm17n__mconv_reset_converter(_utf8_converter)
    # one Unicode character cannot have more than 6 UTF-8 bytes
    # (actually not more than 4 ...)
    bufsize = (libm17n__mtext_len(mtext_pointer) + 1) * 6
    conversion_buffer = bytes(bufsize)
    libm17n__mconv_rebind_buffer(
        _utf8_converter,
        ctypes.c_char_p(conversion_buffer),
        ctypes.c_int(bufsize))
    libm17n__mconv_encode(_utf8_converter, mtext_pointer)
    # maybe not all of the buffer was really used for the conversion,
    # cut of the unused part:
    conversion_buffer = conversion_buffer[0:conversion_buffer.find(b'\x00')]
    return conversion_buffer.decode('utf-8')

def _init():
    '''Open libm17n and fill global variables for functions and
    variables from libm17n
    '''
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

def _del():
    '''Cleanup'''
    libm17n__lib.m17n_fini()

class __ModuleInitializer:
    def __init__(self):
        _init()
        return

    def __del__(self):
        return

__module_init = __ModuleInitializer()


class Transliterator:
    '''A class for transliterators using libm17n

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

    >>> trans = Transliterator('NoIme')
    >>> trans.transliterate(['a', 'b', 'c', 'C-c', 'G-4'])
    'abcC-cG-4'

    >>> trans = Transliterator('ja-anthy')
    >>> trans.transliterate(['c', 'h', 'o', 'u', 'c', 'h', 'o', 'u'])
    'ちょうちょう'

    >>> trans = Transliterator('zh-py')
    >>> trans.transliterate(['n', 'i', 'h', 'a', 'o'])
    '你好'

    >>> trans = Transliterator('zh-tonepy')
    >>> trans.transliterate(['n', 'i', '3', 'h', 'a', 'o', '3'])
    '你好'

    If initializing the transliterator fails, for example
    because a non-existing input method was given as the argument,
    a ValueError is raised:

    >>> trans = Transliterator('ru-translitx')
    Traceback (most recent call last):
      File "/usr/lib64/python3.4/doctest.py", line 1318, in __run
        compileflags, 1), test.globs)
      File "<doctest __main__.Transliterator[8]>", line 1, in <module>
        trans = Transliterator('ru-translitx')
      File "m17n_translit.py", line 194, in __init__
        raise ValueError('minput_open_im() failed')
    ValueError: minput_open_im() failed
    '''
    def __init__(self, ime):
        '''Initialize the input method to use for the transliteration

        Raises ValueError if something fails.

        :param ime: Full name of the m17n input method, for example
                    “hi-inscript2” or “t-latn-post”. There is one
                    special input method name “NoIme”. The input method
                    “NoIme” is just a dummy which does not transliteration
                    at all, it only joins the list of Msymbol names to
                    a string.
        :type ime: string
        '''
        self._dummy = False
        if ime == 'NoIme':
            self._dummy = True
            return
        language = ime.split('-')[0]
        name = '-'.join(ime.split('-')[1:])
        self._im = libm17n__minput_open_im(
            libm17n__msymbol(ctypes.c_char_p(language.encode('utf-8'))),
            libm17n__msymbol(ctypes.c_char_p(name.encode('utf-8'))),
            ctypes.c_void_p(None))
        try:
            _im_contents = self._im.contents
        except ValueError: # NULL pointer access
            raise ValueError('minput_open_im() failed')
        self._ic = libm17n__minput_create_ic(self._im, ctypes.c_void_p(None))
        try:
            _ic_contents = self._ic.contents
        except ValueError: # NULL pointer access
            raise ValueError('minput_create_ic() failed')

    def transliterate(self, msymbol_list):
        '''Transliterate a list of Msymbol names

        Returns the transliteration as  a string.

        :param msymbol_list: A list of strings which are interpreted
                             as the names of Msymbols to transliterate.
                             If the input method has the special name “NoIme”,
                             no transliteration is done, the list of
                             Msymbols is just joined to a single string.
        :type msymbol_list: A list of strings
        :rtype: string
        '''
        if type(msymbol_list) != type([]):
            raise ValueError('Argument of transliterate() must be a list.')
        if self._dummy:
            return ''.join(msymbol_list)
        libm17n__minput_reset_ic(self._ic)
        output = ''
        for symbol in msymbol_list + ['nil']:
            _symbol = libm17n__msymbol(symbol.encode('utf-8'))
            retval = libm17n__minput_filter(
                self._ic, _symbol, ctypes.c_void_p(None))
            if retval == 0:
                _mt = libm17n__mtext()
                retval = libm17n__minput_lookup(
                    self._ic, _symbol, ctypes.c_void_p(None), _mt)
                if libm17n__mtext_len(_mt) > 0:
                    output += mtext_to_string(_mt)
                if retval and symbol != 'nil':
                    output += symbol
        return output

if __name__ == "__main__":
    import doctest
    (failed,  attempted) = doctest.testmod()
    if failed:
        sys.exit(1)
    else:
        sys.exit(0)
