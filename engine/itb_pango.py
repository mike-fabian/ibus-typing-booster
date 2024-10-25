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

from typing import List
from typing import Tuple
import sys
from gi import require_version # type: ignore
require_version('Gtk', '3.0')
from gi.repository import Gtk # type: ignore
require_version('Pango', '1.0')
from gi.repository import Pango

def get_fonts_used_for_text(
        font: str, text: str, fallback: bool = True) -> List[Tuple[str, str]]:
    '''Return a list of fonts which were really used to render a text

    :param font: The font requested to render the text in
    :param text: The text to render
    :param fallback: Whether to enable font fallback. If disabled, then
                     glyphs will only be used from the closest matching
                     font on the system. No fallback will be done to other
                     fonts on the system that might contain the glyphs needed
                     for the text.

    Examples:

    >>> get_fonts_used_for_text('DejaVu Sans Mono', '😀 ')
    [('😀', 'Noto Color Emoji'), (' ', 'DejaVu Sans Mono')]

    >>> get_fonts_used_for_text('DejaVu Sans', '日本語 नमस्ते')
    [('日本語', 'Droid Sans'), (' ', 'DejaVu Sans'), ('नमस्ते', 'Droid Sans')]

    >>> get_fonts_used_for_text('DejaVu Sans', '日本語 🕉️')
    [('日本語', 'Droid Sans'), (' ', 'DejaVu Sans'), ('🕉️', 'Noto Color Emoji')]
    '''
    fonts_used = []
    text_utf8 = text.encode('UTF-8', errors='replace')
    label = Gtk.Label()
    pango_context = label.get_pango_context()
    pango_layout = Pango.Layout(pango_context)
    pango_font_description = Pango.font_description_from_string(font)
    pango_layout.set_font_description(pango_font_description)
    pango_attr_list = Pango.AttrList()
    pango_attr_fallback = Pango.attr_fallback_new(fallback)
    pango_attr_list.insert(pango_attr_fallback)
    pango_layout.set_attributes(pango_attr_list)
    pango_layout.set_text(text)
    pango_layout_line = pango_layout.get_line_readonly(0)
    gs_list = pango_layout_line.runs
    number_of_runs = len(gs_list)
    for glyph_item in gs_list:
        pango_item = glyph_item.item
        offset = pango_item.offset
        length = pango_item.length
        _num_chars = pango_item.num_chars
        pango_glyph_string = glyph_item.glyphs
        _num_glyphs = pango_glyph_string.num_glyphs
        pango_analysis = pango_item.analysis
        pango_font = pango_analysis.font
        font_description_used = pango_font.describe()
        run_text = text_utf8[offset:offset + length].decode('UTF-8', errors='replace')
        run_family = font_description_used.get_family()
        fonts_used.append((run_text, run_family))
    return fonts_used

def _init() -> None:
    '''Initialization'''
    return

def _del() -> None:
    '''Cleanup'''
    return

class __ModuleInitializer: # pylint: disable=too-few-public-methods,invalid-name
    def __init__(self) -> None:
        _init()

    def __del__(self) -> None:
        return

if __name__ == "__main__":
    import doctest
    (FAILED, _ATTEMPTED) = doctest.testmod()
    sys.exit(FAILED)
