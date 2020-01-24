# vim:set noet ts=4
#
# ibus-typing-booster - A completion input method for IBus
#
# Copyright (c) 2011-2012 Anish Patil <anish.developer@gmail.com>
# Copyright (c) 2012-2018 Mike FABIAN <mfabian@redhat.com>
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
	data \
	data/annotations \
	data/annotationsDerived \
	po \
	setup \
	tests \
	$(NULL)

ACLOCAL_AMFLAGS = -I m4

# To register as an AppStream component to be visible in the software center
# (See http://www.freedesktop.org/software/appstream/docs/ for more details):
appdata_DATA = \
	typing-booster.appdata.xml \
	$(NULL)

appdatadir = $(datadir)/metainfo

schemas_DATA = \
	org.freedesktop.ibus.engine.typing-booster.gschema.xml
	$(NULL)

schemasdir = $(datadir)/glib-2.0/schemas/

install-data-hook:
	if test -z "$(DESTDIR)"; then \
	    glib-compile-schemas $(schemasdir); \
	fi

uninstall-hook:
	SCHEMAS_FILES=`ls $(schemasdir)/*.gschema.xml` || true;         \
	if test -z "$$SCHEMAS_FILES" &&                                 \
	    test -f $(schemasdir)/gschemas.compiled; then               \
	    rm $(schemasdir)/gschemas.compiled;                         \
	fi

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
	typing-booster.appdata.xml \
	$(schemas_DATA) \
	@PACKAGE_NAME@.spec.fedora \
	@PACKAGE_NAME@.spec.suse \
	README.html \
	README.md \
	$(NULL)

noinst_DIST = \
	$(NULL)


#DISTCLEANFILES = \
#	po/stamp-it \
#	$(NULL)


README: README.html
	w3m -cols 78 -o display_borders=1 -o display_link_number=1 $< > $@

README.html: README.md
	pandoc -f gfm -t html --standalone --self-contained --metadata pagetitle="IBus-typing-booster README" $< > $@

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
