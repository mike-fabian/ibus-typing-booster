# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2016-2019 Mike FABIAN <mfabian@redhat.com>
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
 Define some mock classes for the unittests.
'''

from typing import Any
from typing import List
# pylint: disable=wrong-import-position
from gi import require_version # type: ignore
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore
# pylint: enable=wrong-import-position

# pylint: disable=missing-function-docstring
# pylint: disable=too-few-public-methods
# pylint: disable=missing-class-docstring
class MockEngine:
    '''Mock engine class to simulate IBus.Engine for testing'''
    props = None
    def __init__(
            self,
            engine_name: str = '',
            connection: Any = None,
            object_path: str = '') -> None:
        self.mock_engine_name = engine_name
        self.mock_connection = connection
        self.mock_object_path = object_path
        self.mock_auxiliary_text = ''
        self.mock_preedit_text = ''
        self.mock_preedit_text_cursor_pos = 0
        self.mock_preedit_text_visible = True
        self.mock_preedit_focus_mode = IBus.PreeditFocusMode.COMMIT
        self.mock_committed_text = ''
        self.mock_committed_text_cursor_pos = 0
        self.client_capabilities = (
            IBus.Capabilite.PREEDIT_TEXT
            | IBus.Capabilite.AUXILIARY_TEXT
            | IBus.Capabilite.LOOKUP_TABLE
            | IBus.Capabilite.FOCUS
            | IBus.Capabilite.PROPERTY)
        # There are lots of weird problems with surrounding text
        # which makes this hard to test. Therefore this mock
        # engine does not try to support surrounding text, i.e.
        # we omit “| IBus.Capabilite.SURROUNDING_TEXT” here.

    def update_auxiliary_text(self, text: IBus.Text, _visible: bool) -> None:
        self.mock_auxiliary_text = text.text

    def commit_text(self, text: IBus.Text) -> None:
        self.mock_committed_text = (
            self.mock_committed_text[
                :self.mock_committed_text_cursor_pos]
            + text.text
            + self.mock_committed_text[
                self.mock_committed_text_cursor_pos:])
        self.mock_committed_text_cursor_pos += len(text.text)

    def forward_key_event(self, val: int, _code: int, _state: int) -> None:
        if (val == IBus.KEY_Left
            and self.mock_committed_text_cursor_pos > 0):
            self.mock_committed_text_cursor_pos -= 1
            return
        unicode = IBus.keyval_to_unicode(val)
        if unicode:
            self.mock_committed_text = (
            self.mock_committed_text[
                :self.mock_committed_text_cursor_pos]
            + unicode
            + self.mock_committed_text[
                self.mock_committed_text_cursor_pos:])
            self.mock_committed_text_cursor_pos += len(unicode)

    def update_lookup_table(
            self, table: IBus.LookupTable, visible: bool) -> None:
        pass

    def update_preedit_text(self, text: IBus.Text, cursor_pos: int, visible: bool) -> None:
        self.mock_preedit_text = text.get_text()
        self.mock_preedit_text_cursor_pos = cursor_pos
        self.mock_preedit_text_visible = visible

    def update_preedit_text_with_mode(
            self,
            text: IBus.Text,
            cursor_pos: int,
            visible: bool,
            focus_mode: IBus.PreeditFocusMode) -> None:
        self.mock_preedit_focus_mode = focus_mode
        self.update_preedit_text(text, cursor_pos, visible)

    def hide_preedit_text(self) -> None:
        self.update_preedit_text(IBus.Text.new_from_string(''), 0, False)

    def register_properties(self, property_list: List[IBus.Property]) -> None:
        pass

    def update_property(self, _property: IBus.Property) -> None:
        pass

    def hide_lookup_table(self) -> None:
        pass

    def get_surrounding_text(self) -> None:
        pass

    def connect(self, signal: str, callback_function: Any) -> None:
        pass

    def add_table_by_locale(self, locale: str) -> None:
        pass

class MockLookupTable:
    def __init__(
            self,
            page_size: int = 9,
            cursor_pos: int = 0,
            cursor_visible: bool = False,
            wrap_around: bool = True) -> None:
        self.clear()
        self.mock_labels = {
            1: '1.',
            2: '2.',
            3: '3.',
            4: '4.',
            5: '5.',
            6: '6.',
            7: '7.',
            8: '8.',
            9: '9.',
        }
        self.mock_page_size = page_size
        self.mock_cursor_pos = cursor_pos
        self.mock_cursor_visible = cursor_visible
        self.cursor_visible = cursor_visible
        self.mock_wrap_around = wrap_around
        self.mock_candidates: List[str] = []
        self.mock_orientation = 0

    def clear(self) -> None:
        self.mock_candidates = []
        self.mock_cursor_pos = 0

    def set_label(self, index: int, label: IBus.Text) -> None:
        self.mock_labels[index] = label.get_text()

    def get_label(self, index: int) -> str:
        return self.mock_labels[index]

    def set_page_size(self, size: int) -> None:
        self.mock_page_size = size

    def get_page_size(self) -> int:
        return self.mock_page_size

    def set_round(self, wrap_around: bool) -> None:
        self.mock_wrap_around = wrap_around

    def set_cursor_pos(self, pos: int) -> None:
        self.mock_cursor_pos = pos

    def get_cursor_pos(self) -> int:
        return self.mock_cursor_pos

    def set_cursor_visible(self, visible: bool) -> None:
        self.mock_cursor_visible = visible
        self.cursor_visible = visible

    def cursor_down(self) -> None:
        if self.mock_candidates:
            self.mock_cursor_pos += 1
            self.mock_cursor_pos %= len(self.mock_candidates)

    def cursor_up(self) -> None:
        if self.mock_candidates:
            if self.mock_cursor_pos > 0:
                self.mock_cursor_pos -= 1
            else:
                self.mock_cursor_pos = len(self.mock_candidates) - 1

    def set_orientation(self, orientation: int) -> None:
        self.mock_orientation = orientation

    def get_orientation(self) -> int:
        return self.mock_orientation

    def get_number_of_candidates(self) -> int:
        return len(self.mock_candidates)

    def append_candidate(self, candidate: IBus.Text) -> None:
        self.mock_candidates.append(candidate.get_text())

    def get_candidate(self, index: int) -> str:
        return self.mock_candidates[index]

class MockPropList:
    def append(self, _property: IBus.Property) -> None:
        pass

class MockProperty:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def set_label(self, ibus_text: IBus.Text) -> None:
        pass

    def set_symbol(self, ibus_text: IBus.Text) -> None:
        pass

    def set_tooltip(self, ibus_text: IBus.Text) -> None:
        pass

    def set_sensitive(self, sensitive: bool) -> None:
        pass

    def set_visible(self, visible: bool) -> None:
        pass

    def set_state(self, visible: bool) -> None:
        pass
