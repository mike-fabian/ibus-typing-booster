# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 2013-2015 Mike FABIAN <mfabian@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#  This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#  You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import re
import unicodedata

# If a character of one of these categories is typed and no
# transliteration is used, the preëdit can be committed immediately.
# However, if transliteration is used, we may need to handle a
# punctuation or symbol character. For example, “.c” is
# transliterated to “ċ” in the “t-latn-pre” transliteration
# method, therefore we cannot just pass it through, we have to add
# it to the input and see what comes next.
#
# This list is very similar to the list of categories to strip from
# tokens. But I removed the 'Pd' (Punctuation, Dash) category because
# of words like “up-to-date”. Triggering a commit at the first “-”
# prevents learning such words from user input. I.e. the list of
# categories to trigger immediate commit should contain only categories
# which are very unlikely to appear as parts of words.
categories_to_trigger_immediate_commit = [
    'Po', 'Pi', 'Pf', 'Ps', 'Pe', 'Pc', 'Sm', 'Sc']

categories_to_strip_from_tokens = [
    'Po', 'Pi', 'Pf', 'Ps', 'Pe', 'Pc', 'Pd', 'Sm', 'Sc']

def lstrip_token(token):
    token = token.lstrip()
    while (len(token) > 0
           and
           unicodedata.category(token[0]) in categories_to_strip_from_tokens):
        token = token[1:]
    return token

def rstrip_token(token):
    token = token.rstrip()
    while (len(token) > 0
           and
           unicodedata.category(token[-1]) in categories_to_strip_from_tokens):
        token = token[0:-1]
    return token

def strip_token(token):
    return rstrip_token(lstrip_token(token))

def tokenize(text):
    pattern = re.compile(r'[\s]+')
    tokens = []
    for s in pattern.split(text.strip()):
        tokens.append(strip_token(s))
    return tokens

def is_ascii(text):
    '''Checks whether all characters in text are ASCII characters

    Returns “True” if the text is all ASCII, “False” if not.

    :param text: The text to check
    :type text: string
    :rtype: bool

    Examples:

    >>> is_ascii('Abc')
    True

    >>> is_ascii('Naïve')
    False
    '''
    try:
        text.encode('ascii')
    except UnicodeEncodeError:
        return False
    else:
        return True

# Mapping of Unicode ordinals to Unicode ordinals, strings, or None.
# Unmapped characters are left untouched. Characters mapped to None
# are deleted.

TRANS_TABLE = {
    ord('ẞ'): 'SS',
    ord('ß'): 'ss',
    ord('Ø'): 'O',
    ord('ø'): 'o',
    ord('Æ'): 'AE',
    ord('æ'): 'ae',
    ord('Œ'): 'OE',
    ord('œ'): 'oe',
    ord('Ł'): 'L',
    ord('ł'): 'l',
}

def remove_accents(text):
    '''Removes accents from the text

    Returns the text with all accents removed

    Using “from unidecode import unidecode” is more
    sophisticated, but I am not sure whether I can require
    “unidecode”.

    :param text: The text to change
    :type text: string
    :rtype: string

    Examples:

    >>> remove_accents('Ångstrøm')
    'Angstrom'

    >>> remove_accents('ÅÆæŒœĳøßẞü')
    'AAEaeOEoeijossSSu'

    '''
    return ''.join([
        x for x in unicodedata.normalize('NFKD', text)
        if unicodedata.category(x) != 'Mn']).translate(TRANS_TABLE)

if __name__ == "__main__":
    import doctest
    doctest.testmod()
