# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2025 Mike FABIAN <mfabian@redhat.com>
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
dictionary_download.py

Uses Gio.File to download dictionary files with a Gtk3 progress dialog.
'''
from typing import Dict
from typing import Set
from typing import List
from typing import Optional
from typing import Callable
from typing import TYPE_CHECKING
# pylint: disable=wrong-import-position
import sys
if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal
# pylint: enable=wrong-import-position
InstallStatus = Literal['success', 'cancelled', 'failure']
OutputCallback = Callable[[str], None]
CompleteCallback = Callable[[InstallStatus], None]
import pathlib
import os
import locale
import subprocess
import time
import logging
from gi import require_version
# pylint: disable=wrong-import-position
require_version('GLib', '2.0')
require_version('Gio', '2.0')
from gi.repository import GLib # type: ignore
from gi.repository import Gio # type: ignore
# pylint: enable=wrong-import-position
from i18n import _, init as i18n_init
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
# pylint: disable=import-error, wrong-import-order
import itb_util
from itb_gtk import Gtk # type: ignore
if TYPE_CHECKING:
    # These imports are only for type checkers (mypy). They must not be
    # executed at runtime because itb_gtk controls the Gtk/Gdk versions.
    # pylint: disable=reimported
    from gi.repository import Gtk # type: ignore
    # pylint: enable=reimported
from g_compat_helpers import (
    add_child,
    show_all,
)
# pylint: enable=import-error, wrong-import-order

LOGGER = logging.getLogger('ibus-typing-booster')

# pylint: disable=line-too-long
# https://github.com/LibreOffice/dictionaries/
DICTIONARY_SOURCES = {
    'af': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/af_ZA/af_ZA',
    'af_ZA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/af_ZA/af_ZA',
    'an': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/an_ES/an_ES',
    'an_ES': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/an_ES/an_ES',
    'ar': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_AE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_BH': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_DJ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_DZ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_EG': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_IL': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_IN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_IQ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_JO': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_KM': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_KW': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_LB': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_LY': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_MA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_MR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_OM': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_PS': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_QA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_SA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_SD': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_SO': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_SY': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_TD': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_TN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'ar_YE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ar/ar',
    'as': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/as_IN/as_IN',
    'as_IN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/as_IN/as_IN',
    # Fedora package: hunspell-ast-2.0-17.fc43.noarch
    # ast: (This is ZIP archive, not sure whether I should support that.
    # https://extensions.libreoffice.org/assets/downloads/340/1717185915/ort-ast-20240531.oxt
    'be': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/be_BY/be-official',
    'be_BY': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/be_BY/be-official',
    'bg': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/bg_BG/bg_BG',
    'bg_BG': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/bg_BG/bg_BG',
    'bn': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/bn_BD/bn_BD',
    'bn_BD': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/bn_BD/bn_BD',
    'bn_IN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/bn_BD/bn_BD',
    'bo': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/bo/bo',
    'bo_CN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/bo/bo',
    'bo_IN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/bo/bo',
    'br': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/br_FR/br_FR',
    'br_FR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/br_FR/br_FR',
    'bs': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/bs_BA/bs_BA',
    'bs_BA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/bs_BA/bs_BA',
    'ca': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ca/dictionaries/ca',
    'ca_AD': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ca/dictionaries/ca',
    'ca_ES': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ca/dictionaries/ca',
    'ca_ES_VALENCIA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ca/dictionaries/ca-valencia',
    'ca_FR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ca/dictionaries/ca',
    'ca_IT': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ca/dictionaries/ca',
    'ckb': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ckb/dictionaries/ckb',
    'ckb_IQ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ckb/dictionaries/ckb',
    'cs': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/cs_CZ/cs_CZ',
    'cs_CZ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/cs_CZ/cs_CZ',
    'da': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/da_DK/da_DK',
    'da_DK': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/da_DK/da_DK',
    'de': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/de/de_DE_frami',
    'de_AT': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/de/de_AT_frami',
    'de_BE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/de/de_DE_frami',
    'de_CH': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/de/de_CH_frami',
    'de_DE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/de/de_DE_frami',
    'de_IT': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/de/de_AT_frami',
    'de_LI': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/de/de_CH_frami',
    'de_LU': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/de/de_DE_frami',
    'el': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/el_GR/el_GR',
    'el_CY': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/el_GR/el_GR',
    'el_GR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/el_GR/el_GR',
    'en': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_US',
    'en_001': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_US',
    'en_150': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_AG': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_AI': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_AS': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_AT': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_AU': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_AU',
    'en_BB': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_BE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_BI': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_BM': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_BS': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_BW': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_BZ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_CA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_CA',
    'en_CC': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_CH': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_CK': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_CM': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_CX': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_CY': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_DE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_DG': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_DK': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_DM': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_GB': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_ER': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_FI': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_FJ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_FK': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_FM': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_GD': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_GG': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_GH': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_GI': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_GM': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_GU': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_GY': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_HK': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_IE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_IL': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_IM': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_IN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_IO': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_JE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_JM': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_KE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_KI': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_KN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_KY': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_LC': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_LR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_LS': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_MG': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_MH': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_MO': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_MP': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_MS': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_MT': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_MU': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_MW': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_MY': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_NA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_NF': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_NG': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_NL': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_NR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_NU': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_NZ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_PG': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_PH': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_PK': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_PN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_PR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_PW': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_RW': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_SB': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_SC': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_SD': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_SE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_SG': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_SH': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_SI': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_SL': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_SS': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_SX': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_SZ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_TC': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_TK': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_TO': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_TT': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_TV': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_TZ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_UG': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_UM': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_US',
    'en_US': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_US',
    'en_US_POSIX': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_US',
    'en_VC': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_VG': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_VI': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_US',
    'en_VU': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_WS': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_ZA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_ZA',
    'en_ZM': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'en_ZW': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/en_GB',
    'eo': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/eo/eo',
    'es': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_ES',
    'es_419': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_MX',
    'es_AR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_AR',
    'es_BO': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_BO',
    'es_BR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_UY',
    'es_BZ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_MX',
    'es_CL': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_CL',
    'es_CO': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_CO',
    'es_CR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_CR',
    'es_CU': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_CU',
    'es_DO': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_DO',
    'es_EA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_ES',
    'es_EC': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_EC',
    'es_ES': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_ES',
    'es_GQ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_GQ',
    'es_GT': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_GT',
    'es_HN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_HN',
    'es_MX': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_MX',
    'es_NI': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_NI',
    'es_PA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_PA',
    'es_PE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_PE',
    'es_PH': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_PH',
    'es_PR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_PR',
    'es_PY': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_PY',
    'es_SV': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_SV',
    'es_US': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_US',
    'es_UY': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_UY',
    'es_VE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/es_VE',
    'et': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/et_EE/et_EE',
    'et_EE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/et_EE/et_EE',
    'fa': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fa_IR/fa-IR',
    'fa_IR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fa_IR/fa-IR',
    'fr': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_BE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_BF': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_BI': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_BJ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_BL': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_CA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_CD': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_CF': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_CG': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_CH': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_CI': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_CM': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_DJ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_DZ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_FR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_GA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_GF': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_GN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_GP': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_GQ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_HT': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_KM': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_LU': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_MA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_MC': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_MF': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_MG': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_ML': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_MQ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_MR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_MU': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_NC': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_NE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_PF': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_PM': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_RE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_RW': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_SC': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_SN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_SY': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_TD': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_TG': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_TN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_VU': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_WF': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'fr_YT': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/fr',
    'gd': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/gd_GB/gd_GB',
    'gd_GB': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/gd_GB/gd_GB',
    'gl': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/gl/gl_ES',
    'gl_ES': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/gl/gl_ES',
    'gu': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/gu_IN/gu_IN',
    'gu_IN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/gu_IN/gu_IN',
    'gug': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/gug/gug',
    'he': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/he_IL/he_IL',
    'he_IL': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/he_IL/he_IL',
    'hi': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/hi_IN/hi_IN',
    'hi_IN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/hi_IN/hi_IN',
    'hr': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/hr_HR/hr_HR',
    'hr_HR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/hr_HR/hr_HR',
    'hu': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/hu_HU/hu_HU',
    'hu_HU': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/hu_HU/hu_HU',
    'id': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/id/id_ID',
    'id_ID': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/id/id_ID',
    'is': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/is/is',
    'is_IS': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/is/is',
    'it': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/it_IT/it_IT',
    'it_CH': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/it_IT/it_IT',
    'it_IT': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/it_IT/it_IT',
    'ku_SY': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/kmr_Latn/kmr_Latn',
    'ku_TR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/kmr_Latn/kmr_Latn',
    'kmr': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/kmr_Latn/kmr_Latn',
    'kmr_SY': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/kmr_Latn/kmr_Latn',
    'kmr_TR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/kmr_Latn/kmr_Latn',
    'kmr_Latn': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/kmr_Latn/kmr_Latn',
    'kmr_Latn_TR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/kmr_Latn/kmr_Latn',
    'kmr_Latn_SY': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/kmr_Latn/kmr_Latn',
    'kn': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/kn_IN/kn_IN',
    'kn_IN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/kn_IN/kn_IN',
    'ko': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ko_KR/ko_KR',
    'ko_KR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ko_KR/ko_KR',
    'lo': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/lo_LA/lo_LA',
    'lo_LA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/lo_LA/lo_LA',
    'lt': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/lt_LT/lt',
    'lt_LT': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/lt_LT/lt',
    'lv': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/lv_LV/lv_LV',
    'lv_LV': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/lv_LV/lv_LV',
    # 'mg_MG' Fedora package: hunspell-mg-0.20050109-36.fc43.noarch
    # http://download.services.openoffice.org/contrib/dictionaries/mg_MG.zip
    'mn': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/mn_MN/mn_MN',
    'mn_MN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/mn_MN/mn_MN',
    'mr': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/mr_IN/mr_IN',
    'mr_IN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/mr_IN/mr_IN',
    'ne': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ne_NP/ne_NP',
    'ne_IN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ne_NP/ne_NP',
    'ne_NP': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ne_NP/ne_NP',
    'nl': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/nl_NL/nl_NL',
    'nl_AW': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/nl_NL/nl_NL',
    'nl_BE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/nl_NL/nl_NL',
    'nl_NL': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/nl_NL/nl_NL',
    'nb': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/no/nb_NO',
    'nb_NO': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/no/nb_NO',
    'nb_SJ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/no/nb_NO',
    'nn': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/no/nn_NO',
    'nn_NO': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/no/nn_NO',
    'oc': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/oc_FR/oc_FR',
    'oc_FR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/oc_FR/oc_FR',
    'or': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/or_IN/or_IN',
    'or_IN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/or_IN/or_IN',
    'pa': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/pa_IN/pa_IN',
    'pa_IN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/pa_IN/pa_IN',
    'pl': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/pl_PL/pl_PL',
    'pl_PL': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/pl_PL/pl_PL',
    'pt': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/pt_BR/pt_BR',
    'pt_BR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/pt_BR/pt_BR',
    'pt_PT': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/pt_PT/pt_PT',
    'ro': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ro/ro_RO',
    'ro_RO': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ro/ro_RO',
    'ru': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ru_RU/ru_RU',
    'ru_RU': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ru_RU/ru_RU',
    'ru_UA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ru_RU/ru_RU',
    'sa': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sa_IN/sa_IN',
    'sa_IN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sa_IN/sa_IN',
    'si': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/si_LK/si_LK',
    'si_LK': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/si_LK/si_LK',
    'sk': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sk_SK/sk_SK',
    'sk_SK': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sk_SK/sk_SK',
    'sl': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sl_SI/sl_SI',
    'sl_SI': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sl_SI/sl_SI',
    'sq': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sq_AL/sq_AL',
    'sq_AL': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sq_AL/sq_AL',
    'sr_Latn': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sr/sr-Latn',
    'sr': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sr/sr',
    'sr_Cyrl': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sr/sr',
    'sr_ME': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sr/sr',
    'sr_RS': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sr/sr',
    'sr_YU': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sr/sr',
    'sv': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sv_SE/sv_SE',
    'sv_FI': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sv_SE/sv_FI',
    'sv_SE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sv_SE/sv_SE',
    'sw': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sw_TZ/sw_TZ',
    'sw_KE': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sw_TZ/sw_TZ',
    'sw_TZ': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/sw_TZ/sw_TZ',
    'ta': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ta_IN/ta_IN',
    'ta_IN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/ta_IN/ta_IN',
    'te': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/te_IN/te_IN',
    'te_IN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/te_IN/te_IN',
    'th': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/th_TH/th_TH',
    'th_TH': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/th_TH/th_TH',
    'tr': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/tr_TR/tr_TR',
    'tr_TR': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/tr_TR/tr_TR',
    'uk': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/uk_UA/uk_UA',
    'uk_UA': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/uk_UA/uk_UA',
    'vi': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/vi/vi_VN',
    'vi_VN': 'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/vi/vi_VN',
}
# pylint: enable=line-too-long

def ensure_gvfs_alive(on_output: Optional[Callable[[str], None]] = None) -> None:
    '''
    Ensure GVfs daemons (gvfsd and gvfsd-http) are running and responsive.
    If they appear hung, restart them safely.
    Logs progress via on_output if provided.
    '''

    def log(msg: str) -> None:
        LOGGER.info(msg)
        if on_output:
            on_output(msg)

    def gio_test() -> bool:
        '''Try a quick non-blocking check for GIO HTTP responsiveness.'''
        try:
            subprocess.run(
                [
                    'gio', 'info', '--attributes=standard::size',
                    'https://raw.githubusercontent.com/LibreOffice/dictionaries/master/README.md'
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False,
            )
            return True
        except subprocess.TimeoutExpired:
            return False
        except FileNotFoundError:
            # GIO CLI missing – nothing to test.
            return True

    if not gio_test():
        log('⚠️ GVfs HTTP backend appears hung — restarting gvfsd...')
        subprocess.run(['pkill', '-f', 'gvfsd-http'], check=False)
        subprocess.run(['pkill', '-f', 'gvfsd'], check=False)
        time.sleep(1)
        if gio_test():
            log('✅ GVfs HTTP backend recovered.')
        else:
            log('❌ GVfs HTTP backend still unresponsive.')
    else:
        log('GVfs backend appears responsive.')

def download_file_async(
    url: str,
    dest_path: str,
    on_output: Optional[Callable[[str], None]],
    on_progress: Optional[Callable[[float], None]],
    on_complete: Optional[Callable[[InstallStatus], None]],
    cancellable: Optional[Gio.Cancellable] = None,
) -> None:
    '''
    Download a file from url to dest_path asynchronously.

    on_output(line):       textual log
    on_progress(fraction): 0.0..1.0 progress fraction
                           for the current file(may be coarse)
    on_complete(status):   'success' | 'failure' | 'cancelled'
    '''
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        src = Gio.File.new_for_uri(url)
        dest = Gio.File.new_for_path(dest_path)
        if on_output:
            on_output('Starting:')

        def progress_cb(cur_bytes: int, total_bytes: int) -> None:
            if total_bytes > 0 and on_progress:
                fraction = float(cur_bytes) / float(total_bytes)
                fraction = max(0.0, min(1.0, fraction))
                on_progress(fraction)
            if on_output:
                kb = cur_bytes / 1024.0
                on_output(f'{kb:.1f} KiB')

        def finish_cb(fileobj: Gio.File, result: Gio.AsyncResult) -> None:
            try:
                # This raises on error or cancellation
                fileobj.copy_finish(result)
                if on_output:
                    on_output('Finished.')
                if on_complete:
                    on_complete('success')
            except GLib.Error as err:
                # detect cancellation
                if err.matches( # pylint: disable=no-value-for-parameter
                        Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED):
                    if on_output:
                        on_output('Cancelled.')
                    if on_complete:
                        on_complete('cancelled')
                else:
                    LOGGER.error('Download failed: %s', err)
                    if on_output:
                        on_output(f'Failed: {err}')
                    if on_complete:
                        on_complete('failure')

        src.copy_async(
            dest,
            Gio.FileCopyFlags.OVERWRITE,
            GLib.PRIORITY_DEFAULT,
            cancellable,
            progress_cb,
            finish_cb,
        )

    except Exception as error: # pylint: disable=broad-except
        LOGGER.exception('Exception during download: %s', error)
        if on_output:
            on_output(f'Exception during download: {error}')
        if on_complete and not (cancellable and cancellable.is_cancelled()):
            on_complete('failure')

def download_dictionaries_sequentially_async(
    languages: Set[str],
    on_output: Optional[Callable[[str], None]],
    on_progress: Optional[Callable[[float], None]],
    on_complete: Optional[Callable[[InstallStatus], None]],
    cancellable: Optional[Gio.Cancellable] = None,
) -> None:
    '''Download dictionaries sequentially, one by one.'''
    url_list: List[Dict[str, str]] = []
    for language in sorted(languages):
        url_base = DICTIONARY_SOURCES.get(language, '')
        if not url_base:
            continue
        for suffix in ('.dic', '.aff'):
            url_list.append({
                'url': f'{url_base}{suffix}',
                'dest':
                itb_util.xdg_save_data_path('ibus-typing-booster/data/')
                + language + suffix})

    results: Dict[str, bool] = {}

    def download_next(index: int = 0) -> None:
        '''Download the next url'''
        if cancellable and cancellable.is_cancelled():
            LOGGER.info('Download cancelled, stopping sequence.')
            if on_complete:
                on_complete('cancelled')
            return
        if index >= len(url_list):
            success = all(results.values())
            LOGGER.info('All downloads done: success=%s', success)
            if on_complete:
                on_complete('success' if success else 'failure')
            return
        url = url_list[index]['url']
        destination = url_list[index]['dest']
        LOGGER.info('Downloading url %s (%d/%d)', url, index + 1, len(url_list))
        if on_output:
            on_output(f'📥 {url}...')

        def handle_output(line: str) -> None:
            '''Call on_output'''
            if on_output:
                on_output(line)

        def handle_progress(fraction: float) -> None:
            '''Call on_progress'''
            if on_progress:
                on_progress(fraction)

        def handle_complete(status: InstallStatus) -> None:
            '''Called when one url is completed

            Puts easily parsable lines into the output to make it
            easy for dialog to update the progress.
            '''
            results[url] = status == 'success'
            if on_output:
                on_output(f'{url} ➡️ {destination} {"✔️" if status == "success" else "⚠️"}')
            if status == 'cancelled':
                LOGGER.info('Installation cancelled before url #%d', index)
                return
            download_next(index + 1)

        download_file_async(
            url,
            destination,
            on_output=handle_output,
            on_progress=handle_progress,
            on_complete=handle_complete,
            cancellable=cancellable)

    download_next()

def ensure_enchant_symlinks(data_dir: str) -> None:
    '''Ensure Enchant hunspell/nuspell directories link to downloaded dictionaries.

    Creates or replaces symlinks for *.dic/*.aff in data_dir under
    ~/.config/enchant/{hunspell,nuspell}/, and cleans up broken symlinks.
    '''
    config_root = pathlib.Path.home() / '.config' / 'enchant'
    data_path = pathlib.Path(data_dir)
    if not data_path.exists():
        LOGGER.warning('Data directory does not exist: %s', data_dir)
        return
    for backend in ('hunspell', 'nuspell'):
        backend_dir = config_root / backend
        backend_dir.mkdir(parents=True, exist_ok=True)
        # Clean up broken symlinks first:
        for link in backend_dir.glob('*'):
            if link.is_symlink() and not link.exists():
                LOGGER.info('Removing broken symlink: %s', link)
                try:
                    link.unlink()
                except OSError as err:
                    LOGGER.error(
                        'Failed to remove broken symlink %s: %s', link, err)
        # Create or update valid symlinks:
        for dict_file in pathlib.Path(data_dir).glob('*.dic'):
            for suffix in ('dic', 'aff'):
                source = data_path / f'{dict_file.stem}.{suffix}'
                if not source.exists():
                    continue
                dest = backend_dir / source.name
                try:
                    # Replace only missing or symlinked destinations
                    if dest.exists():
                        if dest.is_symlink():
                            dest.unlink()
                        else:
                            LOGGER.info(
                                'Preserving existing user dictionary: %s', dest)
                            continue
                    os.symlink(source, dest)
                    LOGGER.info('Linked %s → %s', dest, source)
                except OSError as err:
                    LOGGER.error(
                        'Failed to create symlink %s → %s: %s', dest, source, err)

def download_dictionaries_with_dialog(
    parent: Optional[Gtk.Window],
    languages: Set[str],
    on_complete: Optional[CompleteCallback] = None,
) -> None:
    '''Show a transient GTK dialog to download dictionaries asynchronously.'''
    dialog = Gtk.Dialog(
        title='📥 ' + _('Download dictionaries'),
        transient_for=parent,
        modal=True,
        destroy_with_parent=True)
    dialog.set_default_size(480, 650)
    vbox = dialog.get_content_area()
    top_label = Gtk.Label(label='')
    top_label.set_xalign(0)
    add_child(vbox, top_label)
    textview = Gtk.TextView()
    textview.set_editable(False)
    textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    textbuffer = textview.get_buffer()
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_vexpand(True)
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    add_child(scrolled, textview)
    add_child(vbox, scrolled)
    progressbar = Gtk.ProgressBar()
    progressbar.set_show_text(True)
    progressbar.set_text('0%')
    add_child(vbox, progressbar)
    action_area = Gtk.Box()
    action_area.set_orientation(Gtk.Orientation.HORIZONTAL)
    action_area.set_halign(Gtk.Align.END)
    action_area.set_valign(Gtk.Align.CENTER)
    action_area.set_can_focus(False)
    action_area.set_hexpand(True)
    action_area.set_vexpand(False)
    action_area.set_spacing(0)
    add_child(vbox, action_area)
    cancel_button = Gtk.Button.new_with_mnemonic(_('_Cancel'))
    add_child(action_area, cancel_button)
    close_button = Gtk.Button.new_with_mnemonic(_('_Close'))
    add_child(action_area, close_button)
    show_all(dialog)
    close_button.set_visible(False)

    url_index: int = 0
    url_count: int = 2 * len(languages)
    cancellable: Gio.Cancellable = Gio.Cancellable()

    def append_line(line: str) -> None:
        '''Append a line to the textbuffer showing detailed progress'''
        nonlocal url_index
        end = textbuffer.get_end_iter()
        textbuffer.insert(end, line + '\n')
        textview.scroll_mark_onscreen(textbuffer.get_insert())
        # Detect per-url completion (From messages I emit myself)
        if '✔️' in line or '⚠️' in line:
            # Count this url as fully processed
            url_index += 1
            text = top_label.get_text()
            # In Python < 3.12, f-string expression part cannot include a backslash
            newline = '\n'
            top_label.set_text(f'{text + newline if text else ""}{line}')

    def update_progressbar(fraction: float) -> None:
        '''Update the progressbar showing the total progress'''
        # Make sure UI never jumps backward if fraction temporarily
        # drops (some async backends report non-monotonic progress
        current_fraction = max(
            progressbar.get_fraction(), (url_index + fraction) / url_count)
        progressbar.set_fraction(current_fraction)
        progressbar.set_text(
            f'{url_index}/{url_count} ({int(current_fraction * 100)}%)')

    def finish(status: InstallStatus) -> None:
        '''Installation of all urls finished or cancelled.'''
        if status == 'success':
            progressbar.set_fraction(1.0)
            progressbar.set_text(f'{url_count}/{url_count} (100%)')
            ensure_enchant_symlinks(
                itb_util.xdg_save_data_path('ibus-typing-booster/data/'))
        elif status == 'cancelled':
            end = textbuffer.get_end_iter()
            textbuffer.insert(end, '⚠️ Download cancelled by user.\n')
        else: # 'failed'
            end = textbuffer.get_end_iter()
            textbuffer.insert(end, '❌ There were some failures.\n')
        cancel_button.set_visible(False)
        close_button.set_visible(True)
        if on_complete:
            on_complete(status)

    def on_cancel(_button: Gtk.Button) -> None:
        '''Cancel button clicked'''
        cancellable.cancel()
        cancel_button.set_visible(False)
        close_button.set_visible(True)

    def on_close(_button: Gtk.Button) -> None:
        '''Close button clicked'''
        if glib_main_loop is not None and glib_main_loop.is_running():
            glib_main_loop.quit()
        dialog.destroy()

    cancel_button.connect('clicked', on_cancel)
    close_button.connect('clicked', on_close)
    # Check GVfs health before starting downloads:
    ensure_gvfs_alive(on_output=append_line)
    download_dictionaries_sequentially_async(
        languages,
        on_output=append_line,
        on_progress=update_progressbar,
        on_complete=finish,
        cancellable=cancellable)
    glib_main_loop: Optional[GLib.MainLoop] = None
    # If a GLib main loop is already running (e.g. from setup UI),
    # don’t start another one; just return control to it.
    if GLib.main_depth() > 0: # pylint: disable=no-value-for-parameter
        # There’s already a running loop
        return
    # Otherwise (standalone testing), run our own main loop
    glib_main_loop = GLib.MainLoop()
    glib_main_loop.run()
    dialog.destroy()

if __name__ == '__main__':
    LOG_HANDLER = logging.StreamHandler(stream=sys.stderr)
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.addHandler(LOG_HANDLER)

    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        LOGGER.exception("IBUS-WARNING **: Using the fallback 'C' locale")
        locale.setlocale(locale.LC_ALL, 'C')
    i18n_init()

    def finish_test(status: InstallStatus) -> None:
        '''Called when downloads have completed'''
        if status == 'success':
            LOGGER.info('Install completed without errors.')
        elif status == 'cancelled':
            LOGGER.info('⚠️ Installation cancelled by user.')
        else: # 'failure'
            LOGGER.info('❌ There were some failures.')

    download_dictionaries_with_dialog(
        None,
        set(sorted(DICTIONARY_SOURCES.keys())[:4]),
        on_complete=finish_test,
    )
