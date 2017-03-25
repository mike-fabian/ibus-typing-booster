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

'''A module to find out which fonts are used by pango to render a string
'''

import sys
import ctypes

class glib__GSList(ctypes.Structure):
    pass
glib__GSList._fields_ = [
    ('data', ctypes.c_void_p),
    ('next', ctypes.POINTER(glib__GSList)),
]
class libgtk3__GtkWidget(ctypes.Structure):
    pass
class libpango__PangoContext(ctypes.Structure):
    pass
class libpango__PangoLayout(ctypes.Structure):
    pass
class libpango__PangoFontDescription(ctypes.Structure):
    pass
class libpango__PangoLayoutLine(ctypes.Structure):
    pass
libpango__PangoLayoutLine._fields_ = [
    ('layout', ctypes.POINTER(libpango__PangoLayout)),
    ('start_index', ctypes.c_int), # start of line as byte index into layout->text
    ('length', ctypes.c_int), # length of line in bytes
    ('runs', ctypes.POINTER(glib__GSList)), 
    ('is_paragraph_start', ctypes.c_uint), # TRUE if this is the first line of the paragraph
    ('resolved_dir', ctypes.c_uint), # Resolved PangoDirection of line
]
class libpango__PangoGlyphString(ctypes.Structure):
    pass
class libpango__PangoEngineShape(ctypes.Structure):
    pass
class libpango__PangoEngineLang(ctypes.Structure):
    pass
class libpango__PangoFont(ctypes.Structure):
    pass
class libpango__PangoLanguage(ctypes.Structure):
    pass
class libpango__PangoAnalysis(ctypes.Structure):
    _fields_ = [
        ('shape_engine', ctypes.POINTER(libpango__PangoEngineShape)),
        ('lang_engine', ctypes.POINTER(libpango__PangoEngineLang)),
        ('font', ctypes.POINTER(libpango__PangoFont)),
        ('level', ctypes.c_uint8),
        ('gravity', ctypes.c_uint8),
        ('flags', ctypes.c_uint8),
        ('script', ctypes.c_uint8),
        ('language', ctypes.POINTER(libpango__PangoLanguage)),
        ('extra_attrs', ctypes.POINTER(glib__GSList)),
    ]
class libpango__PangoItem(ctypes.Structure):
    pass
libpango__PangoItem._fields_ = [
    ('offset', ctypes.c_int),
    ('length', ctypes.c_int),
    ('num_chars', ctypes.c_int),
    ('analysis', libpango__PangoAnalysis),
]
class libpango__PangoGlyphItem(ctypes.Structure):
    pass
libpango__PangoGlyphItem._fields_ = [
    ('item', ctypes.POINTER(libpango__PangoItem)),
    ('glyphs', ctypes.POINTER(libpango__PangoGlyphString)),
]

libglib__lib = None
libgtk3__lib = None
libpango__lib = None
libglib__g_slist_length = None
libglib__g_slist_nth_data = None
libgtk3__gtk_init = None
libgtk3__gtk_label_new = None
libgtk3__gtk_widget_get_pango_context = None
libpango__pango_layout_new = None
libpango__pango_font_description_from_string = None
libpango__pango_layout_set_font_description = None
libpango__pango_layout_set_text = None
libpango__pango_layout_set_font_description = None
libpango__pango_layout_set_text = None
libpango__pango_layout_get_line_readonly = None
libpango__pango_font_describe = None
libpango__pango_font_description_get_family = None

def get_fonts_used_for_text(font, text):
    '''Return a list of fonts which were really used to render a text

    :param font: The font requested to render the text in
    :type font: String
    :param text: The text to render
    :type text: String
    :rtype: List of strings

    Examples:

    >>> get_fonts_used_for_text('DejaVu Sans Mono', '😀 ')
    ['Noto Color Emoji', 'DejaVu Sans Mono']

    >>> get_fonts_used_for_text('DejaVu Sans', '日本語 नमस्ते')
    ['IPAPGothic', 'DejaVu Sans', 'Lohit Hindi']

    >>> get_fonts_used_for_text('DejaVu Sans', '日本語 🕉')
    ['IPAPGothic', 'Noto Color Emoji']
    '''
    fonts_used = []
    label = libgtk3__gtk_label_new(ctypes.c_char_p(b''))
    pango_context_p = libgtk3__gtk_widget_get_pango_context(label)
    pango_layout_p = libpango__pango_layout_new(pango_context_p)
    pango_font_description_p = libpango__pango_font_description_from_string(
        ctypes.c_char_p(font.encode('UTF-8', errors='replace')))
    libpango__pango_layout_set_font_description(
        pango_layout_p, pango_font_description_p)
    text_utf8 = text.encode('UTF-8', errors='replace')
    libpango__pango_layout_set_text(
        pango_layout_p,
        ctypes.c_char_p(text_utf8),
        ctypes.c_int(-1))
    pango_layout_line_p = libpango__pango_layout_get_line_readonly(
        pango_layout_p, ctypes.c_int(0))
    gs_list = pango_layout_line_p.contents.runs.contents
    number_of_runs = libglib__g_slist_length(gs_list)
    for index in range(0, number_of_runs):
        gpointer = libglib__g_slist_nth_data(gs_list, ctypes.c_uint(index))
        pango_glyph_item = ctypes.cast(
            gpointer,
            ctypes.POINTER(libpango__PangoGlyphItem)).contents
        pango_item_p = pango_glyph_item.item
        offset = pango_item_p.contents.offset
        length = pango_item_p.contents.length
        num_chars = pango_item_p.contents.num_chars
        pango_analysis = pango_item_p.contents.analysis
        pango_font_p = pango_analysis.font
        font_description_used = libpango__pango_font_describe(pango_font_p)
        run_text = text_utf8[offset:offset + length].decode('UTF-8', errors='replace')
        run_family = libpango__pango_font_description_get_family(
            font_description_used).decode('UTF-8', errors='replace')
        fonts_used.append((run_text, run_family))
    return fonts_used

def _init():
    global libglib__lib
    libglib__lib = ctypes.CDLL('libglib-2.0.so.0', mode=ctypes.RTLD_GLOBAL)
    global libgtk3__lib
    libgtk3__lib = ctypes.CDLL('libgtk-3.so.0', mode=ctypes.RTLD_GLOBAL)
    global libpango__lib
    libpango__lib = ctypes.CDLL('libpango-1.0.so.0', mode=ctypes.RTLD_GLOBAL)
    global libglib__g_slist_length
    libglib__g_slist_length = libglib__lib.g_slist_length
    libglib__g_slist_length.argtypes = [
        ctypes.POINTER(glib__GSList)]
    libglib__g_slist_length.restype = ctypes.c_uint
    global libglib__g_slist_nth_data
    libglib__g_slist_nth_data = libglib__lib.g_slist_nth_data
    libglib__g_slist_nth_data.argtypes = [
        ctypes.POINTER(glib__GSList), ctypes.c_uint]
    libglib__g_slist_nth_data.restype = ctypes.c_void_p
    global libgtk3__gtk_init
    libgtk3__gtk_init = libgtk3__lib.gtk_init
    libgtk3__gtk_init.argtypes = [
        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.POINTER(ctypes.c_char_p))]
    global libgtk3__gtk_label_new
    libgtk3__gtk_label_new = libgtk3__lib.gtk_label_new
    libgtk3__gtk_label_new.argtypes = [ctypes.c_char_p]
    libgtk3__gtk_label_new.restype = ctypes.POINTER(
        libgtk3__GtkWidget)
    global libgtk3__gtk_widget_get_pango_context
    libgtk3__gtk_widget_get_pango_context = libgtk3__lib.gtk_widget_get_pango_context
    libgtk3__gtk_widget_get_pango_context.argtypes = [ctypes.POINTER(libgtk3__GtkWidget)]
    libgtk3__gtk_widget_get_pango_context.restype = ctypes.POINTER(
        libpango__PangoContext)
    global libpango__pango_layout_new
    libpango__pango_layout_new = libpango__lib.pango_layout_new
    libpango__pango_layout_new.argtypes = [ctypes.POINTER(libpango__PangoContext)]
    libpango__pango_layout_new.restype = ctypes.POINTER(
        libpango__PangoLayout)
    global libpango__pango_font_description_from_string
    libpango__pango_font_description_from_string = libpango__lib.pango_font_description_from_string
    libpango__pango_font_description_from_string.argtypes = [ctypes.c_char_p]
    libpango__pango_font_description_from_string.restype = ctypes.POINTER(
        libpango__PangoFontDescription)
    global libpango__pango_layout_set_font_description
    libpango__pango_layout_set_font_description = libpango__lib.pango_layout_set_font_description
    libpango__pango_layout_set_font_description.argtypes = [
        ctypes.POINTER(libpango__PangoLayout),
        ctypes.POINTER(libpango__PangoFontDescription)]
    global libpango__pango_layout_set_text
    libpango__pango_layout_set_text = libpango__lib.pango_layout_set_text
    libpango__pango_layout_set_text.argtypes = [
        ctypes.POINTER(libpango__PangoLayout), ctypes.c_char_p, ctypes.c_int]
    global libpango__pango_layout_get_line_readonly
    libpango__pango_layout_get_line_readonly = libpango__lib.pango_layout_get_line_readonly
    libpango__pango_layout_get_line_readonly.argtypes = [
        ctypes.POINTER(libpango__PangoLayout), ctypes.c_int]
    libpango__pango_layout_get_line_readonly.restype = ctypes.POINTER(
        libpango__PangoLayoutLine)
    global libpango__pango_font_describe
    libpango__pango_font_describe = libpango__lib.pango_font_describe
    libpango__pango_font_describe.argtypes = [
        ctypes.POINTER(libpango__PangoFont)]
    libpango__pango_font_describe.restype = ctypes.POINTER(
        libpango__PangoFontDescription)
    global libpango__pango_font_description_get_family
    libpango__pango_font_description_get_family = libpango__lib.pango_font_description_get_family
    libpango__pango_font_description_get_family.argtypes = [
        ctypes.POINTER(libpango__PangoFontDescription)]
    libpango__pango_font_description_get_family.restype = ctypes.c_char_p
    libgtk3__gtk_init(
        ctypes.byref(ctypes.c_int(0)),
        ctypes.byref(ctypes.pointer(ctypes.c_char_p(b''))))

def _del():
    '''Cleanup'''
    pass

class __ModuleInitializer:
    def __init__(self):
        _init()
        return

    def __del__(self):
        return

__module_init = __ModuleInitializer()

if __name__ == "__main__":
    import doctest
    (failed,  attempted) = doctest.testmod()
    if failed:
        sys.exit(1)
    else:
        sys.exit(0)
