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
This file implements test cases for finding similar emojis
'''

import sys
import os
import logging
import unittest

LOGGER = logging.getLogger('ibus-typing-booster')

# pylint: disable=wrong-import-position
sys.path.insert(0, "../engine")
import itb_emoji # pylint: disable=import-error
sys.path.pop(0)
# pylint: enable=wrong-import-position

# Set the domain name to something invalid to avoid using
# the translations for the doctest tests. Translations may
# make the tests fail just because some translations are
# added, changed, or missing.
itb_emoji.DOMAINNAME = ''

# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=invalid-name
# pylint: disable=line-too-long

@unittest.skipIf(
    os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/annotations'))
    != os.path.abspath(os.path.dirname(itb_emoji.find_cldr_annotation_path('en'))),
    f'Using external emoji annotations: '
    f'{itb_emoji.find_cldr_annotation_path("en")} '
    f'Testing with older emoji annotations instead '
    f'of those included in the ibus-typing-booster source is likely '
    f'to create meaningless test failures.')
class EmojiSimilarTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None
        LOGGER.info("itb_emoji.find_cldr_annotation_path('en')->%s",
                    itb_emoji.find_cldr_annotation_path('en'))

    def tearDown(self) -> None:
        pass

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_similar_query_is_not_an_emoji(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        self.assertEqual(
            mq.similar('this is not an emoji', match_limit=5),
            [])

    def test_similar_white_smiling_face_en_US(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        matches = mq.similar('☺', match_limit=5)
        self.assertEqual(matches[0].phrase, '☺️')
        self.assertEqual(matches[0].comment, 'white smiling face [☺️, So, people, face, outlined, relaxed, smile, uc1, happy, smiling]')
        self.assertEqual(matches[0].user_freq, 10.0)
        self.assertEqual(matches[1].phrase, '🥲')
        self.assertEqual(matches[1].comment,  'smiling face with tear [So, people, face, happy, smile, smiling]')
        self.assertEqual(matches[1].user_freq, 6.0)
        self.assertEqual(matches[2].phrase, '😇')
        self.assertEqual(matches[2].comment, 'smiling face with halo [So, people, face, smile, happy, smiling]')
        self.assertEqual(matches[2].user_freq, 6.0)
        self.assertEqual(matches[3].phrase, '🙂')
        self.assertEqual(matches[3].comment, 'slightly smiling face [So, people, face, smile, happy, smiling]')
        self.assertEqual(matches[3].user_freq, 6.0)
        self.assertEqual(matches[4].phrase, '😆')
        self.assertEqual(matches[4].comment, 'smiling face with open mouth and tightly-closed eyes [So, people, face, smile, happy, smiling]')
        self.assertEqual(matches[4].user_freq, 6.0)

    def test_similar_white_smiling_face_it_IT(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['it_IT', 'en_US', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        matches = mq.similar('☺', match_limit=5)
        self.assertEqual(matches[0].phrase, '☺️')
        self.assertEqual(matches[0].comment, 'faccina sorridente [☺️, contorno faccina sorridente, delineata, emozionarsi, faccina, felice, rilassata, sorridente]')
        self.assertEqual(matches[0].user_freq, 8.0)
        self.assertEqual(matches[1].phrase, '😊')
        self.assertEqual(matches[1].comment, 'faccina con occhi sorridenti [faccina, felice]')
        self.assertEqual(matches[1].user_freq, 2.0)
        self.assertEqual(matches[2].phrase, '🙂')
        self.assertEqual(matches[2].comment, 'faccina con sorriso accennato [faccina, felice]')
        self.assertEqual(matches[2].user_freq, 2.0)
        self.assertEqual(matches[3].phrase, '😂')
        self.assertEqual(matches[3].comment, 'faccina con lacrime di gioia [faccina, felice]')
        self.assertEqual(matches[3].user_freq, 2.0)
        self.assertEqual(matches[4].phrase, '😃')
        self.assertEqual(matches[4].comment, 'faccina con sorriso e occhi spalancati [felice, sorridente]')
        self.assertEqual(matches[4].user_freq, 2.0)

    def test_similar_camel_en_US(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        matches = mq.similar('🐫', match_limit=5)
        self.assertEqual(matches[0].phrase, '🐫')
        self.assertEqual(matches[0].comment, 'bactrian camel [🐫, So, nature, bactrian, camel, hump, uc6, animal, desert, two, two-hump]')
        self.assertEqual(matches[0].user_freq, 11.0)
        self.assertEqual(matches[1].phrase, '🐪')
        self.assertEqual(matches[1].comment, 'dromedary camel [So, nature, hump, uc6, animal, camel, desert]')
        self.assertEqual(matches[1].user_freq, 7.0)
        self.assertEqual(matches[2].phrase, '🐌')
        self.assertEqual(matches[2].comment, 'snail [So, nature, uc6, animal, nature]')
        self.assertEqual(matches[2].user_freq, 5.0)
        self.assertEqual(matches[3].phrase, '🐝')
        self.assertEqual(matches[3].comment, 'honeybee [So, nature, uc6, animal, nature]')
        self.assertEqual(matches[3].user_freq, 5.0)
        self.assertEqual(matches[4].phrase,'🐞')
        self.assertEqual(matches[4].comment, 'lady beetle [So, nature, uc6, animal, nature]')
        self.assertEqual(matches[4].user_freq, 5.0)

    def test_similar_camel_it_IT(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['it_IT', 'en_US','es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        matches = mq.similar('🐫', match_limit=5)
        self.assertEqual(matches[0].phrase, '🐫')
        self.assertEqual(matches[0].comment, 'cammello [🐫, animale, animali, cammello, deserto, due gobbe, gobba]')
        self.assertEqual(matches[0].user_freq, 7.0)
        self.assertEqual(matches[1].phrase, '🐪')
        self.assertEqual(matches[1].comment, 'dromedario [animale, animali, cammello, deserto, gobba]')
        self.assertEqual(matches[1].user_freq, 5.0)
        self.assertEqual(matches[2].phrase, '🐐')
        self.assertEqual(matches[2].comment, 'capra [animale, animali]')
        self.assertEqual(matches[2].user_freq, 2.0)
        self.assertEqual(matches[3].phrase, '🦒')
        self.assertEqual(matches[3].comment, 'giraffa [animale, animali]')
        self.assertEqual(matches[3].user_freq, 2.0)
        self.assertEqual(matches[4].phrase, '🐏')
        self.assertEqual(matches[4].comment, 'montone [animale, animali]')
        self.assertEqual(matches[4].user_freq, 2.0)

    def test_similar_camel_de_DE(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['de_DE', 'it_IT', 'en_US','es_MX', 'es_ES', 'ja_JP'])
        matches = mq.similar('🐫', match_limit=5)
        self.assertEqual(matches[0].phrase, '🐫')
        self.assertEqual(matches[0].comment, 'Kamel [🐫, Kamel, Tier, Wüste, zweihöckrig]')
        self.assertEqual(matches[0].user_freq, 5.0)
        self.assertEqual(matches[1].phrase, '🐪')
        self.assertEqual(matches[1].comment, 'Dromedar [Kamel, Tier, Wüste]')
        self.assertEqual(matches[1].user_freq, 3.0)
        self.assertEqual(matches[2].phrase, '🦙')
        self.assertEqual(matches[2].comment, 'Lama [Kamel, Tier]')
        self.assertEqual(matches[2].user_freq, 2.0)
        self.assertEqual(matches[3].phrase, '🐐')
        self.assertEqual(matches[3].comment, 'Ziege [Tier]')
        self.assertEqual(matches[3].user_freq, 1.0)
        self.assertEqual(matches[4].phrase, '🐑')
        self.assertEqual(matches[4].comment, 'Schaf [Tier]')
        self.assertEqual(matches[4].user_freq, 1.0)

    def test_similar_camel_es_MX(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['es_MX', 'it_IT', 'de_DE', 'en_US', 'es_ES', 'ja_JP'])
        matches = mq.similar('🐫', match_limit=5)
        self.assertEqual(matches[0].phrase, '🐫')
        self.assertEqual(matches[0].comment, 'camello [🐫, animal, camélido, camello, joroba]')
        self.assertEqual(matches[0].user_freq, 5.0)
        self.assertEqual(matches[1].phrase, '🐪')
        self.assertEqual(matches[1].comment, 'dromedario [animal, camélido, joroba]')
        self.assertEqual(matches[1].user_freq, 3.0)
        self.assertEqual(matches[2].phrase, '\U0001f999')
        self.assertEqual(matches[2].comment, 'llama [camélido]')
        self.assertEqual(matches[2].user_freq, 1.0)
        self.assertEqual(matches[3].phrase, '🐐')
        self.assertEqual(matches[3].comment, 'cabra [animal]')
        self.assertEqual(matches[3].user_freq, 1.0)
        self.assertEqual(matches[4].phrase, '🐑')
        self.assertEqual(matches[4].comment, 'oveja [animal]')
        self.assertEqual(matches[4].user_freq, 1.0)

    def test_similar_camel_es_ES(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['es_ES',  'it_IT', 'es_MX', 'de_DE', 'en_US', 'ja_JP'])
        matches = mq.similar('🐫', match_limit=5)
        self.assertEqual(matches[0].phrase, '🐫')
        self.assertEqual(matches[0].comment, 'camello [🐫, bactriano, camello, desierto, dromedario, jorobas]')
        self.assertEqual(matches[0].user_freq, 6.0)
        self.assertEqual(matches[1].phrase, '🐪')
        self.assertEqual(matches[1].comment, 'dromedario [camello, desierto, dromedario]')
        self.assertEqual(matches[1].user_freq, 3.0)
        self.assertEqual(matches[2].phrase, '🏜️')
        self.assertEqual(matches[2].comment, 'desierto [desierto]')
        self.assertEqual(matches[2].user_freq, 1.0)
        self.assertEqual(matches[3].phrase, '🐫')
        self.assertEqual(matches[3].comment, 'cammello [🐫, animale, animali, cammello, deserto, due gobbe, gobba]')
        self.assertEqual(matches[3].user_freq, 7.0)
        self.assertEqual(matches[4].phrase, '🐪')
        self.assertEqual(matches[4].comment, 'dromedario [animale, animali, cammello, deserto, gobba]')
        self.assertEqual(matches[4].user_freq, 5.0)

    def test_similar_euro_sign_es_ES(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['es_ES',  'it_IT', 'es_MX', 'de_DE', 'en_US', 'ja_JP'])
        matches = mq.similar('€', match_limit=5)
        self.assertEqual(matches[0].phrase, '€')
        self.assertEqual(matches[0].comment, 'euro [€, divisa, EUR, euro, moneda]')
        self.assertEqual(matches[0].user_freq, 5.0)
        self.assertEqual(matches[1].phrase, '£')
        self.assertEqual(matches[1].comment, 'libra esterlina [divisa, moneda]')
        self.assertEqual(matches[1].user_freq, 2.0)
        self.assertEqual(matches[2].phrase, '₽')
        self.assertEqual(matches[2].comment, 'rublo [divisa, moneda]')
        self.assertEqual(matches[2].user_freq, 2.0)
        self.assertEqual(matches[3].phrase, '₹')
        self.assertEqual(matches[3].comment, 'rupia india [divisa, moneda]')
        self.assertEqual(matches[3].user_freq, 2.0)
        self.assertEqual(matches[4].phrase, '¥')
        self.assertEqual(matches[4].comment, 'yen [divisa, moneda]')
        self.assertEqual(matches[4].user_freq, 2.0)

    def test_similar_surfer_es_ES(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['es_ES',  'it_IT', 'es_MX', 'de_DE', 'en_US', 'ja_JP'])
        matches = mq.similar('🏄‍♂', match_limit = 2)
        self.assertEqual(matches[0].phrase, '🏄\u200d♂️')
        self.assertEqual(matches[0].comment, 'hombre haciendo surf [🏄\u200d♂️, hombre, hombre haciendo surf, surf, surfero, surfista]')
        self.assertEqual(matches[0].user_freq, 6.0)
        self.assertEqual(matches[1].phrase, '🏄🏻\u200d♂️')
        self.assertEqual(matches[1].comment, 'hombre haciendo surf: tono de piel claro [hombre, hombre haciendo surf, surf, surfero, surfista]')
        self.assertEqual(matches[1].user_freq, 5.0)

    def test_similar_de_DE_versus_de_CH(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['de_DE'])
        matches = mq.similar('🤐', match_limit = 3)
        self.assertEqual(matches[0].phrase, '🤐')
        self.assertEqual(matches[0].comment, 'Gesicht mit Reißverschlussmund [🤐, Geheimnis, Gesicht, halten, Mund, Reißverschluss, schweigen, Smiley, wahren]')
        self.assertEqual(matches[0].user_freq, 9.0)
        self.assertEqual(matches[1].phrase, '😶')
        self.assertEqual(matches[1].comment, 'Gesicht ohne Mund [Gesicht, Mund, Smiley]')
        self.assertEqual(matches[1].user_freq, 3.0)
        self.assertEqual(matches[2].phrase, '🫢')
        self.assertEqual(matches[2].comment, 'Gesicht mit offenen Augen und Hand über dem Mund [Gesicht, Mund, Smiley]')
        self.assertEqual(matches[2].user_freq, 3.0)
        mq = itb_emoji.EmojiMatcher(
            languages = ['de_CH'])
        matches = mq.similar('🤐', match_limit = 3)
        self.assertEqual(matches[0].phrase, '🤐')
        self.assertEqual(matches[0].comment, 'Gesicht mit Reissverschlussmund [🤐, Geheimnis, Gesicht, halten, Mund, Reissverschluss, schweigen, Smiley, wahren]')
        self.assertEqual(matches[0].user_freq, 9.0)
        self.assertEqual(matches[1].phrase, '😅')
        self.assertEqual(matches[1].comment, 'grinsendes Gesicht mit Schweisstropfen [Gesicht, Mund, Smiley]')
        self.assertEqual(matches[1].user_freq, 3.0)
        self.assertEqual(matches[2].phrase, '😃')
        self.assertEqual(matches[2].comment, 'grinsendes Gesicht mit grossen Augen [Gesicht, Mund, Smiley]')
        self.assertEqual(matches[2].user_freq, 3.0)

    def test_similar_show_keywords_option_en_US(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US'])
        matches =  mq.similar('🐌', match_limit = 3)
        self.assertEqual(matches[0].phrase, '🐌')
        self.assertEqual(matches[0].comment, 'snail [🐌, So, nature, snail, uc6, animal, escargot, garden, nature, slug]')
        self.assertEqual(matches[0].user_freq, 10.0)
        self.assertEqual(matches[1].phrase, '🐞')
        self.assertEqual(matches[1].comment, 'lady beetle [So, nature, uc6, animal, garden, nature]')
        self.assertEqual(matches[1].user_freq, 6.0)
        self.assertEqual(matches[2].phrase, '🐛')
        self.assertEqual(matches[2].comment, 'bug [So, nature, uc6, animal, garden]')
        self.assertEqual(matches[2].user_freq, 5.0)
        matches = mq.similar('🐌', match_limit = 3, show_keywords=False)
        self.assertEqual(matches[0].phrase, '🐌')
        self.assertEqual(matches[0].comment, 'snail')
        self.assertEqual(matches[0].user_freq, 10.0)
        self.assertEqual(matches[1].phrase, '🐞')
        self.assertEqual(matches[1].comment, 'lady beetle')
        self.assertEqual(matches[1].user_freq, 6.0)
        self.assertEqual(matches[2].phrase, '🐛')
        self.assertEqual(matches[2].comment, 'bug',)
        self.assertEqual(matches[2].user_freq, 5.0)

    @unittest.skipIf(
        itb_emoji.pinyin is not None,
        "Skipping because import pinyin worked.")
    def test_similar_horse_racing_pinyin_missing_zh_CN(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_CN'])
        matches = mq.similar('🏇', match_limit = 3)
        self.assertEqual(matches[0].phrase, '🏇')
        self.assertEqual(matches[0].comment, '赛马 [🏇, 三冠, 赛马, 赛马骑师, 马, 骑师, 骑马]')
        self.assertEqual(matches[0].user_freq, 7.0)
        self.assertEqual(matches[1].phrase, '🏇🏻')
        self.assertEqual(matches[1].comment, '赛马: 较浅肤色 [三冠, 赛马, 赛马骑师, 马, 骑师, 骑马]')
        self.assertEqual(matches[1].user_freq, 6.0)
        self.assertEqual(matches[2].phrase, '🏇🏼')
        self.assertEqual(matches[2].comment, '赛马: 中等-浅肤色 [三冠, 赛马, 赛马骑师, 马, 骑师, 骑马]')
        self.assertEqual(matches[2].user_freq, 6.0)

    @unittest.skipUnless(
        itb_emoji.pinyin is not None,
        "Skipping because import pinyin failed.")
    def test_similar_horse_racing_pinyin_available_zh_CN(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_CN'])
        matches = mq.similar('🏇', match_limit = 3)
        self.assertEqual(matches[0].phrase, '🏇')
        self.assertEqual(matches[0].comment, '赛马 [🏇, 三冠, sānguān, 赛马, sàimǎ, 赛马骑师, sàimǎqíshī, 马, mǎ, 骑师, qíshī, 骑马, qímǎ]')
        self.assertEqual(matches[0].user_freq, 13.0)
        self.assertEqual(matches[1].phrase, '🏇🏻')
        self.assertEqual(matches[1].comment, '赛马: 较浅肤色 [三冠, sānguān, 赛马, sàimǎ, 赛马骑师, sàimǎqíshī, 马, mǎ, 骑师, qíshī, 骑马, qímǎ]')
        self.assertEqual(matches[1].user_freq, 12.0)
        self.assertEqual(matches[2].phrase, '🏇🏼')
        self.assertEqual(matches[2].comment, '赛马: 中等-浅肤色 [三冠, sānguān, 赛马, sàimǎ, 赛马骑师, sàimǎqíshī, 马, mǎ, 骑师, qíshī, 骑马, qímǎ]')
        self.assertEqual(matches[2].user_freq, 12.0)

    @unittest.skipIf(
        itb_emoji.pinyin is not None,
        "Skipping because import pinyin worked.")
    def test_similar_horse_racing_pinyin_missing_zh_TW(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_TW'])
        matches = mq.similar('🏇', match_limit = 1)
        self.assertEqual(matches[0].phrase, '🏇')
        self.assertEqual(matches[0].comment, '賽馬 [🏇, 賽馬, 馬, 騎馬]')
        self.assertEqual(matches[0].user_freq, 4.0)

    @unittest.skipUnless(
        itb_emoji.pinyin is not None,
        "Skipping because import pinyin failed.")
    def test_similar_horse_racing_pinyin_available_zh_TW(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_TW'])
        matches = mq.similar('🏇', match_limit = 1)
        self.assertEqual(matches[0].phrase, '🏇')
        self.assertEqual(matches[0].comment, '賽馬 [🏇, 賽馬, sàimǎ, 馬, mǎ, 騎馬, qímǎ]')
        self.assertEqual(matches[0].user_freq, 7.0)

    @unittest.skipIf(
        itb_emoji.pykakasi is not None,
        "Skipping because import pykakasi worked.")
    def test_candidates_pykakasi_missing_ja_JP(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['ja_JP'])
        matches = mq.similar('🐤', match_limit=5)
        self.assertEqual(matches[0].phrase, '🐤')
        self.assertEqual(matches[0].comment, 'ひよこ [🐤, ひな, ひよこ, 動物, 横を向いているひよこ, 顔, 鳥]')
        self.assertEqual(matches[0].user_freq, 7.0)
        self.assertEqual(matches[1].phrase, '🐣',)
        self.assertEqual(matches[1].comment, '卵からかえったひよこ [ひな, ひよこ, 動物, 顔, 鳥]')
        self.assertEqual(matches[1].user_freq, 5.0)
        self.assertEqual(matches[2].phrase, '🐥')
        self.assertEqual(matches[2].comment, '前を向いているひよこ [ひな, ひよこ, 動物, 鳥]')
        self.assertEqual(matches[2].user_freq, 4.0)
        self.assertEqual(matches[3].phrase, '🐦')
        self.assertEqual(matches[3].comment, '鳥 [動物, 顔, 鳥]')
        self.assertEqual(matches[3].user_freq, 3.0)
        self.assertEqual(matches[4].phrase, '🐔')
        self.assertEqual(matches[4].comment, 'にわとり [動物, 顔, 鳥]')
        self.assertEqual(matches[4].user_freq, 3.0)
        matches = mq.similar('🐌', match_limit=5)
        self.assertEqual(matches[0].phrase, '🐌')
        self.assertEqual(matches[0].comment, 'かたつむり [🐌, エスカルゴ, かたつむり, カタツムリ, でんでん虫, 虫]')
        self.assertEqual(matches[0].user_freq, 6.0)
        self.assertEqual(matches[1].phrase, '🦋')
        self.assertEqual(matches[1].comment, 'チョウ [虫]')
        self.assertEqual(matches[1].user_freq, 1.0)
        self.assertEqual(matches[2].phrase, '🐛')
        self.assertEqual(matches[2].comment, '毛虫 [虫]')
        self.assertEqual(matches[2].user_freq, 1.0)
        self.assertEqual(matches[3].phrase, '🐜')
        self.assertEqual(matches[3].comment, 'アリ [虫]')
        self.assertEqual(matches[3].user_freq, 1.0)
        self.assertEqual(matches[4].phrase, '🐝')
        self.assertEqual(matches[4].comment, 'ミツバチ [虫]')
        self.assertEqual(matches[4].user_freq, 1.0)
        matches = mq.similar('😱', match_limit=5)
        self.assertEqual(matches[0].phrase, '😱')
        self.assertEqual(matches[0].comment, '恐怖 [😱, がーん, ショック, 叫び, 叫んでいる顔, 恐怖, 顔, 驚き]')
        self.assertEqual(matches[0].user_freq, 8.0)
        self.assertEqual(matches[1].phrase, '🤯')
        self.assertEqual(matches[1].comment, '頭爆発 [ショック, 顔, 驚き]')
        self.assertEqual(matches[1].user_freq, 3.0)
        self.assertEqual(matches[2].phrase, '🙀')
        self.assertEqual(matches[2].comment, '絶望する猫 [がーん, ショック, 顔]')
        self.assertEqual(matches[2].user_freq, 3.0)
        self.assertEqual(matches[3].phrase, '😨')
        self.assertEqual(matches[3].comment, '青ざめ [がーん, 顔]')
        self.assertEqual(matches[3].user_freq, 2.0)
        self.assertEqual(matches[4].phrase, '😧')
        self.assertEqual(matches[4].comment, '苦悩 [顔, 驚き]')
        self.assertEqual(matches[4].user_freq, 2.0)

    @unittest.skipUnless(
        itb_emoji.pykakasi is not None,
        "Skipping because import pykakasi failed.")
    def test_candidates_pykakasi_available_ja_JP(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['ja_JP'])
        matches = mq.similar('🐤', match_limit=5)
        self.assertEqual(matches[0].phrase, '🐤')
        self.assertEqual(matches[0].comment, 'ひよこ [🐤, ひな, ひよこ, 動物, どうぶつ, 横を向いているひよこ, よこをむいているひよこ, 顔, かお, 鳥, とり, hina, hiyoko, doubutsu, yokowomuiteiruhiyoko, kao, tori]')
        self.assertEqual(matches[0].user_freq, 17.0)
        self.assertEqual(matches[1].phrase, '🐣')
        self.assertEqual(matches[1].comment, '卵からかえったひよこ [ひな, ひよこ, 動物, どうぶつ, 顔, かお, 鳥, とり, hina, hiyoko, doubutsu, kao, tori]')
        self.assertEqual(matches[1].user_freq, 13.0)
        self.assertEqual(matches[2].phrase, '🐥')
        self.assertEqual(matches[2].comment, '前を向いているひよこ [ひな, ひよこ, 動物, どうぶつ, 鳥, とり, hina, hiyoko, doubutsu, tori]')
        self.assertEqual(matches[2].user_freq, 10.0)
        self.assertEqual(matches[3].phrase, '🐦')
        self.assertEqual(matches[3].comment, '鳥 [動物, どうぶつ, 顔, かお, 鳥, とり, doubutsu, kao, tori]')
        self.assertEqual(matches[3].user_freq, 9.0)
        self.assertEqual(matches[4].phrase, '🐔')
        self.assertEqual(matches[4].comment, 'にわとり [動物, どうぶつ, 顔, かお, 鳥, とり, doubutsu, kao, tori]')
        self.assertEqual(matches[4].user_freq, 9.0)
        matches = mq.similar('🐌', match_limit=5)
        self.assertEqual(matches[0].phrase, '🐌')
        self.assertEqual(matches[0].comment, 'かたつむり [🐌, エスカルゴ, えすかるご, かたつむり, カタツムリ, でんでん虫, でんでんむし, 虫, むし, esukarugo, katatsumuri, dendenmushi, mushi]')
        self.assertEqual(matches[0].user_freq, 13.0)
        self.assertEqual(matches[1].phrase, '🦋')
        self.assertEqual(matches[1].comment, 'チョウ [虫, むし, mushi]')
        self.assertEqual(matches[1].user_freq, 3.0)
        self.assertEqual(matches[2].phrase, '🐛')
        self.assertEqual(matches[2].comment, '毛虫 [虫, むし, mushi]')
        self.assertEqual(matches[2].user_freq, 3.0)
        self.assertEqual(matches[3].phrase, '🐜')
        self.assertEqual(matches[3].comment, 'アリ [虫, むし, mushi]')
        self.assertEqual(matches[3].user_freq, 3.0)
        self.assertEqual(matches[4].phrase, '🐝')
        self.assertEqual(matches[4].comment, 'ミツバチ [虫, むし, mushi]')
        self.assertEqual(matches[4].user_freq, 3.0)
        matches = mq.similar('😱', match_limit=5)
        self.assertEqual(matches[0].phrase, '😱')
        self.assertEqual(matches[0].comment, '恐怖 [😱, がーん, ショック, しょっく, 叫び, さけび, 叫んでいる顔, さけんでいるかお, 恐怖, きょうふ, 顔, かお, 驚き, おどろき, gaan, shokku, sakebi, sakendeirukao, kyoufu, kao, odoroki]')
        self.assertEqual(matches[0].user_freq, 21.0)
        self.assertEqual(matches[1].phrase, '🤯')
        self.assertEqual(matches[1].comment, '頭爆発 [ショック, しょっく, 顔, かお, 驚き, おどろき, shokku, kao, odoroki]')
        self.assertEqual(matches[1].user_freq, 9.0)
        self.assertEqual(matches[2].phrase, '🙀')
        self.assertEqual(matches[2].comment, '絶望する猫 [がーん, ショック, しょっく, 顔, かお, gaan, shokku, kao]')
        self.assertEqual(matches[2].user_freq, 8.0)
        self.assertEqual(matches[3].phrase, '🫨')
        self.assertEqual(matches[3].comment, '震えている顔 [がーん, ショック, しょっく, 顔, かお, gaan, shokku, kao]')
        self.assertEqual(matches[3].user_freq, 8.0)
        self.assertEqual(matches[4].phrase, '😧')
        self.assertEqual(matches[4].comment, '苦悩 [顔, かお, 驚き, おどろき, kao, odoroki]')
        self.assertEqual(matches[4].user_freq, 6.0)

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    unittest.main()
