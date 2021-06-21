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

from gi import require_version # type: ignore
require_version('IBus', '1.0')
from gi.repository import IBus # type: ignore

class MockEngine:
    def __init__(self, engine_name = '', connection = None, object_path = ''):
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

    def update_auxiliary_text(self, text, visible):
        self.mock_auxiliary_text = text.text

    def commit_text(self, text):
        self.mock_committed_text = (
            self.mock_committed_text[
                :self.mock_committed_text_cursor_pos]
            + text.text
            + self.mock_committed_text[
                self.mock_committed_text_cursor_pos:])
        self.mock_committed_text_cursor_pos += len(text.text)

    def forward_key_event(self, val, code, state):
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

    def update_lookup_table(self, table, visible):
        pass

    def update_preedit_text(self, text, cursor_pos, visible):
        self.mock_preedit_text = text.get_text()
        self.mock_preedit_text_cursor_pos = cursor_pos
        self.mock_preedit_text_visible = visible

    def update_preedit_text_with_mode(
            self, text, cursor_pos, visible, focus_mode):
        self.mock_preedit_focus_mode = focus_mode
        self.update_preedit_text(text, cursor_pos, visible)

    def register_properties(self, property_list):
        pass

    def update_property(self, property):
        pass

    def hide_lookup_table(self):
        pass

class MockLookupTable:
    def __init__(self, page_size = 9, cursor_pos = 0, cursor_visible = False, round = True):
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
        self.mock_round = round
        self.mock_candidates = []

    def clear(self):
        self.mock_candidates = []
        self.mock_cursor_pos = 0

    def set_label(self, index, label):
        self.mock_labels[index] = label.get_text()

    def get_label(self, index):
        return self.mock_labels[index]

    def set_page_size(self, size):
        self.mock_page_size = size

    def get_page_size(self):
        return self.mock_page_size

    def set_round(self, round):
        self.mock_round = round

    def set_cursor_pos(self, pos):
        self.mock_cursor_pos = pos

    def get_cursor_pos(self):
        return self.mock_cursor_pos

    def set_cursor_visible(self, visible):
        self.mock_cursor_visible = visible
        self.cursor_visible = visible

    def cursor_down(self):
        if len(self.mock_candidates):
            self.mock_cursor_pos += 1
            self.mock_cursor_pos %= len(self.mock_candidates)

    def cursor_up(self):
        if len(self.mock_candidates):
            if self.mock_cursor_pos > 0:
                self.mock_cursor_pos -= 1
            else:
                self.mock_cursor_pos = len(self.mock_candidates) - 1

    def set_orientation(self, orientation):
        self.mock_orientation = orientation

    def get_number_of_candidates(self):
        return len(self.mock_candidates)

    def append_candidate(self, candidate):
        self.mock_candidates.append(candidate.get_text())

    def get_candidate(self, index):
        return self.mock_candidates[index]

    def get_number_of_candidates(self):
        return len(self.mock_candidates)

class MockPropList:
    def append(self, property):
        pass

class MockProperty:
    def __init__(self, *args, **kwargs):
        pass

    def set_label(self, ibus_text):
        pass

    def set_symbol(self, ibus_text):
        pass

    def set_tooltip(self, ibus_text):
        pass

    def set_sensitive(self, sensitive):
        pass

    def set_visible(self, visible):
        pass

    def set_state(self, visible):
        pass
