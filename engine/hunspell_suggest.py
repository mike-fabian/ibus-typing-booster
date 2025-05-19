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

from typing import Dict
from typing import Tuple
from typing import List
from typing import Iterable
from typing import Any
import os
import sys
import unicodedata
import logging
import itb_util

IMPORT_REGEX_SUCCESFUL = False
try:
    import regex # type: ignore
    IMPORT_REGEX_SUCCESFUL = True
    # Enable new improved regex engine instead of backwards compatible
    # v0.  regex.match('ß', 'SS', regex.IGNORECASE) matches only with
    # the improved version!  See also: https://pypi.org/project/regex/
    regex.DEFAULT_VERSION = regex.VERSION1 # pylint: disable=no-member
except (ImportError,):
    # Use standard “re” module as a fallback:
    import re

LOGGER = logging.getLogger('ibus-typing-booster')

DEBUG_LEVEL = int(0)

IMPORT_ENCHANT_SUCCESSFUL = False
IMPORT_HUNSPELL_SUCCESSFUL = False
try:
    import enchant # type: ignore
    IMPORT_ENCHANT_SUCCESSFUL = True
except (ImportError,):
    try:
        import hunspell # type: ignore
        IMPORT_HUNSPELL_SUCCESSFUL = True
    except (ImportError,):
        pass

IMPORT_LIBVOIKKO_SUCCESSFUL = False
try:
    import libvoikko # type: ignore
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

# pylint: disable=attribute-defined-outside-init
class Dictionary():
    '''A class to hold a hunspell dictionary'''
    # As soon as it is OK ot require Python >= 3.7, use these nicer type hints:
    #
    # _instances: Dict[Tuple[Type['Dictionary'], str], 'Dictionary'] = {}
    #
    # def __new__(cls: Type['Dictionary'], name: str = 'en_US') -> 'Dictionary':
    #
    # openSUSE Leap 15.4 still has only Python 3.6.
    _instances: Dict[Tuple[Any, str], Any] = {}

    def __new__(cls: Any, name: str = 'en_US') -> Any:
        '''Caching instances of this class and reuse previously created instances'''
        key = (cls, name)
        if key not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[key] = instance
            instance._initialize(name=name)
        return cls._instances[key]

    def _initialize(self, name: str = 'en_US') -> None:
        '''Initialize a Dictionary'''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('name=%s', name)
        self.name = name
        self.language = self.name.split('_')[0]
        self.dic_path = ''
        self.encoding = 'UTF-8'
        self.words: List[str]= []
        self.word_pairs: List[Tuple[str, str]] = []
        self.max_word_len = 0 # maximum length of words in this dictionary
        self.enchant_dict = None
        self.pyhunspell_object = None
        self.voikko: libvoikko.Voikko = None
        if self.name != 'None':
            self.load_dictionary()

    def load_dictionary(self) -> None:
        '''Load a hunspell dictionary and instantiate a
        enchant.Dict() or a hunspell.Hunspell() object.

        '''
        if DEBUG_LEVEL > 0:
            LOGGER.debug('load_dictionary() ...\n')
        (self.dic_path,
         self.encoding,
         self.words) = itb_util.get_hunspell_dictionary_wordlist(self.name)
        if self.words:
            if self.language in itb_util.ACCENT_LANGUAGES:
                self.word_pairs = [
                    (x, itb_util.remove_accents(
                        x, keep=itb_util.ACCENT_LANGUAGES[self.language]))
                    for x in self.words
                ]
            for word in self.words:
                self.max_word_len = max(self.max_word_len, len(word))
            if DEBUG_LEVEL > 1:
                LOGGER.debug(
                    'max_word_len = %s\n', self.max_word_len)
            if self.name.split('_')[0] == 'fi':
                self.enchant_dict = None
                self.pyhunspell_object = None
                self.voikko = None
                if not IMPORT_LIBVOIKKO_SUCCESSFUL:
                    LOGGER.warning(
                        'Language is “fi” but “import libvoikko” failed.')
                    return
                try:
                    self.voikko = libvoikko.Voikko('fi')
                except (libvoikko.VoikkoException,) as error:
                    LOGGER.warning('Init of voikko failed: %s: %s',
                                   error.__class__.__name__, error)
                    self.voikko = None
                return
            if IMPORT_ENCHANT_SUCCESSFUL:
                try:
                    self.enchant_dict = enchant.Dict(self.name)
                except enchant.errors.DictNotFoundError as error:
                    LOGGER.exception(
                        'Error initializing enchant for %s: %s: %s',
                        self.name, error.__class__.__name__, error)
                    self.enchant_dict = None
                except Exception as error: # pylint: disable=broad-except
                    LOGGER.exception(
                        'Unexpected error initializing enchant for %s: %s: %s',
                        self.name, error.__class__.__name__, error)
                    self.enchant_dict = None
            elif IMPORT_HUNSPELL_SUCCESSFUL and self.dic_path:
                aff_path = self.dic_path.replace('.dic', '.aff')
                try:
                    self.pyhunspell_object = (
                        hunspell.HunSpell( # pylint: disable=used-before-assignment
                            self.dic_path, aff_path))
                except hunspell.HunSpellError as error:
                    LOGGER.debug(
                        'Error initializing hunspell for %s: %s: %s',
                        self.name, error.__class__.__name__, error)
                    self.pyhunspell_object = None
                except Exception as error: # pylint: disable=broad-except
                    LOGGER.debug(
                        'Unexpected error initializing hunspell for '
                        '%s: %s: %s',
                        self.name, error.__class__.__name__, error)
                    self.pyhunspell_object = None

    def spellcheck_enchant(self, word: str) -> bool:
        '''
        Spellcheck a word using enchant

        :param word: The word to spellcheck
        :return: True if spelling is correct, False if not or unknown
        '''
        if not self.enchant_dict:
            return False
        # enchant does the right thing for all languages, including
        # Korean, if the input is a Unicode string in NFC.
        return self.enchant_dict.check(unicodedata.normalize('NFC', word))

    def spellcheck_pyhunspell(self, word: str) -> bool:
        '''
        Spellcheck a word using pyhunspell

        :param word: The word to spellcheck
        :return: True if spelling is correct, False if not or unknown
        '''
        if not self.pyhunspell_object:
            return False
        # pyhunspell needs its input passed in dictionary encoding.
        # and also returns in dictionary encoding.
        return self.pyhunspell_object.spell(
            unicodedata.normalize('NFC', word).encode(
                self.encoding, 'replace'))

    def spellcheck_voikko(self, word: str) -> bool:
        '''
        Spellcheck a word using voikko

        :param word: The word to spellcheck
        :return: True if spelling is correct, False if not or unknown
        '''
        if not self.voikko:
            return False
        # voikko works correctly if the input is a Unicode string in NFC.
        return bool(self.voikko.spell(unicodedata.normalize('NFC', word)))

    def spellcheck(self, word: str) -> bool:
        '''
        Spellcheck a word using enchant, pyhunspell, or voikko

        :param word: The word to spellcheck
        :return: True if spelling is correct, False if not or unknown

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
            return bool(self.voikko.spell(word))
        return False

    def has_spellchecking(self) -> bool:
        '''
        Returns wether this dictionary supports spellchecking or not

        :return: True if this dictionary spports spellchecking, False if not

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

    def spellcheck_suggest_enchant(self, word: str) -> List[str]:
        '''
        Return spellchecking suggestions for word using enchant

        :param word: The word to return spellchecking suggestions for
        :return: List of spellchecking suggestions, possibly empty.
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

    def spellcheck_suggest_pyhunspell(self, word: str) -> List[str]:
        '''
        Return spellchecking suggestions for word using pyhunspell

        :param word: The word to return spellchecking suggestions for
        :return: List of spellchecking suggestions, possibly empty.
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

    def spellcheck_suggest_voikko(self, word: str) -> List[str]:
        '''
        Return spellchecking suggestions for word using voikko

        :param word: The word to return spellchecking suggestions for
        :return: List of spellchecking suggestions, possibly empty.
        '''
        if not word or not self.voikko:
            return []
        return [
            unicodedata.normalize(
                itb_util.NORMALIZATION_FORM_INTERNAL, x)
            for x in
            self.voikko.suggest(unicodedata.normalize('NFC', word))
            ]

    def spellcheck_suggest(self, word: str) -> List[str]:
        '''Return spellchecking suggestions for word using enchant,
        pyhunspell or voikko

        :param word: The word to return spellchecking suggestions for
        :return: List of spellchecking suggestions, possibly empty.

        Results can be quite different depending on whether enchant or
        pyhunspell is used and in case of enchant whether hunspell,
        aspell, myspell, or ispell are used. So for the doctests,
        better don’t check the complete list of suggestions returned.

        Examples:

        >>> d = Dictionary('en_US')
        >>> 'Camel' in d.spellcheck_suggest('kamel')
        True

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
# pylint: enable=attribute-defined-outside-init

class Hunspell:
    '''A class to suggest completions or corrections
    using a list of Hunspell dictionaries
    '''
    def __init__(self, dictionary_names: Iterable[str] = ()) -> None:
        global DEBUG_LEVEL # pylint: disable=global-statement
        try:
            DEBUG_LEVEL = int(
                str(os.getenv('IBUS_TYPING_BOOSTER_DEBUG_LEVEL')))
        except (TypeError, ValueError):
            DEBUG_LEVEL = int(0)
        if DEBUG_LEVEL > 1:
            if dictionary_names:
                LOGGER.debug(
                    'Hunspell.__init__(dictionary_names=%s)\n',
                    dictionary_names)
            else:
                LOGGER.debug('Hunspell.__init__(dictionary_names=())\n')
        self._suggest_cache: Dict[str, List[Tuple[str, int]]] = {}
        self._dictionary_names: List[str] = list(dictionary_names)
        self._dictionaries: List[Dictionary] = []
        self.init_dictionaries()

    def init_dictionaries(self) -> None:
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

    def get_dictionary_names(self) -> List[str]:
        '''Returns a copy of the list of dictionary names.

        It is important to return a copy, we do not want to change
        the private member variable directly.'''
        return list(self._dictionary_names[:])

    def set_dictionary_names(self, dictionary_names: List[str]) -> None:
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

    def spellcheck(self, input_phrase: str) -> bool:
        '''
        Checks if a string is likely to be spelled correctly checking
        multiple dictionaries

        :param input_phrase: A string to spellcheck
        :return: True if it is more likely to be spelled correctly,
                 False if it is more likely to be spelled incorrectly.
                 In detail this means:
                 True:
                     - If it is a correctly spelled word in at least one of
                       the dictionaries supporting spellchecking
                     - None of the dictionaries support spellchecking
                     - Contains spaces, spellchecking cannot work
                 else False.

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

    def spellcheck_match_list(self, input_phrase: str) -> List[str]:
        '''
        Returns a list of dictionaries where input_phrase can be found

        :param input_phrase: The word to be spellchecked
        :return: A list of dictionary names which accept input phrase
                 as a valid word.

        Examples:

        >>> h = Hunspell(['en_US', 'None', 'it_IT', 'fr_FR'])
        >>> h.spellcheck_match_list('arrive')
        ['en_US', 'fr_FR']
        >>> h.spellcheck_match_list('arrivé')
        ['fr_FR']
        >>> h.spellcheck_match_list('ragazzo')
        ['it_IT']
        >>> h.spellcheck_match_list(' \t')
        []
        '''
        match_list = []
        if not input_phrase.strip():
            return []
        for dictionary in self._dictionaries:
            if dictionary.spellcheck(input_phrase):
                match_list.append(dictionary.name)
        return match_list

    def spellcheck_single_dictionary(self, words: Iterable[str] = ()) -> List[str]:
        '''
        Checks whether there is at least one dictionary where all words
        in the input list spellcheck as True.

        :param words: A list or tuple of words to spellcheck
        :return: - '' if at least one input word is empty
                 - name of a dictionary where all
                   words in the input list spellcheck as True, if
                   there is no such dictionary, return ''.

        Examples:

        >>> h = Hunspell(['en_US', 'fr_FR'])

        All 3 words spellcheck True in the French dictionary:

        >>> h.spellcheck_single_dictionary(('Je', 'suis', 'arrivé'))
        ['fr_FR']

        Not a correct French sentence but all 3 words spellcheck True
        in the French dictionary:

        >>> h.spellcheck_single_dictionary(('Je', 'suis', 'arrive'))
        ['fr_FR']

        All words spellcheck as True in both the English and the French dictionary:

        >>> h.spellcheck_single_dictionary(('arrive', 'arrive', 'arrive'))
        ['en_US', 'fr_FR']

        Not all 3 words spellcheck True in the French dictionary and
        not all 3 words spellcheck True in the English dictionary either:

        >>> h.spellcheck_single_dictionary(('Je', 'suis', 'arrived'))
        []

        All 3 words spellcheck True in the English dictionary:

        >>> h.spellcheck_single_dictionary(('I', 'have', 'arrived'))
        ['en_US']

        Unfortunately these 3 words spellcheck True in the French dictionary
        ('have' is a form of the verb 'haver', 'I' is the name of the letter):

        >>> h.spellcheck_single_dictionary(('I', 'have', 'arrivé'))
        ['fr_FR']

        If the input contains empty words the result is '':

        >>> h.spellcheck_single_dictionary(('I', 'have', ''))
        []
        '''
        if not words:
            return []
        for word in words:
            if not word:
                return []
        dictionary_names = []
        for dictionary in self._dictionaries:
            spellcheck_total = True
            for word in words:
                spellcheck_total &= dictionary.spellcheck(word)
            if spellcheck_total:
                dictionary_names.append(dictionary.name)
        return sorted(dictionary_names)

    def suggest(self, input_phrase: str) -> List[Tuple[str, int]]:
        # pylint: disable=line-too-long
        '''Return completions or corrections for the input phrase

        :param input_phrase: A string to find completions or corrections for

        Returns a list of tuples of the form (<word>, <score>)
                <score> can have these values:
                    0: This is a completion, i.e. input_phrase matches
                       the beginning of <word> (accent insensitive match)
                   negative number: This is a spell checking correction

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
        [('principianti', 0), ('principiati', -2), ('principiante', -3), ('principiarti', -4), ('principiasti', -5)]

        >>> h = Hunspell(['es_ES'])
        >>> h.suggest('teneis')
        [('tenéis', 0), ('teneos', -2), ('tenes', -3), ('tenis', -4), ('tienes', -5), ('te neis', -6), ('te-neis', -7)]

        >>> h.suggest('tenéis')[0]
        ('tenéis', 0)

        >>> h = Hunspell(['en_US'])
        >>> ('Camelot', 0) in h.suggest('camel') # Should work with aspell and hunspell
        True

        >>> h = Hunspell(['fr_FR'])
        >>> h.suggest('differemmen')
        [('différemment', 0)]

        >>> h = Hunspell(['None'])
        >>> h.suggest('camel')
        []

        >>> h = Hunspell(['None', 'en_US'])
        >>> ('Camelot', 0) in h.suggest('camel') # Should work with aspell and hunspell
        True
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

        suggested_words: Dict[str, int] = {}
        for dictionary in self._dictionaries:
            if dictionary.words:
                if dictionary.word_pairs:
                    input_phrase_no_accents = itb_util.remove_accents(
                        input_phrase,
                        keep=itb_util.ACCENT_LANGUAGES[dictionary.language])
                # If the input phrase is longer than than the maximum
                # word length in a dictionary, don’t try
                # complete it, it just wastes time then.
                if len(input_phrase) <= dictionary.max_word_len:
                    if dictionary.word_pairs:
                        if IMPORT_REGEX_SUCCESFUL:
                            regex_pattern = regex.compile(
                                regex.escape(input_phrase_no_accents),
                                regex.IGNORECASE)
                            suggested_words.update([
                                (x[0], 0)
                                for x in dictionary.word_pairs
                                if regex_pattern.match(x[1])])
                        else:
                            re_pattern = re.compile( # pylint: disable=used-before-assignment
                                re.escape(input_phrase_no_accents),
                                re.IGNORECASE)
                            suggested_words.update([
                                (x[0], 0)
                                for x in dictionary.word_pairs
                                if re_pattern.match(x[1])])
                    else:
                        if IMPORT_REGEX_SUCCESFUL:
                            regex_pattern = regex.compile(
                                regex.escape(input_phrase),
                                regex.IGNORECASE)
                            suggested_words.update([
                                (x, 0)
                                for x in dictionary.words
                                if regex_pattern.match(x)])
                        else:
                            re_pattern = re.compile(
                                re.escape(input_phrase),
                                re.IGNORECASE)
                            suggested_words.update([
                                (x, 0)
                                for x in dictionary.words
                                if re_pattern.match(x)])
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
                    for index, suggestion in enumerate(extra_suggestions):
                        if suggestion not in suggested_words:
                            if (dictionary.word_pairs
                                and
                                itb_util.remove_accents(
                                    suggestion,
                                    keep=itb_util.ACCENT_LANGUAGES[
                                        dictionary.language])
                                == input_phrase_no_accents):
                                suggested_words[suggestion] = 0
                            else:
                                suggested_words[suggestion] = -(index + 1)
        sorted_suggestions = sorted(
            suggested_words.items(),
            key=lambda x: (
                - x[1],    # 0: in dictionary, negative: spellcheck
                len(x[0]), # length of word ascending
                x[0],      # alphabetical
            ))[0:MAX_WORDS]
        self._suggest_cache[input_phrase] = sorted_suggestions
        return sorted_suggestions

BENCHMARK = True

def main() -> None:
    '''
    Used for testing and profiling.

    “python3 hunspell_suggest.py”

    runs some tests and prints profiling data.
    '''
    log_handler = logging.StreamHandler(stream=sys.stderr)
    log_formatter = logging.Formatter(
        '%(asctime)s %(filename)s '
        'line %(lineno)d %(funcName)s %(levelname)s: '
        '%(message)s')
    log_handler.setFormatter(log_formatter)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(log_handler)

    if BENCHMARK:
        import cProfile # pylint: disable=import-outside-toplevel
        import pstats # pylint: disable=import-outside-toplevel
        profile = cProfile.Profile()
        profile.enable()

    import doctest # pylint: disable=import-outside-toplevel
    (failed, _attempted) = doctest.testmod()

    if BENCHMARK:
        profile.disable()
        stats = pstats.Stats(profile)
        stats.strip_dirs()
        stats.sort_stats('cumulative')
        stats.print_stats('hunspell', 25)
        stats.print_stats('enchant', 25)

    LOGGER.info('itb_util.remove_accents() cache info: %s',
                itb_util.remove_accents.cache_info())

    sys.exit(failed)

if __name__ == "__main__":
    main()
