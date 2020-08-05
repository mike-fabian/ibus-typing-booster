# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2012-2013 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012-2016 Mike FABIAN <mfabian@redhat.com>
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

'''A module used by ibus-typing-booster to suggest words by using the
hunspell dictonaries.

'''

import os
import sys
import unicodedata
import logging
import itb_util

LOGGER = logging.getLogger('ibus-typing-booster')

DEBUG_LEVEL = int(0)

IMPORT_ENCHANT_SUCCESSFUL = False
IMPORT_HUNSPELL_SUCCESSFUL = False
try:
    import enchant
    IMPORT_ENCHANT_SUCCESSFUL = True
except (ImportError,):
    try:
        import hunspell
        IMPORT_HUNSPELL_SUCCESSFUL = True
    except (ImportError,):
        pass

IMPORT_LIBVOIKKO_SUCCESSFUL = False
try:
    import libvoikko
    IMPORT_LIBVOIKKO_SUCCESSFUL = True
except (ImportError,):
    pass

# Maximum words that should be returned.
# This should a rather big number in order not
# to throw away useful matches. But making it very huge
# makes the performance worse. For example when setting
# it to 1000, I see a noticable delay when typing the first
# letter of a word until the candidate lookup table pops up.
MAX_WORDS = 100

# List of languages where accent insensitive matching makes sense:
ACCENT_LANGUAGES = {
    'af': '',
    'ast': '',
    'az': '',
    'be': '',
    'bg': '',
    'br': '',
    'bs': '',
    'ca': '',
    'cs': '',
    'csb': '',
    'cv': '',
    'cy': '',
    'da': 'æÆøØåÅ',
    'de': '',
    'dsb': '',
    'el': '',
    'en': '',
    'es': '',
    'eu': '',
    'fi': 'åÅäÄöÖ',
    'fo': '',
    'fr': '',
    'fur': '',
    'fy': '',
    'ga': '',
    'gd': '',
    'gl': '',
    'grc': '',
    'gv': '',
    'haw': '',
    'hr': '',
    'hsb': '',
    'ht': '',
    'hu': '',
    'ia': '',
    'is': '',
    'it': '',
    'kk': '',
    'ku': '',
    'ky': '',
    'lb': '',
    'ln': '',
    'lv': '',
    'mg': '',
    'mi': '',
    'mk': '',
    'mn': '',
    'mos': '',
    'mt': '',
    'nb': 'æÆøØåÅ',
    'nds': '',
    'nl': '',
    'nn': 'æÆøØåÅ',
    'nr': '',
    'nso': '',
    'ny': '',
    'oc': '',
    'pl': '',
    'plt': '',
    'pt': '',
    'qu': '',
    'quh': '',
    'ru': '',
    'sc': '',
    'se': '',
    'sh': '',
    'shs': '',
    'sk': '',
    'sl': '',
    'smj': '',
    'sq': '',
    'sr': '',
    'ss': '',
    'st': '',
    'sv': 'åÅäÄöÖ',
    'tet': '',
    'tk': '',
    'tn': '',
    'ts': '',
    'uk': '',
    'uz': '',
    've': '',
    'vi': '',
    'wa': '',
    'xh': '',
}

class Dictionary:
    '''A class to hold a hunspell dictionary
    '''
    def __init__(self, name='en_US'):
        if DEBUG_LEVEL > 1:
            LOGGER.debug('Dictionary.__init__(name=%s)\n', name)
        self.name = name
        self.language = self.name.split('_')[0]
        self.dic_path = ''
        self.encoding = 'UTF-8'
        self.words = []
        self.word_pairs = []
        self.max_word_len = 0 # maximum length of words in this dictionary
        self.enchant_dict = None
        self.pyhunspell_object = None
        self.voikko = None
        if self.name != 'None':
            self.load_dictionary()

    def load_dictionary(self):
        '''Load a hunspell dictionary and instantiate a
        enchant.Dict() or a hunspell.Hunspell() object.

        '''
        if DEBUG_LEVEL > 0:
            LOGGER.debug('load_dictionary() ...\n')
        (self.dic_path,
         self.encoding,
         self.words) = itb_util.get_hunspell_dictionary_wordlist(self.name)
        if self.words:
            if self.language in ACCENT_LANGUAGES:
                self.word_pairs = [
                    (x, itb_util.remove_accents(
                        x, keep=ACCENT_LANGUAGES[self.language]))
                    for x in self.words
                ]
            for word in self.words:
                if len(word) > self.max_word_len:
                    self.max_word_len = len(word)
            if DEBUG_LEVEL > 1:
                LOGGER.debug(
                    'max_word_len = %s\n', self.max_word_len)
            if self.name.split('_')[0] == 'fi':
                self.enchant_dict = None
                self.pyhunspell_object = None
                if IMPORT_LIBVOIKKO_SUCCESSFUL:
                    self.voikko = libvoikko.Voikko('fi')
                return
            if IMPORT_ENCHANT_SUCCESSFUL:
                try:
                    self.enchant_dict = enchant.Dict(self.name)
                except enchant.errors.DictNotFoundError:
                    LOGGER.exception(
                        'Error initializing enchant for %s', self.name)
                    self.enchant_dict = None
                except Exception:
                    LOGGER.exception(
                        'Unknown error initializing enchant for %s',
                        self.name)
                    self.enchant_dict = None
            elif IMPORT_HUNSPELL_SUCCESSFUL and self.dic_path:
                aff_path = self.dic_path.replace('.dic', '.aff')
                try:
                    self.pyhunspell_object = hunspell.HunSpell(
                        self.dic_path, aff_path)
                except hunspell.HunSpellError:
                    LOGGER.debug(
                        'Error initializing hunspell for %s', self.name)
                    self.pyhunspell_object = None
                except Exception:
                    LOGGER.debug(
                        'Unknown error initializing hunspell for %s',
                        self.name)
                    self.pyhunspell_object = None

    def spellcheck_enchant(self, word):
        '''
        Spellcheck a word using enchant

        :param word: The word to spellcheck
        :type word: String
        :return: True if spelling is correct, False if not or unknown
        :rtype: Boolean
        '''
        if not self.enchant_dict:
            return False
        # enchant does the right thing for all languages, including
        # Korean, if the input is a Unicode string in NFC.
        return self.enchant_dict.check(unicodedata.normalize('NFC', word))

    def spellcheck_pyhunspell(self, word):
        '''
        Spellcheck a word using pyhunspell

        :param word: The word to spellcheck
        :type word: String
        :return: True if spelling is correct, False if not or unknown
        :rtype: Boolean
        '''
        if not self.pyhunspell_object:
            return False
        # pyhunspell needs its input passed in dictionary encoding.
        # and also returns in dictionary encoding.
        return self.pyhunspell_object.spell(
            unicodedata.normalize('NFC', word).encode(
                self.encoding, 'replace'))

    def spellcheck_voikko(self, word):
        '''
        Spellcheck a word using voikko

        :param word: The word to spellcheck
        :type word: String
        :return: True if spelling is correct, False if not or unknown
        :rtype: Boolean
        '''
        if not self.voikko:
            return False
        # voikko works correctly if the input is a Unicode string in NFC.
        return self.voikko.spell(unicodedata.normalize('NFC', word))

    def spellcheck(self, word):
        '''
        Spellcheck a word using enchant, pyhunspell, or voikko

        :param word: The word to spellcheck
        :type word: String
        :return: True if spelling is correct, False if not or unknown
        :rtype: Boolean

        >>> d = Dictionary('en_US')
        >>> d.spellcheck('winter')
        True

        >>> d.spellcheck('winxer')
        False

        >>> d = Dictionary('None')
        >>> d.spellcheck('winter')
        False

        >>> d.spellcheck('winxer')
        False
        '''
        if self.enchant_dict:
            return self.spellcheck_enchant(word)
        if self.pyhunspell_object:
            return self.spellcheck_pyhunspell(word)
        if self.voikko:
            return self.voikko.spell(word)
        return False

    def has_spellchecking(self):
        '''
        Returns wether this dictionary supports spellchecking or not

        :return: True if this dictionary spports spellchecking, False if not
        :rtype: Boolean

        Examples:

        >>> d = Dictionary('en_US')
        >>> d.has_spellchecking()
        True

        >>> d = Dictionary('zh_CN')
        >>> d.has_spellchecking()
        False

        >>> d = Dictionary('None')
        >>> d.has_spellchecking()
        False
        '''
        if self.enchant_dict or self.pyhunspell_object or self.voikko:
            return True
        return False

    def spellcheck_suggest_enchant(self, word):
        '''
        Return spellchecking suggestions for word using enchant

        :param word: The word to return spellchecking suggestions for
        :type word: String
        :return: List of spellchecking suggestions, possibly empty.
        :rtype: List of strings
        '''
        if not word or not self.enchant_dict:
            return []
        # enchant does the right thing for all languages, including
        # Korean, if the input is NFC. It takes Unicode strings and
        # returns Unicode strings, no encoding and decoding is
        # necessary, neither for Python2 nor for Python3.
        return [
            unicodedata.normalize(
                itb_util.NORMALIZATION_FORM_INTERNAL, x)
            for x in
            self.enchant_dict.suggest(unicodedata.normalize('NFC', word))
            ]

    def spellcheck_suggest_pyhunspell(self, word):
        '''
        Return spellchecking suggestions for word using pyhunspell

        :param word: The word to return spellchecking suggestions for
        :type word: String
        :return: List of spellchecking suggestions, possibly empty.
        :rtype: List of strings
        '''
        if not word or not self.pyhunspell_object:
            return []
        # pyhunspell needs its input passed in dictionary encoding.
        return [
            unicodedata.normalize(
                itb_util.NORMALIZATION_FORM_INTERNAL, x)
            for x in
            self.pyhunspell_object.suggest(
                unicodedata.normalize('NFC', word).encode(
                    self.encoding, 'replace'))
            ]

    def spellcheck_suggest_voikko(self, word):
        '''
        Return spellchecking suggestions for word using voikko

        :param word: The word to return spellchecking suggestions for
        :type word: String
        :return: List of spellchecking suggestions, possibly empty.
        :rtype: List of strings
        '''
        if not word:
            return []
        return [
            unicodedata.normalize(
                itb_util.NORMALIZATION_FORM_INTERNAL, x)
            for x in
            self.voikko.suggest(unicodedata.normalize('NFC', word))
            ]

    def spellcheck_suggest(self, word):
        '''
        Return spellchecking suggestions for word using enchant, pyhunspell or voikko

        :param word: The word to return spellchecking suggestions for
        :type word: String
        :return: List of spellchecking suggestions, possibly empty.
        :rtype: List of strings

        Examples:

        >>> d = Dictionary('en_US')
        >>> d.spellcheck_suggest('kamel')
        ['camel', 'Camel']

        >>> d.spellcheck_suggest('')
        []

        >>> d = Dictionary('None')
        >>> d.spellcheck_suggest('kamel')
        []
        '''
        if self.enchant_dict:
            return self.spellcheck_suggest_enchant(word)
        if self.pyhunspell_object:
            return self.spellcheck_suggest_pyhunspell(word)
        if self.voikko:
            return self.spellcheck_suggest_voikko(word)
        return []

class Hunspell:
    '''A class to suggest completions or corrections
    using a list of Hunspell dictionaries
    '''
    def __init__(self, dictionary_names=()):
        global DEBUG_LEVEL
        try:
            DEBUG_LEVEL = int(os.getenv('IBUS_TYPING_BOOSTER_DEBUG_LEVEL'))
        except (TypeError, ValueError):
            DEBUG_LEVEL = int(0)
        if DEBUG_LEVEL > 1:
            if dictionary_names:
                LOGGER.debug(
                    'Hunspell.__init__(dictionary_names=%s)\n',
                    dictionary_names)
            else:
                LOGGER.debug('Hunspell.__init__(dictionary_names=())\n')
        self._suggest_cache = {}
        self._dictionary_names = dictionary_names
        self._dictionaries = []
        self.init_dictionaries()

    def init_dictionaries(self):
        '''Initialize the hunspell dictionaries
        '''
        if DEBUG_LEVEL > 1:
            if self._dictionary_names:
                LOGGER.debug(
                    'Hunspell.init_dictionaries() dictionary_names=%s\n',
                    self._dictionary_names)
            else:
                LOGGER.debug(
                    'Hunspell.init_dictionaries() dictionary_names=()\n')
        self._suggest_cache = {}
        self._dictionaries = []
        for dictionary_name in self._dictionary_names:
            self._dictionaries.append(Dictionary(name=dictionary_name))

    def get_dictionary_names(self):
        '''Returns a copy of the list of dictionary names.

        It is important to return a copy, we do not want to change
        the private member variable directly.'''
        return self._dictionary_names[:]

    def set_dictionary_names(self, dictionary_names):
        '''Sets the list of dictionary names.

        If the new list of dictionary names differs from the existing
        one, re-initialize the dictionaries.
        '''
        if dictionary_names != self._dictionary_names:
            if set(dictionary_names) != set(self._dictionary_names):
                # Some dictionaries are really different, reinitialize:
                self._dictionary_names = dictionary_names
                self.init_dictionaries()
            else:
                # Only the order of dictionaries has changed.
                # Reinitializing wastes time, just reorder the
                # dictionaries:
                self._dictionary_names = dictionary_names
                dictionaries_new = []
                for name in dictionary_names:
                    for dictionary in self._dictionaries:
                        if dictionary.name == name:
                            dictionaries_new.append(dictionary)
                self._dictionaries = dictionaries_new
        if DEBUG_LEVEL > 1:
            LOGGER.debug('set_dictionary_names(%s):\n', dictionary_names)
            for dictionary in self._dictionaries:
                LOGGER.debug('%s\n', dictionary.name)

    def spellcheck(self, input_phrase):
        '''
        Checks if a string is likely to be spelled correctly checking
        multiple dictionaries

        :param input_phrase: A string to spellcheck
        :type input_phrase: String
        :return: True if it is more likely to be spelled correctly,
                 False if it is more likely to be spelled incorrectly.
                 In detail this means:
                 True:
                     - If it is a correctly spelled word in at least one of
                       the dictionaries supporting spellchecking
                     - None of the dictionaries support spellchecking
                     - Contains spaces, spellchecking cannot work
                 else False.
        :rtype: Boolean

        Examples:

        >>> h = Hunspell(['en_US', 'de_DE', 'ja_JP'])
        >>> h.spellcheck('Hello')
        True

        >>> h.spellcheck('Grüße')
        True

        >>> h.spellcheck('Gruße')
        False

        >>> h = Hunspell(['en_US', 'ja_JP'])
        >>> h.spellcheck('Grüße')
        False

        >>> h = Hunspell(['ja_JP'])
        >>> h.spellcheck('Grüße')
        True

        >>> h = Hunspell(['en_US', 'None'])
        >>> h.spellcheck('Grüße')
        False

        >>> h = Hunspell(['None'])
        >>> h.spellcheck('Grüße')
        True
        '''
        if ' ' in input_phrase:
            return True
        spellchecking_dictionaries_available = False
        spellcheck_total = False
        for dictionary in self._dictionaries:
            if dictionary.has_spellchecking():
                spellchecking_dictionaries_available = True
                spellcheck_total |= dictionary.spellcheck(input_phrase)
        if not spellcheck_total and spellchecking_dictionaries_available:
            return False
        return True

    def suggest(self, input_phrase):
        # pylint: disable=line-too-long
        '''Return completions or corrections for the input phrase

        :param input_phrase: A string to find completions or corrections for
        :type input_phrase: String
        :rtype: A list of tuples of the form (<word>, <score>)
                <score> can have these values:
                    0: This is a completion, i.e. input_phrase matches
                       the beginning of <word> (accent insensitive match)
                   -1: This is a spell checking correction from hunspell
                       (i.e. either from enchant or pyhunspell)

        Examples:

        (Attention, the return values are in internal
        normalization form ('NFD'))

        >>> h = Hunspell(['de_DE', 'cs_CZ'])
        >>> h.suggest('Geschwindigkeitsubertre')[0]
        ('Geschwindigkeitsübertretungsverfahren', 0)

        >>> h.suggest('Geschwindigkeitsübertretungsverfahren')[0]
        ('Geschwindigkeitsübertretungsverfahren', 0)

        >>> h.suggest('Glühwürmchen')[0]
        ('Glühwürmchen', 0)

        >>> h.suggest('Alpengluhen')[0]
        ('Alpenglühen', 0)

        >>> h.suggest('filosofictejs')[0]
        ('filosofičtější', 0)

        >>> h.suggest('filosofičtější')[0]
        ('filosofičtější', 0)

        >>> h.suggest('filosofičtějš')[0]
        ('filosofičtější', 0)

        >>> h = Hunspell(['it_IT'])
        >>> h.suggest('principianti')
        [('principianti', 0), ('principiati', -1), ('principiante', -1), ('principiarti', -1), ('principiasti', -1)]

        >>> h = Hunspell(['es_ES'])
        >>> h.suggest('teneis')
        [('tenéis', 0), ('tenes', -1), ('tenis', -1), ('teneos', -1), ('tienes', -1), ('te neis', -1), ('te-neis', -1)]

        >>> h.suggest('tenéis')[0]
        ('tenéis', 0)

        >>> h = Hunspell(['en_US'])
        >>> h.suggest('camel')
        [('camel', 0), ('camellia', 0), ('camelhair', 0), ('came', -1), ('Camel', -1), ('cameo', -1), ('came l', -1), ('camels', -1)]

        >>> h = Hunspell(['fr_FR'])
        >>> h.suggest('differemmen')
        [('différemment', 0)]

        >>> h = Hunspell(['None'])
        >>> h.suggest('camel')
        []

        >>> h = Hunspell(['None', 'en_US'])
        >>> h.suggest('camel')
        [('camel', 0), ('camellia', 0), ('camelhair', 0), ('came', -1), ('Camel', -1), ('cameo', -1), ('came l', -1), ('camels', -1)]

        '''
        # pylint: enable=line-too-long
        if input_phrase in self._suggest_cache:
            return self._suggest_cache[input_phrase]
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                "Hunspell.suggest() input_phrase=%(ip)s\n",
                {'ip': input_phrase.encode('UTF-8')})
        # http://pwet.fr/man/linux/fichiers_speciaux/hunspell says:
        #
        # > A dictionary file (*.dic) contains a list of words, one per
        # > line. The first line of the dictionaries (except personal
        # > dictionaries) contains the word count. Each word may
        # > optionally be followed by a slash ("/") and one or more
        # > flags, which represents affixes or special attributes.
        #
        # I.e. if '/' is already contained in the input, it cannot
        # match a word in the dictionary and we return an empty list
        # immediately:
        if '/' in input_phrase:
            self._suggest_cache[input_phrase] = []
            return []
        # make sure input_phrase is in the internal normalization form (NFD):
        input_phrase = unicodedata.normalize(
            itb_util.NORMALIZATION_FORM_INTERNAL, input_phrase)
        # But enchant and pyhunspell want NFC as input, make a copy in NFC:
        input_phrase_nfc = unicodedata.normalize('NFC', input_phrase)

        suggested_words = {}
        for dictionary in self._dictionaries:
            if dictionary.words:
                if dictionary.word_pairs:
                    input_phrase_no_accents = itb_util.remove_accents(
                        input_phrase,
                        keep=ACCENT_LANGUAGES[dictionary.language])
                # If the input phrase is longer than than the maximum
                # word length in a dictionary, don’t try
                # complete it, it just wastes time then.
                if len(input_phrase) <= dictionary.max_word_len:
                    if dictionary.word_pairs:
                        suggested_words.update([
                            (x[0], 0)
                            for x in dictionary.word_pairs
                            if x[1].startswith(input_phrase_no_accents)])
                    else:
                        suggested_words.update([
                            (x, 0)
                            for x in dictionary.words
                            if x.startswith(input_phrase)])
                if len(input_phrase) >= 4:
                    if dictionary.spellcheck(input_phrase):
                        # This is a valid word in this dictionary.
                        # It might have been missed by the
                        # matching above because the dictionary
                        # might not contain all possible word
                        # forms (The prefix and suffix information
                        # has been ignored). But the spell checker
                        # knows about this, if the spell checker
                        # thinks it is a correct word, it must be
                        # counted as a match of course:
                        suggested_words[input_phrase] = 0
                    extra_suggestions = [
                        unicodedata.normalize(
                            itb_util.NORMALIZATION_FORM_INTERNAL, x)
                        for x in
                        dictionary.spellcheck_suggest(input_phrase)
                    ]
                    for suggestion in extra_suggestions:
                        if suggestion not in suggested_words:
                            if (dictionary.word_pairs
                                and
                                itb_util.remove_accents(
                                    suggestion,
                                    keep=ACCENT_LANGUAGES[dictionary.language])
                                == input_phrase_no_accents):
                                suggested_words[suggestion] = 0
                            else:
                                suggested_words[suggestion] = -1
        sorted_suggestions = sorted(
            suggested_words.items(),
            key=lambda x: (
                - x[1],    # 0: in dictionary, -1: hunspell
                len(x[0]), # length of word ascending
                x[0],      # alphabetical
            ))[0:MAX_WORDS]
        self._suggest_cache[input_phrase] = sorted_suggestions
        return sorted_suggestions

BENCHMARK = True

def main():
    '''
    Used for testing and profiling.

    “python3 hunspell_suggest.py”

    runs some tests and prints profiling data.
    '''
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)

    if BENCHMARK:
        import cProfile
        import pstats
        profile = cProfile.Profile()
        profile.enable()

    import doctest
    (failed, dummy_attempted) = doctest.testmod()

    if BENCHMARK:
        profile.disable()
        stats = pstats.Stats(profile)
        stats.strip_dirs()
        stats.sort_stats('cumulative')
        stats.print_stats('hunspell', 25)
        stats.print_stats('enchant', 25)

    if failed:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
