# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 2012-2013 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012-2013 Mike FABIAN <mfabian@redhat.com>
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

import os
import sys
import unicodedata
import re
import codecs
try:
    import hunspell
    import_hunspell_successful = True
except:
    import_hunspell_successful = False

# Maximum words that should be returned.
# This should a rather big number in order not
# to throw away useful matches. But making it very huge
# makes the performance worse. For example when setting
# it to 1000, I see a noticable delay when typing the first
# letter of a word until the candidate lookup table pops up.
max_words = 100
max_words_row = 50

class Hunspell:
    def __init__(self,lang='en',loc='/usr/share/myspell/',dict_name='en_US.dic',aff_name='en_US.aff'):
        self.language=lang
        self.normalization_form_internal = 'NFD'
        if self.language.startswith('ko'):
            self.normalization_form_internal = 'NFKD'
        self.loc = loc
        self.dict_name = dict_name
        self.aff_name = aff_name
        self.encoding = 'UTF-8'
        self.dict_buffer = None
        self.aff_buffer = None
        self.load_dictionary()

    def load_dictionary(self):
        self.encoding = 'UTF-8'
        self.dict_buffer = None
        self.aff_buffer = None
        self.pyhunspell_object = None
        print "load_dictionary() ..."
        if not os.path.isfile(self.loc+self.dict_name) or not os.path.isfile(self.loc+self.aff_name):
            print "load_dictionary(): .dic or .aff file missing."
            return
        try:
            self.aff_buffer = open(
                self.loc+self.aff_name).read().replace('\r\n', '\n')
        except:
            import traceback
            traceback.print_exc()
        if self.aff_buffer:
            encoding_pattern = re.compile(
                r'^[\s]*SET[\s]+(?P<encoding>[-a-zA-Z0-9_]+)[\s]*$',
                re.MULTILINE|re.UNICODE)
            match = encoding_pattern.search(self.aff_buffer)
            if match:
                self.encoding = match.group('encoding')
                print "load_dictionary(): encoding=%(enc)s found in %(aff)s" %{
                    'enc': self.encoding, 'aff': self.loc+self.aff_name}
        try:
            self.dict_buffer = codecs.open(
                self.loc+self.dict_name).read().decode(self.encoding).replace('\r\n', '\n')
        except:
            print "load_dictionary(): loading %(dic)s as %(enc)s encoding failed, fall back to ISO-8859-1." %{
                'dic': self.loc+self.dict_name, 'enc': self.encoding}
            self.encoding = 'ISO-8859-1'
            try:
                self.dict_buffer = codecs.open(
                    self.loc+self.dict_name).read().decode(self.encoding).replace('\r\n', '\n')
            except:
                print "load_dictionary(): loading %(dic)s as %(enc)s encoding failed, giving up." %{
                    'dic': self.loc+self.dict_name, 'enc': self.encoding}
                self.dict_buffer = None
                self.aff_buffer = None
                import traceback
                traceback.print_exc()
        if self.dict_buffer:
            self.dict_buffer = unicodedata.normalize(
                self.normalization_form_internal, self.dict_buffer)
        if import_hunspell_successful:
            self.pyhunspell_object = hunspell.HunSpell(
                self.loc+self.dict_name,
                self.loc+self.aff_name)
        else:
            self.pyhunspell_object = None

    def words_start(self,word):
        if type(word) != type(u''):
            word = word.decode('utf8')
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
        if '/' in word:
            return []
        # And we should not match further than '/'.
        # Take care to use a non-greedy regexp to match only
        # one line and not accidentally big chunks of the file!
        try:
            regexp = r'^'+re.escape(word)+r'.*?(?=/|$)'
            patt_start = re.compile(regexp,re.MULTILINE|re.UNICODE)
        except:
            import traceback
            traceback.print_exc()
        if self.dict_buffer != None:
            start_words = patt_start.findall(self.dict_buffer)
            if self.pyhunspell_object != None:
                if len(word) >= 4:
                    # Always pass NFC to pyhunspell and convert the
                    # result back to NFKD, even for Korean (For
                    # Korean, hunspell does a NFC -> NFKD conversion
                    # of the input and NFKD->NFC conversion of the
                    # output)
                    word = unicodedata.normalize('NFC', word)
                    extra_suggestions = map(
                        lambda x: unicodedata.normalize(
                            self.normalization_form_internal, x.decode(self.encoding)),
                        self.pyhunspell_object.suggest(word.encode(self.encoding, 'replace')))
                    for suggestion in extra_suggestions:
                        if suggestion not in start_words:
                            start_words.append(suggestion)
        else:
            start_words = [u'☹ %(loc)s%(dict_name)s not found.' %{'loc': self.loc, 'dict_name': self.dict_name}, u'☹ please install hunspell dictionary!']
        return list(set(start_words[0:max_words]))

    def suggest(self, input_phrase):
        # If the input phrase is very long, don’t try looking
        # something up in the hunspell dictionaries. The regexp match
        # gets very slow if the input phrase is very long. And there
        # are no very long words in the hunspell dictionaries anyway,
        # the longest word in the German hunspell dictionary currently
        # seems to be “Geschwindigkeitsübertretungsverfahren” trying
        # to match words longer than that just wastes time.
        if len(input_phrase) > 40:
            return []
        return self.words_start(input_phrase)



