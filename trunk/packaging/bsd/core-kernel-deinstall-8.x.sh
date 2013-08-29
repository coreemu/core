#!/bin/sh
PREV=""

if [ ! -e "/boot/kernel.old" ] ; then
  if [ ! -e "/boot/GENERIC" ] ; then
    echo Previous kernel does not exist in /boot/kernel.old or /boot/GENERIC !
    exit 1;
  else
    PREV="/boot/GENERIC"
  fi;
else
  PREV="/boot/kernel.old"
fi;

echo Removing current kernel...
chflags -R noschg /boot/kernel
rm -rf /boot/kernel
echo Restoring previous kernel from $PREV...
mv $PREV /boot/kernel

exit 0;
