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

TESTS = \
	test_0_gtk.py \
	test_compose_sequences.py \
	test_emoji_candidates.py \
	test_emoji_similar.py \
	test_emoji_unicode_version.py \
	test_hunspell_suggest.py \
	test_itb.py \
	test_itb_m17n_emulation.py \
	test_itb_pango.py \
	test_itb_util.py \
	test_keyvals_to_keycodes.py \
	test_m17n_db_info.py \
	test_m17n_translit.py \
	test_tabsqlitedb.py \
	$(NULL)

check_SCRIPTS = run_tests

LOG_COMPILER = $(builddir)/run_tests

TESTS_ENVIRONMENT = \
	IBUS_TYPING_BOOSTER_LOCATION=../

test_meta_in = meta.test.in
test_metas =

if ENABLE_INSTALLED_TESTS
test_metas += $(patsubst %.py, %.test, $(TESTS))
test_source_DATA = $(test_metas)
test_sourcedir = $(datadir)/installed-tests/ibus-typing-booster
test_exec_SCRIPTS = \
	$(TESTS) \
	gtkcases.py \
	mock_engine.py \
	testutils.py \
	run_tests \
	chant_d_automne.txt \
	the_road_not_taken.txt \
	test-issue-707.mim \
	$(NULL)
test_execdir = $(libexecdir)/installed-tests/ibus-typing-booster

$(test_metas): $(test_meta_in)
	@TEST_EXEC=`echo $@ | sed -e 's&\.test&\.py&'`; \
	sed -e "s&@TEST_EXECDIR@&$(test_execdir)&g" \
	    -e "s&@TEST_EXEC@&$$TEST_EXEC&g" $< > $@.tmp; \
	mv $@.tmp $@; \
	$(NULL)
endif

run_tests: run_tests.in
	sed -e 's&@PYTHON_BIN@&$(PYTHON)&g' \
	    -e 's&@PKGDATADIR@&$(pkgdatadir)&g' \
	    -e 's&@SRCDIR@&$(srcdir)&g' $< > $@
	chmod +x $@

EXTRA_DIST = \
	$(test_meta_in) \
	__init__.py \
	gtkcases.py \
	mock_engine.py \
	testutils.py \
	run_tests.in \
	chant_d_automne.txt \
	the_road_not_taken.txt \
	test-issue-707.mim \
	$(TESTS) \
	$(NULL)

CLEANFILES = \
	$(test_metas) \
	run_tests \
	$(NULL)

MAINTAINERCLEANFILES = \
	Makefile.in \
	$(NULL)
