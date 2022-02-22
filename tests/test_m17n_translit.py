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
import unittest

from gi import require_version # type: ignore
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore

sys.path.insert(0, "../engine")
import itb_util
import m17n_translit
from m17n_translit import Transliterator
sys.path.pop(0)

class M17nTranslitTestCase(unittest.TestCase):
    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def get_transliterator_or_skip(self, ime: str) -> Any:
        try:
            sys.stderr.write('ime "%s" ... ' %ime)
            trans = Transliterator(ime)
        except ValueError as error:
            trans = None
            self.skipTest(error)
        except Exception as error:
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
            dummy_trans = Transliterator('ru-translitx')
        except ValueError:
            pass
        except Exception:
            # Something unexpected happened:
            self.assertTrue(False)

    def test_ru_translit(self) -> None:
        trans = Transliterator('ru-translit')
        self.assertEqual(trans.transliterate(list('y')), 'ы')
        self.assertEqual(trans.transliterate(list('yo')), 'ё')
        self.assertEqual(trans.transliterate(list('yo y')), 'ё ы')

    def test_mr_itrans(self) -> None:
        trans = Transliterator('mr-itrans')
        self.assertEqual(trans.transliterate(list('praviN')), 'प्रविण्')
        self.assertEqual(trans.transliterate(list('namaste')), 'नमस्ते')

    def test_hi_itrans(self) -> None:
        trans = Transliterator('hi-itrans')
        self.assertEqual(trans.transliterate(list('namaste')), 'नमस्ते')
        self.assertEqual(trans.transliterate(list('. ')), '। ')

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
        trans = Transliterator('t-latn-post')
        self.assertEqual(trans.transliterate(list('gru"n')), 'grün')

    def test_NoIME(self) -> None:
        trans = Transliterator('NoIME')
        self.assertEqual(
            trans.transliterate(['a', 'b', 'c', 'C-c', 'G-4']),
            'abcC-cG-4')

    def test_si_wijesekera(self) -> None:
        trans = Transliterator('si-wijesekera')
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

if __name__ == '__main__':
    unittest.main()
