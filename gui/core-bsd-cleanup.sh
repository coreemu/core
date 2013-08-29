#!/bin/sh
#
# cleanup.sh
#
# Copyright 2005-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# Removes leftover netgraph nodes and vimages from an emulation that
# did not exit properly.
#

ngnodes="pipe eiface hub switch wlan"
vimages=`vimage -l | fgrep -v "    " | cut -d: -f 1 | sed s/\"//g`

# shutdown netgraph nodes
for ngn in $ngnodes
do
	nodes=`ngctl list | grep $ngn | awk '{print $2}'`
	for n in $nodes
	do
		echo ngctl shutdown $n:
		ngctl shutdown $n:
	done
done

# kills processes and remove vimages
for vimage in $vimages
do
    procs=`vimage $vimage ps x | awk '{print $1}'`
    for proc in $procs
    do
	if [ $proc != "PID" ]
	then
	echo vimage $vimage kill $proc
	vimage $vimage kill $proc
	fi
    done
    loopback=`vimage $vimage ifconfig -a | head -n 1 | awk '{split($1,a,":"); print a[1]}'`
    if [ "$loopback" != "" ]
    then
	addrs=`ifconfig $loopback | grep inet | awk '{print $2}'`
	for addr in $addrs
	do
		echo vimage $vimage ifconfig $loopback $addr -alias
		vimage $vimage ifconfig $loopback $addr -alias
		if [ $? != 0 ]
		then
		    vimage $vimage ifconfig $loopback inet6 $addr -alias
		fi
	done
    	echo vimage $vimage ifconfig $loopback down
    	vimage $vimage ifconfig $loopback down
    fi
    vimage $vimage kill -9 -1 2> /dev/null
    echo vimage -d $vimage
    vimage -d $vimage
done

# clean up temporary area
rm -rf /tmp/pycore.*
