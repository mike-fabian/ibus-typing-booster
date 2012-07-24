# vim:set noet ts=4:
#
# ibus-typing-booster - Table Engine for ibus
#
# Copyright (c) 2011-2012 Anish Patil <apatil@redhat.com>
# Copyright (c) 2011-2012 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

libexec_SCRIPTS = ibus-setup-typing-booster

setup_typing_booster_PYTHON = \
	main.py \
	pkginstall.py \
	pref.py \
	setup.glade \
	$(NULL)

setup_typing_booster_built_files = \
	$(libexec_SCRIPTS) \
	$(NULL)

setup_typing_booster_built_in_files = $(addsuffix .in, $(setup_typing_booster_built_files))

setup_typing_boosterdir = $(datadir)/ibus-typing-booster/setup

CONFIG_CLEAN_FILES = \
	$(libexec_SCRIPTS) \
	$(NULL)

CLEANFILES = \
	*.pyc \
	$(NULL)

EXTRA_DIST = \
	$(setup_typing_booster_built_in_files) \
	$(NULL)

# Need a time lag between .py and .py.in files to build .py files
# because *_PYTHON valuables are installed in the tarball.
dist-hook:
	@sleep 1; \
	for in_file in $(setup_typing_booster_built_in_files) ; do \
	    if [ -f $(distdir)/$(srcdir)/$$in_file ] ; then \
	        touch $(distdir)/$(srcdir)/$$in_file; \
	    fi; \
	done;

test:
	$(ENV_IBUS_TEST) DBUS_DEBUG=true \
		   LANG=en_US \
		   PYTHONPATH=$(abs_top_srcdir):$(pyexecdir) \
		   IBUS_LOCALEDIR=@localedir@ \
		   $(PYTHON) $(srcdir)/main.py

