#!/usr/bin/python3

# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2019 Mike FABIAN <mfabian@redhat.com>
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

'''
This file implements test cases for finding key codes for key values
'''

from typing import Any
import sys
import os
import locale
import tempfile
import unittest

# Avoid failing test cases because of stuff in the users M17NDIR ('~/.m17n.d'):
os.environ['M17NDIR'] = tempfile.TemporaryDirectory().name # pylint: disable=consider-using-with
M17N_CONFIG_FILE= os.path.join(os.environ['M17NDIR'], 'config.mic')

# pylint: disable=wrong-import-position
sys.path.insert(0, "../engine")
import m17n_translit # pylint: disable=import-error
import itb_util # pylint: disable=import-error
sys.path.pop(0)
# pylint: enable=wrong-import-position

# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name

M17N_DB_INFO = itb_util.M17nDbInfo()
M17N_DB_VERSION = (M17N_DB_INFO.get_major_version(),
                   M17N_DB_INFO.get_minor_version(),
                   M17N_DB_INFO.get_micro_version())

class M17nTranslitTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # Avoid translations changing test case results:
        locale.setlocale(locale.LC_MESSAGES, 'en_US.UTF-8')

    def tearDown(self) -> None:
        pass

    def get_transliterator_or_skip(self, ime: str) -> Any:
        try:
            sys.stderr.write(f'ime "{ime}" ... ')
            trans = m17n_translit.Transliterator(ime)
        except ValueError as error:
            trans = None
            self.skipTest(error)
        except Exception as error: # pylint: disable=broad-except
            sys.stderr.write('Unexpected exception!')
            trans = None
            self.skipTest(error)
        return trans

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_non_existing_ime(self) -> None:
        # If initializing the transliterator fails, for example
        # because a non-existing input method was given as the
        # argument, a ValueError is raised:
        try:
            dummy_trans = m17n_translit.Transliterator('ru-translitx')
        except ValueError:
            pass
        except Exception: # pylint: disable=broad-except
            # Something unexpected happened:
            self.assertTrue(False) # pylint: disable=redundant-unittest-assert

    def test_ru_translit(self) -> None:
        trans = m17n_translit.Transliterator('ru-translit')
        self.assertEqual(trans.transliterate(list('y')), 'ы')
        self.assertEqual(trans.transliterate(list('yo')), 'ё')
        self.assertEqual(trans.transliterate(list('yo y')), 'ё ы')

    def test_mr_itrans(self) -> None:
        trans = m17n_translit.Transliterator('mr-itrans')
        self.assertEqual(trans.transliterate(list('praviN')), 'प्रविण्')
        self.assertEqual(trans.transliterate(list('namaste')), 'नमस्ते')
        self.assertEqual(trans.transliterate(['n']), 'न्')
        self.assertEqual(trans.transliterate(['n', ' ']), 'न् ')
        self.assertEqual(trans.transliterate(['n', 'S-C-Return']), 'न्S-C-Return')
        self.assertEqual(trans.transliterate(['S-C-Return']), 'S-C-Return')

    def test_hi_itrans(self) -> None:
        trans = m17n_translit.Transliterator('hi-itrans')
        self.assertEqual(trans.transliterate(list('namaste')), 'नमस्ते')
        self.assertEqual(trans.transliterate(list('. ')), '। ')
        self.assertEqual(trans.transliterate(['S-C-Return']), 'S-C-Return')
        self.assertEqual(trans.transliterate(['n']), 'न्')
        self.assertEqual(trans.transliterate(['n', ' ']), 'न ')
        self.assertEqual(trans.transliterate(['n', 'S-C-Return']), 'न्')
        self.assertEqual(trans.transliterate(['n', 'S-C-Return', ' ']), 'न् ')
        self.assertEqual(trans.transliterate(['n', 'T']), 'ण्ट्')
        self.assertEqual(trans.transliterate(['n', 'T', 'S-C-Return']), 'ण्ट्')
        self.assertEqual(trans.transliterate(['n', 'S-C-Return', 'T']), 'न्ट्')
        self.assertEqual(trans.transliterate(['n', 'S-C-Return', 'T', ' ']), 'न्ट ')
        self.assertEqual(trans.transliterate(['n', 'S-C-Return', 'T', 'S-C-Return']), 'न्ट्')
        self.assertEqual(trans.transliterate(['n', 'S-C-Return', 'T', 'S-C-Return', ' ']), 'न्ट् ')
        self.assertEqual(trans.transliterate(['a']), 'अ')
        self.assertEqual(trans.transliterate(['a', ' ']), 'अ ')
        self.assertEqual(trans.transliterate(['a', 'S-C-Return']), 'अS-C-Return')

    def test_unicode(self) -> None:
        trans = self.get_transliterator_or_skip('t-unicode')
        self.assertEqual('', trans.transliterate([]))
        self.assertEqual(
            'U+', trans.transliterate(['C-u']))
        self.assertEqual(
            'ॲ', trans.transliterate(['C-u', '0', '9', '7', '2', ' ']).strip())
        self.assertEqual(
            '☺', trans.transliterate(['C-u', '2', '6', '3', 'a', ' ']).strip())
        self.assertEqual(
            '☺', trans.transliterate(['C-u', '2', '6', '3', 'A', ' ']).strip())

    def test_unicode_hi_itrans(self) -> None:
        '''Unicode input should work not only when the t-unicode input method
        is selected but for all m17n input methods'''
        trans = self.get_transliterator_or_skip('hi-itrans')
        self.assertEqual('', trans.transliterate([]))
        self.assertEqual(
            'U+', trans.transliterate(['C-u']))
        self.assertEqual(
            'ॲ', trans.transliterate(['C-u', '0', '9', '7', '2', ' ']).strip())
        self.assertEqual(
            '☺', trans.transliterate(['C-u', '2', '6', '3', 'a', ' ']).strip())
        self.assertEqual(
            '☺', trans.transliterate(['C-u', '2', '6', '3', 'A', ' ']).strip())
        self.assertEqual(
            'नमस्ते', trans.transliterate(list('namaste')))
        self.assertEqual(
            'नमस्ते ☺',
            trans.transliterate(
                list('namaste ') + ['C-u', '2', '6', '3', 'a', ' ']).strip())

    def test_hi_inscript2(self) -> None:
        trans = self.get_transliterator_or_skip('hi-inscript2')
        self.assertEqual(trans.transliterate([]), '')
        # Hindi-Inscript2 uses the AltGr key a lot, 'G-4' is the
        # MSymbol name for AltGr-4 and it transliterates to something
        # different than just '4':
        self.assertEqual(trans.transliterate(['4', 'G-4']), '४₹')
        self.assertEqual(trans.transliterate(['G-p']), 'ज़')
        # AltGr-3 ('G-3') is not used though in Hindi-Inscript2.
        # Therefore, 'G-3' transliterates just as 'G-3':
        self.assertEqual(trans.transliterate(['3', 'G-3']), '३G-3')

    def test_mr_inscript2(self) -> None:
        trans = self.get_transliterator_or_skip('mr-inscript2')
        # In mr-inscript2, 'G-1' transliterates to U+200D ZERO WIDTH
        # JOINER ('\xe2\x80\x8d' in UTF-8 encoding):
        self.assertEqual(
            trans.transliterate(['j', 'd', 'G-1', '/']).encode('utf-8'),
            b'\xe0\xa4\xb0\xe0\xa5\x8d\xe2\x80\x8d\xe0\xa4\xaf')

    def test_t_latn_post(self) -> None:
        trans = m17n_translit.Transliterator('t-latn-post')
        self.assertEqual(trans.transliterate(list('gru"n')), 'grün')

    def test_NoIME(self) -> None:
        trans = m17n_translit.Transliterator('NoIME')
        self.assertEqual(
            trans.transliterate(['a', 'b', 'c', 'C-c', 'G-4']),
            'abcC-cG-4')

    def test_si_wijesekera(self) -> None:
        trans = m17n_translit.Transliterator('si-wijesekera')
        self.assertEqual(trans.transliterate(list('a')), '්')
        self.assertEqual(trans.transliterate(list('t')), 'එ')
        self.assertEqual(trans.transliterate(list('ta')), 'ඒ')
        self.assertEqual(
            trans.transliterate(list('vksIal kjSka ')), 'ඩනිෂ්ක නවීන් ')

    def test_ja_anthy(self) -> None:
        trans = self.get_transliterator_or_skip('ja-anthy')
        self.assertEqual(
            trans.transliterate(list('chouchou')), 'ちょうちょう')

    def test_zh_py(self) -> None:
        trans = self.get_transliterator_or_skip('zh-py')
        self.assertEqual(
            trans.transliterate(['n', 'i', 'h', 'a', 'o']), '你好')

    def test_zh_tonepy(self) -> None:
        trans = self.get_transliterator_or_skip('zh-tonepy')
        self.assertEqual(
            trans.transliterate(['n', 'i', '3', 'h', 'a', 'o', '3']), '你好')

    def test_ko_romaja(self) -> None:
        trans = self.get_transliterator_or_skip('ko-romaja')
        self.assertEqual(
            trans.transliterate(list('annyeonghaseyo')), '안녕하세요')

    def test_si_sayura(self) -> None:
        # pylint: disable=line-too-long
        # pylint: disable=fixme
        trans = self.get_transliterator_or_skip('si-sayura')
        self.assertEqual(trans.transliterate(list('a')), 'අ')
        self.assertEqual(trans.transliterate(list('a ')), 'අ ')
        self.assertEqual(trans.transliterate(list('a a ')), 'අ අ ')
        self.assertEqual(trans.transliterate(list('aa')), 'ආ')
        self.assertEqual(trans.transliterate(list('aa ')), 'ආ ')
        self.assertEqual(trans.transliterate(list('aaa')), 'ආ')
        self.assertEqual(trans.transliterate(list('aaaa')), 'ආ')
        self.assertEqual(trans.transliterate(list('aaaa ')), 'ආ ')
        self.assertEqual(trans.transliterate(list('A')), 'ඇ')
        self.assertEqual(trans.transliterate(list('q')), 'ඇ')
        self.assertEqual(trans.transliterate(list('AA')), 'ඈ')
        self.assertEqual(trans.transliterate(list('qq')), 'ඈ')
        self.assertEqual(trans.transliterate(list('qqq')), 'ඈ')
        self.assertEqual(trans.transliterate(list('Aa')), 'ආ')
        self.assertEqual(trans.transliterate(list('qa')), 'ආ')
        self.assertEqual(trans.transliterate(list('Aaa')), 'ආ')
        self.assertEqual(trans.transliterate(list('qaa')), 'ආ')
        self.assertEqual(trans.transliterate(list('e')), 'එ')
        self.assertEqual(trans.transliterate(list('E')), 'එ')
        self.assertEqual(trans.transliterate(list('ee')), 'ඒ')
        self.assertEqual(trans.transliterate(list('EE')), 'ඒ')
        self.assertEqual(trans.transliterate(list('eE')), 'ඒ')
        self.assertEqual(trans.transliterate(list('eee')), 'ඒ')
        self.assertEqual(trans.transliterate(list('EEE')), 'ඒ')
        self.assertEqual(trans.transliterate(list('eEe')), 'ඒ')
        self.assertEqual(trans.transliterate(list('i')), 'ඉ')
        self.assertEqual(trans.transliterate(list('ii')), 'ඊ')
        self.assertEqual(trans.transliterate(list('iii')), 'ඊ')
        self.assertEqual(trans.transliterate(list('u')), 'උ')
        self.assertEqual(trans.transliterate(list('uu')), 'ඌ')
        self.assertEqual(trans.transliterate(list('uuu')), 'ඌ')
        self.assertEqual(trans.transliterate(list('I')), 'ඓ')
        self.assertEqual(trans.transliterate(list('II')), '')
        self.assertEqual(trans.transliterate(list('o')), 'ඔ')
        self.assertEqual(trans.transliterate(list('oo')), 'ඕ')
        self.assertEqual(trans.transliterate(list('O')), 'ඖ')
        self.assertEqual(trans.transliterate(list('OO')), '')
        self.assertEqual(trans.transliterate(list('u')), 'උ')
        self.assertEqual(trans.transliterate(list('U')), 'ඍ')
        self.assertEqual(trans.transliterate(list('UU')), 'ඎ')
        self.assertEqual(trans.transliterate(list('UUU')), 'ඎ')
        # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
        self.assertEqual(trans.transliterate(list('V')), 'ව')
        # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
        self.assertEqual(trans.transliterate(list('VV')), 'වව')
        self.assertEqual(trans.transliterate(list('z')), 'ඤ')
        self.assertEqual(trans.transliterate(list('Z')), 'ඥ')
        self.assertEqual(trans.transliterate(list('k')), 'ක')
        self.assertEqual(trans.transliterate(list('ka')), 'කා')
        self.assertEqual(trans.transliterate(list('K')), 'ඛ')
        self.assertEqual(trans.transliterate(list('H')), 'හ')
        # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
        self.assertEqual(trans.transliterate(list('kf')), 'කෆ')
        self.assertEqual(trans.transliterate(list('kH')), 'ඛ')
        self.assertEqual(trans.transliterate(list('kaa')), 'කා')
        self.assertEqual(trans.transliterate(list('f')), 'ෆ')
        self.assertEqual(trans.transliterate(list('g')), 'ග')
        # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
        self.assertEqual(trans.transliterate(list('gf')), 'ගෆ')
        self.assertEqual(trans.transliterate(list('gH')), 'ඝ')
        self.assertEqual(trans.transliterate(list('X')), 'ඞ')
        self.assertEqual(trans.transliterate(list('c')), 'ච')
        self.assertEqual(trans.transliterate(list('C')), 'ඡ')
        # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
        self.assertEqual(trans.transliterate(list('cf')), 'චෆ')
        self.assertEqual(trans.transliterate(list('cH')), 'ඡ')
        self.assertEqual(trans.transliterate(list('j')), 'ජ')
        self.assertEqual(trans.transliterate(list('J')), 'ඣ')
        # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
        self.assertEqual(trans.transliterate(list('jf')), 'ජෆ')
        self.assertEqual(trans.transliterate(list('jH')), 'ඣ')
        self.assertEqual(trans.transliterate(list('T')), 'ට')
        # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
        self.assertEqual(trans.transliterate(list('Tf')), 'ටෆ')
        self.assertEqual(trans.transliterate(list('TH')), 'ඨ')
        self.assertEqual(trans.transliterate(list('D')), 'ඩ')
        # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
        self.assertEqual(trans.transliterate(list('Df')), 'ඩෆ')
        self.assertEqual(trans.transliterate(list('DH')), 'ඪ')
        self.assertEqual(trans.transliterate(list('N')), 'ණ')
        self.assertEqual(trans.transliterate(list('n')), 'න')
        self.assertEqual(trans.transliterate(list('m')), 'ම')
        self.assertEqual(trans.transliterate(list('L')), 'ළ')
        self.assertEqual(trans.transliterate(list('F')), 'ෆ')
        self.assertEqual(trans.transliterate(list('t')), 'ත')
        # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
        self.assertEqual(trans.transliterate(list('tf')), 'තෆ')
        self.assertEqual(trans.transliterate(list('tH')), 'ථ')
        self.assertEqual(trans.transliterate(list('d')), 'ද')
        # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
        self.assertEqual(trans.transliterate(list('df')), 'දෆ')
        self.assertEqual(trans.transliterate(list('dH')), 'ධ')
        self.assertEqual(trans.transliterate(list('p')), 'ප')
        self.assertEqual(trans.transliterate(list('P')), 'ඵ')
        # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
        self.assertEqual(trans.transliterate(list('pf')), 'පෆ')
        self.assertEqual(trans.transliterate(list('pH')), 'ඵ')
        self.assertEqual(trans.transliterate(list('b')), 'බ')
        self.assertEqual(trans.transliterate(list('B')), 'භ')
        # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
        self.assertEqual(trans.transliterate(list('bf')), 'බෆ')
        self.assertEqual(trans.transliterate(list('bH')), 'භ')
        self.assertEqual(trans.transliterate(list('y')), 'ය')
        self.assertEqual(trans.transliterate(list('r')), 'ර')
        self.assertEqual(trans.transliterate(list('l')), 'ල')
        self.assertEqual(trans.transliterate(list('v')), 'ව')
        self.assertEqual(trans.transliterate(list('s')), 'ස')
        self.assertEqual(trans.transliterate(list('S')), 'ශ')
        # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
        self.assertEqual(trans.transliterate(list('sf')), 'සෆ')
        # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
        self.assertEqual(trans.transliterate(list('Sf')), 'ශෆ')
        self.assertEqual(trans.transliterate(list('sH')), 'ෂ')
        self.assertEqual(trans.transliterate(list('SH')), 'ෂ')
        self.assertEqual(trans.transliterate(list('h')), 'හ')
        self.assertEqual(trans.transliterate(list('G')), 'ඟ')
        self.assertEqual(trans.transliterate(list('gG')), 'ඟ')
        self.assertEqual(trans.transliterate(list('dG')), 'ඳ')
        self.assertEqual(trans.transliterate(list('DG')), 'ඬ')
        self.assertEqual(trans.transliterate(list('M')), 'ඹ')
        self.assertEqual(trans.transliterate(list('bG')), 'ඹ')
        self.assertEqual(trans.transliterate(list('kw')), 'ක්')
        self.assertEqual(trans.transliterate(list('ka')), 'කා')
        self.assertEqual(trans.transliterate(list('kq')), 'කැ')
        self.assertEqual(trans.transliterate(list('kqq')), 'කෑ')
        self.assertEqual(trans.transliterate(list('ki')), 'කි')
        self.assertEqual(trans.transliterate(list('kii')), 'කී')
        self.assertEqual(trans.transliterate(list('ku')), 'කු')
        self.assertEqual(trans.transliterate(list('kuu')), 'කූ')
        self.assertEqual(trans.transliterate(list('kU')), 'කෘ')
        self.assertEqual(trans.transliterate(list('kUU')), 'කෲ')
        self.assertEqual(trans.transliterate(list('ke')), 'කෙ')
        self.assertEqual(trans.transliterate(list('kee')), 'කේ')
        self.assertEqual(trans.transliterate(list('ko')), 'කො')
        self.assertEqual(trans.transliterate(list('koo')), 'කෝ')
        self.assertEqual(trans.transliterate(list('kI')), 'කෛ')
        self.assertEqual(trans.transliterate(list('kO')), 'කෞ')
        self.assertEqual(trans.transliterate(list('kx')), 'කං')
        # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
        self.assertEqual(trans.transliterate(list('kQ')), 'කQ')
        self.assertEqual(trans.transliterate(list('W')), '\u200c')
        self.assertEqual(trans.transliterate(list('kWsH')), 'ක්‍ෂ')
        self.assertEqual(trans.transliterate(list('nWd')), 'න්‍ද')
        self.assertEqual(trans.transliterate(list('nWdu')), 'න්‍දු')
        self.assertEqual(trans.transliterate(list('inWdRiy')), 'ඉන්‍ද්‍රිය')
        self.assertEqual(trans.transliterate(list('rWk')), 'ර්‍ක')
        self.assertEqual(trans.transliterate(list('R')), 'ර')
        self.assertEqual(trans.transliterate(list('Y')), 'ය')
        self.assertEqual(trans.transliterate(list('kR')), 'ක්‍ර')
        self.assertEqual(trans.transliterate(list('kY')), 'ක්‍ය')
        self.assertEqual(trans.transliterate(list('E')), 'එ')
        self.assertEqual(trans.transliterate(list('takWsHN')), 'තාක්‍ෂණ')
        self.assertEqual(trans.transliterate(list('takwsHN')), 'තාක්ෂණ')
        # pylint: enable=line-too-long
        # pylint: enable=fixme

    def test_bn_national_jatiya(self) -> None:
        '''
        Test my new bn-national-jatiya.mim input method
        '''
        # pylint: disable=line-too-long
        trans = self.get_transliterator_or_skip('bn-national-jatiya')
        self.assertEqual(trans.transliterate(['G-0']), '৹') # U+09F9 BENGALI CURRENCY DENOMINATOR SIXTEEN
        self.assertEqual(trans.transliterate(['0']), '০') # U+09E6 BENGALI DIGIT ZERO
        self.assertEqual(trans.transliterate(['G-1']), '৴') # U+09F4 BENGALI CURRENCY NUMERATOR ONE
        self.assertEqual(trans.transliterate(['1']), '১')   # U+09E7 BENGALI DIGIT ONE
        self.assertEqual(trans.transliterate(['G-2']), '৵') # U+09F5 BENGALI CURRENCY NUMERATOR TWO
        self.assertEqual(trans.transliterate(['2']), '২')  # U+09E8 BENGALI DIGIT TWO
        self.assertEqual(trans.transliterate(['G-3']), '৶') # U+09F6 BENGALI CURRENCY NUMERATOR THREE
        self.assertEqual(trans.transliterate(['3']), '৩')  # U+09E9 BENGALI DIGIT THREE
        self.assertEqual(trans.transliterate(['G-4']), '৳') # U+09F3 BENGALI RUPEE SIGN
        self.assertEqual(trans.transliterate(['4']), '৪')  # U+09EA BENGALI DIGIT FOUR
        self.assertEqual(trans.transliterate(['G-5']), '৷') # U+09F7 BENGALI CURRENCY NUMERATOR FOUR
        self.assertEqual(trans.transliterate(['5']), '৫')  # U+09EB BENGALI DIGIT FIVE
        self.assertEqual(trans.transliterate(['G-6']), '৸') # U+09F8 BENGALI CURRENCY NUMERATOR ONE LESS THAN THE DENOMINATOR
        self.assertEqual(trans.transliterate(['6']), '৬')  # U+09EC BENGALI DIGIT SIX
        self.assertEqual(trans.transliterate(['G-7']), 'ं') # U+0902 DEVANAGARI SIGN ANUSVARA (Only in /usr/share/X11/xkb/symbols/bn)
        self.assertEqual(trans.transliterate(['7']), '৭')  # U+09ED BENGALI DIGIT SEVEN
        self.assertEqual(trans.transliterate(['G-8']), '') # Nothing
        self.assertEqual(trans.transliterate(['8']), '৮')  # U+09EE BENGALI DIGIT EIGHT
        self.assertEqual(trans.transliterate(['G-9']), '') # Nothing
        self.assertEqual(trans.transliterate(['9']), '৯')  # U+09EF BENGALI DIGIT NINE
        self.assertEqual(trans.transliterate(['G-A']), 'ৠ') # U+09E0 BENGALI LETTER VOCALIC RR
        self.assertEqual(trans.transliterate(['A']), 'ৗ')  # U+09D7 BENGALI AU LENGTH MARK
        self.assertEqual(trans.transliterate(['G-&']), '') # Nothing
        self.assertEqual(trans.transliterate(['&']), '&')  # U+0026 AMPERSAND
        self.assertEqual(trans.transliterate(["G-'"]), '') # Nothing
        self.assertEqual(trans.transliterate(["'"]), "'")  # U+0027 APOSTROPHE
        self.assertEqual(trans.transliterate(['G-*']), '') # Nothing
        self.assertEqual(trans.transliterate(['*']), '*')  # U+002A ASTERISK
        self.assertEqual(trans.transliterate(['G-@']), '') # Nothing
        self.assertEqual(trans.transliterate(['@']), '@')  # U+0040 COMMERCIAL AT
        self.assertEqual(trans.transliterate(['G-B']), '') # Nothing
        self.assertEqual(trans.transliterate(['B']), 'ণ')  # U+09A3 BENGALI LETTER NNA
        self.assertEqual(trans.transliterate(['G-\\']), '') # Nothing
        self.assertEqual(trans.transliterate(['\\']), '\\')  # U+005C REVERSE SOLIDUS
        self.assertEqual(trans.transliterate(['G-|']), '') # Nothing
        self.assertEqual(trans.transliterate(['|']), '|')  # U+007C VERTICAL LINE
        self.assertEqual(trans.transliterate(['G-{']), '') # Nothing
        self.assertEqual(trans.transliterate(['{']), '{')  # U+007B LEFT CURLY BRACKET
        self.assertEqual(trans.transliterate(['G-}']), '') # Nothing
        self.assertEqual(trans.transliterate(['}']), '}')  # U+007D RIGHT CURLY BRACKET
        self.assertEqual(trans.transliterate(['G-[']), '') # Nothing
        self.assertEqual(trans.transliterate(['[']), '[')  # U+005B LEFT SQUARE BRACKET
        self.assertEqual(trans.transliterate(['G-]']), '') # Nothing
        self.assertEqual(trans.transliterate([']']), ']')  # U+005D RIGHT SQUARE BRACKET
        self.assertEqual(trans.transliterate(['G-C']), 'ঐ') # U+0990 BENGALI LETTER AI
        self.assertEqual(trans.transliterate(['C']), 'ঐ')  # U+0990 BENGALI LETTER AI
        self.assertEqual(trans.transliterate(['*', 'C']), '*ঐ')  # U+0990 BENGALI LETTER AI
        self.assertEqual(trans.transliterate([' ', 'C']), ' ঐ')  # U+0990 BENGALI LETTER AI
        self.assertEqual(trans.transliterate(['j', 'C']), 'কৈ')  # ক U+0995 BENGALI LETTER KA + ৈ U+09C8 BENGALI VOWEL SIGN AI
        self.assertEqual(trans.transliterate(['G-^', 'C']), 'ৎঐ')  # ৎ U+09CE BENGALI LETTER KHANDA TA + ঐ U+0990 BENGALI LETTER A
        self.assertEqual(trans.transliterate(['p', 'C']), 'ড়ৈ')  # ড় U+09DC BENGALI LETTER RRA + ৈ U+09C8 BENGALI VOWEL SIGN AI
        self.assertEqual(trans.transliterate(['P', 'C']), 'ঢ়ৈ')  # ঢ় U+09DD BENGALI LETTER RHA + ৈ U+09C8 BENGALI VOWEL SIGN AI
        self.assertEqual(trans.transliterate(['W', 'C']), 'য়ৈ')  # য় U+09DF BENGALI LETTER YYA + ৈ U+09C8 BENGALI VOWEL SIGN AI
        self.assertEqual(trans.transliterate(['G-^']), 'ৎ') # U+09CE BENGALI LETTER KHANDA TA
        self.assertEqual(trans.transliterate(['^']), '^')  # U+005E CIRCUMFLEX ACCENT
        self.assertEqual(trans.transliterate(['G-:']), '') # Nothing
        self.assertEqual(trans.transliterate([':']), ':')  # U+003A COLON
        self.assertEqual(trans.transliterate(['G-,']), '') # Nothing
        self.assertEqual(trans.transliterate([',']), ',')  # U+002C COMMA
        self.assertEqual(trans.transliterate(['G-D']), 'ঈ') # U+0988 BENGALI LETTER II
        self.assertEqual(trans.transliterate(['D']), 'ঈ')  # U+0988 BENGALI LETTER II
        self.assertEqual(trans.transliterate(['j', 'D']), 'কী')  # ক U+0995 BENGALI LETTER KA + ী U+09C0 BENGALI VOWEL SIGN II
        self.assertEqual(trans.transliterate(['G-$']), '৲') # U+09F2 BENGALI RUPEE MARK
        self.assertEqual(trans.transliterate(['$']), '$')  # U+0024 DOLLAR SIGN
        self.assertEqual(trans.transliterate(['G-E']), '') # Nothing
        self.assertEqual(trans.transliterate(['E']), 'ঢ')  # U+09A2 BENGALI LETTER DDHA
        self.assertEqual(trans.transliterate(['G-=']), '‍') # U+200D ZERO WIDTH JOINER (Only in /usr/share/X11/xkb/symbols/bn)
        self.assertEqual(trans.transliterate(['=']), '=')  # U+003D EQUALS SIGN
        self.assertEqual(trans.transliterate(['G-!']), '') # Nothing
        self.assertEqual(trans.transliterate(['!']), '!')  # U+0021 EXCLAMATION MARK
        self.assertEqual(trans.transliterate(['G-F']), 'ৱ') # U+09F1 BENGALI LETTER RA WITH LOWER DIAGONAL
        self.assertEqual(trans.transliterate(['F']), 'ভ')  # U+09AD BENGALI LETTER BHA
        self.assertEqual(trans.transliterate(['G-G']), '') # Nothing
        self.assertEqual(trans.transliterate(['G']), '।')  # U+0964 DEVANAGARI DANDA
        self.assertEqual(trans.transliterate(['G-`']), '‌') # U+200C ZERO WIDTH NON-JOINER (Only in OpenBangla National_Jatiya.json)
        self.assertEqual(trans.transliterate(['`']), '‌')   # U+200C ZERO WIDTH NON-JOINER (Only in OpenBangla National_Jatiya.json)
        self.assertEqual(trans.transliterate(['G->']), '') # Nothing
        self.assertEqual(trans.transliterate(['>']), '>')  # U+003E GREATER-THAN SIGN
        self.assertEqual(trans.transliterate(['G-H']), '') # Nothing
        self.assertEqual(trans.transliterate(['H']), 'অ')  # U+0985 BENGALI LETTER A
        self.assertEqual(trans.transliterate(['G-#']), '') # Nothing
        self.assertEqual(trans.transliterate(['#']), '#')  # U+0023 NUMBER SIGN
        self.assertEqual(trans.transliterate(['G-I']), '') # Nothing
        self.assertEqual(trans.transliterate(['I']), 'ঞ')  # U+099E BENGALI LETTER NYA
        self.assertEqual(trans.transliterate(['G-J']), '') # Nothing
        self.assertEqual(trans.transliterate(['J']), 'খ')  # U+0996 BENGALI LETTER KHA
        self.assertEqual(trans.transliterate(['G-K']), '') # Nothing
        self.assertEqual(trans.transliterate(['K']), 'থ')  # U+09A5 BENGALI LETTER THA
        self.assertEqual(trans.transliterate(['G-L']), 'ৡ') # U+09E1 BENGALI LETTER VOCALIC LL
        self.assertEqual(trans.transliterate(['L']), 'ধ')  # U+09A7 BENGALI LETTER DHA
        self.assertEqual(trans.transliterate(['G-<']), '') # Nothing
        self.assertEqual(trans.transliterate(['<']), '<')  # U+003C LESS-THAN SIGN
        self.assertEqual(trans.transliterate(['G-M']), '') # Nothing
        self.assertEqual(trans.transliterate(['M']), 'শ')  # U+09B6 BENGALI LETTER SHA
        self.assertEqual(trans.transliterate(['G--']),  '‌') # U+200C ZERO WIDTH NON-JOINER (Only in /usr/share/X11/xkb/symbols/bn)
        self.assertEqual(trans.transliterate(['-']), '-')  # U+002D HYPHEN-MINUS
        self.assertEqual(trans.transliterate(['G-N']), '') # Nothing
        self.assertEqual(trans.transliterate(['N']), 'ষ')  # U+09B7 BENGALI LETTER SSA
        self.assertEqual(trans.transliterate(['G-O']), '') # Nothing
        self.assertEqual(trans.transliterate(['O']), 'ঘ')  # U+0998 BENGALI LETTER GHA
        self.assertEqual(trans.transliterate(['G-P']), '') # Nothing
        self.assertEqual(trans.transliterate(['P']), 'ঢ়')  # U+09DD BENGALI LETTER RHA
        self.assertEqual(trans.transliterate(['G-(']), '') # Nothing
        self.assertEqual(trans.transliterate(['(']), '(')  # U+0028 LEFT PARENTHESIS
        self.assertEqual(trans.transliterate(['G-)']), '') # Nothing
        self.assertEqual(trans.transliterate([')']), ')')  # U+0029 RIGHT PARENTHESIS
        self.assertEqual(trans.transliterate(['G-%']), '') # Nothing
        self.assertEqual(trans.transliterate(['%']), '%')  # U+0025 PERCENT SIGN
        self.assertEqual(trans.transliterate(['G-.']), '়') # U+09BC BENGALI SIGN NUKTA (Only in /usr/share/X11/xkb/symbols/bn)
        self.assertEqual(trans.transliterate(['.']), '.')  # U+002E FULL STOP
        self.assertEqual(trans.transliterate(['G-+']), '') # Nothing
        self.assertEqual(trans.transliterate(['+']), '+')  # U+002B PLUS SIGN
        self.assertEqual(trans.transliterate(['G-Q']), 'ৡ') # U+09E1 BENGALI LETTER VOCALIC LL
        self.assertEqual(trans.transliterate(['j', 'G-Q']), 'কৣ') # ক U+0995 BENGALI LETTER KA + ৣ U+09E3 BENGALI VOWEL SIGN VOCALIC LL
        self.assertEqual(trans.transliterate(['Q']), 'ং')  # U+0982 BENGALI SIGN ANUSVARA
        self.assertEqual(trans.transliterate(['G-?']), '') # Nothing
        self.assertEqual(trans.transliterate(['?']), '?')  # U+003F QUESTION MARK
        self.assertEqual(trans.transliterate(['G-"']), '') # Nothing
        self.assertEqual(trans.transliterate(['"']), '"') # U+0022 QUOTATION MARK
        self.assertEqual(trans.transliterate(['G-R']), '') # Nothing
        self.assertEqual(trans.transliterate(['R']), 'ফ')  # U+09AB BENGALI LETTER PHA
        self.assertEqual(trans.transliterate(['G-S']), 'ঊ') # U+098A BENGALI LETTER UU
        self.assertEqual(trans.transliterate(['S']), 'ঊ')  # U+098A BENGALI LETTER UU
        self.assertEqual(trans.transliterate(['j', 'S']), 'কূ')  # ক U+0995 BENGALI LETTER KA + ূ U+09C2 BENGALI VOWEL SIGN UU
        self.assertEqual(trans.transliterate(['G-;']), '') # Nothing
        self.assertEqual(trans.transliterate([';']), ';')  # U+003B SEMICOLON
        self.assertEqual(trans.transliterate(['G-/']), '') # Nothing
        self.assertEqual(trans.transliterate(['/']), '/')  # U+002F SOLIDUS
        self.assertEqual(trans.transliterate(['G-T']), '') # Nothing
        self.assertEqual(trans.transliterate(['T']), 'ঠ')  # U+09A0 BENGALI LETTER TTHA
        self.assertEqual(trans.transliterate(['G-~']), '‍') # U+200D ZERO WIDTH JOINER (Only in OpenBangla National_Jatiya.json)
        self.assertEqual(trans.transliterate(['~']), '‍')   # U+200D ZERO WIDTH JOINER (Only in OpenBangla National_Jatiya.json)
        self.assertEqual(trans.transliterate(['G-U']), '') # Nothing
        self.assertEqual(trans.transliterate(['U']), 'ঝ')  # U+099D BENGALI LETTER JHA
        self.assertEqual(trans.transliterate(['G-_']), '') # Nothing
        self.assertEqual(trans.transliterate(['_']), '_')  # U+005F LOW LINE
        self.assertEqual(trans.transliterate(['G-V']), '') # Nothing
        self.assertEqual(trans.transliterate(['V']), 'ল')  # U+09B2 BENGALI LETTER LA
        self.assertEqual(trans.transliterate(['G-W']), '') # Nothing
        self.assertEqual(trans.transliterate(['W']), 'য়')  # U+09DF BENGALI LETTER YYA
        self.assertEqual(trans.transliterate(['G-X']), 'ঔ') # U+0994 BENGALI LETTER AU
        self.assertEqual(trans.transliterate(['X']), 'ঔ')  # U+0994 BENGALI LETTER AU
        self.assertEqual(trans.transliterate(['j', 'X']), 'কৌ') # ক U+0995 BENGALI LETTER K + ৌ U+09CC BENGALI VOWEL SIGN AU
        self.assertEqual(trans.transliterate(['G-Y']), '') # Nothing
        self.assertEqual(trans.transliterate(['Y']), 'ছ')  # U+099B BENGALI LETTER CHA
        self.assertEqual(trans.transliterate(['G-Z']), '') # Nothing
        self.assertEqual(trans.transliterate(['Z']), 'ঃ')  # U+0983 BENGALI SIGN VISARGA
        self.assertEqual(trans.transliterate(['G-a']), 'ঋ') # U+098B BENGALI LETTER VOCALIC R
        self.assertEqual(trans.transliterate(['a']), 'ঋ')  # U+098B BENGALI LETTER VOCALIC R
        self.assertEqual(trans.transliterate(['j', 'a']), 'কৃ') # ক U+0995 BENGALI LETTER KA + ৃ U+09C3 BENGALI VOWEL SIGN VOCALIC R
        self.assertEqual(trans.transliterate(['G-b']), '') # Nothing
        self.assertEqual(trans.transliterate(['b']), 'ন')  # U+09A8 BENGALI LETTER NA
        self.assertEqual(trans.transliterate(['G-c']), 'এ') # U+098F BENGALI LETTER E
        self.assertEqual(trans.transliterate(['c']), 'এ')  # U+098F BENGALI LETTER E
        self.assertEqual(trans.transliterate(['j', 'c']), 'কে')  # ক U+0995 BENGALI LETTER KA + ে U+09C7 BENGALI VOWEL SIGN E
        self.assertEqual(trans.transliterate(['G-d']), 'ই') # U+0987 BENGALI LETTER I
        self.assertEqual(trans.transliterate(['d']), 'ই')  # U+0987 BENGALI LETTER I
        self.assertEqual(trans.transliterate(['j', 'd']), 'কি') # ক U+0995 BENGALI LETTER KA + ি U+09BF BENGALI VOWEL SIGN I
        self.assertEqual(trans.transliterate(['G-e']), 'ৠ') # U+09E0 BENGALI LETTER VOCALIC RR
        self.assertEqual(trans.transliterate(['j', 'G-e']), 'কৄ') # ক U+0995 BENGALI LETTER KA + ৄ U+09C4 BENGALI VOWEL SIGN VOCALIC RR
        self.assertEqual(trans.transliterate(['e']), 'ড')  # U+09A1 BENGALI LETTER DDA
        self.assertEqual(trans.transliterate(['G-f']), 'ৰ') # U+09F0 BENGALI LETTER RA WITH MIDDLE DIAGONAL
        self.assertEqual(trans.transliterate(['f']), 'ব')  # U+09AC BENGALI LETTER BA
        self.assertEqual(trans.transliterate(['G-g']), '॥') # U+0965 DEVANAGARI DOUBLE DANDA
        self.assertEqual(trans.transliterate(['G-h']), 'আ') # U+0986 BENGALI LETTER AA
        self.assertEqual(trans.transliterate(['h']), 'আ')  # U+0986 BENGALI LETTER AA
        self.assertEqual(trans.transliterate(['j', 'h']), 'কা')  # ক U+0995 BENGALI LETTER KA + া U+09BE BENGALI VOWEL SIGN AA
        self.assertEqual(trans.transliterate(['G-i']), 'ঽ') # U+09BD BENGALI SIGN AVAGRAHA
        self.assertEqual(trans.transliterate(['i']), 'হ')  # U+09B9 BENGALI LETTER HA
        self.assertEqual(trans.transliterate(['G-j']), '঻') # U+09BB script bengali, not assigned (Only in /usr/share/X11/xkb/symbols/bn)
        self.assertEqual(trans.transliterate(['j']), 'ক')  # U+0995 BENGALI LETTER KA
        self.assertEqual(trans.transliterate(['G-k']), 'ৎ') # U+09CE BENGALI LETTER KHANDA TA (Only in /usr/share/X11/xkb/symbols/bn)
        self.assertEqual(trans.transliterate(['k']), 'ত')  # U+09A4 BENGALI LETTER TA
        self.assertEqual(trans.transliterate(['G-l']), 'ঌ') # U+098C BENGALI LETTER VOCALIC L
        self.assertEqual(trans.transliterate(['l']), 'দ')  # U+09A6 BENGALI LETTER DA
        self.assertEqual(trans.transliterate(['G-m']), '') # Nothing
        self.assertEqual(trans.transliterate(['m']), 'ম')  # U+09AE BENGALI LETTER MA
        self.assertEqual(trans.transliterate(['G-n']), '') # Nothing
        self.assertEqual(trans.transliterate(['n']), 'স')  # U+09B8 BENGALI LETTER SA
        self.assertEqual(trans.transliterate(['G-o']), '') # Nothing
        self.assertEqual(trans.transliterate(['o']), 'গ')  # U+0997 BENGALI LETTER GA
        self.assertEqual(trans.transliterate(['G-p']), '') # Nothing
        self.assertEqual(trans.transliterate(['p']), 'ড়')  # U+09DC BENGALI LETTER RRA
        self.assertEqual(trans.transliterate(['G-q']), 'ঌ') # U+098C BENGALI LETTER VOCALIC L
        self.assertEqual(trans.transliterate(['j', 'G-q']), 'কৢ') # ক U+0995 BENGALI LETTER KA + ৢ U+09E2 BENGALI VOWEL SIGN VOCALIC L
        self.assertEqual(trans.transliterate(['q']), 'ঙ')  # U+0999 BENGALI LETTER NGA
        self.assertEqual(trans.transliterate(['G-r']), '') # Nothing
        self.assertEqual(trans.transliterate(['r']), 'প')  # U+09AA BENGALI LETTER PA
        self.assertEqual(trans.transliterate(['G-s']), 'উ') # U+0989 BENGALI LETTER U
        self.assertEqual(trans.transliterate(['s']), 'উ') # U+0989 BENGALI LETTER U
        self.assertEqual(trans.transliterate(['j', 's']), 'কু') # ক U+0995 BENGALI LETTER KA + ু U+09C1 BENGALI VOWEL SIGN U
        self.assertEqual(trans.transliterate(['G-t']), '') # Nothing
        self.assertEqual(trans.transliterate(['t']), 'ট')  # U+099F BENGALI LETTER TTA
        self.assertEqual(trans.transliterate(['G-u']), '') # Nothing
        self.assertEqual(trans.transliterate(['u']), 'জ')  # U+099C BENGALI LETTER JA
        self.assertEqual(trans.transliterate(['G-v']), '') # Nothing
        self.assertEqual(trans.transliterate(['v']), 'র')  # U+09B0 BENGALI LETTER RA
        self.assertEqual(trans.transliterate(['G-w']), '') # Nothing
        self.assertEqual(trans.transliterate(['w']), 'য')  # U+09AF BENGALI LETTER YA
        self.assertEqual(trans.transliterate(['G-x']), 'ও') # U+0993 BENGALI LETTER O
        self.assertEqual(trans.transliterate(['x']), 'ও') # U+0993 BENGALI LETTER O
        self.assertEqual(trans.transliterate(['j', 'x']), 'কো') # ক U+0995 BENGALI LETTER KA+ ো U+09CB BENGALI VOWEL SIGN O
        self.assertEqual(trans.transliterate(['G-y']), '') # Nothing
        self.assertEqual(trans.transliterate(['y']), 'চ')  # U+099A BENGALI LETTER CA
        self.assertEqual(trans.transliterate(['G-z']), '৺') # U+09FA BENGALI ISSHAR
        self.assertEqual(trans.transliterate(['z']), 'ঁ')  # U+0981 BENGALI SIGN CANDRABINDU
        # dead key:
        self.assertEqual(trans.transliterate(['g']), '্')  # U+09CD BENGALI SIGN VIRAMABENGALI SIGN VIRAMA
        self.assertEqual(trans.transliterate(list('gh')), 'আ')  # + া U+09BE BENGALI VOWEL SIGN AA = আ U+0986 BENGALI LETTER AA
        self.assertEqual(trans.transliterate(list('gd')), 'ই') # + ি U+09BF BENGALI VOWEL SIGN I = ই U+0987 BENGALI LETTER I
        self.assertEqual(trans.transliterate(list('gD')), 'ঈ') # + ী U+09C0 BENGALI VOWEL SIGN II = ঈ U+0988 BENGALI LETTER II
        self.assertEqual(trans.transliterate(list('gs')), 'উ') # + ু U+09C1 BENGALI VOWEL SIGN U = উ U+0989 BENGALI LETTER U
        self.assertEqual(trans.transliterate(list('gS')), 'ঊ') # + ূ U+09C2 BENGALI VOWEL SIGN UU = ঊ U+098A BENGALI LETTER UU
        self.assertEqual(trans.transliterate(list('ga')), 'ঋ') # + ৃ U+09C3 BENGALI VOWEL SIGN VOCALIC R = ঋ U+098B BENGALI LETTER VOCALIC R
        self.assertEqual(trans.transliterate(list('gc')), 'এ') # + ে U+09C7 BENGALI VOWEL SIGN E = এ U+098F BENGALI LETTER E
        self.assertEqual(trans.transliterate(list('gC')), 'ঐ') # + ৈ U+09C8 BENGALI VOWEL SIGN AI = ঐ U+0990 BENGALI LETTER AI
        self.assertEqual(trans.transliterate(list('gx')), 'ও') # + ো U+09CB BENGALI VOWEL SIGN O = ও U+0993 BENGALI LETTER O
        self.assertEqual(trans.transliterate(list('gX')), 'ঔ') # + ৌ U+09CC BENGALI VOWEL SIGN AU = ঔ U+0994 BENGALI LETTER AU
        self.assertEqual(trans.transliterate(list('gG')), '॥') # + । U+0964 DEVANAGARI DANDA = ॥ U+0965 DEVANAGARI DOUBLE DANDA
        # pylint: enable=line-too-long

    def test_get_variables_bn_national_jatiya(self) -> None:
        trans = self.get_transliterator_or_skip('bn-national-jatiya')
        self.assertEqual(
            trans.get_variables(),
            [('use-automatic-vowel-forming',
              'If this variable is 1 (the default), automatic vowel forming is used.\n'
              'For example, a dependent vowel like া is automatically converted to\n'
              'the independent form আ if it is not typed after a consonant.',
              '1')])

    def test_get_variables_ath_phonetic(self) -> None:
        trans = self.get_transliterator_or_skip('ath-phonetic')
        self.assertEqual(
            trans.get_variables(),
            [('s-bridge-below', 'private use', '58283')])

    def test_get_variables_bo_ewts(self) -> None:
        trans = self.get_transliterator_or_skip('bo-ewts')
        self.assertEqual(
            trans.get_variables(),
            [('precomposed',
              'Flag to tell whether or not to generate precomposed characters.\n'
              'If 1 (the default), generate precomposed characters (i.e. NFC) if available '
              '(e.g. "ྲྀ"(U+0F76).\n'
              'If 0, generate only decomposed characters (i.e. NFD) (e.g. "ྲྀ" (U+0FB2 '
              'U+0F80).',
              '1')])

    def test_get_variables_hi_itrans(self) -> None:
        trans = self.get_transliterator_or_skip('hi-itrans')
        self.assertEqual(
            trans.get_variables(),
            [('trim-last-halant',
              'If this variable is 1 (the default), the last Halant in a syllable\n'
              'is removed if it is followed by non Devanagari letter.  For instance,\n'
              'typing "har.." produces "हर।", not "हर्।".',
              '1')])

    def test_get_variables_ja_anthy(self) -> None:
        trans = self.get_transliterator_or_skip('ja-anthy')
        self.assertEqual(
            trans.get_variables(),
            [('input-mode',
              'Hiragana or Katakana (not yet implemented)\nSelect Hiragana or Katakana',
              'hiragana'),
             ('zen-han', 'Zenkaku or Hankaku (not yet implemented)', 'zenkaku')])

    @unittest.skipUnless(
        M17N_DB_VERSION >= (1, 8, 2),
        'Skipping because m17n-db is too old')
    def test_get_variables_ml_swanalekha(self) -> None:
        trans = self.get_transliterator_or_skip('ml-swanalekha')
        self.assertEqual(
            trans.get_variables(),
            [('candidates-group-size',
              'Maximum number of candidates in a candidate group.\n'
              'Value must be an integer.\n'
              'If the value is not positive, number of candidates in a group is decided\n'
              'by how candiates are grouped in an input method source file.',
              '10'),
             ('show-lookup', 'Show lookup table', '0')])

    def test_get_variables_mr_gamabhana(self) -> None:
        trans = self.get_transliterator_or_skip('mr-gamabhana')
        self.assertEqual(
            trans.get_variables(),
            [('trim-last-halant',
              'If this variable is 1 (the default), the last Halant in a syllable\n'
              'is removed if it is followed by non Devanagari letter.  For instance,\n'
              'typing "har.." produces "हर।", not "हर्।".',
              '1')])

    def test_get_variables_oj_phonetic(self) -> None:
        trans = self.get_transliterator_or_skip('oj-phonetic')
        self.assertEqual(
            trans.get_variables(),
            [('i-style-p', 'unofficial', '43502'),
             ('i-style-t', 'unofficial', '43503'),
             ('i-style-k', 'unofficial', '43504'),
             ('i-style-c', 'unofficial', '43505'),
             ('i-style-m', 'unofficial', '43506'),
             ('i-style-n', 'unofficial', '43507'),
             ('i-style-s', 'unofficial', '43508'),
             ('i-style-sh', 'unofficial', '43509')])

    def test_get_variables_sa_itrans(self) -> None:
        trans = self.get_transliterator_or_skip('sa-itrans')
        self.assertEqual(
            trans.get_variables(),
            [('trim-last-halant', '', '0'), ('enable-udatta', '', '1')])

    def test_get_variables_si_wijesekera(self) -> None:
        trans = self.get_transliterator_or_skip('si-wijesekera')
        self.assertEqual(
            trans.get_variables(),
            [('use-surrounding-text',
              'Surrounding text vs. preedit.\n'
              'If 1, try to use surrounding text.  Otherwise, use preedit.',
              '0')])

    def test_get_variables_ta_lk_renganathan(self) -> None:
        trans = self.get_transliterator_or_skip('ta-lk-renganathan')
        self.assertEqual(
            trans.get_variables(),
            [('use-surrounding-text',
              'Surrounding text vs. preedit\n'
              'If 1, try to use surrounding text.  Otherwise, use preedit.',
              '0')])

    def test_get_variables_th_kesmanee(self) -> None:
        trans = self.get_transliterator_or_skip('th-kesmanee')
        self.assertEqual(
            trans.get_variables(),
            [('level',
              'Acceptance level\n'
              'The level of character sequence acceptance defined in WTT 2.0.\n'
              '0 accepts any key sequence.  2 accepts only orthographic ones.\n'
              '1 is somewhere between.',
              '1')])

    def test_get_variables_th_pattachote(self) -> None:
        trans = self.get_transliterator_or_skip('th-pattachote')
        self.assertEqual(
            trans.get_variables(),
            [('level',
              'Acceptance level\n'
              'The level of character sequence acceptance defined in WTT 2.0.\n'
              '0 accepts any key sequence.  2 accepts only orthographic ones.\n'
              '1 is somewhere between.',
              '1')])

    def test_get_variables_th_tis820(self) -> None:
        trans = self.get_transliterator_or_skip('th-tis820')
        self.assertEqual(
            trans.get_variables(),
            [('level',
              'Acceptance level\n'
              'The level of character sequence acceptance defined in WTT 2.0.\n'
              '0 accepts any key sequence.  2 accepts only orthographic ones.\n'
              '1 is somewhere between.',
              '1')])

    def test_get_variables_t_unicode(self) -> None:
        trans = self.get_transliterator_or_skip('t-unicode')
        self.assertEqual(
            trans.get_variables(),
            [('prompt',
              'Preedit prompt\n'
              'Prompt string shown in the preedit area while typing hexadecimal numbers.',
              'U+')])

    @unittest.skipUnless(
        M17N_DB_VERSION >= (1, 8, 2),
        'Skipping because m17n-db is too old')
    def test_get_variables_vi_han(self) -> None:
        trans = self.get_transliterator_or_skip('vi-han')
        self.assertEqual(
            trans.get_variables(),
            [('candidates-group-size',
              'Maximum number of candidates in a candidate group.\n'
              'Value must be an integer.\n'
              'If the value is not positive, number of candidates in a group is decided\n'
              'by how candiates are grouped in an input method source file.',
              '10')])

    @unittest.skipUnless(
        M17N_DB_VERSION >= (1, 8, 2),
        'Skipping because m17n-db is too old')
    def test_get_variables_vi_nomvni(self) -> None:
        trans = self.get_transliterator_or_skip('vi-nomvni')
        self.assertEqual(
            trans.get_variables(),
            [('candidates-group-size',
              'Maximum number of candidates in a candidate group.\n'
              'Value must be an integer.\n'
              'If the value is not positive, number of candidates in a group is decided\n'
              'by how candiates are grouped in an input method source file.',
              '10')])

    @unittest.skipUnless(
        M17N_DB_VERSION >= (1, 8, 2),
        'Skipping because m17n-db is too old')
    def test_get_variables_vi_nomtelex(self) -> None:
        trans = self.get_transliterator_or_skip('vi-nomtelex')
        self.assertEqual(
            trans.get_variables(),
            [('candidates-group-size',
              'Maximum number of candidates in a candidate group.\n'
              'Value must be an integer.\n'
              'If the value is not positive, number of candidates in a group is decided\n'
              'by how candiates are grouped in an input method source file.',
              '10')])

    def test_get_variables_vi_tcvn(self) -> None:
        trans = self.get_transliterator_or_skip('vi-tcvn')
        self.assertEqual(
            trans.get_variables(),
            [('tone-mark-on-last',
              'Flag to control tone mark position in equivocal cases.\n'
              'If this variable is 0 (the default), put tone mark on the first vowel\n'
              'in such equivocal cases as "oa", "oe", "uy".\n'
              'Otherwise, put tone mark on the last vowel.',
              '0'),
             ('backspace-is-undo',
              'Flag to control the action of Backspace key (delete or undo).\n'
              'If this variable is 0 (the default), Backspace key deletes the previous\n'
              'character (e.g. "q u a i s BS" => "quá").\n'
              'If the value is 1, Backspace key undoes the previous key\n'
              '(e.g. "q u a i s BS" => "quai").',
              '0')])

    def test_get_variables_vi_telex(self) -> None:
        trans = self.get_transliterator_or_skip('vi-telex')
        self.assertEqual(
            trans.get_variables(),
            [('tone-mark-on-last',
              'Flag to control tone mark position in equivocal cases.\n'
              'If this variable is 0 (the default), put tone mark on the first vowel\n'
              'in such equivocal cases as "oa", "oe", "uy".\n'
              'Otherwise, put tone mark on the last vowel.',
              '0'),
             ('backspace-is-undo',
              'Flag to control the action of Backspace key (delete or undo).\n'
              'If this variable is 0 (the default), Backspace key deletes the previous\n'
              'character (e.g. "q u a i s BS" => "quá").\n'
              'If the value is 1, Backspace key undoes the previous key\n'
              '(e.g. "q u a i s BS" => "quai").',
              '0')])

    def test_get_variables_vi_viqr(self) -> None:
        trans = self.get_transliterator_or_skip('vi-viqr')
        self.assertEqual(
            trans.get_variables(),
            [('tone-mark-on-last',
              'Flag to control tone mark position in equivocal cases.\n'
              'If this variable is 0 (the default), put tone mark on the first vowel\n'
              'in such equivocal cases as "oa", "oe", "uy".\n'
              'Otherwise, put tone mark on the last vowel.',
              '0'),
             ('backspace-is-undo',
              'Flag to control the action of Backspace key (delete or undo).\n'
              'If this variable is 0 (the default), Backspace key deletes the previous\n'
              'character (e.g. "q u a i s BS" => "quá").\n'
              'If the value is 1, Backspace key undoes the previous key\n'
              '(e.g. "q u a i s BS" => "quai").',
              '0')])

    def test_get_variables_vi_vni(self) -> None:
        trans = self.get_transliterator_or_skip('vi-vni')
        self.assertEqual(
            trans.get_variables(),
            [('tone-mark-on-last',
              'Flag to control tone mark position in equivocal cases.\n'
              'If this variable is 0 (the default), put tone mark on the first vowel\n'
              'in such equivocal cases as "oa", "oe", "uy".\n'
              'Otherwise, put tone mark on the last vowel.',
              '0'),
             ('backspace-is-undo',
              'Flag to control the action of Backspace key (delete or undo).\n'
              'If this variable is 0 (the default), Backspace key deletes the previous\n'
              'character (e.g. "q u a i s BS" => "quá").\n'
              'If the value is 1, Backspace key undoes the previous key\n'
              '(e.g. "q u a i s BS" => "quai").',
              '0')])

    @unittest.skipUnless(
        M17N_DB_VERSION >= (1, 8, 2),
        'Skipping because m17n-db is too old')
    def test_get_variables_zh_cangjie(self) -> None:
        trans = self.get_transliterator_or_skip('zh-cangjie')
        self.assertEqual(
            trans.get_variables(),
            [('candidates-group-size',
              'Maximum number of candidates in a candidate group.\n'
              'Value must be an integer.\n'
              'If the value is not positive, number of candidates in a group is decided\n'
              'by how candiates are grouped in an input method source file.',
              '10')])

    @unittest.skipUnless(
        M17N_DB_VERSION >= (1, 8, 2),
        'Skipping because m17n-db is too old')
    def test_get_variables_zh_py_b5(self) -> None:
        trans = self.get_transliterator_or_skip('zh-py-b5')
        self.assertEqual(
            trans.get_variables(),
            [('candidates-group-size',
              'Maximum number of candidates in a candidate group.\n'
              'Value must be an integer.\n'
              'If the value is not positive, number of candidates in a group is decided\n'
              'by how candiates are grouped in an input method source file.',
              '10'),
             ('candidates-charset',
              'Character set to limit candidates.\n'
              'Value must be a symbol representing a charater set, or nil.\n'
              'If the value is not nil, a candidate containing a character not belonging\n'
              'to the specified character set is ignored.',
              'big5')])

    @unittest.skipUnless(
        M17N_DB_VERSION >= (1, 8, 2),
        'Skipping because m17n-db is too old')
    def test_get_variables_zh_py_gb(self) -> None:
        trans = self.get_transliterator_or_skip('zh-py-gb')
        self.assertEqual(
            trans.get_variables(),
            [('candidates-group-size',
              'Maximum number of candidates in a candidate group.\n'
              'Value must be an integer.\n'
              'If the value is not positive, number of candidates in a group is decided\n'
              'by how candiates are grouped in an input method source file.',
              '10'),
             ('candidates-charset',
              'Character set to limit candidates.\n'
              'Value must be a symbol representing a charater set, or nil.\n'
              'If the value is not nil, a candidate containing a character not belonging\n'
              'to the specified character set is ignored.',
              'gb2312.1980')])

    @unittest.skipUnless(
        M17N_DB_VERSION >= (1, 8, 2),
        'Skipping because m17n-db is too old')
    def test_get_variables_zh_py(self) -> None:
        trans = self.get_transliterator_or_skip('zh-py')
        self.assertEqual(
            trans.get_variables(),
            [('candidates-group-size',
              'Maximum number of candidates in a candidate group.\n'
              'Value must be an integer.\n'
              'If the value is not positive, number of candidates in a group is decided\n'
              'by how candiates are grouped in an input method source file.',
              '10')])

    @unittest.skipUnless(
        M17N_DB_VERSION >= (1, 8, 2),
        'Skipping because m17n-db is too old')
    def test_get_variables_zh_quick(self) -> None:
        trans = self.get_transliterator_or_skip('zh-quick')
        self.assertEqual(
            trans.get_variables(),
            [('candidates-group-size',
              'Maximum number of candidates in a candidate group.\n'
              'Value must be an integer.\n'
              'If the value is not positive, number of candidates in a group is decided\n'
              'by how candiates are grouped in an input method source file.',
              '10')])

    @unittest.skipUnless(
        M17N_DB_VERSION >= (1, 8, 2),
        'Skipping because m17n-db is too old')
    def test_get_variables_zh_tonepy_b5(self) -> None:
        trans = self.get_transliterator_or_skip('zh-tonepy-b5')
        self.assertEqual(
            trans.get_variables(),
            [('candidates-group-size',
              'Maximum number of candidates in a candidate group.\n'
              'Value must be an integer.\n'
              'If the value is not positive, number of candidates in a group is decided\n'
              'by how candiates are grouped in an input method source file.',
              '10'),
             ('candidates-charset',
              'Character set to limit candidates.\n'
              'Value must be a symbol representing a charater set, or nil.\n'
              'If the value is not nil, a candidate containing a character not belonging\n'
              'to the specified character set is ignored.',
              'big5')])

    @unittest.skipUnless(
        M17N_DB_VERSION >= (1, 8, 2),
        'Skipping because m17n-db is too old')
    def test_get_variables_zh_tonepy_gb(self) -> None:
        trans = self.get_transliterator_or_skip('zh-tonepy-gb')
        self.assertEqual(
            trans.get_variables(),
            [('candidates-group-size',
              'Maximum number of candidates in a candidate group.\n'
              'Value must be an integer.\n'
              'If the value is not positive, number of candidates in a group is decided\n'
              'by how candiates are grouped in an input method source file.',
              '10'),
             ('candidates-charset',
              'Character set to limit candidates.\n'
              'Value must be a symbol representing a charater set, or nil.\n'
              'If the value is not nil, a candidate containing a character not belonging\n'
              'to the specified character set is ignored.',
              'gb2312.1980')])

    @unittest.skipUnless(
        M17N_DB_VERSION >= (1, 8, 2),
        'Skipping because m17n-db is too old')
    def test_get_variables_zh_tonepy(self) -> None:
        trans = self.get_transliterator_or_skip('zh-tonepy')
        self.assertEqual(
            trans.get_variables(),
            [('candidates-group-size',
              'Maximum number of candidates in a candidate group.\n'
              'Value must be an integer.\n'
              'If the value is not positive, number of candidates in a group is decided\n'
              'by how candiates are grouped in an input method source file.',
              '10')])

    @unittest.skipUnless(
        M17N_DB_VERSION >= (1, 8, 2),
        'Skipping because m17n-db is too old')
    def test_get_variables_zh_zhuyin(self) -> None:
        trans = self.get_transliterator_or_skip('zh-zhuyin')
        self.assertEqual(
            trans.get_variables(),
            [('candidates-group-size',
              'Maximum number of candidates in a candidate group.\n'
              'Value must be an integer.\n'
              'If the value is not positive, number of candidates in a group is decided\n'
              'by how candiates are grouped in an input method source file.',
              '10')])

    def test_set_variables(self) -> None:
        trans_bn_national_jatiya = self.get_transliterator_or_skip('bn-national-jatiya')
        trans_t_unicode = self.get_transliterator_or_skip('t-unicode')
        trans_ja_anthy = self.get_transliterator_or_skip('ja-anthy')
        self.assertEqual(
            trans_bn_national_jatiya.get_variables(),
            [('use-automatic-vowel-forming',
              'If this variable is 1 (the default), automatic vowel forming is used.\n'
              'For example, a dependent vowel like া is automatically converted to\n'
              'the independent form আ if it is not typed after a consonant.',
              '1')])
        self.assertEqual(
            trans_t_unicode.get_variables(),
            [('prompt',
              'Preedit prompt\n'
              'Prompt string shown in the preedit area while typing hexadecimal numbers.',
              'U+')])
        self.assertEqual(
            trans_ja_anthy.get_variables(),
            [('input-mode',
              'Hiragana or Katakana (not yet implemented)\nSelect Hiragana or Katakana',
              'hiragana'),
             ('zen-han', 'Zenkaku or Hankaku (not yet implemented)', 'zenkaku')])
        trans_bn_national_jatiya.set_variables({'use-automatic-vowel-forming': '0'})
        self.assertEqual(
            trans_bn_national_jatiya.get_variables(),
            [('use-automatic-vowel-forming',
              'If this variable is 1 (the default), automatic vowel forming is used.\n'
              'For example, a dependent vowel like া is automatically converted to\n'
              'the independent form আ if it is not typed after a consonant.',
              '0')])
        self.assertEqual(
            trans_t_unicode.get_variables(),
            [('prompt',
              'Preedit prompt\n'
              'Prompt string shown in the preedit area while typing hexadecimal numbers.',
              'U+')])
        self.assertEqual(
            trans_ja_anthy.get_variables(),
            [('input-mode',
              'Hiragana or Katakana (not yet implemented)\nSelect Hiragana or Katakana',
              'hiragana'),
             ('zen-han', 'Zenkaku or Hankaku (not yet implemented)', 'zenkaku')])
        trans_t_unicode.set_variables({'prompt': 'U_'})
        self.assertEqual(
            trans_bn_national_jatiya.get_variables(),
            [('use-automatic-vowel-forming',
              'If this variable is 1 (the default), automatic vowel forming is used.\n'
              'For example, a dependent vowel like া is automatically converted to\n'
              'the independent form আ if it is not typed after a consonant.',
              '0')])
        self.assertEqual(
            trans_t_unicode.get_variables(),
            [('prompt',
              'Preedit prompt\n'
              'Prompt string shown in the preedit area while typing hexadecimal numbers.',
              'U_')])
        self.assertEqual(
            trans_ja_anthy.get_variables(),
            [('input-mode',
              'Hiragana or Katakana (not yet implemented)\nSelect Hiragana or Katakana',
              'hiragana'),
             ('zen-han', 'Zenkaku or Hankaku (not yet implemented)', 'zenkaku')])
        trans_ja_anthy.set_variables({'input-mode': 'katakana', 'zen-han': 'hankaku'})
        self.assertEqual(
            trans_bn_national_jatiya.get_variables(),
            [('use-automatic-vowel-forming',
              'If this variable is 1 (the default), automatic vowel forming is used.\n'
              'For example, a dependent vowel like া is automatically converted to\n'
              'the independent form আ if it is not typed after a consonant.',
              '0')])
        self.assertEqual(
            trans_t_unicode.get_variables(),
            [('prompt',
              'Preedit prompt\n'
              'Prompt string shown in the preedit area while typing hexadecimal numbers.',
              'U_')])
        self.assertEqual(
            trans_ja_anthy.get_variables(),
            [('input-mode',
              'Hiragana or Katakana (not yet implemented)\nSelect Hiragana or Katakana',
              'katakana'),
             ('zen-han', 'Zenkaku or Hankaku (not yet implemented)', 'hankaku')])
        with open(M17N_CONFIG_FILE, mode='rt', encoding='utf-8') as config_file:
            config_file_contents = config_file.read()
        self.assertEqual(
            config_file_contents,
            ';; -*- mode:lisp; coding:utf-8 -*-\n'
            '((input-method bn national-jatiya)\n'
            ' (variable\n'
            '  (use-automatic-vowel-forming nil 0)))\n'
            '((input-method t unicode)\n'
            ' (variable\n'
            '  (prompt nil\n'
            '   "U_")))\n'
            '((input-method ja anthy)\n'
            ' (variable\n'
            '  (input-mode nil katakana)\n'
            '  (zen-han nil hankaku)))\n'
            )
        # Now set the default values again:
        trans_bn_national_jatiya.set_variables({'use-automatic-vowel-forming': '1'})
        trans_t_unicode.set_variables({'prompt': 'U+'})
        trans_ja_anthy.set_variables({'input-mode': 'hiragana', 'zen-han': 'zenkaku'})
        with open(M17N_CONFIG_FILE, mode='rt', encoding='utf-8') as config_file:
            config_file_contents = config_file.read()
        self.assertEqual(
            config_file_contents,
            ';; -*- mode:lisp; coding:utf-8 -*-\n'
            '((input-method bn national-jatiya)\n'
            ' (variable\n'
            '  (use-automatic-vowel-forming nil 1)))\n'
            '((input-method t unicode)\n'
            ' (variable\n'
            '  (prompt nil\n'
            '   "U+")))\n'
            '((input-method ja anthy)\n'
            ' (variable\n'
            '  (input-mode nil hiragana)\n'
            '  (zen-han nil zenkaku)))\n'
            )
        # Now set the *global* default values by setting empty values:
        trans_bn_national_jatiya.set_variables({'use-automatic-vowel-forming': ''})
        trans_t_unicode.set_variables({'prompt': ''})
        trans_ja_anthy.set_variables({'input-mode': '', 'zen-han': ''})
        # Setting the *global* default values like this should make the config
        # file empty (except for the comment line at the top):
        with open(M17N_CONFIG_FILE, mode='rt', encoding='utf-8') as config_file:
            config_file_contents = config_file.read()
        self.assertEqual(
            config_file_contents,
            ';; -*- mode:lisp; coding:utf-8 -*-\n'
            )

    def test_set_variables_reload_input_method(self) -> None:
        trans = self.get_transliterator_or_skip('bn-national-jatiya')
        self.assertEqual(
            trans.get_variables(),
            [('use-automatic-vowel-forming',
              'If this variable is 1 (the default), automatic vowel forming is used.\n'
              'For example, a dependent vowel like া is automatically converted to\n'
              'the independent form আ if it is not typed after a consonant.',
              '1')])
        self.assertEqual(trans.transliterate(['a']), 'ঋ')  # U+098B BENGALI LETTER VOCALIC R
        trans.set_variables({'use-automatic-vowel-forming': '0'})
        with open(M17N_CONFIG_FILE, mode='rt', encoding='utf-8') as config_file:
            config_file_contents = config_file.read()
        self.assertEqual(
            config_file_contents,
            ';; -*- mode:lisp; coding:utf-8 -*-\n'
            '((input-method bn national-jatiya)\n'
            ' (variable\n'
            '  (use-automatic-vowel-forming nil 0)))\n'
            )
        # Changing the variable has an immediate effect on the already existing
        # trans object:
        self.assertEqual(trans.transliterate(['a']), 'ৃ')  # U+09C3 BENGALI VOWEL SIGN VOCALIC R
        # reinitialize m17n_translit:
        m17n_translit.fini()
        m17n_translit.init()
        # using the old trans for example like
        # trans.transliterate(['a']) would segfault now, we need to
        # get a new object and check that it uses the new variable
        # value as well:
        trans = self.get_transliterator_or_skip('bn-national-jatiya')
        self.assertEqual(trans.transliterate(['a']), 'ৃ')  # U+09C3 BENGALI VOWEL SIGN VOCALIC R
        # set the default again:
        trans.set_variables({'use-automatic-vowel-forming': ''})
        # Setting the *global* default value like this should make the config
        # file empty (except for the comment line at the top):
        with open(M17N_CONFIG_FILE, mode='rt', encoding='utf-8') as config_file:
            config_file_contents = config_file.read()
        self.assertEqual(
            config_file_contents,
            ';; -*- mode:lisp; coding:utf-8 -*-\n'
            )
        # Again the change has an immediate effect of the existing trans object:
        self.assertEqual(trans.transliterate(['a']), 'ঋ')  # U+098B BENGALI LETTER VOCALIC R
        # reinitialize m17n_translit:
        m17n_translit.fini()
        m17n_translit.init()
        # using the old trans for example like
        # trans.transliterate(['a']) would segfault now, we need to
        # get a new object and check that it uses the new variable
        # value as well:
        trans = self.get_transliterator_or_skip('bn-national-jatiya')
        self.assertEqual(trans.transliterate(['a']), 'ঋ')  # U+098B BENGALI LETTER VOCALIC R

if __name__ == '__main__':
    unittest.main()
