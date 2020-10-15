# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2015-2016 Mike FABIAN <mfabian@redhat.com>
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
This module is used to get synonyms, hypernyms, and hyponyms from NLTK.

If nltk cannot be imported, it raises “ImportError”,
if the wordnet corpus is not installed it raises “LookupError”.

If “LookupError" is raised because the corpus is mising, install
it using:

    python3
    import nltk
    nltk.download()

'''

from typing import List
import sys
import nltk # type: ignore
from nltk.corpus import wordnet # type: ignore

def synonyms(word: str, keep_original: bool = True) -> List[str]:
    '''List synonyms for word

    :param word: The word for which synonyms should be looked up
    :type word: string
    :param keep_original: Whether the original word should be in
                          the result as well. If the original word
                          is kept in the results, it is put first
                          in the list.
    :rtype: A list of strings

    Examples:

    >>> synonyms('fedora')
    ['fedora', 'Stetson', 'felt hat', 'homburg', 'trilby']

    >>> synonyms('fedora', keep_original = False)
    ['Stetson', 'felt hat', 'homburg', 'trilby']
    '''
    result = sorted(set(lemma_name.replace('_', ' ')
                        for synset in wordnet.synsets(word)
                        for lemma_name in synset.lemma_names()))
    if word in result:
        result.remove(word)
    if keep_original:
        result = [word] + result
    return result[:]

def hyponyms(word: str, keep_original: bool = True) -> List[str]:
    '''List hyponyms for word

    :param word: The word for which hyponyms should be looked up
    :type word: string
    :param keep_original: Whether the original word should be in
                          the result as well. If the original word
                          is kept in the results, it is put first
                          in the list.
    :rtype: A list of strings

    Examples:

    >>> hyponyms('hat')
    ['hat', 'Panama', 'Panama hat', 'Stetson', 'bearskin', 'beaver', 'boater', 'bonnet', 'bowler', 'bowler hat', 'busby', 'campaign hat', 'cavalier hat', 'cocked hat', 'cowboy hat', 'deerstalker', 'derby', 'derby hat', 'dress hat', 'dunce cap', "dunce's cap", 'fedora', 'felt hat', "fool's cap", 'fur hat', 'high hat', 'homburg', 'leghorn', 'millinery', 'opera hat', 'plug hat', 'poke bonnet', 'sailor', 'shako', 'shovel hat', 'silk hat', 'skimmer', 'slouch hat', 'snap-brim hat', 'sombrero', "sou'wester", 'stovepipe', 'straw hat', 'sun hat', 'sunhat', 'ten-gallon hat', 'tirolean', 'titfer', 'top hat', 'topper', 'toque', 'trilby', 'tyrolean', "woman's hat"]

    >>> hyponyms('hat', keep_original = False)
    ['Panama', 'Panama hat', 'Stetson', 'bearskin', 'beaver', 'boater', 'bonnet', 'bowler', 'bowler hat', 'busby', 'campaign hat', 'cavalier hat', 'cocked hat', 'cowboy hat', 'deerstalker', 'derby', 'derby hat', 'dress hat', 'dunce cap', "dunce's cap", 'fedora', 'felt hat', "fool's cap", 'fur hat', 'high hat', 'homburg', 'leghorn', 'millinery', 'opera hat', 'plug hat', 'poke bonnet', 'sailor', 'shako', 'shovel hat', 'silk hat', 'skimmer', 'slouch hat', 'snap-brim hat', 'sombrero', "sou'wester", 'stovepipe', 'straw hat', 'sun hat', 'sunhat', 'ten-gallon hat', 'tirolean', 'titfer', 'top hat', 'topper', 'toque', 'trilby', 'tyrolean', "woman's hat"]
    '''
    result = sorted(set(lemma.name().replace('_', ' ')
                        for synset in wordnet.synsets(word)
                        for hyponym in synset.hyponyms()
                        for lemma in hyponym.lemmas()))
    if word in result:
        result.remove(word)
    if keep_original:
        result = [word] + result
    return result[:]

def hypernyms(word: str, keep_original: bool = True) -> List[str]:
    '''List hypernyms for word

    :param word: The word for which hyperyms should be looked up
    :type word: string
    :param keep_original: Whether the original word should be in
                          the result as well. If the original word
                          is kept in the results, it is put first
                          in the list.
    :rtype: A list of strings

    Examples:

    >>> hypernyms('fedora')
    ['fedora', 'chapeau', 'hat', 'lid']

    >>> hypernyms('fedora', keep_original = False)
    ['chapeau', 'hat', 'lid']
    '''
    result = sorted(set(lemma.name().replace('_', ' ')
                        for synset in wordnet.synsets(word)
                        for hypernym in synset.hypernyms()
                        for lemma in hypernym.lemmas()))
    if word in result:
        result.remove(word)
    if keep_original:
        result = [word] + result
    return result[:]

def related(word: str, keep_original: bool = True) -> List[str]:
    '''List all related words (synonyms, hypernyms, and hyponyms)

    :param word: The word for which related words should be looked up
    :type word: string
    :param keep_original: Whether the original word should be in
                          the result as well. If the original word
                          is kept in the results, it is put first
                          in the list.
    :rtype: A list of strings

    Examples:

    >>> related('fedora')
    ['fedora', 'Stetson', 'felt hat', 'homburg', 'trilby', 'chapeau', 'hat', 'lid']
    '''
    result = (
        synonyms(word, keep_original=False)
        + hypernyms(word, keep_original=False)
        + hyponyms(word, keep_original=False)
    )
    if word in result:
        result.remove(word)
    if keep_original:
        result = [word] + result
    return result[:]

def _init() -> None:
    '''Init this module

    Try to load the wordnet corpus here to make sure this module is
    really usable.
    '''
    try:
        wordnet.synsets('car')
    except (LookupError,):
        raise LookupError
    except:
        print("Unexpected error:", sys.exc_info()[0])
        raise

def _del() -> None:
    '''Cleanup, nothing to do here'''
    return

class __ModuleInitializer:
    def __init__(self) -> None:
        _init()
        return

    def __del__(self) -> None:
        # _del()
        return

__module_init = __ModuleInitializer()

BENCHMARK = True

def main() -> None:
    '''
    Used for testing and profiling.

    “python3 itb_nltk.py”

    runs some tests and prints profiling data.
    '''
    if BENCHMARK:
        import cProfile
        import pstats
        profile = cProfile.Profile()
        profile.enable()

    import doctest
    _init()
    (failed, dummy_attempted) = doctest.testmod()

    if BENCHMARK:
        profile.disable()
        stats = pstats.Stats(profile)
        stats.strip_dirs()
        stats.sort_stats('cumulative')
        stats.print_stats('nltk', 25)
        stats.print_stats('wordnet', 25)

    if failed:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
