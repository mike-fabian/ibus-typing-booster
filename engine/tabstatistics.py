# -*- coding: utf-8 -*-
# vim:et sts=4 sw=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2019 Mike FABIAN <mfabian@redhat.com>
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
Utility to inspec the user database of Typing Booster and print
some information about the contents
'''

from typing import List
from typing import Tuple
from typing import Dict
from typing import Any
import os
import sys
import time
import sqlite3
import argparse

import itb_util

def parse_args() -> Any:
    '''
    Parse the command line arguments.
    '''
    parser = argparse.ArgumentParser(
        description='Tool for inspecting the user database of Typing Booster')
    parser.add_argument(
        '-v', '--verbose',
        dest='verbose',
        action='store_true',
        default=False,
        help=('Print more verbose information. '
             'default: %(default)s'))
    parser.add_argument(
        '-f', '--file',
        dest='file',
        type=str,
        action='store',
        default='~/.local/share/ibus-typing-booster/user.db',
        help=('Full path of the database file to inspect, '
              'default: "%(default)s"'))
    parser.add_argument(
        '-m', '--max-rows',
        dest='max_rows',
        type=int,
        action='store',
        default=int(50000),
        help=('Maximum number of rows to keep in the database. '
              'default: "%(default)s"'))
    parser.add_argument(
        '-r', '--rows',
        dest='rows',
        action='store_true',
        default=False,
        help=('Print all rows of the database, '
              'default: %(default)s'))
    parser.add_argument(
        '-t', '--total-rows',
        dest='total_rows',
        action='store_true',
        default=False,
        help=('Print total number of rows in the database. '
              'default: %(default)s'))
    parser.add_argument(
        '-p', '--period',
        dest='period',
        type=str,
        action='store',
        default='none',
        help=('Print keystrokes saved by period. '
              'Period can be "none|second(s)|minute(s)|hour(s)|day(s)|week(s)|month(s)|year(s)|total(s)". '
              '"none" means do not print saved keystrokes. '
              'default: "%(default)s"'))
    parser.add_argument(
        '--time_newest',
        dest='time_newest',
        action='store_true',
        default=False,
        help=('Show the newest timestamp in the database. '
              'default: %(default)s'))
    parser.add_argument(
        '--time_oldest',
        dest='time_oldest',
        action='store_true',
        default=False,
        help=('Show the oldest timestamp in the database. '
              'default: %(default)s'))
    parser.add_argument(
        '--time_now',
        dest='time_now',
        action='store_true',
        default=False,
        help=('Show the timestamp used for “now” when doing the calculations. '
              'default: %(default)s'))
    parser.add_argument(
        '-u', '--user_freq_distribution',
        dest='user_freq_distribution',
        action='store_true',
        default=False,
        help=('Show the destribution of user frequencies, i.e. '
              'how many rows are there wich have been used once, '
              'how many rows have been  used twice, etc. ... '
              'default: %(default)s'))
    parser.add_argument(
        '-d', '--decay',
        dest='decay',
        action='store_true',
        default=False,
        help=('Show information about which rows would be decayed or deleted. '
              '(Just shows information, doesn’t change the database!) '
              'default: %(default)s'))
    return parser.parse_args()

_ARGS = parse_args()

class DbContents:
    def __init__(self, user_db_file='', max_rows=50000, verbose=False) -> None:
        self._max_rows = max_rows
        self._verbose = verbose
        self._time_now = time.time()
        self._user_db_file = os.path.expanduser(user_db_file)
        self._database = sqlite3.connect(self._user_db_file)
        # id, input_phrase, phrase, p_phrase, pp_phrase, user_freq, timestamp
        self._original_rows: List[Tuple[int, str, str, str, str, int, float]] = []
        self._original_rows = self._database.execute('SELECT * FROM phrases;').fetchall()
        self.sort_by_time_ascending()
        self._time_oldest = 0.0
        self._time_newest = 0.0
        if self._original_rows:
            self._time_oldest = self._original_rows[0][6]
            self._time_newest = self._original_rows[-1][6]

    def print_decay(self) -> None:
        self.sort_by_user_freq_time_ascending()
        print(f'1st pass: Maximum number of rows to keep='
              f'{self._max_rows}')
        index = len(self._original_rows)
        number_delete_above_max = 0
        rows_kept: List[Tuple[int, str, str, str, str, int, float]] = []
        for row in self._original_rows:
            user_freq = row[5]
            if (index > self._max_rows
                and user_freq < itb_util.SHORTCUT_USER_FREQ):
                number_delete_above_max += 1
                if self._verbose:
                    self._print_row(row, prefix='>max: ')
            else:
                rows_kept.append(row)
            index -= 1
        print('1st pass: Number of rows to delete above maximum size='
              f'{number_delete_above_max}')
        # As the first pass above removes rows sorted by count and
        # then by timestamp, it will never remove rows with a higher
        # count even if they are extremely old. Therefore, a second
        # pass uses sorting only by timestamp in order to first decay and
        # eventually remove some rows which have not been used for a
        # long time as well, even if they have a higher count.
        # In this second pass, the 0.1% oldest rows are checked
        # and:
        #
        # - if user_freq == 1 remove the row
        # - if user_freq > 1 divide user_freq by 2 and update timestamp to “now”
        #
        # 0.1% is really not much but I want to be careful not to remove
        # too much when trying this out.
        #
        # sort kept rows by timestamp only instead of user_freq and timestamp:
        rows_kept = sorted(rows_kept,
                           key = lambda x: (
                               x[6], # timestamp
                               x[0], # id
                           ))
        if self._verbose:
            for row in rows_kept:
                self._print_row(row, prefix='1st pass kept: ')
        index = len(rows_kept)
        print(f'1st pass: Number of rows kept={index}')
        index_decay = int(self._max_rows * 0.999)
        print(f'2nd pass: Index for decay={index_decay}')
        number_of_rows_to_decay = 0
        number_of_rows_to_delete = 0
        for row in rows_kept:
            user_freq = row[5]
            if (index > index_decay
                and user_freq < itb_util.SHORTCUT_USER_FREQ):
                if user_freq == 1:
                    number_of_rows_to_delete += 1
                    if self._verbose:
                        self._print_row(row, prefix='2nd pass delete: ')
                else:
                    number_of_rows_to_decay += 1
                    if self._verbose:
                        self._print_row(row, prefix='2nd pass decay: ')
            index -= 1
        print(f'2nd pass: Number of rows to decay='
              f'{number_of_rows_to_decay}')
        print(f'2nd pass: Number of rows to delete='
              f'{number_of_rows_to_delete}')

    def print_total_rows(self) -> None:
        print(f'Total number of rows={len(self._original_rows)}')

    def print_time_oldest(self) -> None:
        print(f'Oldest timestamp={self._time_oldest} '
              f'{time.ctime(self._time_oldest)}')

    def print_time_newest(self) -> None:
        print(f'Newest timestamp={self._time_newest} '
              f'{time.ctime(self._time_newest)}')

    def print_time_now(self) -> None:
        print(f'Now timestamp={self._time_now} '
              f'{time.ctime(self._time_now)}')

    def print_savings(self, period='none') -> None:
        length_typed: Dict[int, int] = {}
        length_committed: Dict[int, int] = {}
        percent_saved: Dict[int, float] = {}
        length_typed_b: Dict[int, int] = {}
        length_committed_b: Dict[int, int] = {}
        percent_saved_b: Dict[int, float] = {}
        period_lengths_in_seconds = {
            'none': 0,
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 3600 * 24,
            'week': 3600 * 24 * 7,
            'month': 3600 * 24 * 30,
            'year': 3600 * 24 * 365,
            'total': self._time_now - self._time_oldest,
        }
        period_length_in_seconds = period_lengths_in_seconds.get(period, 0)
        if not period_length_in_seconds and period.endswith('s'):
            period = period[:-1]
            period_length_in_seconds = period_lengths_in_seconds.get(period, 0)
        for row in self._original_rows:
            user_freq = row[5]
            timestamp = row[6]
            # Saved keystrokes
            # If typing something like “smile” and selecting “☺” the number of
            # saved keystrokes (characters) becomes negative!
            length_typed_row = len(row[1]) * user_freq
            # Calculate committed length in 'NFD' because when “grun” was typed
            # but “grün” was committed, then the accented version has been selected
            # as a candidate and not having to type the accented version probably
            # saved typing something in the order of one keystroke.
            # But actually no conversion to 'NFD' is necessary here because the database
            # is already in 'NFD'.
            length_committed_row = len(row[2]) * user_freq
            if period_length_in_seconds > 0:
                period_index = int((self._time_now - timestamp) / period_length_in_seconds)
                if period == 'total':
                    period_index = 0 # avoid rounding error
                if length_committed_row >= length_typed_row:
                    # Counting savings only when the committed length is not shorter
                    # then the typed length. When the committed length is shorter,
                    # one has most likely typed an emoji, for example typed
                    # “smiling_cat_heart_” and then selected “️😻”. The committed
                    # length is only 1 and the typed length is 17 so the saving
                    # would be negative. But actually one probably saved some time
                    # getting the emoji by typing this instead of scrolling through
                    # a huge list of emoji in a graphical user interface.
                    # In almost all cases when length_committed is shorter than
                    # length_typed, an emoji or a mathematical symbol has been typed.
                    # Therefore, better don’t included them into the calculation
                    # of the keystrokes saved.
                    if period_index in length_typed:
                        length_typed[period_index] += length_typed_row
                        length_committed[period_index] += length_committed_row
                        if length_committed_row > length_typed_row:
                            length_typed_b[period_index] += length_typed_row
                            length_committed_b[period_index] += length_committed_row
                    else:
                        length_typed[period_index] = length_typed_row
                        length_committed[period_index] = length_committed_row
                        if length_committed_row > length_typed_row:
                            length_typed_b[period_index] = length_typed_row
                            length_committed_b[period_index] = length_committed_row
                        else:
                            length_typed_b[period_index] = 0
                            length_committed_b[period_index] = 0
                    if length_committed[period_index]:
                        percent_saved[period_index] = (
                            100.0 * (length_committed[period_index]
                                     - length_typed[period_index])
                            / length_committed[period_index])
                    else:
                        percent_saved[period_index] = 0.0
                    if length_committed_b[period_index]:
                        percent_saved_b[period_index] = (
                            100.0 * (length_committed_b[period_index]
                                     - length_typed_b[period_index])
                            / length_committed_b[period_index])
                    else:
                        percent_saved_b[period_index] = 0.0
        for index in sorted(length_committed, reverse=True):
            print(f'{period} {index:3}: '
                  f'{length_typed[index]:7} '
                  f'{length_committed[index]:7} '
                  f'{percent_saved[index]:6.4}% '
                  f'{length_typed_b[index]:7} '
                  f'{length_committed_b[index]:7} '
                  f'{percent_saved_b[index]:6.4}%')

    def print_user_freq_distribution(self) -> None:
        user_freqs: Dict[int, int] = {}
        for row in self._original_rows:
            user_freq = row[5]
            if user_freq in user_freqs:
                user_freqs[user_freq] += 1
            else:
                user_freqs[user_freq] = 1
        for count in sorted(user_freqs):
            print(f'{count:7}: {user_freqs[count]}')

    def _print_row(self,
                   row: Tuple[int, str, str, str, str, int, float],
                   prefix='') -> None:
        print(f'{prefix}'
              f'{row[0]:7} ' # id
              f'{row[5]:7} ' # user_freq
              f'{time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(row[6]))}' # timestamp
              f'{str(row[6]-int(row[6]))[1:8]} ' # fractional seconds part of timestamp
              f'{repr(row[4])} ' # pp_phrase
              f'{repr(row[3])} ' # p_phrase
              f'{repr(row[1])} ' # input_phrase
              f'{repr(row[2])} ' # phrase
              )

    def dump(self) -> None:
        for row in self._original_rows:
            self._print_row(row)

    def sort_by_time_ascending(self) -> None:
        self._original_rows = sorted(self._original_rows,
                                     key = lambda x: (
                                         x[6], # timestamp
                                         x[0], # id
                                     ))

    def sort_by_user_freq_time_ascending(self) -> None:
        self._original_rows = sorted(self._original_rows,
                                     key = lambda x: (
                                         x[5], # user_freq
                                         x[6], # timestamp
                                         x[0], # id
                                     ))

if __name__ == '__main__':
        dbcontents = DbContents(user_db_file=_ARGS.file,
                                verbose=_ARGS.verbose,
                                max_rows=_ARGS.max_rows)
        dbcontents.sort_by_user_freq_time_ascending()
        if _ARGS.rows:
            dbcontents.dump()
        dbcontents.print_savings(_ARGS.period)
        if _ARGS.user_freq_distribution:
            dbcontents.print_user_freq_distribution()
        if _ARGS.time_oldest:
            dbcontents.print_time_oldest()
        if _ARGS.time_newest:
            dbcontents.print_time_newest()
        if _ARGS.time_now:
            dbcontents.print_time_now()
        if _ARGS.decay:
            dbcontents.print_decay()
        if _ARGS.total_rows:
            dbcontents.print_total_rows()

