#!/bin/sh
#
# (c)2010-2012 the Boeing Company
#
# author:	Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
# Bootstrap the autoconf system.
#

# PASS
if [ x$1 = x ]; then
  echo "Bootstrapping the autoconf system..."
  echo "(Messages below about copying and installing files are normal.)"
# clean - take out the trash
elif [ x$1 = xclean ]; then
  echo "Cleaning up the autoconf mess..."
  rm -rf autom4te.cache config
  exit 0;
# help text
else
  echo "usage: $0 [clean]"
  echo -n "  Use this script to bootstrap the autoconf build system prior to "
  echo "running the "
  echo "  ./configure script."
  exit 1;
fi

# try to keep everything nice and tidy in ./config
if ! [ -d "config" ]; then
  mkdir config
fi

# bootstrapping
echo "(1/4) Running aclocal..." && aclocal -I config \
  && echo "(2/4) Running autoheader..." && autoheader \
  && echo "(3/4) Running automake..." \
	&& automake --add-missing --copy --foreign \
  && echo "(4/4) Running autoconf..." && autoconf \
  && echo "" \
  && echo "You are now ready to run \"./configure\"."
