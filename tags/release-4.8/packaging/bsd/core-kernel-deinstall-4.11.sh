#!/bin/sh

echo Restoring /kernel.old ...
install -m 555 -o root -g wheel -fschg /kernel.old /kernel
rm -rf /modules
mv /modules.old /modules

