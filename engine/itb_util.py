# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2013-2016 Mike FABIAN <mfabian@redhat.com>
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
Utility functions used in ibus-typing-booster
'''

import sys
import os
import re
import string
import unicodedata
from gi.repository import GLib
IMPORT_XDG_BASEDIRECTORY_SUCCESSFUL = False
try:
    import xdg.BaseDirectory
    IMPORT_XDG_BASEDIRECTORY_SUCCESSFUL = True
except (ImportError,):
    IMPORT_XDG_BASEDIRECTORY_SUCCESSFUL = False

NORMALIZATION_FORM_INTERNAL = 'NFD'

# maximum possible value for the INTEGER datatype in SQLite3
SQLITE_MAXINT = 2**63-1
# user frequency used for a user defined shortcut
SHORTCUT_USER_FREQ = 1000000

# If a character ending a sentence is committed (possibly
# followed by whitespace) remove trailing white space
# before the committed string. For example if
# commit_phrase is “!”, and the context before is “word ”,
# make the result “word!”.  And if the commit_phrase is “!
# ” and the context before is “word ” make the result
# “word! ”.
SENTENCE_END_CHARACTERS = '.,;:?!)'

CATEGORIES_TO_STRIP_FROM_TOKENS = (
    'Po', 'Pi', 'Pf', 'Ps', 'Pe', 'Pc', 'Pd'
)

def lstrip_token(token):
    '''Strips some characters from the left side of a token

    Characters which have a type listed in CATEGORIES_TO_STRIP_FROM_TOKENS
    are stripped from the left side of a token.

    The stripped token is returned.

    :param token: The token where characters may be stripped from
    :type token: String
    :rtype: String

    Examples:

    >>> lstrip_token(".'foo'.")
    "foo'."
    '''
    token = token.lstrip()
    while (len(token) > 0
           and
           unicodedata.category(token[0]) in CATEGORIES_TO_STRIP_FROM_TOKENS):
        token = token[1:]
    return token

def rstrip_token(token):
    '''Strips some characters from the right side of a token

    Characters which have a type listed in CATEGORIES_TO_STRIP_FROM_TOKENS
    are stripped from the right side of a token.

    The stripped token is returned.

    :param token: The token where characters may be stripped from
    :type token: String
    :rtype: String

    Examples:

    >>> rstrip_token(".'foo'.")
    ".'foo"
    '''
    token = token.rstrip()
    while (len(token) > 0
           and
           unicodedata.category(token[-1]) in CATEGORIES_TO_STRIP_FROM_TOKENS):
        token = token[0:-1]
    return token

def strip_token(token):
    '''Strips some characters from both sides of a token

    Characters which have a type listed in CATEGORIES_TO_STRIP_FROM_TOKENS
    are stripped from both sides of a token.

    The stripped token is returned.

    :param token: The token where characters may be stripped from
    :type token: String
    :rtype: String

    Examples:

    >>> strip_token(".'foo'.")
    'foo'
    '''
    return rstrip_token(lstrip_token(token))

def tokenize(text):
    '''Splits a text into tokens

    Returns a list tokens

    :param text: The text to tokenize
    :type text: String
    :rtype: List of strings
    '''
    pattern = re.compile(r'[\s]+')
    tokens = []
    for word in pattern.split(text.strip()):
        tokens.append(strip_token(word))
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

def is_right_to_left(text):
    '''Check whether a text is right-to-left text or not

    :param text: The text to check
    :type text: string
    :rtype: boolean

    See: http://unicode.org/reports/tr9/#P2

    TR9> In each paragraph, find the first character of type L, AL, or R
    TR9> while skipping over any characters between an isolate initiator
    TR9> and its matching PDI or, if it has no matching PDI, the end of the
    TR9> paragraph

    Examples:

    >>> is_right_to_left('Hallo!')
    False

    >>> is_right_to_left('﷼')
    True

    >>> is_right_to_left('⁨﷼⁩')
    False

    >>> is_right_to_left('⁨﷼⁩﷼')
    True

    >>> is_right_to_left('a⁨﷼⁩﷼')
    False

    >>> is_right_to_left('⁨a⁩⁨﷼⁩﷼')
    True
    '''
    skip = False
    for char in text:
        bidi_cat = unicodedata.bidirectional(char)
        if skip and bidi_cat != 'PDI':
            continue
        skip = False
        if bidi_cat in ('AL', 'R'):
            return True
        if bidi_cat == 'L':
            return False
        if bidi_cat in ('LRI', 'RLI', 'FSI'):
            skip = True
    return False

def bidi_embed(text):
    '''Embed the text using explicit directional embedding

    Returns “RLE + text + PDF” if the text is right-to-left,
    if not it returns “LRE + text + PDF”.

    :param text: The text to embed
    :type text: string
    :rtype: string

    See: http://unicode.org/reports/tr9/#Explicit_Directional_Embeddings

    Examples:

    >>> bidi_embed('a')
    '‪a‬'

    >>> bidi_embed('﷼')
    '‫﷼‬'
    '''
    if is_right_to_left(text):
        return chr(0x202B) + text + chr(0x202C) # RLE + text + PDF
    else:
        return chr(0x202A) + text + chr(0x202C) # LRE + text + PDF

def contains_letter(text):
    '''Returns whether “text” contains a “letter” type character

    :param text: The text to check
    :type text: string
    :rtype: boolean

    Examples:

    >>> contains_letter('Hi!')
    True

    >>> contains_letter(':-)')
    False
    '''
    for char in text:
        category = unicodedata.category(char)
        if category in ('Ll', 'Lu', 'Lo',):
            return True
    return False

def config_section_normalize(section):
    '''Replaces “_:” with “-” in the dconf section and converts to lower case

    :param section: The name of the dconf section
    :type section: string
    :rtype: string

    To make the comparison of the dconf sections work correctly.

    I avoid using .lower() here because it is locale dependent, when
    using .lower() this would not achieve the desired effect of
    comparing the dconf sections case insentively in some locales, it
    would fail for example if Turkish locale (tr_TR.UTF-8) is set.

    Examples:

    >>> config_section_normalize('Foo_bAr:Baz')
    'foo-bar-baz'
    '''
    return re.sub(r'[_:]', r'-', section).translate(
        bytes.maketrans(
            bytes(string.ascii_uppercase.encode('ascii')),
            bytes(string.ascii_lowercase.encode('ascii'))))

def variant_to_value(variant):
    '''
    Convert a GLib variant to a value
    '''
    # pylint: disable=unidiomatic-typecheck
    if type(variant) != GLib.Variant:
        return variant
    type_string = variant.get_type_string()
    if type_string == 's':
        return variant.get_string()
    elif type_string == 'i':
        return variant.get_int32()
    elif type_string == 'b':
        return variant.get_boolean()
    elif type_string == 'as':
        # In the latest pygobject3 3.3.4 or later, g_variant_dup_strv
        # returns the allocated strv but in the previous release,
        # it returned the tuple of (strv, length)
        if type(GLib.Variant.new_strv([]).dup_strv()) == tuple:
            return variant.dup_strv()[0]
        else:
            return variant.dup_strv()
    else:
        print('error: unknown variant type: %s' %type_string)
    return variant

def get_hunspell_dictionary_wordlist(language):
    '''
    Open the hunspell dictionary file for a language

    :param language: The language of the dictionary to open
    :type language: String
    :rtype: tuple of the form (dic_path, dictionary_encoding, wordlist) where
            dic_path is the full path of the dictionary file found,
            dictionary_encoding is the encoding of that dictionary file,
            and wordlist is a list of words found in that file.
            If no dictionary can be found for the requested language,
            the return value is ('', '', []).
    '''
    dirnames = [
        '/usr/share/hunspell',
        '/usr/share/myspell',
        '/usr/share/myspell/dicts',
        '/usr/local/share/hunspell', # On FreeBSD the dictionaries are here
        '/usr/local/share/myspell',
        '/usr/local/share/myspell/dicts',
    ]
    dic_path = ''
    aff_path = ''
    for dirname in dirnames:
        if os.path.isfile(os.path.join(dirname, language + '.dic')):
            dic_path = os.path.join(dirname, language + '.dic')
            aff_path = os.path.join(dirname, language + '.aff')
            break
    if not dic_path:
        sys.stderr.write(
            'get_hunspell_dictionary_wordlist(): '
            + 'No file %s.dic found in %s\n'
            %(language, dirnames))
        return ('', '', [])
    sys.stderr.write(
        'get_hunspell_dictionary_wordlist(): '
        + '%s file found.\n'
        %dic_path)
    dictionary_encoding = 'UTF-8'
    if os.path.isfile(aff_path):
        aff_buffer = ''
        try:
            aff_buffer = open(
                aff_path,
                mode='r',
                encoding='ISO-8859-1',
                errors='ignore').read().replace('\r\n', '\n')
        except (FileNotFoundError, PermissionError):
            traceback.print_exc()
        except:
            sys.stderr.write(
                'get_hunspell_dictionary_wordlist() '
                + 'Unexpected error loading .aff File: %s\n'
                %aff_path)
            traceback.print_exc()
        if aff_buffer:
            encoding_pattern = re.compile(
                r'^[\s]*SET[\s]+(?P<encoding>[-a-zA-Z0-9_]+)[\s]*$',
                re.MULTILINE)
            match = encoding_pattern.search(aff_buffer)
            if match:
                dictionary_encoding = match.group('encoding')
                sys.stderr.write(
                    'get_hunspell_dictionary_wordlist(): '
                    + 'dictionary encoding=%s found in %s\n'
                    %(dictionary_encoding, aff_path))
            else:
                sys.stderr.write(
                    'get_hunspell_dictionary_wordlist(): '
                    + 'No encoding found in %s\n'
                    %aff_path)
    else:
        sys.stderr.write(
            'get_hunspell_dictionary_wordlist(): '
            + '%s file missing. Trying to open %s using %s encoding\n'
            %(aff_path, dic_path, dictionary_encoding))
    dic_buffer = ''
    try:
        dic_buffer = open(
            dic_path, encoding=dictionary_encoding).readlines()
    except (UnicodeDecodeError, FileNotFoundError, PermissionError):
        sys.stderr.write(
            'get_hunspell_dictionary_wordlist(): '
            + 'loading %s as %s encoding failed, '
            %(dic_path, dictionary_encoding)
            + 'fall back to ISO-8859-1.\n')
        dictionary_encoding = 'ISO-8859-1'
        try:
            dic_buffer = open(
                dic_path,
                encoding=dictionary_encoding).readlines()
        except (UnicodeDecodeError, FileNotFoundError, PermissionError):
            sys.stderr.write(
                'get_hunspell_dictionary_wordlist(): '
                + 'loading %s as %s encoding failed, '
                %(dic_path, dictionary_encoding)
                + 'giving up.\n')
            traceback.print_exc()
            return ('', '', [])
        except:
            sys.stderr.write(
                'get_hunspell_dictionary_wordlist(): '
                + 'Unexpected error loading .dic File: %s\n' %dic_path)
            traceback.print_exc()
            return ('', '', [])
    except:
        sys.stderr.write(
            'get_hunspell_dictionary_wordlist(): '
            + 'Unexpected error loading .dic File: %s\n' %dic_path)
        traceback.print_exc()
        return ('', '', [])
    if not dic_buffer:
        return ('', '', [])
    sys.stderr.write(
        'get_hunspell_dictionary_wordlist(): '
        + 'Successfully loaded %s using %s encoding.\n'
        %(dic_path, dictionary_encoding))
    # http://pwet.fr/man/linux/fichiers_speciaux/hunspell says:
    #
    # > A dictionary file (*.dic) contains a list of words, one per
    # > line. The first line of the dictionaries (except personal
    # > dictionaries) contains the word count. Each word may
    # > optionally be followed by a slash ("/") and one or more
    # > flags, which represents affixes or special attributes.
    #
    # Some dictionaries, like fr_FR.dic and pt_PT.dic also contain
    # some lines where words are followed by a tab and some stuff.
    # For example, pt_PT.dic contains lines like:
    #
    # abaixo	[CAT=adv,SUBCAT=lugar]
    # abalada/p	[CAT=nc,G=f,N=s]
    #
    # and fr_FR.dic contains lines like:
    #
    # différemment	8
    # différence/1	2
    #
    # Therefore, remove everthing following a '/' or a tab from a line
    # to make the memory use of the word list a bit smaller and the
    # regular expressions we use later to match words in the
    # dictionary slightly simpler and maybe a tiny bit faster:
    word_list = [
        unicodedata.normalize(
            NORMALIZATION_FORM_INTERNAL,
            re.sub(r'[/\t].*', '', x.replace('\n', '')))
        for x in dic_buffer
    ]
    return (dic_path, dictionary_encoding, word_list)

def xdg_save_data_path(*resource):
    '''
    Compatibility function for systems which do not have pyxdg.
    (For example openSUSE Leap 42.1)
    '''
    if IMPORT_XDG_BASEDIRECTORY_SUCCESSFUL:
        return xdg.BaseDirectory.save_data_path(*resource)
    else:
        # Replicate implementation of xdg.BaseDirectory.save_data_path
        # here:
        xdg_data_home = os.environ.get('XDG_DATA_HOME') or os.path.join(
            os.path.expanduser('~'), '.local', 'share')
        resource = os.path.join(*resource)
        assert not resource.startswith('/')
        path = os.path.join(xdg_data_home, resource)
        if not os.path.isdir(path):
            os.makedirs(path)
        return path

if __name__ == "__main__":
    import doctest
    (FAILED, ATTEMPTED) = doctest.testmod()
    if FAILED:
        sys.exit(1)
    else:
        sys.exit(0)
