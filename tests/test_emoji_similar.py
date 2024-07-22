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
    '..' not in itb_emoji.find_cldr_annotation_path('en'),
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
        self.assertEqual(
            mq.similar('☺', match_limit=5),
            [('☺️', 'white smiling face [☺️, So, people, face, outlined, relaxed, smile, uc1, happy, smiling]', 10), ('🥲', 'smiling face with tear [So, people, face, happy, smile, smiling]', 6), ('😇', 'smiling face with halo [So, people, face, smile, happy, smiling]', 6), ('🙂', 'slightly smiling face [So, people, face, smile, happy, smiling]', 6), ('😆', 'smiling face with open mouth and tightly-closed eyes [So, people, face, smile, happy, smiling]', 6)])

    def test_similar_white_smiling_face_it_IT(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['it_IT', 'en_US', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        self.assertEqual(
            mq.similar('☺', match_limit=5),
            [('☺️', 'faccina sorridente [☺️, contorno faccina sorridente, delineata, emozionarsi, faccina, felice, rilassata, sorridente]', 8), ('🤩', 'colpo di fulmine [faccina, felice]', 2), ('😊', 'faccina con occhi sorridenti [faccina, felice]', 2), ('🙂', 'faccina con sorriso accennato [faccina, felice]', 2), ('😂', 'faccina con lacrime di gioia [faccina, felice]', 2)])

    def test_similar_camel_en_US(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US', 'it_IT', 'es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        self.assertEqual(
            [('🐫', 'bactrian camel [🐫, So, nature, bactrian, camel, hump, uc6, animal, desert, two, two-hump]', 11), ('🐪', 'dromedary camel [So, nature, hump, uc6, animal, camel, desert]', 7), ('🐌', 'snail [So, nature, uc6, animal, nature]', 5), ('🐝', 'honeybee [So, nature, uc6, animal, nature]', 5), ('🐞', 'lady beetle [So, nature, uc6, animal, nature]', 5)],
            mq.similar('🐫', match_limit=5))

    def test_similar_camel_it_IT(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['it_IT', 'en_US','es_MX', 'es_ES', 'de_DE', 'ja_JP'])
        self.assertEqual(
            mq.similar('🐫', match_limit=5),
            [('🐫', 'cammello [🐫, animale, animali, cammello, deserto, due gobbe, gobba]', 7), ('🐪', 'dromedario [animale, animali, cammello, deserto, gobba]', 5), ('🐐', 'capra [animale, animali]', 2), ('🦒', 'giraffa [animale, animali]', 2), ('🐏', 'montone [animale, animali]', 2)])

    def test_similar_camel_de_DE(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['de_DE', 'it_IT', 'en_US','es_MX', 'es_ES', 'ja_JP'])
        self.assertEqual(
            mq.similar('🐫', match_limit=5),
            [('🐫', 'Kamel [🐫, Kamel, Tier, Wüste, zweihöckrig]', 5), ('🐪', 'Dromedar [Kamel, Tier, Wüste]', 3), ('🦙', 'Lama [Kamel, Tier]', 2), ('🐐', 'Ziege [Tier]', 1), ('🐑', 'Schaf [Tier]', 1)])

    def test_similar_camel_es_MX(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['es_MX', 'it_IT', 'de_DE', 'en_US', 'es_ES', 'ja_JP'])
        self.assertEqual(
            mq.similar('🐫', match_limit=5),
            [('🐫', 'camello [🐫, animal, camélido, camello, joroba]', 5), ('🐪', 'dromedario [animal, camélido, joroba]', 3), ('\U0001f999', 'llama [camélido]', 1), ('🐐', 'cabra [animal]', 1), ('🐑', 'oveja [animal]', 1)])

    def test_similar_camel_es_ES(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['es_ES',  'it_IT', 'es_MX', 'de_DE', 'en_US', 'ja_JP'])
        self.assertEqual(
            mq.similar('🐫', match_limit=5),
            [('🐫', 'camello [🐫, bactriano, camello, desierto, dromedario, jorobas]', 6), ('🐪', 'dromedario [camello, desierto, dromedario]', 3), ('🏜️', 'desierto [desierto]', 1), ('🐫', 'cammello [🐫, animale, animali, cammello, deserto, due gobbe, gobba]', 7), ('🐪', 'dromedario [animale, animali, cammello, deserto, gobba]', 5)])

    def test_similar_euro_sign_es_ES(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['es_ES',  'it_IT', 'es_MX', 'de_DE', 'en_US', 'ja_JP'])
        self.assertEqual(
            mq.similar('€', match_limit=5),
            [('€', 'euro [€, divisa, EUR, euro, moneda]', 5), ('£', 'libra esterlina [divisa, moneda]', 2), ('₽', 'rublo [divisa, moneda]', 2), ('₹', 'rupia india [divisa, moneda]', 2), ('¥', 'yen [divisa, moneda]', 2)])

    def test_similar_surfer_es_ES(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['es_ES',  'it_IT', 'es_MX', 'de_DE', 'en_US', 'ja_JP'])
        self.assertEqual(
            mq.similar('🏄‍♂', match_limit = 2),
            [('🏄\u200d♂️', 'hombre haciendo surf [🏄\u200d♂️, hombre, hombre haciendo surf, surf, surfero, surfista]', 6), ('🏄🏻\u200d♂️', 'hombre haciendo surf: tono de piel claro [hombre, hombre haciendo surf, surf, surfero, surfista]', 5)])

    def test_similar_de_DE_versus_de_CH(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['de_DE'])
        self.assertEqual(
            mq.similar('🤐', match_limit = 3),
            [('🤐', 'Gesicht mit Reißverschlussmund [🤐, Geheimnis, Gesicht, halten, Mund, Reißverschluss, schweigen, Smiley, wahren]', 9), ('😶', 'Gesicht ohne Mund [Gesicht, Mund, Smiley]', 3), ('🫢', 'Gesicht mit offenen Augen und Hand über dem Mund [Gesicht, Mund, Smiley]', 3)])
        mq = itb_emoji.EmojiMatcher(
            languages = ['de_CH'])
        self.assertEqual(
            mq.similar('🤐', match_limit = 3),
            [('🤐', 'Smiley mit Reissverschlussmund [🤐, Geheimnis, Gesicht, halten, Mund, Reissverschluss, schweigen, Smiley, wahren]', 9), ('🤪', 'irres Gesicht [Gesicht, Smiley]', 2), ('🥵', 'schwitzendes Gesicht [Gesicht, Smiley]', 2)])

    def test_similar_show_keywords_option_en_US(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US'])
        self.assertEqual(
            [('🐌', 'snail [🐌, So, nature, snail, uc6, animal, escargot, garden, nature, slug]', 10), ('🐞', 'lady beetle [So, nature, uc6, animal, garden, nature]', 6), ('🐛', 'bug [So, nature, uc6, animal, garden]', 5)],
            mq.similar('🐌', match_limit = 3))
        self.assertEqual(
            [('🐌', 'snail', 10), ('🐞', 'lady beetle', 6), ('🐛', 'bug', 5)],
            mq.similar('🐌', match_limit = 3, show_keywords=False))

    @unittest.skipIf(
        itb_emoji.IMPORT_PINYIN_SUCCESSFUL,
        "Skipping because import pinyin worked.")
    def test_similar_horse_racing_pinyin_missing_zh_CN(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_CN'])
        self.assertEqual(
            mq.similar('🏇', match_limit = 3),
            [('🏇', '赛马 [🏇, 三冠, 赛马, 赛马骑师, 马, 骑师, 骑马]', 7), ('🐎', '马 [赛马, 马, 骑马]', 3), ('🏇🏻', '赛马: 较浅肤色 [赛马, 马]', 2)])

    @unittest.skipUnless(
        itb_emoji.IMPORT_PINYIN_SUCCESSFUL,
        "Skipping because import pinyin failed.")
    def test_similar_horse_racing_pinyin_available_zh_CN(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_CN'])
        self.assertEqual(
            mq.similar('🏇', match_limit = 3),
            [('🏇', '赛马 [🏇, 三冠, sānguān, 赛马, sàimǎ, 赛马骑师, sàimǎqíshī, 马, mǎ, 骑师, qíshī, 骑马, qímǎ]', 13), ('🐎', '马 [赛马, sàimǎ, 马, mǎ, 骑马, qímǎ]', 6), ('🏇🏻', '赛马: 较浅肤色 [赛马, sàimǎ, 马, mǎ]', 4)])

    @unittest.skipIf(
        itb_emoji.IMPORT_PINYIN_SUCCESSFUL,
        "Skipping because import pinyin worked.")
    def test_similar_horse_racing_pinyin_missing_zh_TW(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_TW'])
        self.assertEqual(
            mq.similar('🏇', match_limit = 1),
            [('🏇', '賽馬 [🏇, 賽馬, 馬, 騎馬]', 4)])

    @unittest.skipUnless(
        itb_emoji.IMPORT_PINYIN_SUCCESSFUL,
        "Skipping because import pinyin failed.")
    def test_similar_horse_racing_pinyin_available_zh_TW(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['zh_TW'])
        self.assertEqual(
            mq.similar('🏇', match_limit = 1),
            [('🏇', '賽馬 [🏇, 賽馬, sàimǎ, 馬, mǎ, 騎馬, qímǎ]', 7)])

    @unittest.skipIf(
        itb_emoji.IMPORT_PYKAKASI_SUCCESSFUL,
        "Skipping because import pykakasi worked.")
    def test_candidates_pykakasi_missing_ja_JP(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['ja_JP'])
        self.assertEqual(
            [('🐤', 'ひよこ [🐤, ひな, ひよこ, 動物, 横を向いているひよこ, 顔, 鳥]', 7), ('🐣', '卵からかえったひよこ [ひな, ひよこ, 動物, 顔, 鳥]', 5), ('🐥', '前を向いているひよこ [ひな, ひよこ, 動物, 鳥]', 4), ('🐦', '鳥 [動物, 顔, 鳥]', 3), ('🐔', 'にわとり [動物, 顔, 鳥]', 3)],
            mq.similar('🐤', match_limit=5))
        self.assertEqual(
            [('🐌', 'かたつむり [🐌, エスカルゴ, かたつむり, カタツムリ, でんでん虫, 虫]', 6), ('🦋', 'チョウ [虫]', 1), ('🐛', '毛虫 [虫]', 1), ('🐜', 'アリ [虫]', 1), ('🐝', 'ミツバチ [虫]', 1)],
            mq.similar('🐌', match_limit=5))
        self.assertEqual(
            [('😱', '恐怖 [😱, がーん, ショック, 叫び, 叫んでいる顔, 恐怖, 顔, 驚き]', 8), ('🤯', '頭爆発 [ショック, 顔, 驚き]', 3), ('🙀', '絶望する猫 [がーん, ショック, 顔]', 3), ('😨', '青ざめ [がーん, 顔]', 2), ('😧', '苦悩 [顔, 驚き]', 2)],
            mq.similar('😱', match_limit=5))

    @unittest.skipUnless(
        itb_emoji.IMPORT_PYKAKASI_SUCCESSFUL,
        "Skipping because import pykakasi failed.")
    def test_candidates_pykakasi_available_ja_JP(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['ja_JP'])
        self.assertEqual(
            [('🐤', 'ひよこ [🐤, ひな, ひよこ, 動物, どうぶつ, 横を向いているひよこ, よこをむいているひよこ, 顔, かお, 鳥, とり, hina, hiyoko, doubutsu, yokowomuiteiruhiyoko, kao, tori]', 17), ('🐣', '卵からかえったひよこ [ひな, ひよこ, 動物, どうぶつ, 顔, かお, 鳥, とり, hina, hiyoko, doubutsu, kao, tori]', 13), ('🐥', '前を向いているひよこ [ひな, ひよこ, 動物, どうぶつ, 鳥, とり, hina, hiyoko, doubutsu, tori]', 10), ('🐦', '鳥 [動物, どうぶつ, 顔, かお, 鳥, とり, doubutsu, kao, tori]', 9), ('🐔', 'にわとり [動物, どうぶつ, 顔, かお, 鳥, とり, doubutsu, kao, tori]', 9)],
            mq.similar('🐤', match_limit=5))
        self.assertEqual(
            [('🐌', 'かたつむり [🐌, エスカルゴ, えすかるご, かたつむり, カタツムリ, でんでん虫, でんでんむし, 虫, むし, esukarugo, katatsumuri, dendenmushi, mushi]', 13), ('🦋', 'チョウ [虫, むし, mushi]', 3), ('🐛', '毛虫 [虫, むし, mushi]', 3), ('🐜', 'アリ [虫, むし, mushi]', 3), ('🐝', 'ミツバチ [虫, むし, mushi]', 3)],
            mq.similar('🐌', match_limit=5))
        self.assertEqual(
            [('😱', '恐怖 [😱, がーん, ショック, しょっく, 叫び, さけび, 叫んでいる顔, さけんでいるかお, 恐怖, きょうふ, 顔, かお, 驚き, おどろき, gaan, shokku, sakebi, sakendeirukao, kyoufu, kao, odoroki]', 21), ('🤯', '頭爆発 [ショック, しょっく, 顔, かお, 驚き, おどろき, shokku, kao, odoroki]', 9), ('🙀', '絶望する猫 [がーん, ショック, しょっく, 顔, かお, gaan, shokku, kao]', 8), ('🫨', '震えている顔 [がーん, ショック, しょっく, 顔, かお, gaan, shokku, kao]', 8), ('😧', '苦悩 [顔, かお, 驚き, おどろき, kao, odoroki]', 6)],
            mq.similar('😱', match_limit=5))


if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    unittest.main()
