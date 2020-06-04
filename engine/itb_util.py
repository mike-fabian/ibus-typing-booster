# -*- coding: utf-8 -*-
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

# “Wrong continued indentation”: pylint: disable=bad-continuation

import sys
import os
import re
import unicodedata
import locale
import logging
import shutil
import subprocess
import glob
import gettext
from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus
require_version('GLib', '2.0')
from gi.repository import GLib
require_version('Gdk', '3.0')
from gi.repository import Gdk
require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import GObject

import version

IMPORT_DISTRO_SUCCESSFUL = False
try:
    import distro
    IMPORT_DISTRO_SUCCESSFUL = True
except (ImportError,):
    IMPORT_DISTRO_SUCCESSFUL = False

IMPORT_XDG_BASEDIRECTORY_SUCCESSFUL = False
try:
    import xdg.BaseDirectory
    IMPORT_XDG_BASEDIRECTORY_SUCCESSFUL = True
except (ImportError,):
    IMPORT_XDG_BASEDIRECTORY_SUCCESSFUL = False

IMPORT_PYAUDIO_SUCCESSFUL = False
try:
    import pyaudio
    IMPORT_PYAUDIO_SUCCESSFUL = True
except (ImportError,):
    IMPORT_PYAUDIO_SUCCESSFUL = False

IMPORT_QUEUE_SUCCESSFUL = False
try:
    import queue
    IMPORT_QUEUE_SUCCESSFUL = True
except (ImportError,):
    IMPORT_QUEUE_SUCCESSFUL = False

LOGGER = logging.getLogger('ibus-typing-booster')

DOMAINNAME = 'ibus-typing-booster'
_ = lambda a: gettext.dgettext(DOMAINNAME, a)
N_ = lambda a: a

# When matching keybindings, only the bits in the following mask are
# considered for key.state:
KEYBINDING_STATE_MASK = (
    IBus.ModifierType.MODIFIER_MASK
    & ~IBus.ModifierType.LOCK_MASK # Caps Lock
    & ~IBus.ModifierType.MOD2_MASK # Num Lock
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

LOCALE_DEFAULTS = {
    # Contains the default input methods and dictionaries which should
    # be used if ibus-typing-booster is started for the very first
    # time. In that case, no previous settings can be found from dconf
    # and a reasonable default should be used depending on the current
    # locale.
    'af_NA': {'inputmethods': ['NoIME'], 'dictionaries': ['af_NA']},
    'af_ZA': {'inputmethods': ['NoIME'], 'dictionaries': ['af_ZA']},
    'ak_GH': {'inputmethods': ['NoIME'], 'dictionaries': ['ak_GH']},
    'am_ET': {'inputmethods': ['am-sera'], 'dictionaries': ['am_ET']},
    'ar_AE': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_AE']},
    'ar_BH': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_BH']},
    'ar_DJ': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_DJ']},
    'ar_DZ': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_DZ']},
    'ar_EG': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_EG']},
    'ar_ER': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_ER']},
    'ar_IL': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_IL']},
    'ar_IN': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_IN']},
    'ar_IQ': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_IQ']},
    'ar_JO': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_JO']},
    'ar_KM': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_KM']},
    'ar_KW': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_KW']},
    'ar_LB': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_LB']},
    'ar_LY': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_LY']},
    'ar_MA': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_MA']},
    'ar_MR': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_MR']},
    'ar_OM': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_OM']},
    'ar_PS': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_PS']},
    'ar_QA': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_QA']},
    'ar_SA': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_SA']},
    'ar_SD': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_SD']},
    'ar_SO': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_SO']},
    'ar_SY': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_SY']},
    'ar_TD': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_TD']},
    'ar_TN': {'inputmethods':['NoIME'], 'dictionaries': ['ar_TN']},
    'ar_YE': {'inputmethods': ['NoIME'], 'dictionaries': ['ar_YE']},
    # libgnome-desktop/default-input-sources.h has "m17n:as:phonetic"
    # as the default. Parag Nemade says the as translator for Fedora a long
    # time back used as-phonetic. We have no later data from the
    # community.
    'as_IN': {'inputmethods': ['as-phonetic', 'NoIME'],
              'dictionaries': ['as_IN', 'en_GB']},
    'ast_ES': {'inputmethods': ['NoIME'], 'dictionaries': ['ast_ES']},
    'az_AZ': {'inputmethods': ['NoIME'], 'dictionaries': ['az_AZ']},
    'be_BY': {'inputmethods': ['NoIME'], 'dictionaries': ['be_BY']},
    'ber_MA': {'inputmethods': ['NoIME'], 'dictionaries': ['ber_MA']},
    'bg_BG': {'inputmethods': ['NoIME'], 'dictionaries': ['bg_BG']},
    'bn_IN': {'inputmethods': ['bn-inscript2', 'NoIME'],
              'dictionaries': ['bn_IN', 'en_GB']},
    'br_FR': {'inputmethods': ['NoIME'], 'dictionaries': ['br_FR']},
    'bs_BA': {'inputmethods': ['NoIME'], 'dictionaries': ['bs_BA']},
    'ca_AD': {'inputmethods': ['NoIME'], 'dictionaries': ['ca_AD']},
    'ca_ES': {'inputmethods': ['NoIME'], 'dictionaries': ['ca_ES']},
    'ca_FR': {'inputmethods': ['NoIME'], 'dictionaries': ['ca_FR']},
    'ca_IT': {'inputmethods': ['NoIME'], 'dictionaries': ['ca_IT']},
    'cop_EG': {'inputmethods': ['NoIME'], 'dictionaries': ['cop_EG']},
    'cs_CZ': {'inputmethods': ['NoIME'], 'dictionaries': ['cs_CZ']},
    'csb_PL': {'inputmethods': ['NoIME'], 'dictionaries': ['csb_PL']},
    'cv_RU': {'inputmethods': ['NoIME'], 'dictionaries': ['cv_RU']},
    'cy_GB': {'inputmethods': ['NoIME'], 'dictionaries': ['cy_GB']},
    'da_DK': {'inputmethods': ['NoIME'], 'dictionaries': ['da_DK']},
    'de_AT': {'inputmethods': ['NoIME'], 'dictionaries': ['de_AT']},
    'de_BE': {'inputmethods': ['NoIME'], 'dictionaries': ['de_BE']},
    'de_CH': {'inputmethods': ['NoIME'], 'dictionaries': ['de_CH']},
    'de_DE': {'inputmethods':['NoIME'], 'dictionaries': ['de_DE']},
    'de_LI': {'inputmethods': ['NoIME'], 'dictionaries': ['de_LI']},
    'de_LU': {'inputmethods': ['NoIME'], 'dictionaries': ['de_LU']},
    'dsb_DE': {'inputmethods': ['NoIME'], 'dictionaries': ['dsb_DE']},
    'el_CY': {'inputmethods': ['NoIME'], 'dictionaries': ['el_CY']},
    'el_GR': {'inputmethods': ['NoIME'], 'dictionaries': ['el_GR']},
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
    'en_US': {'inputmethods': ['NoIME'], 'dictionaries': ['en_US']},
    'en_ZA': {'inputmethods': ['NoIME'], 'dictionaries': ['en_ZA']},
    'en_ZM': {'inputmethods': ['NoIME'], 'dictionaries': ['en_ZM']},
    'en_ZW': {'inputmethods': ['NoIME'], 'dictionaries': ['en_ZW']},
    'eo': {'inputmethods': ['NoIME'], 'dictionaries': ['eo']},
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
    'et_EE': {'inputmethods': ['NoIME'], 'dictionaries': ['et_EE']},
    'eu_ES': {'inputmethods': ['NoIME'], 'dictionaries': ['eu_ES']},
    'fa_IR': {'inputmethods': ['NoIME'], 'dictionaries': ['fa_IR']},
    'fil_PH': {'inputmethods': ['NoIME'], 'dictionaries': ['fil_PH']},
    'fj': {'inputmethods': ['NoIME'], 'dictionaries': ['fj']},
    'fo_FO': {'inputmethods': ['NoIME'], 'dictionaries': ['fo_FO']},
    'fr_BE': {'inputmethods': ['NoIME'], 'dictionaries': ['fr_BE']},
    'fr_CA': {'inputmethods': ['NoIME'], 'dictionaries': ['fr_CA']},
    'fr_CH': {'inputmethods': ['NoIME'], 'dictionaries': ['fr_CH']},
    'fr_FR': {'inputmethods': ['NoIME'], 'dictionaries': ['fr_FR']},
    'fr_LU': {'inputmethods': ['NoIME'], 'dictionaries': ['fr_LU']},
    'fr_MC': {'inputmethods': ['NoIME'], 'dictionaries': ['fr_MC']},
    'fur_IT': {'inputmethods': ['NoIME'], 'dictionaries': ['fur_IT']},
    'fy_DE': {'inputmethods': ['NoIME'], 'dictionaries': ['fy_DE']},
    'fy_NL': {'inputmethods': ['NoIME'], 'dictionaries': ['fy_NL']},
    'ga_IE': {'inputmethods': ['NoIME'], 'dictionaries': ['ga_IE']},
    'gd_GB': {'inputmethods': ['NoIME'], 'dictionaries': ['gd_GB']},
    'gl_ES': {'inputmethods': ['NoIME'], 'dictionaries': ['gl_ES']},
    'grc': {'inputmethods': ['NoIME'], 'dictionaries': ['grc']},
    'gu_IN': {'inputmethods': ['gu-inscript2', 'NoIME'],
              'dictionaries': ['gu_IN', 'en_GB']},
    'gv_GB': {'inputmethods': ['NoIME'], 'dictionaries': ['gv_GB']},
    'haw': {'inputmethods': ['NoIME'], 'dictionaries': ['haw']},
    'he_IL': {'inputmethods': ['NoIME'], 'dictionaries': ['he_IL']},
    'hi_IN': {'inputmethods': ['hi-inscript2', 'NoIME'],
              'dictionaries': ['hi_IN', 'en_GB']},
    'hil_PH': {'inputmethods': ['NoIME'], 'dictionaries': ['hil_PH']},
    'hr_HR': {'inputmethods': ['NoIME'], 'dictionaries': ['hr_HR']},
    'hsb_DE': {'inputmethods': ['NoIME'], 'dictionaries': ['hsb_DE']},
    'ht_HT': {'inputmethods': ['NoIME'], 'dictionaries': ['ht_HT']},
    'hu_HU': {'inputmethods': ['NoIME'], 'dictionaries': ['hu_HU']},
    'hy_AM': {'inputmethods': ['NoIME'], 'dictionaries': ['hy_AM']},
    'ia': {'inputmethods': ['NoIME'], 'dictionaries': ['ia']},
    'id_ID': {'inputmethods': ['NoIME'], 'dictionaries': ['id_ID']},
    'is_IS': {'inputmethods': ['NoIME'], 'dictionaries': ['is_IS']},
    'it_CH': {'inputmethods': ['NoIME'], 'dictionaries': ['it_CH']},
    'it_IT': {'inputmethods': ['NoIME'], 'dictionaries': ['it_IT']},
    'kk_KZ': {'inputmethods': ['NoIME'], 'dictionaries': ['kk_KZ']},
    'km_KH': {'inputmethods': ['NoIME'], 'dictionaries': ['km_KH']},
    # libgnome-desktop/default-input-sources.h has "m17n:kn:kgp" as
    # the default for kn_IN. According to Parag Nemade this probably came
    # from the translation community.
    'kn_IN': {'inputmethods': ['kn-kgp', 'NoIME'],
              'dictionaries': ['kn_IN', 'en_GB']},
    'ko_KR': {'inputmethods': ['ko-han2', 'NoIME'],
              'dictionaries': ['ko_KR', 'en_GB']},
    'ku_SY': {'inputmethods': ['NoIME'], 'dictionaries': ['ku_SY']},
    'ku_TR': {'inputmethods': ['NoIME'], 'dictionaries': ['ku_TR']},
    'ky_KG': {'inputmethods': ['NoIME'], 'dictionaries': ['ky_KG']},
    'la': {'inputmethods': ['NoIME'], 'dictionaries': ['la']},
    'lb_LU': {'inputmethods': ['NoIME'], 'dictionaries': ['lb_LU']},
    'ln_CD': {'inputmethods': ['NoIME'], 'dictionaries': ['ln_CD']},
    'lt_LT': {'inputmethods': ['NoIME'], 'dictionaries': ['lt_LT']},
    'lv_LV': {'inputmethods': ['NoIME'], 'dictionaries': ['lv_LV']},
    'mai_IN': {'inputmethods': ['mai-inscript2', 'NoIME'],
               'dictionaries': ['mai_IN', 'en_GB']},
    'mg': {'inputmethods': ['NoIME'], 'dictionaries': ['mg']},
    'mi_NZ': {'inputmethods': ['NoIME'], 'dictionaries': ['mi_NZ']},
    'mk_MK': {'inputmethods': ['NoIME'], 'dictionaries': ['mk_MK']},
    'ml_IN': {'inputmethods': ['ml-inscript2', 'NoIME'],
              'dictionaries': ['ml_IN', 'en_GB']},
    'mn_MN': {'inputmethods': ['NoIME'], 'dictionaries': ['mn_MN']},
    'mos_BF': {'inputmethods': ['NoIME'], 'dictionaries': ['mos_BF']},
    'mr_IN': {'inputmethods': ['mr-inscript2', 'NoIME'],
              'dictionaries': ['mr_IN', 'en_GB']},
    'ms_BN': {'inputmethods': ['NoIME'], 'dictionaries': ['ms_BN']},
    'ms_MY': {'inputmethods': ['NoIME'], 'dictionaries': ['ms_MY']},
    'mt_MT': {'inputmethods': ['NoIME'], 'dictionaries': ['mt_MT']},
    'nb_NO': {'inputmethods': ['NoIME'], 'dictionaries': ['nb_NO']},
    'nds_DE': {'inputmethods': ['NoIME'], 'dictionaries': ['nds_DE']},
    'nds_NL': {'inputmethods': ['NoIME'], 'dictionaries': ['nds_NL']},
    'ne_IN': {'inputmethods': ['ne-rom', 'NoIME'],
              'dictionaries': ['ne_IN', 'en_GB']},
    'ne_NP': {'inputmethods': ['ne-rom', 'NoIME'],
              'dictionaries': ['ne_NP', 'en_GB']},
    'nl_AW': {'inputmethods': ['NoIME'], 'dictionaries': ['nl_AW']},
    'nl_BE': {'inputmethods': ['NoIME'], 'dictionaries': ['nl_BE']},
    'nl_NL': {'inputmethods': ['NoIME'], 'dictionaries': ['nl_NL']},
    'nn_NO': {'inputmethods': ['NoIME'], 'dictionaries': ['nn_NO']},
    'nr_ZA': {'inputmethods': ['NoIME'], 'dictionaries': ['nr_ZA']},
    'nso_ZA': {'inputmethods': ['NoIME'], 'dictionaries': ['nso_ZA']},
    'ny_MW': {'inputmethods': ['NoIME'], 'dictionaries': ['ny_MW']},
    'oc_FR': {'inputmethods': ['NoIME'], 'dictionaries': ['oc_FR']},
    'om_ET': {'inputmethods': ['NoIME'], 'dictionaries': ['om_ET']},
    'om_KE': {'inputmethods': ['NoIME'], 'dictionaries': ['om_KE']},
    'or_IN': {'inputmethods': ['or-inscript2', 'NoIME'],
              'dictionaries': ['or_IN', 'en_GB']},
    'pa_IN': {'inputmethods': ['pa-inscript2', 'NoIME'],
              'dictionaries': ['pa_IN', 'en_GB']},
    'pl_PL': {'inputmethods': ['NoIME'], 'dictionaries': ['pl_PL']},
    'plt': {'inputmethods': ['NoIME'], 'dictionaries': ['plt']},
    'pt_AO': {'inputmethods': ['NoIME'], 'dictionaries': ['pt_AO']},
    'pt_BR': {'inputmethods': ['NoIME'], 'dictionaries': ['pt_BR']},
    'pt_PT': {'inputmethods': ['NoIME'], 'dictionaries': ['pt_PT']},
    'qu_EC': {'inputmethods': ['NoIME'], 'dictionaries': ['qu_EC']},
    'quh_BO': {'inputmethods': ['NoIME'], 'dictionaries': ['quh_BO']},
    'ro_RO': {'inputmethods': ['NoIME'], 'dictionaries': ['ro_RO']},
    'ru_RU': {'inputmethods': ['NoIME'], 'dictionaries': ['ru_RU']},
    'ru_UA': {'inputmethods': ['NoIME'], 'dictionaries': ['ru_UA']},
    'rw_RW': {'inputmethods': ['NoIME'], 'dictionaries': ['rw_RW']},
    'sc_IT': {'inputmethods': ['NoIME'], 'dictionaries': ['sc_IT']},
    'se_FI': {'inputmethods': ['NoIME'], 'dictionaries': ['se_FI']},
    'se_NO': {'inputmethods': ['NoIME'], 'dictionaries': ['se_NO']},
    'se_SE': {'inputmethods': ['NoIME'], 'dictionaries': ['se_SE']},
    'sh_ME': {'inputmethods': ['NoIME'], 'dictionaries': ['sh_ME']},
    'sh_RS': {'inputmethods': ['NoIME'], 'dictionaries': ['sh_RS']},
    'sh_YU': {'inputmethods': ['NoIME'], 'dictionaries': ['sh_YU']},
    'shs_CA': {'inputmethods': ['NoIME'], 'dictionaries': ['shs_CA']},
    'si_LK': {'inputmethods': ['si-wijesekera', 'NoIME'],
              'dictionaries': ['si_LK', 'en_GB']},
    'sk_SK': {'inputmethods': ['NoIME'], 'dictionaries': ['sk_SK']},
    'sl_SI': {'inputmethods': ['NoIME'], 'dictionaries': ['sl_SI']},
    'smj_NO': {'inputmethods': ['NoIME'], 'dictionaries': ['smj_NO']},
    'smj_SE': {'inputmethods': ['NoIME'], 'dictionaries': ['smj_SE']},
    'so_DJ': {'inputmethods': ['NoIME'], 'dictionaries': ['so_DJ']},
    'so_ET': {'inputmethods': ['NoIME'], 'dictionaries': ['so_ET']},
    'so_KE': {'inputmethods': ['NoIME'], 'dictionaries': ['so_KE']},
    'so_SO': {'inputmethods': ['NoIME'], 'dictionaries': ['so_SO']},
    'sq_AL': {'inputmethods': ['NoIME'], 'dictionaries': ['sq_AL']},
    'sr_ME': {'inputmethods': ['NoIME'], 'dictionaries': ['sr_ME']},
    'sr_RS': {'inputmethods': ['NoIME'], 'dictionaries': ['sr_RS']},
    'sr_YU': {'inputmethods': ['NoIME'], 'dictionaries': ['sr_YU']},
    'ss_ZA': {'inputmethods': ['NoIME'], 'dictionaries': ['ss_ZA']},
    'st_ZA': {'inputmethods': ['NoIME'], 'dictionaries': ['st_ZA']},
    'sv_FI': {'inputmethods': ['NoIME'], 'dictionaries': ['sv_FI']},
    'sv_SE': {'inputmethods': ['NoIME'], 'dictionaries': ['sv_SE']},
    'sw_KE': {'inputmethods': ['NoIME'], 'dictionaries': ['sw_KE']},
    'sw_TZ': {'inputmethods': ['NoIME'], 'dictionaries': ['sw_TZ']},
    # libgnome-desktop/default-input-sources.h has "m17n:ta:tamil99"
    # as the default for ta_IN. According to Parag Nemade this probably came
    # from the translation community.
    'ta_IN': {'inputmethods': ['ta-tamil99', 'NoIME'],
              'dictionaries': ['ta_IN', 'en_GB']},
    'te_IN': {'inputmethods': ['te-inscript2', 'NoIME'],
              'dictionaries': ['te_IN', 'en_GB']},
    'tet_ID': {'inputmethods': ['NoIME'], 'dictionaries': ['tet_ID']},
    'tet_TL': {'inputmethods': ['NoIME'], 'dictionaries': ['tet_TL']},
    'th_TH': {'inputmethods': ['NoIME'], 'dictionaries': ['th_TH']},
    'ti_ER': {'inputmethods': ['NoIME'], 'dictionaries': ['ti_ER']},
    'ti_ET': {'inputmethods': ['NoIME'], 'dictionaries': ['ti_ET']},
    'tk_TM': {'inputmethods': ['NoIME'], 'dictionaries': ['tk_TM']},
    'tl_PH': {'inputmethods': ['NoIME'], 'dictionaries': ['tl_PH']},
    'tn_BW': {'inputmethods': ['NoIME'], 'dictionaries': ['tn_BW']},
    'tn_ZA': {'inputmethods': ['NoIME'], 'dictionaries': ['tn_ZA']},
    'tpi_PG': {'inputmethods': ['NoIME'], 'dictionaries': ['tpi_PG']},
    'ts_ZA': {'inputmethods': ['NoIME'], 'dictionaries': ['ts_ZA']},
    'uk_UA': {'inputmethods': ['NoIME'], 'dictionaries': ['uk_UA']},
    'ur_IN': {'inputmethods': ['ur-phonetic', 'NoIME'],
              'dictionaries': ['ur_IN', 'en_GB']},
    'ur_PK': {'inputmethods': ['NoIME'], 'dictionaries': ['ur_PK']},
    'uz_UZ': {'inputmethods': ['NoIME'], 'dictionaries': ['uz_UZ']},
    've_ZA': {'inputmethods': ['NoIME'], 'dictionaries': ['ve_ZA']},
    'vi_VN': {'inputmethods': ['NoIME'], 'dictionaries': ['vi_VN']},
    'wa_BE': {'inputmethods': ['NoIME'], 'dictionaries': ['wa_BE']},
    'xh_ZA': {'inputmethods': ['NoIME'], 'dictionaries': ['xh_ZA']},
    'yi_US': {'inputmethods': ['NoIME', 'yi-yivo'],
              'dictionaries': ['yi_US', 'en_US']},
    'zu_ZA': {'inputmethods': ['NoIME'], 'dictionaries': ['zu_ZA', 'en_GB']},
}

def get_default_input_methods(locale_string):
    '''
    Gets the default input methods for a locale

    :param locale_string:
    :type locale_string: String
    :rtype: List of  Strings

    Examples:

    >>> get_default_input_methods('te_IN')
    ['te-inscript2', 'NoIME']

    >>> get_default_input_methods('xx_YY')
    ['NoIME']
    '''
    if locale_string in LOCALE_DEFAULTS:
        default_input_methods = LOCALE_DEFAULTS[locale_string]['inputmethods']
    else:
        default_input_methods = ['NoIME']
    return default_input_methods

def get_default_dictionaries(locale_string):
    '''
    Gets the default dictionaries for a locale

    :param locale_string:
    :type locale_string: String
    :rtype: List of  Strings

    Examples:

    >>> get_default_dictionaries('te_IN')
    ['te_IN', 'en_GB']

    >>> get_default_dictionaries('xx_YY')
    ['en_US']
    '''
    if locale_string in LOCALE_DEFAULTS:
        default_dictionaries = LOCALE_DEFAULTS[locale_string]['dictionaries']
    else:
        default_dictionaries = ['en_US']
    return default_dictionaries

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
    'bez',
    'bez_TZ',
    'bg',
    'bg_BG',
    'bgn',
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
    'ff_CM',
    'ff_GN',
    'ff_MR',
    'ff_SN',
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
    'mk',
    'mk_MK',
    'ml',
    'ml_IN',
    'mn',
    'mn_MN',
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
    'nus',
    'nus_SS',
    'nyn',
    'nyn_UG',
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
    'sah',
    'sah_RU',
    'saq',
    'saq_KE',
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
    'None': '🏴',
    'af': '🇿🇦',
    'af_NA': '🇳🇦',
    'af_ZA': '🇿🇦',
    'agq': '🇨🇲',
    'agq_CM': '🇨🇲',
    'ak': '🇬🇭',
    'ak_GH': '🇬🇭',
    'am': '🇪🇹',
    'am_ET': '🇪🇹',
    'ar': '🌍',
    'ar_001': '🌐',
    'ar_AE': '🇦🇪',
    'ar_BH': '🇧🇭',
    'ar_DJ': '🇩🇯',
    'ar_DZ': '🇩🇿',
    'ar_EG': '🇪🇬',
    'ar_EH': '🇪🇭',
    'ar_ER': '🇪🇷',
    'ar_IL': '🇮🇱',
    'ar_IN': '🇮🇳',
    'ar_IQ': '🇮🇶',
    'ar_JO': '🇯🇴',
    'ar_KM': '🇰🇲',
    'ar_KW': '🇰🇼',
    'ar_LB': '🇱🇧',
    'ar_LY': '🇱🇾',
    'ar_MA': '🇲🇦',
    'ar_MR': '🇲🇷',
    'ar_OM': '🇴🇲',
    'ar_PS': '🇵🇸',
    'ar_QA': '🇶🇦',
    'ar_SA': '🇸🇦',
    'ar_SD': '🇸🇩',
    'ar_SO': '🇸🇴',
    'ar_SS': '🇸🇸',
    'ar_SY': '🇸🇾',
    'ar_TD': '🇹🇩',
    'ar_TN': '🇹🇳',
    'ar_YE': '🇾🇪',
    'as': '🌏',
    'as_IN': '🇮🇳',
    'asa': '🌍',
    'asa_TZ': '🇹🇿',
    'ast': '🌍',
    'ast_ES': '🇪🇸',
    'az': '🌍',
    'az_AZ': '🇦🇿',
    'az_Cyrl': '🌍',
    'az_Cyrl_AZ': '🇦🇿',
    'az_Latn': '🌍',
    'az_Latn_AZ': '🇦🇿',
    'bas': '🌍',
    'bas_CM': '🇨🇲',
    'be': '🌍',
    'be_BY': '🇧🇾',
    'bem': '🌍',
    'bem_ZM': '🇿🇲',
    'bez': '🌍',
    'bez_TZ': '🇹🇿',
    'bg': '🌍',
    'bg_BG': '🇧🇬',
    'bm': '🌍',
    'bm_ML': '🇲🇱',
    'bn': '🌏',
    'bn_BD': '🇧🇩',
    'bn_IN': '🇮🇳',
    'bo': '🌏',
    'bo_CN': '🇨🇳',
    'bo_IN': '🇮🇳',
    'br': '🌍',
    'br_FR': '🇫🇷',
    'brx': '🌏',
    'brx_IN': '🇮🇳',
    'bs': '🌍',
    'bs_BA': '🇧🇦',
    'bs_Cyrl': '🌍',
    'bs_Cyrl_BA': '🇧🇦',
    'bs_Latn': '🌍',
    'bs_Latn_BA': '🇧🇦',
    'ca': '🌍',
    'ca_AD': '🇦🇩',
    'ca_ES': '🇪🇸',
    'ca_ES_VALENCIA': '🇪🇸',
    'ca_FR': '🇫🇷',
    'ca_IT': '🇮🇹',
    'ccp': '🌏',
    'ccp_BD': '🇧🇩',
    'ccp_IN': '🇮🇳',
    'ce': '🌍',
    'ce_RU': '🇷🇺',
    'cgg': '🌍',
    'cgg_UG': '🇺🇬',
    'chr': '🌎',
    'chr_US': '🇺🇸',
    'ckb': '🌍',
    'ckb_IQ': '🇮🇶',
    'ckb_IR': '🇮🇷',
    'cop': '🌍',
    'cop_EG': '🇪🇬',
    'cs': '🌍',
    'cs_CZ': '🇨🇿',
    'csb_PL': '🇵🇱',
    'cu': '🌍',
    'cu_RU': '🇷🇺',
    'cy': '🌍',
    'cy_GB': '🏴󠁧󠁢󠁷󠁬󠁳󠁿',
    'da': '🌍',
    'da_DK': '🇩🇰',
    'da_GL': '🇬🇱',
    'dav': '🌍',
    'dav_KE': '🇰🇪',
    'de': '🌍',
    'de_AT': '🇦🇹',
    'de_BE': '🇧🇪',
    'de_CH': '🇨🇭',
    'de_DE': '🇩🇪',
    'de_IT': '🇮🇹',
    'de_LI': '🇱🇮',
    'de_LU': '🇱🇺',
    'dje': '🌍',
    'dje_NE': '🇳🇪',
    'dsb': '🌍',
    'dsb_DE': '🇩🇪',
    'dua': '🌍',
    'dua_CM': '🇨🇲',
    'dyo': '🌍',
    'dyo_SN': '🇸🇳',
    'dz': '🌏',
    'dz_BT': '🇧🇹',
    'ebu': '🌍',
    'ebu_KE': '🇰🇪',
    'ee': '🌍',
    'ee_GH': '🇬🇭',
    'ee_TG': '🇹🇬',
    'el': '🌍',
    'el_CY': '🇨🇾',
    'el_GR': '🇬🇷',
    'en': '🌍',
    'en_001': '🌐',
    'en_150': '🌍',
    'en_AG': '🇦🇬',
    'en_AI': '🇦🇮',
    'en_AS': '🇦🇸',
    'en_AT': '🇦🇹',
    'en_AU': '🇦🇺',
    'en_BB': '🇧🇧',
    'en_BE': '🇧🇪',
    'en_BI': '🇧🇮',
    'en_BM': '🇧🇲',
    'en_BS': '🇧🇸',
    'en_BW': '🇧🇼',
    'en_BZ': '🇧🇿',
    'en_CA': '🇨🇦',
    'en_CC': '🇨🇨',
    'en_CH': '🇨🇭',
    'en_CK': '🇨🇰',
    'en_CM': '🇨🇲',
    'en_CX': '🇨🇽',
    'en_CY': '🇨🇾',
    'en_DE': '🇩🇪',
    'en_DG': '🇩🇬',
    'en_DK': '🇩🇰',
    'en_DM': '🇩🇲',
    'en_ER': '🇪🇷',
    'en_FI': '🇫🇮',
    'en_FJ': '🇫🇯',
    'en_FK': '🇫🇰',
    'en_FM': '🇫🇲',
    'en_GB': '🇬🇧',
    'en_GD': '🇬🇩',
    'en_GG': '🇬🇬',
    'en_GH': '🇬🇭',
    'en_GI': '🇬🇮',
    'en_GM': '🇬🇲',
    'en_GU': '🇬🇺',
    'en_GY': '🇬🇾',
    'en_HK': '🇭🇰',
    'en_IE': '🇮🇪',
    'en_IL': '🇮🇱',
    'en_IM': '🇮🇲',
    'en_IN': '🇮🇳',
    'en_IO': '🇮🇴',
    'en_JE': '🇯🇪',
    'en_JM': '🇯🇲',
    'en_KE': '🇰🇪',
    'en_KI': '🇰🇮',
    'en_KN': '🇰🇳',
    'en_KY': '🇰🇾',
    'en_LC': '🇱🇨',
    'en_LR': '🇱🇷',
    'en_LS': '🇱🇸',
    'en_MG': '🇲🇬',
    'en_MH': '🇲🇭',
    'en_MO': '🇲🇴',
    'en_MP': '🇲🇵',
    'en_MS': '🇲🇸',
    'en_MT': '🇲🇹',
    'en_MU': '🇲🇺',
    'en_MW': '🇲🇼',
    'en_MY': '🇲🇾',
    'en_NA': '🇳🇦',
    'en_NF': '🇳🇫',
    'en_NG': '🇳🇬',
    'en_NL': '🇳🇱',
    'en_NR': '🇳🇷',
    'en_NU': '🇳🇺',
    'en_NZ': '🇳🇿',
    'en_PG': '🇵🇬',
    'en_PH': '🇵🇭',
    'en_PK': '🇵🇰',
    'en_PN': '🇵🇳',
    'en_PR': '🇵🇷',
    'en_PW': '🇵🇼',
    'en_RW': '🇷🇼',
    'en_SB': '🇸🇧',
    'en_SC': '🇸🇨',
    'en_SD': '🇸🇩',
    'en_SE': '🇸🇪',
    'en_SG': '🇸🇬',
    'en_SH': '🇸🇭',
    'en_SI': '🇸🇮',
    'en_SL': '🇸🇱',
    'en_SS': '🇸🇸',
    'en_SX': '🇸🇽',
    'en_SZ': '🇸🇿',
    'en_TC': '🇹🇨',
    'en_TK': '🇹🇰',
    'en_TO': '🇹🇴',
    'en_TT': '🇹🇹',
    'en_TV': '🇹🇻',
    'en_TZ': '🇹🇿',
    'en_UG': '🇺🇬',
    'en_UM': '🇺🇲',
    'en_US': '🇺🇸',
    'en_US_POSIX': '🇺🇸',
    'en_VC': '🇻🇨',
    'en_VG': '🇻🇬',
    'en_VI': '🇻🇮',
    'en_VU': '🇻🇺',
    'en_WS': '🇼🇸',
    'en_ZA': '🇿🇦',
    'en_ZM': '🇿🇲',
    'en_ZW': '🇿🇼',
    'eo': '🌍',
    'eo_001': '🌐',
    'es': '🌍',
    'es_419': '🌎',
    'es_AR': '🇦🇷',
    'es_BO': '🇧🇴',
    'es_BR': '🇧🇷',
    'es_BZ': '🇧🇿',
    'es_CL': '🇨🇱',
    'es_CO': '🇨🇴',
    'es_CR': '🇨🇷',
    'es_CU': '🇨🇺',
    'es_DO': '🇩🇴',
    'es_EA': '🇪🇦',
    'es_EC': '🇪🇨',
    'es_ES': '🇪🇸',
    'es_GQ': '🇬🇶',
    'es_GT': '🇬🇹',
    'es_HN': '🇭🇳',
    'es_IC': '🇮🇨',
    'es_MX': '🇲🇽',
    'es_NI': '🇳🇮',
    'es_PA': '🇵🇦',
    'es_PE': '🇵🇪',
    'es_PH': '🇵🇭',
    'es_PR': '🇵🇷',
    'es_PY': '🇵🇾',
    'es_SV': '🇸🇻',
    'es_US': '🇺🇸',
    'es_UY': '🇺🇾',
    'es_VE': '🇻🇪',
    'et': '🌍',
    'et_EE': '🇪🇪',
    'eu': '🌍',
    'eu_ES': '🇪🇸',
    'ewo': '🌍',
    'ewo_CM': '🇨🇲',
    'fa': '🌍',
    'fa_AF': '🇦🇫',
    'fa_IR': '🇮🇷',
    'ff': '🌍',
    'ff_CM': '🇨🇲',
    'ff_GN': '🇬🇳',
    'ff_MR': '🇲🇷',
    'ff_SN': '🇸🇳',
    'fi': '🌍',
    'fi_FI': '🇫🇮',
    'fil': '🌏',
    'fil_PH': '🇵🇭',
    'fj': '🇫🇯',
    'fj_FJ': '🇫🇯',
    'fo': '🌍',
    'fo_DK': '🇩🇰',
    'fo_FO': '🇫🇴',
    'fr': '🌍',
    'fr_BE': '🇧🇪',
    'fr_BF': '🇧🇫',
    'fr_BI': '🇧🇮',
    'fr_BJ': '🇧🇯',
    'fr_BL': '🇧🇱',
    'fr_CA': '🇨🇦',
    'fr_CD': '🇨🇩',
    'fr_CF': '🇨🇫',
    'fr_CG': '🇨🇬',
    'fr_CH': '🇨🇭',
    'fr_CI': '🇨🇮',
    'fr_CM': '🇨🇲',
    'fr_DJ': '🇩🇯',
    'fr_DZ': '🇩🇿',
    'fr_FR': '🇫🇷',
    'fr_GA': '🇬🇦',
    'fr_GF': '🇬🇫',
    'fr_GN': '🇬🇳',
    'fr_GP': '🇬🇵',
    'fr_GQ': '🇬🇶',
    'fr_HT': '🇭🇹',
    'fr_KM': '🇰🇲',
    'fr_LU': '🇱🇺',
    'fr_MA': '🇲🇦',
    'fr_MC': '🇲🇨',
    'fr_MF': '🇲🇫',
    'fr_MG': '🇲🇬',
    'fr_ML': '🇲🇱',
    'fr_MQ': '🇲🇶',
    'fr_MR': '🇲🇷',
    'fr_MU': '🇲🇺',
    'fr_NC': '🇳🇨',
    'fr_NE': '🇳🇪',
    'fr_PF': '🇵🇫',
    'fr_PM': '🇵🇲',
    'fr_RE': '🇷🇪',
    'fr_RW': '🇷🇼',
    'fr_SC': '🇸🇨',
    'fr_SN': '🇸🇳',
    'fr_SY': '🇸🇾',
    'fr_TD': '🇹🇩',
    'fr_TG': '🇹🇬',
    'fr_TN': '🇹🇳',
    'fr_VU': '🇻🇺',
    'fr_WF': '🇼🇫',
    'fr_YT': '🇾🇹',
    'fur': '🌍',
    'fur_IT': '🇮🇹',
    'fy': '🌍',
    'fy_DE': '🇩🇪',
    'fy_NL': '🇳🇱',
    'ga': '🌍',
    'ga_IE': '🇮🇪',
    'gd': '🌍',
    'gd_GB': '🏴󠁧󠁢󠁳󠁣󠁴󠁿',
    'gl': '🌍',
    'gl_ES': '🇪🇸',
    'grc': '🇬🇷',
    'gsw': '🌍',
    'gsw_CH': '🇨🇭',
    'gsw_FR': '🇫🇷',
    'gsw_LI': '🇱🇮',
    'gu': '🌏',
    'gu_IN': '🇮🇳',
    'guz': '🌍',
    'guz_KE': '🇰🇪',
    'gv': '🌍',
    'gv_GB': '🇬🇧',
    'gv_IM': '🇮🇲',
    'ha': '🌍',
    'ha_GH': '🇬🇭',
    'ha_NE': '🇳🇪',
    'ha_NG': '🇳🇬',
    'haw': '🌎',
    'haw_US': '🇺🇸',
    'he': '🌍',
    'he_IL': '🇮🇱',
    'hi': '🌏',
    'hi_IN': '🇮🇳',
    'hil_PH': '🇵🇭',
    'hr': '🌍',
    'hr_BA': '🇧🇦',
    'hr_HR': '🇭🇷',
    'hsb': '🌍',
    'hsb_DE': '🇩🇪',
    'ht': '🌎',
    'ht_HT': '🇭🇹',
    'hu': '🌍',
    'hu_HU': '🇭🇺',
    'hy': '🌍',
    'hy_AM': '🇦🇲',
    'ia': '🌍',
    'id': '🌏',
    'id_ID': '🇮🇩',
    'ig': '🌍',
    'ig_NG': '🇳🇬',
    'ii': '🌏',
    'ii_CN': '🇨🇳',
    'is': '🌍',
    'is_IS': '🇮🇸',
    'it': '🌍',
    'it_CH': '🇨🇭',
    'it_IT': '🇮🇹',
    'it_SM': '🇸🇲',
    'it_VA': '🇻🇦',
    'ja': '🌏',
    'ja_JP': '🇯🇵',
    'jgo': '🌍',
    'jgo_CM': '🇨🇲',
    'jmc': '🌍',
    'jmc_TZ': '🇹🇿',
    'jv': '🌏',
    'jv_ID': '🌍',
    'ka': '🌍',
    'ka_GE': '🇬🇪',
    'kab': '🌍',
    'kab_DZ': '🇩🇿',
    'kam': '🌍',
    'kam_KE': '🇰🇪',
    'kde': '🌍',
    'kde_TZ': '🇹🇿',
    'kea': '🌍',
    'kea_CV': '🇨🇻',
    'khq': '🌍',
    'khq_ML': '🇲🇱',
    'ki': '🌍',
    'ki_KE': '🇰🇪',
    'kk': '🌍',
    'kk_KZ': '🇰🇿',
    'kkj': '🌍',
    'kkj_CM': '🇨🇲',
    'kl': '🌍',
    'kl_GL': '🇬🇱',
    'kln': '🌍',
    'kln_KE': '🇰🇪',
    'km': '🌏',
    'km_KH': '🇰🇭',
    'kn': '🌏',
    'kn_IN': '🇮🇳',
    'ko': '🌏',
    'ko_KP': '🇰🇵',
    'ko_KR': '🇰🇷',
    'kok': '🌏',
    'kok_IN': '🇮🇳',
    'ks': '🌏',
    'ks_IN': '🇮🇳',
    'ksb': '🌍',
    'ksb_TZ': '🇹🇿',
    'ksf': '🌍',
    'ksf_CM': '🇨🇲',
    'ksh': '🌍',
    'ksh_DE': '🇩🇪',
    'ku': '🌍',
    'ku_SY': '🇸🇾',
    'ku_TR': '🇹🇷',
    'kw': '🌍',
    'kw_GB': '🇬🇧',
    'ky': '🌍',
    'ky_KG': '🇰🇬',
    'la': '🇻🇦',
    'la_VA': '🇻🇦',
    'lag': '🌍',
    'lag_TZ': '🇹🇿',
    'lb': '🌍',
    'lb_LU': '🇱🇺',
    'lg': '🌍',
    'lg_UG': '🇺🇬',
    'lkt': '🌎',
    'lkt_US': '🇺🇸',
    'ln': '🌍',
    'ln_AO': '🇦🇴',
    'ln_CD': '🇨🇩',
    'ln_CF': '🇨🇫',
    'ln_CG': '🇨🇬',
    'lo': '🌏',
    'lo_LA': '🇱🇦',
    'lrc': '🌍',
    'lrc_IQ': '🇮🇶',
    'lrc_IR': '🇮🇷',
    'lt': '🌍',
    'lt_LT': '🇱🇹',
    'lu': '🌍',
    'lu_CD': '🇨🇩',
    'luo': '🌍',
    'luo_KE': '',
    'luy': '🌍',
    'luy_KE': '🇰🇪',
    'lv': '🌍',
    'lv_LV': '🇱🇻',
    'mai': '🌍',
    'mai_IN': '🇮🇳',
    'mas': '🌍',
    'mas_KE': '🇰🇪',
    'mas_TZ': '🇹🇿',
    'mer': '🌍',
    'mer_KE': '🇰🇪',
    'mfe': '🌍',
    'mfe_MU': '🇲🇺',
    'mg': '🌍',
    'mg_MG': '🇲🇬',
    'mgh': '🌍',
    'mgh_MZ': '🇲🇿',
    'mgo': '🌍',
    'mgo_CM': '🇨🇲',
    'mi': '🌏',
    'mi_NZ': '🇳🇿',
    'mk': '🌍',
    'mk_MK': '🇲🇰',
    'ml': '🌏',
    'ml_IN': '🇮🇳',
    'mn': '🌏',
    'mn_MN': '🇲🇳',
    'mos': '🌍',
    'mos_BF': '🇧🇫',
    'mr': '🌏',
    'mr_IN': '🇮🇳',
    'ms': '🌏',
    'ms_BN': '🇧🇳',
    'ms_MY': '🇲🇾',
    'ms_SG': '🇸🇬',
    'mt': '🌍',
    'mt_MT': '🇲🇹',
    'mua': '🌍',
    'mua_CM': '🇨🇲',
    'my': '🌏',
    'my_MM': '🇲🇲',
    'mzn': '🌍',
    'mzn_IR': '🇮🇷',
    'naq': '🌍',
    'naq_NA': '🇳🇦',
    'nb': '🌍',
    'nb_NO': '🇳🇴',
    'nb_SJ': '🇸🇯',
    'nd': '🌍',
    'nd_ZW': '🇿🇼',
    'nds': '🌍',
    'nds_DE': '🇩🇪',
    'nds_NL': '🇳🇱',
    'ne': '🌏',
    'ne_IN': '🇮🇳',
    'ne_NP': '🇳🇵',
    'nl': '🌍',
    'nl_AW': '🇦🇼',
    'nl_BE': '🇧🇪',
    'nl_BQ': '🇧🇶',
    'nl_CW': '🇨🇼',
    'nl_NL': '🇳🇱',
    'nl_SR': '🇸🇷',
    'nl_SX': '🇸🇽',
    'nmg': '🌍',
    'nmg_CM': '🇨🇲',
    'nn': '🌍',
    'nn_NO': '🇳🇴',
    'nnh': '🌍',
    'nnh_CM': '🇨🇲',
    'nr': '🌍',
    'nr_ZA': '🇿🇦',
    'nso': '🌍',
    'nso_ZA': '🇿🇦',
    'nus': '🌍',
    'nus_SS': '🇸🇸',
    'ny': '🌍',
    'ny_MW': '🇲🇼',
    'nyn': '🌍',
    'nyn_UG': '🇺🇬',
    'oc': '🌍',
    'oc_FR': '🇫🇷',
    'om': '🌍',
    'om_ET': '🇪🇹',
    'om_KE': '🇰🇪',
    'or': '🌏',
    'or_IN': '🇮🇳',
    'os': '🌍',
    'os_GE': '🇬🇪',
    'os_RU': '🇷🇺',
    'pa': '🌍',
    'pa_IN': '🇮🇳',
    'pa_Arab': '🌍',
    'pa_Arab_PK': '🇵🇰',
    'pa_Guru': '🌍',
    'pa_Guru_IN': '🇮🇳',
    'pl': '🌍',
    'pl_PL': '🇵🇱',
    'plt': '🌍',
    'plt_MG': '🇲🇬',
    'prg': '🌍',
    'prg_001': '🌐',
    'ps': '🌍',
    'ps_AF': '🇦🇫',
    'pt': '🌍',
    'pt_AO': '🇦🇴',
    'pt_BR': '🇧🇷',
    'pt_CH': '🇨🇭',
    'pt_CV': '🇨🇻',
    'pt_GQ': '🇬🇶',
    'pt_GW': '🇬🇼',
    'pt_LU': '🇱🇺',
    'pt_MO': '🇲🇴',
    'pt_MZ': '🇲🇿',
    'pt_PT': '🇵🇹',
    'pt_ST': '🇸🇹',
    'pt_TL': '🇹🇱',
    'qu': '🌎',
    'qu_BO': '🇧🇴',
    'qu_EC': '🇪🇨',
    'qu_PE': '🇵🇪',
    'quh': '🌎',
    'quh_BO': '🇧🇴',
    'rm': '🌍',
    'rm_CH': '🇨🇭',
    'rn': '🌍',
    'rn_BI': '🇧🇮',
    'ro': '🌍',
    'ro_MD': '🇲🇩',
    'ro_RO': '🇷🇴',
    'rof': '🌍',
    'rof_TZ': '🇹🇿',
    'root': '🌐',
    'ru': '🌍',
    'ru_BY': '🇧🇾',
    'ru_KG': '🇰🇬',
    'ru_KZ': '🇰🇿',
    'ru_MD': '🇲🇩',
    'ru_RU': '🇷🇺',
    'ru_UA': '🇺🇦',
    'rw': '🌍',
    'rw_RW': '🇷🇼',
    'rwk': '🌍',
    'rwk_TZ': '🇹🇿',
    'sah': '🌍',
    'sah_RU': '🇷🇺',
    'saq': '🌍',
    'saq_KE': '🇰🇪',
    'sbp': '🌍',
    'sbp_TZ': '🇹🇿',
    'sd': '🌍',
    'sd_PK': '🇵🇰',
    'se': '🌍',
    'se_FI': '🇫🇮',
    'se_NO': '🇳🇴',
    'se_SE': '🇸🇪',
    'seh': '🌍',
    'seh_MZ': '🇲🇿',
    'ses': '🌍',
    'ses_ML': '🇲🇱',
    'sg': '🌍',
    'sg_CF': '🇨🇫',
    'sh': '🌍',
    'sh_ME': '🇲🇪',
    'sh_RS': '🇷🇸',
    'sh_YU': '🌍',
    'shi': '🌍',
    'shi_Latn': '🌍',
    'shi_Latn_MA': '🇲🇦',
    'shi_Tfng': '🌍',
    'shi_Tfng_MA': '🇲🇦',
    'shs': '🌎',
    'shs_CA': '🇨🇦',
    'si': '🌍',
    'si_LK': '🇱🇰',
    'sk': '🌍',
    'sk_SK': '🇸🇰',
    'sl': '🌍',
    'sl_SI': '🇸🇮',
    'smj': '🌍',
    'smj_NO': '🇳🇴',
    'smj_SE': '🇸🇪',
    'smn': '🌍',
    'smn_FI': '🇫🇮',
    'sn': '🌍',
    'sn_ZW': '🇿🇼',
    'so': '🌍',
    'so_DJ': '🇩🇯',
    'so_ET': '🇪🇹',
    'so_KE': '🇰🇪',
    'so_SO': '🇸🇴',
    'sq': '🌍',
    'sq_AL': '🇦🇱',
    'sq_MK': '🇲🇰',
    'sq_XK': '🇽🇰',
    'sr': '🌍',
    'sr_ME': '🇲🇪',
    'sr_RS': '🇷🇸',
    'sr_YU': '🌍',
    'sr_Cyrl': '🌍',
    'sr_Cyrl_BA': '🇧🇦',
    'sr_Cyrl_ME': '🇲🇪',
    'sr_Cyrl_RS': '🇷🇸',
    'sr_Cyrl_XK': '🇽🇰',
    'sr_Latn': '🌍',
    'sr_Latn_BA': '🇧🇦',
    'sr_Latn_ME': '🇲🇪',
    'sr_Latn_RS': '🇷🇸',
    'sr_Latn_XK': '🇽🇰',
    'ss': '🌍',
    'ss_ZA': '🇿🇦',
    'st': '🌍',
    'st_ZA': '🇿🇦',
    'su': '🌏',
    'su_ID': '🇮🇩',
    'sv': '🌍',
    'sv_AX': '🇦🇽',
    'sv_FI': '🇫🇮',
    'sv_SE': '🇸🇪',
    'sw': '🌍',
    'sw_CD': '🇨🇩',
    'sw_KE': '🇰🇪',
    'sw_TZ': '🇹🇿',
    'sw_UG': '🇺🇬',
    'ta': '🌏',
    'ta_IN': '🇮🇳',
    'ta_LK': '🇱🇰',
    'ta_MY': '🇲🇾',
    'ta_SG': '🇸🇬',
    'te': '🌏',
    'te_IN': '🇮🇳',
    'teo': '🌍',
    'teo_KE': '🇰🇪',
    'teo_UG': '🇺🇬',
    'tet': '🌏',
    'tet_ID': '🇮🇩',
    'tet_TL': '🇹🇱',
    'tg': '🌍',
    'tg_TJ': '🇹🇯',
    'th': '🌏',
    'th_TH': '🇹🇭',
    'ti': '🌍',
    'ti_ER': '🇪🇷',
    'ti_ET': '🇪🇹',
    'tk': '🌍',
    'tk_TM': '🇹🇲',
    'tl': '🌏',
    'tl_PH': '🇵🇭',
    'tn': '🌍',
    'tn_BW': '🇧🇼',
    'tn_ZA': '🇿🇦',
    'to': '🌏',
    'to_TO': '🇹🇴',
    'tpi': '🌏',
    'tpi_PG': '🇵🇬',
    'tr': '🌍',
    'tr_CY': '🇨🇾',
    'tr_TR': '🇹🇷',
    'ts': '🌍',
    'ts_ZA': '🇿🇦',
    'tt': '🌍',
    'tt_RU': '🇷🇺',
    'twq': '🌍',
    'twq_NE': '🇳🇪',
    'tzm': '🌍',
    'tzm_MA': '🇲🇦',
    'ug': '🌏',
    'ug_CN': '🇨🇳',
    'uk': '🌍',
    'uk_UA': '🇺🇦',
    'ur': '🌏',
    'ur_IN': '🇮🇳',
    'ur_PK': '🇵🇰',
    'uz': '🌍',
    'uz_Arab': '🌍',
    'uz_Arab_AF': '🇦🇫',
    'uz_Cyrl': '🌍',
    'uz_Cyrl_UZ': '🇺🇿',
    'uz_Latn': '🌍',
    'uz_Latn_UZ': '🇺🇿',
    'uz_UZ': '🇺🇿',
    'vai': '🌍',
    'vai_Latn': '🌍',
    'vai_Latn_LR': '🇱🇷',
    'vai_Vaii': '🌍',
    'vai_Vaii_LR': '🇱🇷',
    've': '🌍',
    've_ZA': '🇿🇦',
    'vi': '🌏',
    'vi_VN': '🇻🇳',
    'vo': '🌍',
    'vo_001': '🌐',
    'vun': '🌍',
    'vun_TZ': '🇹🇿',
    'wa': '🌍',
    'wa_BE': '🇧🇪',
    'wae': '🌍',
    'wae_CH': '🇨🇭',
    'wo': '🌍',
    'wo_SN': '🇸🇳',
    'xh': '🌍',
    'xh_ZA': '🇿🇦',
    'xog': '🌍',
    'xog_UG': '🇺🇬',
    'yav': '🌍',
    'yav_CM': '🇨🇲',
    'yi': '🌍',
    'yi_001': '🌐',
    'yi_US': '🇺🇸',
    'yo': '🌍',
    'yo_BJ': '🇧🇯',
    'yo_NG': '🇳🇬',
    'yue': '🌏',
    'yue_Hans': '🌏',
    'yue_Hans_CN': '🇨🇳',
    'yue_Hant': '🌏',
    'yue_Hant_HK': '🇭🇰',
    'zgh': '🌍',
    'zgh_MA': '🇲🇦',
    'zh': '🌏',
    'zh_HK': '🇭🇰',
    'zh_Hans': '🌏',
    'zh_Hans_CN': '🇨🇳',
    'zh_Hans_HK': '🇭🇰',
    'zh_Hans_MO': '🇲🇴',
    'zh_Hans_SG': '🇸🇬',
    'zh_Hant': '🌏',
    'zh_Hant_HK': '🇭🇰',
    'zh_Hant_MO': '🇲🇴',
    'zh_Hant_TW': '🇹🇼',
    'zh_TW': '🇹🇼',
    'zu': '🌍',
    'zu_ZA': '🇿🇦',
}

SPANISH_419_LOCALES = (
    'es_AR', 'es_MX', 'es_BO', 'es_CL', 'es_CO', 'es_CR',
    'es_CU', 'es_DO', 'es_EC', 'es_GT', 'es_HN', 'es_NI',
    'es_PA', 'es_PE', 'es_PR', 'es_PY', 'es_SV', 'es_US',
    'es_UY', 'es_VE',)

def expand_languages(languages):
    # pylint: disable=line-too-long
    '''Expands the given list of languages by including fallbacks.

    Returns a possibly longer list of languages by adding
    aliases and fallbacks.

    :param languages: A list of languages (or locale names)
    :type languages: List of strings
    :rtype: List  of strings

    Examples:

    >>> expand_languages(['es_MX', 'es_ES', 'ja_JP'])
    ['es_MX', 'es_419', 'es', 'es_ES', 'es', 'ja_JP', 'ja', 'en']

    >>> expand_languages(['zh_Hant', 'zh_CN', 'zh_TW', 'zh_SG', 'zh_HK', 'zh_MO'])
    ['zh_Hant', 'zh_CN', 'zh', 'zh_TW', 'zh_Hant', 'zh_SG', 'zh', 'zh_HK', 'zh_Hant', 'zh_MO', 'zh_Hant', 'en']

    >>> expand_languages(['en_GB', 'en'])
    ['en_GB', 'en_001', 'en', 'en', 'en_001']

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
        if (language not in ('zh_TW', 'zh_HK', 'zh_MO', 'zh_Hant')
                and language.split('_')[:1] != [language]):
            expanded_languages += language.split('_')[:1]
    if 'en' not in expanded_languages:
        expanded_languages.append('en')
    return expanded_languages

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
    while (token
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
    while (token
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

def color_string_to_argb(color_string):
    '''
    Converts a color string to a 32bit  ARGB value

    :param color_string: The color to convert to 32bit ARGB
    :type color_string: String
                        - Standard name from the X11 rgb.txt
                        - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                     or ”#rrrrggggbbbb”
                        - RGB color: “rgb(r,g,b)”
                        - RGBA color: “rgba(r,g,b,a)”
    :rtype: Integer

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
            + ((int(gdk_rgba.blue * 0xff) & 0xff)))

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

def is_right_to_left_messages():
    '''
    Check whether the effective LC_MESSAGES locale points to a languages
    which is usually written  in a right-to-left script.

    :return: True if right-to-left, False if not.
    :rtype: Boolean
    '''
    lc_messages_locale, dummy_lc_messages_encoding = locale.getlocale(
        category=locale.LC_MESSAGES)
    if not lc_messages_locale:
        return False
    lang = lc_messages_locale.split('_')[0]
    if lang in ('ar', 'arc', 'dv', 'fa', 'he', 'ps', 'ur', 'yi'):
        # 'ku' could be Latin script or Arabic script or even Cyrillic
        # or Armenian script
        return True
    return False

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
    if type_string == 'i':
        return variant.get_int32()
    if type_string == 'b':
        return variant.get_boolean()
    if type_string == 'v':
        return variant.unpack()
    if type_string and type_string[0] == 'a':
        return variant.unpack()
    print('error: unknown variant type: %s' % type_string)
    return variant

def dict_update_existing_keys(pdict, other_pdict):
    '''Update values of existing keys in a Python dict from another Python dict

    Using pdict.update(other_pdict) would add keys and values from other_pdict
    to pdict even for keys which do not exist in pdict. Sometimes I want
    to update only existing keys and ignore new keys.

    :param pdict: The Python dict to update
    :type pdict: Python dict
    :param other_pdict: The Python dict to get the updates from
    :type other_pdict: Python dict

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

def distro_id():
    '''
    Compatibility wrapper around distro.id()

    :rtype: String

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
        return distro.id()
    return ''

def find_hunspell_dictionary(language):
    '''
    Find the hunspell dictionary file for a language

    :param language: The language of the dictionary to search for
    :type language: String
    :rtype: tuple of the form (dic_path, aff_path) where
            dic_path is the full path of the .dic file found
            and aff_path is the full path of the .aff file found.
            If no dictionary can be found for the requested language,
            the return value is ('', '').
    '''
    datadir = os.path.join(os.path.dirname(__file__), '../data')
    user_datadir = xdg_save_data_path('ibus-typing-booster/data')
    dirnames = [
        user_datadir,
        datadir,
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
    (dic_path, aff_path) = find_hunspell_dictionary(language)
    if not dic_path:
        return ('', '', [])
    LOGGER.info('%s file found.', dic_path)
    dictionary_encoding = 'UTF-8'
    if os.path.isfile(aff_path):
        aff_buffer = ''
        try:
            with open(aff_path,
                      mode='r',
                      encoding='ISO-8859-1',
                      errors='ignore') as aff_file:
                aff_buffer = aff_file.read().replace('\r\n', '\n')
        except (FileNotFoundError, PermissionError):
            LOGGER.exception('Error loading .aff File: %s', aff_path)
        except Exception:
            LOGGER.exception(
                'Unexpected error loading .aff File: %s', aff_path)
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
    dic_buffer = ''
    try:
        with open(dic_path, encoding=dictionary_encoding) as dic_file:
            dic_buffer = dic_file.readlines()
    except (UnicodeDecodeError, FileNotFoundError, PermissionError):
        LOGGER.exception(
            'loading %s as %s encoding failed, fall back to ISO-8859-1.',
            dic_path, dictionary_encoding)
        dictionary_encoding = 'ISO-8859-1'
        try:
            with open(dic_path, encoding=dictionary_encoding) as dic_file:
                dic_buffer = dic_file.readlines()
        except (UnicodeDecodeError, FileNotFoundError, PermissionError):
            LOGGER.exception(
                'loading %s as %s encoding failed, giving up.',
                dic_path, dictionary_encoding)
            return ('', '', [])
        except Exception:
            LOGGER.exception(
                'Unexpected error loading .dic File: %s', dic_path)
            return ('', '', [])
    except Exception:
        LOGGER.exeption(
            'Unexpected error loading .dic File: %s', dic_path)
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

class ComposeSequences:
    '''Class to handle compose sequences.

    Finds all compose files, i.e. the system wide compose file
    for the current locale and the compose files from the users
    home directory and stores the compose sequences found there
    in an internal variable.
    '''
    def __init__(self):
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
            IBus.KEY_Multi_key: '⎄',
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
            # Extra dead elements for German T3 layout: (in
            # /usr/include/X11/keysymdef.h but they don’t exist in
            # ibus.
            #
            # IBus.KEY_dead_lowline: '_',
            # IBus.KEY_dead_aboveverticalline: '\u00A0\u030D',
            # IBus.KEY_dead_belowverticalline: '\u00A0\u0329',
            # IBus.KEY_dead_longsolidusoverlay: '\u00A0\u0338',
            #
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
        self._dead_keys = {
            # See also /usr/include/X11/keysymdef.h and
            # ibus/src/ibusenginesimple.c
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
            # IBus.KEY_dead_currency: '', # FIXME
            # dead_dasia is an alias for dead_abovereversedcomma
            IBus.KEY_dead_dasia: '\u0314', # COMBINING REVERSED COMMA ABOVE
            IBus.KEY_dead_diaeresis: '\u0308', # COMBINING DIAERESIS
            IBus.KEY_dead_doubleacute: '\u030B', # COMBINING DOUBLE ACUTE ACCENT
            IBus.KEY_dead_doublegrave: '\u030F', # COMBINING DOUBLE GRAVE ACCENT
            IBus.KEY_dead_grave: '\u0300', # COMBINING GRAVE ACCENT
            # IBus.KEY_dead_greek: '', # FIXME
            IBus.KEY_dead_hook: '\u0309', # COMBINING HOOK ABOVE
            IBus.KEY_dead_horn: '\u031B', # COMBINING HORN
            IBus.KEY_dead_invertedbreve: '\u0311', # COMBINING INVERTED BREVE
            # IBus.KEY_dead_iota: '', # FIXME
            IBus.KEY_dead_macron: '\u0304', # COMBINING MACRON
            IBus.KEY_dead_ogonek: '\u0328', # COMBINING OGONEK
            # dead_perispomeni is an alias for dead_tilde
            IBus.KEY_dead_perispomeni: '\u0303', # COMBINING TILDE
            # dead_psili is an alias for dead_abovecomma
            IBus.KEY_dead_psili: '\u0313', # COMBINING COMMA ABOVE
            # IBus.KEY_dead_semivoiced_sound: '', # FIXME
            IBus.KEY_dead_stroke: '\u0336', # COMBINING LONG STROKE OVERLAY
            # FIXME: 0335;COMBINING SHORT STROKE OVERLAY ???
            IBus.KEY_dead_tilde: '\u0303', # COMBINING TILDE
            # IBus.KEY_dead_voiced_sound: '゛', # FIXME
            #
            # Extra dead elements for German T3 layout: (in
            # /usr/include/X11/keysymdef.h but they don’t exist in
            # ibus.
            #
            # IBus.KEY_dead_lowline: '\u0332', # COMBINING LOW LINE
            # IBus.KEY_dead_aboveverticalline: '\u030D', # COMBINING VERTICAL LINE ABOVE
            # IBus.KEY_dead_belowverticalline: '\u0329', # COMBINING VERTICAL LINE BELOW
            # IBus.KEY_dead_longsolidusoverlay: '\u0338', # COMBINING LONG SOLIDUS OVERLAY
            #
            # Dead vowels for universal syllable entry:
            # IBus.KEY_dead_a: 'ぁ', # FIXME
            # IBus.KEY_dead_A: 'あ', # FIXME
            # IBus.KEY_dead_i: 'ぃ', # FIXME
            # IBus.KEY_dead_I: 'い', # FIXME
            # IBus.KEY_dead_u: 'ぅ', # FIXME
            # IBus.KEY_dead_U: 'う', # FIXME
            # IBus.KEY_dead_e: 'ぇ', # FIXME
            # IBus.KEY_dead_E: 'え', # FIXME
            # IBus.KEY_dead_o: 'ぉ', # FIXME
            # IBus.KEY_dead_O: 'お', # FIXME
            IBus.KEY_dead_small_schwa: '\u1DEA ', # COMBINING LATIN SMALL LETTER SCHWA
            # IBus.KEY_dead_capital_schwa: '', # FIXME
        }
        self._compose_sequences = {}
        compose_file_paths = []
        compose_file_paths.append(self._locale_compose_file())
        compose_file_paths.append(os.path.expanduser('~/.config/ibus/Compose'))
        # For the meaning of XCOMPOSEFILE, see
        # https://www.x.org/releases/X11R7.5/doc/man/man5/Compose.5.html
        user_compose_file = os.environ.get(
            'XCOMPOSEFILE') or os.path.expanduser('~/.XCompose')
        compose_file_paths.append(user_compose_file)
        for path in compose_file_paths:
            self._read_compose_file(path)

    def _add_compose_sequence(self, sequence, result):
        # pylint: disable=line-too-long
        '''Adds a compose sequence to self._compose_sequences

        :param sequence: Keysyms of the compose sequence as written
                         in Compose files
        :type sequence: String
        :param result: The result which should be inserted when typing that
                       compose sequence
        :type result: String

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
        '''
        # pylint: enable=line-too-long
        names = re.sub(r'[<>\s]+', ' ', sequence).strip().split()
        keyvals = []
        for name in names:
            if re.match(r'U[0-9a-fA-F]{4}', name):
                keyvals.append(int(name[1:], 16))
            else:
                try:
                    keyvals.append(eval('IBus.KEY_' + name))
                except AttributeError:
                    LOGGER.error(
                        'Invalid compose sequence. keysym "%s" does not exist.'
                        % name)
                    return
        if not keyvals:
            return
        compose_sequences = self._compose_sequences
        for keyval in keyvals:
            if (not keyval in compose_sequences
                or isinstance(compose_sequences[keyval], str)):
                compose_sequences[keyval] = {}
            last_compose_sequences = compose_sequences
            last_keyval = keyval
            compose_sequences = compose_sequences[keyval]
        last_compose_sequences[last_keyval] = result

    def _locale_compose_file(self):
        '''Returns the full path of the default compose file for the current
        locale

        :rtype: String
        '''
        lc_ctype_locale, lc_ctype_encoding = locale.getlocale(
            category=locale.LC_CTYPE)
        if lc_ctype_encoding not in ('UTF-8', 'utf8'):
            LOGGER.warning('Not running in an UTF-8 locale: %s.%s',
                           lc_ctype_locale, lc_ctype_encoding)
        xorg_locale_path = '/usr/share/X11/locale'
        for loc in (lc_ctype_locale, 'en_US'):
            locale_compose_file = os.path.join(
                xorg_locale_path, loc + '.UTF-8', 'Compose')
            if os.path.isfile(locale_compose_file):
                return locale_compose_file
        return ''

    def _read_compose_file(self, compose_path):
        '''Reads a compose file and stores the compose sequences
        found  there in self._compose_sequences.

        :param compose_path: Path to a compose file to read
        :type compose_path: String
        '''
        if not compose_path or not os.path.isfile(compose_path):
            LOGGER.info('Skipping reading of compose file "%s"', compose_path)
            return
        try:
            with open(compose_path,
                      mode='r',
                      encoding='UTF-8',
                      errors='ignore') as compose_file:
                lines = compose_file.readlines()
        except FileNotFoundError:
            LOGGER.exception('Errror loading %s: %s',
                             compose_path, _('File not found'))
        except PermissionError:
            LOGGER.exception('Error loading %s: %s',
                             compose_path, _('Permission error'))
        except UnicodeDecodeError:
            LOGGER.exception('Error loading %s: %s',
                             compose_path, _('Unicode decoding error'))
        except Exception:
            LOGGER.exception('Unexpected error loading %s: %s',
                             compose_path, _('Unknown error'))
        if not lines:
            LOGGER.warning('File %s has no content', compose_path)
            return
        LOGGER.info('Reading compose file %s', compose_path)
        # For the syntax of the compose files see:
        # https://www.x.org/releases/X11R7.5/doc/man/man5/Compose.5.html
        include_pattern = re.compile(
            r'^\s*include\s*"(?P<include_path>[^"]+)".*')
        compose_sequence_pattern = re.compile(
            r'^\s*(?P<sequence>(<[a-zA-Z0-9_]+>\s*)+):\s*"(?P<result>(\\"|[^"])+)".*')
        for line in lines:
            if not line.strip():
                continue
            match = include_pattern.search(line)
            if match:
                include_path = match.group('include_path')
                include_path = include_path.replace(
                    '%L', self._locale_compose_file())
                include_path = include_path.replace(
                    '%H', os.path.expanduser('~'))
                include_path = os.path.normpath(include_path)
                self._read_compose_file(include_path)
            match = compose_sequence_pattern.search(line)
            if match:
                sequence = match.group('sequence')
                result = match.group('result').replace('\\"', '"')
                self._add_compose_sequence(sequence, result)

    def preedit_representation(self, keyvals):
        # pylint: disable=line-too-long
        '''Returns a text to display in the preedit for a partially
        typed compose sequence.

        :param keyvals: A list of key values
        :type keyvals: List of integers
        :return: The text to display in the preedit for a partially
                 typed compose sequence consisting of these key values
        :rtype: String

        Examples:

        >>> c = ComposeSequences()
        >>> c.preedit_representation([IBus.KEY_Multi_key, IBus.KEY_asciitilde, IBus.KEY_dead_circumflex])
        '⎄~^'
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
        return representation

    def _compose_dead_key_sequence(self, keyvals):
        # pylint: disable=line-too-long
        '''
        Interprets a list of key values as a dead key sequence

        :param keyvals: A list of key values
        :type kevals: List of integers
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
        :rtype: String (possibly empty) or None

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
                    or not unicodedata.category(character) in ('Lu', 'Ll')):
                    return '' # Invalid dead key sequence
                combining_sequence = character + combining_sequence
        return unicodedata.normalize('NFC', combining_sequence)

    def compose(self, keyvals):
        # pylint: disable=line-too-long
        '''
        Interprets a list of key values as a compose sequence

        :param keyvals: A list of key values
        :type keyvals: List of integers
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
        :rtype: String (posssibly empty) or None

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

        Not defined in any Compose file, but nevertheless valid
        because it is interpreted as a “reasonable” dead key sequence:

        >>> c.compose([IBus.KEY_dead_circumflex, IBus.KEY_x])
        '\u0078\u0302'
        '''
        # pylint: enable=line-too-long
        if not keyvals:
            return ''
        compose_sequences = self._compose_sequences
        for keyval in keyvals:
            if keyval not in compose_sequences:
                # This sequence is not defined in any of the Compose
                # files read. In that sense it is an invalid sequence
                # and “return ''” would be appropriate here.  But
                # instead of just “return ''”, try whether it can be
                # interpreted as a “reasonable” dead key sequence:
                return self._compose_dead_key_sequence(keyvals)
            if isinstance(compose_sequences[keyval], str):
                return compose_sequences[keyval]
            compose_sequences = compose_sequences[keyval]
        return None

class M17nDbInfo:
    '''Class to find and store information about the available input
    methods from m17n-db.
    '''
    def __init__(self):
        self._dirs = []
        self._imes = {}
        self._find_dirs()
        self._find_imes()

    def _find_dirs(self):
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
            result = subprocess.run([m17n_db_binary], stdout=subprocess.PIPE)
            system_dir = result.stdout.strip().decode('UTF-8')
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

    def _find_imes(self):
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
            }
        for dirname in self._dirs:
            for mim_path in glob.glob(os.path.join(dirname, '*.mim')):
                try:
                    with open(mim_path,
                              mode='r',
                              encoding='UTF-8',
                              errors='ignore') as ime_file:
                        full_contents = ime_file.read()
                except FileNotFoundError:
                    LOGGER.exception('Errror loading %s: %s',
                                     mim_path, _('File not found'))
                except PermissionError:
                    LOGGER.exception('Error loading %s: %s',
                                     mim_path, _('Permission error'))
                except UnicodeDecodeError:
                    LOGGER.exception('Error loading %s: %s',
                                     mim_path, _('Unicode decoding error'))
                except Exception:
                    LOGGER.exception('Unexpected error loading %s: %s',
                                     mim_path, _('Unknown error'))
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
                title_pattern = re.compile(
                    r'\([\s]*title[\s]*"(?P<title>.+?)(?<!\\)"[\s]*\)',
                    re.DOTALL|re.MULTILINE|re.UNICODE)
                match = title_pattern.search(full_contents)
                if match:
                    title = match.group('title').replace('\\"', '"')
                    self._imes[ime]['title'] = title
                description_pattern = re.compile(
                    r'\([\s]*description[\s]*'
                    r'"(?P<description>.+?)(?<!\\)"[\s]*\)',
                    re.DOTALL|re.MULTILINE|re.UNICODE)
                match = description_pattern.search(full_contents)
                if match:
                    description = match.group('description').replace(
                        '\\"', '"')
                    self._imes[ime]['description'] = description
                self._imes[ime]['content'] = full_contents

    def get_dirs(self):
        '''
        Returns the list of directories  which contain the m17n input methods.

        There has be one system directory (e.g. /usr/share/m17n) and
        it is possible that there is also a user directory indicated
        by the M17NDIR environment variable. If the environment
        variable M17NDIR is not set, the user directory is '~/.m17nd.'
        if that directory exists.

        :return: A list of one or two directories
        :rtype: List of strings

        '''
        return self._dirs[:]

    def get_imes(self):
        '''Get a list of the available input methods

        The special input method 'NoIME' should always be first
        in the list returned.

        :return: A list of names of the available input methods.
        :rtype: List of strings
        '''
        return sorted(self._imes)

    def get_path(self, ime):
        '''Get the full path of the implementation file of the input method.

        :param ime: Name of the input method
        :type ime: String
        :return: Path of the implementation file of the input method.
                 Empty string if no file has been found implementing “ime”
        :rtype: String

        '''
        if ime in self._imes and 'path' in self._imes[ime]:
            return self._imes[ime]['path']
        return ''

    def get_title(self, ime):
        '''Get the title of the input method.

        :param ime: Name of the input method
        :type ime: String
        :return: Title of the input method.
                 Empty string if no title has been found.
        :rtype: String
        '''
        if ime in self._imes and 'title' in self._imes[ime]:
            return self._imes[ime]['title']
        return ''

    def get_description(self, ime):
        '''Get the description of the input method.

        :param ime: Name of the input method
        :type ime: String
        :return: Description of the input method.
                 Empty string if no description has been found.
        :rtype: String
        '''
        if ime in self._imes and 'description' in self._imes[ime]:
            return self._imes[ime]['description']
        return ''

    def get_content(self, ime):
        '''Get the content of the implementation file of the input method.

        :param ime: Name of the input method
        :type ime: String
        :return: Content of the implementation file of the input method.
                 Empty string if no content has been found.
        :rtype: String
        '''
        if ime in self._imes and 'content' in self._imes[ime]:
            return self._imes[ime]['content']
        return ''

    def __str__(self):
        return repr(self._imes)

def xdg_save_data_path(*resource):
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
    resource = os.path.join(*resource)
    assert not resource.startswith('/')
    path = os.path.join(xdg_data_home, resource)
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
    def __init__(self):
        self.keyvals_to_keycodes = {}
        display = Gdk.Display.get_default()
        keymap = Gdk.Keymap.get_for_display(display)
        for keycode in range(0, 256):
            (keycode_found,
             dummy_keymapkeys,
             keyvals) = Gdk.Keymap.get_entries_for_keycode(keymap, keycode)
            if keycode_found:
                for keyval in keyvals:
                    if keyval:
                        if (keyval in self.keyvals_to_keycodes
                            and
                            keycode not in self.keyvals_to_keycodes[keyval]):
                            self.keyvals_to_keycodes[keyval].append(keycode)
                        else:
                            self.keyvals_to_keycodes[keyval] = [keycode]
        # Gdk.Keymap.get_entries_for_keycode() seems to never find any
        # key codes on big endian platforms (s390x). Might be a bug in
        # that function. Until I figure out what the problem really
        # is, fall back to the standard us layout for the most
        # important key values:
        self._standard_us_layout_keyvals_to_keycodes = {
            IBus.KEY_Left: [113],
            IBus.KEY_BackSpace: [22],
            IBus.KEY_a: [38],
        }
        for keyval in self._standard_us_layout_keyvals_to_keycodes:
            if keyval not in self.keyvals_to_keycodes:
                LOGGER.warning('No keycodes found: keyval: %s name: %s',
                               keyval, IBus.keyval_name(keyval))
                self.keyvals_to_keycodes[keyval] = (
                    self._standard_us_layout_keyvals_to_keycodes[keyval])

    def keycodes(self, keyval):
        '''Returns a list of key codes of the hardware keys which can generate
        the given key value on the current keyboard layout.

        :param keyval: A key value
        :type keyval: Integer
        :return: A list of key codes of hardware keys, possibly empty
        :rtype: List of integers between 9 and 255

        '''
        if keyval in self.keyvals_to_keycodes:
            return self.keyvals_to_keycodes[keyval]
        return []

    def keycode(self, keyval):
        '''Returns one key code of one hardware key which can generate the
        given key value (there may be more than one, see the
        keycodes() function.

        :param keyval: A key value
        :type keyval: Integer
        :return: One key code of a hardware key which can generate
                 the given key value
        :rtype: Integer between 9 and 255

        '''
        keycodes = self.keycodes(keyval)
        if keycodes:
            return keycodes[0]
        return 0

    def ibus_keycodes(self, keyval):
        '''Returns a list of ibus key codes of the hardware keys which can
        generate the given key value on the current keyboard layout.

        ibus key codes are calculated by subtracting 8 from the
        “normal” key codes.  The smallest possible keycode seems to be
        9 (usually mapped to Escape).  Therefore, after subtracting 8
        it is at least 1.

        :param keyval: A key value
        :type keyval: Integer
        :return: A list of ibus key codes of hardware keys, possibly empty
        :rtype: List of integers between 1 and 247

        '''
        if keyval in self.keyvals_to_keycodes:
            return [max(0, x - 8) for x in self.keyvals_to_keycodes[keyval]]
        return []

    def ibus_keycode(self, keyval):
        '''Returns one ibus key code of one hardware key which can generate
        the given key value (there may be more than one, see the
        ibus_keycodes() function)

        ibus key codes are calculated by subtracting 8 from the
        “normal” key codes.  The smallest possible keycode seems to be
        9 (usually mapped to Escape).  Therefore, after subtracting 8
        it is at least 1.

        :param keyval: A key value
        :type keyval: Integer
        :return: One ibus key code of a hardware key which can generate
                 the given key value
        :rtype: Integer between 1 and 247
        '''
        return max(0, self.keycode(keyval) - 8)

    def __str__(self):
        return_string = ''
        for keyval in sorted(self.keyvals_to_keycodes):
            return_string += 'keyval: %s name: %s keycodes: %s\n' % (
                keyval, IBus.keyval_name(keyval),
                self.keyvals_to_keycodes[keyval])
        return return_string

class KeyEvent:
    '''Key event class used to make the checking of details of the key
    event easy
    '''
    def __init__(self, keyval, keycode, state):
        self.val = keyval
        self.code = keycode
        self.state = state
        self.name = IBus.keyval_name(self.val)
        self.unicode = IBus.keyval_to_unicode(self.val)
        self.msymbol = self.unicode
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
        self.super = self.state & IBus.ModifierType.SUPER_MASK != 0
        self.hyper = self.state & IBus.ModifierType.HYPER_MASK != 0
        self.meta = self.state & IBus.ModifierType.META_MASK != 0
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

    def __eq__(self, other):
        if (self.val == other.val
                and self.code == other.code
                and self.state == other.state):
            return True
        return False

    def __ne__(self, other):
        if (self.val != other.val
                or self.code != other.code
                or self.state != other.state):
            return True
        return False

    def __str__(self):
        return (
            "val=%s code=%s state=0x%08x name='%s' unicode='%s' msymbol='%s' "
            % (self.val,
               self.code,
               self.state,
               self.name,
               self.unicode,
               self.msymbol)
            + "shift=%s lock=%s control=%s super=%s hyper=%s meta=%s "
            % (self.shift,
               self.lock,
               self.control,
               self.super,
               self.hyper,
               self.meta)
            + "mod1=%s mod5=%s release=%s\n"
            % (self.mod1,
               self.mod5,
               self.release))

def keyevent_to_keybinding(keyevent):
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

def keybinding_to_keyevent(keybinding):
    name = keybinding.split('+')[-1]
    keyval = IBus.keyval_from_name(name)
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
    def __init__(self, keybindings):
        self._hotkeys = {}
        for command in keybindings:
            for keybinding in keybindings[command]:
                key = keybinding_to_keyevent(keybinding)
                val = key.val
                state = key.state & KEYBINDING_STATE_MASK
                if command in self._hotkeys:
                    self._hotkeys[command].append((val, state))
                else:
                    self._hotkeys[command] = [(val, state)]

    def __contains__(self, command_key_tuple):
        if not isinstance(command_key_tuple, tuple):
            return False
        command = command_key_tuple[1]
        key = command_key_tuple[0]
        val = key.val
        state = key.state & KEYBINDING_STATE_MASK
        if command in self._hotkeys:
            if (val, state) in self._hotkeys[command]:
                return True
        return False

    def __str__(self):
        return repr(self._hotkeys)

class ItbKeyInputDialog(Gtk.MessageDialog):
    def __init__(
            self,
            # Translators: This is used in the title bar of a dialog window
            # requesting that the user types a key to be used as a new
            # key binding for a command.
            title=_('Key input'),
            parent=None):
        Gtk.Dialog.__init__(
            self,
            title=title,
            parent=parent)
        self.add_button(_('Cancel'), Gtk.ResponseType.CANCEL)
        self.set_modal(True)
        self.set_markup(
            '<big><b>%s</b></big>'
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

    def on_key_press_event(# pylint: disable=no-self-use
            self, widget, event):
        widget.e = (event.keyval,
                    event.get_state() & KEYBINDING_STATE_MASK)
        return True
    def on_key_release_event(# pylint: disable=no-self-use
            self, widget, _event):
        widget.response(Gtk.ResponseType.OK)
        return True

class ItbAboutDialog(Gtk.AboutDialog):
    def  __init__(self, parent=None):
        Gtk.AboutDialog.__init__(self, parent=parent)
        self.set_modal(True)
        # An empty string in aboutdialog.set_logo_icon_name('')
        # prevents an ugly default icon to be shown. We don’t yet
        # have nice icons for ibus-typing-booster.
        self.set_logo_icon_name('')
        self.set_title(
            '🚀 ibus-typing-booster %s' %version.get_version())
        self.set_program_name(
            '🚀 ibus-typing-booster')
        self.set_version(version.get_version())
        self.set_comments(
            _('A completion input method to speedup typing.'))
        self.set_copyright(
            'Copyright © 2017–2019 Mike FABIAN')
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
            self, _about_dialog, _response):
        '''
        The “About” dialog has been closed by the user

        :param _about_dialog: The “About” dialog
        :type _about_dialog: GtkDialog object
        :param _response: The response when the “About” dialog was closed
        :type _response: Gtk.ResponseType enum
        '''
        self.destroy()

# Audio recording parameters
AUDIO_RATE = 16000
AUDIO_CHUNK = int(AUDIO_RATE / 10)  # 100ms

class MicrophoneStream(object):
    '''Opens a recording stream as a generator yielding the audio chunks.

    This code is from:

    https://github.com/GoogleCloudPlatform/python-docs-samples/blob/master/speech/cloud-client/transcribe_streaming_mic.py

    https://github.com/GoogleCloudPlatform/python-docs-samples/blob/master/LICENSE

    GoogleCloudPlatform/python-docs-samples is licensed under the
    Apache License 2.0
    '''
    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
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

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
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
    (FAILED, ATTEMPTED) = doctest.testmod()
    if FAILED:
        sys.exit(1)
    sys.exit(0)
