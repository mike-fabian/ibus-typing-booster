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
import re
import traceback
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

NORMALIZATION_FORM_INTERNAL = 'NFD'

class Dictionary:
    '''A class to hold a hunspell dictionary
    '''
    def __init__(self, name = 'en_US'):
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "Dictionary.__init__(name=%s)\n" %name)
        self.loc = '/usr/share/myspell'
        self.name = name
        self.encoding = 'UTF-8'
        self.words = []
        self.word_pairs = []
        self.enchant_dict = None
        self.pyhunspell_object = None
        self.load_dictionary()

    def load_dictionary(self):
        '''Load a hunspell dictionary and instantiate a
        enchant.Dict() or a hunspell.Hunspell() object.

        '''
        if DEBUG_LEVEL > 0:
            sys.stderr.write("load_dictionary() ...\n")
        dic_path = os.path.join(self.loc, self.name+'.dic')
        aff_path = os.path.join(self.loc, self.name+'.aff')
        if not os.path.isfile(dic_path) or not os.path.isfile(aff_path):
            sys.stderr.write(
                "load_dictionary %(n)s: %(d)s %(a)s file missing.\n"
                %{'n': self.name, 'd': dic_path, 'a': aff_path})
            return
        aff_buffer = None
        dic_buffer = None
        try:
            aff_buffer = open(
                aff_path,
                mode='r',
                encoding='ISO-8859-1',
                errors='ignore').read().replace('\r\n', '\n')
        except (FileNotFoundError, PermissionError):
            traceback.print_exc()
        except:
            sys.stderr.write(
                'Unexpected error loading .aff File: %s\n' %aff_path)
            traceback.print_exc()
        if aff_buffer:
            encoding_pattern = re.compile(
                r'^[\s]*SET[\s]+(?P<encoding>[-a-zA-Z0-9_]+)[\s]*$',
                re.MULTILINE)
            match = encoding_pattern.search(aff_buffer)
            if match:
                self.encoding = match.group('encoding')
                if DEBUG_LEVEL > 0:
                    sys.stderr.write(
                        "load_dictionary(): encoding=%(enc)s found in %(aff)s"
                        %{'enc': self.encoding, 'aff': aff_path})
        try:
            dic_buffer = open(
                dic_path, encoding=self.encoding).readlines()
        except (UnicodeDecodeError, FileNotFoundError, PermissionError):
            if DEBUG_LEVEL > 0:
                sys.stderr.write(
                    "load_dictionary(): "
                    + "loading %(dic)s as %(enc)s encoding failed, "
                    %{'dic': dic_path, 'enc': self.encoding}
                    + "fall back to ISO-8859-1.\n")
            self.encoding = 'ISO-8859-1'
            try:
                dic_buffer = open(
                    dic_path,
                    encoding=self.encoding).readlines()
            except (UnicodeDecodeError, FileNotFoundError, PermissionError):
                sys.stderr.write(
                    "load_dictionary(): "
                    + "loading %(dic)s as %(enc)s encoding failed, "
                    %{'dic': dic_path, 'enc': self.encoding}
                    + "giving up.\n")
                dic_buffer = None
                traceback.print_exc()
                return
            except:
                sys.stderr.write(
                    'Unexpected error loading .dic File: %s\n' %dic_path)
                traceback.print_exc()
                return
        except:
            sys.stderr.write(
                'Unexpected error loading .dic File: %s\n' %dic_path)
            traceback.print_exc()
            return
        if dic_buffer:
            if DEBUG_LEVEL > 0:
                sys.stderr.write(
                    "load_dictionary(): "
                    + "Successfully loaded %(dic)s using %(enc)s encoding.\n"
                    %{'dic': dic_path, 'enc': self.encoding})
            # http://pwet.fr/man/linux/fichiers_speciaux/hunspell says:
            #
            # > A dictionary file (*.dic) contains a list of words, one per
            # > line. The first line of the dictionaries (except personal
            # > dictionaries) contains the word count. Each word may
            # > optionally be followed by a slash ("/") and one or more
            # > flags, which represents affixes or special attributes.
            #
            # Therefore, remove '/' and the following flags from each
            # line to make the buffer a bit smaller and the regular
            # expressions we use later to match words in the
            # dictionary slightly simpler and maybe a tiny bit faster:
            self.words = [
                unicodedata.normalize(
                    NORMALIZATION_FORM_INTERNAL,
                    re.sub(r'/.*', '', x.replace('\n', '')))
                for x in dic_buffer
            ]
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
            if IMPORT_ENCHANT_SUCCESSFUL:
                self.enchant_dict = enchant.Dict(self.name)
            elif IMPORT_HUNSPELL_SUCCESSFUL:
                self.pyhunspell_object = hunspell.HunSpell(dic_path, aff_path)

class Hunspell:
    '''A class to suggest completions or corrections
    using a list of Hunspell dictionaries
    '''
    def __init__(self, dictionary_names = ('en_US',)):
        global DEBUG_LEVEL
        try:
            DEBUG_LEVEL = int(os.getenv('IBUS_TYPING_BOOSTER_DEBUG_LEVEL'))
        except (TypeError, ValueError):
            DEBUG_LEVEL = int(0)
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "Hunspell.__init__(dictionary_names=%s)\n"
                %dictionary_names)
        self._suggest_cache = {}
        self._dictionary_names = dictionary_names
        self._dictionaries = []
        self.init_dictionaries()

    def init_dictionaries(self):
        '''Initialize the hunspell dictionaries
        '''
        if DEBUG_LEVEL > 1:
            sys.stderr.write(
                "Hunspell.init_dictionaries() dictionary_names=%s\n"
                %self._dictionary_names)
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
        one, re-initilize the dictionaries.
        '''
        if dictionary_names != self._dictionary_names:
            self._dictionary_names = dictionary_names
            self.init_dictionaries()

    def suggest(self, input_phrase):
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

        (Attention, the return values are in NORMALIZATION_FORM_INTERNAL ('NFD'))

        >>> h = Hunspell(['de_DE', 'cs_CZ'])
        >>> h.suggest('Geschwindigkeitsubertre')
        [('Geschwindigkeitsübertretungsverfahren', 0), ('Schreitgeschwindigkeit', -1), ('Geschwindigkeitsabhängig', -1), ('Geschwindigkeitsoptimiert', -1), ('Geschwindigkeitsabhängige', -1)]

        >>> h.suggest('filosofictejsi')
        [('filosofičtější', 0), ('filosofičtěji', -1)]

        >>> h = Hunspell(['it_IT'])
        >>> h.suggest('principianti')
        [('principianti', 0), ('principiati', -1), ('principiante', -1), ('principiarti', -1), ('principiasti', -1)]

        >>> h = Hunspell(['es_ES'])
        >>> h.suggest('teneis')
        [('tenéis', 0), ('tenes', -1), ('tenis', -1), ('teneos', -1), ('tienes', -1), ('te neis', -1), ('te-neis', -1)]
        '''
        if input_phrase in self._suggest_cache:
            return self._suggest_cache[input_phrase]
        # If the input phrase is very long, don’t try looking
        # something up in the hunspell dictionaries. The regexp match
        # gets very slow if the input phrase is very long. And there
        # are no very long words in the hunspell dictionaries anyway,
        # the longest word in the German hunspell dictionary currently
        # seems to be “Geschwindigkeitsübertretungsverfahren” trying
        # to match words longer than that just wastes time.
        if len(input_phrase) > 40:
            self._suggest_cache[input_phrase] = []
            return []
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
            NORMALIZATION_FORM_INTERNAL, input_phrase)
        # But enchant and pyhunspell want NFC as input, make a copy in NFC:
        input_phrase_nfc = unicodedata.normalize('NFC', input_phrase)
        # '/' is already removed from the buffer, we do not need to
        # take care of it in the regexp.
        patt_start = re.compile(r'^' + re.escape(input_phrase))

        suggested_words = {}
        for dictionary in self._dictionaries:
            if dictionary.words:
                if dictionary.word_pairs:
                    suggested_words.update([
                        (x[0], 0)
                        for x in dictionary.word_pairs
                        if patt_start.match(x[1])])
                else:
                    suggested_words.update([
                        (x, 0)
                        for x in dictionary.words
                        if patt_start.match(x)])
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
                                NORMALIZATION_FORM_INTERNAL, x)
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
                        if dictionary.pyhunspell_object.spell(input_phrase_nfc):
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
                                NORMALIZATION_FORM_INTERNAL, x.decode(
                                    dictionary.encoding))
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
                    dic_path = os.path.join(dictionary.loc, dictionary.name+'.dic')
                    suggested_words.update([
                        ('☹ %(dic_path)s not found. ' %{'dic_path': dic_path}
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
        sorted_suggestions =  sorted(
            suggested_words.items(),
            key = lambda x: (
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
        import cProfile, pstats
        profile = cProfile.Profile()
        profile.enable()

    import doctest
    doctest.testmod()

    if BENCHMARK:
        profile.disable()
        stats = pstats.Stats(profile)
        stats.strip_dirs()
        stats.sort_stats('cumulative')
        stats.print_stats('hunspell', 25)
        stats.print_stats('enchant', 25)

if __name__ == "__main__":
    main()
