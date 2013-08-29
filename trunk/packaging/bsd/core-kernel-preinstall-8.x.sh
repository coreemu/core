#!/bin/sh

if [ "x$2" = "xPOST-INSTALL" ]
then
  echo Please reboot this machine to enable the new CORE kernel.
  exit 0;
fi;

# PRE-INSTALL
# save the GENERIC kernel
OLDNAME=`strings /boot/kernel/kernel | tail -n 1`
if [ "x$OLDNAME" = "xGENERIC" ]
then
  chflags -R noschg /boot/kernel
  mv /boot/kernel /boot/GENERIC
  exit 0;
fi;
# get rid of /boot/kernel.old if it is in the way
if [ -e "/boot/kernel.old" ] ; then
  chflags -R noschg /boot/kernel.old
  rm -rf /boot/kernel.old
fi;

chflags -R noschg /boot/kernel
mv /boot/kernel /boot/kernel.old

exit 0;
