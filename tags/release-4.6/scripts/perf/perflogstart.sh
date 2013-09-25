#!/bin/sh
# (c)2010-2012 the Boeing Company
# author: Yueli Yang <yueli.yang@boeing.com>
#
# start core performance logging and collect output to file 
# /tmp/pycore.nnnn/perf<sessionid>.log
HOOKS_DIR=`dirname $0`

sid=` pwd | awk -F / {'print $3'} | awk -F . {'print $2'} `
python $HOOKS_DIR/perflogserver.py -t -a -c /etc/core/perflogserver.conf -s $sid > perf$sid.log &
