# -*- coding: utf-8 -*-
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
import os
import unicodedata
import re
import time
import locale
import logging
from gettext import dgettext
from gi import require_version # type: ignore
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore
require_version('Gio', '2.0')
from gi.repository import Gio
require_version('GLib', '2.0')
from gi.repository import GLib
from m17n_translit import Transliterator
import itb_util
import itb_emoji

IMPORT_SIMPLEAUDIO_SUCCESSFUL = False
try:
    import simpleaudio # type: ignore
    IMPORT_SIMPLEAUDIO_SUCCESSFUL = True
except (ImportError,):
    IMPORT_SIMPLEAUDIO_SUCCESSFUL = False

IMPORT_GOOGLE_SPEECH_TO_TEXT_SUCCESSFUL = False
try:
    from google.cloud import speech # type: ignore
    from google.cloud.speech import enums # type: ignore
    from google.cloud.speech import types
    IMPORT_GOOGLE_SPEECH_TO_TEXT_SUCCESSFUL = True
except (ImportError,):
    IMPORT_GOOGLE_SPEECH_TO_TEXT_SUCCESSFUL = False

LOGGER = logging.getLogger('ibus-typing-booster')

__all__ = (
    "TypingBoosterEngine",
)

_ = lambda a: dgettext("ibus-typing-booster", a)
N_ = lambda a: a

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

class TypingBoosterEngine(IBus.Engine):
    '''The IBus Engine for ibus-typing-booster'''

    def __init__(self, bus, obj_path, database, unit_test=False) -> None:
        global DEBUG_LEVEL
        try:
            DEBUG_LEVEL = int(str(os.getenv(
                'IBUS_TYPING_BOOSTER_DEBUG_LEVEL')))
        except (TypeError, ValueError):
            DEBUG_LEVEL = int(0)
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                'TypingBoosterEngine.__init__(bus=%s, obj_path=%s, db=%s)',
                bus, obj_path, database)
        super().__init__(
            connection=bus.get_connection(), object_path=obj_path)
        self._keyvals_to_keycodes = itb_util.KeyvalsToKeycodes()
        self._compose_sequences = itb_util.ComposeSequences()
        self._unit_test = unit_test
        self._input_purpose = 0
        self._input_hints = 0
        self._lookup_table_is_invalid = False
        self._lookup_table_shows_related_candidates = False
        self._current_auxiliary_text = ''
        self._bus = bus
        self.database = database
        self.emoji_matcher: Optional[itb_emoji.EmojiMatcher] = None
        self._setup_pid = 0
        self._gsettings = Gio.Settings(
            schema='org.freedesktop.ibus.engine.typing-booster')
        self._gsettings.connect('changed', self.on_gsettings_value_changed)

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

        self._current_imes: List[str] = []

        # Between some events sent to ibus like forward_key_event(),
        # delete_surrounding_text(), commit_text(), a sleep is necessary.
        # Without the sleep, these events may be processed out of order.
        self._ibus_event_sleep_seconds = 0.1

        self._emoji_predictions = itb_util.variant_to_value(
            self._gsettings.get_value('emojipredictions'))
        if self._emoji_predictions is None:
            self._emoji_predictions = False # default

        self.is_lookup_table_enabled_by_min_char_complete = False
        self._min_char_complete = itb_util.variant_to_value(
            self._gsettings.get_value('mincharcomplete'))
        if self._min_char_complete is None:
            self._min_char_complete = 1 # default
        if self._min_char_complete < 1:
            self._min_char_complete = 1 # minimum
        if self._min_char_complete > 9:
            self._min_char_complete = 9 # maximum

        self._debug_level = itb_util.variant_to_value(
            self._gsettings.get_value('debuglevel'))
        if self._debug_level is None:
            self._debug_level = 0 # default
        if self._debug_level < 0:
            self._debug_level = 0 # minimum
        if self._debug_level > 255:
            self._debug_level = 255 # maximum
        DEBUG_LEVEL = self._debug_level

        self._page_size = itb_util.variant_to_value(
            self._gsettings.get_value('pagesize'))
        if self._page_size is None:
            self._page_size = 6 # reasonable default page size
        if self._page_size < 1:
            self._page_size = 1 # minimum page size supported
        if self._page_size > 9:
            self._page_size = 9 # maximum page size supported

        self._lookup_table_orientation = itb_util.variant_to_value(
            self._gsettings.get_value('lookuptableorientation'))
        if self._lookup_table_orientation is None:
            self._lookup_table_orientation = IBus.Orientation.VERTICAL

        self._preedit_underline = itb_util.variant_to_value(
            self._gsettings.get_value('preeditunderline'))
        if self._preedit_underline is None:
            self._preedit_underline = IBus.AttrUnderline.SINGLE

        self._preedit_style_only_when_lookup = itb_util.variant_to_value(
            self._gsettings.get_value('preeditstyleonlywhenlookup'))
        if self._preedit_style_only_when_lookup is None:
            self._preedit_style_only_when_lookup = False

        self._show_number_of_candidates = itb_util.variant_to_value(
            self._gsettings.get_value('shownumberofcandidates'))
        if self._show_number_of_candidates is None:
            self._show_number_of_candidates = False

        self._show_status_info_in_auxiliary_text = itb_util.variant_to_value(
            self._gsettings.get_value('showstatusinfoinaux'))
        if self._show_status_info_in_auxiliary_text is None:
            self._show_status_info_in_auxiliary_text = False

        self._is_candidate_auto_selected = False
        self._auto_select_candidate = itb_util.variant_to_value(
            self._gsettings.get_value('autoselectcandidate'))
        if self._auto_select_candidate is None:
            self._auto_select_candidate = False

        self.is_lookup_table_enabled_by_tab = False
        self._tab_enable = itb_util.variant_to_value(
            self._gsettings.get_value('tabenable'))
        if self._tab_enable is None:
            self._tab_enable = False

        self._off_the_record = itb_util.variant_to_value(
            self._gsettings.get_value('offtherecord'))
        if self._off_the_record is None:
            self._off_the_record = False # default

        self._hide_input = False

        self._input_mode = True

        self._qt_im_module_workaround = itb_util.variant_to_value(
            self._gsettings.get_value('qtimmoduleworkaround'))
        if self._qt_im_module_workaround is None:
            self._qt_im_module_workaround = False # default

        self._arrow_keys_reopen_preedit = itb_util.variant_to_value(
            self._gsettings.get_value('arrowkeysreopenpreedit'))
        if self._arrow_keys_reopen_preedit is None:
            self._arrow_keys_reopen_preedit = False # default

        self._auto_commit_characters = itb_util.variant_to_value(
            self._gsettings.get_value('autocommitcharacters'))
        if not self._auto_commit_characters:
            self._auto_commit_characters = '' # default

        self._remember_last_used_preedit_ime = False
        self._remember_last_used_preedit_ime = itb_util.variant_to_value(
            self._gsettings.get_value('rememberlastusedpreeditime'))
        if self._remember_last_used_preedit_ime is None:
            self._remember_last_used_preedit_ime = False

        self._add_space_on_commit = itb_util.variant_to_value(
            self._gsettings.get_value('addspaceoncommit'))
        if self._add_space_on_commit is None:
            self._add_space_on_commit = True

        self._inline_completion = itb_util.variant_to_value(
            self._gsettings.get_value('inlinecompletion'))
        if self._inline_completion is None:
            self._inline_completion = False

        self._auto_capitalize = itb_util.variant_to_value(
            self._gsettings.get_value('autocapitalize'))
        if self._auto_capitalize is None:
            self._auto_capitalize = False

        self._color_preedit_spellcheck = itb_util.variant_to_value(
            self._gsettings.get_value('colorpreeditspellcheck'))
        if self._color_preedit_spellcheck is None:
            self._color_preedit_spellcheck = True

        self._color_preedit_spellcheck_string = itb_util.variant_to_value(
            self._gsettings.get_value('colorpreeditspellcheckstring'))
        self._color_preedit_spellcheck_argb = itb_util.color_string_to_argb(
            self._color_preedit_spellcheck_string)

        self._color_inline_completion = itb_util.variant_to_value(
            self._gsettings.get_value('colorinlinecompletion'))
        if self._color_inline_completion is None:
            self._color_inline_completion = True

        self._color_inline_completion_string = itb_util.variant_to_value(
            self._gsettings.get_value('colorinlinecompletionstring'))
        self._color_inline_completion_argb = itb_util.color_string_to_argb(
            self._color_inline_completion_string)

        self._color_userdb = itb_util.variant_to_value(
            self._gsettings.get_value('coloruserdb'))
        if self._color_userdb is None:
            self._color_userdb = True

        self._color_userdb_string = itb_util.variant_to_value(
            self._gsettings.get_value('coloruserdbstring'))
        self._color_userdb_argb = itb_util.color_string_to_argb(
            self._color_userdb_string)

        self._color_spellcheck = itb_util.variant_to_value(
            self._gsettings.get_value('colorspellcheck'))
        if self._color_spellcheck is None:
            self._color_spellcheck = True

        self._color_spellcheck_string = itb_util.variant_to_value(
            self._gsettings.get_value('colorspellcheckstring'))
        self._color_spellcheck_argb = itb_util.color_string_to_argb(
            self._color_spellcheck_string)

        self._color_dictionary = itb_util.variant_to_value(
            self._gsettings.get_value('colordictionary'))
        if self._color_dictionary is None:
            self._color_dictionary = True

        self._color_dictionary_string = itb_util.variant_to_value(
            self._gsettings.get_value('colordictionarystring'))
        self._color_dictionary_argb = itb_util.color_string_to_argb(
            self._color_dictionary_string)

        self._label_userdb = itb_util.variant_to_value(
            self._gsettings.get_value('labeluserdb'))
        if self._label_userdb is None:
            self._label_userdb = True

        self._label_userdb_string = itb_util.variant_to_value(
            self._gsettings.get_value('labeluserdbstring'))

        self._label_spellcheck = itb_util.variant_to_value(
            self._gsettings.get_value('labelspellcheck'))
        if self._label_spellcheck is None:
            self._label_spellcheck = True

        self._label_spellcheck_string = itb_util.variant_to_value(
            self._gsettings.get_value('labelspellcheckstring'))

        self._label_dictionary = itb_util.variant_to_value(
            self._gsettings.get_value('labeldictionary'))
        if self._label_dictionary is None:
            self._label_dictionary = True

        self._label_dictionary_string = itb_util.variant_to_value(
            self._gsettings.get_value('labeldictionarystring'))

        self._label_busy = itb_util.variant_to_value(
            self._gsettings.get_value('labelbusy'))
        if self._label_busy is None:
            self._label_busy = True

        self._label_busy_string = itb_util.variant_to_value(
            self._gsettings.get_value('labelbusystring'))

        self._label_speech_recognition = True
        self._label_speech_recognition_string = '🎙️'

        self._google_application_credentials = itb_util.variant_to_value(
            self._gsettings.get_value('googleapplicationcredentials'))
        if self._google_application_credentials is None:
            self._google_application_credentials = ''

        self._keybindings: Dict[str, List[str]] = {}
        self._hotkeys: Optional[itb_util.HotKeys] = None
        self._normal_digits_used_in_keybindings = False
        self._keypad_digits_used_in_keybindings = False
        self.set_keybindings(
            itb_util.variant_to_value(
                self._gsettings.get_value('keybindings')),
            update_gsettings=False)

        self._remember_input_mode = itb_util.variant_to_value(
            self._gsettings.get_value('rememberinputmode'))
        if (self._keybindings['toggle_input_mode_on_off']
            and self._remember_input_mode):
            self._input_mode = itb_util.variant_to_value(
                self._gsettings.get_value('inputmode'))
        else:
            self.set_input_mode(True, update_gsettings=True)

        self._error_sound_object: Optional[simpleaudio.WaveObject] = None
        self._error_sound_file = ''
        self._error_sound = itb_util.variant_to_value(
            self._gsettings.get_value('errorsound'))
        self.set_error_sound_file(
            itb_util.variant_to_value(
                self._gsettings.get_value('errorsoundfile')),
            update_gsettings=False)

        self._dictionary_names: List[str] = []
        dictionary = itb_util.variant_to_value(
            self._gsettings.get_value('dictionary'))
        if dictionary:
            # There is a dictionary setting in Gsettings, use that:
            names = [x.strip() for x in dictionary.split(',')]
            for name in names:
                if name:
                    self._dictionary_names.append(name)
        else:
            # There is no dictionary setting in Gsettings. Get the default
            # dictionaries for the current effective value of
            # LC_CTYPE and save it to Gsettings:
            self._dictionary_names = itb_util.get_default_dictionaries(
                locale.getlocale(category=locale.LC_CTYPE)[0])
            self._gsettings.set_value(
                'dictionary',
                GLib.Variant.new_string(','.join(self._dictionary_names)))
        if (len(self._dictionary_names)
            > itb_util.MAXIMUM_NUMBER_OF_DICTIONARIES):
            LOGGER.warning(
                'Trying to set more than the allowed maximum of %s '
                %itb_util.MAXIMUM_NUMBER_OF_DICTIONARIES
                + 'dictionaries.\n'
                + 'Trying to set: %s\n' %self._dictionary_names
                + 'Really setting: %s\n'
                %self._dictionary_names[
                    :itb_util.MAXIMUM_NUMBER_OF_DICTIONARIES])
            self._dictionary_names = self._dictionary_names[
                :itb_util.MAXIMUM_NUMBER_OF_DICTIONARIES]
        self.database.hunspell_obj.set_dictionary_names(
            self._dictionary_names[:])

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
        if inputmethod:
            inputmethods = [re.sub(re.escape('noime'), 'NoIME', x.strip(),
                                   flags=re.IGNORECASE)
                            for x in inputmethod.split(',') if x]
            for ime in inputmethods:
                self._current_imes.append(ime)
        if self._current_imes == []:
            # There is no ime set in Gsettings, get a default list
            # of input methods for the current effective value of LC_CTYPE
            # and save it to Gsettings:
            self._current_imes = itb_util.get_default_input_methods(
                locale.getlocale(category=locale.LC_CTYPE)[0])
            self._gsettings.set_value(
                'inputmethod',
                GLib.Variant.new_string(','.join(self._current_imes)))
        if len(self._current_imes) > itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS:
            LOGGER.warning(
                'Trying to set more than the allowed maximum of %s '
                %itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS
                + 'input methods.\n'
                + 'Trying to set: %s\n' %self._current_imes
                + 'Really setting: %s\n'
                %self._current_imes[:itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS])
            self._current_imes = (
                self._current_imes[:itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS])

        self._commit_happened_after_focus_in = False

        self._prev_key: Optional[itb_util.KeyEvent] = None
        self._typed_compose_sequence: List[int] = [] # A list of key values
        self._typed_string: List[str] = [] # A list of msymbols
        self._typed_string_cursor = 0
        self._p_phrase = ''
        self._pp_phrase = ''
        self._ppp_phrase = ''
        self._new_sentence = False
        self._transliterated_strings: Dict[str, str] = {}
        self._transliterators: Dict[str, Transliterator] = {}
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

        LOGGER.info(
            '********** Initialized and ready for input: **********')
        self._clear_input_and_update_ui()

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
                self._transliterators[ime] = Transliterator(ime)
            except ValueError:
                LOGGER.exception(
                    'Error initializing Transliterator %s '
                    'Maybe /usr/share/m17n/%s.mim is not installed?',
                    ime, ime)
                # Use dummy transliterator “NoIME” as a fallback:
                self._transliterators[ime] = Transliterator('NoIME')
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
                self._typed_string[:self._typed_string_cursor]))
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
        if comment:
            phrase += ' ' + itb_util.bidi_embed(comment)
        if spell_checking: # spell checking suggestion
            if (self._label_spellcheck
                and self._label_spellcheck_string.strip()):
                phrase = phrase + ' ' + self._label_spellcheck_string.strip()
            if self._color_spellcheck:
                attrs.append(IBus.attr_foreground_new(
                    self._color_spellcheck_argb, 0, len(phrase)))
        elif from_user_db:
            # This was found in the user database.  So it is
            # possible to delete it with a key binding or
            # mouse-click, if the user desires. Mark it
            # differently to show that it is deletable:
            if (self._label_userdb
                and self._label_userdb_string.strip()):
                phrase = phrase + ' ' + self._label_userdb_string.strip()
            if self._color_userdb:
                attrs.append(IBus.attr_foreground_new(
                    self._color_userdb_argb, 0, len(phrase)))
        else:
            # This is a (possibly accent insensitive) match in a
            # hunspell dictionary or an emoji matched by
            # EmojiMatcher.
            if (self._label_dictionary
                and self._label_dictionary_string.strip()):
                phrase = phrase + ' ' + self._label_dictionary_string.strip()
            if self._color_dictionary:
                attrs.append(IBus.attr_foreground_new(
                    self._color_dictionary_argb, 0, len(phrase)))
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
                        and ((len(stripped_transliterated_string)
                              >= self._min_char_complete))):
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
                    except Exception:
                        LOGGER.exception('Exception when calling select_words')
                if candidates and prefix:
                    candidates = [(prefix+x[0], x[1]) for x in candidates]
                for cand in candidates:
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
        if (self._emoji_predictions
            or self._typed_string[0] in (' ', '_')
            or self._typed_string[-1] in (' ', '_')):
            # If emoji mode is off and the emoji predictions are
            # triggered here because the typed string starts with a '
            # ' or a '_', the emoji matcher might not have been
            # initialized yet.  Make sure it is initialized now:
            if (not self.emoji_matcher
                or
                self.emoji_matcher.get_languages()
                != self._dictionary_names):
                self.emoji_matcher = itb_emoji.EmojiMatcher(
                    languages=self._dictionary_names)
            emoji_scores: Dict[str, Tuple[int, str]] = {}
            for ime in self._current_imes:
                if (self._transliterated_strings[ime]
                        and ((len(self._transliterated_strings[ime])
                              >= self._min_char_complete)
                             or self._tab_enable)):
                    emoji_matcher_candidates = self.emoji_matcher.candidates(
                        self._transliterated_strings[ime])
                    for cand in emoji_matcher_candidates:
                        if (cand[0] not in emoji_scores
                                or cand[2] > emoji_scores[cand[0]][0]):
                            emoji_scores[cand[0]] = (cand[2], cand[1])
            phrase_candidates_emoji_name = []
            for cand in phrase_candidates:
                if cand[0] in emoji_scores:
                    phrase_candidates_emoji_name.append((
                        cand[0], cand[1], emoji_scores[cand[0]][1],
                        cand[1] > 0, cand[1] < 0))
                    # avoid duplicates in the lookup table:
                    del emoji_scores[cand[0]]
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

        :rtype: Integer
        '''
        page, dummy_pos_in_page = divmod(
            self._lookup_table.get_cursor_pos(),
            self._lookup_table.get_page_size())
        return page

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
        return self._candidates[index][0]

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
        for case_mode in self._case_modes:
            # delete all case modes of the displayed candidate:
            phrase = self._case_modes[case_mode]['function'](
                displayed_phrase)
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
        return self._lookup_table.get_cursor_pos()

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
        for ime in self._current_imes:
            if self._typed_compose_sequence:
                self._transliterated_strings[ime] = (
                    self._transliterators[ime].transliterate(
                        self._typed_string[:self._typed_string_cursor])
                    + self._compose_sequences.preedit_representation(
                        self._typed_compose_sequence)
                    + self._transliterators[ime].transliterate(
                        self._typed_string[self._typed_string_cursor:]))
            else:
                self._transliterated_strings[ime] = (
                    self._transliterators[ime].transliterate(
                        self._typed_string))
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
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if isinstance(imes, str):
            imes = [x.strip() for x in imes.split(',')]
        imes = [re.sub(re.escape('noime'), 'NoIME', x.strip(),
                       flags=re.IGNORECASE)
                for x in imes if x]
        if imes == self._current_imes: # nothing to do
            return
        if len(imes) > itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS:
            LOGGER.error(
                'Trying to set more than the allowed maximum of %s '
                %itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS
                + 'input methods.\n'
                + 'Trying to set: %s\n' %imes
                + 'Really setting: %s\n'
                %imes[:itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS])
            imes = imes[:itb_util.MAXIMUM_NUMBER_OF_INPUT_METHODS]
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
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        if isinstance(dictionary_names, str):
            dictionary_names = [x.strip() for x in dictionary_names.split(',')]
        dictionary_names = [x for x in dictionary_names if x]
        if dictionary_names == self._dictionary_names: # nothing to do
            return
        if len(dictionary_names) > itb_util.MAXIMUM_NUMBER_OF_DICTIONARIES:
            LOGGER.error(
                'Trying to set more than the allowed maximum of %s '
                %itb_util.MAXIMUM_NUMBER_OF_DICTIONARIES
                + 'dictionaries.\n'
                + 'Trying to set: %s\n' %dictionary_names
                + 'Really setting: %s\n'
                %dictionary_names[:itb_util.MAXIMUM_NUMBER_OF_DICTIONARIES])
            dictionary_names = (
                dictionary_names[:itb_util.MAXIMUM_NUMBER_OF_DICTIONARIES])
        self._dictionary_names = dictionary_names
        self.database.hunspell_obj.set_dictionary_names(dictionary_names)
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
        '''Get current list of dictionary names

        :rtype: list of strings
        '''
        # It is important to return a copy, we do not want to change
        # the private member variable directly.
        return self._dictionary_names[:]

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

        :rtype: Python dictionary of key bindings for commands
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
                     + ' ' + itb_util.FLAGS.get(current_dictionaries[i], ''),
                     'label': current_dictionaries[i]
                     + ' ' + itb_util.FLAGS.get(current_dictionaries[i], ''),
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
                label = '%(label)s (%(symbol)s)' % {
                    'label': menu['label'],
                    'symbol': symbol}
                tooltip = '%(tooltip)s\n%(shortcut_hint)s' % {
                    'tooltip': menu['tooltip'],
                    'shortcut_hint': menu['shortcut_hint']}
        visible = len(self.get_dictionary_names()) > 1
        self._init_or_update_sub_properties_dictionary(
            sub_properties, current_mode=current_mode)
        if not key in self._prop_dict: # initialize property
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
                label = '%(label)s (%(symbol)s)' % {
                    'label': menu['label'],
                    'symbol': symbol}
                tooltip = '%(tooltip)s\n%(shortcut_hint)s' % {
                    'tooltip': menu['tooltip'],
                    'shortcut_hint': menu['shortcut_hint']}
        visible = len(self.get_current_imes()) > 1
        self._init_or_update_sub_properties_preedit_ime(
            sub_properties, current_mode=current_mode)
        if not key in self._prop_dict: # initialize property
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
        for mode in sorted(modes, key=lambda x: (modes[x]['number'])):
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
        for mode in sorted(modes, key=lambda x: (modes[x]['number'])):
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
                label = '%s' % menu['label']
                tooltip = '%(tooltip)s\n%(shortcut_hint)s' % {
                    'tooltip': menu['tooltip'],
                    'shortcut_hint': menu['shortcut_hint']}
        visible = bool(menu_key != 'InputMode'
                       or self._keybindings['toggle_input_mode_on_off'])
        self._init_or_update_sub_properties(
            menu_key, sub_properties_dict, current_mode=current_mode)
        if not menu_key in self._prop_dict: # initialize property
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
        if not menu_key in self._sub_props_dict:
            update = False
            self._sub_props_dict[menu_key] = IBus.PropList()
        else:
            update = True
        visible = bool(menu_key != 'InputMode'
                       or self._keybindings['toggle_input_mode_on_off'])
        for mode in sorted(modes, key=lambda x: (modes[x]['number'])):
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

    def do_property_activate(
            self,
            ibus_property: str,
            prop_state=IBus.PropState.UNCHECKED) -> None:
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
        self._update_ui()

    def do_destroy(self) -> None:
        '''Called when this input engine is destroyed
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('entering function')
        self._clear_input_and_update_ui()
        self.do_focus_out()
        super().destroy()

    def _update_preedit(self) -> None:
        '''Update Preedit String in UI'''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('entering function')
        # get_caret() should also use NFC!
        _str = unicodedata.normalize(
            'NFC', self._transliterated_strings[
                self.get_current_imes()[0]])
        _str = self._case_modes[self._current_case_mode]['function'](_str)
        if self._hide_input:
            _str = '*' * len(_str)
        if _str == '':
            super().update_preedit_text_with_mode(
                IBus.Text.new_from_string(''), 0, False,
                IBus.PreeditFocusMode.COMMIT)
        else:
            attrs = IBus.AttrList()
            if (not self._preedit_style_only_when_lookup
                or self.is_lookup_table_enabled_by_tab
                or self.is_lookup_table_enabled_by_min_char_complete):
                attrs.append(IBus.attr_underline_new(
                    self._preedit_underline, 0, len(_str)))
                if (self._color_preedit_spellcheck
                    and len(_str) >= 4
                    and not self.database.hunspell_obj.spellcheck(_str)):
                    attrs.append(IBus.attr_foreground_new(
                        self._color_preedit_spellcheck_argb, 0, len(_str)))
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
            aux_string = '(%d / %d) ' % (
                self.get_lookup_table().get_cursor_pos() + 1,
                self.get_lookup_table().get_number_of_candidates())
        if self._show_status_info_in_auxiliary_text:
            if self._emoji_predictions:
                aux_string += (
                    MODE_ON_SYMBOL + EMOJI_PREDICTION_MODE_SYMBOL + ' ')
            else:
                aux_string += (
                    MODE_OFF_SYMBOL + EMOJI_PREDICTION_MODE_SYMBOL + ' ')
            if self._off_the_record:
                aux_string += (
                    MODE_ON_SYMBOL + OFF_THE_RECORD_MODE_SYMBOL + ' ')
            else:
                aux_string += (
                    MODE_OFF_SYMBOL + OFF_THE_RECORD_MODE_SYMBOL + ' ')
            names = self.get_dictionary_names()
            dictionary_label = (
                names[0] + ' ' + itb_util.FLAGS.get(names[0], ''))
            if dictionary_label:
                aux_string += dictionary_label
            preedit_ime = self.get_current_imes()[0]
            if preedit_ime != 'NoIME':
                aux_string += ' ' + preedit_ime + ' '
        # Colours do not work at the moment in the auxiliary text!
        # Needs fix in ibus.
        attrs = IBus.AttrList()
        attrs.append(IBus.attr_foreground_new(
            itb_util.color_string_to_argb('SlateGray'),
            0,
            len(aux_string)))
        if DEBUG_LEVEL > 0:
            context = (
                'Context: ' + self.get_ppp_phrase()
                + ' ' + self.get_pp_phrase()
                + ' ' + self.get_p_phrase())
            aux_string += context
            attrs.append(IBus.attr_foreground_new(
                itb_util.color_string_to_argb('DeepPink'),
                len(aux_string)-len(context),
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
        # Also make sure to hide lookup table if there are
        # no candidates to display. On f17, this makes no
        # difference but gnome-shell in f18 will display
        # an empty suggestion popup if the number of candidates
        # is zero!
        if (self.is_empty()
            or self._hide_input
            or self.get_lookup_table().get_number_of_candidates() == 0
            or (self._tab_enable and not self.is_lookup_table_enabled_by_tab)):
            self.hide_lookup_table()
            self._update_preedit()
            return
        if (not self._inline_completion
            or self.get_lookup_table().get_cursor_pos() != 0):
            # Show standard lookup table:
            self.update_lookup_table(self.get_lookup_table(), True)
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
            self.update_lookup_table(self.get_lookup_table(), True)
            self._update_preedit()
            return
        # Show only the first candidate, inline in the preëdit, hide
        # the lookup table and the auxiliary text:
        completion = first_candidate[len(typed_string):]
        self.hide_lookup_table()
        text = IBus.Text.new_from_string('')
        super().update_auxiliary_text(text, False)
        text = IBus.Text.new_from_string(typed_string + completion)
        attrs = IBus.AttrList()
        attrs.append(IBus.attr_underline_new(
            self._preedit_underline, 0, len(typed_string)))
        if self.get_lookup_table().cursor_visible:
            attrs.append(IBus.attr_underline_new(
                self._preedit_underline,
                len(typed_string), len(typed_string + completion)))
        else:
            if (self._color_preedit_spellcheck
                and len(typed_string) >= 4
                and not self.database.hunspell_obj.spellcheck(typed_string)):
                attrs.append(IBus.attr_foreground_new(
                    self._color_preedit_spellcheck_argb, 0, len(typed_string)))
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
        if (self._lookup_table_is_invalid
            and self._auto_select_candidate
            and self.get_lookup_table().get_number_of_candidates()
            and not self._lookup_table.cursor_visible):
            self._lookup_table.set_cursor_visible(True)
            self._is_candidate_auto_selected = True
        self._update_lookup_table()
        self._lookup_table_is_invalid = False

    def _update_candidates_and_lookup_table_and_aux(self) -> None:
        '''Update the candidates, the lookup table and the auxiliary text'''
        self._update_candidates()
        self._update_lookup_table_and_aux()

    def _update_ui(self) -> None:
        '''Update User Interface'''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('entering function')
        self._update_preedit()
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
            self._current_auxiliary_text = IBus.Text.new_from_string('')
            super().update_auxiliary_text(
                self._current_auxiliary_text, False)
            return
        self._lookup_table_shows_related_candidates = False
        if self._lookup_table_is_invalid:
            return
        self._lookup_table_is_invalid = True
        # Don’t show the lookup table if it is invalid anway
        self.get_lookup_table().clear()
        self.get_lookup_table().set_cursor_visible(False)
        self.hide_lookup_table()
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
        try:
            import itb_nltk
            for synonym in itb_nltk.synonyms(phrase, keep_original=False):
                related_candidates.append((synonym, '[synonym]', 0))
            for hypernym in itb_nltk.hypernyms(phrase, keep_original=False):
                related_candidates.append((hypernym, '[hypernym]', 0))
            for hyponym in itb_nltk.hyponyms(phrase, keep_original=False):
                related_candidates.append((hyponym, '[hyponym]', 0))
        except (ImportError, LookupError):
            pass
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
            return
        self._candidates = []
        self.get_lookup_table().clear()
        self.get_lookup_table().set_cursor_visible(False)
        for cand in related_candidates:
            self._candidates.append((cand[0], cand[2], cand[1], False, False))
            self._append_candidate_to_lookup_table(
                phrase=cand[0], user_freq=cand[2], comment=cand[1])
        self._update_lookup_table_and_aux()
        self._lookup_table_shows_related_candidates = True

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
        :rtype: Boolean
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
        :rtype: Boolean
        :param index: The index of the candidate to remove in the lookup table
        :type index: Integer
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
        if not self.get_lookup_table().get_number_of_candidates():
            return False
        candidate_number = (
            self._get_lookup_table_current_page() * self._page_size + index)
        if not (candidate_number
            < self._lookup_table.get_number_of_candidates()
            and 0 <= index < self._page_size):
            return False
        phrase = self.get_string_from_lookup_table_current_page(index)
        if phrase:
            self._commit_string(phrase + extra_text)
            return True
        return False

    def _commit_string(
            self,
            commit_phrase: str,
            input_phrase: str = '') -> None:
        '''Commits a string

        Also updates the context and the user database of learned
        input.

        May remove whitespace before the committed string if
        the committed string ended a sentence.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('(%s, %s)', commit_phrase, input_phrase)
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
        pattern_non_white_space = re.compile(r'\S')
        if pattern_non_white_space.search(commit_phrase):
            pattern_new_sentence = re.compile(
                r'['
                + re.escape(itb_util.AUTO_CAPITALIZE_CHARACTERS)
                + r']+[\s]*$')
            self._new_sentence = False
            if pattern_new_sentence.search(commit_phrase):
                self._new_sentence = True
        if (self.client_capabilities & IBus.Capabilite.SURROUNDING_TEXT
            and self._input_purpose not in [itb_util.InputPurpose.TERMINAL]):
            # If a single character ending a sentence is committed
            # (possibly followed by whitespace) remove trailing white
            # space before the committed string. For example if
            # commit_phrase is “!”, and the context before is “word ”,
            # make the result “word!”.  And if the commit_phrase is “!
            # ” and the context before is “word ” make the result
            # “word! ”.
            pattern_sentence_end = re.compile(
                r'^['
                + re.escape(itb_util.REMOVE_WHITESPACE_CHARACTERS)
                + r']+[\s]*$')
            if pattern_sentence_end.search(commit_phrase):
                surrounding_text = self.get_surrounding_text()
                text = surrounding_text[0].get_text()
                cursor_pos = surrounding_text[1]
                anchor_pos = surrounding_text[2]
                if DEBUG_LEVEL > 1:
                    LOGGER.debug(
                        'Checking for whitespace before sentence end char. '
                        'surrounding_text = '
                        '[text = "%s", cursor_pos = %s, anchor_pos = %s]',
                        text, cursor_pos, anchor_pos)
                # The commit_phrase is *not* yet in the surrounding text,
                # it will show up there only when the next key event is
                # processed:
                pattern = re.compile(r'(?P<white_space>[\s]+)$')
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
                            'Removed whitespace before sentence end char. '
                            'surrounding_text = '
                            '[text = "%s", cursor_pos = %s, anchor_pos = %s]',
                            text, cursor_pos, anchor_pos)
        if self._qt_im_module_workaround:
            super().commit_text(
                IBus.Text.new_from_string(commit_phrase))
        else:
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
        self._clear_input_and_update_ui()
        self._commit_happened_after_focus_in = True
        if self._off_the_record or self._hide_input:
            return
        stripped_commit_phrase = itb_util.strip_token(commit_phrase)
        stripped_input_phrase = itb_util.strip_token(input_phrase)
        if not stripped_commit_phrase or not stripped_input_phrase:
            return
        self.database.check_phrase_and_update_frequency(
            input_phrase=stripped_input_phrase,
            phrase=stripped_commit_phrase,
            p_phrase=self.get_p_phrase(),
            pp_phrase=self.get_pp_phrase())
        if (self.get_p_phrase()
            and self.get_pp_phrase()
            and self.get_ppp_phrase()):
            # Commit the current commit phrase and the previous
            # phrase as a single unit as well for better
            # completions. For example, if the current commit
            # phrase is “to” and the total context was “I am
            # going”, then also commit “going to” with the context
            # “I am”:
            self.database.check_phrase_and_update_frequency(
                input_phrase=
                self.get_p_phrase() + ' ' + stripped_commit_phrase,
                phrase=self.get_p_phrase() + ' ' + stripped_commit_phrase,
                p_phrase=self.get_pp_phrase(),
                pp_phrase=self.get_ppp_phrase())
        # push context after recording in the database is finished:
        self.push_context(stripped_commit_phrase)

    def _reopen_preedit_or_return_false(
            self,
            key: itb_util.KeyEvent) -> bool:
        '''BackSpace, Delete or arrow left or right has been typed.

        If the end of a word has been reached again and if it is
        possible to get that word back into preëdit, do that and
        return True.

        If not end of a word has been reached or it is impossible to
        get the word back into preëdit, use _return_false(key.val,
        key.code, key.state) to pass the key to the application.

        :rtype: Boolean

        '''
        if (not self.client_capabilities & IBus.Capabilite.SURROUNDING_TEXT
            or self._input_purpose in [itb_util.InputPurpose.TERMINAL]):
            return self._return_false(key.val, key.code, key.state)
        surrounding_text = self.get_surrounding_text()
        text = surrounding_text[0].get_text()
        cursor_pos = surrounding_text[1]
        dummy_anchor_pos = surrounding_text[2]
        if not surrounding_text:
            return self._return_false(key.val, key.code, key.state)
        if not self._commit_happened_after_focus_in:
            # Before the first commit or cursor movement, the
            # surrounding text is probably from the previously
            # focused window (bug!), don’t use it.
            return self._return_false(key.val, key.code, key.state)
        if (not self._arrow_keys_reopen_preedit
                and key.val in (IBus.KEY_Left, IBus.KEY_KP_Left,
                                IBus.KEY_Right, IBus.KEY_KP_Right,
                                IBus.KEY_BackSpace,
                                IBus.KEY_Delete, IBus.KEY_KP_Delete)):
            # using arrows key to reopen the preëdit is disabled
            return self._return_false(key.val, key.code, key.state)
        if (key.shift
            or key.control
            or key.mod1
            or key.mod2
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
            # *Except* for CapsLock. CapsLock causes no problems at
            # all for reopening the preëdit, so we don’t want to check
            # for key.modifier which would include key.lock but check
            # for the modifiers which cause problems individually.
            return self._return_false(key.val, key.code, key.state)
        if key.val in (IBus.KEY_BackSpace, IBus.KEY_Left, IBus.KEY_KP_Left):
            pattern = re.compile(
                r'(^|.*[\s]+)(?P<token>[\S]+)[\s]$')
            match = pattern.match(text[:cursor_pos])
            if not match:
                return self._return_false(key.val, key.code, key.state)
            # The pattern has matched, i.e. left of the cursor is
            # a single whitespace and left of that a token was
            # found.
            token = match.group('token')
            # Delete the whitespace and the token from the
            # application.
            if key.val in (IBus.KEY_BackSpace,):
                self.delete_surrounding_text(-1-len(token), 1+len(token))
            else:
                self.forward_key_event(key.val, key.code, key.state)
                # The sleep is needed because this is racy, without the
                # sleep it works unreliably.
                time.sleep(self._ibus_event_sleep_seconds)
                self.delete_surrounding_text(-len(token), len(token))
            # get the context to the left of the token:
            self.get_context()
            # put the token into the preedit again
            self._insert_string_at_cursor(list(token))
            # update the candidates.
            self._update_ui()
            return True
        if key.val in (IBus.KEY_Delete, IBus.KEY_KP_Delete,
                       IBus.KEY_Right, IBus.KEY_KP_Right):
            pattern = re.compile(
                r'^[\s](?P<token>[\S]+)($|[\s]+.*)')
            match = pattern.match(text[cursor_pos:])
            if not match:
                return self._return_false(key.val, key.code, key.state)
            token = match.group('token')
            if key.val in (IBus.KEY_Delete, IBus.KEY_KP_Delete):
                self.delete_surrounding_text(0, len(token) + 1)
            else:
                self.forward_key_event(key.val, key.code, key.state)
                # The sleep is needed because this is racy, without the
                # sleep it works unreliably.
                time.sleep(self._ibus_event_sleep_seconds)
                self.delete_surrounding_text(0, len(token))
            # get the context to the left of the token:
            self.get_context()
            # put the token into the preedit again
            self._insert_string_at_cursor(list(token))
            self._typed_string_cursor = 0
            # update the candidates.
            self._update_ui()
            return True
        return self._return_false(key.val, key.code, key.state)

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
        if (not self.client_capabilities & IBus.Capabilite.SURROUNDING_TEXT
            or self._input_purpose in [itb_util.InputPurpose.TERMINAL]):
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
                '[text = "%s", cursor_pos = %s, anchor_pos = %s]',
                repr(text), cursor_pos, anchor_pos)
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
            mode: Union[bool, Any],
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
                GLib.Variant.new_boolean(mode))

    def toggle_inline_completion(self, update_gsettings: bool = True) -> None:
        '''Toggles whether the best completion is first shown inline in the
        preëdit instead of using a combobox to show a candidate list.

        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean

        '''
        self.set_inline_completion(
            not self._inline_completion, update_gsettings)

    def get_inline_completion(self) -> bool:
        '''Returns the current value of the flag whether to show a completion
        first inline in the preëdit instead of using a combobox to show a
        candidate list.

        :rtype: boolean
        '''
        return self._inline_completion

    def set_auto_capitalize(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to capitalize automatically after punctuation

        :param mode: Whether to automatically capitalize after punctuation.
        :type mode: boolean
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean

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
        :type update_gsettings: boolean

        '''
        self.set_auto_capitalize(
            not self._auto_capitalize, update_gsettings)

    def get_auto_capitalize(self) -> bool:
        '''Returns the current value of the flag whether to show a completion
        first inline in the preëdit instead of using a combobox to show a
        candidate list.
        '''
        return self._auto_capitalize

    def set_qt_im_module_workaround(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether the workaround for the qt im module is used or not

        :param mode: Whether to use the workaround for the qt im module or not
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._qt_im_module_workaround:
            return
        self._qt_im_module_workaround = mode
        if update_gsettings:
            self._gsettings.set_value(
                'qtimmoduleworkaround',
                GLib.Variant.new_boolean(mode))

    def toggle_qt_im_module_workaround(
            self, update_gsettings: bool = True) -> None:
        '''Toggles whether the workaround for the qt im module is used or not

        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        self.set_qt_im_module_workaround(
            not self._qt_im_module_workaround, update_gsettings)

    def get_qt_im_module_workaround(self) -> bool:
        '''Returns the current value of the flag to enable
        a workaround for the qt im module
        '''
        return self._qt_im_module_workaround

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
        if self._prop_dict and self.input_mode_menu:
            self._init_or_update_property_menu(
                self.input_mode_menu, mode)
        self._clear_input_and_update_ui()
        if update_gsettings:
            self._gsettings.set_value(
                'inputmode',
                GLib.Variant.new_boolean(mode))

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
        :type update_gsettings: boolean
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
        :type label_string: String
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', label_string, update_gsettings)
        if label_string == self._label_dictionary_string:
            return
        self._label_dictionary_string = label_string
        if update_gsettings:
            self._gsettings.set_value(
                'labeldictionarystring',
                GLib.Variant.new_string(label_string))

    def get_label_dictionary_string(self) -> str:
        '''Returns the current value of the “label dictionary” string'''
        return self._label_dictionary_string

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
        :type mode: boolean
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
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
        :type mode: integer >= 0 and <= 2
                    IBUS_ORIENTATION_HORIZONTAL = 0,
                    IBUS_ORIENTATION_VERTICAL   = 1,
                    IBUS_ORIENTATION_SYSTEM     = 2.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        :type update_gsettings: boolean
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
            update_gsettings=True) -> None:
        '''Sets the minimum number of characters to try completion

        :param min_char_complete: The minimum number of characters
                                  to type before completion is tried.
                                  1 <= min_char_complete <= 9
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
        if 1 <= min_char_complete <= 9:
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
        global DEBUG_LEVEL
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
            self, path: Union[str, Any], update_gsettings: bool = True) -> None:
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
                "errorsoundfile",
                GLib.Variant.new_string(path))
        path = os.path.expanduser(path)
        if not IMPORT_SIMPLEAUDIO_SUCCESSFUL:
            LOGGER.info(
                'No error sound because python3-simpleaudio is not available.')
        else:
            if not os.path.isfile(path):
                LOGGER.info('Error sound file %s does not exist.', path)
            elif not os.access(path, os.R_OK):
                LOGGER.info('Error sound file %s not readable.', path)
            else:
                try:
                    LOGGER.info(
                        'Trying to initialize error sound from %s', path)
                    self._error_sound_object = (
                        simpleaudio.WaveObject.from_wave_file(path))
                    LOGGER.info('Error sound initialized.')
                except (FileNotFoundError, PermissionError):
                    LOGGER.exception(
                        'Initializing error sound object failed.')
                except:
                    LOGGER.exception(
                        'Initializing error sound object failed.')

    def get_error_sound_file(self) -> str:
        '''
        Return the path of the .wav file containing the error sound.
        '''
        return self._error_sound_file

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
            mode: Union[bool, Any],
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
                GLib.Variant.new_boolean(mode))

    def get_auto_select_candidate(self) -> bool:
        '''Returns the current value of the
        “Automatically select the best candidate” mode
        '''
        return self._auto_select_candidate

    def do_candidate_clicked(
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
        :type error_message: String
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
        except Exception:
            LOGGER.exception(
                'Exception when intializing Google speech-to-text')
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
        flag = itb_util.FLAGS.get(language_code.replace('-', '_'), '')
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
            except Exception:
                LOGGER.exception('Google speech-to-text error')
                self._speech_recognition_error(
                    _('Google speech-to-text error. See debug.log.'))
                return

        if transcript:
            # Uppercase first letter of transcript if the text left
            # of the cursor ends with a sentence ending character
            # or if the text left of the cursor is empty.
            # If surrounding text cannot be used, uppercase the
            # first letter unconditionally:
            if (not self.client_capabilities & IBus.Capabilite.SURROUNDING_TEXT
                or self._input_purpose in [itb_util.InputPurpose.TERMINAL]):
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
                        '[text = "%s", cursor_pos = %s, anchor_pos = %s]',
                        text, cursor_pos, anchor_pos)
                    LOGGER.debug('text_left = %s', text_left)
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
        if self.is_empty():
            return False
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
            self.set_current_imes(
                imes[1:] + imes[:1],
                update_gsettings=self._remember_last_used_preedit_ime)
            return True
        return False

    def _command_previous_input_method(self) -> bool:
        '''Handle hotkey for the command “previous_input_method”

        :return: True if the key was completely handled, False if not.
        '''
        imes = self.get_current_imes()
        if len(imes) > 1:
            # remove the last ime in the list and add it in front:
            self.set_current_imes(
                imes[-1:] + imes[:-1],
                update_gsettings=self._remember_last_used_preedit_ime)
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
            self.set_dictionary_names(
                names[1:] + names[:1],
                update_gsettings=True)
            return True
        return False

    def _command_previous_dictionary(self) -> bool:
        '''Handle hotkey for the command “previous_dictionary”

        :return: True if the key was completely handled, False if not.
        '''
        names = self.get_dictionary_names()
        if len(names) > 1:
            # remove the last dictionary in the list and add it in front:
            self.set_dictionary_names(
                names[-1:] + names[:-1],
                update_gsettings=True)
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
        :rtype: Boolean
        '''
        self._hide_input = not self._hide_input
        self._update_ui()
        return True

    def _command_setup(self) -> bool:
        '''Handle hotkey for the command “setup”

        :return: True if the key was completely handled, False if not.
        :rtype: Boolean
        '''
        self._start_setup()
        return True

    def _command_commit_candidate_1(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_1”

        :return: True if the key was completely handled, False if not.
        :rtype: Boolean
        '''
        return self._commit_candidate(0, extra_text='')

    def _command_commit_candidate_1_plus_space(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_1_plus_space”

        :return: True if the key was completely handled, False if not.
        :rtype: Boolean
        '''
        return self._commit_candidate(0, extra_text=' ')

    def _command_remove_candidate_1(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_1”

        :return: True if the key was completely handled, False if not.
        :rtype: Boolean
        '''
        return self._remove_candidate(0)

    def _command_commit_candidate_2(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_2”

        :return: True if the key was completely handled, False if not.
        :rtype: Boolean
        '''
        return self._commit_candidate(1, extra_text='')

    def _command_commit_candidate_2_plus_space(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_2_plus_space”

        :return: True if the key was completely handled, False if not.
        :rtype: Boolean
        '''
        return self._commit_candidate(1, extra_text=' ')

    def _command_remove_candidate_2(self) -> bool:
        '''Handle hotkey for the command “remove_candidate_2”

        :return: True if the key was completely handled, False if not.
        :rtype: Boolean
        '''
        return self._remove_candidate(1)

    def _command_commit_candidate_3(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_3”

        :return: True if the key was completely handled, False if not.
        :rtype: Boolean
        '''
        return self._commit_candidate(2, extra_text='')

    def _command_commit_candidate_3_plus_space(self) -> bool:
        '''Handle hotkey for the command “commit_candidate_3_plus_space”

        :return: True if the key was completely handled, False if not.
        :rtype: Boolean
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
            commands: Iterable[str] = ()) -> bool:
        '''Handle hotkey commands

        :return: True if the key was completely handled, False if not.
        :param key: The typed key. If this is a hotkey,
                    execute the command for this hotkey.
        :type key: KeyEvent object
        :param commands: A list of commands to check whether
                         the key matches the keybinding for one of
                         these commands.
                         If the list of commands is empty, check
                         *all* commands in the self._keybindings
                         dictionary.
        :type commands: List of strings
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
        for command in commands:
            if (self._prev_key, key, command) in self._hotkeys: # type: ignore
                if DEBUG_LEVEL > 1:
                    LOGGER.debug('matched command=%s', command)
                command_function_name = '_command_%s' % command
                try:
                    command_function = getattr(self, command_function_name)
                except (AttributeError,):
                    LOGGER.exception('There is no function %s',
                                     command_function_name)
                    return False
                if command_function():
                    return True
        return False

    def _return_false(self, keyval: int, keycode: int, state: int) -> bool:
        '''A replacement for “return False” in do_process_key_event()

        do_process_key_event should return “True” if a key event has
        been handled completely. It should return “False” if the key
        event should be passed to the application.

        But just doing “return False” doesn’t work well when trying to
        do the unit tests. The MockEngine class in the unit tests
        cannot get that return value. Therefore, it cannot do the
        necessary updates to the self._mock_committed_text etc. which
        prevents proper testing of the effects of such keys passed to
        the application. Instead of “return False”, one can also use
        self.forward_key_event(keyval, keycode, keystate) to pass the
        key to the application. And this works fine with the unit
        tests because a forward_key_event function is implemented in
        MockEngine as well which then gets the key and can test its
        effects.

        Unfortunately, “forward_key_event()” does not work in Qt5
        applications because the ibus module in Qt5 does not implement
        “forward_key_event()”. Therefore, always using
        “forward_key_event()” instead of “return False” in
        “do_process_key_event()” would break ibus-typing-booster
        completely for all Qt5 applictions.

        To work around this problem and make unit testing possible
        without breaking Qt5 applications, we use this helper function
        which uses “forward_key_event()” when unit testing and “return
        False” during normal usage.

        '''
        if self._unit_test:
            self.forward_key_event(keyval, keycode, state)
            return True
        return False

    def _forward_key_event_left(self) -> None:
        '''Forward an arrow left event to the application.'''
        # Without using a correct ibus key code, this does not work
        # correctly, i.e. self.forward_key_event(IBus.KEY_Left, 0, 0)
        # does *not* work anymore!
        #
        # The ibus key code for IBus.KEY_Left is usually 105, but
        # it could be different on an unusual keyboard layout.
        # It is better to make sure and calculate it correctly
        # for the current layout.
        self.forward_key_event(
            IBus.KEY_Left,
            self._keyvals_to_keycodes.ibus_keycode(IBus.KEY_Left),
            0)

    def _handle_compose(self, key: itb_util.KeyEvent) -> bool:
        '''Internal method to handle possible compose keys

        :return: True if the key event has been handled, else False
        ;rtype: Boolean
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('KeyEvent object: %s', key)
        if key.state & IBus.ModifierType.RELEASE_MASK:
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Ignoring release event.')
            return False
        if (not self._typed_compose_sequence
            and not key.name == 'Multi_key'
            and not key.name.startswith('dead_')):
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Not in a compose sequence.')
            return False
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
            self._typed_compose_sequence = self._typed_compose_sequence[:-1]
        else:
            self._typed_compose_sequence.append(key.val)
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
        self.hide_lookup_table()
        self._current_auxiliary_text = IBus.Text.new_from_string('')
        super().update_auxiliary_text(
            self._current_auxiliary_text, False)
        if not isinstance(compose_result, str):
            self._update_transliterated_strings()
            self._update_preedit()
            return True
        if DEBUG_LEVEL > 1:
            LOGGER.debug('Compose sequence finished.')
        self._typed_compose_sequence = []
        self._update_transliterated_strings()
        self._update_preedit()
        if not compose_result:
            if DEBUG_LEVEL > 1:
                LOGGER.debug('Finished compose sequence is empty.')
            if self._error_sound and self._error_sound_object:
                dummy = self._error_sound_object.play()
        if compose_result:
            if self.get_input_mode():
                self._insert_string_at_cursor(list(compose_result))
                self._update_ui()
            else:
                super().commit_text(
                    IBus.Text.new_from_string(compose_result))
        return True

    def do_process_key_event(
            self, keyval: int, keycode: int, state: int) -> bool:
        '''Process Key Events
        Key Events include Key Press and Key Release,
        modifier means Key Pressed
        '''
        key = itb_util.KeyEvent(keyval, keycode, state)
        if DEBUG_LEVEL > 1:
            LOGGER.debug('KeyEvent object: %s', key)

        if self._handle_compose(key):
            return True

        if self._handle_hotkeys(key, commands=['toggle_input_mode_on_off']):
            return True

        if (not self._input_mode
            or (self._input_purpose
                in [itb_util.InputPurpose.PASSWORD,
                    itb_util.InputPurpose.PIN])):
            return self._return_false(keyval, keycode, state)

        if self._handle_hotkeys(key):
            return True

        result = self._process_key_event(key)
        self._prev_key = key
        return result

    def _process_key_event(self, key: itb_util.KeyEvent) -> bool:
        '''Internal method to process key event

        :return: True if the key event has been completely handled by
                 ibus-typing-booster and should not be passed through anymore.
                 False if the key event has not been handled completely
                 and is passed through.
        '''
        # Ignore (almost all) key release events
        if key.state & IBus.ModifierType.RELEASE_MASK:
            return self._return_false(key.val, key.code, key.state)

        if self.is_empty():
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
                return self._return_false(key.val, key.code, key.state)
            if key.val == IBus.KEY_space and not key.mod5:
                # if the first character is a space, just pass it through
                # it makes not sense trying to complete (“not key.mod5” is
                # checked here because AltGr+Space is the key binding to
                # insert a literal space into the preëdit):
                return self._return_false(key.val, key.code, key.state)
            if key.val in (IBus.KEY_BackSpace,
                           IBus.KEY_Left, IBus.KEY_KP_Left,
                           IBus.KEY_Delete, IBus.KEY_KP_Delete,
                           IBus.KEY_Right, IBus.KEY_KP_Right):
                return self._reopen_preedit_or_return_false(key)
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
                        return self._return_false(key.val, key.code, key.state)
                    # If a digit has been typed and we use
                    # transliteration, we may want to convert it to
                    # native digits. For example, with mr-inscript we
                    # want “3” to be converted to “३”. So we try
                    # to transliterate and commit the result:
                    transliterated_digit = self._transliterators[
                        self.get_current_imes()[0]
                    ].transliterate([key.msymbol])
                    self._commit_string(
                        transliterated_digit,
                        input_phrase=transliterated_digit)
                    return True

        # These keys may trigger a commit:
        if (key.msymbol not in ('G- ',)
            and (key.val in (IBus.KEY_space, IBus.KEY_Tab,
                             IBus.KEY_Return, IBus.KEY_KP_Enter,
                             IBus.KEY_Right, IBus.KEY_KP_Right,
                             IBus.KEY_Delete, IBus.KEY_KP_Delete,
                             IBus.KEY_Left, IBus.KEY_KP_Left,
                             IBus.KEY_BackSpace,
                             IBus.KEY_Down, IBus.KEY_KP_Down,
                             IBus.KEY_Up, IBus.KEY_KP_Up,
                             IBus.KEY_Page_Down,
                             IBus.KEY_KP_Page_Down,
                             IBus.KEY_KP_Next,
                             IBus.KEY_Page_Up,
                             IBus.KEY_KP_Page_Up,
                             IBus.KEY_KP_Prior)
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
                # into the preëdit, if possible.
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
            if self.is_empty():
                return self._return_false(key.val, key.code, key.state)
            if (not self.get_lookup_table().cursor_visible
                or self._is_candidate_auto_selected):
                # Nothing is *manually* selected in the lookup table,
                # the edit keys like Right, Left, BackSpace, and
                # Delete edit the preëdit (If something is selected in
                # the lookup table, they should cause a commit,
                # especially when inline completion is used and the
                # first candidate is selected, editing the preëdit is
                # confusing):
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
            # This key does not only a cursor movement in the preëdit,
            # it really triggers a commit.
            if DEBUG_LEVEL > 1:
                LOGGER.debug('_process_key_event() commit triggered.\n')
            # We need to transliterate
            # the preëdit again here, because adding the commit key to
            # the input might influence the transliteration. For example
            # When using hi-itrans, “. ” translates to “। ”
            # (See: https://bugzilla.redhat.com/show_bug.cgi?id=1353672)
            preedit_ime = self._current_imes[0]
            input_phrase = self._transliterators[
                preedit_ime].transliterate(
                    self._typed_string + [key.msymbol])
            input_phrase = self._case_modes[
                self._current_case_mode]['function'](input_phrase)
            # If the transliteration now ends with the commit key, cut
            # it off because the commit key is passed to the
            # application later anyway and we do not want to pass it
            # twice:
            if key.msymbol and input_phrase.endswith(key.msymbol):
                input_phrase = input_phrase[:-len(key.msymbol)]
            if (self.get_lookup_table().get_number_of_candidates()
                and self.get_lookup_table().cursor_visible):
                # something is selected in the lookup table, commit
                # the selected phrase
                commit_string = self.get_string_from_lookup_table_cursor_pos()
            elif (key.val in (IBus.KEY_Return, IBus.KEY_KP_Enter)
                  and (self._typed_string_cursor
                       < len(self._typed_string))):
                # “Return” or “Enter” is used to commit the preëdit
                # while the cursor is not at the end of the preëdit.
                # That means the part of the preëdit to the left of
                # the cursor should be commited first, then the
                # “Return” or enter should be forwarded to the
                # application, then the part of the preëdit to the
                # right of the cursor should be committed.
                input_phrase_left = (
                    self._transliterators[preedit_ime].transliterate(
                        self._typed_string[:self._typed_string_cursor]))
                input_phrase_left = self._case_modes[
                    self._current_case_mode]['function'](input_phrase_left)
                input_phrase_right = (
                    self._transliterators[preedit_ime].transliterate(
                        self._typed_string[self._typed_string_cursor:]))
                if self._current_case_mode == 'upper':
                    input_phrase_right = self._case_modes[
                        self._current_case_mode]['function'](
                            input_phrase_right)
                if input_phrase_left:
                    self._commit_string(
                        input_phrase_left, input_phrase=input_phrase_left)
                # The sleep is needed because this is racy, without the
                # sleep it works unreliably.
                time.sleep(self._ibus_event_sleep_seconds)
                self.forward_key_event(key.val, key.code, key.state)
                self._commit_string(
                    input_phrase_right, input_phrase=input_phrase_right)
                for dummy_char in input_phrase_right:
                    self._forward_key_event_left()
                return True
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
                return self._return_false(key.val, key.code, key.state)
            forward_arrow_left_events_ok = False
            if not self.get_lookup_table().cursor_visible:
                forward_arrow_left_events_ok = True
            self._commit_string(commit_string, input_phrase=input_phrase)
            if (key.val
                in (IBus.KEY_Left, IBus.KEY_KP_Left, IBus.KEY_BackSpace)
                and forward_arrow_left_events_ok):
                # After committing, the cursor is at the right
                # side of the committed string. When the string
                # has been committed because arrow-left or
                # control-arrow-left or backspace reached the left
                # side of the preëdit, the cursor has to be moved
                # to the left side of the string. This should be
                # done in a way which works even when surrounding
                # text is not supported. We can do it by
                # forwarding as many arrow-left events to the
                # application as the committed string has
                # characters.
                #
                # Note that when a candidate is selected, the cursor
                # is the selected candidated is committed and the then
                # it is correct that the cursor is at the right side
                # of the committed candidate, so no left key events
                # are necessary in that case.
                for dummy_char in commit_string:
                    self._forward_key_event_left()
                # The sleep is needed because this is racy, without the
                # sleep it works unreliably.
                time.sleep(self._ibus_event_sleep_seconds)
                if self._reopen_preedit_or_return_false(key):
                    return True
            if key.val in (IBus.KEY_Right, IBus.KEY_KP_Right,
                           IBus.KEY_Delete, IBus.KEY_KP_Delete):
                if self._reopen_preedit_or_return_false(key):
                    return True
            # Forward the key event which triggered the commit here
            # and return True instead of trying to pass that key event
            # to the application by returning False. Doing it by
            # returning false works correctly in GTK applications
            # and Qt applications when using the ibus module of Qt.
            # But not when using XIM, i.e. not when using Qt with the XIM
            # module and not in X11 applications like xterm.
            #
            # When “return False” is used, the key event which
            # triggered the commit here arrives *before* the committed
            # string when XIM is used. I.e. when typing “word ” the
            # space which triggered the commit gets to application
            # first and the applications receives “ word”. No amount
            # of sleep before the “return False” can fix this. See:
            # https://bugzilla.redhat.com/show_bug.cgi?id=1291238
            if self._qt_im_module_workaround:
                return self._return_false(key.val, key.code, key.state)
            self.forward_key_event(key.val, key.code, key.state)
            return True

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
            if (key.msymbol in ('G- ',)
                and not self._has_transliteration([key.msymbol])):
                insert_msymbol = ' '
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
            self._update_ui()
            return True

        # What kind of key was this??
        #
        # The unicode character for this key is apparently the empty
        # string.  And apparently it was not handled as a select key
        # or other special key either.  So whatever this was, we
        # cannot handle it, just pass it through to the application by
        # returning “False”.
        return self._return_false(key.val, key.code, key.state)

    def do_focus_in(self) -> None:
        '''Called when a window gets focus while this input engine is enabled

        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('do_focus_in()\n')
        self._keyvals_to_keycodes = itb_util.KeyvalsToKeycodes()
        self.register_properties(self.main_prop_list)
        self.clear_context()
        self._commit_happened_after_focus_in = False
        self._update_ui()

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
        if not input_phrase:
            input_phrase = self._transliterated_strings[
                self.get_current_imes()[0]]
        if not commit_phrase:
            typed_string = unicodedata.normalize('NFC', input_phrase)
            first_candidate = ''
            if self._candidates:
                first_candidate = self._candidates[0][0]
            if (not self._inline_completion
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
        if not self._off_the_record and not self._hide_input:
            self.database.check_phrase_and_update_frequency(
                input_phrase=stripped_input_phrase,
                phrase=stripped_commit_phrase,
                p_phrase=self.get_p_phrase(),
                pp_phrase=self.get_pp_phrase())
            self.push_context(stripped_commit_phrase)

    def do_focus_out(self) -> None:
        '''Called when a window looses focus while this input engine is
        enabled

        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('do_focus_out()\n')
        self._input_purpose = 0
        # The preëdit, if there was any, has already been committed
        # automatically because
        # update_preedit_text_with_mode(,,,IBus.PreeditFocusMode.COMMIT)
        # has been used. But the contents of the preëdit have not
        # been recorded in the user database yet. Do it now:
        if not self.is_empty():
            self._record_in_database_and_push_context()
        self.clear_context()
        self._clear_input_and_update_ui()

    def do_reset(self) -> None:
        '''Called when the mouse pointer is used to move to cursor to a
        different position in the current window.

        Also called when certain keys are pressed:

            Return, KP_Enter, ISO_Enter, Up, Down, (and others?)
        '''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('do_reset()\n')
        if self._prev_key is not None and self._prev_key.val in (
                IBus.KEY_Return, IBus.KEY_KP_Enter, IBus.KEY_ISO_Enter):
            # The “Return” and “KP_Enter” keys trigger a call to
            # do_reset().  But I don’t want to clear the context, in
            # that case, Usually this just means that one continues to
            # write in the next line and the context is still valid.
            return
        # The preëdit, if there was any, has already been committed
        # automatically because
        # update_preedit_text_with_mode(,,,IBus.PreeditFocusMode.COMMIT)
        # has been used. But the contents of the preëdit have not
        # been recorded in the user database yet. Do it now:
        if not self.is_empty():
            self._record_in_database_and_push_context()
        self.clear_context()
        self._clear_input_and_update_ui()

    def do_set_content_type(self, purpose: int, hints: int) -> None:
        '''Called when the input purpose or hints change'''
        LOGGER.debug('purpose=%s hints=%s\n', purpose, format(hints, '016b'))
        self._input_purpose = purpose
        self._input_hints = hints
        if DEBUG_LEVEL > 1:
            if self._input_purpose in list(itb_util.InputPurpose):
                for input_purpose in list(itb_util.InputPurpose):
                    if self._input_purpose == input_purpose:
                        LOGGER.debug(
                            'self._input_purpose = %s (%s)',
                            self._input_purpose, str(input_purpose))
            else:
                LOGGER.debug(
                    'self._input_purpose = %s (Unknown)',
                    self._input_purpose)
            for hint in list(itb_util.InputHints):
                if self._input_hints & hint:
                    LOGGER.debug(
                        'hint: %s %s',
                        str(hint), format(int(hint), '016b'))

    def do_enable(self) -> None:
        '''Called when this input engine is enabled'''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('do_enable()\n')
        # Tell the input-context that the engine will utilize
        # surrounding-text:
        self.get_surrounding_text()
        self.do_focus_in()

    def do_disable(self) -> None:
        '''Called when this input engine is disabled'''
        if DEBUG_LEVEL > 1:
            LOGGER.debug('do_disable()\n')
        self._clear_input_and_update_ui()

    def do_page_up(self) -> bool:
        '''Called when the page up button in the lookup table is clicked with
        the mouse

        '''
        if self._page_up():
            self._update_lookup_table_and_aux()
            return True
        return True

    def do_page_down(self) -> bool:
        '''Called when the page down button in the lookup table is clicked with
        the mouse

        '''
        if self._page_down():
            self._update_lookup_table_and_aux()
            return True
        return False

    def do_cursor_up(self) -> bool:
        '''Called when the mouse wheel is rolled up in the candidate area of
        the lookup table

        '''
        res = self._arrow_up()
        self._update_lookup_table_and_aux()
        return res

    def do_cursor_down(self) -> bool:
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

    def on_gsettings_value_changed(self, _settings, key) -> None:
        '''
        Called when a value in the settings has been changed.

        :param settings: The settings object
        :type settings: Gio.Settings object
        :param key: The key of the setting which has changed
        :type key: String
        '''
        value = itb_util.variant_to_value(self._gsettings.get_value(key))
        LOGGER.debug('Settings changed: key=%s value=%s\n', key, value)
        set_functions = {
            'inputmethod': self.set_current_imes,
            'dictionary':  self.set_dictionary_names,
            'dictionaryinstalltimestamp': self._reload_dictionaries,
            'qtimmoduleworkaround': self.set_qt_im_module_workaround,
            'addspaceoncommit': self.set_add_space_on_commit,
            'inlinecompletion': self.set_inline_completion,
            'autocapitalize': self.set_auto_capitalize,
            'arrowkeysreopenpreedit': self.set_arrow_keys_reopen_preedit,
            'emojipredictions': self.set_emoji_prediction_mode,
            'offtherecord': self.set_off_the_record_mode,
            'autocommitcharacters': self.set_auto_commit_characters,
            'tabenable': self.set_tab_enable,
            'rememberlastusedpreeditime':
            self.set_remember_last_used_preedit_ime,
            'rememberinputmode': self.set_remember_input_mode,
            'inputmode': self.set_input_mode,
            'pagesize': self.set_page_size,
            'lookuptableorientation': self.set_lookup_table_orientation,
            'preeditunderline': self.set_preedit_underline,
            'preeditstyleonlywhenlookup':
            self.set_preedit_style_only_when_lookup,
            'mincharcomplete': self.set_min_char_complete,
            'debuglevel': self.set_debug_level,
            'errorsound': self.set_error_sound,
            'errorsoundfile': self.set_error_sound_file,
            'shownumberofcandidates': self.set_show_number_of_candidates,
            'showstatusinfoinaux': self.set_show_status_info_in_auxiliary_text,
            'autoselectcandidate': self.set_auto_select_candidate,
            'colorpreeditspellcheck': self.set_color_preedit_spellcheck,
            'colorpreeditspellcheckstring':
            self.set_color_preedit_spellcheck_string,
            'colorinlinecompletion': self.set_color_inline_completion,
            'colorinlinecompletionstring':
            self.set_color_inline_completion_string,
            'coloruserdb': self.set_color_userdb,
            'coloruserdbstring': self.set_color_userdb_string,
            'colorspellcheck': self.set_color_spellcheck,
            'colorspellcheckstring': self.set_color_spellcheck_string,
            'colordictionary': self.set_color_dictionary,
            'colordictionarystring': self.set_color_dictionary_string,
            'labeluserdb': self.set_label_userdb,
            'labeluserdbstring': self.set_label_userdb_string,
            'labelspellcheck': self.set_label_spellcheck,
            'labelspellcheckstring': self.set_label_spellcheck_string,
            'labeldictionary': self.set_label_dictionary,
            'labeldictionarystring': self.set_label_dictionary_string,
            'labelbusy': self.set_label_busy,
            'labelbusystring': self.set_label_busy_string,
            'keybindings': self.set_keybindings,
            'googleapplicationcredentials':
            self.set_google_application_credentials,
        }
        if key in set_functions:
            set_functions[key](value, update_gsettings=False)
            return
        LOGGER.warning('Unknown key\n')
        return
