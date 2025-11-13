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
import sys
# pylint: disable=wrong-import-position
if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal
# pylint: enable=wrong-import-position
import unicodedata
import os
import fnmatch
import ast
import time
import copy
import enum
import logging
import threading
import subprocess
import textwrap
from gettext import dgettext
from dataclasses import dataclass, field
# pylint: disable=wrong-import-position
from gi import require_version
require_version('IBus', '1.0')
from gi.repository import IBus
require_version('Gio', '2.0')
from gi.repository import Gio # type: ignore
require_version('GLib', '2.0')
from gi.repository import GLib # type: ignore
# pylint: enable=wrong-import-position
import m17n_translit
import itb_util
import itb_active_window
import itb_sound
import itb_emoji
import itb_version

IMPORT_ITB_OLLAMA_ERROR = None
try:
    import itb_ollama
    IMPORT_ITB_OLLAMA_ERROR = None
except (ImportError,) as error:
    IMPORT_ITB_OLLAMA_ERROR = error

USING_REGEX = False
try:
    # Enable new improved regex engine instead of backwards compatible
    # v0.  regex.match('ß', 'SS', regex.IGNORECASE) matches only with
    # the improved version!  See also: https://pypi.org/project/regex/
    import regex # type: ignore
    regex.DEFAULT_VERSION = regex.VERSION1
    re = regex
    USING_REGEX = True
except ImportError:
    # Use standard “re” module as a fallback:
    import re
    USING_REGEX = False

IMPORT_ITB_NLTK_SUCCESSFUL = False
try:
    import itb_nltk
    IMPORT_ITB_NLTK_SUCCESSFUL = True
except (ImportError, LookupError, ValueError):
    IMPORT_ITB_NLTK_SUCCESSFUL = False

IMPORT_GOOGLE_SPEECH_TO_TEXT_SUCCESSFUL = False
try:
    from google.cloud import speech # type: ignore
    from google.cloud.speech import enums as speech_enums # type: ignore
    from google.cloud.speech import types as speech_types
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

IBUS_VERSION = (IBus.MAJOR_VERSION, IBus.MINOR_VERSION, IBus.MICRO_VERSION)

def log_glib_callback_exception(
        func: Callable[..., Any],
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any]) -> None:
    '''Log exceptions in GLib callbacks'''
    exc_type, exc_value, exc_traceback = sys.exc_info()
    assert exc_type is not None
    assert exc_value is not None
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    func_name = getattr(func, '__qualname__', repr(func))
    LOGGER.error(
        'Unhandled exception in GLib callback %s(args=%r, kwargs=%r)',
        func_name, args, kwargs,
        exc_info=(exc_type, exc_value, exc_traceback))

def _wrap_glib_callback(func: Callable[..., Any]) -> Callable[..., Any]:
    '''Wrap a GLib callback so that exceptions are logged via
    log_glib_callback_exception'''
    def safe_func(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception: # pylint: disable=broad-except
            log_glib_callback_exception(func, args, kwargs)
            # Returning False stops the GLib source from being called again
            return False
    return safe_func

_real_idle_add = GLib.idle_add
_real_timeout_add = GLib.timeout_add

def _idle_add_safe(
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any) -> Any:
    return _real_idle_add(_wrap_glib_callback(func), *args, **kwargs)

def _timeout_add_safe(
        interval: int,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any) -> Any:
    return _real_timeout_add(interval, _wrap_glib_callback(func), *args, **kwargs)

GLib.idle_add = _idle_add_safe
GLib.timeout_add = _timeout_add_safe

@dataclass(frozen=False)
class SurroundingText:
    '''
    A dataclass containing the information about surrounding text

    text: str = ''              The text
    cursor_pos: int = 0         The cursor position
    anchor_pos: int = 0         The anchor position. It should be different from
                                the cursor position if a selection is active.
    event: threading.event = field(default_factory=threading.Event)
                                Used to check whether an update of this
                                surrounding text object happened since
                                the last trigger requesting an update
    '''
    text: str = ''
    cursor_pos: int = 0
    anchor_pos: int = 0
    # Do **not** use `event: threading.Event = threading.Event()`!
    # That would reuse the same Event instance across all SurroundingText objects!
    event: threading.Event = field(default_factory=threading.Event)

    def copy(self) -> 'SurroundingText':
        '''Create a copy of a Surrounding text object

        copy.deepcopy() fails on threading.Event because
        a threading.Event contains a _thread.lock internally
        and _thread.lock is not picklable.
        And copy.deepcopy() relies on pickle under the hood to clone
        objects with internal state. So Python raises:
        TypeError: cannot pickle '_thread.lock' object
        '''
        new_event = threading.Event()
        if self.event.is_set():
            new_event.set()
        return SurroundingText(
            text=self.text,
            cursor_pos=self.cursor_pos,
            anchor_pos=self.anchor_pos,
            event=new_event)

class LookupTableState(enum.Enum):
    '''Enum of states of the TypingBoosterLookupTable'''
    NORMAL = enum.auto()
    SELECTION_INFO = enum.auto()
    RELATED_CANDIDATES = enum.auto()
    COMPOSE_COMPLETIONS = enum.auto()
    M17N_CANDIDATES = enum.auto()

    def __str__(self) -> str:
        return self.name.lower()

class TypingBoosterLookupTable:
    '''Lookup table for Typing Booster

    This extends IBus.LookupTable to make it easier to track
    in which state the Typing Booster lookup table is.

    Using composition instead of interiting from IBus.LookupTable!

    When trying to use inheritance, the TypingBoosterLookupTable
    instance, despite being created from the subclass, is effectively
    an instance of the C-side IBus.LookupTable class — so the extra
    Python methods of TypingBoosterLookupTable are lost.

    The GObject system calls the C constructor first, which allocates
    a GObject*.  PyGObject then wraps it in a Python object — but not
    the subclass's object, unless the base class was designed to
    allow Python subclassing.

    IBus.LookupTable (and most IBus or GTK types) are not subclassable
    in pure Python.
    '''
    def __init__(
            self,
            page_size: int = 9,
            orientation: IBus.Orientation = IBus.Orientation.SYSTEM,
    ) -> None:
        self._ibus_lookup_table = IBus.LookupTable()
        self._ibus_lookup_table.clear()
        self._ibus_lookup_table.set_page_size(page_size)
        self._ibus_lookup_table.set_orientation(orientation)
        self._ibus_lookup_table.set_cursor_visible(False)
        # IBus.LookupTable.set_round() chooses whether the cursor in
        # the lookup table wraps around when the end or the beginning
        # of the table is reached.  I think this is confusing for
        # ibus-typing-booster, it should be set to False.
        self._ibus_lookup_table.set_round(False)
        for index in range(0, 9):
            label = str(index + 1)
            self._ibus_lookup_table.set_label(
                index, IBus.Text.new_from_string(label))
        self._state: LookupTableState = LookupTableState.NORMAL
        self._hidden: bool = False
        self._related_candidates_phrase: str = ''
        self._enabled_by_tab: bool = False
        self._enabled_by_min_char_complete: bool = False

    # I could use something like:
    #
    # def __getattr__(self, name: str) -> Any:
    #     '''Delegate unknown attributes to the internal IBus.LookupTable.'''
    #     return getattr(self._ibus_lookup_table, name)
    #
    # to automatically make all IBus.LookupTable attributes accessible.
    # But although this looks elegant and reduces boilerplate code,
    # mypy cannot help me anymore to find mistyped attributes.
    # mypy would then assume that all attributes exist:
    # “Any unknown attribute access could return anything.”
    #
    # Better explicitly define all the IBus delegate methods which
    # are really used:

    def clear(self) -> None:
        '''Delegate to IBus.LookupTable'''
        self._ibus_lookup_table.clear()

    def get_number_of_candidates(self) -> int:
        '''Delegate to IBus.LookupTable'''
        return self._ibus_lookup_table.get_number_of_candidates()

    def set_cursor_visible(self, visible: bool) -> None:
        '''Delegate to IBus.LookupTable'''
        self._ibus_lookup_table.set_cursor_visible(visible)

    def is_cursor_visible(self) -> bool:
        '''Delegate to IBus.LookupTable'''
        return self._ibus_lookup_table.is_cursor_visible()

    def set_cursor_pos(self, cursor_pos: int) -> None:
        '''Delegate to IBus.LookupTable'''
        self._ibus_lookup_table.set_cursor_pos(cursor_pos)

    def get_cursor_pos(self) -> int:
        '''Delegate to IBus.LookupTable'''
        return self._ibus_lookup_table.get_cursor_pos()

    def set_page_size(self, page_size: int) -> None:
        '''Delegate to IBus.LookupTable'''
        self._ibus_lookup_table.set_page_size(page_size)

    def get_page_size(self) -> int:
        '''Delegate to IBus.LookupTable'''
        return self._ibus_lookup_table.get_page_size()

    def set_round(self, wrap_around: bool) -> None:
        '''Delegate to IBus.LookupTable'''
        self._ibus_lookup_table.set_round(wrap_around)

    def get_round(self) -> bool:
        '''Delegate to IBus.LookupTable'''
        return self._ibus_lookup_table.get_round()

    def set_orientation(self, orientation: int) -> None:
        '''Delegate to IBus.LookupTable'''
        self._ibus_lookup_table.set_orientation(orientation)

    def get_orientation(self) -> int:
        '''Delegate to IBus.LookupTable'''
        return self._ibus_lookup_table.get_orientation()

    def set_label(self, index: int, text: IBus.Text) -> None:
        '''Delegate to IBus.LookupTable'''
        self._ibus_lookup_table.set_label(index, text)

    def get_label(self, index: int) -> IBus.Text:
        '''Delegate to IBus.LookupTable'''
        return self._ibus_lookup_table.get_label(index)

    def page_up(self) -> bool:
        '''Delegate to IBus.LookupTable'''
        return self._ibus_lookup_table.page_up()

    def page_down(self) ->bool:
        '''Delegate to IBus.LookupTable'''
        return self._ibus_lookup_table.page_down()

    def cursor_up(self) -> bool:
        '''Delegate to IBus.LookupTable'''
        return self._ibus_lookup_table.cursor_up()

    def cursor_down(self) -> bool:
        '''Delegate to IBus.LookupTable'''
        return self._ibus_lookup_table.cursor_down()

    def append_candidate(self, text: IBus.Text) -> None:
        '''Delegate to IBus.LookupTable'''
        self._ibus_lookup_table.append_candidate(text)

    @property
    def state(self) -> LookupTableState:
        '''The state of the lookup table'''
        return self._state

    @state.setter
    def state(self, value: LookupTableState) -> None:
        '''The state of the lookup table'''
        self._state = value
        if value != LookupTableState.RELATED_CANDIDATES:
            self._related_candidates_phrase = ''

    @property
    def enabled_by_tab(self) -> bool:
        '''Whether the lookup table has been enabled by typing Tab.'''
        return self._enabled_by_tab

    @enabled_by_tab.setter
    def enabled_by_tab(self, value: bool) -> None:
        '''Whether the lookup table has been enabled by typing Tab.'''
        self._enabled_by_tab = value

    @property
    def enabled_by_min_char_complete(self) -> bool:
        '''Whether the lookup table has been enabled by typing enough characters.'''
        return self._enabled_by_min_char_complete

    @enabled_by_min_char_complete.setter
    def enabled_by_min_char_complete(self, value: bool) -> None:
        '''Whether the lookup table has been enabled by typing enough characters.'''
        self._enabled_by_min_char_complete = value

    @property
    def related_candidates_phrase(self) -> str:
        '''Phrase for which related candidates were looked up.'''
        return self._related_candidates_phrase

    @related_candidates_phrase.setter
    def related_candidates_phrase(self, phrase: str) -> None:
        '''Phrase for which related candidates were looked up.'''
        self._related_candidates_phrase = phrase

    @property
    def hidden(self) -> bool:
        '''Get whether the lookup table is hidden'''
        return self._hidden

    @hidden.setter
    def hidden(self, hidden: bool) -> None:
        '''Set whether the lookup table is hidden'''
        self._hidden = hidden

    @property
    def ibus_lookup_table(self) -> IBus.LookupTable:
        '''Return the internal IBus.LookupTable'''
        return self._ibus_lookup_table

class TypingBoosterAuxiliaryText:
    '''Tracks the current contents and visibility of the auxiliary text.

    This class encapsulates the state of the auxiliary text, ensuring that
    the content and visibility are always synchronized with the displayed text.
    '''
    def __init__(self) -> None:
        self._visible: bool = False
        self._content: IBus.Text = IBus.Text.new_from_string('')

    @property
    def visible(self) -> bool:
        '''Get whether the auxiliary text is visible'''
        return self._visible

    @visible.setter
    def visible(self, visible: bool) -> None:
        '''Set whether the auxiliary text is hidden'''
        self._visible = visible

    @property
    def content(self) -> IBus.Text:
        '''Get the current content of the auxiliary text'''
        return self._content

    @content.setter
    def content(self, content: IBus.Text) -> None:
        '''Set the current content of the auxiliary text'''
        self._content = content

class TypingBoosterPreeditText:
    '''Tracks the current contents and visibility of the preedit text.

    This class encapsulates the state of the preedit text, ensuring that
    the content and visibility are always synchronized with the displayed text.
    '''
    def __init__(self) -> None:
        self._content: IBus.Text = IBus.Text.new_from_string('')
        self._cursor_pos: int = 0
        self._visible: bool = False
        self._focus_mode: int = IBus.PreeditFocusMode.CLEAR

    @property
    def content(self) -> IBus.Text:
        '''Get the current content of the preedit text'''
        return self._content

    @content.setter
    def content(self, content: IBus.Text) -> None:
        '''Set the current content of the preedit text'''
        self._content = content

    @property
    def cursor_pos(self) -> int:
        '''Get the preedit cursor position'''
        return self._cursor_pos

    @cursor_pos.setter
    def cursor_pos(self, cursor_pos: int) -> None:
        '''Set the preedit cursor position'''
        self._cursor_pos = cursor_pos

    @property
    def visible(self) -> bool:
        '''Get whether the preedit text is visible'''
        return self._visible

    @visible.setter
    def visible(self, visible: bool) -> None:
        '''Set whether the preedit text is hidden'''
        self._visible = visible

    @property
    def focus_mode(self) -> int:
        '''Get the current focus mode of the preedit text'''
        return self._focus_mode

    @focus_mode.setter
    def focus_mode(self, focus_mode: int) -> None:
        '''Set the current focus mode of the preedit text'''
        self._focus_mode = focus_mode

    @property
    def text_str(self) -> str:
        '''Get the content of the preedit text as a string'''
        return self._content.text

class TypingBoosterEngine(IBus.Engine):
    '''The IBus Engine for ibus-typing-booster'''

    def __init__(
            self,
            bus: IBus.Bus,
            obj_path: str,
            database: Any, # tabsqlitedb.TabSqliteDb
            engine_name: str = 'typing-booster',
            unit_test: bool = False) -> None:
        LOGGER.info(
            'TypingBoosterEngine.__init__'
            '(bus=%s, obj_path=%s, database=%s, '
            'engine_name=%s, unit_test=%s)',
            bus, obj_path, database, engine_name, unit_test)
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

        self._engine_name = engine_name
        self._m17n_ime_lang = ''
        self._m17n_ime_name = ''
        schema_path = '/org/freedesktop/ibus/engine/typing-booster/'
        if self._engine_name != 'typing-booster':
            try:
                match = itb_util.M17N_ENGINE_NAME_PATTERN.search(
                        self._engine_name)
                if not match:
                    raise ValueError('Invalid engine name.')
                self._m17n_ime_lang = match.group('lang')
                self._m17n_ime_name = match.group('name')
                schema_path = ('/org/freedesktop/ibus/engine/tb/'
                               f'{self._m17n_ime_lang}/{self._m17n_ime_name}/')
            except ValueError as error:
                LOGGER.exception(
                    'Failed to match engine_name %s: %s: %s',
                    engine_name, error.__class__.__name__, error)
                raise # Re-raise the original exception
        self._gsettings = Gio.Settings(
            schema='org.freedesktop.ibus.engine.typing-booster',
            path=schema_path)

        self._keyvals_to_keycodes = itb_util.KeyvalsToKeycodes()
        self._compose_sequences = itb_util.ComposeSequences()
        self._unit_test = unit_test
        self._input_purpose: int = 0
        self._input_hints: int = 0
        self._current_auxiliary_text: TypingBoosterAuxiliaryText = (
            TypingBoosterAuxiliaryText())
        self._current_preedit_text: TypingBoosterPreeditText = (
            TypingBoosterPreeditText())
        self._bus = bus
        self.database = database
        self.emoji_matcher: Optional[itb_emoji.EmojiMatcher] = None
        self._setup_process: Optional[subprocess.Popen[Any]] = None
        self._settings_dict = self._init_settings_dict()

        self._prop_dict: Dict[str, IBus.Property] = {}
        self._sub_props_dict: Dict[str, IBus.PropList] = {}
        self.main_prop_list: IBus.PropList = IBus.PropList()
        self.emoji_prediction_mode_menu: Dict[str, Any] = {}
        self.emoji_prediction_mode_properties: Dict[str, Any]= {}
        self.off_the_record_mode_menu: Dict[str, Any] = {}
        self.off_the_record_mode_properties: Dict[str, Any] = {}
        self.input_mode_menu: Dict[str, Any] = {}
        self.input_mode_properties: Dict[str, Any] = {}
        self.dictionary_menu: Dict[str, Any] = {}
        self.dictionary_properties: Dict[str, Any] = {}
        self.dictionary_sub_properties_prop_list: IBus.PropList = IBus.PropList()
        self.preedit_ime_menu: Dict[str, Any] = {}
        self.preedit_ime_properties: Dict[str, Any] = {}
        self.preedit_ime_sub_properties_prop_list: IBus.PropList = IBus.PropList()

        self._im_client: str = ''

        self._current_imes: List[str] = []

        self._ai_chat_enable: bool = self._settings_dict[
            'aichatenable']['user']
        self._ai_system_message: str = self._settings_dict[
            'aisystemmessage']['user']
        self._ollama_client: Optional[itb_ollama.ItbOllamaClient] = None
        self._ollama_server_label = '🦙'
        self._ollama_model: str = self._settings_dict[
            'ollamamodel']['user']
        self._ollama_max_context: int = self._settings_dict[
            'ollamamaxcontext']['user']
        self._ollama_response_style: Literal['preedit', 'aux'] = 'aux'
        self._ollama_messages: List[Dict[str, str]] = []
        self._ollama_selection_text = ''
        self._ollama_prompt: Dict[str, str] = {}
        self._ollama_response = ''
        self._ollama_chat_query_thread: Optional[threading.Thread] = None
        self._ollama_chat_query_error = False
        self._ollama_stop_event: threading.Event = threading.Event()
        self._ollama_aux_wrapper: textwrap.TextWrapper = textwrap.TextWrapper(
            width=80,
            expand_tabs=True,
            replace_whitespace=True,
            drop_whitespace=True,
            break_long_words=True,
            break_on_hyphens=True)

        self._timeout_source_id: int = 0
        self._candidates_delay_milliseconds: int = self._settings_dict[
            'candidatesdelaymilliseconds']['user']
        self._candidates_delay_milliseconds = max(
            self._candidates_delay_milliseconds, 0)
        self._candidates_delay_milliseconds = min(
            self._candidates_delay_milliseconds, itb_util.UINT32_MAX)
        LOGGER.info('self._candidates_delay_milliseconds=%s',
                    self._candidates_delay_milliseconds)

        # Between some events sent to ibus like forward_key_event(),
        # delete_surrounding_text(), commit_text(), a sleep is necessary.
        # Without the sleep, these events may be processed out of order.
        self._ibus_event_sleep_seconds: float = self._settings_dict[
            'ibuseventsleepseconds']['user']
        LOGGER.info('self._ibus_event_sleep_seconds=%s', self._ibus_event_sleep_seconds)

        self._ibus_keymap: str = self._settings_dict['ibuskeymap']['user']
        self._ibus_keymap_object: Optional[IBus.Keymap] = (
            self.new_ibus_keymap(self._ibus_keymap))
        self._use_ibus_keymap: bool = self._settings_dict[
            'useibuskeymap']['user']

        self._word_predictions: bool = self._settings_dict[
            'wordpredictions']['user']
        self._temporary_word_predictions = False
        self._emoji_predictions: bool = self._settings_dict[
            'emojipredictions']['user']
        self._temporary_emoji_predictions = False
        self._unicode_data_all: bool = self._settings_dict[
            'unicodedataall']['user']
        self._emoji_match_limit = 10_000

        self._min_char_complete: int = self._settings_dict[
            'mincharcomplete']['user']
        self._min_char_complete = max(self._min_char_complete, 0)
        self._min_char_complete = min(self._min_char_complete, 9)

        self._debug_level: int = self._settings_dict['debuglevel']['user']
        self._debug_level = max(self._debug_level, 0)
        LOGGER.info('self._debug_level=%s', self._debug_level)

        self._page_size: int = self._settings_dict['pagesize']['user']
        self._page_size = max(self._page_size, 1)
        self._page_size = min(self._page_size, 9)

        self._lookup_table_orientation: int = self._settings_dict[
            'lookuptableorientation']['user']

        self._preedit_underline: int = self._settings_dict[
            'preeditunderline']['user']

        self._preedit_style_only_when_lookup: bool = self._settings_dict[
            'preeditstyleonlywhenlookup']['user']

        self._show_number_of_candidates: bool = self._settings_dict[
            'shownumberofcandidates']['user']

        self._show_status_info_in_auxiliary_text: bool = self._settings_dict[
            'showstatusinfoinaux']['user']

        self._is_candidate_auto_selected = False
        self._auto_select_candidate: int = self._settings_dict[
            'autoselectcandidate']['user']

        self._tab_enable: bool = self._settings_dict[
            'tabenable']['user']

        self._disable_in_terminals: bool = self._settings_dict[
            'disableinterminals']['user']

        self._ascii_digits: bool = self._settings_dict['asciidigits']['user']

        self._off_the_record: bool = self._settings_dict[
            'offtherecord']['user']

        self._hide_input = False

        self._input_mode = True

        self._avoid_forward_key_event: bool = self._settings_dict[
            'avoidforwardkeyevent']['user']

        self._prefer_commit: bool = self._settings_dict[
            'prefercommit']['user']

        self._arrow_keys_reopen_preedit: bool = self._settings_dict[
            'arrowkeysreopenpreedit']['user']

        self._emoji_trigger_characters: str = self._settings_dict[
            'emojitriggercharacters']['user']

        self._emoji_style: str = self._settings_dict[
            'emojistyle']['user']

        self._auto_commit_characters: str = self._settings_dict[
            'autocommitcharacters']['user']

        self._remember_last_used_preedit_ime: bool = self._settings_dict[
            'rememberlastusedpreeditime']['user']

        self._add_space_on_commit: bool = self._settings_dict[
            'addspaceoncommit']['user']

        self._inline_completion: int = self._settings_dict[
            'inlinecompletion']['user']

        self._record_mode: int = self._settings_dict['recordmode']['user']

        self._auto_capitalize: bool = self._settings_dict[
            'autocapitalize']['user']

        self._color_preedit_spellcheck: bool = self._settings_dict[
            'colorpreeditspellcheck']['user']

        self._color_preedit_spellcheck_string: str = self._settings_dict[
            'colorpreeditspellcheckstring']['user']
        self._color_preedit_spellcheck_argb = itb_util.color_string_to_argb(
            self._color_preedit_spellcheck_string)

        self._color_inline_completion: bool = self._settings_dict[
            'colorinlinecompletion']['user']

        self._color_inline_completion_string: str = self._settings_dict[
            'colorinlinecompletionstring']['user']
        self._color_inline_completion_argb = itb_util.color_string_to_argb(
            self._color_inline_completion_string)

        self._color_compose_preview: bool = self._settings_dict[
            'colorcomposepreview']['user']

        self._color_compose_preview_string: str = self._settings_dict[
            'colorcomposepreviewstring']['user']
        self._color_compose_preview_argb = itb_util.color_string_to_argb(
            self._color_compose_preview_string)

        self._color_m17n_preedit: bool = self._settings_dict[
            'colorm17npreedit']['user']

        self._color_m17n_preedit_string: str = self._settings_dict[
            'colorm17npreeditstring']['user']
        self._color_m17n_preedit_argb = itb_util.color_string_to_argb(
            self._color_m17n_preedit_string)

        self._color_userdb: bool = self._settings_dict['coloruserdb']['user']

        self._color_userdb_string: str = self._settings_dict[
            'coloruserdbstring']['user']
        self._color_userdb_argb = itb_util.color_string_to_argb(
            self._color_userdb_string)

        self._color_spellcheck: bool = self._settings_dict[
            'colorspellcheck']['user']

        self._color_spellcheck_string: str = self._settings_dict[
            'colorspellcheckstring']['user']
        self._color_spellcheck_argb = itb_util.color_string_to_argb(
            self._color_spellcheck_string)

        self._color_dictionary: bool = self._settings_dict[
            'colordictionary']['user']

        self._color_dictionary_string: str = self._settings_dict[
            'colordictionarystring']['user']
        self._color_dictionary_argb = itb_util.color_string_to_argb(
            self._color_dictionary_string)

        self._label_userdb: bool = self._settings_dict['labeluserdb']['user']

        self._label_userdb_string: str = self._settings_dict[
            'labeluserdbstring']['user']

        self._label_spellcheck: bool = self._settings_dict[
            'labelspellcheck']['user']

        self._label_spellcheck_string: str = self._settings_dict[
            'labelspellcheckstring']['user']

        self._label_dictionary: bool = self._settings_dict[
            'labeldictionary']['user']

        self._label_dictionary_string: str = ''
        self._label_dictionary_dict: Dict[str, str] = {}
        self.set_label_dictionary_string(
            self._settings_dict['labeldictionarystring']['user'],
            update_gsettings=False)

        self._flag_dictionary: bool = self._settings_dict[
            'flagdictionary']['user']

        self._label_busy: bool = self._settings_dict['labelbusy']['user']

        self._label_busy_string: str = self._settings_dict[
            'labelbusystring']['user']

        self._label_speech_recognition: bool = True
        self._label_speech_recognition_string: str = '🎙️'

        self._google_application_credentials: str = self._settings_dict[
            'googleapplicationcredentials']['user']

        self._keybindings: Dict[str, List[str]] = {}
        self._hotkeys: Optional[itb_util.HotKeys] = None
        self._normal_digits_used_in_keybindings = False
        self._keypad_digits_used_in_keybindings = False
        self.set_keybindings(
            self._settings_dict['keybindings']['user'], update_gsettings=False)

        self._autosettings: List[Tuple[str, str, str]] = []
        self.set_autosettings(
            self._settings_dict['autosettings']['user'],
            update_gsettings=False)
        self._autosettings_revert: Dict[str, Any] = {}

        self._remember_input_mode: bool = self._settings_dict[
            'rememberinputmode']['user']
        if (self._keybindings['toggle_input_mode_on_off']
            and self._remember_input_mode):
            self._input_mode = self._settings_dict['inputmode']['user']
        else:
            self.set_input_mode(True, update_gsettings=True)

        self._sound_backend: str = self._settings_dict['soundbackend']['user']
        self._error_sound_object: Optional[itb_sound.SoundObject] = None
        self._error_sound_file = ''
        self._error_sound: bool = self._settings_dict['errorsound']['user']
        self.set_error_sound_file(
            self._settings_dict['errorsoundfile']['user'],
            update_gsettings=False)

        self._dictionary_names: List[str] = []
        dictionary = self._settings_dict['dictionary']['user']
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
            if self._debug_level > 1:
                LOGGER.debug('Instantiate EmojiMatcher(languages = %s',
                             self._dictionary_names)
            self.emoji_matcher = itb_emoji.EmojiMatcher(
                languages=self._dictionary_names,
                unicode_data_all=self._unicode_data_all,
                variation_selector=self._emoji_style)
            if self._debug_level > 1:
                LOGGER.debug('EmojiMatcher() instantiated.')
        else:
            self.emoji_matcher = None

        # Try to get the selected input methods from Gsettings:
        inputmethod = self._settings_dict['inputmethod']['user']
        self._current_imes = itb_util.input_methods_str_to_list(inputmethod)
        if ','.join(self._current_imes) != inputmethod:
            # Value changed due to normalization or getting the locale
            # defaults, save it back to settings:
            self._gsettings.set_value(
                'inputmethod',
                GLib.Variant.new_string(','.join(self._current_imes)))

        self._commit_happened_after_focus_in = False

        self._prev_key: Optional[itb_util.KeyEvent] = None
        self._translated_key_state = 0
        self._m17n_trans_parts: m17n_translit.TransliterationParts = (
            m17n_translit.TransliterationParts())
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
        self._candidates: List[itb_util.PredictionCandidate] = []
        # a copy of self._candidates in case mode 'orig':
        self._candidates_case_mode_orig: List[itb_util.PredictionCandidate] = []
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
                    str, 'title')(itb_util.normalize_nfc_and_composition_exclusions(x))},
            'upper': {
                'next': 'lower',
                'previous': 'capitalize',
                'function': getattr(str, 'upper')},
            'lower': {
                'next': 'capitalize',
                'previous': 'upper',
                'function': getattr(str, 'lower')},
        }

        self._lookup_table: TypingBoosterLookupTable = TypingBoosterLookupTable(
            page_size=self._page_size,
            orientation=self._lookup_table_orientation)

        cached_input_mode_true_symbol = itb_util.ibus_read_cache().get(
            self._engine_name, {}).get('symbol', '')
        LOGGER.info('Cached symbol: %r Current symbol: %r',
                    cached_input_mode_true_symbol,
                    self._settings_dict['inputmodetruesymbol']['user'])
        if (cached_input_mode_true_symbol
            != self._settings_dict['inputmodetruesymbol']['user']):
            LOGGER.info(
                'Cached symbol is outdated, call `ibus write-cache`.')
            itb_util.ibus_write_cache()

        self.input_mode_properties = {
            'InputMode.Off': {
                'number': 0,
                'symbol': self._settings_dict['inputmodefalsesymbol']['user'],
                'label': _('Off'),
            },
            'InputMode.On': {
                'number': 1,
                'symbol': self._settings_dict['inputmodetruesymbol']['user'],
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
            IBus.KEY_BackSpace, IBus.KEY_Escape)
        self._surrounding_text = SurroundingText()
        self._surrounding_text_old = SurroundingText()
        self.connect('set-surrounding-text', self._on_set_surrounding_text)
        self._is_context_from_surrounding_text = False

        self._gsettings.connect('changed', self._on_gsettings_value_changed)

        self._clear_input_and_update_ui()

        LOGGER.info(
            '*** ibus-typing-booster %s initialized, ready for input: ***',
            itb_version.get_version())

        cleanup_database_thread = threading.Thread(
            target=self.database.cleanup_database)
        cleanup_database_thread.start()

    def show_lookup_table(self) -> None: # pylint: disable=arguments-differ
        super().show_lookup_table()
        self._lookup_table.hidden = False

    def hide_lookup_table(self) -> None: # pylint: disable=arguments-differ
        super().hide_lookup_table()
        self._lookup_table.hidden = True

    def update_lookup_table( # pylint: disable=arguments-differ
            self,
            lookup_table: Union[IBus.LookupTable, TypingBoosterLookupTable],
            visible: bool) -> None:
        if isinstance(lookup_table, TypingBoosterLookupTable):
            super().update_lookup_table(lookup_table.ibus_lookup_table, visible)
            lookup_table.hidden = not visible
        else:
            super().update_lookup_table(lookup_table, visible)

    def show_auxiliary_text(self) -> None: # pylint: disable=arguments-differ
        super().show_auxiliary_text()
        self._current_auxiliary_text.visible = True

    def hide_auxiliary_text(self) -> None: # pylint: disable=arguments-differ
        super().hide_auxiliary_text()
        self._current_auxiliary_text.visible = False

    def update_auxiliary_text( # pylint: disable=arguments-differ
            self, content: IBus.Text, visible: bool) -> None:
        super().update_auxiliary_text(content, visible)
        self._current_auxiliary_text.visible = visible
        self._current_auxiliary_text.content = content

    def show_preedit_text(self) -> None: # pylint: disable=arguments-differ
        super().show_preedit_text()
        self._current_preedit_text.visible = True

    def hide_preedit_text(self) -> None: # pylint: disable=arguments-differ
        super().hide_preedit_text()
        self._current_preedit_text.visible = False

    def update_preedit_text( # pylint: disable=arguments-differ
            self, content: IBus.Text, cursor_pos: int, visible: bool) -> None:
        super().update_preedit_text(content, cursor_pos, visible)
        self._current_preedit_text.content = content
        self._current_preedit_text.cursor_pos = cursor_pos
        self._current_preedit_text.visible = visible

    def update_preedit_text_with_mode( # pylint: disable=arguments-differ
            self,
            content: IBus.Text,
            cursor_pos: int,
            visible: bool,
            focus_mode: int) -> None:
        super().update_preedit_text_with_mode(
            content, cursor_pos, visible, focus_mode)
        self._current_preedit_text.content = content
        self._current_preedit_text.cursor_pos = cursor_pos
        self._current_preedit_text.visible = visible
        self._current_preedit_text.focus_mode = focus_mode

    @property
    def has_osk(self) -> bool:
        '''Return True if OSK capability flag is set.'''
        return bool(self.client_capabilities & itb_util.Capabilite.OSK)

    @property
    def has_surrounding_text(self) -> bool:
        '''Return True if SURROUNDING_TEXT capability flag is set.'''
        return bool(
            self.client_capabilities & itb_util.Capabilite.SURROUNDING_TEXT)

    def _trigger_surrounding_text_update(self) -> None:
        '''Trigger surrounding text update by calling get_surrounding_text()

        Also clears the event in the self._surrounding_text object
        which indicates that an update happened since the last
        trigger. But keeps the rest of the data.
        '''
        self._surrounding_text.event.clear()
        self.get_surrounding_text() # trigger surrounding text update

    def _init_settings_dict(self) -> Dict[str, Any]:
        '''Initialize a dictionary with the default and user settings for all
        settings keys.

        The default settings start with the defaults from the
        gsettings schema. Some of these generic default values may be
        overridden by more specific default settings for the specific engine.
        After this possible modification for a specific engine we have the final default
        settings for this specific typing booster input method.

        The user settings start with a copy of these final default settings,
        then they are possibly modified by user gsettings.

        Keeping a copy of the default settings in the settings dictionary
        makes it easy to revert some or all settings to the defaults.
        '''
        settings_dict: Dict[str, Any] = {}
        set_get_functions: Dict[str, Dict[str, Any]] = {
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
            'prefercommit': {
                'set': self.set_prefer_commit,
                'get': self.get_prefer_commit},
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
            'wordpredictions': {
                'set': self.set_word_prediction_mode,
                'get': self.get_word_prediction_mode},
            'emojipredictions': {
                'set': self.set_emoji_prediction_mode,
                'get': self.get_emoji_prediction_mode},
            'unicodedataall': {
                'set': self.set_unicode_data_all_mode,
                'get': self.get_unicode_data_all_mode},
            'offtherecord': {
                'set': self.set_off_the_record_mode,
                'get': self.get_off_the_record_mode},
            'emojitriggercharacters': {
                'set': self.set_emoji_trigger_characters,
                'get': self.get_emoji_trigger_characters},
            'emojistyle': {
                'set': self.set_emoji_style,
                'get': self.get_emoji_style},
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
            'candidatesdelaymilliseconds': {
                'set': self.set_candidates_delay_milliseconds,
                'get': self.get_candidates_delay_milliseconds},
            'ibuseventsleepseconds': {
                'set': self.set_ibus_event_sleep_seconds,
                'get': self.get_ibus_event_sleep_seconds},
            'useibuskeymap': {
                'set': self.set_use_ibus_keymap,
                'get': self.get_use_ibus_keymap},
            'ibuskeymap': {
                'set': self.set_ibus_keymap,
                'get': self.get_ibus_keymap},
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
            'colorm17npreedit': {
                'set': self.set_color_m17n_preedit,
                'get': self.get_color_m17n_preedit},
            'colorm17npreeditstring': {
                'set': self.set_color_m17n_preedit_string,
                'get': self.get_color_m17n_preedit_string},
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
            'aichatenable': {
                'set': self.set_ai_chat_enable,
                'get': self.get_ai_chat_enable},
            'aisystemmessage': {
                'set': self.set_ai_system_message,
                'get': self.get_ai_system_message},
            'ollamamodel': {
                'set': self.set_ollama_model,
                'get': self.get_ollama_model},
            'ollamamaxcontext': {
                'set': self.set_ollama_max_context,
                'get': self.get_ollama_max_context},
            'inputmodetruesymbol': {
                'set': self.set_input_mode_true_symbol,
                'get': self.get_input_mode_true_symbol},
            'inputmodefalsesymbol': {
                'set': self.set_input_mode_false_symbol,
                'get': self.get_input_mode_false_symbol},
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
        schema_source: Gio.SettingsSchemaSource = (
            Gio.SettingsSchemaSource.get_default()) # pylint: disable=no-value-for-parameter
        schema: Gio.SettingsSchema = schema_source.lookup(
            'org.freedesktop.ibus.engine.typing-booster', True)
        special_defaults = {
            'dictionary': 'None',  # special dummy dictionary
            'inputmethod': f'{self._m17n_ime_lang}-{self._m17n_ime_name}',
            'wordpredictions': False,
            'emojipredictions': False,
            'emojitriggercharacters': '',
            'offtherecord': True,
            'preeditunderline': 0,
        }
        if self._engine_name != 'typing-booster':
            symbol = ''
            for pattern, pattern_symbol in itb_util.M17N_IME_SYMBOLS:
                if re.fullmatch(pattern, self._engine_name):
                    symbol = pattern_symbol
                    break
            if symbol:
                special_defaults['inputmodetruesymbol'] = symbol
                special_defaults['inputmodefalsesymbol'] = f'•{symbol}'
        elif (itb_util.is_desktop('gnome')
              and itb_util.get_gnome_shell_version() >= (48, 3)):
            # If running on Gnome and gnome-shell is new enough to contain
            # https://gitlab.gnome.org/GNOME/gnome-shell/-/merge_requests/3753
            # make the input mode symbols black and white:
            special_defaults['inputmodetruesymbol'] = '🚀\uFE0E'
            special_defaults['inputmodefalsesymbol'] = '🐌\uFE0E'
        for key in schema.list_keys():
            if key == 'keybindings': # keybindings are special!
                default_value = itb_util.variant_to_value(
                    self._gsettings.get_default_value('keybindings'))
                if self._engine_name != 'typing-booster':
                    default_value['toggle_input_mode_on_off'] = []
                    default_value['commit_and_forward_key'] = ['Left']
                # copy the updated default keybindings, i.e. the
                # default keybindings for this specific engine, into
                # the user keybindings:
                user_value = copy.deepcopy(default_value)
                user_gsettings = itb_util.variant_to_value(
                    self._gsettings.get_user_value(key))
                if not user_gsettings:
                    user_gsettings = {}
                itb_util.dict_update_existing_keys(user_value, user_gsettings)
            else:
                default_value = itb_util.variant_to_value(
                    self._gsettings.get_default_value(key))
                if (self._engine_name != 'typing-booster'
                    or key in ('inputmodetruesymbol', 'inputmodefalsesymbol')):
                    default_value = special_defaults.get(key, default_value)
                user_value = itb_util.variant_to_value(
                    self._gsettings.get_user_value(key))
                if user_value is None:
                    user_value = default_value
            settings_dict[key] = {'default': default_value, 'user': user_value}
            if key in set_get_functions:
                if 'set' in set_get_functions[key]:
                    settings_dict[
                        key]['set_function'] = set_get_functions[key]['set']
                if 'get' in set_get_functions[key]:
                    settings_dict[
                        key]['get_function'] = set_get_functions[key]['get']
            else:
                LOGGER.warning('key %s missing in set_get_functions', key)
        return settings_dict

    def _init_transliterators(self) -> None:
        '''Initialize the dictionary of m17n-db transliterator objects'''
        self._transliterators = {}
        for ime in self._current_imes:
            # using m17n transliteration
            try:
                if self._debug_level > 1:
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

    def _show_prediction_candidates(self) -> bool:
        '''Checks whether prediction candidate lists are wanted

        If neither emoji predictions are possible nor word predictions
        are possible, calculations to produce the “normal” Typing Booster
        lookup table can be skipped completely.

        But m17n candidates lookup tables and Compose lookup tables
        are still possible then.
        '''
        return bool(self._emoji_predictions
                    or self._emoji_trigger_characters != ''
                    or self._temporary_emoji_predictions
                    or self._temporary_word_predictions
                    or self._word_predictions)

    def _try_early_commit(self) -> bool:
        '''
        Whether it should be checked if parts of the
        transliteration can be committed already
        '''
        return bool(not self.is_empty()
                    and len(self._current_imes) == 1
                    and not self._typed_compose_sequence
                    and not self._word_predictions
                    and not self._temporary_word_predictions
                    and not self._emoji_predictions
                    and not self._temporary_emoji_predictions
                    and not self._typed_string[0] in self._emoji_trigger_characters)

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
        self._m17n_trans_parts = m17n_translit.TransliterationParts()
        self._prev_key = None
        self._translated_key_state = 0
        self._typed_string = []
        self._typed_string_cursor = 0
        for ime in self._current_imes:
            self._transliterated_strings[ime] = ''
        self._timeout_source_id = 0
        self.hide_lookup_table()
        self._lookup_table.enabled_by_tab = False
        self._lookup_table.enabled_by_min_char_complete = False
        self._lookup_table.state = LookupTableState.NORMAL
        self._temporary_word_predictions = False
        self._temporary_emoji_predictions = False
        self.update_preedit_text_with_mode(
            IBus.Text.new_from_string(''), 0, False,
            IBus.PreeditFocusMode.COMMIT)
        self.update_auxiliary_text(
            IBus.Text.new_from_string(''), False)

    def _insert_string_at_cursor(self, string_to_insert: List[str]) -> None:
        '''Insert typed string at cursor position'''
        if self._debug_level > 1:
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

    def get_caret(self, extra_msymbol: str = '') -> int:
        '''Get caret position in preëdit string

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

        https://github.com/mike-fabian/ibus-typing-booster/issues/519
        A key which triggered a commit might have changed the
        transliteration, see
        https://bugzilla.redhat.com/show_bug.cgi?id=1353672 and it
        might have even changed the length of the transliteration,
        even increasing the length is possible.  So sometimes we need
        to consider an extra msymbol coming from the commit key to
        calculate the caret position in the preedit string.
        '''
        preedit_ime = self._current_imes[0]
        typed_string = self._typed_string[:self._typed_string_cursor]
        if extra_msymbol and not self._typed_compose_sequence:
            typed_string += [extra_msymbol]
        transliterated_string_up_to_cursor = (
            self._transliterators[preedit_ime].transliterate(
                typed_string, ascii_digits=self._ascii_digits))
        if (extra_msymbol and not self._typed_compose_sequence
            and transliterated_string_up_to_cursor.endswith(extra_msymbol)):
            transliterated_string_up_to_cursor = (
                transliterated_string_up_to_cursor[:-len(extra_msymbol)])
        caret = len(transliterated_string_up_to_cursor)
        if self._typed_compose_sequence:
            caret += len(
                self._compose_sequences.preedit_representation(
                    self._typed_compose_sequence))
        return caret

    def _append_candidate_to_lookup_table(
            self, phrase: str = '',
            user_freq: float = 0.0,
            comment: str = '',
            from_user_db: bool = False,
            spell_checking: bool = False) -> None:
        '''append candidate to lookup_table'''
        phrase = itb_util.normalize_nfc_and_composition_exclusions(phrase)
        dictionary_matches: List[str] = []
        if phrase and itb_util.is_invisible(phrase):
            if len(phrase) == 1:
                if comment == '':
                    # There may be a comment already if this came from
                    # EmojiMatcher, if a comment is already there, leave
                    # it alone.
                    comment = f'U+{ord(phrase):04X} ' + itb_util.unicode_name(
                        phrase).lower()
            phrase = repr(phrase)
        elif (len(phrase) >= 3
            and not comment
            and not self._m17n_trans_parts.candidates
            and not self._typed_compose_sequence):
            dictionary_matches = (
                self.database.hunspell_obj.spellcheck_match_list(phrase))
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
        phrase = itb_util.elide_middle(phrase, max_length=80)
        attrs = IBus.AttrList()
        comment = itb_util.elide_middle(comment, max_length=80)
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
            # hunspell dictionary
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
        # If a candidate (longer than one character) contains
        # newlines, replace them with a symbol indicating the new
        # line. Rendering the real newlines in the lookup table looks
        # terrible. On non-Gnome desktops, all entries in the lookup
        # table always have the same height. So when one entry uses 3
        # lines in the lookup table, all other entries use 3 lines as
        # well. In Gnome this works somewhat better, only the entry
        # which really uses multiple lines uses extra space in the
        # lookup table. But this still looks terrible. When one uses
        # custom shortcuts to expand to whole paragraphs, this uses
        # far too much space in the lookup table.
        #
        # U+2028 LINE SEPARATOR and U+2029 PARAGRAPH SEPARATOR also make
        # the line spacing in the lookup table huge, which looks ugly.
        # Replace them with repr(character).
        phrase = phrase.replace(
            '\n', '␤').replace( # ␤ U+2424 SYMBOL FOR NEWLINE
                '\r', '␍').replace( # ␍ U+240D SYMBOL FOR CARRIAGE RETURN
                    '\u2028', repr('\u2028')).replace(
                        '\u2029', repr('\u2029'))
        if self._debug_level > 1 and not self.has_osk:
            # Show frequency information for debugging
            phrase += f' {str(user_freq)}'
            attrs.append(IBus.attr_foreground_new(
                itb_util.color_string_to_argb('HotPink'),
                len(phrase) - len(str(user_freq)),
                len(phrase)))
        text = IBus.Text.new_from_string(phrase)
        text.set_attributes(attrs)
        self._lookup_table.append_candidate(text)
        self._lookup_table.set_cursor_visible(False)

    def _update_candidates(self) -> None:
        '''Update the list of candidates and fill the lookup table with the
        candidates
        '''
        if self._debug_level > 1:
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
        phrase_frequencies: Dict[str, float] = {}
        phrase_candidates: List[itb_util.PredictionCandidate] = []
        self._lookup_table.enabled_by_min_char_complete = False
        if self._word_predictions or self._temporary_word_predictions:
            for ime in self._current_imes:
                if self._transliterated_strings[ime]:
                    candidates = []
                    prefix_length = 0
                    prefix = ''
                    stripped_transliterated_string = (
                        itb_util.lstrip_token(self._transliterated_strings[ime]))
                    if ime in ['ko-romaja', 'ko-han2']:
                        # The two Korean input methods we have in m17n produce
                        # Jamo from the Hangul compatibility block and not
                        # from the Hangul Jamo area.  For example
                        # transliterating 'h' using
                        # /usr/share/m17n/ko-romaja.mim gives ㅎ U+314E HANGUL
                        # LETTER HIEUH and not ᄒU+1112 HANGUL CHOSEONG HIEUH.
                        # To make matching in the /usr/share/myspell/ko_KR.dic
                        # work we need ᄒU+1112. When matching in the user
                        # database and in hunspell dictionaries the input is
                        # converted to NFD, but that does not convert Jamo
                        # from the Hangul compatibility block:
                        #
                        # >>> f'{ord(unicodedata.normalize('NFD', '\u314e')):X}'
                        # '314E'
                        #
                        # But converting to NFKD does what we need:
                        #
                        # >>> f'{ord(unicodedata.normalize('NFKD', '\u314e')):X}'
                        # '1112'
                        #
                        # And further conversions to NFC, NFKC, NFD, NFKD do
                        # not change this anymore, the result remains in the
                        # Hangul jamo area (U+1112)
                        stripped_transliterated_string = unicodedata.normalize(
                            'NFKD', stripped_transliterated_string)
                    if (stripped_transliterated_string
                        and (len(stripped_transliterated_string)
                             >= self._min_char_complete)):
                        self._lookup_table.enabled_by_min_char_complete = True
                    if (self._lookup_table.enabled_by_min_char_complete
                        or self._lookup_table.enabled_by_tab
                        or self.has_osk):
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
                        candidates = [
                            itb_util.PredictionCandidate(
                                phrase=prefix+x.phrase,
                                user_freq=x.user_freq)
                            for x in candidates]
                    shortcut_candidates: List[Tuple[str, float]] = []
                    try:
                        shortcut_candidates = self.database.select_shortcuts(
                            self._transliterated_strings[ime])
                    except Exception as error: # pylint: disable=broad-except
                        LOGGER.exception(
                            'Exception when calling select_shortcuts: %s: %s',
                            error.__class__.__name__, error)
                    for cand in candidates + shortcut_candidates:
                        if cand.phrase in phrase_frequencies:
                            phrase_frequencies[cand.phrase] = max(
                                phrase_frequencies[cand.phrase],
                                cand.user_freq)
                        else:
                            phrase_frequencies[cand.phrase] = cand.user_freq
            phrase_candidates = itb_util.best_candidates(phrase_frequencies)
        # If the first candidate is exactly the same as the typed string
        # prefer longer candidates which start exactly with the typed
        # string. If the user wants the typed string, he can easily
        # commit the preëdit, there is no need to select a candidate in
        # that case. Offering longer completions instead may give
        # the opportunity to save some key strokes.
        if phrase_candidates:
            typed_string = itb_util.normalize_nfc_and_composition_exclusions(
                self._transliterated_strings[
                    self.get_current_imes()[0]])
            first_candidate = itb_util.normalize_nfc_and_composition_exclusions(
                phrase_candidates[0].phrase)
            if typed_string == first_candidate:
                phrase_frequencies = {}
                first_candidate_user_freq = phrase_candidates[0].user_freq
                first_candidate_length = len(first_candidate)
                for cand in phrase_candidates:
                    candidate_normalized = (
                        itb_util.normalize_nfc_and_composition_exclusions(
                            cand.phrase))
                    if (len(candidate_normalized) > first_candidate_length
                        and candidate_normalized.startswith(first_candidate)):
                        phrase_frequencies[cand.phrase] = (
                            cand.user_freq + first_candidate_user_freq)
                    else:
                        phrase_frequencies[cand.phrase] = cand.user_freq
                phrase_candidates = itb_util.best_candidates(
                    phrase_frequencies)
        if ((self._emoji_predictions and not self.has_osk)
            or self._temporary_emoji_predictions
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
                    languages=self._dictionary_names,
                    unicode_data_all=self._unicode_data_all,
                    variation_selector=self._emoji_style)
            emoji_scores: Dict[str, Tuple[float, str]] = {}
            emoji_max_score: float = 0.0
            for ime in self._current_imes:
                if (self._transliterated_strings[ime]
                    and (len(self._transliterated_strings[ime])
                         >= self._min_char_complete
                         or self.has_osk
                         or self._tab_enable)):
                    emoji_matcher_candidates = self.emoji_matcher.candidates(
                        self._transliterated_strings[ime],
                        match_limit=self._emoji_match_limit,
                        trigger_characters=self._emoji_trigger_characters)
                    for ecand in emoji_matcher_candidates:
                        emoji_max_score = max(emoji_max_score, ecand.user_freq)
                        if (ecand.phrase not in emoji_scores
                                or ecand.user_freq > emoji_scores[ecand.phrase][0]):
                            emoji_scores[ecand.phrase] = (ecand.user_freq, ecand.comment)
            phrase_candidates_emoji_name: List[itb_util.PredictionCandidate] = []
            for cand in phrase_candidates:
                # If this candidate is duplicated in the emoji candidates,
                # don’t use this as a text candidate but increase the score
                # of the emoji candidate:
                emoji = ''
                if cand.phrase in emoji_scores:
                    emoji = cand.phrase
                elif (cand.phrase[0] in self._emoji_trigger_characters
                    and cand.phrase[1:] in emoji_scores):
                    emoji = cand.phrase[1:]
                if emoji:
                    emoji_scores[emoji] = (emoji_max_score + cand.user_freq,
                                           emoji_scores[emoji][1])
                else:
                    phrase_candidates_emoji_name.append(
                        itb_util.PredictionCandidate(
                            phrase=cand.phrase,
                            user_freq=cand.user_freq,
                            comment=self.emoji_matcher.name(cand.phrase),
                            from_user_db=cand.user_freq > 0,
                            spell_checking=cand.user_freq < 0))
            emoji_candidates: List[itb_util.PredictionCandidate] = []
            for (key, value) in sorted(
                    emoji_scores.items(),
                    key=lambda x: (
                        - x[1][0],   # score
                        - len(x[0]), # length of emoji string
                        x[1][1]      # name of emoji
                    ))[:self._emoji_match_limit]:
                emoji_candidates.append(
                    itb_util.PredictionCandidate(
                        phrase=key, user_freq=value[0], comment=value[1]))
            page_size = self._lookup_table.get_page_size()
            phrase_candidates_top = phrase_candidates_emoji_name[:page_size-1]
            phrase_candidates_rest = phrase_candidates_emoji_name[page_size-1:]
            emoji_candidates_top = emoji_candidates[:page_size]
            emoji_candidates_rest = emoji_candidates[page_size:]
            for cand in phrase_candidates_top:
                self._candidates.append(
                    itb_util.PredictionCandidate(
                        phrase=cand.phrase,
                        user_freq=cand.user_freq,
                        comment=cand.comment,
                        from_user_db=cand.from_user_db,
                        spell_checking=cand.spell_checking))
            for cand in emoji_candidates_top:
                self._candidates.append(
                    itb_util.PredictionCandidate(
                        phrase=cand.phrase,
                        user_freq=cand.user_freq,
                        comment=cand.comment,
                        from_user_db=False,
                        spell_checking=False))
            for cand in phrase_candidates_rest:
                self._candidates.append(
                    itb_util.PredictionCandidate(
                        phrase=cand.phrase,
                        user_freq=cand.user_freq,
                        comment=cand.comment,
                        from_user_db=cand.from_user_db,
                        spell_checking=cand.spell_checking))
            for cand in emoji_candidates_rest:
                self._candidates.append(
                    itb_util.PredictionCandidate(
                        phrase=cand.phrase,
                        user_freq=cand.user_freq,
                        comment=cand.comment,
                        from_user_db=False,
                        spell_checking=False))
        else:
            for cand in phrase_candidates:
                self._candidates.append(
                    itb_util.PredictionCandidate(
                        phrase=cand.phrase,
                        user_freq=cand.user_freq,
                        comment='',
                        from_user_db=cand.user_freq > 0,
                        spell_checking=cand.user_freq < 0))
        for cand in self._candidates:
            self._append_candidate_to_lookup_table(
                phrase=cand.phrase,
                user_freq=cand.user_freq,
                comment=cand.comment,
                from_user_db=cand.from_user_db,
                spell_checking=cand.spell_checking)
        self._candidates_case_mode_orig = self._candidates.copy()
        if self._current_case_mode != 'orig':
            self._case_mode_change(mode=self._current_case_mode)
        return

    def _arrow_down(self) -> bool:
        '''Process Arrow Down Key Event
        Move Lookup Table cursor down'''
        if not self._lookup_table.is_cursor_visible():
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
        # mypy loses track of this being a str (bug in mypy?)
        return str(self._candidates[index].phrase)

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
        if self._debug_level > 1:
            LOGGER.debug(
                'Removing candidate with index=%s from user database', index)
        if not self._set_lookup_table_cursor_pos_in_current_page(index):
            return False
        displayed_phrase = self.get_string_from_lookup_table_cursor_pos()
        if not displayed_phrase:
            return False
        index = self._lookup_table.get_cursor_pos()
        if 0 <= index <= len(self._candidates_case_mode_orig):
            case_mode_orig_phrase = self._candidates_case_mode_orig[
                index].phrase
            if self._debug_level > 1:
                LOGGER.debug('Removing phrase with original case mode “%s”',
                             case_mode_orig_phrase)
                self.database.remove_phrase(
                    phrase=case_mode_orig_phrase)
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
                if self._debug_level > 1:
                    LOGGER.debug('Removing “%s”', stripped_phrase)
                self.database.remove_phrase(phrase=stripped_phrase)
            # Try to remove the whole candidate as well from the database.
            # Probably this won’t do anything, just to make sure that it
            # is really removed even if the prefix also ended up in the
            # database for whatever reason (It could be because the list
            # of prefixes to strip from tokens has changed compared to a
            # an older release of ibus-typing-booster).
            if self._debug_level > 1:
                LOGGER.debug('Removing “%s”', phrase)
            self.database.remove_phrase(phrase=phrase)
        return True

    def get_cursor_pos(self) -> int:
        '''get lookup table cursor position'''
        return int(self._lookup_table.get_cursor_pos())

    def get_lookup_table(self) -> TypingBoosterLookupTable:
        '''Get lookup table'''
        return self._lookup_table

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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
                    languages=dictionary_names,
                    unicode_data_all=self._unicode_data_all,
                    variation_selector=self._emoji_style)
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
        if self._debug_level > 0:
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
        symbol = ''
        label= ''
        tooltip = ''
        for prop in sub_properties:
            if sub_properties[prop]['number'] == int(current_mode):
                symbol = sub_properties[prop]['symbol']
                label = f'{menu["label"]} ({symbol})'
                tooltip = f'{menu["tooltip"]}\n{menu["shortcut_hint"]}'
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
        symbol = ''
        label = ''
        tooltip = ''
        for prop in sub_properties:
            if sub_properties[prop]['number'] == int(current_mode):
                symbol = sub_properties[prop]['symbol']
                label = f'{menu["label"]} ({symbol})'
                tooltip = f'{menu["tooltip"]}\n{menu["shortcut_hint"]}'
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
        if self.dictionary_sub_properties_prop_list.get(0) is None:
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
        if self.preedit_ime_sub_properties_prop_list.get(0) is None:
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
        symbol = ''
        label = ''
        tooltip = ''
        for prop in sub_properties_dict:
            if sub_properties_dict[prop]['number'] == int(current_mode):
                symbol = sub_properties_dict[prop]['symbol']
                label = menu['label']
                tooltip = f'{menu["tooltip"]}\n{menu["shortcut_hint"]}'
        visible = True
        if menu_key == 'InputMode':
            visible = bool(self._keybindings['toggle_input_mode_on_off'])
        if menu_key in ('EmojiPredictionMode', 'OffTheRecordMode'):
            visible = self._show_prediction_candidates()
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
        visible = True
        if menu_key == 'InputMode':
            visible = bool(self._keybindings['toggle_input_mode_on_off'])
        if menu_key in ('EmojiPredictionMode', 'OffTheRecordMode'):
            visible = self._show_prediction_candidates()
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
        self.preedit_ime_sub_properties_prop_list = IBus.PropList()
        self.dictionary_sub_properties_prop_list = IBus.PropList()
        self.main_prop_list = IBus.PropList()

        if self._engine_name != 'typing-booster':
            m17n_db_info = itb_util.M17nDbInfo()
            m17n_icon_property = IBus.Property(
                key='m17n_icon',
                label=IBus.Text.new_from_string(self._engine_name),
                icon= m17n_db_info.get_icon(
                    f'{self._m17n_ime_lang}-{self._m17n_ime_name}'),
                tooltip=IBus.Text.new_from_string(self._engine_name),
                # sensitive=True is necessary to make it clearly
                # visible (not gray) in the floating toolbar. It is
                # also necessary to enable the tooltip which is useful
                # to show the full engine name if the icon is not clear.
                sensitive=True,
                # Even with visible=False it is still visible in the
                # floating toolbar. It hides it only in the panel menu.
                # So visible=False does exactly what I want here, in the
                # panel it is useless but in the floating toolbar it shows
                # which engine is selected.
                visible=False
            )
            self.main_prop_list.append(m17n_icon_property)

        if self._keybindings['toggle_input_mode_on_off']:
            self._init_or_update_property_menu(
                self.input_mode_menu,
                self._input_mode)

        if self._show_prediction_candidates():
            # These two menus are not useful for the restricted
            # engines emulating ibus-m17n:
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

        setup_property = IBus.Property(
            key='setup',
            label=IBus.Text.new_from_string(_('Setup')),
            icon='gtk-preferences',
            tooltip=IBus.Text.new_from_string(
                _('Preferences for ibus-typing-booster')),
            sensitive=True,
            visible=True)
        self.main_prop_list.append(setup_property)
        self.register_properties(self.main_prop_list)

    def do_property_activate( # pylint: disable=arguments-differ
            self,
            ibus_property: str,
            prop_state: IBus.PropState = IBus.PropState.UNCHECKED) -> None:
        '''
        Handle clicks on properties
        '''
        if self._debug_level > 1:
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
        if self._is_setup_running():
            LOGGER.info('Another setup tool is still running, terminating it ...')
            self._stop_setup()

        if os.getenv('IBUS_TYPING_BOOSTER_LIB_LOCATION'):
            setup_cmd = os.path.join(
                os.getenv('IBUS_TYPING_BOOSTER_LIB_LOCATION', ''),
                'ibus-setup-typing-booster')
            cmd = [setup_cmd, '--engine-name', self._engine_name]
        else:
            setup_python_script = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '../setup/main.py')
            cmd = [sys.executable, setup_python_script, '--engine-name', self._engine_name]
        LOGGER.info('Starting setup tool: "%s"', ' '.join(cmd))
        try:
            self._setup_process = subprocess.Popen( # pylint: disable=consider-using-with
                cmd)
        except Exception as error: # pylint: disable=broad-except
            LOGGER.exception(
                'Exception when starting setup tools: %s: %s',
                error.__class__.__name__, error)
            self._setup_process = None

    def _is_setup_running(self) -> bool:
        '''Check if the setup process is still running.'''
        if self._setup_process is None:
            return False
        return self._setup_process.poll() is None # None means still running

    def _stop_setup(self) -> None:
        '''Terminate the setup process if running.'''
        if self._is_setup_running() and self._setup_process:
            self._setup_process.terminate()
            # self._setup_process.kill()
            LOGGER.info('Stopped setup tool.')

    def _clear_input_and_update_ui(self) -> None:
        '''Clear the preëdit and close the lookup table
        '''
        self._clear_input()
        self._update_ui_empty_input()

    def do_destroy(self) -> None: # pylint: disable=arguments-differ
        '''Called when this input engine is destroyed
        '''
        if self._debug_level > 0:
            LOGGER.debug('entering function')
        self._clear_input_and_update_ui()
        self.do_focus_out()
        super().destroy()

    def _add_color_to_attrs_for_spellcheck(
            self, attrs: IBus.AttrList, text: str) -> bool:
        '''May color the preedit if spellchecking fails

        :param attrs: The attribute list of the preedit
        :param text: The current text in the preedit which
                     may need color added
        '''
        if (self._typed_compose_sequence
            or self._m17n_trans_parts.candidates
            or self.get_current_imes()[0][:2] in ('zh', 'ja')
            or not self._color_preedit_spellcheck):
            return False
        stripped_text = itb_util.strip_token(text)
        prefix_length = text.find(stripped_text)
        if (len(stripped_text) >= 4
            and not
            self.database.hunspell_obj.spellcheck(stripped_text)):
            attrs.append(IBus.attr_foreground_new(
                self._color_preedit_spellcheck_argb,
                prefix_length,
                prefix_length + len(stripped_text)))
            return True
        return False

    def _add_color_to_attrs_for_compose(self, attrs: IBus.AttrList) -> bool:
        '''May color the compose part of the preedit

        :param attrs: The attribute list of the preedit
        '''
        if (not self._typed_compose_sequence
            or not self._color_compose_preview):
            return False
        ime = self.get_current_imes()[0]
        length_before_compose = len(
            self._transliterated_strings_before_compose[ime])
        length_compose = len(
            self._transliterated_strings_compose_part)
        attrs.append(IBus.attr_foreground_new(
            self._color_compose_preview_argb,
            length_before_compose,
            length_before_compose + length_compose))
        return True

    def _add_color_to_attrs_for_m17n_preedit(
            self, attrs: IBus.AttrList) -> bool:
        '''May color the m17n candidate part of the preedit

        :param attrs: The attribute list of the preedit

        Uses the same color as for compose preedits.
        '''
        if (self._typed_compose_sequence
            or not self._color_m17n_preedit):
            return False
        if self._m17n_trans_parts.candidates:
            length_before = len(self._m17n_trans_parts.committed)
            length_inner_preedit = len(self._m17n_trans_parts.preedit)
        else:
            ime = self.get_current_imes()[0]
            trans = self._transliterators[ime]
            transliterated_parts = trans.transliterate_parts(
                self._typed_string, ascii_digits=self._ascii_digits)
            length_before = len(transliterated_parts.committed)
            length_inner_preedit = len(transliterated_parts.preedit)
        if not length_inner_preedit:
            return False
        attrs.append(IBus.attr_foreground_new(
            self._color_m17n_preedit_argb,
            length_before,
            length_before + length_inner_preedit))
        return True

    def _get_preedit_string_with_case_mode_applied(self) -> str:
        '''Apply the current case mode and normalization only to the
        parts of the preedit which do not belong to an “inner” preedit.

        An “inner” preedit might come from a compose sequence, an m17n
        candidate list, or an unfinished m17n transliteration.
        '''
        ime = self.get_current_imes()[0]
        trans = self._transliterators[ime]
        text = self._transliterated_strings[ime]
        if self._typed_compose_sequence:
            before = self._transliterated_strings_before_compose[ime]
            inner_preedit = self._transliterated_strings_compose_part
        elif self._m17n_trans_parts.candidates:
            before = self._m17n_trans_parts.committed
            inner_preedit = self._m17n_trans_parts.preedit
        else:
            transliterated_parts = trans.transliterate_parts(
                self._typed_string, ascii_digits=self._ascii_digits)
            before = transliterated_parts.committed
            inner_preedit = transliterated_parts.preedit
        after = text[len(before) + len(inner_preedit):]
        cm_func = self._case_modes[self._current_case_mode]['function']
        before = str(cm_func(before))
        after = str(cm_func(after))
        return before + inner_preedit + after

    def _update_preedit(self) -> None:
        '''Update Preedit String in UI'''
        if self._debug_level > 1:
            LOGGER.debug('entering function')
        _str = self._get_preedit_string_with_case_mode_applied()
        if self._debug_level > 2:
            LOGGER.debug('_str=“%s”', _str)
        if self._hide_input:
            _str = '*' * len(_str)
        if _str == '':
            if self._current_preedit_text.text_str == '':
                if self._debug_level > 1:
                    LOGGER.debug('Avoid clearing already empty preedit.')
                return
            self.update_preedit_text_with_mode(
                IBus.Text.new_from_string(''), 0, False,
                IBus.PreeditFocusMode.COMMIT)
            return
        attrs = IBus.AttrList()
        if (not self._preedit_style_only_when_lookup
            or self._lookup_table.enabled_by_tab
            or self._lookup_table.enabled_by_min_char_complete):
            attrs.append(IBus.attr_underline_new(
                self._preedit_underline, 0, len(_str)))
            compose_colored = self._add_color_to_attrs_for_compose(attrs)
            m17n_colored = False
            if not compose_colored:
                m17n_colored = self._add_color_to_attrs_for_m17n_preedit(attrs)
            if not (compose_colored or m17n_colored):
                self._add_color_to_attrs_for_spellcheck(attrs, _str)
        else:
            # Preedit style “only when lookup is enabled” is
            # requested and lookup is *not* enabled.  Therefore,
            # make the preedit appear as if it were completely
            # normal text:
            attrs.append(IBus.attr_underline_new(
                IBus.AttrUnderline.NONE, 0, len(_str)))
        text = IBus.Text.new_from_string(_str)
        text.set_attributes(attrs)
        self.update_preedit_text_with_mode(
            text, self.get_caret(), True, IBus.PreeditFocusMode.COMMIT)

    def _update_aux(self) -> None:
        '''Update auxiliary text'''
        aux_string = ''
        if self._lookup_table.state == LookupTableState.M17N_CANDIDATES:
            aux_string += ''.join(
                self._typed_string[
                    self._m17n_trans_parts.committed_index
                    :self._typed_string_cursor]).replace(
                                   ''.join(itb_util.ANTHY_HENKAN_WIDE), '')
            aux_string += ' '
        if self._show_number_of_candidates:
            aux_string += (
                f'({self._lookup_table.get_cursor_pos() + 1} / '
                f'{self._lookup_table.get_number_of_candidates()}) ')
        if self._show_status_info_in_auxiliary_text:
            if self._lookup_table.state == LookupTableState.COMPOSE_COMPLETIONS:
                aux_string += '⎄ '
            elif self._lookup_table.state == LookupTableState.RELATED_CANDIDATES:
                aux_string += '🔗 '
            elif self._lookup_table.state == LookupTableState.SELECTION_INFO:
                aux_string += '🔬 '
            elif self._lookup_table.state == LookupTableState.M17N_CANDIDATES:
                aux_string += f'🦜 {self._m17n_trans_parts.status} '
            else:
                # “Normal” lookup table
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
        if self._debug_level > 0 and not self._unit_test:
            client = f'🪟{self._im_client}'
            aux_string += client
            attrs.append(IBus.attr_foreground_new(
                itb_util.color_string_to_argb('Purple'),
                len(aux_string)-len(client),
                len(aux_string)))
        if self._debug_level > 2:
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
        text.set_attributes(attrs)
        visible = True
        if (self._lookup_table.get_number_of_candidates() == 0
            or self._hide_input
            or (self._tab_enable
                and not self.has_osk
                and not self._lookup_table.enabled_by_tab)
            or not aux_string):
            visible = False
        self.update_auxiliary_text(text, visible)

    def _update_lookup_table(self) -> None:
        '''Update the lookup table

        Show it if it is not empty and not disabled, otherwise hide it.
        '''
        # Also make sure to hide lookup table if there are
        # no candidates to display. On f17, this makes no
        # difference but gnome-shell in f18 will display
        # an empty suggestion popup if the number of candidates
        # is zero!
        if ((self.is_empty()
             and not self.has_osk
             and self._min_char_complete != 0
             and self._lookup_table.state not in (
                 LookupTableState.RELATED_CANDIDATES,
                 LookupTableState.SELECTION_INFO)
             and not self._typed_compose_sequence)
            or self._hide_input
            or self._lookup_table.get_number_of_candidates() == 0
            or (self._tab_enable
                and not self.has_osk
                and not self._lookup_table.enabled_by_tab)):
            self.hide_lookup_table()
            self._update_preedit()
            return
        if (not self._inline_completion
            or self.has_osk
            or self._typed_compose_sequence
            or self._lookup_table.state in (
                LookupTableState.M17N_CANDIDATES,
                LookupTableState.RELATED_CANDIDATES,
                LookupTableState.SELECTION_INFO)
            or self._lookup_table.get_cursor_pos() != 0):
            # Show standard lookup table:
            self.update_lookup_table(self.get_lookup_table(), True)
            self._update_preedit()
            return
        # There is at least one candidate the lookup table cursor
        # points to the first candidate, the lookup table is enabled
        # and inline completion is on.
        typed_string = itb_util.normalize_nfc_and_composition_exclusions(
            self._transliterated_strings[
                self.get_current_imes()[0]])
        first_candidate = itb_util.normalize_nfc_and_composition_exclusions(
            self._candidates[0].phrase)
        if (not first_candidate.startswith(typed_string)
            or first_candidate == typed_string):
            # The first candidate is not a direct completion of the
            # typed string. Trying to show that inline gets very
            # confusing.  Don’t do that, show standard lookup table:
            if (self._inline_completion < 2
                or self._lookup_table.is_cursor_visible()):
                # Show standard lookup table as a fallback:
                self.update_lookup_table(self.get_lookup_table(), True)
            else:
                # self._inline_completion == 2 means do not fall back
                # to the standard lookup table:
                self.hide_lookup_table()
                text = IBus.Text.new_from_string('')
                self.update_auxiliary_text(text, False)
            self._update_preedit()
            return
        # Show only the first candidate, inline in the preëdit, hide
        # the lookup table and the auxiliary text:
        completion = first_candidate[len(typed_string):]
        self.hide_lookup_table()
        text = IBus.Text.new_from_string('')
        self.update_auxiliary_text(text, False)
        text = IBus.Text.new_from_string(typed_string + completion)
        attrs = IBus.AttrList()
        attrs.append(IBus.attr_underline_new(
            self._preedit_underline, 0, len(typed_string)))
        if self._lookup_table.is_cursor_visible():
            attrs.append(IBus.attr_underline_new(
                self._preedit_underline,
                len(typed_string), len(typed_string + completion)))
        else:
            m17n_colored = self._add_color_to_attrs_for_m17n_preedit(attrs)
            if not m17n_colored:
                self._add_color_to_attrs_for_spellcheck(attrs, typed_string)
            if self._color_inline_completion:
                attrs.append(IBus.attr_foreground_new(
                    self._color_inline_completion_argb,
                    len(typed_string), len(typed_string + completion)))
            attrs.append(IBus.attr_underline_new(
                IBus.AttrUnderline.NONE,
                len(typed_string), len(typed_string + completion)))
        text.set_attributes(attrs)
        if (self._lookup_table.is_cursor_visible()
            and not self._is_candidate_auto_selected):
            caret = len(first_candidate)
        else:
            caret = self.get_caret()
        self.update_preedit_text_with_mode(
            text, caret, True, IBus.PreeditFocusMode.COMMIT)
        return

    def _update_lookup_table_and_aux(self) -> None:
        '''Update the lookup table and the auxiliary text

        :return: None, always, which is falsy and should work
                 the same as `return False` to remove the source
                 added by Glib.timeout_add() (GLib.SOURCE_REMOVE is False)
        '''
        self._update_aux()
        # auto select best candidate if the option
        # self._auto_select_candidate is on:
        self._is_candidate_auto_selected = False
        if (self._lookup_table.get_number_of_candidates()
            and not self._lookup_table.is_cursor_visible()):
            if self._auto_select_candidate == 2:
                # auto select: Yes, always
                self._lookup_table.set_cursor_visible(True)
                self._is_candidate_auto_selected = True
            elif self._auto_select_candidate == 1:
                # auto select: Yes, but only when extremely likely
                first_candidate = ''
                user_freq = 0.0
                typed_string = ''
                if self._candidates:
                    first_candidate = self._candidates[0].phrase
                    user_freq = self._candidates[0].user_freq
                typed_string = itb_util.normalize_nfc_and_composition_exclusions(
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
        self._timeout_source_id = 0

    def _update_candidates_and_lookup_table_and_aux(self) -> None:
        '''Update the candidates, the lookup table and the auxiliary text

        :return: None, always, which is falsy and should work
                 the same as `return False` to remove the source
                 added by Glib.timeout_add() (GLib.SOURCE_REMOVE is False)
        '''
        if self._label_busy and self._label_busy_string.strip():
            # Show a label in the auxiliary text to indicate that the
            # lookup table is being updated (by default an hourglass
            # with moving sand):
            self.update_auxiliary_text(
                IBus.Text.new_from_string(
                    self._label_busy_string.strip()), True)
        else:
            self.update_auxiliary_text(
                IBus.Text.new_from_string(''), False)
        self._update_candidates()
        self._update_lookup_table_and_aux()
        if self._debug_level < 2:
            return
        if not self.has_surrounding_text:
            return
        LOGGER.debug('self._surrounding_text=%r', self._surrounding_text)

    def _update_ui_empty_input(self) -> None:
        '''Update the UI when the input is empty.

        Even when the input is empty, it is possible that a preedit
        and a lookup table are shown because it is possible that
        self._min_char_complete == 0 and then sometimes a completion
        is tried even when the input is empty.

        '''
        if self._debug_level > 1:
            LOGGER.debug('entering function')
        self._update_preedit()
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)
        self.hide_lookup_table()
        self._lookup_table.enabled_by_tab = False
        self._lookup_table.state = LookupTableState.NORMAL
        self.update_auxiliary_text(
            IBus.Text.new_from_string(''), False)

    def _update_ui_empty_input_try_completion(self) -> None:
        '''Update the UI when the input is empty and try a completion.'''
        if self._debug_level > 1:
            LOGGER.debug('entering function')
        if not self.is_empty():
            self._update_preedit()
            return
        self.get_context()
        if (not self._unit_test
            and
            (not self._surrounding_text.event.is_set()
             or not self._is_context_from_surrounding_text)):
            if self._debug_level > 1:
                LOGGER.debug(
                    'Failed to get context from surrounding text. '
                    'Do not try to complete on empty input.')
            self._update_ui_empty_input()
            return
        if ((self._min_char_complete != 0 and not self.has_osk)
            or self._hide_input
            or not self._word_predictions
            or (self._tab_enable
                and not self.has_osk
                and not self._lookup_table.enabled_by_tab)):
            # If the lookup table would be hidden anyway, there is no
            # point in updating the candidates, save some time by making
            # sure the lookup table and the auxiliary text are really
            # empty and hidden and return immediately:
            self._update_ui_empty_input()
            return
        self._lookup_table.enabled_by_tab = False
        self._lookup_table.state = LookupTableState.NORMAL
        phrase_candidates = self.database.select_words(
            '', p_phrase=self.get_p_phrase(), pp_phrase=self.get_pp_phrase())
        if self._debug_level > 2:
            LOGGER.debug('phrase_candidates=%s', phrase_candidates)
        if not phrase_candidates:
            self._update_ui_empty_input()
            return
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)
        self.hide_lookup_table()
        if self._label_busy and self._label_busy_string.strip():
            # Show a label in the auxiliary text to indicate that the
            # lookup table is being updated (by default an hourglass
            # with moving sand):
            self.update_auxiliary_text(
                IBus.Text.new_from_string(
                    self._label_busy_string.strip()), True)
        else:
            self.update_auxiliary_text(
                IBus.Text.new_from_string(''), False)
        self._candidates = [
            itb_util.PredictionCandidate(
                phrase=cand.phrase,
                user_freq=cand.user_freq,
                comment='',
                from_user_db=True,
                spell_checking=False)
            for cand in phrase_candidates]
        for cand in self._candidates:
            self._append_candidate_to_lookup_table(
                phrase=cand.phrase,
                user_freq=cand.user_freq,
                comment=cand.comment,
                from_user_db=cand.from_user_db,
                spell_checking=cand.spell_checking)
        self._candidates_case_mode_orig = self._candidates.copy()
        if self._current_case_mode != 'orig':
            self._case_mode_change(mode=self._current_case_mode)
        self._update_preedit()
        if self._timeout_source_id:
            GLib.source_remove(self._timeout_source_id)
            self._timeout_source_id = 0
        delay = self._candidates_delay_milliseconds
        if self.has_osk:
            delay = 0
        self._timeout_source_id = GLib.timeout_add(
            delay, self._update_lookup_table_and_aux)

    def _update_ui(self) -> None:
        '''Update User Interface'''
        if self._debug_level > 1:
            LOGGER.debug('entering function')
        if self.is_empty():
            # Hide lookup table again if preëdit became empty and
            # suggestions are only enabled by Tab key:
            self._lookup_table.enabled_by_tab = False
        if (self.is_empty()
            or self._hide_input
            or not self._show_prediction_candidates()
            or (self._tab_enable
                and not self.has_osk
                and not self._lookup_table.enabled_by_tab)):
            # If the lookup table would be hidden anyway, there is no
            # point in updating the candidates, save some time by making
            # sure the lookup table and the auxiliary text are really
            # empty and hidden and return immediately:
            self._lookup_table.clear()
            self._lookup_table.set_cursor_visible(False)
            self.hide_lookup_table()
            self.update_auxiliary_text(
                IBus.Text.new_from_string(''), False)
            self._update_preedit()
            return
        self._lookup_table.state = LookupTableState.NORMAL
        # See: https://github.com/mike-fabian/ibus-typing-booster/issues/474
        # Nevertheless update the preedit unconditionally here, even though
        # it is updated again in _update_lookup_table(). Because when
        # self._candidates_delay_milliseconds is big and thus
        # updating the candidates is delayed by a long time, it is weird
        # when the preedit does not update until the lookup table appears.
        self._update_preedit()
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)
        self.hide_lookup_table()
        self.update_auxiliary_text(
            IBus.Text.new_from_string(''), False)
        if self._timeout_source_id:
            GLib.source_remove(self._timeout_source_id)
            self._timeout_source_id = 0
        delay = self._candidates_delay_milliseconds
        if self.has_osk:
            delay = 0
        self._timeout_source_id = GLib.timeout_add(
            delay, self._update_candidates_and_lookup_table_and_aux)

    def _lookup_related_candidates(self, phrase: str ='') -> bool:
        '''Lookup related (similar) emoji or related words (synonyms,
        hyponyms, hypernyms).

        :return: True if related candidates could be found, False if not.
        '''
        if (self._lookup_table.state in (
                LookupTableState.COMPOSE_COMPLETIONS,
                LookupTableState.M17N_CANDIDATES)):
            if self._debug_level > 1:
                LOGGER.debug(
                    'Compose completions or m17n candidates are shown, '
                    'not looking up related candidates')
            return False
        # We might end up here by typing a shortcut key like
        # AltGr+F12.  This should also work when suggestions are only
        # enabled by Tab and are currently disabled.  Typing such a
        # shortcut key explicitly requests looking up related
        # candidates, so it should have the same effect as Tab and
        # enable the lookup table:
        if (self._tab_enable
            and not self.has_osk
            and not self._lookup_table.enabled_by_tab):
            self._lookup_table.enabled_by_tab = True
        if phrase == '':
            if (self._lookup_table.get_number_of_candidates()
                and  self._lookup_table.is_cursor_visible()):
                phrase = self.get_string_from_lookup_table_cursor_pos()
            else:
                phrase = self._transliterated_strings[
                    self.get_current_imes()[0]]
        if not phrase:
            return False
        # Hide lookup table and show an hourglass with moving sand in
        # the auxiliary text to indicate that the lookup table is
        # being updated. Don’t clear the lookup table here because we
        # might want to show it quickly again if nothing related is
        # found:
        original_auxiliary_text_content = self._current_auxiliary_text.content
        original_auxiliary_text_visible = self._current_auxiliary_text.visible
        if self._lookup_table.get_number_of_candidates():
            self.hide_lookup_table()
        if self._label_busy and self._label_busy_string.strip():
            # Show a label in the auxiliary text to indicate that the
            # lookup table is being updated (by default an hourglass
            # with moving sand):
            self.update_auxiliary_text(
                IBus.Text.new_from_string(
                    self._label_busy_string.strip()), True)
        else:
            self.update_auxiliary_text(
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
                languages=self._dictionary_names,
                unicode_data_all=self._unicode_data_all,
                variation_selector=self._emoji_style)
        if self._debug_level > 0:
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
                    related_candidates.append(itb_util.PredictionCandidate(
                        phrase=synonym, user_freq=0, comment='[synonym]'))
                for hypernym in itb_nltk.hypernyms(phrase, keep_original=False):
                    related_candidates.append(itb_util.PredictionCandidate(
                        phrase=hypernym, user_freq=0, comment='[hypernym]'))
                for hyponym in itb_nltk.hyponyms(phrase, keep_original=False):
                    related_candidates.append(itb_util.PredictionCandidate(
                        phrase=hyponym, user_freq=0, comment='[hyponym]'))
            except (LookupError,) as error:
                LOGGER.exception(
                    'Exception when trying to use nltk: %s: %s',
                     error.__class__.__name__, error)
        if self._debug_level > 1:
            LOGGER.debug(
                'related_candidates of “%s” = %s\n',
                phrase, related_candidates)
        if not related_candidates:
            # Nothing related found, show the original lookup table
            # and original auxiliary text again:
            self.update_auxiliary_text(
                original_auxiliary_text_content,
                original_auxiliary_text_visible)
            if self._lookup_table.get_number_of_candidates():
                self.update_lookup_table(self.get_lookup_table(), True)
            return False
        self._candidates = []
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)
        for cand in related_candidates:
            self._candidates.append(
                itb_util.PredictionCandidate(
                    phrase=cand.phrase,
                    user_freq=cand.user_freq,
                    comment=cand.comment,
                    from_user_db=False,
                    spell_checking=False))
            self._append_candidate_to_lookup_table(
                phrase=cand.phrase, user_freq=cand.user_freq, comment=cand.comment)
        self._lookup_table.state = LookupTableState.RELATED_CANDIDATES
        self._lookup_table.related_candidates_phrase = phrase
        self._update_lookup_table_and_aux()
        return True

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
        if self._debug_level > 1:
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
        if self.is_empty():
            return False
        if mode in ('next', 'previous'):
            self._current_case_mode = self._case_modes[
                self._current_case_mode][mode]
        else:
            self._current_case_mode = mode
        if (not self._candidates
            or not self._lookup_table.get_number_of_candidates()):
            return True
        new_candidates = []
        for cand in self._candidates_case_mode_orig:
            new_candidates.append(
                itb_util.PredictionCandidate(
                    phrase=self._case_modes[
                        self._current_case_mode]['function'](cand.phrase),
                    user_freq=cand.user_freq,
                    comment=cand.comment,
                    from_user_db=cand.from_user_db,
                    spell_checking=cand.spell_checking))
        self._candidates = new_candidates
        cursor_visible = self._lookup_table.is_cursor_visible()
        cursor_pos = self._lookup_table.get_cursor_pos()
        self._lookup_table.clear()
        for cand in self._candidates:
            self._append_candidate_to_lookup_table(
                phrase=cand.phrase,
                user_freq=cand.user_freq,
                comment=cand.comment,
                from_user_db=cand.from_user_db,
                spell_checking=cand.spell_checking)
        self._lookup_table.set_cursor_pos(cursor_pos)
        self._lookup_table.set_cursor_visible(cursor_visible)
        return True

    def _has_transliteration(self, msymbol_list: List[str]) -> bool:
        '''Check whether the current input (list of msymbols) has a
        (non-trivial, i.e. not transliterating to itself)
        transliteration in any of the current input methods.
        '''
        for ime in self.get_current_imes():
            if self._transliterators[ime].transliterate(
                    msymbol_list) != ''.join(msymbol_list):
                if self._debug_level > 1:
                    LOGGER.debug(
                        '_has_transliteration(%s) == True\n', msymbol_list)
                return True
        if self._debug_level > 1:
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
        if not self._lookup_table.get_number_of_candidates():
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
        if self.has_osk:
            LOGGER.info(
                'OSK is visible: do not commit candidate by index %s', index)
            return False
        if (not self._lookup_table.get_number_of_candidates()
            or self._lookup_table.hidden):
            return False
        candidate_number = (
            self._get_lookup_table_current_page() * self._page_size + index)
        if not (candidate_number
            < self._lookup_table.get_number_of_candidates()
            and 0 <= index < self._page_size):
            return False
        selected_candidate = (
            self.get_string_from_lookup_table_current_page(index))
        if not selected_candidate:
            return False
        if self._lookup_table.state == LookupTableState.COMPOSE_COMPLETIONS:
            self._lookup_table.state = LookupTableState.NORMAL
            self._candidates = []
            self._lookup_table.clear()
            self._lookup_table.set_cursor_visible(False)
            self._update_lookup_table_and_aux()
            self._typed_compose_sequence = []
            self._update_transliterated_strings()
            self._update_preedit()
            if self.get_input_mode():
                self._insert_string_at_cursor(list(selected_candidate))
                self._update_ui()
                return True
            super().commit_text(
                IBus.Text.new_from_string(selected_candidate))
            self._commit_happened_after_focus_in = True
            return True
        if self._lookup_table.state == LookupTableState.M17N_CANDIDATES:
            if self._debug_level > 1:
                LOGGER.debug('Commit m17n candidate “%s”', selected_candidate)
            self._lookup_table.state = LookupTableState.NORMAL
            self._candidates = []
            self._lookup_table.clear()
            self._lookup_table.set_cursor_visible(False)
            self._update_lookup_table_and_aux()
            selected_candidate_length = len(selected_candidate)
            m17n_preedit_replacement = selected_candidate
            if (all(len(candidate) == selected_candidate_length
                   for candidate in self._m17n_trans_parts.candidates)):
                # If all candidates have the same length, replacing
                # only part of the m17n preedit is possible and
                # better. Otherwise replacing the whole m17n preedit
                # is probably best.
                m17n_preedit_replacement = (
                    self._m17n_trans_parts.preedit[
                        :self._m17n_trans_parts.cursor_pos][
                            :-len(selected_candidate)]
                    + selected_candidate
                    + self._m17n_trans_parts.preedit[
                        self._m17n_trans_parts.cursor_pos:])
            if self._debug_level > 1:
                LOGGER.debug(
                    'm17n_preedit_replacement=“%s” trans_parts=%s',
                    m17n_preedit_replacement, repr(self._m17n_trans_parts))
                LOGGER.debug(
                    'OLD: self._typed_string=%s, self._typed_string_cursor=%s',
                    self._typed_string, self._typed_string_cursor)
            self._typed_string = (
                self._typed_string[:self._m17n_trans_parts.committed_index]
                + list(m17n_preedit_replacement)
                + self._typed_string[self._typed_string_cursor:])
            self._typed_string_cursor = (
                self._m17n_trans_parts.committed_index
                + len(list(m17n_preedit_replacement)))
            if self._debug_level > 1:
                LOGGER.debug(
                    'NEW: self._typed_string=%s, self._typed_string_cursor=%s',
                    self._typed_string, self._typed_string_cursor)
            self._update_transliterated_strings()
            self._m17n_trans_parts = m17n_translit.TransliterationParts()
            self._update_ui()
            return True
        if self.is_empty():
            self._commit_string(selected_candidate + extra_text,
                                input_phrase=selected_candidate)
        else:
            # _commit_string() will calculate input_phrase:
            self._commit_string(selected_candidate + extra_text)
        self._clear_input()
        if extra_text == ' ':
            self._trigger_surrounding_text_update()
            # Tiny delay to give the surrounding text a chance to
            # update:
            GLib.timeout_add(5, self._update_ui_empty_input_try_completion)
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
        if self._debug_level > 1:
            LOGGER.debug('commit_phrase=“%s” input_phrase=“%s”',
                         repr(commit_phrase), repr(input_phrase))
        if not commit_phrase:
            return
        # If the suggestions are only enabled by Tab key, i.e. the
        # lookup table is not shown until Tab has been typed, hide
        # the lookup table again after each commit. That means
        # that after each commit, when typing continues the
        # lookup table is first hidden again and one has to type
        # Tab again to show it.
        self._lookup_table.enabled_by_tab = False
        # Same for the case when the lookup table was enabled by
        # the minimum numbers to complete, reset this here to
        # make sure that the preëdit styling for the next letter
        # typed will be correct.
        self._lookup_table.enabled_by_min_char_complete = False
        if not input_phrase:
            input_phrase = self._transliterated_strings[
                self.get_current_imes()[0]]
        if not input_phrase:
            input_phrase = commit_phrase
        if not commit_phrase.isspace():
            # If commit_phrase contains only white space
            # leave self._new_sentence as it is!
            self._new_sentence = False
            names = self.get_dictionary_names()
            name = names[0] if names else ''
            if itb_util.text_ends_a_sentence(commit_phrase, language=name):
                self._new_sentence = True
        if fix_sentence_end:
            commit_phrase = (
                self._commit_string_fix_sentence_end(commit_phrase)
                + commit_phrase)
        # Trying to make multiline commits work in different environments.
        #
        # See also
        # https://github.com/mike-fabian/ibus-typing-booster/commit/35a22dab25be8cb9d09d048ca111f661d6b73909
        #
        # commit_mode == 'single':
        #     Commit everything in a single commit
        #
        #     I think committing everything here in a single commit
        #     **should** always work, unfortunately it does not ☹.
        #
        #     Works (+) or doesn’t work (-) for:
        #     + gnome-shell: + gnome-text-editor
        #                    + browsers “complicated stuff”
        #                        + firefox, google-chrome
        #                            + google-docs
        #                            + gmail compose editor
        #                            + facebook comment editor
        #                    + gnome-text-editor
        #                    + *everywhere* else, I think
        #     + xim: + xterm
        #     + QIBusInputContext: + kwrite
        #                          + kate
        #                          + ...
        #     + Qt: probably but not tested
        #     + gtk4-im: + gtk4-demo
        #                + gnome-text-editor
        #                + ptyxis
        #                + ...
        #     +/- gtk3-im: + gedit
        #                  + gnome-terminal
        #                  + xfce4-terminal
        #                  + browsers “simple stuff”
        #                      + firefox, google-chrome
        #                          + google-translate
        #                          + ...
        #                  - browsers “complicated stuff”
        #                      - firefox, google-chrome
        #                          - google-docs
        #                          - gmail mail compose editor
        #                          - facebook comment editor
        #                          - ...
        #                 - thunderbird
        #
        # commit_mode == 'multi-forward-shift-return':
        #     Commit each line separately and forward a “Shift+Return” key
        #     event between each line. “Shift+Return” instead of just “Return”
        #     because “Return” sends messages in most chat programs
        #     (WhatsApp, Telegram, ...) and chat like things like
        #     Facebook comments. “Shift+Return” avoids sending the message
        #     and inserts a new line. In non-chat places it seems to have
        #     no disadvantages sending a “Shift+Return“ seems to behave
        #     the same as just “Return”.
        #
        #     Works (+) or doesn’t work (-) for:
        #     + xim: + xterm
        #            + ...
        #     + gtk3-im: + *everywhere*, including
        #                + browsers “complicated stuff”
        #                    + firefox, google-chrome
        #                        + google-docs
        #                        + gmail compose editor
        #                        + facebook comment editor
        #                + thunderbird
        #     - gtk4-im: - gtk4-demo
        #                - gnome-text-editor, ...
        #     - SDL2_Application
        #
        # commit_mode == 'multi-commit-return':
        #     Commit each line separately and commit a '\r'
        #     (not '\n'!) between each line.
        #
        #     Works (+) or doesn’t work (-) for:
        #     + gtk4-im:  + gnome-text-editor
        #                 + ptyxis
        #                 + ...
        #     +/- gtk3-im: + gedit
        #                  + xfce4-terminal
        #                  + gnome-terminal
        #                  + browsers “simple stuff”
        #                      + firefox, google-chrome
        #                          + google-translate
        #                          + ...
        #                  - browsers “complicated stuff”
        #                      - firefox, google-chrome
        #                          - google-docs
        #                          - gmail mail compose editor
        #                          - facebook comment editor
        #                          - ...
        #                 - thunderbird
        #     - xim: - xterm
        #            - ...
        #
        #     This surprisingly worked for me in firefox in the
        #     facebook comment editor on F41 on **real** hardware. I
        #     had hoped already I had found a solution which works
        #     everywhere. But then I was disappointed to find that
        #     this didn’t work on F41 in a qemu VM. I didn’t
        #     understand the difference, both F41 were fully updated,
        #     both running an Xorg desktop.  And it does not work with
        #     xim either.
        #
        #     This mode rarely helps, but it seems to help in some
        #     corner cases. So let’s try this mode as a last resort
        #     when we know already that a single commit will not work
        #     and forwarding key events is not allowed because
        #     self._avoid_forward_key_event is True.
        commit_lines = commit_phrase.split('\n')
        if self._debug_level > 0:
            LOGGER.debug('commit_phrase=%s commit_lines=%s',
                         repr(commit_phrase), repr(commit_lines))
        # The first matching regexp in commit_mode_patterns wins:
        commit_mode_patterns = (
            (r'^gnome-shell:', 'single'),
            (r'^gtk4-im:', 'single'),
            (r'^(Qt|QIBusInputContext):', 'single'),
            (r'^xim:', 'single'),
            (r'^gtk3-im:', 'multi-forward-shift-return'),
            # When ibus has just started, in the first window which
            # gets focus the im module is unknown, i.e. the pattern
            # r'^:' would match (I think that must be a bug somewhere,
            # I reported it here:
            # https://github.com/ibus/ibus/issues/2717). If nothing
            # else is known using a single commit is probably the best
            # bet.  But if we can detect firefox, thunderbird, or
            # google-chrome, we know that it must be 'gtk3-im' so we
            # can use 'multi-forward-shift-return'.  Try to match
            # these case insensitively (regexp starts with (?i)):
            (r'(?i)^:.*firefox.*:', 'multi-forward-shift-return'),
            (r'(?i)^:.*google-chrome.*:', 'multi-forward-shift-return'),
            (r'(?i)^:.*thunderbird.*:', 'multi-forward-shift-return'),
            (r'^:', 'single'),
        )
        commit_mode = 'single'
        if len(commit_lines) >= 2:
            if self._debug_level > 0:
                LOGGER.debug('self._im_client=“%s”', self._im_client)
            for pattern, mode in commit_mode_patterns:
                if re.search(pattern, self._im_client):
                    if self._debug_level > 0:
                        LOGGER.debug(
                            'commit_mode_pattern match: pattern=%s mode=%s',
                            pattern, mode)
                    commit_mode = mode
                    break # first matching pattern wins!
        if (commit_mode == 'multi-forward-shift-return'
            and self._avoid_forward_key_event):
            commit_mode = 'multi-commit-return'
        if self._debug_level > 0:
            LOGGER.debug('commit_mode=%s', commit_mode)
        if commit_mode.startswith('multi'):
            for index, commit_line in enumerate(commit_lines):
                if index < len(commit_lines) - 1:
                    if commit_line:
                        super().commit_text(
                            IBus.Text.new_from_string(commit_line))
                        # The sleep is needed because this is racy,
                        # without the sleep it is likely that all the
                        # commits come first followed by all the
                        # forwarded Return keys:
                        time.sleep(self._ibus_event_sleep_seconds)
                    if commit_mode == 'multi-forward-shift-return':
                        self.forward_key_event(
                            IBus.KEY_Return,
                            self._keyvals_to_keycodes.ibus_keycode(
                                IBus.KEY_Return),
                            IBus.ModifierType.SHIFT_MASK)
                    else: # commit_mode == 'multi-commit-return':
                        super().commit_text(
                            IBus.Text.new_from_string('\r'))
                else:
                    if self._debug_level > 0:
                        LOGGER.debug('commit %s', repr(commit_line))
                    super().commit_text(
                        IBus.Text.new_from_string(commit_line))
                time.sleep(self._ibus_event_sleep_seconds)
        else: # commit_mode == 'single':
            super().commit_text(
                IBus.Text.new_from_string(commit_phrase))
        self._commit_happened_after_focus_in = True
        if (self._off_the_record
            or self._record_mode == 3
            or self._hide_input
            or self._input_hints & itb_util.InputHints.PRIVATE):
            if self._debug_level > 1:
                LOGGER.debug('Privacy: NOT recording and pushing context.')
            return
        stripped_commit_phrase = itb_util.strip_token(commit_phrase)
        if self._debug_level > 1:
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
            if self._debug_level > 1:
                LOGGER.debug('self._record_mode=%d: Not recording: %r',
                             self._record_mode, commit_phrase)
            return
        if (self._record_mode == 2
            and not self.database.hunspell_obj.spellcheck(commit_phrase)):
            if self._debug_level > 1:
                LOGGER.debug('self._record_mode=%d: Not recording: %r',
                             self._record_mode, commit_phrase)
            return
        if self._debug_level > 1:
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
                if self._debug_level > 1:
                    LOGGER.debug(
                        'self._record_mode=%d: Not recording multi: %r',
                        self._record_mode,
                        self.get_p_phrase() + ' ' + stripped_commit_phrase)
                return
            if (self._record_mode == 2
                and not
                self.database.hunspell_obj.spellcheck(self.get_p_phrase())):
                if self._debug_level > 1:
                    LOGGER.debug(
                        'self._record_mode=%d: Not recording multi: %r',
                        self._record_mode,
                        self.get_p_phrase() + ' ' + stripped_commit_phrase)
                return
            if self._debug_level > 1:
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
        if (not self.has_surrounding_text
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
        if self._debug_level > 1:
            LOGGER.debug('language_code=%r', language_code)
        chars_dict = itb_util.FIX_WHITESPACE_CHARACTERS.get(
            language_code, itb_util.FIX_WHITESPACE_CHARACTERS['*'])
        for chars, new_whitespace in chars_dict.items():
            pattern_sentence_end = re.compile(
                r'^[' + re.escape(chars) + r']+[\s]*$')
            if pattern_sentence_end.search(commit_phrase):
                text = self._surrounding_text.text
                cursor_pos = self._surrounding_text.cursor_pos
                if self._debug_level > 1:
                    LOGGER.debug(
                        'Checking for whitespace before commit_phrase %r: '
                        'self._surrounding_text=%r',
                        commit_phrase, self._surrounding_text)
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
                    if self._debug_level > 1:
                        text = self._surrounding_text.text
                        cursor_pos = self._surrounding_text.cursor_pos
                        LOGGER.debug(
                            'Removed whitespace before commit_phrase %r: '
                            'self._surrounding_text=%r '
                            'Replace with %r',
                            commit_phrase,
                            self._surrounding_text, new_whitespace)
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
        if self._debug_level > 1:
            LOGGER.debug('KeyEvent object: %s', key)
            LOGGER.debug('self._arrow_keys_reopen_preedit=%s',
                         self._arrow_keys_reopen_preedit)
        if not self._arrow_keys_reopen_preedit:
            if self._debug_level > 1:
                LOGGER.debug('self._arrow_keys_reopen_preedit not set. '
                             'Do not reopen preedit.')
            return False
        if not self.is_empty():
            if self._debug_level > 1:
                LOGGER.debug('There is input already, no need to reopen.')
            return False
        if self._prev_key is not None and self._prev_key.val != key.val:
            if self._debug_level > 1:
                LOGGER.debug(
                    'Previous key not set or not equal to the just released '
                    'key. Better do not try to reopen the preedit.')
            return False
        if (key.val not in (IBus.KEY_Left, IBus.KEY_KP_Left,
                            IBus.KEY_Right, IBus.KEY_KP_Right,
                            IBus.KEY_BackSpace,
                            IBus.KEY_Delete, IBus.KEY_KP_Delete)):
            if self._debug_level > 1:
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
            if self._debug_level > 1:
                LOGGER.debug(
                    'Not reopening the preedit because a modifier is set.')
            return False
        if (not self.has_surrounding_text
            or self._input_purpose in [itb_util.InputPurpose.TERMINAL.value]):
            if self._debug_level > 1:
                LOGGER.debug('Surrounding text is not supported. '
                             'No way to repopen preedit.')
            return False
        if self._debug_level > 1:
            LOGGER.debug(
                'self._surrounding_text_old=%r', self._surrounding_text_old)
        text_old = self._surrounding_text_old.text
        cursor_pos_old = self._surrounding_text_old.cursor_pos
        anchor_pos_old = self._surrounding_text_old.anchor_pos
        if not text_old:
            LOGGER.debug(
                'Old surrounding text is empty. Cannot reopen preedit.')
            return False
        if cursor_pos_old != anchor_pos_old:
            LOGGER.debug('cursor_pos_old=%s anchor_pos_old=%s differ.',
                         cursor_pos_old, anchor_pos_old)
            LOGGER.debug('Cannot reopen preedit.')
            return False
        self._surrounding_text.event.wait(timeout=0.1)
        if not self._surrounding_text.event.is_set():
            LOGGER.debug(
                'Surrounding text has not been set since last key event. '
                'Something is wrong with the timing. Do not try to reopen '
                'the preedit.')
            return False
        if self._debug_level > 1:
            LOGGER.debug('self._surrounding_text=%r', self._surrounding_text)
        text = self._surrounding_text.text
        cursor_pos = self._surrounding_text.cursor_pos
        anchor_pos = self._surrounding_text.anchor_pos
        if text == '':
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
                if self._debug_level > 1:
                    LOGGER.debug(
                        'No whitespace or end of line or buffer '
                        'to the right of cursor.')
                return False
            pattern = re.compile(r'(^|.*[\s]+)(?P<token>[\S]+)$')
            match = pattern.match(text[:cursor_pos])
            if not match:
                if self._debug_level > 1:
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
            self.update_preedit_text_with_mode(
                IBus.Text.new_from_string(''), 0, True,
                IBus.PreeditFocusMode.COMMIT)
            if (re.search(r'^[^:]*:[^:]*:WhatsApp', self._im_client)
                and len(token) == cursor_pos):
                # Workaround for WhatsApp in firefox (google-chrome
                # does not support surrounding text so we don't get
                # here anyway):
                #
                # If reaching a word in WhatsApp from the right
                # **and** the length of the token deleted via
                # surrounding text is equal to the cursor_pos then we
                # know that after deleting the surrounding text the
                # cursor is at the beginning of a line. If surrounding
                # text is deleted at the beginning of a line, WhatsApp
                # seems to sometimes enable a selection. When the
                # preedit is then reopened, it may appear like
                # selected text and behave strangely or even vanish
                # immediately.  See:
                # https://github.com/mike-fabian/ibus-typing-booster/issues/617
                # We try to cancel that selection here by sending
                # Control+c (copies the selection) followed by
                # Control+v (replaces the selection with its copy):
                LOGGER.debug(
                    'Apply WhatsApp workaround for reopening preedit '
                    'at the beginning of a line.')
                time.sleep(self._ibus_event_sleep_seconds)
                self._forward_generated_key_event(
                    IBus.KEY_c, keystate=IBus.ModifierType.CONTROL_MASK)
                self._forward_generated_key_event(
                    IBus.KEY_c, keystate=
                    IBus.ModifierType.CONTROL_MASK|IBus.ModifierType.RELEASE_MASK)
                self._forward_generated_key_event(
                    IBus.KEY_v, keystate=IBus.ModifierType.CONTROL_MASK)
                self._forward_generated_key_event(
                    IBus.KEY_v, keystate=
                    IBus.ModifierType.CONTROL_MASK|IBus.ModifierType.RELEASE_MASK)
                time.sleep(self._ibus_event_sleep_seconds)
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
                    LOGGER.debug('Unexpected cursor movement on Delete key, '
                                 'cannot reopen preedit.')
            pattern = re.compile(r'(^|.*[\s]+)$')
            match = pattern.match(text[:cursor_pos])
            if not match:
                if self._debug_level > 1:
                    LOGGER.debug(
                        'No whitespace or beginning of line or buffer '
                        'to the left of cursor.')
                return False
            pattern = re.compile(r'^(?P<token>[\S]+)($|[\s]+.*)')
            match = pattern.match(text[cursor_pos:])
            if not match:
                if self._debug_level > 1:
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
            self.update_preedit_text_with_mode(
                IBus.Text.new_from_string(''), 0, True,
                IBus.PreeditFocusMode.COMMIT)
            if (re.search(r'^[^:]*:[^:]*:WhatsApp', self._im_client)
                and not text[:cursor_pos].strip()):
                # Workaround for WhatsApp in firefox (google-chrome
                # does not support surrounding text so we don't get
                # here anyway):
                #
                # If reaching a word in WhatsApp from the left **and**
                # there is only whitespace in the surrounding text up
                # to the cursor_pos then it is possible that after
                # deleting the surrounding text the cursor is at the
                # beginning of a line. If surrounding text is deleted
                # at the beginning of a line, WhatsApp seems to
                # sometimes enable a selection. When the preedit is
                # then reopened, it may appear like selected text and
                # behave strangely or even vanish immediately.  See:
                # https://github.com/mike-fabian/ibus-typing-booster/issues/617
                # We try to cancel that selection here by sending
                # Control+c (copies the selection) followed by
                # Control+v (replaces the selection with its copy):
                LOGGER.debug(
                    'Apply WhatsApp workaround for reopening preedit '
                    'at the beginning of a line.')
                time.sleep(self._ibus_event_sleep_seconds)
                self._forward_generated_key_event(
                    IBus.KEY_c, keystate=IBus.ModifierType.CONTROL_MASK)
                self._forward_generated_key_event(
                    IBus.KEY_c, keystate=
                    IBus.ModifierType.CONTROL_MASK|IBus.ModifierType.RELEASE_MASK)
                self._forward_generated_key_event(
                    IBus.KEY_v, keystate=IBus.ModifierType.CONTROL_MASK)
                self._forward_generated_key_event(
                    IBus.KEY_v, keystate=
                    IBus.ModifierType.CONTROL_MASK|IBus.ModifierType.RELEASE_MASK)
                time.sleep(self._ibus_event_sleep_seconds)
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
        if (not self.has_surrounding_text
            or self._input_purpose in [itb_util.InputPurpose.TERMINAL.value]):
            # If getting the surrounding text is not supported, leave
            # the context as it is, i.e. rely on remembering what was
            # typed last.
            if self._debug_level > 1:
                LOGGER.debug('Surrounding text not supported.')
            return
        text = self._surrounding_text.text
        cursor_pos = self._surrounding_text.cursor_pos
        if self._debug_level > 1:
            LOGGER.debug('self._surrounding_text=%r', self._surrounding_text)
        if text == '':
            if self._debug_level > 1:
                LOGGER.debug('Surrounding text is empty, cannot get context.')
            return
        tokens = ([
            itb_util.strip_token(token)
            for token in itb_util.tokenize(text[:cursor_pos])])[-3:]
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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

    def set_prefer_commit(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to prefer commits over passing key events through

        :param mode: Whether to prefer commits over passing key events through
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if self._debug_level > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._prefer_commit:
            return
        self._prefer_commit = mode
        if update_gsettings:
            self._gsettings.set_value(
                'prefercommit',
                GLib.Variant.new_boolean(mode))

    def toggle_prefer_commit(
            self, update_gsettings: bool = True) -> None:
        '''Toggles whether to prefer commits over passing key events through

        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        self.set_prefer_commit(
            not self._prefer_commit, update_gsettings)

    def get_prefer_commit(self) -> bool:
        '''
        Returns whether commits are preferred over passing key events through
        '''
        return self._prefer_commit

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
        if self._debug_level > 1:
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
            and self._lookup_table.state == LookupTableState.COMPOSE_COMPLETIONS
            and self._lookup_table.is_cursor_visible()):
            # something is manually selected in the compose lookup table
            self._lookup_table.state = LookupTableState.NORMAL
            compose_result = self.get_string_from_lookup_table_cursor_pos()
            self._candidates = []
            self._lookup_table.clear()
            self._lookup_table.set_cursor_visible(False)
            self._update_lookup_table_and_aux()
            self._typed_compose_sequence = []
            self._insert_string_at_cursor(list(compose_result))
            self._update_transliterated_strings()
        preedit_ime = self._current_imes[0]
        input_phrase = self._transliterated_strings[preedit_ime]
        input_phrase = self._case_modes[
            self._current_case_mode]['function'](input_phrase)
        if (self._lookup_table.get_number_of_candidates()
            and self._lookup_table.is_cursor_visible()):
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
            if self._debug_level > 0:
                LOGGER.error('commit string unexpectedly empty.')
            return
        # Remember whether a candidate is selected and where the
        # caret is now because after self._commit_string() this
        # information is gone:
        candidate_was_selected = False
        if self._lookup_table.is_cursor_visible():
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
        if self._debug_level > 1:
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

    def set_input_mode_true_symbol(
            self, symbol: str, update_gsettings: bool = True) ->  None:
        '''Sets the symbol used for input mode true

        :param symbol: Which symbol to  use for input mode true
        '''
        if self._debug_level > 1:
            LOGGER.debug('(%s)', symbol)
        if symbol == self.get_input_mode_true_symbol():
            return
        self.input_mode_properties['InputMode.On']['symbol'] = symbol
        if self._prop_dict and self.input_mode_menu:
            self._init_or_update_property_menu(
                self.input_mode_menu, 1)
        itb_util.ibus_write_cache()
        if update_gsettings:
            self._gsettings.set_value(
                'inputmodetruesymbol',
                GLib.Variant.new_boolean(symbol))

    def get_input_mode_true_symbol(self) -> str:
        '''Returns the current value of the symbol used for input mode true'''
        return str(self.input_mode_properties['InputMode.On']['symbol'])

    def set_input_mode_false_symbol(
            self, symbol: str, update_gsettings: bool = True) ->  None:
        '''Sets the symbol used for input mode false

        :param symbol: Which symbol to  use for input mode false
        '''
        if self._debug_level > 1:
            LOGGER.debug('(%s)', symbol)
        if symbol == self.get_input_mode_false_symbol():
            return
        self.input_mode_properties['InputMode.Off']['symbol'] = symbol
        if self._prop_dict and self.input_mode_menu:
            self._init_or_update_property_menu(
                self.input_mode_menu, 0)
        if update_gsettings:
            self._gsettings.set_value(
                'inputmodefalsesymbol',
                GLib.Variant.new_boolean(symbol))

    def get_input_mode_false_symbol(self) -> str:
        '''Returns the current value of the symbol used for input mode false'''
        return str(self.input_mode_properties['InputMode.Off']['symbol'])

    def set_word_prediction_mode(
            self, mode: bool, update_gsettings: bool = True) -> None:
        '''Sets the word prediction mode

        :param mode: Whether to switch word prediction on or off
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if self._debug_level > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._word_predictions:
            return
        self._word_predictions = mode
        self._update_ui()
        if update_gsettings:
            self._gsettings.set_value(
                'wordpredictions',
                GLib.Variant.new_boolean(mode))

    def toggle_word_prediction_mode(
            self, update_gsettings: bool = True) -> None:
        '''Toggles whether word predictions are shown or not

        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        self.set_word_prediction_mode(
            not self._word_predictions, update_gsettings)

    def get_word_prediction_mode(self) -> bool:
        '''Returns the current value of the word prediction mode'''
        return self._word_predictions

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
        if self._debug_level > 1:
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
                languages=self._dictionary_names,
                unicode_data_all=self._unicode_data_all,
                variation_selector=self._emoji_style)
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

    def set_unicode_data_all_mode(
            self, mode: bool, update_gsettings: bool = True) -> None:
        '''Sets the mode whether to load all Unicode characters for
        Unicode symbol and emoji prediction

        :param mode: Whether to load all Unicode characters
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.

        '''
        if self._debug_level > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._unicode_data_all:
            return
        self._unicode_data_all = mode
        if self.emoji_matcher:
            if self._debug_level > 1:
                LOGGER.debug('Updating EmojiMatcher')
            self.emoji_matcher = itb_emoji.EmojiMatcher(
                languages=self._dictionary_names,
                unicode_data_all=self._unicode_data_all,
                variation_selector=self._emoji_style)
        self._update_ui()
        if update_gsettings:
            self._gsettings.set_value(
                'unicodedataall',
                GLib.Variant.new_boolean(mode))

    def toggle_unicode_data_all_mode(
            self, update_gsettings: bool = True) -> None:
        '''Toggles whether all Unicode characters are loaded for
        Unicode symbol and emoji prediction.

        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        self.set_unicode_data_all_mode(
            not self._unicode_data_all, update_gsettings)

    def get_unicode_data_all_mode(self) -> bool:
        '''Returns the current value of the mode whether to load all
        Unicode characters for Unicode symbol and emoji prediction
        '''
        return self._unicode_data_all

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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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

    def set_emoji_style(
            self,
            style: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the emoji style

        :param style: 'emoji' uses colorful emoji (emoji style).
                      'text' uses monochrome emoji (text style).
                      Any other value uses unqualified emoji sequences.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.

        '''
        if self._debug_level > 1:
            LOGGER.debug(
                '(%r, update_gsettings = %s)',
                style, update_gsettings)
        if style == self._emoji_style:
            return
        self._emoji_style = style
        if self.emoji_matcher:
            if self._debug_level > 1:
                LOGGER.debug('Updating EmojiMatcher')
            self.emoji_matcher.set_variation_selector(
                self._emoji_style)
        if self._lookup_table.state == LookupTableState.RELATED_CANDIDATES:
            # If there is a lookup table showing related candidates
            # it might show Emoji and needs to be regenerated to
            # display the Emoji in the new style:
            self._lookup_related_candidates(
                self._lookup_table.related_candidates_phrase)
        elif self._lookup_table.state == LookupTableState.NORMAL:
            # It there is a “normal” lookup table, update to UI to regenerated
            # it to display the Emoji in the new style:
            self._update_ui()
        if update_gsettings:
            self._gsettings.set_value(
                'emojistyle',
                GLib.Variant.new_string(style))

    def toggle_emoji_style(
            self, update_gsettings: bool = True) -> None:
        '''Toggles through the values of the emoji style

        Does not toggle through all 3 styles on purpose, toggles only
        between 'emoji' and 'text'. If any other style is set, it toggles to 'emoji'.

        It is possible to set 'No style' in the setup tool to get
        unqualified emoji sequences, but that is useful only in very
        rare circumstances. If that is desired, use the setup tool.
        This command toggles only between 'emoji' and 'text', I found
        that toggling through the 3rd state as well was more confusing
        then helpful.
        '''
        next_style = {'emoji': 'text', 'text': 'emoji'}
        self.set_emoji_style(
            next_style.get(self._emoji_style, 'emoji'),
            update_gsettings)

    def get_emoji_style(self) -> str:
        '''Returns the current emoji style'''
        return self._emoji_style

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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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

    def set_color_m17n_preedit(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to use color for the m17n preedit

        :param mode: Whether to use color for the m17n preedit
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if self._debug_level > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._color_m17n_preedit:
            return
        self._color_m17n_preedit = mode
        if update_gsettings:
            self._gsettings.set_value(
                'colorm17npreedit',
                GLib.Variant.new_boolean(mode))

    def get_color_m17n_preedit(self) -> bool:
        '''Returns the current value of the “color m17n preedit” mode'''
        return self._color_m17n_preedit

    def set_color_m17n_preedit_string(
            self,
            color_string: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the color for the m17n preedit

        :param color_string: The color for the m17n preedit
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
        if self._debug_level > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', color_string, update_gsettings)
        if color_string == self._color_m17n_preedit_string:
            return
        self._color_m17n_preedit_string = color_string
        self._color_m17n_preedit_argb = itb_util.color_string_to_argb(
            self._color_m17n_preedit_string)
        if update_gsettings:
            self._gsettings.set_value(
                'colorm17npreeditstring',
                GLib.Variant.new_string(color_string))

    def get_color_m17n_preedit_string(self) -> str:
        '''Returns the current value of the “color m17n preedit” string'''
        return self._color_m17n_preedit_string

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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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

    def set_ai_chat_enable(
            self,
            mode: Union[bool, Any],
            update_gsettings: bool = True) -> None:
        '''Sets whether to enable AI chat or not

        :param mode: Whether to enable AI chat or not
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if self._debug_level > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._ai_chat_enable:
            return
        self._ai_chat_enable = mode
        if update_gsettings:
            self._gsettings.set_value(
                'aichatenable',
                GLib.Variant.new_boolean(mode))

    def get_ai_chat_enable(self) -> bool:
        '''Returns the current value of the flag whether
        to enable AI chat or not
        '''
        return self._ai_chat_enable

    def set_ai_system_message(
            self,
            ai_system_message: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the system message to start AI chats with

        :param ai_system_message: The system message to start AI chats with
        :param update_gsettings:  Whether to write the change to Gsettings.
                                  Set this to False if this method is
                                  called because the Gsettings key changed
                                  to avoid endless loops when the Gsettings
                                  key is changed twice in a short time.
        '''
        if self._debug_level > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', ai_system_message, update_gsettings)
        if ai_system_message == self._ai_system_message:
            return
        self._ai_system_message = ai_system_message
        if update_gsettings:
            self._gsettings.set_value(
                'aisystemmessage',
                GLib.Variant.new_string(ai_system_message))

    def get_ai_system_message(self) -> str:
        '''Returns the current system message to start AI chats with'''
        return self._ai_system_message

    def set_ollama_model(
            self,
            ollama_model: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the model to use for ollama

        :param ollama_model:     The model to use for ollama
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if self._debug_level > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', ollama_model, update_gsettings)
        if ollama_model == self._ollama_model:
            return
        self._ollama_model = ollama_model
        if update_gsettings:
            self._gsettings.set_value(
                'ollamamodel',
                GLib.Variant.new_string(ollama_model))

    def get_ollama_model(self) -> str:
        '''Returns the current value of the ollama model'''
        return self._ollama_model

    def set_ollama_max_context(
            self,
            max_context: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the maximum number of ollama messages to keep as context
        when continuing a chat

        :param max_context:      Maximum number of messages to keep as context.
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.debug(
            '(%s, update_gsettings = %s)', max_context, update_gsettings)
        if max_context == self._ollama_max_context:
            return
        self._ollama_max_context = max_context
        if update_gsettings:
            self._gsettings.set_value(
                'ollamamaxcontext',
                GLib.Variant.new_uint32(max_context))

    def get_ollama_max_context(self) -> int:
        '''Returns the maximum number of ollama messages to keep as context'''
        return self._ollama_max_context

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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', debug_level, update_gsettings)
        if debug_level == self._debug_level:
            return
        if 0 <= debug_level <= 255:
            self._debug_level = debug_level
            self._clear_input_and_update_ui()
            if update_gsettings:
                self._gsettings.set_value(
                    'debuglevel',
                    GLib.Variant.new_int32(debug_level))

    def get_debug_level(self) -> int:
        '''Returns the current debug level'''
        return self._debug_level

    def set_candidates_delay_milliseconds(
            self,
            milliseconds: Union[int, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the delay of the candidates in milliseconds

        :param milliseconds:     delay of the candidates in milliseconds
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        LOGGER.debug(
            '(%s, update_gsettings = %s)', milliseconds, update_gsettings)
        if milliseconds == self._candidates_delay_milliseconds:
            return
        self._candidates_delay_milliseconds = milliseconds
        if update_gsettings:
            self._gsettings.set_value(
                'candidatesdelaymilliseconds',
                GLib.Variant.new_uint32(self._candidates_delay_milliseconds))

    def get_candidates_delay_milliseconds(self) -> int:
        '''Returns the current value of the candidates delay in milliseconds'''
        return self._candidates_delay_milliseconds

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

    def set_use_ibus_keymap(
            self, mode: bool, update_gsettings: bool = True) -> None:
        '''Sets whether the use of an IBus keymap is forced

        :param mode: True if the use of an IBus keymap is forced, False if not
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if self._debug_level > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', mode, update_gsettings)
        if mode == self._use_ibus_keymap:
            return
        self._use_ibus_keymap = mode
        if update_gsettings:
            self._gsettings.set_value(
                'useibuskeymap',
                GLib.Variant.new_boolean(mode))

    @staticmethod
    def new_ibus_keymap(keymap: str = 'in') -> Optional[IBus.Keymap]:
        '''Construct a new IBus.Keymap object and store it in
        self._ibus_keymap_object
        '''
        if keymap not in itb_util.AVAILABLE_IBUS_KEYMAPS:
            LOGGER.warning(
                'keymap %s not in itb_util.AVAILABLE_IBUS_KEYMAPS=%s',
                keymap, repr(itb_util.AVAILABLE_IBUS_KEYMAPS))
        # Try the standard constructor (works on Fedora, fails on Alpine)
        try:
            return IBus.Keymap(keymap)
        except (TypeError, AttributeError) as error:
            LOGGER.warning(
                'IBus.Keymap("%s") failed: %s: %s. '
                'Falling back to IBus.Keymap.new("%s").',
                keymap, error.__class__.__name__, error, keymap)
        # Always deprecated, but necessary for Alpine Linux
        try:
            return IBus.Keymap.new(keymap)
        except (TypeError, AttributeError) as error:
            LOGGER.exception(
                'Exception in IBus.Keymap.new("%s"): %s: %s',
                keymap, error.__class__.__name__, error)
            LOGGER.error('Returning None')
            return None

    def set_ibus_keymap(
            self,
            keymap: Union[str, Any],
            update_gsettings: bool = True) -> None:
        '''Sets the  IBus keymap to use if the use of an IBus keymap is forced

        :param keymap: The IBus keymap to use
        :param update_gsettings: Whether to write the change to Gsettings.
                                 Set this to False if this method is
                                 called because the Gsettings key changed
                                 to avoid endless loops when the Gsettings
                                 key is changed twice in a short time.
        '''
        if self._debug_level > 1:
            LOGGER.debug(
                '(%s, update_gsettings = %s)', keymap, update_gsettings)
        if keymap == self._ibus_keymap:
            return
        self._ibus_keymap = keymap
        self._ibus_keymap_object = self.__class__.new_ibus_keymap(keymap)
        if update_gsettings:
            self._gsettings.set_value(
                'ibuskeymap',
                GLib.Variant.new_string(keymap))

    def get_use_ibus_keymap(self) -> bool:
        '''Returns whether the use of an IBus keymap is forced'''
        return self._use_ibus_keymap

    def get_ibus_keymap(self) -> str:
        '''Returns the name of the IBus keymap to use if the use of an
        IBus keymap is forced
        '''
        return self._ibus_keymap

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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
            LOGGER.debug(
                'index = %s button = %s state = %s\n', index, button, state)
        if not self._set_lookup_table_cursor_pos_in_current_page(index):
            return
        self._lookup_table.set_cursor_visible(True)

        if self._lookup_table.state == LookupTableState.COMPOSE_COMPLETIONS:
            if button == 1:
                phrase = self.get_string_from_lookup_table_cursor_pos()
                self._lookup_table.state = LookupTableState.NORMAL
                self._candidates = []
                self._lookup_table.clear()
                self._lookup_table.set_cursor_visible(False)
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
                if self._add_space_on_commit or self.has_osk:
                    self._clear_input()
                    self._trigger_surrounding_text_update()
                    # Tiny delay to give the surrounding text a chance
                    # to update:
                    GLib.timeout_add(5, self._update_ui_empty_input_try_completion)
                else:
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
        self.update_auxiliary_text(
            IBus.Text.new_from_string(
                auxiliary_text_label + '⚠️' + error_message), True)
        time.sleep(2)
        self._update_ui()

    def _speech_recognition(self) -> None:
        '''
        Listen to microphone, convert to text using Google speech-to-text
        and insert converted text.
        '''
        if self._debug_level:
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

        config = speech_types.RecognitionConfig(
            encoding=speech_enums.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=itb_util.AUDIO_RATE,
            language_code=language_code)
        streaming_config = speech_types.StreamingRecognitionConfig(
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
        self.update_auxiliary_text(
            IBus.Text.new_from_string(auxiliary_text_label), True)

        transcript = ''
        with itb_util.MicrophoneStream(
                itb_util.AUDIO_RATE, itb_util.AUDIO_CHUNK) as stream:
            audio_generator = stream.generator()
            requests = (speech_types.StreamingRecognizeRequest(audio_content=content)
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
                    if self._debug_level > 1:
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
                    self.update_auxiliary_text(
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
            if (not self.has_surrounding_text
                or
                self._input_purpose in [itb_util.InputPurpose.TERMINAL.value]):
                transcript = transcript[0].upper() + transcript[1:]
            else:
                text = self._surrounding_text.text
                cursor_pos = self._surrounding_text.cursor_pos
                text_left = text[:cursor_pos].strip()
                if self._debug_level > 1:
                    LOGGER.debug(
                        'self._surrounding_text=%r', self._surrounding_text)
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
        if (self._lookup_table.state in (
                LookupTableState.M17N_CANDIDATES,
                LookupTableState.COMPOSE_COMPLETIONS,
                LookupTableState.SELECTION_INFO,
                LookupTableState.RELATED_CANDIDATES)):
            return False
        self._case_mode_change(mode='next')
        self._update_lookup_table_and_aux()
        return True

    def _command_previous_case_mode(self) -> bool:
        '''Handle hotkey for the command “next_case_mode”

        :return: True if the key was completely handled, False if not.
        '''
        if (self._lookup_table.state in (
                LookupTableState.M17N_CANDIDATES,
                LookupTableState.COMPOSE_COMPLETIONS,
                LookupTableState.SELECTION_INFO,
                LookupTableState.RELATED_CANDIDATES)):
            return False
        self._case_mode_change(mode='previous')
        self._update_lookup_table_and_aux()
        return True

    def _command_cancel(self) -> bool:
        '''Handle hotkey for the command “cancel”

        :return: True if the key was completely handled, False if not.
        '''
        if self._ollama_chat_query_thread:
            self._ollama_chat_query_cancel(commit_selection=True)
            return True
        if (self.is_empty()
            and not self._typed_compose_sequence
            and self._lookup_table.state != LookupTableState.SELECTION_INFO):
            if (self._lookup_table.get_number_of_candidates()
                or self._temporary_word_predictions
                or self._temporary_emoji_predictions):
                # There might be candidates even if the input
                # is empty if self._min_char_complete == 0.
                # If that is the case, cancel these candidates.
                # If temporary predictions are enabled, disable them.
                # If anything was done, return True. If not, return False
                # because then there is nothing to cancel and the
                # key which triggered the cancel command should be
                # passed through.
                self._clear_input_and_update_ui()
                return True
            return False
        if self._typed_compose_sequence:
            if self._lookup_table.state == LookupTableState.COMPOSE_COMPLETIONS:
                if self._lookup_table.is_cursor_visible():
                    # A candidate is selected in the lookup table.
                    # Deselect it and show the first page of the candidate
                    # list:
                    self._lookup_table.set_cursor_visible(False)
                    self._lookup_table.set_cursor_pos(0)
                    self._update_lookup_table_and_aux()
                    return True
                self._lookup_table.state = LookupTableState.NORMAL
                self._lookup_table.clear()
                self._lookup_table.set_cursor_visible(False)
                self._update_lookup_table_and_aux()
                self._update_preedit()
                self._candidates = []
                return True
            if self._debug_level > 1:
                LOGGER.debug('Compose sequence cancelled.')
            self._typed_compose_sequence = []
            self._update_transliterated_strings()
            if self.get_input_mode():
                self._update_ui()
            else:
                self._update_preedit()
            return True
        if (self._m17n_trans_parts.candidates
            and self._lookup_table.state == LookupTableState.M17N_CANDIDATES):
            if self._lookup_table.is_cursor_visible():
                # A candidate is selected in the lookup table.
                # Deselect it and show the first page of the candidate
                # list:
                self._lookup_table.set_cursor_visible(False)
                self._lookup_table.set_cursor_pos(0)
                self._update_lookup_table_and_aux()
                return True
            if self._debug_level > 1:
                LOGGER.debug('Cancel m17n candidates lookup table')
            self._lookup_table.state = LookupTableState.NORMAL
            if ((self._tab_enable or self._min_char_complete > 1)
                and self._lookup_table.enabled_by_tab):
                self._lookup_table.enabled_by_tab = False
            if self._current_imes[0] == 'ja-anthy':
                # This should close the m17n lookup table and go
                # back to kana in the preedit:
                typed_string_up_to_cursor = (
                    self._typed_string[:self._typed_string_cursor])
                if (typed_string_up_to_cursor[
                        -len(itb_util.ANTHY_HENKAN_WIDE):]
                    == itb_util.ANTHY_HENKAN_WIDE):
                    if self._debug_level > 1:
                        LOGGER.debug(
                            'ja-anthy: removing itb_util.ANTHY_HENKAN_WIDE')
                    typed_string_up_to_cursor = typed_string_up_to_cursor[
                        :-len(itb_util.ANTHY_HENKAN_WIDE)]
                    self._typed_string = (
                        typed_string_up_to_cursor
                        + self._typed_string[self._typed_string_cursor:])
                    self._typed_string_cursor = len(typed_string_up_to_cursor)
                self._remove_character_before_cursor()
            else:
                # For all other input methods, cancel the whole
                # part of the preedit which produces the  current
                # m17n candidates:
                self._typed_string = (
                    self._typed_string[
                        :self._m17n_trans_parts.committed_index]
                    + self._typed_string[self._typed_string_cursor:])
                self._typed_string_cursor = (
                    self._m17n_trans_parts.committed_index)
                self._update_transliterated_strings()
            self._m17n_trans_parts = m17n_translit.TransliterationParts()
            self._update_ui()
            return True
        if self._lookup_table.is_cursor_visible():
            # A candidate is selected in the lookup table.
            # Deselect it and show the first page of the candidate
            # list:
            self._lookup_table.set_cursor_visible(False)
            self._lookup_table.set_cursor_pos(0)
            self._update_lookup_table_and_aux()
            return True
        if (self._lookup_table.state == LookupTableState.RELATED_CANDIDATES
            or self._current_case_mode != 'orig'):
            self._current_case_mode = 'orig'
            # Force an update to the original lookup table:
            self._update_ui()
            return True
        if ((self._tab_enable or self._min_char_complete > 1)
            and not self.has_osk
            and self._lookup_table.enabled_by_tab
            and self._lookup_table.get_number_of_candidates()):
            # If lookup table was enabled by typing Tab, and it is
            # not empty, close it again but keep the preëdit:
            self._lookup_table.enabled_by_tab = False
            self._lookup_table.clear()
            self._lookup_table.set_cursor_visible(False)
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
        if self.has_osk:
            LOGGER.info('enable_lookup command ignored because OSK is used.')
            return False

        if self._typed_compose_sequence:
            if self._lookup_table.state == LookupTableState.COMPOSE_COMPLETIONS:
                return False
            compose_completions = (
                self._compose_sequences.find_compose_completions(
                    self._typed_compose_sequence,
                    self._keyvals_to_keycodes.keyvals()))
            self._candidates = []
            self._lookup_table.clear()
            self._lookup_table.set_cursor_visible(False)
            for compose_completion in compose_completions:
                compose_result = self._compose_sequences.compose(
                    self._typed_compose_sequence + compose_completion)
                if compose_result:
                    self._candidates.append(
                        itb_util.PredictionCandidate(
                            phrase=compose_result,
                            user_freq=0,
                            comment='',
                            from_user_db=False,
                            spell_checking=False))
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
            self._lookup_table.enabled_by_tab = True
            self._lookup_table.state = LookupTableState.COMPOSE_COMPLETIONS
            self._update_lookup_table_and_aux()
            return True

        if (self._m17n_trans_parts.candidates
            and (self._m17n_trans_parts.candidate_show
                 or self._current_imes[0] == 'ja-anthy')):
            if (self._lookup_table.state == LookupTableState.M17N_CANDIDATES
                and self._current_imes[0] != 'ja-anthy'):
                # ja-anthy is an exeption here because when after
                # cancel, nothing is selected in the lookup table,
                # space should reselect the second candidate.
                return False
            if self._debug_level > 1:
                LOGGER.debug('Enabling m17n lookup table')
            if self._timeout_source_id:
                # If a timeout has been added for an update of
                # non-m17n candidates remove it, otherwise it might
                # destroy the m17n candidates lookup table when the
                # timeout occurs.
                GLib.source_remove(self._timeout_source_id)
                self._timeout_source_id = 0
            self._lookup_table.enabled_by_tab = True
            self._lookup_table.state = LookupTableState.M17N_CANDIDATES
            self._update_lookup_table_and_aux()
            # Select the first candidate automatically because most
            # Japanese and Chinese input methods behave like this and because
            # it saves one “next candidate” keystroke to get to the second
            # candidate which is the first one which makes a difference
            # to just continuing with the preedit:
            self._lookup_table.set_cursor_visible(True)
            self._is_candidate_auto_selected = True
            if self._current_imes[0] == 'ja-anthy':
                self._command_select_next_candidate()
                self._is_candidate_auto_selected = False
            self.update_lookup_table(self.get_lookup_table(), True)
            return True

        if ((self._tab_enable
             or (self._min_char_complete > 1
                 and
                 not self._lookup_table.enabled_by_min_char_complete))
            and not self._lookup_table.enabled_by_tab
            and not self.is_empty()):
            self._lookup_table.enabled_by_tab = True
            # update the ui here to see the effect immediately
            # do not wait for the next keypress:
            self._update_ui()
            return True
        return False

    def _command_selection_to_preedit(self) -> bool:
        '''Put the selection into preedit

        The return value should always be True. Even if putting the
        selection into preedit failed, the key which executed the
        command has been fully handled.  Makes no sense to use it as
        input just because getting the selection failed.
        '''
        GLib.idle_add(self._selection_to_preedit_get_selection)
        return True

    def _selection_to_preedit_get_selection(self) -> bool:
        '''Get the primary selection

        If possible use surrounding text, if that is not supported
        or fails, get it using the clipboard.

        :return: *Must* always return False to avoid that this callback
                 called by GLib.idle_add() runs again.
        '''
        selection_text = ''
        if self.has_surrounding_text:
            if not self._surrounding_text.event.is_set():
                if self._debug_level > 1:
                    LOGGER.warning(
                        'Surrounding text not set since last trigger.')
            if self._debug_level > 1:
                LOGGER.debug('self._surrounding_text=%r',
                             self._surrounding_text)
            text = self._surrounding_text.text
            cursor_pos = self._surrounding_text.cursor_pos
            anchor_pos = self._surrounding_text.anchor_pos
            selection_start = min(cursor_pos, anchor_pos)
            selection_end = max(cursor_pos, anchor_pos)
            selection_text = text[selection_start:selection_end]
            LOGGER.debug('selection_text=%r', selection_text)
        if selection_text != '':
            if cursor_pos > anchor_pos:
                self.delete_surrounding_text(
                    -len(selection_text), len(selection_text))
            else:
                self.delete_surrounding_text(0, len(selection_text))
            # https://github.com/mike-fabian/ibus-typing-booster/issues/474#issuecomment-1872148410
            # In very rare cases, like in the editor of
            # https://meta.stackexchange.com/ the
            # delete_surrounding_text() does not seem to remove
            # the text from the editor until something is
            # committed or the preedit is set to an empty string:
            self.update_preedit_text_with_mode(
                IBus.Text.new_from_string(''), 0, True,
                IBus.PreeditFocusMode.COMMIT)
            if (re.search(r'^[^:]*:[^:]*:WhatsApp', self._im_client)
                and not text[:cursor_pos].strip()):
                # Workaround for WhatsApp in firefox (google-chrome
                # does not support surrounding text so we don't get
                # here anyway):
                #
                # If reaching a word in WhatsApp from the left **and**
                # there is only whitespace in the surrounding text up
                # to the cursor_pos then it is possible that after
                # deleting the surrounding text the cursor is at the
                # beginning of a line. If surrounding text is deleted
                # at the beginning of a line, WhatsApp seems to
                # sometimes enable a selection. When the preedit is
                # then reopened, it may appear like selected text and
                # behave strangely or even vanish immediately.  See:
                # https://github.com/mike-fabian/ibus-typing-booster/issues/617
                # We try to cancel that selection here by sending
                # Control+c (copies the selection) followed by
                # Control+v (replaces the selection with its copy):
                LOGGER.debug(
                    'Apply WhatsApp workaround for reopening preedit '
                    'at the beginning of a line.')
                time.sleep(self._ibus_event_sleep_seconds)
                self._forward_generated_key_event(
                    IBus.KEY_c, keystate=IBus.ModifierType.CONTROL_MASK)
                self._forward_generated_key_event(
                    IBus.KEY_c, keystate=
                    IBus.ModifierType.CONTROL_MASK|IBus.ModifierType.RELEASE_MASK)
                self._forward_generated_key_event(
                    IBus.KEY_v, keystate=IBus.ModifierType.CONTROL_MASK)
                self._forward_generated_key_event(
                    IBus.KEY_v, keystate=
                    IBus.ModifierType.CONTROL_MASK|IBus.ModifierType.RELEASE_MASK)
                time.sleep(self._ibus_event_sleep_seconds)
            self._selection_to_preedit_open_preedit(selection_text)
            return False
        if self._debug_level > 1:
            LOGGER.debug('Surrounding text not supported or failed. '
                         'Fallback to primary selection.')
        selection_text = itb_util.get_primary_selection_text()
        LOGGER.debug('selection_text=%r', selection_text)
        # Calling self._selection_to_preedit_open_preedit() after
        # itb_util.get_primary_selection_text() needs GLib.idle_add(),
        # without that no lookup table pops up!
        if selection_text != '':
            GLib.idle_add(lambda:
                self._selection_to_preedit_open_preedit(selection_text))
        return False

    def _selection_to_preedit_open_preedit(self, selection_text: str) -> bool:
        '''Put selection text into preedit

        :return: *Must* always return False to avoid that this callback
                 called by GLib.idle_add() runs again.
        '''
        self.get_context()
        self._insert_string_at_cursor(list(selection_text))
        self._update_ui()
        return False

    def _command_show_selection_info(self) -> bool:
        '''Show info about the currently selected text

        The return value should always be True. Even if showing the
        selection failed, the key which executed the command has been
        fully handled.  Makes no sense to use it as input just because
        getting the selection failed.
        '''
        GLib.idle_add(self._show_selection_info_get_selection)
        return True

    def _show_selection_info_get_selection(self) -> bool:
        '''Get the primary selection

        If possible use surrounding text, if that is not supported
        or fails, get it using the clipboard.

        :return: *Must* always return False to avoid that this callback
                 called by GLib.idle_add() runs again.
        '''
        selection_text = ''
        text_left_of_cursor = ''
        if self.has_surrounding_text:
            if not self._surrounding_text.event.is_set():
                if self._debug_level > 1:
                    LOGGER.warning(
                        'Surrounding text not set since last trigger.')
            if self._debug_level > 1:
                LOGGER.debug('self._surrounding_text=%r',
                             self._surrounding_text)
            text = self._surrounding_text.text
            cursor_pos = self._surrounding_text.cursor_pos
            anchor_pos = self._surrounding_text.anchor_pos
            selection_start = min(cursor_pos, anchor_pos)
            selection_end = max(cursor_pos, anchor_pos)
            selection_text = text[selection_start:selection_end]
            # If a selection could be fetched from surrounding text use
            # it, if not use the surrounding text up to the cursor.
            text_left_of_cursor = text[:cursor_pos]
            if self._debug_level > 1:
                LOGGER.debug('selection_text=%r text_left_of_cursor=%r',
                             selection_text, text_left_of_cursor)
        if selection_text != '':
            GLib.idle_add(lambda:
                self._show_selection_info_show_candidates(
                selection_text, selection_text))
            return False
        if self._debug_level > 1:
            LOGGER.debug('Surrounding text not supported or failed. '
                         'Fallback to primary selection.')
        selection_text = itb_util.get_primary_selection_text()
        # `wl-paste -p` might have been used to get the primary
        # selection.  If `wl-paste` (with or without `-p`) is used, it
        # causes a focus out, a focus in to `self._im_client=fake`,
        # then a focus out and a focus in to where the focus
        # originally was.  This might close the candidate if it was
        # already shown or prevent it from appearing. So instead of
        # using GLib.idle_add use GLib.timeout_add to add a delay to
        # give the focus events time to happen before the candidate
        # list is shown:
        delay = 30 # milliseconds
        if selection_text != '':
            GLib.timeout_add(delay,
                lambda:
                self._show_selection_info_show_candidates(
                selection_text, selection_text))
            return False
        if text_left_of_cursor != '':
            GLib.timeout_add(delay,
                lambda:
                self._show_selection_info_show_candidates(
                '', text_left_of_cursor))
        return False

    def _show_selection_info_show_candidates(
            self, selection_text: str, text_to_analyze: str) -> bool:
        '''Show info about grapheme clusters in text_to_analyze

        :return: *Must* always return False to avoid that this callback
                 called by GLib.idle_add() runs again.
        '''
        if self._debug_level > 1:
            LOGGER.debug('selection_text=%r text_to_analyze=%r',
                         selection_text, text_to_analyze)
        if text_to_analyze == '':
            return False
        grapheme_clusters = list(text_to_analyze)
        if USING_REGEX:
            grapheme_clusters = re.findall(r'\X', text_to_analyze)
        # If a selection text was found, use all grapheme clusters in
        # that selection. If no selection was found, use only the
        # grapheme cluster directly to the left of the cursor.
        if selection_text == '':
            grapheme_clusters = grapheme_clusters[-1:]
        # Make sure we have an EmojiMatcher to be able to get
        # names for emoji:
        if (not self.emoji_matcher
            or self.emoji_matcher.get_languages() != self._dictionary_names):
            self.emoji_matcher = itb_emoji.EmojiMatcher(
                languages=self._dictionary_names,
                unicode_data_all=self._unicode_data_all,
                variation_selector=self._emoji_style)
        candidates = []
        code_point_list_phrase = ''
        full_breakdown_phrase = ''
        for cluster in grapheme_clusters:
            name = self.emoji_matcher.name(cluster)
            if len(cluster) == 1:
                phrase = f'\u00A0{cluster} U+{ord(cluster):04X} {name}'
                comment = phrase
                candidates.append(itb_util.PredictionCandidate(
                    phrase=selection_text + phrase, comment=comment))
                full_breakdown_phrase += phrase
                code_point_list_phrase += f' U+{ord(cluster):04X}'
                continue
            phrase = f'\u00A0{cluster}'
            if name:
                phrase += f' {name}'
            comment = phrase
            candidates.append(itb_util.PredictionCandidate(
                phrase=selection_text + phrase, comment=comment))
            for index, char in enumerate(cluster):
                name = self.emoji_matcher.name(char)
                phrase = f'\u00A0{char} U+{ord(char):04X}'
                if name:
                    phrase += f' {name}'
                if index < len(cluster) - 1:
                    comment = f' ├─{phrase}'
                else:
                    comment = f' └─{phrase}'
                candidates.append(itb_util.PredictionCandidate(
                    phrase=selection_text + phrase, comment=comment))
                full_breakdown_phrase += phrase
                code_point_list_phrase += f' U+{ord(char):04X}'
        if not candidates:
            if self._debug_level > 1:
                LOGGER.debug('No candidates found.')
            return False
        candidates.append(itb_util.PredictionCandidate(
            phrase=selection_text + code_point_list_phrase,
            comment=itb_util.elide_middle(
                code_point_list_phrase, max_length=40)))
        candidates.append(itb_util.PredictionCandidate(
            phrase=selection_text + full_breakdown_phrase,
            comment=itb_util.elide_middle(
                full_breakdown_phrase, max_length=40)))
        self._candidates = candidates
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)
        for candidate in self._candidates:
            self._append_candidate_to_lookup_table(
                phrase='', comment=candidate.comment)
        self._lookup_table.state = LookupTableState.SELECTION_INFO
        self._update_lookup_table_and_aux()
        return False

    def _command_ai_chat_start_new(self) -> bool:
        '''Start a new chat with an AI chat bot forgetting
        previous interactions adding the current selection as
        the initial input.

        The return value should always be True. Even something fails
        the key which executed the command has been fully handled and
        it makes no sense to use it as input.
        '''
        if not self._ai_chat_enable:
            return False
        self._ollama_messages = []
        self._ai_chat()
        return True

    def _command_ai_chat_continue(self) -> bool:
        '''Continue a chat with an AI chat bot adding the
        current selection as additional input.

        The return value should always be True. Even something fails
        the key which executed the command has been fully handled and
        it makes no sense to use it as input.
        '''
        if not self._ai_chat_enable:
            return False
        self._ai_chat()
        return True

    def _ai_chat(self) -> None:
        '''Continue or start a chat with an AI chat bot using
        the current selection, as additional input. If nothing
        is selected but surrounding text works, use the current
        line up to the cursor as additional input.
        '''
        if IMPORT_ITB_OLLAMA_ERROR:
            LOGGER.error(
                '“import itb_ollama” failed: %r', IMPORT_ITB_OLLAMA_ERROR)
            return
        if self._ollama_model == '':
            LOGGER.error('ollama model is not set.')
            return
        self._ollama_client = itb_ollama.ItbOllamaClient()
        if self._ollama_client.get_server() not in ('ollama', 'ramalama'):
            self._ollama_client = None
            LOGGER.error('Failed to connect to ollama server.')
            return
        if self._ollama_client.get_server() == 'ollama':
            self._ollama_server_label = '🦙🔵'
        if self._ollama_client.get_server() == 'ramalama':
            self._ollama_server_label = '🦙🔴'
        if not self._ollama_client.is_available(self._ollama_model):
            command = [sys.executable,
                       os.path.join(
                           os.path.dirname(__file__), 'ollama_pull.py'),
                       '--model', f'{self._ollama_model}']
            try:
                with open(os.devnull, 'wb') as devnull:
                    _ = subprocess.Popen( # pylint: disable=consider-using-with
                        command,
                        stdout=devnull,
                        stderr=devnull,
                        stdin=devnull,
                        # keep running, even when Typing Booster exits:
                        start_new_session=True)
            except Exception as error: # pylint: disable=broad-except
                LOGGER.exception(
                    'Exception when calling %r: %s', command, error)
            return
        GLib.idle_add(self._ai_chat_get_prompt)

    def _ai_chat_get_prompt(self) -> bool:
        '''Get the prompt from the primary selection or surrounding text

        Try these methods to get a prompt and use the first which works:

        - use surrounding text to get the selection
        - get the primary selection
        - get the current line up to the cursor from surrounding text

        :return: *Must* always return False to avoid that this callback
                 called by GLib.idle_add() runs again.
        '''
        selection_text = ''
        if self.has_surrounding_text:
            if self._debug_level > 1:
                LOGGER.debug('self._surrounding_text=%r',
                             self._surrounding_text)
            text = self._surrounding_text.text
            cursor_pos = self._surrounding_text.cursor_pos
            anchor_pos = self._surrounding_text.anchor_pos
            selection_start = min(cursor_pos, anchor_pos)
            selection_end = max(cursor_pos, anchor_pos)
            selection_text = text[selection_start:selection_end]
        if selection_text != '':
            # If there was a preedit, it has been committed by
            # selecting. Don’t commit anything here because it would
            # replace the selection. If the selection was done using
            # the mouse, a lookup table might still be shown. Any
            # remaining input is useless as well in that case, clear
            # it:
            self._clear_input()
            self.hide_lookup_table()
            GLib.idle_add(lambda:
                          self._ai_chat_query(
                              selection_text, selection_text))
            return False
        if self._debug_level > 1:
            LOGGER.debug(
                'Surrounding text not supported or '
                'failed to get a selection. '
                'Fallback to primary selection.')
        selection_text = itb_util.get_primary_selection_text()
        delay = 30 # milliseconds
        if selection_text != '':
            # If there was a preedit, it has been committed by
            # selecting. Don’t commit anything here because it would
            # replace the selection. If the selection was done using
            # the mouse, a lookup table might still be shown. Any
            # remaining input is useless as well in that case, clear
            # it:
            self._clear_input()
            self.hide_lookup_table()
            # `wl-paste -p` might have been used to get the primary
            # selection.  If `wl-paste` (with or without `-p`) is used, it
            # causes a focus out, a focus in to `self._im_client=fake`,
            # then a focus out and a focus in to where the focus
            # originally was.  This might close the candidate if it was
            # already shown or prevent it from appearing. So instead of
            # using GLib.idle_add use GLib.timeout_add to add a delay to
            # give the focus events time to happen before continuing.
            GLib.timeout_add(delay,
                             lambda:
                             self._ai_chat_query(
                                 selection_text, selection_text))
            return False
        if self._debug_level > 1:
            LOGGER.debug('Could not get a selection by any method.')
        if not self.has_surrounding_text:
            LOGGER.error(
                'Surrounding text not supported, giving up to get a prompt.')
            return False
        if self._debug_level > 1:
            LOGGER.debug('self._surrounding_text=%r', self._surrounding_text)
        prompt = self._surrounding_text.text[
            :self._surrounding_text.cursor_pos].split('\n')[-1]
        if self._current_preedit_text.text_str != '':
            if not prompt.endswith(self._current_preedit_text.text_str):
                prompt += self._current_preedit_text.text_str
            self._commit_current_input()
        GLib.timeout_add(delay, lambda: self._ai_chat_query('', prompt))
        return False

    def _ai_chat_query(self, selection_text: str, prompt: str) -> bool:
        '''Do something with AI on the selected text

        :return: *Must* always return False to avoid that this callback
                 called by GLib.idle_add() runs again.
        '''
        if self._debug_level > 1:
            LOGGER.debug('selection_text=%r prompt=%r', selection_text, prompt)
        if self._label_busy and self._label_busy_string.strip():
            # Show a label in the auxiliary text to indicate busy
            # state (by default an hourglass with moving sand):
            self.update_auxiliary_text(
                IBus.Text.new_from_string(
                    f'{self._label_busy_string.strip()}'
                    f'{self._ollama_server_label}'
                    f'[{len(self._ollama_messages)}] {self._ollama_model}\n'
                    f'{prompt}'), True)
        else:
            self.update_auxiliary_text(
                IBus.Text.new_from_string(''), False)
        if prompt == '':
            # Keep auxilary text for a second to show that getting a
            # prompt failed.
            time.sleep(1)
            self.update_auxiliary_text(IBus.Text.new_from_string(''), False)
            return False
        self._ollama_messages = (
            [] if self._ollama_max_context == 0
            else self._ollama_messages[-self._ollama_max_context * 2 :])
        self._ollama_selection_text = selection_text
        self._ollama_prompt = {'role': 'user', 'content': prompt}
        if self._ollama_stop_event:
            self._ollama_stop_event.clear()
        self._ollama_chat_query_thread = threading.Thread(
            daemon=True,
            target=self._ollama_chat_query_thread_function,
            args=([{'role': 'system', 'content': self._ai_system_message}]
                  + copy.deepcopy(self._ollama_messages)
                  + [self._ollama_prompt],
                  self._ollama_stop_event))
        self._ollama_chat_query_thread.start()
        return False

    def _ollama_chat_query_thread_function(
            self,
            messages: List[Dict[str, str]],
            stop_event: threading.Event) -> None:
        '''Thread to stream an ollama chat response'''
        if self._debug_level > 1:
            LOGGER.debug('Starting ollama chat stream %r', messages)
        if self._ollama_client is None:
            LOGGER.error('Ollama client not connected.')
            return
        self._ollama_response = ''
        try:
            stream = self._ollama_client.chat(
                self._ollama_model, messages=messages, stream=True)
            LOGGER.info('Ollama chat stream started.')
            for chunk in stream:
                if stop_event.is_set():
                    LOGGER.info('Ollama chat stream stopped by event.')
                    break
                if isinstance(chunk, dict) and 'choices' in chunk:
                    choices = chunk.get('choices')
                    if isinstance(choices, list) and len(choices) > 0:
                        choice0 = choices[0]
                        if isinstance(choice0, dict) and 'delta' in choice0:
                            delta = choice0['delta']
                            if isinstance(delta, dict) and 'content' in delta:
                                content = delta['content']
                                if content is not None:
                                    self._ollama_response += delta['content']
                GLib.idle_add(self._ollama_chat_query_update_response)
            self._ollama_response = self._ollama_response.strip()
            GLib.idle_add(self._ollama_chat_query_update_response)
            GLib.idle_add(self._ollama_chat_query_finalize_chat)
        except Exception as error: # pylint: disable=broad-except
            LOGGER.error('Error in ollama chat stream: %s', error)
            GLib.idle_add(self._ollama_chat_query_handle_error, str(error))

    def _ollama_chat_query_update_response(self) -> bool:
        '''Update ollama preedit text from main thread

        :return: *Must* always return False to avoid that this callback
                 called by GLib.idle_add() runs again.
        '''
        if self._ollama_response_style == 'preedit':
            attrs = IBus.AttrList()
            attrs.append(IBus.attr_underline_new(
                self._preedit_underline, 0, len(self._ollama_response)))
            ibus_text = IBus.Text.new_from_string(self._ollama_response)
            ibus_text.set_attributes(attrs)
            self.update_preedit_text_with_mode(
                ibus_text, len(self._ollama_response), True,
                IBus.PreeditFocusMode.CLEAR)
            return False
        if self._ollama_response_style == 'aux':
            aux_prefix = ''
            if self._label_busy and self._label_busy_string.strip():
                aux_prefix = (
                    f'{self._label_busy_string.strip()}'
                    f'{self._ollama_server_label}'
                    f'[{len(self._ollama_messages)}] {self._ollama_model}\n')
            aux_lines = '\n'.join([self._ollama_aux_wrapper.fill(line)
                 for line in self._ollama_response.splitlines()])
            max_aux_lines_stream = 10
            aux_lines_split = aux_lines.splitlines()
            if len(aux_lines_split) > max_aux_lines_stream:
                aux_lines = '\n'.join(
                    ['[…]'] + aux_lines_split[-max_aux_lines_stream:])
            self.update_auxiliary_text(
                IBus.Text.new_from_string(aux_prefix + aux_lines),
                True)
            return False
        LOGGER.error('Invalid self._ollama_response_style = %r',
                     self._ollama_response_style)
        return False

    def _ollama_chat_query_finalize_chat(self) -> bool:
        '''Finalize the chat from main thread

        :return: *Must* always return False to avoid that this callback
                 called by GLib.idle_add() runs again.
        '''
        if self._debug_level > 1:
            LOGGER.debug('self._ollama_response=%r', self._ollama_response)
        if self._ollama_response_style == 'preedit':
            self.update_auxiliary_text(IBus.Text.new_from_string(''), False)
            return False
        if self._ollama_response_style == 'aux':
            if self._ollama_model.startswith('deepseek'):
                self._ollama_response = re.sub(
                    r'<think>.*?</think>', '',
                    self._ollama_response, flags=re.DOTALL).strip()
            self.update_auxiliary_text(
                IBus.Text.new_from_string(
                    '\n'.join(
                        [self._ollama_aux_wrapper.fill(line)
                         for line in self._ollama_response.splitlines()])),
                True)
            return False
        LOGGER.error('Invalid self._ollama_response_style = %r',
                     self._ollama_response_style)
        return False

    def _ollama_chat_query_handle_error(self, error_message: str) -> bool:
        '''Handle chat errors from main thread

        :return: *Must* always return False to avoid that this callback
                 called by GLib.idle_add() runs again.
        '''
        LOGGER.error('Ollama chat error: %s', error_message)
        self._ollama_chat_query_error = True
        super().commit_text(IBus.Text.new_from_string(
            f'{self._ollama_selection_text}'))
        self.update_preedit_text_with_mode(
            IBus.Text.new_from_string(''), 0, True,
            IBus.PreeditFocusMode.COMMIT)
        self.update_auxiliary_text(IBus.Text.new_from_string(''), False)
        return False

    def _ollama_chat_query_cancel(
            self, commit_selection: bool = True) -> None:
        '''Cancel an ollama chat query, if it already finished,
        discard the result.
        '''
        LOGGER.info('Ollama chat cancel.')
        if not self._ollama_chat_query_thread:
            return
        if not self._ollama_stop_event:
            return
        if self._ollama_chat_query_thread.is_alive():
            self._ollama_stop_event.set()
            self._ollama_chat_query_thread.join()
            self._ollama_stop_event.clear()
        self._ollama_chat_query_thread = None
        if commit_selection:
            super().commit_text(IBus.Text.new_from_string(
                f'{self._ollama_selection_text}'))
        GLib.idle_add(self._ollama_chat_query_cancel_hide_ui)

    def _ollama_chat_query_cancel_hide_ui(self) -> bool:
        '''Hide the preedit text and the auxiliary text

        :return: *Must* always return False to avoid that this callback
                 called by GLib.idle_add() runs again.
        '''
        self.update_preedit_text_with_mode(
            IBus.Text.new_from_string(''), 0, True,
            IBus.PreeditFocusMode.COMMIT)
        self.update_auxiliary_text(IBus.Text.new_from_string(''), False)
        return False

    def _ollama_chat_query_process_key(self, key: itb_util.KeyEvent) -> bool:
        '''Process a key event while an ollama chat query is ongoing

        :return: True if the key event has been completely handled by
                 ibus-typing-booster and should not be passed through anymore.
                 False if the key event has not been handled completely
                 and is passed through.
        '''
        if not self._ollama_chat_query_thread: # Should never happen
            return False
        (match, return_value) = self._handle_hotkeys(key, commands=['cancel'])
        if match:
            return return_value
        if self._ollama_chat_query_thread.is_alive():
            # Ignore all keys except those cancelling until the query
            # is finished:
            return True
        if (key.val in (IBus.KEY_Shift_R,
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
            # Ignore all pure modifier keys
            return True
        self._ollama_chat_query_thread = None
        if self._ollama_chat_query_error:
            self._ollama_chat_query_error = False
            return True
        self._ollama_messages.append(self._ollama_prompt)
        self._ollama_messages.append(
            {"role": "assistant", "content": self._ollama_response})
        if key.control:
            super().commit_text(IBus.Text.new_from_string(
                f'{self._ollama_response}'))
        elif key.mod1: # Usually Alt
            super().commit_text(IBus.Text.new_from_string(
                f'{self._ollama_selection_text}'))
        else:
            super().commit_text(IBus.Text.new_from_string(
                f'{self._ollama_selection_text}\n{self._ollama_response}'))
        self.update_preedit_text_with_mode(
            IBus.Text.new_from_string(''), 0, True,
            IBus.PreeditFocusMode.COMMIT)
        self.update_auxiliary_text(IBus.Text.new_from_string(''), False)
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
        if ((self._m17n_trans_parts.candidates and
             not self._m17n_trans_parts.candidate_show
             and self._current_imes[0] != 'ja-anthy')
             or not self._lookup_table.get_number_of_candidates()):
            return False
        dummy = self._arrow_down()
        self._update_lookup_table_and_aux()
        return True

    def _command_select_previous_candidate(self) -> bool:
        '''Handle hotkey for the command “select_previous_candidate”

        :return: True if the key was completely handled, False if not.
        '''
        if ((self._m17n_trans_parts.candidates and
             not self._m17n_trans_parts.candidate_show
             and self._current_imes[0] != 'ja-anthy')
            or not self._lookup_table.get_number_of_candidates()):
            return False
        dummy = self._arrow_up()
        self._update_lookup_table_and_aux()
        return True

    def _command_lookup_table_page_down(self) -> bool:
        '''Handle hotkey for the command “lookup_table_page_down”

        :return: True if the key was completely handled, False if not.
        '''
        if ((self._m17n_trans_parts.candidates and
             not self._m17n_trans_parts.candidate_show
             and self._current_imes[0] != 'ja-anthy')
            or not self._lookup_table.get_number_of_candidates()):
            return False
        dummy = self._page_down()
        self._update_lookup_table_and_aux()
        return True

    def _command_lookup_table_page_up(self) -> bool:
        '''Handle hotkey for the command “lookup_table_page_up”

        :return: True if the key was completely handled, False if not.
        '''
        if ((self._m17n_trans_parts.candidates and
             not self._m17n_trans_parts.candidate_show
             and self._current_imes[0] != 'ja-anthy')
            or not self._lookup_table.get_number_of_candidates()):
            return False
        dummy = self._page_up()
        self._update_lookup_table_and_aux()
        return True

    def _command_toggle_emoji_prediction(self) -> bool:
        '''Handle hotkey for the command “toggle_emoji_prediction”

        :return: True if the key was completely handled, False if not.
        '''
        self.toggle_emoji_prediction_mode()
        return True

    def _command_toggle_emoji_style(self) -> bool:
        '''Handle hotkey for the command “toggle_emoji_style”

        :return: True if the key was completely handled, False if not.
        '''
        self.toggle_emoji_style()
        return True

    def _command_trigger_emoji_predictions(self) -> bool:
        '''Handle hotkey for the command “trigger_emoji_predictions”

        :return: True if the key was completely handled, False if not.
        '''
        self._temporary_emoji_predictions = True
        return True

    def _command_trigger_word_predictions(self) -> bool:
        '''Handle hotkey for the command “trigger_word_predictions”

        :return: True if the key was completely handled, False if not.
        '''
        self._temporary_word_predictions = True
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
            return self._lookup_related_candidates()
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
        if (not self.has_surrounding_text
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
        LOGGER.debug('self._commit_happened_after_focus_in=%r '
                     'self._surrounding_text=%r',
                     self._commit_happened_after_focus_in,
                     self._surrounding_text)
        if self._surrounding_text.text == '':
            if self._debug_level > 1:
                LOGGER.debug(
                    'Surrounding text empty. Cannot change line direction.')
            return
        text = self._surrounding_text.text
        cursor_pos = self._surrounding_text.cursor_pos
        anchor_pos = self._surrounding_text.anchor_pos
        if self._debug_level > 1:
            LOGGER.debug('self._surrounding_text=%r list(text)=%r',
                         self._surrounding_text, list(text))
        if cursor_pos != anchor_pos:
            LOGGER.debug('cursor_pos != anchor_pos, do nothing.')
            return
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
        if self._debug_level > 1:
            LOGGER.debug('KeyEvent object: %s\n', key)
        if self._debug_level > 5:
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
                if self._debug_level > 1:
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
        if self._debug_level > 0:
            LOGGER.info('key=%s', key)
        self._prev_key = key
        self._prev_key.time = time.time()
        self._prev_key.handled = True
        self._surrounding_text_old = self._surrounding_text.copy()
        self._trigger_surrounding_text_update()
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
        This has been fixed though at least when triggering a commit
        with space by inserting the space into the application by
        committing it as well instead of sending it to the application.
        I.e. when a space triggers a commit, neither `return False`
        nor `forward_key_event()` is used.

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
        if self._debug_level > 0:
            LOGGER.info('key=%s', key)
        self._prev_key = key
        self._prev_key.time = time.time()
        self._prev_key.handled = False
        self._surrounding_text_old = self._surrounding_text.copy()
        self._trigger_surrounding_text_update()
        if not key.code:
            LOGGER.warning(
                'key.code=0 is not a valid keycode. Probably caused by OSK.')
        # If it is possible to commit instead of forwarding a key event
        # or doing a “return False”, prefer the commit:
        if (self._prefer_commit
            and key.unicode
            and unicodedata.category(key.unicode) not in ('Cc',)
            and (key.val not in (
                IBus.KEY_Return, IBus.KEY_KP_Enter, IBus.KEY_ISO_Enter,
                IBus.KEY_BackSpace, IBus.KEY_Delete))
            and not key.state & IBus.ModifierType.RELEASE_MASK
            and not key.state & itb_util.KEYBINDING_STATE_MASK):
            if self._debug_level > 0:
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
        # forward_key_event() doesn’t work in Gtk4 and it doesn’t seem
        # to work in SDL2 applications like supertuxkart and
        # performous, see
        # https://github.com/mike-fabian/ibus-typing-booster/issues/580
        if (self._avoid_forward_key_event
            or self._im_client.startswith('gtk4-im')
            or self._im_client.startswith('SDL2_Application')
            or
            (self.client_capabilities & itb_util.Capabilite.SYNC_PROCESS_KEY)):
            if self._debug_level > 0:
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
            LOGGER.info('Forwarding key event')
            self.forward_key_event(key.val, key.code, key.state)
            return True
        if self._debug_level > 0:
            LOGGER.info('Returning False')
        return False

    def _forward_generated_key_event(self, keyval: int, keystate: int = 0) -> None:
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
            if self._debug_level > 0:
                LOGGER.debug(
                    'return without doing anything because '
                    'self._avoid_forward_key_event is True. '
                    'keyval=%s', keyval)
            return
        keycode = self._keyvals_to_keycodes.keycode(keyval)
        ibus_keycode = self._keyvals_to_keycodes.ibus_keycode(keyval)
        if self._debug_level > 0:
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

    def _handle_m17n_candidates(self, key: itb_util.KeyEvent) -> bool:
        if self._debug_level > 1:
            LOGGER.debug('KeyEvent object: %s', key)
        if self._typed_compose_sequence:
            if self._debug_level > 1:
                LOGGER.debug('Do not interfere with compose sequence')
            return False
        if key.state & IBus.ModifierType.RELEASE_MASK:
            if self._debug_level > 1:
                LOGGER.debug('Ignoring release event.')
            return False
        if (not self._m17n_trans_parts.candidates
            and not self._is_candidate_auto_selected
            and self._lookup_table.get_number_of_candidates()
            and self._lookup_table.is_cursor_visible()):
            if self._debug_level > 1:
                LOGGER.debug('Manual selection in lookup table. '
                             'Do not interfere with that.')
            return False
        if (not self._m17n_trans_parts.candidates
            and not key.msymbol):
            if self._debug_level > 1:
                LOGGER.debug('Empty key.msymbol cannot start '
                             'a m17n candidate sequence.')
            return False
        if (not self._m17n_trans_parts.candidates
            and key.val in self._commit_trigger_keys
            and not self._current_imes[0] in ('ja-anthy',)
            and key.val == IBus.KEY_space
            and key.msymbol == ' '):
            # I could make BackSpace, Delete, Left, and Right reopen
            # m17n candidates. But it seems a bit complicated and I
            # guess it is not very useful. Therefore, I don’t allow
            # these keys to reopen m17n candidates at the moment.
            if self._debug_level > 1:
                LOGGER.debug('Commit trigger keys usually cannot start '
                             'a m17n candidate sequence except the space '
                             'key for ja-anthy')
            return False
        if (self._m17n_trans_parts.candidates
            and key.val in
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
            # necessary, they should not be added to the m17n candidates
            # sequence because they usually modify the next key and
            # only the result of that modified next key press should
            # be added to the m17n candidates sequence.
            #
            # Ignoring the other modifiers seems optional ...
            if self._debug_level > 1:
                LOGGER.debug('Inside m17n candidates sequence, ignoring key %s',
                             IBus.keyval_name(key.val))
            return True
        if self._m17n_trans_parts.candidates:
            (match, return_value) = self._handle_hotkeys(
                    key, commands=['cancel',
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
                if self._debug_level > 1:
                    LOGGER.debug('hotkey matched %s %s', match, return_value)
                return return_value
        if (self._lookup_table.state == LookupTableState.M17N_CANDIDATES
            and self._lookup_table.is_cursor_visible()
            and not self._is_candidate_auto_selected
            and not key.val in (IBus.KEY_BackSpace,)):
            if self._debug_level > 1:
                LOGGER.debug('m17n candidate manually selected')
            if (self._current_imes[0] == 'ja-anthy'
                and key.val == IBus.KEY_space and key.msymbol == ' '):
                if self._debug_level > 1:
                    LOGGER.debug('ja-anthy: select next candidate')
                self._command_select_next_candidate()
                return True
            if self._debug_level > 1:
                LOGGER.debug('Candidate selected -> typed string')
            selected_candidate = self.get_string_from_lookup_table_cursor_pos()
            self._candidates = []
            self._lookup_table.clear()
            self._lookup_table.set_cursor_visible(False)
            self._update_lookup_table_and_aux()
            self._lookup_table.state = LookupTableState.NORMAL
            selected_candidate_length = len(selected_candidate)
            m17n_preedit_replacement = selected_candidate
            if (all(len(candidate) == selected_candidate_length
                   for candidate in self._m17n_trans_parts.candidates)):
                # If all candidates have the same length, replacing
                # only part of the m17n preedit is possible and
                # better. Otherwise replacing the whole m17n preedit
                # is probably best.
                m17n_preedit_replacement = (
                    self._m17n_trans_parts.preedit[
                        :self._m17n_trans_parts.cursor_pos][
                            :-len(selected_candidate)]
                    + selected_candidate
                    + self._m17n_trans_parts.preedit[
                        self._m17n_trans_parts.cursor_pos:])
            if self._debug_level > 1:
                LOGGER.debug(
                    'm17n_preedit_replacement=“%s” trans_parts=%s',
                    m17n_preedit_replacement,repr(self._m17n_trans_parts))
                LOGGER.debug(
                    'OLD: self._typed_string=%s, self._typed_string_cursor=%s',
                    self._typed_string, self._typed_string_cursor)
            if self._try_early_commit():
                if self._debug_level > 1:
                    LOGGER.debug(
                        'Early commit %r',
                        self._m17n_trans_parts.committed
                        + m17n_preedit_replacement)
                self._typed_string = (
                    self._typed_string[self._typed_string_cursor:])
                self._typed_string_cursor = 0
                super().commit_text(
                    IBus.Text.new_from_string(
                        self._m17n_trans_parts.committed
                        + m17n_preedit_replacement))
                # The next thing might be a commit of a space which
                # triggered this commit, expecially on wayland two
                # commits immediately after each other may cause
                # problems, unfortunately a sleep maybe be needed
                # otherwise this is racy, without the sleeps it works
                # unreliably.
                time.sleep(self._ibus_event_sleep_seconds)
            else:
                self._typed_string = (
                    self._typed_string[:self._m17n_trans_parts.committed_index]
                    + list(m17n_preedit_replacement)
                    + self._typed_string[self._typed_string_cursor:])
                self._typed_string_cursor = (
                    self._m17n_trans_parts.committed_index
                    + len(list(m17n_preedit_replacement)))
            if self._debug_level > 1:
                LOGGER.debug(
                    'NEW:self._typed_string=%s, self._typed_string_cursor=%s',
                    self._typed_string, self._typed_string_cursor)
            self._update_transliterated_strings()
            self._m17n_trans_parts = m17n_translit.TransliterationParts()
            if (self._current_imes[0].startswith('zh')
                and key.val == IBus.KEY_space and key.msymbol == ' '):
                if self._debug_level > 1:
                    LOGGER.debug(
                        'zh: manually selected m17n commit, avoid space')
                self._update_ui()
                return True
            if (self._current_imes[0] == 'ja-anthy'
                and key.val in
                (IBus.KEY_Return, IBus.KEY_KP_Enter, IBus.KEY_ISO_Enter)):
                if self._debug_level > 1:
                    LOGGER.debug(
                        'ja-anthy: manually selected m17n commit, avoid Return')
                self._update_ui()
                return True
            # The key which caused the selected candidate to be pasted
            # into self._typed_string could produce m17n candidates
            # again (Example: Type `a` with zh-py, select a candidate
            # with Tab, type `a` again).  Therefore,
            # self._handle_m17n_candidates(key) needs to be called
            # again:
            if self._debug_level > 1:
                LOGGER.debug('Manually selected m17n commit, try recursion')
            return self._handle_m17n_candidates(key)
        if (self._m17n_trans_parts.candidates
            and key.val in self._commit_trigger_keys
            and not (self._current_imes[0] in ('t-lsymbol',)
                     and self._typed_string[
                         :self._typed_string_cursor][-1:] == ['/'])
            and not key.val in (IBus.KEY_BackSpace,)):
            # There are m17n candidates but nothing is selected in
            # the lookup table or the lookup table is not shown at all
            # (because no key was pressed to enable a lookup table).
            #
            # The key might usually trigger a commit outside of m17n
            # candidate sequences.  For all these commit trigger keys
            # it seems a good idea to me to accept the current m17n
            # candidates preedit as the final result and continue,
            # passing the key through.
            #
            # BackSpace is an exception, it should **not** accept the
            # current m17n candidates preedit but continue to the
            # block where BackSpace removes the last msymbol from the
            # input.  For example when using zh-py.mim, the input
            # ['a'] produces啊 in the preedit and shows m17n
            # candidates for the pinyin 'a'.  The input ['a', 'i']
            # produces 爱 in the preedit and shows m17n candidates for
            # the pinyin 'ai'.  A BackSpace should go back to ['a']
            # and show pinyin candidates for 'a'.
            if self._debug_level > 1:
                LOGGER.debug('m17n candidates commit trigger key')
            if (self._current_imes[0] == 'ja-anthy'
                and key.val == IBus.KEY_space and key.msymbol == ' '):
                if self._debug_level > 1:
                    LOGGER.debug('ja-anthy: enable lookup')
                self._command_enable_lookup()
                return True
            phrase = self._m17n_trans_parts.preedit
            self._candidates = []
            self._lookup_table.clear()
            self._lookup_table.set_cursor_visible(False)
            self._update_lookup_table_and_aux()
            self._lookup_table.state = LookupTableState.NORMAL
            if self._debug_level > 1:
                LOGGER.debug('phrase=%s, trans_parts=%s',
                             phrase, repr(self._m17n_trans_parts))
                LOGGER.debug(
                    'OLD: self._typed_string=%s, self._typed_string_cursor=%s',
                    self._typed_string, self._typed_string_cursor)
            if self._try_early_commit():
                if self._debug_level > 1:
                    LOGGER.debug('Early commit %r',
                                self._m17n_trans_parts.committed + phrase)
                self._typed_string = (
                    self._typed_string[self._typed_string_cursor:])
                self._typed_string_cursor = 0
                super().commit_text(
                    IBus.Text.new_from_string(
                        self._m17n_trans_parts.committed + phrase))
                # The next thing might be a commit of a space which
                # triggered this commit, expecially on wayland two
                # commits immediately after each other may cause
                # problems, unfortunately a sleep maybe be needed
                # otherwise this is racy, without the sleeps it works
                # unreliably.
                time.sleep(self._ibus_event_sleep_seconds)
            else:
                self._typed_string = (
                    self._typed_string[:self._m17n_trans_parts.committed_index]
                    + list(phrase)
                    + self._typed_string[self._typed_string_cursor:])
                self._typed_string_cursor = (
                    self._m17n_trans_parts.committed_index
                    + len(phrase))
            if self._debug_level > 1:
                LOGGER.debug(
                    'NEW:self._typed_string=%s, self._typed_string_cursor=%s',
                    self._typed_string, self._typed_string_cursor)
            self._update_transliterated_strings()
            self._m17n_trans_parts = m17n_translit.TransliterationParts()
            if (self._current_imes[0].startswith('zh')
                and key.val == IBus.KEY_space and key.msymbol == ' '):
                # When using Chinese input methods with ibus-m17n, the
                # space key commits without appending a space. Mimic
                # that behaviour by using `return True`.
                if self._debug_level > 1:
                    LOGGER.debug(
                        'zh: commit key triggered m17n commit, avoid space')
                self._update_ui()
                return True
            if (self._current_imes[0] == 'ja-anthy'
                and key.val in
                (IBus.KEY_Return, IBus.KEY_KP_Enter, IBus.KEY_ISO_Enter)):
                if self._debug_level > 1:
                    LOGGER.debug(
                        'ja-anthy: commit key triggered m17n commit, avoid Return')
                self._update_ui()
                return True
            return False
        # Check now whether the first input method would show candidates
        # if key was processed at the cursor position:
        typed_string_up_to_cursor = (
            self._typed_string[:self._typed_string_cursor])
        if self._debug_level > 1:
            LOGGER.debug('typed_string_up_to_cursor=%s',
                         repr(typed_string_up_to_cursor))
        if self._current_imes[0] == 'ja-anthy':
            if (typed_string_up_to_cursor[-len(itb_util.ANTHY_HENKAN_WIDE):]
                == itb_util.ANTHY_HENKAN_WIDE):
                if self._debug_level > 1:
                    LOGGER.debug(
                        'ja-anthy: removing itb_util.ANTHY_HENKAN_WIDE')
                typed_string_up_to_cursor = typed_string_up_to_cursor[
                    :-len(itb_util.ANTHY_HENKAN_WIDE)]
                self._typed_string = (
                    typed_string_up_to_cursor
                    + self._typed_string[self._typed_string_cursor:])
                self._typed_string_cursor = len(typed_string_up_to_cursor)
                if key.val == IBus.KEY_space and key.msymbol == ' ':
                    # This should never happen because when ja-anthy
                    # already is in henkan mode, space selects the
                    # next candidate, see code further above.
                    if self._debug_level > 1:
                        LOGGER.debug('ja-anthy: continue henkan mode')
                    typed_string_up_to_cursor += itb_util.ANTHY_HENKAN_WIDE
                elif key.val in (IBus.KEY_BackSpace,):
                    if self._debug_level > 1:
                        LOGGER.debug('ja-anthy: BackSpace in henkan mode')
                    typed_string_up_to_cursor.pop()
                else:
                    if self._debug_level > 1:
                        LOGGER.debug('ja-anthy: other key in henkan mode')
                    typed_string_up_to_cursor.append(key.msymbol)
            elif key.val == IBus.KEY_space and key.msymbol == ' ':
                if self._debug_level > 1:
                    LOGGER.debug('ja-anthy: start henkan mode')
                    # Adding itb_util.ANTHY_HENKAN_WIDE is a crazy
                    # hack to force the henkan region to be as wide as
                    # possible.  When using ibus-m17n, it is possible
                    # to move the henkan region with `Left` or `Right`
                    # and to resize it with `S-Left` and `S-Right`. At
                    # the moment, I cannot see a way how to make that
                    # work in Typing Booster. By default the position
                    # and size of the henkan region seems to depend on
                    # previous history. Having inconsistent positions
                    # and sizes of the henkan region depending on what
                    # anthy did before is a show stopper if the henkan
                    # region cannot be changed. To get consistent
                    # results I try to make the henkan region
                    # encompass all of the current m17n candidate
                    # input.
                    #
                    # Actually it is no big problem that the henkan region
                    # cannot be changed in Typing Booster, as Typing Booster
                    # does not really commit m17n candidate results, it
                    # only commits them to the preedit where they one can
                    # then continue to edit the results. It feels a bit different
                    # but not necessarily bad. It seems have some advantages
                    # as well, overall it seems reasonably OK.
                typed_string_up_to_cursor += [' '] + itb_util.ANTHY_HENKAN_WIDE
            elif key.val in (IBus.KEY_BackSpace,):
                if self._debug_level > 1:
                    LOGGER.debug('ja-anthy: BackSpace in kana mode')
                typed_string_up_to_cursor.pop()
            else:
                if self._debug_level > 1:
                    LOGGER.debug('ja-anthy: other key in kana mode')
                typed_string_up_to_cursor.append(key.msymbol)
        elif not typed_string_up_to_cursor:
            typed_string_up_to_cursor.append(key.msymbol)
        elif key.val in (IBus.KEY_BackSpace,):
            typed_string_up_to_cursor.pop()
        else:
            typed_string_up_to_cursor.append(key.msymbol)
        transliterated_parts = self._transliterators[
             self._current_imes[0]].transliterate_parts(
                 typed_string_up_to_cursor, ascii_digits=self._ascii_digits)
        if self._debug_level > 1:
            LOGGER.debug('After processing key: '
                         'typed_string_up_to_cursor=%r '
                         '-> transliterated_parts=%r',
                         typed_string_up_to_cursor,
                         transliterated_parts)
        if self._try_early_commit():
            if self._debug_level > 1:
                LOGGER.debug('Maybe commit early.')
            if (transliterated_parts.candidates
                and transliterated_parts.committed
                and transliterated_parts.committed_index):
                if self._debug_level > 1:
                    LOGGER.debug('Commit %r early.',
                                 transliterated_parts.committed)
                typed_string_up_to_cursor = typed_string_up_to_cursor[
                    transliterated_parts.committed_index:]
                super().commit_text(
                    IBus.Text.new_from_string(
                        transliterated_parts.committed))
                transliterated_parts = self._transliterators[
                    self._current_imes[0]].transliterate_parts(
                        typed_string_up_to_cursor,
                        ascii_digits=self._ascii_digits)
            elif self._debug_level > 1:
                LOGGER.debug('Nothing to commit early.')
        if not transliterated_parts.candidates:
            if self._m17n_trans_parts.candidates:
                if self._debug_level > 1:
                    LOGGER.debug('Clear and hide m17n candidates lookup table')
                # Clearing the lookup table is necessary here!  If it
                # is not cleared, and a candidate happens to be
                # manually selected, a BackSpace key here trigger a
                # replacement of the whole preedit with that candidate
                # and then delete it by passing the Backspace.
                #
                # Example with t-lsymbol: Type `a/:)` + Tab to select
                # the second candidate 😃.  BackSpace would then cause
                # the whole predit including the leading `a` to be
                # replaced with 😃 which then gets deleted by the
                # BackSpace, leaving nothing.
                self._lookup_table.clear()
                self._lookup_table.set_cursor_visible(False)
                self.hide_lookup_table()
                self.update_auxiliary_text(
                    IBus.Text.new_from_string(''), False)
                self._lookup_table.enabled_by_tab = False
                self._lookup_table.state = LookupTableState.NORMAL
            self._m17n_trans_parts = m17n_translit.TransliterationParts()
            if (transliterated_parts.committed == ''
                and transliterated_parts.committed_index == 0
                and transliterated_parts.preedit == ''
                and transliterated_parts.cursor_pos == 0
                and not (key.unicode == 'Z'
                         and self._current_imes[0] in (
                             'ko-romaja',
                             'vi-han',
                             'vi-nomtelex',
                             'vi-nomvi',
                             'zh-cangjie',
                             'zh-quick',
                             'zh-tonepy',
                             'zh-zhuyin',
                             'zh-py'))):
                # The `Z` in input methods which include cjk-util.mim switches
                # to single-fullwidth-mode which affects only the next character.
                # It should not be removed here, it must still be there when the next
                # character is actually typed otherwise the Mnil finalizing each
                # transliteration in m17n_translit.Transliterator
                if self._debug_level > 1:
                    LOGGER.debug(
                        'Removing input which changed only m17n-lib state %r',
                        typed_string_up_to_cursor)
                self._typed_string = self._typed_string[self._typed_string_cursor:]
                self._typed_string_cursor = 0
                self._update_transliterated_strings()
                # If input up to the cursor produces not output at all
                # it must have changed only the internal m17n-lib
                # state For example `>>` for `zh-py` changes to
                # full-width ASCII mode but produces no output. This
                # should be removed from the input here (which is
                # directly after the very first transliteration pass
                # in the processing of the key) to avoid displaying
                # the keys which changed the mode after further
                # transliteration passes or changing mode again in
                # further transliteration passes if it is not a one
                # way state switch but a toogle.
                self._update_ui()
                return True
            if self._debug_level > 1:
                LOGGER.debug('No m17n candidates.')
            return False
        self._typed_string = (typed_string_up_to_cursor
                              + self._typed_string[self._typed_string_cursor:])
        self._typed_string_cursor = len(typed_string_up_to_cursor)
        self._update_transliterated_strings()
        self._m17n_trans_parts = transliterated_parts
        if self._debug_level > 1:
            LOGGER.debug('Filling m17n candidate lookup table.')
        self._lookup_table.state = LookupTableState.NORMAL
        self._candidates = []
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)
        self.hide_lookup_table()
        self.update_auxiliary_text(
            IBus.Text.new_from_string(''), False)
        for candidate in self._m17n_trans_parts.candidates:
            if candidate:
                prediction_candidate = itb_util.PredictionCandidate(
                    phrase=candidate,
                    user_freq=0,
                    comment='',
                    from_user_db=False,
                    spell_checking=False)
                self._candidates.append(prediction_candidate)
                self._append_candidate_to_lookup_table(
                    phrase=candidate, comment='')
        if not self._lookup_table.get_number_of_candidates():
            # ja-anthy sometimes produces empty candidates.  Which is
            # *very* weird! Also reproducible with ibus-m17n!  I added
            # a workaround for ja-anthy in m17n_translit.py, it n ow
            # tries to filter and fix such broken anthy output. So
            # this should never happen now. But who knows, maybe there
            # are more such problems. At least better catch the
            # problem of an unexpected empty candidate list here:
            LOGGER.debug(
                'All m17n candidates were empty. Should never happen.')
            self._lookup_table.clear()
            self._lookup_table.set_cursor_visible(False)
            self.hide_lookup_table()
            self.update_auxiliary_text(
                    IBus.Text.new_from_string(''), False)
            self._lookup_table.enabled_by_tab = False
            self._lookup_table.state = LookupTableState.NORMAL
            self._m17n_trans_parts = m17n_translit.TransliterationParts()
            return False
        if self._timeout_source_id:
            # If a timeout has been added for an update of
            # non-m17n candidates remove it, otherwise it might
            # destroy the m17n candidates lookup table when the
            # timeout occurs.
            GLib.source_remove(self._timeout_source_id)
            self._timeout_source_id = 0
        self._lookup_table.enabled_by_tab = False
        if self._tab_enable and not self.has_osk:
            if self._debug_level > 1:
                LOGGER.debug('Tab enable set, just update preedit')
            self._update_preedit()
            return True
        if self._m17n_trans_parts.candidate_show:
            if self._debug_level > 1:
                LOGGER.debug('Show m17n candidate lookup table')
            self._lookup_table.state = LookupTableState.M17N_CANDIDATES
            self._update_lookup_table_and_aux()
            # Select the first candidate automatically because most
            # Japanese and Chinese input methods behave like this and because
            # it saves one “next candidate” keystroke to get to the second
            # candidate which is the first one which makes a difference
            # to just continuing with the preedit:
            self._lookup_table.set_cursor_visible(True)
            self._is_candidate_auto_selected = True
            self.update_lookup_table(self.get_lookup_table(), True)
            return True
        if self._debug_level > 1:
            LOGGER.debug('m17n candidate lookup table exists but is hidden')
        if self._current_imes[0] in ('ja-anthy',):
            if self._debug_level > 1:
                LOGGER.debug(
                    'Just update preedit for %s', self._current_imes[0])
            self._update_preedit()
            return True
        # Standard lookup table works fine here for vi-tcvn, vi-telex,
        # vi-viqr, vi-vni, ... It does probably work well for **all**
        # input methods which sometimes or always use “candidate_show
        # == 0” **except** for ja-anthy.  Maybe it is posssible to
        # make this work for ja-anthy, but it might not even make any
        # sense for ja-anthy.
        if self._debug_level > 1:
            LOGGER.debug('Show standard lookup table instead')
        self._update_ui()
        return True

    def _handle_compose(self, key: itb_util.KeyEvent, add_to_preedit: bool = True) -> bool:
        '''Internal method to handle possible compose keys

        :return: True if the key event has been handled, else False
        '''
        if self._debug_level > 1:
            LOGGER.debug('KeyEvent object: %s', key)
        if self._m17n_trans_parts.candidates:
            if self._debug_level > 1:
                LOGGER.debug('Do not interfere with m17n candidates.')
            return False
        if key.state & IBus.ModifierType.RELEASE_MASK:
            if self._debug_level > 1:
                LOGGER.debug('Ignoring release event.')
            return False
        if (not self._typed_compose_sequence
            and not self._compose_sequences.is_start_key(key.val)):
            if self._debug_level > 1:
                LOGGER.debug(
                    'Not in a compose sequence and the key cannot '
                    'start a compose sequence either. '
                    'Key Event object: %s', key)
            return False
        if (self.is_empty()
            and not self._word_predictions
            and not self._temporary_word_predictions
            and not self._emoji_predictions
            and not self._temporary_emoji_predictions):
            # No predictions are possible and the compose result can
            # be immediately committed when the compose sequences
            # finishes.
            add_to_preedit = False
        if (not self._typed_compose_sequence
            and not self._m17n_trans_parts.candidates
            and not self._is_candidate_auto_selected
            and self._lookup_table.get_number_of_candidates()
            and self._lookup_table.is_cursor_visible()):
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
            if self._debug_level > 1:
                LOGGER.debug('Inside compose sequence, ignoring key %s',
                             IBus.keyval_name(key.val))
            return True
        ime = self.get_current_imes()[0]
        if key.val in (IBus.KEY_BackSpace,):
            self._typed_compose_sequence.pop()
        elif not self._input_mode or ime[:2] in ('ja', 'zh'):
            # https://github.com/mike-fabian/ibus-typing-booster/issues/760
            # https://github.com/mike-fabian/ibus-typing-booster/issues/654
            # If an input method transliterates a single character
            # into another single character, use the transliterated
            # result for compose. An example where this makes sense is
            # `hi-inscript2` and the following compose sequence from
            # /usr/share/X11/locale/en_US.UTF-8/Compose
            #
            # <Multi_key> <U093C> <U0930> : "ऱ" U0931 # DEVANAGARI LETTER RRA
            #
            # It is probably also useful for input methods like `fr-azerty`.
            #
            # But of course this is not needed when direct input is used.
            #
            # And it seems to make no sense for any of the
            # Chinese and Japanese input methods in m17n-db, there are no
            # compose sequences in /usr/share/X11/locale/en_US.UTF-8/Compose
            # which could be typed with any of the Chinese and Japanese input
            # methods. There are some sequences like
            #
            # <dead_voiced_sound> <kana_CHI>: "ヂ" U30C2 # KATAKANA LETTER DI
            #
            # but these are impossible to type with the Japanese input methods
            # in m17n-db.
            #
            # I am not sure about Korean (`ko-han2` and `ko-romaja`)
            # because /usr/share/X11/locale/en_US.UTF-8/Compose
            # contains for example
            #
            # <Multi_key> <U1107> <U110E> : "ᄨ" U1128 # HANGUL CHOSEONG PIEUP-CHIEUCH
            #
            # and ko-romaja contains 0x1107 and 0x110E so it might be possible
            # to produce such a compose sequence with ko-romaja.
            self._typed_compose_sequence.append(key.val)
        else:
            transliterated_msymbol = self._transliterators[
                ime].transliterate([key.msymbol],
                                   ascii_digits=self._ascii_digits)
            if (transliterated_msymbol != key.msymbol
                and len(transliterated_msymbol) == 1):
                new_keyval = IBus.unicode_to_keyval(transliterated_msymbol)
                if self._debug_level > 1:
                    LOGGER.debug(
                        'Using transliterated key for compose %s %s %s',
                        repr(transliterated_msymbol),
                        f'Unicode 0x{ord(transliterated_msymbol):x}',
                        f'new_keyval=0x{new_keyval:x}')
                self._typed_compose_sequence.append(new_keyval)
            else:
                self._typed_compose_sequence.append(key.val)
        if not self._typed_compose_sequence:
            if self._debug_level > 1:
                LOGGER.debug('Editing made the compose sequence empty.')
            self._lookup_table.state = LookupTableState.NORMAL
            self._update_transliterated_strings()
            self._update_ui()
            return True
        compose_result = self._compose_sequences.compose(
            self._typed_compose_sequence)
        if self._debug_level > 1:
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
        if (self._lookup_table.state == LookupTableState.COMPOSE_COMPLETIONS
            and self._lookup_table.is_cursor_visible()):
            # something is manually selected in the compose lookup table
            self._lookup_table.state = LookupTableState.NORMAL
            compose_result = self.get_string_from_lookup_table_cursor_pos()
            self._candidates = []
            self._lookup_table.clear()
            self._lookup_table.set_cursor_visible(False)
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
        self._lookup_table.state = LookupTableState.NORMAL
        self._candidates = []
        self._lookup_table.clear()
        self._lookup_table.set_cursor_visible(False)
        self.hide_lookup_table()
        self.update_auxiliary_text(
            IBus.Text.new_from_string(''), False)
        if not isinstance(compose_result, str):
            # compose sequence is unfinished
            self._update_transliterated_strings()
            self._update_preedit()
            return True
        if not compose_result:
            if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._current_preedit_text.text_str == '':
            if self._debug_level > 1:
                LOGGER.debug('Avoid clearing already empty preedit.')
            return True
        self.update_preedit_text_with_mode(
            IBus.Text.new_from_string(''), 0, False,
            IBus.PreeditFocusMode.COMMIT)
        return True

    def _translate_to_ibus_keymap(
            self, key: itb_util.KeyEvent) -> itb_util.KeyEvent:
        '''Translate key to the selected IBus keymap'''
        if self._ibus_keymap_object is None:
            return key
        state = self._translated_key_state
        if key.release:
            state |= IBus.ModifierType.RELEASE_MASK
        new_key = itb_util.KeyEvent(
            IBus.Keymap.lookup_keysym(
                self._ibus_keymap_object, key.code, state),
            key.code, state)
        new_key.translated = True
        if (key.name in ('ISO_Level3_Shift', 'Multi_key')
            or
            new_key.val == IBus.KEY_VoidSymbol
            or
            (new_key.val == key.val
             and
             new_key.state & itb_util.KEYBINDING_STATE_MASK
             == key.state & itb_util.KEYBINDING_STATE_MASK)):
            # Do not translate 'ISO_Level3_Shift' and 'Multi_key' if
            # these are already available in the original keyboard
            # layout, but not in the IBus keymap translated to.
            # Translating them just would take something useful away.
            # Also, on some desktops, 'ISO_Level3_Shift' can be set
            # independently of the currently selected keyboard layout
            # in the control centre of the desktop. For example in
            # Gnome one can set 'Alt_L', 'Alt_R', 'Super_L', 'Super_R'
            # 'Menu', or 'Control_R' to produce 'ISO_Level3_Shift'.
            # If 'ISO_Level3_Shift' is on any of these keys, one should
            # just leave it alone and never translate it away.
            # Similar for the 'Multi_key': None of the IBus keymaps
            # contains 'Multi_key', so translating 'Multi_key' would just
            # always take it away and destroy the Compose support.
            #
            # Do not translate keys either when the new value is
            # IBus.KEY_VoidSymbol, i.e. when they cannot be found in
            # the IBus keymap to translate to. Skipping the
            # translation for such keys keeps them around to
            # potentially do something useful.
            new_key = key
        # Peter Hutterer explained to me that the state masks are
        # updated immediately **after** pressing a modifier key. For
        # example when the press event of Control is checked with
        # `xev` or here in the state supplied by ibus, the state does
        # not have the bit IBus.ModifierType.CONTROL_MASK set (it is
        # still 0x0 if no other modifiers are pressed). But that bit
        # is relevant for the next key press. Therefore I keep track
        # of the modifiers bits in `self._translated_key_state` and
        # set them when modifiers keys are pressed and remove them
        # when modifier keys are released. Doing that I can apply the
        # correct state bits when translating the next key to an IBus
        # keymap.
        if new_key.name in ('Shift_L', 'Shift_R'):
            if new_key.release:
                self._translated_key_state &= ~IBus.ModifierType.SHIFT_MASK
            else:
                self._translated_key_state |= IBus.ModifierType.SHIFT_MASK
        if new_key.name in ('Control_L', 'Control_R'):
            if new_key.release:
                self._translated_key_state &= ~IBus.ModifierType.CONTROL_MASK
            else:
                self._translated_key_state |= IBus.ModifierType.CONTROL_MASK
        if new_key.name in ('Alt_L', 'Alt_R'):
            if new_key.release:
                self._translated_key_state &= ~IBus.ModifierType.MOD1_MASK
            else:
                self._translated_key_state |= IBus.ModifierType.MOD1_MASK
        if new_key.name in ('Super_L', 'Super_R'):
            if new_key.release:
                self._translated_key_state &= ~IBus.ModifierType.SUPER_MASK
            else:
                self._translated_key_state |= IBus.ModifierType.SUPER_MASK
        if new_key.name in ('ISO_Level3_Shift'):
            if new_key.release:
                self._translated_key_state &= ~IBus.ModifierType.MOD5_MASK
            else:
                self._translated_key_state |= IBus.ModifierType.MOD5_MASK
        self._translated_key_state &= itb_util.KEYBINDING_STATE_MASK
        if self._debug_level > 1:
            LOGGER.debug('new_key: %s state for next key=%x',
                         new_key, self._translated_key_state)
        return new_key

    def do_process_key_event( # pylint: disable=arguments-differ
            self, keyval: int, keycode: int, state: int) -> bool:
        '''Process Key Events
        Key Events include Key Press and Key Release,
        modifier means Key Pressed
        '''
        key = itb_util.KeyEvent(keyval, keycode, state)
        if self._debug_level > 1:
            LOGGER.debug('KeyEvent object: %s', key)
            LOGGER.debug('self._surrounding_text=%r', self._surrounding_text)

        if self._use_ibus_keymap:
            key = self._translate_to_ibus_keymap(key)

        if self._ollama_chat_query_thread:
            if self._ollama_chat_query_process_key(key):
                return self._return_true(key)
            return self._return_false(key)

        disabled = False
        if not self._input_mode:
            if self._debug_level > 0:
                LOGGER.debug('Direct input mode')
            disabled = True
        elif (self._disable_in_terminals
              and itb_util.detect_terminal(self._input_purpose, self._im_client)):
            if self._debug_level > 0:
                LOGGER.debug(
                    'Terminal detected and the option '
                    'to disable in terminals is set.')
            disabled = True
        elif (self.has_osk
              and
              (self._input_purpose in [itb_util.InputPurpose.TERMINAL.value])):
            if self._debug_level > 0:
                LOGGER.debug(
                    'OSK is visible and input purpose is TERMINAL, '
                    'disable to avoid showing passwords in the '
                    'OSK completion buttons.')
            disabled = True
        elif (self._input_purpose
              in [itb_util.InputPurpose.PASSWORD.value,
                  itb_util.InputPurpose.PIN.value]):
            if self._debug_level > 0:
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

        if self._handle_m17n_candidates(key):
            return self._return_true(key)

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
                if self._debug_level > 1:
                    LOGGER.debug('Preedit reopened successfully.')
            if (self._prev_key is not None
                and self._prev_key.handled
                and not self._prev_key.release
                and self._prev_key.val == key.val):
                if self._debug_level > 0:
                    LOGGER.info('Press key event was handled. '
                                'Do not pass release key event.')
                return True
            return False

        if self.is_empty() and not self._lookup_table.is_cursor_visible():
            if self._debug_level > 1:
                LOGGER.debug(
                    'self.is_empty(): KeyEvent object: %s', key)
            # This is the first character typed since the last commit
            # there is nothing in the preëdit yet.
            if key.val < 32:
                # If the first character of a new word is a control
                # character, return False to pass the character through as is,
                # it makes no sense trying to complete something
                # starting with a control character:
                self._update_ui_empty_input()
                return False
            if (key.val == IBus.KEY_space
                and not key.mod5
                and not key.shift
                and not self._has_transliteration([key.msymbol])):
                # if the first character is a space, just pass it
                # through it makes not sense trying to complete (“not
                # key.mod5” is checked here because AltGr+Space is the
                # key binding to insert a literal space into the
                # preëdit, “not key.shift” is checked here because
                # some input methods transliterate the msymbol 'S- '
                # (See:
                # https://github.com/mike-fabian/ibus-typing-booster/issues/524)):
                self._update_ui_empty_input()
                return False
            if (key.val >= 32 and not key.control
                and not self._tab_enable
                and not self.has_osk
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
                    # opened. If OSK is used, committing by index is
                    # never possible, therefore digits can be put
                    # into the preedit always.
                    # Putting a digit into the candidate list
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
            and ((key.val in self._commit_trigger_keys
                  # https://github.com/mike-fabian/ibus-typing-booster/issues/709
                  and not self._has_transliteration([key.msymbol]))
                 or (len(key.msymbol) == 1
                     and (key.control
                          or key.mod1 # mod1: Usually Alt
                          or key.mod4 # mod4: Usually Super, Hyper
                          or key.super or key.hyper or key.meta))
                 or (itb_util.msymbol_triggers_commit(key.msymbol)
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
                # The modifier key combinations which should be passed
                # through include those with multiple modifiers like
                # 'A-C-l' for example. See:
                # https://github.com/mike-fabian/ibus-typing-booster/issues/622
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
                #
                # 'S- ' (Shift-space) should not trigger a commit if
                # it has a transliteration, see:
                # https://github.com/mike-fabian/ibus-typing-booster/issues/524
            if self.is_empty() and not self._lookup_table.is_cursor_visible():
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
            if (not key.shift and (not self._lookup_table.is_cursor_visible()
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
                    self._lookup_table.enabled_by_tab = False
                    self._lookup_table.enabled_by_min_char_complete = False
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
                    self._lookup_table.enabled_by_tab = False
                    self._lookup_table.enabled_by_min_char_complete = False
                    if key.control:
                        self._remove_string_after_cursor()
                    else:
                        self._remove_character_after_cursor()
                    if self.is_empty():
                        self._new_sentence = False
                        self._current_case_mode = 'orig'
                    self._update_ui()
                    return True
            if (not key.shift and (self._lookup_table.is_cursor_visible()
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
                    self._lookup_table.enabled_by_tab = False
                    self._lookup_table.enabled_by_min_char_complete = False
                    if key.control:
                        # Move cursor to the beginning of the typed string
                        self._typed_string_cursor = 0
                    else:
                        self._typed_string_cursor -= 1
                    self._update_ui()
                    return True
                if (key.val in (IBus.KEY_BackSpace,)
                    and self._typed_string_cursor > 0):
                    self._lookup_table.enabled_by_tab = False
                    self._lookup_table.enabled_by_min_char_complete = False
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
            if self._debug_level > 1:
                LOGGER.debug('_process_key_event() commit triggered.\n')
            input_phrase = self._transliterated_strings[preedit_ime]
            input_phrase = self._case_modes[
                self._current_case_mode]['function'](input_phrase)
            # We need to transliterate
            # the preëdit again here, because adding the commit key to
            # the input might influence the transliteration. For example
            # When using hi-itrans, “. ” translates to “। ”
            # (See: https://bugzilla.redhat.com/show_bug.cgi?id=1353672)
            #
            # But not for `ja-anthy`. In case of `ja-anthy`, a Return
            # will be absorbed in the transliteration because it does
            # a commit in m17n. Other commit trigger keys cannot do
            # anything to change the `ja-anthy` transliteration
            # either.
            if (self._typed_string_cursor == len(self._typed_string)
                and not self._current_imes[0] == 'ja-anthy'):
                input_phrase = self._transliterators[
                    preedit_ime].transliterate(
                        self._typed_string + [key.msymbol],
                        ascii_digits=self._ascii_digits)
                if key.msymbol:
                    if input_phrase.endswith(key.msymbol):
                        # If the transliteration now ends with the commit
                        # key, cut it off because the commit key is passed
                        # to the application later anyway and we do not
                        # want to pass it twice:
                        input_phrase = input_phrase[:-len(key.msymbol)]
                        input_phrase = self._case_modes[
                            self._current_case_mode]['function'](input_phrase)
                        if input_phrase == '':
                            if self._debug_level > 1:
                                LOGGER.debug(
                                    'Cutting off the commit key made the '
                                    'transliteration empty. '
                                    'If anything is selected in the '
                                    'lookup table, commit it. '
                                    'Then call clear input and update UI to remove'
                                    'any remaining preedit or lookup table.')
                            if (self._lookup_table.get_number_of_candidates()
                                and self._lookup_table.is_cursor_visible()):
                                # something is selected in the lookup
                                # table, commit the selected phrase
                                input_phrase = commit_string = (
                                    self.get_string_from_lookup_table_cursor_pos())
                                self._commit_string(
                                    commit_string, input_phrase=input_phrase)
                                # Sleep between the commit and the forward key event:
                                time.sleep(self._ibus_event_sleep_seconds)
                                if (key.val in (IBus.KEY_space, IBus.KEY_Tab)
                                    and not (key.control
                                             or key.mod1
                                             or key.super
                                             or key.hyper
                                             or key.meta)):
                                    self._clear_input()
                                    self._trigger_surrounding_text_update()
                                    # Tiny delay to give the
                                    # surrounding text a chance to
                                    # update:
                                    GLib.timeout_add(
                                        5, self._update_ui_empty_input_try_completion)
                                else:
                                    self._clear_input_and_update_ui()
                                return False
                            self._clear_input_and_update_ui()
                            return False
                    elif (key.msymbol == ' '
                          and self._typed_string == ['Z']
                          and input_phrase == '\u3000'):
                        # All m17n input methods which include
                        # cjk-util (e.g. zh-py, ko-romaja, …) can
                        # produce a fullwidth space by typing
                        # Z+space. That should not go into preedit if
                        # it is the first thing typed on empty input.
                        LOGGER.debug('Fullwidth space typed by typing Z+space '
                                     'on empty input. Commit it, clear input, '
                                     'and update UI.')
                        super().commit_text(IBus.Text.new_from_string('\u3000'))
                        self._clear_input_and_update_ui()
                        return True
                    else:
                        # The commit key has been absorbed by the
                        # transliteration.  Add the key to the input
                        # instead of committing:
                        if self._debug_level > 1:
                            LOGGER.debug(
                                'Insert instead of commit: key.msymbol=“%s”',
                                key.msymbol)
                        self._insert_string_at_cursor([key.msymbol])
                        self._update_ui()
                        return True
            if (self._lookup_table.get_number_of_candidates()
                and self._lookup_table.is_cursor_visible()):
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
                # In Japanese input methods, a Return commits, in Chinese
                # input methods a space commits. The commit key is not
                # passed through.
                if (self._current_imes[0] == 'ja-anthy'
                    and key.val in (IBus.KEY_Return,
                                    IBus.KEY_KP_Enter, IBus.KEY_ISO_Enter)):
                    return True
                if (self._current_imes[0].startswith('zh')
                    and key.val == IBus.KEY_space and key.msymbol == ' '):
                    return True
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
                if self._debug_level > 0:
                    LOGGER.error('commit string unexpectedly empty.')
                self._update_ui_empty_input()
                return False
            # Remember whether a candidate is selected and where the
            # caret is now because after self._commit_string() this
            # information is gone:
            candidate_was_selected = False
            if self._lookup_table.is_cursor_visible():
                candidate_was_selected = True
            caret_was = self.get_caret(extra_msymbol=key.msymbol)
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
                self._trigger_surrounding_text_update()
                # Tiny delay of to give the surrounding text a chance
                # to update:
                GLib.timeout_add(5, self._update_ui_empty_input_try_completion)
            else:
                self._clear_input_and_update_ui()
            # In Japanese input methods, a Return commits, in Chinese
            # input methods a space commits. The commit key is not
            # passed through and a cursor correction does not seem to
            # make sense either.
            if (self._current_imes[0] == 'ja-anthy'
                and key.val in (IBus.KEY_Return,
                                IBus.KEY_KP_Enter, IBus.KEY_ISO_Enter)):
                return True
            if (self._current_imes[0].startswith('zh')
                and key.val == IBus.KEY_space and key.msymbol == ' '):
                return True
            # These sleeps between commit() and
            # forward_key_event() are unfortunately needed because
            # this is racy, without the sleeps it works
            # unreliably.
            time.sleep(self._ibus_event_sleep_seconds)
            if not candidate_was_selected:
                # cursor needs to be corrected leftwards:
                commit_string = itb_util.normalize_nfc_and_composition_exclusions(
                    commit_string)
                for dummy_char in commit_string[caret_was:]:
                    self._forward_generated_key_event(IBus.KEY_Left)
            return False

        if (key.unicode
            # https://github.com/mike-fabian/ibus-typing-booster/issues/709
            or (key.msymbol and self._has_transliteration([key.msymbol]))):
            # If the suggestions are only enabled by Tab key, i.e. the
            # lookup table is not shown until Tab has been typed, hide
            # the lookup table again when characters are added to the
            # preëdit:
            self._lookup_table.enabled_by_tab = False
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
                and self._lookup_table.get_number_of_candidates()
                and self._lookup_table.is_cursor_visible()):
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
                if self._debug_level > 1:
                    LOGGER.debug(
                        'auto committing because of key.msymbol = %s',
                        key.msymbol)
                self._commit_string(
                    input_phrase + ' ', input_phrase=input_phrase)
                self._clear_input()
            if self._try_early_commit():
                transliterated_parts = self._transliterators[
                    self.get_current_imes()[0]].transliterate_parts(
                        self._typed_string, ascii_digits=self._ascii_digits)
                if self._debug_level > 1:
                    LOGGER.debug(
                        'Maybe commit early: '
                        'self._typed_string=%r '
                        'self._typed_string_cursor=%s '
                        '-> transliterated_parts=%r',
                        self._typed_string, self._typed_string_cursor,
                        transliterated_parts)
                if (transliterated_parts.committed
                    and transliterated_parts.committed_index):
                    self._typed_string = self._typed_string[
                        transliterated_parts.committed_index:]
                    self._typed_string_cursor = len(self._typed_string)
                    self._update_transliterated_strings()
                    # The might be m17n candidates, empty candidate list to
                    # remove them:
                    self._candidates = []
                    if (not self._prefer_commit
                        and transliterated_parts.committed_index == 1
                        and transliterated_parts.committed == key.unicode
                        and not transliterated_parts.preedit
                        and not transliterated_parts.cursor_pos):
                        self._update_ui()
                        return False
                    super().commit_text(
                        IBus.Text.new_from_string(
                            transliterated_parts.committed))
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
            LOGGER.debug(
                'object_path=%s client=%s self.client_capabilities=%s\n',
                object_path, client, f'{self.client_capabilities:010b}')
        self._surrounding_text = SurroundingText()
        self._surrounding_text_old = SurroundingText()
        self._trigger_surrounding_text_update()
        (program_name,
         window_title) = itb_active_window.get_active_window()
        if self._debug_level > 1:
            LOGGER.debug(
                'program_name=“%s” window_title=“%s”',
                program_name, window_title)
        self._im_client = client
        if ':' not in self._im_client:
            self._im_client += ':' + program_name + ':' + window_title
        else:
            self._im_client += ':' + window_title
        if self._debug_level > 1:
            LOGGER.debug('self._im_client=%s\n', self._im_client)
        self._keyvals_to_keycodes = itb_util.KeyvalsToKeycodes()
        if self._debug_level > 2:
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
        self._update_ui()
        self._apply_autosettings()

    def _apply_autosettings(self) -> None:
        '''Apply automatic setting changes for the window which just got focus'''
        if self._debug_level > 0:
            LOGGER.debug('self._im_client=%s', self._im_client)
        if self._autosettings_revert:
            self._revert_autosettings()
        if not self._im_client:
            return
        autosettings_apply: Dict[str, Any] = {}
        for (setting, value, regexp) in self._autosettings:
            if (not regexp
                or setting not in self._settings_dict
                or 'set_function' not in self._settings_dict[setting]
                or 'get_function' not in self._settings_dict[setting]):
                continue
            pattern = re.compile(regexp)
            if not pattern.search(self._im_client):
                continue
            current_value = self._settings_dict[setting]['get_function']()
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
            self._settings_dict[setting]['set_function'](
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
        if self._debug_level > 1:
            LOGGER.debug('commit_phrase=%r input_phrase=%r',
                         commit_phrase, input_phrase)
        if not input_phrase:
            input_phrase = self._transliterated_strings[
                self.get_current_imes()[0]]
        if not commit_phrase:
            typed_string = itb_util.normalize_nfc_and_composition_exclusions(
                input_phrase)
            first_candidate = ''
            if self._candidates:
                first_candidate = self._candidates[0].phrase
            if (not self._inline_completion
                or self.has_osk
                or self._lookup_table.get_cursor_pos() != 0
                or not first_candidate
                or not first_candidate.startswith(typed_string)
                or first_candidate == typed_string):
                # Standard lookup table was shown, preedit contained
                # input_phrase:
                commit_phrase = input_phrase
            else:
                commit_phrase = first_candidate
        # commit_phrase should always be in NFC:
        commit_phrase = itb_util.normalize_nfc_and_composition_exclusions(
            commit_phrase)
        stripped_input_phrase = itb_util.strip_token(input_phrase)
        stripped_commit_phrase = itb_util.strip_token(commit_phrase)
        if (self._off_the_record
            or self._record_mode == 3
            or self._hide_input
            or self._input_hints & itb_util.InputHints.PRIVATE):
            if self._debug_level > 1:
                LOGGER.debug('Privacy: NOT recording and pushing context.')
            return
        if self._debug_level > 1:
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
            if self._debug_level > 1:
                LOGGER.debug(
                    'Empty input or commit: NOT recording and pushing context')
            return
        if (self._record_mode == 1
            and not self.database.phrase_exists(stripped_commit_phrase)
            and not self.database.hunspell_obj.spellcheck(stripped_commit_phrase)):
            if self._debug_level > 1:
                LOGGER.debug('self._record_mode=%d: Not recording: %r',
                             self._record_mode, stripped_commit_phrase)
            return
        if (self._record_mode == 2
            and not self.database.hunspell_obj.spellcheck(stripped_commit_phrase)):
            if self._debug_level > 1:
                LOGGER.debug('self._record_mode=%d: Not recording: %r',
                             self._record_mode, stripped_commit_phrase)
            return
        if self._debug_level > 1:
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
        if self._debug_level > 1:
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
        if self._debug_level > 1:
            LOGGER.debug('object_path=%s\n', object_path)
        if self._ollama_chat_query_thread:
            self._ollama_chat_query_cancel(commit_selection=False)
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
        for ime in self._current_imes:
            # ibus-m17n also calls minput_reset_ic() on focus out.
            # This is necessary if one wants to reset the input
            # methods to their default states. For example, if zh-py
            # is in fullwidth-mode (to input fullwidth Latin), calling
            # reset_ic() switches to the default mode to input Chinese
            # characters.
            self._transliterators[ime].reset_ic()

    def _revert_autosettings(self) -> None:
        '''Revert automatic setting changes which were done on focus in'''
        for setting, value in self._autosettings_revert.items():
            LOGGER.info('Revert autosetting: %s: -> %s', setting, value)
            self._settings_dict[setting]['set_function'](
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
        if self._debug_level > 1:
            LOGGER.debug('self._current_preedit_text.text_str=%r '
                         'self._typed_string=%s '
                         'self._typed_compose_sequence=%s '
                         'compose preedit representation=%r',
                         self._current_preedit_text.text_str,
                         repr(self._typed_string),
                         repr(self._typed_compose_sequence),
                         self._compose_sequences.preedit_representation(
                             self._typed_compose_sequence))
        if self._ollama_chat_query_thread:
            self._ollama_chat_query_cancel(commit_selection=False)
            return
        # The press events of arrow keys like `Left` and `BackSpace`
        # cause a call to `do_reset()`. If that clears
        # self._surrounding_text_old() the comparison of
        # self._surrounding_text with self._surrounding_text.old()
        # during the release event cannot work anymore. And then
        # reopening preedits always fails, even in firefox which seems
        # to be the last place where it currently still works.
        # So do not clear self._surrounding_text_old here, only
        # clear self._surrounding_text:
        self._surrounding_text = SurroundingText()
        self._trigger_surrounding_text_update()
        for ime in self._current_imes:
            # ibus-m17n also calls minput_reset_ic() on focus out.
            # This is necessary if one wants to reset the input
            # methods to their default states. For example, if zh-py
            # is in fullwidth-mode (to input fullwidth Latin), calling
            # reset_ic() switches to the default mode to input Chinese
            # characters.
            self._transliterators[ime].reset_ic()
        if self._current_preedit_text.text_str == '':
            if self._debug_level > 1:
                LOGGER.debug('Current preedit is empty: '
                             'do not record, clear input, update UI.')
            # If the current preedit is empty, that means that there is
            # no current input, neither "normal" nor compose input. In that
            # case, there is nothing to record in the database, no pending
            # input needs to be cleared and the UI needs no update.
            # Except a lookup table might need to be removed. Because
            # a lookup table might have been created by
            # _command_show_selection_info() with an empty preedit.
            self._lookup_table.clear()
            self._lookup_table.set_cursor_visible(False)
            self.hide_lookup_table()
            self.update_auxiliary_text(
                IBus.Text.new_from_string(''), False)
            self._lookup_table.enabled_by_tab = False
            self._lookup_table.state = LookupTableState.NORMAL
            if (self._prev_key
                and
                self._prev_key.val in (
                    IBus.KEY_Return, IBus.KEY_KP_Enter, IBus.KEY_ISO_Enter)):
                if self._debug_level > 1:
                    LOGGER.debug(
                        'Avoid clearing context after Return or Enter')
                return
            if self._debug_level > 1:
                LOGGER.debug('Clear context: cursor might have moved, '
                             'remembered context might be wrong')
            self.clear_context()
            return
        if (self.has_surrounding_text
            and
            self._input_purpose not in [itb_util.InputPurpose.TERMINAL.value]):
            text = self._surrounding_text.text
            cursor_pos = self._surrounding_text.cursor_pos
            text_to_cursor = text[:cursor_pos]
            if self._debug_level > 1:
                LOGGER.debug('self._surrounding_text=%r',
                             self._surrounding_text)
            if (self._im_client.startswith('gtk3-im')
                and not text_to_cursor.endswith(self._current_preedit_text.text_str)):
                # On Wayland this causes problems, as the surrounding text
                # behaves differently. Do this workaround only if the im client
                # uses gtk3-im, if not it will cause more problems then help.
                LOGGER.debug('self._current_preedit_text.text_str=“%s”',
                             self._current_preedit_text.text_str)
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
            if self._debug_level > 1:
                LOGGER.debug('probably triggered by key')
        else:
            if self._debug_level > 1:
                LOGGER.debug('probably triggered by mouse')
        # The preëdit, if there was any, has already been committed
        # automatically because
        # update_preedit_text_with_mode(,,,IBus.PreeditFocusMode.COMMIT)
        # has been used. But the contents of the preëdit have not
        # been recorded in the user database yet. Do it now:
        if not self.is_empty():
            self._record_in_database_and_push_context()
        if self._debug_level > 1:
            LOGGER.debug('Clearing context and input.')
        self.clear_context()
        self._clear_input_and_update_ui()

    def do_set_content_type( # pylint: disable=arguments-differ
            self, purpose: int, hints: int) -> None:
        '''Called when the input purpose or hints change'''
        LOGGER.debug('purpose=%s hints=%s\n', purpose, format(hints, '016b'))
        self._input_purpose = purpose
        self._input_hints = hints
        if self._debug_level > 1:
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
        if self._debug_level > 1:
            LOGGER.debug('do_enable()\n')
        self._surrounding_text = SurroundingText()
        self._surrounding_text_old = SurroundingText()
        self._trigger_surrounding_text_update()
        self.do_focus_in()

    def do_disable(self) -> None: # pylint: disable=arguments-differ
        '''Called when this input engine is disabled'''
        if self._debug_level > 1:
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

    def _on_set_surrounding_text(self,
                                _engine: IBus.Engine,
                                text: IBus.Text,
                                cursor_pos: int,
                                anchor_pos: int) -> None:
        '''Called when the surrounding text has changed.

        Useful especially in debugging for stuff like this:

        self._surrounding_text.event.clear()

        or get a new object which has the event cleared:

        self._surrounding_text = SurroundingText()
        ... some stuff ...

        # Now check whether at  least one set-surrounding-text signal
        # has occured:
        self._set_surrounding_text.event.is_set()

        or:

        # If at least one set-surrounding-text signal
        # has already occured, continue immediately, else
        # wait for such a signal to occur but continue after
        # a timeout:
        self._set_surrounding_text.event.wait(timeout=0.1)
        '''
        if self._debug_level > 1:
            LOGGER.debug('text=%r cursor_pos=%s anchor_pos=%s',
                         text.get_text(), cursor_pos, anchor_pos)
        self._surrounding_text.text = text.get_text()
        self._surrounding_text.cursor_pos = cursor_pos
        self._surrounding_text.anchor_pos = anchor_pos
        self._surrounding_text.event.set()

    def _on_gsettings_value_changed(
            self, _settings: Gio.Settings, key: str) -> None:
        '''
        Called when a value in the settings has been changed.

        :param settings: The settings object
        :param key: The key of the setting which has changed
        '''
        value = itb_util.variant_to_value(self._gsettings.get_value(key))
        LOGGER.debug('Settings changed: key=%s value=%s\n', key, value)
        if (key in self._settings_dict
            and 'set_function' in self._settings_dict[key]):
            self._settings_dict[key]['set_function'](
                value, update_gsettings=False)
            return
        LOGGER.warning('Unknown key\n')
        return
