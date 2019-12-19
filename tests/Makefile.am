# vim:set noet ts=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2016 Mike FABIAN <mfabian@redhat.com>
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

TESTS = run_tests

run_tests: run_tests.in
	sed -e 's&@PYTHON_BIN@&$(PYTHON)&g' \
	    -e 's&@SRCDIR@&$(srcdir)&g' $< > $@
	chmod +x $@

EXTRA_DIST = \
	__init__.py \
	mock_engine.py \
	run_tests.in \
	test_compose_sequences.py \
	test_emoji_candidates.py \
	test_emoji_similar.py \
	test_emoji_unicode_version.py \
	test_hunspell_suggest.py \
	test_itb.py \
	test_keyvals_to_keycodes.py \
	test_m17n_db_info.py \
	test_m17n_translit.py \
	$(NULL)

CLEANFILES = \
	run_tests \
	$(NULL)

MAINTAINERCLEANFILES = \
	Makefile.in \
	$(NULL)
