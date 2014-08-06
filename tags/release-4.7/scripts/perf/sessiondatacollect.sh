#!/bin/sh
# (c)2010-2012 the Boeing Company
# author: Yueli Yang <yueli.yang@boeing.com>
#
# Create a tar ball of the CORE session's runtime folder /tmp/pycore.nnnn
# Collection such runtime tar balls from all distributed servers to folder
# /tmp/<sessionid>-<date>-<time> for example: /tmp/56779-11Oct14-09:33:13

currentdir=` pwd `
sid=${currentdir##*.}
ts=` date +%y%h%d-%T `
logfile=/tmp/corelog.tgz
echo Collect data from localhost:$currentdir to $logfile
cd ..
tar -czf $logfile ${currentdir##*/}
if [ ! $? = 0 ]; then
    echo Failed to collect CORE data from localhost:$currentdir to $logfile
fi
cd $currentdir

m=` grep master $currentdir/servers `
if [ ! $sid = ${m##*=} ]; then
   # quite if this is not a master server
   echo not a master server
   exit
fi

# On a master server, create a folder to harvest overall core emulation data
logdir=/tmp/$sid-$ts
if [ ! -e $logdir ]; then
    echo create folder $logdir 
    mkdir $logdir
fi
cp $logfile $logdir/localhost-${currentdir##*.}.tgz

# harvest CORE data from distributed servers
hs=` grep -v master= $currentdir/servers | awk {'print $2'} `
echo hosts are localhost $hs
for h in $hs; do
    echo checking host $h ...
    out=` ping -c 1 -w 1 $h | grep " 0 received," `
    if [ " $out " = "  " ]; then
        slavesid=` ssh $h tar -tzf $logfile | awk -F / {'print $1'} `
        if [ $? = 0 ]; then
            destlogfile=$logdir/$h-${slavesid##*.}.tgz
            echo Collect data from $h:$logfile to $destlogfile
            scp $h:$logfile $destlogfile
        else
            echo $logfile could not be found on host $h
        fi
    fi
done
