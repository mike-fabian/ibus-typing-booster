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
class EmojiUnicodeVersionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None
        LOGGER.info("itb_emoji.find_cldr_annotation_path('en')->%s",
                    itb_emoji.find_cldr_annotation_path('en'))

    def tearDown(self) -> None:
        pass

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_unicode_version_emoji_data_file(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US'])
        self.assertEqual(mq.unicode_version('☺'), '0.6')
        self.assertEqual(mq.unicode_version('🤿'), '12.0')
        self.assertEqual(mq.unicode_version('⚧'), '13.0')

    def test_unicode_version_emoji_sequences_file(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US'])
        self.assertEqual(mq.unicode_version('🇿🇼'), '2.0')
        self.assertEqual(mq.unicode_version('🤳🏽'), '3.0')
        self.assertEqual(mq.unicode_version('🤲🏿'), '5.0')
        self.assertEqual(
            mq.unicode_version(
            '🏴\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f'),
            '5.0')

    def test_unicode_version_emoji_zwj_sequences_file(self) -> None:
        mq = itb_emoji.EmojiMatcher(
            languages = ['en_US'])
        # transgender flag:
        self.assertEqual(mq.unicode_version('🏳\u200d\u26a7'), '13.0')
        # transgender flag fully qualified:
        self.assertEqual(mq.unicode_version('🏳\ufe0f\u200d\u26a7\ufe0f'), '13.0')

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    unittest.main()
