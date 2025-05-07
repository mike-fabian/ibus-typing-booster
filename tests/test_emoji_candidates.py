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

LOGGER = logging.getLogger('ibus-typing-booster')

# pylint: disable=wrong-import-position
sys.path.insert(0, "../engine")
import itb_emoji # pylint: disable=import-error
sys.path.pop(0)

import testutils # pylint: disable=import-error
# pylint: enable=wrong-import-position

# Set the domain name to something invalid to avoid using
# the translations for the doctest tests. Translations may
# make the tests fail just because some translations are
# added, changed, or missing.
itb_emoji.DOMAINNAME = ''

IMPORT_ENCHANT_SUCCESSFUL = False
IMPORT_HUNSPELL_SUCCESSFUL = False
try:
    # pylint: disable=unused-import
    import enchant # type: ignore
    # pylint: enable=unused-import
    IMPORT_ENCHANT_SUCCESSFUL = True
except (ImportError,):
    try:
        # pylint: disable=unused-import
        import hunspell # type: ignore
        # pylint: enable=unused-import
        IMPORT_HUNSPELL_SUCCESSFUL = True
    except (ImportError,):
        pass

# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=invalid-name
# pylint: disable=line-too-long

@unittest.skipIf(
    '..' not in itb_emoji.find_cldr_annotation_path('en'),
    f'Using external emoji annotations: '
    f'{itb_emoji.find_cldr_annotation_path("en")} '
    f'Testing with older emoji annotations instead '
    f'of those included in the ibus-typing-booster source is likely '
    f'to create meaningless test failures.')
class EmojiCandidatesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None
        LOGGER.info("itb_emoji.find_cldr_annotation_path('en')->%s",
                    itb_emoji.find_cldr_annotation_path('en'))

    def tearDown(self) -> None:
        pass

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_candidates_empty_query(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['fr_FR'])
        self.assertEqual(mq.candidates(''), [])

    def test_candidates_empty_language_list(self) -> None:
        '''
        Emoji matching with an empty language list should fall back to English.
        '''
        mq = itb_emoji.EmojiMatcher(
            languages = [])
        self.assertEqual(
            mq.candidates('orangutan', match_limit=1)[0].phrase,
            '🦧')
        mq = itb_emoji.EmojiMatcher(
            languages = ['en'])
        self.assertEqual(
            mq.candidates('orangutan', match_limit=1)[0].phrase,
            '🦧')

    def test_candidates_similar_emoji(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        matches = mq.candidates('😺', match_limit=3)
        self.assertEqual(matches[0].phrase, '😺')
        self.assertEqual(matches[0].comment, 'smiling cat face with open mouth [😺, So, people, cat, face, mouth, open, smile, uc6, animal, grinning, smiling]')
        self.assertEqual(matches[0].user_freq, 12.0)
        self.assertEqual(matches[1].phrase, '😸')
        self.assertEqual(matches[1].comment, 'grinning cat face with smiling eyes [So, people, cat, face, smile, uc6, animal, grinning, smiling]')
        self.assertEqual(matches[1].user_freq, 9.0)
        self.assertEqual(matches[2].phrase, '😅')
        self.assertEqual(matches[2].comment, 'smiling face with open mouth and cold sweat [So, people, face, open, smile, uc6, grinning, mouth, smiling]')
        self.assertEqual(matches[2].user_freq, 9.0)

    def test_candidates_japanese_full_width_low_line(self) -> None:
        # ＿ U+FF3F FULLWIDTH LOW LINE should not disturb the match
        mq = itb_emoji.EmojiMatcher(languages = ['ja_JP'])
        first_match = mq.candidates('ネコ')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ')
        first_match = mq.candidates('ネコ＿')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ')

    def test_candidates_multilingual_classic(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm='classic')
        first_match = mq.candidates('ant')[0]
        self.assertEqual(first_match.phrase, '🐜')
        self.assertEqual(first_match.comment, 'ant')
        first_match = mq.candidates('ameise')[0]
        self.assertEqual(first_match.phrase, '🐜')
        self.assertEqual(first_match.comment, 'Ameise')
        first_match = mq.candidates('Ameise')[0]
        self.assertEqual(first_match.phrase, '🐜')
        self.assertEqual(first_match.comment, 'Ameise')
        first_match = mq.candidates('formica')[0]
        self.assertEqual(first_match.phrase, '🐜')
        self.assertEqual(first_match.comment, 'formica')
        first_match = mq.candidates('hormiga')[0]
        self.assertEqual(first_match.phrase, '🐜')
        self.assertEqual(first_match.comment, 'hormiga')
        first_match = mq.candidates('cacca')[0]
        self.assertEqual(first_match.phrase, '💩')
        self.assertEqual(first_match.comment, 'cacca')
        first_match = mq.candidates('orso')[0]
        self.assertEqual(first_match.phrase, '🐻')
        self.assertEqual(first_match.comment, 'orso')
        first_match = mq.candidates('lupo')[0]
        self.assertEqual(first_match.phrase, '🐺')
        self.assertEqual(first_match.comment, 'lupo')
        first_match = mq.candidates('gatto')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'gatto')
        first_match = mq.candidates('gatto sorride')[0]
        self.assertEqual(first_match.phrase, '😺')
        self.assertEqual(first_match.comment, 'gatto che sorride')
        first_match = mq.candidates('halo')[0]
        self.assertEqual(first_match.phrase, '😇')
        self.assertEqual(first_match.comment, 'cara sonriendo con aureola [halo]')
        first_match = mq.candidates('factory')[0]
        self.assertEqual(first_match.phrase, '🏭')
        self.assertEqual(first_match.comment, 'factory')

    @unittest.skipUnless(
        itb_emoji.IMPORT_RAPIDFUZZ_SUCCESSFUL,
        'Skipping because this test requires rapidfuzz to work.')
    def test_candidates_multilingual_rapidfuzz(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm = 'rapidfuzz')
        first_match = mq.candidates('ant')[0]
        self.assertEqual(first_match.phrase, '🐜')
        self.assertEqual(first_match.comment, 'ant')
        first_match = mq.candidates('ameise')[0]
        self.assertEqual(first_match.phrase, '🐜')
        self.assertEqual(first_match.comment, 'Ameise')
        first_match = mq.candidates('Ameise')[0]
        self.assertEqual(first_match.phrase, '🐜', 'Ameise')
        first_match = mq.candidates('formica')[0]
        self.assertEqual(first_match.phrase, '🐜')
        self.assertEqual(first_match.comment, 'formica [formichina]')
        first_match = mq.candidates('hormiga')[0]
        self.assertEqual(first_match.phrase, '🐜')
        self.assertEqual(first_match.comment, 'hormiga')
        first_match, second_match = mq.candidates('cacca')[:2]
        self.assertEqual(first_match.phrase, '💩')
        self.assertEqual(first_match.comment, 'cacca')
        self.assertEqual(second_match.phrase, '\U000cacca')
        self.assertEqual(second_match.comment, 'U+CACCA')
        first_match = mq.candidates('orso')[0]
        self.assertEqual(first_match.phrase, '🐻')
        self.assertEqual(first_match.comment, 'orso')
        first_match = mq.candidates('lupo')[0]
        self.assertEqual(first_match.phrase, '🐺')
        self.assertEqual(first_match.comment, 'lupo [muso di lupo]')
        first_match = mq.candidates('gatto')[0]
        self.assertEqual(first_match.phrase, '😺')
        self.assertEqual(first_match.comment, 'gatto che sorride')
        first_match = mq.candidates('gatto sorride')[0]
        self.assertEqual(first_match.phrase, '😺')
        self.assertEqual(first_match.comment, 'gatto che sorride [sorridente]')
        first_match = mq.candidates('halo')[0]
        self.assertEqual(first_match.phrase, '😇')
        self.assertEqual(first_match.comment, 'smiling face with halo')
        first_match = mq.candidates('factory')[0]
        self.assertEqual(first_match.phrase, '🧑\u200d🏭')
        self.assertEqual(first_match.comment, 'factory worker')

    def test_candidates_white_space_and_underscores_classic(self) -> None:
        # Any white space and '_' can be used to separate keywords in the
        # query string:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm='classic')
        first_match = mq.candidates('gatto_	 sorride')[0]
        self.assertEqual(first_match.phrase, '😺')
        self.assertEqual(first_match.comment, 'gatto che sorride')
        first_match = mq.candidates('nerd glasses')[0]
        self.assertEqual(first_match.phrase, '🤓')
        self.assertEqual(first_match.comment, 'nerd face [glasses]')
        first_match = mq.candidates('smiling face with sunglasses')[0]
        self.assertEqual(first_match.phrase, '😎')
        self.assertEqual(first_match.comment, 'smiling face with sunglasses')

    @unittest.skipUnless(
        itb_emoji.IMPORT_RAPIDFUZZ_SUCCESSFUL,
        'Skipping because this test requires rapidfuzz to work.')
    def test_candidates_white_space_and_underscores_rapidfuzz(self) -> None:
        # Any white space and '_' can be used to separate keywords in the
        # query string:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm='rapidfuzz')
        first_match = mq.candidates('gatto_	 sorride')[0]
        self.assertEqual(first_match.phrase, '😺')
        self.assertEqual(first_match.comment, 'gatto che sorride [sorridente]')
        first_match = mq.candidates('nerd glasses')[0]
        self.assertEqual(first_match.phrase, '🤓')
        self.assertEqual(first_match.comment, 'nerd face [glasses]')
        first_match = mq.candidates('smiling face with sunglasses')[0]
        self.assertEqual(first_match.phrase, '😎')
        self.assertEqual(first_match.comment, 'smiling face with sunglasses')

    def test_candidates_skin_tones_classic(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['ja_JP'], match_algorithm='classic')
        first_match = mq.candidates('man tone5')[0]
        self.assertEqual(first_match.phrase, '👨🏿')
        self.assertEqual(first_match.comment, 'man: dark skin tone “man tone5”')
        first_match = mq.candidates('skin tone')[0]
        self.assertEqual(first_match.phrase, '👋🏻')
        self.assertEqual(first_match.comment, 'waving hand: light skin tone')
        first_match = mq.candidates('tone1')[0]
        self.assertEqual(first_match.phrase, '🏻')
        self.assertEqual(first_match.comment, 'emoji modifier fitzpatrick type-1-2 “tone1”')
        first_match = mq.candidates('tone5')[0]
        self.assertEqual(first_match.phrase, '🏿')
        self.assertEqual(first_match.comment, 'emoji modifier fitzpatrick type-6 “tone5”')

    @unittest.skipUnless(
        itb_emoji.IMPORT_RAPIDFUZZ_SUCCESSFUL,
        'Skipping because this test requires rapidfuzz to work.')
    def test_candidates_skin_tones_rapidfuzz(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['ja_JP'], match_algorithm='rapidfuzz')
        first_match = mq.candidates('man tone5')[0]
        self.assertEqual(first_match.phrase, '👨🏿')
        self.assertEqual(first_match.comment, 'man: dark skin tone “man tone5”')
        first_match = mq.candidates('skin tone')[0]
        self.assertEqual(first_match.phrase, '👋🏻')
        self.assertEqual(first_match.comment, 'waving hand: light skin tone')
        first_match = mq.candidates('tone1')[0]
        self.assertEqual(first_match.phrase, '👋🏻')
        self.assertEqual(first_match.comment, 'waving hand: light skin tone “wave tone1”')
        first_match = mq.candidates('tone5')[0]
        self.assertEqual(first_match.phrase, '👋🏿')
        self.assertEqual(first_match.comment, 'waving hand: dark skin tone “wave tone5”')

    def test_candidates_some_letters_classic(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm='classic')
        first_match = mq.candidates('latin capital letter a')[0]
        self.assertEqual(first_match.phrase, '🅰\ufe0f')
        self.assertEqual(first_match.comment, 'negative squared latin capital letter a')
        first_match = mq.candidates('squared a')[0]
        self.assertEqual(first_match.phrase, '🅰\ufe0f')
        self.assertEqual(first_match.comment, 'negative squared latin capital letter a')
        first_match = mq.candidates('squared capital a')[0]
        self.assertEqual(first_match.phrase, '🅰\ufe0f')
        self.assertEqual(first_match.comment, 'negative squared latin capital letter a')
        first_match = mq.candidates('latin small letter c')[0]
        self.assertEqual(first_match.phrase, '🔡')
        self.assertEqual(first_match.comment, 'input symbol for latin small letters')

    @unittest.skipUnless(
        itb_emoji.IMPORT_RAPIDFUZZ_SUCCESSFUL,
        'Skipping because this test requires rapidfuzz to work.')
    def test_candidates_some_letters_rapidfuzz(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm='rapidfuzz')
        first_match = mq.candidates('latin capital letter a')[0]
        self.assertEqual(first_match.phrase, '🅰\ufe0f')
        self.assertEqual(first_match.comment, 'negative squared latin capital letter a')
        first_match = mq.candidates('squared a')[0]
        self.assertEqual(first_match.phrase, '🅰\ufe0f')
        self.assertEqual(first_match.comment, 'negative squared latin capital letter a')
        first_match = mq.candidates('squared capital a')[0]
        self.assertEqual(first_match.phrase, '🅰\ufe0f')
        self.assertEqual(first_match.comment, 'negative squared latin capital letter a')
        first_match = mq.candidates('latin small letter c')[0]
        self.assertEqual(first_match.phrase, '🔡')
        self.assertEqual(first_match.comment, 'input symbol for latin small letters')

    def test_candidates_flags_classic(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US'], match_algorithm='classic')
        first_match = mq.candidates('us')[0]
        self.assertEqual(first_match.phrase, '🇺🇸')
        self.assertEqual(first_match.comment, 'flag: united states “us”')
        first_match = mq.candidates('flag us')[0]
        self.assertEqual(first_match.phrase, '🇺🇸')
        self.assertEqual(first_match.comment, 'flag: united states “flag us”')
        first_match = mq.candidates('united nations')[0]
        self.assertEqual(first_match.phrase, '🇺🇳')
        self.assertEqual(first_match.comment, 'flag: united nations')
        first_match = mq.candidates('united')[0]
        self.assertEqual(first_match.phrase, '🇺🇳')
        self.assertEqual(first_match.comment, 'flag: united nations')
        first_match = mq.candidates('outlying islands')[0]
        self.assertEqual(first_match.phrase, '🇺🇲')
        self.assertEqual(first_match.comment, 'flag: u.s. outlying islands')
        first_match = mq.candidates('flag united arab')[0]
        self.assertEqual(first_match.phrase, '🇦🇪')
        self.assertEqual(first_match.comment, 'flag: united arab emirates')
        first_match = mq.candidates('mm')[0]
        self.assertEqual(first_match.phrase, '🇲🇲')
        self.assertEqual(first_match.comment, 'flag: myanmar (burma) “mm”')
        first_match = mq.candidates('flag mm')[0]
        self.assertEqual(first_match.phrase, '🇲🇲')
        self.assertEqual(first_match.comment, 'flag: myanmar (burma) “flag mm”')
        first_match = mq.candidates('myanmar burma')[0]
        self.assertEqual(first_match.phrase, '🇲🇲')
        self.assertEqual(first_match.comment, 'flag: myanmar (burma) “flag: myanmar burma”')
        first_match = mq.candidates('sj')[0]
        self.assertEqual(first_match.phrase, '🇸🇯')
        self.assertEqual(first_match.comment, 'flag: svalbard & jan mayen “sj”')
        first_match = mq.candidates('flag sj')[0]
        self.assertEqual(first_match.phrase, '🇸🇯')
        self.assertEqual(first_match.comment, 'flag: svalbard & jan mayen “flag sj”')
        first_match = mq.candidates('svalbard')[0]
        self.assertEqual(first_match.phrase, '🇸🇯')
        self.assertEqual(first_match.comment, 'flag: svalbard & jan mayen')
        first_match = mq.candidates('jan mayen')[0]
        self.assertEqual(first_match.phrase, '🇸🇯')
        self.assertEqual(first_match.comment, 'flag: svalbard & jan mayen')
        first_match = mq.candidates('mayen')[0]
        self.assertEqual(first_match.phrase, '🇸🇯')
        self.assertEqual(first_match.comment, 'flag: svalbard & jan mayen')

    @unittest.skipUnless(
        itb_emoji.IMPORT_RAPIDFUZZ_SUCCESSFUL,
        'Skipping because this test requires rapidfuzz to work.')
    def test_candidates_flags_rapidfuzz(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US'], match_algorithm='rapidfuzz')
        first_match = mq.candidates('us')[0]
        self.assertEqual(first_match.phrase, '🇺🇲')
        self.assertEqual(first_match.comment, 'flag: us outlying islands')
        first_match = mq.candidates('flag us')[0]
        self.assertEqual(first_match.phrase, '🇺🇸')
        self.assertEqual(first_match.comment, 'flag: united states “flag us” {flags}')
        first_match = mq.candidates('united nations')[0]
        self.assertEqual(first_match.phrase, '🇺🇳')
        self.assertEqual(first_match.comment, 'flag: united nations')
        first_match = mq.candidates('united')[0]
        self.assertEqual(first_match.phrase, '🇦🇪')
        self.assertEqual(first_match.comment, 'flag: united arab emirates')
        first_match = mq.candidates('outlying islands')[0]
        self.assertEqual(first_match.phrase, '🇺🇲')
        self.assertEqual(first_match.comment, 'flag: u.s. outlying islands')
        first_match = mq.candidates('flag united arab emirates')[0]
        self.assertEqual(first_match.phrase, '🇦🇪')
        self.assertEqual(first_match.comment, 'flag: united arab emirates')
        first_match = mq.candidates('mm myanmar')[0]
        self.assertEqual(first_match.phrase, '🇲🇲')
        self.assertEqual(first_match.comment, 'flag: myanmar (burma)')
        first_match = mq.candidates('flag mm')[0]
        self.assertEqual(first_match.phrase, '🇲🇲')
        self.assertEqual(first_match.comment, 'flag: myanmar (burma) “flag mm” {flags}')
        first_match = mq.candidates('myanmar')[0]
        self.assertEqual(first_match.phrase, '🇲🇲')
        self.assertEqual(first_match.comment, 'flag: myanmar (burma)')
        first_match = mq.candidates('sj')[0]
        self.assertEqual(first_match.phrase, '🇸🇯')
        self.assertEqual(first_match.comment, 'flag: svalbard & jan mayen “flag sj”')
        first_match = mq.candidates('flag sj')[0]
        self.assertEqual(first_match.phrase, '🇸🇯')
        self.assertEqual(first_match.comment, 'flag: svalbard & jan mayen “flag sj” {flags}')
        first_match = mq.candidates('svalbard')[0]
        self.assertEqual(first_match.phrase, '🇸🇯')
        self.assertEqual(first_match.comment, 'flag: svalbard & jan mayen')
        first_match = mq.candidates('jan mayen')[0]
        self.assertEqual(first_match.phrase, '🇸🇯')
        self.assertEqual(first_match.comment, 'flag: svalbard & jan mayen')
        first_match = mq.candidates('mayen')[0]
        self.assertEqual(first_match.phrase, '🇸🇯')
        self.assertEqual(first_match.comment, 'flag: svalbard & jan mayen')

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        testutils.enchant_working_as_expected(),
        'Skipping because of an unexpected change in the enchant behaviour.')
    def test_candidates_persons_classic(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US'], match_algorithm='classic')
        first_match = mq.candidates('family')[0]
        self.assertEqual(first_match.phrase, '👪')
        self.assertEqual(first_match.comment, 'family')
        first_match = mq.candidates('man')[0]
        self.assertEqual(first_match.phrase, '👨')
        self.assertEqual(first_match.comment, 'man')
        first_match = mq.candidates('woman')[0]
        self.assertEqual(first_match.phrase, '👩')
        self.assertEqual(first_match.comment, 'woman')
        first_match = mq.candidates('girl')[0]
        self.assertEqual(first_match.phrase, '👧')
        self.assertEqual(first_match.comment, 'girl')
        first_match = mq.candidates('boy')[0]
        self.assertEqual(first_match.phrase, '👦')
        self.assertEqual(first_match.comment, 'boy')
        first_match = mq.candidates('family man')[0]
        self.assertEqual(first_match.phrase, '👨\u200d👩\u200d👦')
        self.assertEqual(first_match.comment, 'family: man, woman, boy')
        first_match = mq.candidates('man woman girl boy')[0]
        self.assertEqual(first_match.phrase, '👨‍👩‍👧‍👦')
        self.assertEqual(first_match.comment, 'family: man, woman, girl, boy')
        first_match = mq.candidates('people holding hands')[0]
        self.assertEqual(first_match.phrase, '🧑‍🤝‍🧑')
        self.assertEqual(first_match.comment, 'people holding hands')

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        testutils.enchant_working_as_expected(),
        'Skipping because of an unexpected change in the enchant behaviour.')
    @unittest.skipUnless(
        itb_emoji.IMPORT_RAPIDFUZZ_SUCCESSFUL,
        'Skipping because this test requires rapidfuzz to work.')
    def test_candidates_persons_rapidfuzz(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US'], match_algorithm='rapidfuzz')
        first_match = mq.candidates('family people')[0]
        self.assertEqual(first_match.phrase, '👪')
        self.assertEqual(first_match.comment, 'family {people}')
        first_match = mq.candidates('man people')[0]
        self.assertEqual(first_match.phrase, '👨')
        self.assertEqual(first_match.comment, 'man {people}')
        first_match = mq.candidates('woman people')[0]
        self.assertEqual(first_match.phrase, '👩')
        self.assertEqual(first_match.comment, 'woman {people}')
        first_match = mq.candidates('girl people')[0]
        self.assertEqual(first_match.phrase, '👧')
        self.assertEqual(first_match.comment, 'girl {people}')
        first_match = mq.candidates('boy people')[0]
        self.assertEqual(first_match.phrase, '👦')
        self.assertEqual(first_match.comment, 'boy {people}')
        first_match = mq.candidates('family man')[0]
        self.assertEqual(first_match.phrase, '👨\u200d👩\u200d👦')
        self.assertEqual(first_match.comment, 'family: man, woman, boy')
        first_match = mq.candidates('man woman girl boy')[0]
        self.assertEqual(first_match.phrase, '👨‍👩‍👧‍👦')
        self.assertEqual(first_match.comment, 'family: man, woman, girl, boy')
        first_match = mq.candidates('people holding hands')[0]
        self.assertEqual(first_match.phrase, '🧑‍🤝‍🧑')
        self.assertEqual(first_match.comment, 'people holding hands')

    def test_candidates_birthday_cake_classic(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm = 'classic')
        first_match = mq.candidates('birthday')[0]
        self.assertEqual(first_match.phrase, '🎂')
        self.assertEqual(first_match.comment, 'birthday cake')
        first_match = mq.candidates('birth bottle')[0]
        self.assertEqual(first_match.phrase, '🍼')
        self.assertEqual(first_match.comment, 'baby bottle [birth]')

    @unittest.skipUnless(
        itb_emoji.IMPORT_RAPIDFUZZ_SUCCESSFUL,
        'Skipping because this test requires rapidfuzz to work.')
    def test_candidates_birthday_cake_rapidfuzz(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm = 'rapidfuzz')
        first_match = mq.candidates('birthday')[0]
        self.assertEqual(first_match.phrase, '🎂')
        self.assertEqual(first_match.comment, 'birthday cake [bday]')
        first_match = mq.candidates('birth bottle')[0]
        self.assertEqual(first_match.phrase, '🍼')
        self.assertEqual(first_match.comment, 'baby bottle [birth]')

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        testutils.enchant_working_as_expected(),
        'Skipping because of an unexpected change in the enchant behaviour.')
    def test_candidates_symbols_classic(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm='classic')
        first_match = mq.candidates('recycling symbol')[0]
        self.assertEqual(first_match.phrase, '♻️')
        self.assertEqual(first_match.comment,
                         'black universal recycling symbol {Symbol}')
        first_match = mq.candidates('atom symbol')[0]
        self.assertEqual(first_match.phrase, '⚛\ufe0f')
        self.assertEqual(first_match.comment, 'atom symbol {Symbol}')
        first_match = mq.candidates('peace symbol')[0]
        self.assertEqual(first_match.phrase, '☮\ufe0f')
        # .startswith() because it may be 'peace symbol {Symbol}' or
        # just 'peace symbol'
        self.assertTrue(first_match.comment.startswith('peace symbol'))
        first_match = mq.candidates('peace symbol')[0]
        self.assertEqual(first_match.phrase, '☮\ufe0f')
        # .startswith() because it may be 'peace symbol {Symbol}' or
        # just 'peace symbol'
        self.assertTrue(first_match.comment.startswith('peace symbol'))

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        testutils.enchant_working_as_expected(),
        'Skipping because of an unexpected change in the enchant behaviour.')
    @unittest.skipUnless(
        itb_emoji.IMPORT_RAPIDFUZZ_SUCCESSFUL,
        'Skipping because this test requires rapidfuzz to work.')
    def test_candidates_symbols_rapidfuzz(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm='rapidfuzz')
        first_match = mq.candidates('recycling symbol')[0]
        self.assertEqual(first_match.phrase, '♻️')
        self.assertEqual(first_match.comment,
                         'black universal recycling symbol {Symbol}')
        first_match = mq.candidates('atom symbol')[0]
        self.assertEqual(first_match.phrase, '⚛\ufe0f')
        self.assertEqual(first_match.comment, 'atom symbol {Symbol} {symbols}')
        first_match = mq.candidates('peace symbol')[0]
        self.assertEqual(first_match.phrase, '☮\ufe0f')
        # .startswith() because it may be 'peace symbol {Symbol}' or
        # just 'peace symbol'
        self.assertTrue(first_match.comment.startswith('peace symbol'))
        first_match = mq.candidates('peace symbol')[0]
        self.assertEqual(first_match.phrase, '☮\ufe0f')
        # .startswith() because it may be 'peace symbol {Symbol}' or
        # just 'peace symbol'
        self.assertTrue(first_match.comment.startswith('peace symbol'))

    def test_candidates_animals_classic(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm='classic')
        first_match = mq.candidates('animal dog')[0]
        self.assertEqual(first_match.phrase, '🐶')
        self.assertEqual(first_match.comment, 'dog face [animal]')
        first_match = mq.candidates('dromedary animal')[0]
        self.assertEqual(first_match.phrase, '🐪')
        self.assertEqual(first_match.comment, 'dromedary camel [animal]')
        first_match = mq.candidates('camel bac')[0]
        self.assertEqual(first_match.phrase, '🐫')
        self.assertEqual(first_match.comment, 'bactrian camel')
        first_match = mq.candidates('nature snail')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'snail {nature}')

    @unittest.skipUnless(
        itb_emoji.IMPORT_RAPIDFUZZ_SUCCESSFUL,
        'Skipping because this test requires rapidfuzz to work.')
    def test_candidates_animals_rapidfuzz(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm='rapidfuzz')
        first_match = mq.candidates('animal dog')[0]
        self.assertEqual(first_match.phrase, '🐶')
        self.assertEqual(first_match.comment, 'dog face [animal]')
        first_match = mq.candidates('dromedary animal')[0]
        self.assertEqual(first_match.phrase, '🐪')
        self.assertEqual(first_match.comment, 'dromedary camel [animal]')
        first_match = mq.candidates('camel bac')[0]
        self.assertEqual(first_match.phrase, '🐫')
        self.assertEqual(first_match.comment, 'bactrian camel')
        first_match = mq.candidates('nature snail')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'snail {nature}')

    def test_candidates_travel_classic(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm='classic')
        first_match = mq.candidates('camera')[0]
        self.assertEqual(first_match.phrase, '📷')
        self.assertEqual(first_match.comment, 'camera')
        first_match = mq.candidates('travel locomotive')[0]
        self.assertEqual(first_match.phrase, '🚂')
        self.assertEqual(first_match.comment, 'steam locomotive {travel}')
        first_match = mq.candidates('ferry')[0]
        self.assertEqual(first_match.phrase, '⛴\ufe0f')
        self.assertEqual(first_match.comment, 'ferry')
        first_match = mq.candidates('ferry travel')[0]
        self.assertEqual(first_match.phrase, '⛴\ufe0f')
        self.assertEqual(first_match.comment, 'ferry {travel}')
        first_match = mq.candidates('ferry travel boat')[0]
        self.assertEqual(first_match.phrase, '⛴\ufe0f')
        self.assertEqual(first_match.comment, 'ferry {travel}')
        first_match = mq.candidates('boat')[0]
        self.assertEqual(first_match.phrase, '🚣')
        self.assertEqual(first_match.comment, 'rowboat')
        first_match = mq.candidates('anchor')[0]
        self.assertEqual(first_match.phrase, '⚓')
        self.assertEqual(first_match.comment, 'anchor')
        first_match = mq.candidates('anchor ship')[0]
        self.assertEqual(first_match.phrase, '⚓')
        self.assertEqual(first_match.comment, 'anchor')

    @unittest.skipUnless(
        itb_emoji.IMPORT_RAPIDFUZZ_SUCCESSFUL,
        'Skipping because this test requires rapidfuzz to work.')
    def test_candidates_travel_rapidfuzz(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm='rapidfuzz')
        first_match = mq.candidates('camera')[0]
        self.assertEqual(first_match.phrase, '🎥')
        self.assertEqual(first_match.comment, 'movie camera')
        first_match = mq.candidates('travel locomotive')[0]
        self.assertEqual(first_match.phrase, '🚂')
        self.assertEqual(first_match.comment, 'steam locomotive {travel}')
        first_match = mq.candidates('ferry')[0]
        self.assertEqual(first_match.phrase, '⛴\ufe0f')
        self.assertEqual(first_match.comment, 'ferry')
        first_match = mq.candidates('ferry travel')[0]
        self.assertEqual(first_match.phrase, '⛴\ufe0f')
        self.assertEqual(first_match.comment, 'ferry {travel}')
        first_match = mq.candidates('ferry travel boat')[0]
        self.assertEqual(first_match.phrase, '⛴\ufe0f')
        self.assertEqual(first_match.comment, 'ferry {travel}')
        first_match = mq.candidates('boat')[0]
        self.assertEqual(first_match.phrase, '🚣')
        self.assertEqual(first_match.comment, 'rowboat')
        first_match = mq.candidates('anchor')[0]
        self.assertEqual(first_match.phrase, '⚓')
        self.assertEqual(first_match.comment, 'anchor')
        first_match = mq.candidates('anchor ship')[0]
        self.assertEqual(first_match.phrase, '⚓')
        self.assertEqual(first_match.comment, 'anchor')

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        testutils.enchant_working_as_expected(),
        'Skipping because of an unexpected change in the enchant behaviour.')
    def test_candidates_spellchecking(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US'])
        first_match = mq.candidates('buterfly', spellcheck=True)[0]
        self.assertEqual(first_match.phrase, '\U0001f98b')
        self.assertEqual(first_match.comment, 'butterfly')
        first_match = mq.candidates('badminton', spellcheck=True)[0]
        self.assertEqual(first_match.phrase, '🏸')
        self.assertEqual(first_match.comment, 'badminton racquet and shuttlecock')
        first_match = mq.candidates('badmynton', spellcheck=True)[0]
        self.assertEqual(first_match.phrase, '🏸')
        self.assertEqual(first_match.comment, 'badminton racquet and shuttlecock')
        first_match = mq.candidates('padminton', spellcheck=True)[0]
        self.assertEqual(first_match.phrase, '🏸')
        self.assertEqual(first_match.comment, 'badminton racquet and shuttlecock')
        first_match = mq.candidates('hedgehgo', spellcheck=True)[0]
        self.assertEqual(first_match.phrase, '🦔')
        self.assertEqual(first_match.comment, 'hedgehog')

    def test_candidates_various_unicode_chars_classic(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm='classic')
        first_match, second_match = mq.candidates('euro sign')[:2]
        self.assertEqual(first_match.phrase, '💶')
        self.assertEqual(first_match.comment, 'banknote with euro sign')
        self.assertEqual(second_match.phrase, '€')
        self.assertEqual(second_match.comment, 'euro sign')
        first_match = mq.candidates('superscript one')[0]
        self.assertEqual(first_match.phrase, '¹')
        self.assertEqual(first_match.comment, 'superscript one')
        first_match, second_match = mq.candidates('currency sign')[:2]
        self.assertEqual(first_match.phrase, '¤')
        self.assertEqual(first_match.comment, 'currency sign {Currency}')
        self.assertEqual(second_match.phrase, '💴')
        self.assertEqual(second_match.comment, 'banknote with yen sign [currency]')
        first_match = mq.candidates('connector')[0]
        self.assertEqual(first_match.phrase, '﹎')
        self.assertEqual(first_match.comment, 'centreline low line {Connector}')
        first_match = mq.candidates('dash')[0]
        self.assertEqual(first_match.phrase, '💨')
        self.assertEqual(first_match.comment, 'dash symbol')
        first_match = mq.candidates('close')[0]
        self.assertEqual(first_match.phrase, '😥')
        self.assertEqual(first_match.comment, 'disappointed but relieved face [close]')
        first_match = mq.candidates('punctuation dotted')[0]
        self.assertEqual(first_match.phrase, '⁜')
        self.assertEqual(first_match.comment, 'dotted cross {Punctuation}')
        first_match = mq.candidates('final double quote')[0]
        self.assertEqual(first_match.phrase, '”')
        self.assertEqual(first_match.comment, 'right double quotation mark {Final quote}')
        first_match = mq.candidates('initial double quote')[0]
        self.assertEqual(first_match.phrase, '“')
        self.assertEqual(first_match.comment, 'left double quotation mark {Initial quote}')
        first_match = mq.candidates('modifier')[0]
        self.assertEqual(first_match.phrase, '🏻')
        self.assertEqual(first_match.comment, 'emoji modifier fitzpatrick type-1-2 {Modifier}')
        first_match = mq.candidates('math nabla')[0]
        self.assertEqual(first_match.phrase, '∇')
        self.assertEqual(first_match.comment, 'nabla {Math}')
        first_match = mq.candidates('separator line')[0]
        self.assertEqual(first_match.phrase, ' ')
        self.assertEqual(first_match.comment, 'U+2028 line separator {Line}')
        first_match = mq.candidates('separator paragraph')[0]
        self.assertEqual(first_match.phrase, ' ')
        self.assertEqual(first_match.comment, 'U+2029 paragraph separator {Paragraph}')
        first_match = mq.candidates('separator space')[0]
        self.assertEqual(first_match.phrase, ' ')
        self.assertEqual(first_match.comment, 'U+0020 space {Space}')

    @unittest.skipUnless(
        itb_emoji.IMPORT_RAPIDFUZZ_SUCCESSFUL,
        'Skipping because this test requires rapidfuzz to work.')
    def test_candidates_various_unicode_chars_rapidfuzz(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'],
            match_algorithm='rapidfuzz')
        first_match, second_match = mq.candidates('euro sign')[:2]
        self.assertEqual(first_match.phrase, '💶')
        self.assertEqual(first_match.comment, 'banknote with euro sign')
        self.assertEqual(second_match.phrase, '€')
        self.assertEqual(second_match.comment, 'euro sign')
        first_match = mq.candidates('superscript one')[0]
        self.assertEqual(first_match.phrase, '¹')
        self.assertEqual(first_match.comment, 'superscript one')
        first_match, second_match = mq.candidates('currency sign')[:2]
        self.assertEqual(first_match.phrase, '💲')
        self.assertEqual(first_match.comment, 'heavy dollar sign')
        self.assertEqual(second_match.phrase, '💴')
        self.assertEqual(second_match.comment, 'banknote with yen sign [currency]')
        first_match = mq.candidates('connector')[0]
        self.assertEqual(first_match.phrase, '_')
        self.assertEqual(first_match.comment, 'low line {Connector}')
        first_match = mq.candidates('dash')[0]
        self.assertEqual(first_match.phrase, '💨')
        self.assertEqual(first_match.comment, 'dash symbol [dashing]')
        first_match = mq.candidates('close')[0]
        self.assertEqual(first_match.phrase, '📕')
        self.assertEqual(first_match.comment, 'closed book')
        first_match = mq.candidates('punctuation')[0]
        self.assertEqual(first_match.phrase, '❗')
        self.assertEqual(first_match.comment, 'heavy exclamation mark symbol [punctuation]')
        first_match = mq.candidates('final double quote')[0]
        self.assertEqual(first_match.phrase, '”')
        self.assertEqual(first_match.comment, 'right double quotation mark {Final quote}')
        first_match = mq.candidates('initial double quote')[0]
        self.assertEqual(first_match.phrase, '“')
        self.assertEqual(first_match.comment, 'left double quotation mark {Initial quote}')
        first_match = mq.candidates('emoji modifier')[0]
        self.assertEqual(first_match.phrase, '🏻')
        self.assertEqual(first_match.comment, 'emoji modifier fitzpatrick type-1-2 {Modifier}')
        first_match = mq.candidates('math nabla')[0]
        self.assertEqual(first_match.phrase, '∇')
        self.assertEqual(first_match.comment, 'nabla {Math}')
        first_match = mq.candidates('separator line')[0]
        self.assertEqual(first_match.phrase, ' ')
        self.assertEqual(first_match.comment, 'U+2028 line separator {Line}')
        first_match = mq.candidates('separator paragraph')[0]
        self.assertEqual(first_match.phrase, ' ')
        self.assertEqual(first_match.comment, 'U+2029 paragraph separator {Paragraph}')
        first_match = mq.candidates('separator space')[0]
        self.assertEqual(first_match.phrase, ' ')
        self.assertEqual(first_match.comment, 'U+0020 space {Space}')

    def test_candidates_french_text_classic(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['fr_FR'], match_algorithm='classic')
        first_match = mq.candidates('chat')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'chat')
        first_match = mq.candidates('réflexion')[0]
        self.assertEqual(first_match.phrase, '🤔')
        self.assertEqual(first_match.comment, 'visage en pleine réflexion')

    @unittest.skipUnless(
        itb_emoji.IMPORT_RAPIDFUZZ_SUCCESSFUL,
        'Skipping because this test requires rapidfuzz to work.')
    def test_candidates_french_text_rapidfuzz(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['fr_FR'], match_algorithm='rapidfuzz')
        first_match = mq.candidates('chat animal')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'chat')
        first_match = mq.candidates('réflexion')[0]
        self.assertEqual(first_match.phrase, '🤔')
        self.assertEqual(first_match.comment, 'visage en pleine réflexion')

    def test_candidates_french_similar(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['fr_FR'])
        matches = mq.candidates('🤔', match_limit = 3)
        self.assertEqual(matches[0].phrase, '🤔')
        self.assertEqual(matches[0].comment, 'visage en pleine réflexion [🤔, émoticône, hum, méditer, penser, réfléchir, réflexion, visage, visage en pleine réflexion]')
        self.assertEqual(matches[0].user_freq, 9.0)
        self.assertEqual(matches[1].phrase, '🤐')
        self.assertEqual(matches[1].comment, 'visage avec bouche fermeture éclair [émoticône, visage]')
        self.assertEqual(matches[1].user_freq, 2.0)
        self.assertEqual(matches[2].phrase, '🤗')
        self.assertEqual(matches[2].comment, 'visage qui fait un câlin [émoticône, visage]')
        self.assertEqual(matches[2].user_freq, 2.0)

    def test_candidates_code_point_input_classic(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['fr_FR'], match_algorithm='classic')
        first_match = mq.candidates('2019')[0]
        self.assertEqual(first_match.phrase, '’')
        self.assertEqual(first_match.comment, 'U+2019 apostrophe droite')
        first_match = mq.candidates('41')[0]
        self.assertEqual(first_match.phrase, 'A')
        self.assertEqual(first_match.comment, 'U+41 latin capital letter a')
        first_match = mq.candidates('2a')[0]
        self.assertEqual(first_match.phrase, '*')
        self.assertEqual(first_match.comment, 'U+2A astérisque')
        first_match = mq.candidates('1b')[0]
        self.assertEqual(first_match.phrase, '\x1b')
        self.assertEqual(first_match.comment, 'U+1B')

    @unittest.skipUnless(
        itb_emoji.IMPORT_RAPIDFUZZ_SUCCESSFUL,
        'Skipping because this test requires rapidfuzz to work.')
    def test_candidates_code_point_input_rapidfuzz(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['fr_FR'], match_algorithm='rapidfuzz')
        first_match = mq.candidates('2019')[0]
        self.assertEqual(first_match.phrase, '’')
        self.assertEqual(first_match.comment, 'U+2019 apostrophe droite')
        first_match = mq.candidates('41')[0]
        self.assertEqual(first_match.phrase, 'A')
        self.assertEqual(first_match.comment, 'U+41 latin capital letter a')
        first_match = mq.candidates('2a')[0]
        self.assertEqual(first_match.phrase, '*')
        self.assertEqual(first_match.comment, 'U+2A astérisque')
        first_match = mq.candidates('1b')[0]
        self.assertEqual(first_match.phrase, '\x1b')
        self.assertEqual(first_match.comment, 'U+1B')

    def test_candidates_de_DE_versus_de_CH_classic(self) -> None: # pylint: disable=invalid-name
        # pylint: disable=fixme
        # FIXME: This doesn’t work perfectly, when de_CH is the main
        # language, “Reissverschluss” should be preferred in the
        # results.
        # pylint: enable=fixme
        mq = itb_emoji.EmojiMatcher(
            languages = ['de_DE'],
            match_algorithm = 'classic')
        first_match = mq.candidates('Reissverschluss')[0]
        self.assertEqual(first_match.phrase, '🤐')
        self.assertEqual(first_match.comment, 'Gesicht mit Reißverschlussmund')
        first_match = mq.candidates('Reißverschluss')[0]
        self.assertEqual(first_match.phrase, '🤐')
        self.assertEqual(first_match.comment, 'Gesicht mit Reißverschlussmund')
        first_match = mq.candidates('Reißverschluß')[0]
        self.assertEqual(first_match.phrase, '🤐')
        self.assertEqual(first_match.comment, 'Gesicht mit Reißverschlussmund')
        mq = itb_emoji.EmojiMatcher(
            languages = ['de_CH'],
            match_algorithm = 'classic')
        first_match = mq.candidates('Reissverschluss')[0]
        self.assertEqual(first_match.phrase, '🤐')
        self.assertEqual(first_match.comment, 'Gesicht mit Reißverschlussmund')
        first_match = mq.candidates('Reißverschluss')[0]
        self.assertEqual(first_match.phrase, '🤐')
        self.assertEqual(first_match.comment, 'Gesicht mit Reißverschlussmund')
        first_match = mq.candidates('Reißverschluß')[0]
        self.assertEqual(first_match.phrase, '🤐')
        self.assertEqual(first_match.comment, 'Gesicht mit Reißverschlussmund')

    @unittest.skipUnless(
        itb_emoji.IMPORT_RAPIDFUZZ_SUCCESSFUL,
        'Skipping because this test requires rapidfuzz to work.')
    def test_candidates_de_DE_versus_de_CH_rapidfuzz(self) -> None: # pylint: disable=invalid-name
        # pylint: disable=fixme
        # FIXME: This doesn’t work perfectly, when de_CH is the main
        # language, “Reissverschluss” should be preferred in the
        # results.
        # pylint: enable=fixme
        mq = itb_emoji.EmojiMatcher(
            languages = ['de_DE'],
            match_algorithm = 'rapidfuzz')
        first_match = mq.candidates('Reissverschluss')[0]
        self.assertEqual(first_match.phrase, '🤐')
        self.assertEqual(first_match.comment, 'Gesicht mit Reißverschlussmund')
        first_match = mq.candidates('Reißverschluss')[0]
        self.assertEqual(first_match.phrase, '🤐')
        self.assertEqual(first_match.comment, 'Gesicht mit Reißverschlussmund')
        first_match = mq.candidates('Reißverschluß')[0]
        self.assertEqual(first_match.phrase, '🤐')
        self.assertEqual(first_match.comment, 'Gesicht mit Reißverschlussmund')
        mq = itb_emoji.EmojiMatcher(
            languages = ['de_CH'],
            match_algorithm = 'rapidfuzz')
        first_match = mq.candidates('Reissverschluss')[0]
        self.assertEqual(first_match.phrase, '🤐')
        self.assertEqual(first_match.comment, 'Smiley mit Reissverschlussmund')
        first_match = mq.candidates('Reißverschluss')[0]
        self.assertEqual(first_match.phrase, '🤐')
        self.assertEqual(first_match.comment, 'Smiley mit Reissverschlussmund')
        first_match = mq.candidates('Reißverschluß')[0]
        self.assertEqual(first_match.phrase, '🤐')
        self.assertEqual(first_match.comment, 'Smiley mit Reissverschlussmund')

    @unittest.skipIf(
        itb_emoji.IMPORT_PINYIN_SUCCESSFUL,
        "Skipping because import pinyin worked.")
    def test_candidates_pinyin_missing_zh_CN(self) -> None: # pylint: disable=invalid-name
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_CN'])
        first_match = mq.candidates('赛马')[0]
        self.assertEqual(first_match.phrase, '🏇')
        self.assertEqual(first_match.comment, '赛马')
        self.assertEqual(
            0, len(mq.candidates('saima')))

    @unittest.skipUnless(
        itb_emoji.IMPORT_PINYIN_SUCCESSFUL,
        "Skipping because import pinyin failed.")
    def test_candidates_pinyin_available_zh_CN_classic(self) -> None: # pylint: disable=invalid-name
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_CN'],
            match_algorithm = 'classic')
        first_match = mq.candidates('赛马')[0]
        self.assertEqual(first_match.phrase, '🏇')
        self.assertEqual(first_match.comment, '赛马')
        first_match = mq.candidates('saima')[0]
        self.assertEqual(first_match.phrase, '🏇')
        self.assertEqual(first_match.comment, '赛马 “sàimǎ”')

    @unittest.skipUnless(
        itb_emoji.IMPORT_PINYIN_SUCCESSFUL,
        "Skipping because import pinyin failed.")
    def test_candidates_pinyin_available_zh_CN_rapidfuzz(self) -> None: # pylint: disable=invalid-name
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_CN'],
            match_algorithm = 'rapidfuzz')
        first_match = mq.candidates('赛马')[0]
        self.assertEqual(first_match.phrase, '🏇')
        self.assertEqual(first_match.comment, '赛马')
        first_match = mq.candidates('saima')[0]
        self.assertEqual(first_match.phrase, '🏇')
        self.assertEqual(first_match.comment, '赛马 “sàimǎ” [qímǎ]')

    @unittest.skipIf(
        itb_emoji.IMPORT_PINYIN_SUCCESSFUL,
        "Skipping because import pinyin worked.")
    def test_candidates_pinyin_missing_zh_TW_classic(self) -> None: # pylint: disable=invalid-name
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_TW'],
            match_algorithm = 'classic')
        first_match = mq.candidates('賽馬')[0]
        self.assertEqual(first_match.phrase, '🏇')
        self.assertEqual(first_match.comment, '賽馬')
        self.assertEqual(
            0, len(mq.candidates('saima')))

    @unittest.skipIf(
        itb_emoji.IMPORT_PINYIN_SUCCESSFUL,
        "Skipping because import pinyin worked.")
    def test_candidates_pinyin_missing_zh_TW_rapidfuzz(self) -> None: # pylint: disable=invalid-name
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_TW'],
            match_algorithm = 'rapidfuzz')
        first_match = mq.candidates('賽馬')[0]
        self.assertEqual(first_match.phrase, '🏇')
        self.assertEqual(first_match.comment, '賽馬')
        self.assertEqual(
            0, len(mq.candidates('saima')))

    @unittest.skipUnless(
        itb_emoji.IMPORT_PINYIN_SUCCESSFUL,
        "Skipping because import pinyin failed.")
    def test_candidates_pinyin_available_zh_TW_classic(self) -> None: # pylint: disable=invalid-name
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_TW'],
            match_algorithm = 'classic')
        first_match = mq.candidates('賽馬')[0]
        self.assertEqual(first_match.phrase, '🏇')
        self.assertEqual(first_match.comment, '賽馬')
        first_match = mq.candidates('saima')[0]
        self.assertEqual(first_match.phrase, '🏇')
        self.assertEqual(first_match.comment, '賽馬 “sàimǎ”')

    @unittest.skipUnless(
        itb_emoji.IMPORT_PINYIN_SUCCESSFUL,
        "Skipping because import pinyin failed.")
    def test_candidates_pinyin_available_zh_TW_rapidfuzz(self) -> None: # pylint: disable=invalid-name
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_TW'],
            match_algorithm = 'rapidfuzz')
        first_match = mq.candidates('賽馬')[0]
        self.assertEqual(first_match.phrase, '🏇')
        self.assertEqual(first_match.comment, '賽馬')
        first_match = mq.candidates('saima')[0]
        self.assertEqual(first_match.phrase, '🏇')
        self.assertEqual(first_match.comment, '賽馬 “sàimǎ” [qímǎ]')

    @unittest.skipIf(
        itb_emoji.IMPORT_PYKAKASI_SUCCESSFUL,
        "Skipping because import pykakasi worked.")
    def test_candidates_pykakasi_missing_ja_JP_classic(self) -> None: # pylint: disable=invalid-name
        mq = itb_emoji.EmojiMatcher(
            languages = ['ja_JP'],
            match_algorithm = 'classic')
        self.assertEqual(
            0, len(mq.candidates('katatsumuri')))
        first_match = mq.candidates('かたつむり')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり')
        first_match = mq.candidates('かたつむり_')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり')
        first_match = mq.candidates('かたつむり＿')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり')
        first_match = mq.candidates('カタツムリ')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり [カタツムリ]')
        first_match = mq.candidates('カタツムリ_')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり [カタツムリ]')
        first_match = mq.candidates('カタツムリ＿')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり [カタツムリ]')
        first_match = mq.candidates('ネコ')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ')
        first_match = mq.candidates('ネコ_')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ')
        first_match = mq.candidates('ネコ＿')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ')
        self.assertEqual(
            0, len(mq.candidates('ねこ')))
        self.assertEqual(
            0, len(mq.candidates('ねこ_')))
        self.assertEqual(
            0, len(mq.candidates('ねこ＿')))

    @unittest.skipIf(
        itb_emoji.IMPORT_PYKAKASI_SUCCESSFUL,
        "Skipping because import pykakasi worked.")
    def test_candidates_pykakasi_missing_ja_JP_rapidfuzz(self) -> None: # pylint: disable=invalid-name
        mq = itb_emoji.EmojiMatcher(
            languages = ['ja_JP'],
            match_algorithm = 'rapidfuzz')
        self.assertEqual(
            0, len(mq.candidates('katatsumuri')))
        first_match = mq.candidates('かたつむり')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり')
        first_match = mq.candidates('かたつむり_')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり')
        first_match = mq.candidates('かたつむり＿')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり')
        first_match = mq.candidates('カタツムリ')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり [カタツムリ]')
        first_match = mq.candidates('カタツムリ_')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり [カタツムリ]')
        first_match = mq.candidates('カタツムリ＿')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり [カタツムリ]')
        first_match = mq.candidates('ネコ')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ')
        first_match = mq.candidates('ネコ_')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ')
        first_match = mq.candidates('ネコ＿')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ')
        self.assertEqual(
            0, len(mq.candidates('ねこ')))
        self.assertEqual(
            0, len(mq.candidates('ねこ_')))
        self.assertEqual(
            0, len(mq.candidates('ねこ＿')))

    @unittest.skipUnless(
        itb_emoji.IMPORT_PYKAKASI_SUCCESSFUL,
        "Skipping because import pykakasi failed.")
    def test_candidates_pykakasi_available_ja_JP_classic(self) -> None: # pylint: disable=invalid-name
        mq = itb_emoji.EmojiMatcher(
            languages = ['ja_JP'],
            match_algorithm = 'classic')
        first_match = mq.candidates('katatsumuri')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり “katatsumuri”')
        first_match = mq.candidates('かたつむり')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり')
        first_match = mq.candidates('かたつむり_')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり')
        first_match = mq.candidates('かたつむり＿')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり')
        first_match = mq.candidates('カタツムリ')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり [カタツムリ]')
        first_match = mq.candidates('カタツムリ_')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり [カタツムリ]')
        first_match = mq.candidates('カタツムリ＿')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり [カタツムリ]')
        first_match = mq.candidates('ネコ')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ')
        first_match = mq.candidates('ネコ_')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ')
        first_match = mq.candidates('ネコ＿')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ')
        first_match = mq.candidates('ねこ')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ “ねこ”')
        first_match = mq.candidates('ねこ_')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ “ねこ”')
        first_match = mq.candidates('ねこ＿')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ “ねこ”')

    @unittest.skipUnless(
        itb_emoji.IMPORT_PYKAKASI_SUCCESSFUL,
        "Skipping because import pykakasi failed.")
    def test_candidates_pykakasi_available_ja_JP_rapidfuzz(self) -> None: # pylint: disable=invalid-name
        mq = itb_emoji.EmojiMatcher(
            languages = ['ja_JP'],
            match_algorithm = 'rapidfuzz')
        first_match = mq.candidates('katatsumuri')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり “katatsumuri”')
        first_match = mq.candidates('かたつむり')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり')
        first_match = mq.candidates('かたつむり_')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり')
        first_match = mq.candidates('かたつむり＿')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり')
        first_match = mq.candidates('カタツムリ')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり [カタツムリ]')
        first_match = mq.candidates('カタツムリ_')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり [カタツムリ]')
        first_match = mq.candidates('カタツムリ＿')[0]
        self.assertEqual(first_match.phrase, '🐌')
        self.assertEqual(first_match.comment, 'かたつむり [カタツムリ]')
        first_match = mq.candidates('ネコ')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ')
        first_match = mq.candidates('ネコ_')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ')
        first_match = mq.candidates('ネコ＿')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ')
        first_match = mq.candidates('ねこ')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ “ねこ”')
        first_match = mq.candidates('ねこ_')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ “ねこ”')
        first_match = mq.candidates('ねこ＿')[0]
        self.assertEqual(first_match.phrase, '🐈')
        self.assertEqual(first_match.comment, 'ネコ “ねこ”')

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    unittest.main()
