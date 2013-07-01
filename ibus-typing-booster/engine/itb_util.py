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

