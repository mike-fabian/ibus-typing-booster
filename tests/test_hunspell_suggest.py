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
import itb_util
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

def get_libvoikko_version():
    if IMPORT_LIBVOIKKO_SUCCESSFUL:
        return libvoikko.Voikko.getVersion()
    else:
        return '0'

class HunspellSuggestTestCase(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def tearDown(self):
        pass

    def test_dummy(self):
        self.assertEqual(True, True)

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    def test_de_DE_cs_CZ_enchant(self):
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

    @unittest.skipUnless(
        IMPORT_HUNSPELL_SUCCESSFUL and not IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-pyhunspell to work.")
    def test_de_DE_cs_CZ_pyhunspell(self):
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
             ('filosofie\u0300ti\u0300ji', -1)])
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
        itb_util.get_hunspell_dictionary_wordlist('el_GR')[0],
        "Skipping because no Greek dictionary could be found. ")
    def test_el_GR(self):
        h = hunspell_suggest.Hunspell(['el_GR'])
        self.assertEqual(
            h.suggest('αλφαβητο')[0],
            ('αλφάβητο', 0))

    def test_fi_FI_dictionary_file(self):
        # dictionary file is included in ibus-typing-booster
        h = hunspell_suggest.Hunspell(['fi_FI'])
        self.assertEqual(
            h.suggest('kissa'),
            [('kissa', 0),
             ('kissaa', 0),
             ('kissani', 0),
             ('kissassa', 0),
             ('kissajuttu', 0),
             ('kissamaiseksi',0)])

    @unittest.skipUnless(
        get_libvoikko_version() >= '4.3',
        "Skipping, requires python3-libvoikko version >= 4.3.")
    def test_fi_FI_voikko(self):
        d = hunspell_suggest.Dictionary('fi_FI')
        self.assertEqual(d.has_spellchecking(), True)
        h = hunspell_suggest.Hunspell(['fi_FI'])
        self.assertEqual(
            h.suggest('kisssa'),
            [('kissa', -1),
             ('Kiassa', -1),
             ('kissaa', -1),
             ('kisassa', -1),
             ('kisussa', -1)])
        self.assertEqual(
            h.suggest('Pariisin-suurlähettila'),
            [('Pariisin-suurla\u0308hettila\u0308s', 0),
             ('Pariisin-suurlähetetila', -1),
             ('Pariisin-suurlähettiala', -1)])

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    def test_en_US_spellcheck_enchant(self):
        d = hunspell_suggest.Dictionary('en_US')
        self.assertEqual(d.spellcheck_enchant('winter'), True)
        self.assertEqual(d.spellcheck_enchant('winxer'), False)

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    def test_en_US_spellcheck_suggest_enchant(self):
        d = hunspell_suggest.Dictionary('en_US')
        self.assertEqual(
            d.spellcheck_suggest_enchant('kamel'),
            ['camel', 'Camel'])

    @unittest.skipUnless(
        IMPORT_HUNSPELL_SUCCESSFUL and not IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-pyhunspell to work.")
    def test_en_US_spellcheck_pyhunspell(self):
        d = hunspell_suggest.Dictionary('en_US')
        self.assertEqual(d.spellcheck_pyhunspell('winter'), True)
        self.assertEqual(d.spellcheck_pyhunspell('winxer'), False)

    @unittest.skipUnless(
        IMPORT_HUNSPELL_SUCCESSFUL and not IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-pyhunspell to work.")
    def test_en_US_spellcheck_suggest_pyhunspell(self):
        d = hunspell_suggest.Dictionary('en_US')
        self.assertEqual(
            d.spellcheck_suggest_pyhunspell('kamel'),
            ['camel', 'Camel'])

    @unittest.skipUnless(
        get_libvoikko_version() >= '4.3',
        "Skipping, requires python3-libvoikko version >= 4.3.")
    def test_fi_FI_spellcheck_voikko(self):
        d = hunspell_suggest.Dictionary('fi_FI')
        self.assertEqual(d.spellcheck_voikko('kissa'), True)
        self.assertEqual(d.spellcheck_voikko('kisssa'), False)
        self.assertEqual(d.spellcheck_voikko('Päiviä'), True)
        self.assertEqual(d.spellcheck_voikko('Päivia'), False)

    @unittest.skipUnless(
        get_libvoikko_version() >= '4.3',
        "Skipping, requires python3-libvoikko version >= 4.3.")
    def test_fi_FI_spellcheck_suggest_voikko(self):
        d = hunspell_suggest.Dictionary('fi_FI')
        self.assertEqual(
            d.spellcheck_suggest_voikko('kisssa'),
            ['kissa', 'kissaa', 'kisassa', 'kisussa', 'Kiassa'])

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('sv_SE')[0],
        "Skipping because no Swedisch dictionary could be found. ")
    def test_sv_SE(self):
        h = hunspell_suggest.Hunspell(['sv_SE'])
        self.assertEqual(
            h.suggest('östgo'),
            [('östgot', 0),
             ('östgöte', 0),
             ('östgotisk', 0),
             ('östgötsk', 0),
             ('östgötska', 0)])
        self.assertEqual(
            h.suggest('östgot'),
            [('östgot', 0),
             ('östgotisk', 0),
             ('Östgot', -1)])
        self.assertEqual(
            h.suggest('östgö'),
            [('östgöte', 0),
             ('östgötsk', 0),
             ('östgötska', 0)])
        self.assertEqual(
            h.suggest('östgöt')[0:4],
            [('östgöte', 0),
             ('östgötsk', 0),
             ('östgötska', 0),
             ('östgot', -1)])

if __name__ == '__main__':
    unittest.main()
