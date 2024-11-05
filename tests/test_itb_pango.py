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
This file implements test cases for itb_pango.py
'''

import sys
import logging
import unittest

LOGGER = logging.getLogger('ibus-typing-booster')

IMPORT_DISTRO_SUCCESSFUL = False
try:
    import distro
    IMPORT_DISTRO_SUCCESSFUL = True
except (ImportError,):
    IMPORT_DISTRO_SUCCESSFUL = False

# pylint: disable=wrong-import-position
sys.path.insert(0, "../engine")
import itb_pango # pylint: disable=import-error
sys.path.pop(0)
# pylint: enable=wrong-import-position

# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring

class ItbPangoTestCase(unittest.TestCase):
    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def font_available_or_skip(self, font_family_name: str) -> None:
        if not font_family_name in itb_pango.get_available_font_names():
            self.skipTest(f'{font_family_name} is not available.')

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    @unittest.skipUnless(
        IMPORT_DISTRO_SUCCESSFUL
        and distro.id() == 'fedora'
        and distro.version() >= '40',
        'Skipping, fonts might be different on Fedora < 40 or other distributions.')
    def test_dejavu_sans(self) -> None:
        font_name = 'DejaVu Sans'
        fallback_font_name = 'Noto Color Emoji'
        self.font_available_or_skip(font_name)
        self.font_available_or_skip(fallback_font_name)

        text = '' # empty string
        fallback = False
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 0)
        fallback = True
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 0)

        text = '\n' # new line
        fallback = False
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 0)
        fallback = True
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 0)

        text = '\u0008' # BACKSPACE
        fallback = False
        # supported, fallback will not be used:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], False)

        text = '\u001B' # ESCAPE
        fallback = False
        # supported, fallback will not be used:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], False)

        text = ' ' # normal SPACE
        fallback = False
        # supported, fallback will not be used:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], False) # SPACE is not visible
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True)

        text = 'a' # normal letter
        fallback = False
        # supported, fallback will not be used:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True) # visible
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True)

    @unittest.skipUnless(
        IMPORT_DISTRO_SUCCESSFUL
        and distro.id() == 'fedora'
        and distro.version() >= '40',
        'Skipping, fonts might be different on Fedora < 40 or other distributions.')
    def test_titter_color_emoji(self) -> None:
        font_name = 'Twitter Color Emoji'
        fallback_font_name = 'Noto Color Emoji'
        self.font_available_or_skip(font_name)
        self.font_available_or_skip(fallback_font_name)

        text = '☺\uFE0F' # request text representation
        fallback = False
        # supported, fallback will not be used:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True)

    @unittest.skipUnless(
        IMPORT_DISTRO_SUCCESSFUL
        and distro.id() == 'fedora'
        and distro.version() >= '40',
        'Skipping, fonts might be different on Fedora < 40 or other distributions.')
    def test_symbola(self) -> None:
        font_name = 'Symbola'
        fallback_font_name = 'Noto Color Emoji'
        self.font_available_or_skip(font_name)
        self.font_available_or_skip(fallback_font_name)

        text = '☺' # Lacks Emoji_Presentation, defaults to text representation
        fallback = False
        # supported by Symbola
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True)

        text = '☺' # Lacks Emoji_Presentation, defaults to text representation
        fallback = True
        # supported by Symbola
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True)

        text = '☺\uFE0E' # request text representation
        fallback = False
        # supported by Symbola
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True)

        text = '☺\uFE0E' # request text representation
        fallback = True
        # supported by Symbola, as Text representation is requested,
        # fallback to “Noto Color Emoji” does not happen:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True)

        text = '☺\uFE0F' # request emoji representation
        fallback = False
        # supported by Symbola
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True)

        text = '☺\uFE0F' # request emoji representation
        fallback = True
        # supported by Symbola but request for emoji representation triggers fallback to
        # “Noto Color Emoji“:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], fallback_font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True)

        text = '😇︎' # has Emoji_Presentation property
        fallback = False
        # Symbola is used:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True)

        text = '😇︎' # has Emoji_Presentation property
        fallback = True
        # Symbola is used:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True)

        # 🫩︎ U+1FAE9 FACE WITH BAGS UNDER EYES, added in Unicode 16.0,
        # has Emoji_Presentation property
        text = '🫩︎'
        fallback = False
        # Symbola has no glyph for this:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], False)

         # 🫩︎ U+1FAE9 FACE WITH BAGS UNDER EYES, added in Unicode 16.0,
         # has Emoji_Presentation property
        text = '🫩︎'
        fallback = True
        # fallback to “Noto Color Emoji” is used:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], fallback_font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True)

    @unittest.skipUnless(
        IMPORT_DISTRO_SUCCESSFUL
        and distro.id() == 'fedora'
        and distro.version() >= '40',
        'Skipping, fonts might be different on Fedora < 40 or other distributions.')
    def test_twemoji(self) -> None:
        font_name = 'Twemoji'
        fallback_font_name = 'Noto Color Emoji'
        self.font_available_or_skip(font_name)
        self.font_available_or_skip(fallback_font_name)

        text = '☺\uFE0F'
        fallback = False
        # supported by Twemoji
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True)

        text = '🙂‍↕️'
        fallback = False
        # twitter-twemoji-fonts-14.0.2-5.fc40.noarch
        # does not support this and does not render this as a single glyph:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 3)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, False)
        fallback = True
        # Falling back to “Noto Color Emoji”
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], fallback_font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, False)

        text = '🇨🇶'
        fallback = False
        # “Twemoji” has no glyph for the flag of Sark (added in
        # Unicode 16.0) but “Noto Color Emoji” has it.  Even though
        # “Twemoji” has no glyph for the flag of Sark, Pango renders
        # the sequence of two code points (U+1F1E8 U+1F1F) as one
        # glyph when “Twemoji” is specified and fallback is not
        # allowed (Visually the glyph shown appears empty, there is no
        # “Tofu”):
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], False) # it’s empty!
        self.assertEqual('glyph-available' in results_for_run, False)
        fallback = True
        # falling back to “Noto Color Emoji”
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], fallback_font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, False)

        text = '🏴󠁧󠁢󠁷󠁬󠁳󠁿'
        fallback = False
        # “Twemoji” does correctly support the flag of Wales:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, False)
        fallback = True
        # with fallback enabled, Pango falls back to “Noto Color Emoji” nevertheless:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], fallback_font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, False)

        text = '🫩'
        fallback = False
        # “Twemoji” does not have the glyph for this single code point
        # emoji, (visually the glyph shown when Twemoji is used is a
        # “Tofu” block with the code point inside):
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], False) # Tofu glyph shown
        fallback = True
        # with fallback enabled, Pango correctly falls back to “Noto Color Emoji”:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], fallback_font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True) # real glyph shown

        text = '🤥' # U+1F925, single code point
        fallback = False
        # “Twemoji” does correctly support it:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True) # real glyph shown
        fallback = True
        # with fallback enabled, Pango falls back to “Noto Color Emoji” nevertheless:
        fonts_used = itb_pango.get_fonts_used_for_text(font_name, text, fallback=fallback)
        self.assertEqual(len(fonts_used), 1)
        run, results_for_run = fonts_used[0]
        self.assertEqual(run, text)
        self.assertEqual(results_for_run['font'], fallback_font_name)
        self.assertEqual(results_for_run['glyph-count'], 1)
        self.assertEqual(results_for_run['visible'], True)
        self.assertEqual('glyph-available' in results_for_run, True)
        self.assertEqual(results_for_run['glyph-available'], True) # real glyph shown

    @unittest.skipUnless(
        IMPORT_DISTRO_SUCCESSFUL
        and distro.id() == 'fedora'
        and distro.version() >= '40',
        'Skipping, fonts might be different on Fedora < 40 or other distributions.')
    def test_twemoji_fallback_needed(self) -> None:
        font_name = 'Twemoji'
        self.font_available_or_skip(font_name)
        # Twemoji does not support the emoji sequence for “head
        # shaking vertically” (U+1F642 U+200D U+2195, added in Unicode
        # 15.1):
        self.assertEqual(itb_pango.emoji_font_fallback_needed(font_name, '🙂‍↕️'), True)
        # Twemoji does not have the flag of Sark (U+1F1E8 U+1F1F6, added in Unicode 16.0):
        self.assertEqual(itb_pango.emoji_font_fallback_needed(font_name, '🇨🇶'), True)
        # Twemoji does not have U+1FAE9 FACE WITH BAGS UNDER EYES (added in Unicode 16.0):
        self.assertEqual(itb_pango.emoji_font_fallback_needed(font_name, '🫩'), True)
        # But Twemoji has U+1F925 LYING FACE (added in Unicode 9.0):
        self.assertEqual(itb_pango.emoji_font_fallback_needed(font_name, '🤥'), False)

    @unittest.skipUnless(
        IMPORT_DISTRO_SUCCESSFUL
        and distro.id() == 'fedora'
        and distro.version() >= '40',
        'Skipping, fonts might be different on Fedora < 40 or other distributions.')
    def test_twitter_color_emoji_fallback_needed(self) -> None:
        font_name = 'Twitter Color Emoji'
        self.font_available_or_skip(font_name)
        self.assertEqual(itb_pango.emoji_font_fallback_needed(font_name, '🙂‍↕️'), False)
        self.assertEqual(itb_pango.emoji_font_fallback_needed(font_name, '🤥'), False)
        self.assertEqual(itb_pango.emoji_font_fallback_needed(font_name, '☺\ufe0f'), False)
        self.assertEqual(itb_pango.emoji_font_fallback_needed(font_name, '☺\ufe0e'), False)
        # No regular characters:
        self.assertEqual(itb_pango.emoji_font_fallback_needed(font_name, 'A'), True)
        # Flag of Sark, Unicode 16.0, not available in 'Twitter Color Emoji' yet:
        self.assertEqual(itb_pango.emoji_font_fallback_needed(font_name, '🇨🇶'), True)
        # Fallback might always be needed for mor than one emoji, we don’t know:
        self.assertEqual(itb_pango.emoji_font_fallback_needed(font_name, '🏴󠁧󠁢󠁷󠁬󠁳󠁿🤥'), True)

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    unittest.main()
