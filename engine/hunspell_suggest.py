# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 2012-2013 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012-2016 Mike FABIAN <mfabian@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#  This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#  You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

'''A module used by ibus-typing-booster to suggest words by using the
hunspell dictonaries.

'''

import os
import sys
import unicodedata
import re
import traceback

DEBUG_LEVEL = int(0)

IMPORT_ENCHANT_SUCCESSFUL = False
IMPORT_HUNSPELL_SUCCESSFUL = False
try:
    import enchant
    IMPORT_ENCHANT_SUCCESSFUL = True
except (ImportError,):
    try:
        import hunspell # only available for Python2
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
        self.buffer = None
        self.enchant_dict = None
        self.pyhunspell_object = None
        self.load_dictionary()

    def load_dictionary(self):
        '''Load a hunspell dictionary into a buffer and instanticate a
        enchant.Dict() or a hunspell.Hunspell() object.

        '''
        print("load_dictionary() ...")
        dic_path = os.path.join(self.loc, self.name+'.dic')
        aff_path = os.path.join(self.loc, self.name+'.aff')
        if not os.path.isfile(dic_path) or not os.path.isfile(aff_path):
            print("load_dictionary %(n)s: %(d)s %(a)s file missing."
                  %{'n': self.name, 'd': dic_path, 'a': aff_path})
            return
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
                print("load_dictionary(): encoding=%(enc)s found in %(aff)s" %{
                    'enc': self.encoding, 'aff': aff_path})
        try:
            self.buffer = open(
                dic_path, encoding=self.encoding).read().replace('\r\n', '\n')
        except (UnicodeDecodeError, FileNotFoundError, PermissionError):
            print("load_dictionary(): "
                  + "loading %(dic)s as %(enc)s encoding failed, "
                  %{'dic': dic_path, 'enc': self.encoding}
                  + "fall back to ISO-8859-1.")
            self.encoding = 'ISO-8859-1'
            try:
                self.buffer = open(
                    dic_path,
                    encoding=self.encoding).read().replace('\r\n', '\n')
            except (UnicodeDecodeError, FileNotFoundError, PermissionError):
                print("load_dictionary(): "
                      + "loading %(dic)s as %(enc)s encoding failed, "
                      %{'dic': dic_path, 'enc': self.encoding}
                      + "giving up.")
                self.buffer = None
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
        if self.buffer:
            print("load_dictionary(): "
                  + "Successfully loaded %(dic)s using %(enc)s encoding."
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
            self.buffer = re.sub(r'/.*', '', self.buffer)
            self.buffer = unicodedata.normalize(
                NORMALIZATION_FORM_INTERNAL, self.buffer)
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
        '''
        # If the input phrase is very long, don’t try looking
        # something up in the hunspell dictionaries. The regexp match
        # gets very slow if the input phrase is very long. And there
        # are no very long words in the hunspell dictionaries anyway,
        # the longest word in the German hunspell dictionary currently
        # seems to be “Geschwindigkeitsübertretungsverfahren” trying
        # to match words longer than that just wastes time.
        if len(input_phrase) > 40:
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
            return []
        # '/' is already removed from the buffer, we do not need to
        # take care of it in the regexp.  Take care to use a
        # non-greedy regexp to match only one line and not
        # accidentally big chunks of the file!
        patt_start = re.compile(r'^' + re.escape(input_phrase) + r'.*?$',
                                re.MULTILINE)
        suggested_words = []
        for dictionary in self._dictionaries:
            if dictionary.buffer:
                suggested_words += patt_start.findall(dictionary.buffer)
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
                        # (pyhunspell (which works only for Python2)
                        # needs to get its input passed in dictionary
                        # encoding and also returns it in dictionary
                        # encoding).
                        input_phrase = unicodedata.normalize(
                            'NFC', input_phrase)
                        extra_suggestions = [
                            unicodedata.normalize(
                                NORMALIZATION_FORM_INTERNAL, x)
                            for x in
                            dictionary.enchant_dict.suggest(input_phrase)
                        ]
                        for suggestion in extra_suggestions:
                            if suggestion not in suggested_words:
                                suggested_words.append(suggestion)
                elif dictionary.pyhunspell_object:
                    if len(input_phrase) >= 4:
                        # Always pass NFC to pyhunspell and convert
                        # the result back to the internal
                        # normalization form (NFD) (hunspell does the
                        # right thing for Korean if the input is NFC).
                        input_phrase = unicodedata.normalize(
                            'NFC', input_phrase)
                        extra_suggestions = [
                            unicodedata.normalize(
                                NORMALIZATION_FORM_INTERNAL, x.decode(
                                    dictionary.encoding))
                            for x in
                            dictionary.pyhunspell_object.suggest(
                                input_phrase.encode(
                                    dictionary.encoding, 'replace'))
                        ]
                        for suggestion in extra_suggestions:
                            if suggestion not in suggested_words:
                                suggested_words.append(suggestion)
            else:
                dic_path = os.path.join(dictionary.loc, dictionary.name+'.dic')
                suggested_words.insert(
                    0,
                    '☹ %(dic_path)s not found. '
                    %{'dic_path': dic_path}
                    + 'Please install hunspell dictionary!')
        return suggested_words[0:MAX_WORDS]

