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

import sys
import os
import re
import string
import unicodedata
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

IMPORT_XDG_BASEDIRECTORY_SUCCESSFUL = False
try:
    import xdg.BaseDirectory
    IMPORT_XDG_BASEDIRECTORY_SUCCESSFUL = True
except (ImportError,):
    IMPORT_XDG_BASEDIRECTORY_SUCCESSFUL = False

DOMAINNAME = 'ibus-typing-booster'
_ = lambda a: gettext.dgettext(DOMAINNAME, a)
N_ = lambda a: a

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
    'af_NA': {'inputmethods': ['NoIme'], 'dictionaries': ['af_NA']},
    'af_ZA': {'inputmethods': ['NoIme'], 'dictionaries': ['af_ZA']},
    'ak_GH': {'inputmethods': ['NoIme'], 'dictionaries': ['ak_GH']},
    'am_ET': {'inputmethods': ['am-sera'], 'dictionaries': ['am_ET']},
    'ar_AE': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_AE']},
    'ar_BH': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_BH']},
    'ar_DJ': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_DJ']},
    'ar_DZ': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_DZ']},
    'ar_EG': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_EG']},
    'ar_ER': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_ER']},
    'ar_IL': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_IL']},
    'ar_IN': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_IN']},
    'ar_IQ': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_IQ']},
    'ar_JO': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_JO']},
    'ar_KM': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_KM']},
    'ar_KW': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_KW']},
    'ar_LB': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_LB']},
    'ar_LY': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_LY']},
    'ar_MA': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_MA']},
    'ar_MR': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_MR']},
    'ar_OM': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_OM']},
    'ar_PS': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_PS']},
    'ar_QA': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_QA']},
    'ar_SA': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_SA']},
    'ar_SD': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_SD']},
    'ar_SO': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_SO']},
    'ar_SY': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_SY']},
    'ar_TD': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_TD']},
    'ar_TN': {'inputmethods':['NoIme'], 'dictionaries': ['ar_TN']},
    'ar_YE': {'inputmethods': ['NoIme'], 'dictionaries': ['ar_YE']},
    'as_IN': {'inputmethods': ['as-inscript2', 'NoIme'], 'dictionaries': ['as_IN', 'en_GB']},
    'ast_ES': {'inputmethods': ['NoIme'], 'dictionaries': ['ast_ES']},
    'az_AZ': {'inputmethods': ['NoIme'], 'dictionaries': ['az_AZ']},
    'be_BY': {'inputmethods': ['NoIme'], 'dictionaries': ['be_BY']},
    'ber_MA': {'inputmethods': ['NoIme'], 'dictionaries': ['ber_MA']},
    'bg_BG': {'inputmethods': ['NoIme'], 'dictionaries': ['bg_BG']},
    'bn_IN': {'inputmethods': ['bn-inscript2', 'NoIme'], 'dictionaries': ['bn_IN', 'en_GB']},
    'br_FR': {'inputmethods': ['NoIme'], 'dictionaries': ['br_FR']},
    'bs_BA': {'inputmethods': ['NoIme'], 'dictionaries': ['bs_BA']},
    'ca_AD': {'inputmethods': ['NoIme'], 'dictionaries': ['ca_AD']},
    'ca_ES': {'inputmethods': ['NoIme'], 'dictionaries': ['ca_ES']},
    'ca_FR': {'inputmethods': ['NoIme'], 'dictionaries': ['ca_FR']},
    'ca_IT': {'inputmethods': ['NoIme'], 'dictionaries': ['ca_IT']},
    'cop_EG': {'inputmethods': ['NoIme'], 'dictionaries': ['cop_EG']},
    'cs_CZ': {'inputmethods': ['NoIme'], 'dictionaries': ['cs_CZ']},
    'csb_PL': {'inputmethods': ['NoIme'], 'dictionaries': ['csb_PL']},
    'cv_RU': {'inputmethods': ['NoIme'], 'dictionaries': ['cv_RU']},
    'cy_GB': {'inputmethods': ['NoIme'], 'dictionaries': ['cy_GB']},
    'da_DK': {'inputmethods': ['NoIme'], 'dictionaries': ['da_DK']},
    'de_AT': {'inputmethods': ['NoIme'], 'dictionaries': ['de_AT']},
    'de_BE': {'inputmethods': ['NoIme'], 'dictionaries': ['de_BE']},
    'de_CH': {'inputmethods': ['NoIme'], 'dictionaries': ['de_CH']},
    'de_DE': {'inputmethods':['NoIme'], 'dictionaries': ['de_DE']},
    'de_LI': {'inputmethods': ['NoIme'], 'dictionaries': ['de_LI']},
    'de_LU': {'inputmethods': ['NoIme'], 'dictionaries': ['de_LU']},
    'dsb_DE': {'inputmethods': ['NoIme'], 'dictionaries': ['dsb_DE']},
    'el_CY': {'inputmethods': ['NoIme'], 'dictionaries': ['el_CY']},
    'el_GR': {'inputmethods': ['NoIme'], 'dictionaries': ['el_GR']},
    'en_AG': {'inputmethods': ['NoIme'], 'dictionaries': ['en_AG']},
    'en_AU': {'inputmethods': ['NoIme'], 'dictionaries': ['en_AU']},
    'en_BS': {'inputmethods': ['NoIme'], 'dictionaries': ['en_BS']},
    'en_BW': {'inputmethods': ['NoIme'], 'dictionaries': ['en_BW']},
    'en_BZ': {'inputmethods': ['NoIme'], 'dictionaries': ['en_BZ']},
    'en_CA': {'inputmethods': ['NoIme'], 'dictionaries': ['en_CA']},
    'en_DK': {'inputmethods': ['NoIme'], 'dictionaries': ['en_DK']},
    'en_GB': {'inputmethods': ['NoIme'], 'dictionaries': ['en_GB']},
    'en_GH': {'inputmethods': ['NoIme'], 'dictionaries': ['en_GH']},
    'en_HK': {'inputmethods': ['NoIme'], 'dictionaries': ['en_HK']},
    'en_IE': {'inputmethods': ['NoIme'], 'dictionaries': ['en_IE']},
    'en_IN': {'inputmethods': ['NoIme'], 'dictionaries': ['en_IN']},
    'en_JM': {'inputmethods': ['NoIme'], 'dictionaries': ['en_JM']},
    'en_MW': {'inputmethods': ['NoIme'], 'dictionaries': ['en_MW']},
    'en_NA': {'inputmethods': ['NoIme'], 'dictionaries': ['en_NA']},
    'en_NG': {'inputmethods': ['NoIme'], 'dictionaries': ['en_NG']},
    'en_NZ': {'inputmethods': ['NoIme'], 'dictionaries': ['en_NZ']},
    'en_PH': {'inputmethods': ['NoIme'], 'dictionaries': ['en_PH']},
    'en_SG': {'inputmethods': ['NoIme'], 'dictionaries': ['en_SG']},
    'en_TT': {'inputmethods': ['NoIme'], 'dictionaries': ['en_TT']},
    'en_US': {'inputmethods': ['NoIme'], 'dictionaries': ['en_US']},
    'en_ZA': {'inputmethods': ['NoIme'], 'dictionaries': ['en_ZA']},
    'en_ZM': {'inputmethods': ['NoIme'], 'dictionaries': ['en_ZM']},
    'en_ZW': {'inputmethods': ['NoIme'], 'dictionaries': ['en_ZW']},
    'eo': {'inputmethods': ['NoIme'], 'dictionaries': ['eo']},
    'es_AR': {'inputmethods': ['NoIme'], 'dictionaries': ['es_AR']},
    'es_BO': {'inputmethods': ['NoIme'], 'dictionaries': ['es_BO']},
    'es_CL': {'inputmethods': ['NoIme'], 'dictionaries': ['es_CL']},
    'es_CO': {'inputmethods': ['NoIme'], 'dictionaries': ['es_CO']},
    'es_CR': {'inputmethods': ['NoIme'], 'dictionaries': ['es_CR']},
    'es_CU': {'inputmethods': ['NoIme'], 'dictionaries': ['es_CU']},
    'es_DO': {'inputmethods': ['NoIme'], 'dictionaries': ['es_DO']},
    'es_EC': {'inputmethods': ['NoIme'], 'dictionaries': ['es_EC']},
    'es_ES': {'inputmethods': ['NoIme'], 'dictionaries': ['es_ES']},
    'es_GT': {'inputmethods': ['NoIme'], 'dictionaries': ['es_GT']},
    'es_HN': {'inputmethods': ['NoIme'], 'dictionaries': ['es_HN']},
    'es_MX': {'inputmethods': ['NoIme'], 'dictionaries': ['es_MX']},
    'es_NI': {'inputmethods': ['NoIme'], 'dictionaries': ['es_NI']},
    'es_PA': {'inputmethods': ['NoIme'], 'dictionaries': ['es_PA']},
    'es_PE': {'inputmethods': ['NoIme'], 'dictionaries': ['es_PE']},
    'es_PR': {'inputmethods': ['NoIme'], 'dictionaries': ['es_PR']},
    'es_PY': {'inputmethods': ['NoIme'], 'dictionaries': ['es_PY']},
    'es_SV': {'inputmethods': ['NoIme'], 'dictionaries': ['es_SV']},
    'es_US': {'inputmethods': ['NoIme'], 'dictionaries': ['es_US']},
    'es_UY': {'inputmethods': ['NoIme'], 'dictionaries': ['es_UY']},
    'es_VE': {'inputmethods': ['NoIme'], 'dictionaries': ['es_VE']},
    'et_EE': {'inputmethods': ['NoIme'], 'dictionaries': ['et_EE']},
    'eu_ES': {'inputmethods': ['NoIme'], 'dictionaries': ['eu_ES']},
    'fa_IR': {'inputmethods': ['NoIme'], 'dictionaries': ['fa_IR']},
    'fil_PH': {'inputmethods': ['NoIme'], 'dictionaries': ['fil_PH']},
    'fj': {'inputmethods': ['NoIme'], 'dictionaries': ['fj']},
    'fo_FO': {'inputmethods': ['NoIme'], 'dictionaries': ['fo_FO']},
    'fr_BE': {'inputmethods': ['NoIme'], 'dictionaries': ['fr_BE']},
    'fr_CA': {'inputmethods': ['NoIme'], 'dictionaries': ['fr_CA']},
    'fr_CH': {'inputmethods': ['NoIme'], 'dictionaries': ['fr_CH']},
    'fr_FR': {'inputmethods': ['NoIme'], 'dictionaries': ['fr_FR']},
    'fr_LU': {'inputmethods': ['NoIme'], 'dictionaries': ['fr_LU']},
    'fr_MC': {'inputmethods': ['NoIme'], 'dictionaries': ['fr_MC']},
    'fur_IT': {'inputmethods': ['NoIme'], 'dictionaries': ['fur_IT']},
    'fy_DE': {'inputmethods': ['NoIme'], 'dictionaries': ['fy_DE']},
    'fy_NL': {'inputmethods': ['NoIme'], 'dictionaries': ['fy_NL']},
    'ga_IE': {'inputmethods': ['NoIme'], 'dictionaries': ['ga_IE']},
    'gd_GB': {'inputmethods': ['NoIme'], 'dictionaries': ['gd_GB']},
    'gl_ES': {'inputmethods': ['NoIme'], 'dictionaries': ['gl_ES']},
    'grc': {'inputmethods': ['NoIme'], 'dictionaries': ['grc']},
    'gu_IN': {'inputmethods': ['gu-inscript2', 'NoIme'], 'dictionaries': ['gu_IN', 'en_GB']},
    'gv_GB': {'inputmethods': ['NoIme'], 'dictionaries': ['gv_GB']},
    'haw': {'inputmethods': ['NoIme'], 'dictionaries': ['haw']},
    'he_IL': {'inputmethods': ['NoIme'], 'dictionaries': ['he_IL']},
    'hi_IN': {'inputmethods': ['hi-inscript2', 'NoIme'], 'dictionaries': ['hi_IN', 'en_GB']},
    'hil_PH': {'inputmethods': ['NoIme'], 'dictionaries': ['hil_PH']},
    'hr_HR': {'inputmethods': ['NoIme'], 'dictionaries': ['hr_HR']},
    'hsb_DE': {'inputmethods': ['NoIme'], 'dictionaries': ['hsb_DE']},
    'ht_HT': {'inputmethods': ['NoIme'], 'dictionaries': ['ht_HT']},
    'hu_HU': {'inputmethods': ['NoIme'], 'dictionaries': ['hu_HU']},
    'hy_AM': {'inputmethods': ['NoIme'], 'dictionaries': ['hy_AM']},
    'ia': {'inputmethods': ['NoIme'], 'dictionaries': ['ia']},
    'id_ID': {'inputmethods': ['NoIme'], 'dictionaries': ['id_ID']},
    'is_IS': {'inputmethods': ['NoIme'], 'dictionaries': ['is_IS']},
    'it_CH': {'inputmethods': ['NoIme'], 'dictionaries': ['it_CH']},
    'it_IT': {'inputmethods': ['NoIme'], 'dictionaries': ['it_IT']},
    'kk_KZ': {'inputmethods': ['NoIme'], 'dictionaries': ['kk_KZ']},
    'km_KH': {'inputmethods': ['NoIme'], 'dictionaries': ['km_KH']},
    'kn_IN': {'inputmethods': ['kn-inscript2', 'NoIme'], 'dictionaries': ['kn_IN', 'en_GB']},
    'ko_KR': {'inputmethods': ['ko-han2', 'NoIme'], 'dictionaries': ['ko_KR', 'en_GB']},
    'ku_SY': {'inputmethods': ['NoIme'], 'dictionaries': ['ku_SY']},
    'ku_TR': {'inputmethods': ['NoIme'], 'dictionaries': ['ku_TR']},
    'ky_KG': {'inputmethods': ['NoIme'], 'dictionaries': ['ky_KG']},
    'la': {'inputmethods': ['NoIme'], 'dictionaries': ['la']},
    'lb_LU': {'inputmethods': ['NoIme'], 'dictionaries': ['lb_LU']},
    'ln_CD': {'inputmethods': ['NoIme'], 'dictionaries': ['ln_CD']},
    'lt_LT': {'inputmethods': ['NoIme'], 'dictionaries': ['lt_LT']},
    'lv_LV': {'inputmethods': ['NoIme'], 'dictionaries': ['lv_LV']},
    'mai_IN': {'inputmethods': ['mai-inscript2', 'NoIme'], 'dictionaries': ['mai_IN', 'en_GB']},
    'mg': {'inputmethods': ['NoIme'], 'dictionaries': ['mg']},
    'mi_NZ': {'inputmethods': ['NoIme'], 'dictionaries': ['mi_NZ']},
    'mk_MK': {'inputmethods': ['NoIme'], 'dictionaries': ['mk_MK']},
    'ml_IN': {'inputmethods': ['ml-inscript2', 'NoIme'], 'dictionaries': ['ml_IN', 'en_GB']},
    'mn_MN': {'inputmethods': ['NoIme'], 'dictionaries': ['mn_MN']},
    'mos_BF': {'inputmethods': ['NoIme'], 'dictionaries': ['mos_BF']},
    'mr_IN': {'inputmethods': ['mr-inscript2', 'NoIme'], 'dictionaries': ['mr_IN', 'en_GB']},
    'ms_BN': {'inputmethods': ['NoIme'], 'dictionaries': ['ms_BN']},
    'ms_MY': {'inputmethods': ['NoIme'], 'dictionaries': ['ms_MY']},
    'mt_MT': {'inputmethods': ['NoIme'], 'dictionaries': ['mt_MT']},
    'nb_NO': {'inputmethods': ['NoIme'], 'dictionaries': ['nb_NO']},
    'nds_DE': {'inputmethods': ['NoIme'], 'dictionaries': ['nds_DE']},
    'nds_NL': {'inputmethods': ['NoIme'], 'dictionaries': ['nds_NL']},
    'ne_IN': {'inputmethods': ['ne-rom', 'NoIme'], 'dictionaries': ['ne_IN', 'en_GB']},
    'ne_NP': {'inputmethods': ['ne-rom', 'NoIme'], 'dictionaries': ['ne_NP', 'en_GB']},
    'nl_AW': {'inputmethods': ['NoIme'], 'dictionaries': ['nl_AW']},
    'nl_BE': {'inputmethods': ['NoIme'], 'dictionaries': ['nl_BE']},
    'nl_NL': {'inputmethods': ['NoIme'], 'dictionaries': ['nl_NL']},
    'nn_NO': {'inputmethods': ['NoIme'], 'dictionaries': ['nn_NO']},
    'nr_ZA': {'inputmethods': ['NoIme'], 'dictionaries': ['nr_ZA']},
    'nso_ZA': {'inputmethods': ['NoIme'], 'dictionaries': ['nso_ZA']},
    'ny_MW': {'inputmethods': ['NoIme'], 'dictionaries': ['ny_MW']},
    'oc_FR': {'inputmethods': ['NoIme'], 'dictionaries': ['oc_FR']},
    'om_ET': {'inputmethods': ['NoIme'], 'dictionaries': ['om_ET']},
    'om_KE': {'inputmethods': ['NoIme'], 'dictionaries': ['om_KE']},
    'or_IN': {'inputmethods': ['or-inscript2', 'NoIme'], 'dictionaries': ['or_IN', 'en_GB']},
    'pa_IN': {'inputmethods': ['pa-inscript2', 'NoIme'], 'dictionaries': ['pa_IN', 'en_GB']},
    'pl_PL': {'inputmethods': ['NoIme'], 'dictionaries': ['pl_PL']},
    'plt': {'inputmethods': ['NoIme'], 'dictionaries': ['plt']},
    'pt_AO': {'inputmethods': ['NoIme'], 'dictionaries': ['pt_AO']},
    'pt_BR': {'inputmethods': ['NoIme'], 'dictionaries': ['pt_BR']},
    'pt_PT': {'inputmethods': ['NoIme'], 'dictionaries': ['pt_PT']},
    'qu_EC': {'inputmethods': ['NoIme'], 'dictionaries': ['qu_EC']},
    'quh_BO': {'inputmethods': ['NoIme'], 'dictionaries': ['quh_BO']},
    'ro_RO': {'inputmethods': ['NoIme'], 'dictionaries': ['ro_RO']},
    'ru_RU': {'inputmethods': ['NoIme'], 'dictionaries': ['ru_RU']},
    'ru_UA': {'inputmethods': ['NoIme'], 'dictionaries': ['ru_UA']},
    'rw_RW': {'inputmethods': ['NoIme'], 'dictionaries': ['rw_RW']},
    'sc_IT': {'inputmethods': ['NoIme'], 'dictionaries': ['sc_IT']},
    'se_FI': {'inputmethods': ['NoIme'], 'dictionaries': ['se_FI']},
    'se_NO': {'inputmethods': ['NoIme'], 'dictionaries': ['se_NO']},
    'se_SE': {'inputmethods': ['NoIme'], 'dictionaries': ['se_SE']},
    'sh_ME': {'inputmethods': ['NoIme'], 'dictionaries': ['sh_ME']},
    'sh_RS': {'inputmethods': ['NoIme'], 'dictionaries': ['sh_RS']},
    'sh_YU': {'inputmethods': ['NoIme'], 'dictionaries': ['sh_YU']},
    'shs_CA': {'inputmethods': ['NoIme'], 'dictionaries': ['shs_CA']},
    'si_LK': {'inputmethods': ['NoIme'], 'dictionaries': ['si_LK', 'en_GB']},
    'sk_SK': {'inputmethods': ['NoIme'], 'dictionaries': ['sk_SK']},
    'sl_SI': {'inputmethods': ['NoIme'], 'dictionaries': ['sl_SI']},
    'smj_NO': {'inputmethods': ['NoIme'], 'dictionaries': ['smj_NO']},
    'smj_SE': {'inputmethods': ['NoIme'], 'dictionaries': ['smj_SE']},
    'so_DJ': {'inputmethods': ['NoIme'], 'dictionaries': ['so_DJ']},
    'so_ET': {'inputmethods': ['NoIme'], 'dictionaries': ['so_ET']},
    'so_KE': {'inputmethods': ['NoIme'], 'dictionaries': ['so_KE']},
    'so_SO': {'inputmethods': ['NoIme'], 'dictionaries': ['so_SO']},
    'sq_AL': {'inputmethods': ['NoIme'], 'dictionaries': ['sq_AL']},
    'sr_ME': {'inputmethods': ['NoIme'], 'dictionaries': ['sr_ME']},
    'sr_RS': {'inputmethods': ['NoIme'], 'dictionaries': ['sr_RS']},
    'sr_YU': {'inputmethods': ['NoIme'], 'dictionaries': ['sr_YU']},
    'ss_ZA': {'inputmethods': ['NoIme'], 'dictionaries': ['ss_ZA']},
    'st_ZA': {'inputmethods': ['NoIme'], 'dictionaries': ['st_ZA']},
    'sv_FI': {'inputmethods': ['NoIme'], 'dictionaries': ['sv_FI']},
    'sv_SE': {'inputmethods': ['NoIme'], 'dictionaries': ['sv_SE']},
    'sw_KE': {'inputmethods': ['NoIme'], 'dictionaries': ['sw_KE']},
    'sw_TZ': {'inputmethods': ['NoIme'], 'dictionaries': ['sw_TZ']},
    'ta_IN': {'inputmethods': ['ta-inscript2', 'NoIme'], 'dictionaries': ['ta_IN', 'en_GB']},
    'te_IN': {'inputmethods': ['te-inscript2', 'NoIme'], 'dictionaries': ['te_IN', 'en_GB']},
    'tet_ID': {'inputmethods': ['NoIme'], 'dictionaries': ['tet_ID']},
    'tet_TL': {'inputmethods': ['NoIme'], 'dictionaries': ['tet_TL']},
    'th_TH': {'inputmethods': ['NoIme'], 'dictionaries': ['th_TH']},
    'ti_ER': {'inputmethods': ['NoIme'], 'dictionaries': ['ti_ER']},
    'ti_ET': {'inputmethods': ['NoIme'], 'dictionaries': ['ti_ET']},
    'tk_TM': {'inputmethods': ['NoIme'], 'dictionaries': ['tk_TM']},
    'tl_PH': {'inputmethods': ['NoIme'], 'dictionaries': ['tl_PH']},
    'tn_BW': {'inputmethods': ['NoIme'], 'dictionaries': ['tn_BW']},
    'tn_ZA': {'inputmethods': ['NoIme'], 'dictionaries': ['tn_ZA']},
    'tpi_PG': {'inputmethods': ['NoIme'], 'dictionaries': ['tpi_PG']},
    'ts_ZA': {'inputmethods': ['NoIme'], 'dictionaries': ['ts_ZA']},
    'uk_UA': {'inputmethods': ['NoIme'], 'dictionaries': ['uk_UA']},
    'ur_IN': {'inputmethods': ['NoIme'], 'dictionaries': ['ur_IN']},
    'ur_PK': {'inputmethods': ['NoIme'], 'dictionaries': ['ur_PK']},
    'uz_UZ': {'inputmethods': ['NoIme'], 'dictionaries': ['uz_UZ']},
    've_ZA': {'inputmethods': ['NoIme'], 'dictionaries': ['ve_ZA']},
    'vi_VN': {'inputmethods': ['NoIme'], 'dictionaries': ['vi_VN']},
    'wa_BE': {'inputmethods': ['NoIme'], 'dictionaries': ['wa_BE']},
    'xh_ZA': {'inputmethods': ['NoIme'], 'dictionaries': ['xh_ZA']},
    'yi_US': {'inputmethods': ['NoIme', 'yi-yivo'], 'dictionaries': ['yi_US', 'en_US']},
    'zu_ZA': {'inputmethods': ['NoIme'], 'dictionaries': ['zu_ZA', 'en_GB']},
}

def get_default_input_methods(locale):
    '''
    Gets the default input methods for a locale

    :param locale:
    :type locale: String
    :rtype: List of  Strings

    Examples:

    >>> get_default_input_methods('te_IN')
    ['te-inscript2', 'NoIme']

    >>> get_default_input_methods('xx_YY')
    ['NoIme']
    '''
    if locale in LOCALE_DEFAULTS:
        default_input_methods = LOCALE_DEFAULTS[locale]['inputmethods']
    else:
        default_input_methods = ['NoIme']
    return default_input_methods

def get_default_dictionaries(locale):
    '''
    Gets the default dictionaries for a locale

    :param locale:
    :type locale: String
    :rtype: List of  Strings

    Examples:

    >>> get_default_dictionaries('te_IN')
    ['te_IN', 'en_GB']

    >>> get_default_dictionaries('xx_YY')
    ['en_US']
    '''
    if locale in LOCALE_DEFAULTS:
        default_dictionaries = LOCALE_DEFAULTS[locale]['dictionaries']
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
    # List of all locales/languages where CLDR annotation files currently exist.
    # Not all of these are necessarily available at the moment.
    # That depends what is currently installed on the system.
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

SUPPORTED_DICTIONARIES = set()
SUPPORTED_DICTIONARIES.update(HUNSPELL_DICTIONARIES)
SUPPORTED_DICTIONARIES.update(CLDR_ANNOTATION_FILES)

M17N_INPUT_METHODS = {
    # Dictionary of all the m17n input methods which are
    # useful with ibus-typing-booster.
    #
    # Key: name of input method.
    # Value: file name where the input method is implemented.
    'am-sera': 'am-sera.mim',
    'ar-kbd': 'ar-kbd.mim',
    'ar-translit': 'ar-translit.mim',
    'as-inscript': 'as-inscript.mim',
    'as-inscript2': 'as-inscript2.mim',
    'as-itrans': 'as-itrans.mim',
    'as-phonetic': 'as-phonetic.mim',
    'ath-phonetic': 'ath-phonetic.mim',
    'be-kbd': 'be-kbd.mim',
    'bla-phonetic': 'bla-phonetic.mim',
    'bn-disha': 'bn-disha.mim',
    'bn-inscript': 'bn-inscript.mim',
    'bn-inscript2': 'bn-inscript2.mim',
    'bn-itrans': 'bn-itrans.mim',
    'bn-probhat': 'bn-probhat.mim',
    'bo-ewts': 'bo-ewts.mim',
    'bo-tcrc': 'bo-tcrc.mim',
    'bo-wylie': 'bo-wylie.mim',
    'brx-inscript2': 'brx-inscript2-deva.mim',
    # 't-nil-cjk-util': 'cjk-util.mim', # not useful
    'cmc-kbd': 'cmc-kbd.mim',
    'cr-western': 'cr-western.mim',
    'cs-kbd': 'cs-kbd.mim',
    'da-post': 'da-post.mim',
    'doi-inscript2': 'doi-inscript2-deva.mim',
    'dv-phonetic': 'dv-phonetic.mim',
    'el-kbd': 'el-kbd.mim',
    'eo-h-fundamente': 'eo-h-f.mim',
    'eo-h-sistemo': 'eo-h.mim',
    'eo-plena': 'eo-plena.mim',
    'eo-q-sistemo': 'eo-q.mim',
    'eo-vi-sistemo': 'eo-vi.mim',
    'eo-x-sistemo': 'eo-x.mim',
    'fa-isiri': 'fa-isiri.mim',
    'fr-azerty': 'fr-azerty.mim',
    # 't-nil-global': 'global.mim', # not useful
    'grc-mizuochi': 'grc-mizuochi.mim',
    'gu-inscript': 'gu-inscript.mim',
    'gu-inscript2': 'gu-inscript2.mim',
    'gu-itrans': 'gu-itrans.mim',
    'gu-phonetic': 'gu-phonetic.mim',
    'he-kbd': 'he-kbd.mim',
    'hi-inscript': 'hi-inscript.mim',
    'hi-inscript2': 'hi-inscript2.mim',
    'hi-itrans': 'hi-itrans.mim',
    'hi-optitransv2': 'hi-optitransv2.mim',
    'hi-phonetic': 'hi-phonetic.mim',
    'hi-remington': 'hi-remington.mim',
    'hi-typewriter': 'hi-typewriter.mim',
    'hi-vedmata': 'hi-vedmata.mim',
    'hr-kbd': 'hr-kbd.mim',
    'hu-rovas-post': 'hu-rovas-post.mim',
    'hy-kbd': 'hy-kbd.mim',
    'ii-phonetic': 'ii-phonetic.mim',
    'iu-phonetic': 'iu-phonetic.mim',
    'ja-anthy': 'ja-anthy.mim',
    'ja-tcode': 'ja-tcode.mim',
    'ja-trycode': 'ja-trycode.mim',
    'ka-kbd': 'ka-kbd.mim',
    'kk-arabic': 'kk-arabic.mim',
    'kk-kbd': 'kk-kbd.mim',
    'km-yannis': 'km-yannis.mim',
    'kn-inscript': 'kn-inscript.mim',
    'kn-inscript2': 'kn-inscript2.mim',
    'kn-itrans': 'kn-itrans.mim',
    'kn-kgp': 'kn-kgp.mim',
    'kn-optitransv2': 'kn-optitransv2.mim',
    'kn-typewriter': 'kn-typewriter.mim',
    'ko-han2': 'ko-han2.mim',
    'ko-romaja': 'ko-romaja.mim',
    'kok-inscript2': 'kok-inscript2-deva.mim',
    'ks-inscript': 'ks-inscript.mim',
    'ks-kbd': 'ks-kbd.mim',
    't-latn-post': 'latn-post.mim',
    't-latn-pre': 'latn-pre.mim',
    't-latn1-pre': 'latn1-pre.mim',
    'lo-kbd': 'lo-kbd.mim',
    'lo-lrt': 'lo-lrt.mim',
    't-lsymbol': 'lsymbol.mim',
    'mai-inscript': 'mai-inscript.mim',
    'mai-inscript2': 'mai-inscript2.mim',
    't-math-latex': 'math-latex.mim',
    'mr-minglish': 'minglish.mim',
    'ml-enhanced-inscript': 'ml-enhanced-inscript.mim',
    'ml-inscript': 'ml-inscript.mim',
    'ml-inscript2': 'ml-inscript2.mim',
    'ml-itrans': 'ml-itrans.mim',
    'ml-mozhi': 'ml-mozhi.mim',
    'ml-remington': 'ml-remington.mim',
    'ml-swanalekha': 'ml-swanalekha.mim',
    'mni-inscript2': 'mni-inscript2-beng.mim',
    'mni-inscript2': 'mni-inscript2-mtei.mim',
    'mr-inscript': 'mr-inscript.mim',
    'mr-inscript2': 'mr-inscript2.mim',
    'mr-itrans': 'mr-itrans.mim',
    'mr-phonetic': 'mr-phonetic.mim',
    'mr-remington': 'mr-remington.mim',
    'mr-typewriter': 'mr-typewriter.mim',
    'my-kbd': 'my-kbd.mim',
    'ne-inscript2': 'ne-inscript2-deva.mim',
    'ne-rom-translit': 'ne-rom-translit.mim',
    'ne-rom': 'ne-rom.mim',
    'ne-trad-ttf': 'ne-trad-ttf.mim',
    'ne-trad': 'ne-trad.mim',
    'nsk-phonetic': 'nsk-phonetic.mim',
    'oj-phonetic': 'oj-phonetic.mim',
    'or-inscript': 'or-inscript.mim',
    'or-inscript2': 'or-inscript2.mim',
    'or-itrans': 'or-itrans.mim',
    'or-phonetic': 'or-phonetic.mim',
    'pa-anmollipi': 'pa-anmollipi.mim',
    'pa-inscript': 'pa-inscript.mim',
    'pa-inscript2': 'pa-inscript2-guru.mim',
    'pa-itrans': 'pa-itrans.mim',
    'pa-jhelum': 'pa-jhelum.mim',
    'pa-phonetic': 'pa-phonetic.mim',
    'ps-phonetic': 'ps-phonetic.mim',
    't-rfc1345': 'rfc1345.mim',
    'ru-kbd': 'ru-kbd.mim',
    'ru-phonetic': 'ru-phonetic.mim',
    'ru-translit': 'ru-translit.mim',
    'ru-yawerty': 'ru-yawerty.mim',
    'sa-harvard-kyoto': 'sa-harvard-kyoto.mim',
    'sa-IAST': 'sa-iast.mim',
    'sa-inscript2': 'sa-inscript2.mim',
    'sa-itrans': 'sa-itrans.mim',
    'sat-inscript2': 'sat-inscript2-deva.mim',
    'sat-inscript2': 'sat-inscript2-olck.mim',
    'sd-inscript': 'sd-inscript.mim',
    'sd-inscript2': 'sd-inscript2-deva.mim',
    'si-phonetic-dynamic': 'si-phonetic-dynamic.mim',
    'si-samanala': 'si-samanala.mim',
    'si-singlish': 'si-singlish.mim',
    'si-sumihiri': 'si-sumihiri.mim',
    'si-transliteration': 'si-trans.mim',
    'si-wijesekera': 'si-wijesekera.mim',
    'sk-kbd': 'sk-kbd.mim',
    'sr-kbd': 'sr-kbd.mim',
    't-ssymbol': 'ssymbol.mim',
    'sv-post': 'sv-post.mim',
    't-syrc-phonetic': 'syrc-phonetic.mim',
    'ta-inscript': 'ta-inscript.mim',
    'ta-inscript2': 'ta-inscript2.mim',
    'ta-itrans': 'ta-itrans.mim',
    'ta-lk-renganathan': 'ta-lk-renganathan.mim',
    'ta-phonetic': 'ta-phonetic.mim',
    'ta-tamil99': 'ta-tamil99.mim',
    'ta-typewriter': 'ta-typewriter.mim',
    'ta-vutam': 'ta-vutam.mim',
    'tai-sonla-kbd': 'tai-sonla.mim',
    'te-apple': 'te-apple.mim',
    'te-inscript': 'te-inscript.mim',
    'te-inscript2': 'te-inscript2.mim',
    'te-itrans': 'te-itrans.mim',
    'te-pothana': 'te-pothana.mim',
    'te-rts': 'te-rts.mim',
    'te-sarala': 'te-sarala.mim',
    'th-kesmanee': 'th-kesmanee.mim',
    'th-pattachote': 'th-pattachote.mim',
    'th-tis820': 'th-tis820.mim',
    'ug-kbd': 'ug-kbd.mim',
    'uk-kbd': 'uk-kbd.mim',
    't-unicode': 'unicode.mim',
    'ur-phonetic': 'ur-phonetic.mim',
    'uz-kbd': 'uz-kbd.mim',
    # 't-nil vi-base': 'vi-base.mim', # not useful
    'vi-han': 'vi-han.mim',
    'vi-nomvni': 'vi-nom-vni.mim',
    'vi-nomtelex': 'vi-nom.mim',
    'vi-tcvn': 'vi-tcvn.mim',
    'vi-telex': 'vi-telex.mim',
    'vi-viqr': 'vi-viqr.mim',
    'vi-vni': 'vi-vni.mim',
    'yi-yivo': 'yi-yivo.mim',
    'zh-bopomofo': 'zh-bopomofo.mim',
    'zh-cangjie': 'zh-cangjie.mim',
    'zh-pinyin-vi': 'zh-pinyin-vi.mim',
    'zh-pinyin': 'zh-pinyin.mim',
    'zh-py-b5': 'zh-py-b5.mim',
    'zh-py-gb': 'zh-py-gb.mim',
    'zh-py': 'zh-py.mim',
    'zh-quick': 'zh-quick.mim',
    'zh-tonepy-b5': 'zh-tonepy-b5.mim',
    'zh-tonepy-gb': 'zh-tonepy-gb.mim',
    'zh-tonepy': 'zh-tonepy.mim',
    # 't-nil-zh-util': 'zh-util.mim', # not useful
    'zh-zhuyin': 'zh-zhuyin.mim',
}

SPANISH_419_LOCALES = (
    'es_AR', 'es_MX', 'es_BO', 'es_CL', 'es_CO', 'es_CR',
    'es_CU', 'es_DO', 'es_EC', 'es_GT', 'es_HN', 'es_NI',
    'es_PA', 'es_PE', 'es_PR', 'es_PY', 'es_SV', 'es_US',
    'es_UY', 'es_VE',)

def expand_languages(languages):
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
    '''
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
    for language in expand_languages([language]):
        for dirname in dirnames:
            if os.path.isfile(os.path.join(dirname, language + '.dic')):
                dic_path = os.path.join(dirname, language + '.dic')
                aff_path = os.path.join(dirname, language + '.aff')
                return (dic_path, aff_path)
    sys.stderr.write(
        'find_hunspell_dictionary(): '
        + 'No file %s.dic found in %s\n'
        %(language, dirnames))
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

def get_ime_help(ime_name):
    '''
    Get help for an input method.

    :param ime_name: Name of the input method
    :type ime_name: String
    :rtype: tuple of the form (path, title, description, full_contents, error)
            where “path” is the full path of the file implementing the input method,
            “title” is title of the input method,
            “description” is the description of the input method,
            and full_contents is the full content of the file implementing
            the input method.
            “error” is empty if getting help for the input method was successfull,
            otherwise it might contain an error message.

    “NoIme” is handled as a special case.

    Examples:

    >>> get_ime_help('latn-post')[1]
    'Latin-post'

    >>> get_ime_help('latn-post')[4]
    ''

    >>> get_ime_help('mr-itrans')[1]
    'क'

    >>> get_ime_help('ko-romaja')[1]
    '로마자'
    '''
    path = ''
    title = ''
    description = ''
    full_contents = ''
    error = ''
    if not ime_name:
        return ('', '', '', '', '')
    if ime_name == 'NoIme':
        title = _('Native Keyboard')
        description = _(
            'Direct keyboard input. This is not really an input method, '
            + 'it uses directly whatever comes from the current keyboard layout '
            + 'without any further changes. So no transliteration or composing '
            + 'is done here.')
        return (path, title, description, full_contents, error)
    if ime_name in M17N_INPUT_METHODS:
        mim_file = M17N_INPUT_METHODS[ime_name]
    else:
        mim_file = ime_name+'.mim'
    dirnames = [
        '/usr/share/m17n',
        '/usr/local/share/m17n', # On FreeBSD, the .mim files are here
    ]
    m17n_dir = ''
    for dirname in dirnames:
        if os.path.isdir(dirname):
            m17n_dir = dirname
    if not m17n_dir:
        # Maybe don’t mark this error message as translatable, it should
        # never happen in practice:
        return ('', '', '', '', ('m17n dir not found, tried: %s' %dirnames))
    path = os.path.join(m17n_dir, mim_file)
    try:
        with open(path, mode='r', encoding='UTF-8', errors='ignore') as ime_file:
            full_contents = ime_file.read()
    except FileNotFoundError:
        return ('', '', '', '', _('File not found'))
    except PermissionError:
        return ('', '', '', '', _('Permission error'))
    except UnicodeDecodeError:
        return ('', '', '', '', _('Unicode decoding error'))
    except:
        return ('', '', '', '', _('Unknown error'))
    if full_contents:
        title_pattern = re.compile(
            r'\([\s]*title[\s]*"(?P<title>.+?)(?<!\\)"[\s]*\)',
            re.DOTALL|re.MULTILINE|re.UNICODE)
        match = title_pattern.search(full_contents)
        if match:
            title = match.group('title').replace('\\"', '"')
        description_pattern = re.compile(
            r'\([\s]*description[\s]*"(?P<description>.+?)(?<!\\)"[\s]*\)',
            re.DOTALL|re.MULTILINE|re.UNICODE)
        match = description_pattern.search(full_contents)
        if match:
            description = match.group('description').replace('\\"', '"')
    return (path, title, description, full_contents, error)


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
    def __str__(self):
        return (
            "val=%s code=%s state=0x%08x name='%s' unicode='%s' msymbol='%s' "
            % (self.val,
               self.code,
               self.state,
               self.name,
               self.unicode,
               self.msymbol)
            + "shift=%s control=%s mod1=%s mod5=%s release=%s\n"
            % (self.shift,
               self.control,
               self.mod1,
               self.mod5,
               self.release))

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
            'Copyright © 2017 Mike FABIAN')
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
            self, dummy_about_dialog, dummy_response):
        '''
        The “About” dialog has been closed by the user

        :param dummy_about_dialog: The “About” dialog
        :type dummy_about_dialog: GtkDialog object
        :param dummy_response: The response when the “About” dialog was closed
        :type dummy_response: Gtk.ResponseType enum
        '''
        self.destroy()

if __name__ == "__main__":
    import doctest
    (FAILED, ATTEMPTED) = doctest.testmod()
    if FAILED:
        sys.exit(1)
    sys.exit(0)
