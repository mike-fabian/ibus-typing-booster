# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 2013 Mike FABIAN <mfabian@redhat.com>
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
categories_to_trigger_immediate_commit = ['Po', 'Pi', 'Pf', 'Ps', 'Pe', 'Pc', 'Sm', 'Sc', 'Cf']

categories_to_strip_from_tokens = ['Po', 'Pi', 'Pf', 'Ps', 'Pe', 'Pc', 'Pd', 'Sm', 'Sc', 'Cf']

def lstrip_token(token):
    token = token.lstrip()
    while len(token) > 0 and unicodedata.category(token[0]) in categories_to_strip_from_tokens:
        token = token[1:]
    return token

def rstrip_token(token):
    token = token.rstrip()
    while len(token) > 0 and unicodedata.category(token[-1]) in categories_to_strip_from_tokens:
        token = token[0:-1]
    return token

def strip_token(token):
    return rstrip_token(lstrip_token(token))

def tokenize(text):
    pattern = re.compile(r'[\s]+', re.UNICODE)
    tokens = []
    for s in pattern.split(text.strip()):
        tokens.append(strip_token(s))
    return tokens

