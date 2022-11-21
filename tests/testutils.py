#!/usr/bin/python3
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2016 Mike FABIAN <mfabian@redhat.com>
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
This file implements a few helper functions for test cases
'''

import sys
import locale

sys.path.insert(0, "../engine")
# pylint: disable=wrong-import-position
# pylint: disable=import-error
import itb_util
# pylint: enable=import-error
# pylint: enable=wrong-import-position
sys.path.pop(0)

IMPORT_ENCHANT_SUCCESSFUL = False
IMPORT_HUNSPELL_SUCCESSFUL = False
try:
    import enchant # type: ignore
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
    import libvoikko # type: ignore
    IMPORT_LIBVOIKKO_SUCCESSFUL = True
except (ImportError,):
    pass

def get_libvoikko_version() -> str:
    '''Return the version of libvoikko

    If libvoikko is not available, return 0
    '''
    if IMPORT_LIBVOIKKO_SUCCESSFUL:
        return str(libvoikko.Voikko.getVersion())
    return '0'

def init_libvoikko_error() -> str:
    '''
    Checks whether an error happens during initilization of Voikko.

    :return: '' (empty string) if Voikko initialization worked.
             error message string if Voikko initialization failed.
    '''
    if IMPORT_LIBVOIKKO_SUCCESSFUL:
        try:
            voikko = libvoikko.Voikko('fi')
            if voikko:
                return ''
            return 'Intialization of Voikko failed: object empty'
        except (libvoikko.VoikkoException,) as error:
            return str(error)
    return 'import libvoikko failed.'

def enchant_sanity_test(language: str = '', word: str = '') -> bool:
    '''Checks whether python3-enchant returns some suggestions given a
    language and a word.

    :param language: The language of the dictionary to try
    :param word: The word to give to enchant to ask for suggestions

    This is used as a sanity check whether python3-enchant works at all.
    For example, if a Czech dictionary is opened like

        d = enchant.Dict('cs_CZ')

    and then something like

        retval = d.suggest('Praha')

    returns an empty list instead of a list of some words, then
    something is seriously wrong with python3-enchant and it is better
    to skip the test case which relies on python3-enchant working for
    that language.
    '''
    if not (language and word):
        return False
    if not itb_util.get_hunspell_dictionary_wordlist(language)[0]:
        return False
    enchant_dictionary = enchant.Dict(language)
    if enchant_dictionary.suggest(word):
        return True
    return  False

def enchant_working_as_expected() -> bool:
    '''Checks if the behaviour has changed somehow.

    Even if enchant is working, the behaviour might change
    if enchant is updated to a new version and/or dictionaries
    are updated.

    This function tries to detect if the behaviour of enchant
    is different to what I see on my development system and
    if it is different skip test cases which might fail only
    because of unexpected enchant behaviour.

    As soon as I see that this causes test cases on my development
    system to be skipped, I should check carefully and then probably
    update the test cases.
    '''
    if not IMPORT_ENCHANT_SUCCESSFUL:
        return False
    enchant_dictionary = enchant.Dict('en_US')
    if enchant_dictionary.check('hedgehgo'):
        return False
    if (enchant_dictionary.suggest('hedgehgo') !=
        ['hedgehog', 'hedgehop']):
        return False
    return True

def set_locale_error(locale_name: str) -> str:
    '''
    Checks whether an error occurs when trying to set locale.

    :return: '' (empty string) if setting this locale worked.
             error message string if setting this locale failed.

    It checks by trying to set LC_CTYPE and then restoring the old
    value.
    '''
    (old_lc_ctype_locale,
     old_lc_ctype_encoding) = locale.getlocale(locale.LC_CTYPE)
    if not old_lc_ctype_locale:
        old_lc_ctype_locale = 'en_US'
    if not old_lc_ctype_encoding:
        old_lc_ctype_encoding = 'UTF-8'
    old_locale_name = old_lc_ctype_locale + '.' + old_lc_ctype_encoding
    try:
        locale.setlocale(locale.LC_CTYPE, locale_name)
        locale.setlocale(locale.LC_CTYPE, old_locale_name)
        return ''
    except (locale.Error,) as error:
        return f'{locale_name}: {str(error)}'
