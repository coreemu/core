#!/bin/sh
# (c)2010-2012 the Boeing Company
# author: Yueli Yang <yueli.yang@boeing.com>
#
# Stop timesync service. If it was not yet in sync with any ntp server,
# adjust its time to the first ntp server in # configured in /etc/ntp.conf 
#
# Usage: sudo sh timesyncstop.sh [deubg]

dbg=$1
if [ "$dbg" = "debug" ]; then
    date +%y%h%d-%T-%N
fi
svs=""
if [ -e /usr/sbin/ntpd ]; then
   # command "sudo /usr/sbin/ntpd -q -g"  will start the ntp service and 
   # keep it on until it performs a good synchronization, then it leaves.
   # It is not quick enough for our need here
   /etc/init.d/ntp status
   if [ $? = 0 ]; then
      svs=`ntpq -c peers | awk {'print $1'} | grep ^*`
      if [ "$dbg" = "debug" ]; then
          ntpq -c peers
          echo "get time servers for later need: $svs"
          ntptime
          echo "terminate ntpd process"
      fi 
      /etc/init.d/ntp stop
   fi

   # if there are time servers configured in file /etc/ntp.conf, 
   # adjust time to the first server
   if [ "$svs" = "" ]; then
      svs=`grep ^server /etc/ntp.conf | awk {'print $2'} `
      if [ "$dbg" = "debug" ]; then
          echo "$svs"
      fi
      for sv in "$svs"; do
          ntpdate $sv  
          # may use "sntp -s $sv" or "rdate" if ntpdate is deprecated
          break
      done
   else
      if [ "$dbg" = "debug" ]; then
         echo No time adjustment because time sync was stable with $svs
      fi
   fi
fi
if [ "$dbg" = "debug" ]; then
    date +%y%h%d-%T-%N
fi
