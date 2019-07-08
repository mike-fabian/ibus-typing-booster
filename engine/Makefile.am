# vim:set noet ts=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2011-2012 Anish Patil <apatil@redhat.com>
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

desktop_in_in_files = emoji-picker.desktop.in.in

desktop_in_files = $(desktop_in_in_files:.in.in=.in)

emoji-picker.desktop: emoji-picker.desktop.in.in
	( \
		PREFIX=$(prefix); \
		PKGDATADIR=$(pkgdatadir); \
		LIBEXECDIR=$(libexecdir); \
		s=`cat $<`; \
		eval "echo \"$${s}\""; \
	) > $@

desktopdir=$(datadir)/applications
desktop_DATA = $(desktop_in_files:.desktop.in=.desktop)

engine_table_PYTHON = \
	factory.py \
	main.py \
	hunspell_table.py \
	hunspell_suggest.py \
	tabsqlitedb.py \
	itb_util.py \
	itb_emoji.py \
	itb_nltk.py \
	itb_pango.py \
	m17n_translit.py \
	emoji_picker.py \
	itb_version.py \
	tabstatistics.py \
	$(NULL)
engine_table_DATA = \
	$(NULL)
engine_tabledir = $(datadir)/ibus-typing-booster/engine

bin_SCRIPTS = emoji-picker

libexec_SCRIPTS = ibus-engine-typing-booster

engine_DATA = typing-booster.xml
enginedir = $(datadir)/ibus/component

EXTRA_DIST = \
	itb_version.py.in \
	ibus-engine-typing-booster.in \
	typing-booster.xml.in \
	emoji-picker.in \
	$(desktop_in_in_files) \
	$(NULL)

CLEANFILES = \
	*.pyc \
	*.pyo \
	ibus-engine-typing-booster \
	typing-booster.xml \
	emoji-picker \
	$(desktop_DATA) \
	$(desktop_in_files) \
	$(NULL)

MAINTAINERCLEANFILES = \
	Makefile.in \
	$(NULL)

typing-booster.xml: typing-booster.xml.in
	( \
		libexecdir=${libexecdir}; \
		pkgdatadir=${pkgdatadir}; \
		s=`cat $<`; \
		eval "echo \"$${s}\""; \
	) > $@

test:
	$(ENV) \
		IBUS_TYPING_BOOSTER_LOCATION=$(abs_top_srcdir) \
		DBUS_DEBUG=true \
		LANG=en_US \
		PYTHONPATH=$(abs_top_srcdir) \
		$(PYTHON) $(srcdir)/main.py

