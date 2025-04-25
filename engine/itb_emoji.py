# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2015-2018 Mike FABIAN <mfabian@redhat.com>
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

'''A module used by ibus-typing-booster to match emoji and similar
Unicode characters.

'''

from typing import Any
from typing import List
from typing import Tuple
from typing import Dict
from typing import Set
from typing import Optional
from typing import Iterable
from typing import Callable
import os
import sys
import re
import functools
import itertools
import gzip
import json
import unicodedata
import html
import logging
import gettext
import itb_util

DOMAINNAME = 'ibus-typing-booster'
_: Callable[[str], str] = lambda a: gettext.dgettext(DOMAINNAME, a)
N_: Callable[[str], str] = lambda a: a

IMPORT_RAPIDFUZZ_SUCCESSFUL = False
try:
    import rapidfuzz
    IMPORT_RAPIDFUZZ_SUCCESSFUL = True
except (ImportError,):
    IMPORT_RAPIDFUZZ_SUCCESSFUL = False

IMPORT_ENCHANT_SUCCESSFUL = False
try:
    import enchant # type: ignore
    IMPORT_ENCHANT_SUCCESSFUL = True
except (ImportError,):
    IMPORT_ENCHANT_SUCCESSFUL = False

IMPORT_PYKAKASI_SUCCESSFUL = False
try:
    import pykakasi
    IMPORT_PYKAKASI_SUCCESSFUL = True
    KAKASI_INSTANCE = pykakasi.kakasi() # type: ignore
except (ImportError,):
    IMPORT_PYKAKASI_SUCCESSFUL = False

IMPORT_PINYIN_SUCCESSFUL = False
try:
    import pinyin # type: ignore
    IMPORT_PINYIN_SUCCESSFUL = True
except (ImportError,):
    IMPORT_PINYIN_SUCCESSFUL = False

LOGGER = logging.getLogger('ibus-typing-booster')

DATADIR = os.path.join(os.path.dirname(__file__), '../data')
# USER_DATADIR will be “~/.local/share/ibus-typing-booster/data” by default
USER_DATADIR = itb_util.xdg_save_data_path('ibus-typing-booster/data')
CLDR_ANNOTATION_DIRNAMES = (
    USER_DATADIR, DATADIR,
    # On Fedora >= 25 there is a
    # “cldr-emoji-annotation” package which has the
    # .xml files here in the subdirs “annotations”
    # and “annotationsDerived”:
    '/usr/share/unicode/cldr/common/',
    '/local/mfabian/src/cldr/common/')

UNICODE_CATEGORIES = {
    'Cc': {'valid': False, 'major': 'Other', 'minor': 'Control'},
    # 'Cf' contains RIGHT-TO-LEFT MARK ...
    'Cf': {'valid': True, 'major': 'Other', 'minor': 'Format'},
    'Cn': {'valid': False, 'major': 'Other', 'minor': 'Not assigned'},
    'Co': {'valid': False, 'major': 'Other', 'minor': 'Private use'},
    'Cs': {'valid': False, 'major': 'Other', 'minor': 'Surrogate'},
    'Ll': {'valid': False, 'major': 'Letter', 'minor': 'Lowercase'},
    'Lm': {'valid': False, 'major': 'Letter', 'minor': 'Modifier'},
    'Lo': {'valid': False, 'major': 'Letter', 'minor': 'Other'},
    'Lt': {'valid': False, 'major': 'Letter', 'minor': 'Titlecase'},
    'Lu': {'valid': False, 'major': 'Letter', 'minor': 'Uppercase'},
    'Mc': {'valid': False, 'major': 'Mark', 'minor': 'Spacing combining'},
    'Me': {'valid': False, 'major': 'Mark', 'minor': 'Enclosing'},
    'Mn': {'valid': False, 'major': 'Mark', 'minor': 'Nonspacing'},
    'Nd': {'valid': False, 'major': 'Number', 'minor': 'Decimal digit'},
    'Nl': {'valid': False, 'major': 'Number', 'minor': 'Letter'},
    # 'No' contains SUPERSCRIPT ONE ...
    'No': {'valid': True, 'major': 'Number', 'minor': 'Other'},
    'Pc': {'valid': True, 'major': 'Punctuation', 'minor': 'Connector'},
    'Pd': {'valid': True, 'major': 'Punctuation', 'minor': 'Dash'},
    'Pe': {'valid': True, 'major': 'Punctuation', 'minor': 'Close'},
    'Pf': {'valid': True, 'major': 'Punctuation', 'minor': 'Final quote'},
    'Pi': {'valid': True, 'major': 'Punctuation', 'minor': 'Initial quote'},
    'Po': {'valid': True, 'major': 'Punctuation', 'minor': 'Other'},
    'Ps': {'valid': True, 'major': 'Punctuation', 'minor': 'Open'},
    'Sc': {'valid': True, 'major': 'Symbol', 'minor': 'Currency'},
    'Sk': {'valid': True, 'major': 'Symbol', 'minor': 'Modifier'},
    'Sm': {'valid': True, 'major': 'Symbol', 'minor': 'Math'},
    'So': {'valid': True, 'major': 'Symbol', 'minor': 'Other'},
    'Zl': {'valid': True, 'major': 'Separator', 'minor': 'Line'},
    'Zp': {'valid': True, 'major': 'Separator', 'minor': 'Paragraph'},
    'Zs': {'valid': True, 'major': 'Separator', 'minor': 'Space'},
}

EMOJI_VERSION_TO_UNICODE_VERSIONS = {
    # See: https://emojipedia.org/emoji-versions
    '1.0': ['6.0', '6.1', '7.0', '8.0'],
    # No Unicode update, only new sequences and emoji presentations
    # for existing code points:
    '2.0': ['6.0', '6.1', '7.0', '8.0'],
    '3.0': ['9.0'],
    '4.0': ['9.0'],
    '5.0': ['10.0'],
    # Emoji versions 6.0-10.0 do not exist.  It was decided that from
    # 11.0 on, the emoji version should align with the Unicode
    # version:
    '11.0': ['11.0'],
    '12.0': ['12.0'],
    # No Unicode update, only new sequences and emoji presentations
    # for existing code points:
    '12.1': ['12.0'],
    '13.0': ['13.0'],
    # No Unicode update, only new sequences and emoji presentations
    # for existing code points:
    '13.1': ['13.0'],
    '14.0': ['14.0'],
    '15.0': ['15.0'],
    '15.1': ['15.1'],
    '16.0': ['16.0'],
    '17.0': ['17.0'],
}

# VALID_RANGES are taken from ibus-uniemoji
# (but not used anymore at the moment)
VALID_RANGES = (
    (0x0024, 0x0024), # DOLLAR SIGN
    (0x00a2, 0x00a5), # CENT SIGN, POUND SIGN, CURRENCY SIGN, YEN SIGN
    (0x058f, 0x058f), # ARMENIAN DRAM SIGN
    (0x060b, 0x060b), # AFGHANI SIGN
    (0x09f2, 0x09f3), # BENGALI RUPEE MARK, BENGALI RUPEE SIGN
    (0x09fb, 0x09fb), # BENGALI GANDA MARK
    (0x0af1, 0x0af1), # GUJARATI RUPEE SIGN
    (0x0bf9, 0x0bf9), # TAMIL RUPEE SIGN
    (0x0e3f, 0x0e3f), # THAI CURRENCY SYMBOL BAHT
    (0x17db, 0x17db), # KHMER CURRENCY SYMBOL RIEL
    (0x2000, 0x206f), # General Punctuation, Layout Controls,
                      # Invisible Operators
    (0x2070, 0x209f), # Superscripts and Subscripts
    (0x20a0, 0x20cf), # Currency Symbols
    (0x20d0, 0x20ff), # Combining Diacritical Marks for Symbols
    (0x2100, 0x214f), # Additional Squared Symbols, Letterlike Symbols
    (0x2150, 0x218f), # Number Forms
    (0x2190, 0x21ff), # Arrows
    (0x2200, 0x22ff), # Mathematical Operators
    (0x2300, 0x23ff), # Miscellaneous Technical, Floors and Ceilings
    (0x2336, 0x237a), # APL symbols
    (0x2400, 0x243f), # Control Pictures
    (0x2440, 0x245f), # Optical Character Recognition (OCR)
    (0x2460, 0x24ff), # Enclosed Alphanumerics
    (0x2500, 0x257f), # Box Drawing
    (0x2580, 0x259f), # Block Elements
    (0x25a0, 0x25ff), # Geometric Shapes
    (0x2600, 0x26ff), # Miscellaneous Symbols
    (0x2616, 0x2617), # Japanese Chess
    (0x2654, 0x265f), # Chess
    (0x2660, 0x2667), # Card suits
    (0x2630, 0x2637), # Yijing Trigrams
    (0x268a, 0x268f), # Yijing Monograms and Digrams
    (0x26c0, 0x26c3), # Checkers/Draughts
    (0x2700, 0x27bf), # Dingbats
    (0x27c0, 0x27ef), # Miscellaneous Mathematical Symbols-A
    (0x27f0, 0x27ff), # Supplemental Arrows-A
    (0x2800, 0x28ff), # Braille Patterns
    (0x2900, 0x297f), # Supplemental Arrows-B
    (0x2980, 0x29ff), # Miscellaneous Mathematical Symbols-B
    (0x2a00, 0x2aff), # Supplemental Mathematical Operators
    (0x2b00, 0x2bff), # Additional Shapes, Miscellaneous Symbols and Arrows
    (0xa838, 0xa838), # NORTH INDIC RUPEE MARK
    (0xfdfc, 0xfdfc), # RIAL SIGN
    (0xfe69, 0xfe69), # SMALL DOLLAR SIGN
    (0xff01, 0xff60), # Fullwidth symbols and currency signs
    (0x1f300, 0x1f5ff), # Miscellaneous Symbols and Pictographs
    (0x1f600, 0x1f64f), # Emoticons
    (0x1f650, 0x1f67f), # Ornamental Dingbats
    (0x1f680, 0x1f6ff), # Transport and Map Symbols
    (0x1f900, 0x1f9ff), # Supplemental Symbols and Pictographs
)

VALID_CHARACTERS = {
    'ﷺ', # ARABIC LIGATURE SALLALLAHOU ALAYHE WASALLAM
    'ﷻ', # ARABIC LIGATURE JALLAJALALOUHOU
    '﷽', # ARABIC LIGATURE BISMILLAH AR-RAHMAN AR-RAHEEM
    # https://en.wikipedia.org/wiki/Biangbiang_noodles
    # simplified Chinese: 𰻝𰻝面; traditional Chinese: 𰻞𰻞麵; pinyin: Biángbiángmiàn
    '𰻞', # CJK IDEOGRAPH-30EDE biáng traditional
    '𰻝', # CJK IDEOGRAPH-30EDD biáng simplified
}
UNICODE_DATA_EXTRA_LINES = (
    '30EDE;<CJK Ideograph Extension G> biáng Traditional Chinese;Lo;0;L;;;;;N;;;;;',
    '30EDD;<CJK Ideograph Extension G> biáng Simplified Chinese;Lo;0;L;;;;;N;;;;;',
)

SKIN_TONE_MODIFIERS = ('🏻', '🏼', '🏽', '🏾', '🏿')

def is_invisible(text: str) -> bool:
    '''Checks whether a text is invisible

    Returns True if the text is invisible, False if not.

    May return True for some texts which are not completely
    invisible but hard to see in most fonts.

    :param text: The text

    Examples:

    >>> is_invisible('a')
    False

    >>> is_invisible(' ')
    True

    >>> is_invisible(' a')
    False

    >>> is_invisible('  ')
    True

    >>> is_invisible('')
    True
    '''
    return all(unicodedata.category(character)
               in ('Cc', 'Cf', 'Zl', 'Zp', 'Zs') for character in text)

if IMPORT_PYKAKASI_SUCCESSFUL:
    def kakasi_convert(text: str, target: str='orig') -> str:
        '''
        Convert Japanese text to hiragana, katakana, or romaji

        :param text: The text to be converted
        :param target: The target to be converted to, can be:
                       'orig':     return original text, no conversion
                       'hira':     convert to hiragana
                       'kana':     convert to katakana
                       'hepburn':  convert to Hepburn romanization
                       'kunrei':   convert to Kunrei romanization
                       'passport': convert to Passport romanization

        Examples:

        >>> kakasi_convert('かな漢字')
        'かな漢字'

        >>> kakasi_convert('かな漢字', target='hira')
        'かなかんじ'

        >>> kakasi_convert('かな, foobar, 漢字,', target='hira')
        'かな, foobar, かんじ,'

        >>> kakasi_convert('かな漢字', target='kana')
        'カナカンジ'

        >>> kakasi_convert('かな漢字', target='hepburn')
        'kanakanji'

        >>> kakasi_convert('かな漢字', target='kunrei')
        'kanakanzi'

        >>> kakasi_convert('かな漢字', target='passport')
        'kanakanji'
        '''
        if not IMPORT_PYKAKASI_SUCCESSFUL or target == 'orig':
            return text
        result = ''
        for item in KAKASI_INSTANCE.convert(text):
            result += item[target]
        return result

def _in_range(codepoint: int) -> bool:
    '''Checks whether the codepoint is in one of the valid ranges

    Returns True if the codepoint is in one of the valid ranges,
    else it returns False.

    :param codepoint: The Unicode codepoint to check

    Examples:

    >>> _in_range(0x1F915)
    True

    >>> _in_range(0x1F815)
    False

    >>> _in_range(ord('€'))
    True

    >>> _in_range(ord('₹'))
    True

    >>> _in_range(ord('₺'))
    True
    '''
    return any( # pylint: disable=use-a-generator
        [x <= codepoint <= y for x, y in VALID_RANGES])

def _find_path_and_open_function(
        dirnames: Iterable[str],
        basenames: Iterable[str],
        subdir: str = '') -> Tuple[str, Optional[Callable[[Any], Any]]]:
    '''Find the first existing file of a list of basenames and dirnames

    For each file in “basenames”, tries whether that file or the
    file with “.gz” added can be found in the list of directories
    “dirnames” where “subdir” is added to each directory in the list.

    Returns a tuple (path, open_function) where “path” is the
    complete path of the first file found and the open function
    is either “open()” or “gzip.open()”.

    :param dirnames: A list of directories to search in
    :param basenames: A list of file names to search for
    :param subdir: A subdirectory to be added to each directory in the list
    '''
    for basename in basenames:
        for dirname in dirnames:
            path = os.path.join(dirname, subdir, basename)
            if os.path.exists(path):
                if path.endswith('.gz'):
                    return (path, gzip.open)
                return (path, open)
            path = os.path.join(dirname, subdir, basename + '.gz')
            if os.path.exists(path):
                return (path, gzip.open)
    return ('', None)

def find_cldr_annotation_path(language: str) -> str:
    '''
    Finds which CLDR annotation file would be used for the language given

    Returns the full path of the  file found or an empty string if
    no file can be found for the language given.

    This function is intended to be used by the ibus-typing-booster
    setup tool to check whether CLDR annotations exist for a certain
    language.

    :param language: The language to search the annotation file for
    '''
    dirnames = CLDR_ANNOTATION_DIRNAMES
    locale = itb_util.parse_locale(language)
    acceptable_match = locale.language
    if locale.script:
        acceptable_match += '_' + locale.script
    for _language in itb_util.expand_languages([language]):
        basenames = (_language + '.xml',)
        (path, dummy_open_function) = _find_path_and_open_function(
            dirnames, basenames, subdir='annotations')
        if path and os.path.basename(path).startswith(acceptable_match):
            return path
    return ''

# @functools.cache is available only in Python >= 3.9.
#
# Python >= 3.9 is not available on RHEL8, not yet on openSUSE
# Tumbleweed (2021-22-29), ...
#
# But @functools.lru_cache(maxsize=None) is the same and it is
# available for Python >= 3.2, that means it should be available
# everywhere.
#
# Many keywords are of course shared by many emoji, therefore the
# query string is often matched against labels already matched
# previously. Caching previous matches speeds it up quite a bit.
@functools.lru_cache(maxsize=None)
def _match_classic(label: str, match_string: str) -> float:
    '''Matches a label from the emoji data against the query string.'''
    label = itb_util.remove_accents(label.lower())
    total_score = 0.0
    label_words = set(label.split())
    label_no_spaces = label.replace(' ', '')
    # Sort longest words first.
    word_list = sorted(match_string.split(sep=None), key=len, reverse=True)
    word_set = set(word_list)
    # Exact set match (highest priority)
    # For example 'black cat' counts as an exact match for 'cat black'.
    if label_words == word_set:
        total_score += 1000.0
    # Exact word matches
    for word in word_set:
        # use set() here to avoid making an exact match stronger
        # just because a word happens to be twice in the input.
        if word == label:
            total_score += 300.0 if len(word_list) == 1 else 200.0

    # Substring matches
    tmp_label = label
    tmp_no_spaces = label_no_spaces
    for word in word_list:
        # Match at word boundaries
        match_start = tmp_label.find(word)
        if match_start >= 0:
            if match_start == 0 or tmp_label[match_start - 1] == ' ':
                total_score += 120.0 if match_start == 0 else 100.0
                total_score += len(word)
                # Slight speed improvement, removing the part of
                # the string which has already been matched makes
                # the string shorter and speeds up matching the
                # remaining words
                tmp_label = tmp_label[:match_start] + tmp_label[match_start + len(word):]

        # Match with spaces ignored
        match_start = tmp_no_spaces.find(word)
        if match_start >= 0:
            total_score += 40.0 if match_start == 0 else 20.0
            total_score += len(word)
            # Slight speed improvement, removing the part of the
            # string which has already been matched makes the
            # string shorter and speeds up matching the remaining
            # words
            tmp_no_spaces = tmp_no_spaces[:match_start] + tmp_no_spaces[match_start + len(word):]
    return total_score

@functools.lru_cache(maxsize=None)
def _match_rapidfuzz(label: str, match_string: str) -> float:
    '''Matches a label from the emoji data against the query string using rapidfuzz.'''
    label = itb_util.remove_accents(label.lower())
    return rapidfuzz.fuzz.token_set_ratio(label, match_string, score_cutoff=90.0)

class EmojiMatcher():
    '''A class to find Emoji which best match a query string'''

    def __init__(self, languages: Iterable[str] = ('en_US',),
                 unicode_data: bool = True,
                 unicode_data_all: bool = False,
                 emoji_unicode_min: str = '0.0',
                 emoji_unicode_max: str = '100.0',
                 cldr_data: bool = True,
                 variation_selector: str = 'emoji',
                 romaji: bool = True,
                 match_algorithm: str = 'rapidfuzz') -> None:
        '''
        Initialize the emoji matcher

        :param languages: A list of languages to use for matching emoji
        :param unicode_data: Whether to load the UnicodeData.txt file as well
        :param unicode_data_all: Whether to load *all* of the Unicode
                                 characters from UnicodeData.txt.
                                 If False, most regular letters are omitted.
        :param cldr_data: Whether to load data from CLDR as well
        :param romaji: Whether to add Latin transliteration for Japanese.
                       Works only when pykakasi is available, if this is not
                       the case, this option is ignored.
        '''
        self._languages = languages
        self._gettext_translations: Dict[str, Any] = {}
        for language in itb_util.expand_languages(self._languages):
            mo_file = gettext.find(DOMAINNAME, languages=[language])
            if (mo_file
                    and
                    '/' + language  + '/LC_MESSAGES/' + DOMAINNAME + '.mo'
                    in mo_file):
                # Get the gettext translation instance only if a
                # translation file for this *exact* language was
                # found.  Ignore it if only a fallback was found. For
                # example, if “de_DE” was requested and only “de” was
                # found, ignore it.
                try:
                    self._gettext_translations[language] = gettext.translation(
                        DOMAINNAME, languages=[language])
                except (OSError, ):
                    self._gettext_translations[language] = None
            else:
                self._gettext_translations[language] = None
        self._unicode_data_all = unicode_data_all
        self._emoji_unicode_min = emoji_unicode_min
        self._emoji_unicode_max = emoji_unicode_max
        self._variation_selector = variation_selector
        self._romaji = romaji
        self._unicode_blocks: Dict[range, str] = {}
        self._enchant_dicts = []
        if IMPORT_ENCHANT_SUCCESSFUL:
            for language in self._languages:
                if enchant.dict_exists(language):
                    self._enchant_dicts.append(enchant.Dict(language))
        self._emoji_dict: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._candidate_cache: Dict[
            Tuple[str, int, str], List[itb_util.PredictionCandidate]] = {}
        self._match_function: Callable[[Any, Any], Any] = _match_classic
        self._good_match_score: float = 90.0
        self.set_match_algorithm(match_algorithm)
        # The three data sources are loaded in this order on purpose.
        # The data from Unicode is loaded first to put the official
        # names first into the list of names to display the official
        # names in the candidates, if possible.  The second best names
        # are the long names of emojione.
        if unicode_data:
            self._load_unicode_data()
        self._load_unicode_emoji_data()
        self._load_unicode_emoji_sequences()
        self._load_unicode_emoji_zwj_sequences()
        self._load_derived_age()
        self._load_unicode_emoji_test()
        self._load_emojione_data()
        if cldr_data:
            for language in itb_util.expand_languages(self._languages):
                self._load_cldr_annotation_data(language, 'annotations')
                self._load_cldr_annotation_data(language, 'annotationsDerived')
        self._load_unicode_blocks()

    def set_match_algorithm(self, name: str = 'rapidfuzz') -> None:
        '''Sets the match algorithm

        Currently supported: 'rapidfuzz', 'classic'

        When 'rapidfuzz is requested byt `import rapidfuzz` has failed,
        a fallback to 'classic' is used.

        Changing the match algorithm clears the candidate cache.
        '''
        self._candidate_cache = {}
        if name == 'rapidfuzz' and  IMPORT_RAPIDFUZZ_SUCCESSFUL:
            self._match_function = _match_rapidfuzz
            self._good_match_score = 90.0
            return
        if name == 'classic':
            self._good_match_score = 200.0
            self._match_function = _match_classic
            return
        self._good_match_score = 200.0
        self._match_function = _match_classic
        return

    def get_languages(self) -> List[str]:
        # pylint: disable=line-too-long
        '''Returns a copy of the list of languages of this EmojiMatcher

        Useful to check whether an already available EmojiMatcher instance
        can be used or whether one needs a new instance because one needs
        a different list of languages.

        Note that the order of that list is important, a matcher which
        supports the same languages but in an different order might
        return different results.

        Examples:

        >>> m = EmojiMatcher(languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        >>> m.get_languages()
        ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP']

        '''
        # pylint: enable=line-too-long
        #
        # Use list() to make a copy instead of self._languages[:] because
        # the latter might return the default tuple ('en_US',) instead
        # of a list ['en_US'] which makes comparison with another list
        # more inconvenient:
        return list(self._languages)

    def variation_selector_normalize(
            self, emoji_string: str, variation_selector: str ='emoji') -> str:
        # pylint: disable=line-too-long
        '''Removes or adds emoji presentation selectors

        U+FE0E VARIATION SELECTOR-15 selects text presentation
        U+FE0F VARIATION SELECTOR-16 selects emoji presentation

        Returns the possibly changed sequence.

        If emoji_string is equal to '\ufe0e' or '\ufe0f', it is returned unchanged.

        See:

        http://unicode.org/reports/tr51/#Emoji_Variation_Selector_Notes
        http://unicode.org/reports/tr51/#def_fully_qualified_emoji_zwj_sequence
        http://unicode.org/reports/tr51/#def_non_fully_qualified_emoji_zwj_sequence

        :param emoji_string: The emoji sequence to change.
        :param variation_selector: If 'emoji', make it a fully qualified
                                   sequence using VS16 characters as needed.
                                   If 'text' use VS15 characters as needed
                                   to choose the text presentation of the emojis.
                                   If it is neither 'emoji' nor 'text',  remove
                                   all VS15 and VS16 characters.

        Examples:

        >>> matcher = EmojiMatcher()

        If variation_selector is neither 'emoji' nor 'text, all variation selectors
        are removed from a sequence, no matter whether the sequence
        was correct or not:

        >>> matcher.variation_selector_normalize('⛹\ufe0f\u200d♀\ufe0f', variation_selector='')
        '⛹\u200d♀'

        >>> matcher.variation_selector_normalize('⛹🏿\u200d♀\ufe0f', variation_selector='')
        '⛹🏿\u200d♀'

        >>> matcher.variation_selector_normalize('#\ufe0f⃣', variation_selector='')
        '#⃣'

        >>> matcher.variation_selector_normalize('#⃣\ufe0f', variation_selector='')
        '#⃣'

        If variation_selector='emoji', variation selectors-16 are added to
        sequences as needed to make sequences fully qualified
        and incorrect sequences are repaired:

        >>> matcher.variation_selector_normalize('⛹🏿\ufe0f\u200d♀\ufe0f', variation_selector='emoji')
        '⛹🏿\u200d♀\ufe0f'

        >>> matcher.variation_selector_normalize('⛹\ufe0f🏿\u200d♀\ufe0f', variation_selector='emoji')
        '⛹🏿\u200d♀\ufe0f'

        >>> matcher.variation_selector_normalize('⛹\u200d\ufe0f♀', variation_selector='emoji')
        '⛹\ufe0f\u200d♀\ufe0f'

        >>> matcher.variation_selector_normalize('#⃣\ufe0f', variation_selector='emoji')
        '#\ufe0f⃣'

        >>> matcher.variation_selector_normalize('⛹\ufe0f♀', variation_selector='emoji')
        '⛹\ufe0f♀\ufe0f'

        >>> matcher.variation_selector_normalize('⛹', variation_selector='emoji')
        '⛹\ufe0f'
        '''
        # pylint: enable=line-too-long
        if emoji_string in {'\ufe0e', '\ufe0f'}:
            return emoji_string
        emoji_string = emoji_string.replace('\ufe0e', '').replace('\ufe0f', '')
        if variation_selector not in ('emoji', 'text'):
            return emoji_string
        if '\U0001f1e6' <= emoji_string[0] <= '\U0001f1ff':
            # do not insert any variation selectors in flag sequences:
            return emoji_string
        result: List[str] = []
        selector = '\ufe0f' if variation_selector == 'emoji' else '\ufe0e'
        for index, character in enumerate(emoji_string):
            result.append(character)
            is_last = index == len(emoji_string) - 1
            next_character = emoji_string[index + 1] if not is_last else ''
            is_skin_tone_next = next_character in SKIN_TONE_MODIFIERS
            if (character not in SKIN_TONE_MODIFIERS
                and 'Emoji' in self.properties(character)
                and (variation_selector == 'text'
                     or 'Emoji_Presentation' not in self.properties(character))
                and not is_skin_tone_next):
                result.append(selector)
        return ''.join(result)

    def _add_to_emoji_dict(
            self,
            emoji_dict_key: Tuple[str, str],
            values_key: str,
            values: Any) -> None:
        '''Adds data to the emoji_dict if not already there'''
        if not emoji_dict_key or not values_key or not values:
            return
        normalized_key = (
            self.variation_selector_normalize(
                emoji_dict_key[0], variation_selector=''),
            emoji_dict_key[1])
        # inner_dict = self._emoji_dict.setdefault(normalized_key, {})
        # is slower than the below try/except for mostly-existing keys
        # because the default argument {} is always evaluated before
        # checking the key. So it needlesssly creates empty
        # dictionaries. Also, Method calls like setdefault() in Python
        # are slower than direct try/except or in checks.
        #
        # Approach   When Key Exists (Hit)   When Key Missing (Miss)   Best For
        # try/except Fastest (direct access) Slow (exception handling) Hit rate >90%
        # in check   Slower (two lookups)    Fastest (no exception)    Hit rate <50%
        try:
            inner_dict = self._emoji_dict[normalized_key]
        except KeyError:
            inner_dict = {}
            self._emoji_dict[normalized_key] = inner_dict

        if isinstance(values, list):
            if values_key not in inner_dict:
                inner_dict[values_key] = []
            existing = inner_dict[values_key]
            for value in values:
                if value not in existing:
                    # append() is slightly slower than += for small lists
                    existing += [value]
        else:
            inner_dict[values_key] = values

    def _load_unicode_blocks(self) -> None:
        '''Loads the names of Unicode blocks'''
        dirnames = (USER_DATADIR, DATADIR,
                    # On Fedora, the “unicode-ucd” package has the
                    # Blocks.txt file here:
                    '/usr/share/unicode/ucd',
                    # On Ubuntu 20.04.3 it is here:
                    '/usr/share/unicode/',)
        basenames = ('Blocks.txt',)
        (path, open_function) = _find_path_and_open_function(
            dirnames, basenames)
        if not path:
            LOGGER.warning(
                'could not find "%s" in "%s"', basenames, dirnames)
            return
        if open_function is None:
            LOGGER.warning('could not find open function')
            return
        lines = []
        with open_function( # type: ignore
                path, mode='rt', encoding='utf-8') as blocks_file:
            lines = blocks_file.readlines()
        blocks_pattern = re.compile(r'([0-9A-F]+)\.\.([0-9A-F]+);\ (\S.*\S)')
        for line in lines:
            line = re.sub(r'#.*$', '', line).strip()
            if not line:
                continue
            match = blocks_pattern.match(line)
            if match:
                block_start, block_end, block_name = match.groups()
                self._unicode_blocks[
                    range(int(block_start, 16),
                          int(block_end, 16) + 1)] = block_name

    def _load_derived_age(self) -> None:
        '''Loads in which Unicode versions code points were added

        This updates 'uversion' for codepoints in `self._emoji_dict`, based on
        the DerivedAge.txt Unicode data file.

        This might overwrite uversion data already loaded from the
        emoji-data.txt file, for example:

        🧦 was added in Unicode 10.0 in and added to Emoji 5.0 in
        2017. So when by the emoji data files 5.0 was found,
        'uversion' will be overwritten with 10.0 here and 5.0 will
        still be available as 'eversion'.
        '''
        dirnames = (USER_DATADIR, DATADIR,
                    # On Fedora, the “unicode-ucd” package has the
                    # DerivedAge.txt file here:
                    '/usr/share/unicode/ucd',
                    # On Ubuntu 20.04.3 it is here:
                    '/usr/share/unicode/',)
        basenames = ('DerivedAge.txt',)
        (path, open_function) = _find_path_and_open_function(
            dirnames, basenames)
        if not path:
            LOGGER.warning(
                'could not find "%s" in "%s"', basenames, dirnames)
            return
        if open_function is None:
            LOGGER.warning('could not find open function')
            return
        try:
            with open_function( # type: ignore
                    path, mode='rt', encoding='utf-8') as derived_age_file:
                for line in derived_age_file:
                    line = line.partition('#')[0].strip()
                    if not line:
                        continue
                    try:
                        codepoint_string, unicode_version = (
                            part.strip() for part in line.split(';', 1))
                    except ValueError:
                        continue # Malformed line
                    if '..' in codepoint_string:
                        start_hex, end_hex = codepoint_string.split('..')
                        start, end = int(start_hex, 16), int(end_hex, 16)
                    else:
                        start = end = int(codepoint_string, 16)
                    for codepoint in range(start, end + 1):
                        emoji_string = chr(codepoint)
                        emoji_dict_key = (emoji_string, 'en')
                        if emoji_dict_key in self._emoji_dict:
                            self._add_to_emoji_dict(
                                emoji_dict_key, 'uversion', unicode_version)
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Error while loading DerivedAge: %s: %s',
                error.__class__.__name__, error)

    def _load_unicode_data(self) -> None:
        '''Loads emoji names from UnicodeData.txt'''
        dirnames = (USER_DATADIR, DATADIR,
                    # On Fedora, the “unicode-ucd” package has the
                    # UnicodeData.txt file here:
                    '/usr/share/unicode/ucd',
                    # On Ubuntu 20.04.3 it is here:
                    '/usr/share/unicode/',)
        basenames = ('UnicodeData.txt',)
        (path, open_function) = _find_path_and_open_function(
            dirnames, basenames)
        if not path:
            LOGGER.warning(
                'could not find "%s" in "%s"', basenames, dirnames)
            return
        if open_function is None:
            LOGGER.warning('could not find open function')
            return
        try:
            with open_function( # type: ignore
                    path, mode='rt', encoding='utf-8') as unicode_data_file:
                for line in itertools.chain(unicode_data_file,
                                            UNICODE_DATA_EXTRA_LINES):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        codepoint_string, name, category, _ = line.split(';', 3)
                    except ValueError:
                        continue  # Malformed line
                    emoji_string = chr(int(codepoint_string, 16))
                    if category in ('Cc', 'Co', 'Cs'):
                        # Never load control characters (“Cc”), they cause
                        # too much problems when trying to display
                        # them. Never load the “First” and “Last”
                        # characters of private use characters “Co” and
                        # surrogates (“Cs”) either as these are completely
                        # useless.
                        continue
                    if (not self._unicode_data_all
                            and not UNICODE_CATEGORIES[category]['valid']
                            and emoji_string not in VALID_CHARACTERS):
                        continue
                    self._add_to_emoji_dict(
                        (emoji_string, 'en'), 'names', [name.lower()])
                    self._add_to_emoji_dict(
                        (emoji_string, 'en'),
                        'ucategories', [
                            category,
                            UNICODE_CATEGORIES[category]['major'],
                            UNICODE_CATEGORIES[category]['minor']])
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Error while loading UnicodeData: %s: %s',
                error.__class__.__name__, error)

    def _load_unicode_emoji_data(self) -> None:
        '''
        Loads emoji property data from emoji-data.txt

        http://unicode.org/Public/emoji/5.0/emoji-data.txt
        '''
        dirnames = (USER_DATADIR, DATADIR)
        basenames = ('emoji-data.txt',)
        (path, open_function) = _find_path_and_open_function(
            dirnames, basenames)
        if not path:
            LOGGER.warning(
                'could not find "%s" in "%s"', basenames, dirnames)
            return
        if open_function is None:
            LOGGER.warning('could not find open function')
            return
        try:
            with open_function( # type: ignore
                    path, mode='rt', encoding='utf-8') as unicode_emoji_data_file:
                for line in unicode_emoji_data_file.readlines():
                    emoji_version = ''
                    pattern = re.compile(
                        r'[^;]*;[^;]*#\s*E(?P<eversion>[0-9]+\.[0-9]+)\s*'
                        + r'\[[0-9]+\]')
                    match = pattern.match(line)
                    if match and match.group('eversion'):
                        emoji_version = match.group('eversion')
                    line = line.partition('#')[0].strip()
                    if not line:
                        continue
                    try:
                        codepoint_string, property_string = (
                            x.strip() for x in line.split(';', 1))
                    except ValueError:
                        continue # Malformed line
                    if '..' in codepoint_string:
                        start_hex, end_hex = codepoint_string.split('..')
                        start, end = int(start_hex, 16), int(end_hex, 16)
                    else:
                        start = end = int(codepoint_string, 16)
                    for codepoint in range(start, end +1):
                        emoji_string = chr(codepoint)
                        emoji_dict_key = (emoji_string, 'en')
                        self._add_to_emoji_dict(
                            emoji_dict_key, 'properties', [property_string])
                        if emoji_version:
                            self._add_to_emoji_dict(
                                emoji_dict_key, 'eversion', emoji_version)
                            # Redundant, as these are single code points,
                            # the Unicode version will be overwritten by
                            # Data from DerivedAge.txt when calling
                            # _load_derived_age():
                            self._add_to_emoji_dict(
                                emoji_dict_key, 'uversion', emoji_version)
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Error while loading emoji-data.txt: %s: %s',
                error.__class__.__name__, error)

    def _load_unicode_emoji_sequences(self) -> None:
        '''
        Loads emoji property data from emoji-data.txt

        http://unicode.org/Public/emoji/5.0/emoji-sequences.txt
        '''
        dirnames = (USER_DATADIR, DATADIR)
        basenames = ('emoji-sequences.txt',)
        (path, open_function) = _find_path_and_open_function(
            dirnames, basenames)
        if not path:
            LOGGER.warning(
                'could not find "%s" in "%s"', basenames, dirnames)
            return
        if open_function is None:
            LOGGER.warning('could not find open function')
            return
        with open_function( # type: ignore
                path,
                mode='rt',
                encoding='utf-8') as unicode_emoji_sequences_file:
            for line in unicode_emoji_sequences_file.readlines():
                emoji_version = ''
                pattern = re.compile(
                    r'[^;]*;[^;]*;[^;]*#\s*E(?P<eversion>[0-9]+\.[0-9]+)\s*'
                    + r'\[[0-9]+\]')
                match = pattern.match(line)
                if match and match.group('eversion'):
                    emoji_version = match.group('eversion')
                line = re.sub(r'#.*$', '', line).strip()
                if not line:
                    continue
                codepoints, property_string, name = (
                    x.strip() for x in line.split(';')[:3])
                if property_string == 'Basic_Emoji':
                    continue
                if codepoints == '0023 FE0F 20E3' and name == 'keycap:':
                    name = 'keycap: #'
                emoji_string = ''
                for codepoint in codepoints.split(' '):
                    emoji_string += chr(int(codepoint, 16))
                if emoji_string:
                    self._add_to_emoji_dict(
                        (emoji_string, 'en'), 'properties', [property_string])
                    self._add_to_emoji_dict(
                        (emoji_string, 'en'), 'names', [name.lower()])
                    if emoji_version:
                        self._add_to_emoji_dict(
                            (emoji_string, 'en'), 'eversion', emoji_version)
                        # Sequences also need to have some Unicode version set
                        # otherwise the emoji-picker GUI will not display
                        # them:
                        unicode_version = emoji_version
                        if emoji_version in EMOJI_VERSION_TO_UNICODE_VERSIONS:
                            unicode_version = EMOJI_VERSION_TO_UNICODE_VERSIONS[
                                emoji_version][-1]
                        self._add_to_emoji_dict(
                            (emoji_string, 'en'), 'uversion', unicode_version)

    def _load_unicode_emoji_zwj_sequences(self) -> None:
        '''
        Loads emoji property data from emoji-zwj-sequences.txt

        http://unicode.org/Public/emoji/5.0/emoji-zwj-sequences.txt
        '''
        dirnames = (USER_DATADIR, DATADIR)
        basenames = ('emoji-zwj-sequences.txt',)
        (path, open_function) = _find_path_and_open_function(
            dirnames, basenames)
        if not path:
            LOGGER.warning(
                'could not find "%s" in "%s"', basenames, dirnames)
            return
        if open_function is None:
            LOGGER.warning('could not find open function')
            return
        with open_function( # type: ignore
                path,
                mode='rt',
                encoding='utf-8') as unicode_emoji_zwj_sequences_file:
            for line in unicode_emoji_zwj_sequences_file.readlines():
                emoji_version = ''
                pattern = re.compile(
                    r'[^;]*;[^;]*;[^;]*#\s*E(?P<eversion>[0-9]+\.[0-9]+)\s*'
                    + r'\[[0-9]+\]')
                match = pattern.match(line)
                if match and match.group('eversion'):
                    emoji_version = match.group('eversion')
                line = re.sub(r'#.*$', '', line).strip()
                if not line:
                    continue
                codepoints, property_string, name = (
                    x.strip() for x in line.split(';')[:3])
                emoji_string = ''
                for codepoint in codepoints.split(' '):
                    emoji_string += chr(int(codepoint, 16))
                if emoji_string:
                    self._add_to_emoji_dict(
                        (emoji_string, 'en'), 'properties', [property_string])
                    self._add_to_emoji_dict(
                        (emoji_string, 'en'), 'names', [name.lower()])
                    if emoji_version:
                        self._add_to_emoji_dict(
                            (emoji_string, 'en'), 'eversion', emoji_version)
                        # Sequences also need to have some Unicode version set
                        # otherwise the emoji-picker GUI will not display
                        # them:
                        unicode_version = emoji_version
                        if emoji_version in EMOJI_VERSION_TO_UNICODE_VERSIONS:
                            unicode_version = EMOJI_VERSION_TO_UNICODE_VERSIONS[
                                emoji_version][-1]
                        self._add_to_emoji_dict(
                            (emoji_string, 'en'), 'uversion', unicode_version)

    def _load_unicode_emoji_test(self) -> None:
        '''Loads emoji property data from emoji-test.txt

        http://unicode.org/Public/emoji/4.0/emoji-test.txt

        This is mostly for emoji sorting and for some categorization
        '''
        dirnames = (USER_DATADIR, DATADIR)
        basenames = ('emoji-test.txt',)
        (path, open_function) = _find_path_and_open_function(
            dirnames, basenames)
        if not path:
            LOGGER.warning(
                'could not find "%s" in "%s"', basenames, dirnames)
            return
        if open_function is None:
            LOGGER.warning('could not find open function')
            return
        with open_function( # type: ignore
                path, mode='rt', encoding='utf-8') as unicode_emoji_test_file:
            group = ''
            subgroup = ''
            cldr_order = 0
            cldr_group_to_emojione_category = {
                'Smileys & People': N_('people'),
                'Smileys & Emotion': N_('people'), # New in Unicode 12.0
                'People & Body': N_('people'), # New in Unicode 12.0
                'Animals & Nature': N_('nature'),
                'Food & Drink': N_('food'),
                'Travel & Places': N_('travel'),
                'Activities': N_('activity'),
                'Objects': N_('objects'),
                'Symbols': N_('symbols'),
                'Flags': N_('flags'),
                'Modifiers': N_('modifier'), # not in emoji-test.txt
                'Component': N_('modifier'), # New in Unicode 12.0
                'Regional': N_('regional'), # not in emoji-test.txt
            }
            cldr_subgroup_to_emojione_category = {
                'person-sport':  N_('activity'),
            }
            for line in unicode_emoji_test_file.readlines():
                pattern = re.compile(r'# group:(?P<group>.+)$')
                match = pattern.match(line)
                if match and match.group('group'):
                    group = match.group('group').strip()
                    continue
                pattern = re.compile(r'# subgroup:(?P<subgroup>.+)$')
                match = pattern.match(line)
                if match and match.group('subgroup'):
                    subgroup = match.group('subgroup').strip()
                    continue
                name = ''
                pattern = re.compile(
                    r'[^#]+#\s+\S+\s+E(?P<eversion>[0-9]+\.[0-9]+)'
                    + r'\s+(?P<name>.+)$')
                match = pattern.match(line)
                if match and match.group('name'):
                    name = match.group('name').strip()
                line = re.sub(r'#.*$', '', line).strip()
                if not line:
                    continue
                codepoints, property_string = (
                    x.strip() for x in line.split(';')[:2])
                if property_string != 'fully-qualified':
                    # The non-fully-qualified sequences are
                    # all duplicates of the fully-qualified
                    # sequences.
                    continue
                cldr_order += 1
                emoji_string = ''
                for codepoint in codepoints.split(' '):
                    emoji_string += chr(int(codepoint, 16))
                if emoji_string:
                    categories = [cldr_group_to_emojione_category[group]]
                    if subgroup in cldr_subgroup_to_emojione_category:
                        categories.append(
                            cldr_subgroup_to_emojione_category[subgroup])
                    self._add_to_emoji_dict(
                        (emoji_string, 'en'), 'cldr_order', str(cldr_order))
                    self._add_to_emoji_dict(
                        (emoji_string, 'en'), 'categories', categories)
                    self._add_translated_categories_to_emoji_dict(
                        emoji_string, categories)
                    if name:
                        self._add_to_emoji_dict(
                            (emoji_string, 'en'), 'names', [name.lower()])
                    if self.emoji_version(emoji_string) == '':
                        LOGGER.warning('Emoji “%s” lacks emoji version, '
                                       'this should not happen!',
                                       emoji_string)
                    if self.unicode_version(emoji_string) == '':
                        LOGGER.warning('Emoji “%s” lacks Unicode version, '
                                       'this should not happen!',
                                       emoji_string)

    def _load_emojione_data(self) -> None:
        '''
        Loads emoji names, aliases, keywords, and categories from
        the emojione.json file.
        '''
        dirnames = (USER_DATADIR, DATADIR)
                    # The current version of the file
                    # has the name “emoji.json”, an old
                    # version was named “emojione.json”
        basenames = ('emoji.json', 'emojione.json')
        (path, open_function) = _find_path_and_open_function(
            dirnames, basenames)
        if not path:
            LOGGER.warning(
                'could not find "%s" in "%s"', basenames, dirnames)
            return
        if open_function is None:
            LOGGER.warning('could not find open function')
            return
        with open_function( # type: ignore
                path, mode='rt', encoding='utf-8') as emoji_one_file:
            emojione = json.load(emoji_one_file)
        for dummy_emojione_key, emojione_value in emojione.items():
            codepoints = emojione_value['code_points']['fully_qualified']

            emoji_string = ''.join([
                chr(int(codepoint, 16)) for codepoint in codepoints.split('-')
            ])

            # emojione has names like “kiss (woman,woman)”, “couple
            # (man,man)” “family (man,man,girl,boy)”, “cocos (keeling)
            # islands”, “ceuta, melilla” …. The parentheses and commas
            # disturb the matching because my matching assumes that
            # words are seperated only by spaces. And they also match
            # too much for ASCII-smiley query strings like “:-)”. But
            # they are nicer for display. Therefore, if a name
            # contains such characters keep both the original name
            # (for display) and the name with these characters removed
            display_name = emojione_value['name'].lower()
            match_name = re.sub(r' ?[(,)] ?', r' ', display_name).strip(' ')
            names = [display_name]
            shortname = emojione_value[
                'shortname'].replace('_', ' ').strip(':')
            aliases = [x.replace('_', ' ').strip(':')
                       for x in emojione_value['shortname_alternates']]
            ascii_aliases = emojione_value['ascii']
            if match_name not in names:
                names += [match_name]
            if shortname not in names:
                names += [shortname]
            for alias in aliases + ascii_aliases:
                if alias not in names:
                    names += [alias]

            categories = [emojione_value['category']]
            # EmojiOne has duplicate entries in the keywords.  The
            # keywords also have random order (maybe because of the
            # way json.load(file) works?), sort them to get
            # reproducible output in the test cases (if the order
            # changes, which keyword matches last may change, that
            # does not change the score but it may have an effect on
            # the additional information added to the display string
            # added because of a keyword match).
            keywords = sorted(list(set(emojione_value['keywords'])))
            if '' in keywords:
                # EmojiOne 3 has some empty strings in the keyword lists
                # remove them:
                keywords.remove('')

            emoji_order = emojione_value['order']

            if emoji_string == '🏳🌈':
                # The rainbow flag should be a zwj sequence.
                # This is a bug in emojione version 2:
                # https://github.com/Ranks/emojione/issues/455
                # Fix it here:
                emoji_string = '🏳\u200d🌈'

            if (len(emoji_string) == 1
                    and emoji_string in '🇦🇧🇨🇩🇪🇫🇬🇭🇮🇯🇰🇱🇲🇳🇴🇵🇶🇷🇸🇹🇺🇻🇼🇽🇾🇿'):
                # Work around bug in emojione version 3.0
                # https://github.com/Ranks/emojione/issues/476
                # The category should *not* be 'people':
                categories = ['regional']

            if emoji_string in SKIN_TONE_MODIFIERS:
                # Work around bug in emojione version 3.0
                # https://github.com/Ranks/emojione/issues/476
                # The category should *not* be 'people':
                categories = ['modifier']

            if (len(emoji_string) == 2 and emoji_string[1] == '\ufe0f'
                    and emoji_string[0] in '#*0123456789'):
                # Work around bug in emojione version 3.0
                # https://github.com/Ranks/emojione/issues/476
                # The category should *not* be 'people':
                categories = []

            self._add_to_emoji_dict(
                (emoji_string, 'en'), 'names', names)
            self._add_to_emoji_dict(
                (emoji_string, 'en'), 'categories', categories)
            self._add_to_emoji_dict(
                (emoji_string, 'en'), 'keywords', keywords)
            self._add_to_emoji_dict(
                (emoji_string, 'en'), 'emoji_order', emoji_order)

            self._add_translated_categories_to_emoji_dict(
                emoji_string, categories)

    def _add_translated_categories_to_emoji_dict(
            self, emoji_string: str, categories: List[str]) -> None:
        '''
        Add translated versions of categories for an emoji
        to self._emoji_dict

        :param emoji_string: An emoji
        :param categories: The categories of the emoji
        '''
        dummy_categories_to_translate = [
            # Translators: This is a name for a category of emoji
            N_('activity'),
            # Translators: This is a name for a category of emoji
            N_('flags'),
            # Translators: This is a name for a category of emoji
            N_('food'),
            # Translators: This is a name for a category of emoji
            N_('modifier'),
            # Translators: This is a name for a category of emoji
            N_('nature'),
            # Translators: This is a name for a category of emoji
            N_('objects'),
            # Translators: This is a name for a category of emoji
            N_('people'),
            # Translators: This is a name for a category of emoji
            N_('regional'),
            # Translators: This is a name for a category of emoji
            N_('symbols'),
            # Translators: This is a name for a category of emoji
            N_('travel'),
        ]

        for language in itb_util.expand_languages(self._languages):
            if self._gettext_translations[language]:
                translated_categories = []
                for category in categories:
                    translated_category = self._gettext_translations[
                        language].gettext(category)
                    translated_categories.append(
                        translated_category)
                    if language == 'ja' and IMPORT_PYKAKASI_SUCCESSFUL:
                        translated_category_hiragana = (
                            kakasi_convert(
                                translated_category, target='hira'))
                        if (translated_category_hiragana
                                != translated_category):
                            translated_categories.append(
                                translated_category_hiragana)
                        if self._romaji:
                            translated_category_romaji = (
                                kakasi_convert(
                                    translated_category,
                                    target='hepburn')).lower()
                            if (translated_category_romaji
                                    != translated_category):
                                translated_categories.append(
                                    translated_category_romaji)
                self._add_to_emoji_dict(
                    (emoji_string, language),
                    'categories', translated_categories)

    def _load_cldr_annotation_data(self, language: str, subdir: str) -> None:
        '''
        Loads translations of emoji names and keywords.

        Translations are loaded from the annotation data from CLDR.
        '''
        dirnames = CLDR_ANNOTATION_DIRNAMES
        basenames = (language + '.xml',)
        (path, open_function) = _find_path_and_open_function(
            dirnames, basenames, subdir=subdir)
        if not path:
            return
        if open_function is None:
            LOGGER.warning('could not find open function')
            return
        # change language to the language of the file which was really
        # found (For example, it could be that 'es_ES' was requested,
        # but only the fallback 'es' was really found):
        language = os.path.basename(
            path).replace('.gz', '').replace('.xml', '')
        with open_function( # type: ignore
                path, mode='rt', encoding='utf-8') as cldr_annotation_file:
            pattern = re.compile(
                r'.*<annotation cp="(?P<emojistring>[^"]+)"'
                +r'\s*(?P<tts>type="tts"){0,1}'
                +r'[^>]*>'
                +r'(?P<content>.+)'
                +r'</annotation>.*'
            )
            for line in cldr_annotation_file.readlines():
                match = pattern.match(line)
                if match:
                    emoji_string = match.group('emojistring')
                    content = html.unescape(match.group('content'))
                    if content == '↑↑↑':
                        continue
                    if language.startswith('en'):
                        content = content.lower()
                    if match.group('tts'):
                        if (language in ('zh', 'zh_Hant')
                                and IMPORT_PINYIN_SUCCESSFUL):
                            self._add_to_emoji_dict(
                                (emoji_string, language),
                                'names',
                                [content,
                                 pinyin.get(content)]
                            )
                        elif language == 'ja' and IMPORT_PYKAKASI_SUCCESSFUL:
                            self._add_to_emoji_dict(
                                (emoji_string, language),
                                'names',
                                [content,
                                 kakasi_convert(content, target='hira')]
                            )
                            if self._romaji:
                                self._add_to_emoji_dict(
                                    (emoji_string, language),
                                    'names',
                                    [content,
                                     kakasi_convert(content,
                                                    target='hepburn').lower()]
                                )
                        else:
                            self._add_to_emoji_dict(
                                (emoji_string, language),
                                'names',
                                [content]
                            )
                    else:
                        if (language in ('zh', 'zh_Hant')
                                and IMPORT_PINYIN_SUCCESSFUL):
                            for content_part in content.split('|'):
                                keyword = content_part.strip()
                                keyword_pinyin = pinyin.get(keyword)
                                self._add_to_emoji_dict(
                                    (emoji_string, language),
                                    'keywords',
                                    [keyword, keyword_pinyin]
                                )
                        elif language == 'ja' and IMPORT_PYKAKASI_SUCCESSFUL:
                            for content_part in content.split('|'):
                                keyword = content_part.strip()
                                keyword_hiragana = kakasi_convert(
                                    keyword, target='hira')
                                self._add_to_emoji_dict(
                                    (emoji_string, language),
                                    'keywords',
                                    [keyword, keyword_hiragana]
                                )
                            if self._romaji:
                                for content_part in content.split('|'):
                                    keyword = content_part.strip()
                                    keyword_romaji = kakasi_convert(
                                        keyword, target='hepburn').lower()
                                    self._add_to_emoji_dict(
                                        (emoji_string, language),
                                        'keywords',
                                        [keyword, keyword_romaji]
                                    )
                        else:
                            self._add_to_emoji_dict(
                                (emoji_string, language),
                                'keywords',
                                [x.strip()
                                 for x in content.split('|')]
                            )

    def candidates(
            self,
            query_string: str,
            match_limit: int = 20,
            trigger_characters: str  = '') -> List[itb_util.PredictionCandidate]:
        # pylint: disable=line-too-long
        '''
        Find a list of emoji which best match a query string.

        :param query_string: A search string
        :param match_limit: Limit the number of matches to this amount
        :return: List of emoji which best match the query string

        Returns a list of tuples of the form (<emoji>, <name>, <score),
                i.e. a list like this:
                [('🎂', 'birthday cake', 3106), ...]

        Examples:

        >>> mq = EmojiMatcher(languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])

        If the query string is an emoji itself, similar emoji are returned:

        >>> matches = mq.candidates('😺', match_limit=3)
        >>> matches[0].phrase
        '😺'
        >>> matches[0].comment
        'smiling cat face with open mouth [😺, So, people, cat, face, mouth, open, smile, uc6, animal, grinning, smiling]'
        >>> matches[0].user_freq
        12.0
        >>> matches[1].phrase
        '😸'
        >>> matches[1].comment
        'grinning cat face with smiling eyes [So, people, cat, face, smile, uc6, animal, grinning, smiling]'
        >>> matches[1].user_freq
        9.0
        >>> matches[2].phrase
        '😅'
        >>> matches[2].comment
        'smiling face with open mouth and cold sweat [So, people, face, open, smile, uc6, grinning, mouth, smiling]'
        >>> matches[2].user_freq
        9.0

        It works in different languages:

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('ネコ＿')[0]
        >>> first_match.phrase
        '🐈'
        >>> first_match.comment
        'ネコ'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('ネコ＿')[0]
        >>> first_match.phrase
        '🐈'
        >>> first_match.comment
        'ネコ'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('ant')[0]
        >>> first_match.phrase
        '🐜'
        >>> first_match.comment
        'ant'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('ant')[0]
        >>> first_match.phrase
        '🐜'
        >>> first_match.comment
        'ant'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('ameise')[0]
        >>> first_match.phrase
        '🐜'
        >>> first_match.comment
        'Ameise'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('ameise')[0]
        >>> first_match.phrase
        '🐜'
        >>> first_match.comment
        'Ameise'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('formica')[0]
        >>> first_match.phrase
        '🐜'
        >>> first_match.comment
        'formica'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('formica')[0]
        >>> first_match.phrase
        '🐜'
        >>> first_match.comment
        'formica'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('hormiga')[0]
        >>> first_match.phrase
        '🐜'
        >>> first_match.comment
        'hormiga'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('hormiga')[0]
        >>> first_match.phrase
        '🐜'
        >>> first_match.comment
        'hormiga'

        Any white space and '_' can be used to separate keywords in the
        query string:

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('gatto sorride')[0]
        >>> first_match.phrase
        '😺'
        >>> first_match.comment
        'gatto che sorride'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('gatto sorride')[0]
        >>> first_match.phrase
        '😺'
        >>> first_match.comment
        'gatto che sorride'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('gatto_	 sorride')[0]
        >>> first_match.phrase
        '😺'
        >>> first_match.comment
        'gatto che sorride'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('gatto_	 sorride')[0]
        >>> first_match.phrase
        '😺'
        >>> first_match.comment
        'gatto che sorride'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('nerd glasses')[0]
        >>> first_match.phrase
        '🤓'
        >>> first_match.comment
        'nerd face [glasses]'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('nerd glasses')[0]
        >>> first_match.phrase
        '🤓'
        >>> first_match.comment
        'nerd face [glasses]'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('smiling face with sunglasses')[0]
        >>> first_match.phrase
        '😎'
        >>> first_match.comment
        'smiling face with sunglasses'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('smiling face with sunglasses')[0]
        >>> first_match.phrase
        '😎'
        >>> first_match.comment
        'smiling face with sunglasses'

        ASCII emoji match as well:

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates(':-)')[0]
        >>> first_match.phrase
        '🙂'
        >>> first_match.comment
        'slightly smiling face “:-)”'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates(':-)')[0]
        >>> first_match.phrase
        '🙂'
        >>> first_match.comment
        'slightly smiling face “:-)”'

        The query string can contain typos:

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('buterfly')[0]
        >>> first_match.phrase
        '🦋'
        >>> first_match.comment
        'butterfly'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('buterfly')[0]
        >>> first_match.phrase
        '🦋'
        >>> first_match.comment
        'butterfly'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('badminton')[0]
        >>> first_match.phrase
        '🏸'
        >>> first_match.comment
        'badminton racquet and shuttlecock'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('badminton')[0]
        >>> first_match.phrase
        '🏸'
        >>> first_match.comment
        'badminton racquet and shuttlecock'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('badminton')[0]
        >>> first_match.phrase
        '🏸'
        >>> first_match.comment
        'badminton racquet and shuttlecock'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('badminton')[0]
        >>> first_match.phrase
        '🏸'
        >>> first_match.comment
        'badminton racquet and shuttlecock'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('badmynton')[0]
        >>> first_match.phrase
        '🏸'
        >>> first_match.comment
        'Badminton'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('badmynton')[0]
        >>> first_match.phrase
        '🏸'
        >>> first_match.comment
        'badminton racquet and shuttlecock'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('padminton')[0]
        >>> first_match.phrase
        '🏸'
        >>> first_match.comment
        'Badminton'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('padminton')[0]
        >>> first_match.phrase
        '🏸'
        >>> first_match.comment
        'badminton racquet and shuttlecock'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('hedgehgo')[0]
        >>> first_match.phrase
        '🦔'
        >>> first_match.comment
        'hedgehog'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('hedgehgo')[0]
        >>> first_match.phrase
        '🦔'
        >>> first_match.comment
        'hedgehog'

        Non-emoji Unicode characters can be matched as well:

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('euro sign c')[0]
        >>> first_match.phrase
        '€'
        >>> first_match.comment
        'euro sign'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('euro sign')[0]
        >>> first_match.phrase
        '€'
        >>> first_match.comment
        'euro sign'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('superscript one')[0]
        >>> first_match.phrase
        '¹'
        >>> first_match.comment
        'superscript one'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('superscript one')[0]
        >>> first_match.phrase
        '¹'
        >>> first_match.comment
        'superscript one'

        Unicode code points can be used in the query:

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('2019')[0]
        >>> first_match.phrase
        '’'
        >>> first_match.comment
        'U+2019 right single quotation mark'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('2019')[0]
        >>> first_match.phrase
        '’'
        >>> first_match.comment
        'U+2019 right single quotation mark'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('41')[0]
        >>> first_match.phrase
        'A'
        >>> first_match.comment
        'U+41 latin capital letter a'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('41')[0]
        >>> first_match.phrase
        'A'
        >>> first_match.comment
        'U+41 latin capital letter a'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('2a')[0]
        >>> first_match.phrase
        '*'
        >>> first_match.comment
        'U+2A asterisk'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('2a')[0]
        >>> first_match.phrase
        '*'
        >>> first_match.comment
        'U+2A asterisk'

        >>> mq.set_match_algorithm('rapidfuzz')
        >>> first_match = mq.candidates('1b')[0]
        >>> first_match.phrase
        '\\x1b'
        >>> first_match.comment
        'U+1B'
        >>> mq.set_match_algorithm('classic')
        >>> first_match = mq.candidates('1b')[0]
        >>> first_match.phrase
        '\\x1b'
        >>> first_match.comment
        'U+1B'
        '''
        # pylint: enable=line-too-long
        if ((query_string, match_limit, trigger_characters)
            in self._candidate_cache):
            return self._candidate_cache[(
                query_string, match_limit, trigger_characters)]
        # David Mandelberg’s idea to do the emoji search first without
        # spellchecking and only if nothing matches do it again with
        # spellchecking doesn’t make it faster as we hoped, it makes
        # it slower.
        #
        #candidates = self._candidates(
        #    query_string=query_string,
        #    match_limit=match_limit,
        #    trigger_characters=trigger_characters,
        #    spellcheck=False)
        #if candidates:
        #    self._candidate_cache[(
        #        query_string, match_limit, trigger_characters)] = candidates
        #    return candidates
        candidates = self._candidates(
            query_string=query_string,
            match_limit=match_limit,
            trigger_characters=trigger_characters,
            spellcheck=True)
        self._candidate_cache[(
            query_string, match_limit, trigger_characters)] = candidates
        return candidates

    def _candidates(
            self,
            query_string: str,
            match_limit: int = 20,
            trigger_characters: str  = '',
            spellcheck: bool = False) -> List[itb_util.PredictionCandidate]:
        # Remove the trigger characters from the beginning and end of
        # the query string:
        if query_string[:1] and query_string[:1] in trigger_characters:
            query_string = query_string[1:]
        if query_string[-1:] and query_string[-1:] in trigger_characters:
            query_string = query_string[:-1]
        if not query_string:
            return []
        # self._emoji_dict contains only emoji or sequences without
        # variation selectors:
        query_string = self.variation_selector_normalize(
            query_string, variation_selector='')
        # Replace any sequence of white space characters and '_'
        # and '＿' in the query string with a single ' '.  '＿'
        # (U+FF3F FULLWIDTH LOW LINE) is included here because when
        # Japanese transliteration is used, something like “neko_”
        # transliterates to “ねこ＿” and that should of course match
        # the emoji for “ねこ”　(= “cat”):
        query_string = re.sub(r'[＿_\s]+', ' ', query_string)
        if (query_string, 'en') in self._emoji_dict:
            # the query_string is itself an emoji, match similar ones:
            candidates = self.similar(query_string, match_limit=match_limit)
            return candidates
        match_string = query_string
        if spellcheck:
            for word in match_string.split(sep=None):
                # Keep duplicates from the original query string.
                # If a word in the input string is not correctly spelled
                # in any of the enabled dictionaries, add spell checking
                # suggestions to the list (don’t do that if it is spelled
                # correctly in at least one dictionary):
                if len(word) > 5 and IMPORT_ENCHANT_SUCCESSFUL:
                    word_title = word.title()
                    if not any(dic.check(word) or dic.check(word_title)
                               for dic in self._enchant_dicts):
                        # incorrect in *all* dictionaries, add suggestions
                        suggestions = {
                            x.lower()
                            for dic in self._enchant_dicts
                            for x in dic.suggest(word)
                            if len(x) > 2
                        }
                        match_string += f' {" ".join(suggestions)}'
        match_string = itb_util.remove_accents(match_string.lower())
        candidates = []
        for emoji_key, emoji_value in self._emoji_dict.items():
            total_score = 0.0
            name_good_match = ''
            ucategory_good_match = ''
            category_good_match = ''
            keyword_good_match = ''
            if 'names' in emoji_value:
                for name in emoji_value['names']:
                    score = self._match_function(name, match_string)
                    if not name_good_match and score >= self._good_match_score:
                        name_good_match = name
                    total_score += 2 * score
            if 'ucategories' in emoji_value:
                for ucategory in emoji_value['ucategories']:
                    score = self._match_function(ucategory, match_string)
                    if score >= self._good_match_score:
                        ucategory_good_match = ucategory
                    total_score += score
            if 'categories' in emoji_value:
                for category in emoji_value['categories']:
                    score = self._match_function(category, match_string)
                    if score >= self._good_match_score:
                        category_good_match = category
                    total_score += score
            if 'keywords' in emoji_value:
                for keyword in emoji_value['keywords']:
                    score = self._match_function(keyword, match_string)
                    if score >= self._good_match_score:
                        keyword_good_match = keyword
                    total_score += score

            if total_score > 0:
                if 'names' in emoji_value:
                    display_name = emoji_value['names'][0]
                else:
                    display_name = self.name(emoji_key[0])
                if (len(emoji_key[0]) == 1
                        and is_invisible(emoji_key[0])):
                    # Add the code point to the display name of
                    # “invisible” characters:
                    display_name = (f'U+{ord(emoji_key[0]):04X} '
                                    + display_name)
                # If the match was good because something else
                # but the main name had a good match, show it in
                # the display name to make the user understand why
                # this emoji matched:
                if name_good_match not in display_name:
                    display_name += ' “' + name_good_match + '”'
                if ucategory_good_match not in display_name:
                    display_name += ' {' + ucategory_good_match + '}'
                if category_good_match not in display_name:
                    display_name += ' {' + category_good_match + '}'
                if keyword_good_match not in display_name:
                    display_name += ' [' + keyword_good_match + ']'
                candidates.append(itb_util.PredictionCandidate(
                    phrase=self.variation_selector_normalize(
                        emoji_key[0],
                        self._variation_selector),
                    user_freq=total_score,
                    comment=display_name))

        try:
            codepoint = int(query_string, 16)
            if (0x0 <= codepoint <= 0x1FFFFF
                    # exclude surrogates and private use characters:
                    and not 0xd800 <= codepoint <= 0xf8ff
                    and not 0xf0000 <= codepoint <= 0xffffd
                    and not 0x100000 <= codepoint <= 0x10fffd):
                char = chr(codepoint)
                name = self.name(char)
                if not name:
                    try:
                        name = unicodedata.name(char).lower()
                    except (ValueError,):
                        pass
                if name:
                    name = ' ' + name
                candidates.append(itb_util.PredictionCandidate(
                    phrase=char,
                    user_freq=self._good_match_score * 10.0,
                    comment=f'U+{query_string.upper()}{name}'))
        except (ValueError,):
            pass

        sorted_candidates = sorted(
            candidates,
            key=lambda x: (
                - x.user_freq,             # score
                self.cldr_order(x.phrase), # CLDR order
                - len(x.phrase),           # length of the emoji sequence
                x.comment                  # name of the emoji
            ))[:match_limit]

        return sorted_candidates

    def names(self, emoji_string: str, language: str = '') -> List[str]:
        # pylint: disable=line-too-long
        '''Find the names of an emoji

        Returns a list of names of the emoji in the language requested
        or and empty list if no name can be found in that language.

        If no language is requested, the list of names is returned in
        the first language of this EmojiMatcher for which a list of
        names can be found.

        :param emoji_string: The string of Unicode characters which are
                             used to encode the emoji
        :param language: The language requested for the name

        Examples:

        >>> matcher = EmojiMatcher(languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        >>> matcher.names('🙂')
        ['slightly smiling face', 'slight smile', ':)', ':-)', '=]', '=)', ':]']

        >>> matcher.names('🙂', language='it')
        ['faccina con sorriso accennato']
        '''
        # pylint: enable=line-too-long
        #
        # self._emoji_dict contains only emoji or sequences without
        # variation selectors:
        emoji_string = self.variation_selector_normalize(
            emoji_string, variation_selector='')
        if language:
            if ((emoji_string, language) in self._emoji_dict
                    and
                    'names' in self._emoji_dict[(emoji_string, language)]):
                return list(
                    self._emoji_dict[(emoji_string, language)]['names'])
            return []
        for _language in itb_util.expand_languages(self._languages):
            if ((emoji_string, _language) in self._emoji_dict
                    and
                    'names' in self._emoji_dict[(emoji_string, _language)]):
                return list(
                    self._emoji_dict[(emoji_string, _language)]['names'])
        return []

    def name(self, emoji_string: str, language: str = '') -> str:
        # pylint: disable=line-too-long
        '''Find the main name of an emoji.

        Returns a name of the emoji in the language requested
        or and empty string if no name can be found in that language.

        If no language is requested, the name is returned in the first
        language of this EmojiMatcher for which a name can be
        found.

        :param emoji_string: The string of Unicode characters which are
                             used to encode the emoji
        :param language: The language requested for the name

        Examples:

        >>> matcher = EmojiMatcher(languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])

        >>> matcher.name('🏸')
        'badminton racquet and shuttlecock'

        >>> matcher.name('🖥')
        'desktop computer'

        >>> matcher = EmojiMatcher(languages=['es_MX', 'es_ES', 'it_IT', 'ja_JP'])
        >>> matcher.name('🖥')
        'computadora de escritorio'

        >>> matcher = EmojiMatcher(languages=['es_ES', 'es_MX', 'it_IT', 'ja_JP'])
        >>> matcher.name('🖥')
        'ordenador de sobremesa'

        >>> matcher = EmojiMatcher(languages=['de_DE', 'es_ES', 'es_MX', 'it_IT', 'ja_JP'])
        >>> matcher.name('🖥')
        'Desktopcomputer'

        >>> matcher = EmojiMatcher(languages=['it_IT', 'es_ES', 'es_MX', 'ja_JP'])
        >>> matcher.name('🖥')
        'computer fisso'

        >>> matcher = EmojiMatcher(languages=['fr_FR'])
        >>> matcher.name('🖥')
        'ordinateur de bureau'

        >>> matcher.name('🤔')
        'visage en pleine réflexion'

        >>> matcher = EmojiMatcher(languages=['de_DE'])
        >>> matcher.name('🤔')
        'nachdenkendes Gesicht'

        >>> matcher.name('⚽')
        'Fußball'

        >>> matcher = EmojiMatcher(languages=['de_CH'])
        >>> matcher.name('🤔')
        'nachdenkendes Gesicht'

        >>> matcher.name('⚽')
        'Fussball'

        >>> matcher.name('a')
        ''

        >>> matcher.name(' ')
        'space'
        '''
        # pylint: enable=line-too-long
        names = self.names(emoji_string, language=language)
        if names:
            return names[0]
        return ''

    def keywords(self, emoji_string: str, language: str = '') -> List[str]:
        # pylint: disable=line-too-long
        '''Return the keywords of an emoji

        Returns a list of keywords of the emoji in the language requested
        or an empty list if no keywords can be found in that language.

        If no language is requested, the list of keywords is returned in
        the first language of this EmojiMatcher for which a list of
        keywords can be found.

        :param emoji_string: The string of Unicode characters which are
                             used to encode the emoji
        :param language: The language requested for the name

        Examples:

        >>> matcher = EmojiMatcher(languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        >>> matcher.keywords('🙂')
        ['face', 'smile', 'uc7', 'happy', 'slightly', 'smiling']

        >>> matcher.keywords('🙂', language='it')
        ['contento', 'faccina', 'faccina che sorride', 'faccina con sorriso accennato', 'felice', 'mezzo sorriso', 'ok', 'sorrisetto', 'sorriso', 'sorriso a bocca chiusa', 'sorriso accennato', 'va bene']
        '''
        # pylint: enable=line-too-long
        #
        # self._emoji_dict contains only emoji or sequences without
        # variation selectors:
        emoji_string = self.variation_selector_normalize(
            emoji_string, variation_selector='')
        if language:
            if ((emoji_string, language) in self._emoji_dict
                    and
                    'keywords' in self._emoji_dict[(emoji_string, language)]):
                return list(
                    self._emoji_dict[(emoji_string, language)]['keywords'])
            return []
        for _language in itb_util.expand_languages(self._languages):
            if ((emoji_string, _language) in self._emoji_dict
                    and
                    'keywords' in self._emoji_dict[(emoji_string, _language)]):
                return list(
                    self._emoji_dict[(emoji_string, _language)]['keywords'])
        return []

    def categories(self, emoji_string: str, language: str = '') -> List[str]:
        # pylint: disable=line-too-long
        '''Return the categories of an emoji

        Returns a list of categories of the emoji in the language requested
        or and empty list if no categories can be found in that language.

        If no language is requested, the list of categories is returned in
        the first language of this EmojiMatcher for which a list of
        categories can be found.

        :param emoji_string: The string of Unicode characters which are
                             used to encode the emoji
        :param language: The language requested for the name

        Examples:

        >>> matcher = EmojiMatcher(languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        >>> matcher.categories('🙂')
        ['people']
        '''
        # pylint: enable=line-too-long
        #
        # self._emoji_dict contains only emoji or sequences without
        # variation selectors:
        emoji_string = self.variation_selector_normalize(
            emoji_string, variation_selector='')
        if language:
            if ((emoji_string, language) in self._emoji_dict
                    and 'categories' in
                    self._emoji_dict[(emoji_string, language)]):
                return list(
                    self._emoji_dict[(emoji_string, language)]['categories'])
            return []
        for _language in itb_util.expand_languages(self._languages):
            if ((emoji_string, _language) in self._emoji_dict
                    and 'categories' in
                    self._emoji_dict[(emoji_string, _language)]):
                return list(
                    self._emoji_dict[(emoji_string, _language)]['categories'])
        return []

    def similar(
            self,
            emoji_string: str,
            match_limit: int = 1000,
            show_keywords: bool = True) -> List[itb_util.PredictionCandidate]:
        # pylint: disable=line-too-long
        '''Find similar emojis

        “Similar” means they share categories or keywords.

        :param emoji_string: The string of Unicode  characters which are
                             used to encode the emoji
        :param match_limit: Limit the number of matches to this amount
        :param show_keywords: Whether the list of keywords and categories which
                              matched should be included in the names of the
                              ressults.
        :return: List of similar emoji
                A list of tuples of the form (<emoji>, <name>, <score>),
                i.e. a list like this:

                [('🐫', "cammello ['🐫', 'gobba', 'animale']", 3), ...]

                The name includes the list of categories or keywords
                which matched, the score is the number of categories
                or keywords matched.

                The list is sorted by preferred language, then score,
                then name.

        Examples:

        >>> matcher = EmojiMatcher(languages = ['en_US'])

        >>> matcher.similar('this is not an emoji', match_limit = 5)
        []

        >>> matches = matcher.similar('☺', match_limit = 5)
        >>> matches[0].phrase
        '☺️'
        >>> matches[0].comment
        'white smiling face [☺️, So, people, face, outlined, relaxed, smile, uc1, happy, smiling]'
        >>> matches[0].user_freq
        10.0
        >>> matches[1].phrase
        '🥲'
        >>> matches[1].comment
        'smiling face with tear [So, people, face, happy, smile, smiling]'
        >>> matches[1].user_freq
        6.0
        >>> matches[2].phrase
        '😇'
        >>> matches[2].comment
        'smiling face with halo [So, people, face, smile, happy, smiling]'
        >>> matches[2].user_freq
        6.0
        >>> matches[3].phrase
        '🙂'
        >>> matches[3].comment
        'slightly smiling face [So, people, face, smile, happy, smiling]'
        >>> matches[3].user_freq
        6.0
        >>> matches[4].phrase
        '😆'
        >>> matches[4].comment
        'smiling face with open mouth and tightly-closed eyes [So, people, face, smile, happy, smiling]'
        >>> matches[4].user_freq
        6.0

        >>> matcher = EmojiMatcher(languages = ['it_IT'])
        >>> matches = matcher.similar('☺', match_limit = 5)
        >>> matches[0].phrase
        '☺️'
        >>> matches[0].comment
        'faccina sorridente [☺️, contorno faccina sorridente, delineata, emozionarsi, faccina, felice, rilassata, sorridente]'
        >>> matches[0].user_freq
        8.0
        >>> matches[1].phrase
        '🤩'
        >>> matches[1].comment
        'colpo di fulmine [faccina, felice]'
        >>> matches[1].user_freq
        2.0
        >>> matches[2].phrase
        '😊'
        >>> matches[2].comment
        'faccina con occhi sorridenti [faccina, felice]'
        >>> matches[2].user_freq
        2.0
        >>> matches[3].phrase
        '🙂'
        >>> matches[3].comment
        'faccina con sorriso accennato [faccina, felice]'
        >>> matches[3].user_freq
        2.0
        >>> matches[4].phrase
        '😂'
        >>> matches[4].comment
        'faccina con lacrime di gioia [faccina, felice]'
        >>> matches[4].user_freq
        2.0

        Some symbols which are not emoji work as well:

        >>> matcher = EmojiMatcher(languages = ['es_ES',  'it_IT', 'es_MX', 'de_DE', 'en_US', 'ja_JP'])
        >>> matches = matcher.similar('€', match_limit = 5)
        >>> matches[0].phrase
        '€'
        >>> matches[0].comment
        'euro [€, divisa, EUR, euro, moneda]'
        >>> matches[0].user_freq
        5.0
        >>> matches[1].phrase
        '£'
        >>> matches[1].comment
        'libra esterlina [divisa, moneda]'
        >>> matches[1].user_freq
        2.0
        >>> matches[2].phrase
        '₽'
        >>> matches[2].comment
        'rublo [divisa, moneda]'
        >>> matches[2].user_freq
        2.0
        >>> matches[3].phrase
        '₹'
        >>> matches[3].comment
        'rupia india [divisa, moneda]'
        >>> matches[3].user_freq
        2.0
        >>> matches[4].phrase
        '¥'
        >>> matches[4].comment
        'yen [divisa, moneda]'
        >>> matches[4].user_freq
        2.0
        '''
        # pylint: enable=line-too-long
        #
        # self._emoji_dict contains only emoji or sequences without
        # variation selectors:
        emoji_string = self.variation_selector_normalize(
            emoji_string, variation_selector='')
        candidate_scores: Dict[Tuple[str, str, str], List[str]] = {}
        original_labels: Dict[str, Set[str]] = {}
        expanded_languages = itb_util.expand_languages(self._languages)
        label_keys = ('ucategories', 'categories', 'keywords')
        for language in expanded_languages:
            original_labels[language] = set()
            emoji_key = (emoji_string, language)
            if emoji_key not in self._emoji_dict:
                continue
            for label_key in label_keys:
                if label_key in self._emoji_dict[emoji_key]:
                    for label in self._emoji_dict[emoji_key][label_key]:
                        original_labels[language].add(label)
                        if (label_key == 'ucategories'
                                and label in UNICODE_CATEGORIES):
                            # For example, label could be 'So' in this
                            # case.  The next two labels will be
                            # 'Symbol' and 'Other' then. In almost all
                            # cases, adding these as well to
                            # original_labels_for_language would not
                            # change the final result. It would only
                            # add two more strings to the list of
                            # matching labels for *every* similar
                            # emoji. Therefore, it would only make the
                            # candidate list for similar emoji much
                            # wider without giving any extra
                            # information to the user. Better skip
                            # the rest of labels in this case.
                            break
        for similar_key, similar_key_value in self._emoji_dict.items():
            similar_string = similar_key[0]
            language = similar_key[1]
            if 'names' in similar_key_value:
                similar_name = similar_key_value['names'][0]
            else:
                similar_name = self.name(similar_string)
            if (len(similar_string) == 1
                    and is_invisible(similar_string)):
                # Add the code point to the display name of
                # “invisible” characters:
                similar_name = (f'U+{ord(similar_string):04X} '
                                + similar_name)
            scores_key = (
                similar_string, language, similar_name)
            if similar_string == emoji_string:
                # This is exactly the same emoji, add the emoji
                # itself as one extra label.  This way, the
                # original emoji gets a higher score then emoji
                # which share all categories and all keywords.
                # The most similar emoji should always be the
                # original emoji itself.
                candidate_scores[scores_key] = [
                    self.variation_selector_normalize(
                        emoji_string,
                        variation_selector=self._variation_selector)]
            for label_key in label_keys:
                if label_key in similar_key_value:
                    for label in similar_key_value[label_key]:
                        if label in original_labels[language]:
                            if scores_key in candidate_scores:
                                candidate_scores[scores_key].append(label)
                            else:
                                candidate_scores[scores_key] = [label]
        candidates: List[itb_util.PredictionCandidate] = [] #List[Tuple[str, str, float]] = []
        cldr_order_emoji_string = self.cldr_order(emoji_string)
        for csi in sorted(
                candidate_scores.items(),
                key=lambda csi: (
                    expanded_languages.index(csi[0][1]), # language index
                    - len(csi[1]), # number of matching labels
                    # abs(difference in cldr_order):
                    + abs(self.cldr_order(csi[0][0])
                          - cldr_order_emoji_string),
                    self.cldr_order(csi[0][0]), # CLDR order
                    - len(csi[0][0]), # length of emoji string
                    csi[0][2], # emoji name
                ))[:match_limit]:
            emoji = self.variation_selector_normalize(
                csi[0][0],
                variation_selector=self._variation_selector)
            if show_keywords:
                name = csi[0][2] + ' [' + ', '.join(csi[1]) + ']'
            else:
                name = csi[0][2]
            score = len(csi[1])
            candidates.append(itb_util.PredictionCandidate(
                phrase=emoji, user_freq=float(score), comment=name))
        return candidates

    def emoji_by_label(self) -> Dict[str, Dict[str, Dict[str, List[str]]]]:
        '''
        Return a dictionary listing the emoji by label
        '''
        label_keys = ('ucategories', 'categories', 'keywords', 'names')
        emoji_by_label_dict: Dict[str, Dict[str, Dict[str, List[str]]]] = {}
        for label_key in label_keys:
            for emoji_key, emoji_value in self._emoji_dict.items():
                emoji = self.variation_selector_normalize(
                    emoji_key[0],
                    variation_selector=self._variation_selector)
                if not self.unicode_version_in_range(emoji):
                    continue
                if len(emoji) > 1:
                    has_skin_tone_modifier = False
                    for modifier in SKIN_TONE_MODIFIERS:
                        if modifier in emoji:
                            has_skin_tone_modifier = True
                    if has_skin_tone_modifier:
                        # Skip all emoji which already contain a
                        # skin tone modifier, the skin tone variants
                        # will be created when needed when browsing
                        # the categories in emoji-picker:
                        continue
                language = emoji_key[1]
                if language not in emoji_by_label_dict:
                    emoji_by_label_dict[language] = {}
                if label_key in emoji_value:
                    if label_key not in emoji_by_label_dict[language]:
                        emoji_by_label_dict[language][label_key] = {}
                    if label_key == 'ucategories':
                        ucategory_label_full = ', '.join(
                            emoji_value[label_key])
                        if (ucategory_label_full
                            not in emoji_by_label_dict[language][label_key]):
                            emoji_by_label_dict[
                                language][
                                    label_key][
                                        ucategory_label_full] = [emoji]
                        else:
                            emoji_by_label_dict[
                                language][
                                    label_key][
                                        ucategory_label_full].append(emoji)
                    else:
                        for label in emoji_value[label_key]:
                            if label not in emoji_by_label_dict[language][label_key]:
                                emoji_by_label_dict[
                                    language][
                                        label_key][
                                            label] = [emoji]
                            else:
                                emoji_by_label_dict[
                                    language][
                                        label_key][
                                            label].append(emoji)
        for language, language_value in emoji_by_label_dict.items():
            for label_key in language_value:
                for label in language_value[label_key]:
                    language_value[label_key][label] = sorted(
                        language_value[label_key][label],
                        key=lambda x: (
                            self.cldr_order(x),
                            x,
                        ))
        return emoji_by_label_dict

    def emoji_order(self, emoji_string: str) -> int:
        '''Returns the “emoji_order” number from emojione

        Useful for sorting emoji. For characters which do not
        have an emoji order, 0xffffffff is returned.

        :param emoji_string: An emoji

        Examples:

        >>> matcher = EmojiMatcher(languages = ['en'])
        >>> matcher.emoji_order('😀')
        1

        >>> hex(matcher.emoji_order('∬'))
        '0xffffffff'
        '''
        # self._emoji_dict contains only emoji or sequences without
        # variation selectors:
        emoji_string = self.variation_selector_normalize(
            emoji_string, variation_selector='')
        if ((emoji_string, 'en') in self._emoji_dict
                and 'emoji_order' in self._emoji_dict[(emoji_string, 'en')]):
            return int(self._emoji_dict[(emoji_string, 'en')]['emoji_order'])
        return 0xFFFFFFFF

    def cldr_order(self, emoji_string: str) -> int:
        '''Returns a “cldr_order” number from CLDR

        Useful for sorting emoji. For characters which do not
        have a “cldr_order” number, 0xffffffff is returned.

        The “cldr_order” number is generated  by parsing
        emoji-test.txt.

        :param emoji_string: An emoji

        Examples:

        >>> matcher = EmojiMatcher(languages = ['en'])
        >>> matcher.cldr_order('😀')
        1

        >>> hex(matcher.cldr_order('∬'))
        '0xffffffff'
        '''
        # self._emoji_dict contains only emoji or sequences without
        # variation selectors:
        emoji_string = self.variation_selector_normalize(
            emoji_string, variation_selector='')
        if ((emoji_string, 'en') in self._emoji_dict
                and 'cldr_order' in self._emoji_dict[(emoji_string, 'en')]):
            return int(self._emoji_dict[(emoji_string, 'en')]['cldr_order'])
        return 0xFFFFFFFF

    def properties(self, emoji_string: str) -> List[str]:
        '''
        Returns the emoji properties of this emoji from the unicode.org data

        :param emoji_string: An emoji
        '''
        # self._emoji_dict contains only emoji or sequences without
        # variation selectors:
        emoji_string = self.variation_selector_normalize(
            emoji_string, variation_selector='')
        if (((emoji_string, 'en') in self._emoji_dict)
                and ('properties' in self._emoji_dict[(emoji_string, 'en')])):
            return list(self._emoji_dict[(emoji_string, 'en')]['properties'])
        return []

    def unicode_category(self, emoji_string: str) -> List[str]:
        '''
        Returns the Unicode category of this emoji from UnicodeData.txt

        :param emoji_string: An emoji or Unicode character
        '''
        emoji_string = self.variation_selector_normalize(
            emoji_string, variation_selector='')
        if (((emoji_string, 'en') in self._emoji_dict)
                and ('ucategories' in self._emoji_dict[(emoji_string, 'en')])):
            return list(self._emoji_dict[(emoji_string, 'en')]['ucategories'])
        return []

    def emoji_version(self, emoji_string: str) -> str:
        '''
        Returns the Emoji version when this emoji/character was added

        :param emoji_string: An emoji
        '''
        # self._emoji_dict contains only emoji or sequences without
        # variation selectors:
        emoji_string = self.variation_selector_normalize(
            emoji_string, variation_selector='')
        if (((emoji_string, 'en') in self._emoji_dict)
                and ('eversion' in self._emoji_dict[(emoji_string, 'en')])):
            return str(self._emoji_dict[(emoji_string, 'en')]['eversion'])
        return ''

    def unicode_version(self, emoji_string: str) -> str:
        '''
        Returns the Unicode version when this emoji/character was added

        :param emoji_string: An emoji
        '''
        # self._emoji_dict contains only emoji or sequences without
        # variation selectors:
        emoji_string = self.variation_selector_normalize(
            emoji_string, variation_selector='')
        if (((emoji_string, 'en') in self._emoji_dict)
                and ('uversion' in self._emoji_dict[(emoji_string, 'en')])):
            return str(self._emoji_dict[(emoji_string, 'en')]['uversion'])
        return ''

    def unicode_version_in_range(self, emoji_string: str) -> bool:
        '''
        Checks whether the Unicode version of this emoji is in the desired
        range

        :param emoji_string: An emoji
        :return: True if the Unicode version is in the desired range,
                 False if not.
        '''
        unicode_version = self.unicode_version(emoji_string)
        if not unicode_version:
            return False
        version = [
            int(number)
            for number in re.findall(r'\d+', unicode_version)]
        min_version = [
            int(number)
            for number in re.findall(r'\d+', self._emoji_unicode_min)]
        max_version = [
            int(number)
            for number in re.findall(r'\d+', self._emoji_unicode_max)]
        # Make all version number lists at at least length 3 to make
        # comparison work well:
        # `[15, 0, 0] <= [15] <= [15, 0]` is `False` but
        # `[15, 0, 0] <= [15, 0, 0] <= [15, 0, 0]` is `True`.
        version += [0] * (3 - len(version))
        min_version += [0] * (3 - len(min_version))
        max_version += [0] * (3 - len(max_version))
        if min_version <= version <= max_version:
            return True
        return False

    def unicode_block(self, emoji_string: str) -> str:
        '''Returns the name of the Unicode block the character is in'''
        # Get rid of the variation selector to be able to get the
        # Unicode block name of the base character:
        emoji_string = self.variation_selector_normalize(
            emoji_string, variation_selector='')
        if len(emoji_string) != 1:
            return ''
        codepoint = ord(emoji_string)
        for block_range, block_name in self._unicode_blocks.items():
            if codepoint in block_range:
                return block_name
        return ''

    def skin_tone_modifier_supported(self, emoji_string: str) -> bool:
        '''Checks whether skin tone modifiers are possible for this emoji

        Returns True if skin  tone modifiers  are possible
        for this emoji_string, False if not.

        :param emoji_string: The emoji to check

        Examples:

        >>> matcher = EmojiMatcher(languages = ['en'])
        >>> matcher.skin_tone_modifier_supported('👩')
        True

        >>> matcher.skin_tone_modifier_supported('👩🏻')
        True

        >>> matcher.skin_tone_modifier_supported('👮\u200d♀')
        True

        >>> matcher.skin_tone_modifier_supported('😀')
        False

        >>> matcher.skin_tone_modifier_supported('😀🏻')
        False

        >>> matcher.skin_tone_modifier_supported('')
        False

        >>> matcher.skin_tone_modifier_supported('🏻')
        False
        '''
        if len(self.skin_tone_variants(emoji_string)) > 1:
            return True
        return False

    def skin_tone_variants(self, emoji_string: str) -> List[str]:
        # pylint: disable=line-too-long
        '''
        Returns a list of skin tone variants for the given emoji

        If the given emoji does not support skin tones, a list
        containing only the original emoji is returned.

        :param emoji_string: The emoji to check

        Examples:

        >>> matcher = EmojiMatcher(languages = ['en'])
        >>> matcher.skin_tone_variants('👩')
        ['👩', '👩🏻', '👩🏼', '👩🏽', '👩🏾', '👩🏿']

        >>> matcher.skin_tone_variants('👩🏻')
        ['👩', '👩🏻', '👩🏼', '👩🏽', '👩🏾', '👩🏿']

        >>> matcher.skin_tone_variants('👮\u200d♀\ufe0f')
        ['👮\u200d♀\ufe0f', '👮🏻\u200d♀\ufe0f', '👮🏼\u200d♀\ufe0f', '👮🏽\u200d♀\ufe0f', '👮🏾\u200d♀\ufe0f', '👮🏿\u200d♀\ufe0f']

        >>> matcher.skin_tone_variants('👩\u200d🎓')
        ['👩\u200d🎓', '👩🏻\u200d🎓', '👩🏼\u200d🎓', '👩🏽\u200d🎓', '👩🏾\u200d🎓', '👩🏿\u200d🎓']

        >>> matcher.skin_tone_variants('😀')
        ['😀']

        >>> matcher.skin_tone_variants('😀🏿')
        ['😀🏿']

        >>> matcher.skin_tone_variants('')
        ['']

        >>> matcher.skin_tone_variants('🏿')
        ['🏿']

        # Family: woman, girl
        # See: http://unicode.org/Public/emoji/5.0/emoji-zwj-sequences.txt
        # which contains the line:
        #
        # 1F469 200D 1F467; Emoji_ZWJ_Sequence; family: woman, girl # 6.0  [1] (👩‍👧)
        >>> len(matcher.skin_tone_variants('👩\u200d👧'))
        36

        >>> len(matcher.skin_tone_variants('👩🏼\u200d👧🏿'))
        36

        >>> matcher.skin_tone_variants('👩🏼\u200d👧🏿') == matcher.skin_tone_variants('👩\u200d👧')
        True

        >>> matcher.skin_tone_variants('👩\u200d👧')
        ['👩\u200d👧', '👩\u200d👧🏻', '👩\u200d👧🏼', '👩\u200d👧🏽', '👩\u200d👧🏾', '👩\u200d👧🏿', '👩🏻\u200d👧', '👩🏻\u200d👧🏻', '👩🏻\u200d👧🏼', '👩🏻\u200d👧🏽', '👩🏻\u200d👧🏾', '👩🏻\u200d👧🏿', '👩🏼\u200d👧', '👩🏼\u200d👧🏻', '👩🏼\u200d👧🏼', '👩🏼\u200d👧🏽', '👩🏼\u200d👧🏾', '👩🏼\u200d👧🏿', '👩🏽\u200d👧', '👩🏽\u200d👧🏻', '👩🏽\u200d👧🏼', '👩🏽\u200d👧🏽', '👩🏽\u200d👧🏾', '👩🏽\u200d👧🏿', '👩🏾\u200d👧', '👩🏾\u200d👧🏻', '👩🏾\u200d👧🏼', '👩🏾\u200d👧🏽', '👩🏾\u200d👧🏾', '👩🏾\u200d👧🏿', '👩🏿\u200d👧', '👩🏿\u200d👧🏻', '👩🏿\u200d👧🏼', '👩🏿\u200d👧🏽', '👩🏿\u200d👧🏾', '👩🏿\u200d👧🏿']

        >>> len(matcher.skin_tone_variants('👨\u200d👩\u200d👧\u200d👦'))
        1296

        # Woman in lotus position
        # Does support skin tone in http://unicode.org/Public/emoji/5.0/emoji-data.txt
        # which contains the line:
        #
        # “1F9D1..1F9DD  ; Emoji_Modifier_Base  #10.0 [13] (🧑..🧝)    adult..elf”
        >>> matcher.skin_tone_variants('🧘\u200d♀\ufe0f')
        ['\U0001f9d8\u200d♀\ufe0f', '\U0001f9d8🏻\u200d♀\ufe0f', '\U0001f9d8🏼\u200d♀\ufe0f', '\U0001f9d8🏽\u200d♀\ufe0f', '\U0001f9d8🏾\u200d♀\ufe0f', '\U0001f9d8🏿\u200d♀\ufe0f']

        >>> matcher.skin_tone_variants('🏌\ufe0f\u200d♂\ufe0f')
        ['🏌\ufe0f\u200d♂\ufe0f', '🏌🏻\u200d♂\ufe0f', '🏌🏼\u200d♂\ufe0f', '🏌🏽\u200d♂\ufe0f', '🏌🏾\u200d♂\ufe0f', '🏌🏿\u200d♂\ufe0f']

        >>> matcher.skin_tone_variants('✌\ufe0f')
        ['✌\ufe0f', '✌🏻', '✌🏼', '✌🏽', '✌🏾', '✌🏿']

        >>> matcher = EmojiMatcher(languages = ['en'], variation_selector='')
        >>> matcher.skin_tone_variants('🏌\ufe0f\u200d♂\ufe0f')
        ['🏌\u200d♂', '🏌🏻\u200d♂', '🏌🏼\u200d♂', '🏌🏽\u200d♂', '🏌🏾\u200d♂', '🏌🏿\u200d♂']

        >>> matcher.skin_tone_variants('🏌\u200d♂')
        ['🏌\u200d♂', '🏌🏻\u200d♂', '🏌🏼\u200d♂', '🏌🏽\u200d♂', '🏌🏾\u200d♂', '🏌🏿\u200d♂']
        '''
        # pylint: enable=line-too-long
        if not emoji_string or emoji_string in SKIN_TONE_MODIFIERS:
            return [emoji_string]
        emoji_string = self.variation_selector_normalize(
            emoji_string, variation_selector='')
        if 'Emoji_Modifier_Base' in self.properties(emoji_string):
            return [
                self.variation_selector_normalize(
                    emoji_string + tone,
                    variation_selector=self._variation_selector)
                for tone in ('',) + SKIN_TONE_MODIFIERS]
        if ((emoji_string[-1] in SKIN_TONE_MODIFIERS)
                and ((emoji_string, 'en') in self._emoji_dict)):
            return [
                self.variation_selector_normalize(
                    emoji_string[:-1] + tone,
                    variation_selector=self._variation_selector)
                for tone in ('',) + SKIN_TONE_MODIFIERS]
        emoji_parts = emoji_string.split('\u200d')
        if len(emoji_parts) >= 2 and len(emoji_parts) <= 4:
            for modifier in SKIN_TONE_MODIFIERS:
                for i, emoji_part in enumerate(emoji_parts):
                    emoji_parts[i] = emoji_part.replace(modifier, '')
            skin_tone_variants = []
            if len(emoji_parts) == 2:
                for variant0 in self.skin_tone_variants(emoji_parts[0]):
                    for variant1 in self.skin_tone_variants(emoji_parts[1]):
                        skin_tone_variants.append(
                            variant0
                            + '\u200d'
                            + variant1)
            if len(emoji_parts) == 3:
                for variant0 in self.skin_tone_variants(emoji_parts[0]):
                    for variant1 in self.skin_tone_variants(emoji_parts[1]):
                        for variant2 in self.skin_tone_variants(emoji_parts[2]):
                            skin_tone_variants.append(
                                variant0
                                + '\u200d'
                                + variant1
                                + '\u200d'
                                + variant2)
            if len(emoji_parts) == 4:
                for variant0 in self.skin_tone_variants(emoji_parts[0]):
                    for variant1 in self.skin_tone_variants(emoji_parts[1]):
                        for variant2 in self.skin_tone_variants(emoji_parts[2]):
                            for variant3 in self.skin_tone_variants(emoji_parts[3]):
                                skin_tone_variants.append(
                                    variant0
                                    + '\u200d'
                                    + variant1
                                    + '\u200d'
                                    + variant2
                                    + '\u200d'
                                    + variant3)
            if skin_tone_variants:
                return skin_tone_variants
        return [self.variation_selector_normalize(
            emoji_string,
            variation_selector=self._variation_selector)]


    def debug_loading_data(self) -> None:
        '''To debug whether the data has been loaded correctly'''
        count = 0
        for key, value in sorted(self._emoji_dict.items()):
            print(f'key={key} value={sorted(value.items())}')
            count += 1
        print(f'count={count}')

    def list_emoji_one_bugs(self) -> None:
        '''
        Function to list bugs in emojione.json to help with reporting bugs.
        '''
        print('--------------------------------------------------')
        print('Possible bugs in emojione.json:')
        print('--------------------------------------------------')
        print('\n')
        for emoji_key, dummy_emoji_value in sorted(self._emoji_dict.items()):
            if emoji_key[1] == 'en':
                if ((emoji_key[0] + SKIN_TONE_MODIFIERS[0], 'en')
                        in self._emoji_dict):
                    if ('Emoji_Modifier_Base'
                            not in self.properties(emoji_key[0])):
                        print('emoji '
                              f'“{emoji_key[0]}” (U+{ord(emoji_key[0]):04X}) '
                              'has skintones in emojione '
                              'but not the Emoji_Modifier_Base '
                              'property in emoji-data.txt.')
                if 'Emoji_Modifier_Base' in self.properties(emoji_key[0]):
                    if ('emoji_order' not in self._emoji_dict[
                            (emoji_key[0] + SKIN_TONE_MODIFIERS[0], 'en')]):
                        print('emoji '
                              f'“{emoji_key[0]}” (U+{ord(emoji_key[0]):04X}) '
                              'has the property Emoji_Modifier_Base '
                              'in emoji-data.txt but no skin tones '
                              'in emojione.')
                if 'Emoji_ZWJ_Sequence' in self.properties(emoji_key[0]):
                    if ('emoji_order'
                            not in self._emoji_dict[(emoji_key[0], 'en')]):
                        print(f'ZWJ sequence “{emoji_key[0]}” '
                              'from unicode.org missing in emojione')
                else:
                    if (('emoji_order'
                         in self._emoji_dict[(emoji_key[0], 'en')])
                            and '\u200d' in emoji_key[0]):
                        print(f'ZWJ sequence “{emoji_key[0]}” '
                              'in emojione but not in unicode.org')

BENCHMARK = True

def main() -> None:
    '''
    Used for testing and profiling.

    “python3 itb_emoji.py”

    runs some tests and prints profiling data.
    '''
    log_handler = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(log_handler)

    if BENCHMARK:
        import cProfile # pylint: disable=import-outside-toplevel
        import pstats # pylint: disable=import-outside-toplevel
        profile = cProfile.Profile()
        profile.enable()

    failed = 0
    if False: # pylint: disable=using-constant-test
        matcher = EmojiMatcher(
            languages=['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE',
                       'ja_JP', 'zh_TW', 'zh_CN'],
            unicode_data=True, cldr_data=True)
        matcher.debug_loading_data()
        matcher.list_emoji_one_bugs()
    elif not IMPORT_RAPIDFUZZ_SUCCESSFUL:
        LOGGER.info('Skipping doctests because rapidfuzz is not available.')
    elif not IMPORT_ENCHANT_SUCCESSFUL:
        LOGGER.info('Skipping doctests because enchant is not available.')
    else:
        import doctest # pylint: disable=import-outside-toplevel
        # Set the domain name to something invalid to avoid using
        # the translations for the doctest tests. Translations may
        # make the tests fail just because some translations are
        # added, changed, or missing.
        global DOMAINNAME # pylint: disable=global-statement
        DOMAINNAME = ''
        flags = doctest.REPORT_NDIFF #|doctest.FAIL_FAST
        (failed, _attempted) = doctest.testmod(optionflags=flags)

    if BENCHMARK:
        profile.disable()
        stats = pstats.Stats(profile)
        stats.strip_dirs()
        stats.sort_stats('cumulative')
        stats.print_stats('itb_emoji', 50)
        stats.print_stats('enchant', 25)

    LOGGER.info(
        'itb_util.remove_accents() cache info: %s',
        itb_util.remove_accents.cache_info())
    LOGGER.info(
        '_match_classic() cache info: %s',
        _match_classic.cache_info()) # pylint: disable=no-value-for-parameter
    LOGGER.info(
        '_match_rapidfuzz() cache info: %s',
        _match_rapidfuzz.cache_info()) # pylint: disable=no-value-for-parameter

    sys.exit(failed)

if __name__ == "__main__":
    main()
