# Process this file with autoconf to produce a configure script.
# vim:set et ts=4:
#
# ibus-typing-booster - The Tables engine for IBus
#
# Copyright (c) 20011-2012 Anish Patil <apatil@redhat.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# if not 1, append datestamp to the version number.
m4_define([package_name], [ibus-typing-booster])
m4_define([ibus_released], [1])
m4_define([ibus_major_version], [1])
m4_define([ibus_minor_version], [2])
m4_define([ibus_micro_version], [3])
m4_define(ibus_maybe_datestamp,
    m4_esyscmd([if test x]ibus_released[ != x1; then date +.%Y%m%d | tr -d '\n\r'; fi]))

m4_define([ibus_version],
    ibus_major_version.ibus_minor_version.ibus_micro_version[]ibus_maybe_datestamp)

AC_INIT([package_name], [ibus_version], [http://code.google.com/p/ibus/issues/entry], [package_name])
AM_INIT_AUTOMAKE([1.10])
AM_MAINTAINER_MODE
# AC_GNU_SOURCE

# AC_CONFIG_HEADERS([config.h])
AC_CONFIG_MACRO_DIR([m4])

#check python
AM_PATH_PYTHON([2.5])

# check for ibus
PKG_CHECK_MODULES([IBUS],[ibus-1.0 >= 1.1.0])

# define GETTEXT_* variables
GETTEXT_PACKAGE=ibus-typing-booster
AC_SUBST(GETTEXT_PACKAGE)
AC_DEFINE_UNQUOTED(GETTEXT_PACKAGE,"$GETTEXT_PACKAGE", [Define to the read-only architecture-independent data directory.])

AM_GNU_GETTEXT([external])
AM_GNU_GETTEXT_VERSION(0.16.1)

# ARGUMENTS
AC_ARG_ENABLE([additional],
    [AC_HELP_STRING([--disable-additional],
        [Dont generate additional Engine])], ,
    [enable_additional=yes])

AM_CONDITIONAL([IBUS_EUROPEAN_TABLE_BUILD_ADDITIONAL],[test x"$enable_additional" = x"yes"])

# OUTPUT files
AC_CONFIG_FILES([po/Makefile.in
    Makefile
    engine/Makefile
    engine/typing-booster.xml.in
    engine/ibus-engine-typing-booster
    setup/Makefile
    setup/ibus-setup-typing-booster
    data/Makefile
    icons/Makefile
    icons/additional/Makefile
    hunspell-tables/Makefile
    m4/Makefile
    ibus-typing-booster.spec
    ibus-typing-booster.pc]
)

AC_OUTPUT

AC_MSG_RESULT([
Build options:
  Version                   $VERSION
  Install prefix            $prefix
  Build Additional          $enable_additional
])
