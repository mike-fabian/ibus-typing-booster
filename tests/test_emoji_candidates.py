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
This file implements test cases for emoji candidates
'''

import sys
import logging
import unittest

from gi import require_version # type: ignore
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore

LOGGER = logging.getLogger('ibus-typing-booster')

import testutils

sys.path.insert(0, "../engine")
import itb_util
import itb_emoji
sys.path.pop(0)

# Set the domain name to something invalid to avoid using
# the translations for the doctest tests. Translations may
# make the tests fail just because some translations are
# added, changed, or missing.
itb_emoji.DOMAINNAME = ''

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

@unittest.skipIf(
    '..' not in itb_emoji.find_cldr_annotation_path('en'),
    'Using external emoji annotations: %s '
    % itb_emoji.find_cldr_annotation_path('en')
    + 'Testing with older emoji annotations instead '
    'of those included in the ibus-typing-booster source is likely '
    'to create meaningless test failures.')
class EmojiCandidatesTestCase(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        LOGGER.info("itb_emoji.find_cldr_annotation_path('en')->%s",
                    itb_emoji.find_cldr_annotation_path('en'))

    def tearDown(self):
        pass

    def test_dummy(self):
        self.assertEqual(True, True)

    def test_candidates_empty_query(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['fr_FR'])
        self.assertEqual(mq.candidates(''), [])

    def test_candidates_empty_language_list(self):
        '''
        Emoji matching with an empty language list should fall back to English.
        '''
        mq = itb_emoji.EmojiMatcher(
            languages = [])
        self.assertEqual(
            mq.candidates('orangutan', match_limit=1)[0][0],
            '🦧')
        mq = itb_emoji.EmojiMatcher(
            languages = ['en'])
        self.assertEqual(
            mq.candidates('orangutan', match_limit=1)[0][0],
            '🦧')

    def test_candidates_similar_emoji(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        # pylint: disable=line-too-long
        self.assertEqual(
            mq.candidates('😺', match_limit=3),
            [('😺', 'smiling cat face with open mouth [😺, So, people, cat, face, mouth, open, smile, grinning]', 9), ('😆', 'smiling face with open mouth and tightly-closed eyes [So, people, face, mouth, open, smile]', 6), ('😄', 'smiling face with open mouth and smiling eyes [So, people, face, mouth, open, smile]', 6)]
        )
        # pylint: enable=line-too-long

    def test_candidates_japanese_full_width_low_line(self):
        # ＿ U+FF3F FULLWIDTH LOW LINE should not disturb the match
        mq = itb_emoji.EmojiMatcher(languages = ['ja_JP'])
        self.assertEqual(
            mq.candidates('ネコ')[0][:2],
            ('🐈', 'ネコ'))
        self.assertEqual(
            mq.candidates('ネコ＿')[0][:2],
            ('🐈', 'ネコ'))

    def test_candidates_multilingual(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        self.assertEqual(
            mq.candidates('ant')[0][:2],
            ('🐜', 'ant'))
        self.assertEqual(
            mq.candidates('ameise')[0][:2],
            ('🐜', 'Ameise'))
        self.assertEqual(
            mq.candidates('Ameise')[0][:2],
            ('🐜', 'Ameise'))
        self.assertEqual(
            mq.candidates('formica')[0][:2],
            ('🐜', 'formica'))
        self.assertEqual(
            mq.candidates('hormiga')[0][:2],
            ('🐜', 'hormiga'))
        self.assertEqual(
            mq.candidates('cacca')[0][:2],
            ('💩', 'cacca'))
        self.assertEqual(
            mq.candidates('orso')[0][:2],
            ('🐻', 'orso'))
        self.assertEqual(
            mq.candidates('lupo')[0][:2],
            ('🐺', 'lupo'))
        self.assertEqual(
            mq.candidates('gatto')[0][:2],
            ('🐈', 'gatto'))
        self.assertEqual(
            mq.candidates('gatto sorride')[0][:2],
            ('😺', 'gatto che sorride'))
        self.assertEqual(
            mq.candidates('halo')[0][:2],
            ('😇', 'smiling face with halo'))
        self.assertEqual(
            mq.candidates('factory')[0][:2],
            ('🏭', 'factory'))

    def test_candidates_white_space_and_underscores(self):
        # Any white space and '_' can be used to separate keywords in the
        # query string:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        self.assertEqual(
            mq.candidates('gatto_	 sorride')[0][:2],
            ('😺', 'gatto che sorride'))
        self.assertEqual(
            mq.candidates('nerd glasses')[0][:2],
            ('🤓', 'nerd face'))
        self.assertEqual(
            mq.candidates('smiling face sun glasses')[0][:2],
            ('😎', 'smiling face with sunglasses'))

    def test_candidates_skin_tones(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        self.assertEqual(
            mq.candidates('man tone5')[0][:2],
            ('👨🏿', 'man: dark skin tone “man tone5”'))
        self.assertEqual(
            mq.candidates('skin tone')[0][:2],
            ('🏻', 'emoji modifier fitzpatrick type-1-2 “tone1” [skin tone]'))
        self.assertEqual(
            mq.candidates('tone1')[0][:2],
            ('🏻', 'emoji modifier fitzpatrick type-1-2 “tone1”'))
        self.assertEqual(
            mq.candidates('tone5')[0][:2],
            ('🏿', 'emoji modifier fitzpatrick type-6 “tone5”'))

    def test_candidates_some_letters(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        self.assertEqual(
            mq.candidates('a')[0][:2],
            ('🅰\ufe0f', 'negative squared latin capital letter a'))
        self.assertEqual(
            mq.candidates('squared a')[0][:2],
            ('🅰\ufe0f', 'negative squared latin capital letter a'))
        self.assertEqual(
            mq.candidates('squared capital a')[0][:2],
            ('🅰\ufe0f', 'negative squared latin capital letter a'))
        self.assertEqual(
            mq.candidates('c')[0][:2],
            ('©️', 'copyright sign'))

    def test_candidates_flags(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        self.assertEqual(
            mq.candidates('us')[0][:2],
            ('🇺🇸', 'flag: united states “us”'))
        self.assertEqual(
            mq.candidates('flag us')[0][:2],
            ('🇺🇸', 'flag: united states “us”'))
        self.assertEqual(
            mq.candidates('united states')[0][:2],
            ('🇺🇸', 'flag: united states'))
        self.assertEqual(
            mq.candidates('united')[0][:2],
            ('🇦🇪', 'flag: united arab emirates'))
        self.assertEqual(
            mq.candidates('united minor outlying islands')[0][:2],
            ('🇺🇲', 'flag: u.s. outlying islands'))
        self.assertEqual(
            mq.candidates('united arab')[0][:2],
            ('🇦🇪', 'flag: united arab emirates'))
        self.assertEqual(
            mq.candidates('mm')[0][:2],
            ('🇲🇲', 'flag: myanmar (burma) “mm”'))
        self.assertEqual(
            mq.candidates('flag mm')[0][:2],
            ('🇲🇲', 'flag: myanmar (burma) “mm”'))
        self.assertEqual(
            mq.candidates('myanmar')[0][:2],
            ('🇲🇲', 'flag: myanmar (burma) “myanmar burma”'))
        self.assertEqual(
            mq.candidates('sj')[0][:2],
            ('🇸🇯', 'flag: svalbard & jan mayen “sj”'))
        self.assertEqual(
            mq.candidates('flag sj')[0][:2],
            ('🇸🇯', 'flag: svalbard & jan mayen “sj”'))
        self.assertEqual(
            mq.candidates('svalbard')[0][:2],
            ('🇸🇯', 'flag: svalbard & jan mayen'))
        self.assertEqual(
            mq.candidates('jan mayen')[0][:2],
            ('🇸🇯', 'flag: svalbard & jan mayen'))
        self.assertEqual(
            mq.candidates('mayen')[0][:2],
            ('🇸🇯', 'flag: svalbard & jan mayen'))

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        testutils.enchant_working_as_expected(),
        'Skipping because of an unexpected change in the enchant behaviour.')
    def test_candidates_persons(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US'])
        self.assertEqual(
            mq.candidates('family')[0][:2],
            ('👪', 'family'))
        self.assertEqual(
            mq.candidates('man')[0][:2],
            ('👨', 'man'))
        self.assertEqual(
            mq.candidates('woman')[0][:2],
            ('👩', 'woman'))
        self.assertEqual(
            mq.candidates('girl')[0][:2],
            ('👧', 'girl'))
        self.assertEqual(
            mq.candidates('boy')[0][:2],
            ('👦', 'boy'))
        self.assertEqual(
            mq.candidates('family man')[0][:2],
            ('👨\u200d👩\u200d👦', 'family: man, woman, boy “family man woman boy”'))
        self.assertEqual(
            mq.candidates('man man girl boy')[0][:2],
            ('👨\u200d👧\u200d👦', 'family: man, girl, boy “family man girl boy”'))
        self.assertEqual(
            mq.candidates('manmangirlboy')[0][:2],
            ('👨\u200d👨\u200d👧\u200d👦', 'family: man, man, girl, boy'))
        self.assertEqual(
            mq.candidates('people')[0][:2],
            ('👯', 'woman with bunny ears “people with bunny ears partying”'))

    def test_candidates_birthday_cake(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        self.assertEqual(
            mq.candidates('bir')[0][:2],
            ('🎂', 'birthday cake'))
        self.assertEqual(
            mq.candidates('birth')[0][:2],
            ('🎂', 'birthday cake'))

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        testutils.enchant_working_as_expected(),
        'Skipping because of an unexpected change in the enchant behaviour.')
    def test_candidates_symbols(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        self.assertEqual(
            mq.candidates('symbol')[0][:2],
            ('🔣', 'input symbol for symbols {Symbol}'))
        self.assertEqual(
            mq.candidates('atomsymbol')[0][:2],
            ('⚛\ufe0f', 'atom symbol'))
        self.assertEqual(
            mq.candidates('peacesymbol')[0][:2],
            ('☮\ufe0f', 'peace symbol {Symbol}'))
        self.assertEqual(
            mq.candidates('peace symbol')[0][:2],
            ('☮\ufe0f', 'peace symbol {Symbol}'))

    def test_candidates_animals(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        self.assertEqual(
            mq.candidates('animal')[0][:2],
            ('🐵', 'cara de mono [animal]'))
        self.assertEqual(
            mq.candidates('dromedary animal')[0][:2],
            ('🐪', 'dromedary camel'))
        self.assertEqual(
            mq.candidates('camel')[0][:2],
            ('🐫', 'bactrian camel'))
        self.assertEqual(
            mq.candidates('nature')[0][:2],
            ('🙈', 'see-no-evil monkey {nature}'))

    def test_candidates_travel(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        self.assertEqual(
            mq.candidates('camera')[0][:2],
            ('📷', 'camera'))
        self.assertEqual(
            mq.candidates('travel')[0][:2],
            ('\U0001f9f3', 'luggage {travel}'))
        self.assertEqual(
            mq.candidates('ferry')[0][:2],
            ('⛴\ufe0f', 'ferry'))
        self.assertEqual(
            mq.candidates('ferry travel')[0][:2],
            ('⛴\ufe0f', 'ferry {travel}'))
        self.assertEqual(
            mq.candidates('ferry travel boat')[0][:2],
            ('⛴\ufe0f', 'ferry {travel}'))
        self.assertEqual(
            mq.candidates('boat')[0][:2],
            ('🚣🏻\u200d♂️', 'man rowing boat: light skin tone “man rowing boat light skin tone”'))
        self.assertEqual(
            mq.candidates('anchor')[0][:2],
            ('⚓', 'anchor'))
        self.assertEqual(
            mq.candidates('anchor boat')[0][:2],
            ('🚣🏻\u200d♂️', 'man rowing boat: light skin tone “man rowing boat light skin tone”'))

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        testutils.enchant_working_as_expected(),
        'Skipping because of an unexpected change in the enchant behaviour.')
    def test_candidates_spellchecking(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US'])
        self.assertEqual(
            ('\U0001f98b', 'butterfly'),
            mq.candidates('buterfly')[0][:2])
        self.assertEqual(
            ('🏸', 'badminton racquet and shuttlecock'),
            mq.candidates('badminton')[0][:2])
        self.assertEqual(
            ('🏸', 'badminton racquet and shuttlecock'),
            mq.candidates('badmynton')[0][:2])
        self.assertEqual(
            ('🏸', 'badminton racquet and shuttlecock'),
            mq.candidates('padminton')[0][:2])
        self.assertEqual(
            ('🦔', 'hedgehog'),
            mq.candidates('hedgehgo')[0][:2])

    def test_candidates_various_unicode_chars(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        self.assertEqual(
            mq.candidates('euro sign')[0][:2],
            ('€', 'euro sign'))
        self.assertEqual(
            mq.candidates('superscript one')[0][:2],
            ('¹', 'superscript one'))
        self.assertEqual(
            mq.candidates('currency')[0][:2],
            ('₳', 'austral sign {Currency} [currency]'))
        self.assertEqual(
            mq.candidates('connector')[0][:2],
            ('﹎', 'centreline low line {Connector}'))
        self.assertEqual(
            mq.candidates('dash')[0][:2],
            ('💨', 'dash symbol'))
        self.assertEqual(
            mq.candidates('close')[0][:2],
            ('〉', 'right angle bracket “close angle bracket” {Close}'))
        self.assertEqual(
            mq.candidates('punctuation')[0][:2],
            ('‼\ufe0f', 'double exclamation mark {Punctuation} [punctuation]'))
        self.assertEqual(
            mq.candidates('final quote')[0][:2],
            ('’', 'right single quotation mark {Final quote}'))
        self.assertEqual(
            mq.candidates('initial quote')[0][:2],
            ('‘', 'left single quotation mark {Initial quote}'))
        self.assertEqual(
            mq.candidates('modifier')[0][:2],
            ('🏻', 'emoji modifier fitzpatrick type-1-2 {Modifier}'))
        self.assertEqual(
            mq.candidates('math')[0][:2],
            ('𝜵', 'mathematical bold italic nabla {Math}'))
        self.assertEqual(
            mq.candidates('separator line')[0][:2],
            (' ', 'U+2028 line separator {Line}'))
        self.assertEqual(
            mq.candidates('separator paragraph')[0][:2],
            (' ', 'U+2029 paragraph separator {Paragraph}'))
        self.assertEqual(
            mq.candidates('separator space')[0][:2],
            (' ', 'U+20 space {Space}'))

    def test_candidates_french_text(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['fr_FR'])
        self.assertEqual(
            mq.candidates('chat')[0][:2],
            ('🐈', 'chat'))
        self.assertEqual(
            mq.candidates('réflexion')[0][:2],
            ('🤔', 'visage en pleine réflexion'))

    def test_candidates_french_similar(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['fr_FR'])
        self.assertEqual(
            mq.candidates('🤔', match_limit = 3),
            [('🤔', 'visage en pleine réflexion [🤔, réflexion, visage, visage en pleine réflexion]', 4), ('🤐', 'visage avec bouche fermeture éclair [visage]', 1), ('🤗', 'visage qui fait un câlin [visage]', 1)])

    def test_candidates_code_point_input(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['fr_FR'])
        self.assertEqual(
            mq.candidates('2019'),
            [('’', 'U+2019 apostrophe droite', 2000)])
        self.assertEqual(
            mq.candidates('41'),
            [('A', 'U+41 latin capital letter a', 2000)])
        self.assertEqual(
            mq.candidates('2a'),
            [('*', 'U+2A astérisque', 2000)])
        self.assertEqual(
            mq.candidates('1b'),
            [('\x1b', 'U+1B', 2000)])

    def test_candidates_de_DE_versus_de_CH(self):
        # FIXME: This doesn’t work perfectly, when de_CH is the main
        # language, “Reissverschluss” should be preferred in the
        # results.
        mq = itb_emoji.EmojiMatcher(
            languages = ['de_DE'])
        self.assertEqual(
            mq.candidates('Reissverschluss')[0][:2],
            ('🤐', 'Gesicht mit Reißverschlussmund'))
        self.assertEqual(
            mq.candidates('Reißverschluss')[0][:2],
            ('🤐', 'Gesicht mit Reißverschlussmund'))
        self.assertEqual(
            mq.candidates('Reißverschluß')[0][:2],
            ('🤐', 'Gesicht mit Reißverschlussmund'))
        mq = itb_emoji.EmojiMatcher(
            languages = ['de_CH'])
        self.assertEqual(
            mq.candidates('Reissverschluss')[0][:2],
            ('🤐', 'Gesicht mit Reißverschlussmund'))
        self.assertEqual(
            mq.candidates('Reißverschluss')[0][:2],
            ('🤐', 'Gesicht mit Reißverschlussmund'))
        self.assertEqual(
            mq.candidates('Reißverschluß')[0][:2],
            ('🤐', 'Gesicht mit Reißverschlussmund'))

    @unittest.skipIf(
        itb_emoji.IMPORT_PINYIN_SUCCESSFUL,
        "Skipping because import pinyin worked.")
    def test_candidates_pinyin_missing_zh_CN(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_CN'])
        self.assertEqual(
            mq.candidates('赛马')[0][:2],
            ('🏇', '赛马'))
        self.assertEqual(
            0, len(mq.candidates('saima')))

    @unittest.skipUnless(
        itb_emoji.IMPORT_PINYIN_SUCCESSFUL,
        "Skipping because import pinyin failed.")
    def test_candidates_pinyin_available_zh_CN(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_CN'])
        self.assertEqual(
            mq.candidates('赛马')[0][:2],
            ('🏇', '赛马'))
        self.assertEqual(
            mq.candidates('saima')[0][:2],
            ('🏇', '赛马 “sàimǎ”'))

    @unittest.skipIf(
        itb_emoji.IMPORT_PINYIN_SUCCESSFUL,
        "Skipping because import pinyin worked.")
    def test_candidates_pinyin_missing_zh_TW(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_TW'])
        self.assertEqual(
            mq.candidates('賽馬')[0][:2],
            ('🏇', '賽馬'))
        self.assertEqual(
            0, len(mq.candidates('saima')))

    @unittest.skipUnless(
        itb_emoji.IMPORT_PINYIN_SUCCESSFUL,
        "Skipping because import pinyin failed.")
    def test_candidates_pinyin_available_zh_TW(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_TW'])
        self.assertEqual(
            mq.candidates('賽馬')[0][:2],
            ('🏇', '賽馬'))
        self.assertEqual(
            mq.candidates('saima')[0][:2],
            ('🏇', '賽馬 “sàimǎ”'))

    @unittest.skipIf(
        itb_emoji.IMPORT_PYKAKASI_SUCCESSFUL,
        "Skipping because import pykakasi worked.")
    def test_candidates_pykakasi_missing_ja_JP(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['ja_JP'])
        self.assertEqual(
            0, len(mq.candidates('katatsumuri')))
        self.assertEqual(
            mq.candidates('かたつむり')[0][:2],
            ('🐌', 'かたつむり'))
        self.assertEqual(
            mq.candidates('かたつむり_')[0][:2],
            ('🐌', 'かたつむり'))
        self.assertEqual(
            mq.candidates('かたつむり＿')[0][:2],
            ('🐌', 'かたつむり'))
        self.assertEqual(
            0, len(mq.candidates('カタツムリ')))
        self.assertEqual(
            0, len(mq.candidates('カタツムリ_')))
        self.assertEqual(
            0, len(mq.candidates('カタツムリ＿')))
        self.assertEqual(
            mq.candidates('ネコ')[0][:2],
            ('🐈', 'ネコ'))
        self.assertEqual(
            mq.candidates('ネコ_')[0][:2],
            ('🐈', 'ネコ'))
        self.assertEqual(
            mq.candidates('ネコ＿')[0][:2],
            ('🐈', 'ネコ'))
        self.assertEqual(
            0, len(mq.candidates('ねこ')))
        self.assertEqual(
            0, len(mq.candidates('ねこ_')))
        self.assertEqual(
            0, len(mq.candidates('ねこ＿')))

    @unittest.skipUnless(
        itb_emoji.IMPORT_PYKAKASI_SUCCESSFUL,
        "Skipping because import pykakasi failed.")
    def test_candidates_pykakasi_available_ja_JP(self):
        mq = itb_emoji.EmojiMatcher(
            languages = ['ja_JP'])
        self.assertEqual(
            mq.candidates('katatsumuri')[0][:2],
            ('🐌', 'かたつむり “katatsumuri”'))
        self.assertEqual(
            mq.candidates('かたつむり')[0][:2],
            ('🐌', 'かたつむり'))
        self.assertEqual(
            mq.candidates('かたつむり_')[0][:2],
            ('🐌', 'かたつむり'))
        self.assertEqual(
            mq.candidates('かたつむり＿')[0][:2],
            ('🐌', 'かたつむり'))
        self.assertEqual(
            0, len(mq.candidates('カタツムリ')))
        self.assertEqual(
            0, len(mq.candidates('カタツムリ_')))
        self.assertEqual(
            0, len(mq.candidates('カタツムリ＿')))
        self.assertEqual(
            mq.candidates('ネコ')[0][:2],
            ('🐈', 'ネコ'))
        self.assertEqual(
            mq.candidates('ネコ_')[0][:2],
            ('🐈', 'ネコ'))
        self.assertEqual(
            mq.candidates('ネコ＿')[0][:2],
            ('🐈', 'ネコ'))
        self.assertEqual(
            mq.candidates('ねこ')[0][:2],
            ('🐈', 'ネコ “ねこ”'))
        self.assertEqual(
            mq.candidates('ねこ_')[0][:2],
            ('🐈', 'ネコ “ねこ”'))
        self.assertEqual(
            mq.candidates('ねこ＿')[0][:2],
            ('🐈', 'ネコ “ねこ”'))

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    unittest.main()
