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
This file implements test cases for suggestions from hunspell dictionaries
'''

import sys
import unittest

from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus

sys.path.insert(0, "../engine")
import hunspell_suggest
sys.path.pop(0)

IMPORT_ENCHANT_SUCCESSFUL = False
IMPORT_HUNSPELL_SUCCESSFUL = False
try:
    import enchant
    IMPORT_ENCHANT_SUCCESSFUL = True
except (ImportError,):
    try:
        import hunspell
        IMPORT_HUNSPELL_SUCCESSFUL = True
    except (ImportError,):
        pass

IMPORT_LIBVOIKKO_SUCCESSFUL = False
try:
    import libvoikko
    IMPORT_LIBVOIKKO_SUCCESSFUL = True
except (ImportError,):
    pass

class HunspellSuggestTestCase(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def tearDown(self):
        pass

    def test_dummy(self):
        self.assertEqual(True, True)

    def test_de_DE_cs_CZ(self):
        h = hunspell_suggest.Hunspell(['de_DE', 'cs_CZ'])
        self.assertEqual(
            h.suggest('Geschwindigkeitsubertre')[0],
            ('Geschwindigkeitsu\u0308bertretungsverfahren', 0))
        self.assertEqual(
            h.suggest('Geschwindigkeitsübertretungsverfahren')[0],
            ('Geschwindigkeitsu\u0308bertretungsverfahren', 0))
        self.assertEqual(
            h.suggest('Glühwürmchen')[0],
            ('Glu\u0308hwu\u0308rmchen', 0))
        self.assertEqual(
            h.suggest('Alpengluhen')[0],
            ('Alpenglu\u0308hen', 0))
        self.assertEqual(
            h.suggest('filosofictejsi'),
            [('filosofic\u030Cte\u030Cjs\u030Ci\u0301', 0),
             ('filosofic\u030Cte\u030Cji', -1)])
        self.assertEqual(
            h.suggest('filosofictejs')[0],
            ('filosofic\u030Cte\u030Cjs\u030Ci\u0301', 0))
        self.assertEqual(
            h.suggest('filosofičtější')[0],
            ('filosofic\u030Cte\u030Cjs\u030Ci\u0301', 0))
        self.assertEqual(
            h.suggest('filosofičtějš')[0],
            ('filosofic\u030Cte\u030Cjs\u030Ci\u0301', 0))

    def test_it_IT(self):
        h = hunspell_suggest.Hunspell(['it_IT'])
        self.assertEqual(
            h.suggest('principianti'),
            [('principianti', 0),
             ('principiati', -1),
             ('principiante', -1),
             ('principiarti', -1),
             ('principiasti', -1)])

    def test_es_ES(self):
        h = hunspell_suggest.Hunspell(['es_ES'])
        self.assertEqual(
            h.suggest('teneis'),
            [('tene\u0301is', 0),
             ('tenes', -1),
             ('tenis', -1),
             ('teneos', -1),
             ('tienes', -1),
             ('te neis', -1),
             ('te-neis', -1)])
        self.assertEqual(
            h.suggest('tenéis')[0],
            ('tene\u0301is', 0))

    def test_en_US(self):
        h = hunspell_suggest.Hunspell(['en_US'])
        self.assertEqual(
            h.suggest('camel'),
            [('camel', 0),
             ('camellia', 0),
             ('camelhair', 0),
             ('came', -1),
             ('Camel', -1),
             ('cameo', -1),
             ('came l', -1),
             ('camels', -1)])

    def test_fr_FR(self):
        h = hunspell_suggest.Hunspell(['fr_FR'])
        self.assertEqual(
            h.suggest('differemmen'),
            [('diffe\u0301remment', 0)])

    @unittest.skipUnless(
        IMPORT_LIBVOIKKO_SUCCESSFUL,
        "Skipping because this test requires python3-libvoikko to work.")
    def test_fi_FI(self):
        h = hunspell_suggest.Hunspell(['fi_FI'])
        self.assertEqual(
            h.suggest('kissa'),
            [('kissa', 0)])
        self.assertEqual(
            h.suggest('kisssa'),
            [('kissa', -1),
             ('kissaa', -1),
             ('kisassa', -1),
             ('kisussa', -1)])

if __name__ == '__main__':
    unittest.main()
