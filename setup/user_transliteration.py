#!/usr/bin/python3
# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2012-2014 Anish Patil <apatil@redhat.com>
# Copyright (c) 2014 Mike FABIAN <mfabian@redhat.com>
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

from typing import List
from typing import Dict
from typing import Optional
import os
import os.path as path
import sys
import re
import codecs
import sqlite3
import time
from gi.repository import Translit # type: ignore


class LangDictTable:
    '''
        Class that specifies accent rules that needs to be appied for each language
        If user has specified user dictionary then that can be overiden by default mapping
    '''
    def __init__(self, dict_name: str, lang_dict: Optional[Dict[str, str]] = None) -> None:
        self.lang: str = dict_name
        self.lang_table: Optional[Dict[str, str]] = lang_dict

    def get_lang_table(self) -> Dict[str, str]:
        if self.lang_table:
            return self.lang_table
        else:
            return self.get_sys_lang_table()

    def get_sys_lang_table(self) -> Dict[str, str]:
        if self.lang == 'mr_IN.dic':
            return self.get_mr_table()
        return {}

    def get_mr_table(self) -> Dict[str, str]:
        table: Dict[str, str] = dict({
            ('ā', 'aa'),
            ('ṭ', 't'),
            ('ḍ', 'd'),
            ('ē', 'e'),
            ('ĕ', 'ey'),
            ('ẖ', 'ha'),
            ('ṛ', 'da'),
            ('ġ', 'gan'),
            ('ī', 'ee'),
            ('ḵ', 'k'),
            ('ḷ', 'l'),
            ('ṁ', '-mm'),
            ('ṅ', 'nn'),
            ('ṇ', 'na'),
            ('', 'a'),
            ('ō', 'o'),
            ('ṣ', 'sh'),
            ('ŏ', 'oy'),
            ('ḥ', 'tah'),
            ('ś', 'she'),
            ('ṟ', 'rr'),
            ('ū', 'u'),
            ('ñ', 'dnya'),
            ('n̄' , 'n')
        })
        return table

class LatinConvert:
    def __init__(self,
                 user_dict: str,
                 hunspell_dict: str,
                 aff_file: str,
                 dict_name: str) -> None:
        self.user_db = user_dict
        self.hunspell_dict = hunspell_dict
        self.aff_file = aff_file
        self.trans = Translit.Transliterator.get("icu", "en")
        self.conv_table = LangDictTable(dict_name)
        self.lang_table = self.conv_table.get_lang_table()

    def read_hunspell_dict(self) -> str:
        aff_buffer = ''
        encoding = ''
        dict_buffer = ''
        try:
            aff_buffer = codecs.open(
                self.aff_file, mode='r', encoding='ISO-8859-1').read().replace('\r\n', '\n')
        except:
            import traceback
            traceback.print_exc()
        if aff_buffer:
            encoding_pattern = re.compile(
                r'^[\s]*SET[\s]+(?P<encoding>[-a-zA-Z0-9_]+)[\s]*$',
                re.MULTILINE|re.UNICODE)
            match = encoding_pattern.search(aff_buffer)
            if match:
                encoding = match.group('encoding')
                print("load_dictionary(): encoding=%(enc)s found in %(aff)s" %{
                    'enc': encoding, 'aff': self.aff_file})
        try:
            dict_buffer = codecs.open(
                self.hunspell_dict, encoding=encoding).read().replace('\r\n', '\n')
        except:
            print("load_dictionary(): loading %(dic)s as %(enc)s encoding failed, fall back to ISO-8859-1." %{
                'dic': self.hunspell_dict, 'enc': encoding})
            encoding = 'ISO-8859-1'
            try:
                dict_buffer = codecs.open(
                    self.hunspell_dict, encoding=encoding).read().replace('\r\n', '\n')
            except:
                print("load_dictionary(): loading %(dic)s as %(enc)s encoding failed, giving up." %{
                    'dic': self.hunspell_dict, 'enc': encoding})
        if dict_buffer[0] == '\ufeff':
            dict_buffer = dict_buffer[1:]
        return dict_buffer

    def get_words(self) -> List[str]:
        buff = self.read_hunspell_dict()
        word_pattern = re.compile(r'^[^\s]+.*?(?=/|$)', re.MULTILINE|re.UNICODE)
        words: List[str] = word_pattern.findall(buff)
        nwords = int(words[0])
        words = words[1:]
        return words

    def trans_word(self, word: str) -> str:
        try:
            return str(self.trans.transliterate(word)[0])
        except:
            print("Error while transliteration")
            return word

    def remove_accent(self, word: str) -> str:
        new_word  = []
        # To- Do use list compression
        for char in word:
            if char in self.lang_table:
                new_word.append(self.lang_table[char])
            elif char in[ '\u0325', '\u0310','\u0304', '\u0315','\u0314']:
                pass
            else:
                new_word.append(char)
        return ''.join(new_word)

    def get_converted_words(self) -> List[str]:
        words = self.get_words()
        icu_words = list(map(self.trans_word, words))
        ascii_words = list(map(self.remove_accent, icu_words))
        return ascii_words

    def insert_into_db(self) -> None:
        words = self.get_converted_words()
        sql_table_name = "phrases"
        try:
            conn = sqlite3.connect(self.user_db)
            sql = "INSERT INTO %s (input_phrase, phrase, user_freq, timestamp) values(:input_phrase, :phrase, :user_freq, :timestamp);" % (sql_table_name)
            sqlargs = []
            list(map(lambda x: sqlargs.append(
                {'input_phrase': x,
                 'phrase': x,
                 'user_freq': 0,
                 'timestamp': time.time()}),
                words))
            conn.executemany(sql,sqlargs)
            conn.commit()
        except:
            import traceback
            traceback.print_exc()

import argparse
parser = argparse.ArgumentParser(
    description='Transliterate a hunspell dictionary to Latin script and insert it into the user database. Currently works only for mr_IN.dic.')
parser.add_argument('-u', '--userdictionary',
                    nargs='?',
                    type=str,
                    default='',
                    help='user dictionary. For example ~/.local/share/ibus-typing-booster/user.db. A full path can be given or only the basename. When only the basename is given, ~/.local/share/ibus-typing-booster/ is prepended automatically.')
parser.add_argument('-d', '--hunspelldict',
                    nargs='?',
                    type=str,
                    default='',
                    help='hunspell file path. For example /usr/share/myspell/mr_IN.dic. A full path can be given or only the basename. When only the basename is given, /usr/share/myspell/ is prepended automatically.')
args = parser.parse_args()

def main() -> None:
    if not args.userdictionary or not args.hunspelldict:
        parser.print_help()
        sys.exit(1)
    user_dict = args.userdictionary
    hunspell_dict = args.hunspelldict
    if user_dict:
        #check whether user dict exists in the path
        tables_path = path.expanduser('~/.local/share/ibus-typing-booster')
        if '/' not in user_dict:
            # if user_dict already contains a '/' full path was given
            # on the command line. If there is no '/', it is only the file
            # name, add the default path:
            user_dict = path.join (tables_path, user_dict)
        if not path.exists(user_dict):
            sys.stderr.write(
                "The user database %(udb)s does not exist .\n" %{'udb': user_dict})
            sys.exit(1)
    if hunspell_dict:
        # Not sure how to get hunspell dict path from env
        hunspell_path = "/usr/share/myspell/"
        if '/' not in hunspell_dict:
            # if hunspell_dict already contains a '/' full path was given
            # on the command line. If there is no '/', it is only the file
            # name, add the default path:
            hunspell_dict = path.join(hunspell_path,hunspell_dict)
        if not path.exists(hunspell_dict):
            sys.stderr.write(
                "The hunspell dictionary  %(hud)s does not exists .\n" %{'hud': hunspell_dict})
            sys.exit(1)
    lt = LatinConvert(user_dict,
                      hunspell_dict,
                      hunspell_dict.replace('.dic', '.aff'),
                      os.path.basename(hunspell_dict))
    lt.insert_into_db()

if __name__ == '__main__':
    main()
