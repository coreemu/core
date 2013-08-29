#!/bin/sh
# (c)2010-2012 the Boeing Company
# author: Yueli Yang <yueli.yang@boeing.com>
#
# terminate core perfromance logging process

perfproc=` ps aux | grep perflogserver | grep python | awk {'print $2'} `
if [ ! $perfproc = "" ]; then
     echo "terminating core performance log process $perfproc"
     kill -9 $perfproc 
fi
