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
import itb_util

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

# Maximum words that should be returned.
# This should a rather big number in order not
# to throw away useful matches. But making it very huge
# makes the performance worse. For example when setting
# it to 1000, I see a noticable delay when typing the first
# letter of a word until the candidate lookup table pops up.
MAX_WORDS = 100

class Dictionary:
    '''A class to hold a hunspell dictionary
    '''
    def __init__(self, name='en_US'):
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "Dictionary.__init__(name=%s)\n" %name)
        self.name = name
        self.dic_path = ''
        self.encoding = 'UTF-8'
        self.words = []
        self.word_pairs = []
        self.max_word_len = 0 # maximum length of words in this dictionary
        self.enchant_dict = None
        self.pyhunspell_object = None
        self.load_dictionary()

    def load_dictionary(self):
        '''Load a hunspell dictionary and instantiate a
        enchant.Dict() or a hunspell.Hunspell() object.

        '''
        if DEBUG_LEVEL > 0:
            sys.stderr.write("load_dictionary() ...\n")
        (self.dic_path,
         self.encoding,
         self.words) = itb_util.get_hunspell_dictionary_wordlist(self.name)
        if self.words:
            # List of languages where accent insensitive matching makes sense:
            accent_languages = (
                'af', 'ast', 'az', 'be', 'bg', 'br', 'bs', 'ca', 'cs', 'csb',
                'cv', 'cy', 'da', 'de', 'dsb', 'el', 'en', 'es', 'eu', 'fo',
                'fr', 'fur', 'fy', 'ga', 'gd', 'gl', 'grc', 'gv', 'haw', 'hr',
                'hsb', 'ht', 'hu', 'ia', 'is', 'it', 'kk', 'ku', 'ky', 'lb',
                'ln', 'lv', 'mg', 'mi', 'mk', 'mn', 'mos', 'mt', 'nb', 'nds',
                'nl', 'nn', 'nr', 'nso', 'ny', 'oc', 'pl', 'plt', 'pt', 'qu',
                'quh', 'ru', 'sc', 'se', 'sh', 'shs', 'sk', 'sl', 'smj', 'sq',
                'sr', 'ss', 'st', 'sv', 'tet', 'tk', 'tn', 'ts', 'uk', 'uz',
                've', 'vi', 'wa', 'xh',
            )
            if self.name.split('_')[0] in accent_languages:
                self.word_pairs = [
                    (x, itb_util.remove_accents(x))
                    for x in self.words
                ]
            for word in self.words:
                if len(word) > self.max_word_len:
                    self.max_word_len = len(word)
            if DEBUG_LEVEL > 1:
                sys.stderr.write(
                    'load_dictionary() max_word_len = %s\n'
                    % self.max_word_len)
            if IMPORT_ENCHANT_SUCCESSFUL:
                try:
                    self.enchant_dict = enchant.Dict(self.name)
                except enchant.errors.DictNotFoundError as error:
                    sys.stderr.write(
                        'Error initializing enchant for %s: %s\n'
                        % (self.name, error))
                    self.enchant_dict = None
                except:
                    sys.stderr.write(
                        'Unknown error initializing enchant for %s\n'
                        % self.name)
                    self.enchant_dict = None
            elif IMPORT_HUNSPELL_SUCCESSFUL and self.dic_path:
                aff_path = self.dic_path.replace('.dic', '.aff')
                try:
                    self.pyhunspell_object = hunspell.HunSpell(
                        self.dic_path, aff_path)
                except hunspell.HunSpellError as error:
                    sys.stderr.write(
                        'Error initializing hunspel for %s: %s\n'
                        % (self.name, error))
                    self.pyhunspell_object = None
                except:
                    sys.stderr.write(
                        'Unknown error initializing hunspell for %s\n'
                        % self.name)
                    self.pyhunspell_object = None

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
                sys.stderr.write(
                    'Hunspell.__init__(dictionary_names=%s)\n'
                    %dictionary_names)
            else:
                sys.stderr.write(
                    'Hunspell.__init__(dictionary_names=())\n')
        self._suggest_cache = {}
        self._dictionary_names = dictionary_names
        self._dictionaries = []
        self.init_dictionaries()

    def init_dictionaries(self):
        '''Initialize the hunspell dictionaries
        '''
        if DEBUG_LEVEL > 1:
            if self._dictionary_names:
                sys.stderr.write(
                    'Hunspell.init_dictionaries() dictionary_names=%s\n'
                    %self._dictionary_names)
            else:
                sys.stderr.write(
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
            sys.stderr.write('set_dictionary_names(%s):\n' % dictionary_names)
            for dictionary in self._dictionaries:
                sys.stderr.write('%s\n' % dictionary.name)

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

        >>> h.suggest('filosofictejsi')
        [('filosofičtější', 0), ('filosofičtěji', -1)]

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
        '''
        # pylint: enable=line-too-long
        if input_phrase in self._suggest_cache:
            return self._suggest_cache[input_phrase]
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "Hunspell.suggest() input_phrase=%(ip)s\n"
                %{'ip': input_phrase.encode('UTF-8')})
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
        input_phrase_no_accents = unicodedata.normalize(
            itb_util.NORMALIZATION_FORM_INTERNAL,
            itb_util.remove_accents(input_phrase))
        # But enchant and pyhunspell want NFC as input, make a copy in NFC:
        input_phrase_nfc = unicodedata.normalize('NFC', input_phrase)

        suggested_words = {}
        for dictionary in self._dictionaries:
            if dictionary.words:
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
                if dictionary.enchant_dict:
                    if len(input_phrase) >= 4:
                        # Always pass NFC to enchant and convert the
                        # result back to the internal normalization
                        # form (NFD) (enchant does the right thing for
                        # Korean if the input is NFC).  enchant takes
                        # unicode strings and returns unicode strings,
                        # no encoding and decoding to and from the
                        # hunspell dictionary encoding is necessary
                        # (neither for Python2 nor Python3).
                        # (pyhunspell needs to get its input passed
                        # in dictionary encoding and also returns it
                        # in dictionary encoding).
                        if dictionary.enchant_dict.check(input_phrase_nfc):
                            # This is a valid word in this dictionary.
                            # It might have been missed by the matching
                            # above because the dictionary might not
                            # contain all possible word forms (The
                            # prefix and suffix information has been
                            # ignored). But hunspell knows about this,
                            # if hunspell thinks it is a correct word,
                            # it must be counted as a match of course:
                            suggested_words[input_phrase] = 0
                        extra_suggestions = [
                            unicodedata.normalize(
                                itb_util.NORMALIZATION_FORM_INTERNAL, x)
                            for x in
                            dictionary.enchant_dict.suggest(input_phrase_nfc)
                        ]
                        suggested_words.update([
                            (suggestion, -1)
                            for suggestion in extra_suggestions
                            if suggestion not in suggested_words])
                elif dictionary.pyhunspell_object:
                    if len(input_phrase) >= 4:
                        # Always pass NFC to pyhunspell and convert
                        # the result back to the internal
                        # normalization form (NFD) (hunspell does the
                        # right thing for Korean if the input is NFC).
                        if dictionary.pyhunspell_object.spell(
                                input_phrase_nfc.encode(
                                    dictionary.encoding, 'replace')):
                            # This is a valid word in this dictionary.
                            # It might have been missed by the matching
                            # above because the dictionary might not
                            # contain all possible word forms (The
                            # prefix and suffix information has been
                            # ignored). But hunspell knows about this,
                            # if hunspell thinks it is a correct word,
                            # it must be counted as a match of course:
                            suggested_words[input_phrase] = 0
                        extra_suggestions = [
                            unicodedata.normalize(
                                itb_util.NORMALIZATION_FORM_INTERNAL, x)
                            for x in
                            dictionary.pyhunspell_object.suggest(
                                input_phrase_nfc.encode(
                                    dictionary.encoding, 'replace'))
                        ]
                        suggested_words.update([
                            (suggestion, -1)
                            for suggestion in extra_suggestions
                            if suggestion not in suggested_words])
            else:
                if (dictionary.name[:2]
                        not in ('ja', 'ja_JP',
                                'zh', 'zh_CN', 'zh_TW', 'zh_MO', 'zh_SG')):
                    # For some languages, hunspell dictionaries don’t
                    # exist because hunspell makes no sense for these
                    # languages.  In these cases, just ignore that the
                    # hunspell dictionary is missing.  With the
                    # appropriate input method added, emoji can be
                    # matched nevertheless.
                    suggested_words.update([
                        ('☹ %(name)s dictionary not found. '
                         %{'name': dictionary.name}
                         + 'Please install hunspell dictionary!',
                         0)])
        for word in suggested_words:
            if (suggested_words[word] == -1
                    and
                    itb_util.remove_accents(word)
                    == itb_util.remove_accents(input_phrase)):
                # This spell checking correction is actually even
                # an accent insensitive match, adjust accordingly:
                suggested_words[word] = 0
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
