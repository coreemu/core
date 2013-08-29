#!/bin/sh

if [ "x$2" = "xPOST-INSTALL" ]
then
  install -m 555 -o root -g wheel -fschg /kernel.new /kernel
  rm -f /kernel.new
  echo Please reboot this machine to enable the new CORE kernel.
  exit 0;
fi;

install -m 555 -o root -g wheel -fschg /kernel /kernel.old
if [ -e /modules.old ]
then
  rm -rf /modules.old
fi;

mv /modules /modules.old
exit 0;
