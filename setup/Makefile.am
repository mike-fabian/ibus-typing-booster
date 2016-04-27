# vim:set noet ts=4:
#
# ibus-typing-booster - Table Engine for ibus
#
# Copyright (c) 2011-2012 Anish Patil <apatil@redhat.com>
# Copyright (c) 2011-2012 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#  This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#  You should have received a copy of the GNU General Public License 
# along with this program.  If not, see <http://www.gnu.org/licenses/>

libexec_SCRIPTS = ibus-setup-typing-booster

desktop_in_in_files = ibus-setup-typing-booster.desktop.in.in

desktop_in_files = $(desktop_in_in_files:.in.in=.in)

ibus-setup-typing-booster.desktop: ibus-setup-typing-booster.desktop.in.in
	( \
		PKGDATADIR=$(pkgdatadir); \
		LIBEXECDIR=$(libexecdir); \
		s=`cat $<`; \
		eval "echo \"$${s}\""; \
	) > $@

desktopdir=$(datadir)/applications
desktop_DATA = $(desktop_in_files:.desktop.in=.desktop)


setup_typing_booster_PYTHON = \
	i18n.py \
	main.py \
	pkginstall.py \
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
	$(desktop_DATA) \
	$(desktop_in_files) \
	*.pyc \
	$(NULL)

EXTRA_DIST = \
	$(setup_typing_booster_built_in_files) \
	$(desktop_in_in_files) \
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

