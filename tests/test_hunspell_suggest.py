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

# pylint: disable=wrong-import-position
sys.path.insert(0, "../engine")
import hunspell_suggest # pylint: disable=import-error
import itb_util # pylint: disable=import-error
sys.path.pop(0)

import testutils # pylint: disable=import-error
# pylint: enable=wrong-import-position

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

IMPORT_LIBVOIKKO_SUCCESSFUL = False
try:
    # pylint: disable=unused-import
    import libvoikko # type: ignore
    # pylint: enable=unused-import
    IMPORT_LIBVOIKKO_SUCCESSFUL = True
except (ImportError,):
    pass

# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=invalid-name
# pylint: disable=line-too-long

class HunspellSuggestTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None

    def tearDown(self) -> None:
        pass

    def test_dummy(self) -> None:
        self.assertEqual(True, True)

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('cs_CZ')[0],
        'Skipping because no Czech hunspell dictionary could be found.')
    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('de_DE')[0],
        'Skipping because no German hunspell dictionary could be found.')
    @unittest.skipUnless(
        testutils.enchant_sanity_test(language='cs_CZ', word='Praha'),
        'Skipping because python3-enchant seems broken for cs_CZ.')
    def test_de_DE_cs_CZ_enchant(self) -> None:
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
        print('FIXME', h.suggest('filosofictejsi'))
        self.assertEqual(
            h.suggest('filosofictejsi'), [
                ('filosofic\u030Cte\u030Cjs\u030Ci\u0301', 0),
                ('filosofic\u030Cte\u030Cjs\u030Ci\u0301m', 0),
                ('filosofic\u030Cte\u030Cji', -1),
            ])
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
    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('cs_CZ')[0],
        'Skipping because no Czech hunspell dictionary could be found.')
    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('de_DE')[0],
        'Skipping because no German hunspell dictionary could be found.')
    def test_de_DE_cs_CZ_pyhunspell(self) -> None:
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

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('it_IT')[0],
        'Skipping because no Italian hunspell dictionary could be found.')
    def test_it_IT(self) -> None:
        h = hunspell_suggest.Hunspell(['it_IT'])
        self.assertEqual(
            h.suggest('principianti'),
            [('principianti', 0),
             ('principiati', -2),
             ('principiante', -3),
             ('principiarti', -4),
             ('principiasti', -5)])

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('es_ES')[0],
        'Skipping because no Spanish hunspell dictionary could be found.')
    def test_es_ES(self) -> None:
        h = hunspell_suggest.Hunspell(['es_ES'])
        self.assertEqual(
            h.suggest('teneis'),
            [('tene\u0301is', 0),
             ('teneos', -2),
             ('tenes', -3),
             ('tenis', -4),
             ('tienes', -5),
             ('te neis', -6),
             ('te-neis', -7)])
        self.assertEqual(
            h.suggest('tenéis')[0],
            ('tene\u0301is', 0))

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('en_US')[0],
        'Skipping because no US English hunspell dictionary could be found.')
    @unittest.skipUnless(
        testutils.enchant_sanity_test(language='cs_CZ', word='Praha'),
        'Skipping because python3-enchant seems broken for cs_CZ.')
    @unittest.skipUnless(
        testutils.enchant_working_as_expected(),
        'Skipping because of an unexpected change in the enchant behaviour.')
    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_en_US(self) -> None:
        h = hunspell_suggest.Hunspell(['en_US'])
        normal_suggestions = set((
            'Camel', 'camel', 'camels', 'Camelot', 'camellia', 'camelhair', 'Camelopardalis'))
        spellcheck_suggestions = set(('came', 'cameo'))
        for word, freq in h.suggest('camel'):
            if word in normal_suggestions and freq == 0:
                normal_suggestions.remove(word)
            if word in spellcheck_suggestions and freq < 0:
                spellcheck_suggestions.remove(word)
        self.assertEqual(normal_suggestions, set())
        self.assertEqual(spellcheck_suggestions, set())

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('fr_FR')[0],
        'Skipping because no French hunspell dictionary could be found.')
    def test_fr_FR(self) -> None:
        h = hunspell_suggest.Hunspell(['fr_FR'])
        self.assertEqual(
            h.suggest('differemmen'),
            [('diffe\u0301remment', 0)])

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('el_GR')[0],
        "Skipping because no Greek dictionary could be found. ")
    def test_el_GR(self) -> None:
        h = hunspell_suggest.Hunspell(['el_GR'])
        self.assertEqual(
            h.suggest('αλφαβητο')[0],
            ('αλφάβητο', 0))

    def test_fi_FI_dictionary_file(self) -> None:
        # dictionary file is included in ibus-typing-booster
        #
        # This should work with and without voikko
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
        testutils.get_libvoikko_version() >= '4.3',
        "Skipping, requires python3-libvoikko version >= 4.3.")
    @unittest.skipIf(
        testutils.init_libvoikko_error(),
        f'Skipping, {testutils.init_libvoikko_error()}')
    def test_fi_FI_voikko(self) -> None:
        d = hunspell_suggest.Dictionary('fi_FI')
        self.assertEqual(d.has_spellchecking(), True)
        h = hunspell_suggest.Hunspell(['fi_FI'])
        print(h.suggest('kisssa'))
        self.assertEqual(
            h.suggest('kisssa'),
            [('kissa', -1),
             ('kissaa', -2),
             ('kisassa', -3),
             ('kisussa', -4),
             ('Kiassa', -5)])
        self.assertEqual(
            h.suggest('Pariisin-suurlähettila'),
            [('Pariisin-suurla\u0308hettila\u0308s', 0),
             ('Pariisin-suurlähettiala', -1),
             ('Pariisin-suurlähetetila', -2)])

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('en_US')[0],
        'Skipping because no US English hunspell dictionary could be found.')
    def test_en_US_spellcheck_enchant(self) -> None:
        d = hunspell_suggest.Dictionary('en_US')
        self.assertEqual(d.spellcheck_enchant('winter'), True)
        self.assertEqual(d.spellcheck_enchant('winxer'), False)

    @unittest.skipUnless(
        IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-enchant to work.")
    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('en_US')[0],
        'Skipping because no US English hunspell dictionary could be found.')
    @unittest.skipUnless(
        testutils.enchant_sanity_test(language='cs_CZ', word='Praha'),
        'Skipping because python3-enchant seems broken for cs_CZ.')
    @unittest.skipUnless(
        testutils.enchant_working_as_expected(),
        'Skipping because of an unexpected change in the enchant behaviour.')
    @unittest.skipUnless(
        testutils.get_hunspell_dictionary_length('en_US') >= 10000,
        'Skipping because en_US dictionary is suspiciously small, '
        'see: https://bugzilla.redhat.com/show_bug.cgi?id=2218460')
    def test_en_US_spellcheck_suggest_enchant(self) -> None:
        d = hunspell_suggest.Dictionary('en_US')
        self.assertTrue('camel' in d.spellcheck_suggest_enchant('kamel'))
        self.assertTrue('Camel' in d.spellcheck_suggest_enchant('kamel'))

    @unittest.skipUnless(
        IMPORT_HUNSPELL_SUCCESSFUL and not IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-pyhunspell to work.")
    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('en_US')[0],
        'Skipping because no US English hunspell dictionary could be found.')
    def test_en_US_spellcheck_pyhunspell(self) -> None:
        d = hunspell_suggest.Dictionary('en_US')
        self.assertEqual(d.spellcheck_pyhunspell('winter'), True)
        self.assertEqual(d.spellcheck_pyhunspell('winxer'), False)

    @unittest.skipUnless(
        IMPORT_HUNSPELL_SUCCESSFUL and not IMPORT_ENCHANT_SUCCESSFUL,
        "Skipping because this test requires python3-pyhunspell to work.")
    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('en_US')[0],
        'Skipping because no US English hunspell dictionary could be found.')
    def test_en_US_spellcheck_suggest_pyhunspell(self) -> None:
        d = hunspell_suggest.Dictionary('en_US')
        self.assertEqual(
            d.spellcheck_suggest_pyhunspell('kamel'),
            ['camel', 'Camel'])

    @unittest.skipUnless(
        testutils.get_libvoikko_version() >= '4.3',
        "Skipping, requires python3-libvoikko version >= 4.3.")
    @unittest.skipIf(
        testutils.init_libvoikko_error(),
        f'Skipping, {testutils.init_libvoikko_error()}')
    def test_fi_FI_spellcheck_voikko(self) -> None:
        d = hunspell_suggest.Dictionary('fi_FI')
        self.assertEqual(d.spellcheck_voikko('kissa'), True)
        self.assertEqual(d.spellcheck_voikko('kisssa'), False)
        self.assertEqual(d.spellcheck_voikko('Päiviä'), True)
        self.assertEqual(d.spellcheck_voikko('Päivia'), False)

    @unittest.skipUnless(
        testutils.get_libvoikko_version() >= '4.3',
        "Skipping, requires python3-libvoikko version >= 4.3.")
    @unittest.skipIf(
        testutils.init_libvoikko_error(),
        f'Skipping, {testutils.init_libvoikko_error()}')
    def test_fi_FI_spellcheck_suggest_voikko(self) -> None:
        d = hunspell_suggest.Dictionary('fi_FI')
        self.assertEqual(
            d.spellcheck_suggest_voikko('kisssa'),
            ['kissa', 'kissaa', 'kisassa', 'kisussa', 'Kiassa'])

    @unittest.skipUnless(
        itb_util.get_hunspell_dictionary_wordlist('sv_SE')[0],
        "Skipping because no Swedish dictionary could be found. ")
    def test_sv_SE(self) -> None:
        h = hunspell_suggest.Hunspell(['sv_SE'])
        self.assertEqual(
            h.suggest('östgo')[0:6], [
                ('östgot', 0),
                ('Östgöta', 0),
                ('östgöte', 0),
                ('Östgötar', 0),
                ('östgotisk', 0),
                ('östgötsk', 0),
            ])
        self.assertEqual(
            h.suggest('östgot'), [
                ('östgot', 0),
                ('östgotisk', 0),
                ('Östgot', -1),
            ])
        self.assertEqual(
            h.suggest('östgö')[0:4], [
                ('Östgöta', 0),
                ('östgöte', 0),
                ('Östgötar', 0),
                ('östgötsk', 0),
            ])
        self.assertEqual(
            h.suggest('östgöt')[0:4], [
                ('Östgöta', 0),
                ('östgöte', 0),
                ('Östgötar', 0),
                ('östgötsk', 0),
            ])

if __name__ == '__main__':
    unittest.main()
