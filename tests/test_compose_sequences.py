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
This file implements test cases for compose sequences.
'''

import sys
import logging
import locale
import unittest

# pylint: disable=wrong-import-position
from gi import require_version # type: ignore
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore
# pylint: enable=wrong-import-position

LOGGER = logging.getLogger('ibus-typing-booster')

sys.path.insert(0, "../engine")
import itb_util # pylint: disable=import-error
sys.path.pop(0)

import testutils # pylint: disable=import-error

# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring

class ComposeSequencesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        locale.setlocale(locale.LC_CTYPE, 'en_US.UTF-8')
        self._compose_sequences = itb_util.ComposeSequences()

    def tearDown(self) -> None:
        pass

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    def test_adding_and_deleting_compose_sequences(self) -> None:
        # pylint: disable=protected-access
        self._compose_sequences._add_compose_sequence(
            '<Multi_key> <e> <m> <p> <t> <y>', '∅')
        available_keyvals = None
        keyvals = [IBus.KEY_Multi_key,
                   IBus.KEY_e,
                   IBus.KEY_m,
                   IBus.KEY_p]
        completions = self._compose_sequences.find_compose_completions(
            keyvals, available_keyvals)
        self.assertEqual(
            ['ty'], self._compose_sequences._lookup_representations(completions))
        keyvals = [IBus.KEY_Multi_key,
                   IBus.KEY_e,
                   IBus.KEY_m,
                   IBus.KEY_p,
                   IBus.KEY_t,
                   IBus.KEY_y]
        completions = self._compose_sequences.find_compose_completions(
            keyvals, available_keyvals)
        self.assertEqual(
            [], self._compose_sequences._lookup_representations(completions))
        self.assertEqual(
            "∅", self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_e,
                 IBus.KEY_m,
                 IBus.KEY_p,
                 IBus.KEY_t,
                 IBus.KEY_y]))
        # Define a shorter compose sequence overriding the previous longer one:
        self._compose_sequences._add_compose_sequence(
            '<Multi_key> <e> <m> <p> <t>', '🕳️')
        available_keyvals = None
        keyvals = [IBus.KEY_Multi_key,
                   IBus.KEY_e,
                   IBus.KEY_m,
                   IBus.KEY_p]
        completions = self._compose_sequences.find_compose_completions(
            keyvals, available_keyvals)
        self.assertEqual(
            ['t'], self._compose_sequences._lookup_representations(completions))
        keyvals = [IBus.KEY_Multi_key,
                   IBus.KEY_e,
                   IBus.KEY_m,
                   IBus.KEY_p,
                   IBus.KEY_t]
        completions = self._compose_sequences.find_compose_completions(
            keyvals, available_keyvals)
        self.assertEqual(
            [], self._compose_sequences._lookup_representations(completions))
        keyvals = [IBus.KEY_Multi_key,
                   IBus.KEY_e,
                   IBus.KEY_m,
                   IBus.KEY_p,
                   IBus.KEY_t,
                   IBus.KEY_y]
        completions = self._compose_sequences.find_compose_completions(
            keyvals, available_keyvals)
        self.assertEqual(
            [], self._compose_sequences._lookup_representations(completions))
        self.assertEqual(
            "🕳️",
            self._compose_sequences.compose(
            [IBus.KEY_Multi_key,
             IBus.KEY_e,
             IBus.KEY_m,
             IBus.KEY_p,
             IBus.KEY_t]))
        # The sequence '<Multi_key> <e> <m> <p> <t> <y> does not exist
        # anymore now, but '<Multi_key> <e> <m> <p> <t>' already gives a result
        # and the trailing '<y>' is ignored:
        self.assertEqual(
            "🕳️",
            self._compose_sequences.compose(
            [IBus.KEY_Multi_key,
             IBus.KEY_e,
             IBus.KEY_m,
             IBus.KEY_p,
             IBus.KEY_t,
             IBus.KEY_y]))
        # Now remove a compose sequence by using an empty replacement text:
        self._compose_sequences._add_compose_sequence(
            '<Multi_key> <e> <m> <p> <t> <y>', '')
        available_keyvals = None
        keyvals = [IBus.KEY_Multi_key,
                   IBus.KEY_e,
                   IBus.KEY_m,
                   IBus.KEY_p]
        completions = self._compose_sequences.find_compose_completions(
            keyvals, available_keyvals)
        self.assertEqual(
            [], self._compose_sequences._lookup_representations(completions))
        keyvals = [IBus.KEY_Multi_key,
                   IBus.KEY_e,
                   IBus.KEY_m,
                   IBus.KEY_p,
                   IBus.KEY_t]
        completions = self._compose_sequences.find_compose_completions(
            keyvals, available_keyvals)
        self.assertEqual(
            [], self._compose_sequences._lookup_representations(completions))
        keyvals = [IBus.KEY_Multi_key,
                   IBus.KEY_e,
                   IBus.KEY_m,
                   IBus.KEY_p,
                   IBus.KEY_t,
                   IBus.KEY_y]
        completions = self._compose_sequences.find_compose_completions(
            keyvals, available_keyvals)
        self.assertEqual(
            [], self._compose_sequences._lookup_representations(completions))
        # Invalid now, sequence has been deleted (invalid sequence returns
        # and empty string):
        self.assertEqual(
            '',
            self._compose_sequences.compose(
            [IBus.KEY_Multi_key,
             IBus.KEY_e,
             IBus.KEY_m,
             IBus.KEY_p,
             IBus.KEY_t,
             IBus.KEY_y]))
        self.assertEqual(
            '',
            self._compose_sequences.compose(
            [IBus.KEY_Multi_key,
             IBus.KEY_e,
             IBus.KEY_m,
             IBus.KEY_p]))
        # Check that there are still sequences starting with '<Multi_key> <e>'
        # they should not have been deleted:
        available_keyvals = None
        keyvals = [IBus.KEY_Multi_key,
                   IBus.KEY_e]
        completions = self._compose_sequences.find_compose_completions(
            keyvals, available_keyvals)
        self.assertNotEqual(
            [], self._compose_sequences._lookup_representations(completions))
        self.assertEqual(
            None,
            self._compose_sequences.compose(
            [IBus.KEY_Multi_key,
             IBus.KEY_e]))
        self.assertEqual(
            '€',
            self._compose_sequences.compose(
            [IBus.KEY_Multi_key,
             IBus.KEY_e,
             IBus.KEY_equal]))
        # pylint: enable=protected-access

    def test_preedit_representations(self) -> None:
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [IBus.KEY_Multi_key,
                 IBus.KEY_asciitilde,
                 IBus.KEY_dead_circumflex,
                 IBus.KEY_A]),
            '~^A')
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [IBus.KEY_Multi_key,
                 IBus.KEY_asciitilde,
                 IBus.KEY_Multi_key,
                 IBus.KEY_dead_circumflex,
                 IBus.KEY_A]),
            '~·^A')
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [0x2276]),
            '≶')
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [IBus.KEY_Multi_key, 0x2276]),
            '≶')
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [IBus.KEY_Multi_key, 0x093C]),
            '़')
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [IBus.KEY_a, IBus.KEY_dead_belowdiaeresis]),
            'a\u00A0\u0324')

    def test_compose(self) -> None:
        # Valid sequence should return a composed result:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_asciitilde,
                 IBus.KEY_dead_circumflex,
                 IBus.KEY_A]),
            'Ẫ')
        # Incomplete sequence should return None:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_asciitilde,
                 IBus.KEY_dead_circumflex]),
            None)
        # Invalid sequence should return empty string:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_circumflex,
                 IBus.KEY_openstar]),
            '')
        # An empty sequence should return an empty string:
        self.assertEqual(
            self._compose_sequences.compose([]), '')
        # Valid sequence, would give a different result in cs_CZ locale,
        # here is the result for non-cs_CZ locales:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_caron,
                 IBus.KEY_u]),
            'ǔ')
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_a,
                 IBus.KEY_quotedbl]),
            'ä')
        # Key values of Unicode characters are equal to their Unicode
        # code points:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 0x0061, # U+0061 LATIN SMALL LETTER A
                 IBus.KEY_quotedbl]),
            'ä')

    def test_compose_parse_double_quote_in_result(self) -> None:
        # Make sure this sequence from
        # /usr/share/X11/locale/en_US.UTF-8/Compose is parsed
        # correctly:
        #
        # <dead_diaeresis> <space> : "\"" quotedbl # REVERSE SOLIDUS
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_diaeresis,
                 IBus.KEY_space]),
            '"')

    def test_compose_arabic(self) -> None:
        # /usr/share/X11/locale/en_US.UTF-8/Compose contains:
        # # Arabic Lam-Alef ligatures
        # <UFEFB>	:   "لا" # ARABIC LIGATURE LAM WITH ALEF
        # <UFEF7>	:   "لأ" # ARABIC LIGATURE LAM WITH ALEF WITH HAMZA ABOVE
        # <UFEF9>	:   "لإ" # ARABIC LIGATURE LAM WITH ALEF WITH HAMZA BELOW
        # <UFEF5>	:   "لآ" # ARABIC LIGATURE LAM WITH ALEF WITH MADDA ABOVE
        self.assertEqual(
            self._compose_sequences.compose(
                [0x0100FEFB]),
                '\u0644\u0627')
        self.assertEqual(
            self._compose_sequences.compose(
                [0x0100FEF7]),
                '\u0644\u0623')
        self.assertEqual(
            self._compose_sequences.compose(
                [0x0100FEF9]),
                '\u0644\u0625')
        self.assertEqual(
            self._compose_sequences.compose(
                [0x0100FEF5]),
                '\u0644\u0622')

    @unittest.skipIf(
        testutils.set_locale_error('cs_CZ.UTF-8'),
        f'Skipping, this test needs a locale which is not available: '
        f'{testutils.set_locale_error("cs_CZ.UTF-8")}')
    def test_compose_cs_CZ(self) -> None: # pylint: disable=invalid-name
        # /usr/share/X11/locale/cs_CZ.UTF-8/Compose overrides some of
        # the compose sequences from
        # /usr/share/X11/locale/en_US.UTF-8/Compose:
        locale.setlocale(locale.LC_CTYPE, 'cs_CZ.UTF-8')
        self._compose_sequences = itb_util.ComposeSequences()
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_caron,
                 IBus.KEY_u]),
            'ů')
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_caron,
                 IBus.KEY_U]),
            'Ů')
        # This sequence comes from
        # /usr/share/X11/locale/en_US.UTF-8/Compose and is not
        # overridden in /usr/share/X11/locale/cs_CZ.UTF-8/:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_a,
                 IBus.KEY_quotedbl]),
            'ä')

    @unittest.skipIf(
        testutils.set_locale_error('km_KH.UTF-8'),
        f'Skipping, this test needs a locale which is not available: '
        f'{testutils.set_locale_error("km_KH.UTF-8")}')
    def test_compose_km_KH(self) -> None: # pylint: disable=invalid-name
        locale.setlocale(locale.LC_CTYPE, 'km_KH.UTF-8')
        self._compose_sequences = itb_util.ComposeSequences()
        # This sequence comes from
        # /usr/share/X11/locale/en_US.UTF-8/Compose and is not
        # overridden in /usr/share/X11/locale/km_KH.UTF-8/:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_a,
                 IBus.KEY_quotedbl]),
            'ä')
        # /usr/share/X11/locale/km_KH.UTF-8/Compose overrides some of
        # the compose sequences from
        # /usr/share/X11/locale/en_US.UTF-8/Compose (Well, actually it
        # doesn’t, all sequences from the km_KH.UTF-8 Compose file are
        # already in the en_US.UTF-8 Compose file. Therefore, the
        # km_KH.UTF-8 Compose file does not really add anything at all
        # (See
        # https://gitlab.freedesktop.org/xorg/lib/libx11/issues/106):
        self.assertEqual(
            self._compose_sequences.compose(
                [0x010017FF]),
            'ាំ')

    @unittest.skipIf(
        testutils.set_locale_error('pt_BR.UTF-8'),
        f'Skipping, this test needs a locale which is not available: '
        f'{testutils.set_locale_error("pt_BR.UTF-8")}')
    def test_compose_pt_BR(self) -> None: # pylint: disable=invalid-name
        # This sequence comes from
        # /usr/share/X11/locale/en_US.UTF-8/Compose and is not
        # overridden in /usr/share/X11/locale/pt_BR.UTF-8/:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_a,
                 IBus.KEY_quotedbl]),
            'ä')
        # These will be overridden:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_acute,
                 IBus.KEY_C]),
            'Ć')
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_acute,
                 IBus.KEY_c]),
            'ć')
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_U,
                 IBus.KEY_comma]),
            'Ų')
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_U,
                 IBus.KEY_comma,
                 IBus.KEY_E]),
            'Ų')
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_U,
                 IBus.KEY_comma,
                 IBus.KEY_e]),
            'Ų')
        # /usr/share/X11/locale/pt_BR.UTF-8/Compose overrides some of
        # the compose sequences from
        # /usr/share/X11/locale/en_US.UTF-8/Compose:
        locale.setlocale(locale.LC_CTYPE, 'pt_BR.UTF-8')
        self._compose_sequences = itb_util.ComposeSequences()
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_acute,
                 IBus.KEY_C]),
            'Ç')
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_acute,
                 IBus.KEY_c]),
            'ç')
        # Incomplete sequence now because overridden by the longer
        # sequences:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_U,
                 IBus.KEY_comma]),
            None)
        # The new longer sequences:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_U,
                 IBus.KEY_comma,
                 IBus.KEY_E]),
            'Ḝ')
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_U,
                 IBus.KEY_comma,
                 IBus.KEY_e]),
            'ḝ')
        # This sequence comes from
        # /usr/share/X11/locale/en_US.UTF-8/Compose and is not
        # overridden in /usr/share/X11/locale/pt_BR.UTF-8/:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_a,
                 IBus.KEY_quotedbl]),
            'ä')

    @unittest.skipIf(
        testutils.set_locale_error('pt_PT.UTF-8'),
        f'Skipping, this test needs a locale which is not available: '
        f'{testutils.set_locale_error("pt_PT.UTF-8")}')
    def test_compose_pt_PT(self) -> None: # pylint: disable=invalid-name
        # These sequences come from
        # /usr/share/X11/locale/en_US.UTF-8/Compose and is not
        # overridden in /usr/share/X11/locale/pt_PT.UTF-8/:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_a,
                 IBus.KEY_quotedbl]),
            'ä')
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_U,
                 IBus.KEY_comma]),
            'Ų')
        # These will be overridden:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_acute,
                 IBus.KEY_C]),
            'Ć')
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_acute,
                 IBus.KEY_c]),
            'ć')
        # /usr/share/X11/locale/pt_PT.UTF-8/Compose overrides some of
        # the compose sequences from
        # /usr/share/X11/locale/en_US.UTF-8/Compose:
        locale.setlocale(locale.LC_CTYPE, 'pt_PT.UTF-8')
        self._compose_sequences = itb_util.ComposeSequences()
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_acute,
                 IBus.KEY_C]),
            'Ç')
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_acute,
                 IBus.KEY_c]),
            'ç')
        # This sequence comes from
        # /usr/share/X11/locale/en_US.UTF-8/Compose and is not
        # overridden in /usr/share/X11/locale/pt_BR.UTF-8/:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_a,
                 IBus.KEY_quotedbl]),
            'ä')
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_U,
                 IBus.KEY_comma]),
            'Ų')

    @unittest.skipIf(
        testutils.set_locale_error('am_ET.UTF-8'),
        f'Skipping, this test needs a locale which is not available: '
        f'{testutils.set_locale_error("am_ET.UTF-8")}')
    def test_compose_am_ET(self) -> None: # pylint: disable=invalid-name
        # These sequences come from
        # /usr/share/X11/locale/en_US.UTF-8/Compose:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_a,
                 IBus.KEY_quotedbl]),
            'ä')
        # /usr/share/X11/locale/am_ET.UTF-8/Compose overrides some of
        # the compose sequences from
        # /usr/share/X11/locale/en_US.UTF-8/Compose (I think almost
        # all of the compose sequences in the am_ET.UTF-8 compose file
        # are weird, I think they make it impossible to type a normal
        # ASCII “u” and a normal ASCII “\” in am_ET.UTF-8 locale when
        # compose support works. ibus-typing-booster currently ignores
        # compose sequences which do not start with either Multi_key
        # or a dead key. I.e. ibus-typing-booster currently ignores
        # all compose sequences from the am_ET.UTF-8 compose file):
        locale.setlocale(locale.LC_CTYPE, 'am_ET.UTF-8')
        self._compose_sequences = itb_util.ComposeSequences()
        # pylint: disable=protected-access
        if (self._compose_sequences._locale_compose_file()
            != '/usr/share/X11/locale/am_ET.UTF-8/Compose'):
            self.skipTest(
                '/usr/share/X11/locale/am_ET.UTF-8/Compose not available')
        # pylint: enable=protected-access
        if self._compose_sequences.compose([0x0100FE75, 0x01001200]) != '':
            self.skipTest(
                'New Compose file updated by '
                'Benno Schulenberg <bensberg@telfort.nl> '
                'is installed, see: '
                'https://gitlab.freedesktop.org/xorg/lib/libx11/-/commit/488b156fe2cc8aca6946a49236ec7b7698fceda4') # pylint: disable=line-too-long
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_u,
                 0x01001200]),
            'ሁ')
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_backslash,
                 IBus.KEY_quotedbl]),
            '፥')
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_backslash,
                 IBus.KEY_apostrophe]),
            '፦')
        # This sequence comes from
        # /usr/share/X11/locale/en_US.UTF-8/Compose and because
        # /usr/share/X11/locale/am_ET.UTF-8/Compose does not include
        # /usr/share/X11/locale/en_US.UTF-8/Compose this sequence
        # is invalid in am_ET.UTF-8 locale and therefore returns
        # an empty string:
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_a,
                 IBus.KEY_quotedbl]),
            '')

    def test_reasonable_dead_key_sequences(self) -> None:
        # “reasonable” dead key sequences are are handled even if they
        # are not defined in any Compose file.
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_circumflex,
                 IBus.KEY_x]),
            '\u0078\u0302') # x̂
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_abovedot,
                 IBus.KEY_dead_macron,
                 IBus.KEY_e]),
            '\u0113\u0307') # ē̇
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_dead_macron,
                 IBus.KEY_dead_abovedot,
                 IBus.KEY_e]),
            '\u0117\u0304') # ė̄

    def test_keypad_fallback(self) -> None:
        self.assertEqual(
            None,
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_minus, IBus.KEY_minus],
                keypad_fallback=True))
        self.assertEqual(
            None,
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_minus, IBus.KEY_minus],
                keypad_fallback=False))
        self.assertEqual(
            None,
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_KP_Subtract, IBus.KEY_KP_Subtract],
                keypad_fallback=True))
        self.assertEqual(
            '',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_KP_Subtract, IBus.KEY_KP_Subtract],
                keypad_fallback=False))
        self.assertEqual(
            None,
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_minus, IBus.KEY_KP_Subtract],
                keypad_fallback=True))
        self.assertEqual(
            '',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_minus, IBus.KEY_KP_Subtract],
                keypad_fallback=False))
        self.assertEqual(
            None,
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_KP_Subtract, IBus.KEY_minus],
                keypad_fallback=True))
        self.assertEqual(
            '',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_KP_Subtract, IBus.KEY_minus],
                keypad_fallback=False))
        self.assertEqual(
            '—',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_minus, IBus.KEY_minus, IBus.KEY_minus],
                keypad_fallback=True))
        self.assertEqual(
            '—',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_minus, IBus.KEY_minus, IBus.KEY_minus],
                keypad_fallback=False))
        self.assertEqual(
            '—',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_KP_Subtract, IBus.KEY_KP_Subtract, IBus.KEY_KP_Subtract],
                keypad_fallback=True))
        self.assertEqual(
            '',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_KP_Subtract, IBus.KEY_KP_Subtract, IBus.KEY_KP_Subtract],
                keypad_fallback=False))
        self.assertEqual(
            '—',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_minus, IBus.KEY_KP_Subtract, IBus.KEY_KP_Subtract],
                keypad_fallback=True))
        self.assertEqual(
            '',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_minus, IBus.KEY_KP_Subtract, IBus.KEY_KP_Subtract],
                keypad_fallback=False))
        self.assertEqual(
            '—',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_KP_Subtract, IBus.KEY_minus, IBus.KEY_KP_Subtract],
                keypad_fallback=True))
        self.assertEqual(
            '',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_KP_Subtract, IBus.KEY_minus, IBus.KEY_KP_Subtract],
                keypad_fallback=False))
        self.assertEqual(
            '—',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_KP_Subtract, IBus.KEY_KP_Subtract, IBus.KEY_minus],
                keypad_fallback=True))
        self.assertEqual(
            '',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_KP_Subtract, IBus.KEY_KP_Subtract, IBus.KEY_minus],
                keypad_fallback=False))
        self.assertEqual(
            '½',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_1, IBus.KEY_2],
                keypad_fallback=True))
        self.assertEqual(
            '½',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_1, IBus.KEY_2],
                keypad_fallback=False))
        self.assertEqual(
            '½',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_KP_1, IBus.KEY_2],
                keypad_fallback=True))
        self.assertEqual(
            '',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_KP_1, IBus.KEY_2],
                keypad_fallback=False))
        self.assertEqual(
            '½',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_1, IBus.KEY_KP_2],
                keypad_fallback=True))
        self.assertEqual(
            '',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_1, IBus.KEY_KP_2],
                keypad_fallback=False))
        self.assertEqual(
            None,
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_1],
                keypad_fallback=True))
        self.assertEqual(
            None,
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_1],
                keypad_fallback=False))
        self.assertEqual(
            None,
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_KP_1],
                keypad_fallback=True))
        self.assertEqual(
            '',
            self._compose_sequences.compose(
                [IBus.KEY_Multi_key,
                 IBus.KEY_KP_1],
                keypad_fallback=False))

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    unittest.main()
