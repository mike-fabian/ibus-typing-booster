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
import locale
import unittest

from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus

sys.path.insert(0, "../engine")
import itb_util
sys.path.pop(0)

class ComposeSequencesTestCase(unittest.TestCase):
    def setUp(self):
        locale.setlocale(locale.LC_CTYPE, 'en_US.UTF-8')
        self._compose_sequences = itb_util.ComposeSequences()

    def tearDown(self):
        pass

    def test_dummy(self):
        self.assertEqual(True, True)

    def test_preedit_representations(self):
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [IBus.KEY_Multi_key,
                 IBus.KEY_asciitilde,
                 IBus.KEY_dead_circumflex,
                 IBus.KEY_A]),
            '⎄~^A')
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [0x2276]),
            '≶')
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [IBus.KEY_Multi_key, 0x2276]),
            '⎄≶')
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [IBus.KEY_Multi_key, 0x093C]),
            '⎄़')
        self.assertEqual(
            self._compose_sequences.preedit_representation(
                [IBus.KEY_a, IBus.KEY_dead_belowdiaeresis]),
            'a\u00A0\u0324')

    def test_compose(self):
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

    def test_compose_parse_double_quote_in_result(self):
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

    def test_compose_cs_CZ(self):
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

    def test_compose_km_KH(self):
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
                [0x17FF]),
            'ាំ')

    def test_compose_pt_BR(self):
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

    def test_compose_pt_PT(self):
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

    def test_compose_am_ET(self):
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
        self.assertEqual(
            self._compose_sequences.compose(
                [IBus.KEY_u,
                 0x1200]),
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

    def test_reasonable_dead_key_sequences(self):
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

if __name__ == '__main__':
    unittest.main()
