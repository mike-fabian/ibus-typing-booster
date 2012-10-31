# vim:set noet ts=4
#
# ibus-hunspell-table - The Table engine for IBus
#
# Copyright (c) 2011-2012 Anish Patil <anish.developer@gmail.com>
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

DISTCHECK_CONFIGURE_FLAGS = \
	$(NULL)

SUBDIRS = \
	engine \
	icons \
	m4 \
	hunspell-tables \
	data \
	po \
	setup \
	$(NULL)

ACLOCAL_AMFLAGS = -I m4

pkgconfig_DATA = \
	ibus-typing-booster.pc \
	$(NULL)

pkgconfigdir = $(libdir)/pkgconfig

AUX_DIST = \
	config.guess \
	config.sub \
	install-sh \
	missing \
	py-compile \
	$(NULL)

MAINTAINERCLEANFILES = \
	Makefile.in \
	aclocal.m4 \
	configure \
	$(AUX_DIST) \
	$(NULL)


EXTRA_DIST = \
	config.rpath \
	autogen.sh \
	@PACKAGE_NAME@.spec \
	$(NULL)

noinst_DIST = \
	$(NULL)


#DISTCLEANFILES = \
#	po/stamp-it \
#	$(NULL)

rpm: dist @PACKAGE_NAME@.spec
	rpmbuild -bb \
			--define "_sourcedir `pwd`" \
			--define "_builddir `pwd`" \
			--define "_specdir `pwd`" \
			--define "_rpmdir `pwd`" \
			--define "_srcrpmdir `pwd`" \
			@PACKAGE_NAME@.spec

srpm: dist @PACKAGE_NAME@.spec
	rpmbuild -bs \
			--define "_sourcedir `pwd`" \
			--define "_builddir `pwd`" \
			--define "_srcrpmdir `pwd`" \
			--define "_rpmdir `pwd`" \
			--define "_specdir `pwd`" \
			@PACKAGE_NAME@.spec

clean-rpm:
	$(RM) -r "`uname -i`"

clean-local: clean-rpm
