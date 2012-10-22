# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 2012-2013 Anish Patil <apatil@redhat.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# $Id: $
#


import re
import codecs

tab_dict = {
    '0':0,
    'a':1, 'b':2, 'c':3, 'd':4, 'e':5,
    'f':6, 'g':7, 'h':8, 'i':9, 'j':10,
    'k':11, 'l':12, 'm':13, 'n':14, 'o':15,
    'p':16, 'q':17, 'r':18, 's':19, 't':20,
    'u':21, 'v':22, 'w':23, 'x':24, 'y':25,
    'z':26, "'":27, ';':28, '`':29, '~':30,
    '!':31, '@':32, '#':33, '$':34, '%':35,
    '^':36, '&':37, '*':38, '(':39, ')':40,
    '-':41, '_':42, '=':43, '+':44, '[':45,
    ']':46, '{':47, '}':48, '|':49, '/':50,
    ':':51, '"':52,  '<':53, '>':54, ',':55,
    '.':56, '?':57, '\\':58, 'A':59, 'B':60,
    'C':61, 'D':62, 'E':63, 'F':64, 'G':65,
    'H':66, 'I':67, 'J':68, 'K':69, 'L':70,
    'M':71, 'N':72, 'O':73, 'P':74, 'Q':75,
    'R':76, 'S':77, 'T':78, 'U':79, 'V':80,
    'W':81, 'X':82, 'Y':83, 'Z':84, '0':85,
    '1':86, '2':87, '3':88, '4':89, '5':90,
    '6':91, '7':92, '8':93, '9':94
    }

# Maximum words that needs to be returned 
max_words = 9
max_words_row = 50
# System frequency by default it is kept as 0
system_freq = 0
# The system word is 1 and user defined word is -1
system_word = 1

class Hunspell:
    def __init__(self,lang='en',loc='/usr/share/myspell/',dict_name='en_US.dic',aff_name='en_US.aff',m17n=False,langdict=None,
                 lang_chars='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
                 encoding='UTF-8'):
        self.lang=lang
        self.loc = loc
        self.dict_name = dict_name
        self.lang_chars=lang_chars
        self.m17n=m17n
        self.tab_dict = tab_dict
        self.encoding = encoding
        if langdict != None:
            self.tab_dict = langdict

        try:
            self.dict_buffer = codecs.open(loc+dict_name).read().decode(self.encoding)
            self.aff_handle = open(loc+aff_name)
        except:
            # print "Dictionary file %s or AFF file is not present %s ",(dict_name,aff_name)
            self.dict_buffer = None
            self.aff_handle = None
            pass


    ''' This function takes list as input and converts the words in the list into tab_dict format'''
    def convert_tab_dict(self,words):
        # The function checks the key is tab dict or not if it is there get the val otherwise -1
        ch_tab_dict = lambda x : self.tab_dict[x]  if x in self.tab_dict.keys() else  -1 
        num_format = [ map(ch_tab_dict,word) for word in words ]
        return num_format

    def words_start(self,word):
        if type(word) != type(u''):
            word = word.decode('utf8')
        char_class = self.lang_chars
        # We try to match a word in the dictionary by trying to
        # match the word as typed so far followed by characters
        # allowed in the language, i.e. followed by characters listed
        # in the value of 'lang_chars' in the .conf file.
        #
        # In case 'lang_chars' contains the characters '\', ']', '^', and '-'
        # they need to be escaped because these are meta-characters
        # in a regular expression character class.
        char_class = char_class.replace('\\', '\\\\')
        char_class = char_class.replace(']', '\\]')
        char_class = char_class.replace('^', '\\^')
        char_class = char_class.replace('-', '\\-')
        try:
            regexp = '^'+word+'['+char_class+']*'
            patt_start = re.compile(regexp,re.MULTILINE|re.UNICODE)
        except:
            # Exception here means characters such as ( are present in the string
            word = word.strip('()+=|-')
            regexp = '^'+word+'['+char_class+']*'
            patt_start = re.compile(regexp,re.MULTILINE|re.UNICODE)
        if self.dict_buffer != None:
            start_words = patt_start.findall(self.dict_buffer)
        else:
            start_words = [unicode('☹ %(loc)s%(dict_name)s not found.' %{'loc': self.loc, 'dict_name': self.dict_name}, 'utf-8'), unicode('☹ please install hunspell dictionary!', 'utf-8') ]
        words = set(start_words[0:max_words])
        # The list consists of words but in there  
        tab_words = [ list(word) for word in words ] 
        # return the words wrt to their numbers e.g the word "abc" will contain numbers "123"
        #self.num_words = self.convert_tab_dict(self.tab_words)
        return words,self.convert_tab_dict(tab_words)

    ''' You need to send data in the following protocol==> sq no,len,len,string up to 50 char,string,-1,1'''
    def convert_to_lists(self,words,num_words):
        formated_words = []
        for seq,word in enumerate(words):
            w_len = len(word)
            formated_words.append([seq,w_len,w_len])
            (formated_words[seq]).extend(num_words[seq]) # a bit of c-style :(
            filler_len = max_words_row - w_len
            (formated_words[seq]).extend([None for i in range(filler_len)])
            (formated_words[seq]).append(word)
            (formated_words[seq]).append(system_word)
            (formated_words[seq]).append(system_freq)
        return formated_words

    def suggest(self,word):
        words,num_words = self.words_start(word)
        suggestions = []
        if words:
            suggestions = self.convert_to_lists(words,num_words)
        return suggestions



