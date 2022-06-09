#!/bin/sh
set -e
set -x

autoreconf -fiv
./configure --enable-maintainer-mode $*
