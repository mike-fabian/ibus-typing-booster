# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2015-2019 Mike FABIAN <mfabian@redhat.com>
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
Extra test cases for m17n_translit.py
'''

import sys

def dummy():
    '''
    >>> import m17n_translit
    >>> from m17n_translit import Transliterator

    >>> trans = Transliterator('mr-itrans')
    >>> trans.transliterate(list('namaste'))
    'नमस्ते'

    >>> trans = Transliterator('si-wijesekera')
    >>> trans.transliterate(list('a'))
    '්'
    >>> trans.transliterate(list('t'))
    'එ'
    >>> trans.transliterate(list('ta'))
    'ඒ'

    >>> trans = Transliterator('si-sayura')
    >>> trans.transliterate(list('a'))
    'අ'
    >>> trans.transliterate(list('a '))
    'අ '
    >>> trans.transliterate(list('aa'))
    'ආ'
    >>> trans.transliterate(list('aa '))
    'ආ '
    >>> trans.transliterate(list('aaa'))
    'ආ'
    >>> trans.transliterate(list('aaaa'))
    'ආ'
    >>> trans.transliterate(list('aaaa '))
    'ආ '
    >>> trans.transliterate(list('A'))
    'ඇ'
    >>> trans.transliterate(list('q'))
    'ඇ'
    >>> trans.transliterate(list('AA'))
    'ඈ'
    >>> trans.transliterate(list('qq'))
    'ඈ'
    >>> trans.transliterate(list('Aa'))
    'ආ'
    >>> trans.transliterate(list('qa'))
    'ආ'
    >>> trans.transliterate(list('e'))
    'එ'
    >>> trans.transliterate(list('E'))
    'එ'
    >>> trans.transliterate(list('ee'))
    'ඒ'
    >>> trans.transliterate(list('EE'))
    'ඒ'
    >>> trans.transliterate(list('eE'))
    'ඒ'
    >>> trans.transliterate(list('eee'))
    'ඒ'
    >>> trans.transliterate(list('EEE'))
    'ඒ'
    >>> trans.transliterate(list('eEe'))
    'ඒ'
    >>> trans.transliterate(list('i'))
    'ඉ'
    >>> trans.transliterate(list('ii'))
    'ඊ'
    >>> trans.transliterate(list('iii'))
    'ඊ'
    >>> trans.transliterate(list('u'))
    'උ'
    >>> trans.transliterate(list('uu'))
    'ඌ'
    >>> trans.transliterate(list('uuu'))
    'ඌ'
    >>> trans.transliterate(list('I'))
    'ඓ'
    >>> trans.transliterate(list('II'))
    ''
    >>> trans.transliterate(list('o'))
    'ඔ'
    >>> trans.transliterate(list('oo'))
    'ඕ'
    >>> trans.transliterate(list('O'))
    'ඖ'
    >>> trans.transliterate(list('OO'))
    ''
    >>> trans.transliterate(list('u'))
    'උ'
    >>> trans.transliterate(list('U'))
    'ඍ'
    >>> trans.transliterate(list('UU'))
    'ඎ'
    >>> trans.transliterate(list('V')) # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
    'ව'
    >>> trans.transliterate(list('VV')) # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
    'වව'
    >>> trans.transliterate(list('z'))
    'ඤ'
    >>> trans.transliterate(list('Z'))
    'ඥ'
    >>> trans.transliterate(list('k'))
    'ක'
    >>> trans.transliterate(list('ka'))
    'කා'
    >>> trans.transliterate(list('K'))
    'ඛ'
    >>> trans.transliterate(list('H'))
    'හ'
    >>> trans.transliterate(list('kf')) # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
    'කෆ'
    >>> trans.transliterate(list('kH'))
    'ඛ'
    >>> trans.transliterate(list('kaa'))
    'කා'
    >>> trans.transliterate(list('f'))
    'ෆ'
    >>> trans.transliterate(list('g'))
    'ග'
    >>> trans.transliterate(list('gf')) # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
    'ගෆ'
    >>> trans.transliterate(list('gH'))
    'ඝ'
    >>> trans.transliterate(list('X'))
    'ඞ'
    >>> trans.transliterate(list('c'))
    'ච'
    >>> trans.transliterate(list('C'))
    'ඡ'
    >>> trans.transliterate(list('cf')) # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
    'චෆ'
    >>> trans.transliterate(list('cH'))
    'ඡ'
    >>> trans.transliterate(list('j'))
    'ජ'
    >>> trans.transliterate(list('J'))
    'ඣ'
    >>> trans.transliterate(list('jf')) # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
    'ජෆ'
    >>> trans.transliterate(list('jH'))
    'ඣ'
    >>> trans.transliterate(list('T'))
    'ට'
    >>> trans.transliterate(list('Tf')) # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
    'ටෆ'
    >>> trans.transliterate(list('TH'))
    'ඨ'
    >>> trans.transliterate(list('D'))
    'ඩ'
    >>> trans.transliterate(list('Df')) # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
    'ඩෆ'
    >>> trans.transliterate(list('DH'))
    'ඪ'
    >>> trans.transliterate(list('N'))
    'ණ'
    >>> trans.transliterate(list('n'))
    'න'
    >>> trans.transliterate(list('m'))
    'ම'
    >>> trans.transliterate(list('L'))
    'ළ'
    >>> trans.transliterate(list('F'))
    'ෆ'
    >>> trans.transliterate(list('t'))
    'ත'
    >>> trans.transliterate(list('tf')) # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
    'තෆ'
    >>> trans.transliterate(list('tH'))
    'ථ'
    >>> trans.transliterate(list('d'))
    'ද'
    >>> trans.transliterate(list('df')) # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
    'දෆ'
    >>> trans.transliterate(list('dH'))
    'ධ'
    >>> trans.transliterate(list('p'))
    'ප'
    >>> trans.transliterate(list('P'))
    'ඵ'
    >>> trans.transliterate(list('pf')) # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
    'පෆ'
    >>> trans.transliterate(list('pH'))
    'ඵ'
    >>> trans.transliterate(list('b'))
    'බ'
    >>> trans.transliterate(list('B'))
    'භ'
    >>> trans.transliterate(list('bf')) # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
    'බෆ'
    >>> trans.transliterate(list('bH'))
    'භ'
    >>> trans.transliterate(list('y'))
    'ය'
    >>> trans.transliterate(list('r'))
    'ර'
    >>> trans.transliterate(list('l'))
    'ල'
    >>> trans.transliterate(list('v'))
    'ව'
    >>> trans.transliterate(list('s'))
    'ස'
    >>> trans.transliterate(list('S'))
    'ශ'
    >>> trans.transliterate(list('sf')) # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
    'සෆ'
    >>> trans.transliterate(list('Sf')) # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
    'ශෆ'
    >>> trans.transliterate(list('sH'))
    'ෂ'
    >>> trans.transliterate(list('SH'))
    'ෂ'
    >>> trans.transliterate(list('h'))
    'හ'
    >>> trans.transliterate(list('G'))
    'ඟ'
    >>> trans.transliterate(list('gG'))
    'ඟ'
    >>> trans.transliterate(list('dG'))
    'ඳ'
    >>> trans.transliterate(list('DG'))
    'ඬ'
    >>> trans.transliterate(list('M'))
    'ඹ'
    >>> trans.transliterate(list('bG'))
    'ඹ'
    >>> trans.transliterate(list('kw'))
    'ක්'
    >>> trans.transliterate(list('ka'))
    'කා'
    >>> trans.transliterate(list('kq'))
    'කැ'
    >>> trans.transliterate(list('kqq'))
    'කෑ'
    >>> trans.transliterate(list('ki'))
    'කි'
    >>> trans.transliterate(list('kii'))
    'කී'
    >>> trans.transliterate(list('ku'))
    'කු'
    >>> trans.transliterate(list('kuu'))
    'කූ'
    >>> trans.transliterate(list('kU'))
    'කෘ'
    >>> trans.transliterate(list('kUU'))
    'කෲ'
    >>> trans.transliterate(list('ke'))
    'කෙ'
    >>> trans.transliterate(list('kee'))
    'කේ'
    >>> trans.transliterate(list('ko'))
    'කො'
    >>> trans.transliterate(list('koo'))
    'කෝ'
    >>> trans.transliterate(list('kI'))
    'කෛ'
    >>> trans.transliterate(list('kO'))
    'කෞ'
    >>> trans.transliterate(list('kx'))
    'කං'
    >>> trans.transliterate(list('kQ')) # FIXME agrees with ibus-sayura, but: https://www.sayura.net/im/sayura.pdf
    'කQ'
    >>> trans.transliterate(list('W'))
    '\u200c'
    >>> trans.transliterate(list('kWsH'))
    'ක්‍ෂ'
    >>> trans.transliterate(list('nWd'))
    'න්‍ද'
    >>> trans.transliterate(list('nWdu'))
    'න්‍දු'
    >>> trans.transliterate(list('inWdRiy'))
    'ඉන්‍ද්‍රිය'
    >>> trans.transliterate(list('rWk'))
    'ර්‍ක'
    >>> trans.transliterate(list('R'))
    'ර'
    >>> trans.transliterate(list('Y'))
    'ය'
    >>> trans.transliterate(list('kR'))
    'ක්‍ර'
    >>> trans.transliterate(list('kY'))
    'ක්‍ය'
    >>> trans.transliterate(list('E'))
    'එ'
    '''

if __name__ == "__main__":
    import doctest
    (FAILED, ATTEMPTED) = doctest.testmod()
    if FAILED:
        # Return number of failed tests:
        sys.exit(FAILED)
    sys.exit(0)
