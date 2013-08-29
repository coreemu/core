#!/bin/sh

VER=`grep -m 1 "set CORE_VERSION" ../../gui/version.tcl | awk '{ print $3 }'`
ARCH=`uname -m`
# determine FreeBSD 4.11 or 7.x
REL=`uname -r`
case "$REL" in
    9.*)
	echo "Using FreeBSD 9.x..."
	KERN=9.x
	;;
    8.*)
	echo "Using FreeBSD 8.x..."
	KERN=8.x
	;;
    4.11-RELEASE)
	echo "Using FreeBSD 4.11..."
	KERN=4.11
	;;
    *)
	echo "What version of FreeBSD are you running (4.11/8.x) ?"
	exit 1
esac

if [ "a$1" = "aclean" ]
then
	echo Cleaning up...
	rm -f core.pkglist.tmp
	rm -f core.pkglist
	rm -f core-${KERN}-${VER}.tbz
	rm -rf /tmp/staging
	exit
fi;


#
# build the packing list
#
echo @comment ORIGIN:net/core > core.pkglist
echo @cwd /usr/local >> core.pkglist
PKG_BASH=`pkg_info -E -x ^bash`
# for 4.11 change this back to 8.4
PKG_TCL=`pkg_info -E -x ^tcl-8.5`
PKG_TK=`pkg_info -E -x ^tk-8.5`
echo @pkgdep ${PKG_BASH} >> core.pkglist
echo @comment DEPORIGIN:shells/bash >> core.pkglist
echo @pkgdep ${PKG_TCL} >> core.pkglist
echo @comment DEPORIGIN:lang/tcl85 >> core.pkglist
echo @pkgdep ${PKG_TK} >> core.pkglist
echo @comment DEPORIGIN:x11-toolkits/tk85 >> core.pkglist

SAVEDIR=`pwd`
cd ../..
rm -rf /tmp/staging
gmake DESTDIR=/tmp/staging install
cd $SAVEDIR
find /tmp/staging/usr/local \! -type d >> core.pkglist
echo @cwd /etc >> core.pkglist
find /tmp/staging/etc \! -type d >> core.pkglist
sed -e "s,^/tmp/staging/usr/local/,," core.pkglist > core.pkglist.new1
sed -e "s,^/tmp/staging/etc/,," core.pkglist.new1 > core.pkglist
rm -f core.pkglist.new1

#
# build the package
#
pkg_create -c core.pkgdesc -d core.pkgdesclong -f core.pkglist -v core-${KERN}-${ARCH}-${VER}.tbz

