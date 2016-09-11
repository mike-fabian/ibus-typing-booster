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

'''A module used by ibus-typing-booster to match emoji and similar
Unicode characters.

'''

import os
import sys
import re
import gzip
import json
from difflib import SequenceMatcher

IMPORT_ENCHANT_SUCCESSFUL = False
try:
    import enchant
    IMPORT_ENCHANT_SUCCESSFUL = True
except (ImportError,):
    IMPORT_ENCHANT_SUCCESSFUL = False

DATADIR = os.path.join(os.path.dirname(__file__), '../data')

# VALID_CATEGORIES and VALID_RANGES are taken from ibus-uniemoji.

VALID_CATEGORIES = (
    'Sm', # Symbol, math
    'So', # Symbol, other
    'Sc', # Symbol, Currency
    'Pd', # Punctuation, dash
    'Po', # Punctuation, other
)

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
}

def _in_range(codepoint):
    '''Checks whether the codepoint is in one of the valid ranges

    Returns True if the codepoint is in one of the valid ranges,
    else it returns False.

    :param codepoint: The Unicode codepoint to check
    :type codepoint: Integer
    :rtype: Boolean

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
    return any([x <= codepoint <= y for x, y in VALID_RANGES])

SPANISH_419_LOCALES = (
    'es_AR', 'es_MX', 'es_BO', 'es_CL', 'es_CO', 'es_CR',
    'es_CU', 'es_DO', 'es_EC', 'es_GT', 'es_HN', 'es_NI',
    'es_PA', 'es_PE', 'es_PR', 'es_PY', 'es_SV', 'es_US',
    'es_UY', 'es_VE',)

def _expand_languages(languages):
    '''Expands the given list of languages by including fallbacks.

    Returns a possibly longer list of languages by adding
    aliases and fallbacks.

    :param languages: A list of languages (or locale names)
    :type languages: List of strings
    :rtype: List  of strings

    Examples:

    >>> _expand_languages(['es_MX', 'es_ES', 'ja_JP'])
    ['es_MX', 'es_419', 'es', 'es_ES', 'es', 'ja_JP', 'ja', 'en']
    '''
    expanded_languages = []
    for language in languages:
        expanded_languages.append(language)
        if language in SPANISH_419_LOCALES:
            expanded_languages.append('es_419')
        if language.split('_')[:1] != [language]:
            expanded_languages += language.split('_')[:1]
    if 'en' not in expanded_languages:
        expanded_languages.append('en')
    return expanded_languages

def _find_path_and_open_function(dirnames, basenames):
    '''Find the first existing file of a list of basenames and dirnames

    For each file in “basenames”, tries whether that file or the
    file with “.gz” added can be found in the list of directories
    “dirnames”.

    Returns a tuple (path, open_function) where “path” is the
    complete path of the first file found and the open function
    is either “open()” or “gzip.open()”.

    :param dirnames: A list of directories to search in
    :type dirnames: List of strings
    :param basenames: A list of file names to search for
    :type basenames: List of strings
    :rtype: A tuple (path, open_function)

    '''
    for basename in basenames:
        for dirname in dirnames:
            path = os.path.join(dirname, basename)
            if os.path.exists(path):
                if path.endswith('.gz'):
                    return (path, gzip.open)
                else:
                    return (path, open)
            path = os.path.join(dirname, basename + '.gz')
            if os.path.exists(path):
                return (path, gzip.open)
    return ('', None)

class EmojiMatcher():
    '''A class to find Emoji which best match a query string'''

    def __init__(self, languages = ('en_US',),
                 unicode_data = True, cldr_data = True, quick = True):
        '''
        Initialize the emoji matcher

        :param languages: A list of languages to use for matching emoji
        :type languages: List or tuple of strings
        :param unicode_data: Whether to load the UnicodeData.txt file as well
        :type unicode_data: Boolean
        :param cldr_data: Whether to load data from CLDR as well
        :type cldr_data: Boolean
        :param quick: Whether to do a quicker but slighly less precise match.
                      Quick matching is about 4 times faster and usually
                      good enough.
        :type quick: Boolean
        '''
        self._languages = languages
        self._quick = quick
        self._enchant_dicts = []
        if IMPORT_ENCHANT_SUCCESSFUL:
            for language in self._languages:
                if enchant.dict_exists(language):
                    self._enchant_dicts.append(enchant.Dict(language))
        # From the documentation
        # (https://docs.python.org/3.6/library/difflib.html):
        # “SequenceMatcher computes and caches detailed information
        # about the second sequence, so if you want to compare one
        # sequence against many sequences, use set_seq2() to set the
        # commonly used sequence once and call set_seq1() repeatedly,
        # once for each of the other sequences.”
        self._matcher = SequenceMatcher(
            isjunk = None, a = '', b = '', autojunk = False)
        self._match_cache = {}
        self._string1 = ''
        self._seq1 = ''
        self._len1 = 0
        self._string2 = ''
        self._string2_number_of_words = 0
        self._string2_word_list = []
        self._seq2 = ''
        self._len2 = 0
        self._emoji_dict = {}
        self._candidate_cache = {}
        # The three data sources are loaded in this order on purpose.
        # The data from Unicode is loaded first to put the official
        # names first into the list of names to display the official
        # names in the candidates, if possible.  The second best names
        # are the long names of emojione.
        if unicode_data:
            self._load_unicode_data()
        self._load_emojione_data()
        if cldr_data:
            for language in self._languages:
                self._load_cldr_annotation_data(language)

    def get_languages(self):
        '''Returns a copy of the list of languages of this EmojiMatcher

        Useful to check whether an already available EmojiMatcher instance
        can be used or whether one needs a new instance because one needs
        a different list of languages.

        Note that the order of that list is important, a matcher which
        supports the same languages but in an different order might
        return different results.

        :rtype: A list of strings

        Examples:

        >>> m = EmojiMatcher(languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        >>> m.get_languages()
        ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP']

        '''
        # Use list() to make a copy instead of self._languages[:] because
        # the latter might return the default tuple ('en_US',) instead
        # of a list ['en_US'] which makes comparison with another list
        # more inconvenient:
        return list(self._languages)

    def _add_to_emoji_dict(self, emoji_dict_key, values_key, values):
        '''Adds data to the emoji_dict if not already there'''
        if emoji_dict_key not in self._emoji_dict:
            self._emoji_dict[emoji_dict_key] = {values_key : values}
        else:
            if values_key not in self._emoji_dict[emoji_dict_key]:
                self._emoji_dict[emoji_dict_key][values_key] = values
            else:
                for value in values:
                    if (value not in
                        self._emoji_dict[emoji_dict_key][values_key]):
                        self._emoji_dict[emoji_dict_key][values_key] += [value]

    def _load_unicode_data(self):
        '''Loads emoji names from UnicodeData.txt'''
        dirnames = (DATADIR, '/usr/share/unicode/ucd')
        basenames = ('UnicodeData.txt',)
        (path, open_function) = _find_path_and_open_function(
            dirnames, basenames)
        if not path:
            sys.stderr.write(
                '_load_unicode_data(): could not find "%s" in "%s"\n'
                %(basenames, dirnames))
            return
        with open_function(path, mode = 'rt') as unicode_data_file:
            for line in unicode_data_file.readlines():
                if not line.strip():
                    continue
                codepoint_string, name, category = line.split(';')[:3]
                codepoint_integer = int(codepoint_string, 16)
                emoji_string = chr(codepoint_integer)
                if ((category not in VALID_CATEGORIES
                     or not _in_range(codepoint_integer))
                    and emoji_string not in VALID_CHARACTERS):
                    continue
                self._add_to_emoji_dict(
                    (emoji_string, 'en'), 'names', [name.lower()])
                self._add_to_emoji_dict(
                    (emoji_string, 'en'), 'categories', [category.lower()])

    def _load_emojione_data(self):
        '''
        Loads emoji names, aliases, keywords, and categories from
        the emojione.json file.
        '''
        dirnames = (DATADIR, '/usr/lib/node_modules/emojione/')
        basenames = ('emojione.json', 'emoji.json')
        (path, open_function) = _find_path_and_open_function(
            dirnames, basenames)
        if not path:
            sys.stderr.write(
                '_load_emojione_data(): could not find "%s" in "%s"\n'
                %(basenames, dirnames))
            return
        with open_function(path, mode = 'rt') as emoji_one_file:
            emojione = json.load(emoji_one_file)
        for dummy_emojione_key, emojione_value in emojione.items():
            codepoints = emojione_value['unicode']
            # ZWJ emojis are in the 'unicode_alternates' field:
            if ('unicode_alternates' in emojione_value
                and '200d' in emojione_value['unicode_alternates']):
                codepoints = emojione_value['unicode_alternates']

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
            display_name = emojione_value['name']
            match_name = re.sub(r' ?[(,)] ?', r' ', display_name).strip(' ')
            names = [display_name]
            shortname = emojione_value[
                'shortname'].replace('_', ' ').strip(':')
            aliases = [x.replace('_', ' ').strip(':')
                       for x in emojione_value['aliases']]
            ascii_aliases = emojione_value['aliases_ascii']
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

            self._add_to_emoji_dict(
                (emoji_string, 'en'), 'names', names)
            self._add_to_emoji_dict(
                (emoji_string, 'en'), 'categories', categories)
            self._add_to_emoji_dict(
                (emoji_string, 'en'), 'keywords', keywords)

    def _load_cldr_annotation_data(self, language):
        '''
        Loads translations of emoji names and keywords.

        Translations are loaded from the annotation data from CLDR.
        '''
        dirnames = (DATADIR,
                    '/local/mfabian/src/cldr-svn/trunk/common/annotations')
        basenames = [x + '.xml' for x in _expand_languages([language])]
        (path, open_function) = _find_path_and_open_function(
            dirnames, basenames)
        if not path:
            sys.stderr.write(
                '_load_cldr_annotation_data(): could not find "%s" in "%s"\n'
                %(basenames, dirnames))
            return
        # change language to the language of the file which was really
        # found (For example, it could be that 'es_ES' was requested,
        # but only the fallback 'es' was really found):
        language = os.path.basename(
            path).replace('.gz', '').replace('.xml', '')
        with open_function(path, mode = 'rt') as cldr_annotation_file:
            pattern = re.compile(
                r'.*<annotation cp="(?P<emojistring>[^"]+)"'
                +r'\s*(?P<tts>type="tts"){0,1}'
                +r'>'
                +r'(?P<content>.+)'
                +r'</annotation>.*'
            )
            for line in cldr_annotation_file.readlines():
                match = pattern.match(line)
                if match:
                    emoji_string = match.group('emojistring')
                    if match.group('tts'):
                        self._add_to_emoji_dict(
                            (emoji_string, language),
                            'names',
                            [match.group('content')]
                        )
                    else:
                        self._add_to_emoji_dict(
                            (emoji_string, language),
                            'keywords',
                            [x.strip()
                             for x in match.group('content').split('|')]
                        )

    def _set_seq1(self, string):
        '''Sequence 1 is a label from the emoji data'''
        string = string.lower()
        self._string1 = string
        if not self._quick:
            # only needed when using SequenceMatcher()
            string = ' ' + string + ' '
            self._seq1 = string
            self._len1 = len(string)
            self._matcher.set_seq1(string)

    def _set_seq2(self, string):
        '''Sequence 2 is the query string, i.e. the user input'''
        string = string.lower()
        self._string2 = string
        # Split the input string into a list of words:
        word_list = []
        original_words = string.split(sep=None)
        self._string2_number_of_words = len(original_words)
        for word in original_words:
            word_list += [word]
            # If a word in the input string is not correctly spelled
            # in any of the enabled dictionaries, add spell checking
            # suggestions to the list (don’t do that it it is spelled
            # correctly in at least one dictionary):
            if len(word) > 3 and IMPORT_ENCHANT_SUCCESSFUL:
                spelled_correctly = False
                for dic in self._enchant_dicts:
                    if dic.check(word) or dic.check(word.title()):
                        spelled_correctly = True
                if not spelled_correctly: # incorrect in *all* dictionaries
                    wlist = []
                    for dic in self._enchant_dicts:
                        # don’t use spellchecking suggestions shorter then
                        # 3 characters and lower case everything
                        wlist += [
                            x.lower() for x in dic.suggest(word) if len(x) > 2]
                    # remove possible duplicates from spellchecking
                    word_list += set(wlist)
        # Keep duplicates coming from the query string.
        # Sort longest words first.
        self._string2_word_list = sorted(word_list, key = lambda x: -len(x))
        if not self._quick:
            # only needed when using SequenceMatcher()
            string = ' ' + string + ' '
            self._seq2 = string
            self._len2 = len(string)
            self._matcher.set_seq2(string)
            self._match_cache = {}

    def _match(self, label, debug = False):
        '''Matches a label from the emoji data against the query string.

        The query string must have been already set with
        self._set_seq2(query_string) before calling self._match().

        '''
        self._set_seq1(label)
        total_score = 0
        if debug:
            print('string1 = “%s” string2 = “%s” string2_word_list = “%s”'
                  %(self._string1, self._string2, self._string2_word_list))
        if (self._string1, self._string2) in self._match_cache:
            # Many keywords are of course shared by many emoji,
            # therefore the query string is often matched against
            # labels already matched previously. Caching previous
            # matches speeds it up quite a bit.
            total_score = self._match_cache[(self._string1, self._string2)]
            if debug:
                print('Cached, total_score = %s' %total_score)
            return total_score
        # Does the complete query string match exactly?
        if self._string1 == self._string2:
            if debug:
                print('Exact match, total_score += 1000')
            total_score += 1000
        # Does a word in the query string match exactly?
        for word in set(self._string2_word_list):
            # use set() here to avoid making an exact match stronger
            # just because a word happens to be twice in the input.
            if word == self._string1:
                if self._string2_number_of_words == 1:
                    total_score += 300
                    if debug:
                        print('Spell check exact match, word = “%s”, '
                              %word + 'total_score += 300')
                else:
                    total_score += 200
                    if debug:
                        print('Exact match from word_list, word = “%s”, '
                              %word + 'total_score += 200')
        # Does a word in the query string match the beginning of a word in
        # the label?
        tmp = self._string1
        for word in self._string2_word_list:
            match = re.search(r'\b' + re.escape(word), tmp)
            if match:
                match_value = 100 + match.end() - match.start()
                if match.start() == 0:
                    match_value += 20
                total_score += match_value
                tmp = tmp[:match.start()] + tmp[match.end():]
                if debug:
                    print('Substring match from word_list, word = “%s”, '
                          %word
                          + 'total_score += %s' %match_value)
        # Does a word in the query string match the label if spaces in
        # the label are ignored?
        tmp = self._string1.replace(' ','')
        for word in self._string2_word_list:
            match = re.search(re.escape(word), tmp)
            if match:
                match_value = 20 + match.end() - match.start()
                if match.start() == 0:
                    match_value += 20
                total_score += match_value
                tmp = tmp[:match.start()] + tmp[match.end():]
                if debug:
                    print('Space insensitive substring match from word_list, '
                          + 'word = “%s”, ' %word
                          + 'total_score += %s' %match_value)
        if self._quick:
            self._match_cache[(self._string1, self._string2)] = total_score
            return total_score
        # The following code using SequenceMatcher() might increase
        # the total_score by up to 500 approximately. It improves
        # the matching a little bit but it is very slow.
        if debug:
            print('seq1 = “%s” seq2 = “%s”' %(self._seq1, self._seq2))
        for tag, i1, i2, j1, j2 in self._matcher.get_opcodes():
            score = 0
            if tag in ('replace', 'delete', 'insert'):
                pass
            if tag  == 'equal':
                match_length = i2 - i1
                if match_length > 1:
                    score += match_length
                    # favor word boundaries
                    if self._seq1[i1] == ' ':
                        if i1 == 0 and j1 == 0:
                            score += 4 * match_length
                        elif i1 == 0 or j1 == 0:
                            score += 2 * match_length
                        else:
                            score += match_length
                    if i1 > 0 and j1 > 0 and self._seq1[i1 - 1] == ' ':
                        score += match_length
                    if self._seq1[i2 - 1] == ' ':
                        if i2 == self._len1 and j2 == self._len2:
                            score += 4 * match_length
                        elif i2 == self._len1 or j2 == self._len2:
                            score += 2 * match_length
                        else:
                            score += match_length
            total_score += score
            if debug:
                print(
                    '{:7} a[{:2}:{:2}] --> b[{:2}:{:2}]'.format(
                        tag, i1, i2, j1, j2)
                    + '{:3} {:3} {!r} --> {!r}'.format(
                        score, total_score,
                        self._seq1[i1:i2], self._seq2[j1:j2]))
        self._match_cache[(self._string1, self._string2)] = total_score
        return total_score

    def candidates(self, query_string, match_limit = 20, debug = tuple()):
        '''
        Find a list of emoji which best match a query string.

        :param query_string: A search string
        :type query_string: string
        :param match_limit: Limit the number of matches to this amount
        :type match_limit: integer
        :param debug: List or tuple of emojis to print debug information
                      about the matching to stdout.
        :type debug: List of strings
        :rtype: A list of tuples of the form (<emoji>, <name>, <score),
                i.e. a list like this:
                [('🎂', 'birthday cake', 3106), ...]

        Examples:

        >>> mq = EmojiMatcher(languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])

        >>> mq.candidates('😺', match_limit = 3)
        [('😺', "smiling cat face with open mouth ['animal', 'cat', 'face', 'happy', 'mouth', 'open', 'people', 'smile', 'so']", 9), ('😸', "grinning cat face with smiling eyes ['animal', 'cat', 'face', 'happy', 'people', 'smile', 'so']", 7), ('😃', "smiling face with open mouth ['face', 'happy', 'mouth', 'open', 'people', 'smile', 'so']", 7)]

        >>> mq.candidates('ant')[0][:2]
        ('🐜', 'ant')

        >>> mq.candidates('ameise')[0][:2]
        ('🐜', 'Ameise')

        >>> mq.candidates('Ameise')[0][:2]
        ('🐜', 'Ameise')

        >>> mq.candidates('formica')[0][:2]
        ('🐜', 'formica')

        >>> mq.candidates('hormiga')[0][:2]
        ('🐜', 'hormiga')

        >>> mq.candidates('cacca')[0][:2]
        ('💩', 'cacca')

        >>> mq.candidates('orso')[0][:2]
        ('🐻', 'faccina orso')

        >>> mq.candidates('lupo')[0][:2]
        ('🐺', 'faccina lupo')

        >>> mq.candidates('gatto')[0][:2]
        ('🐈', 'gatto')

        >>> mq.candidates('gatto sorride')[0][:2]
        ('😺', 'gatto che sorride')

        Any white space and '_' can be used to separate keywords in the
        query string:

        >>> mq.candidates('gatto_	 sorride')[0][:2]
        ('😺', 'gatto che sorride')

        >>> mq.candidates('nerd glasses')[0][:2]
        ('🤓', 'nerd face')

        >>> mq.candidates('smiling face eye sun glasses')[0][:2]
        ('😎', 'smiling face with sunglasses')

        >>> mq.candidates('halo')[0][:2]
        ('😇', 'smiling face with halo')

        >>> mq.candidates('factory')[0][:2]
        ('🏭', 'factory')

        >>> mq.candidates('man tone5')[0][:2]
        ('👨🏿', 'man tone 5 “man tone5”')

        >>> mq.candidates('mantone5')[0][:2]
        ('👨🏿', 'man tone 5')

        >>> mq.candidates('tone')[0][:2]
        ('🏻', 'emoji modifier Fitzpatrick type-1-2 “tone1”')

        >>> mq.candidates('tone5')[0][:2]
        ('🏿', 'emoji modifier Fitzpatrick type-6 “tone5”')

        >>> mq.candidates('a')[0][:2]
        ('🅰', 'negative squared latin capital letter a “a button”')

        >>> mq.candidates('squared a')[0][:2]
        ('🅰', 'negative squared latin capital letter a “a button”')

        >>> mq.candidates('squared capital a')[0][:2]
        ('🅰', 'negative squared latin capital letter a “a button”')

        >>> mq.candidates('c')[0][:2]
        ('©', 'Copyright')

        >>> mq.candidates('us')[0][:2]
        ('🇺🇸', 'united states “us”')

        >>> mq.candidates('flag us')[0][:2]
        ('🇺🇸', 'united states “us” [flag]')

        >>> mq.candidates('united states')[0][:2]
        ('🇺🇸', 'united states')

        >>> mq.candidates('united')[0][:2]
        ('🇺🇸', 'united states')

        >>> mq.candidates('united minor')[0][:2]
        ('🇺🇲', 'united states minor outlying islands')

        >>> mq.candidates('united arab')[0][:2]
        ('🇦🇪', 'the united arab emirates')

        >>> mq.candidates('mm')[0][:2]
        ('🇲🇲', 'myanmar “mm”')

        >>> mq.candidates('flag mm')[0][:2]
        ('🇲🇲', 'myanmar “mm” [flag]')

        >>> mq.candidates('myanmar')[0][:2]
        ('🇲🇲', 'myanmar')

        >>> mq.candidates('sj')[0][:2]
        ('🇸🇯', 'svalbard and jan mayen “sj”')

        >>> mq.candidates('flag sj')[0][:2]
        ('🇸🇯', 'svalbard and jan mayen “sj” [flag]')

        >>> mq.candidates('svalbard')[0][:2]
        ('🇸🇯', 'svalbard and jan mayen')

        >>> mq.candidates('jan mayen')[0][:2]
        ('🇸🇯', 'svalbard and jan mayen')

        >>> mq.candidates('mayen')[0][:2]
        ('🇸🇯', 'svalbard and jan mayen')

        >>> mq.candidates(':-)')[0][:2]
        ('🙂', 'slightly smiling face “:-)”')

        >>> mq.candidates('family')[0][:2]
        ('👪', 'family')

        >>> mq.candidates('man')[0][:2]
        ('👨', 'man')

        >>> mq.candidates('woman')[0][:2]
        ('👩', 'woman')

        >>> mq.candidates('girl')[0][:2]
        ('👧', 'girl')

        >>> mq.candidates('boy')[0][:2]
        ('👦', 'boy')

        >>> mq.candidates('family man')[0][:2]
        ('👨\u200d👨\u200d👦\u200d👦', 'family (man,man,boy,boy) “family mmbb”')

        >>> mq.candidates('man man girl boy')[0][:2]
        ('👨\u200d👨\u200d👧\u200d👦', 'family (man,man,girl,boy) “family man man girl boy”')

        >>> mq.candidates('mmgb')[0][:2]
        ('👨\u200d👨\u200d👧\u200d👦', 'family (man,man,girl,boy) “family mmgb”')

        >>> mq.candidates('manmangirlboy')[0][:2]
        ('👨\u200d👨\u200d👧\u200d👦', 'family (man,man,girl,boy)')

        >>> mq.candidates('bird')[0][:2]
        ('🐦', 'bird')

        >>> mq.candidates('bir')[0][:2]
        ('🎂', 'birthday cake')

        >>> mq.candidates('birth')[0][:2]
        ('🎂', 'birthday cake')

        >>> mq.candidates('camera')[0][:2]
        ('📷', 'camera')

        >>> mq.candidates('symbol')[0][:2]
        ('🔣', 'input symbol for symbols “input symbols”')

        >>> mq.candidates('atomsymbol')[0][:2]
        ('⚛', 'atom symbol')

        >>> mq.candidates('peacesymbol')[0][:2]
        ('☮', 'peace symbol')

        >>> mq.candidates('peace symbol')[0][:2]
        ('☮', 'peace symbol')

        >>> mq.candidates('animal')[0][:2]
        ('🐝', 'abeja [animal]')

        >>> mq.candidates('dromedary animal')[0][:2]
        ('🐪', 'dromedary camel')

        >>> mq.candidates('camel')[0][:2]
        ('🐫', 'bactrian camel “two-hump camel”')

        >>> mq.candidates('people')[0][:2]
        ('👯', 'woman with bunny ears “people with bunny ears partying”')

        >>> mq.candidates('nature')[0][:2]
        ('🌼', 'blossom {nature}')

        >>> mq.candidates('thankyou')[0][:2]
        ('🍻', 'clinking beer mugs [thank you]')

        >>> mq.candidates('travel')[0][:2]
        ('🚡', 'aerial tramway {travel}')

        >>> mq.candidates('ferry')[0][:2]
        ('⛴', 'ferry')

        >>> mq.candidates('ferry travel')[0][:2]
        ('⛴', 'ferry {travel}')

        >>> mq.candidates('ferry travel boat')[0][:2]
        ('⛴', 'ferry {travel}')

        >>> mq.candidates('boat')[0][:2]
        ('🛥', 'motor boat')

        >>> mq.candidates('anchor')[0][:2]
        ('⚓', 'anchor')

        >>> mq.candidates('anchor boat')[0][:2]
        ('⚓', 'anchor [boat]')

        >>> mq.candidates('buterfly')[0][:2]
        ('\U0001f98b', 'butterfly')

        >>> mq.candidates('badminton')[0][:2]
        ('🏸', 'badminton racquet and shuttlecock')

        >>> mq.candidates('badmynton')[0][:2]
        ('🏸', 'badminton racquet and shuttlecock')

        >>> mq.candidates('padminton')[0][:2]
        ('🏸', 'badminton racquet and shuttlecock')

        >>> mq.candidates('fery')[0][:2]
        ('⛴', 'ferry')

        >>> mq.candidates('euro sign')[0][:2]
        ('€', 'euro sign')

        >>> mq = EmojiMatcher(languages = ['fr_FR'])
        >>> mq.candidates('chat')[0][:2]
        ('🐈', 'chat')

        fr.xml from CLDR has no name (tts) for 🤔.
        Therefore, we get the English name as a fallback:

        >>> mq.candidates('réflexion')[0][:2]
        ('🤔', 'thinking face [réflexion]')

        >>> mq.candidates('🤔', match_limit = 3)
        [('🤔', "thinking face ['réflexion', 'visage']", 2), ('💆\u200d♀', "femme qui se fait masser le visage ['visage']", 1), ('💆\u200d♂', "homme qui se fait masser le visage ['visage']", 1)]

        fr.xml from CLDR has no name (tts) for 🤔, but de.xml has a German name for 🤔.
        Therefore, we get the German name as a fallback here:

        >>> mq = EmojiMatcher(languages = ['fr_FR', 'de_DE'])
        >>> mq.candidates('réflexion')[0][:2]
        ('🤔', 'Nachdenkender Smiley [réflexion]')

        >>> mq.candidates('🤔', match_limit = 3)
        [('🤔', "Nachdenkender Smiley ['réflexion', 'visage']", 2), ('💆\u200d♀', "femme qui se fait masser le visage ['visage']", 1), ('💆\u200d♂', "homme qui se fait masser le visage ['visage']", 1)]
        '''
        # Replace any sequence of white space characters and '_' in
        # the query string with a single ' ':
        query_string = re.sub('[_\s]+', ' ', query_string)
        if ((query_string, match_limit) in self._candidate_cache
            and not debug):
            return self._candidate_cache[(query_string, match_limit)]
        if (query_string, 'en') in self._emoji_dict:
            # the query_string is itself an emoji, match similar ones:
            candidates = self.similar(query_string, match_limit = match_limit)
            self._candidate_cache[(query_string, match_limit)] = candidates
            return candidates
        self._set_seq2(query_string)
        candidates = []
        for emoji_key, emoji_value in self._emoji_dict.items():
            if emoji_key[0] in debug:
                debug_match = True
                print('===================================')
                print('Debug match for “%s”' %emoji_key[0])
                print('===================================')
            else:
                debug_match = False

            total_score = 0
            good_match_score = 200
            name_good_match = ''
            category_good_match = ''
            keyword_good_match = ''
            if 'names' in emoji_value:
                for name in emoji_value['names']:
                    score = 2 * self._match(name, debug = debug_match)
                    if score >= good_match_score:
                        name_good_match = name
                    total_score += score
            if 'categories' in emoji_value:
                for category in emoji_value['categories']:
                    score = self._match(category, debug = debug_match)
                    if score >= good_match_score:
                        category_good_match = category
                    total_score += score
            if 'keywords' in emoji_value:
                for keyword in emoji_value['keywords']:
                    score = self._match(keyword, debug = debug_match)
                    if score >= good_match_score:
                        keyword_good_match = keyword
                    total_score += score

            if total_score > 0:
                if 'names' in emoji_value:
                    display_name = emoji_value['names'][0]
                else:
                    display_name = self.name(emoji_key[0])
                # If the match was good because something else
                # but the main name had a good match, show it in
                # the display name to make the user understand why
                # this emoji matched:
                if name_good_match not in display_name:
                    display_name += ' “' + name_good_match + '”'
                if category_good_match not in display_name:
                    display_name += ' {' + category_good_match + '}'
                if keyword_good_match not in display_name:
                    display_name += ' [' + keyword_good_match + ']'
                candidates.append((emoji_key[0], display_name, total_score))

        sorted_candidates = sorted(candidates,
                                   key = lambda x: (
                                       - x[2],
                                       - len(x[0]),
                                       x[1]
                                   ))[:match_limit]

        self._candidate_cache[(query_string, match_limit)] = sorted_candidates
        return sorted_candidates

    def name(self, emoji_string):
        '''Find a name of an emoji.

        Returns a name of the emoji in the first language given
        for which where a name can be found.

        :param emoji_string: The string of Unicode characters which are
                             used to encode the emoji
        :type emoji_string: A string
        :rtype: string

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
        'Computer'

        >>> matcher = EmojiMatcher(languages=['it_IT', 'es_ES', 'es_MX', 'ja_JP'])
        >>> matcher.name('🖥')
        'desktop PC'

        >>> matcher = EmojiMatcher(languages=['fr_FR'])
        >>> matcher.name('🖥')
        'ordinateur de bureau'

        fr.xml from CLDR has no name (tts) for this emoji.
        Therefore, we get the English name as a fallback:

        >>> matcher.name('🤔')
        'thinking face'

        If we add German as another fallback language, we get a German name
        because a German name for 🤔 exists in de.xml in CLDR:

        >>> matcher = EmojiMatcher(languages=['fr_FR', 'de_DE'])
        >>> matcher.name('🤔')
        'Nachdenkender Smiley'
        '''
        for language in _expand_languages(self._languages):
            if ((emoji_string, language) in self._emoji_dict
                and 'names' in self._emoji_dict[(emoji_string, language)]):
                return self._emoji_dict[(emoji_string, language)]['names'][0]
        return ''

    def similar(self, emoji_string, match_limit = 1000):
        '''Find similar emojis

        “Similar” means they share categories or keywords.

        :param emoji_string: The string of Unicode  characters which are
                             used to encode the emoji
        :type emoji_string: A string
        :rtype: A list of tuples of the form (<emoji>, <name>, <score>),
                i.e. a list like this:

                [('🐫', "cammello ['animale', 'gobba']", 2), ...]

                The name includes the list of categories or keywords
                which matched, the score is the number of categories
                or keywords matched.

                The list is sorted by preferred language, then score,
                then name.

        Examples:

        >>> matcher = EmojiMatcher(languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])

        >>> matcher.similar('this is not an emoji', match_limit = 5)
        []

        >>> matcher.similar('☺', match_limit = 5)
        [('☺', "white smiling face ['face', 'happy', 'outlined', 'people', 'relaxed', 'smile', 'smiley', 'so']", 8), ('😋', "face savouring delicious food ['face', 'happy', 'people', 'smile', 'smiley', 'so']", 6), ('😁', "grinning face with smiling eyes ['face', 'happy', 'people', 'smile', 'smiley', 'so']", 6), ('🙂', "slightly smiling face ['face', 'happy', 'people', 'smile', 'smiley', 'so']", 6), ('😍', "smiling face with heart-shaped eyes ['face', 'happy', 'people', 'smile', 'smiley', 'so']", 6)]

        >>> matcher = EmojiMatcher(languages = ['it_IT', 'en_US', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        >>> matcher.similar('☺', match_limit = 5)
        [('☺', "faccina sorridente ['contorno faccina sorridente', 'emozionarsi', 'faccina', 'sorridente']", 4), ('😺', "gatto che sorride ['faccina', 'sorridente']", 2), ('👽', "alieno ['faccina']", 1), ('👼', "angioletto ['faccina']", 1), ('🤑', "avidità di denaro ['faccina']", 1)]

        >>> matcher = EmojiMatcher(languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        >>> matcher.similar('🐫', match_limit = 5)
        [('🐫', "bactrian camel ['animal', 'bactrian', 'camel', 'hump', 'hump day', 'nature', 'so', 'wildlife']", 8), ('🐪', "dromedary camel ['animal', 'hump', 'nature', 'so', 'wildlife']", 5), ('🐻', "bear face ['animal', 'nature', 'so', 'wildlife']", 4), ('🐦', "bird ['animal', 'nature', 'so', 'wildlife']", 4), ('🐡', "blowfish ['animal', 'nature', 'so', 'wildlife']", 4)]

        >>> matcher = EmojiMatcher(languages = [ 'it_IT', 'en_US','es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        >>> matcher.similar('🐫', match_limit = 5)
        [('🐫', "cammello ['animale', 'gobba']", 2), ('🐪', "dromedario ['animale', 'gobba']", 2), ('🐀', "Ratto ['animale']", 1), ('🐁', "Topo ['animale']", 1), ('\U0001f986', "anatra ['animale']", 1)]

        >>> matcher = EmojiMatcher(languages = ['de_DE', 'it_IT', 'en_US','es_MX', 'es_ES', 'ja_JP'])
        >>> matcher.similar('🐫', match_limit = 5)
        [('🐫', "Kamel ['Tier', 'zweihöckrig']", 2), ('🐒', "Affe ['Tier']", 1), ('🐵', "Affengesicht ['Tier']", 1), ('🐜', "Ameise ['Tier']", 1), ('🐝', "Biene ['Tier']", 1)]

        >>> matcher = EmojiMatcher(languages = ['es_MX', 'it_IT', 'de_DE', 'en_US', 'es_ES', 'ja_JP'])
        >>> matcher.similar('🐫', match_limit = 5)
        [('🐫', "camello ['animal', 'joroba']", 2), ('🐪', "dromedario ['animal', 'joroba']", 2), ('🐝', "abeja ['animal']", 1), ('🕷', "araña ['animal']", 1), ('🐿', "ardilla ['animal']", 1)]

        >>> matcher = EmojiMatcher(languages = ['es_ES',  'it_IT', 'es_MX', 'de_DE', 'en_US', 'ja_JP'])
        >>> matcher.similar('🐫', match_limit = 5)
        [('🐫', "camello ['bactriano', 'camello', 'desierto', 'jorobas']", 4), ('🐪', "dromedario ['camello', 'desierto']", 2), ('🏜', "desierto ['desierto']", 1), ('🐫', "cammello ['animale', 'gobba']", 2), ('🐪', "dromedario ['animale', 'gobba']", 2)]

        >>> matcher = EmojiMatcher(languages = ['es_ES',  'it_IT', 'es_MX', 'de_DE', 'en_US', 'ja_JP'])
        >>> matcher.similar('€', match_limit = 10)
        [('؋', "afghani sign ['sc']", 1), ('֏', "armenian dram sign ['sc']", 1), ('₳', "austral sign ['sc']", 1), ('৻', "bengali ganda mark ['sc']", 1), ('৲', "bengali rupee mark ['sc']", 1), ('৳', "bengali rupee sign ['sc']", 1), ('₵', "cedi sign ['sc']", 1), ('¢', "cent sign ['sc']", 1), ('₡', "colon sign ['sc']", 1), ('₢', "cruzeiro sign ['sc']", 1)]
        '''
        candidate_scores = {}
        expanded_languages = _expand_languages(self._languages)
        for language in expanded_languages:
            emoji_key = (emoji_string, language)
            if emoji_key not in self._emoji_dict:
                continue
            original_labels_for_language = set()
            label_keys = ('categories', 'keywords')
            for label_key in label_keys:
                if label_key in self._emoji_dict[emoji_key]:
                    for label in self._emoji_dict[emoji_key][label_key]:
                        original_labels_for_language.add(label)
            for similar_key in self._emoji_dict:
                if similar_key[1] != language:
                    continue
                similar_string = similar_key[0]
                if 'names' in self._emoji_dict[similar_key]:
                    similar_name = self._emoji_dict[similar_key]['names'][0]
                else:
                    similar_name = self.name(similar_string)
                for label_key in label_keys:
                    if label_key in self._emoji_dict[similar_key]:
                        for label in self._emoji_dict[similar_key][label_key]:
                            if label in original_labels_for_language:
                                scores_key = (
                                    similar_string, language, similar_name)
                                if scores_key in candidate_scores:
                                    candidate_scores[scores_key].add(label)
                                else:
                                    candidate_scores[scores_key] = set([label])
        candidates = []
        for x in sorted(candidate_scores.items(),
                        key = lambda x:(
                            expanded_languages.index(x[0][1]), # language index
                            - len(x[1]), # number of matching labels
                            - len(x[0][0]), # length of emoji string
                            x[0][2], # emoji name
                        ))[:match_limit]:
            candidates.append(
                (x[0][0], x[0][2] + ' ' + repr(sorted(x[1])), len(x[1])))
        return candidates

    def debug_loading_data(self):
        '''To debug whether the data has been loaded correctly'''
        count = 0
        for key, value in sorted(self._emoji_dict.items()):
            print("key=%s value=%s" %(key, sorted(value.items())))
            count += 1
        print('count=%s' %count)

BENCHMARK = True

def main():
    '''
    Used for testing and profiling.

    “python3 itb_emoji.py”

    runs some tests and prints profiling data.
    '''
    if BENCHMARK:
        import cProfile, pstats
        profile = cProfile.Profile()
        profile.enable()

    if False:
        matcher = EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            unicode_data = True, cldr_data = True)
        matcher.debug_loading_data()
    else:
        import doctest
        doctest.testmod()

    if BENCHMARK:
        profile.disable()
        stats = pstats.Stats(profile)
        stats.strip_dirs()
        stats.sort_stats('cumulative')
        stats.print_stats('itb_emoji', 25)
        stats.print_stats('difflib', 25)
        stats.print_stats('enchant', 25)

if __name__ == "__main__":
    main()
