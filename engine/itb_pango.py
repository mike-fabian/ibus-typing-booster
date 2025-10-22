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
from typing import Dict
from typing import Any
import sys
import re
import subprocess
import shutil
import functools
import logging
from gi import require_version
# pylint: disable=wrong-import-position
require_version('Gtk', '3.0')
from gi.repository import Gtk # type: ignore
require_version('Pango', '1.0')
from gi.repository import Pango # type: ignore
# pylint: enable=wrong-import-position

LOGGER = logging.getLogger('ibus-typing-booster')

@functools.lru_cache(maxsize=1)
def _get_global_gtk_label() -> Gtk.Label:
    '''Create a reusable Gtk.Label, first call initializes'''
    return Gtk.Label()

@functools.lru_cache(maxsize=1)
def _get_global_pango_context() -> Pango.Context:
    '''Create a reusable Pango.Context, first call initializes'''
    return _get_global_gtk_label().get_pango_context()

@functools.lru_cache(maxsize=1)
def _get_global_pango_layout() -> Pango.Layout:
    '''Create a reusable Pango.Layout, first call initializes'''
    return Pango.Layout(_get_global_pango_context())

# @functools.cache is available only in Python >= 3.9.
#
# Python >= 3.9 is not available on RHEL8, not yet on openSUSE
# Tumbleweed (2021-22-29), ...
#
# But @functools.lru_cache(maxsize=None) is the same and it is
# available for Python >= 3.2, that means it should be available
# everywhere.

@functools.lru_cache(maxsize=None)
def get_font_file(family: str) -> str:
    '''Use Fontconfig to find the font file path for a given font family

    Examples:

    >>> get_font_file('Noto Color Emoji')
    '/home/mfabian/.fonts/Noto-COLRv1.ttf'

    >>> get_font_file('og-dcm-emoji')
    '/home/mfabian/.fonts/og-dcm-emoji.ttf'

    >>> get_font_file('This family does not exist.')
    '/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf'

    '''
    path = ''
    fc_match_binary = shutil.which('fc-match')
    if not fc_match_binary:
        return path
    try:
        family = family.replace('-', '\\-')
        output = subprocess.check_output([fc_match_binary, family, '--format', '%{file}'],
                                         stderr=subprocess.STDOUT,
                                         encoding='utf-8')
        path = output.strip()
    except FileNotFoundError as error:
        LOGGER.warning('Exception when calling %s: %s: %s',
                       fc_match_binary, error.__class__.__name__, error)
    except subprocess.CalledProcessError as error:
        LOGGER.warning('Exception when calling %s: %s: %s',
                       fc_match_binary, error.__class__.__name__, error)
    except Exception as error: # pylint: disable=broad-except
        LOGGER.warning('Exception when calling %s: %s: %s',
                       fc_match_binary, error.__class__.__name__, error)
    return path

@functools.lru_cache(maxsize=None)
def get_font_lang(family: str) -> str:
    '''Use Fontconfig to find the supported languages by font family matched with fc-match

    Examples:

    >>> get_font_lang('Noto Color Emoji')
    'und-zsye'
    '''
    lang = ''
    fc_match_binary = shutil.which('fc-match')
    if not fc_match_binary:
        return lang
    try:
        family = family.replace('-', '\\-')
        output = subprocess.check_output([fc_match_binary, family, '--format', '%{lang}'],
                                         stderr=subprocess.STDOUT,
                                         encoding='utf-8')
        lang = output.strip()
    except FileNotFoundError as error:
        LOGGER.warning('Exception when calling %s: %s: %s',
                       fc_match_binary, error.__class__.__name__, error)
    except subprocess.CalledProcessError as error:
        LOGGER.warning('Exception when calling %s: %s: %s',
                       fc_match_binary, error.__class__.__name__, error)
    except Exception as error: # pylint: disable=broad-except
        LOGGER.warning('Exception when calling %s: %s: %s',
                       fc_match_binary, error.__class__.__name__, error)
    return lang

@functools.lru_cache(maxsize=None)
def get_font_version(font_file: str) -> str:
    '''Use otfinfo to get the font version from a font file

    Examples:

    >>> get_font_version('/usr/share/fonts/google-noto-color-emoji-fonts/NotoColorEmoji.ttf')
    'Version 2.047;GOOG;noto-emoji:20240827:6c211821b8442ab3683a502f9a79b2034293fced'

    >>> get_font_version('/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf')
    'Version 2.37'

    >>> get_font_version('/this-file-does-not-exist.ttf')
    ''
    '''
    version = ''
    otfinfo_binary = shutil.which('otfinfo')
    if not otfinfo_binary:
        return version
    try:
        output = subprocess.check_output([otfinfo_binary, '-v', font_file],
                                         stderr=subprocess.STDOUT,
                                         encoding='utf-8')
        version = output.strip()
    except FileNotFoundError as error:
        LOGGER.warning('Exception when calling %s: %s: %s',
                       otfinfo_binary, error.__class__.__name__, error)
    except subprocess.CalledProcessError as error:
        LOGGER.warning('Exception when calling %s: %s: %s',
                       otfinfo_binary, error.__class__.__name__, error)
    except Exception as error: # pylint: disable=broad-except
        LOGGER.warning('Exception when calling %s: %s: %s',
                       otfinfo_binary, error.__class__.__name__, error)
    return version

@functools.lru_cache(maxsize=None)
def get_font_tables(font_file: str) -> List[str]:
    # pylint: disable=line-too-long
    '''Use otfinfo to get the OpenType tables in a font file

    (Only those which are interesting for rendering emoji)

    Examples:

    >>> get_font_tables('/usr/share/fonts/google-noto-color-emoji-fonts/NotoColorEmoji.ttf')
    ['CBDT']

    >>> get_font_tables('/home/mfabian/.fonts/Noto-COLRv1.ttf')
    ['COLR']

    >>> get_font_tables('/home/mfabian/.fonts/openmoji/OpenMoji-color-glyf_colr_1.ttf')
    ['COLR']

    >>> get_font_tables('/home/mfabian/.fonts/openmoji/OpenMoji-black-glyf.ttf')
    []

    # I do not have this font installed at the moment:
    #
    #>>> get_font_tables('/home/mfabian/.fonts/openmoji/OpenMoji-color-colr1_svg.ttf')
    #['COLR', 'SVG']

    >>> get_font_tables('/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf')
    []

    '''
    # pylint: enable=line-too-long
    tables: List[str] = []
    otfinfo_binary = shutil.which('otfinfo')
    if not otfinfo_binary:
        return tables
    try:
        output = subprocess.check_output([otfinfo_binary, '-t', font_file],
                                         stderr=subprocess.STDOUT,
                                         encoding='utf-8')
        pattern = re.compile(r'\s*(?P<size>[0-9]+)\s+(?P<table>\S+)\s*')
        for line in output.splitlines():
            match_result = pattern.match(line.strip())
            if match_result:
                _size = match_result.group('size')
                table = match_result.group('table')
                if table in ('CBDT', 'COLR', 'SVG'):
                    tables.append(table)
    except FileNotFoundError as error:
        LOGGER.warning('Exception when calling %s: %s: %s',
                       otfinfo_binary, error.__class__.__name__, error)
    except subprocess.CalledProcessError as error:
        LOGGER.warning('Exception when calling %s: %s: %s',
                       otfinfo_binary, error.__class__.__name__, error)
    except Exception as error: # pylint: disable=broad-except
        LOGGER.warning('Exception when calling %s: %s: %s',
                       otfinfo_binary, error.__class__.__name__, error)
    return tables

def get_available_font_names() -> List[str]:
    # pylint: disable=line-too-long
    '''Return a list of the names of fonts available on the system

    Examples:

    “Sans”, “Serif”, and “Monospace” are not “real” fonts but should
    always be available:

    >>> 'Sans' in get_available_font_names()
    True

    >>> 'Serif' in get_available_font_names()
    True

    >>> 'Monospace' in get_available_font_names()
    True

    “Noto Sans” is a real font which is probably avaible on most systems:

    >>> 'Noto Sans' in get_available_font_names()
    True
    '''
    # pylint: enable=line-too-long
    families =  _get_global_pango_context().list_families()
    return sorted([family.get_name() for family in families])

def get_fonts_used_for_text(
        font: str, text: str, fallback: bool = True) -> List[Tuple[str, Dict[str, Any]]]:
    # pylint: disable=line-too-long
    '''Return a list of fonts which were really used to render a text

    :param font: The font requested to render the text in
    :param text: The text to render
    :param fallback: Whether to enable font fallback. If disabled, then
                     glyphs will only be used from the closest matching
                     font on the system. No fallback will be done to other
                     fonts on the system that might contain the glyphs needed
                     for the text.

    Examples:

    Don’t run CI checks regularly on these examples, it depends too much
    on the fonts installed on the system used to do the test. The results
    are also locale dependent, the results below are with LC_ALL=en_US.UTF-8:

    >>> fonts_used = get_fonts_used_for_text('DejaVu Sans Mono', '😀 ')
    >>> len(fonts_used)
    2
    >>> fonts_used[0][0]
    '😀'
    >>> fonts_used[0][1]['font']
    'Noto Color Emoji'
    >>> fonts_used[0][1]['glyph-count']
    1
    >>> fonts_used[0][1]['visible']
    True
    >>> fonts_used[0][1]['glyph-available']
    True
    >>> fonts_used[0][1]['file']
    '/home/mfabian/.fonts/Noto-COLRv1.ttf'
    >>> fonts_used[0][1]['lang']
    'und-zsye'
    >>> fonts_used[0][1]['version']
    'Version 2.047;GOOG;noto-emoji:20240827:6c211821b8442ab3683a502f9a79b2034293fced'
    >>> fonts_used[0][1]['opentype-tables']
    ['COLR']
    >>> fonts_used[1][0]
    ' '
    >>> fonts_used[1][1]['font']
    'DejaVu Sans Mono'
    >>> fonts_used[1][1]['glyph-count']
    1
    >>> fonts_used[1][1]['visible']
    False
    >>> fonts_used[1][1]['glyph-available']
    True
    >>> fonts_used[1][1]['file']
    '/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf'
    >>> fonts_used[1][1]['lang']
    'aa|af|ar|ast|av|ay|az-az|az-ir|bm|be|bg|bi|bin|br|bs|bua|ca|ce|ch|chm|co|cs|cv|cy|da|de|el|en|eo|es|et|eu|fa|fi|fj|fo|fr|ff|fur|fy|ga|gd|gl|gn|gv|ha|haw|ho|hr|hu|hy|ia|ig|id|ie|ik|io|is|it|ka|kaa|ki|kk|kl|ku-am|kum|kv|kw|ky|la|lb|lez|ln|lt|lv|mg|mh|mi|mk|mo|mt|nb|nds|nl|nn|no|nr|nso|ny|oc|om|os|pl|pt|rm|ro|ru|sah|sco|se|sel|shs|sk|sl|sm|sma|smj|smn|so|sq|sr|ss|st|sv|sw|tk|tl|tn|to|tr|ts|tt|tw|tyv|uk|uz|ve|vo|vot|wa|wen|wo|xh|yap|yo|zu|ak|an|ber-dz|crh|csb|ee|fat|fil|hsb|ht|hz|jv|kab|kj|kr|ku-tr|kwm|lg|li|mn-mn|ms|na|ng|nv|pap-an|pap-aw|qu|quz|rn|rw|sc|sg|sn|su|ty|za|agr|ayc|bem|dsb|lij|mfe|mhr|miq|mjw|nhn|niu|rif|sgs|szl|tpi|unm|wae|yuw'
    >>> fonts_used[1][1]['version']
    'Version 2.37'

    >>> fonts_used = get_fonts_used_for_text('DejaVu Sans', '日本語 नमस्ते')
    >>> fonts_used[0][0]
    '日本語 '
    >>> fonts_used[0][1]['font']
    'Droid Sans'
    >>> fonts_used[0][1]['glyph-count']
    4
    >>> fonts_used[0][1]['visible']
    True
    >>> fonts_used[0][1]['file']
    '/usr/share/fonts/google-droid-sans-fonts/DroidSans.ttf'
    >>> fonts_used[0][1]['lang']
    'aa|ab|af|av|ay|ba|be|bg|bi|bin|br|bs|bua|ca|ce|ch|chm|co|cs|cu|cv|cy|da|de|el|en|eo|es|et|eu|fi|fj|fo|fr|fur|fy|gd|gl|gn|gv|ho|hr|hu|ia|ig|id|ie|ik|io|is|it|kaa|ki|kk|kl|kum|kv|ky|la|lb|lez|lt|lv|mg|mh|mk|mo|mt|nb|nds|nl|nn|no|nr|nso|ny|oc|om|os|pl|pt|rm|ro|ru|sah|se|sel|sh|sk|sl|sma|smj|smn|so|sq|sr|ss|st|sv|sw|tg|tk|tl|tn|tr|ts|tt|tyv|uk|uz|vo|vot|wa|wen|wo|xh|yap|zu|an|crh|csb|fil|hsb|ht|jv|kj|ku-tr|kwm|lg|li|mn-mn|ms|na|ng|pap-an|pap-aw|rn|rw|sc|sg|sn|su|ty|za|agr|ayc|bem|dsb|lij|mfe|mhr|miq|mjw|nhn|niu|szl|tpi|unm|wae|yuw'
    >>> fonts_used[0][1]['version']
    'Version 1.00 build 114'
    >>> fonts_used[1][0]
    'नमस्ते'
    >>> fonts_used[1][1]['font']
    'Noto Sans Devanagari'
    >>> fonts_used[1][1]['glyph-count']
    5
    >>> fonts_used[1][1]['visible']
    True
    >>> fonts_used[1][1]['file']
    '/usr/share/fonts/google-noto/NotoSansDevanagari-Regular.ttf'
    >>> fonts_used[1][1]['lang']
    'bh|bho|hi|kok|mr|ne|sa|hne|mai|brx|sat|doi|anp|bhb|hif|mag|raj|the'
    >>> fonts_used[1][1]['version']
    'Version 2.006; ttfautohint (v1.8.4.7-5d5b)'

    >>> fonts_used = get_fonts_used_for_text('DejaVu Sans', '日本語 🕉️')
    >>> fonts_used[0][0]
    '日本語 '
    >>> fonts_used[0][1]['font']
    'Droid Sans'
    >>> fonts_used[0][1]['glyph-count']
    4
    >>> fonts_used[0][1]['visible']
    True
    >>> fonts_used[0][1]['file']
    '/usr/share/fonts/google-droid-sans-fonts/DroidSans.ttf'
    >>> fonts_used[0][1]['lang']
    'aa|ab|af|av|ay|ba|be|bg|bi|bin|br|bs|bua|ca|ce|ch|chm|co|cs|cu|cv|cy|da|de|el|en|eo|es|et|eu|fi|fj|fo|fr|fur|fy|gd|gl|gn|gv|ho|hr|hu|ia|ig|id|ie|ik|io|is|it|kaa|ki|kk|kl|kum|kv|ky|la|lb|lez|lt|lv|mg|mh|mk|mo|mt|nb|nds|nl|nn|no|nr|nso|ny|oc|om|os|pl|pt|rm|ro|ru|sah|se|sel|sh|sk|sl|sma|smj|smn|so|sq|sr|ss|st|sv|sw|tg|tk|tl|tn|tr|ts|tt|tyv|uk|uz|vo|vot|wa|wen|wo|xh|yap|zu|an|crh|csb|fil|hsb|ht|jv|kj|ku-tr|kwm|lg|li|mn-mn|ms|na|ng|pap-an|pap-aw|rn|rw|sc|sg|sn|su|ty|za|agr|ayc|bem|dsb|lij|mfe|mhr|miq|mjw|nhn|niu|szl|tpi|unm|wae|yuw'
    >>> fonts_used[0][1]['version']
    'Version 1.00 build 114'
    >>> fonts_used[1][0]
    '🕉️'
    >>> fonts_used[1][1]['font']
    'Noto Color Emoji'
    >>> fonts_used[1][1]['glyph-count']
    1
    >>> fonts_used[1][1]['visible']
    True
    >>> fonts_used[1][1]['file']
    '/home/mfabian/.fonts/Noto-COLRv1.ttf'
    >>> fonts_used[1][1]['lang']
    'und-zsye'
    >>> fonts_used[1][1]['version']
    'Version 2.047;GOOG;noto-emoji:20240827:6c211821b8442ab3683a502f9a79b2034293fced'
    >>> fonts_used[1][1]['opentype-tables']
    ['COLR']

    >>> fonts_used = get_fonts_used_for_text('DejaVu Sans', '🕉\uFE0F')
    >>> fonts_used[0][0]
    '🕉️'
    >>> fonts_used[0][1]['font']
    'Noto Color Emoji'
    >>> fonts_used[0][1]['glyph-count']
    1
    >>> fonts_used[0][1]['visible']
    True
    >>> fonts_used[0][1]['file']
    '/home/mfabian/.fonts/Noto-COLRv1.ttf'
    >>> fonts_used[0][1]['lang']
    'und-zsye'
    >>> fonts_used[0][1]['version']
    'Version 2.047;GOOG;noto-emoji:20240827:6c211821b8442ab3683a502f9a79b2034293fced'
    >>> fonts_used[0][1]['opentype-tables']
    ['COLR']
    '''
    # pylint: enable=line-too-long
    fonts_used = []
    text_utf8 = text.encode('UTF-8', errors='replace')
    pango_layout = _get_global_pango_layout()
    pango_font_description = Pango.font_description_from_string(font)
    pango_layout.set_font_description(pango_font_description)
    pango_attr_list = Pango.AttrList()
    pango_attr_fallback = Pango.attr_fallback_new(fallback)
    pango_attr_list.insert(pango_attr_fallback)
    pango_layout.set_attributes(pango_attr_list)
    pango_layout.set_text(text)
    pango_layout_line = pango_layout.get_line_readonly(0)
    gs_list = pango_layout_line.runs
    for glyph_item in gs_list:
        pango_item = glyph_item.item
        offset = pango_item.offset
        length = pango_item.length
        # _num_chars = pango_item.num_chars
        pango_glyph_string = glyph_item.glyphs
        num_glyphs = pango_glyph_string.num_glyphs
        pango_analysis = pango_item.analysis
        pango_font = pango_analysis.font
        font_description_used = pango_font.describe()
        run_text = text_utf8[offset:offset + length].decode(
            'UTF-8', errors='replace')
        run_family = font_description_used.get_family()
        pango_layout_run = _get_global_pango_layout()
        pango_layout_run.set_font_description(pango_font_description)
        pango_layout_run.set_attributes(pango_attr_list)
        pango_layout_run.set_text(run_text)
        pango_layout_run_line = pango_layout_run.get_line_readonly(0)
        visible = False
        ink_rect, _logical_rect = pango_layout_run_line.get_pixel_extents()
        if ink_rect.width > 0 and ink_rect.height > 0:
            visible = True
        results_for_run = {
            'font': run_family,
            'glyph-count': num_glyphs,
            'visible': visible}
        if (num_glyphs == 1
            and len(run_text) == 1
            and hasattr(Pango.Font, 'has_char')):
            results_for_run['glyph-available'] = pango_font.has_char(
                run_text)
        path = get_font_file(run_family)
        if path:
            results_for_run['file'] = path
            lang = get_font_lang(run_family)
            if lang:
                results_for_run['lang'] = lang
            version = get_font_version(path)
            if version:
                results_for_run['version'] = version
            open_type_tables = get_font_tables(path)
            if open_type_tables:
                results_for_run['opentype-tables'] = open_type_tables
        fonts_used.append((run_text, results_for_run))
    return fonts_used

def emoji_font_fallback_needed(font: str, text: str) -> bool:
    '''
    Examples:

    Twemoji does not support the emoji sequence for “head shaking vertically”
    (U+1F642 U+200D U+2195, added in Unicode 15.1):

    >>> emoji_font_fallback_needed('Twemoji', '🙂‍↕️')
    True

    Twemoji does not have the flag of Sark (U+1F1E8 U+1F1F6, added in Unicode 16.0):

    >>> emoji_font_fallback_needed('Twemoji',  '🇨🇶')
    True

    Twemoji does not have U+1FAE9 FACE WITH BAGS UNDER EYES (added in Unicode 16.0):

    >>> emoji_font_fallback_needed('Twemoji', '🫩')
    True

    But Twemoji has U+1F925 LYING FACE (added in Unicode 9.0):

    >>> emoji_font_fallback_needed('Twemoji', '🤥')
    False

    >>> emoji_font_fallback_needed('Twemoji', '☺\ufe0f')
    False

    Twemoji does support the emoji sequence for the flag of Wales
    (U+1F3F4 U+E0067 U+E0062 U+E0077 U+E006C U+E0073 U+E007F):

    >>> emoji_font_fallback_needed('Twemoji', '🏴󠁧󠁢󠁷󠁬󠁳󠁿')
    False

    Twemoji does not have regular Latin characters like “A”:

    >>> emoji_font_fallback_needed('Twemoji', 'A')
    True

    But of course any standard font has “A”:

    >>> emoji_font_fallback_needed('Sans', 'A')
    False

    If the text given contains more than one emoji, then we don’t know and
    the result is always True because a fallback might be needed:

    >>> emoji_font_fallback_needed('Twemoji', '🏴󠁧󠁢󠁷󠁬󠁳󠁿🤥')
    True

    >>> emoji_font_fallback_needed('OpenMoji Color', '🧗‍♀️')
    False
    '''
    if not font:
        return True
    if not text:
        return False
    fonts_used = get_fonts_used_for_text(font, text, fallback=False)
    if not fonts_used:
        return False
    if len(fonts_used) > 1:
        # If there is more than one run, that means the text contained more
        # then just a single emoji or a single character. A fallback
        # might be needed in that case, that is hard to tell. Just
        # assume it is needed for the moment:
        return True
    results_for_run = fonts_used[0][1]
    if (results_for_run['glyph-count'] > 1
        or not results_for_run['visible']
        or ('glyph-available' in results_for_run
            and not results_for_run['glyph-available'])):
        text_new = text
        for char in ('\uFE0E', '\uFE0F'):
            # With some fonts sequences containing variations selectors
            # get extra glyphs for the variation selectors, even though
            # these are invisible and apparently irrelevant for whether
            # the font supports the emoji or not.
            #
            # For example with “Twemoji”, '☺\uFE0F' gets 1 glyph but with
            # “Twitter Color Emoji” it gets 2 glyphs and both fonts
            # support that emoji.  Another example is 😶‍🌫️ U+1F636 U+200D
            # U+1F32B U+FE0F FACE IN CLOUDS which gets two glyphs when
            # using the black and white “Noto Emoji” font but the second
            # glyph is for U+FE0F and irrelevant.  ❤️‍🔥 U+2764 U+FE0F
            # U+200D U+1F525 HEART ON FIRE also gets two glyphs with “Noto
            # Emoji” but only one if the U+FE0F is removed.
            #
            # If the original sequence which might contain variation
            # selectors was already detected as supported False should
            # be returned, no fallback is needed then. If it was
            # detected as not supported, try again with the variation
            # selectors removed, if that is detected as supported, no
            # fallback is needed.
            text_new = text_new.replace(char, '')
        if text_new == text:
            # Variation selectors were already removed or didn’t exist
            # in the first place:
            return True
        # Try again with the variation selectors removed:
        return emoji_font_fallback_needed(font, text_new)
    return False

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
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    import doctest
    (FAILED, _ATTEMPTED) = doctest.testmod()
    LOGGER.info('get_font_file() cache info: %s', get_font_file.cache_info())
    LOGGER.info('get_font_version() cache info: %s', get_font_version.cache_info())
    LOGGER.info('get_font_tables() cache info: %s', get_font_tables.cache_info())
    sys.exit(FAILED)
