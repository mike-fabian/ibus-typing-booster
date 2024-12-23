# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2013-2018 Mike FABIAN <mfabian@redhat.com>
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

from typing import Any
from typing import Tuple
from typing import List
from typing import Dict
from typing import Set
from typing import Optional
from typing import Union
from typing import Iterable
from typing import Callable
# pylint: disable=wrong-import-position
import sys
if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal
from enum import Enum, Flag
import os
import re
import functools
import collections
import unicodedata
import locale
import logging
import shutil
import subprocess
import glob
import gettext
from gi import require_version # type: ignore
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore
require_version('GLib', '2.0')
from gi.repository import GLib
require_version('Gdk', '3.0')
from gi.repository import Gdk
require_version('Gtk', '3.0')
from gi.repository import Gtk
# pylint: enable=wrong-import-position

import itb_version

IMPORT_DISTRO_SUCCESSFUL = False
try:
    import distro
    IMPORT_DISTRO_SUCCESSFUL = True
except (ImportError,):
    IMPORT_DISTRO_SUCCESSFUL = False

# Importing xdg.BaseDirectory is not needed at the moment, see
# the implemention of xdg_save_data_path() below does not use it
# at the moment.
#
#IMPORT_XDG_BASEDIRECTORY_SUCCESSFUL = False
#try:
#    import xdg.BaseDirectory # type: ignore
#    IMPORT_XDG_BASEDIRECTORY_SUCCESSFUL = True
#except (ImportError,):
#    IMPORT_XDG_BASEDIRECTORY_SUCCESSFUL = False

IMPORT_PYAUDIO_SUCCESSFUL = False
try:
    import pyaudio # type: ignore
    IMPORT_PYAUDIO_SUCCESSFUL = True
except (ImportError,):
    IMPORT_PYAUDIO_SUCCESSFUL = False

IMPORT_QUEUE_SUCCESSFUL = False
try:
    import queue
    IMPORT_QUEUE_SUCCESSFUL = True
except (ImportError,):
    IMPORT_QUEUE_SUCCESSFUL = False

IMPORT_LANGTABLE_SUCCESSFUL = False
try:
    import langtable # type: ignore
    IMPORT_LANGTABLE_SUCCESSFUL = True
except (ImportError,):
    IMPORT_LANGTABLE_SUCCESSFUL = False

IMPORT_PYCOUNTRY_SUCCESSFUL = False
try:
    import pycountry # type: ignore
    IMPORT_PYCOUNTRY_SUCCESSFUL = True
except (ImportError,):
    IMPORT_PYCOUNTRY_SUCCESSFUL = False

LOGGER = logging.getLogger('ibus-typing-booster')

DOMAINNAME = 'ibus-typing-booster'
_: Callable[[str], str] = lambda a: gettext.dgettext(DOMAINNAME, a)
N_: Callable[[str], str] = lambda a: a

M17N_ENGINE_NAME_PATTERN = re.compile(
    r'^tb:(?P<lang>[a-z]{1,3}):(?P<name>[^\s:]+)$')

AVAILABLE_IBUS_KEYMAPS = ('in', 'jp', 'kr', 'us')

# When matching keybindings, only the bits in the following mask are
# considered for key.state:
KEYBINDING_STATE_MASK = (
    IBus.ModifierType.MODIFIER_MASK
    & ~IBus.ModifierType.LOCK_MASK # Caps Lock
    & ~IBus.ModifierType.MOD2_MASK # Num Lock
    & ~IBus.ModifierType.MOD3_MASK # Scroll Lock
)

# The number of current dictionaries needs to be limited to some fixed
# maximum number because of the property menu to select the highest
# priority dictionary. Unfortunately the number of sub-properties for
# such a menu cannot be changed, as a workaround a fixed number can be
# used and unused entries can be hidden.
MAXIMUM_NUMBER_OF_DICTIONARIES = 10

# The number of current imes needs to be limited to some fixed
# maximum number because of the property menu to select the preëdit
# ime. Unfortunately the number of sub-properties for such a menu
# cannot be changed, as a workaround a fixed number can be used
# and unused entries can be hidden.
MAXIMUM_NUMBER_OF_INPUT_METHODS = 10

NORMALIZATION_FORM_INTERNAL: Literal['NFC', 'NFD', 'NFKC', 'NFKD'] = 'NFD'

# maximum possible value for the Gsettings.get_int32()
INT32_MAX = 2**31-1
# maximum possible value for the Gsettings.get_uint32()
UINT32_MAX = 2**32-1
# maximum possible value for the INTEGER datatype in SQLite3
# and for Gsettings.get_int64()
INT64_MAX = 2**63-1
# maximum possible value for the Gsettings.get_uint64()
UINT64_MAX = 2**64-1
# user frequency used for a user defined shortcut
SHORTCUT_USER_FREQ = 1000000

# If a punctuation character from the following list is comitted
# (possibly followed by whitespace) remove trailing white space before
# the committed string. For example if commit_phrase is “!”, and the
# context before is “word ”, make the result “word!”.  And if the
# commit_phrase is “!  ” and the context before is “word ” make the
# result “word! ”.
FIX_WHITESPACE_CHARACTERS = {
    'fr_FR': {'.,)]}': '',
              '?!;:%#«»€$¢£¥฿': ' ', # U+202F NARROW NO-BREAK SPACE
              },
    'fr_CA': {'.,;?!)]}': '',
              ':': ' ', # U+202F NARROW NO-BREAK SPACE
              },
    # all other languages:
    '*': {'.,;:?!)]}': ''},
}
FIX_WHITESPACE_CHARACTERS['fr_MC'] = FIX_WHITESPACE_CHARACTERS['fr_FR']
FIX_WHITESPACE_CHARACTERS['fr_BE'] = FIX_WHITESPACE_CHARACTERS['fr_FR']
FIX_WHITESPACE_CHARACTERS['fr_LU'] = FIX_WHITESPACE_CHARACTERS['fr_FR']
FIX_WHITESPACE_CHARACTERS['fr_CH'] = FIX_WHITESPACE_CHARACTERS['fr_FR']

# If a commit ends with one of these characters and auto-capitalization is
# activated, capitalize the next word:
AUTO_CAPITALIZE_CHARACTERS = '.;:?!)'

CATEGORIES_TO_STRIP_FROM_TOKENS = (
    'Po', # Punctuation Other
    'Pi', # Punctuation Initial quote
    'Pf', # Punctuation Final quote
    'Ps', # Punctuation Open
    'Pe', # Punctuation Close
    'Pc', # Punctuation Connector
    'Pd', # Punctuation Dash
)

# List of languages where accent insensitive matching makes sense:
ACCENT_LANGUAGES = {
    'af': '',
    'ast': '',
    'az': '',
    'be': '',
    'bg': '',
    'br': '',
    'bs': '',
    'ca': '',
    'cs': '',
    'csb': '',
    'cv': '',
    'cy': '',
    'da': 'æÆøØåÅ',
    'de': '',
    'dsb': '',
    'el': '',
    'en': '',
    'es': '',
    'eu': '',
    'fi': 'åÅäÄöÖ',
    'fo': '',
    'fr': '',
    'fur': '',
    'fy': '',
    'ga': '',
    'gd': '',
    'gl': '',
    'grc': '',
    'gv': '',
    'haw': '',
    'hr': '',
    'hsb': '',
    'ht': '',
    'hu': '',
    'ia': '',
    'is': '',
    'it': '',
    'kk': '',
    'ku': '',
    'ky': '',
    'lb': '',
    'ln': '',
    'lv': '',
    'mg': '',
    'mi': '',
    'mk': '',
    'mn': '',
    'mos': '',
    'mt': '',
    'nb': 'æÆøØåÅ',
    'nds': '',
    'nl': '',
    'nn': 'æÆøØåÅ',
    'nr': '',
    'nso': '',
    'ny': '',
    'oc': '',
    'pl': '',
    'plt': '',
    'pt': '',
    'qu': '',
    'quh': '',
    'ru': '',
    'sc': '',
    'se': '',
    'sh': '',
    'shs': '',
    'sk': '',
    'sl': '',
    'smj': '',
    'sq': '',
    'sr': '',
    'ss': '',
    'st': '',
    'sv': 'åÅäÄöÖ',
    'tet': '',
    'tk': '',
    'tn': '',
    'ts': '',
    'uk': '',
    'uz': '',
    've': '',
    'vi': '',
    'wa': '',
    'xh': '',
}

M17N_IME_SYMBOLS = [
    # These are to be displayed in the Gnome panel when the input method
    # is selected. In the Panels of non-Gnome desktops, the icons are displayed
    # instead.
    #
    # However, even on non-Gnome desktops, if a direct input mode is
    # enabled these symbols are displayed instead of the icons if
    # switching between “normal” input mode and direct input mode. To
    # indicate direct input mode, a character is added to the
    # symbol. As symbols longer than 2 Unicode characters to not work
    # as indicators for input methods in the Gnome panel, make sure
    # all of these symbols are consist of only one Unicode character
    # so that when the character to indicate direct input mode is
    # added, it still does not exceed 2 characters (Invisible
    # characters count as well to this limit, do not add extra
    # invisible characters like combining characters or variation
    # selectors!)
    #
    # See also:
    # https://bugzilla.redhat.com/show_bug.cgi?id=1678386
    # https://gitlab.gnome.org/GNOME/gnome-shell/-/issues/1026
    # (Input method indicator should not limit to 2 characters, at least 3 characters should be allowed)
    #
    # These symbols are chosen almost like those in ibus-m17n, except where
    # it exceeds the one character limit.
    (r'tb:zh:tonepy.*', '调'),
    (r'tb:zh:quick', '簡'),
    (r'tb:zh:py.*', '拼'),
    (r'tb:zh:pinyin.*', 'P'), # ibus-m17n uses 'PY'
    (r'tb:zh:cangjie.*', '倉'),
    (r'tb:zh:bopomofo.*', 'ㄅ'),
    (r'tb:yi:.+', 'ש'),
    (r'tb:vi:nom.*', '喃'),
    (r'tb:vi:han.*', '越'),
    (r'tb:vi:.+', 'ắ'),
    (r'tb:ur:.+', 'خ'),
    (r'tb:th:.+', 'ท'),
    (r'tb:tai:.+', '꫞'),
    (r'tb:ru:.+', 'Я'),
    (r'tb:ps:.+', 'خ'),
    (r'tb:oj:.+', 'ᐏ'),
    (r'tb:nsk:.+', 'ᐃ'),
    (r'tb:lo:.+', 'ກ'),
    (r'tb:km:.+', 'ក'),
    (r'tb:kk:kbd', 'Қ'), # ibus-m17n uses ҚА
    (r'tb:kk:arabic', 'ق'), # ibus-m17n uses قا
    (r'tb:ja:.+', 'あ'),
    (r'tb:iu:.+', 'ᐃ'),
    (r'tb:ii:.+', 'ꆈ'),
    (r'tb:fa:.+', 'ف'),
    (r'tb:cr:.+', 'ᐃ'),
    (r'tb:bo:.+', 'ཀ'),
    (r'tb:am:.+', 'አ'),
    (r'tb:te:.+', 'క'),
    (r'tb:ta:.+', 'க'),
    (r'tb:si:.+', 'සි'),
    (r'tb:sd:.+', 'क'),
    (r'tb:sat:.+deva', 'क'),
    (r'tb:sat:.+olck', 'ᱚ'),
    (r'tb:sa:.+', 'क'),
    (r'tb:pa:.+', 'ਕ'),
    (r'tb:or:.+', 'କ'),
    (r'tb:ne:.+', 'क'),
    (r'tb:mr:.+', 'क'),
    (r'tb:mni:.+mtei', 'ꯀ'),
    (r'tb:mni:.+beng', 'ক'),
    (r'tb:ml:.+', 'ക'),
    (r'tb:mai:.+', 'क'),
    (r'tb:ks:kbd', 'خ'),
    (r'tb:ks:.+', 'क'),
    (r'tb:kok:.+', 'क'),
    (r'tb:kn:.+', 'ಕ'),
    (r'tb:hi:.+', 'क'),
    (r'tb:gu:.+', 'ક'),
    (r'tb:doi:.+', 'क'),
    (r'tb:brx:.+', 'क'),
    (r'tb:bn:.+', 'ক'),
    (r'tb:as:.+', 'ক'),
    # Fallback for all the rest is ⌨ U+2328 KEYBOARD.  A character to
    # indicate direct input mode can be added to this:
    (r'.*', '\u2328'),
]

LOCALE_DEFAULTS = {
    # Contains the default input methods and dictionaries which should
    # be used if ibus-typing-booster is started for the very first
    # time. In that case, no previous settings can be found from dconf
    # and a reasonable default should be used depending on the current
    # locale.
    'af': {'inputmethods': ['NoIME'], 'dictionaries': ['af_ZA']},
    'af_NA': {'inputmethods': ['NoIME'], 'dictionaries': ['af_NA']},
    'ak': {'inputmethods': ['NoIME'], 'dictionaries': ['ak_GH']},
    'am': {'inputmethods': ['am-sera'], 'dictionaries': ['am_ET']},
    'ar': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_SA']},
    'ar_AE': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_AE']},
    'ar_BH': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_BH']},
    'ar_DJ': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_DJ']},
    'ar_DZ': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_DZ']},
    'ar_EG': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_EG']},
    'ar_ER': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_ER']},
    'ar_IL': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_IL']},
    'ar_IN': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_IN']},
    'ar_IQ': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_IQ']},
    'ar_JO': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_JO']},
    'ar_KM': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_KM']},
    'ar_KW': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_KW']},
    'ar_LB': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_LB']},
    'ar_LY': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_LY']},
    'ar_MA': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_MA']},
    'ar_MR': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_MR']},
    'ar_OM': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_OM']},
    'ar_PS': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_PS']},
    'ar_QA': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_QA']},
    'ar_SA': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_SA']},
    'ar_SD': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_SD']},
    'ar_SO': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_SO']},
    'ar_SY': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_SY']},
    'ar_TD': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_TD']},
    'ar_TN': {'inputmethods':['ar-kbd', 'NoIME'], 'dictionaries': ['ar_TN']},
    'ar_YE': {'inputmethods': ['ar-kbd', 'NoIME'], 'dictionaries': ['ar_YE']},
    # libgnome-desktop/default-input-sources.h has "m17n:as:phonetic"
    # as the default. Parag Nemade says the as translator for Fedora a long
    # time back used as-phonetic. We have no later data from the
    # community.
    'as': {'inputmethods': ['as-inscript2', 'NoIME'],
           'dictionaries': ['as_IN', 'en_GB']},
    'ast': {'inputmethods': ['NoIME'], 'dictionaries': ['ast_ES']},
    'az': {'inputmethods': ['NoIME'], 'dictionaries': ['az_AZ']},
    'be': {'inputmethods': ['NoIME'], 'dictionaries': ['be_BY']},
    'ber': {'inputmethods': ['NoIME'], 'dictionaries': ['ber_MA']},
    'bg': {'inputmethods': ['NoIME'], 'dictionaries': ['bg_BG']},
    'bn': {'inputmethods': ['bn-inscript2', 'NoIME'],
           'dictionaries': ['bn_IN', 'en_GB']},
    'br': {'inputmethods': ['NoIME'], 'dictionaries': ['br_FR']},
    'brx': {'inputmethods': ['brx-inscript2-deva', 'NoIME'],
            'dictionaries': ['en_GB']},
    'bs': {'inputmethods': ['NoIME'], 'dictionaries': ['bs_BA']},
    'ca': {'inputmethods': ['NoIME'], 'dictionaries': ['ca_ES']},
    'ca_AD': {'inputmethods': ['NoIME'], 'dictionaries': ['ca_AD']},
    'ca_FR': {'inputmethods': ['NoIME'], 'dictionaries': ['ca_FR']},
    'ca_IT': {'inputmethods': ['NoIME'], 'dictionaries': ['ca_IT']},
    'cop': {'inputmethods': ['NoIME'], 'dictionaries': ['cop_EG']},
    'cs': {'inputmethods': ['NoIME'], 'dictionaries': ['cs_CZ']},
    'csb': {'inputmethods': ['NoIME'], 'dictionaries': ['csb_PL']},
    'cv': {'inputmethods': ['NoIME'], 'dictionaries': ['cv_RU']},
    'cy': {'inputmethods': ['NoIME'], 'dictionaries': ['cy_GB']},
    'da': {'inputmethods': ['NoIME'], 'dictionaries': ['da_DK']},
    'de': {'inputmethods':['NoIME'], 'dictionaries': ['de_DE']},
    'de_AT': {'inputmethods': ['NoIME'], 'dictionaries': ['de_AT']},
    'de_BE': {'inputmethods': ['NoIME'], 'dictionaries': ['de_BE']},
    'de_CH': {'inputmethods': ['NoIME'], 'dictionaries': ['de_CH']},
    'de_LI': {'inputmethods': ['NoIME'], 'dictionaries': ['de_LI']},
    'de_LU': {'inputmethods': ['NoIME'], 'dictionaries': ['de_LU']},
    'doi': {'inputmethods': ['doi-inscript2-deva', 'NoIME'],
            'dictionaries': ['en_GB']},
    'dsb': {'inputmethods': ['NoIME'], 'dictionaries': ['dsb_DE']},
    'el': {'inputmethods': ['NoIME'], 'dictionaries': ['el_GR']},
    'en': {'inputmethods': ['NoIME'], 'dictionaries': ['en_US']},
    'en_US': {'inputmethods': ['NoIME'], 'dictionaries': ['en_US']},
    'el_CY': {'inputmethods': ['NoIME'], 'dictionaries': ['el_CY']},
    'en_AG': {'inputmethods': ['NoIME'], 'dictionaries': ['en_AG']},
    'en_AU': {'inputmethods': ['NoIME'], 'dictionaries': ['en_AU']},
    'en_BS': {'inputmethods': ['NoIME'], 'dictionaries': ['en_BS']},
    'en_BW': {'inputmethods': ['NoIME'], 'dictionaries': ['en_BW']},
    'en_BZ': {'inputmethods': ['NoIME'], 'dictionaries': ['en_BZ']},
    'en_CA': {'inputmethods': ['NoIME'], 'dictionaries': ['en_CA']},
    'en_DK': {'inputmethods': ['NoIME'], 'dictionaries': ['en_DK']},
    'en_GB': {'inputmethods': ['NoIME'], 'dictionaries': ['en_GB']},
    'en_GH': {'inputmethods': ['NoIME'], 'dictionaries': ['en_GH']},
    'en_HK': {'inputmethods': ['NoIME'], 'dictionaries': ['en_HK']},
    'en_IE': {'inputmethods': ['NoIME'], 'dictionaries': ['en_IE']},
    'en_IN': {'inputmethods': ['NoIME'], 'dictionaries': ['en_IN']},
    'en_JM': {'inputmethods': ['NoIME'], 'dictionaries': ['en_JM']},
    'en_MW': {'inputmethods': ['NoIME'], 'dictionaries': ['en_MW']},
    'en_NA': {'inputmethods': ['NoIME'], 'dictionaries': ['en_NA']},
    'en_NG': {'inputmethods': ['NoIME'], 'dictionaries': ['en_NG']},
    'en_NZ': {'inputmethods': ['NoIME'], 'dictionaries': ['en_NZ']},
    'en_PH': {'inputmethods': ['NoIME'], 'dictionaries': ['en_PH']},
    'en_SG': {'inputmethods': ['NoIME'], 'dictionaries': ['en_SG']},
    'en_TT': {'inputmethods': ['NoIME'], 'dictionaries': ['en_TT']},
    'en_ZA': {'inputmethods': ['NoIME'], 'dictionaries': ['en_ZA']},
    'en_ZM': {'inputmethods': ['NoIME'], 'dictionaries': ['en_ZM']},
    'en_ZW': {'inputmethods': ['NoIME'], 'dictionaries': ['en_ZW']},
    'eo': {'inputmethods': ['NoIME'], 'dictionaries': ['eo']},
    'es_': {'inputmethods': ['NoIME'], 'dictionaries': ['es_ES']},
    'es_AR': {'inputmethods': ['NoIME'], 'dictionaries': ['es_AR']},
    'es_BO': {'inputmethods': ['NoIME'], 'dictionaries': ['es_BO']},
    'es_CL': {'inputmethods': ['NoIME'], 'dictionaries': ['es_CL']},
    'es_CO': {'inputmethods': ['NoIME'], 'dictionaries': ['es_CO']},
    'es_CR': {'inputmethods': ['NoIME'], 'dictionaries': ['es_CR']},
    'es_CU': {'inputmethods': ['NoIME'], 'dictionaries': ['es_CU']},
    'es_DO': {'inputmethods': ['NoIME'], 'dictionaries': ['es_DO']},
    'es_EC': {'inputmethods': ['NoIME'], 'dictionaries': ['es_EC']},
    'es_ES': {'inputmethods': ['NoIME'], 'dictionaries': ['es_ES']},
    'es_GT': {'inputmethods': ['NoIME'], 'dictionaries': ['es_GT']},
    'es_HN': {'inputmethods': ['NoIME'], 'dictionaries': ['es_HN']},
    'es_MX': {'inputmethods': ['NoIME'], 'dictionaries': ['es_MX']},
    'es_NI': {'inputmethods': ['NoIME'], 'dictionaries': ['es_NI']},
    'es_PA': {'inputmethods': ['NoIME'], 'dictionaries': ['es_PA']},
    'es_PE': {'inputmethods': ['NoIME'], 'dictionaries': ['es_PE']},
    'es_PR': {'inputmethods': ['NoIME'], 'dictionaries': ['es_PR']},
    'es_PY': {'inputmethods': ['NoIME'], 'dictionaries': ['es_PY']},
    'es_SV': {'inputmethods': ['NoIME'], 'dictionaries': ['es_SV']},
    'es_US': {'inputmethods': ['NoIME'], 'dictionaries': ['es_US']},
    'es_UY': {'inputmethods': ['NoIME'], 'dictionaries': ['es_UY']},
    'es_VE': {'inputmethods': ['NoIME'], 'dictionaries': ['es_VE']},
    'et': {'inputmethods': ['NoIME'], 'dictionaries': ['et_EE']},
    'eu': {'inputmethods': ['NoIME'], 'dictionaries': ['eu_ES']},
    'fa': {'inputmethods': ['NoIME'], 'dictionaries': ['fa_IR']},
    'fil': {'inputmethods': ['NoIME'], 'dictionaries': ['fil_PH']},
    'fj': {'inputmethods': ['NoIME'], 'dictionaries': ['fj']},
    'fo': {'inputmethods': ['NoIME'], 'dictionaries': ['fo_FO']},
    'fr': {'inputmethods': ['NoIME'], 'dictionaries': ['fr_FR']},
    'fr_BE': {'inputmethods': ['NoIME'], 'dictionaries': ['fr_BE']},
    'fr_CA': {'inputmethods': ['NoIME'], 'dictionaries': ['fr_CA']},
    'fr_CH': {'inputmethods': ['NoIME'], 'dictionaries': ['fr_CH']},
    'fr_LU': {'inputmethods': ['NoIME'], 'dictionaries': ['fr_LU']},
    'fr_MC': {'inputmethods': ['NoIME'], 'dictionaries': ['fr_MC']},
    'fur': {'inputmethods': ['NoIME'], 'dictionaries': ['fur_IT']},
    'fy': {'inputmethods': ['NoIME'], 'dictionaries': ['fy_NL']},
    'fy_DE': {'inputmethods': ['NoIME'], 'dictionaries': ['fy_DE']},
    'ga': {'inputmethods': ['NoIME'], 'dictionaries': ['ga_IE']},
    'gd': {'inputmethods': ['NoIME'], 'dictionaries': ['gd_GB']},
    'gl': {'inputmethods': ['NoIME'], 'dictionaries': ['gl_ES']},
    'grc': {'inputmethods': ['NoIME'], 'dictionaries': ['grc']},
    'gu': {'inputmethods': ['gu-inscript2', 'NoIME'],
           'dictionaries': ['gu_IN', 'en_GB']},
    'gv': {'inputmethods': ['NoIME'], 'dictionaries': ['gv_GB']},
    'haw': {'inputmethods': ['NoIME'], 'dictionaries': ['haw']},
    'he': {'inputmethods': ['NoIME'], 'dictionaries': ['he_IL']},
    'hi': {'inputmethods': ['hi-inscript2', 'NoIME'],
           'dictionaries': ['hi_IN', 'en_GB']},
    'hil': {'inputmethods': ['NoIME'], 'dictionaries': ['hil_PH']},
    'hr': {'inputmethods': ['NoIME'], 'dictionaries': ['hr_HR']},
    'hsb': {'inputmethods': ['NoIME'], 'dictionaries': ['hsb_DE']},
    'ht': {'inputmethods': ['NoIME'], 'dictionaries': ['ht_HT']},
    'hu': {'inputmethods': ['NoIME'], 'dictionaries': ['hu_HU']},
    'hy': {'inputmethods': ['NoIME'], 'dictionaries': ['hy_AM']},
    'ia': {'inputmethods': ['NoIME'], 'dictionaries': ['ia']},
    'id': {'inputmethods': ['NoIME'], 'dictionaries': ['id_ID']},
    'is': {'inputmethods': ['NoIME'], 'dictionaries': ['is_IS']},
    'it': {'inputmethods': ['NoIME'], 'dictionaries': ['it_IT']},
    'it_CH': {'inputmethods': ['NoIME'], 'dictionaries': ['it_CH']},
    'kk': {'inputmethods': ['NoIME'], 'dictionaries': ['kk_KZ']},
    'km': {'inputmethods': ['NoIME'], 'dictionaries': ['km_KH']},
    # libgnome-desktop/default-input-sources.h has "m17n:kn:kgp" as
    # the default for kn_IN. According to Parag Nemade this probably came
    # from the translation community.
    'kn': {'inputmethods': ['kn-inscript2', 'NoIME'],
           'dictionaries': ['kn_IN', 'en_GB']},
    'ko': {'inputmethods': ['ko-han2', 'NoIME'],
           'dictionaries': ['ko_KR', 'en_GB']},
    'kok' : {'inputmethods': ['kok-inscript2-deva', 'NoIME'],
             'dictionaries': ['en_GB']},
    'ks': {'inputmethods': ['ks-kbd', 'NoIME'], 'dictionaries': ['en_GB']},
    'ks_Deva': {'inputmethods': ['ks-inscript2-deva', 'NoIME'],
                'dictionaries': ['en_GB']},
    'ku': {'inputmethods': ['NoIME'], 'dictionaries': ['ku_TR']},
    'ku_SY': {'inputmethods': ['NoIME'], 'dictionaries': ['ku_SY']},
    'ky': {'inputmethods': ['NoIME'], 'dictionaries': ['ky_KG']},
    'la': {'inputmethods': ['NoIME'], 'dictionaries': ['la']},
    'lb': {'inputmethods': ['NoIME'], 'dictionaries': ['lb_LU']},
    'ln': {'inputmethods': ['NoIME'], 'dictionaries': ['ln_CD']},
    'lt': {'inputmethods': ['NoIME'], 'dictionaries': ['lt_LT']},
    'lv': {'inputmethods': ['NoIME'], 'dictionaries': ['lv_LV']},
    'mai': {'inputmethods': ['mai-inscript2', 'NoIME'],
            'dictionaries': ['mai_IN', 'en_GB']},
    'mg': {'inputmethods': ['NoIME'], 'dictionaries': ['mg']},
    'mi': {'inputmethods': ['NoIME'], 'dictionaries': ['mi_NZ']},
    'mk': {'inputmethods': ['NoIME'], 'dictionaries': ['mk_MK']},
    'ml': {'inputmethods': ['ml-inscript2', 'NoIME'],
           'dictionaries': ['ml_IN', 'en_GB']},
    'mn': {'inputmethods': ['NoIME'], 'dictionaries': ['mn_MN']},
    'mni': {'inputmethods': ['mni-inscript2-beng', 'NoIME'],
            'dictionaries': ['en_GB']},
    'mni_Mtei': {'inputmethods': ['mni-inscript2-mtei', 'NoIME'],
                 'dictionaries': ['en_GB']},
    'mos': {'inputmethods': ['NoIME'], 'dictionaries': ['mos_BF']},
    'mr': {'inputmethods': ['mr-inscript2', 'NoIME'],
           'dictionaries': ['mr_IN', 'en_GB']},
    'ms': {'inputmethods': ['NoIME'], 'dictionaries': ['ms_MY']},
    'ms_BN': {'inputmethods': ['NoIME'], 'dictionaries': ['ms_BN']},
    'mt': {'inputmethods': ['NoIME'], 'dictionaries': ['mt_MT']},
    'nb': {'inputmethods': ['NoIME'], 'dictionaries': ['nb_NO']},
    'no': {'inputmethods': ['NoIME'], 'dictionaries': ['nb_NO']},
    'nds': {'inputmethods': ['NoIME'], 'dictionaries': ['nds_DE']},
    'nds_NL': {'inputmethods': ['NoIME'], 'dictionaries': ['nds_NL']},
    'ne': {'inputmethods': ['ne-rom', 'NoIME'],
           'dictionaries': ['ne_NP', 'en_GB']},
    'ne_IN': {'inputmethods': ['ne-inscript2-deva', 'NoIME'],
              'dictionaries': ['ne_IN', 'en_GB']},
    'nl': {'inputmethods': ['NoIME'], 'dictionaries': ['nl_NL']},
    'nl_AW': {'inputmethods': ['NoIME'], 'dictionaries': ['nl_AW']},
    'nl_BE': {'inputmethods': ['NoIME'], 'dictionaries': ['nl_BE']},
    'nn': {'inputmethods': ['NoIME'], 'dictionaries': ['nn_NO']},
    'nr': {'inputmethods': ['NoIME'], 'dictionaries': ['nr_ZA']},
    'nso': {'inputmethods': ['NoIME'], 'dictionaries': ['nso_ZA']},
    'ny': {'inputmethods': ['NoIME'], 'dictionaries': ['ny_MW']},
    'oc': {'inputmethods': ['NoIME'], 'dictionaries': ['oc_FR']},
    'om': {'inputmethods': ['NoIME'], 'dictionaries': ['om_ET']},
    'om_KE': {'inputmethods': ['NoIME'], 'dictionaries': ['om_KE']},
    'or': {'inputmethods': ['or-inscript2', 'NoIME'],
           'dictionaries': ['or_IN', 'en_GB']},
    'pa': {'inputmethods': ['pa-inscript2-guru', 'NoIME'],
           'dictionaries': ['pa_IN', 'en_GB']},
    'pa_PK': {'inputmethods': ['NoIME'], 'dictionaries': ['en_GB']},
    'pl': {'inputmethods': ['NoIME'], 'dictionaries': ['pl_PL']},
    'plt': {'inputmethods': ['NoIME'], 'dictionaries': ['plt']},
    'pt': {'inputmethods': ['NoIME'], 'dictionaries': ['pt_PT']},
    'pt_AO': {'inputmethods': ['NoIME'], 'dictionaries': ['pt_AO']},
    'pt_BR': {'inputmethods': ['NoIME'], 'dictionaries': ['pt_BR']},
    'pt_PT': {'inputmethods': ['NoIME'], 'dictionaries': ['pt_PT']},
    'qu': {'inputmethods': ['NoIME'], 'dictionaries': ['qu_EC']},
    'quh': {'inputmethods': ['NoIME'], 'dictionaries': ['quh_BO']},
    'ro': {'inputmethods': ['NoIME'], 'dictionaries': ['ro_RO']},
    'ru': {'inputmethods': ['NoIME'], 'dictionaries': ['ru_RU']},
    'ru_UA': {'inputmethods': ['NoIME'], 'dictionaries': ['ru_UA']},
    'rw': {'inputmethods': ['NoIME'], 'dictionaries': ['rw_RW']},
    'sa': {'inputmethods': ['sa-inscript2', 'NoIME'],
           'dictionaries': ['en_GB']},
    'sat': {'inputmethods': ['sat-inscript2-deva', 'NoIME'],
            'dictionaries': ['en_GB']},
    'sc': {'inputmethods': ['NoIME'], 'dictionaries': ['sc_IT']},
    'sd': {'inputmethods': ['NoIME'], 'dictionaries': ['en_GB']},
    'sd_Arab': {'inputmethods': ['NoIME'], 'dictionaries': ['en_GB']},
    'sd_Deva': {'inputmethods': ['sd-inscript2-deva', 'NoIME'],
                'dictionaries': ['en_GB']},
    'se': {'inputmethods': ['NoIME'], 'dictionaries': ['se_SE']},
    'se_FI': {'inputmethods': ['NoIME'], 'dictionaries': ['se_FI']},
    'se_NO': {'inputmethods': ['NoIME'], 'dictionaries': ['se_NO']},
    'sh': {'inputmethods': ['NoIME'], 'dictionaries': ['sh_RS']},
    'sh_ME': {'inputmethods': ['NoIME'], 'dictionaries': ['sh_ME']},
    'sh_YU': {'inputmethods': ['NoIME'], 'dictionaries': ['sh_YU']},
    'shs': {'inputmethods': ['NoIME'], 'dictionaries': ['shs_CA']},
    'si': {'inputmethods': ['si-wijesekara', 'NoIME'],
           'dictionaries': ['si_LK', 'en_GB']},
    'sk': {'inputmethods': ['NoIME'], 'dictionaries': ['sk_SK']},
    'sl': {'inputmethods': ['NoIME'], 'dictionaries': ['sl_SI']},
    'smj': {'inputmethods': ['NoIME'], 'dictionaries': ['smj_NO']},
    'smj_SE': {'inputmethods': ['NoIME'], 'dictionaries': ['smj_SE']},
    'so': {'inputmethods': ['NoIME'], 'dictionaries': ['so_SO']},
    'so_DJ': {'inputmethods': ['NoIME'], 'dictionaries': ['so_DJ']},
    'so_ET': {'inputmethods': ['NoIME'], 'dictionaries': ['so_ET']},
    'so_KE': {'inputmethods': ['NoIME'], 'dictionaries': ['so_KE']},
    'sq': {'inputmethods': ['NoIME'], 'dictionaries': ['sq_AL']},
    'sr': {'inputmethods': ['NoIME'], 'dictionaries': ['sr_RS']},
    'sr_ME': {'inputmethods': ['NoIME'], 'dictionaries': ['sr_ME']},
    'sr_YU': {'inputmethods': ['NoIME'], 'dictionaries': ['sr_YU']},
    'ss': {'inputmethods': ['NoIME'], 'dictionaries': ['ss_ZA']},
    'st': {'inputmethods': ['NoIME'], 'dictionaries': ['st_ZA']},
    'sv': {'inputmethods': ['NoIME'], 'dictionaries': ['sv_SE']},
    'sv_FI': {'inputmethods': ['NoIME'], 'dictionaries': ['sv_FI']},
    'sw': {'inputmethods': ['NoIME'], 'dictionaries': ['sw_TZ']},
    'sw_KE': {'inputmethods': ['NoIME'], 'dictionaries': ['sw_KE']},
    # libgnome-desktop/default-input-sources.h has "m17n:ta:tamil99"
    # as the default for ta_IN. According to Parag Nemade this probably came
    # from the translation community.
    'ta': {'inputmethods': ['ta-inscript2', 'NoIME'],
           'dictionaries': ['ta_IN', 'en_GB']},
    'te': {'inputmethods': ['te-inscript2', 'NoIME'],
           'dictionaries': ['te_IN', 'en_GB']},
    'tet': {'inputmethods': ['NoIME'], 'dictionaries': ['tet_ID']},
    'tet_TL': {'inputmethods': ['NoIME'], 'dictionaries': ['tet_TL']},
    'th': {'inputmethods': ['NoIME'], 'dictionaries': ['th_TH']},
    'ti': {'inputmethods': ['NoIME'], 'dictionaries': ['ti_ER']},
    'ti_ET': {'inputmethods': ['NoIME'], 'dictionaries': ['ti_ET']},
    'tk': {'inputmethods': ['NoIME'], 'dictionaries': ['tk_TM']},
    'tl': {'inputmethods': ['NoIME'], 'dictionaries': ['tl_PH']},
    'tn': {'inputmethods': ['NoIME'], 'dictionaries': ['tn_ZA']},
    'tn_BW': {'inputmethods': ['NoIME'], 'dictionaries': ['tn_BW']},
    'tpi': {'inputmethods': ['NoIME'], 'dictionaries': ['tpi_PG']},
    'ts': {'inputmethods': ['NoIME'], 'dictionaries': ['ts_ZA']},
    'uk': {'inputmethods': ['NoIME'], 'dictionaries': ['uk_UA']},
    'ur': {'inputmethods': ['NoIME'], 'dictionaries': ['ur_PK']},
    'ur_IN': {'inputmethods': ['ur-phonetic', 'NoIME'],
              'dictionaries': ['ur_IN', 'en_GB']},
    'uz': {'inputmethods': ['NoIME'], 'dictionaries': ['uz_UZ']},
    've': {'inputmethods': ['NoIME'], 'dictionaries': ['ve_ZA']},
    'vi': {'inputmethods': ['NoIME', 'vi-telex'], 'dictionaries': ['vi_VN']},
    'wa': {'inputmethods': ['NoIME'], 'dictionaries': ['wa_BE']},
    'xh': {'inputmethods': ['NoIME'], 'dictionaries': ['xh_ZA']},
    'yi': {'inputmethods': ['NoIME', 'yi-yivo'],
              'dictionaries': ['yi_US', 'en_US']},
    'zu': {'inputmethods': ['NoIME'], 'dictionaries': ['zu_ZA', 'en_GB']},
}

def get_default_input_methods(locale_string: str) -> List[str]:
    '''
    Gets the default input methods for a locale

    :param locale_string: The name of the locale to get the default
                          input methods for

    Examples:

    >>> get_default_input_methods('te_IN')
    ['te-inscript2', 'NoIME']

    >>> get_default_input_methods('ks_IN.UTF-8@devanagari')
    ['ks-inscript2-deva', 'NoIME']

    >>> get_default_input_methods('ks_IN.UTF-8')
    ['ks-kbd', 'NoIME']

    >>> get_default_input_methods('mni_IN.UTF-8')
    ['mni-inscript2-beng', 'NoIME']

    >>> get_default_input_methods('mni_Mtei') # No locale in glibc for this!
    ['mni-inscript2-mtei', 'NoIME']

    >>> get_default_input_methods('xx_YY')
    ['NoIME']
    '''
    language = locale_normalize(locale_string)
    for lang in expand_languages([language]):
        if lang in LOCALE_DEFAULTS:
            return LOCALE_DEFAULTS[lang]['inputmethods']
    return ['NoIME']

def get_default_dictionaries(locale_string: str) -> List[str]:
    '''
    Gets the default dictionaries for a locale

    :param locale_string: The name of the locale to get the default
                          dictionaries for

    Examples:

    >>> get_default_dictionaries('te_IN')
    ['te_IN', 'en_GB']

    >>> get_default_dictionaries('xx_YY')
    ['en_US']
    '''
    language = locale_normalize(locale_string)
    for lang in expand_languages([language]):
        if lang in LOCALE_DEFAULTS:
            return LOCALE_DEFAULTS[lang]['dictionaries']
    return ['en_US']

def input_methods_str_to_list(imes_str: str) -> List[str]:
    '''Converts a list of input methods from a comma separated string
    to a list of strings.

    :param imes_str: Input methods as a comma separated string

    Examples:

    If the input is not empty but contains nothing which could be an
    input method, the default input method ['NoIME'] is returned:

    >>> input_methods_str_to_list(',,')
    ['NoIME']

    If the input is empty, the default list of input methods for
    the current locale is returned:

    >>> old_lc_all = os.environ.get('LC_ALL')
    >>> os.environ['LC_ALL'] = 'hi_IN.UTF-8'
    >>> input_methods_str_to_list('')
    ['hi-inscript2', 'NoIME']

    >>> if old_lc_all:
    ...     os.environ['LC_ALL'] = old_lc_all
    ... else:
    ...     # unneeded return value assigned to variable
    ...     _ = os.environ.pop('LC_ALL', None)

    If the input has more than the maximum number of allowed input
    methods, the list is reduced to the maximum (currently 10):

    >>> input_methods_str_to_list('0, 1,2,3 ,4,5,6,7,8,9,10,11,12')
    ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']


    If the input contains duplicates, the duplicates are removed:

    >>> input_methods_str_to_list('a ,a,b , c ,, a ,d,e,f, ')
    ['a', 'b', 'c', 'd', 'e', 'f']

    Non-standard spellings of the special input method ['NoIME']
    are converted to the standard spelling:

    >>> input_methods_str_to_list('nOiMe')
    ['NoIME']
    '''
    if imes_str == '':
        return get_default_input_methods(get_effective_lc_ctype())
    imes: List[str] = []
    for ime in  [re.sub(re.escape('noime'), 'NoIME', x.strip(),
                        flags=re.IGNORECASE)
                 for x in imes_str.split(',') if x.strip()]:
        if ime not in imes:
            imes.append(ime)
    if len(imes) > MAXIMUM_NUMBER_OF_INPUT_METHODS:
        LOGGER.error(
            'More than the allowed maximum of %s input methods.\n'
            'Trying to use: %s\n'
            'Really using: %s\n',
            MAXIMUM_NUMBER_OF_INPUT_METHODS,
            imes,
            imes[:MAXIMUM_NUMBER_OF_INPUT_METHODS])
        imes = imes[:MAXIMUM_NUMBER_OF_INPUT_METHODS]
    if imes:
        return imes
    return ['NoIME']

def dictionaries_str_to_list(dictionaries_str: str) -> List[str]:
    # pylint: disable=line-too-long
    '''
    Converts a list of dictionaries from a comma separated string to
    a list of strings.

    ;param dictionaries_str: Dictionaries as a comma separated string

    Examples:

    If the input is not empty but contains nothing which could be a
    dictionary, the default dictionary ['en_US'] is returned:

    >>> dictionaries_str_to_list(',')
    ['en_US']

    If the input is empty, the default list of dictionaries for
    the current locale is returned:

    >>> old_lc_all = os.environ.get('LC_ALL')
    >>> os.environ['LC_ALL'] = 'hi_IN.UTF-8'
    >>> dictionaries_str_to_list('')
    ['hi_IN', 'en_GB']

    >>> if old_lc_all:
    ...     os.environ['LC_ALL'] = old_lc_all
    ... else:
    ...     # unneeded return value assigned to variable
    ...     _ = os.environ.pop('LC_ALL', None)

    If the input has more than the maximum number of allowed dictionaries
    the list is reduced to the maximum (currently 10):

    >>> dictionaries_str_to_list('en_AG,en_AU,en_BW,en_CA,en_DK,en_GB,en_HK,en_IE,en_IL,en_IN,en_NG,en_NZ,en_PH,en_SC,en_SG,en_US,en_ZA,en_ZM,en_ZW')
    ['en_AG', 'en_AU', 'en_BW', 'en_CA', 'en_DK', 'en_GB', 'en_HK', 'en_IE', 'en_IL', 'en_IN']

    If the input contains duplicates, the duplicates are removed:

    >>> dictionaries_str_to_list('en_US.UTF-8,en_US,en.UTF-8,en,C')
    ['en_US', 'en', 'en_US_POSIX']

    Non-standard spellings of the special dictionary ['None']
    are converted to the standard spelling:

    >>> dictionaries_str_to_list('nOnE')
    ['None']

    >>> dictionaries_str_to_list('a,en_GB')
    ['en_GB']
    >>> dictionaries_str_to_list('xxxx')
    ['en_US']
    '''
    # pylint: enable=line-too-long
    if dictionaries_str == '':
        return get_default_dictionaries(get_effective_lc_ctype())
    dictionaries: List[str] = []
    for dictionary in [re.sub(re.escape('none'), 'None', x.strip(),
                              flags=re.IGNORECASE)
                       for x in dictionaries_str.split(',') if x.strip()]:
        if dictionary != 'None':
            dictionary = locale_normalize(dictionary)
        if dictionary and dictionary not in dictionaries:
            dictionaries.append(dictionary)
    if len(dictionaries) > MAXIMUM_NUMBER_OF_DICTIONARIES:
        LOGGER.error(
            'More than the allowed maximum of %s dictionaries.\n'
            'Trying to use: %s\n'
            'Really using: %s\n',
            MAXIMUM_NUMBER_OF_DICTIONARIES,
            dictionaries,
            dictionaries[:MAXIMUM_NUMBER_OF_DICTIONARIES])
        dictionaries = dictionaries[:MAXIMUM_NUMBER_OF_DICTIONARIES]
    if dictionaries:
        return dictionaries
    return ['en_US']

HUNSPELL_DICTIONARIES = {
    # List of all locales/languages where hunspell dictionaries exist.
    # They do not necessary need to be installed on the system at the
    # moment.  But it is known that a hunspell dictionary for that
    # locale/language exists, so usually one just needs to install the
    # right package to make it available.
    'af_NA',
    'af_ZA',
    'ak_GH',
    'am_ET',
    'ar_AE',
    'ar_BH',
    'ar_DJ',
    'ar_DZ',
    'ar_EG',
    'ar_ER',
    'ar_IL',
    'ar_IN',
    'ar_IQ',
    'ar_JO',
    'ar_KM',
    'ar_KW',
    'ar_LB',
    'ar_LY',
    'ar_MA',
    'ar_MR',
    'ar_OM',
    'ar_PS',
    'ar_QA',
    'ar_SA',
    'ar_SD',
    'ar_SO',
    'ar_SY',
    'ar_TD',
    'ar_TN',
    'ar_YE',
    'as_IN',
    'ast_ES',
    'az_AZ',
    'be_BY',
    'ber_MA',
    'bg_BG',
    'bn_IN',
    'br_FR',
    'bs_BA',
    'ca_AD',
    'ca_ES',
    'ca_FR',
    'ca_IT',
    'cop_EG',
    'cs_CZ',
    'csb_PL',
    'cv_RU',
    'cy_GB',
    'da_DK',
    'de_AT',
    'de_BE',
    'de_CH',
    'de_DE',
    'de_LI',
    'de_LU',
    'dsb_DE',
    'el_CY',
    'el_GR',
    'en_AG',
    'en_AU',
    'en_BS',
    'en_BW',
    'en_BZ',
    'en_CA',
    'en_DK',
    'en_GB',
    'en_GH',
    'en_HK',
    'en_IE',
    'en_IN',
    'en_JM',
    'en_MW',
    'en_NA',
    'en_NG',
    'en_NZ',
    'en_PH',
    'en_SG',
    'en_TT',
    'en_US',
    'en_ZA',
    'en_ZM',
    'en_ZW',
    'eo',
    'es_AR',
    'es_BO',
    'es_CL',
    'es_CO',
    'es_CR',
    'es_CU',
    'es_DO',
    'es_EC',
    'es_ES',
    'es_GT',
    'es_HN',
    'es_MX',
    'es_NI',
    'es_PA',
    'es_PE',
    'es_PR',
    'es_PY',
    'es_SV',
    'es_US',
    'es_UY',
    'es_VE',
    'et_EE',
    'eu_ES',
    'fa_IR',
    'fil_PH',
    'fj',
    'fo_FO',
    'fr_BE',
    'fr_CA',
    'fr_CH',
    'fr_FR',
    'fr_LU',
    'fr_MC',
    'fur_IT',
    'fy_DE',
    'fy_NL',
    'ga_IE',
    'gd_GB',
    'gl_ES',
    'grc',
    'gu_IN',
    'gv_GB',
    'haw',
    'he_IL',
    'hi_IN',
    'hil_PH',
    'hr_HR',
    'hsb_DE',
    'ht_HT',
    'hu_HU',
    'hy_AM',
    'ia',
    'id_ID',
    'is_IS',
    'it_CH',
    'it_IT',
    'kk_KZ',
    'km_KH',
    'kn_IN',
    'ko_KR',
    'ku_SY',
    'ku_TR',
    'ky_KG',
    'la',
    'lb_LU',
    'ln_CD',
    'lt_LT',
    'lv_LV',
    'mai_IN',
    'mg',
    'mi_NZ',
    'mk_MK',
    'ml_IN',
    'mn_MN',
    'mos_BF',
    'mr_IN',
    'ms_BN',
    'ms_MY',
    'mt_MT',
    'nb_NO',
    'nds_DE',
    'nds_NL',
    'ne_IN',
    'ne_NP',
    'nl_AW',
    'nl_BE',
    'nl_NL',
    'nn_NO',
    'nr_ZA',
    'nso_ZA',
    'ny_MW',
    'oc_FR',
    'om_ET',
    'om_KE',
    'or_IN',
    'pa_IN',
    'pl_PL',
    'plt',
    'pt_AO',
    'pt_BR',
    'pt_PT',
    'qu_EC',
    'quh_BO',
    'ro_RO',
    'ru_RU',
    'ru_UA',
    'rw_RW',
    'sc_IT',
    'se_FI',
    'se_NO',
    'se_SE',
    'sh_ME',
    'sh_RS',
    'sh_YU',
    'shs_CA',
    'si_LK',
    'sk_SK',
    'sl_SI',
    'smj_NO',
    'smj_SE',
    'so_DJ',
    'so_ET',
    'so_KE',
    'so_SO',
    'sq_AL',
    'sr_ME',
    'sr_RS',
    'sr_YU',
    'ss_ZA',
    'st_ZA',
    'sv_FI',
    'sv_SE',
    'sw_KE',
    'sw_TZ',
    'ta_IN',
    'te_IN',
    'tet_ID',
    'tet_TL',
    'th_TH',
    'ti_ER',
    'ti_ET',
    'tk',
    'tl_PH',
    'tn_BW',
    'tn_ZA',
    'tpi_PG',
    'ts_ZA',
    'uk_UA',
    'ur_IN',
    'ur_PK',
    'uz_UZ',
    've_ZA',
    'vi_VN',
    'wa_BE',
    'xh_ZA',
    'yi_US',
    'zu',
}

CLDR_ANNOTATION_FILES = {
    # List of all locales/languages where CLDR annotation files
    # currently exist.  Not all of these are necessarily available at
    # the moment.  That depends what is currently installed on the
    # system.
    'af',
    'af_NA',
    'af_ZA',
    'agq',
    'agq_CM',
    'ak',
    'ak_GH',
    'am',
    'am_ET',
    'ar',
    'ar_001',
    'ar_AE',
    'ar_BH',
    'ar_DJ',
    'ar_DZ',
    'ar_EG',
    'ar_EH',
    'ar_ER',
    'ar_IL',
    'ar_IQ',
    'ar_JO',
    'ar_KM',
    'ar_KW',
    'ar_LB',
    'ar_LY',
    'ar_MA',
    'ar_MR',
    'ar_OM',
    'ar_PS',
    'ar_QA',
    'ar_SA',
    'ar_SD',
    'ar_SO',
    'ar_SS',
    'ar_SY',
    'ar_TD',
    'ar_TN',
    'ar_YE',
    'as',
    'as_IN',
    'asa',
    'asa_TZ',
    'ast',
    'ast_ES',
    'az',
    'az_Cyrl',
    'az_Cyrl_AZ',
    'az_Latn',
    'az_Latn_AZ',
    'bas',
    'bas_CM',
    'be',
    'be_BY',
    'bem',
    'bem_ZM',
    'bew',
    'bez',
    'bez_TZ',
    'bg',
    'bg_BG',
    'bgn',
    'blo',
    'bm',
    'bm_ML',
    'bn',
    'bn_BD',
    'bn_IN',
    'bo',
    'bo_CN',
    'bo_IN',
    'br',
    'br_FR',
    'brx',
    'brx_IN',
    'bs',
    'bs_Cyrl',
    'bs_Cyrl_BA',
    'bs_Latn',
    'bs_Latn_BA',
    'ca',
    'ca_AD',
    'ca_ES',
    'ca_ES_VALENCIA',
    'ca_FR',
    'ca_IT',
    'ccp',
    'ccp_BD',
    'ccp_IN',
    'ce',
    'ce_RU',
    'ceb',
    'cgg',
    'cgg_UG',
    'chr',
    'chr_US',
    'ckb',
    'ckb_IQ',
    'ckb_IR',
    'cs',
    'cs_CZ',
    'cu',
    'cu_RU',
    'cv',
    'cy',
    'cy_GB',
    'da',
    'da_DK',
    'da_GL',
    'dav',
    'dav_KE',
    'de',
    'de_AT',
    'de_BE',
    'de_CH',
    'de_DE',
    'de_IT',
    'de_LI',
    'de_LU',
    'dje',
    'dje_NE',
    'doi',
    'dsb',
    'dsb_DE',
    'dua',
    'dua_CM',
    'dyo',
    'dyo_SN',
    'dz',
    'dz_BT',
    'ebu',
    'ebu_KE',
    'ee',
    'ee_GH',
    'ee_TG',
    'el',
    'el_CY',
    'el_GR',
    'en',
    'en_001',
    'en_150',
    'en_AG',
    'en_AI',
    'en_AS',
    'en_AT',
    'en_AU',
    'en_BB',
    'en_BE',
    'en_BI',
    'en_BM',
    'en_BS',
    'en_BW',
    'en_BZ',
    'en_CA',
    'en_CC',
    'en_CH',
    'en_CK',
    'en_CM',
    'en_CX',
    'en_CY',
    'en_DE',
    'en_DG',
    'en_DK',
    'en_DM',
    'en_ER',
    'en_FI',
    'en_FJ',
    'en_FK',
    'en_FM',
    'en_GB',
    'en_GD',
    'en_GG',
    'en_GH',
    'en_GI',
    'en_GM',
    'en_GU',
    'en_GY',
    'en_HK',
    'en_IE',
    'en_IL',
    'en_IM',
    'en_IN',
    'en_IO',
    'en_JE',
    'en_JM',
    'en_KE',
    'en_KI',
    'en_KN',
    'en_KY',
    'en_LC',
    'en_LR',
    'en_LS',
    'en_MG',
    'en_MH',
    'en_MO',
    'en_MP',
    'en_MS',
    'en_MT',
    'en_MU',
    'en_MW',
    'en_MY',
    'en_NA',
    'en_NF',
    'en_NG',
    'en_NL',
    'en_NR',
    'en_NU',
    'en_NZ',
    'en_PG',
    'en_PH',
    'en_PK',
    'en_PN',
    'en_PR',
    'en_PW',
    'en_RW',
    'en_SB',
    'en_SC',
    'en_SD',
    'en_SE',
    'en_SG',
    'en_SH',
    'en_SI',
    'en_SL',
    'en_SS',
    'en_SX',
    'en_SZ',
    'en_TC',
    'en_TK',
    'en_TO',
    'en_TT',
    'en_TV',
    'en_TZ',
    'en_UG',
    'en_UM',
    'en_US',
    'en_US_POSIX',
    'en_VC',
    'en_VG',
    'en_VI',
    'en_VU',
    'en_WS',
    'en_ZA',
    'en_ZM',
    'en_ZW',
    'eo',
    'eo_001',
    'es',
    'es_419',
    'es_AR',
    'es_BO',
    'es_BR',
    'es_BZ',
    'es_CL',
    'es_CO',
    'es_CR',
    'es_CU',
    'es_DO',
    'es_EA',
    'es_EC',
    'es_ES',
    'es_GQ',
    'es_GT',
    'es_HN',
    'es_IC',
    'es_MX',
    'es_NI',
    'es_PA',
    'es_PE',
    'es_PH',
    'es_PR',
    'es_PY',
    'es_SV',
    'es_US',
    'es_UY',
    'es_VE',
    'et',
    'et_EE',
    'eu',
    'eu_ES',
    'ewo',
    'ewo_CM',
    'fa',
    'fa_AF',
    'fa_IR',
    'ff',
    'ff_Adlm',
    'fi',
    'fi_FI',
    'fil',
    'fil_PH',
    'fo',
    'fo_DK',
    'fo_FO',
    'fr',
    'fr_BE',
    'fr_BF',
    'fr_BI',
    'fr_BJ',
    'fr_BL',
    'fr_CA',
    'fr_CD',
    'fr_CF',
    'fr_CG',
    'fr_CH',
    'fr_CI',
    'fr_CM',
    'fr_DJ',
    'fr_DZ',
    'fr_FR',
    'fr_GA',
    'fr_GF',
    'fr_GN',
    'fr_GP',
    'fr_GQ',
    'fr_HT',
    'fr_KM',
    'fr_LU',
    'fr_MA',
    'fr_MC',
    'fr_MF',
    'fr_MG',
    'fr_ML',
    'fr_MQ',
    'fr_MR',
    'fr_MU',
    'fr_NC',
    'fr_NE',
    'fr_PF',
    'fr_PM',
    'fr_RE',
    'fr_RW',
    'fr_SC',
    'fr_SN',
    'fr_SY',
    'fr_TD',
    'fr_TG',
    'fr_TN',
    'fr_VU',
    'fr_WF',
    'fr_YT',
    'frr',
    'fur',
    'fur_IT',
    'fy',
    'fy_NL',
    'ga',
    'ga_IE',
    'gd',
    'gd_GB',
    'gl',
    'gl_ES',
    'gsw',
    'gsw_CH',
    'gsw_FR',
    'gsw_LI',
    'gu',
    'gu_IN',
    'guz',
    'guz_KE',
    'gv',
    'gv_IM',
    'ha',
    'ha_GH',
    'ha_NE',
    'ha_NG',
    'haw',
    'haw_US',
    'he',
    'he_IL',
    'hi',
    'hi_IN',
    'hi_Latn',
    'hr',
    'hr_BA',
    'hr_HR',
    'hsb',
    'hsb_DE',
    'hu',
    'hu_HU',
    'hy',
    'hy_AM',
    'id',
    'id_ID',
    'ig',
    'ig_NG',
    'ii',
    'ii_CN',
    'is',
    'is_IS',
    'it',
    'it_CH',
    'it_IT',
    'it_SM',
    'it_VA',
    'ja',
    'ja_JP',
    'jgo',
    'jgo_CM',
    'jmc',
    'jmc_TZ',
    'jv',
    'ka',
    'ka_GE',
    'kab',
    'kab_DZ',
    'kam',
    'kam_KE',
    'kde',
    'kde_TZ',
    'kea',
    'kea_CV',
    'khq',
    'khq_ML',
    'ki',
    'ki_KE',
    'kk',
    'kk_Arab',
    'kk_KZ',
    'kkj',
    'kkj_CM',
    'kl',
    'kl_GL',
    'kln',
    'kln_KE',
    'km',
    'km_KH',
    'kn',
    'kn_IN',
    'ko',
    'ko_KP',
    'ko_KR',
    'kok',
    'kok_IN',
    'ks',
    'ks_IN',
    'ksb',
    'ksb_TZ',
    'ksf',
    'ksf_CM',
    'ksh',
    'ksh_DE',
    'ku',
    'kw',
    'kw_GB',
    'ky',
    'ky_KG',
    'lag',
    'lag_TZ',
    'lb',
    'lb_LU',
    'lg',
    'lg_UG',
    'lij',
    'lkt',
    'lkt_US',
    'ln',
    'ln_AO',
    'ln_CD',
    'ln_CF',
    'ln_CG',
    'lo',
    'lo_LA',
    'lrc',
    'lrc_IQ',
    'lrc_IR',
    'lt',
    'lt_LT',
    'lu',
    'lu_CD',
    'luo',
    'luo_KE',
    'luy',
    'luy_KE',
    'lv',
    'lv_LV',
    'mai',
    'mas',
    'mas_KE',
    'mas_TZ',
    'mer',
    'mer_KE',
    'mfe',
    'mfe_MU',
    'mg',
    'mg_MG',
    'mgh',
    'mgh_MZ',
    'mgo',
    'mgo_CM',
    'mi',
    'mk',
    'mk_MK',
    'ml',
    'ml_IN',
    'mn',
    'mn_MN',
    'mni',
    'mr',
    'mr_IN',
    'ms',
    'ms_BN',
    'ms_MY',
    'ms_SG',
    'mt',
    'mt_MT',
    'mua',
    'mua_CM',
    'my',
    'my_MM',
    'mzn',
    'mzn_IR',
    'naq',
    'naq_NA',
    'nb',
    'nb_NO',
    'nb_SJ',
    'nd',
    'nd_ZW',
    'nds',
    'nds_DE',
    'nds_NL',
    'ne',
    'ne_IN',
    'ne_NP',
    'nl',
    'nl_AW',
    'nl_BE',
    'nl_BQ',
    'nl_CW',
    'nl_NL',
    'nl_SR',
    'nl_SX',
    'nmg',
    'nmg_CM',
    'nn',
    'nn_NO',
    'nnh',
    'nnh_CM',
    'no',
    'no_NO',
    'nso',
    'nus',
    'nus_SS',
    'nyn',
    'nyn_UG',
    'oc',
    'om',
    'om_ET',
    'om_KE',
    'or',
    'or_IN',
    'os',
    'os_GE',
    'os_RU',
    'pa',
    'pa_Arab',
    'pa_Arab_PK',
    'pa_Guru',
    'pa_Guru_IN',
    'pap',
    'pcm',
    'pl',
    'pl_PL',
    'prg',
    'prg_001',
    'ps',
    'ps_AF',
    'pt',
    'pt_AO',
    'pt_BR',
    'pt_CH',
    'pt_CV',
    'pt_GQ',
    'pt_GW',
    'pt_LU',
    'pt_MO',
    'pt_MZ',
    'pt_PT',
    'pt_ST',
    'pt_TL',
    'qu',
    'qu_BO',
    'qu_EC',
    'qu_PE',
    'quc',
    'rhg',
    'rm',
    'rm_CH',
    'rn',
    'rn_BI',
    'ro',
    'ro_MD',
    'ro_RO',
    'rof',
    'rof_TZ',
    'root',
    'ru',
    'ru_BY',
    'ru_KG',
    'ru_KZ',
    'ru_MD',
    'ru_RU',
    'ru_UA',
    'rw',
    'rw_RW',
    'rwk',
    'rwk_TZ',
    'sa',
    'sah',
    'sah_RU',
    'saq',
    'saq_KE',
    'sat',
    'sbp',
    'sbp_TZ',
    'sc',
    'sd',
    'sd_PK',
    'se',
    'se_FI',
    'se_NO',
    'se_SE',
    'seh',
    'seh_MZ',
    'ses',
    'ses_ML',
    'sg',
    'sg_CF',
    'shi',
    'shi_Latn',
    'shi_Latn_MA',
    'shi_Tfng',
    'shi_Tfng_MA',
    'si',
    'si_LK',
    'sk',
    'sk_SK',
    'sl',
    'sl_SI',
    'smn',
    'smn_FI',
    'sn',
    'sn_ZW',
    'so',
    'so_DJ',
    'so_ET',
    'so_KE',
    'so_SO',
    'sq',
    'sq_AL',
    'sq_MK',
    'sq_XK',
    'sr',
    'sr_Cyrl',
    'sr_Cyrl_BA',
    'sr_Cyrl_ME',
    'sr_Cyrl_RS',
    'sr_Cyrl_XK',
    'sr_Latn',
    'sr_Latn_BA',
    'sr_Latn_ME',
    'sr_Latn_RS',
    'sr_Latn_XK',
    'su',
    'sv',
    'sv_AX',
    'sv_FI',
    'sv_SE',
    'sw',
    'sw_CD',
    'sw_KE',
    'sw_TZ',
    'sw_UG',
    'ta',
    'ta_IN',
    'ta_LK',
    'ta_MY',
    'ta_SG',
    'te',
    'te_IN',
    'teo',
    'teo_KE',
    'teo_UG',
    'tg',
    'tg_TJ',
    'th',
    'th_TH',
    'ti',
    'ti_ER',
    'ti_ET',
    'tk',
    'tk_TM',
    'tn',
    'to',
    'to_TO',
    'tr',
    'tr_CY',
    'tr_TR',
    'tt',
    'tt_RU',
    'twq',
    'twq_NE',
    'tzm',
    'tzm_MA',
    'ug',
    'ug_CN',
    'uk',
    'uk_UA',
    'ur',
    'ur_IN',
    'ur_PK',
    'uz',
    'uz_Arab',
    'uz_Arab_AF',
    'uz_Cyrl',
    'uz_Cyrl_UZ',
    'uz_Latn',
    'uz_Latn_UZ',
    'vai',
    'vai_Latn',
    'vai_Latn_LR',
    'vai_Vaii',
    'vai_Vaii_LR',
    'vec',
    'vi',
    'vi_VN',
    'vo',
    'vo_001',
    'vun',
    'vun_TZ',
    'wae',
    'wae_CH',
    'wo',
    'wo_SN',
    'xh',
    'xog',
    'xog_UG',
    'yav',
    'yav_CM',
    'yi',
    'yi_001',
    'yo',
    'yo_BJ',
    'yo_NG',
    'yue',
    'yue_Hans',
    'yue_Hans_CN',
    'yue_Hant',
    'yue_Hant_HK',
    'zgh',
    'zgh_MA',
    'zh',
    'zh_Hans',
    'zh_Hans_CN',
    'zh_Hans_HK',
    'zh_Hans_MO',
    'zh_Hans_SG',
    'zh_Hant',
    'zh_Hant_HK',
    'zh_Hant_MO',
    'zh_Hant_TW',
    'zu',
    'zu_ZA',
}

GOOGLE_SPEECH_TO_TEXT_LANGUAGES = {
    # List of languages supported by the Google Cloud Speech-to-Text
    # speech recognition engine.
    #
    # https://cloud.google.com/speech-to-text/docs/languages
    #
    # The original list above uses identifiers in BCP-47 format.
    #
    # In the list below, “-” is replaced “_” to be able to merge
    # the list better with the lists of hunspell dictionaries and
    # cldr annotation files.
    'af_ZA',
    'am_ET',
    'hy_AM',
    'az_AZ',
    'id_ID',
    'ms_MY',
    'bn_BD',
    'bn_IN',
    'ca_ES',
    'cs_CZ',
    'da_DK',
    'de_DE',
    'en_AU',
    'en_CA',
    'en_GH',
    'en_GB',
    'en_IN',
    'en_IE',
    'en_KE',
    'en_NZ',
    'en_NG',
    'en_PH',
    'en_ZA',
    'en_TZ',
    'en_US',
    'es_AR',
    'es_BO',
    'es_CL',
    'es_CO',
    'es_CR',
    'es_EC',
    'es_SV',
    'es_ES',
    'es_US',
    'es_GT',
    'es_HN',
    'es_MX',
    'es_NI',
    'es_PA',
    'es_PY',
    'es_PE',
    'es_PR',
    'es_DO',
    'es_UY',
    'es_VE',
    'eu_ES',
    'fil_PH',
    'fr_CA',
    'fr_FR',
    'gl_ES',
    'ka_GE',
    'gu_IN',
    'hr_HR',
    'zu_ZA',
    'is_IS',
    'it_IT',
    'jv_ID',
    'kn_IN',
    'km_KH',
    'lo_LA',
    'lv_LV',
    'lt_LT',
    'hu_HU',
    'ml_IN',
    'mr_IN',
    'nl_NL',
    'ne_NP',
    'nb_NO',
    'pl_PL',
    'pt_BR',
    'pt_PT',
    'ro_RO',
    'si_LK',
    'sk_SK',
    'sl_SI',
    'su_ID',
    'sw_TZ',
    'sw_KE',
    'fi_FI',
    'sv_SE',
    'ta_IN',
    'ta_SG',
    'ta_LK',
    'ta_MY',
    'te_IN',
    'vi_VN',
    'tr_TR',
    'ur_PK',
    'ur_IN',
    'el_GR',
    'bg_BG',
    'ru_RU',
    'sr_RS',
    'uk_UA',
    'he_IL',
    'ar_IL',
    'ar_JO',
    'ar_AE',
    'ar_BH',
    'ar_DZ',
    'ar_SA',
    'ar_IQ',
    'ar_KW',
    'ar_MA',
    'ar_TN',
    'ar_OM',
    'ar_PS',
    'ar_QA',
    'ar_LB',
    'ar_EG',
    'fa_IR',
    'hi_IN',
    'th_TH',
    'ko_KR',
    'zh_TW',
    'yue_Hant_HK',
    'ja_JP',
    'zh_HK',
    'zh',
}

SUPPORTED_DICTIONARIES = set()
SUPPORTED_DICTIONARIES.update(HUNSPELL_DICTIONARIES)
SUPPORTED_DICTIONARIES.update(CLDR_ANNOTATION_FILES)
SUPPORTED_DICTIONARIES.update(GOOGLE_SPEECH_TO_TEXT_LANGUAGES)

FLAGS = {
    'None': '🏴', # Fallback if nothing else can be found
    'root': '🌐',
    '001': '🌐', # World
    '150': '🌍', # Europe
    '419': '🌎', # South America
    'A': '🇦',
    'B': '🇧',
    'C': '🇨',
    'D': '🇩',
    'E': '🇪',
    'F': '🇫',
    'G': '🇬',
    'H': '🇭',
    'I': '🇮',
    'J': '🇯',
    'K': '🇰',
    'L': '🇱',
    'M': '🇲',
    'N': '🇳',
    'O': '🇴',
    'P': '🇵',
    'Q': '🇶',
    'R': '🇷',
    'S': '🇸',
    'T': '🇹',
    'U': '🇺',
    'V': '🇻',
    'W': '🇼',
    'X': '🇽',
    'Y': '🇾',
    'Z': '🇿',
    'af': '🇿🇦',
    'agq': '🇨🇲',
    'ak': '🇬🇭',
    'am': '🇪🇹',
    'ar': '🌍',
    'as': '🌏',
    'asa': '🌍',
    'ast': '🌍',
    'az': '🌍',
    'bas': '🌍',
    'be': '🌍',
    'bem': '🌍',
    'bez': '🌍',
    'bg': '🌍',
    'bgn': '🇦🇫🇮🇷🇵🇰',
    'bm': '🌍',
    'bn': '🌏',
    'bo': '🌏',
    'br': '🌍',
    'brx': '🌏',
    'bs': '🌍',
    'ca': '🌍',
    'ccp': '🌏',
    'ce': '🌍',
    'ceb': '🇵🇭',
    'cgg': '🌍',
    'chr': '🌎',
    'ckb': '🌍',
    'cop': '🌍',
    'cs': '🌍',
    'cu': '🌍',
    'cy': '🌍',
    'cy_GB': '🏴󠁧󠁢󠁷󠁬󠁳󠁿',
    'da': '🌍',
    'dav': '🌍',
    'de': '🌍',
    'dje': '🌍',
    'dsb': '🌍',
    'doi': '🇮🇳',
    'dua': '🌍',
    'dyo': '🌍',
    'dz': '🌏',
    'ebu': '🌍',
    'ee': '🌍',
    'el': '🌍',
    'en': '🌍',
    'eo': '🌍',
    'es': '🌍',
    'et': '🌍',
    'eu': '🌍',
    'ewo': '🌍',
    'fa': '🌍',
    'ff': '🌍',
    'fi': '🌍',
    'fil': '🌏',
    'fj': '🇫🇯',
    'fo': '🌍',
    'fr': '🌍',
    'fur': '🌍',
    'fy': '🌍',
    'ga': '🌍',
    'gd': '🌍',
    'gd_GB': '🏴󠁧󠁢󠁳󠁣󠁴󠁿',
    'gl': '🌍',
    'grc': '🇬🇷',
    'gsw': '🌍',
    'gu': '🌏',
    'guz': '🌍',
    'gv': '🌍',
    'ha': '🌍',
    'haw': '🌎',
    'he': '🌍',
    'hi': '🌏',
    'hr': '🌍',
    'hsb': '🌍',
    'ht': '🌎',
    'hu': '🌍',
    'hy': '🌍',
    'ia': '🌍',
    'id': '🌏',
    'ig': '🌍',
    'ii': '🌏',
    'is': '🌍',
    'it': '🌍',
    'ja': '🌏',
    'jgo': '🌍',
    'jmc': '🌍',
    'jv': '🌏',
    'jv_ID': '🌍',
    'ka': '🌍',
    'kab': '🌍',
    'kam': '🌍',
    'kde': '🌍',
    'kea': '🌍',
    'khq': '🌍',
    'ki': '🌍',
    'kk': '🌍',
    'kkj': '🌍',
    'kl': '🌍',
    'kln': '🌍',
    'km': '🌏',
    'kn': '🌏',
    'ko': '🌏',
    'kok': '🌏',
    'ks': '🌏',
    'ksb': '🌍',
    'ksf': '🌍',
    'ksh': '🌍',
    'ku': '🌍',
    'kw': '🌍',
    'ky': '🌍',
    'la': '🇻🇦',
    'lag': '🌍',
    'lb': '🌍',
    'lg': '🌍',
    'lkt': '🌎',
    'ln': '🌍',
    'lo': '🌏',
    'lrc': '🌍',
    'lt': '🌍',
    'lu': '🌍',
    'luo': '🌍',
    'luo_KE': '',
    'luy': '🌍',
    'lv': '🌍',
    'mai': '🌍',
    'mas': '🌍',
    'mer': '🌍',
    'mfe': '🌍',
    'mg': '🌍',
    'mgh': '🌍',
    'mgo': '🌍',
    'mi': '🌏',
    'mk': '🌍',
    'ml': '🌏',
    'mn': '🌏',
    'mni': '🇮🇳🇧🇩🇲🇲',
    'mos': '🌍',
    'mr': '🌏',
    'ms': '🌏',
    'mt': '🌍',
    'mua': '🌍',
    'my': '🌏',
    'mzn': '🌍',
    'naq': '🌍',
    'nb': '🌍',
    'nd': '🌍',
    'nds': '🌍',
    'ne': '🌏',
    'nl': '🌍',
    'nmg': '🌍',
    'nn': '🌍',
    'nnh': '🌍',
    'no': '🇳🇴',
    'nr': '🌍',
    'nso': '🌍',
    'nus': '🌍',
    'ny': '🌍',
    'nyn': '🌍',
    'oc': '🌍',
    'om': '🌍',
    'or': '🌏',
    'os': '🌍',
    'pa': '🌍',
    'pcm': '🇳🇬',
    'pl': '🌍',
    'plt': '🌍',
    'prg': '🌍',
    'ps': '🌍',
    'pt': '🌍',
    'qu': '🌎',
    'quh': '🌎',
    'rm': '🌍',
    'rn': '🌍',
    'ro': '🌍',
    'rof': '🌍',
    'ru': '🌍',
    'rw': '🌍',
    'rwk': '🌍',
    'sa': '🇮🇳',
    'sah': '🌍',
    'saq': '🌍',
    'sat': '🇮🇳',
    'sbp': '🌍',
    'sc': '🇮🇹',
    'sd': '🌍',
    'se': '🌍',
    'seh': '🌍',
    'ses': '🌍',
    'sg': '🌍',
    'sh': '🌍',
    'shi': '🌍',
    'shs': '🌎',
    'si': '🌍',
    'sk': '🌍',
    'sl': '🌍',
    'smj': '🌍',
    'smn': '🌍',
    'sn': '🌍',
    'so': '🌍',
    'sq': '🌍',
    'sr': '🌍',
    'ss': '🌍',
    'st': '🌍',
    'su': '🌏',
    'sv': '🌍',
    'sw': '🌍',
    'ta': '🌏',
    'te': '🌏',
    'teo': '🌍',
    'tet': '🌏',
    'tg': '🌍',
    'th': '🌏',
    'ti': '🌍',
    'tk': '🌍',
    'tl': '🌏',
    'tn': '🌍',
    'to': '🌏',
    'tpi': '🌏',
    'tr': '🌍',
    'ts': '🌍',
    'tt': '🌍',
    'twq': '🌍',
    'tzm': '🌍',
    'ug': '🌏',
    'uk': '🌍',
    'ur': '🌏',
    'uz': '🌍',
    'vai': '🌍',
    've': '🌍',
    'vi': '🌏',
    'vo': '🌍',
    'vun': '🌍',
    'wa': '🌍',
    'wae': '🌍',
    'wo': '🌍',
    'xh': '🌍',
    'xog': '🌍',
    'yav': '🌍',
    'yi': '🌍',
    'yo': '🌍',
    'yue': '🌏',
    'yue_Hans': '🌏',
    'yue_Hant': '🌏',
    'zgh': '🌍',
    'zh': '🌏',
    'zh_Hans': '🌏',
    'zh_Hant': '🌏',
    'zu': '🌍',
}

def get_flag(lookup_text: str) -> str:
    '''Lookup a flag emoji for a lookup string or a reaonable fallback
    if there is no flag.

    Examples:

    >>> get_flag('en_GB')
    '🇬🇧'
    >>> get_flag('GB')
    '🇬🇧'

    There is no Yugoslavia anymore, nevertheless returning '🇾🇺' is
    fine, a white flag with question mark is shown in the “Noto Color
    Emoji” font.

    >>> get_flag('YU')
    '🇾🇺'
    >>> get_flag('en_001')
    '🌐'
    >>> get_flag('001')
    '🌐'
    >>> get_flag('ca_Latn_ES_VALENCIA')
    '🇪🇸'
    >>> get_flag('af')
    '🇿🇦'
    >>> get_flag('zu')
    '🌍'
    '''
    if lookup_text in FLAGS:
        return FLAGS[lookup_text]
    if (len(lookup_text) == 2
        and lookup_text.isalpha()
        and lookup_text.isupper()
        and lookup_text[0] in FLAGS
        and lookup_text[1] in FLAGS):
        return FLAGS[lookup_text[0]] + FLAGS[lookup_text[1]]
    if lookup_text.isdigit() and len(lookup_text) == 3:
        return FLAGS.get(lookup_text, FLAGS['None'])
    locale = parse_locale(lookup_text) # pylint: disable=redefined-outer-name
    if (len(locale.territory) == 2
        and locale.territory.isalpha()
        and locale.territory.isupper()
        and locale.territory[0] in FLAGS
        and locale.territory[1] in FLAGS):
        return FLAGS[locale.territory[0]] + FLAGS[locale.territory[1]]
    if locale.territory.isdigit() and len(locale.territory) == 3:
        return FLAGS.get(locale.territory, FLAGS['None'])
    if locale.language and locale.language in FLAGS:
        return FLAGS[locale.language]
    return FLAGS['None']

def get_flags(dictionaries: List[str]) -> Dict[str, str]:
    # pylint: disable=line-too-long
    '''
    Examples:

    >>> get_flags(['de_DE', 'fr_FR', 'eo'])
    {'de_DE': '🇩🇪', 'fr_FR': '🇫🇷', 'eo': '🌍'}
    >>> get_flags(['fr_FR', 'de_DE', 'fy_DE', 'eo', 'de', '150'])
    {'fr_FR': '🇫🇷fr_FR', 'de_DE': '🇩🇪de_DE', 'fy_DE': '🇩🇪fy_DE', 'eo': '🌍eo', 'de': '🌍de', '150': '🌍150'}
    '''
    # pylint: enable=line-too-long
    flags: Dict[str, str] = {}
    flags_seen: Set[str] = set()
    duplicate_flags = False
    for dictionary in dictionaries:
        new_flag = get_flag(dictionary)
        flags[dictionary] = new_flag
        if new_flag in flags_seen:
            duplicate_flags = True
        flags_seen.add(new_flag)
    if duplicate_flags:
        for key, flag in flags.items():
            if not flag.endswith(key):
                flags[key] += key
    return flags

def get_effective_lc_ctype() -> str:
    '''Returns the effective value of LC_CTYPE'''
    if 'LC_ALL' in os.environ:
        return os.environ['LC_ALL']
    if 'LC_CTYPE' in os.environ:
        return os.environ['LC_CTYPE']
    if 'LANG' in os.environ:
        return os.environ['LANG']
    return 'C'

def get_effective_lc_messages() -> str:
    '''Returns the effective value of LC_MESSAGES'''
    if 'LC_ALL' in os.environ:
        return os.environ['LC_ALL']
    if 'LC_MESSAGES' in os.environ:
        return os.environ['LC_MESSAGES']
    if 'LANG' in os.environ:
        return os.environ['LANG']
    return 'C'

@functools.lru_cache(maxsize=None)
def detect_terminal(input_purpose: int, im_client: str) -> bool:
    '''Detect whether the focus is on a terminal

    Checks input purpose first and if that is not set to TERMINAL,
    checks the program name in im_client to guess whether it is
    a terminal.
    '''
    if input_purpose in [InputPurpose.TERMINAL.value]:
        return True
    if not im_client:
        return False
    terminal_regexps = [
        '^xim:xterm:',
        '^QIBusInputContext:konsole:',
        '^xim:rxvt:',
        '^xim:urxvt:',
    ]
    for regexp in terminal_regexps:
        if re.compile(regexp).search(im_client):
            return True
    return False

# For the ICU/CLDR locale pattern see: http://userguide.icu-project.org/locale
# (We ignore the variant code here)
_cldr_locale_pattern = re.compile(
    # language must be 2 or 3 lower case letters:
    '^(?P<language>[a-z]{2,3}'
    # language is only valid if
    +'(?=$|@' # locale string ends here or only options follow
    +'|_[A-Z][a-z]{3}(?=$|@|_[A-Z0-9]{2,3}(?=$|@))' # valid script follows
    +'|_[A-Z0-9]{2,3}(?=$|@)' # valid territory follows
    +'))'
    # script must be 1 upper case letter followed by
    # 3 lower case letters:
    +'(?:_(?P<script>[A-Z][a-z]{3})'
    # script is only valid if
    +'(?=$|@' # locale string ends here or only options follow
    +'|_[A-Z0-9]{2,3}(?=$|@)' # valid territory follows
    +')){0,1}'
    # territory must be 2 upper case letters or 3 digits:
    +'(?:_(?P<territory>[A-Z0-9]{2,3})'
    # territory is only valid if
    +'(?=$|@' # locale string ends here or only options follow
    +')){0,1}')

# http://www.unicode.org/iso15924/iso15924-codes.html
_glibc_script_ids = {
    'latin': 'Latn',
    # Tatar, tt_RU.UTF-8@iqtelif
    # see: http://en.wikipedia.org/wiki/User:Ultranet/%C4%B0QTElif
    'iqtelif': 'Latn',
    'cyrillic': 'Cyrl',
    'devanagari': 'Deva',
}

Locale = collections.namedtuple(
    'Locale',
    ['language', 'script', 'territory', 'variant', 'encoding'])

def parse_locale(localeId: str) -> Locale: # pylint: disable=invalid-name
    # pylint: disable=line-too-long
    '''
    Parses a locale name in glibc or CLDR format and returns
    language, script, territory, variant, and encoding

    :param localeId: The name of the locale
    :return: The parts of the locale:
             language, script, territory, variant, encoding
    :rtype: A namedtuple of strings
            Locale(language=string,
                   script=string,
                   territory=string,
                   variant=string,
                   encoding=string)

    It replaces glibc names for scripts like “latin”
    with the iso-15924 script names like “Latn”.
    I.e. these inputs all give the same result:

        “sr_latin_RS”
        “sr_Latn_RS”
        “sr_RS@latin”
        “sr_RS@Latn”

    Examples:

    >>> parse_locale('de_DE')
    Locale(language='de', script='', territory='DE', variant='', encoding='')

    >>> parse_locale('de_DE.UTF-8')
    Locale(language='de', script='', territory='DE', variant='', encoding='UTF-8')

    >>> parse_locale('de_DE.utf8')
    Locale(language='de', script='', territory='DE', variant='', encoding='utf8')

    >>> parse_locale('de_DE@euro')
    Locale(language='de', script='', territory='DE', variant='EURO', encoding='')

    >>> parse_locale('de_DE.ISO-8859-15')
    Locale(language='de', script='', territory='DE', variant='', encoding='ISO-8859-15')

    >>> parse_locale('de_DE.ISO-8859-15@euro')
    Locale(language='de', script='', territory='DE', variant='EURO', encoding='ISO-8859-15')

    >>> parse_locale('de_DE.iso885915@euro')
    Locale(language='de', script='', territory='DE', variant='EURO', encoding='iso885915')

    >>> parse_locale('gez_ER.UTF-8@abegede')
    Locale(language='gez', script='', territory='ER', variant='ABEGEDE', encoding='UTF-8')

    >>> parse_locale('ar_ER.UTF-8@saaho')
    Locale(language='ar', script='', territory='ER', variant='SAAHO', encoding='UTF-8')

    >>> parse_locale('zh_Hant_TW')
    Locale(language='zh', script='Hant', territory='TW', variant='', encoding='')

    >>> parse_locale('zh_TW')
    Locale(language='zh', script='', territory='TW', variant='', encoding='')

    >>> parse_locale('es_419')
    Locale(language='es', script='', territory='419', variant='', encoding='')

    >>> parse_locale('sr_latin_RS')
    Locale(language='sr', script='Latn', territory='RS', variant='', encoding='')

    >>> parse_locale('sr_Latn_RS')
    Locale(language='sr', script='Latn', territory='RS', variant='', encoding='')

    >>> parse_locale('sr_RS@latin')
    Locale(language='sr', script='Latn', territory='RS', variant='', encoding='')

    >>> parse_locale('sr_RS@Latn')
    Locale(language='sr', script='Latn', territory='RS', variant='', encoding='')

    >>> parse_locale('sr_RS.UTF-8@latin')
    Locale(language='sr', script='Latn', territory='RS', variant='', encoding='UTF-8')

    >>> parse_locale('ca_ES')
    Locale(language='ca', script='', territory='ES', variant='', encoding='')

    >>> parse_locale('ca_ES.UTF-8')
    Locale(language='ca', script='', territory='ES', variant='', encoding='UTF-8')

    >>> parse_locale('ca_ES_VALENCIA')
    Locale(language='ca', script='', territory='ES', variant='VALENCIA', encoding='')

    >>> parse_locale('ca_Latn_ES_VALENCIA')
    Locale(language='ca', script='Latn', territory='ES', variant='VALENCIA', encoding='')

    >>> parse_locale('ca_ES.UTF-8@valencia')
    Locale(language='ca', script='', territory='ES', variant='VALENCIA', encoding='UTF-8')

    >>> parse_locale('ca_ES@valencia')
    Locale(language='ca', script='', territory='ES', variant='VALENCIA', encoding='')

    >>> parse_locale('en_US_POSIX')
    Locale(language='en', script='', territory='US', variant='POSIX', encoding='')

    >>> parse_locale('POSIX')
    Locale(language='en', script='', territory='US', variant='POSIX', encoding='')

    >>> parse_locale('C')
    Locale(language='en', script='', territory='US', variant='POSIX', encoding='')

    >>> parse_locale('C.UTF-8')
    Locale(language='en', script='', territory='US', variant='POSIX', encoding='UTF-8')

    '''
    # pylint: enable=line-too-long
    language = ''
    script = ''
    territory = ''
    variant = ''
    encoding = ''
    if localeId:
        dot_index = localeId.find('.')
        at_index = localeId.find('@')
        if 0 <= dot_index < at_index:
            encoding  = localeId[dot_index + 1:at_index]
            localeId = localeId[:dot_index] + localeId[at_index:]
        elif dot_index >= 0:
            encoding = localeId[dot_index + 1:]
            localeId = localeId[:dot_index]
    if localeId:
        valencia_index = localeId.lower().find('@valencia')
        if valencia_index < 0:
            valencia_index = localeId.upper().find('_VALENCIA')
        if valencia_index >= 0:
            variant = 'VALENCIA'
            localeId = localeId[:valencia_index]
    if localeId:
        if localeId in ('C', 'POSIX', 'en_US_POSIX'):
            language = 'en'
            territory = 'US'
            variant = 'POSIX'
            localeId = ''
    if localeId:
        for key, script_id_iso in _glibc_script_ids.items():
            localeId = localeId.replace(key, script_id_iso)
            if localeId.endswith('@' + script_id_iso):
                script = script_id_iso
                localeId = localeId.replace('@' + script_id_iso, '')
    if localeId:
        at_index = localeId.find('@')
        if at_index >= 0:
            # If there is still an @ followed by something, it is not
            # a known script, otherwise it would have been parsed as a
            # script in the previous section. In that case it is a
            # variant of the locale.
            variant = localeId[at_index + 1:].upper()
            localeId = localeId[:at_index]
    if localeId:
        match = _cldr_locale_pattern.match(localeId)
        if match:
            language = match.group('language')
            if match.group('script'):
                script = match.group('script')
            if match.group('territory'):
                territory = match.group('territory')
        else:
            LOGGER.info("localeId contains invalid locale id=%s", localeId)
    return Locale(language=language,
                  script=script,
                  territory=territory,
                  variant=variant,
                  encoding=encoding)

def locale_normalize(localeId: str) -> str: # pylint: disable=invalid-name
    '''
    Returns a normalized version of the locale id string
    *without* the encoding.

    :param localeId: The original locale id string

    Examples:

    >>> locale_normalize('ks_IN@devanagari')
    'ks_Deva_IN'
    >>> locale_normalize('ks_IN.UTF-8@devanagari')
    'ks_Deva_IN'
    >>> locale_normalize('tt_RU.UTF-8@iqtelif')
    'tt_Latn_RU'
    >>> locale_normalize('de_DE.ISO-8859-15@euro')
    'de_DE_EURO'
    >>> locale_normalize('gez_ER.UTF-8@abegede')
    'gez_ER_ABEGEDE'
    >>> locale_normalize('ar_ER.UTF-8@saaho')
    'ar_ER_SAAHO'
    >>> locale_normalize('es_419')
    'es_419'
    >>> locale_normalize('sr_RS.UTF-8@latin')
    'sr_Latn_RS'
    >>> locale_normalize('ca_ES.UTF-8@valencia')
    'ca_ES_VALENCIA'
    >>> locale_normalize('C.UTF-8')
    'en_US_POSIX'
    >>> locale_normalize('xxx')
    'xxx'
    >>> locale_normalize('')
    ''

    An empty string is returned if the input cannot be
    a valid locale id:

    >>> locale_normalize('x')
    ''
    >>> locale_normalize('xxxx')
    ''
    '''
    locale = parse_locale(localeId) # pylint: disable=redefined-outer-name
    normalized_locale_id: str = locale.language
    if locale.script:
        normalized_locale_id += '_' + locale.script
    if locale.territory:
        normalized_locale_id += '_' + locale.territory
    if locale.variant:
        normalized_locale_id += '_' + locale.variant
    return normalized_locale_id

SPANISH_419_LOCALES = (
    'es_AR', 'es_MX', 'es_BO', 'es_CL', 'es_CO', 'es_CR',
    'es_CU', 'es_DO', 'es_EC', 'es_GT', 'es_HN', 'es_NI',
    'es_PA', 'es_PE', 'es_PR', 'es_PY', 'es_SV', 'es_US',
    'es_UY', 'es_VE',)

def expand_languages(languages: Iterable[str]) -> List[str]:
    # pylint: disable=line-too-long
    '''Expands the given list of languages by including fallbacks.

    Returns a possibly longer list of languages by adding
    aliases and fallbacks.

    :param languages: A list of languages (or locale names)

    Examples:

    >>> expand_languages(['es_MX', 'es_ES', 'ja_JP'])
    ['es_MX', 'es_419', 'es', 'es_ES', 'es', 'ja_JP', 'ja', 'en']

    >>> expand_languages(['zh_Hant', 'zh_CN', 'zh_TW', 'zh_SG', 'zh_HK', 'zh_MO'])
    ['zh_Hant', 'zh_CN', 'zh', 'zh_TW', 'zh_Hant', 'zh_SG', 'zh', 'zh_HK', 'zh_Hant', 'zh_MO', 'zh_Hant', 'en']

    >>> expand_languages(['ks_Deva_IN'])
    ['ks_Deva_IN', 'ks_Deva', 'ks', 'en']

    >>> expand_languages(['ca_ES_VALENCIA'])
    ['ca_ES_VALENCIA', 'ca_ES', 'ca', 'en']

    >>> expand_languages(['ca_Latn_ES_VALENCIA'])
    ['ca_Latn_ES_VALENCIA', 'ca_Latn_ES', 'ca_Latn', 'ca', 'en']

    >>> expand_languages(['nb_NO'])
    ['nb_NO', 'no', 'nb', 'en']

    >>> expand_languages(['nn_NO'])
    ['nn_NO', 'nn', 'en']

    >>> expand_languages(['no_NO'])
    ['no_NO', 'nb', 'no', 'en']

    >>> expand_languages(['en_GB', 'en'])
    ['en_GB', 'en_001', 'en', 'en', 'en_001']

    >>> expand_languages(['sr_Latn_RS'])
    ['sr_Latn_RS', 'sr_Latn', 'sr', 'en']

    >>> expand_languages(['ca_ES_VALENCIA'])
    ['ca_ES_VALENCIA', 'ca_ES', 'ca', 'en']

    >>> expand_languages(['en_US_POSIX'])
    ['en_US_POSIX', 'en_001', 'en_US', 'en']

    >>> expand_languages([])
    ['en']
    '''
    # pylint: enable=line-too-long
    expanded_languages = []
    for language in languages:
        expanded_languages.append(language)
        if language in SPANISH_419_LOCALES:
            expanded_languages.append('es_419')
        if language in ('zh_TW', 'zh_HK', 'zh_MO'):
            expanded_languages.append('zh_Hant')
        if language[:2] == 'en':
            expanded_languages.append('en_001')
        if language[:2] == 'nb':
            expanded_languages.append('no')
        if language[:2] == 'no':
            expanded_languages.append('nb')
        language_parts = language.split('_')
        if (language not in ('zh_TW', 'zh_HK', 'zh_MO', 'zh_Hant')
                and language_parts[:1] != [language]):
            while len(language_parts) > 1:
                expanded_languages += ['_'.join(language_parts[:-1])]
                language_parts.pop()
    if 'en' not in expanded_languages:
        expanded_languages.append('en')
    return expanded_languages

def locale_text_to_match(localeId: str) -> str: # pylint: disable=invalid-name
    # pylint: disable=line-too-long
    '''
    Returns a text which can be matched against typed user input
    to check whether the user might be looking for this locale

    :param localeId: The name of the locale

    Examples:

    >>> old_lc_all = os.environ.get('LC_ALL')
    >>> os.environ['LC_ALL'] = 'de_DE.UTF-8'

    When using langtable:

    >> locale_text_to_match('fr_FR')
    'fr_fr franzosisch (frankreich) francais (france) french (france)'

    >> locale_text_to_match('t')
    't others, miscellaneous, various, diverse weiteres, sonstiges, verschiedenes, anderes, ubriges'

    When using pycountry

    >> locale_text_to_match('fr_FR')
    'fr_fr french franzosisch francais france frankreich france'

    >>> if old_lc_all:
    ...     os.environ['LC_ALL'] = old_lc_all
    ... else:
    ...     # unneeded return value assigned to variable
    ...     _ = os.environ.pop('LC_ALL', None)
    '''
    # pylint: enable=line-too-long
    effective_lc_messages = get_effective_lc_messages()
    text_to_match = localeId.replace(' ', '')
    if localeId == 't':
        text_to_match += ' ' + (
            'Others, Miscellaneous, Various, Diverse'
            # Translators: This is a string is never displayed
            # anywhere, it is only for searching.
            #
            # It should contain words which could mean
            # something like “Other” or “Various”.  When
            # something is entered into search field to find
            # input methods, and this something matches
            # anything in the original English string *or* its
            # translation, all m17n input methods which are
            # not for a single language but for multiple
            # languages or for some other special purpose are
            # listed. For example input methods like these:
            #
            # • t-latn-pre:  Prefix input method for
            #                Latin based languages
            # • t-latn-post: Postfix input method for
            #                Latin based languages
            # • t-rfc1345:   Generic input method using
            #                RFC1345 mnemonics.
            # • t-unicode:   For Unicode characters by typing
            #                character code
            #
            # The translation does not need to have the same
            # number of words as the original English, any
            # number of words is fine. It doesn’t matter if the words
            # are seperated by punctuation or white space.
            + ' ' + _('Others, Miscellaneous, Various, Diverse')
            )
    elif IMPORT_LANGTABLE_SUCCESSFUL:
        query_languages = [effective_lc_messages, localeId, 'en']
        for query_language in query_languages:
            if query_language:
                text_to_match += ' ' + langtable.language_name(
                    languageId=localeId,
                    languageIdQuery=query_language)
    elif IMPORT_PYCOUNTRY_SUCCESSFUL:
        locale = parse_locale(localeId) # pylint: disable=redefined-outer-name
        if locale.language:
            language = pycountry.languages.get(alpha_2=locale.language)
            if not language:
                language = pycountry.languages.get(alpha_3=locale.language)
            if not language:
                language = pycountry.languages.get(
                    bibliographic=locale.language)
            if language and language.name:
                text_to_match += ' ' + language.name
                gtrans = gettext.translation(
                    'iso_639-3', fallback=True,
                    languages=[effective_lc_messages])
                text_to_match += ' ' + gtrans.gettext(language.name)
                gtrans = gettext.translation(
                    'iso_639-3', fallback=True,
                    languages=[locale.language])
                text_to_match += ' ' + gtrans.gettext(language.name)
        if locale.territory:
            country = pycountry.countries.get(alpha_2=locale.territory)
            if not country:
                country = pycountry.countries.get(alpha_3=locale.territory)
            if country and country.name:
                text_to_match += ' ' + country.name
                gtrans = gettext.translation(
                    'iso_3166', fallback=True,
                    languages=[effective_lc_messages])
                text_to_match += ' ' + gtrans.gettext(country.name)
                gtrans = gettext.translation(
                    'iso_3166', fallback=True,
                    languages=[locale.language])
                text_to_match += ' ' + gtrans.gettext(country.name)
    return remove_accents(text_to_match).lower()

def locale_language_description( # pylint: disable=invalid-name
        localeId: str) -> str:
    '''
    Returns a description of the language of the locale

    :param localeId: The name of the locale

    Examples:

    >>> old_lc_all = os.environ.get('LC_ALL')
    >>> os.environ['LC_ALL'] = 'de_DE_IN.UTF-8'

    >> locale_language_description('fr_FR')
    'Französisch (Frankreich)'

    >>> if old_lc_all:
    ...     os.environ['LC_ALL'] = old_lc_all
    ... else:
    ...     # unneeded return value assigned to variable
    ...     _ = os.environ.pop('LC_ALL', None)
    '''
    language_description = ''
    effective_lc_messages = get_effective_lc_messages()
    if IMPORT_LANGTABLE_SUCCESSFUL:
        language_description = langtable.language_name(
            languageId=localeId,
            languageIdQuery=effective_lc_messages)
        if not language_description:
            language_description = langtable.language_name(
                languageId=localeId, languageIdQuery='en')
    elif IMPORT_PYCOUNTRY_SUCCESSFUL:
        locale = parse_locale(localeId) # pylint: disable=redefined-outer-name
        if locale.language:
            language = pycountry.languages.get(alpha_2=locale.language)
            if not language:
                language = pycountry.languages.get(alpha_3=locale.language)
            if not language:
                language = pycountry.languages.get(
                    bibliographic=locale.language)
            if language and language.name:
                gtrans = gettext.translation(
                    'iso_639-3', fallback=True,
                    languages=[effective_lc_messages])
                language_description = gtrans.gettext(language.name)
        if locale.territory:
            country = pycountry.countries.get(alpha_2=locale.territory)
            if not country:
                country = pycountry.countries.get(alpha_3=locale.territory)
            if country and country.name:
                gtrans = gettext.translation(
                    'iso_3166', fallback=True,
                    languages=[effective_lc_messages])
                cname_trans = gtrans.gettext(country.name)
                language_description += (
                    ' (' + cname_trans[0].upper() + cname_trans[1:]
                    + ')')
    if language_description:
        language_description = (
            language_description[0].upper() + language_description[1:])
    return language_description

def text_ends_a_sentence(text: str = '') -> bool:
    '''
    Checks whether text ends a sentence

    :param text: The text to check
    :return: True if text ends a sentence, False if not.

    Examples:

    >>> text_ends_a_sentence(' ')
    False
    >>> text_ends_a_sentence(' hello ')
    False
    >>> text_ends_a_sentence(' hello . ')
    True
    >>> text_ends_a_sentence('. ')
    True
    >>> text_ends_a_sentence(' . ')
    True
    '''
    if text.isspace():
        return False
    pattern_new_sentence = re.compile(
        r'[' + re.escape(AUTO_CAPITALIZE_CHARACTERS) + r']+[\s]*$')
    if pattern_new_sentence.search(text):
        return True
    return False

def lstrip_token(token: str) -> str:
    '''Strips some characters from the left side of a token

    Characters which have a type listed in CATEGORIES_TO_STRIP_FROM_TOKENS
    are stripped from the left side of a token.

    The stripped token is returned.

    :param token: The token where characters may be stripped from

    Examples:

    >>> lstrip_token(".'foo'.")
    "foo'."
    '''
    token = token.lstrip()
    while (token
           and
           unicodedata.category(token[0]) in CATEGORIES_TO_STRIP_FROM_TOKENS):
        token = token[1:]
    return token

def rstrip_token(token: str) -> str:
    '''Strips some characters from the right side of a token

    Characters which have a type listed in CATEGORIES_TO_STRIP_FROM_TOKENS
    are stripped from the right side of a token.

    The stripped token is returned.

    :param token: The token where characters may be stripped from

    Examples:

    >>> rstrip_token(".'foo'.")
    ".'foo"
    '''
    token = token.rstrip()
    while (token
           and
           unicodedata.category(token[-1]) in CATEGORIES_TO_STRIP_FROM_TOKENS):
        token = token[0:-1]
    return token

def strip_token(token: str) -> str:
    '''Strips some characters from both sides of a token

    Characters which have a type listed in CATEGORIES_TO_STRIP_FROM_TOKENS
    are stripped from both sides of a token.

    The stripped token is returned.

    :param token: The token where characters may be stripped from

    Examples:

    >>> strip_token(".'foo'.")
    'foo'
    '''
    return rstrip_token(lstrip_token(token))

def tokenize(text: str) -> List[str]:
    '''Splits a text into tokens

    Returns a list of tokens

    :param text: The text to tokenize

    Examples:

    >>> tokenize('a b c')
    ['a', 'b', 'c']

    >>> tokenize('\\n a b c')
    ['a', 'b', 'c']

    >>> tokenize('a \\n b c')
    ['a', 'b', 'c']

    >>> tokenize('a (b) c')
    ['a', 'b', 'c']

    >>> tokenize('a () c')
    ['a', 'c']

    >>> tokenize('')
    []

    >>> tokenize('\\n')
    []
    '''
    pattern = re.compile(r'[\s]+')
    tokens = []
    for word in pattern.split(text.strip()):
        token = strip_token(word)
        if token:
            tokens.append(token)
    return tokens

def color_string_to_argb(color_string: str) -> int:
    '''
    Converts a color string to a 32bit  ARGB value

    :param color_string: The color to convert to 32bit ARGB
                         Can be expressed in the following ways:
                             - Standard name from the X11 rgb.txt
                             - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                          or ”#rrrrggggbbbb”
                             - RGB color: “rgb(r,g,b)”
                             - RGBA color: “rgba(r,g,b,a)”

    Examples:

    >>> print('%x' %color_string_to_argb('rgb(0xff, 0x10, 0x25)'))
    ffff1025

    >>> print('%x' %color_string_to_argb('#108040'))
    ff108040

    >>> print('%x' %color_string_to_argb('#fff000888'))
    ffff0088

    >>> print('%x' %color_string_to_argb('#ffff00008888'))
    ffff0088

    >>> print('%x' %color_string_to_argb('rgba(0xff, 0x10, 0x25, 0.5)'))
    7fff1025
    '''
    gdk_rgba = Gdk.RGBA()
    gdk_rgba.parse(color_string)
    return (((int(gdk_rgba.alpha * 0xff) & 0xff) << 24)
            + ((int(gdk_rgba.red * 0xff) & 0xff) << 16)
            + ((int(gdk_rgba.green * 0xff) & 0xff) << 8)
            + (int(gdk_rgba.blue * 0xff) & 0xff))

def is_ascii(text: str) -> bool:
    '''Checks whether all characters in text are ASCII characters

    Returns “True” if the text is all ASCII, “False” if not.

    :param text: The text to check

    Examples:

    >>> is_ascii('Abc')
    True

    >>> is_ascii('Naïve')
    False
    '''
    if sys.version_info >= (3, 7): # str.ascii() was introduced in Python 3.7
        return text.isascii()
    return all(ord(char) < 128 for char in text)

# Mapping of Unicode ordinals to Unicode ordinals, strings, or None.
# Unmapped characters are left untouched. Characters mapped to None
# are deleted.

# See also: https://www.icao.int/publications/Documents/9303_p3_cons_en.pdf
# Section 6, Page 30.

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
    ord('Þ'): 'TH',
    ord('Ħ'): 'H',
    ord('Ŋ'): 'N',
    ord('Ŧ'): 'T',
}

# @functools.cache is available only in Python >= 3.9.
#
# Python >= 3.9 is not available on RHEL8, not yet on openSUSE
# Tumbleweed (2021-22-29), ...
#
# But @functools.lru_cache(maxsize=None) is the same and it is
# available for Python >= 3.2, that means it should be available
# everywhere.

@functools.lru_cache(maxsize=None)
def remove_accents(text: str, keep: str = '') -> str:
    # pylint: disable=line-too-long
    '''Removes accents from the text

    Using “from unidecode import unidecode” is maybe more
    sophisticated, but I am not sure whether I can require
    “unidecode”. And maybe it cannot easily keep some accents for some
    languages.

    :param text: The text to change
    :param keep: A string of characters which should be kept unchanged
    :return: The text with some or all accents removed
             in NORMALIZATION_FORM_INTERNAL

    Examples:

    >>> remove_accents('Ångstrøm')
    'Angstrom'

    >>> remove_accents('ÅÆæŒœĳøßẞü')
    'AAEaeOEoeijossSSu'

    >>> remove_accents('abcÅøßẞüxyz')
    'abcAossSSuxyz'

    >>> unicodedata.normalize('NFC', remove_accents('abcÅøßẞüxyz', keep='åÅØø'))
    'abcÅøssSSuxyz'

    >>> unicodedata.normalize('NFC', remove_accents('alkoholförgiftning', keep='åÅÖö'))
    'alkoholförgiftning'

    '''
    # pylint: enable=line-too-long
    if not keep:
        result = ''.join([
            x for x in unicodedata.normalize('NFKD', text)
            if unicodedata.category(x) != 'Mn']).translate(TRANS_TABLE)
        return unicodedata.normalize(NORMALIZATION_FORM_INTERNAL, result)
    result = ''
    keep = unicodedata.normalize('NFC', keep)
    for char in unicodedata.normalize('NFC', text):
        if char in keep:
            result += char
            continue
        result += ''.join([
            x for x in unicodedata.normalize('NFKD', char)
            if unicodedata.category(x) != 'Mn']).translate(TRANS_TABLE)
    return unicodedata.normalize(NORMALIZATION_FORM_INTERNAL, result)

COMPOSITION_EXCLUSIONS = {
    # See https://www.unicode.org/Public/16.0.0/ucd/CompositionExclusions.txt
    '\u0915\u093C': '\u0958', # DEVANAGARI LETTER QA
    '\u0916\u093C': '\u0959', # DEVANAGARI LETTER KHHA
    '\u0917\u093C': '\u095A', # DEVANAGARI LETTER GHHA
    '\u091C\u093C': '\u095B', # DEVANAGARI LETTER ZA
    '\u0921\u093C': '\u095C', # DEVANAGARI LETTER DDDHA
    '\u0922\u093C': '\u095D', # DEVANAGARI LETTER RHA
    '\u092B\u093C': '\u095E', # DEVANAGARI LETTER FA
    '\u092F\u093C': '\u095F', # DEVANAGARI LETTER YYA
    '\u09A1\u09BC': '\u09DC', # BENGALI LETTER RRA
    '\u09A2\u09BC': '\u09DD', # BENGALI LETTER RHA
    '\u09AF\u09BC': '\u09DF', # BENGALI LETTER YYA
    '\u0A32\u0A3C': '\u0A33', #  GURMUKHI LETTER LLA
    '\u0A38\u0A3C': '\u0A36', #  GURMUKHI LETTER SHA
    '\u0A16\u0A3C': '\u0A59', #  GURMUKHI LETTER KHHA
    '\u0A17\u0A3C': '\u0A5A', #  GURMUKHI LETTER GHHA
    '\u0A1C\u0A3C': '\u0A5B', #  GURMUKHI LETTER ZA
    '\u0A2B\u0A3C': '\u0A5E', #  GURMUKHI LETTER FA
    '\u0B21\u0B3C': '\u0B5C', #  ORIYA LETTER RRA
    '\u0B22\u0B3C': '\u0B5D', #  ORIYA LETTER RHA
    '\u0F42\u0FB7': '\u0F43', #  TIBETAN LETTER GHA
    '\u0F4C\u0FB7': '\u0F4D', #  TIBETAN LETTER DDHA
    '\u0F51\u0FB7': '\u0F52', #  TIBETAN LETTER DHA
    '\u0F56\u0FB7': '\u0F57', #  TIBETAN LETTER BHA
    '\u0F5B\u0FB7': '\u0F5C', #  TIBETAN LETTER DZHA
    '\u0F40\u0FB5': '\u0F69', #  TIBETAN LETTER KSSA
    '\u0FB2\u0F80': '\u0F76', #  TIBETAN VOWEL SIGN VOCALIC R
    '\u0FB3\u0F80': '\u0F78', #  TIBETAN VOWEL SIGN VOCALIC L
    '\u0F92\u0FB7': '\u0F93', #  TIBETAN SUBJOINED LETTER GHA
    '\u0F9C\u0FB7': '\u0F9D', #  TIBETAN SUBJOINED LETTER DDHA
    '\u0FA1\u0FB7': '\u0FA2', #  TIBETAN SUBJOINED LETTER DHA
    '\u0FA6\u0FB7': '\u0FA7', #  TIBETAN SUBJOINED LETTER BHA
    '\u0FAB\u0FB7': '\u0FAC', #  TIBETAN SUBJOINED LETTER DZHA
    '\u0F90\u0FB5': '\u0FB9', #  TIBETAN SUBJOINED LETTER KSSA
    '\u05D9\u05B4': '\uFB1D', #  HEBREW LETTER YOD WITH HIRIQ
    '\u05F2\u05B7': '\uFB1F', #  HEBREW LIGATURE YIDDISH YOD YOD PATAH
    '\u05E9\u05C1': '\uFB2A', #  HEBREW LETTER SHIN WITH SHIN DOT
    '\u05E9\u05C2': '\uFB2B', #  HEBREW LETTER SHIN WITH SIN DOT
    '\u05E9\u05BC\u05C1': '\uFB2C', #  HEBREW LETTER SHIN WITH DAGESH AND SHIN DOT
    '\u05E9\u05BC\u05C2': '\uFB2D', #  HEBREW LETTER SHIN WITH DAGESH AND SIN DOT
    '\u05D0\u05B7': '\uFB2E', #  HEBREW LETTER ALEF WITH PATAH
    '\u05D0\u05B8': '\uFB2F', #  HEBREW LETTER ALEF WITH QAMATS
    '\u05D0\u05BC': '\uFB30', #  HEBREW LETTER ALEF WITH MAPIQ
    '\u05D1\u05BC': '\uFB31', #  HEBREW LETTER BET WITH DAGESH
    '\u05D2\u05BC': '\uFB32', #  HEBREW LETTER GIMEL WITH DAGESH
    '\u05D3\u05BC': '\uFB33', #  HEBREW LETTER DALET WITH DAGESH
    '\u05D4\u05BC': '\uFB34', #  HEBREW LETTER HE WITH MAPIQ
    '\u05D5\u05BC': '\uFB35', #  HEBREW LETTER VAV WITH DAGESH
    '\u05D6\u05BC': '\uFB36', #  HEBREW LETTER ZAYIN WITH DAGESH
    '\u05D8\u05BC': '\uFB38', #  HEBREW LETTER TET WITH DAGESH
    '\u05D9\u05BC': '\uFB39', #  HEBREW LETTER YOD WITH DAGESH
    '\u05DA\u05BC': '\uFB3A', #  HEBREW LETTER FINAL KAF WITH DAGESH
    '\u05DB\u05BC': '\uFB3B', #  HEBREW LETTER KAF WITH DAGESH
    '\u05DC\u05BC': '\uFB3C', #  HEBREW LETTER LAMED WITH DAGESH
    '\u05DE\u05BC': '\uFB3E', #  HEBREW LETTER MEM WITH DAGESH
    '\u05E0\u05BC': '\uFB40', #  HEBREW LETTER NUN WITH DAGESH
    '\u05E1\u05BC': '\uFB41', #  HEBREW LETTER SAMEKH WITH DAGESH
    '\u05E3\u05BC': '\uFB43', #  HEBREW LETTER FINAL PE WITH DAGESH
    '\u05E4\u05BC': '\uFB44', #  HEBREW LETTER PE WITH DAGESH
    '\u05E6\u05BC': '\uFB46', #  HEBREW LETTER TSADI WITH DAGESH
    '\u05E7\u05BC': '\uFB47', #  HEBREW LETTER QOF WITH DAGESH
    '\u05E8\u05BC': '\uFB48', #  HEBREW LETTER RESH WITH DAGESH
    '\u05E9\u05BC': '\uFB49', #  HEBREW LETTER SHIN WITH DAGESH
    '\u05EA\u05BC': '\uFB4A', #  HEBREW LETTER TAV WITH DAGESH
    '\u05D5\u05B9': '\uFB4B', #  HEBREW LETTER VAV WITH HOLAM
    '\u05D1\u05BF': '\uFB4C', #  HEBREW LETTER BET WITH RAFE
    '\u05DB\u05BF': '\uFB4D', #  HEBREW LETTER KAF WITH RAFE
    '\u05E4\u05BF': '\uFB4E', #  HEBREW LETTER PE WITH RAFE
    '\u2ADD\u0338': '\u2ADC', #  FORKING
    '\u1D15\u0045': '\u1D15E',   #  MUSICAL SYMBOL HALF NOTE
    '\u1D15\u0046': '\u1D15F',   #  MUSICAL SYMBOL QUARTER NOTE
    '\u1D16\u0030': '\u1D160',   #  MUSICAL SYMBOL EIGHTH NOTE
    '\u1D16\u0031': '\u1D161',   #  MUSICAL SYMBOL SIXTEENTH NOTE
    '\u1D16\u0032': '\u1D162',   #  MUSICAL SYMBOL THIRTY-SECOND NOTE
    '\u1D16\u0033': '\u1D163',   #  MUSICAL SYMBOL SIXTY-FOURTH NOTE
    '\u1D16\u0034': '\u1D164',   #  MUSICAL SYMBOL ONE HUNDRED TWENTY-EIGHTH NOTE
    '\u1D1B\u0042': '\u1D1BB',   #  MUSICAL SYMBOL MINIMA
    '\u1D1B\u0043': '\u1D1BC',   #  MUSICAL SYMBOL MINIMA BLACK
    '\u1D1B\u0044': '\u1D1BD',   #  MUSICAL SYMBOL SEMIMINIMA WHITE
    '\u1D1B\u0045': '\u1D1BE',   #  MUSICAL SYMBOL SEMIMINIMA BLACK
    '\u1D1B\u0046': '\u1D1BF',   #  MUSICAL SYMBOL FUSA WHITE
    '\u1D1C\u0030': '\u1D1C0',   #  MUSICAL SYMBOL FUSA BLACK Should be complete
    # for Unicode 16.0.0, add further exclusions if needed for later
    # Unicode versions.
}

# Compile a regex that matches any of the keys in COMPOSITION_EXCLUSIONS
COMPOSITION_EXCLUSION_REGEX = re.compile(
    '|'.join(map(re.escape, COMPOSITION_EXCLUSIONS.keys())))

def normalize_nfc_and_composition_exclusions(text: str) -> str:
    # pylint: disable=line-too-long
    '''
    Normalize to NFC **and** also recompose characters listed as
    composition exclusions.

    :param text: The text to normalize
    :return: The normalized text

    Examples:

    >>> normalize_nfc_and_composition_exclusions('\u09a1\u09bc')
    '\u09dc'

    >>> normalize_nfc_and_composition_exclusions('gr\u0075\u0308n \u09a1\u09bc \u09a2\u09bc \u09af\u09bc \u09a1')
    'gr\u00FCn \u09dc \u09dd \u09df \u09a1'
    '''
    # pylint: enable=line-too-long
    text = unicodedata.normalize('NFC', text)

    # openSUSE Leap 15.4 still has only Python 3.6.
    # Cannot use the nicer type hint
    # def replace_exclusions(match: re.Match[str]) -> str:
    def replace_exclusions(match: Any) -> str:
        return COMPOSITION_EXCLUSIONS[match.group(0)]

    return COMPOSITION_EXCLUSION_REGEX.sub(replace_exclusions, text)

def is_right_to_left_messages() -> bool:
    '''
    Check whether the effective LC_MESSAGES locale points to a languages
    which is usually written in a right-to-left script.

    :return: True if right-to-left, False if not.
    '''
    lc_messages_locale = get_effective_lc_messages()
    if not lc_messages_locale:
        return False
    lang = lc_messages_locale.split('_')[0]
    if lang in ('ar', 'arc', 'dv', 'fa', 'he', 'ps', 'syr', 'ur', 'yi'):
        # 'ku' could be Latin script or Arabic script or even Cyrillic
        # or Armenian script
        #
        # 'rhg' (Rohingya) could be written in Rohg (RTL),
        # Arab (RTL), Mymr (LTR), Latn (LTR), Beng (LTR)
        # There is no glibc locale yet for 'rhg'
        #
        # 'man' uses the Nkoo script (RTL)
        # Ther are several varieties of 'man': 'kao', 'mlq', 'mnk',
        # 'mwk', 'xkg', 'jad', 'rkm', 'bm', 'bam', 'mku', 'emk', 'msc'
        # 'mzj', 'jod', 'jud', 'kfo', 'kga', 'mxx', 'dyu', 'bof', 'skq'
        # There is no glibc locale yet for any of these.
        #
        # 'wo' (Wolof) may be written in Gara (RTL). There is no locale
        # for this script yet, the wo_SN glibc locale uses Latn script.
        #
        # 'ff' (Fula) may be written in Adlm (RTL). There is no locale for
        # this script yet, the ff_SN glibc locale uses Latn script.
        return True
    return False

def is_right_to_left(text: str) -> bool:
    # pylint: disable=bidirectional-unicode
    '''Check whether a text is right-to-left text or not

    :param text: The text to check

    See: http://unicode.org/reports/tr9/#P2

    TR9> In each paragraph, find the first character of type L, AL, or R
    TR9> while skipping over any characters between an isolate initiator
    TR9> and its matching PDI or, if it has no matching PDI, the end of the
    TR9> paragraph

    U+2069 POP DIRECTIONAL ISOLATE
    U+2068 FIRST STRONG ISOLATE

    Examples:

    >>> is_right_to_left('Hallo!')
    False

    >>> is_right_to_left('﷼')
    True

    >>> is_right_to_left('\u2068﷼\u2069')
    False

    >>> is_right_to_left('\u2068﷼\u2069﷼')
    True

    >>> is_right_to_left('a\u2068﷼\u2069﷼')
    False

    >>> is_right_to_left('\u2068a\u2069\u2068﷼\u2069﷼')
    True
    '''
    # pylint: enable=bidirectional-unicode
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

def bidi_embed(text: str) -> str:
    # pylint: disable=bidirectional-unicode
    '''Embed the text using explicit directional embedding

    Returns “RLE + text + PDF” if the text is right-to-left,
    if not it returns “LRE + text + PDF”.

    :param text: The text to embed

    See: http://unicode.org/reports/tr9/#Explicit_Directional_Embeddings

    Examples:

    >>> bidi_embed('a')
    '\u202Aa\u202C'

    >>> bidi_embed('﷼')
    '\u202B﷼\u202C'
    '''
    # pylint: enable=bidirectional-unicode
    if is_right_to_left(text):
        return chr(0x202B) + text + chr(0x202C) # RLE + text + PDF
    return chr(0x202A) + text + chr(0x202C) # LRE + text + PDF

def contains_letter(text: str) -> bool:
    '''Returns whether “text” contains a “letter” type character

    :param text: The text to check

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

def variant_to_value(variant: GLib.Variant) -> Any:
    '''
    Convert a GLib variant to a value
    '''
    if variant is None:
        return None
    if not isinstance(variant, GLib.Variant):
        LOGGER.info('not a GLib.Variant')
        return variant
    type_string = variant.get_type_string()
    if type_string == 's':
        return variant.get_string()
    if type_string == 'i':
        return variant.get_int32()
    if type_string == 'u':
        return variant.get_uint32()
    if type_string == 'x':
        return variant.get_int64()
    if type_string == 't':
        return variant.get_uint64()
    if type_string == 'd':
        return variant.get_double()
    if type_string == 'b':
        return variant.get_boolean()
    if type_string == 'v':
        return variant.unpack()
    if type_string and type_string[0] == 'a':
        return variant.unpack()
    LOGGER.error('unknown variant type: %s', type_string)
    return variant

def dict_update_existing_keys(
        pdict: Dict[Any, Any], other_pdict: Dict[Any, Any]) -> None:
    '''Update values of existing keys in a Python dict from another Python dict

    Using pdict.update(other_pdict) would add keys and values from other_pdict
    to pdict even for keys which do not exist in pdict. Sometimes I want
    to update only existing keys and ignore new keys.

    :param pdict: The Python dict to update
    :param other_pdict: The Python dict to get the updates from

    Examples:

    >>> old_pdict = {'a': 1, 'b': 2}
    >>> new_pdict = {'b': 3, 'c': 4}
    >>> dict_update_existing_keys(old_pdict, new_pdict)
    >>> sorted(old_pdict.items())
    [('a', 1), ('b', 3)]
    >>> old_pdict.update(new_pdict)
    >>> sorted(old_pdict.items())
    [('a', 1), ('b', 3), ('c', 4)]
    '''
    for key in other_pdict:
        if key in pdict:
            pdict[key] = other_pdict[key]

def distro_id() -> str:
    '''
    Compatibility wrapper around distro.id()

    From the help of distro.id():

        This package maintains the following reliable distro ID values:

        ==============  =========================================
        Distro ID       Distribution
        ==============  =========================================
        "ubuntu"        Ubuntu
        "debian"        Debian
        "rhel"          RedHat Enterprise Linux
        "centos"        CentOS
        "fedora"        Fedora
        "sles"          SUSE Linux Enterprise Server
        "opensuse"      openSUSE
        "amazon"        Amazon Linux
        "arch"          Arch Linux
        "cloudlinux"    CloudLinux OS
        "exherbo"       Exherbo Linux
        "gentoo"        GenToo Linux
        "ibm_powerkvm"  IBM PowerKVM
        "kvmibm"        KVM for IBM z Systems
        "linuxmint"     Linux Mint
        "mageia"        Mageia
        "mandriva"      Mandriva Linux
        "parallels"     Parallels
        "pidora"        Pidora
        "raspbian"      Raspbian
        "oracle"        Oracle Linux (and Oracle Enterprise Linux)
        "scientific"    Scientific Linux
        "slackware"     Slackware
        "xenserver"     XenServer
        "openbsd"       OpenBSD
        "netbsd"        NetBSD
        "freebsd"       FreeBSD
        ==============  =========================================

    There seem to be other return values, so far I know:

        "opensuse-leap" openSUSE Leap
        "opensuse-tumbleweed" openSUSE tumbleweed
        "sles"          SUSE Linux Enterprise server
        "sled"          SUSE Linux Enterprise Desktop 15 SP1

    '''
    if IMPORT_DISTRO_SUCCESSFUL:
        return str(distro.id())
    return ''

def find_hunspell_dictionary(language: str) -> Tuple[str, str]:
    '''
    Find the hunspell dictionary file for a language

    :param language: The language of the dictionary to search for

    The returned Tuple contains (dic_path, aff_path) where
    dic_path is the full path of the .dic file found
    and aff_path is the full path of the .aff file found.
    If no dictionary can be found for the requested language,
    the return value is ('', '').
    '''
    datadir = os.path.join(os.path.dirname(__file__), '../data')
    user_datadir = xdg_save_data_path('ibus-typing-booster/data')
    dicpaths = []
    dicpath_string = os.environ.get('DICPATH')
    if dicpath_string:
        dicpaths = [os.path.expanduser(path)
                    for path in dicpath_string.split(':') if path]
    dirnames = [user_datadir, datadir]
    dirnames += dicpaths
    dirnames += [
        '/usr/share/hunspell',
        '/usr/share/myspell',
        '/usr/share/myspell/dicts',
        '/usr/local/share/hunspell', # On FreeBSD the dictionaries are here
        '/usr/local/share/myspell',
        '/usr/local/share/myspell/dicts',
    ]
    dic_path = ''
    aff_path = ''
    for lang in expand_languages([language]):
        for dirname in dirnames:
            if os.path.isfile(os.path.join(dirname, lang + '.dic')):
                dic_path = os.path.join(dirname, lang + '.dic')
                aff_path = os.path.join(dirname, lang + '.aff')
                return (dic_path, aff_path)
    LOGGER.warning(
        'No file %s.dic found in %s', language, dirnames)
    return ('', '')

def get_hunspell_dictionary_wordlist(
        language: str) -> Tuple[str, str, List[str]]:
    '''
    Open the hunspell dictionary file for a language

    :param language: The language of the dictionary to open

    The returned Tuple looks  like this:

        (dic_path, dictionary_encoding, wordlist)

    where dic_path is the full path of the dictionary file found,
    dictionary_encoding is the encoding of that dictionary file,
    and wordlist is a list of words found in that file.
    If no dictionary can be found for the requested language,
    the return value is ('', '', []).
    '''
    (dic_path, aff_path) = find_hunspell_dictionary(language)
    if not dic_path:
        return ('', '', [])
    LOGGER.info('%s file found.', dic_path)
    dictionary_encoding = 'UTF-8'
    if os.path.isfile(aff_path):
        aff_buffer = ''
        try:
            with open(aff_path,
                      encoding='ISO-8859-1',
                      errors='ignore') as aff_file:
                aff_buffer = aff_file.read().replace('\r\n', '\n')
        except (FileNotFoundError, PermissionError) as error:
            LOGGER.exception('Error loading .aff File %s: %s: %s',
                             aff_path, error.__class__.__name__, error)
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error loading .aff File %s: %s: %s',
                             aff_path, error.__class__.__name__, error)
        if aff_buffer:
            encoding_pattern = re.compile(
                r'^[\s]*SET[\s]+(?P<encoding>[-a-zA-Z0-9_]+)[\s]*$',
                re.MULTILINE)
            match = encoding_pattern.search(aff_buffer)
            if match:
                dictionary_encoding = match.group('encoding')
                LOGGER.info(
                    'dictionary encoding=%s found in %s',
                    dictionary_encoding, aff_path)
            else:
                LOGGER.info(
                    'No encoding found in %s', aff_path)
    else:
        LOGGER.info(
            '%s file missing. Trying to open %s using %s encoding',
            aff_path, dic_path, dictionary_encoding)
    dic_buffer = []
    try:
        with open(dic_path, encoding=dictionary_encoding) as dic_file:
            dic_buffer = dic_file.readlines()
    except (UnicodeDecodeError, FileNotFoundError, PermissionError) as error:
        LOGGER.exception(
            'loading %s as %s encoding failed, '
            'fall back to ISO-8859-1. %s: %s',
            dic_path, dictionary_encoding, error.__class__.__name__, error)
        dictionary_encoding = 'ISO-8859-1'
        try:
            with open(dic_path, encoding=dictionary_encoding) as dic_file:
                dic_buffer = dic_file.readlines()
        except (UnicodeDecodeError,
                FileNotFoundError,
                PermissionError) as error2:
            LOGGER.exception(
                'loading %s as %s encoding failed, giving up. %s: %s',
                dic_path, dictionary_encoding, error.__class__.__name__, error2)
            return ('', '', [])
        except Exception as error2: # pylint: disable=broad-except
            LOGGER.exception(
                'Unexpected error loading .dic File %s: %s: %s',
                dic_path, error.__class__.__name__, error2)
            return ('', '', [])
    except Exception as error: # pylint: disable=broad-except
        LOGGER.exception(
            'Unexpected error loading .dic File %s: %s: %s',
            dic_path, error.__class__.__name__, error)
        return ('', '', [])
    if not dic_buffer:
        return ('', '', [])
    LOGGER.info(
        'Successfully loaded %s using %s encoding.',
        dic_path, dictionary_encoding)
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
    # Newer French dictionaries downloaded from
    #
    # http://grammalecte.net/download/fr/hunspell-french-dictionaries-v6.4.1.zip
    #
    # even contain stuff like:
    #
    # différemment po:adv
    # différence/S.() po:nom is:fem
    #
    # i.e. the separator between the word and the extra stuff
    # can be a space instead of a tab.
    #
    # As far as I know, hunspell dictionaries never contain whitespace
    # within the words themselves.
    #
    # Therefore, remove everything following a '/', ' ', or a tab from
    # a line to make the memory use of the word list a bit smaller and
    # the regular expressions we use later to match words in the
    # dictionary slightly simpler and maybe a tiny bit faster:
    #
    word_list = [
        unicodedata.normalize(
            NORMALIZATION_FORM_INTERNAL,
            re.sub(r'[/\t ].*', '', x.replace('\n', '')))
        for x in dic_buffer
    ]
    return (dic_path, dictionary_encoding, word_list)

class Capabilite(Flag):
    '''Compatibility class to handle IBus.Capabilite the same way no matter
    what version of ibus is used.

    For example, older versions of ibus might not have IBus.Capabilite.SYNC_PROCESS_KEY_V2
    (or maybe even do not have IBus.Capabilite at all). Then

        capabilities & IBus.Capabilite.SYNC_PROCESS_KEY_V2

    will produce an exception. But when using this compatibility class

        capabilities & IBus.Capabilite.SYNC_PROCESS_KEY_V2

    will just be False but not cause an exception.

    >>> int(Capabilite.PREEDIT_TEXT)
    1

    >>> Capabilite.PREEDIT_TEXT == 1
    True

    >>> Capabilite.PREEDIT_TEXT | 2
    3

    >>> 2 | Capabilite.PREEDIT_TEXT
    3

    >>> int(Capabilite.PREEDIT_TEXT | Capabilite.AUXILIARY_TEXT)
    3

    >>> 3 == Capabilite.AUXILIARY_TEXT | Capabilite.PREEDIT_TEXT
    True

    >>> 3 == Capabilite.AUXILIARY_TEXT | IBus.Capabilite.PREEDIT_TEXT
    True

    >>> Capabilite.PREEDIT_TEXT == IBus.Capabilite.PREEDIT_TEXT
    True
    '''
    def __new__(cls, attr: str) -> Any:
        obj = object.__new__(cls)
        if hasattr(IBus, 'Capabilite') and hasattr(IBus.Capabilite, attr):
            obj._value_ = int(getattr(IBus.Capabilite, attr))
        else:
            obj._value_ = 0
        return obj

    def __int__(self) -> int:
        return int(self._value_)

    def __eq__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is IBus.Capabilite):
            return bool(int(self) == int(other))
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) == other)
        return NotImplemented

    def __or__(self, other: Any) -> Any:
        if self.__class__ is other.__class__:
            return self.value | other.value
        if other.__class__ is IBus.Capabilite:
            return int(self) | int(other)
        if other.__class__ is int:
            return int(self) | other
        return NotImplemented

    def __ror__(self, other: Any) -> Any: # type: ignore[override]
        return self.__or__(other)

    def __and__(self, other: Any) -> Any:
        if self.__class__ is other.__class__:
            return self.value & other.value
        if other.__class__ is IBus.Capabilite:
            return int(self) & int(other)
        if other.__class__ is int:
            return int(self) & other
        return NotImplemented

    def __rand__(self, other: Any) -> Any: # type: ignore[override]
        return self.__and__(other)

    PREEDIT_TEXT = 'PREEDIT_TEXT'
    AUXILIARY_TEXT = 'AUXILIARY_TEXT'
    LOOKUP_TABLE = 'LOOKUP_TABLE'
    FOCUS = 'FOCUS'
    PROPERTY = 'PROPERTY'
    SURROUNDING_TEXT = 'SURROUNDING_TEXT'
    OSK = 'OSK'
    SYNC_PROCESS_KEY = 'SYNC_PROCESS_KEY'
    SYNC_PROCESS_KEY_V2 = 'SYNC_PROCESS_KEY_V2'

class InputPurpose(Enum):
    '''Compatibility class to handle InputPurpose the same way no matter
    what version of ibus is used.

    For example, older versions of ibus might not have
    IBus.InputPurpose.TERMINAL and then

        input_purpose == IBus.InputPurpose.TERMINAL

    will produce an exception. But when using this compatibility class

        input_purpose == InputPurpose.TERMINAL

    will just be False but not cause an exception.

    See also:

    https://docs.gtk.org/gtk3/enum.InputPurpose.html
    https://docs.gtk.org/gtk4/enum.InputPurpose.html

    Examples:

    >>> int(InputPurpose.PASSWORD)
    8

    >>> 8 == InputPurpose.PASSWORD
    True

    >>> int(InputPurpose.PIN)
    9

    >>> InputPurpose.PASSWORD <= InputPurpose.PIN
    True

    >>> InputPurpose.PASSWORD == Gtk.InputPurpose.PASSWORD
    True

    >>> InputPurpose.PASSWORD == IBus.InputPurpose.PASSWORD
    True
    '''
    def __new__(cls, attr: str) -> Any:
        obj = object.__new__(cls)
        if hasattr(Gtk, 'InputPurpose') and hasattr(Gtk.InputPurpose, attr):
            obj._value_ = int(getattr(Gtk.InputPurpose, attr))
        else:
            obj._value_ = -1
        return obj

    def __int__(self) -> int:
        return int(self._value_)

    def __eq__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputPurpose
            or other.__class__ is IBus.InputPurpose):
            return int(self) == int(other)
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) == other)
        return NotImplemented

    def __gt__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputPurpose
            or other.__class__ is IBus.InputPurpose):
            return int(self) > int(other)
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) > other)
        return NotImplemented

    def __lt__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputPurpose
            or other.__class__ is IBus.InputPurpose):
            return bool(int(self) < int(other))
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) < other)
        return NotImplemented

    def __ge__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputPurpose
            or other.__class__ is IBus.InputPurpose):
            return bool(int(self) >= int(other))
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) >= other)
        return NotImplemented

    def __le__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputPurpose
            or other.__class__ is IBus.InputPurpose):
            return bool(int(self) <= int(other))
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) <= other)
        return NotImplemented

    FREE_FORM = 'FREE_FORM'
    ALPHA = 'ALPHA'
    DIGITS = 'DIGITS'
    NUMBER = 'NUMBER'
    PHONE = 'PHONE'
    URL = 'URL'
    EMAIL = 'EMAIL'
    NAME = 'NAME'
    PASSWORD = 'PASSWORD'
    PIN = 'PIN'
    TERMINAL = 'TERMINAL'

class InputHints(Flag):
    '''Compatibility class to handle InputHints the same way no matter
    what version of ibus is used.

    For example, older versions of ibus might not have IBus.InputHints.PRIVATE
    (or maybe even do not have IBus.InputHints at all). Then

        input_hints & IBus.InputHints.PRIVATE

    will produce an exception. But when using this compatibility class

        input_hints & InputHints.PRIVATE

    will just be False but not cause an exception.

    See also:

    https://docs.gtk.org/gtk3/flags.InputHints.html
    https://docs.gtk.org/gtk4/flags.InputHints.html

    Examples:

    >>> int(InputHints.SPELLCHECK)
    1

    >>> InputHints.SPELLCHECK == 1
    True

    >>> InputHints.SPELLCHECK | 2
    3

    >>> 2 | InputHints.SPELLCHECK
    3

    >>> int(InputHints.NO_SPELLCHECK | InputHints.SPELLCHECK)
    3

    >>> 3 == InputHints.NO_SPELLCHECK | InputHints.SPELLCHECK
    True

    >>> 3 == InputHints.NO_SPELLCHECK | Gtk.InputHints.SPELLCHECK
    True

    >>> 3 == InputHints.NO_SPELLCHECK | IBus.InputHints.SPELLCHECK
    True

    >>> InputHints.SPELLCHECK == IBus.InputHints.SPELLCHECK
    True

    >>> InputHints.SPELLCHECK == Gtk.InputHints.SPELLCHECK
    True
    '''
    def __new__(cls, attr: str) -> Any:
        obj = object.__new__(cls)
        if hasattr(Gtk, 'InputHints') and hasattr(Gtk.InputHints, attr):
            obj._value_ = int(getattr(Gtk.InputHints, attr))
        else:
            obj._value_ = 0
        return obj

    def __int__(self) -> int:
        return int(self._value_)

    def __eq__(self, other: Any) -> bool:
        if (self.__class__ is other.__class__
            or other.__class__ is Gtk.InputHints
            or other.__class__ is IBus.InputHints):
            return bool(int(self) == int(other))
        if other.__class__ is int or other.__class__ is float:
            return bool(int(self) == other)
        return NotImplemented

    def __or__(self, other: Any) -> Any:
        if self.__class__ is other.__class__:
            return self.value | other.value
        if (other.__class__ is Gtk.InputHints
            or other.__class__ is IBus.InputHints):
            return int(self) | int(other)
        if other.__class__ is int:
            return int(self) | other
        return NotImplemented

    def __ror__(self, other: Any) -> Any: # type: ignore[override]
        return self.__or__(other)

    def __and__(self, other: Any) -> Any:
        if self.__class__ is other.__class__:
            return self.value & other.value
        if (other.__class__ is Gtk.InputHints
            or other.__class__ is IBus.InputHints):
            return int(self) & int(other)
        if other.__class__ is int:
            return int(self) & other
        return NotImplemented

    def __rand__(self, other: Any) -> Any: # type: ignore[override]
        return self.__and__(other)

    NONE = 'NONE'
    SPELLCHECK = 'SPELLCHECK'
    NO_SPELLCHECK = 'NO_SPELLCHECK'
    WORD_COMPLETION = 'WORD_COMPLETION'
    LOWERCASE = 'LOWERCASE'
    UPPERCASE_CHARS = 'UPPERCASE_CHARS'
    UPPERCASE_WORDS = 'UPPERCASE_WORDS'
    UPPERCASE_SENTENCES = 'UPPERCASE_SENTENCES'
    INHIBIT_OSK = 'INHIBIT_OSK'
    VERTICAL_WRITING = 'VERTICAL_WRITING'
    EMOJI = 'EMOJI'
    NO_EMOJI = 'NO_EMOJI'
    PRIVATE = 'PRIVATE'

class ComposeSequences:
    '''Class to handle compose sequences.

    Finds all compose files, i.e. the system wide compose file
    for the current locale and the compose files from the users
    home directory and stores the compose sequences found there
    in an internal variable.
    '''
    def __init__(self) -> None:
        self._keypad_keyvals = {
            IBus.KEY_KP_0: IBus.KEY_0,
            IBus.KEY_KP_1: IBus.KEY_1,
            IBus.KEY_KP_2: IBus.KEY_2,
            IBus.KEY_KP_3: IBus.KEY_3,
            IBus.KEY_KP_4: IBus.KEY_4,
            IBus.KEY_KP_5: IBus.KEY_5,
            IBus.KEY_KP_6: IBus.KEY_6,
            IBus.KEY_KP_7: IBus.KEY_7,
            IBus.KEY_KP_9: IBus.KEY_8,
            IBus.KEY_KP_Equal: IBus.KEY_equal,
            IBus.KEY_KP_Divide: IBus.KEY_slash,
            IBus.KEY_KP_Multiply: IBus.KEY_asterisk,
            IBus.KEY_KP_Subtract: IBus.KEY_minus,
            IBus.KEY_KP_Add: IBus.KEY_plus,
            IBus.KEY_KP_Decimal: IBus.KEY_period,
            IBus.KEY_KP_Space: IBus.KEY_2,
        }
        # Not the exact inversion of self._keypad_keyvals because of
        # the weird KP_Space!:
        self._non_keypad_keyvals = {
            IBus.KEY_0: IBus.KEY_KP_0,
            IBus.KEY_1: IBus.KEY_KP_1,
            IBus.KEY_2: IBus.KEY_KP_2,
            IBus.KEY_3: IBus.KEY_KP_3,
            IBus.KEY_4: IBus.KEY_KP_4,
            IBus.KEY_5: IBus.KEY_KP_5,
            IBus.KEY_6: IBus.KEY_KP_6,
            IBus.KEY_7: IBus.KEY_KP_7,
            IBus.KEY_8: IBus.KEY_KP_9,
            IBus.KEY_equal: IBus.KEY_KP_Equal,
            IBus.KEY_slash: IBus.KEY_KP_Divide,
            IBus.KEY_asterisk: IBus.KEY_KP_Multiply,
            IBus.KEY_minus: IBus.KEY_KP_Subtract,
            IBus.KEY_plus: IBus.KEY_KP_Add,
            IBus.KEY_period: IBus.KEY_KP_Decimal,
        }
        self._preedit_representations = {
            # See also /usr/include/X11/keysymdef.h and
            # ibus/src/ibusenginesimple.c
            #
            # Nonspacing combining marks used by the Unicode Standard
            # may be exhibited in apparent isolation by applying them
            # to U+00A0 NO-BREAK SPACE. This convention might be
            # employed, for example, when talking about the combining
            # mark itself as a mark, rather than using it in its
            # normal way in text (that is, applied as an accent to a
            # base letter or in other combinations).
            #
            # Sadly the official character ⎄ U+2384 COMPOSITION SYMBOL
            # is a bit too distracting so we use · U+00B7 MIDDLE DOT
            # to represent the Multi_key in the preedit:
            IBus.KEY_Multi_key: '·',
            IBus.KEY_dead_abovecomma: '᾿',
            IBus.KEY_dead_abovedot: '˙',
            IBus.KEY_dead_abovereversedcomma: '῾',
            IBus.KEY_dead_abovering: '˚',
            IBus.KEY_dead_acute: '´',
            IBus.KEY_dead_belowbreve: '\u00A0\u032E',
            IBus.KEY_dead_belowcircumflex: 'ꞈ',
            IBus.KEY_dead_belowcomma: ',',
            IBus.KEY_dead_belowdiaeresis: '\u00A0\u0324',
            IBus.KEY_dead_belowdot: '.',
            IBus.KEY_dead_belowmacron: 'ˍ',
            IBus.KEY_dead_belowring: '˳',
            IBus.KEY_dead_belowtilde: '˷',
            IBus.KEY_dead_breve: '˘',
            IBus.KEY_dead_caron: 'ˇ',
            IBus.KEY_dead_cedilla: '¸',
            IBus.KEY_dead_circumflex: '^',
            IBus.KEY_dead_currency: '¤',
            IBus.KEY_dead_dasia: '῾', # alias for dead_abovereversedcomma
            IBus.KEY_dead_diaeresis: '¨',
            IBus.KEY_dead_doubleacute: '˝',
            IBus.KEY_dead_doublegrave: '˵',
            IBus.KEY_dead_grave: '`',
            IBus.KEY_dead_greek: 'μ',
            IBus.KEY_dead_hook: '\u00A0\u0309',
            IBus.KEY_dead_horn: '\u00A0\u031B',
            IBus.KEY_dead_invertedbreve: '\u00A0\u0311',
            IBus.KEY_dead_iota: 'ͺ',
            IBus.KEY_dead_macron: '¯',
            IBus.KEY_dead_ogonek: '˛',
            IBus.KEY_dead_perispomeni: '~', # alias for dead_tilde
            IBus.KEY_dead_psili: '᾿', # alias for dead_abovecomma
            IBus.KEY_dead_semivoiced_sound: '゜',
            IBus.KEY_dead_stroke: '/',
            IBus.KEY_dead_tilde: '~',
            IBus.KEY_dead_voiced_sound: '゛',
            # Dead vowels for universal syllable entry:
            IBus.KEY_dead_a: 'ぁ',
            IBus.KEY_dead_A: 'あ',
            IBus.KEY_dead_i: 'ぃ',
            IBus.KEY_dead_I: 'い',
            IBus.KEY_dead_u: 'ぅ',
            IBus.KEY_dead_U: 'う',
            IBus.KEY_dead_e: 'ぇ',
            IBus.KEY_dead_E: 'え',
            IBus.KEY_dead_o: 'ぉ',
            IBus.KEY_dead_O: 'お',
            IBus.KEY_dead_small_schwa: 'ə',
            IBus.KEY_dead_capital_schwa: 'Ə',
        }
        # Extra dead elements for German T3 layout: (in
        # /usr/include/X11/keysymdef.h but they don’t exist in
        # ibus.
        #
        # They have been added recently (on 2021-07-26):
        #
        # pylint: disable=line-too-long
        #
        # https://github.com/ibus/ibus/commit/3e2609e68c9107ce7c65e2d5876bfdc9f0f8c854
        #
        # pylint: enable=line-too-long
        #
        # IBus.KEY_dead_lowline: '_',
        # IBus.KEY_dead_aboveverticalline: '\u00A0\u030D',
        # IBus.KEY_dead_belowverticalline: '\u00A0\u0329',
        # IBus.KEY_dead_longsolidusoverlay: '\u00A0\u0338',
        #
        # Add them automatically as soon as they start to exist:
        if hasattr(IBus, 'KEY_dead_lowline'):
            self._preedit_representations[
                getattr(IBus, 'KEY_dead_lowline')] = '_'
        if hasattr(IBus, 'KEY_dead_aboveverticalline'):
            self._preedit_representations[
                getattr(IBus, 'KEY_dead_aboveverticalline')] = '\u00A0\u030D'
        if hasattr(IBus, 'KEY_dead_belowverticalline'):
            self._preedit_representations[
                getattr(IBus, 'KEY_dead_belowverticalline')] = '\u00A0\u0329'
        if hasattr(IBus, 'KEY_dead_longsolidusoverlay'):
            self._preedit_representations[
                getattr(IBus, 'KEY_dead_longsolidusoverlay')] = '\u00A0\u0338'
        self._dead_keys = {
            # See also /usr/include/X11/keysymdef.h and
            # ibus/src/ibusenginesimple.c
            #
            # pylint: disable=line-too-long
            IBus.KEY_dead_abovecomma: '\u0313', # COMBINING COMMA ABOVE
            IBus.KEY_dead_abovedot: '\u0307', # COMBINING DOT ABOVE
            IBus.KEY_dead_abovereversedcomma: '\u0314', # COMBINING REVERSED COMMA ABOVE
            IBus.KEY_dead_abovering: '\u030A', # COMBINING RING ABOVE;
            IBus.KEY_dead_acute: '\u0301', # COMBINING ACUTE ACCENT
            IBus.KEY_dead_belowbreve: '\u032E', # COMBINING BREVE BELOW
            IBus.KEY_dead_belowcircumflex: '\u032D', # COMBINING CIRCUMFLEX ACCENT BELOW
            IBus.KEY_dead_belowcomma: '\u0326', # COMBINING COMMA BELOW
            IBus.KEY_dead_belowdiaeresis: '\u0324', # COMBINING DIAERESIS BELOW
            IBus.KEY_dead_belowdot: '\u0323', # COMBINING DOT BELOW
            IBus.KEY_dead_belowmacron: '\u0331', # COMBINING MACRON BELOW
            IBus.KEY_dead_belowring: '\u0325', # COMBINING RING BELOW
            IBus.KEY_dead_belowtilde: '\u0330', # COMBINING TILDE BELOW
            IBus.KEY_dead_breve: '\u0306', # COMBINING BREVE
            IBus.KEY_dead_caron: '\u030C', # COMBINING CARON
            IBus.KEY_dead_cedilla: '\u0327', # COMBINING CEDILLA
            IBus.KEY_dead_circumflex: '\u0302', # COMBINING CIRCUMFLEX ACCENT
            # pylint: disable=fixme
            # IBus.KEY_dead_currency: '', # FIXME
            # pylint: enable=fixme
            # dead_dasia is an alias for dead_abovereversedcomma
            IBus.KEY_dead_dasia: '\u0314', # COMBINING REVERSED COMMA ABOVE
            IBus.KEY_dead_diaeresis: '\u0308', # COMBINING DIAERESIS
            IBus.KEY_dead_doubleacute: '\u030B', # COMBINING DOUBLE ACUTE ACCENT
            IBus.KEY_dead_doublegrave: '\u030F', # COMBINING DOUBLE GRAVE ACCENT
            IBus.KEY_dead_grave: '\u0300', # COMBINING GRAVE ACCENT
            # pylint: disable=fixme
            # IBus.KEY_dead_greek: '', # FIXME
            # pylint: enable=fixme
            IBus.KEY_dead_hook: '\u0309', # COMBINING HOOK ABOVE
            IBus.KEY_dead_horn: '\u031B', # COMBINING HORN
            IBus.KEY_dead_invertedbreve: '\u0311', # COMBINING INVERTED BREVE
            IBus.KEY_dead_iota: '\u0345', # U+0345 COMBINING GREEK YPOGEGRAMMENI (old-name: GREEK NON-SPACING IOTA BELOW)
            IBus.KEY_dead_macron: '\u0304', # COMBINING MACRON
            IBus.KEY_dead_ogonek: '\u0328', # COMBINING OGONEK
            # dead_perispomeni is an alias for dead_tilde
            IBus.KEY_dead_perispomeni: '\u0303', # COMBINING TILDE
            # dead_psili is an alias for dead_abovecomma
            IBus.KEY_dead_psili: '\u0313', # COMBINING COMMA ABOVE
            IBus.KEY_dead_semivoiced_sound: '\u309A', # COMBINING KATAKANA-HIRAGANA SEMI-VOICED SOUND MARK
            IBus.KEY_dead_stroke: '\u0335', # COMBINING SHORT STROKE OVERLAY
            # U+0336 COMBINING LONG STROKE OVERLAY might be reasonable as well
            # but gtk uses U+0335 for dead_stroke, see
            # https://gitlab.gnome.org/GNOME/gtk/-/blob/master/gtk/gtkcomposetable.c#L1528
            IBus.KEY_dead_tilde: '\u0303', # COMBINING TILDE
            IBus.KEY_dead_voiced_sound: '\u0399', # COMBINING KATAKANA-HIRAGANA VOICED SOUND MARK
            #
            # Dead vowels for universal syllable entry:
            IBus.KEY_dead_a: '\u0363', # COMBINING LATIN SMALL LETTER A
            IBus.KEY_dead_A: '\u0363', # COMBINING LATIN SMALL LETTER A
            IBus.KEY_dead_i: '\u0365', # COMBINING LATIN SMALL LETTER I
            IBus.KEY_dead_I: '\u0365', # COMBINING LATIN SMALL LETTER I
            IBus.KEY_dead_u: '\u0367', # COMBINING LATIN SMALL LETTER U
            IBus.KEY_dead_U: '\u0367', # COMBINING LATIN SMALL LETTER U
            IBus.KEY_dead_e: '\u0364', # COMBINING LATIN SMALL LETTER E
            IBus.KEY_dead_E: '\u0364', # COMBINING LATIN SMALL LETTER E
            IBus.KEY_dead_o: '\u0366', # COMBINING LATIN SMALL LETTER O
            IBus.KEY_dead_O: '\u0366', # COMBINING LATIN SMALL LETTER O
            IBus.KEY_dead_small_schwa: '\u1DEA ', # COMBINING LATIN SMALL LETTER SCHWA
            IBus.KEY_dead_capital_schwa: '\u1DEA', # COMBINING LATIN SMALL LETTER SCHWA
            #
            # I don’t know how to make a distinction between upper and
            # lower case for the “dead vowels of the universal syllable entry”.
            #
            # But I follow Gtk now, see:
            # https://gitlab.gnome.org/GNOME/gtk/-/blob/master/gtk/gtkcomposetable.c#L1528
            #
            # pylint: enable=line-too-long
        }
        # Extra dead elements for German T3 layout: (in
        # /usr/include/X11/keysymdef.h but they don’t exist in
        # ibus.
        #
        # They have been added recently (on 2021-07-26):
        #
        # pylint: disable=line-too-long
        #
        # https://github.com/ibus/ibus/commit/3e2609e68c9107ce7c65e2d5876bfdc9f0f8c854
        #
        # IBus.KEY_dead_lowline: '\u0332', # COMBINING LOW LINE
        # IBus.KEY_dead_aboveverticalline: '\u030D', # COMBINING VERTICAL LINE ABOVE
        # IBus.KEY_dead_belowverticalline: '\u0329', # COMBINING VERTICAL LINE BELOW
        # IBus.KEY_dead_longsolidusoverlay: '\u0338', # COMBINING LONG SOLIDUS OVERLAY
        #
        # pylint: enable=line-too-long
        #
        # Add them automatically as soon as they start to exist:
        if hasattr(IBus, 'KEY_dead_lowline'):
            self._dead_keys[
                getattr(IBus, 'KEY_dead_lowline')] = '\u0332'
        if hasattr(IBus, 'KEY_dead_aboveverticalline'):
            self._dead_keys[
                getattr(IBus, 'KEY_dead_aboveverticalline')] = '\u030D'
        if hasattr(IBus, 'KEY_dead_belowverticalline'):
            self._dead_keys[
                getattr(IBus, 'KEY_dead_belowverticalline')] = '\u0329'
        if hasattr(IBus, 'KEY_dead_longsolidusoverlay'):
            self._dead_keys[
                getattr(IBus, 'KEY_dead_longsolidusoverlay')] = '\u0338'
        self._compose_sequences: Dict[int, Any] = {}
        compose_file_paths = []
        # Gtk reads compose files like this:
        #
        # https://docs.gtk.org/gtk3/class.IMContextSimple.html
        # https://docs.gtk.org/gtk4/class.IMContextSimple.html
        # explains how Gtk reads compose files:
        #
        #     GtkIMContextSimple reads additional compose sequences
        #     from the first of the following files that is found:
        #     ~/.config/gtk-3.0/Compose, ~/.XCompose,
        #     /usr/share/X11/locale/$locale/Compose (for locales that
        #     have a nontrivial Compose file).
        #
        # The compose support in Gtk can be tested for example with
        #
        #     GTK_IM_MODULE=gtk-im-context-simple gedit
        #
        # ibus-typing-booster reads compose files as follows, which is
        # slightly different from Gtk:
        user_compose_file = os.environ.get(
            'XCOMPOSEFILE') or os.path.expanduser('~/.XCompose')
        if (os.path.isfile(user_compose_file)
            and os.access(user_compose_file, os.R_OK)):
            # A user compose file either pointed to by XCOMPOSEFILE
            # (see
            # https://www.x.org/releases/X11R7.5/doc/man/man5/Compose.5.html
            # https://www.mankier.com/5/Compose)
            # or ~/.XCompose has been found and is readable.  **Only**
            # this compose file is added to the list of compose file
            # to read, allowing the user to avoid loading the system
            # compose files. This way it is possible for the user to
            # avoid compose sequences in the system compose files if
            # he doesn’t want them.  The user compose file may contain
            # “include” statements though to enable the user to
            # include other compose files as desired.
            compose_file_paths.append(user_compose_file)
        else:
            # No user compose file could be found or it was not
            # readable.  Fill the list of compose files to read with
            # the system compose files, first the locale specific
            # compose file from Xorg, then the file from Gtk and then
            # the file from ibus:
            compose_file_paths.append(self._locale_compose_file())
            compose_file_paths.append(
                os.path.expanduser('~/.config/gtk-3.0/Compose'))
            compose_file_paths.append(
                os.path.expanduser('~/.config/gtk-4.0/Compose'))
            compose_file_paths.append(
                os.path.expanduser('~/.config/ibus/Compose'))
        # Now read all compose files on the list. If some of the
        # compose files read contain different definitions of compose
        # sequences, the definition read last wins.
        #
        # All the compose files read may contain include statements
        # including other compose files.
        #
        # There are 3 substitutions that can be made in the file name
        # of the include instruction (only %H and %L are mentioned in
        # https://www.x.org/releases/X11R7.5/doc/man/man5/Compose.5.html
        # but https://www.mankier.com/5/Compose and “man xcompose” on
        # Fedora 34 also mention %S. %S was added ages ago by Marko
        # Myllynen to allow rewriting the fi_FI compose file so that
        # it includes en_US and then defines everything specified in
        # the standard.  Marko confirmed that %S works on F34):
        #
        # %H  expands to the user's home directory
        #     (the $HOME environment variable)
        # %L  expands to the name of the locale specific Compose file
        #     (i.e. "/usr/share/X11/locale/<localename>/Compose")
        # %S  expands to the name of the system directory for Compose files
        #     (i.e. "/usr/share/X11/locale")
        #
        # For example, to include the locale specific default compose
        # file one can use (let’s assume the current locale is
        # en_US.UTF-8):
        #
        #     include "%S/en_US.UTF-8/Compose"
        #
        # or, shorter:
        #
        #     include "%L"
        for path in compose_file_paths:
            self._read_compose_file(path)

    def _add_compose_sequence(self, sequence: str, result: str) -> None:
        # pylint: disable=line-too-long
        '''Adds a compose sequence to self._compose_sequences

        :param sequence: Keysyms of the compose sequence as written
                         in Compose files
        :param result: The result which should be inserted when typing that
                       compose sequence

        Examples:

        If a Compose file contains a line like:

            <Multi_key> <asciitilde> <dead_circumflex> <A> 	: "Ẫ"   U1EAA # LATIN CAPITAL LETTER A WITH CIRCUMFLEX AND TILDE

        Then “sequence” is “<Multi_key> <asciitilde> <dead_circumflex> <A>”
        (whitespace in the sequence string is ignored) and “result” is “Ẫ”.

        If conflicting compose sequences are added using this function,
        the sequence added last wins. For example wenn calling:

            _add_compose_sequence('<Multi_key> <t> <e> <s> <t>', '😇')
            _add_compose_sequence('<Multi_key> <t> <e> <s> <t> <s>', '😇')

        the sequence stored in self._compose_sequences is

            <Multi_key> <t> <e> <s> <t> <s> : "😇"

        and the previously stored shorter sequence

            <Multi_key> <t> <e> <s> <t> : "😇"

        has been deleted. When now calling

            _add_compose_sequence('<Multi_key> <t> <e> <s>', '😇')

        the sequence stored in self._compose_sequences is now

            <Multi_key> <t> <e> <s> : "😇"

        and both previously stored longer sequences have been deleted.
        I.e. the last stored sequence always wins in case of conflicts.

        It also implements this small syntax extension idea by Matthias Clasen:
        unwanted compose sequences can be removed by using an empty result
        string. I.e. if

            <Multi_key> <t> <e> <s> : ""

        comes last, the sequence <Multi_key> <t> <e> <s> and all
        longer sequences starting exactly like that become undefined.
        '''
        # pylint: enable=line-too-long
        names = re.sub(r'[<>\s]+', ' ', sequence).strip().split()
        keyvals = []
        for name in names:
            if re.match(r'U[0-9a-fA-F]{4,5}', name):
                code_point = int(name[1:], 16)
                if code_point > 0x7F: # above ASCII range
                    code_point += 0x01000000
                keyvals.append(code_point)
            else:
                try:
                    keyvals.append(getattr(IBus, f'KEY_{name}'))
                except AttributeError as error:
                    LOGGER.error(
                        'Invalid compose sequence. '
                        'keysym "%s" does not exist. %s: %s',
                        name, error.__class__.__name__, error)
                    return
        if not keyvals:
            return
        compose_sequences = self._compose_sequences
        if result == '':
            for keyval in keyvals:
                if keyval not in compose_sequences:
                    return
                if (isinstance(compose_sequences[keyval], str)
                    or len(compose_sequences[keyval]) == 1):
                    del compose_sequences[keyval]
                    return
                compose_sequences = compose_sequences[keyval]
            return
        for keyval in keyvals:
            if (keyval not in compose_sequences
                or isinstance(compose_sequences[keyval], str)):
                compose_sequences[keyval] = {}
            last_compose_sequences = compose_sequences
            last_keyval = keyval
            compose_sequences = compose_sequences[keyval]
        last_compose_sequences[last_keyval] = result

    def _xorg_locale_path(self) -> str: # pylint: disable=no-self-use
        '''Returns the name of the system directory for compose files.

        Usually this is “/usr/share/X11/locale”.
        '''
        return '/usr/share/X11/locale'

    def _locale_compose_file(self) -> str:
        '''Returns the full path of the default compose file for the current
        locale
        '''
        lc_ctype_locale, lc_ctype_encoding = locale.getlocale(
            category=locale.LC_CTYPE)
        if not lc_ctype_locale:
            lc_ctype_locale = 'en_US'
        if not lc_ctype_encoding:
            lc_ctype_encoding = 'UTF-8'
        if lc_ctype_encoding not in ('UTF-8', 'utf8'):
            LOGGER.warning('Not running in an UTF-8 locale: %s.%s',
                           lc_ctype_locale, lc_ctype_encoding)
        for loc in (lc_ctype_locale, 'en_US'):
            locale_compose_file = os.path.join(
                self._xorg_locale_path(), loc + '.UTF-8', 'Compose')
            if os.path.isfile(locale_compose_file):
                return locale_compose_file
        return ''

    def _read_compose_file(self, compose_path: str) -> None:
        '''Reads a compose file and stores the compose sequences
        found  there in self._compose_sequences.

        :param compose_path: Path to a compose file to read
        '''
        if not compose_path or not os.path.isfile(compose_path):
            LOGGER.info('Skipping reading of compose file "%s"', compose_path)
            return
        try:
            with open(compose_path,
                      encoding='UTF-8',
                      errors='ignore') as compose_file:
                lines = compose_file.readlines()
        except FileNotFoundError as error:
            LOGGER.exception('Error loading %s: %s: %s: %s',
                             compose_path, _('File not found'),
                             error.__class__.__name__, error)
        except PermissionError as error:
            LOGGER.exception('Error loading %s: %s: %s: %s',
                             compose_path, _('Permission error'),
                             error.__class__.__name__, error)
        except UnicodeDecodeError as error:
            LOGGER.exception('Error loading %s: %s: %s: %s',
                             compose_path, _('Unicode decoding error'),
                             error.__class__.__name__, error)
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception('Unexpected error loading %s: %s: %s: %s',
                             compose_path, _('Unknown error'),
                             error.__class__.__name__, error)
        if not lines:
            LOGGER.warning('File %s has no content', compose_path)
            return
        LOGGER.info('Reading compose file %s', compose_path)
        # For the syntax of the compose files see:
        # https://www.x.org/releases/X11R7.5/doc/man/man5/Compose.5.html
        # https://www.mankier.com/5/Compose
        include_pattern = re.compile(
            r'^\s*include\s*"(?P<include_path>[^"]+)".*')
        compose_sequence_pattern = re.compile(
            r'^\s*(?P<sequence>(<[a-zA-Z0-9_]+>\s*)+):'
            r'\s*"(?P<result>(\\"|[^"])*)".*')
        for line in lines:
            if not line.strip():
                continue
            match = include_pattern.search(line)
            if match:
                include_path = match.group('include_path')
                include_path = include_path.replace(
                    '%S', self._xorg_locale_path())
                include_path = include_path.replace(
                    '%L', self._locale_compose_file())
                include_path = include_path.replace(
                    '%H', os.path.expanduser('~'))
                include_path = os.path.normpath(include_path)
                self._read_compose_file(include_path)
            match = compose_sequence_pattern.search(line)
            if match:
                sequence = match.group('sequence')
                result = match.group('result')
                result = result.replace('\\"', '"')
                result = result.replace('\\\\', '\\')
                self._add_compose_sequence(sequence, result)

    def preedit_representation(self, keyvals: List[int]) -> str:
        # pylint: disable=line-too-long
        '''Returns a text to display in the preedit for a partially
        typed compose sequence.

        :param keyvals: A list of key values
        :return: The text to display in the preedit for a partially
                 typed compose sequence consisting of these key values

        Examples:

        >>> c = ComposeSequences()
        >>> c.preedit_representation([IBus.KEY_Multi_key, IBus.KEY_asciitilde, IBus.KEY_dead_circumflex])
        '~^'
        >>> c.preedit_representation([IBus.KEY_Multi_key, IBus.KEY_asciitilde, IBus.KEY_Multi_key, IBus.KEY_dead_circumflex])
        '~·^'
        >>> c.preedit_representation([IBus.KEY_Multi_key])
        '·'
        >>> c.preedit_representation([IBus.KEY_dead_macron])
        '¯'
        >>> c.preedit_representation([0x01EB])
        'ǫ'
        >>> c.preedit_representation([IBus.KEY_dead_macron, 0x01EB])
        '¯ǫ'
        >>> c.preedit_representation([IBus.KEY_1])
        '1'
        >>> c.preedit_representation([IBus.KEY_KP_1]) == c.preedit_representation([IBus.KEY_1])
        True
        >>> c.preedit_representation([IBus.KEY_slash])
        '/'
        >>> c.preedit_representation([IBus.KEY_KP_Divide]) == c.preedit_representation([IBus.KEY_slash])
        True
        >>> c.preedit_representation([IBus.KEY_space])
        ' '
        >>> c.preedit_representation([IBus.KEY_nobreakspace])
        ' '
        '''
        # pylint: enable=line-too-long
        representation = ''
        for keyval in keyvals:
            if keyval in self._preedit_representations:
                representation += self._preedit_representations[keyval]
            else:
                ibus_keyval_to_unicode = IBus.keyval_to_unicode(keyval)
                if ibus_keyval_to_unicode:
                    representation += ibus_keyval_to_unicode
                else:
                    representation += chr(keyval)
        if (len(representation) > 1
            and
            representation[0]
            == self._preedit_representations[IBus.KEY_Multi_key]):
            # Suppress the representation of the Multi_key at the
            # start of a sequence but only if more characters have
            # already been added to the sequence:
            return representation[1:]
        return representation

    def _compose_dead_key_sequence(
            self, keyvals: List[int]) -> Optional[str]:
        # pylint: disable=line-too-long
        '''
        Interprets a list of key values as a dead key sequence

        :param keyvals: A list of key values
        :return:
            None:
                Incomplete sequence
                The key values are not yet a complete dead key
                sequence, but it is still possible to get a
                dead key sequence by adding more key values.
            '' (empty string):
                Empty sequence or invalid sequence.
                Either the sequence is empty or
                there is no such dead key sequence, adding more
                key values could not make it a valid sequence.
            'text' (any non empty string):
                Complete dead key sequence, valid.
                The returned string contains the result of the valid
                dead key sequence.

        Examples:

        >>> c = ComposeSequences()

        Empty sequence:

        >>> c._compose_dead_key_sequence([])
        ''

        Incomplete sequences:

        >>> repr(c._compose_dead_key_sequence([IBus.KEY_dead_circumflex]))
        'None'

        >>> repr(c._compose_dead_key_sequence([IBus.KEY_dead_circumflex, IBus.KEY_dead_tilde]))
        'None'

        Invalid sequences:

        >>> c._compose_dead_key_sequence([IBus.KEY_dead_circumflex, IBus.KEY_Multi_key])
        ''

        >>> c._compose_dead_key_sequence([IBus.KEY_dead_circumflex, IBus.KEY_BackSpace])
        ''

        >>> c._compose_dead_key_sequence([IBus.KEY_dead_circumflex, IBus.KEY_openstar])
        ''

        Complete, valid sequences:

        >>> c._compose_dead_key_sequence([IBus.KEY_dead_circumflex, IBus.KEY_x])
        '\u0078\u0302'

        >>> c._compose_dead_key_sequence([IBus.KEY_dead_tilde, IBus.KEY_n])
        '\u00f1'

        >>> c._compose_dead_key_sequence([IBus.KEY_dead_macron, IBus.KEY_dead_abovedot, IBus.KEY_e])
        '\u0117\u0304'

        >>> c._compose_dead_key_sequence([IBus.KEY_dead_abovedot, IBus.KEY_dead_macron, IBus.KEY_e])
        '\u0113\u0307'

        >>> c._compose_dead_key_sequence([IBus.KEY_dead_belowdot, IBus.KEY_dead_abovedot, IBus.KEY_d])
        '\u1E0D\u0307'

        >>> c._compose_dead_key_sequence([IBus.KEY_dead_abovedot, IBus.KEY_dead_belowdot, IBus.KEY_d])
        '\u1E0D\u0307'

        >>> c._compose_dead_key_sequence([IBus.KEY_dead_abovedot, IBus.KEY_dead_belowdot, IBus.KEY_s])
        '\u1E69'

        >>> c._compose_dead_key_sequence([IBus.KEY_dead_belowdot, IBus.KEY_dead_abovedot, IBus.KEY_s])
        '\u1E69'

        >>> c._compose_dead_key_sequence([IBus.KEY_dead_doublegrave, IBus.KEY_Cyrillic_a])
        '\u0430\u030F'
        '''
        # pylint: enable=line-too-long
        if not keyvals:
            return ''
        combining_sequence = ''
        for index, keyval in enumerate(keyvals):
            if index < len(keyvals) - 1:
                if keyval not in self._dead_keys:
                    return '' # Invalid dead key sequence
                combining_sequence = self._dead_keys[
                    keyval] + combining_sequence
            else:
                if keyval in self._dead_keys:
                    return None # Incomplete sequence
                if len(keyvals) == 1:
                    return '' # Invalid dead key sequence
                character = IBus.keyval_to_unicode(keyval)
                if (not character
                    or unicodedata.category(character) not in ('Lu', 'Ll')):
                    return '' # Invalid dead key sequence
                combining_sequence = character + combining_sequence
        return unicodedata.normalize('NFC', combining_sequence)

    def is_start_key(self, keyval: int) -> bool:
        '''
        Checks whether a key with the value keyval starts Compose sequence

        :return: True if the key can start a Compose sequence, False if not
        '''
        return bool(keyval in self._compose_sequences)

    def compose(
            self,
            keyvals: List[int],
            keypad_fallback: bool = True) -> Optional[str]:
        # pylint: disable=line-too-long
        '''
        Interprets a list of key values as a compose sequence

        :param keyvals: A list of key values
        :param keypad_fallback: Whether fallbacks from KP_1 to 1,
                                KP_Divide to minus, ... (and the
                                (other way round) should be tried.
        :return:
            None:
                Incomplete sequence
                The key values are not yet a complete compose
                sequence, but it is still possible to get a
                complete compose sequence by adding more key values.
            '' (empty string):
                Empty sequence or invalid sequence.
                Either the sequence is empty or
                there is no such compose sequence, adding more
                key values could not make it a valid sequence.
            'text' (any non empty string):
                Complete sequence, valid.
                The returned string contains the result of the valid
                compose sequence.

        Examples:

        >>> c = ComposeSequences()

        Incomplete sequence:

        >>> repr(c.compose([IBus.KEY_Multi_key, IBus.KEY_asciitilde, IBus.KEY_dead_circumflex]))
        'None'

        Empty sequence:

        >>> c.compose([])
        ''

        Invalid sequence:

        >>> c._compose_dead_key_sequence([IBus.KEY_dead_circumflex, IBus.KEY_openstar])
        ''

        Complete, valid sequence:

        >>> c.compose([IBus.KEY_Multi_key, IBus.KEY_asciitilde, IBus.KEY_dead_circumflex, IBus.KEY_A])
        'Ẫ'

        Complete, valid sequence, with trailing junk (IBus.KEY_B is junk):

        >>> c.compose([IBus.KEY_Multi_key, IBus.KEY_asciitilde, IBus.KEY_dead_circumflex, IBus.KEY_A, IBus.KEY_B])
        'Ẫ'

        Not defined in any Compose file, but nevertheless valid
        because it is interpreted as a “reasonable” dead key sequence:

        >>> c.compose([IBus.KEY_dead_circumflex, IBus.KEY_x])
        '\u0078\u0302'

        With keypad_fallback this sequence exists:

        >>> c.compose([IBus.KEY_Multi_key, IBus.KEY_KP_1, IBus.KEY_KP_2], keypad_fallback=True)
        '½'

        Without keypad_fallback this sequence does not exist:

        >>> c.compose([IBus.KEY_Multi_key, IBus.KEY_KP_1, IBus.KEY_KP_2], keypad_fallback=False)
        ''
        '''
        # pylint: enable=line-too-long
        if not keyvals:
            return ''
        compose_sequences = self._compose_sequences
        for keyval in keyvals:
            if keyval in compose_sequences:
                if isinstance(compose_sequences[keyval], str):
                    return str(compose_sequences[keyval])
                compose_sequences = compose_sequences[keyval]
                continue
            if keypad_fallback and keyval in self._keypad_keyvals:
                fallback_keyval = self._keypad_keyvals[keyval]
                if fallback_keyval in compose_sequences:
                    if isinstance(compose_sequences[fallback_keyval], str):
                        return str(compose_sequences[fallback_keyval])
                    compose_sequences = compose_sequences[fallback_keyval]
                    continue
            if keypad_fallback and keyval in self._non_keypad_keyvals:
                fallback_keyval = self._non_keypad_keyvals[keyval]
                if fallback_keyval in compose_sequences:
                    if isinstance(compose_sequences[fallback_keyval], str):
                        return str(compose_sequences[fallback_keyval])
                    compose_sequences = compose_sequences[fallback_keyval]
                    continue
            # This sequence is not defined in any of the Compose
            # files read. In that sense it is an invalid sequence
            # and “return ''” would be appropriate here.  But
            # instead of just “return ''”, try whether it can be
            # interpreted as a “reasonable” dead key sequence:
            return self._compose_dead_key_sequence(keyvals)
        return None

    def lookup_representation(self, keyvals: List[int]) -> str:
        # pylint: disable=line-too-long
        '''Returns a string representation of a compose sequence

        :param keyvals: The compose sequence as a list of key values

        Useful to display a compose sequence in short and human
        readable form in a lookup table to show possible compose
        completions.

        Actually I would really like to use
        self.preedit_representation() for this, why introduce yet
        another function which does “almost” the same?

        The reasons for making a difference between preedit and lookup
        representation are:

        1) <space> and <nobreakspace>:
           Using ' ' as the preedit representation for
           <space> and ' ' for <nobreakspace> is perfectly fine.
           One knows which key one has just typed and one can also
           see that something happened in the preedit because
           the preedit is usually underlined. And such whitespace with
           an underline is visible feedback in the preedit.
           But in the lookup table it would be invisible.
           (By the way, the is <KP_Space> for? It exists in the
           system Compose file).

        2) <tilde> and <dead_tilde> and similar pairs:
           These are not the same thing in a compose sequence
           If the user has typed one of these, it is no problem if they are
           displayed the same way in the preedit, the user knows which key
           she pressed and then it represents that key well enough. But
           if it is shown in a lookup table to show possible completions,
           the user needs to know which key to press next, <tilde> or <dead_tilde>.
           Some keyboard layouts actually have both!
           (Alexander Graf suggested to make that differerence in the lookup
           table *only if* the current keyboard layout actually has both.
           I am thinking about that, I am not sure whether this is a good idea.)

        3) In the preedit representation, <1> and <KP_1> are both represented
           as '1', <slash> and <KP_Divide> are both represented as '/'.
           Again no problem if the user has just typed this, but a problem
           if one needs to know what to type next *exactly*. For example,
           the system Compose file contains:

           <Multi_key> <slash> <o>     : "ø"
           <Multi_key> <o> <slash>     : "ø"
           <Multi_key> <KP_Divide> <o> : "ø"

           but *not*:

           <Multi_key> <o> <KP_Divide> : "ø"

           So if the user has typed <Multi_key> <o>, the next key
           to complete the sequence can be <slash> but *not* <KP_Divide>!

           Similar situation for 1 and KP_1 and all other pairs of keys
           which have equivalents on the “normal” key area and the keypad.

           I tend to consider this bugs in the Compose file.

           Maybe I could avoid this by not displaying completions involving
           KP_something *at all*. Because most of these cases (maybe all cases?)
           the sequences can by typed in two different orders using the “normal”
           key area but only in one specific order using the keypad. I.e.
           showing the completions involving keypad keys adds only very
           little value. Therefore, I decided to omit them for the moment
           by calling self.find_compose_completions()
           with omit_sequences_involving_keypad=True.
           As long as I do this, 3) doesn’t matter.

        Examples:

        >>> c = ComposeSequences()
        >>> sequence = [IBus.KEY_Multi_key, IBus.KEY_dead_tilde, IBus.KEY_a]
        >>> c.lookup_representation(sequence)
        '·💀~a'

        >>> sequence = [IBus.KEY_Multi_key, IBus.KEY_dead_tilde, IBus.KEY_space]
        >>> c.lookup_representation(sequence)
        '·💀~␠'

        >>> c.lookup_representation([IBus.KEY_nobreakspace])
        'nobreakspace'

        >>> c.lookup_representation([IBus.KEY_1])
        '1'

        >>> c.lookup_representation([IBus.KEY_KP_1])
        'KP_1'
        >>> c.lookup_representation([IBus.KEY_KP_Divide])
        'KP_Divide'

        >>> c.lookup_representation([IBus.KEY_dead_macron])
        '💀¯'
        >>> c.lookup_representation([IBus.KEY_dead_macron, IBus.KEY_dead_ogonek])
        '💀¯💀˛'
        >>> c.lookup_representation([IBus.KEY_dead_macron, IBus.KEY_dead_ogonek, IBus.KEY_o])
        '💀¯💀˛o'
        >>> c.lookup_representation([0x01EB])
        'ǫ'
        >>> c.lookup_representation([IBus.KEY_dead_macron, 0x01EB])
        '💀¯ǫ'

        '''
        # pylint: enable=line-too-long
        representation = ''
        for keyval in keyvals:
            keyval_name = IBus.keyval_name(keyval)
            keyval_unicode = IBus.keyval_to_unicode(keyval)
            if keyval_name == 'Multi_key':
                representation += self._preedit_representations[keyval]
            elif keyval_name.startswith('dead_'):
                representation += '💀' + self._preedit_representations[keyval]
            elif keyval_name.startswith('KP_'):
                representation += IBus.keyval_name(keyval)
            elif keyval_name == 'space':
                representation += '␠'
            elif keyval_unicode and keyval_unicode.isspace():
                representation += IBus.keyval_name(keyval)
            elif keyval_unicode:
                representation += keyval_unicode
            else:
                representation += chr(keyval)
        return representation

    def _lookup_representations(
            self, keyval_sequences: List[List[int]]) -> List[str]:
        # pylint: disable=line-too-long
        '''Returns a list of string representations (for lookup tables) of
        compose sequences given as lists of key values

        This is only for testing self.find_compose_completions().

        :param keyval_sequences: A List containing lists of key values

        Examples:

        >>> c = ComposeSequences()
        >>> sequence1 = [IBus.KEY_Multi_key, IBus.KEY_minus]
        >>> sequence2 = [IBus.KEY_Multi_key, IBus.KEY_period]
        >>> keyval_sequences = [sequence1, sequence2]
        >>> c._lookup_representations(keyval_sequences)
        ['·-', '·.']

        '''
        # pylint: enable=line-too-long
        representations = []
        for keyval_sequence in keyval_sequences:
            representations.append(
                self.lookup_representation(keyval_sequence))
        return representations

    def list_compose_sequences(
            self,
            compose_sequences: Dict[int, Union[Dict[Any, Any], str]],
            partial_sequence: Optional[List[int]] = None,
            available_keyvals: Optional[Set[int]] = None,
            omit_sequences_involving_keypad: bool = True) -> List[List[int]]:
        '''Lists all possible compose sequences in a dictionary

        Returns a list of possible sequences, each sequence is a list
        of key values

        :param compose_sequences: The compose_sequences dictionary
                                  to check for possible sequences
        :param available_keyvals: The key values available to type
                                  compose sequences. Sequences from
                                  the compose_sequences dictionary
                                  which require key values not in this
                                  Set are not listed.
                                  If this parameter is None, *All*
                                  sequences in the compose_sequences
                                  dictionary are listed.
        :param omit_sequences_involving_keypad: Omit all sequences
                                                containing any
                                                keys on the keypad.
        '''
        if partial_sequence is None:
            partial_sequence = []
        possible_sequences: List[List[int]] = []
        for keyval in compose_sequences:
            if available_keyvals and keyval not in available_keyvals:
                continue
            if (omit_sequences_involving_keypad
                and IBus.keyval_name(keyval).startswith('KP_')):
                continue
            new_partial_sequence = partial_sequence + [keyval]
            value = compose_sequences[keyval]
            if isinstance(value, str):
                possible_sequences.append(new_partial_sequence)
            else:
                new_compose_sequence = value
                possible_sequences += self.list_compose_sequences(
                    new_compose_sequence,
                    partial_sequence = new_partial_sequence,
                    available_keyvals = available_keyvals)
        return possible_sequences

    def find_compose_completions(
            self,
            keyvals: List[int],
            available_keyvals: Optional[Set[int]] = None,
            omit_sequences_involving_keypad: bool = True) -> List[List[int]]:
        # pylint: disable=line-too-long
        '''Lists all possible compose sequences in the dictionary starting
        with keyvals using only available_keyvals to complete a
        sequence.

        Only the dictionary created from the Compose files read is
        considered, “automatic dead key sequences” are *not* included
        in the possible completions.

        :param kevals: The key values which started the compose sequence
        :param available_keyvals: The key values available to complete the
                                  compose sequence

        Examples:

        >>> c = ComposeSequences()
        >>> keyvals = [IBus.KEY_Multi_key, IBus.KEY_minus, IBus.KEY_minus]
        >>> available_keyvals = None
        >>> completions = c.find_compose_completions(keyvals, available_keyvals)
        >>> completions
        [[32], [45], [46]]
        >>> c._lookup_representations(completions)
        ['␠', '-', '.']

        >>> available_keyvals = set((IBus.KEY_Multi_key, IBus.KEY_minus, IBus.KEY_period))
        >>> completions = c.find_compose_completions(keyvals, available_keyvals)
        >>> c._lookup_representations(completions)
        ['-', '.']

        >>> keyvals = [IBus.KEY_Multi_key]
        >>> available_keyvals = set((IBus.KEY_macron, IBus.KEY_a, IBus.KEY_e, IBus.KEY_x))
        >>> completions = c.find_compose_completions(keyvals, available_keyvals)
        >>> completions
        [[97, 97], [97, 101], [101, 101], [120, 120], [175, 97], [175, 101]]

        >>> c._lookup_representations(completions)
        ['aa', 'ae', 'ee', 'xx', '¯a', '¯e']

        As automatic dead key sequences should not be included,
        ['x'] should not appear as a possible completion here:

        >>> keyvals = [IBus.KEY_dead_grave]
        >>> available_keyvals = [IBus.KEY_a, IBus.KEY_x]
        >>> completions = c.find_compose_completions(keyvals, available_keyvals)
        >>> c._lookup_representations(completions)
        ['a']

        >>> keyvals = [IBus.KEY_Multi_key, IBus.KEY_asciicircum]
        >>> available_keyvals = [IBus.KEY_3, IBus.KEY_KP_3]
        >>> completions = c.find_compose_completions(keyvals, available_keyvals)
        >>> c._lookup_representations(completions)
        ['3']
        >>> completions = c.find_compose_completions(keyvals, available_keyvals, omit_sequences_involving_keypad=False)
        >>> c._lookup_representations(completions)
        ['3', 'KP_3']
        '''
        # pylint: enable=line-too-long
        if not keyvals:
            return []
        compose_sequences = self._compose_sequences
        for keyval in keyvals:
            if keyval not in compose_sequences:
                # No completion possible, it’s invalid:
                return []
            compose_sequences = compose_sequences[keyval]
            if isinstance(compose_sequences, str):
                # It is already complete:
                return []
        sequences = self.list_compose_sequences(
            compose_sequences,
            partial_sequence = [],
            available_keyvals = available_keyvals,
            omit_sequences_involving_keypad = omit_sequences_involving_keypad)
        return sorted(sequences,
                      key=lambda x: (
                          len(x),
                          x
                      ))

class M17nDbInfo:
    '''Class to find and store information about the available input
    methods from m17n-db.
    '''
    def __init__(self) -> None:
        self._dirs: List[str] = []
        self._imes: Dict[str, Dict[str, str]] = {}
        self._version: str = ''
        self._major_version: int = 0
        self._minor_version: int = 0
        self._micro_version: int = 0
        self._get_version()
        self._find_dirs()
        self._find_imes()

    def _get_version(self) -> None:
        '''Gets the version of m17n-db'''
        m17n_db_binary = shutil.which('m17n-db')
        self._version = ''
        if m17n_db_binary:
            try:
                result = subprocess.run(
                    [m17n_db_binary, '-v'],
                    encoding='utf-8', check=True, capture_output=True)
                self._version = result.stdout.strip()
                LOGGER.info('%s printed: %s', m17n_db_binary, self._version)
            except FileNotFoundError as error:
                LOGGER.exception(
                    'Exception when calling %s: %s: %s',
                    m17n_db_binary, error.__class__.__name__, error)
            except subprocess.CalledProcessError as error:
                LOGGER.exception(
                    'Exception when calling %s: %s: %s stderr: %s',
                    m17n_db_binary,
                    error.__class__.__name__, error, error.stderr)
            except Exception as error: # pylint: disable=broad-except
                LOGGER.exception(
                    'Exception when calling %s: %s: %s',
                    m17n_db_binary, error.__class__.__name__, error)
        if self._version:
            (major, minor, micro) = self._version.split('.')
            self._major_version = int(major)
            self._minor_version = int(minor)
            self._micro_version = int(micro)

    def _find_dirs(self) -> None:
        '''Finds the directories which contain the m17n input methods which
        can be used and stores the result in self._dirs
        '''
        self._dirs = []
        user_dir = os.getenv('M17NDIR')
        if not user_dir:
            user_dir = os.path.expanduser('~/.m17n.d')
        system_dir = ''
        m17n_db_binary = shutil.which('m17n-db')
        if m17n_db_binary:
            try:
                result = subprocess.run(
                    [m17n_db_binary],
                    encoding='utf-8', check=True, capture_output=True)
                system_dir = result.stdout.strip()
                LOGGER.info('%s printed: %s', m17n_db_binary, system_dir)
            except FileNotFoundError as error:
                LOGGER.exception(
                    'Exception when calling %s: %s: %s',
                    m17n_db_binary, error.__class__.__name__, error)
            except subprocess.CalledProcessError as error:
                LOGGER.exception(
                    'Exception when calling %s: %s: %s stderr: %s',
                    m17n_db_binary,
                    error.__class__.__name__, error, error.stderr)
            except Exception as error: # pylint: disable=broad-except
                LOGGER.exception(
                    'Exception when calling %s: %s: %s',
                    m17n_db_binary, error.__class__.__name__, error)
        if not os.path.isdir(system_dir):
            dirnames = (
                '/usr/share/m17n',
                '/usr/local/share/m17n', # On FreeBSD, the .mim files are here
            )
            for dirname in dirnames:
                if os.path.isdir(dirname):
                    system_dir = dirname
                    break
        if os.path.isdir(user_dir):
            self._dirs.append(user_dir)
        if os.path.isdir(system_dir):
            self._dirs.append(system_dir)
        else:
            LOGGER.error(
                'System m17n directory "%s" does not exist.', system_dir)

    def _find_imes(self) -> None:
        '''Searches the directories in self._dirs for usable input methods and
        stores information about the input methods found in the
        self._imes dictionary.
        '''
        self._imes = {}
        self._imes['NoIME'] = {
            'path': '',
            'title': _('Native Keyboard'),
            'description': _(
                'Direct keyboard input. This is not really an input method, '
                'it uses directly whatever comes from '
                'the current keyboard layout '
                'without any further changes. '
                'So no transliteration or composing '
                'is done here.'),
            'content': '',
            'icon': os.path.join(
                itb_version.get_prefix(),
                'share/icons/hicolor/48x48/apps/ibus-typing-booster.png'),
            }
        for dirname in self._dirs:
            for mim_path in glob.glob(os.path.join(dirname, '*.mim')):
                try:
                    with open(mim_path,
                              encoding='UTF-8',
                              errors='ignore') as ime_file:
                        full_contents = ime_file.read()
                except FileNotFoundError as error:
                    LOGGER.exception('Error loading %s: %s: %s: %s',
                                     mim_path, _('File not found'),
                                     error.__class__.__name__, error)
                except PermissionError as error:
                    LOGGER.exception('Error loading %s: %s: %s: %s',
                                     mim_path, _('Permission error'),
                                     error.__class__.__name__, error)
                except UnicodeDecodeError as error:
                    LOGGER.exception('Error loading %s: %s: %s: %s',
                                     mim_path, _('Unicode decoding error'),
                                     error.__class__.__name__, error)
                except Exception as error: # pylint: disable=broad-except
                    LOGGER.exception('Unexpected error loading %s: %s: %s: %s',
                                     mim_path, _('Unknown error'),
                                     error.__class__.__name__, error)
                if not full_contents:
                    LOGGER.warning('File %s has no content', mim_path)
                    continue
                input_method_pattern = re.compile(
                    r'\(\s*input-method\s+'
                    r'(?P<lang>.+?)\s+(?P<name>.+?)[\s()]+',
                    re.DOTALL|re.MULTILINE|re.UNICODE)
                match = input_method_pattern.search(full_contents)
                if not match:
                    LOGGER.warning(
                        'File %s does not contain “input-method”',
                        mim_path)
                    continue
                lang = match.group('lang')
                name = match.group('name')
                if name == 'nil':
                    LOGGER.info(
                        'File %s has name “nil”.'
                        'Therefore, it is not actually an input method.',
                        mim_path)
                    continue
                ime = lang + '-' + name
                if ime in self._imes:
                    LOGGER.warning(
                        'Duplicate input method: “%s”.'
                        'Implemented in %s and %s.',
                        ime, mim_path, self._imes[ime]['path'])
                    continue
                self._imes[ime] = {'path': mim_path}
                icon_path_long = os.path.join(
                    dirname, 'icons', lang + '-' + name + '.png')
                icon_path_short = os.path.join(
                    dirname, 'icons', name + '.png')
                if os.path.isfile(icon_path_long):
                    self._imes[ime]['icon'] = icon_path_long
                elif os.path.isfile(icon_path_short):
                    self._imes[ime]['icon'] = icon_path_short
                if 'icon' not in self._imes[ime]:
                    LOGGER.warning(
                        'No icon found for input method: “%s”. '
                        'Neither file %s nor %s exist.',
                        ime, icon_path_long, icon_path_short)
                title_pattern = re.compile(
                    r'\([\s]*title[\s]*"(?P<title>.+?)(?<!\\)"[\s]*\)',
                    re.DOTALL|re.MULTILINE|re.UNICODE)
                match = title_pattern.search(full_contents)
                if match:
                    title = match.group('title').replace('\\"', '"')
                    self._imes[ime]['title'] = title
                description_pattern = re.compile(
                    r'\([\s]*description[\s]*'
                    r'(\(_)?"(?P<description>.+?)(?<!\\)"[\s]*\)',
                    re.DOTALL|re.MULTILINE|re.UNICODE)
                match = description_pattern.search(full_contents)
                if match:
                    description = match.group('description').replace(
                        '\\"', '"')
                    self._imes[ime]['description'] = description
                self._imes[ime]['content'] = full_contents

    def get_version(self) -> str:
        '''Returns the version of m17n-db'''
        return self._version

    def get_major_version(self) -> int:
        '''Returns the major version of m17n-db as an integer'''
        return self._major_version

    def get_minor_version(self) -> int:
        '''Returns the major version of m17n-db as an integer'''
        return self._minor_version

    def get_micro_version(self) -> int:
        '''Returns the major version of m17n-db as an integer'''
        return self._micro_version

    def get_dirs(self) -> List[str]:
        '''
        Returns the list of directories  which contain the m17n input methods.

        There has to be one system directory (e.g. /usr/share/m17n) and
        it is possible that there is also a user directory indicated
        by the M17NDIR environment variable. If the environment
        variable M17NDIR is not set, the user directory is '~/.m17n.d'.
        if that directory exists.

        :return: A list of one or two directories

        '''
        return self._dirs[:]

    def get_imes(self) -> List[str]:
        '''Get a list of the available input methods

        The special input method 'NoIME' should always be first
        in the list returned.

        :return: A list of names of the available input methods.
        '''
        return sorted(self._imes)

    def get_path(self, ime: str) -> str:
        '''Get the full path of the implementation file of the input method.

        :param ime: Name of the input method
        :return: Path of the implementation file of the input method.
                 Empty string if no file has been found implementing “ime”
        '''
        if ime in self._imes and 'path' in self._imes[ime]:
            return self._imes[ime]['path']
        return ''

    def get_title(self, ime: str) -> str:
        '''Get the title of the input method.

        :param ime: Name of the input method
        :return: Title of the input method.
                 Empty string if no title has been found.
        '''
        if ime in self._imes and 'title' in self._imes[ime]:
            return self._imes[ime]['title']
        return ''

    def get_description(self, ime: str) -> str:
        '''Get the description of the input method.

        :param ime: Name of the input method
        :return: Description of the input method.
                 Empty string if no description has been found.
        '''
        if ime in self._imes and 'description' in self._imes[ime]:
            return self._imes[ime]['description']
        return ''

    def get_content(self, ime: str) -> str:
        '''Get the content of the implementation file of the input method.

        :param ime: Name of the input method
        :return: Content of the implementation file of the input method.
                 Empty string if no content has been found.
        '''
        if ime in self._imes and 'content' in self._imes[ime]:
            return self._imes[ime]['content']
        return ''

    def get_icon(self, ime: str) -> str:
        '''Get the full path of the icon file of the input method.

        :param ime: Name of the input method
        :return: Path of the icon file of the input method.
                 Empty string if no icon file has been found.
        '''
        if ime in self._imes and 'icon' in self._imes[ime]:
            return self._imes[ime]['icon']
        return ''

    def __str__(self) -> str:
        return repr(self._imes)

def xdg_save_data_path(*resource: str) -> str:
    '''
    Compatibility function for systems which do not have pyxdg.
    (For example openSUSE Leap 42.1)
    '''
    # if IMPORT_XDG_BASEDIRECTORY_SUCCESSFUL:
    #    return xdg.BaseDirectory.save_data_path(*resource)
    #
    # xdg.BaseDirectory.save_data_path(*resource) unfortunately
    # can fail because it calls os.makedirs() without the exist_ok=True
    # option, and then os.makedirs() can fail in a race condition
    # (see: https://bugs.python.org/issue1675)
    #
    # Replicate implementation of xdg.BaseDirectory.save_data_path
    # here (and add the exist_ok=True parameter to os.makedirs()):
    xdg_data_home = os.environ.get('XDG_DATA_HOME') or os.path.join(
        os.path.expanduser('~'), '.local', 'share')
    resource_joined = os.path.join(*resource)
    assert not resource_joined.startswith('/')
    path = os.path.join(xdg_data_home, resource_joined)
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    return path

class KeyvalsToKeycodes:
    '''Class to convert key values to key codes.

    Key values (Key symbols) are the codes which are sent whenever a
    key is pressed or released.

    Key codes are identifying numbers for physical keys.

    The mapping from key values to key codes is usually not bijective,
    a key value can be generated from different key codes (if that same value
    is mapped to different hardware keys in the keyboard layout)
    and a certain hardware key with a certain key code can generate different
    key values depending on which modifier was pressed.
    '''
    def __init__(self) -> None:
        self.keyvals_to_keycodes: Dict[int, List[int]] = {}
        display = None
        keymap = None
        display = Gdk.Display.get_default()
        if not display:
            LOGGER.warning('Gdk.Display.get_default() returned %s', display)
        else:
            keymap = Gdk.Keymap.get_for_display(display)
        if not keymap:
            LOGGER.warning('Could not get keymap')
        else:
            for keycode in range(0, 256):
                (keycode_found,
                 dummy_keymapkeys,
                 keyvals) = Gdk.Keymap.get_entries_for_keycode(keymap, keycode)
                if keycode_found:
                    for keyval in keyvals:
                        if keyval:
                            if (keyval in self.keyvals_to_keycodes
                                and
                                keycode
                                not in self.keyvals_to_keycodes[keyval]):
                                self.keyvals_to_keycodes[keyval].append(
                                    keycode)
                            else:
                                self.keyvals_to_keycodes[keyval] = [keycode]
        # Gdk.Keymap.get_entries_for_keycode() seems to never find any
        # key codes on big endian platforms (s390x). Might be a bug in
        # that function. Until I figure out what the problem really
        # is, fall back to the standard us layout for the most
        # important key values:
        self._std_us_keyvals_to_keycodes = {
            IBus.KEY_Left: [113],
            IBus.KEY_BackSpace: [22],
            IBus.KEY_a: [38],
        }
        for keyval, keycodes in self._std_us_keyvals_to_keycodes.items():
            if keyval not in self.keyvals_to_keycodes:
                LOGGER.warning('No keycodes found: keyval: %s name: %s',
                               keyval, IBus.keyval_name(keyval))
                self.keyvals_to_keycodes[keyval] = keycodes

    def keyvals(self) -> Set[int]:
        '''Returns the Set of keyvals available on the keyboard layout'''
        return set(self.keyvals_to_keycodes.keys())

    def keycodes(self, keyval: int) -> List[int]:
        '''Returns a list of key codes of the hardware keys which can generate
        the given key value on the current keyboard layout.

        :param keyval: A key value
        :return: A list of key codes of hardware keys, possibly empty
        '''
        if keyval in self.keyvals_to_keycodes:
            return self.keyvals_to_keycodes[keyval]
        return []

    def keycode(self, keyval: int) -> int:
        '''Returns one key code of one hardware key which can generate the
        given key value (there may be more than one, see the
        keycodes() function.

        :param keyval: A key value
        :return: One key code of a hardware key which can generate
                 the given key value, between 9 and 255
        '''
        keycodes = self.keycodes(keyval)
        if keycodes:
            return keycodes[0]
        return 0

    def ibus_keycodes(self, keyval: int) -> List[int]:
        '''Returns a list of ibus key codes of the hardware keys which can
        generate the given key value on the current keyboard layout.

        ibus key codes are calculated by subtracting 8 from the
        “normal” key codes.  The smallest possible keycode seems to be
        9 (usually mapped to Escape).  Therefore, after subtracting 8
        it is at least 1.

        :param keyval: A key value
        :return: A list of ibus key codes of hardware keys, possibly empty
                 The key codes are between 1 and 247
        '''
        if keyval in self.keyvals_to_keycodes:
            return [max(0, x - 8) for x in self.keyvals_to_keycodes[keyval]]
        return []

    def ibus_keycode(self, keyval: int) -> int:
        '''Returns one ibus key code of one hardware key which can generate
        the given key value (there may be more than one, see the
        ibus_keycodes() function)

        ibus key codes are calculated by subtracting 8 from the
        “normal” key codes.  The smallest possible keycode seems to be
        9 (usually mapped to Escape).  Therefore, after subtracting 8
        it is at least 1.

        :param keyval: A key value
        :return: One ibus key code of a hardware key which can generate
                 the given key value. It will be between 1 and 247.
        '''
        return max(0, self.keycode(keyval) - 8)

    def __str__(self) -> str:
        return_string = ''
        for keyval in sorted(self.keyvals_to_keycodes):
            return_string += (
                f'keyval: {keyval} '
                f'name: {IBus.keyval_name(keyval)} '
                f'keycodes: {self.keyvals_to_keycodes[keyval]}\n')
        return return_string

class KeyEvent:
    '''Key event class used to make the checking of details of the key
    event easy
    '''
    def __init__(self, keyval: int, keycode: int, state: int) -> None:
        self.val = keyval
        self.code = keycode
        self.state = state
        self.name = IBus.keyval_name(self.val)
        if re.match(r'U\+[0-9a-fA-F]{4,5}', self.name):
            # Older versions of ibus produce
            #
            # >>> IBus.keyval_name(0x0100263a)
            # 'U+263A'
            #
            # Convert this into the same name used by newere
            # versions of ibus which is:
            #
            # >>> IBus.keyval_name(0x0100263a)
            # '0x100263a'
            #
            # to make it possible for me to always work
            # with the same names, no matter the ibus version
            self.name = f'0x{0x1000000  + int(self.name[2:], 16):x}'
        self.unicode = IBus.keyval_to_unicode(self.val)
        self.msymbol = self.unicode
        if self.msymbol == '\r':
            # https://github.com/mike-fabian/ibus-typing-booster/issues/457
            self.msymbol = self.name # “Return”
        self.shift = self.state & IBus.ModifierType.SHIFT_MASK != 0
        self.lock = self.state & IBus.ModifierType.LOCK_MASK != 0
        self.control = self.state & IBus.ModifierType.CONTROL_MASK != 0
        self.super = self.state & IBus.ModifierType.SUPER_MASK != 0
        self.hyper = self.state & IBus.ModifierType.HYPER_MASK != 0
        self.meta = self.state & IBus.ModifierType.META_MASK != 0
        # mod1: Usually Alt_L (0x40),  Alt_R (0x6c),  Meta_L (0xcd)
        self.mod1 = self.state & IBus.ModifierType.MOD1_MASK != 0
        # mod2: Usually Num_Lock (0x4d)
        self.mod2 = self.state & IBus.ModifierType.MOD2_MASK != 0
        # mod3: Usually Scroll_Lock
        self.mod3 = self.state & IBus.ModifierType.MOD3_MASK != 0
        # mod4: Usually Super_L (0xce),  Hyper_L (0xcf)
        self.mod4 = self.state & IBus.ModifierType.MOD4_MASK != 0
        # mod5: ISO_Level3_Shift (0x5c),  Mode_switch (0xcb)
        self.mod5 = self.state & IBus.ModifierType.MOD5_MASK != 0
        self.button1 = self.state & IBus.ModifierType.BUTTON1_MASK != 0
        self.button2 = self.state & IBus.ModifierType.BUTTON2_MASK != 0
        self.button3 = self.state & IBus.ModifierType.BUTTON3_MASK != 0
        self.button4 = self.state & IBus.ModifierType.BUTTON4_MASK != 0
        self.button5 = self.state & IBus.ModifierType.BUTTON5_MASK != 0
        self.release = self.state & IBus.ModifierType.RELEASE_MASK != 0
        # MODIFIER_MASK: Modifier mask for the all the masks above
        self.modifier = self.state & IBus.ModifierType.MODIFIER_MASK != 0
        if is_ascii(self.msymbol):
            if self.control:
                self.msymbol = 'C-' + self.msymbol
            if self.mod1:
                self.msymbol = 'A-' + self.msymbol
            if self.mod5:
                self.msymbol = 'G-' + self.msymbol
            if (self.shift
                and (self.unicode.isspace() or not self.unicode.isprintable())):
                # (Python has no “isgraph()”, but “isspace() or not isprintable()”
                # does the same as “not isgraph()”.
                #
                # This makes sure that if self.msymbol == 'C-Return'
                # it is changed into 'S-C-Return' (See:
                # https://github.com/mike-fabian/ibus-typing-booster/issues/457)
                # and if self.msymbol == ' ' it is changed into 'S- '
                # (See:
                # https://github.com/mike-fabian/ibus-typing-booster/issues/457)
                # and also other similar cases. There are already .mim
                # files using 'S- ', 'S-C-Return, 'S-Left', and
                # 'S-Right' in m17n-db. Others like 'S-Up', 'S-Down',
                # ... might make sense too. I think that always, when
                # the Unicode value is white space or not printable
                # adding the 'S-' to the msymbol when Shift is pressed
                # is the right thing to do.  But when the character is
                # printable and not white space, for example Ü
                # (self.name == 'Udiaeresis'), then adding the 'S-' is
                # wrong. Pressing Shift+ü generates an uppercase Ü,
                # the Shift has been “absorbed” in making the
                # character uppercase, adding an extra 'S-' to the
                # msymbol is then wrong.
                self.msymbol = 'S-' + self.msymbol
        self.time: float = 0.0
        # Whether the key has been handled by do_process_key_event
        # (i.e. True was returned) or passed through (i.e. “return
        # False” was used or the key was forwarded with
        # forward_key_event()). This is used to avoid passing through
        # a release key if the corresponding press key has been
        # handled.
        self.handled: bool = False
        # Whether the key was translated to an IBus keymap. This might
        # be useful to prefer forward_key_event() over `return False`
        # when the key was translated to an IBus keymap.
        self.translated: bool = False

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KeyEvent):
            return NotImplemented
        if (self.val == other.val
                and self.code == other.code
                and self.state == other.state):
            return True
        return False

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, KeyEvent):
            return NotImplemented
        if (self.val != other.val
                or self.code != other.code
                or self.state != other.state):
            return True
        return False

    def __str__(self) -> str:
        return repr(
            f'val={self.val:08x} '
            f'code={self.code} '
            f'state=0x{self.state:08x} '
            f'name=“{self.name}” '
            f'unicode=“{self.unicode}” '
            f'msymbol=“{self.msymbol}” '
            f'shift={self.shift} '
            f'lock={self.lock} '
            f'control={self.control} '
            f'super={self.super} '
            f'hyper={self.hyper} '
            f'meta={self.meta} '
            f'mod1={self.mod1} '
            f'mod2={self.mod2} '
            f'mod3={self.mod3} '
            f'mod4={self.mod4} '
            f'mod5={self.mod5} '
            f'button1={self.button1} '
            f'button2={self.button2} '
            f'button3={self.button3} '
            f'button4={self.button4} '
            f'button5={self.button5} '
            f'release={self.release} '
            f'modifier={self.modifier} '
            f'time={self.time} '
            f'handled={self.handled} '
            f'translated={self.translated}')

def keyevent_to_keybinding(keyevent: KeyEvent) -> str:
    # pylint: disable=line-too-long
    '''Calculates a keybinding string from a key event.

    Examples:

    >>> keyevent_to_keybinding(KeyEvent(IBus.KEY_Left, 0, 0))
    'Left'

    >>> keyevent_to_keybinding(KeyEvent(0x0100263a, 0, 0))
    '0x100263a'

    >>> keyevent_to_keybinding(KeyEvent(0x0101F923, 0, 0))
    '0x101f923'

    >>> keyevent_to_keybinding(KeyEvent(IBus.KEY_Left, 0, IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK))
    'Shift+Control+Left'

    >>> keyevent_to_keybinding(KeyEvent(0x0100263A, 0, IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK))
    'Shift+Control+0x100263a'

    >>> keyevent_to_keybinding(KeyEvent(0x0101F923, 0, IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK))
    'Shift+Control+0x101f923'
    '''
    # pylint: enable=line-too-long
    keybinding = ''
    if keyevent.shift:
        keybinding += 'Shift+'
    if keyevent.lock:
        keybinding += 'Lock+'
    if keyevent.control:
        keybinding += 'Control+'
    if keyevent.super:
        keybinding += 'Super+'
    if keyevent.hyper:
        keybinding += 'Hyper+'
    if keyevent.meta:
        keybinding += 'Meta+'
    if keyevent.mod1:
        keybinding += 'Mod1+'
    if keyevent.mod2:
        keybinding += 'Mod2+'
    if keyevent.mod3:
        keybinding += 'Mod3+'
    if keyevent.mod4:
        keybinding += 'Mod4+'
    if keyevent.mod5:
        keybinding += 'Mod5+'
    keybinding += keyevent.name
    return keybinding

def keybinding_to_keyevent(keybinding: str) -> KeyEvent:
    # pylint: disable=line-too-long
    '''Returns a key event object created from a key binding string.

    Examples:

    >>> keybinding_to_keyevent('Shift+Control+Left').val == IBus.KEY_Left
    True

    >>> keybinding_to_keyevent('Shift+Control+Left').name
    'Left'

    >>> keybinding_to_keyevent('Shift+Control+Left').state == IBus.ModifierType.SHIFT_MASK | IBus.ModifierType.CONTROL_MASK
    True

    >>> f"0x{keybinding_to_keyevent('Shift+Control+0x100263a').val:08x}"
    '0x0100263a'

    >>> f"0x{keybinding_to_keyevent('Shift+Control+0x101F923').val:08x}"
    '0x0101f923'

    >>> f"0x{keybinding_to_keyevent('Shift+Control+0x101G923').val:08x}"
    '0x00ffffff'

    >>> keybinding_to_keyevent('Shift+Control+0x101G923').val == IBus.KEY_VoidSymbol
    True
    '''
    # pylint: enable=line-too-long
    name = keybinding.split('+')[-1]
    keyval = IBus.keyval_from_name(name)
    if keyval == IBus.KEY_VoidSymbol and re.match(r'0x10[0-9a-fA-F]{5}', name):
        keyval = int(name[2:], 16)
    state = 0
    if 'Shift+' in keybinding:
        state |= IBus.ModifierType.SHIFT_MASK
    if 'Lock+' in keybinding:
        state |= IBus.ModifierType.LOCK_MASK
    if 'Control+' in keybinding:
        state |= IBus.ModifierType.CONTROL_MASK
    if 'Super+' in keybinding:
        state |= IBus.ModifierType.SUPER_MASK
    if 'Hyper+' in keybinding:
        state |= IBus.ModifierType.HYPER_MASK
    if 'Meta+' in keybinding:
        state |= IBus.ModifierType.META_MASK
    if 'Mod1+' in keybinding:
        state |= IBus.ModifierType.MOD1_MASK
    if 'Mod2+' in keybinding:
        state |= IBus.ModifierType.MOD2_MASK
    if 'Mod3+' in keybinding:
        state |= IBus.ModifierType.MOD3_MASK
    if 'Mod4+' in keybinding:
        state |= IBus.ModifierType.MOD4_MASK
    if 'Mod5+' in keybinding:
        state |= IBus.ModifierType.MOD5_MASK
    return KeyEvent(keyval, 0, state)

class HotKeys:
    '''Class to make checking whether a key matches a hotkey for a certain
    command easy
    '''
    def __init__(self, keybindings: Dict[str, List[str]]) -> None:
        self._hotkeys: Dict[str, List[Tuple[int, int]]] = {}
        for command in keybindings:
            for keybinding in keybindings[command]:
                key = keybinding_to_keyevent(keybinding)
                val = key.val
                state = key.state & KEYBINDING_STATE_MASK
                if command in self._hotkeys:
                    self._hotkeys[command].append((val, state))
                else:
                    self._hotkeys[command] = [(val, state)]

    def __contains__(
            self, command_key_tuple: Tuple[KeyEvent, KeyEvent, str]) -> bool:
        if not isinstance(command_key_tuple, tuple):
            return False
        command = command_key_tuple[2]
        key = command_key_tuple[1]
        prev_key = command_key_tuple[0]
        if prev_key is None:
            # When ibus-typing-booster has just started and the very first key
            # is pressed prev_key is not yet set. In that case, assume
            # that it is the same as the current key:
            prev_key = key
        val = key.val
        state = key.state # Do not change key.state, only the copy!
        if key.name in ('Shift_L', 'Shift_R',
                        'Control_L', 'Control_R',
                        'Alt_L', 'Alt_R',
                        'Meta_L', 'Meta_R',
                        'Super_L', 'Super_R',
                        'ISO_Level3_Shift'):
            # For these modifier keys, match on the release event
            # *and* make sure that the previous key pressed was
            # exactly the same key. Then we know that for example only
            # Shift_L was pressed and then released with nothing in
            # between.  For example it could not have been something
            # like “Shift_L” then “a” followed by releasing the “a”
            # and the “Shift_L”.
            if (prev_key.val != val
                or not state & IBus.ModifierType.RELEASE_MASK):
                return False
            state &= ~IBus.ModifierType.RELEASE_MASK
            if key.name in ('Shift_L', 'Shift_R'):
                state &= ~IBus.ModifierType.SHIFT_MASK
            elif key.name in ('Control_L', 'Control_R'):
                state &= ~IBus.ModifierType.CONTROL_MASK
            elif key.name in ('Alt_L', 'Alt_R'):
                state &= ~IBus.ModifierType.MOD1_MASK
            elif key.name in ('Super_L', 'Super_R'):
                state &= ~IBus.ModifierType.SUPER_MASK
                state &= ~IBus.ModifierType.MOD4_MASK
            elif key.name in ('Meta_L', 'Meta_R'):
                state &= ~IBus.ModifierType.META_MASK
                state &= ~IBus.ModifierType.MOD1_MASK
            elif key.name in ('ISO_Level3_Shift',):
                state &= ~IBus.ModifierType.MOD5_MASK
        state = state & KEYBINDING_STATE_MASK
        if command in self._hotkeys:
            if (val, state) in self._hotkeys[command]:
                return True
        return False

    def __str__(self) -> str:
        return repr(self._hotkeys)

class ItbKeyInputDialog(Gtk.MessageDialog): # type: ignore
    '''
    A dialog to enter a key or a key combination to be used as a
    key binding for a command.
    '''
    def __init__(
            self,
            # Translators: This is used in the title bar of a dialog window
            # requesting that the user types a key to be used as a new
            # key binding for a command.
            title: str = _('Key input'),
            parent: Gtk.Window = None) -> None:
        Gtk.MessageDialog.__init__(
            self,
            title=title,
            parent=parent)
        self.add_button(_('Cancel'), Gtk.ResponseType.CANCEL)
        self.set_modal(True)
        self.set_markup(
            '<big><b>%s</b></big>' # pylint: disable=consider-using-f-string
            # Translators: This is from the dialog to enter a key or a
            # key combination to be used as a key binding for a
            # command.
            % _('Please press a key (or a key combination)'))
        self.format_secondary_text(
            # Translators: This is from the dialog to enter a key or a
            # key combination to be used as a key binding for a
            # command.
            _('The dialog will be closed when the key is released'))
        self.connect('key_press_event', self.on_key_press_event)
        self.connect('key_release_event', self.on_key_release_event)
        if parent:
            self.set_transient_for(parent.get_toplevel())
        self.show()

    @staticmethod
    def on_key_press_event(
            widget: Gtk.MessageDialog, event: Gdk.EventKey) -> bool:
        '''Called when a key is pressed'''
        widget.e = (event.keyval,
                    event.get_state() & KEYBINDING_STATE_MASK)
        return True

    @staticmethod
    def on_key_release_event(
            widget: Gtk.MessageDialog, _event: Gdk.EventKey) -> bool:
        '''Called when a key is released'''
        widget.response(Gtk.ResponseType.OK)
        return True

class ItbAboutDialog(Gtk.AboutDialog): # type: ignore
    '''
    The “About” dialog for Typing Booster
    '''
    def  __init__(self, parent: Gtk.Window = None) -> None:
        Gtk.AboutDialog.__init__(self, parent=parent)
        self.set_modal(True)
        # An empty string in aboutdialog.set_logo_icon_name('')
        # prevents an ugly default icon to be shown. We don’t yet
        # have nice icons for ibus-typing-booster.
        self.set_logo_icon_name('')
        self.set_title(
            f'🚀 ibus-typing-booster {itb_version.get_version()}')
        self.set_program_name(
            '🚀 ibus-typing-booster')
        self.set_version(itb_version.get_version())
        self.set_comments(
            _('A completion input method to speedup typing.'))
        self.set_copyright(
            'Copyright © 2012–2023 Mike FABIAN')
        self.set_authors([
            'Mike FABIAN <maiku.fabian@gmail.com>',
            'Anish Patil <anish.developer@gmail.com>',
            ])
        self.set_translator_credits(
            # Translators: put your names here, one name per line.
            _('translator-credits'))
        # self.set_artists('')
        self.set_documenters([
            'Mike FABIAN <maiku.fabian@gmail.com>',
            ])
        self.set_website(
            'http://mike-fabian.github.io/ibus-typing-booster')
        self.set_website_label(
            _('Online documentation:')
            + ' ' + 'http://mike-fabian.github.io/ibus-typing-booster')
        self.set_license('''
        This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
        the Free Software Foundation, either version 3 of the License, or
        (at your option) any later version.

        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
        GNU General Public License for more details.

        You should have received a copy of the GNU General Public License
        along with this program.  If not, see <http://www.gnu.org/licenses/>
        ''')
        self.set_wrap_license(True)
        # overrides the above .set_license()
        self.set_license_type(Gtk.License.GPL_3_0)
        self.connect('response', self.on_close_aboutdialog)
        if parent:
            self.set_transient_for(parent.get_toplevel())
        self.show()

    def on_close_aboutdialog( # pylint: disable=no-self-use
            self,
            _about_dialog: Gtk.Dialog,
            _response: Gtk.ResponseType) -> None:
        '''
        The “About” dialog has been closed by the user

        :param _about_dialog: The “About” dialog
        :param _response: The response when the “About” dialog was closed
        '''
        self.destroy()

# Audio recording parameters
AUDIO_RATE: int = 16000
AUDIO_CHUNK: int = int(AUDIO_RATE / 10)  # 100ms

class MicrophoneStream():
    '''Opens a recording stream as a generator yielding the audio chunks.

    This code is from:

    https://github.com/GoogleCloudPlatform/python-docs-samples/blob/master/speech/cloud-client/transcribe_streaming_mic.py

    https://github.com/GoogleCloudPlatform/python-docs-samples/blob/main/LICENSE

    GoogleCloudPlatform/python-docs-samples is licensed under the
    Apache License 2.0
    '''
    def __init__(self, rate: int, chunk: int):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff: queue.Queue[Any] = queue.Queue()
        self.closed = True
        self._audio_interface: Optional[pyaudio.PyAudio] = None
        self._audio_stream: Optional[Any] = None

    def __enter__(self) -> Any:
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1, rate=self._rate,
            input=True, frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any) -> None:
        if self._audio_stream:
            self._audio_stream.stop_stream()
            self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        if self._audio_interface:
            self._audio_interface.terminate()

    def _fill_buffer(
            self,
            in_data: Any,
            _frame_count: Any,
            _time_info: Any,
            _status_flags: Any) -> Tuple[None, Any]:
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self) -> Iterable[bytes]:
        '''
        Generator method yielding audio chunks
        '''
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get(block=True)
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)

if __name__ == "__main__":
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)
    import doctest
    (FAILED, _ATTEMPTED) = doctest.testmod()
    LOGGER.info('remove_accents() cache info: %s', remove_accents.cache_info())
    sys.exit(FAILED)
