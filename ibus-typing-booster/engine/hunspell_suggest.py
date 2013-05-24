# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 2012-2013 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012 Mike FABIAN <mfabian@redhat.com>
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
    def __init__(self,lang='en',loc='/usr/share/myspell/',dict_name='en_US.dic',aff_name='en_US.aff',
                 encoding='UTF-8'):
        self.lang=lang
        self.loc = loc
        self.dict_name = dict_name
        self.aff_name = aff_name
        self.encoding = encoding
        self.dict_buffer = None
        self.aff_handle = None
        self.load_dictionary()

    def load_dictionary(self):
        self.dict_buffer = None
        self.aff_handle = None
        self.pyhunspell_object = None
        try:
            self.dict_buffer = codecs.open(self.loc+self.dict_name).read().decode(self.encoding).replace('\r\n', '\n')
            self.aff_handle = open(self.loc+self.aff_name)
            if import_hunspell_successful:
                self.pyhunspell_object = hunspell.HunSpell(
                    self.loc+self.dict_name,
                    self.loc+self.aff_name)
        except:
            # print "Dictionary file %s or AFF file is not present %s ",(dict_name,aff_name)
            self.dict_buffer = None
            self.aff_handle = None
            self.pyhunspell_object = None
            import traceback
            traceback.print_exc()
            pass

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
            regexp = r'^'+word+r'.*?(?=/|$)'
            patt_start = re.compile(regexp,re.MULTILINE|re.UNICODE)
        except:
            # Exception here means characters such as ( are present in the string
            word = word.strip('()+=|-')
            regexp = r'^'+word+r'.*?(?=/|$)'
            patt_start = re.compile(regexp,re.MULTILINE|re.UNICODE)
        if self.dict_buffer != None:
            start_words = patt_start.findall(self.dict_buffer)
            if self.pyhunspell_object != None:
                if len(word) >= 4:
                    extra_suggestions = map(
                        lambda x: x.decode(self.encoding),
                        self.pyhunspell_object.suggest(word.encode(self.encoding)))
                    for suggestion in extra_suggestions:
                        if suggestion not in start_words:
                            start_words.append(suggestion)
        else:
            start_words = [unicode('☹ %(loc)s%(dict_name)s not found.' %{'loc': self.loc, 'dict_name': self.dict_name}, 'utf-8'), unicode('☹ please install hunspell dictionary!', 'utf-8') ]
        return list(set(start_words[0:max_words]))

    def suggest(self, input_phrase):
        return self.words_start(input_phrase)



