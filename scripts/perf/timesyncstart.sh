#!/bin/sh
# (c)2010-2012 the Boeing Company
# author: Yueli Yang <yueli.yang@boeing.com>
#
# start time sync with ntpd if it is installed but not started
#
# Usage: sudo timesyncstart.sh [debug]

dbg=$1
if [ "$dbg" = "debug" ]; then
    date +%y%h%d-%T-%N
fi
if [ -e /usr/sbin/ntpd ]; then
   /etc/init.d/ntp status
   if [ $? = 3 ]; then
      /etc/init.d/ntp start
      if [ "$dbg" = "debug" ]; then
         echo "start ntpd process"
         ntptime
         ntpq -c peers
      fi
   fi
fi
if [ "$dbg" = "debug" ]; then
    date +%y%h%d-%T-%N
fi
