#!/bin/sh
VER=0.0

# determine FreeBSD 4.11 or 8.x
REL=`uname -r`
case "$REL" in
    9.*)
	echo "Using FreeBSD 9.x..."
	KERN=9.x
	SCRIPTVER=8.x
	;;
    8.*)
	echo "Using FreeBSD 8.x..."
	KERN=8.x
	SCRIPTVER=8.x
	;;
    4.11-RELEASE)
	echo "Using FreeBSD 4.11..."
	KERN=4.11
	SCRIPTVER=4.11
	;;
    *)
	echo "What version of FreeBSD are you running (4.11/8.x) ?"
	exit 1
esac

if [ "a$1" = "a" ]
then
	echo "usage: ./core-kernel-release.sh 20080228 [clean]"
	echo a version number is required
	exit 1;
else
VER=$1
fi;

if [ "a$2" = "aclean" ]
then
	echo Cleaning up...
	rm -f core-kernel.pkglist.tmp
	rm -f core-kernel.pkglist
	rm -f core-kernel-${KERN}-${VER}.tbz
	exit
fi;


# check for /kernel.new on 4.11
if [ ${KERN} = "4.11" ]
then

if [ -e "/kernel.new" ]
then
  echo Note: proceeding using this kernel...
  ls -al /kernel.new
else
  echo "error: first copy the desired kernel to /kernel.new"
  exit
fi;

fi;



#
# build the packing list
#
echo @comment ORIGIN:net/core-kernel > core-kernel.pkglist
if [ ${KERN} = "4.11" ]
# FreeBSD 4.11
then
echo @cwd / >> core-kernel.pkglist
echo kernel.new >> core-kernel.pkglist
find /modules \! -type d > core-kernel.pkglist.tmp
find /sbin/vimage >> core-kernel.pkglist.tmp
find /usr/share/man/man8/vimage.8.gz >> core-kernel.pkglist.tmp
find /sbin/ngctl >> core-kernel.pkglist.tmp
find /usr/share/man/man8/ngctl.8.gz >> core-kernel.pkglist.tmp
# FreeBSD 8.x
else
echo @cwd /boot >> core-kernel.pkglist
PWDOLD=${PWD}
cd /boot
find kernel \! -type d > ${PWDOLD}/core-kernel.pkglist.tmp
cd ${PWDOLD}
echo @cwd / >> core-kernel.pkglist.tmp
find /usr/sbin/vimage >> core-kernel.pkglist.tmp
find /usr/share/man/man8/vimage.8.gz >> core-kernel.pkglist.tmp
fi;

# remove leading '/' from lines
sed -e "s,^/,," core-kernel.pkglist.tmp >> core-kernel.pkglist

#
# build the package
#
pkg_create -c core-kernel.pkgdesc -d core-kernel.pkgdesclong -f core-kernel.pkglist -i core-kernel-preinstall-${SCRIPTVER}.sh -K core-kernel-deinstall-${SCRIPTVER}.sh -v core-kernel-${KERN}-${VER}.tbz

