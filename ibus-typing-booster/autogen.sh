#!/bin/sh
set -e
set -x

autopoint
aclocal -I m4
# autoheader
automake --add-missing --copy
autoconf
./configure --enable-maintainer-mode $*
