# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2011-2013 Anish Patil <apatil@redhat.com>
# Copyright (c) 2012-2018 Mike FABIAN <mfabian@redhat.com>
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
This file implements the ibus engine for ibus-typing-booster
'''

from typing import Any
from typing import Dict
from typing import List
from typing import Tuple
from typing import Union
from typing import Optional
from typing import Iterable
from typing import Callable
import os
import unicodedata
import re
import fnmatch
import ast
import time
import logging
import threading
from gettext import dgettext
# pylint: disable=wrong-import-position
from gi import require_version # type: ignore
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore
require_version('Gio', '2.0')
from gi.repository import Gio
require_version('GLib', '2.0')
from gi.repository import GLib
# pylint: enable=wrong-import-position
import m17n_translit
import itb_util
import itb_active_window
import itb_sound
import itb_emoji
import itb_version

IMPORT_ITB_NLTK_SUCCESSFUL = False
try:
    import itb_nltk
    IMPORT_ITB_NLTK_SUCCESSFUL = True
except (ImportError, LookupError):
    IMPORT_ITB_NLTK_SUCCESSFUL = False

IMPORT_GOOGLE_SPEECH_TO_TEXT_SUCCESSFUL = False
try:
    from google.cloud import speech # type: ignore
    from google.cloud.speech import enums # type: ignore
    from google.cloud.speech import types
    IMPORT_GOOGLE_SPEECH_TO_TEXT_SUCCESSFUL = True
except (ImportError,):
    IMPORT_GOOGLE_SPEECH_TO_TEXT_SUCCESSFUL = False

IMPORT_BIDI_ALGORITHM_SUCCESSFUL = False
try:
    import bidi.algorithm # type: ignore
    IMPORT_BIDI_ALGORITHM_SUCCESSFUL = True
except (ImportError,):
    IMPORT_BIDI_ALGORITHM_SUCCESSFUL = False

LOGGER = logging.getLogger('ibus-typing-booster')

__all__ = (
    "TypingBoosterEngine",
)

_: Callable[[str], str] = lambda a: dgettext("ibus-typing-booster", a)
N_: Callable[[str], str] = lambda a: a

DEBUG_LEVEL = int(0)

# ☐ U+2610 BALLOT BOX
MODE_OFF_SYMBOL = '☐'
# ☑ U+2611 BALLOT BOX WITH CHECK
# 🗹 U+1F5F9 BALLOT_BOX WITH BOLD CHECK
MODE_ON_SYMBOL = '☑'

#  ☺ U+263A WHITE SMILING FACE
# 😃 U+1F603 SMILING FACE WITH OPEN MOUTH
# 🙂 U+1F642 SLIGHTLY SMILING FACE
EMOJI_PREDICTION_MODE_SYMBOL = '🙂'

# 🕶 U+1F576 DARK SUNGLASSES
# 😎 U+1F60E SMILING FACE WITH SUNGLASSES
# 🕵 U+1F575 SLEUTH OR SPY
OFF_THE_RECORD_MODE_SYMBOL = '🕵'

INPUT_MODE_TRUE_SYMBOL = '🚀'
INPUT_MODE_FALSE_SYMBOL = '🐌'

IBUS_VERSION = (IBus.MAJOR_VERSION, IBus.MINOR_VERSION, IBus.MICRO_VERSION)

class TypingBoosterEngine(IBus.Engine): # type: ignore
    '''The IBus Engine for ibus-typing-booster'''

    def __init__(
            self,
            bus: IBus.Bus,
            obj_path: str,
            database: Any, # tabsqlitedb.TabSqliteDb
            unit_test: bool = False) -> None:
        global DEBUG_LEVEL # pylint: disable=global-statement
        try:
            DEBUG_LEVEL = int(str(os.getenv(
                'IBUS_TYPING_BOOSTER_DEBUG_LEVEL')))
        except (TypeError, ValueError):
            DEBUG_LEVEL = int(0)
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'TypingBoosterEngine.__init__'
                '(bus=%s, obj_path=%s, database=%s)',
                bus, obj_path, database)
        LOGGER.info('ibus version = %s', '.'.join(map(str, IBUS_VERSION)))
        if hasattr(IBus.Engine.props, 'has_focus_id'):
            super().__init__(
                connection=bus.get_connection(),
                object_path=obj_path,
                has_focus_id=True)
            LOGGER.info('This ibus version has focus id.')
        else:
            super().__init__(
                connection=bus.get_connection(),
                object_path=obj_path)
            LOGGER.info('This ibus version does *not* have focus id.')

        self._keyvals_to_keycodes = itb_util.KeyvalsToKeycodes()
        self._compose_sequences = itb_util.ComposeSequences()
        self._unit_test = unit_test
        self._input_purpose: int = 0
        self._input_hints: int = 0
        self._lookup_table_is_invalid = False
        self._lookup_table_hidden = False
        self._lookup_table_shows_related_candidates = False
        self._lookup_table_shows_compose_completions = False
        self._current_auxiliary_text = ''
        self._current_preedit_text = ''
        self._bus = bus
        self.database = database
        self.emoji_matcher: Optional[itb_emoji.EmojiMatcher] = None
        self._setup_pid = 0
        self._gsettings = Gio.Settings(
            schema='org.freedesktop.ibus.engine.typing-booster')

        self._prop_dict: Dict[str, IBus.Property] = {}
        self._sub_props_dict: Dict[str, IBus.PropList] = {}
        self.main_prop_list: List[IBus.Property] = []
        self.emoji_prediction_mode_menu: Dict[str, Any] = {}
        self.emoji_prediction_mode_properties: Dict[str, Any]= {}
        self.off_the_record_mode_menu: Dict[str, Any] = {}
        self.off_the_record_mode_properties: Dict[str, Any] = {}
        self.input_mode_menu: Dict[str, Any] = {}
        self.input_mode_properties: Dict[str, Any] = {}
        self.dictionary_menu: Dict[str, Any] = {}
        self.dictionary_properties: Dict[str, Any] = {}
        self.dictionary_sub_properties_prop_list: IBus.PropList = []
        self.preedit_ime_menu: Dict[str, Any] = {}
        self.preedit_ime_properties: Dict[str, Any] = {}
        self.preedit_ime_sub_properties_prop_list: IBus.PropList = []
        self._setup_property: Optional[IBus.Property] = None
        self._im_client: str = ''

        self._current_imes: List[str] = []

        # Between some events sent to ibus like forward_key_event(),
        # delete_surrounding_text(), commit_text(), a sleep is necessary.
        # Without the sleep, these events may be processed out of order.
        self._ibus_event_sleep_seconds: float = itb_util.variant_to_value(
            self._gsettings.get_value('ibuseventsleepseconds'))
        LOGGER.info('self._ibus_event_sleep_seconds=%s', self._ibus_event_sleep_seconds)

        self._emoji_predictions: bool = itb_util.variant_to_value(
            self._gsettings.get_value('emojipredictions'))

        self.is_lookup_table_enabled_by_min_char_complete = False
        self._min_char_complete: int = itb_util.variant_to_value(
            self._gsettings.get_value('mincharcomplete'))
        self._min_char_complete = max(self._min_char_complete, 0)
        self._min_char_complete = min(self._min_char_complete, 9)

        self._debug_level: int = itb_util.variant_to_value(
            self._gsettings.get_value('debuglevel'))
        self._debug_level = max(self._debug_level, 0)
        self._debug_level = min(self._debug_level, 255)
        DEBUG_LEVEL = self._debug_level

        self._page_size: int = itb_util.variant_to_value(
            self._gsettings.get_value('pagesize'))
        self._page_size = max(self._page_size, 1)
        self._page_size = min(self._page_size, 9)

        self._lookup_table_orientation: int = itb_util.variant_to_value(
            self._gsettings.get_value('lookuptableorientation'))

        self._preedit_underline: int = itb_util.variant_to_value(
            self._gsettings.get_value('preeditunderline'))

        self._preedit_style_only_when_lookup: bool = itb_util.variant_to_value(
            self._gsettings.get_value('preeditstyleonlywhenlookup'))

        self._show_number_of_candidates: bool = itb_util.variant_to_value(
            self._gsettings.get_value('shownumberofcandidates'))

        self._show_status_info_in_auxiliary_text: bool = (
            itb_util.variant_to_value(
                self._gsettings.get_value('showstatusinfoinaux')))

        self._is_candidate_auto_selected = False
        self._auto_select_candidate: int = itb_util.variant_to_value(
            self._gsettings.get_value('autoselectcandidate'))

        self.is_lookup_table_enabled_by_tab = False
        self._tab_enable: bool = itb_util.variant_to_value(
            self._gsettings.get_value('tabenable'))

        self._disable_in_terminals: bool = itb_util.variant_to_value(
            self._gsettings.get_value('disableinterminals'))

        self._ascii_digits: bool = itb_util.variant_to_value(
            self._gsettings.get_value('asciidigits'))

        self._off_the_record: bool = itb_util.variant_to_value(
            self._gsettings.get_value('offtherecord'))

        self._hide_input = False

        self._input_mode = True

        self._avoid_forward_key_event: bool = itb_util.variant_to_value(
            self._gsettings.get_value('avoidforwardkeyevent'))

        self._arrow_keys_reopen_preedit: bool = itb_util.variant_to_value(
            self._gsettings.get_value('arrowkeysreopenpreedit'))

        self._emoji_trigger_characters: str = itb_util.variant_to_value(
            self._gsettings.get_value('emojitriggercharacters'))

        self._auto_commit_characters: str = itb_util.variant_to_value(
            self._gsettings.get_value('autocommitcharacters'))

        self._remember_last_used_preedit_ime: bool = itb_util.variant_to_value(
            self._gsettings.get_value('rememberlastusedpreeditime'))

        self._add_space_on_commit: bool = itb_util.variant_to_value(
            self._gsettings.get_value('addspaceoncommit'))

        self._inline_completion: int = itb_util.variant_to_value(
            self._gsettings.get_value('inlinecompletion'))

        self._record_mode: int = itb_util.variant_to_value(
            self._gsettings.get_value('recordmode'))

        self._auto_capitalize: bool = itb_util.variant_to_value(
            self._gsettings.get_value('autocapitalize'))

        self._color_preedit_spellcheck: bool = itb_util.variant_to_value(
            self._gsettings.get_value('colorpreeditspellcheck'))

        self._color_preedit_spellcheck_string: str = itb_util.variant_to_value(
            self._gsettings.get_value('colorpreeditspellcheckstring'))
        self._color_preedit_spellcheck_argb = itb_util.color_string_to_argb(
            self._color_preedit_spellcheck_string)

        self._color_inline_completion: bool = itb_util.variant_to_value(
            self._gsettings.get_value('colorinlinecompletion'))

        self._color_inline_completion_string: str = itb_util.variant_to_value(
            self._gsettings.get_value('colorinlinecompletionstring'))
        self._color_inline_completion_argb = itb_util.color_string_to_argb(
            self._color_inline_completion_string)

        self._color_compose_preview: bool = itb_util.variant_to_value(
            self._gsettings.get_value('colorcomposepreview'))

        self._color_compose_preview_string: str = itb_util.variant_to_value(
            self._gsettings.get_value('colorcomposepreviewstring'))
        self._color_compose_preview_argb = itb_util.color_string_to_argb(
            self._color_compose_preview_string)

        self._color_userdb: bool = itb_util.variant_to_value(
            self._gsettings.get_value('coloruserdb'))

        self._color_userdb_string: str = itb_util.variant_to_value(
            self._gsettings.get_value('coloruserdbstring'))
        self._color_userdb_argb = itb_util.color_string_to_argb(
            self._color_userdb_string)

        self._color_spellcheck: bool = itb_util.variant_to_value(
            self._gsettings.get_value('colorspellcheck'))

        self._color_spellcheck_string: str = itb_util.variant_to_value(
            self._gsettings.get_value('colorspellcheckstring'))
        self._color_spellcheck_argb = itb_util.color_string_to_argb(
            self._color_spellcheck_string)

        self._color_dictionary: bool = itb_util.variant_to_value(
            self._gsettings.get_value('colordictionary'))

        self._color_dictionary_string: str = itb_util.variant_to_value(
            self._gsettings.get_value('colordictionarystring'))
        self._color_dictionary_argb = itb_util.color_string_to_argb(
            self._color_dictionary_string)

        self._label_userdb: bool = itb_util.variant_to_value(
            self._gsettings.get_value('labeluserdb'))

        self._label_userdb_string: str = itb_util.variant_to_value(
            self._gsettings.get_value('labeluserdbstring'))

        self._label_spellcheck: bool = itb_util.variant_to_value(
            self._gsettings.get_value('labelspellcheck'))

        self._label_spellcheck_string: str = itb_util.variant_to_value(
            self._gsettings.get_value('labelspellcheckstring'))

        self._label_dictionary: bool = itb_util.variant_to_value(
            self._gsettings.get_value('labeldictionary'))

        self._label_dictionary_string: str = ''
        self._label_dictionary_dict: Dict[str, str] = {}
        self.set_label_dictionary_string(
            itb_util.variant_to_value(
                self._gsettings.get_value('labeldictionarystring')),
            update_gsettings=False)

        self._flag_dictionary: bool = itb_util.variant_to_value(
            self._gsettings.get_value('flagdictionary'))

        self._label_busy: bool = itb_util.variant_to_value(
            self._gsettings.get_value('labelbusy'))

        self._label_busy_string: str = itb_util.variant_to_value(
            self._gsettings.get_value('labelbusystring'))

        self._label_speech_recognition: bool = True
        self._label_speech_recognition_string: str = '🎙️'

        self._google_application_credentials: str = itb_util.variant_to_value(
            self._gsettings.get_value('googleapplicationcredentials'))

        self._keybindings: Dict[str, List[str]] = {}
        self._hotkeys: Optional[itb_util.HotKeys] = None
        self._normal_digits_used_in_keybindings = False
        self._keypad_digits_used_in_keybindings = False
        self.set_keybindings(
            itb_util.variant_to_value(
                self._gsettings.get_value('keybindings')),
            update_gsettings=False)

        self._autosettings: List[Tuple[str, str, str]] = []
        self.set_autosettings(
            itb_util.variant_to_value(
                self._gsettings.get_value('autosettings')),
            update_gsettings=False)
        self._autosettings_revert: Dict[str, Any] = {}

        self._remember_input_mode: bool = itb_util.variant_to_value(
            self._gsettings.get_value('rememberinputmode'))
        if (self._keybindings['toggle_input_mode_on_off']
            and self._remember_input_mode):
            self._input_mode = itb_util.variant_to_value(
                self._gsettings.get_value('inputmode'))
        else:
            self.set_input_mode(True, update_gsettings=True)

        self._sound_backend: str = itb_util.variant_to_value(
            self._gsettings.get_value('soundbackend'))
        self._error_sound_object: Optional[itb_sound.SoundObject] = None
        self._error_sound_file = ''
        self._error_sound: bool = itb_util.variant_to_value(
            self._gsettings.get_value('errorsound'))
        self.set_error_sound_file(
            itb_util.variant_to_value(
                self._gsettings.get_value('errorsoundfile')),
            update_gsettings=False)

        self._dictionary_names: List[str] = []
        dictionary = itb_util.variant_to_value(
            self._gsettings.get_value('dictionary'))
        self._dictionary_names = itb_util.dictionaries_str_to_list(dictionary)
        if ','.join(self._dictionary_names) != dictionary:
            # Value changed due to normalization or getting the locale
            # defaults, save it back to settings:
            self._gsettings.set_value(
                'dictionary',
                GLib.Variant.new_string(','.join(self._dictionary_names)))
        self.database.hunspell_obj.set_dictionary_names(
            self._dictionary_names[:])
        self._dictionary_flags: Dict[str, str] = itb_util.get_flags(
            self._dictionary_names)

        if  self._emoji_predictions:
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Instantiate EmojiMatcher(languages = %s',
                             self._dictionary_names)
            self.emoji_matcher = itb_emoji.EmojiMatcher(
                languages=self._dictionary_names)
            if DEBUG_LEVEL > 1:
                LOGGER.debug('EmojiMatcher() instantiated.')
        else:
            self.emoji_matcher = None

        # Try to get the selected input methods from Gsettings:
        inputmethod = itb_util.variant_to_value(
            self._gsettings.get_value('inputmethod'))
        self._current_imes = itb_util.input_methods_str_to_list(inputmethod)
        if ','.join(self._current_imes) != inputmethod:
            # Value changed due to normalization or getting the locale
            # defaults, save it back to settings:
            self._gsettings.set_value(
                'inputmethod',
                GLib.Variant.new_string(','.join(self._current_imes)))

        self._commit_happened_after_focus_in = False
        self._surrounding_text_event_happened_after_focus_in = False

        self._prev_key: Optional[itb_util.KeyEvent] = None
        self._typed_compose_sequence: List[int] = [] # A list of key values
        self._typed_string: List[str] = [] # A list of msymbols
        self._typed_string_cursor = 0
        self._p_phrase = ''
        self._pp_phrase = ''
        self._ppp_phrase = ''
        self._new_sentence = False
        self._transliterated_strings: Dict[str, str] = {}
        self._transliterated_strings_before_compose: Dict[str, str] = {}
        self._transliterated_strings_compose_part = ''
        self._transliterators: Dict[str, m17n_translit.Transliterator] = {}
        self._init_transliterators()
        # self._candidates: Array to hold candidates found in the
        #                   user database, the (hunspell) dictionaries,
        #                   produced by hunspell spellchecking, found
        #                   by the emoji matcher, or found by looking
        #                   up related matches.
        #
        # Each elememt of the self._candidates array is a tuple like
        #
        #     (phrase, user_freq, comment, from_user_db, spell_checking)
        #
        #          phrase:  String, the candidate itself, i.e. the text
        #                   which might be eventually committed.
        #          user_freq: Float, a number indicating a usage frequency.
        #                     If the candidate comes from the user database,
        #                     this is a floating point number between 0 and 1.
        #                     If the candidate comes from the emoji matcher,
        #                     it is some integer number, usually quite big.
        #                     If the candidate comes from looking up related
        #                     stuff it is usually a small integer  number.
        #          comment: String, may give some extra  information about
        #                   the candidate, for example the name of an emoji.
        #                   This is just some extra information, it will not be
        #                   committed.
        #          from_user_db: Boolean, True if this candidate comes from the
        #                        user database, False if not.
        #          spell_checking: Boolean, True if this candidate was produced
        #                          by spellchecking, False if not.
        self._candidates: List[Tuple[str, int, str, bool, bool]] = []
        # a copy of self._candidates in case mode 'orig':
        self._candidates_case_mode_orig: List[
            Tuple[str, int, str, bool, bool]] = []
        self._current_case_mode = 'orig'
        # 'orig': candidates have original case.
        # 'capitalize': candidates have been converted to the first character
        #               in upper case.
        # 'title': candidates have been converted to Python’s title case.
        # 'upper': candidates have been completely converted to upper case.
        # 'lower': candidates have been completely converted to lower case.
        #
        # 'title' does not seem very useful, so when using 'next' or
        # 'previous', 'title' is skipped.
        self._case_modes = {
            'orig': {
                'next': 'capitalize',
                'previous': 'lower',
                'function': lambda x: x},
            'capitalize': {
                'next': 'upper',
                'previous': 'lower',
                'function': lambda x: getattr(
                    str, 'capitalize')(x[:1]) + x[1:]},
            'title': {
                'next': 'upper',
                'previous': 'capitalize',
                # Python’s title case has problems when the string is in NFD.
                # In that case something like this can happen:
                #
                # >>> str.title('bücher')
                # 'BüCher'
                #
                # Therefore, make sure the case change is done after the string
                # is converted to NFC.
                'function': lambda x: getattr(
                    str, 'title')(unicodedata.normalize('NFC', x))},
            'upper': {
                'next': 'lower',
                'previous': 'capitalize',
                'function': getattr(str, 'upper')},
            'lower': {
                'next': 'capitalize',
                'previous': 'upper',
                'function': getattr(str, 'lower')},
        }

        self._lookup_table = self._get_new_lookup_table()

        self.input_mode_properties = {
            'InputMode.Off': {
                'number': 0,
                'symbol': INPUT_MODE_FALSE_SYMBOL,
                'label': _('Off'),
            },
            'InputMode.On': {
                'number': 1,
                'symbol': INPUT_MODE_TRUE_SYMBOL,
                'label': _('On'),
            }
        }
        # The symbol of the property “InputMode” is displayed
        # in the input method indicator of the Gnome3 panel.
        # This depends on the property name “InputMode” and
        # is case sensitive!
        #
        # Don’t make this symbol too long: Using “あ” for hiragana
        # mode and “_A” for direct input mode works in ibus-anthy and
        # ibus-kkc. So 2 Latin characters or one wide character seem
        # to work in Gnome3.  But “☐🚀” for typing-booster on and
        # “☑🚀” for typing-booster off do not work at all in Gnome3,
        # only the rocket emoji is shown in that case and the ballot
        # boxes are not visible. In KDE these look so small that they
        # are very hard to distinguish. Using a single emoji for each
        # mode seems to work well both in Gnome3 and non-Gnome desktops.
        self.input_mode_menu = {
            'key': 'InputMode',
            'label': _('Input mode'),
            'tooltip': _('Here you can switch ibus-typing-booster on or off.'),
            'shortcut_hint': repr(
                self._keybindings['toggle_input_mode_on_off']),
            'sub_properties': self.input_mode_properties
        }
        self.emoji_prediction_mode_properties = {
            'EmojiPredictionMode.Off': {
                'number': 0,
                'symbol': MODE_OFF_SYMBOL + EMOJI_PREDICTION_MODE_SYMBOL,
                'label': _('Off'),
            },
            'EmojiPredictionMode.On': {
                'number': 1,
                'symbol': MODE_ON_SYMBOL + EMOJI_PREDICTION_MODE_SYMBOL,
                'label': _('On'),
            }
        }
        self.emoji_prediction_mode_menu = {
            'key': 'EmojiPredictionMode',
            'label': _('Unicode symbols and emoji predictions'),
            'tooltip':
            _('Unicode symbols and emoji predictions'),
            'shortcut_hint': repr(
                self._keybindings['toggle_emoji_prediction']),
            'sub_properties': self.emoji_prediction_mode_properties
        }
        self.off_the_record_mode_properties = {
            'OffTheRecordMode.Off': {
                'number': 0,
                'symbol': MODE_OFF_SYMBOL + OFF_THE_RECORD_MODE_SYMBOL,
                'label': _('Off'),
            },
            'OffTheRecordMode.On': {
                'number': 1,
                'symbol': MODE_ON_SYMBOL + OFF_THE_RECORD_MODE_SYMBOL,
                'label': _('On'),
            }
        }
        self.off_the_record_mode_menu = {
            'key': 'OffTheRecordMode',
            'label': _('Off the record mode'),
            'tooltip': _('Off the record mode'),
            'shortcut_hint': repr(self._keybindings['toggle_off_the_record']),
            'sub_properties': self.off_the_record_mode_properties
        }

        self._update_dictionary_menu_dicts()
        self._update_preedit_ime_menu_dicts()
        self._init_properties()

        keys_which_select_with_shift = (
            IBus.KEY_Right, IBus.KEY_KP_Right,
            IBus.KEY_Left, IBus.KEY_KP_Left,
            IBus.KEY_End, IBus.KEY_KP_End,
            IBus.KEY_Home, IBus.KEY_KP_Home,
            IBus.KEY_Down, IBus.KEY_KP_Down,
            IBus.KEY_Up, IBus.KEY_KP_Up,
            IBus.KEY_Page_Down, IBus.KEY_KP_Page_Down, IBus.KEY_KP_Next,
            IBus.KEY_Page_Up, IBus.KEY_KP_Page_Up, IBus.KEY_KP_Prior)
        self._commit_trigger_keys = keys_which_select_with_shift + (
            IBus.KEY_space, IBus.KEY_Tab,
            IBus.KEY_Return, IBus.KEY_KP_Enter,
            IBus.KEY_Delete, IBus.KEY_KP_Delete,
            IBus.KEY_BackSpace)
        self.connect('set-surrounding-text', self.on_set_surrounding_text)
        self._set_surrounding_text_text: Optional[str] = None
        self._set_surrounding_text_cursor_pos: Optional[int] = None
        self._set_surrounding_text_anchor_pos: Optional[int] = None
        self._set_surrounding_text_event = threading.Event()
        self._set_surrounding_text_event.clear()
        self._surrounding_text_old: Optional[Tuple[IBus.Text, int, int]] = None
        self._is_context_from_surrounding_text = False

        self._set_get_functions: Dict[str, Dict[str, Any]] = {
            'inputmethod': {
                'set': self.set_current_imes,
                'get': self.get_current_imes},
            'dictionary': {
                'set': self.set_dictionary_names,
                'get': self.get_dictionary_names},
            'dictionaryinstalltimestamp': {
                'set': self._reload_dictionaries},
            'inputmethodchangetimestamp': {
                'set': self._reload_input_methods},
            'avoidforwardkeyevent': {
                'set': self.set_avoid_forward_key_event,
                'get': self.get_avoid_forward_key_event},
            'addspaceoncommit': {
                'set': self.set_add_space_on_commit,
                'get': self.get_add_space_on_commit},
            'inlinecompletion': {
                'set': self.set_inline_completion,
                'get': self.get_inline_completion},
            'recordmode': {
                'set': self.set_record_mode,
                'get': self.get_record_mode},
            'autocapitalize': {
                'set': self.set_auto_capitalize,
                'get': self.get_auto_capitalize},
            'arrowkeysreopenpreedit': {
                'set': self.set_arrow_keys_reopen_preedit,
                'get': self.get_arrow_keys_reopen_preedit},
            'emojipredictions': {
                'set': self.set_emoji_prediction_mode,
                'get': self.get_emoji_prediction_mode},
            'offtherecord': {
                'set': self.set_off_the_record_mode,
                'get': self.get_off_the_record_mode},
            'emojitriggercharacters': {
                'set': self.set_emoji_trigger_characters,
                'get': self.get_emoji_trigger_characters},
            'autocommitcharacters': {
                'set': self.set_auto_commit_characters,
                'get': self.get_auto_commit_characters},
            'tabenable': {
                'set': self.set_tab_enable,
                'get': self.get_tab_enable},
            'rememberlastusedpreeditime': {
                'set': self.set_remember_last_used_preedit_ime,
                'get': self.get_remember_last_used_preedit_ime},
            'rememberinputmode': {
                'set': self.set_remember_input_mode,
                'get': self.get_remember_input_mode},
            'inputmode': {
                'set': self.set_input_mode,
                'get': self.get_input_mode},
            'disableinterminals': {
                'set': self.set_disable_in_terminals,
                'get': self.get_disable_in_terminals},
            'asciidigits': {
                'set': self.set_ascii_digits,
                'get': self.get_ascii_digits},
            'pagesize': {
                'set': self.set_page_size,
                'get': self.get_page_size},
            'lookuptableorientation': {
                'set': self.set_lookup_table_orientation,
                'get': self.get_lookup_table_orientation},
            'preeditunderline': {
                'set': self.set_preedit_underline,
                'get': self.get_preedit_underline},
            'preeditstyleonlywhenlookup': {
                'set': self.set_preedit_style_only_when_lookup,
                'get': self.get_preedit_style_only_when_lookup},
            'mincharcomplete': {
                'set': self.set_min_char_complete,
                'get': self.get_min_char_complete},
            'debuglevel': {
                'set': self.set_debug_level,
                'get': self.get_debug_level},
            'ibuseventsleepseconds': {
                'set': self.set_ibus_event_sleep_seconds,
                'get': self.get_ibus_event_sleep_seconds},
            'errorsound': {
                'set': self.set_error_sound,
                'get': self.get_error_sound},
            'errorsoundfile': {
                'set': self.set_error_sound_file,
                'get': self.get_error_sound_file},
            'soundbackend': {
                'set': self.set_sound_backend,
                'get': self.get_sound_backend},
            'shownumberofcandidates': {
                'set': self.set_show_number_of_candidates,
                'get': self.get_show_number_of_candidates},
            'showstatusinfoinaux': {
                'set': self.set_show_status_info_in_auxiliary_text,
                'get': self.get_show_status_info_in_auxiliary_text},
            'autoselectcandidate': {
                'set': self.set_auto_select_candidate,
                'get': self.get_auto_select_candidate},
            'colorpreeditspellcheck': {
                'set': self.set_color_preedit_spellcheck,
                'get': self.get_color_preedit_spellcheck},
            'colorpreeditspellcheckstring': {
                'set': self.set_color_preedit_spellcheck_string,
                'get': self.get_color_preedit_spellcheck_string},
            'colorinlinecompletion': {
                'set': self.set_color_inline_completion,
                'get': self.get_color_inline_completion},
            'colorinlinecompletionstring': {
                'set': self.set_color_inline_completion_string,
                'get': self.get_color_inline_completion_string},
            'colorcomposepreview': {
                'set': self.set_color_compose_preview,
                'get': self.get_color_compose_preview},
            'colorcomposepreviewstring': {
                'set': self.set_color_compose_preview_string,
                'get': self.get_color_compose_preview_string},
            'coloruserdb': {
                'set': self.set_color_userdb,
                'get': self.get_color_userdb},
            'coloruserdbstring': {
                'set': self.set_color_userdb_string,
                'get': self.get_color_userdb_string},
            'colorspellcheck': {
                'set': self.set_color_spellcheck,
                'get': self.get_color_spellcheck},
            'colorspellcheckstring': {
                'set': self.set_color_spellcheck_string,
                'get': self.get_color_spellcheck_string},
            'colordictionary': {
                'set': self.set_color_dictionary,
                'get': self.get_color_dictionary},
            'colordictionarystring': {
                'set': self.set_color_dictionary_string,
                'get': self.get_color_dictionary_string},
            'labeluserdb': {
                'set': self.set_label_userdb,
                'get': self.get_label_userdb},
            'labeluserdbstring': {
                'set': self.set_label_userdb_string,
                'get': self.get_label_userdb_string},
            'labelspellcheck': {
                'set': self.set_label_spellcheck,
                'get': self.get_label_spellcheck},
            'labelspellcheckstring': {
                'set': self.set_label_spellcheck_string,
                'get': self.get_label_spellcheck_string},
            'labeldictionary': {
                'set': self.set_label_dictionary,
                'get': self.get_label_dictionary},
            'labeldictionarystring': {
                'set': self.set_label_dictionary_string,
                'get': self.get_label_dictionary_string},
            'flagdictionary': {
                'set': self.set_flag_dictionary,
                'get': self.get_flag_dictionary},
            'labelbusy': {
                'set': self.set_label_busy,
                'get': self.get_label_busy},
            'labelbusystring': {
                'set': self.set_label_busy_string,
                'get': self.get_label_busy_string},
            'keybindings': {
                'set': self.set_keybindings,
                'get': self.get_keybindings},
            'autosettings': {
                'set': self.set_autosettings,
                'get': self.get_autosettings},
            'googleapplicationcredentials': {
                'set': self.set_google_application_credentials,
                'get': self.get_google_application_credentials},
        }
        self._gsettings.connect('changed', self.on_gsettings_value_changed)

        self._clear_input_and_update_ui()

        LOGGER.info(
            '*** ibus-typing-booster %s initialized, ready for input: ***',
            itb_version.get_version())

        cleanup_database_thread = threading.Thread(
            target=self.database.cleanup_database)
        cleanup_database_thread.start()

    def _get_new_lookup_table(self) -> IBus.LookupTable:
        '''Get a new lookup table'''
        lookup_table = IBus.LookupTable()
        lookup_table.clear()
        lookup_table.set_page_size(self._page_size)
        lookup_table.set_orientation(self._lookup_table_orientation)
        lookup_table.set_cursor_visible(False)
        # lookup_table.set_round() chooses whether the cursor in the
        # lookup table wraps around when the end or the beginning of
        # the table is reached.  I think this is confusing for
        # ibus-typing-booster, it should be set to False.
        lookup_table.set_round(False)
        for index in range(0, 9):
            label = str(index + 1)
            lookup_table.set_label(index, IBus.Text.new_from_string(label))
        return lookup_table

    def _init_transliterators(self) -> None:
        '''Initialize the dictionary of m17n-db transliterator objects'''
        self._transliterators = {}
        for ime in self._current_imes:
            # using m17n transliteration
            try:
                if DEBUG_LEVEL > 1:
                    LOGGER.debug(
                        'instantiating Transliterator(%(ime)s)',
                        {'ime': ime})
                self._transliterators[ime] = m17n_translit.Transliterator(ime)
            except ValueError:
                LOGGER.exception(
                    'Error initializing Transliterator %s '
                    'Maybe /usr/share/m17n/%s.mim is not installed?',
                    ime, ime)
                # Use dummy transliterator “NoIME” as a fallback:
                self._transliterators[ime] = m17n_translit.Transliterator(
                    'NoIME')
        self._update_transliterated_strings()

    def is_empty(self) -> bool:
        '''Checks whether the preëdit is empty

        Returns True if the preëdit is empty, False if not.
        '''
        return len(self._typed_string) == 0

    def _clear_input(self) -> None:
        '''Clear all input'''
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)
        self._is_candidate_auto_selected = False
        self._candidates = []
        self._current_case_mode = 'orig'
        self._typed_compose_sequence = []
        self._prev_key = None
        self._typed_string = []
        self._typed_string_cursor = 0
        for ime in self._current_imes:
            self._transliterated_strings[ime] = ''
        self.is_lookup_table_enabled_by_tab = False
        self.is_lookup_table_enabled_by_min_char_complete = False
        self._lookup_table_is_invalid = False
        self._lookup_table_hidden = False
        self._lookup_table_shows_related_candidates = False
        self._lookup_table_shows_compose_completions = False

    def _insert_string_at_cursor(self, string_to_insert: List[str]) -> None:
        '''Insert typed string at cursor position'''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('string_to_insert=%s', string_to_insert)
            LOGGER.debug('self._typed_string=%s', self._typed_string)
            LOGGER.debug('self._typed_string_cursor=%s',
                         self._typed_string_cursor)
        self._typed_string = self._typed_string[:self._typed_string_cursor] \
                             +string_to_insert \
                             +self._typed_string[self._typed_string_cursor:]
        self._typed_string_cursor += len(string_to_insert)
        self._update_transliterated_strings()

    def _remove_string_before_cursor(self) -> None:
        '''Remove typed string before cursor'''
        if self._typed_string_cursor > 0:
            self._typed_string = self._typed_string[self._typed_string_cursor:]
            self._typed_string_cursor = 0
            self._update_transliterated_strings()

    def _remove_string_after_cursor(self) -> None:
        '''Remove typed string after cursor'''
        if self._typed_string_cursor < len(self._typed_string):
            self._typed_string = self._typed_string[:self._typed_string_cursor]
            self._update_transliterated_strings()

    def _remove_character_before_cursor(self) -> None:
        '''Remove typed character before cursor'''
        if self._typed_string_cursor > 0:
            self._typed_string = (
                self._typed_string[:self._typed_string_cursor-1]
                +self._typed_string[self._typed_string_cursor:])
            self._typed_string_cursor -= 1
            self._update_transliterated_strings()

    def _remove_character_after_cursor(self) -> None:
        '''Remove typed character after cursor'''
        if self._typed_string_cursor < len(self._typed_string):
            self._typed_string = (
                self._typed_string[:self._typed_string_cursor]
                +self._typed_string[self._typed_string_cursor+1:])
            self._update_transliterated_strings()

    def get_caret(self) -> int:
        '''
        Get caret position in preëdit string

        The preëdit contains the transliterated string, the caret
        position can only be approximated from the cursor position in
        the typed string.

        For example, if the typed string is “gru"n” and the
        transliteration method used is “Latin Postfix”, this
        transliterates to “grün”. Now if the cursor position in the
        typed string is “3”, then the cursor is between the “u”
        and the “"”.  In the transliterated string, this would be in the
        middle of the “ü”. But the caret cannot be shown there of course.

        So the caret position is approximated by transliterating the
        string up to the cursor, i.e. transliterating “gru” which
        gives “gru” and return the length of that
        transliteration as the caret position. Therefore, the caret
        is displayed after the “ü” instead of in the middle of the “ü”.

        This has the effect that when typing “arrow left” over a
        preëdit string “grün” which has been typed as “gru"n”
        using Latin Postfix translation, one needs to type “arrow
        left” two times to get over the “ü”.

        If the cursor is at position 3 in the input string “gru"n”,
        and one types an “a” there, the input string becomes
        “grua"n” and the transliterated string, i.e. the preëdit,
        becomes “gruän”, which might be a bit surprising, but that
        is at least consistent and better then nothing at the moment.

        This problem is certainly worse in languages like Marathi where
        these length differences between the input and the transliteration
        are worse.

        But until this change, the code to move around and edit in
        the preëdit did not work at all. Now it works fine if
        no transliteration is used and works better than nothing
        even if transliteration is used.
        '''
        preedit_ime = self._current_imes[0]
        transliterated_string_up_to_cursor = (
            self._transliterators[preedit_ime].transliterate(
                self._typed_string[:self._typed_string_cursor],
                ascii_digits=self._ascii_digits))
        if preedit_ime in ['ko-romaja', 'ko-han2']:
            transliterated_string_up_to_cursor = unicodedata.normalize(
                'NFKD', transliterated_string_up_to_cursor)
        transliterated_string_up_to_cursor = unicodedata.normalize(
            'NFC', transliterated_string_up_to_cursor)
        caret = len(transliterated_string_up_to_cursor)
        if self._typed_compose_sequence:
            caret += len(
                self._compose_sequences.preedit_representation(
                    self._typed_compose_sequence))
        return caret

    def _append_candidate_to_lookup_table(
            self, phrase: str = '',
            user_freq: int = 0,
            comment: str = '',
            from_user_db: bool = False,
            spell_checking: bool = False) -> None:
        '''append candidate to lookup_table'''
        if not phrase:
            return
        phrase = unicodedata.normalize('NFC', phrase)
        dictionary_matches: List[str] = (
            self.database.hunspell_obj.spellcheck_match_list(phrase))
        # U+2028 LINE SEPARATOR and U+2029 PARAGRAPH SEPARATOR make
        # the line spacing in the lookup table huge, which looks ugly.
        # Remove them to make the lookup table look better.
        # Selecting them does still work because the string which
        # is committed is not read from the lookup table but
        # from self._candidates[index][0].
        phrase = phrase.replace(' ', '').replace(' ', '')
        # Embed “phrase” and “comment” separately with “Explicit
        # Directional Embeddings” (RLE, LRE, PDF).
        #
        # Using “Explicit Directional Isolates” (FSI, PDI) would be
        # better, but they don’t seem to work yet. Maybe not
        # implemented yet?
        #
        # This embedding can be necessary when “phrase” and “comment”
        # have different bidi directions.
        #
        # For example, the currency symbol ﷼ U+FDFC RIAL SIGN is a
        # strong right-to-left character. When looking up related
        # symbols for another currency symbol, U+FDFC RIAL SIGN should
        # be among the candidates. But the comment is just the name
        # from UnicodeData.txt. Without adding any directional
        # formatting characters, the candidate would look like:
        #
        #     1. ['rial sign ['sc ﷼
        #
        # But it should look like:
        #
        #     1.  rial sign ['sc'] ﷼
        #
        # Without the embedding, similar problems happen when “comment”
        # is right-to-left but “phrase” is not.
        phrase = itb_util.bidi_embed(phrase)
        # If a candidate is extremely long, it will make the lookup
        # table too wide maybe wider than the available screen space
        # and then you cannot see the whole candidate anyway. So it is
        # better to elide extremely long candidates. Maybe best to
        # elide them in the middle?:
        if len(phrase) > 80:
            phrase = phrase[:40] + '…' + phrase[-40:]
        attrs = IBus.AttrList()
        if len(comment) > 80:
            comment = comment[:40] + '…' + comment[-40:]
        if comment:
            phrase += ' ' + itb_util.bidi_embed(comment)
        color_used = False
        label_spellcheck_string = self._label_spellcheck_string.strip()
        label_userdb_string = self._label_userdb_string.strip()
        label_dictionary_string = self._label_dictionary_string.strip()
        if spell_checking: # spell checking suggestion
            if self._label_spellcheck and label_spellcheck_string:
                phrase += ' ' + label_spellcheck_string
            if self._color_spellcheck:
                attrs.append(IBus.attr_foreground_new(
                    self._color_spellcheck_argb, 0, len(phrase)))
                color_used = True
        elif from_user_db:
            # This was found in the user database.  So it is
            # possible to delete it with a key binding or
            # mouse-click, if the user desires. Mark it
            # differently to show that it is deletable:
            if self._label_userdb and label_userdb_string:
                phrase += ' ' + label_userdb_string
            if self._color_userdb:
                attrs.append(IBus.attr_foreground_new(
                    self._color_userdb_argb, 0, len(phrase)))
                color_used = True
        if dictionary_matches:
            # This is a (possibly accent insensitive) match in a
            # hunspell dictionary or an emoji matched by
            # EmojiMatcher.
            if self._label_dictionary:
                if not (phrase.endswith(' ')
                        or
                        (label_spellcheck_string
                         and phrase.endswith(label_spellcheck_string))
                        or
                        (label_userdb_string
                         and phrase.endswith(label_userdb_string))):
                    phrase += ' '
                if self._label_dictionary_dict:
                    for dictionary in dictionary_matches:
                        if dictionary in self._label_dictionary_dict:
                            phrase += self._label_dictionary_dict[dictionary]
                        else:
                            for key in sorted(self._label_dictionary_dict,
                                              reverse=True):
                                if fnmatch.fnmatchcase(dictionary, key):
                                    phrase += self._label_dictionary_dict[key]
                                    break
                elif label_dictionary_string:
                    phrase += label_dictionary_string
            if self._flag_dictionary:
                if not (phrase.endswith(' ')
                        or
                        (label_spellcheck_string
                         and phrase.endswith(label_spellcheck_string))
                        or
                        (label_userdb_string
                         and phrase.endswith(label_userdb_string))
                        or
                        (label_dictionary_string
                         and phrase.endswith(label_dictionary_string))):
                    phrase += ' '
                for dictionary in dictionary_matches:
                    phrase += self._dictionary_flags.get(dictionary, '')
            if self._color_dictionary and not color_used:
                attrs.append(IBus.attr_foreground_new(
                    self._color_dictionary_argb, 0, len(phrase)))
                color_used = True
        # If a candidate contains newlines, replace them with an arrow
        # indicating the new line. Rendering the real newlines in the
        # lookup table looks terrible. On non-Gnome desktops, all
        # entries in the lookup table always have the same height. So when one
        # entry uses 3 lines in the lookup table, all other
        # entries use 3 lines as well. In Gnome this works somewhat
        # better, only the entry which really uses multiple lines
        # uses extra space in the lookup table. But this still looks
        # terrible. When one uses custom shortcuts to expand to whole
        # paragraphs, this uses far too much space in the lookup
        # table.
        phrase = phrase.replace('\n', '↩')
        if DEBUG_LEVEL > 1:
            # Show frequency information for debugging
            phrase += ' ' + str(user_freq)
            attrs.append(IBus.attr_foreground_new(
                itb_util.color_string_to_argb('HotPink'),
                len(phrase) - len(str(user_freq)),
                len(phrase)))
        text = IBus.Text.new_from_string(phrase)
        i = 0
        while attrs.get(i) is not None:
            attr = attrs.get(i)
            text.append_attribute(attr.get_attr_type(),
                                  attr.get_value(),
                                  attr.get_start_index(),
                                  attr.get_end_index())
            i += 1
        self._lookup_table.append_candidate(text)
        self._lookup_table.set_cursor_visible(False)

    def _update_candidates(self) -> None:
        '''Update the list of candidates and fill the lookup table with the
        candidates
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('self._typed_string=%s', self._typed_string)
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)
        if self.is_empty():
            # Nothing to do when there is no input available.
            # One can accidentally end up here even though the
            # input is empty because this is called by GLib.idle_add().
            # Better make sure that calling this function with
            # empty input does not pointlessly try to find candidates.
            return
        self._candidates = []
        phrase_frequencies: Dict[str, int] = {}
        self.is_lookup_table_enabled_by_min_char_complete = False
        for ime in self._current_imes:
            if self._transliterated_strings[ime]:
                candidates = []
                prefix_length = 0
                prefix = ''
                stripped_transliterated_string = (
                    itb_util.lstrip_token(self._transliterated_strings[ime]))
                if (stripped_transliterated_string
                        and (len(stripped_transliterated_string)
                              >= self._min_char_complete)):
                    self.is_lookup_table_enabled_by_min_char_complete = True
                if (self.is_lookup_table_enabled_by_min_char_complete
                        or self.is_lookup_table_enabled_by_tab):
                    prefix_length = (
                        len(self._transliterated_strings[ime])
                        - len(stripped_transliterated_string))
                    if prefix_length:
                        prefix = (
                            self._transliterated_strings[ime][0:prefix_length])
                    try:
                        candidates = self.database.select_words(
                            stripped_transliterated_string,
                            p_phrase=self._p_phrase,
                            pp_phrase=self._pp_phrase)
                    except Exception as error: # pylint: disable=broad-except
                        LOGGER.exception(
                            'Exception when calling select_words: %s: %s',
                            error.__class__.__name__, error)
                if candidates and prefix:
                    candidates = [(prefix+x[0], x[1]) for x in candidates]
                shortcut_candidates: List[Tuple[str, float]] = []
                try:
                    shortcut_candidates = self.database.select_shortcuts(
                        self._transliterated_strings[ime])
                except Exception as error: # pylint: disable=broad-except
                    LOGGER.exception(
                        'Exception when calling select_shortcuts: %s: %s',
                        error.__class__.__name__, error)
                for cand in candidates + shortcut_candidates:
                    if cand[0] in phrase_frequencies:
                        phrase_frequencies[cand[0]] = max(
                            phrase_frequencies[cand[0]], cand[1])
                    else:
                        phrase_frequencies[cand[0]] = cand[1]
        phrase_candidates = self.database.best_candidates(phrase_frequencies)
        # If the first candidate is exactly the same as the typed string
        # prefer longer candidates which start exactly with the typed
        # string. If the user wants the typed string, he can easily
        # commit the preëdit, there is no need to select a candidate in
        # that case. Offering longer completions instead may give
        # the opportunity to save some key strokes.
        if phrase_candidates:
            typed_string = unicodedata.normalize(
                'NFC', self._transliterated_strings[
                    self.get_current_imes()[0]])
            first_candidate = unicodedata.normalize(
                'NFC', phrase_candidates[0][0])
            if typed_string == first_candidate:
                phrase_frequencies = {}
                first_candidate_user_freq = phrase_candidates[0][1]
                first_candidate_length = len(first_candidate)
                for cand in phrase_candidates:
                    candidate_normalized = unicodedata.normalize(
                        'NFC', cand[0])
                    if (len(candidate_normalized) > first_candidate_length
                        and candidate_normalized.startswith(first_candidate)):
                        phrase_frequencies[cand[0]] = (
                            cand[1] + first_candidate_user_freq)
                    else:
                        phrase_frequencies[cand[0]] = cand[1]
                phrase_candidates = self.database.best_candidates(
                    phrase_frequencies)
        if ((self._emoji_predictions
             and not self.client_capabilities & itb_util.Capabilite.OSK)
            or self._typed_string[0] in self._emoji_trigger_characters
            or self._typed_string[-1] in self._emoji_trigger_characters):
            # If emoji mode is off and the emoji predictions are
            # triggered here because the typed string starts with an
            # emoji trigger character, the emoji matcher might not have been
            # initialized yet.  Make sure it is initialized now:
            if (not self.emoji_matcher
                or
                self.emoji_matcher.get_languages()
                != self._dictionary_names):
                self.emoji_matcher = itb_emoji.EmojiMatcher(
                    languages=self._dictionary_names)
            emoji_scores: Dict[str, Tuple[int, str]] = {}
            emoji_max_score: int = 0
            for ime in self._current_imes:
                if (self._transliterated_strings[ime]
                        and ((len(self._transliterated_strings[ime])
                              >= self._min_char_complete)
                             or self._tab_enable)):
                    emoji_matcher_candidates = self.emoji_matcher.candidates(
                        self._transliterated_strings[ime],
                        trigger_characters=self._emoji_trigger_characters)
                    for cand in emoji_matcher_candidates:
                        emoji_max_score = max(emoji_max_score, cand[2])
                        if (cand[0] not in emoji_scores
                                or cand[2] > emoji_scores[cand[0]][0]):
                            emoji_scores[cand[0]] = (cand[2], cand[1])
            phrase_candidates_emoji_name: List[Tuple[
                str, int, str, bool, bool]] = []
            for cand in phrase_candidates:
                # If this candidate is duplicated in the emoji candidates,
                # don’t use this as a text candidate but increase the score
                # of the emoji candidate:
                emoji = ''
                if cand[0] in emoji_scores:
                    emoji = cand[0]
                elif (cand[0][0] in self._emoji_trigger_characters
                    and cand[0][1:] in emoji_scores):
                    emoji = cand[0][1:]
                if emoji:
                    emoji_scores[emoji] = (emoji_max_score + cand[1],
                                           emoji_scores[emoji][1])
                else:
                    phrase_candidates_emoji_name.append((
                        cand[0], cand[1], self.emoji_matcher.name(cand[0]),
                        cand[1] > 0, cand[1] < 0))
            emoji_candidates = []
            for (key, value) in sorted(
                    emoji_scores.items(),
                    key=lambda x: (
                        - x[1][0],   # score
                        - len(x[0]), # length of emoji string
                        x[1][1]      # name of emoji
                    ))[:20]:
                emoji_candidates.append((key, value[0], value[1]))
            page_size = self._lookup_table.get_page_size()
            phrase_candidates_top = phrase_candidates_emoji_name[:page_size-1]
            phrase_candidates_rest = phrase_candidates_emoji_name[page_size-1:]
            emoji_candidates_top = emoji_candidates[:page_size]
            emoji_candidates_rest = emoji_candidates[page_size:]
            for cand in phrase_candidates_top:
                self._candidates.append(
                    (cand[0], cand[1], cand[2], cand[3], cand[4]))
            for cand in emoji_candidates_top:
                self._candidates.append(
                    (cand[0], cand[1], cand[2], False, False))
            for cand in phrase_candidates_rest:
                self._candidates.append(
                    (cand[0], cand[1], cand[2], cand[3], cand[4]))
            for cand in emoji_candidates_rest:
                self._candidates.append(
                    (cand[0], cand[1], cand[2], False, False))
        else:
            for cand in phrase_candidates:
                self._candidates.append(
                    (cand[0], cand[1], '', cand[1] > 0, cand[1] < 0))
        for cand in self._candidates:
            self._append_candidate_to_lookup_table(
                phrase=cand[0], user_freq=cand[1], comment=cand[2],
                from_user_db=cand[3], spell_checking=cand[4])
        self._candidates_case_mode_orig = self._candidates.copy()
        if self._current_case_mode != 'orig':
            self._case_mode_change(mode=self._current_case_mode)
        return

    def _arrow_down(self) -> bool:
        '''Process Arrow Down Key Event
        Move Lookup Table cursor down'''
        if not self._lookup_table.cursor_visible:
            self._lookup_table.set_cursor_visible(True)
            return True
        if self._lookup_table.cursor_down():
            return True
        return False

    def _arrow_up(self) -> bool:
        '''Process Arrow Up Key Event
        Move Lookup Table cursor up'''
        self._lookup_table.set_cursor_visible(True)
        if self._lookup_table.cursor_up():
            return True
        return False

    def _page_down(self) -> bool:
        '''Process Page Down Key Event
        Move Lookup Table page down'''
        self._lookup_table.set_cursor_visible(True)
        if self._lookup_table.page_down():
            return True
        return False

    def _page_up(self) -> bool:
        '''Process Page Up Key Event
        move Lookup Table page up'''
        self._lookup_table.set_cursor_visible(True)
        if self._lookup_table.page_up():
            return True
        return False

    def _get_lookup_table_current_page(self) -> int:
        '''
        Returns the index of the currently visible page of the lookup table.

        The first page has index 0.
        '''
        page, dummy_pos_in_page = divmod(
            self._lookup_table.get_cursor_pos(),
            self._lookup_table.get_page_size())
        return int(page)

    def _set_lookup_table_cursor_pos_in_current_page(self, index: int) -> bool:
        '''Sets the cursor in the lookup table to index in the current page

        Returns True if successful, False if not.

        :param index: The index in the current page of the lookup table.
                      The topmost candidate has the index 0 and the label “1”.
        '''
        page_size = self._lookup_table.get_page_size()
        if index < 0 or index >= page_size:
            return False
        page = self._get_lookup_table_current_page()
        new_pos = page * page_size + index
        if new_pos >= self._lookup_table.get_number_of_candidates():
            return False
        self._lookup_table.set_cursor_pos(new_pos)
        return True

    def get_string_from_lookup_table_cursor_pos(self) -> str:
        '''
        Get the candidate at the current cursor position in the lookup
        table.
        '''
        if not self._candidates:
            return ''
        index = self._lookup_table.get_cursor_pos()
        if index >= len(self._candidates):
            # the index given is out of range
            return ''
        return unicodedata.normalize('NFC', self._candidates[index][0])

    def get_string_from_lookup_table_current_page(self, index: int) -> str:
        '''
        Get the candidate at “index” in the currently visible
        page of the lookup table. The topmost candidate
        has the index 0 and has the label “1.”.
        '''
        if not self._set_lookup_table_cursor_pos_in_current_page(index):
            return ''
        return self.get_string_from_lookup_table_cursor_pos()

    def remove_candidate_from_user_database(self, index: int) -> bool:
        '''Remove the candidate shown at index in the candidate list
        from the user database.

        Returns True if successful, False if not.

        :param index: The index in the current page of the lookup table.
                      The topmost candidate has the index 0 and the label “1”.
        :return: True if successful, False if not.

        The removal is done independent of the input phrase, all
        rows in the user database for that phrase are deleted.

        It does not matter either whether this is a user defined
        phrase or a phrase which can be found in the hunspell
        dictionaries.  In both cases, it is removed from the user
        database.

        In case of a system phrase, which can be found in the hunspell
        dictionaries, this means that the phrase could still appear in
        the suggestions after removing it from the user database
        because it still can be suggested by the hunspell
        dictionaries. But it becomes less likely because removing a
        system phrase from the user database resets its user frequency
        to 0 again.

        So the user can always try to delete a phrase if he does not
        want the phrase to be suggested wich such a high priority, no
        matter whether it is a system phrase or a user defined phrase.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'Removing candidate with index=%s from user database', index)
        if not self._set_lookup_table_cursor_pos_in_current_page(index):
            return False
        displayed_phrase = self.get_string_from_lookup_table_cursor_pos()
        if not displayed_phrase:
            return False
        index = self._lookup_table.get_cursor_pos()
        if 0 <= index <= len(self._candidates_case_mode_orig):
            case_mode_orig_phrase = self._candidates_case_mode_orig[index][0]
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Removing phrase with original case mode “%s”',
                             case_mode_orig_phrase)
                self.database.remove_phrase(
                    phrase=case_mode_orig_phrase, commit=True)
        for _, case_mode_value in self._case_modes.items():
            # delete all case modes of the displayed candidate:
            phrase = case_mode_value['function'](displayed_phrase)
            # If the candidate to be removed from the user database starts
            # with characters which are stripped from tokens, we probably
            # want to delete the stripped candidate.  I.e. if the
            # candidate is “_somestuff” we should delete “somestuff” from
            # the user database. Especially when triggering an emoji
            # search with the prefix “_” this is the case. For example,
            # when one types “_ca” one could get the flag of Canada “_🇨🇦”
            # or the castle emoji “_🏰” as suggestions from the user
            # database if one has typed these emoji before. But only the
            # emoji came from the database, not the prefix “_”, because it
            # is one of the prefixes stripped from tokens.  Trying to
            # delete the complete candidate from the user database won’t
            # achieve anything, only the stripped token is in the
            # database.
            stripped_phrase = itb_util.lstrip_token(phrase)
            if stripped_phrase:
                if DEBUG_LEVEL > 1:
                    LOGGER.debug('Removing “%s”', stripped_phrase)
                self.database.remove_phrase(phrase=stripped_phrase,
                                            commit=True)
            # Try to remove the whole candidate as well from the database.
            # Probably this won’t do anything, just to make sure that it
            # is really removed even if the prefix also ended up in the
            # database for whatever reason (It could be because the list
            # of prefixes to strip from tokens has changed compared to a
            # an older release of ibus-typing-booster).
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Removing “%s”', phrase)
            self.database.remove_phrase(phrase=phrase, commit=True)
        return True

    def get_cursor_pos(self) -> int:
        '''get lookup table cursor position'''
        return int(self._lookup_table.get_cursor_pos())

    def get_lookup_table(self) -> IBus.LookupTable:
        '''Get lookup table'''
        return self._lookup_table

    def set_lookup_table(self, lookup_table: IBus.LookupTable) -> None:
        '''Set lookup table'''
        self._lookup_table = lookup_table

    def get_p_phrase(self) -> str:
        '''Get previous word'''
        return self._p_phrase

    def get_pp_phrase(self) -> str:
        '''Get word before previous word'''
        return self._pp_phrase

    def get_ppp_phrase(self) -> str:
        '''Get 2nd word before previous word'''
        return self._ppp_phrase

    def push_context(self, phrase: str) -> None:
        '''Pushes a word on the context stack which remembers the last three
        words typed.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'context=“%s” “%s” “%s” push=“%s”',
                self._ppp_phrase, self._pp_phrase, self._p_phrase, phrase)
        self._is_context_from_surrounding_text = False
        self._ppp_phrase = self._pp_phrase
        self._pp_phrase = self._p_phrase
        self._p_phrase = phrase

    def clear_context(self) -> None:
        '''Clears the context stack which remembers the last two words typed
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'context=“%s” “%s” “%s”',
                self._ppp_phrase, self._pp_phrase, self._p_phrase)
        self._ppp_phrase = ''
        self._pp_phrase = ''
        self._p_phrase = ''
        self._new_sentence = False

    def _update_transliterated_strings(self) -> None:
        '''Transliterates the current input (list of msymbols) for all current
        input methods and stores the results in a dictionary.
        '''
        self._transliterated_strings = {}
        if self._typed_compose_sequence:
            self._transliterated_strings_compose_part = (
                self._compose_sequences.preedit_representation(
                    self._typed_compose_sequence))
        for ime in self._current_imes:
            if self._typed_compose_sequence:
                self._transliterated_strings_before_compose[ime] = (
                    self._transliterators[ime].transliterate(
                        self._typed_string[:self._typed_string_cursor],
                        ascii_digits=self._ascii_digits))
                self._transliterated_strings[ime] = (
                    self._transliterated_strings_before_compose[ime]
                    + self._transliterated_strings_compose_part
                    + self._transliterators[ime].transliterate(
                        self._typed_string[self._typed_string_cursor:],
                        ascii_digits=self._ascii_digits))
            else:
                self._transliterated_strings[ime] = (
                    self._transliterators[ime].transliterate(
                        self._typed_string,
                        ascii_digits=self._ascii_digits))
            if ime in ['ko-romaja', 'ko-han2']:
                self._transliterated_strings[ime] = unicodedata.normalize(
                    'NFKD', self._transliterated_strings[ime])
        if DEBUG_LEVEL > 1:
            LOGGER.debug('self._typed_string=%s', self._typed_string)
            LOGGER.debug(
                'self._transliterated_strings=%s',
                self._transliterated_strings)

    def get_current_imes(self) -> List[str]:
        '''Get current list of input methods

        It is important to return a copy, we do not want to change
        the private member variable directly.
        '''
        return self._current_imes[:]

    def set_current_imes(
            self,
            imes: Union[str, List[str], Any],
            update_gsettings: bool = True) -> None:
        '''Set current list of input methods

        :param imes: List of input methods
                     If a single string is used, it should contain
                     the names of the input methods separated by commas.
                     If the string is empty, the default input
                     methods for the current locale are set.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.debug('imes=%s type(imes)=%s', imes, type(imes))
        if isinstance(imes, str):
            imes = itb_util.input_methods_str_to_list(imes)
        if imes == self._current_imes: # nothing to do
            return
        if set(imes) != set(self._current_imes):
            # Input methods have been added or removed from the list
            # of current input methods. Initialize the
            # transliterators. If only the order of the input methods
            # has changed, initialising the transliterators is not
            # necessary (and neither is updating the transliterated
            # strings necessary).
            self._current_imes = imes
            self._init_transliterators()
        else:
            self._current_imes = imes
        self._update_preedit_ime_menu_dicts()
        self._init_or_update_property_menu_preedit_ime(
            self.preedit_ime_menu, current_mode=0)
        if not self.is_empty():
            self._update_ui()
        if update_gsettings:
            self._gsettings.set_value(
                'inputmethod',
                GLib.Variant.new_string(','.join(imes)))

    def set_dictionary_names(
            self,
            dictionary_names: Union[str, List[str], Any],
            update_gsettings: bool = True) -> None:
        '''Set current dictionary names

        :param dictionary_names: List of names of dictionaries to use
                                 If a single string is used, it should contain
                                 the names of the dictionaries separated
                                 by commas.
                                 If the string is empty, the default
                                 dictionaries for the current locale are set.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.debug('dictionary_names=%s type(dictionary_names)=%s',
                     dictionary_names, type(dictionary_names))
        if isinstance(dictionary_names, str):
            dictionary_names = itb_util.dictionaries_str_to_list(
                dictionary_names)
        if dictionary_names == self._dictionary_names: # nothing to do
            return
        self._dictionary_names = dictionary_names
        self.database.hunspell_obj.set_dictionary_names(dictionary_names)
        self._dictionary_flags = itb_util.get_flags(self._dictionary_names)
        self._update_dictionary_menu_dicts()
        self._init_or_update_property_menu_dictionary(
            self.dictionary_menu, current_mode=0)
        if self._emoji_predictions:
            if (not self.emoji_matcher
                    or
                    self.emoji_matcher.get_languages()
                    != dictionary_names):
                self.emoji_matcher = itb_emoji.EmojiMatcher(
                    languages=dictionary_names)
        if not self.is_empty():
            self._update_ui()
        if update_gsettings:
            self._gsettings.set_value(
                'dictionary',
                GLib.Variant.new_string(','.join(dictionary_names)))

    def get_dictionary_names(self) -> List[str]:
        '''Get current list of dictionary names'''
        # It is important to return a copy, we do not want to change
        # the private member variable directly.
        return self._dictionary_names[:]

    def set_autosettings(
            self,
            autosettings: Union[List[Tuple[str, str, str]], Any],
            update_gsettings: bool = True) -> None:
        '''Set the current automatic settings

        :param autosettings: The automatic settings to use
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 0:
            LOGGER.debug('autosettings=%s', autosettings)
        if not isinstance(autosettings, list):
            return
        if autosettings == self._autosettings:
            return
        self._autosettings = autosettings
        if update_gsettings:
            variant_array = GLib.Variant.new_array(GLib.VariantType('as'), [
                    GLib.Variant.new_array(GLib.VariantType('s'), [
                        GLib.Variant.new_string(x) for x in autosetting])
                    for autosetting in autosettings
                ])
            self._gsettings.set_value(
                'autosettings',
                variant_array)

    def get_autosettings(self) -> List[Tuple[str, str, str]]:
        '''Get current autosettings

        Returns the list of settings automatically applied when
        regular expressions match windows
        '''
        # It is important to return a copy, we do not want to change
        # the private member variable directly.
        return self._autosettings.copy()

    def set_keybindings(
            self,
            keybindings: Union[Dict[str, List[str]], Any],
            update_gsettings: bool = True) -> None:
        '''Set current key bindings

        :param keybindings: The key bindings to use
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        new_keybindings = {}
        # Get the default settings:
        new_keybindings = itb_util.variant_to_value(
            self._gsettings.get_default_value('keybindings'))
        # Update the default settings with the possibly changed settings:
        itb_util.dict_update_existing_keys(new_keybindings, keybindings)
        self._keybindings = new_keybindings
        # Update useage of digits in keybindings:
        self._normal_digits_used_in_keybindings = False
        self._keypad_digits_used_in_keybindings = False
        for command in keybindings:
            for keybinding in keybindings[command]:
                if (keybinding
                    in ('0', '1', '2', '3', '4',
                        '5', '6', '7', '8', '9')):
                    self._normal_digits_used_in_keybindings = True
                if (keybinding
                    in ('KP_0', 'KP_1', 'KP_2', 'KP_3', 'KP_4',
                        'KP_5', 'KP_6', 'KP_7', 'KP_8', 'KP_9')):
                    self._keypad_digits_used_in_keybindings = True
        # Update hotkeys:
        self._hotkeys = itb_util.HotKeys(self._keybindings)
        # If there is no key binding to toggle ibus-typing-booster
        # between ”On” and “Off”, ibus-typing-booster has to be
        # “On” always. I.e. the input mode needs to be set
        # to True in that case:
        if not self._keybindings['toggle_input_mode_on_off']:
            self.set_input_mode(True, update_gsettings=True)
        # Some property menus have tooltips which show hints for the
        # key bindings. These may need to be updated if the key
        # bindings have changed.
        #
        # Also the input mode menu may need to be added or removed
        # depending on whether a keybinding for toggling input mode
        # was added or removed.
        #
        # I don’t check whether the key bindings really have changed,
        # just update all the properties anyway.
        #
        # But update them only if the properties have already been
        # initialized. At program start they might still be empty at
        # the time when self.set_keybindings() is called.
        if self._prop_dict:
            if self.input_mode_menu:
                self.input_mode_menu['shortcut_hint'] = (
                    repr(self._keybindings['toggle_input_mode_on_off']))
            if self.emoji_prediction_mode_menu:
                self.emoji_prediction_mode_menu['shortcut_hint'] = (
                    repr(self._keybindings['toggle_emoji_prediction']))
            if self.off_the_record_mode_menu:
                self.off_the_record_mode_menu['shortcut_hint'] = (
                    repr(self._keybindings['toggle_off_the_record']))
            if self.dictionary_menu:
                self._update_dictionary_menu_dicts()
            if self.preedit_ime_menu:
                self._update_preedit_ime_menu_dicts()
            self._init_properties()
        if update_gsettings:
            variant_dict = GLib.VariantDict(GLib.Variant('a{sv}', {}))
            for command in sorted(self._keybindings):
                variant_array = GLib.Variant.new_array(
                    GLib.VariantType('s'),
                    [GLib.Variant.new_string(x)
                     for x in self._keybindings[command]])
                variant_dict.insert_value(command, variant_array)
            self._gsettings.set_value(
                'keybindings',
                variant_dict.end())

    def get_keybindings(self) -> Dict[str, List[str]]:
        '''Get current key bindings

        Python dictionary of key bindings for commands
        '''
        # It is important to return a copy, we do not want to change
        # the private member variable directly.
        return self._keybindings.copy()

    def _update_dictionary_menu_dicts(self) -> None:
        '''
        Update the Python dicts for the highest priority dictionary menu.
        '''
        self.dictionary_properties = {}
        current_dictionaries = self.get_dictionary_names()
        current_dictionaries_max = itb_util.MAXIMUM_NUMBER_OF_DICTIONARIES
        for i in range(0, current_dictionaries_max):
            if i < len(current_dictionaries):
                self.dictionary_properties[
                    'Dictionary.' + str(i)
                ] = {'number': i,
                     'symbol': current_dictionaries[i]
                     + ' ' + itb_util.get_flag(current_dictionaries[i]),
                     'label': current_dictionaries[i]
                     + ' ' + itb_util.get_flag(current_dictionaries[i]),
                     'tooltip': '', # tooltips do not work in sub-properties
                }
            else:
                self.dictionary_properties[
                    'Dictionary.'+str(i)
                ] = {'number': i, 'symbol': '', 'label': '', 'tooltip': ''}
        self.dictionary_menu = {
            'key': 'Dictionary',
            'label': _('Highest priority dictionary'),
            'tooltip': _('Choose highest priority dictionary'),
            'shortcut_hint':
            'Next: ' + repr(self._keybindings['next_dictionary'])
            + '\n'
            'Previous: '+ repr(self._keybindings['previous_dictionary']),
            'sub_properties': self.dictionary_properties}

    def _update_preedit_ime_menu_dicts(self) -> None:
        '''
        Update the dictionary for the preëdit ime menu.
        '''
        self.preedit_ime_properties = {}
        current_imes = self.get_current_imes()
        current_imes_max = itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS
        for i in range(0, current_imes_max):
            if i < len(current_imes):
                self.preedit_ime_properties[
                    'PreeditIme.' + str(i)
                ] = {'number': i,
                     'symbol': current_imes[i],
                     'label': current_imes[i],
                     'tooltip': '', # tooltips do not work in sub-properties
                }
            else:
                self.preedit_ime_properties[
                    'PreeditIme.'+str(i)
                ] = {'number': i, 'symbol': '', 'label': '', 'tooltip': ''}
        self.preedit_ime_menu = {
            'key': 'PreeditIme',
            'label': _('Preedit input method'),
            'tooltip': _('Switch preedit input method'),
            'shortcut_hint':
            'Next: ' + repr(self._keybindings['next_input_method'])
            + '\n'
            'Previous: '+ repr(self._keybindings['previous_input_method']),
            'sub_properties': self.preedit_ime_properties}

    def _init_or_update_property_menu_dictionary(
            self,
            menu: Dict[str, Any],
            current_mode: int = 0) -> None:
        '''
        Initialize or update the ibus property menu for
        the highest priority dictionary.
        '''
        key = menu['key']
        sub_properties = menu['sub_properties']
        for prop in sub_properties:
            if sub_properties[prop]['number'] == int(current_mode):
                symbol = sub_properties[prop]['symbol']
                label = '{label} ({symbol})'.format(
                    label=menu['label'],
                    symbol=symbol)
                tooltip = '{tooltip}\n{shortcut_hint}'.format(
                    tooltip=menu['tooltip'],
                    shortcut_hint=menu['shortcut_hint'])
        visible = len(self.get_dictionary_names()) > 1
        self._init_or_update_sub_properties_dictionary(
            sub_properties, current_mode=current_mode)
        if key not in self._prop_dict: # initialize property
            self._prop_dict[key] = IBus.Property(
                key=key,
                prop_type=IBus.PropType.MENU,
                label=IBus.Text.new_from_string(label),
                icon='',
                symbol=IBus.Text.new_from_string(symbol),
                tooltip=IBus.Text.new_from_string(tooltip),
                sensitive=visible,
                visible=visible,
                state=IBus.PropState.UNCHECKED,
                sub_props=self.dictionary_sub_properties_prop_list)
            self.main_prop_list.append(self._prop_dict[key])
        else:  # update the property
            self._prop_dict[key].set_label(
                IBus.Text.new_from_string(label))
            self._prop_dict[key].set_symbol(
                IBus.Text.new_from_string(symbol))
            self._prop_dict[key].set_tooltip(
                IBus.Text.new_from_string(tooltip))
            self._prop_dict[key].set_sensitive(visible)
            self._prop_dict[key].set_visible(visible)
            self.update_property(self._prop_dict[key]) # important!

    def _init_or_update_property_menu_preedit_ime(
            self,
            menu: Dict[str, Any],
            current_mode: int = 0) -> None:
        '''
        Initialize or update the ibus property menu for
        the preëdit input method.
        '''
        key = menu['key']
        sub_properties = menu['sub_properties']
        for prop in sub_properties:
            if sub_properties[prop]['number'] == int(current_mode):
                symbol = sub_properties[prop]['symbol']
                label = '{label} ({symbol})'.format(
                    label=menu['label'],
                    symbol=symbol)
                tooltip = '{tooltip}\n{shortcut_hint}'.format(
                    tooltip=menu['tooltip'],
                    shortcut_hint=menu['shortcut_hint'])
        visible = len(self.get_current_imes()) > 1
        self._init_or_update_sub_properties_preedit_ime(
            sub_properties, current_mode=current_mode)
        if key not in self._prop_dict: # initialize property
            self._prop_dict[key] = IBus.Property(
                key=key,
                prop_type=IBus.PropType.MENU,
                label=IBus.Text.new_from_string(label),
                icon='',
                symbol=IBus.Text.new_from_string(symbol),
                tooltip=IBus.Text.new_from_string(tooltip),
                sensitive=visible,
                visible=visible,
                state=IBus.PropState.UNCHECKED,
                sub_props=self.preedit_ime_sub_properties_prop_list)
            self.main_prop_list.append(self._prop_dict[key])
        else:  # update the property
            self._prop_dict[key].set_label(
                IBus.Text.new_from_string(label))
            self._prop_dict[key].set_symbol(
                IBus.Text.new_from_string(symbol))
            self._prop_dict[key].set_tooltip(
                IBus.Text.new_from_string(tooltip))
            self._prop_dict[key].set_sensitive(visible)
            self._prop_dict[key].set_visible(visible)
            self.update_property(self._prop_dict[key]) # important!

    def _init_or_update_sub_properties_dictionary(
            self,
            modes: Dict[str, Any],
            current_mode: int = 0) -> None:
        '''
        Initialize or update the sub-properties of the property menu
        for the highest priority dictionary.
        '''
        if not self.dictionary_sub_properties_prop_list:
            update = False
            self.dictionary_sub_properties_prop_list = IBus.PropList()
        else:
            update = True
        number_of_current_dictionaries = len(self.get_dictionary_names())
        for mode in sorted(modes, key=lambda x: (int(modes[x]['number']))):
            visible = modes[mode]['number'] < number_of_current_dictionaries
            if modes[mode]['number'] == int(current_mode):
                state = IBus.PropState.CHECKED
            else:
                state = IBus.PropState.UNCHECKED
            label = modes[mode]['label']
            if 'tooltip' in modes[mode]:
                tooltip = modes[mode]['tooltip']
            else:
                tooltip = ''
            if not update: # initialize property
                self._prop_dict[mode] = IBus.Property(
                    key=mode,
                    prop_type=IBus.PropType.RADIO,
                    label=IBus.Text.new_from_string(label),
                    icon='',
                    tooltip=IBus.Text.new_from_string(tooltip),
                    sensitive=visible,
                    visible=visible,
                    state=state,
                    sub_props=None)
                self.dictionary_sub_properties_prop_list.append(
                    self._prop_dict[mode])
            else: # update property
                self._prop_dict[mode].set_label(
                    IBus.Text.new_from_string(label))
                self._prop_dict[mode].set_tooltip(
                    IBus.Text.new_from_string(tooltip))
                self._prop_dict[mode].set_sensitive(visible)
                self._prop_dict[mode].set_visible(visible)
                self.update_property(self._prop_dict[mode]) # important!

    def _init_or_update_sub_properties_preedit_ime(
            self,
            modes: Dict[str, Any],
            current_mode: int = 0) -> None:
        '''
        Initialize or update the sub-properties of the property menu
        for the preëdit input method.
        '''
        if not self.preedit_ime_sub_properties_prop_list:
            update = False
            self.preedit_ime_sub_properties_prop_list = IBus.PropList()
        else:
            update = True
        number_of_current_imes = len(self.get_current_imes())
        for mode in sorted(modes, key=lambda x: (int(modes[x]['number']))):
            visible = modes[mode]['number'] < number_of_current_imes
            if modes[mode]['number'] == int(current_mode):
                state = IBus.PropState.CHECKED
            else:
                state = IBus.PropState.UNCHECKED
            label = modes[mode]['label']
            if 'tooltip' in modes[mode]:
                tooltip = modes[mode]['tooltip']
            else:
                tooltip = ''
            if not update: # initialize property
                self._prop_dict[mode] = IBus.Property(
                    key=mode,
                    prop_type=IBus.PropType.RADIO,
                    label=IBus.Text.new_from_string(label),
                    icon='',
                    tooltip=IBus.Text.new_from_string(tooltip),
                    sensitive=visible,
                    visible=visible,
                    state=state,
                    sub_props=None)
                self.preedit_ime_sub_properties_prop_list.append(
                    self._prop_dict[mode])
            else: # update property
                self._prop_dict[mode].set_label(
                    IBus.Text.new_from_string(label))
                self._prop_dict[mode].set_tooltip(
                    IBus.Text.new_from_string(tooltip))
                self._prop_dict[mode].set_sensitive(visible)
                self._prop_dict[mode].set_visible(visible)
                self.update_property(self._prop_dict[mode]) # important!

    def _init_or_update_property_menu(
            self,
            menu: Dict[str, Any],
            current_mode: int = 0) -> None:
        '''
        Initialize or update a ibus property menu
        '''
        menu_key = menu['key']
        sub_properties_dict = menu['sub_properties']
        for prop in sub_properties_dict:
            if sub_properties_dict[prop]['number'] == int(current_mode):
                symbol = sub_properties_dict[prop]['symbol']
                label = menu['label']
                tooltip = f'{menu["tooltip"]}\n{menu["shortcut_hint"]}'
        visible = bool(menu_key != 'InputMode'
                       or self._keybindings['toggle_input_mode_on_off'])
        self._init_or_update_sub_properties(
            menu_key, sub_properties_dict, current_mode=current_mode)
        if menu_key not in self._prop_dict: # initialize property
            self._prop_dict[menu_key] = IBus.Property(
                key=menu_key,
                prop_type=IBus.PropType.MENU,
                label=IBus.Text.new_from_string(label),
                icon='',
                symbol=IBus.Text.new_from_string(symbol),
                tooltip=IBus.Text.new_from_string(tooltip),
                sensitive=visible,
                visible=visible,
                state=IBus.PropState.UNCHECKED,
                sub_props=self._sub_props_dict[menu_key])
            self.main_prop_list.append(self._prop_dict[menu_key])
        else: # update the property
            self._prop_dict[menu_key].set_label(
                IBus.Text.new_from_string(label))
            self._prop_dict[menu_key].set_symbol(
                IBus.Text.new_from_string(symbol))
            self._prop_dict[menu_key].set_tooltip(
                IBus.Text.new_from_string(tooltip))
            self._prop_dict[menu_key].set_sensitive(visible)
            self._prop_dict[menu_key].set_visible(visible)
            self.update_property(self._prop_dict[menu_key]) # important!

    def _init_or_update_sub_properties(
            self,
            menu_key: str,
            modes: Dict[str, Any],
            current_mode: int = 0) -> None:
        '''
        Initialize or update the sub-properties of a property menu entry.
        '''
        if menu_key not in self._sub_props_dict:
            update = False
            self._sub_props_dict[menu_key] = IBus.PropList()
        else:
            update = True
        visible = bool(menu_key != 'InputMode'
                       or self._keybindings['toggle_input_mode_on_off'])
        for mode in sorted(modes, key=lambda x: (int(modes[x]['number']))):
            if modes[mode]['number'] == int(current_mode):
                state = IBus.PropState.CHECKED
            else:
                state = IBus.PropState.UNCHECKED
            label = modes[mode]['label']
            if 'tooltip' in modes[mode]:
                tooltip = modes[mode]['tooltip']
            else:
                tooltip = ''
            if not update: # initialize property
                self._prop_dict[mode] = IBus.Property(
                    key=mode,
                    prop_type=IBus.PropType.RADIO,
                    label=IBus.Text.new_from_string(label),
                    icon='',
                    tooltip=IBus.Text.new_from_string(tooltip),
                    sensitive=visible,
                    visible=visible,
                    state=state,
                    sub_props=None)
                self._sub_props_dict[menu_key].append(
                    self._prop_dict[mode])
            else: # update property
                self._prop_dict[mode].set_label(
                    IBus.Text.new_from_string(label))
                self._prop_dict[mode].set_tooltip(
                    IBus.Text.new_from_string(tooltip))
                self._prop_dict[mode].set_sensitive(visible)
                self._prop_dict[mode].set_visible(visible)
                self._prop_dict[mode].set_state(state)
                self.update_property(self._prop_dict[mode]) # important!

    def _init_properties(self) -> None:
        '''
        Initialize the ibus property menus
        '''
        self._prop_dict = {}
        self._sub_props_dict = {}
        self.preedit_ime_sub_properties_prop_list = []
        self.dictionary_sub_properties_prop_list = []
        self.main_prop_list = IBus.PropList()

        if self._keybindings['toggle_input_mode_on_off']:
            self._init_or_update_property_menu(
                self.input_mode_menu,
                self._input_mode)

        self._init_or_update_property_menu(
            self.emoji_prediction_mode_menu,
            self._emoji_predictions)

        self._init_or_update_property_menu(
            self.off_the_record_mode_menu,
            self._off_the_record)

        self._init_or_update_property_menu_dictionary(
            self.dictionary_menu, current_mode=0)

        self._init_or_update_property_menu_preedit_ime(
            self.preedit_ime_menu, current_mode=0)

        self._setup_property = IBus.Property(
            key='setup',
            label=IBus.Text.new_from_string(_('Setup')),
            icon='gtk-preferences',
            tooltip=IBus.Text.new_from_string(
                _('Preferences for ibus-typing-booster')),
            sensitive=True,
            visible=True)
        self.main_prop_list.append(self._setup_property)
        self.register_properties(self.main_prop_list)

    def do_property_activate( # pylint: disable=arguments-differ
            self,
            ibus_property: str,
            prop_state: IBus.PropState = IBus.PropState.UNCHECKED) -> None:
        '''
        Handle clicks on properties
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'ibus_property=%s prop_state=%s', ibus_property, prop_state)
        if ibus_property == "setup":
            self._start_setup()
            return
        if prop_state != IBus.PropState.CHECKED:
            # If the mouse just hovered over a menu button and
            # no sub-menu entry was clicked, there is nothing to do:
            return
        if ibus_property.startswith(self.dictionary_menu['key']+'.'):
            number = self.dictionary_properties[ibus_property]['number']
            if number != 0:
                # If number 0 has been clicked, there is nothing to
                # do, the first one is already the highest priority
                # dictionary
                names = self.get_dictionary_names()
                self.set_dictionary_names(
                    [names[number]] + names[number+1:] + names[:number],
                    update_gsettings=True)
            return
        if ibus_property.startswith(self.preedit_ime_menu['key']+'.'):
            number = self.preedit_ime_properties[ibus_property]['number']
            if number != 0:
                # If number 0 has been clicked, there is nothing to
                # do, the first one is already the preedit input
                # method
                imes = self.get_current_imes()
                self.set_current_imes(
                    [imes[number]] + imes[number+1:] + imes[:number],
                    update_gsettings=self._remember_last_used_preedit_ime)
            return
        if ibus_property.startswith(
                self.input_mode_menu['key'] + '.'):
            self.set_input_mode(
                bool(self.input_mode_properties
                     [ibus_property]['number']))
        if ibus_property.startswith(
                self.emoji_prediction_mode_menu['key'] + '.'):
            self.set_emoji_prediction_mode(
                bool(self.emoji_prediction_mode_properties
                     [ibus_property]['number']))
            return
        if ibus_property.startswith(
                self.off_the_record_mode_menu['key'] + '.'):
            self.set_off_the_record_mode(
                bool(self.off_the_record_mode_properties
                     [ibus_property]['number']))
            return

    def _start_setup(self) -> None:
        '''Start the setup tool if it is not running yet'''
        if self._setup_pid != 0:
            pid, dummy_state = os.waitpid(self._setup_pid, os.P_NOWAIT)
            if pid != self._setup_pid:
                # If the last setup tool started from here is still
                # running the pid returned by the above os.waitpid()
                # is 0. In that case just return, don’t start a
                # second setup tool.
                return
            self._setup_pid = 0
        setup_cmd = os.path.join(
            str(os.getenv('IBUS_TYPING_BOOSTER_LIB_LOCATION')),
            'ibus-setup-typing-booster')
        if DEBUG_LEVEL > 0:
            LOGGER.debug('Starting setup tool: "%s"\n', setup_cmd)
        self._setup_pid = os.spawnl(
            os.P_NOWAIT,
            setup_cmd,
            'ibus-setup-typing-booster')

    def _clear_input_and_update_ui(self) -> None:
        '''Clear the preëdit and close the lookup table
        '''
        self._clear_input()
        self._update_ui_empty_input()

    def do_destroy(self) -> None: # pylint: disable=arguments-differ
        '''Called when this input engine is destroyed
        '''
        if DEBUG_LEVEL > 0:
            LOGGER.debug('entering function')
        self._clear_input_and_update_ui()
        self.do_focus_out()
        super().destroy()

    def _add_color_to_attrs_for_spellcheck(
            self, attrs: IBus.AttrList, text: str) -> None:
        '''May color the preedit if spellchecking fails

        :param attrs: The attribute list of the preedit
        :param text: The current text in the preedit which
                     may need color added
        '''
        if (self._typed_compose_sequence
            or not self._color_preedit_spellcheck):
            return
        stripped_text = itb_util.strip_token(text)
        prefix_length = text.find(stripped_text)
        if (len(stripped_text) >= 4
            and not
            self.database.hunspell_obj.spellcheck(stripped_text)):
            attrs.append(IBus.attr_foreground_new(
                self._color_preedit_spellcheck_argb,
                prefix_length,
                prefix_length + len(stripped_text)))

    def _add_color_to_attrs_for_compose(self, attrs: IBus.AttrList) -> None:
        '''May color the compose part of the preedit

        :param attrs: The attribute list of the preedit
        '''
        if (not self._typed_compose_sequence
            or not self._color_compose_preview):
            return
        ime = self.get_current_imes()[0]
        length_before_compose = len(
            self._transliterated_strings_before_compose[ime])
        length_compose = len(
            self._transliterated_strings_compose_part)
        attrs.append(IBus.attr_foreground_new(
            self._color_compose_preview_argb,
            length_before_compose,
            length_before_compose + length_compose))

    def _update_preedit(self) -> None:
        '''Update Preedit String in UI'''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('entering function')
        # get_caret() should also use NFC!
        _str = unicodedata.normalize(
            'NFC', self._transliterated_strings[
                self.get_current_imes()[0]])
        _str = self._case_modes[self._current_case_mode]['function'](_str)
        if DEBUG_LEVEL > 2:
            LOGGER.debug('_str=“%s”', _str)
        if self._hide_input:
            _str = '*' * len(_str)
        if _str == '':
            if not self._current_preedit_text:
                if DEBUG_LEVEL > 1:
                    LOGGER.debug('Avoid clearing already empty preedit.')
                return
            super().update_preedit_text_with_mode(
                IBus.Text.new_from_string(''), 0, False,
                IBus.PreeditFocusMode.COMMIT)
            self._current_preedit_text = ''
            return
        self._current_preedit_text = _str
        attrs = IBus.AttrList()
        if (not self._preedit_style_only_when_lookup
            or self.is_lookup_table_enabled_by_tab
            or self.is_lookup_table_enabled_by_min_char_complete):
            attrs.append(IBus.attr_underline_new(
                self._preedit_underline, 0, len(_str)))
            self._add_color_to_attrs_for_compose(attrs)
            self._add_color_to_attrs_for_spellcheck(attrs, _str)
        else:
            # Preedit style “only when lookup is enabled” is
            # requested and lookup is *not* enabled.  Therefore,
            # make the preedit appear as if it were completely
            # normal text:
            attrs.append(IBus.attr_underline_new(
                IBus.AttrUnderline.NONE, 0, len(_str)))
        text = IBus.Text.new_from_string(_str)
        i = 0
        while attrs.get(i) is not None:
            attr = attrs.get(i)
            text.append_attribute(attr.get_attr_type(),
                                  attr.get_value(),
                                  attr.get_start_index(),
                                  attr.get_end_index())
            i += 1
        super().update_preedit_text_with_mode(
            text, self.get_caret(), True, IBus.PreeditFocusMode.COMMIT)

    def _update_aux(self) -> None:
        '''Update auxiliary text'''
        aux_string = ''
        if self._show_number_of_candidates:
            aux_string = (
                f'({self.get_lookup_table().get_cursor_pos() + 1} / '
                f'{self.get_lookup_table().get_number_of_candidates()}) ')
        if self._show_status_info_in_auxiliary_text:
            if self._emoji_predictions:
                aux_string += (
                    f'{MODE_ON_SYMBOL}{EMOJI_PREDICTION_MODE_SYMBOL} ')
            else:
                aux_string += (
                    f'{MODE_OFF_SYMBOL}{EMOJI_PREDICTION_MODE_SYMBOL} ')
            if self._off_the_record:
                aux_string += (
                    f'{MODE_ON_SYMBOL}{OFF_THE_RECORD_MODE_SYMBOL} ')
            else:
                aux_string += (
                    f'{MODE_OFF_SYMBOL}{OFF_THE_RECORD_MODE_SYMBOL} ')
            names = self.get_dictionary_names()
            if names:
                aux_string += f'{names[0]} {itb_util.get_flag(names[0])}'
            preedit_ime = self.get_current_imes()[0]
            if preedit_ime != 'NoIME':
                aux_string += f' {preedit_ime} '
        # Colours do not work at the moment in the auxiliary text!
        # Needs fix in ibus.
        attrs = IBus.AttrList()
        attrs.append(IBus.attr_foreground_new(
            itb_util.color_string_to_argb('SlateGray'),
            0,
            len(aux_string)))
        if DEBUG_LEVEL > 0 and not self._unit_test:
            client = f'🪟{self._im_client}'
            aux_string += client
            attrs.append(IBus.attr_foreground_new(
                itb_util.color_string_to_argb('Purple'),
                len(aux_string)-len(client),
                len(aux_string)))
        if DEBUG_LEVEL > 2:
            context_indicator = '🔴'
            if self._is_context_from_surrounding_text:
                context_indicator = '🟢'
            len_aux_string_orig = len(aux_string)
            aux_string += (f'{context_indicator}'
                           f'{self.get_ppp_phrase()} '
                           f'{self.get_pp_phrase()} '
                           f'{self.get_p_phrase()}')
            attrs.append(IBus.attr_foreground_new(
                itb_util.color_string_to_argb('DeepPink'),
                len_aux_string_orig,
                len(aux_string)))
        text = IBus.Text.new_from_string(aux_string)
        i = 0
        while attrs.get(i) is not None:
            attr = attrs.get(i)
            text.append_attribute(attr.get_attr_type(),
                                  attr.get_value(),
                                  attr.get_start_index(),
                                  attr.get_end_index())
            i += 1
        visible = True
        if (self.get_lookup_table().get_number_of_candidates() == 0
            or self._hide_input
            or (self._tab_enable
                and not self.is_lookup_table_enabled_by_tab)
            or not aux_string):
            visible = False
        super().update_auxiliary_text(text, visible)
        self._current_auxiliary_text = text

    def _update_lookup_table(self) -> None:
        '''Update the lookup table

        Show it if it is not empty and not disabled, otherwise hide it.
        '''
        self._lookup_table_hidden = False
        # Also make sure to hide lookup table if there are
        # no candidates to display. On f17, this makes no
        # difference but gnome-shell in f18 will display
        # an empty suggestion popup if the number of candidates
        # is zero!
        if ((self.is_empty()
             and self._min_char_complete != 0
             and not self._typed_compose_sequence)
            or self._hide_input
            or self.get_lookup_table().get_number_of_candidates() == 0
            or (self._tab_enable and not self.is_lookup_table_enabled_by_tab)):
            self.hide_lookup_table()
            self._lookup_table_hidden = True
            self._update_preedit()
            return
        if (not self._inline_completion
            or (self.client_capabilities & itb_util.Capabilite.OSK)
            or self._typed_compose_sequence
            or self._lookup_table_shows_related_candidates
            or self.get_lookup_table().get_cursor_pos() != 0):
            # Show standard lookup table:
            self.update_lookup_table(self.get_lookup_table(), True)
            self._lookup_table_hidden = False
            self._update_preedit()
            return
        # There is at least one candidate the lookup table cursor
        # points to the first candidate, the lookup table is enabled
        # and inline completion is on.
        typed_string = unicodedata.normalize(
            'NFC', self._transliterated_strings[
                self.get_current_imes()[0]])
        first_candidate = unicodedata.normalize(
            'NFC', self._candidates[0][0])
        if (not first_candidate.startswith(typed_string)
            or first_candidate == typed_string):
            # The first candidate is not a direct completion of the
            # typed string. Trying to show that inline gets very
            # confusing.  Don’t do that, show standard lookup table:
            if (self._inline_completion < 2
                or self.get_lookup_table().cursor_visible):
                # Show standard lookup table as a fallback:
                self.update_lookup_table(self.get_lookup_table(), True)
                self._lookup_table_hidden = False
            else:
                # self._inline_completion == 2 means do not fall back
                # to the standard lookup table:
                self.hide_lookup_table()
                self._lookup_table_hidden = True
                text = IBus.Text.new_from_string('')
                super().update_auxiliary_text(text, False)
            self._update_preedit()
            return
        # Show only the first candidate, inline in the preëdit, hide
        # the lookup table and the auxiliary text:
        completion = first_candidate[len(typed_string):]
        self.hide_lookup_table()
        self._lookup_table_hidden = True
        text = IBus.Text.new_from_string('')
        super().update_auxiliary_text(text, False)
        text = IBus.Text.new_from_string(typed_string + completion)
        self._current_preedit_text = typed_string + completion
        attrs = IBus.AttrList()
        attrs.append(IBus.attr_underline_new(
            self._preedit_underline, 0, len(typed_string)))
        if self.get_lookup_table().cursor_visible:
            attrs.append(IBus.attr_underline_new(
                self._preedit_underline,
                len(typed_string), len(typed_string + completion)))
        else:
            self._add_color_to_attrs_for_spellcheck(attrs, typed_string)
            if self._color_inline_completion:
                attrs.append(IBus.attr_foreground_new(
                    self._color_inline_completion_argb,
                    len(typed_string), len(typed_string + completion)))
            attrs.append(IBus.attr_underline_new(
                IBus.AttrUnderline.NONE,
                len(typed_string), len(typed_string + completion)))
        i = 0
        while attrs.get(i) is not None:
            attr = attrs.get(i)
            text.append_attribute(attr.get_attr_type(),
                                  attr.get_value(),
                                  attr.get_start_index(),
                                  attr.get_end_index())
            i += 1
        if (self.get_lookup_table().cursor_visible
            and not self._is_candidate_auto_selected):
            caret = len(first_candidate)
        else:
            caret = self.get_caret()
        super().update_preedit_text_with_mode(
            text, caret, True, IBus.PreeditFocusMode.COMMIT)
        return

    def _update_lookup_table_and_aux(self) -> None:
        '''Update the lookup table and the auxiliary text'''
        self._update_aux()
        # auto select best candidate if the option
        # self._auto_select_candidate is on:
        self._is_candidate_auto_selected = False
        if (self._lookup_table_is_invalid
            and self.get_lookup_table().get_number_of_candidates()
            and not self._lookup_table.cursor_visible):
            if self._auto_select_candidate == 2:
                # auto select: Yes, always
                self._lookup_table.set_cursor_visible(True)
                self._is_candidate_auto_selected = True
            elif self._auto_select_candidate == 1:
                # auto select: Yes, but only when extremely likely
                first_candidate = ''
                user_freq = 0
                typed_string = ''
                if self._candidates:
                    first_candidate = self._candidates[0][0]
                    user_freq = self._candidates[0][1]
                typed_string = unicodedata.normalize(
                    'NFC',
                    self._transliterated_strings[self.get_current_imes()[0]])
                spellcheck_single_dictionary = (
                    self.database.hunspell_obj.spellcheck_single_dictionary(
                        (self._p_phrase, self._pp_phrase, first_candidate)))
                if (spellcheck_single_dictionary
                    and typed_string
                    and typed_string != first_candidate
                    and itb_util.remove_accents(first_candidate)
                    == typed_string
                    and user_freq > 0.2):
                    self._lookup_table.set_cursor_visible(True)
                    self._is_candidate_auto_selected = True
        self._update_lookup_table()
        self._lookup_table_is_invalid = False

    def _update_candidates_and_lookup_table_and_aux(self) -> None:
        '''Update the candidates, the lookup table and the auxiliary text'''
        self._update_candidates()
        self._update_lookup_table_and_aux()
        if DEBUG_LEVEL < 1:
            return
        if not self.client_capabilities & itb_util.Capabilite.SURROUNDING_TEXT:
            return
        surrounding_text = self.get_surrounding_text()
        if not surrounding_text:
            LOGGER.debug('Surrounding text object is None. '
                         'Should never happen.')
            return
        LOGGER.debug('surrounding_text = [%r, %s, %s]',
                     surrounding_text[0].get_text(),
                     surrounding_text[1], surrounding_text[2])

    def _update_ui_empty_input(self) -> None:
        '''Update the UI when the input is empty.

        Even when the input is empty, it is possible that a preedit
        and a lookup table are shown because it is possible that
        self._min_char_complete == 0 and then sometimes a completion
        is tried even when the input is empty.

        '''
        LOGGER.debug('entering function')
        self._update_preedit()
        self.get_lookup_table().clear()
        self.get_lookup_table().set_cursor_visible(False)
        self.hide_lookup_table()
        self._lookup_table_hidden = True
        self.is_lookup_table_enabled_by_tab = False
        self._lookup_table_shows_related_candidates = False
        self._current_auxiliary_text = IBus.Text.new_from_string('')
        super().update_auxiliary_text(
            self._current_auxiliary_text, False)

    def _update_ui_empty_input_try_completion(self) -> None:
        '''
        Update the UI when the input is empty and try a completion.
        '''
        LOGGER.debug('entering function')
        if not self.is_empty():
            self._update_preedit()
            return
        if (self._min_char_complete != 0
            or self._hide_input
            or (self._tab_enable and not self.is_lookup_table_enabled_by_tab)):
            # If the lookup table would be hidden anyway, there is no
            # point in updating the candidates, save some time by making
            # sure the lookup table and the auxiliary text are really
            # empty and hidden and return immediately:
            self._update_ui_empty_input()
            return
        self.is_lookup_table_enabled_by_tab = False
        self._lookup_table_shows_related_candidates = False
        phrase_candidates = self.database.select_words(
            '', p_phrase=self.get_p_phrase(), pp_phrase=self.get_pp_phrase())
        if DEBUG_LEVEL > 2:
            LOGGER.debug('phrase_candidates=%s', phrase_candidates)
        if not phrase_candidates:
            self._update_ui_empty_input()
            return
        self._lookup_table_is_invalid = True
        # Don’t show the lookup table if it is invalid anway
        self.get_lookup_table().clear()
        self.get_lookup_table().set_cursor_visible(False)
        self.hide_lookup_table()
        self._lookup_table_hidden = True
        if self._label_busy and self._label_busy_string.strip():
            # Show a label in the auxiliary text to indicate that the
            # lookup table is being updated (by default an hourglass
            # with moving sand):
            super().update_auxiliary_text(
                IBus.Text.new_from_string(
                    self._label_busy_string.strip()), True)
        else:
            super().update_auxiliary_text(
                IBus.Text.new_from_string(''), False)
        self._candidates = [(cand[0], cand[1], '', True, False)
                            for cand in phrase_candidates]
        for cand in self._candidates:
            self._append_candidate_to_lookup_table(
                phrase=cand[0], user_freq=cand[1], comment=cand[2],
                from_user_db=cand[3], spell_checking=cand[4])
        self._candidates_case_mode_orig = self._candidates.copy()
        if self._current_case_mode != 'orig':
            self._case_mode_change(mode=self._current_case_mode)
        if self._unit_test:
            self._update_lookup_table_and_aux()
        else:
            GLib.idle_add(self._update_lookup_table_and_aux)

    def _update_ui(self) -> None:
        '''Update User Interface'''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('entering function')
        if self.is_empty():
            # Hide lookup table again if preëdit became empty and
            # suggestions are only enabled by Tab key:
            self.is_lookup_table_enabled_by_tab = False
        if (self.is_empty()
            or self._hide_input
            or (self._tab_enable and not self.is_lookup_table_enabled_by_tab)):
            # If the lookup table would be hidden anyway, there is no
            # point in updating the candidates, save some time by making
            # sure the lookup table and the auxiliary text are really
            # empty and hidden and return immediately:
            self.get_lookup_table().clear()
            self.get_lookup_table().set_cursor_visible(False)
            self.hide_lookup_table()
            self._lookup_table_hidden = True
            self._current_auxiliary_text = IBus.Text.new_from_string('')
            super().update_auxiliary_text(
                self._current_auxiliary_text, False)
            self._update_preedit()
            return
        self._lookup_table_shows_related_candidates = False
        if self._lookup_table_is_invalid:
            self._update_preedit()
            return
        self._lookup_table_is_invalid = True
        # Don’t show the lookup table if it is invalid anway
        self.get_lookup_table().clear()
        self.get_lookup_table().set_cursor_visible(False)
        self.hide_lookup_table()
        self._lookup_table_hidden = True
        if self._label_busy and self._label_busy_string.strip():
            # Show a label in the auxiliary text to indicate that the
            # lookup table is being updated (by default an hourglass
            # with moving sand):
            super().update_auxiliary_text(
                IBus.Text.new_from_string(
                    self._label_busy_string.strip()), True)
        else:
            super().update_auxiliary_text(
                IBus.Text.new_from_string(''), False)
        if self._unit_test:
            self._update_candidates_and_lookup_table_and_aux()
        else:
            GLib.idle_add(self._update_candidates_and_lookup_table_and_aux)

    def _lookup_related_candidates(self) -> None:
        '''Lookup related (similar) emoji or related words (synonyms,
        hyponyms, hypernyms).
        '''
        # We might end up here by typing a shortcut key like
        # AltGr+F12.  This should also work when suggestions are only
        # enabled by Tab and are currently disabled.  Typing such a
        # shortcut key explicitly requests looking up related
        # candidates, so it should have the same effect as Tab and
        # enable the lookup table:
        if self._tab_enable and not self.is_lookup_table_enabled_by_tab:
            self.is_lookup_table_enabled_by_tab = True
        phrase = ''
        if (self.get_lookup_table().get_number_of_candidates()
            and  self.get_lookup_table().cursor_visible):
            phrase = self.get_string_from_lookup_table_cursor_pos()
        else:
            phrase = self._transliterated_strings[
                self.get_current_imes()[0]]
        if not phrase:
            return
        # Hide lookup table and show an hourglass with moving sand in
        # the auxiliary text to indicate that the lookup table is
        # being updated. Don’t clear the lookup table here because we
        # might want to show it quickly again if nothing related is
        # found:
        if self.get_lookup_table().get_number_of_candidates():
            self.hide_lookup_table()
            self._lookup_table_hidden = True
        if self._label_busy and self._label_busy_string.strip():
            # Show a label in the auxiliary text to indicate that the
            # lookup table is being updated (by default an hourglass
            # with moving sand):
            super().update_auxiliary_text(
                IBus.Text.new_from_string(
                    self._label_busy_string.strip()), True)
        else:
            super().update_auxiliary_text(
                IBus.Text.new_from_string(''), False)
        related_candidates = []
        # Try to find similar emoji even if emoji predictions are
        # turned off.  Even when they are turned off, an emoji might
        # show up in the candidate list because it was found in the
        # user database. But when emoji predictions are turned off,
        # it is possible that they never been turned on in this session
        # and then the emoji matcher has not been initialized. Or,
        # the languages have been changed while emoji matching was off.
        # So make sure that the emoji matcher is available for the
        # correct list of languages before searching for similar
        # emoji:
        if (not self.emoji_matcher
            or
            self.emoji_matcher.get_languages()
            != self._dictionary_names):
            self.emoji_matcher = itb_emoji.EmojiMatcher(
                languages=self._dictionary_names)
        if DEBUG_LEVEL > 0:
            related_candidates = self.emoji_matcher.similar(
                phrase)
        else:
            related_candidates = self.emoji_matcher.similar(
                phrase, show_keywords=False)
        if not IMPORT_ITB_NLTK_SUCCESSFUL:
            LOGGER.info('nltk is not available')
        else:
            LOGGER.info('Getting related words from nltk for: “%s”', phrase)
            try:
                for synonym in itb_nltk.synonyms(phrase, keep_original=False):
                    related_candidates.append((synonym, '[synonym]', 0))
                for hypernym in itb_nltk.hypernyms(phrase, keep_original=False):
                    related_candidates.append((hypernym, '[hypernym]', 0))
                for hyponym in itb_nltk.hyponyms(phrase, keep_original=False):
                    related_candidates.append((hyponym, '[hyponym]', 0))
            except (LookupError,) as error:
                LOGGER.exception(
                    'Exception when trying to use nltk: %s: %s',
                     error.__class__.__name__, error)
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'related_candidates of “%s” = %s\n',
                phrase, related_candidates)
        if not related_candidates:
            # Nothing related found, show the original lookup table
            # and original auxiliary text again:
            if self._current_auxiliary_text:
                super().update_auxiliary_text(
                    self._current_auxiliary_text, True)
            else:
                super().update_auxiliary_text(
                    IBus.Text.new_from_string(''), False)
            if self.get_lookup_table().get_number_of_candidates():
                self.update_lookup_table(self.get_lookup_table(), True)
                self._lookup_table_hidden = False
            return
        self._candidates = []
        self.get_lookup_table().clear()
        self.get_lookup_table().set_cursor_visible(False)
        for cand in related_candidates:
            self._candidates.append((cand[0], cand[2], cand[1], False, False))
            self._append_candidate_to_lookup_table(
                phrase=cand[0], user_freq=cand[2], comment=cand[1])
        self._lookup_table_shows_related_candidates = True
        self._update_lookup_table_and_aux()

    def _case_mode_change(
            self,
            mode: str = 'next') -> bool:
        '''Change the case of the current candidates and the preedit

        Change the case of all the candidates in the current list of
        candidates. Then create a new lookup table and fill it
        with the changed candidates to make the changes visible. But
        keep the cursor position and cursor visibility status of the
        old lookup table.

        Available modes:

            'next', 'previous', 'capitalize', 'title', 'upper', 'lower'

        :return: True if something was done, False if not.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('⎆')
        if mode not in (
                'next',
                'previous',
                'orig',
                'capitalize',
                'title',
                'upper',
                'lower'):
            return False
        if (self.is_empty()
            or not self._candidates
            or not self.get_lookup_table().get_number_of_candidates()):
            return False
        if mode in ('next', 'previous'):
            self._current_case_mode = self._case_modes[
                self._current_case_mode][mode]
        else:
            self._current_case_mode = mode
        new_candidates = []
        for cand in self._candidates_case_mode_orig:
            new_candidates.append(
                (self._case_modes[self._current_case_mode]['function'](
                    cand[0]),
                 cand[1], cand[2], cand[3], cand[4]))
        self._candidates = new_candidates
        cursor_visible = self.get_lookup_table().cursor_visible
        cursor_pos = self.get_lookup_table().get_cursor_pos()
        self.get_lookup_table().clear()
        for cand in self._candidates:
            self._append_candidate_to_lookup_table(
                phrase=cand[0], user_freq=cand[1], comment=cand[2],
                from_user_db=cand[3], spell_checking=cand[4])
        self.get_lookup_table().set_cursor_pos(cursor_pos)
        self.get_lookup_table().set_cursor_visible(cursor_visible)
        return True

    def _has_transliteration(self, msymbol_list: List[str]) -> bool:
        '''Check whether the current input (list of msymbols) has a
        (non-trivial, i.e. not transliterating to itself)
        transliteration in any of the current input methods.
        '''
        for ime in self.get_current_imes():
            if self._transliterators[ime].transliterate(
                    msymbol_list) != ''.join(msymbol_list):
                if DEBUG_LEVEL > 1:
                    LOGGER.debug(
                        '_has_transliteration(%s) == True\n', msymbol_list)
                return True
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '_has_transliteration(%s) == False\n', msymbol_list)
        return False

    def _remove_candidate(self, index: int) -> bool:
        '''
        Removes the candidate at “index” in the lookup table from the
        user database.

        :return: True if a candidate could be removed, False if not
        :param index: The index of the candidate to remove in the lookup table
        '''
        if not self.get_lookup_table().get_number_of_candidates():
            return False
        candidate_number = (
            self._get_lookup_table_current_page() * self._page_size + index)
        if not (candidate_number
            < self._lookup_table.get_number_of_candidates()
            and 0 <= index < self._page_size):
            return False
        if self.remove_candidate_from_user_database(index):
            self._update_ui()
            return True
        return False

    def _commit_candidate(
            self,
            index: int,
            extra_text: str = '') -> bool:
        '''
        Commits the candidate at “index” in the lookup table

        :return: True if a candidate could be committed, False if not.
        :param index: The index of the candidate to commit in the lookup table
        :param extra_text: Additional text append to the commit,
                           usually a space
        '''
        if self.client_capabilities & itb_util.Capabilite.OSK:
            LOGGER.info(
                'OSK is visible: do not commit candidate by index %s', index)
            return False
        if (not self.get_lookup_table().get_number_of_candidates()
            or self._lookup_table_hidden):
            return False
        candidate_number = (
            self._get_lookup_table_current_page() * self._page_size + index)
        if not (candidate_number
            < self._lookup_table.get_number_of_candidates()
            and 0 <= index < self._page_size):
            return False
        phrase = self.get_string_from_lookup_table_current_page(index)
        if not phrase:
            return False
        if self._lookup_table_shows_compose_completions:
            self._lookup_table_shows_compose_completions = False
            self._candidates = []
            self.get_lookup_table().clear()
            self.get_lookup_table().set_cursor_visible(False)
            self._update_lookup_table_and_aux()
            self._typed_compose_sequence = []
            self._update_transliterated_strings()
            self._update_preedit()
            if self.get_input_mode():
                self._insert_string_at_cursor(list(phrase))
                self._update_ui()
                return True
            super().commit_text(
                IBus.Text.new_from_string(phrase))
            self._commit_happened_after_focus_in = True
            return True
        if self.is_empty():
            self._commit_string(phrase + extra_text, input_phrase=phrase)
        else:
            # _commit_string() will calculate input_phrase:
            self._commit_string(phrase + extra_text)
        self._clear_input()
        if extra_text == ' ':
            self._update_ui_empty_input_try_completion()
        else:
            self._update_ui_empty_input()
        return True

    def _commit_string(
            self,
            commit_phrase: str,
            input_phrase: str = '',
            push_context: bool = True,
            fix_sentence_end: bool = True) -> None:
        '''Commits a string

        :param commit_phrase: The string to commit
        :param input_phrase: What the use typed to get this string committed
                             (Might be shorter than commit_phrase if a
                             completion was selected)
        :param push_context: Whether to push commit_phrase on the context
                             stack. Doesn’t matter if surrounding text works
                             well and the context is always fetched from
                             surrounding text. But if the fallback of
                             remembering the context is used, this matters.
                             The context should only be pushed if the
                             cursor will end up to the right of commit_phrase.
        :param fix_sentence_end: Whether to try fixing whitespace before
                                 sentence end characters like “.!?”.
                                 Better set this to False when calling
                                 this function several times before
                                 there was a chance that surrounding text
                                 was updated (surrounding text is usually
                                 only updated when a new key event is
                                 processed).

        May also update the context and the user database of learned
        input.

        May remove whitespace before the committed string if
        the committed string ended a sentence.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('commit_phrase=“%s” input_phrase=“%s”',
                         commit_phrase, input_phrase)
        # If the suggestions are only enabled by Tab key, i.e. the
        # lookup table is not shown until Tab has been typed, hide
        # the lookup table again after each commit. That means
        # that after each commit, when typing continues the
        # lookup table is first hidden again and one has to type
        # Tab again to show it.
        self.is_lookup_table_enabled_by_tab = False
        # Same for the case when the lookup table was enabled by
        # the minimum numbers to complete, reset this here to
        # make sure that the preëdit styling for the next letter
        # typed will be correct.
        self.is_lookup_table_enabled_by_min_char_complete = False
        if not input_phrase:
            input_phrase = self._transliterated_strings[
                self.get_current_imes()[0]]
        # commit always in NFC:
        commit_phrase = unicodedata.normalize('NFC', commit_phrase)
        if not commit_phrase.isspace():
            # If the commit space contains only white space
            # leave self._new_sentence as it is!
            self._new_sentence = False
            if itb_util.text_ends_a_sentence(commit_phrase):
                self._new_sentence = True
        if fix_sentence_end:
            commit_phrase = (
                self._commit_string_fix_sentence_end(commit_phrase)
                + commit_phrase)
        if (not self._avoid_forward_key_event
            and re.compile('^gtk3-im:(firefox|thunderbird)').search(self._im_client)):
            # Workaround for Gmail editor in firefox and for thunderbird, see
            # https://github.com/mike-fabian/ibus-typing-booster/commit/35a22dab25be8cb9d09d048ca111f661d6b73909
            #
            # This workaround helps only for '^gtk3-im:', *not* for '^gnome-shell:'.
            for commit_line in commit_phrase.splitlines(keepends=True):
                if not commit_line.endswith('\n'):
                    super().commit_text(
                        IBus.Text.new_from_string(commit_line))
                    continue
                super().commit_text(
                    IBus.Text.new_from_string(commit_line[:-1]))
                self.forward_key_event(
                    IBus.KEY_Return,
                    self._keyvals_to_keycodes.ibus_keycode(IBus.KEY_Return),
                    0)
                # The sleep is needed because this is racy, without the
                # sleep it is likely that all the commits come first
                # followed by all the forwarded Return keys:
                time.sleep(self._ibus_event_sleep_seconds)
        else:
            super().commit_text(
                IBus.Text.new_from_string(commit_phrase))
        self._commit_happened_after_focus_in = True
        if (self._off_the_record
            or self._record_mode == 3
            or self._hide_input
            or self._input_hints & itb_util.InputHints.PRIVATE):
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Privacy: NOT recording and pushing context.')
            return
        if not commit_phrase or not input_phrase:
            return
        stripped_commit_phrase = itb_util.strip_token(commit_phrase)
        if DEBUG_LEVEL > 1:
            LOGGER.debug('input_phrase=%r commit_phrase=%r '
                         'p_phrase=%r pp_phrase=%r ppp_phrase=%r '
                         'record_mode=%d '
                         'spellcheck=%r previously recorded=%d',
                         input_phrase, commit_phrase,
                         self.get_p_phrase(), self.get_pp_phrase(),
                         self.get_ppp_phrase(), self._record_mode,
                         self.database.hunspell_obj.spellcheck(commit_phrase),
                         self.database.phrase_exists(commit_phrase))
        if (self._record_mode == 1
            and not self.database.phrase_exists(commit_phrase)
            and not self.database.hunspell_obj.spellcheck(commit_phrase)):
            if DEBUG_LEVEL > 1:
                LOGGER.debug('self._record_mode=%d: Not recording: %r',
                             self._record_mode, commit_phrase)
            return
        if (self._record_mode == 2
            and not self.database.hunspell_obj.spellcheck(commit_phrase)):
            if DEBUG_LEVEL > 1:
                LOGGER.debug('self._record_mode=%d: Not recording: %r',
                             self._record_mode, commit_phrase)
            return
        if DEBUG_LEVEL > 1:
            LOGGER.debug('recording and pushing context.')
        self.database.check_phrase_and_update_frequency(
            input_phrase=input_phrase,
            phrase=commit_phrase,
            p_phrase=self.get_p_phrase(),
            pp_phrase=self.get_pp_phrase())
        if (stripped_commit_phrase
            and self.get_p_phrase()
            and self.get_pp_phrase()
            and self.get_ppp_phrase()):
            # Commit the current commit phrase and the previous
            # phrase as a single unit as well for better
            # completions. For example, if the current commit
            # phrase is “to” and the total context was “I am
            # going”, then also commit “going to” with the context
            # “I am”:
            if (self._record_mode == 1
                and not self.database.phrase_exists(self.get_p_phrase())
                and not
                self.database.hunspell_obj.spellcheck(self.get_p_phrase())):
                if DEBUG_LEVEL > 1:
                    LOGGER.debug(
                        'self._record_mode=%d: Not recording multi: %r',
                        self._record_mode,
                        self.get_p_phrase() + ' ' + stripped_commit_phrase)
                return
            if (self._record_mode == 2
                and not
                self.database.hunspell_obj.spellcheck(self.get_p_phrase())):
                if DEBUG_LEVEL > 1:
                    LOGGER.debug(
                        'self._record_mode=%d: Not recording multi: %r',
                        self._record_mode,
                        self.get_p_phrase() + ' ' + stripped_commit_phrase)
                return
            if DEBUG_LEVEL > 1:
                LOGGER.debug(
                    'Recording multi: %r',
                    self.get_p_phrase() + ' ' + stripped_commit_phrase)
            self.database.check_phrase_and_update_frequency(
                input_phrase=
                self.get_p_phrase() + ' ' + stripped_commit_phrase,
                phrase=self.get_p_phrase() + ' ' + stripped_commit_phrase,
                p_phrase=self.get_pp_phrase(),
                pp_phrase=self.get_ppp_phrase())
        # push context after recording in the database is finished:
        if push_context:
            self.push_context(stripped_commit_phrase)

    def _commit_string_fix_sentence_end(self, commit_phrase: str) -> str:
        '''Remove trailing white space before sentence end characters

        :param commit_phrase: The text which is going to be committed.
                              (Not committed yet!)

        If a single character ending a sentence is committed (possibly
        followed by whitespace) remove trailing white space before the
        committed string. For example if commit_phrase is “!”, and the
        context before is “word ”, make the result “word!”.  And if
        the commit_phrase is “! ” and the context before is “word ”
        make the result “word! ”.

        '''
        if (not self.client_capabilities & itb_util.Capabilite.SURROUNDING_TEXT
            or
            self._input_purpose in [itb_util.InputPurpose.TERMINAL.value]):
            return ''
        language_code = '*'
        used_french_spacing_dictionaries = {
            'fr_FR', 'fr_MC', 'fr_BE', 'fr_LU', 'fr_CH', 'fr_CA'
        }.intersection(self._dictionary_names)
        if used_french_spacing_dictionaries:
            if self._dictionary_names[0] in used_french_spacing_dictionaries:
                language_code =  self._dictionary_names[0]
            else:
                matched_french_spacing_dictionaries = (
                    used_french_spacing_dictionaries.intersection(
                        self.database.hunspell_obj.spellcheck_single_dictionary(
                        (self._p_phrase, self._pp_phrase, self._ppp_phrase))))
                if matched_french_spacing_dictionaries:
                    language_code = list(matched_french_spacing_dictionaries)[0]
        if DEBUG_LEVEL > 1:
            LOGGER.debug('language_code=%r', language_code)
        chars_dict = itb_util.FIX_WHITESPACE_CHARACTERS.get(
            language_code, itb_util.FIX_WHITESPACE_CHARACTERS['*'])
        for chars, new_whitespace in chars_dict.items():
            pattern_sentence_end = re.compile(
                r'^[' + re.escape(chars) + r']+[\s]*$')
            if pattern_sentence_end.search(commit_phrase):
                surrounding_text = self.get_surrounding_text()
                text = surrounding_text[0].get_text()
                cursor_pos = surrounding_text[1]
                anchor_pos = surrounding_text[2]
                if DEBUG_LEVEL > 1:
                    LOGGER.debug(
                        'Checking for whitespace before commit_phrase %r: '
                        'surrounding_text = [%r, %s, %s]',
                        commit_phrase, text, cursor_pos, anchor_pos)
                # The commit_phrase is *not* yet in the surrounding text,
                # it will show up there only when the next key event is
                # processed:
                pattern = re.compile(r'(?P<white_space>[\s]+)$')
                if re.compile(r'^QIBusInputContext:(kate|kwrite)').search(
                        self._im_client):
                    # For kate and kwrite (but not for other qt5
                    # applications like 'lineedits' from the qt5
                    # examples), the commit phrase is already found in
                    # the surrounding text here even though it is
                    # still in preedit and not committed yet. So it needs
                    # to be added to the regexp. But after the match,
                    # when deleting the surrounding text, only the part
                    # of the regexp which matched the whitespace needs to be
                    # deleted. Weird behaviour, but it seems to work like
                    # that when kate or kwrite are used.
                    regexp = (r'(?P<white_space>[\s]+)'
                              + re.escape(commit_phrase)
                              + r'$')
                    LOGGER.debug(
                        'Special hack for kate and kwrite, use regexp=%r',
                        regexp)
                    pattern = re.compile(regexp)
                match = pattern.search(text[:cursor_pos])
                if match:
                    nchars = len(match.group('white_space'))
                    self.delete_surrounding_text(-nchars, nchars)
                    if DEBUG_LEVEL > 1:
                        surrounding_text = self.get_surrounding_text()
                        text = surrounding_text[0].get_text()
                        cursor_pos = surrounding_text[1]
                        anchor_pos = surrounding_text[2]
                        LOGGER.debug(
                            'Removed whitespace before commit_phrase %r: '
                            'surrounding_text = [%r, %s, %s] '
                            'Replace with %r',
                            commit_phrase,
                            text, cursor_pos, anchor_pos, new_whitespace)
                    return new_whitespace
        return ''

    def _maybe_reopen_preedit(
            self, key: itb_util.KeyEvent) -> bool:
        '''BackSpace, Delete or arrow left or right has been typed.

        If the end of a word has been reached again and if it is
        possible to get that word back into preëdit, do that and
        return True.

        If no end of a word has been reached or it is impossible to
        get the word back into preëdit, return False.

        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('KeyEvent object: %s', key)
            LOGGER.debug('self._arrow_keys_reopen_preedit=%s',
                         self._arrow_keys_reopen_preedit)
        if not self._arrow_keys_reopen_preedit:
            if DEBUG_LEVEL > 1:
                LOGGER.debug('self._arrow_keys_reopen_preedit not set. '
                             'Do not reopen preedit.')
            return False
        if not self.is_empty():
            if DEBUG_LEVEL > 1:
                LOGGER.debug('There is input already, no need to reopen.')
            return False
        if self._prev_key is not None and self._prev_key.val != key.val:
            if DEBUG_LEVEL > 1:
                LOGGER.debug(
                    'Previous key not set or not equal to the just released '
                    'key. Better do not try to reopen the preedit.')
            return False
        if (key.val not in (IBus.KEY_Left, IBus.KEY_KP_Left,
                            IBus.KEY_Right, IBus.KEY_KP_Right,
                            IBus.KEY_BackSpace,
                            IBus.KEY_Delete, IBus.KEY_KP_Delete)):
            if DEBUG_LEVEL > 1:
                LOGGER.debug(
                    'Release key was not in list of keys allowed to '
                    'reopen a preedit. Do not try to reopen the preedit.')
            return False
        if (key.shift
            or key.control
            or key.mod1
            or key.mod3
            or key.mod4
            or key.mod5
            or key.button1
            or key.button2
            or key.button3
            or key.button4
            or key.button5
            or key.super
            or key.hyper
            or key.meta):
            # “Control+Left” usually positions the cursor one word to
            # the left in most programs.  I.e. after Control+Left the
            # cursor usually ends up at the left side of a word.
            # Therefore, one cannot use the same code for reopening
            # the preëdit as for just “Left”. There are similar
            # problems with “Alt+Left”, “Shift+Left”.
            #
            # “Left”, “Right”, “Backspace”, “Delete” also have similar
            # problems together with “Control”, “Alt”, or “Shift” in
            # many programs.  For example “Shift+Left” marks (selects)
            # a region in gedit.
            #
            # Maybe better don’t try to reopen the preëdit at all if
            # any modifier key is on.
            #
            # *Except* for CapsLock and NumLock. CapsLock and NumLock
            # cause no problems at all for reopening the preëdit, so
            # we don’t want to check for key.modifier which would
            # include key.lock (CapsLock) and key.mod2 (NumLock) but
            # check for the modifiers which cause problems
            # individually.
            if DEBUG_LEVEL > 1:
                LOGGER.debug(
                    'Not reopening the preedit because a modifier is set.')
            return False
        if (not self.client_capabilities & itb_util.Capabilite.SURROUNDING_TEXT
            or self._input_purpose in [itb_util.InputPurpose.TERMINAL.value]):
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Surrounding text is not supported. '
                             'No way to repopen preedit.')
            return False
        if not self._commit_happened_after_focus_in:
            # Before the first commit or cursor movement, the
            # surrounding text is probably from the previously
            # focused window (bug!), don’t use it.
            if DEBUG_LEVEL > 1:
                LOGGER.debug('No commit happend yet since focus_in(). '
                             'The surrounding_text is probably wrong. '
                             'Do not try to reopen the preedit.')
            return False
        if not self._surrounding_text_old:
            LOGGER.debug(
                'Old surrounding text object is None. Should never happen.')
            return False
        text_old = self._surrounding_text_old[0].get_text()
        cursor_pos_old = self._surrounding_text_old[1]
        anchor_pos_old = self._surrounding_text_old[2]
        if DEBUG_LEVEL > 1:
            LOGGER.debug('Old surrounding_text = [%r, %s, %s]',
                         text_old, cursor_pos_old, anchor_pos_old)
        if not text_old:
            LOGGER.debug(
                'Old surrounding text is empty. Cannot reopen preedit.')
            return False
        if cursor_pos_old != anchor_pos_old:
            LOGGER.debug('cursor_pos_old=%s anchor_pos_old=%s differ.',
                         cursor_pos_old, anchor_pos_old)
            LOGGER.debug('Cannot reopen preedit.')
            return False
        self._set_surrounding_text_event.wait(timeout=0.1)
        if not self._set_surrounding_text_event.is_set():
            LOGGER.debug(
                'Surrounding text has not been set since last key event. '
                'Something is wrong with the timing. Do not try to reopen '
                'the preedit.')
            return False
        surrounding_text = self.get_surrounding_text()
        if not surrounding_text:
            LOGGER.debug(
                'New surrounding text object is None. Should never happen.')
            return False
        text = surrounding_text[0].get_text()
        cursor_pos = surrounding_text[1]
        anchor_pos = surrounding_text[2]
        if DEBUG_LEVEL > 1:
            LOGGER.debug('New surrounding_text = [%r, %s, %s]',
                         text, cursor_pos, anchor_pos)
        if not text:
            LOGGER.debug(
                'New surrounding text is empty. Cannot reopen preedit.')
            return False
        if cursor_pos != anchor_pos:
            LOGGER.debug('cursor_pos=%s anchor_pos=%s differ.',
                         cursor_pos, anchor_pos)
            LOGGER.debug('Cannot reopen preedit.')
            return False
        if key.val in (IBus.KEY_BackSpace, IBus.KEY_Left, IBus.KEY_KP_Left):
            if cursor_pos != cursor_pos_old - 1:
                LOGGER.debug('Cursor has not moved one column left, '
                             'cannot reopen preedit.')
                return False
            pattern = re.compile(r'^($|[\s]+.*)')
            match = pattern.match(text[cursor_pos:])
            if not match:
                if DEBUG_LEVEL > 1:
                    LOGGER.debug(
                        'No whitespace or end of line or buffer '
                        'to the right of cursor.')
                return False
            pattern = re.compile(r'(^|.*[\s]+)(?P<token>[\S]+)$')
            match = pattern.match(text[:cursor_pos])
            if not match:
                if DEBUG_LEVEL > 1:
                    LOGGER.debug('Could not match token left of cursor.')
                return False
            token = match.group('token')
            # Delete the token, get new context and put it into preedit again:
            self.delete_surrounding_text(-len(token), len(token))
            # https://github.com/mike-fabian/ibus-typing-booster/issues/474#issuecomment-1872148410
            # In very rare cases, like in the editor of https://meta.stackexchange.com/
            # the delete_surrounding_text() does not seem to remove the text
            # from the editor until something is committed or the preedit is
            # set to an empty string:
            super().update_preedit_text_with_mode(
                IBus.Text.new_from_string(''), 0, True,
                IBus.PreeditFocusMode.COMMIT)
            self._current_preedit_text = ''
            self.get_context()
            self._insert_string_at_cursor(list(token))
            self._update_ui()
            return True
        if key.val in (IBus.KEY_Delete, IBus.KEY_KP_Delete,
                       IBus.KEY_Right, IBus.KEY_KP_Right):
            if key.val in (IBus.KEY_Right, IBus.KEY_KP_Right):
                if cursor_pos <= cursor_pos_old:
                    # Movement to the right might be more than one
                    # column, for example when Right is pressed and
                    # while “hello” is in preedit and the
                    # preedit-cursor is behind the “o”, then the old
                    # surrounding text cursor should be before the “h”
                    # and the new surrounding text cursor should one
                    # after the “h” (plus 1 column if it wasn’t
                    # already at the end of the buffer).
                    LOGGER.debug(
                        'Cursor has not moved right, cannot reopen preedit.')
                    return False
            if key.val in (IBus.KEY_Delete, IBus.KEY_KP_Delete):
                if cursor_pos != cursor_pos_old:
                    LOGGER.debug('Unexpected cursor movemend on Delete key, '
                                 'cannot reopen preedit.')
            pattern = re.compile(r'(^|.*[\s]+)$')
            match = pattern.match(text[:cursor_pos])
            if not match:
                if DEBUG_LEVEL > 1:
                    LOGGER.debug(
                        'No whitespace or beginning of line or buffer '
                        'to the left of cursor.')
                return False
            pattern = re.compile(r'^(?P<token>[\S]+)($|[\s]+.*)')
            match = pattern.match(text[cursor_pos:])
            if not match:
                if DEBUG_LEVEL > 1:
                    LOGGER.debug('Could not match token right of cursor.')
                return False
            token = match.group('token')
            # Delete the token, get new context and put it into preedit again:
            self.delete_surrounding_text(0, len(token))
            # https://github.com/mike-fabian/ibus-typing-booster/issues/474#issuecomment-1872148410
            # In very rare cases, like in the editor of https://meta.stackexchange.com/
            # the delete_surrounding_text() does not seem to remove the text
            # from the editor until something is committed or the preedit is
            # set to an empty string:
            super().update_preedit_text_with_mode(
                IBus.Text.new_from_string(''), 0, True,
                IBus.PreeditFocusMode.COMMIT)
            self.get_context()
            self._insert_string_at_cursor(list(token))
            self._typed_string_cursor = 0
            self._update_ui()
            return True
        return False

    def get_context(self) -> None:
        '''Try to get the context from the application using the “surrounding
        text” feature, if possible. If this works, it is much better
        than just using the last two words which were
        committed. Because the cursor position could have changed
        since the last two words were committed, one might have moved
        the cursor with the mouse or the arrow keys.  Unfortunately
        surrounding text is not supported by many applications.
        Basically it only seems to work reasonably well in Gnome
        applications.

        '''
        self._is_context_from_surrounding_text = False
        if (not self.client_capabilities & itb_util.Capabilite.SURROUNDING_TEXT
            or self._input_purpose in [itb_util.InputPurpose.TERMINAL.value]):
            # If getting the surrounding text is not supported, leave
            # the context as it is, i.e. rely on remembering what was
            # typed last.
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Surrounding text not supported.')
            return
        surrounding_text = self.get_surrounding_text()
        if not surrounding_text:
            LOGGER.debug(
                'Surrounding text object is None. Should never happen.')
            return
        text = surrounding_text[0].get_text()
        cursor_pos = surrounding_text[1]
        anchor_pos = surrounding_text[2]
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'Getting context: surrounding_text = '
                '[text = “%r”, cursor_pos = %s, anchor_pos = %s]',
                text, cursor_pos, anchor_pos)
        if not self._commit_happened_after_focus_in:
            # Before the first commit or cursor movement, the
            # surrounding text is probably from the previously
            # focused window (bug!), don’t use it.
            if DEBUG_LEVEL > 1:
                LOGGER.debug(
                    'Skipping context from surrounding_text, no commit yet.')
            return
        tokens = ([
            itb_util.strip_token(token)
            for token in itb_util.tokenize(text[:cursor_pos])])[-3:]
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'Found from surrounding text: tokens=%s', repr(tokens))
        self._p_phrase = ''
        self._pp_phrase = ''
        self._ppp_phrase = ''
        if tokens:
            self._p_phrase = tokens[-1]
        if len(tokens) > 1:
            self._pp_phrase = tokens[-2]
        if len(tokens) > 2:
            self._ppp_phrase = tokens[-3]
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'Updated context from surrounding text=“%s” “%s” “%s”',
                self._ppp_phrase, self._pp_phrase, self._p_phrase)
        self._is_context_from_surrounding_text = True

    def set_add_space_on_commit(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether a space is added when a candidate is committed by 1-9
        or F1-F9 or by mouse click.

        :param mode: Whether to add a space when committing by label
                     or mouse click.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._add_space_on_commit:
            return
        self._add_space_on_commit = mode
        if update_gsettings:
            self._gsettings.set_value(
                'addspaceoncommit',
                GLib.Variant.new_boolean(mode))

    def toggle_add_space_on_commit(
            self, update_gsettings: bool = True) -> None:
        '''Toggles whether a space is added when a candidate is committed by
        1-9 or F1-F9 or by mouse click.

        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        self.set_add_space_on_commit(
            not self._add_space_on_commit, update_gsettings)

    def get_add_space_on_commit(self) -> bool:
        '''Returns the current value of the flag whether to add a space when a
        candidate is committed by 1-9 or F1-F9 or by mouse click.
        '''
        return self._add_space_on_commit

    def set_inline_completion(
            self,
            mode: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether the best completion is first shown inline in the
        preëdit instead of using a combobox to show a candidate list.

        :param mode: Whether to show completions inline
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._inline_completion:
            return
        self._inline_completion = mode
        if update_gsettings:
            self._gsettings.set_value(
                'inlinecompletion',
                GLib.Variant.new_int32(mode))

    def get_inline_completion(self) -> int:
        '''Returns the current value of the flag whether to show a completion
        first inline in the preëdit instead of using a combobox to show a
        candidate list.
        '''
        return self._inline_completion

    def set_record_mode(
            self,
            mode: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether the value of record mode

        :param mode: Specifies how much to record
                     0: Everything
                     1: Correctly spelled or previously recorded words
                     2: Correctly spelled words
                     3: Nothing
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._record_mode:
            return
        self._record_mode = mode
        if update_gsettings:
            self._gsettings.set_value(
                'recordmode',
                GLib.Variant.new_int32(mode))

    def get_record_mode(self) -> int:
        '''Returns the current value of the record mode'''
        return self._record_mode

    def set_auto_capitalize(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to capitalize automatically after punctuation

        :param mode: Whether to automatically capitalize after punctuation.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._auto_capitalize:
            return
        self._auto_capitalize = mode
        if update_gsettings:
            self._gsettings.set_value(
                'autocapitalize',
                GLib.Variant.new_boolean(mode))

    def toggle_auto_capitalize(self, update_gsettings: bool = True) -> None:
        '''Toggles whether to capitalize automatically after punctuation

        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        self.set_auto_capitalize(
            not self._auto_capitalize, update_gsettings)

    def get_auto_capitalize(self) -> bool:
        '''Returns the current value of the flag whether to automatically
        capitalize after punctuation
        '''
        return self._auto_capitalize

    def set_avoid_forward_key_event(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to avoid forward_key_event() or not

        :param mode: Whether to avoid forward_key_event() or not
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._avoid_forward_key_event:
            return
        self._avoid_forward_key_event = mode
        if update_gsettings:
            self._gsettings.set_value(
                'avoidforwardkeyevent',
                GLib.Variant.new_boolean(mode))

    def toggle_avoid_forward_key_event(
            self, update_gsettings: bool = True) -> None:
        '''Toggles whether to avoid forward_key_event() or not

        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        self.set_avoid_forward_key_event(
            not self._avoid_forward_key_event, update_gsettings)

    def get_avoid_forward_key_event(self) -> bool:
        '''Returns whether forward_key_event() is avoided or not'''
        return self._avoid_forward_key_event

    def set_arrow_keys_reopen_preedit(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether the arrow keys are allowed to reopen a preëdit

        :param mode: Whether arrow keys can reopen a preëdit
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._arrow_keys_reopen_preedit:
            return
        self._arrow_keys_reopen_preedit = mode
        if update_gsettings:
            self._gsettings.set_value(
                'arrowkeysreopenpreedit',
                GLib.Variant.new_boolean(mode))

    def toggle_arrow_keys_reopen_preedit(
            self, update_gsettings: bool = True) -> None:
        '''Toggles whether arrow keys are allowed to reopen a preëdit

        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        self.set_arrow_keys_reopen_preedit(
            not self._arrow_keys_reopen_preedit, update_gsettings)

    def get_arrow_keys_reopen_preedit(self) -> bool:
        '''Returns the current value of the flag whether to
        allow arrow keys to reopen the preëdit
        '''
        return self._arrow_keys_reopen_preedit

    def _commit_current_input(self) -> None:
        '''Commits the current state:

        - If nothing is selected in the lookup table, commit the preedit
        - If something is manually selected in the compose lookup table,
          insert it in the preedit, update the preedit and then commit it.
        - If something is selected in the regular (not compose) lookup
          table, commit the selection.
        '''
        if (self._typed_compose_sequence
            and self._lookup_table_shows_compose_completions
            and self.get_lookup_table().cursor_visible):
            # something is manually selected in the compose lookup table
            self._lookup_table_shows_compose_completions = False
            compose_result = self.get_string_from_lookup_table_cursor_pos()
            self._candidates = []
            self.get_lookup_table().clear()
            self.get_lookup_table().set_cursor_visible(False)
            self._update_lookup_table_and_aux()
            self._typed_compose_sequence = []
            self._insert_string_at_cursor(list(compose_result))
            self._update_transliterated_strings()
        preedit_ime = self._current_imes[0]
        input_phrase = self._transliterated_strings[preedit_ime]
        input_phrase = self._case_modes[
            self._current_case_mode]['function'](input_phrase)
        if (self.get_lookup_table().get_number_of_candidates()
            and self.get_lookup_table().cursor_visible):
            # something is selected in the lookup table, commit
            # the selected phrase
            commit_string = self.get_string_from_lookup_table_cursor_pos()
        else:
            # nothing is selected in the lookup table, commit the
            # input_phrase
            commit_string = input_phrase
        if not commit_string:
            # This should not happen, we returned already above when
            # self.is_empty(), if we get here there should
            # have been something in the preëdit or the lookup table:
            if DEBUG_LEVEL > 0:
                LOGGER.error('commit string unexpectedly empty.')
            return
        # Remember whether a candidate is selected and where the
        # caret is now because after self._commit_string() this
        # information is gone:
        candidate_was_selected = False
        if self.get_lookup_table().cursor_visible:
            candidate_was_selected = True
        caret_was = self.get_caret()
        self._commit_string(commit_string, input_phrase=input_phrase)
        self._clear_input_and_update_ui()
        if not candidate_was_selected:
            # cursor needs to be corrected leftwards:
            for dummy_char in commit_string[caret_was:]:
                self._forward_generated_key_event(IBus.KEY_Left)

    def set_input_mode(
            self, mode: bool, update_gsettings: bool = True) ->  None:
        '''Sets the input mode

        :param mode: Whether to switch ibus-typing-booster on or off
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('(%s)', mode)
        if mode == self._input_mode:
            return
        self._input_mode = mode
        if not self._input_mode:
            self._hide_input = False
        if self._prop_dict and self.input_mode_menu:
            self._init_or_update_property_menu(
                self.input_mode_menu, mode)
        if update_gsettings:
            self._gsettings.set_value(
                'inputmode',
                GLib.Variant.new_boolean(mode))
        if self.is_empty() and not self._typed_compose_sequence:
            return
        # Toggling input mode off should not throw away the current input
        # but commit it:
        # https://github.com/mike-fabian/ibus-typing-booster/issues/236
        self._commit_current_input()

    def toggle_input_mode(self, update_gsettings: bool = True) -> None:
        '''Toggles whether ibus-typing-booster is on or off
        '''
        self.set_input_mode(not self._input_mode, update_gsettings)

    def get_input_mode(self) -> bool:
        '''Returns the current value of the input mode'''
        return self._input_mode

    def set_emoji_prediction_mode(
            self, mode: bool, update_gsettings: bool = True) -> None:
        '''Sets the emoji prediction mode

        :param mode: Whether to switch emoji prediction on or off
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._emoji_predictions:
            return
        self._emoji_predictions = mode
        self._init_or_update_property_menu(
            self.emoji_prediction_mode_menu, mode)
        if (self._emoji_predictions
            and (not self.emoji_matcher
                 or
                 self.emoji_matcher.get_languages()
                 != self._dictionary_names)):
            self.emoji_matcher = itb_emoji.EmojiMatcher(
                languages=self._dictionary_names)
        self._update_ui()
        if update_gsettings:
            self._gsettings.set_value(
                'emojipredictions',
                GLib.Variant.new_boolean(mode))

    def toggle_emoji_prediction_mode(
            self, update_gsettings: bool = True) -> None:
        '''Toggles whether emoji predictions are shown or not

        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        self.set_emoji_prediction_mode(
            not self._emoji_predictions, update_gsettings)

    def get_emoji_prediction_mode(self) -> bool:
        '''Returns the current value of the emoji prediction mode'''
        return self._emoji_predictions

    def set_off_the_record_mode(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Off the record” mode

        :param mode: Whether to prevent saving input to the
                     user database or not
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._off_the_record:
            return
        self._off_the_record = mode
        self._init_or_update_property_menu(
            self.off_the_record_mode_menu, mode)
        self._update_ui() # because of the indicator in the auxiliary text
        if update_gsettings:
            self._gsettings.set_value(
                'offtherecord',
                GLib.Variant.new_boolean(mode))

    def toggle_off_the_record_mode(
            self, update_gsettings: bool = True) -> None:
        '''Toggles whether input is saved to the user database or not

        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        self.set_off_the_record_mode(
            not self._off_the_record, update_gsettings)

    def get_off_the_record_mode(self) -> bool:
        '''Returns the current value of the “off the record” mode'''
        return self._off_the_record

    def set_emoji_trigger_characters(
            self,
            emoji_trigger_characters: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the emoji trigger characters

        :param emoji_trigger_characters: The characters which trigger an
                                         emoji and Unicode symbol lookup
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)',
                emoji_trigger_characters, update_gsettings)
        if emoji_trigger_characters == self._emoji_trigger_characters:
            return
        self._emoji_trigger_characters = emoji_trigger_characters
        if update_gsettings:
            self._gsettings.set_value(
                'emojitriggercharacters',
                GLib.Variant.new_string(emoji_trigger_characters))

    def get_emoji_trigger_characters(self) -> str:
        '''Returns the current emoji trigger characters'''
        return self._emoji_trigger_characters

    def set_auto_commit_characters(
            self,
            auto_commit_characters: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the auto commit characters

        :param auto_commit_characters: The characters which trigger a commit
                                       with an extra space
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)',
                auto_commit_characters, update_gsettings)
        if auto_commit_characters == self._auto_commit_characters:
            return
        self._auto_commit_characters = auto_commit_characters
        if update_gsettings:
            self._gsettings.set_value(
                'autocommitcharacters',
                GLib.Variant.new_string(auto_commit_characters))

    def get_auto_commit_characters(self) -> str:
        '''Returns the current auto commit characters'''
        return self._auto_commit_characters

    def set_color_preedit_spellcheck(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether spellchecking is done on the contents of the preedit

        :param mode: Whether to do spellchecking on the contents of the preedit
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._color_preedit_spellcheck:
            return
        self._color_preedit_spellcheck = mode
        if update_gsettings:
            self._gsettings.set_value(
                'colorpreeditspellcheck',
                GLib.Variant.new_boolean(mode))

    def get_color_preedit_spellcheck(self) -> bool:
        '''Returns the current value of the “color preedit_spellcheck” mode'''
        return self._color_preedit_spellcheck

    def set_color_preedit_spellcheck_string(
            self,
            color_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the color for for preedit spellchecking

        :param color_string: The color for preedit spellchecking
                            It is a string in one of the following formats:
                            - Standard name from the X11 rgb.txt
                            - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                         or ”#rrrrggggbbbb”
                            - RGB color: “rgb(r,g,b)”
                            - RGBA color: “rgba(r,g,b,a)”
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', color_string, update_gsettings)
        if color_string == self._color_preedit_spellcheck_string:
            return
        self._color_preedit_spellcheck_string = color_string
        self._color_preedit_spellcheck_argb = itb_util.color_string_to_argb(
            self._color_preedit_spellcheck_string)
        if update_gsettings:
            self._gsettings.set_value(
                'colorpreeditspellcheckstring',
                GLib.Variant.new_string(color_string))

    def get_color_preedit_spellcheck_string(self) -> str:
        '''Returns the current value of the “color preedit spellcheck” string
        '''
        return self._color_preedit_spellcheck_string

    def set_color_inline_completion(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use color for inline completion

        :param mode: Whether to use color for inline completion
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._color_inline_completion:
            return
        self._color_inline_completion = mode
        if update_gsettings:
            self._gsettings.set_value(
                'colorinlinecompletion',
                GLib.Variant.new_boolean(mode))

    def get_color_inline_completion(self) -> bool:
        '''Returns the current value of the “color inline completion” mode'''
        return self._color_inline_completion

    def set_color_inline_completion_string(
            self,
            color_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the color for inline completion

        :param color_string: The color for inline completion
                            It is a string in one of the following formats:
                            - Standard name from the X11 rgb.txt
                            - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                         or ”#rrrrggggbbbb”
                            - RGB color: “rgb(r,g,b)”
                            - RGBA color: “rgba(r,g,b,a)”
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', color_string, update_gsettings)
        if color_string == self._color_inline_completion_string:
            return
        self._color_inline_completion_string = color_string
        self._color_inline_completion_argb = itb_util.color_string_to_argb(
            self._color_inline_completion_string)
        if update_gsettings:
            self._gsettings.set_value(
                'colorinlinecompletionstring',
                GLib.Variant.new_string(color_string))

    def get_color_inline_completion_string(self) -> str:
        '''Returns the current value of the “color inline completion” string'''
        return self._color_inline_completion_string

    def set_color_compose_preview(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use color for the compose preview

        :param mode: Whether to use color for the compose preview
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._color_compose_preview:
            return
        self._color_compose_preview = mode
        if update_gsettings:
            self._gsettings.set_value(
                'colorcomposepreview',
                GLib.Variant.new_boolean(mode))

    def get_color_compose_preview(self) -> bool:
        '''Returns the current value of the “color compose preview” mode'''
        return self._color_compose_preview

    def set_color_compose_preview_string(
            self,
            color_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the color for the compose preview

        :param color_string: The color for the compose preview
                            It is a string in one of the following formats:
                            - Standard name from the X11 rgb.txt
                            - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                         or ”#rrrrggggbbbb”
                            - RGB color: “rgb(r,g,b)”
                            - RGBA color: “rgba(r,g,b,a)”
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', color_string, update_gsettings)
        if color_string == self._color_compose_preview_string:
            return
        self._color_compose_preview_string = color_string
        self._color_compose_preview_argb = itb_util.color_string_to_argb(
            self._color_compose_preview_string)
        if update_gsettings:
            self._gsettings.set_value(
                'colorcomposepreviewstring',
                GLib.Variant.new_string(color_string))

    def get_color_compose_preview_string(self) -> str:
        '''Returns the current value of the “color compose preview” string'''
        return self._color_compose_preview_string

    def set_color_userdb(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use color for user database suggestions

        :param mode: Whether to use color for user database suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._color_userdb:
            return
        self._color_userdb = mode
        if update_gsettings:
            self._gsettings.set_value(
                'coloruserdb',
                GLib.Variant.new_boolean(mode))

    def get_color_userdb(self) -> bool:
        '''Returns the current value of the “color userdb” mode'''
        return self._color_userdb

    def set_color_userdb_string(
            self,
            color_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the color for user database suggestions

        :param color_string: The color for user database suggestions
                            It is a string in one of the following formats:
                            - Standard name from the X11 rgb.txt
                            - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                         or ”#rrrrggggbbbb”
                            - RGB color: “rgb(r,g,b)”
                            - RGBA color: “rgba(r,g,b,a)”
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', color_string, update_gsettings)
        if color_string == self._color_userdb_string:
            return
        self._color_userdb_string = color_string
        self._color_userdb_argb = itb_util.color_string_to_argb(
            self._color_userdb_string)
        if update_gsettings:
            self._gsettings.set_value(
                'coloruserdbstring',
                GLib.Variant.new_string(color_string))

    def get_color_userdb_string(self) -> str:
        '''Returns the current value of the “color userdb” string'''
        return self._color_userdb_string

    def set_color_spellcheck(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use color for spellchecking suggestions

        :param mode: Whether to use color for spellchecking suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._color_spellcheck:
            return
        self._color_spellcheck = mode
        if update_gsettings:
            self._gsettings.set_value(
                'colorspellcheck',
                GLib.Variant.new_boolean(mode))

    def get_color_spellcheck(self) -> bool:
        '''Returns the current value of the “color spellcheck” mode'''
        return self._color_spellcheck

    def set_color_spellcheck_string(
            self,
            color_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the color for spellchecking suggestions

        :param color_string: The color for spellchecking suggestions
                            It is a string in one of the following formats:
                            - Standard name from the X11 rgb.txt
                            - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                         or ”#rrrrggggbbbb”
                            - RGB color: “rgb(r,g,b)”
                            - RGBA color: “rgba(r,g,b,a)”
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', color_string, update_gsettings)
        if color_string == self._color_spellcheck_string:
            return
        self._color_spellcheck_string = color_string
        self._color_spellcheck_argb = itb_util.color_string_to_argb(
            self._color_spellcheck_string)
        if update_gsettings:
            self._gsettings.set_value(
                'colorspellcheckstring',
                GLib.Variant.new_string(color_string))

    def get_color_spellcheck_string(self) -> str:
        '''Returns the current value of the “color spellcheck” string'''
        return self._color_spellcheck_string

    def set_color_dictionary(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use color for dictionary suggestions

        :param mode: Whether to use color for dictionary suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._color_dictionary:
            return
        self._color_dictionary = mode
        if update_gsettings:
            self._gsettings.set_value(
                'colordictionary',
                GLib.Variant.new_boolean(mode))

    def get_color_dictionary(self) -> bool:
        '''Returns the current value of the “color dictionary” mode'''
        return self._color_dictionary

    def set_color_dictionary_string(
            self,
            color_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the color for dictionary suggestions

        :param color_string: The color for dictionary suggestions
                            It is a string in one of the following formats:
                            - Standard name from the X11 rgb.txt
                            - Hex value: “#rgb”, “#rrggbb”, “#rrrgggbbb”
                                         or ”#rrrrggggbbbb”
                            - RGB color: “rgb(r,g,b)”
                            - RGBA color: “rgba(r,g,b,a)”
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', color_string, update_gsettings)
        if color_string == self._color_dictionary_string:
            return
        self._color_dictionary_string = color_string
        self._color_dictionary_argb = itb_util.color_string_to_argb(
            self._color_dictionary_string)
        if update_gsettings:
            self._gsettings.set_value(
                'colordictionarystring',
                GLib.Variant.new_string(color_string))

    def get_color_dictionary_string(self) -> str:
        '''Returns the current value of the “color dictionary” string'''
        return self._color_dictionary_string

    def set_label_userdb(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use a label for user database

        :param mode: Whether to use a label for user database suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._label_userdb:
            return
        self._label_userdb = mode
        if update_gsettings:
            self._gsettings.set_value(
                'labeluserdb',
                GLib.Variant.new_boolean(mode))

    def get_label_userdb(self) -> bool:
        '''Returns the current value of the “label userdb” mode'''
        return self._label_userdb

    def set_label_userdb_string(
            self,
            label_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the label for user database suggestions

        :param label_string: The label for user database suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', label_string, update_gsettings)
        if label_string == self._label_userdb_string:
            return
        self._label_userdb_string = label_string
        if update_gsettings:
            self._gsettings.set_value(
                'labeluserdbstring',
                GLib.Variant.new_string(label_string))

    def get_label_userdb_string(self) -> str:
        '''Returns the current value of the “label userdb” string'''
        return self._label_userdb_string

    def set_label_spellcheck(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use a label for spellchecking suggestions

        :param mode: Whether to use a label for spellchecking suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._label_spellcheck:
            return
        self._label_spellcheck = mode
        if update_gsettings:
            self._gsettings.set_value(
                'labelspellcheck',
                GLib.Variant.new_boolean(mode))

    def get_label_spellcheck(self) -> bool:
        '''Returns the current value of the “label spellcheck” mode'''
        return self._label_spellcheck

    def set_label_spellcheck_string(
            self,
            label_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the label for spellchecking suggestions

        :param label_string: The label for spellchecking suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', label_string, update_gsettings)
        if label_string == self._label_spellcheck_string:
            return
        self._label_spellcheck_string = label_string
        if update_gsettings:
            self._gsettings.set_value(
                'labelspellcheckstring',
                GLib.Variant.new_string(label_string))

    def get_label_spellcheck_string(self) -> str:
        '''Returns the current value of the “label spellcheck” string'''
        return self._label_spellcheck_string

    def set_label_dictionary(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use a label for dictionary suggestions

        :param mode: Whether to use a label for dictionary suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._label_dictionary:
            return
        self._label_dictionary = mode
        if update_gsettings:
            self._gsettings.set_value(
                'labeldictionary',
                GLib.Variant.new_boolean(mode))

    def get_label_dictionary(self) -> bool:
        '''Returns the current value of the “label dictionary” mode'''
        return self._label_dictionary

    def set_label_dictionary_string(
            self,
            label_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the label for dictionary suggestions

        :param label_string: The label for dictionary suggestions
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', label_string, update_gsettings)
        if label_string == self._label_dictionary_string:
            return
        self._label_dictionary_string = label_string
        self._label_dictionary_dict = {}
        if label_string.startswith('{'):
            try:
                self._label_dictionary_dict = ast.literal_eval(label_string)
                if not isinstance(self._label_dictionary_dict, dict):
                    self._label_dictionary_dict = {}
            except (SyntaxError, ValueError) as error:
                LOGGER.exception(
                    'Cannot parse label_string as dict: %s: %s',
                    error.__class__.__name__, error)
        if DEBUG_LEVEL > 1:
            LOGGER.debug('self._label_dictionary_dict=%s',
                         repr(self._label_dictionary_dict))
        if update_gsettings:
            self._gsettings.set_value(
                'labeldictionarystring',
                GLib.Variant.new_string(label_string))

    def get_label_dictionary_string(self) -> str:
        '''Returns the current value of the “label dictionary” string'''
        return self._label_dictionary_string

    def set_flag_dictionary(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to add flags to dictionary matches

        :param mode: Whether to add flags to suggestions matching
                     in dictionaries
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._flag_dictionary:
            return
        self._flag_dictionary = mode
        if update_gsettings:
            self._gsettings.set_value(
                'flagdictionary',
                GLib.Variant.new_boolean(mode))

    def get_flag_dictionary(self) -> bool:
        '''Returns the current value of the “flag dictionary” mode'''
        return self._flag_dictionary

    def set_label_busy(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use a label to indicate busy state

        :param mode: Whether to use a label to indicate busy state
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._label_busy:
            return
        self._label_busy = mode
        if update_gsettings:
            self._gsettings.set_value(
                'labelbusy',
                GLib.Variant.new_boolean(mode))

    def get_label_busy(self) -> bool:
        '''Returns the current value of the “label busy” mode'''
        return self._label_busy

    def set_label_busy_string(
            self,
            label_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the label used to indicate busy state

        :param label_string: The label to indicate busy state
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', label_string, update_gsettings)
        if label_string == self._label_busy_string:
            return
        self._label_busy_string = label_string
        if update_gsettings:
            self._gsettings.set_value(
                'labelbusystring',
                GLib.Variant.new_string(label_string))

    def get_label_busy_string(self) -> str:
        '''Returns the current value of the “label busy” string'''
        return self._label_busy_string

    def set_google_application_credentials(
            self,
            path: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the label used to indicate busy state

        :param path: Full path of the Google application
                     credentials .json file.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', path, update_gsettings)
        if self._google_application_credentials == path:
            return
        self._google_application_credentials = path
        if update_gsettings:
            self._gsettings.set_value(
                'googleapplicationcredentials',
                GLib.Variant.new_string(path))

    def get_google_application_credentials(self) -> str:
        '''Returns the current value of the full path to the
        Google application credentials .json file.
        '''
        return self._google_application_credentials

    def set_tab_enable(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Tab enable” mode

        :param mode: Whether to show a candidate list only when typing Tab
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._tab_enable:
            return
        self._tab_enable = mode
        if update_gsettings:
            self._gsettings.set_value(
                'tabenable',
                GLib.Variant.new_boolean(mode))

    def get_tab_enable(self) -> bool:
        '''Returns the current value of the “Tab enable” mode'''
        return self._tab_enable

    def set_disable_in_terminals(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Disable in terminals” mode

        :param mode: Whether to disable Typing Booster in terminals
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._disable_in_terminals:
            return
        self._disable_in_terminals = mode
        if update_gsettings:
            self._gsettings.set_value(
                'disableinterminals',
                GLib.Variant.new_boolean(mode))

    def get_disable_in_terminals(self) -> bool:
        '''Returns the current value of the “Disable in terminals” mode'''
        return self._disable_in_terminals

    def set_ascii_digits(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether the to convert language specific digits to ASCII digits

        :param mode: Whether to convert language specific digits
                     to ASCII digits
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._ascii_digits:
            return
        self._ascii_digits = mode
        if update_gsettings:
            self._gsettings.set_value(
                'asciidigits',
                GLib.Variant.new_boolean(mode))

    def get_ascii_digits(self) -> bool:
        '''Returns the current value of the “ASCII digits” mode'''
        return self._ascii_digits

    def toggle_ascii_digits(self, update_gsettings: bool = True) -> None:
        '''Toggles whether to convert languages specific digits to ASCII digits

        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        self.set_ascii_digits(
            not self._ascii_digits, update_gsettings)

    def set_remember_last_used_preedit_ime(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Remember last used preëdit ime” mode

        :param mode: Whether to remember the input method used last for
                     the preëdit
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._remember_last_used_preedit_ime:
            return
        self._remember_last_used_preedit_ime = mode
        if update_gsettings:
            self._gsettings.set_value(
                'rememberlastusedpreeditime',
                GLib.Variant.new_boolean(mode))

    def get_remember_last_used_preedit_ime(self) -> bool:
        '''Returns the current value of the
        “Remember last used preëdit ime” mode
        '''
        return self._remember_last_used_preedit_ime

    def set_remember_input_mode(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Remember input mode” mode

        :param mode: Whether to remember the input mode (on/off)
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._remember_input_mode:
            return
        self._remember_input_mode = mode
        if update_gsettings:
            self._gsettings.set_value(
                'rememberinputmode',
                GLib.Variant.new_boolean(mode))

    def get_remember_input_mode(self) -> bool:
        '''Returns the current value of the ”Remember input mode" mode.'''
        return self._remember_input_mode

    def set_page_size(
            self,
            page_size: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the page size of the lookup table

        :param page_size: The page size of the lookup table
                          1 <= size <= 9
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', page_size, update_gsettings)
        if page_size == self._page_size:
            return
        if 1 <= page_size <= 9:
            self._page_size = page_size
            self._lookup_table.set_page_size(self._page_size)
            self._clear_input_and_update_ui()
            if update_gsettings:
                self._gsettings.set_value(
                    'pagesize',
                    GLib.Variant.new_int32(page_size))

    def get_page_size(self) -> int:
        '''Returns the current page size of the lookup table'''
        return self._page_size

    def set_lookup_table_orientation(
            self,
            orientation: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the orientation of the lookup table

        :param orientation: The orientation of the lookup table
                            0 <= orientation <= 2
                            IBUS_ORIENTATION_HORIZONTAL = 0,
                            IBUS_ORIENTATION_VERTICAL   = 1,
                            IBUS_ORIENTATION_SYSTEM     = 2.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', orientation, update_gsettings)
        if orientation == self._lookup_table_orientation:
            return
        if 0 <= orientation <= 2:
            self._lookup_table_orientation = orientation
            self._lookup_table.set_orientation(self._lookup_table_orientation)
            self._clear_input_and_update_ui()
            if update_gsettings:
                self._gsettings.set_value(
                    'lookuptableorientation',
                    GLib.Variant.new_int32(orientation))

    def get_lookup_table_orientation(self) -> int:
        '''Returns the current orientation of the lookup table'''
        return self._lookup_table_orientation

    def set_preedit_underline(
            self,
            underline_mode: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the underline style for the preedit

        :param underline_mode: The underline mode to be used for the preedit
                              0 <= underline_mode <= 3
                              IBus.AttrUnderline.NONE    = 0,
                              IBus.AttrUnderline.SINGLE  = 1,
                              IBus.AttrUnderline.DOUBLE  = 2,
                              IBus.AttrUnderline.LOW     = 3,
                              IBus.AttrUnderline.ERROR   = 4,
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)',
                underline_mode, update_gsettings)
        if underline_mode == self._preedit_underline:
            return
        if 0 <= underline_mode < IBus.AttrUnderline.ERROR:
            self._preedit_underline = underline_mode
            self._update_ui()
            if update_gsettings:
                self._gsettings.set_value(
                    'preeditunderline',
                    GLib.Variant.new_int32(underline_mode))

    def get_preedit_underline(self) -> int:
        '''Returns the current underline style of the preedit'''
        return self._preedit_underline

    def set_preedit_style_only_when_lookup(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Use preedit styling only when lookup is enabled” mode

        :param mode: Whether preedit styling like underlining should
                     be enabled only when lookup is enabled.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings=%s)', mode, update_gsettings)
        if mode == self._preedit_style_only_when_lookup:
            return
        self._preedit_style_only_when_lookup = mode
        if update_gsettings:
            self._gsettings.set_value(
                'preeditstyleonlywhenlookup',
                GLib.Variant.new_boolean(mode))

    def get_preedit_style_only_when_lookup(self) -> bool:
        '''Returns the current value of the “Tab enable” mode'''
        return self._preedit_style_only_when_lookup

    def set_min_char_complete(
            self,
            min_char_complete: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the minimum number of characters to try completion

        :param min_char_complete: The minimum number of characters
                                  to type before completion is tried.
                                  0 <= min_char_complete <= 9
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)',
                min_char_complete, update_gsettings)
        if min_char_complete == self._min_char_complete:
            return
        if 0 <= min_char_complete <= 9:
            self._min_char_complete = min_char_complete
            self._clear_input_and_update_ui()
            if update_gsettings:
                self._gsettings.set_value(
                    'mincharcomplete',
                    GLib.Variant.new_int32(min_char_complete))

    def get_min_char_complete(self) -> int:
        '''Returns the current minimum number of characters to try completion
        '''
        return self._min_char_complete

    def set_debug_level(
            self,
            debug_level: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the debug level

        :param debug_level: The debug level
                            0 <= debug_level <= 255
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        global DEBUG_LEVEL # pylint: disable=global-statement
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', debug_level, update_gsettings)
        if debug_level == self._debug_level:
            return
        if 0 <= debug_level <= 255:
            self._debug_level = debug_level
            DEBUG_LEVEL = debug_level
            self._clear_input_and_update_ui()
            if update_gsettings:
                self._gsettings.set_value(
                    'debuglevel',
                    GLib.Variant.new_int32(debug_level))

    def get_debug_level(self) -> int:
        '''Returns the current debug level'''
        return self._debug_level

    def set_ibus_event_sleep_seconds(
            self,
            seconds: Union[float, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the ibus event sleep seconds

        :param seconds:          ibus event sleep seconds
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.debug(
            '(%s, update_gsettings = %s)', seconds, update_gsettings)
        if seconds == self._ibus_event_sleep_seconds:
            return
        self._ibus_event_sleep_seconds = seconds
        if update_gsettings:
            self._gsettings.set_value(
                'ibuseventsleepseconds',
                GLib.Variant.new_double(self._ibus_event_sleep_seconds))

    def get_ibus_event_sleep_seconds(self) -> float:
        '''Returns the current value ibus event sleep seconds '''
        return self._ibus_event_sleep_seconds

    def set_error_sound(
            self, error_sound: bool, update_gsettings: bool = True) -> None:
        '''Sets whether a sound is played on error or not

        :param error_sound: True if a sound is played on error, False if not
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', error_sound, update_gsettings)
        if error_sound == self._error_sound:
            return
        self._error_sound = error_sound
        if update_gsettings:
            self._gsettings.set_value(
                'errorsound',
                GLib.Variant.new_boolean(error_sound))

    def get_error_sound(self) -> bool:
        '''Returns whether a sound is played on error or not'''
        return self._error_sound

    def set_error_sound_file(
            self,
            path: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the path of the .wav file containing the sound
        to play on error.

        :param path: The path of the .wav file containing the error sound
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the dconf key changed
                                 to avoid endless loops when the dconf
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', path, update_gsettings)
        if not isinstance(path, str):
            return
        if path == self._error_sound_file:
            return
        self._error_sound_file = path
        if update_gsettings:
            self._gsettings.set_value(
                'errorsoundfile',
                GLib.Variant.new_string(path))
        self._error_sound_object = itb_sound.SoundObject(
            os.path.expanduser(path),
            audio_backend=self._sound_backend)

    def get_error_sound_file(self) -> str:
        '''
        Return the path of the .wav file containing the error sound.
        '''
        return self._error_sound_file

    def set_sound_backend(
            self,
            sound_backend: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the sound backend to use

        :param sound_backend: The name of sound backend to use
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the dconf key changed
                                 to avoid endless loops when the dconf
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', sound_backend, update_gsettings)
        if not isinstance(sound_backend, str):
            return
        if sound_backend == self._sound_backend:
            return
        self._sound_backend = sound_backend
        if update_gsettings:
            self._gsettings.set_value(
                'soundbackend',
                GLib.Variant.new_string(sound_backend))
        self._error_sound_object = itb_sound.SoundObject(
            os.path.expanduser(self._error_sound_file),
            audio_backend=self._sound_backend)

    def get_sound_backend(self) -> str:
        '''
        Return the name of the currently used sound backend
        '''
        return self._sound_backend

    def set_show_number_of_candidates(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Show number of candidates” mode

        :param mode: Whether to show the number of candidates
                     in the auxiliary text
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._show_number_of_candidates:
            return
        self._show_number_of_candidates = mode
        self._clear_input_and_update_ui()
        if update_gsettings:
            self._gsettings.set_value(
                'shownumberofcandidates',
                GLib.Variant.new_boolean(mode))

    def get_show_number_of_candidates(self) -> bool:
        '''Returns the current value of the “Show number of candidates” mode
        '''
        return self._show_number_of_candidates

    def set_show_status_info_in_auxiliary_text(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Show status info in auxiliary text” mode

        :param mode: Whether to show status information in the
                     auxiliary text.
                     Currently the status information which can be
                     displayed there is whether emoji mode and
                     off-the-record mode are on or off
                     and which input method is currently used for
                     the preëdit text.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._show_status_info_in_auxiliary_text:
            return
        self._show_status_info_in_auxiliary_text = mode
        self._clear_input_and_update_ui()
        if update_gsettings:
            self._gsettings.set_value(
                'showstatusinfoinaux',
                GLib.Variant.new_boolean(mode))

    def get_show_status_info_in_auxiliary_text(self) -> bool:
        '''Returns the current value of the
        “Show status in auxiliary text” mode
        '''
        return self._show_status_info_in_auxiliary_text

    def set_auto_select_candidate(
            self,
            mode: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the “Automatically select the best candidate” mode

        :param mode: Whether to automatically select the best candidate
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'set_auto_select_candidate(%s, update_gsettings = %s)',
                mode, update_gsettings)
        if mode == self._auto_select_candidate:
            return
        self._auto_select_candidate = mode
        self._clear_input_and_update_ui()
        if update_gsettings:
            self._gsettings.set_value(
                'autoselectcandidate',
                GLib.Variant.new_int32(mode))

    def get_auto_select_candidate(self) -> int:
        '''Returns the current value of the
        “Automatically select the best candidate” mode
        '''
        return self._auto_select_candidate

    def do_candidate_clicked( # pylint: disable=arguments-differ
            self, index: int, button: int, state: int) -> None:
        '''Called when a candidate in the lookup table
        is clicked with the mouse
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'index = %s button = %s state = %s\n', index, button, state)
        if not self._set_lookup_table_cursor_pos_in_current_page(index):
            return
        self._lookup_table.set_cursor_visible(True)

        if self._lookup_table_shows_compose_completions:
            if button == 1:
                phrase = self.get_string_from_lookup_table_cursor_pos()
                self._lookup_table_shows_compose_completions = False
                self._candidates = []
                self.get_lookup_table().clear()
                self.get_lookup_table().set_cursor_visible(False)
                self._update_lookup_table_and_aux()
                self._typed_compose_sequence = []
                self._update_transliterated_strings()
                if phrase:
                    if self.get_input_mode():
                        self._insert_string_at_cursor(list(phrase))
                        self._update_ui()
                        return
                    self._update_preedit()
                    super().commit_text(
                        IBus.Text.new_from_string(phrase))
                    self._commit_happened_after_focus_in = True
            return

        if button == 1 and (state & IBus.ModifierType.CONTROL_MASK):
            self.remove_candidate_from_user_database(index)
            self._update_ui()
            return
        if button == 1:
            phrase = self.get_string_from_lookup_table_cursor_pos()
            if phrase:
                if self._add_space_on_commit:
                    phrase += ' '
                self._commit_string(phrase)
                self._clear_input_and_update_ui()
            return
        if (button == 3
            and (state & IBus.ModifierType.MOD1_MASK)
            and (state & IBus.ModifierType.CONTROL_MASK)):
            self._start_setup()
            return
        if button == 3 and (state & IBus.ModifierType.CONTROL_MASK):
            self.toggle_emoji_prediction_mode()
            return
        if button == 3 and (state & IBus.ModifierType.MOD1_MASK):
            self.toggle_off_the_record_mode()
            return
        if button == 3:
            self._lookup_related_candidates()
            return

    def _speech_recognition_error(self, error_message: str) -> None:
        '''Show an error message in the auxiliary text when
        something goes wrong with speech recognition.

        :param error_message: The text to display as error message
        '''
        auxiliary_text_label = ''
        if (self._label_speech_recognition
            and self._label_speech_recognition_string.strip()):
            # Show a label in the auxiliary text to indicate speech
            # recognition:
            auxiliary_text_label = (
                self._label_speech_recognition_string.strip())
        super().update_auxiliary_text(
            IBus.Text.new_from_string(
                auxiliary_text_label + '⚠️' + error_message), True)
        time.sleep(2)
        self._update_ui()

    def _speech_recognition(self) -> None:
        '''
        Listen to microphone, convert to text using Google speech-to-text
        and insert converted text.
        '''
        if DEBUG_LEVEL:
            LOGGER.debug('speech_recognition()\n')
        self._clear_input_and_update_ui()
        if not IMPORT_GOOGLE_SPEECH_TO_TEXT_SUCCESSFUL:
            self._speech_recognition_error(
                _('Failed to import Google speech-to-text.'))
            return
        if not itb_util.IMPORT_PYAUDIO_SUCCESSFUL:
            self._speech_recognition_error(_('Failed to import pyaudio.'))
            return
        if not itb_util.IMPORT_QUEUE_SUCCESSFUL:
            self._speech_recognition_error(_('Failed to import queue.'))
            return
        language_code = self._dictionary_names[0]
        if not language_code:
            self._speech_recognition_error(
                _('No supported language for speech recognition.'))
            return
        if not os.path.isfile(self._google_application_credentials):
            self._speech_recognition_error(
                _('“Google application credentials” file “%s” not found.')
                % self._google_application_credentials)
            return

        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = (
            self._google_application_credentials)
        try:
            client = speech.SpeechClient()
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Exception when intializing Google speech-to-text: %s: %s',
                error.__class__.__name__, error)
            self._speech_recognition_error(
                _('Failed to init Google speech-to-text. See debug.log.'))
            return

        config = types.RecognitionConfig(
            encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=itb_util.AUDIO_RATE,
            language_code=language_code)
        streaming_config = types.StreamingRecognitionConfig(
            config=config,
            interim_results=True)

        auxiliary_text_label = ''
        if (self._label_speech_recognition
            and self._label_speech_recognition_string.strip()):
            # Show a label in the auxiliary text to indicate speech
            # recognition:
            auxiliary_text_label = (
                self._label_speech_recognition_string.strip())
        auxiliary_text_label += language_code
        flag = itb_util.get_flag(language_code.replace('-', '_'))
        if flag:
            auxiliary_text_label += ' ' + flag
        if (language_code.replace('-', '_')
            not in itb_util.GOOGLE_SPEECH_TO_TEXT_LANGUAGES):
            # The officially list of languages supported by Google
            # speech-to-text is here:
            # https://cloud.google.com/speech-to-text/docs/languages
            # and I copied this list into
            # itb_util.GOOGLE_SPEECH_TO_TEXT_LANGUAGES.
            #
            # But I don’t know any way to find out via the API whether
            # a language is supported or not. When trying to set a
            # language which is not supported, for example “gsw_CH”
            # (Alemannic German), there is no error, but it seems to
            # fall back to recognizing English.
            #
            # In the official list, only “de-DE” is supported, but
            # when trying I found that “de”, “de-DE”, “de-AT”,
            # “de-CH”, “de-BE”, “de-LU” all seem to work the same and
            # seem to recognize standard German.  When using “de-CH”,
            # it uses ß when spelling even though this is not used in
            # Switzerland, so “de-CH” seems to fall back to standard
            # German, there seems to be no difference between using
            # “de-DE” and “de-CH”.
            #
            # For “en-GB” and “en-US”, there *is* a difference, the
            # transcribed text uses British or American spelling
            # depending on which one of these English variants is
            # used.
            #
            # I don’t want to disallow using something like “de-CH”
            # for speech recognition just because it is not on the
            # list of officially supported languages. Therefore, I allow
            # *all* languages to be used for speech recognition. But when
            # a language is not officially supported, I mark it with '❌'
            # in the label to indicate that it is not officially supported
            # and may just fall back to English, but it is also possible
            # that it works just fine. One has to try it.
            auxiliary_text_label += '❌' # not officially supported
        auxiliary_text_label += ': '
        super().update_auxiliary_text(
            IBus.Text.new_from_string(auxiliary_text_label), True)

        transcript = ''
        with itb_util.MicrophoneStream(
                itb_util.AUDIO_RATE, itb_util.AUDIO_CHUNK) as stream:
            audio_generator = stream.generator()
            requests = (types.StreamingRecognizeRequest(audio_content=content)
                        for content in audio_generator)
            responses = client.streaming_recognize(streaming_config, requests)
            try:
                for response in responses:
                    if not response.results:
                        continue
                    # The `results` list is consecutive. For streaming, we
                    # only care about the first result being considered,
                    # since once it's `is_final`, it moves on to
                    # considering the next utterance.
                    result = response.results[0]
                    if not result.alternatives:
                        continue
                    # Display the transcription of the top alternative.
                    transcript = result.alternatives[0].transcript
                    if DEBUG_LEVEL > 1:
                        LOGGER.debug(
                            '-------------------  %s alternative(s)',
                            len(result.alternatives))
                        for alternative in result.alternatives:
                            LOGGER.debug('%s', alternative.transcript)
                    # Display interim results in auxiliary text.
                    # Showing it in the preedit because updating the
                    # preedit causes Gtk events. And I may want to use
                    # Gtk events to cancel voice recording Currently
                    # this is not possible because the voice recording
                    # blocks and Gtk events can be handled only after
                    # the voice recording is finished.  But in future
                    # I may try to use a different thread for the
                    # voice recording.
                    super().update_auxiliary_text(
                        IBus.Text.new_from_string(
                            auxiliary_text_label + transcript),
                        True)
                    if result.is_final:
                        break
            except Exception as error: # pylint: disable=broad-except
                LOGGER.exception('Google speech-to-text error: %s: %s',
                                 error.__class__.__name__, error)
                self._speech_recognition_error(
                    _('Google speech-to-text error. See debug.log.'))
                return

        if transcript:
            # Uppercase first letter of transcript if the text left
            # of the cursor ends with a sentence ending character
            # or if the text left of the cursor is empty.
            # If surrounding text cannot be used, uppercase the
            # first letter unconditionally:
            if (not
                self.client_capabilities & itb_util.Capabilite.SURROUNDING_TEXT
                or
                self._input_purpose in [itb_util.InputPurpose.TERMINAL.value]):
                transcript = transcript[0].upper() + transcript[1:]
            else:
                surrounding_text = self.get_surrounding_text()
                text = surrounding_text[0].get_text()
                cursor_pos = surrounding_text[1]
                anchor_pos = surrounding_text[2]
                text_left = text[:cursor_pos].strip()
                if DEBUG_LEVEL > 1:
                    LOGGER.debug(
                        'surrounding_text = '
                        '[text = %r, cursor_pos = %s, anchor_pos = %s]',
                        text, cursor_pos, anchor_pos)
                    LOGGER.debug('text_left = %r', text_left)
                if not text_left or text_left[-1] in '.;:?!':
                    transcript = transcript[0].upper() + transcript[1:]

        self._insert_string_at_cursor(list(transcript))
        self._update_transliterated_strings()
        self._update_ui()
        return

    def _command_toggle_input_mode_on_off(self) -> bool:
        '''Handle hotkey for the command “toggle_input_mode_on_off”

        :return: True if the key was completely handled, False if not.
        '''
        self.toggle_input_mode()
        return True

    def _command_speech_recognition(self) -> bool:
        '''Handle hotkey for the command “speech_recognition”

        :return: True if the key was completely handled, False if not.
        '''
        self._speech_recognition()
        return True

    def _command_next_case_mode(self) -> bool:
        '''Handle hotkey for the command “next_case_mode”

        :return: True if the key was completely handled, False if not.
        '''
        self._case_mode_change(mode='next')
        self._update_lookup_table_and_aux()
        return True

    def _command_previous_case_mode(self) -> bool:
        '''Handle hotkey for the command “next_case_mode”

        :return: True if the key was completely handled, False if not.
        '''
        self._case_mode_change(mode='previous')
        self._update_lookup_table_and_aux()
        return True

    def _command_cancel(self) -> bool:
        '''Handle hotkey for the command “cancel”

        :return: True if the key was completely handled, False if not.
        '''
        if (self.is_empty()
            and not self._typed_compose_sequence):
            if self.get_lookup_table().get_number_of_candidates():
                # There might be candidates even if the input
                # is empty if self._min_char_complete == 0.
                # If that is the case, cancel these candidates
                # and return True. If not, return False
                # because then there is nothing to cancel and the
                # key which triggered the cancel command should be
                # passed through.
                self._update_ui_empty_input()
                return True
            return False
        if self._typed_compose_sequence:
            if self._lookup_table_shows_compose_completions:
                if self.get_lookup_table().cursor_visible:
                    # A candidate is selected in the lookup table.
                    # Deselect it and show the first page of the candidate
                    # list:
                    self.get_lookup_table().set_cursor_visible(False)
                    self.get_lookup_table().set_cursor_pos(0)
                    self._update_lookup_table_and_aux()
                    return True
                self._lookup_table_shows_compose_completions = False
                self.get_lookup_table().clear()
                self.get_lookup_table().set_cursor_visible(False)
                self._update_lookup_table_and_aux()
                self._update_preedit()
                self._candidates = []
                return True
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Compose sequence cancelled.')
            self._typed_compose_sequence = []
            self._update_transliterated_strings()
            if self.get_input_mode():
                self._update_ui()
            else:
                self._update_preedit()
            return True
        if self.get_lookup_table().cursor_visible:
            # A candidate is selected in the lookup table.
            # Deselect it and show the first page of the candidate
            # list:
            self.get_lookup_table().set_cursor_visible(False)
            self.get_lookup_table().set_cursor_pos(0)
            self._update_lookup_table_and_aux()
            return True
        if (self._lookup_table_shows_related_candidates
            or self._current_case_mode != 'orig'):
            self._current_case_mode = 'orig'
            # Force an update to the original lookup table:
            self._update_ui()
            return True
        if ((self._tab_enable or self._min_char_complete > 1)
                and self.is_lookup_table_enabled_by_tab
                and self.get_lookup_table().get_number_of_candidates()):
            # If lookup table was enabled by typing Tab, and it is
            # not empty, close it again but keep the preëdit:
            self.is_lookup_table_enabled_by_tab = False
            self.get_lookup_table().clear()
            self.get_lookup_table().set_cursor_visible(False)
            self._update_lookup_table_and_aux()
            self._update_preedit()
            self._candidates = []
            self._current_case_mode = 'orig'
            return True
        self._clear_input_and_update_ui()
        self._update_ui()
        return True

    def _command_enable_lookup(self) -> bool:
        '''Handle hotkey for the command “enable_lookup”

        :return: True if the key was completely handled, False if not.
        '''
        if self._typed_compose_sequence:
            if self._lookup_table_shows_compose_completions:
                return False
            compose_completions = (
                self._compose_sequences.find_compose_completions(
                    self._typed_compose_sequence,
                    self._keyvals_to_keycodes.keyvals()))
            self._candidates = []
            self.get_lookup_table().clear()
            self.get_lookup_table().set_cursor_visible(False)
            for compose_completion in compose_completions:
                compose_result = self._compose_sequences.compose(
                    self._typed_compose_sequence + compose_completion)
                if compose_result:
                    self._candidates.append(
                        (compose_result, 0, '', False, False))
                    text_for_lookup_table = (
                        self._compose_sequences.lookup_representation(
                            compose_completion))
                    if (self._lookup_table.get_orientation()
                        == IBus.Orientation.VERTICAL):
                        text_for_lookup_table += '   \t' + compose_result
                    else:
                        text_for_lookup_table += ' ' + compose_result
                    if (self._lookup_table.get_orientation()
                        == IBus.Orientation.VERTICAL):
                        if len(compose_result) < 6:
                            text_for_lookup_table += '  \t'
                            for char in compose_result:
                                text_for_lookup_table += f' U+{ord(char):04X}'
                        if len(compose_result) == 1:
                            text_for_lookup_table += ' ' + unicodedata.name(
                                compose_result).lower()
                    self._append_candidate_to_lookup_table(
                        phrase=text_for_lookup_table)
            self._update_lookup_table_and_aux()
            self._lookup_table_shows_compose_completions = True
            return True

        if ((self._tab_enable
             or (self._min_char_complete > 1
                 and
                 not self.is_lookup_table_enabled_by_min_char_complete))
            and not self.is_lookup_table_enabled_by_tab
            and not self.is_empty()):
            self.is_lookup_table_enabled_by_tab = True
            # update the ui here to see the effect immediately
            # do not wait for the next keypress:
            self._update_ui()
            return True
        return False

    def _command_next_input_method(self) -> bool:
        '''Handle hotkey for the command “next_input_method”

        :return: True if the key was completely handled, False if not.
        '''
        imes = self.get_current_imes()
        if len(imes) > 1:
            # remove the first ime from the list and append it to the end.
            update_gsettings=self._remember_last_used_preedit_ime
            if 'inputmethod' in self._autosettings_revert:
                update_gsettings = False
            self.set_current_imes(
                imes[1:] + imes[:1],
                update_gsettings=update_gsettings)
            return True
        return False

    def _command_previous_input_method(self) -> bool:
        '''Handle hotkey for the command “previous_input_method”

        :return: True if the key was completely handled, False if not.
        '''
        imes = self.get_current_imes()
        if len(imes) > 1:
            # remove the last ime in the list and add it in front:
            update_gsettings=self._remember_last_used_preedit_ime
            if 'inputmethod' in self._autosettings_revert:
                update_gsettings = False
            self.set_current_imes(
                imes[-1:] + imes[:-1],
                update_gsettings=update_gsettings)
            return True
        return False

    def _command_next_dictionary(self) -> bool:
        '''Handle hotkey for the command “next_dictionary”

        :return: True if the key was completely handled, False if not.
        '''
        names = self.get_dictionary_names()
        if len(names) > 1:
            # remove the first dictionary from the list and append
            # it to the end.
            update_gsettings = True
            if 'dictionary' in self._autosettings_revert:
                update_gsettings = False
            self.set_dictionary_names(
                names[1:] + names[:1],
                update_gsettings=update_gsettings)
            return True
        return False

    def _command_previous_dictionary(self) -> bool:
        '''Handle hotkey for the command “previous_dictionary”

        :return: True if the key was completely handled, False if not.
        '''
        names = self.get_dictionary_names()
        if len(names) > 1:
            # remove the last dictionary in the list and add it in front:
            update_gsettings = True
            if 'dictionary' in self._autosettings_revert:
                update_gsettings = False
            self.set_dictionary_names(
                names[-1:] + names[:-1],
                update_gsettings=update_gsettings)
            return True
        return False

    def _command_select_next_candidate(self) -> bool:
        '''Handle hotkey for the command “select_next_candidate”

        :return: True if the key was completely handled, False if not.
        '''
        if self.get_lookup_table().get_number_of_candidates():
            dummy = self._arrow_down()
            self._update_lookup_table_and_aux()
            return True
        return False

    def _command_select_previous_candidate(self) -> bool:
        '''Handle hotkey for the command “select_previous_candidate”

        :return: True if the key was completely handled, False if not.
        '''
        if self.get_lookup_table().get_number_of_candidates():
            dummy = self._arrow_up()
            self._update_lookup_table_and_aux()
            return True
        return False

    def _command_lookup_table_page_down(self) -> bool:
        '''Handle hotkey for the command “lookup_table_page_down”

        :return: True if the key was completely handled, False if not.
        '''
        if self.get_lookup_table().get_number_of_candidates():
            dummy = self._page_down()
            self._update_lookup_table_and_aux()
            return True
        return False

    def _command_lookup_table_page_up(self) -> bool:
        '''Handle hotkey for the command “lookup_table_page_up”

        :return: True if the key was completely handled, False if not.
        '''
        if self.get_lookup_table().get_number_of_candidates():
            dummy = self._page_up()
            self._update_lookup_table_and_aux()
            return True
        return False

    def _command_toggle_emoji_prediction(self) -> bool:
        '''Handle hotkey for the command “toggle_emoji_prediction”

        :return: True if the key was completely handled, False if not.
        '''
        self.toggle_emoji_prediction_mode()
        return True

    def _command_toggle_off_the_record(self) -> bool:
        '''Handle hotkey for the command “toggle_off_the_record”

        :return: True if the key was completely handled, False if not.
        '''
        self.toggle_off_the_record_mode()
        return True

    def _command_toggle_ascii_digits(self) -> bool:
        '''Handle hotkey for the command “toggle_ascii_digits”

        :return: True if the key was completely handled, False if not.
        '''
        self.toggle_ascii_digits()
        return True

    def _command_lookup_related(self) -> bool:
        '''Handle hotkey for the command “lookup_related”

        :return: True if the key was completely handled, False if not.
        '''
        if not self.is_empty():
            self._lookup_related_candidates()
            return True
        return False

    def _command_toggle_hide_input(self) -> bool:
        '''Handle hotkey for the command “toggle_hide_input”

        :return: True if the key was completely handled, False if not.
        '''
        self._hide_input = not self._hide_input
        self._update_ui()
        return True

    def _command_setup(self) -> bool:
        '''Handle hotkey for the command “setup”

        :return: True if the key was completely handled, False if not.
        '''
        self._start_setup()
        return True

    def _change_line_direction(self, direction: str) -> None:
        '''Change the direction of the current line

        :param direction: The desired direction of the current line:
                          'ltr', 'rtl', 'toggle'
        '''
        LOGGER.debug('Trying to change line direction to %r'
                     'self._im_client=%s',
                     direction, self._im_client)
        if (not self.client_capabilities & itb_util.Capabilite.SURROUNDING_TEXT
            or
            self._input_purpose in [itb_util.InputPurpose.TERMINAL.value]):
            LOGGER.debug(
                'Surrounding text not supported, cannot change line direction.')
            return
        if re.compile(
                r':(firefox|google-chrome|soffice|libreoffice-calc):').search(
                    self._im_client):
            LOGGER.debug('firefox, libreoffice, or google-chrome detected. '
                         'Cannot change line direction in these programs. '
                         'These programs already have their own support to '
                         'change direction between RTL and LTR for the whole '
                         'buffer, use this instead of changing the direction '
                         'of single lines with typing booster.')
            return
        if not self.is_empty() or self._typed_compose_sequence:
            LOGGER.debug('Committing pending input first ...')
            self._commit_current_input()
            LOGGER.debug(
                'To make the committed text appear in the surrounding '
                'text, another key event is needed. Therefore, a return '
                'is unfortunately necessary here and to really change '
                'the line direction, one has to press the keybinding again.')
            return
        surrounding_text = self.get_surrounding_text()
        LOGGER.debug('self._surrounding_text_event_happened_after_focus_in=%r '
                     'self._commit_happened_after_focus_in=%r '
                     'surrouning text=[%r, %s, %s]',
                     self._surrounding_text_event_happened_after_focus_in,
                     self._commit_happened_after_focus_in,
                     surrounding_text[0].get_text(),
                     surrounding_text[1], surrounding_text[2])
        if (not self._surrounding_text_event_happened_after_focus_in
            and not self._commit_happened_after_focus_in):
            # Before the first surrounding text event happened,
            # surrounding text is probably from the previously
            # focused window (bug!), don’t use it.
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Neither a surrounding text event nor a '
                             'commit happend since focus in. '
                             'The surrounding_text might be wrong. '
                             'Do not try to change line direction.')
            return
        surrounding_text = self.get_surrounding_text()
        if not surrounding_text:
            LOGGER.debug(
                'New surrounding text object is None. Should never happen.')
            return
        text = surrounding_text[0].get_text()
        cursor_pos = surrounding_text[1]
        anchor_pos = surrounding_text[2]
        LOGGER.debug('surrounding_text=[%r, %s, %s]',
                     list(text), cursor_pos, anchor_pos)
        if cursor_pos != anchor_pos:
            LOGGER.debug('cursor_pos != anchor_pos, do nothing.')
            return
        if not text:
            LOGGER.debug('surrounding text empty, do nothing.')
        cursor_pos_in_current_line = cursor_pos
        current_line = ''
        for line in text.splitlines(keepends=True):
            if len(line) < cursor_pos_in_current_line:
                cursor_pos_in_current_line -= len(line)
                continue
            current_line = line
            break
        if current_line.endswith('\n'):
            current_line = current_line[:-1]
        LOGGER.debug(
            'current_line=%r len(current_line)=%d '
            'cursor_pos_in_current_line=%d ',
            current_line, len(current_line),
            cursor_pos_in_current_line)
        if not current_line.strip():
            LOGGER.debug('Current line empty or whitespace only, do nothing.')
            return
        if direction == 'toggle':
            direction = 'rtl'
            if itb_util.is_right_to_left(current_line):
                direction = 'ltr'
        LOGGER.debug('Current line needs to change direction to %r.',
                     direction)
        directions = {
            'ltr': {'addmark': '\u200E',
                    'removemark': '\u200F',
                    'is_right_to_left': False},
            'rtl': {'addmark': '\u200F',
                    'removemark': '\u200E',
                    'is_right_to_left': True},
        }
        if (directions[direction]['is_right_to_left']
            == itb_util.is_right_to_left(current_line)):
            LOGGER.debug(
                'Current_line already has desired direction %r, do nothing.',
                direction)
            return
        self.delete_surrounding_text(
            -cursor_pos_in_current_line, len(current_line))
        cursor_correction_chars_logical = current_line[cursor_pos_in_current_line:]
        # All chars I currently use in cmarkers have Bidi class “ON” (Other Neutrals)
        markers = ['_\ufffd_', # U+FFFD REPLACEMENT CHARACTER
                    '_\ufffc_', # U+FFFC OBJECT REPLACEMENT CHARACTER
                    '_☺_☺_☺_',  # some emoji
        ]
        cmarker = ''
        for marker in markers:
            if marker not in current_line:
                cmarker = marker
                break
        if not cmarker:
            LOGGER.debug('Could not find suitable cursor marker')
            return
        LOGGER.debug('Using cmarker=%r', cmarker)
        current_line_with_cmarker = (
            f'{current_line[:cursor_pos_in_current_line]}'
            f'{cmarker}'
            f'{current_line[cursor_pos_in_current_line:]}')
        is_right_to_left = directions[direction]['is_right_to_left']
        removemark = str(directions[direction]['removemark'])
        addmark = str(directions[direction]['addmark'])
        if current_line.startswith(removemark):
            LOGGER.debug('Wrong direction mark %r found, remove it.',
                         removemark)
            current_line = current_line[1:]
            current_line_with_cmarker = current_line_with_cmarker[1:]
        if is_right_to_left != itb_util.is_right_to_left(current_line):
            LOGGER.debug('Add direction mark %r', addmark)
            current_line = f'{addmark}{current_line}'
            current_line_with_cmarker = f'{addmark}{current_line_with_cmarker}'
            if is_right_to_left != itb_util.is_right_to_left(current_line):
                LOGGER.error('Line direction still wrong, should never happen.')
                return
        super().commit_text(
            IBus.Text.new_from_string(current_line))
        self._commit_happened_after_focus_in = True
        time.sleep(self._ibus_event_sleep_seconds)
        if re.compile(r'^QIBusInputContext:').search(self._im_client):
            LOGGER.debug('QIBusInputContext detected, correcting cursor.')
            arrow_key_value = IBus.KEY_Left
            if direction == 'rtl':
                arrow_key_value = IBus.KEY_Right
            for char in cursor_correction_chars_logical:
                LOGGER.debug('cursor correction char=%r category=%r',
                             char, unicodedata.category(char))
                if unicodedata.category(char) not in ('Mn',):
                    self._forward_generated_key_event(arrow_key_value)
        elif re.compile(r'^(gtk[3,4]-im|gnome-shell):').search(self._im_client):
            im_module = self._im_client.split(':')[0]
            LOGGER.debug('%r detected, trying to correct cursor.', im_module)
            if im_module == 'gtk4-im':
                LOGGER.debug('forward_key_event() does not work in “gtk4-im”, '
                             'cursor correction cannot not work.')
                return
            if im_module == 'gnome-shell':
                LOGGER.debug('gnome-shell, i.e. wayland input in '
                             'gnome wayland detected. Probably typing '
                             'into some Gtk program. But correcting '
                             'the cursor does not seem to work with '
                             'gnome wayland input. ')
                return
            if not IMPORT_BIDI_ALGORITHM_SUCCESSFUL:
                LOGGER.debug(
                    '"import bidi.algorithm" didn’t work, '
                    'no cursor correction possible. '
                    'Try `pip install --user python-bidi`')
                return
            new_line_with_cmarker = bidi.algorithm.get_display(
                current_line_with_cmarker)
            cmarker_pos = new_line_with_cmarker.find(cmarker)
            if cmarker_pos < 0:
                LOGGER.debug('Failed to find cursor marker in new line. '
                             'No cursor correction possible.')
                return
            arrow_key_value = IBus.KEY_Left
            cursor_correction_chars_display = new_line_with_cmarker[
                cmarker_pos+len(cmarker):]
            if direction == 'rtl':
                arrow_key_value = IBus.KEY_Right
                cursor_correction_chars_display = new_line_with_cmarker[
                    :cmarker_pos]
            LOGGER.debug('current_line_with_cmarker=%r, '
                         'new_line_with_cmarker=%r, '
                         'cmarker_pos=%d '
                         'cursor_correction_chars_display=%r',
                         current_line_with_cmarker,
                         new_line_with_cmarker,
                         cmarker_pos,
                         cursor_correction_chars_display)
            for char in cursor_correction_chars_display:
                LOGGER.debug('cursor correction char=%r category=%r',
                             char, unicodedata.category(char))
                if unicodedata.category(char) not in ('Mn',):
                    self._forward_generated_key_event(arrow_key_value)
        return

    def _command_change_line_direction_left_to_right(self) -> bool:
        '''Make the direction of the current line left-to-right'''
        self._change_line_direction('ltr')
        return True

    def _command_change_line_direction_right_to_left(self) -> bool:
        '''Make the direction of the current line right-to-left'''
        self._change_line_direction('rtl')
        return True

    def _command_change_line_direction_toggle(self) -> bool:
        '''Toggle the direction of the current line between
        left-to-right and right-to-left
        '''
        self._change_line_direction('toggle')
        return True

    def _command_commit(self) -> bool:
        '''Handle hotkey for the command “commit”

        :return: True if the key was completely handled, False if not.
        '''
        if self.is_empty() and not self._typed_compose_sequence:
            return False
        self._commit_current_input()
        return True

    def _command_commit_and_forward_key(self) -> bool:
        '''Handle hotkey for the command “commit_and_forward_key”

        :return: True if the key was completely handled, False if not.
        '''
        if self.is_empty() and not self._typed_compose_sequence:
            return False
        self._commit_current_input()
        return True

    def _command_commit_candidate_1(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_1”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(0, extra_text='')

    def _command_commit_candidate_1_plus_space(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_1_plus_space”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(0, extra_text=' ')

    def _command_remove_candidate_1(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_1”

        :return: True if the key was completely handled, False if not.
        '''
        return self._remove_candidate(0)

    def _command_commit_candidate_2(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_2”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(1, extra_text='')

    def _command_commit_candidate_2_plus_space(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_2_plus_space”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(1, extra_text=' ')

    def _command_remove_candidate_2(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_2”

        :return: True if the key was completely handled, False if not.
        '''
        return self._remove_candidate(1)

    def _command_commit_candidate_3(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_3”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(2, extra_text='')

    def _command_commit_candidate_3_plus_space(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_3_plus_space”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(2, extra_text=' ')

    def _command_remove_candidate_3(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_3”

        :return: True if the key was completely handled, False if not.
        '''
        return self._remove_candidate(2)

    def _command_commit_candidate_4(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_4”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(3, extra_text='')

    def _command_commit_candidate_4_plus_space(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_4_plus_space”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(3, extra_text=' ')

    def _command_remove_candidate_4(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_4”

        :return: True if the key was completely handled, False if not.
        '''
        return self._remove_candidate(3)

    def _command_commit_candidate_5(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_5”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(4, extra_text='')

    def _command_commit_candidate_5_plus_space(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_5_plus_space”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(4, extra_text=' ')

    def _command_remove_candidate_5(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_5”

        :return: True if the key was completely handled, False if not.
        '''
        return self._remove_candidate(4)

    def _command_commit_candidate_6(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_6”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(5, extra_text='')

    def _command_commit_candidate_6_plus_space(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_6_plus_space”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(5, extra_text=' ')

    def _command_remove_candidate_6(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_6”

        :return: True if the key was completely handled, False if not.
        '''
        return self._remove_candidate(5)

    def _command_commit_candidate_7(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_7”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(6, extra_text='')

    def _command_commit_candidate_7_plus_space(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_7_plus_space”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(6, extra_text=' ')

    def _command_remove_candidate_7(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_7”

        :return: True if the key was completely handled, False if not.
        '''
        return self._remove_candidate(6)

    def _command_commit_candidate_8(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_8”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(7, extra_text='')

    def _command_commit_candidate_8_plus_space(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_8_plus_space”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(7, extra_text=' ')

    def _command_remove_candidate_8(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_8”

        :return: True if the key was completely handled, False if not.
        '''
        return self._remove_candidate(7)

    def _command_commit_candidate_9(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_9”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(8, extra_text='')

    def _command_commit_candidate_9_plus_space(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_9_plus_space”

        :return: True if the key was completely handled, False if not.
        '''
        return self._commit_candidate(8, extra_text=' ')

    def _command_remove_candidate_9(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_9”

        :return: True if the key was completely handled, False if not.
        '''
        return self._remove_candidate(8)

    def _handle_hotkeys(
            self,
            key: itb_util.KeyEvent,
            commands: Iterable[str] = ()) -> Tuple[bool, bool]:
        '''Handle hotkey commands

        :return: A tuple of too boolean values (match, return_value)
                 “match” is true if the hotkey matched, false if not
                 “return_value” is the value which should be returned
                 from do_process_key_event().
        :param key: The typed key. If this is a hotkey,
                    execute the command for this hotkey.
        :param commands: A list of commands to check whether
                         the key matches the keybinding for one of
                         these commands.
                         If the list of commands is empty, check
                         *all* commands in the self._keybindings
                         dictionary.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('KeyEvent object: %s\n', key)
        if DEBUG_LEVEL > 5:
            LOGGER.debug('self._hotkeys=%s\n', str(self._hotkeys))

        if not commands:
            # If no specific command list to match is given, try to
            # match against all commands. Sorting shouldn’t really
            # matter, but maybe better do it sorted, then it is done
            # in the same order as the commands are displayed in the
            # setup tool.
            commands = sorted(self._keybindings.keys())
        hotkey_removed_from_compose_sequence = False
        for command in commands:
            if (self._prev_key, key, command) in self._hotkeys: # type: ignore
                if DEBUG_LEVEL > 1:
                    LOGGER.debug('matched command=%s', command)
                if (self._typed_compose_sequence
                    and not hotkey_removed_from_compose_sequence):
                    compose_result = self._compose_sequences.compose(
                        self._typed_compose_sequence)
                    if compose_result != '':
                        # If the hotkey did not make the compose
                        # sequence invalid, the hotkey is apparently
                        # part of a valid compose sequence.  That has
                        # priority so it cannot be used as a hotkey in
                        # that case
                        return (False, False)
                    self._typed_compose_sequence.pop()
                    self._update_transliterated_strings()
                    self._update_preedit()
                    hotkey_removed_from_compose_sequence = True
                command_function_name = f'_command_{command}'
                try:
                    command_function = getattr(self, command_function_name)
                except (AttributeError,):
                    LOGGER.exception('There is no function %s',
                                     command_function_name)
                    if hotkey_removed_from_compose_sequence:
                        self._typed_compose_sequence.append(key.val)
                    return (False, False)
                if command_function():
                    if key.name in ('Shift_L', 'Shift_R',
                                    'Control_L', 'Control_R',
                                    'Alt_L', 'Alt_R',
                                    'Meta_L', 'Meta_R',
                                    'Super_L', 'Super_R',
                                    'ISO_Level3_Shift'):
                        return (True, False)
                    if command in ('commit_and_forward_key',):
                        return (True, False)
                    return (True, True)
        if hotkey_removed_from_compose_sequence:
            self._typed_compose_sequence.append(key.val)
        return (False, False)

    def _return_true(self, key: itb_util.KeyEvent) -> bool:
        '''A replacement for “return True” in do_process_key_event()

        do_process_key_event() should return “True” if a key event has
        been handled completely. It should return “False” if the key
        event should be passed to the application.
        '''
        if DEBUG_LEVEL > 0:
            LOGGER.info('key=%s', key)
        self._prev_key = key
        self._prev_key.time = time.time()
        self._prev_key.handled = True
        self._set_surrounding_text_event.clear()
        self._surrounding_text_old = self.get_surrounding_text()
        return True

    def _return_false(self, key: itb_util.KeyEvent) -> bool:
        '''A replacement for “return False” in do_process_key_event()

        do_process_key_event() should return “True” if a key event has
        been handled completely. It should return “False” if the key
        event should be passed to the application.

        But just doing “return False” has many problems.

        1) It doesn’t work well when trying to do the unit
        tests. The MockEngine class in the unit tests cannot get that
        return value. Therefore, it cannot do the necessary updates to
        the self._mock_committed_text etc. which prevents proper
        testing of the effects of such keys passed to the application.

        2) It does *not* work when using XIM, i.e. *not* when using Qt
        with the XIM module and *not* in X11 applications like xterm.
        When “return False” is used with XIM, the key event which
        triggered the commit here arrives *before* the committed
        string. I.e. when typing “word ” the space which triggered the
        commit gets to application first and the applications receives
        “ word”. No amount of sleep before the “return False” can fix
        this. See: https://bugzilla.redhat.com/show_bug.cgi?id=1291238

        3) “return False” fails to work correctly when the key.code is
        incorrect. The on-screen-keyboard (OSK) often seems to pass
        key events which have key.code == 0, instead of a correct
        key.code. “return False” then does not work, the application
        receives nothing at all.

        To work around the problems with “return False”, one can
        sometimes use self.forward_key_event(key.val, key.code,
        key.state) instead to pass the key to the application.  This
        works fine with the unit tests because a forward_key_event()
        function is implemented in MockEngine as well which then gets
        the key and can test its effects. As far as the unit tests are
        concerned, it does not matter whether the key.code is correct
        or incorrectly key.code == 0.

        But when forward_key_event() is used “for real”, i.e. when not
        doing unit testing, it has the same problem as “return False”
        that it does nothing at all when key.code is 0, which is often
        the case when the on-screen-keyboard OSK is
        used. ibus-typing-booster can fix that in many or even most
        cases by getting a correct key.code for key.val from the
        current keyboard layout, but there are circumstances when this
        is also not possible.

        On top of that, “forward_key_event()” does not work at all in
        some environments even if OSK is not involved:

        - Qt4 when using the input module and not XIM
        - older versions of Qt5
        - older versions of Wayland
        - Gtk4

        So using “forward_key_event()” instead of “return False”
        in “do_process_key_event()” helps in some cases, but there
        are cases when this fails as well.

        A third possibility to pass a key to the application can
        sometimes be to commit something instead of using
        forward_key_event() or “return False”. When committing is
        possible, it seems to be the most reliable option, no problems
        with the order of things as in the “return False” with XIM
        case and no problems when the key.code is incorrectly 0.

        But committing is also not always possible, for example
        key.unicode needs to be a non-empty string in order to make
        committing something possible. And even then it does not
        always make sense, for example when key.val is
        IBus.KEY_Return, key.unicode is '\r' but committing that does
        not have the desired effect of breaking a line. And key
        release events as well as events where modifiers like Control,
        Alt, ... are set should not be committed but really passed
        through to the application.

        To work around these problems as good as possible we use this
        helper function which

        - prefers a commit if possible
        - if committing is not possible, but forward_key_event()
          is possible, use forward_key_event() and try to fix
          key.code in case it is incorrectly set to 0 by OSK (unless
          unit testing, then the key.code does not matter)
        - if committing is not possible and forward_key_event()
          is is not possible either, fall back to the worst option
          “return False”.
        '''
        if DEBUG_LEVEL > 0:
            LOGGER.info('key=%s', key)
        self._prev_key = key
        self._prev_key.time = time.time()
        self._prev_key.handled = False
        self._set_surrounding_text_event.clear()
        self._surrounding_text_old = self.get_surrounding_text()
        if not key.code:
            LOGGER.warning(
                'key.code=0 is not a valid keycode. Probably caused by OSK.')
        # If it is possible to commit instead of forwarding a key event
        # or doing a “return False”, prefer the commit:
        if (key.unicode
            and unicodedata.category(key.unicode) not in ('Cc',)
            and (key.val not in (
                IBus.KEY_Return, IBus.KEY_KP_Enter, IBus.KEY_ISO_Enter,
                IBus.KEY_BackSpace, IBus.KEY_Delete))
            and not key.state & IBus.ModifierType.RELEASE_MASK
            and not key.state & itb_util.KEYBINDING_STATE_MASK):
            if DEBUG_LEVEL > 0:
                LOGGER.info('Committing instead of forwarding or “return False”')
            super().commit_text(
                IBus.Text.new_from_string(key.unicode))
            self._commit_happened_after_focus_in = True
            self._prev_key.handled = True
            return True
        # When unit testing, forward the key event if a commit was not possible.
        # “return False” doesn’t work well when doing unit testing because the
        # MockEngine class cannot get that return value.
        # The keycode does not matter here, we do not care whether it is correct
        # or not when doing unit testing.
        if self._unit_test:
            self.forward_key_event(key.val, key.code, key.state)
            return True
        if (self._avoid_forward_key_event
            or self._im_client.startswith('gtk4-im')
            or
            (self.client_capabilities & itb_util.Capabilite.SYNC_PROCESS_KEY)):
            if DEBUG_LEVEL > 0:
                LOGGER.info('Returning False')
            return False
        if (self._im_client.startswith('gnome-shell')
            and os.getenv('XDG_SESSION_TYPE') == 'wayland'
            and ((key.shift and key.name in
                  ('F1', 'F2', 'F3', 'F4', 'F5', 'F6',
                   'F7', 'F8', 'F9', 'F10', 'F11', 'F12'))
                 or key.control
                 or key.super
                 or key.hyper
                 or key.meta
                 or key.mod1
                 or key.mod4)):
            # https://github.com/mike-fabian/ibus-typing-booster/issues/507
            # Gnome keyboard shortcuts with modifiers don’t work anymore when
            # such a key is forwarded (since Fedora 40, Gnome 46.0).
            LOGGER.info(
                'Returning False: '
                'gnome-shell client in wayland session and possibly '
                'a Gnome keyboard shortcut involving a modifier. ')
            return False
        if not key.code:
            LOGGER.info(
                'key.code= %s, probably coming from OSK, try to fix it ...',
                key.code)
            key.code = self._keyvals_to_keycodes.ibus_keycode(key.val)
            if key.code:
                LOGGER.info('Fixed key.code = %s', key.code)
            else:
                LOGGER.info('Could not fix key.code, still key.code == 0')
        if DEBUG_LEVEL > 0:
            LOGGER.info('Forwarding key event')
        self.forward_key_event(key.val, key.code, key.state)
        return True

    def _forward_generated_key_event(self, keyval: int) -> None:
        '''Forward a generated key event for keyval to the application.'''
        # Without using a correct ibus key code, this does not work
        # correctly, i.e. something like
        # self.forward_key_event(IBus.KEY_Left, 0, 0) used to work
        # (once upon a time) but it does *not* work anymore now!
        #
        # The ibus key code for IBus.KEY_Left is usually 105, but it
        # could be different on an unusual keyboard layout.  So do not
        # hardcode keycodes here, calculate them correctly for the
        # current layout.
        if not self._unit_test and self._avoid_forward_key_event:
            if DEBUG_LEVEL > 0:
                LOGGER.debug(
                    'return without doing anything because '
                    'self._avoid_forward_key_event is True. '
                    'keyval=%s', keyval)
            return
        keycode = self._keyvals_to_keycodes.keycode(keyval)
        ibus_keycode = self._keyvals_to_keycodes.ibus_keycode(keyval)
        keystate = 0
        if DEBUG_LEVEL > 0:
            LOGGER.debug('keyval=%s keycode=%s ibus_keycode=%s keystate=%s',
                         keyval, keycode, ibus_keycode, keystate)
        self.forward_key_event(keyval, ibus_keycode, keystate)

    def _play_error_sound(self) -> None:
        '''Play an error sound if enabled and possible'''
        if self._error_sound and self._error_sound_object:
            try:
                self._error_sound_object.play()
            except Exception as error: # pylint: disable=broad-except
                LOGGER.exception('Playing error sound failed: %s: %s',
                                 error.__class__.__name__, error)

    def _handle_compose(self, key: itb_util.KeyEvent, add_to_preedit: bool = True) -> bool:
        '''Internal method to handle possible compose keys

        :return: True if the key event has been handled, else False
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('KeyEvent object: %s', key)
        if key.state & IBus.ModifierType.RELEASE_MASK:
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Ignoring release event.')
            return False
        if (not self._typed_compose_sequence
            and not self._compose_sequences.is_start_key(key.val)):
            if DEBUG_LEVEL > 1:
                LOGGER.debug(
                    'Not in a compose sequence and the key cannot '
                    'start a compose sequence either. '
                    'Key Event object: %s', key)
            return False
        if (not self._typed_compose_sequence
            and not self._is_candidate_auto_selected
            and self.get_lookup_table().get_number_of_candidates()
            and self.get_lookup_table().cursor_visible):
            # A new compose sequence has just started *and*
            # something is *manually* selected in the lookup
            # table, replace the typed string with the selection
            # and move the cursor to the end:
            self._typed_string = list(
                self.get_string_from_lookup_table_cursor_pos())
            self._typed_string_cursor = len(self._typed_string)
        if (key.val in
            (IBus.KEY_Shift_R,
             IBus.KEY_Shift_L,
             IBus.KEY_ISO_Level3_Shift,
             IBus.KEY_Control_L,
             IBus.KEY_Control_R,
             IBus.KEY_Alt_L,
             IBus.KEY_Alt_R,
             IBus.KEY_Meta_L,
             IBus.KEY_Meta_R,
             IBus.KEY_Super_L,
             IBus.KEY_Super_R)):
            # Ignoring Shift_R, Shift_L, and ISO_Level3_Shift is
            # necessary, they should not be added to the compose
            # sequence because they usually modify the next key and
            # only the result of that modified next key press should
            # be added to the compose sequence.
            #
            # Ignoring the other modifiers seems optional ...
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Inside compose sequence, ignoring key %s',
                             IBus.keyval_name(key.val))
            return True
        if key.val in (IBus.KEY_BackSpace,):
            self._typed_compose_sequence.pop()
        else:
            self._typed_compose_sequence.append(key.val)
        if not self._typed_compose_sequence:
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Editing made the compose sequence empty.')
            self._lookup_table_shows_compose_completions = False
            self._update_transliterated_strings()
            self._update_ui()
            return True
        compose_result = self._compose_sequences.compose(
            self._typed_compose_sequence)
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'Inside compose sequence.'
                'key value names=%s '
                'compose_result=%s',
                [IBus.keyval_name(val)
                 for val in self._typed_compose_sequence],
                repr(compose_result))
        (match, return_value) = self._handle_hotkeys(
                key, commands=['cancel',
                               'change_line_direction_left_to_right',
                               'change_line_direction_right_to_left',
                               'change_line_direction_toggle',
                               'commit',
                               'commit_and_forward_key',
                               'toggle_input_mode_on_off',
                               'enable_lookup',
                               'select_next_candidate',
                               'select_previous_candidate',
                               'lookup_table_page_down',
                               'lookup_table_page_up',
                               'commit_candidate_1',
                               'commit_candidate_1_plus_space',
                               'commit_candidate_2',
                               'commit_candidate_2_plus_space',
                               'commit_candidate_3',
                               'commit_candidate_3_plus_space',
                               'commit_candidate_4',
                               'commit_candidate_4_plus_space',
                               'commit_candidate_5',
                               'commit_candidate_5_plus_space',
                               'commit_candidate_6',
                               'commit_candidate_6_plus_space',
                               'commit_candidate_7',
                               'commit_candidate_7_plus_space',
                               'commit_candidate_8',
                               'commit_candidate_8_plus_space',
                               'commit_candidate_9',
                               'commit_candidate_9_plus_space'])
        if match:
            return return_value
        if (self._lookup_table_shows_compose_completions
            and self.get_lookup_table().cursor_visible):
            # something is manually selected in the compose lookup table
            self._lookup_table_shows_compose_completions = False
            compose_result = self.get_string_from_lookup_table_cursor_pos()
            self._candidates = []
            self.get_lookup_table().clear()
            self.get_lookup_table().set_cursor_visible(False)
            self._update_lookup_table_and_aux()
            self._typed_compose_sequence = []
            self._update_transliterated_strings()
            self._update_preedit()
            if add_to_preedit:
                self._insert_string_at_cursor(list(compose_result))
                self._update_ui()
                return False
            super().commit_text(
                IBus.Text.new_from_string(compose_result))
            self._commit_happened_after_focus_in = True
            return False
        self._lookup_table_shows_compose_completions = False
        self._candidates = []
        self.get_lookup_table().clear()
        self.get_lookup_table().set_cursor_visible(False)
        self.hide_lookup_table()
        self._lookup_table_hidden = True
        self._current_auxiliary_text = IBus.Text.new_from_string('')
        super().update_auxiliary_text(
            self._current_auxiliary_text, False)
        if not isinstance(compose_result, str):
            # compose sequence is unfinished
            self._update_transliterated_strings()
            self._update_preedit()
            return True
        if not compose_result:
            if DEBUG_LEVEL > 1:
                LOGGER.debug(
                    'Last key made compose sequence invalid, remove it.')
            self._typed_compose_sequence.pop()
            self._update_transliterated_strings()
            self._update_preedit()
            if key.val in self._commit_trigger_keys:
                # The key which made the compose sequence invalid
                # might usually (i.e. outside of compose sequences)
                # trigger a commit in ibus-typing-booster.
                #
                # For all these keys it seems a good idea to me to
                # accept the current compose preedit representation
                # as the final result of the compose sequence
                # and continue, passing the key through.
                preedit_representation = (
                    self._compose_sequences.preedit_representation(
                        self._typed_compose_sequence))
                self._typed_compose_sequence = []
                self._update_transliterated_strings()
                self._update_preedit()
                if add_to_preedit:
                    # When not in direct input mode insert the current
                    # compose preedit representation into the typed
                    # string and return False to let processing of the
                    # key continue.
                    # (Even if the the currently typed string is not empty!)
                    self._insert_string_at_cursor(list(preedit_representation))
                    self._update_ui()
                    return False
                # When in direct input mode commit immediately and
                # return False to let processing of the key
                # continue:
                super().commit_text(
                    IBus.Text.new_from_string(preedit_representation))
                self._commit_happened_after_focus_in = True
                return False
            self._play_error_sound()
            return True
        if DEBUG_LEVEL > 1:
            LOGGER.debug('Compose sequence finished.')
        self._typed_compose_sequence = []
        self._update_transliterated_strings()
        if add_to_preedit:
            self._insert_string_at_cursor(list(compose_result))
            self._update_ui()
            return True
        super().commit_text(
            IBus.Text.new_from_string(compose_result))
        self._commit_happened_after_focus_in = True
        if not self._current_preedit_text:
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Avoid clearing already empty preedit.')
            return True
        super().update_preedit_text_with_mode(
            IBus.Text.new_from_string(''), 0, False,
            IBus.PreeditFocusMode.COMMIT)
        self._current_preedit_text = ''
        return True

    def do_process_key_event( # pylint: disable=arguments-differ
            self, keyval: int, keycode: int, state: int) -> bool:
        '''Process Key Events
        Key Events include Key Press and Key Release,
        modifier means Key Pressed
        '''
        key = itb_util.KeyEvent(keyval, keycode, state)
        if DEBUG_LEVEL > 1:
            LOGGER.debug('KeyEvent object: %s', key)

        disabled = False
        if not self._input_mode:
            if DEBUG_LEVEL > 0:
                LOGGER.debug('Direct input mode')
            disabled = True
        elif (self._disable_in_terminals
              and itb_util.detect_terminal(self._input_purpose, self._im_client)):
            if DEBUG_LEVEL > 0:
                LOGGER.debug(
                    'Terminal detected and the option '
                    'to disable in terminals is set.')
            disabled = True
        elif (self.client_capabilities & itb_util.Capabilite.OSK
              and
              (self._input_purpose in [itb_util.InputPurpose.TERMINAL.value])):
            if DEBUG_LEVEL > 0:
                LOGGER.debug(
                    'OSK is visible and input purpose is TERMINAL, '
                    'disable to avoid showing passwords in the '
                    'OSK completion buttons.')
            disabled = True
        elif (self._input_purpose
              in [itb_util.InputPurpose.PASSWORD.value,
                  itb_util.InputPurpose.PIN.value]):
            if DEBUG_LEVEL > 0:
                LOGGER.debug(
                    'Disable because of input purpose PASSWORD or PIN')
            disabled = True

        if self._handle_compose(key, add_to_preedit=not disabled):
            return self._return_true(key)

        (match, return_value) = self._handle_hotkeys(
            key, commands=['toggle_input_mode_on_off',
                           'change_line_direction_left_to_right',
                           'change_line_direction_right_to_left',
                           'change_line_direction_toggle'])
        if match:
            if return_value:
                return self._return_true(key)
            return self._return_false(key)

        if disabled:
            return self._return_false(key)

        (match, return_value) = self._handle_hotkeys(key)
        if match:
            if return_value:
                return self._return_true(key)
            return self._return_false(key)

        result = self._process_key_event(key)
        if result:
            return self._return_true(key)
        return self._return_false(key)

    def _process_key_event(self, key: itb_util.KeyEvent) -> bool:
        '''Internal method to process key event

        :return: True if the key event has been completely handled by
                 ibus-typing-booster and should not be passed through anymore.
                 False if the key event has not been handled completely
                 and is passed through.
        '''
        # Ignore (almost all) key release events
        if key.release:
            if self._maybe_reopen_preedit(key):
                if DEBUG_LEVEL > 1:
                    LOGGER.debug('Preedit reopened successfully.')
            if (self._prev_key is not None
                and self._prev_key.handled
                and not self._prev_key.release
                and self._prev_key.val == key.val):
                if DEBUG_LEVEL > 0:
                    LOGGER.info('Press key event was handled. '
                                'Do not pass release key event.')
                return True
            return False

        if self.is_empty() and not self._lookup_table.cursor_visible:
            if DEBUG_LEVEL > 1:
                LOGGER.debug(
                    'self.is_empty(): KeyEvent object: %s', key)
            # This is the first character typed since the last commit
            # there is nothing in the preëdit yet.
            if key.val < 32 or key.val == IBus.KEY_Escape:
                # If the first character of a new word is a control
                # character, return False to pass the character through as is,
                # it makes no sense trying to complete something
                # starting with a control character:
                self._update_ui_empty_input()
                return False
            if key.val == IBus.KEY_space and not key.mod5:
                # if the first character is a space, just pass it through
                # it makes not sense trying to complete (“not key.mod5” is
                # checked here because AltGr+Space is the key binding to
                # insert a literal space into the preëdit):
                self._update_ui_empty_input()
                return False
            if (key.val >= 32 and not key.control
                and not self._tab_enable
                and key.msymbol
                in ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9')):
                # if key.msymbol is for example 'G-4', then for
                # example with hi-inscript2 it is transliterated to ₹
                # INDIAN RUPEE SIGN.  Such things can be added to the
                # preedit, no need to commit them immediately here.
                if ((key.val in
                     (IBus.KEY_0, IBus.KEY_1, IBus.KEY_2, IBus.KEY_3,
                      IBus.KEY_4, IBus.KEY_5, IBus.KEY_6, IBus.KEY_7,
                      IBus.KEY_8, IBus.KEY_9)
                     and self._normal_digits_used_in_keybindings)
                    or
                    (key.val in
                     (IBus.KP_0, IBus.KP_1, IBus.KP_2, IBus.KP_3,
                      IBus.KP_4, IBus.KP_5, IBus.KP_6, IBus.KP_7,
                      IBus.KP_8, IBus.KP_9)
                     and self._keypad_digits_used_in_keybindings)):
                    # If digits are used as keys to select candidates
                    # it is not possibly to type them while the preëdit
                    # is non-empty and candidates are displayed.
                    # In that case we have to make it possible to
                    # type digits here where the preëdit is still empty.
                    # If digits are not used to select candidates, they
                    # can be treated just like any other input keys.
                    #
                    # When self._tab_enable is on, the candidate list
                    # is only shown when explicitely requested by Tab.
                    # Therefore, in that case digits can be typed
                    # normally as well until the candidate list is
                    # opened.  Putting a digit into the candidate list
                    # is better in that case, one may be able to get a
                    # reasonable completion that way.
                    if self.get_current_imes()[0] == 'NoIME':
                        # If a digit has been typed and no transliteration
                        # is used, we can pass it through
                        self._update_ui_empty_input()
                        return False
                    # If a digit has been typed and we use
                    # transliteration, we may want to convert it to
                    # native digits. For example, with mr-inscript we
                    # want “3” to be converted to “३”. So we try
                    # to transliterate and commit the result:
                    transliterated_digit = self._transliterators[
                        self.get_current_imes()[0]
                    ].transliterate([key.msymbol],
                                    ascii_digits=self._ascii_digits)
                    self._commit_string(
                        transliterated_digit,
                        input_phrase=transliterated_digit)
                    self._clear_input()
                    self._update_ui_empty_input()
                    return True

        # These keys may trigger a commit:
        if (key.msymbol not in ('G- ', 'G-_')
            and (key.val in self._commit_trigger_keys
                 or (len(key.msymbol) == 1
                     and (key.control
                          or key.mod1 # mod1: Usually Alt
                          or key.super or key.hyper or key.meta))
                 or (len(key.msymbol) == 3
                     and key.msymbol[:2] in ('A-', 'C-', 'G-')
                     and not self._has_transliteration([key.msymbol])))):
                # See:
                # https://bugzilla.redhat.com/show_bug.cgi?id=1351748
                # If the user types a modifier key combination, it
                # might have a transliteration in some input methods.
                # For example, AltGr-4 (key.msymbol = 'G-4')
                # transliterates to ₹ when the “hi-inscript2” input
                # method is used.  But trying to handle all modifier
                # key combinations as input is not nice because it
                # prevents the use of such key combinations for other
                # purposes.  C-c is usually used for for copying, C-v
                # for pasting for example. If the user has typed a
                # modifier key combination, check whether any of the
                # current input methods actually transliterates it to
                # something. If none of the current input methods uses
                # it, the key combination can be passed through to be
                # used for its original purpose.  If the preëdit is
                # non empty, commit the preëdit first before passing
                # the modifier key combination through. (Passing
                # something like C-a through without committing the
                # preëdit would be quite confusing, C-a usually goes
                # to the beginning of the current line, leaving the
                # preëdit open while moving would be strange).
                #
                # Up, Down, Page_Up, and Page_Down may trigger a
                # commit if no lookup table is shown because the
                # option to show a lookup table only on request by
                # typing tab is used and no lookup table is shown at
                # the moment.
                #
                # 'G- ' (AltGr-Space) is prevented from triggering
                # a commit here, because it is used to enter spaces
                # into the preëdit, if possible. Same for 'G-_',
                # it is prevented from triggering a commit because
                # it is used to enter underscores into the preedit
                # for emoji lookup.
                #
                # If key.msymbol is a single character and Control,
                # Alt, Super, Hyper, or Meta is pressed, commit the
                # preedit and pass the key to the application because
                # the user probably tried to use a keyboard shortcut
                # like Control+a on a keyboard layout which does not
                # produce ASCII, for example the Greek keyboard layout
                # (On a keyboard layout which produces ASCII,
                # Control+a would result in key.msymbol == 'C-a' and
                # this would also trigger a commit unless 'C-a' is
                # transliterated to something).  See:
                # https://github.com/mike-fabian/ibus-typing-booster/issues/107
            if self.is_empty() and not self._lookup_table.cursor_visible:
                self._update_ui_empty_input()
                return False
            preedit_ime = self._current_imes[0]
            # Support 'S-C-Return' as commit to preedit if the current
            # preedit_ime needs it:
            # https://github.com/mike-fabian/ibus-typing-booster/issues/457
            if (not self.is_empty() and key.msymbol == 'S-C-Return'
                and
                self._transliterators[
                    preedit_ime].transliterate(
                        self._typed_string + [key.msymbol],
                        ascii_digits=self._ascii_digits)
                != self._transliterated_strings[preedit_ime] + 'S-C-Return'):
                self._insert_string_at_cursor([key.msymbol])
                self._update_ui()
                return True
            if (not key.shift and (not self.get_lookup_table().cursor_visible
                                   or self._is_candidate_auto_selected)):
                # Nothing is *manually* selected in the lookup table,
                # the edit keys like space, Tab, Right, Left, BackSpace, and
                # Delete edit the preëdit (If something is selected in
                # the lookup table, they should cause a commit,
                # especially when inline completion is used and the
                # first candidate is selected, editing the preëdit is
                # confusing). But only do this if Shift is not used!
                # With Shift many of these keys should commit instead
                # and select some text.
                if (key.val in (IBus.KEY_Right, IBus.KEY_KP_Right)
                    and (self._typed_string_cursor
                         < len(self._typed_string))):
                    if key.control:
                        # Move cursor to the end of the typed string
                        self._typed_string_cursor = len(self._typed_string)
                    else:
                        self._typed_string_cursor += 1
                    self._update_preedit()
                    self._update_lookup_table_and_aux()
                    return True
                if (key.val in (IBus.KEY_Left, IBus.KEY_KP_Left)
                    and self._typed_string_cursor > 0):
                    if key.control:
                        # Move cursor to the beginning of the typed string
                        self._typed_string_cursor = 0
                    else:
                        self._typed_string_cursor -= 1
                    self._update_preedit()
                    self._update_lookup_table_and_aux()
                    return True
                if (key.val in (IBus.KEY_BackSpace,)
                    and self._typed_string_cursor > 0):
                    self.is_lookup_table_enabled_by_tab = False
                    self.is_lookup_table_enabled_by_min_char_complete = False
                    if key.control:
                        self._remove_string_before_cursor()
                    else:
                        self._remove_character_before_cursor()
                    if self.is_empty():
                        self._new_sentence = False
                        self._current_case_mode = 'orig'
                    self._update_ui()
                    return True
                if (key.val in (IBus.KEY_Delete, IBus.KEY_KP_Delete)
                    and self._typed_string_cursor < len(self._typed_string)):
                    self.is_lookup_table_enabled_by_tab = False
                    self.is_lookup_table_enabled_by_min_char_complete = False
                    if key.control:
                        self._remove_string_after_cursor()
                    else:
                        self._remove_character_after_cursor()
                    if self.is_empty():
                        self._new_sentence = False
                        self._current_case_mode = 'orig'
                    self._update_ui()
                    return True
            if (not key.shift and (self.get_lookup_table().cursor_visible
                                   and not self._is_candidate_auto_selected)):
                # something is manually selected in the lookup table
                # and Shift is not used (When Shift is used, continue
                # to trigger a commit):
                if key.val in (IBus.KEY_Left, IBus.KEY_KP_Left,
                               IBus.KEY_BackSpace):
                    # Left and BackSpace are a bit special compared to
                    # the other keys which might trigger a commit: If
                    # these keys are pressed while something is
                    # manually selected in the lookup table and that
                    # selection would be committed and the key passed
                    # through, the cursor would end up within the word
                    # just committed. And then it would be useful to
                    # put that word into preedit again. But that is
                    # difficult to do and surrounding text is not
                    # reliable so it is better to not commit it in the
                    # first place, just replace the typed string with
                    # the selection, move the cursor to the end, and
                    # then handle the key:
                    self._typed_string = list(
                        self.get_string_from_lookup_table_cursor_pos())
                    self._typed_string_cursor = len(self._typed_string)
                    self._update_transliterated_strings()
                if (key.val in (IBus.KEY_Left, IBus.KEY_KP_Left)
                    and self._typed_string_cursor > 0):
                    self.is_lookup_table_enabled_by_tab = False
                    self.is_lookup_table_enabled_by_min_char_complete = False
                    if key.control:
                        # Move cursor to the beginning of the typed string
                        self._typed_string_cursor = 0
                    else:
                        self._typed_string_cursor -= 1
                    self._update_ui()
                    return True
                if (key.val in (IBus.KEY_BackSpace,)
                    and self._typed_string_cursor > 0):
                    self.is_lookup_table_enabled_by_tab = False
                    self.is_lookup_table_enabled_by_min_char_complete = False
                    if key.control:
                        self._remove_string_before_cursor()
                    else:
                        self._remove_character_before_cursor()
                    if self.is_empty():
                        self._new_sentence = False
                        self._current_case_mode = 'orig'
                    self._update_ui()
                    return True
            # This key does not only do a cursor movement in the preëdit,
            # it really triggers a commit.
            if DEBUG_LEVEL > 1:
                LOGGER.debug('_process_key_event() commit triggered.\n')
            # We need to transliterate
            # the preëdit again here, because adding the commit key to
            # the input might influence the transliteration. For example
            # When using hi-itrans, “. ” translates to “। ”
            # (See: https://bugzilla.redhat.com/show_bug.cgi?id=1353672)
            input_phrase = self._transliterators[
                preedit_ime].transliterate(
                    self._typed_string + [key.msymbol],
                    ascii_digits=self._ascii_digits)
            input_phrase = self._case_modes[
                self._current_case_mode]['function'](input_phrase)
            if key.msymbol:
                if input_phrase.endswith(key.msymbol):
                    # If the transliteration now ends with the commit
                    # key, cut it off because the commit key is passed
                    # to the application later anyway and we do not
                    # want to pass it twice:
                    input_phrase = input_phrase[:-len(key.msymbol)]
                else:
                    # The commit key has been absorbed by the
                    # transliteration.  Add the key to the input
                    # instead of committing:
                    if DEBUG_LEVEL > 1:
                        LOGGER.debug(
                            'Insert instead of commit: key.msymbol=“%s”',
                            key.msymbol)
                    self._insert_string_at_cursor([key.msymbol])
                    self._update_ui()
                    return True
            if (self.get_lookup_table().get_number_of_candidates()
                and self.get_lookup_table().cursor_visible):
                # something is selected in the lookup table, commit
                # the selected phrase
                commit_string = self.get_string_from_lookup_table_cursor_pos()
            elif (key.val in (IBus.KEY_space, IBus.KEY_Tab)
                  and self._typed_string_cursor == 0):
                # “space” or “Tab” is typed while the cursor is at the
                # beginning of the preedit *and* nothing is selected
                # in the lookup table. Commit the space or Tab.  The
                # preedit and lookup table should move one or more
                # columns to the right.  (Tab rarely has this effect
                # here because it is bound to “select_next_candidate”
                # by default!)
                #
                # As the cursor is still at the beginning of the
                # preedit, don’t commit the preedit. As reopening a
                # preedit from surrounding text is always difficult,
                # better keep it if it makes sense.
                if key.val == IBus.KEY_Tab:
                    super().commit_text(IBus.Text.new_from_string('\t'))
                else:
                    super().commit_text(IBus.Text.new_from_string(' '))
                self._commit_happened_after_focus_in = True
                self._update_ui()
                return True
            elif (key.val in (IBus.KEY_space, IBus.KEY_Tab,
                              IBus.KEY_Return, IBus.KEY_KP_Enter)
                  and (self._typed_string_cursor
                       < len(self._typed_string))):
                # “space”, “Tab”, “Return”, or “KP_Enter” is used to
                # commit the preëdit while the cursor is not at the
                # end of the preëdit.  That means the parts of the
                # preëdit to the left of and to the right of the
                # cursor should be committed seperately, the cursor
                # then moved between the two comitted parts and then
                # the key which triggered the commit should be
                # forwarded to the application.
                input_phrase_left = (
                    self._transliterators[preedit_ime].transliterate(
                        self._typed_string[:self._typed_string_cursor],
                        ascii_digits=self._ascii_digits))
                input_phrase_left = self._case_modes[
                    self._current_case_mode]['function'](input_phrase_left)
                input_phrase_right = (
                    self._transliterators[preedit_ime].transliterate(
                        self._typed_string[self._typed_string_cursor:],
                        ascii_digits=self._ascii_digits))
                if self._current_case_mode == 'upper':
                    input_phrase_right = self._case_modes[
                        self._current_case_mode]['function'](
                            input_phrase_right)
                if input_phrase_left:
                    self._commit_string(
                        input_phrase_left, input_phrase=input_phrase_left,
                        fix_sentence_end=False)
                # Cursor will end up to the left of input_phrase_right
                # so don’t push input_phrase_right on the context stack
                # when committing:
                if input_phrase_right:
                    self._commit_string(
                        input_phrase_right, input_phrase=input_phrase_right,
                        push_context=False,
                        fix_sentence_end=False)
                self._clear_input_and_update_ui()
                # These sleeps between commit() and
                # forward_key_event() are unfortunately needed because
                # this is racy, without the sleeps it works
                # unreliably.
                time.sleep(self._ibus_event_sleep_seconds)
                for dummy_char in input_phrase_right:
                    self._forward_generated_key_event(IBus.KEY_Left)
                # self._return_false(key) might use a commit again instead
                # of forward_key_event() and if a commit is used, another
                # sleep is necessary.
                time.sleep(self._ibus_event_sleep_seconds)
                return False
            else:
                # nothing is selected in the lookup table, commit the
                # input_phrase
                commit_string = input_phrase
            if not commit_string:
                # This should not happen, we returned already above when
                # self.is_empty(), if we get here there should
                # have been something in the preëdit or the lookup table:
                if DEBUG_LEVEL > 0:
                    LOGGER.error('commit string unexpectedly empty.')
                self._update_ui_empty_input()
                return False
            # Remember whether a candidate is selected and where the
            # caret is now because after self._commit_string() this
            # information is gone:
            candidate_was_selected = False
            if self.get_lookup_table().cursor_visible:
                candidate_was_selected = True
            caret_was = self.get_caret()
            if not input_phrase:
                input_phrase = commit_string
            self._commit_string(commit_string, input_phrase=input_phrase)
            if (key.val in (IBus.KEY_space, IBus.KEY_Tab)
                and not (key.control
                         or key.mod1
                         or key.super
                         or key.hyper
                         or key.meta)):
                self._clear_input()
                self._update_ui_empty_input_try_completion()
            else:
                self._clear_input_and_update_ui()
            # These sleeps between commit() and
            # forward_key_event() are unfortunately needed because
            # this is racy, without the sleeps it works
            # unreliably.
            time.sleep(self._ibus_event_sleep_seconds)
            if not candidate_was_selected:
                # cursor needs to be corrected leftwards:
                for dummy_char in commit_string[caret_was:]:
                    self._forward_generated_key_event(IBus.KEY_Left)
            return False

        if key.unicode:
            # If the suggestions are only enabled by Tab key, i.e. the
            # lookup table is not shown until Tab has been typed, hide
            # the lookup table again when characters are added to the
            # preëdit:
            self.is_lookup_table_enabled_by_tab = False
            if self.is_empty():
                # first key typed, we will try to complete something now
                # get the context if possible
                self.get_context()
                if self._auto_capitalize:
                    if self._new_sentence:
                        self._current_case_mode = 'capitalize'
                    if self._input_hints & itb_util.InputHints.UPPERCASE_WORDS:
                        self._current_case_mode = 'capitalize'
                    if self._input_hints & itb_util.InputHints.UPPERCASE_CHARS:
                        self._current_case_mode = 'upper'
                    if self._input_hints & itb_util.InputHints.LOWERCASE:
                        self._current_case_mode = 'lower'
            if (key.msymbol in ('G- ', 'G-_')
                and not self._has_transliteration([key.msymbol])):
                insert_msymbol = key.unicode # ' ' for 'G- ' and '_' for 'G-_'
            else:
                insert_msymbol = key.msymbol
            if (not self._is_candidate_auto_selected
                and self.get_lookup_table().get_number_of_candidates()
                and self.get_lookup_table().cursor_visible):
                # something is *manually* selected in the lookup
                # table, replace the typed string with the selection
                # and move the cursor to the end:
                self._typed_string = list(
                    self.get_string_from_lookup_table_cursor_pos())
                self._typed_string_cursor = len(self._typed_string)
            self._insert_string_at_cursor([insert_msymbol])
            # If the character typed could end a sentence, we can
            # *maybe* commit immediately.  However, if transliteration
            # is used, we may need to handle a punctuation or symbol
            # character. For example, “.c” is transliterated to “ċ” in
            # the “t-latn-pre” transliteration method, therefore we
            # cannot commit when encountering a “.”, we have to wait
            # what comes next.
            input_phrase = (
                self._transliterated_strings[
                    self.get_current_imes()[0]])
            # pylint: disable=too-many-boolean-expressions
            if (len(key.msymbol) == 1
                and key.msymbol != ' '
                and key.msymbol in self._auto_commit_characters
                and input_phrase
                and input_phrase[-1] == key.msymbol
                and itb_util.contains_letter(input_phrase)
            ):
                if DEBUG_LEVEL > 1:
                    LOGGER.debug(
                        'auto committing because of key.msymbol = %s',
                        key.msymbol)
                self._commit_string(
                    input_phrase + ' ', input_phrase=input_phrase)
                self._clear_input()
            self._update_ui()
            return True

        # What kind of key was this??
        #
        # The unicode character for this key is apparently the empty
        # string.  And apparently it was not handled as a select key
        # or other special key either.  So whatever this was, we
        # cannot handle it, just pass it through to the application by
        # returning “False”.
        if self.is_empty():
            self._update_ui_empty_input()
        return False

    def do_focus_in(self) -> None: # pylint: disable=arguments-differ
        '''
        Called for ibus < 1.5.27 when a window gets focus while
        this input engine is enabled
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('entering do_focus_in()\n')
        self.do_focus_in_id('', '')

    def do_focus_in_id( # pylint: disable=arguments-differ
            self, object_path: str, client: str) -> None:
        '''Called for ibus >= 1.5.27 when a window gets focus while
        this input engine is enabled

        :param object_path: Example:
                            '/org/freedesktop/IBus/InputContext_23'
        :param client: Possible values and examples where these values occur:
                       '': unknown
                       'fake': focus where input is impossible
                               (e.g. desktop background)
                       'xim': XIM
                             (Gtk3 programs in a Gnome Xorg session
                              when GTK_IM_MODULE is unset also use xim)
                       'gtk-im:<program-name>':  Gtk2 input module
                       'gtk3-im:<program-name>': Gtk3 input module
                       'gtk4-im:<program-name>': Gtk4 input module
                       'gnome-shell': Entries handled by gnome-shell
                                      (like the command line dialog
                                      opened with Alt+F2 or the search
                                      field when pressing the Super
                                      key.) When GTK_IM_MODULE is
                                      unset in a Gnome Wayland session
                                      all programs which would show
                                      'gtk3-im' or 'gtk4-im' with
                                      GTK_IM_MODULE=ibus then show
                                      'gnome-shell' instead.
                       'Qt':      Qt4 input module
                       'QIBusInputContext': Qt5 input module

                       In case of the Gtk input modules, the name of the
                       client is also shown after the “:”, for example
                       like 'gtk3-im:firefox', 'gtk4-im:gnome-text-editor', …
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('object_path=%s client=%s\n', object_path, client)
        self._im_client = client
        (program_name,
         window_title) = itb_active_window.get_active_window()
        if ':' not in self._im_client:
            self._im_client += ':' + program_name + ':' + window_title
        else:
            self._im_client += ':' + window_title
        if DEBUG_LEVEL > 1:
            LOGGER.debug('self._im_client=%s\n', self._im_client)
        self._keyvals_to_keycodes = itb_util.KeyvalsToKeycodes()
        if DEBUG_LEVEL > 2:
            for keyval in self._keyvals_to_keycodes.keyvals():
                name = IBus.keyval_name(keyval)
                if (name.startswith('dead_')
                    or name == 'Multi_key'):
                    LOGGER.debug('Available compose key: %s', name)
                if name in ('a', 'Greek_alpha', 'Cyrillic_ef'):
                    LOGGER.debug('Available key: %s', name)
        self.register_properties(self.main_prop_list)
        self.clear_context()
        self._commit_happened_after_focus_in = False
        self._surrounding_text_event_happened_after_focus_in = False
        self._update_ui()
        self._apply_autosettings()

    def _apply_autosettings(self) -> None:
        '''Apply automatic setting changes for the window which just got focus'''
        if DEBUG_LEVEL > 0:
            LOGGER.debug('self._im_client=%s', self._im_client)
        if self._autosettings_revert:
            self._revert_autosettings()
        if not self._im_client:
            return
        autosettings_apply: Dict[str, Any] = {}
        for (setting, value, regexp) in self._autosettings:
            if (not regexp
                or setting not in self._set_get_functions
                or 'set' not in self._set_get_functions[setting]
                or 'get' not in self._set_get_functions[setting]):
                continue
            pattern = re.compile(regexp)
            if not pattern.search(self._im_client):
                continue
            current_value = self._set_get_functions[setting]['get']()
            if setting in ('inputmethod', 'dictionary'):
                current_value = ','.join(current_value)
            if type(current_value) not in [str, int, bool]:
                continue
            new_value: Union[str, bool, int] = ''
            if isinstance(current_value, str):
                new_value = value
            elif isinstance(current_value, bool):
                if value.lower() in ['true', 'false']:
                    new_value = value.lower() == 'true'
                else:
                    continue
            elif isinstance(current_value, int):
                try:
                    new_value = int(value)
                except (ValueError,) as error:
                    LOGGER.exception(
                        'Exception converting autosettings value to integer: '
                        '%s: %s',
                        error.__class__.__name__, error)
                    continue
            else:
                continue
            LOGGER.info(
                'regexp “%s” matches “%s”, trying to set “%s” to “%s”',
                regexp, self._im_client, setting, value)
            autosettings_apply[setting] = new_value
            self._autosettings_revert[setting] = current_value
        for setting, value in autosettings_apply.items():
            LOGGER.info('Apply autosetting: %s: %s -> %s',
                        setting, self._autosettings_revert[setting], value)
            self._set_get_functions[setting]['set'](
                value, update_gsettings=False)

    def _record_in_database_and_push_context(
            self, commit_phrase: str = '', input_phrase: str = '') -> None:
        '''Record an commit_phrase/input_phrase pair in the user database.

        This function does *not* do the actual commit, it assumes that
        the commit has already happened! If the preëdit has already
        been committed because the focus has been moved to another
        window or to a different cursor position in the same window by
        using a mouse click, this function should be called with both
        parameters empty. In this case it records what has been in the
        already committed preëdit into the user database.

        :param commit_phrase: The phrase which has been committed already.
                              This parameter can be empty, then it is made
                              equal to what has been in the preedit.
        :param input_phrase: The typed input. This parameter can be empty,
                             then the transliterated input is used.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('commit_phrase=%r input_phrase=%r',
                         commit_phrase, input_phrase)
        if not input_phrase:
            input_phrase = self._transliterated_strings[
                self.get_current_imes()[0]]
        if not commit_phrase:
            typed_string = unicodedata.normalize('NFC', input_phrase)
            first_candidate = ''
            if self._candidates:
                first_candidate = self._candidates[0][0]
            if (not self._inline_completion
                or (self.client_capabilities & itb_util.Capabilite.OSK)
                or self.get_lookup_table().get_cursor_pos() != 0
                or not first_candidate
                or not first_candidate.startswith(typed_string)
                or first_candidate == typed_string):
                # Standard lookup table was shown, preedit contained
                # input_phrase:
                commit_phrase = input_phrase
            else:
                commit_phrase = first_candidate
        # commit_phrase should always be in NFC:
        commit_phrase = unicodedata.normalize('NFC', commit_phrase)
        stripped_input_phrase = itb_util.strip_token(input_phrase)
        stripped_commit_phrase = itb_util.strip_token(commit_phrase)
        if (self._off_the_record
            or self._record_mode == 3
            or self._hide_input
            or self._input_hints & itb_util.InputHints.PRIVATE):
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Privacy: NOT recording and pushing context.')
            return
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'stripped_input_phrase=%r stripped_commit_phrase=%r '
                'p_phrase=%r pp_phrase=%r '
                'record_mode=%d '
                'spellcheck=%r previously recorded=%d',
                stripped_input_phrase, stripped_commit_phrase,
                self.get_p_phrase(), self.get_pp_phrase(), self._record_mode,
                self.database.hunspell_obj.spellcheck(commit_phrase),
                self.database.phrase_exists(commit_phrase))
        if not stripped_input_phrase or not stripped_commit_phrase:
            if DEBUG_LEVEL > 1:
                LOGGER.debug(
                    'Empty input or commit: NOT recording and pushing context')
            return
        if (self._record_mode == 1
            and not self.database.phrase_exists(stripped_commit_phrase)
            and not self.database.hunspell_obj.spellcheck(stripped_commit_phrase)):
            if DEBUG_LEVEL > 1:
                LOGGER.debug('self._record_mode=%d: Not recording: %r',
                             self._record_mode, stripped_commit_phrase)
            return
        if (self._record_mode == 2
            and not self.database.hunspell_obj.spellcheck(stripped_commit_phrase)):
            if DEBUG_LEVEL > 1:
                LOGGER.debug('self._record_mode=%d: Not recording: %r',
                             self._record_mode, stripped_commit_phrase)
            return
        if DEBUG_LEVEL > 1:
            LOGGER.debug('recording and pushing context.')
        self.database.check_phrase_and_update_frequency(
            input_phrase=stripped_input_phrase,
            phrase=stripped_commit_phrase,
            p_phrase=self.get_p_phrase(),
            pp_phrase=self.get_pp_phrase())
        self.push_context(stripped_commit_phrase)

    def do_focus_out(self) -> None: # pylint: disable=arguments-differ
        '''
        Called for ibus < 1.5.27 when a window loses focus while
        this input engine is enabled
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('entering do_focus_out()\n')
        self.do_focus_out_id('')

    def do_focus_out_id( # pylint: disable=arguments-differ
            self, object_path: str) -> None:
        '''
        Called for ibus >= 1.5.27 when a window loses focus while
        this input engine is enabled

        :param object_path: Example:
                            '/org/freedesktop/IBus/InputContext_23'
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('object_path=%s\n', object_path)
        # Do not do self._input_purpose = 0 here, see
        # https://gitlab.gnome.org/GNOME/gnome-shell/-/issues/5966#note_1576732
        # if the input purpose is set correctly on focus in, then it
        # should not be necessary to reset it here.
        self._im_client = ''
        # The preëdit, if there was any, has already been committed
        # automatically because
        # update_preedit_text_with_mode(,,,IBus.PreeditFocusMode.COMMIT)
        # has been used. But the contents of the preëdit have not
        # been recorded in the user database yet. Do it now:
        if not self.is_empty():
            self._record_in_database_and_push_context()
        self.clear_context()
        self._clear_input_and_update_ui()
        self._revert_autosettings()

    def _revert_autosettings(self) -> None:
        '''Revert automatic setting changes which were done on focus in'''
        for setting, value in self._autosettings_revert.items():
            LOGGER.info('Revert autosetting: %s: -> %s', setting, value)
            self._set_get_functions[setting]['set'](
                value, update_gsettings=False)
        self._autosettings_revert = {}

    def do_reset(self) -> None: # pylint: disable=arguments-differ
        '''Called when the mouse pointer is used to move to cursor to a
        different position in the current window.

        Also called when certain keys are pressed:

            Return, KP_Enter, ISO_Enter, Up, Down, (and others?)

        Even some key sequences like space + Left and space + Right
        seem to call this.

        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('self._current_preedit_text=%r '
                         'self._typed_string=%s '
                         'self._typed_compose_sequence=%s '
                         'compose preedit representation=%r',
                         self._current_preedit_text,
                         repr(self._typed_string),
                         repr(self._typed_compose_sequence),
                         self._compose_sequences.preedit_representation(
                             self._typed_compose_sequence))
        if not self._current_preedit_text:
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Current preedit is empty: '
                             'do not record, clear input, update UI.')
            # If the current preedit is empty, that means that there is
            # no current input, neither "normal" nor compose input. In that
            # case, there is nothing to record in the database, no pending
            # input needs to be cleared and the UI needs no update.
            if (self._prev_key
                and
                self._prev_key.val in (
                    IBus.KEY_Return, IBus.KEY_KP_Enter, IBus.KEY_ISO_Enter)):
                if DEBUG_LEVEL > 1:
                    LOGGER.debug(
                        'Avoid clearing context after Return or Enter')
                return
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Clear context: cursor might have moved, '
                             'remembered context might be wrong')
            self.clear_context()
            return
        if (self.client_capabilities & itb_util.Capabilite.SURROUNDING_TEXT
            and
            self._input_purpose not in [itb_util.InputPurpose.TERMINAL.value]):
            surrounding_text = self.get_surrounding_text()
            text = surrounding_text[0].get_text()
            cursor_pos = surrounding_text[1]
            anchor_pos = surrounding_text[2]
            if surrounding_text:
                LOGGER.debug('surrounding_text = [%r, %s, %s]',
                             text, cursor_pos, anchor_pos)
            else:
                LOGGER.debug('Surrounding text object is None. '
                             'Should never happen.')
                return
            if not text.endswith(self._current_preedit_text):
                LOGGER.debug(
                    'Whatever caused the reset did not commit the preedit. '
                    'A reset seems to happen sometimes right after '
                    'reopening a preedit. In that case nothing '
                    'should be recorded, nothing cleared, nothing updated.')
                return
        time_since_prev_key_handled = 0.0
        if self._prev_key:
            time_since_prev_key_handled = time.time() - self._prev_key.time
        if 0.0 <= time_since_prev_key_handled <= 0.1:
            if DEBUG_LEVEL > 1:
                LOGGER.debug('probably triggered by key')
        else:
            if DEBUG_LEVEL > 1:
                LOGGER.debug('probably triggered by mouse')
        # The preëdit, if there was any, has already been committed
        # automatically because
        # update_preedit_text_with_mode(,,,IBus.PreeditFocusMode.COMMIT)
        # has been used. But the contents of the preëdit have not
        # been recorded in the user database yet. Do it now:
        if not self.is_empty():
            self._record_in_database_and_push_context()
        if DEBUG_LEVEL > 1:
            LOGGER.debug('Clearing context and input.')
        self.clear_context()
        self._clear_input_and_update_ui()

    def do_set_content_type( # pylint: disable=arguments-differ
            self, purpose: int, hints: int) -> None:
        '''Called when the input purpose or hints change'''
        LOGGER.debug('purpose=%s hints=%s\n', purpose, format(hints, '016b'))
        self._input_purpose = purpose
        self._input_hints = hints
        if DEBUG_LEVEL > 1:
            if (self._input_purpose
                in [int(x) for x in list(itb_util.InputPurpose)]):
                for input_purpose in list(itb_util.InputPurpose):
                    if self._input_purpose == input_purpose:
                        LOGGER.debug(
                            'self._input_purpose = %s (%s)',
                            self._input_purpose, str(input_purpose))
            else:
                LOGGER.debug(
                    'self._input_purpose = %s (Unknown)',
                    self._input_purpose)
            for hint in itb_util.InputHints:
                if self._input_hints & hint:
                    LOGGER.debug(
                        'hint: %s %s',
                        str(hint), format(int(hint), '016b'))

    def do_enable(self) -> None: # pylint: disable=arguments-differ
        '''Called when this input engine is enabled'''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('do_enable()\n')
        # Tell the input-context that the engine will utilize
        # surrounding-text:
        self.get_surrounding_text()
        self.do_focus_in()

    def do_disable(self) -> None: # pylint: disable=arguments-differ
        '''Called when this input engine is disabled'''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('do_disable()\n')
        self._clear_input_and_update_ui()

    def do_page_up(self) -> bool: # pylint: disable=arguments-differ
        '''Called when the page up button in the lookup table is clicked with
        the mouse

        '''
        if self._page_up():
            self._update_lookup_table_and_aux()
            return True
        return True

    def do_page_down(self) -> bool: # pylint: disable=arguments-differ
        '''Called when the page down button in the lookup table is clicked with
        the mouse

        '''
        if self._page_down():
            self._update_lookup_table_and_aux()
            return True
        return False

    def do_cursor_up(self, *_args: Any, **_kwargs: Any) -> bool:
        '''Called when the mouse wheel is rolled up in the candidate area of
        the lookup table

        '''
        res = self._arrow_up()
        self._update_lookup_table_and_aux()
        return res

    def do_cursor_down(self) -> bool: # pylint: disable=arguments-differ
        '''Called when the mouse wheel is rolled down in the candidate area of
        the lookup table

        '''
        res = self._arrow_down()
        self._update_lookup_table_and_aux()
        return res

    # pylint: disable=unused-argument
    def _reload_dictionaries(
            self, value: Any, update_gsettings: bool = False) -> None:
        '''(re)load all dictionaries

        Needs to be called when a dictionary has been updated or
        installed.

        :param value: ignored
        :param update_gsettings: ignored
        '''
        LOGGER.info('Reloading dictionaries ...')
        self.database.hunspell_obj.init_dictionaries()
        self._clear_input_and_update_ui()
    # pylint: enable=unused-argument

    # pylint: disable=unused-argument
    def _reload_input_methods(
            self, value: Any, update_gsettings: bool = False) -> None:
        '''(re)load all input_methods

        Needs to be called when an input method has been changed,
        usually because an optional variable of an input method was changed.

        :param value: ignored
        :param update_gsettings: ignored
        '''
        LOGGER.info('Reloading input methods ...')
        m17n_translit.fini()
        m17n_translit.init()
        self._init_transliterators()
        self._clear_input_and_update_ui()
    # pylint: enable=unused-argument

    def on_set_surrounding_text(self,
                                _engine: IBus.Engine,
                                text: IBus.Text,
                                cursor_pos: int,
                                anchor_pos: int) -> None:
        '''Called when the surrounding text has changed.

        Useful especially in debugging for stuff like this:

        self._set_surrounding_text_event.clear()
        ... some stuff ...
        # Now check whether at  least one set-surrounding-text signal
        # has occured:
        self._set_surrounding_text_event.is_set()

        or:

        self._set_surrounding_text_event.clear()
        ... some stuff ...
        # If at least one set-surrounding-text signal
        # has already occured, continue immediately, else
        # wait for such a signal to occur but continue after
        # a timeout:
        self._set_surrounding_text_event.wait(timeout=0.1)
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('text=“%r” cursor_pos=%s anchor_pos=%s',
                         text.get_text(), cursor_pos, anchor_pos)
        self._set_surrounding_text_text = text.get_text()
        self._set_surrounding_text_cursor_pos = cursor_pos
        self._set_surrounding_text_anchor_pos = anchor_pos
        self._set_surrounding_text_event.set()
        self._surrounding_text_event_happened_after_focus_in = True

    def on_gsettings_value_changed(
            self, _settings: Gio.Settings, key: str) -> None:
        '''
        Called when a value in the settings has been changed.

        :param settings: The settings object
        :param key: The key of the setting which has changed
        '''
        value = itb_util.variant_to_value(self._gsettings.get_value(key))
        LOGGER.debug('Settings changed: key=%s value=%s\n', key, value)
        if (key in self._set_get_functions
            and 'set' in self._set_get_functions[key]):
            self._set_get_functions[key]['set'](value, update_gsettings=False)
            return
        LOGGER.warning('Unknown key\n')
        return
