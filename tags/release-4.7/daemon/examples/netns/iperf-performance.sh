#!/bin/sh
#
# iperf-performance.sh
#
# (c)2013 the Boeing Company
# authors:    Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
# Utility script to automate several iperf runs.
#

# number of iperf runs per test
NUMRUNS=10
# number of seconds per run (10s is iperf default)
RUNTIME=10 
# logging
LOG=/tmp/${0}.log
STAMP=`date +%Y%m%d%H%M%S`

# 
#  client---(loopback)---server
#
loopbacktest () {
  killall iperf 2> /dev/null

  echo ">> loopback iperf test"
  echo "loopback" > ${LOG}

  # start an iperf server in the background
  # -s    = server
  # -y c  = CSV output
  echo "starting local iperf server"
  iperf -s -y c >> ${LOG} &
  
  # run an iperf client NUMRUNS times
  i=1
  while [ $i -le $NUMRUNS ]; do
      echo "run $i/$NUMRUNS:"
      iperf -t ${RUNTIME} -c localhost
      sleep 0.3
      i=$((i+1))
  done
  
  sleep 1
  echo "stopping local iperf server"
  killall -v iperf
  
}

#
#  lxc1( client )---veth-pair---lxc2( server )
#
lxcvethtest () {
  SERVERIP=10.0.0.1
  CLIENTIP=10.0.0.2
  SERVER=/tmp/${0}-server
  CLIENT=/tmp/${0}-client

  echo ">> lxc veth iperf test"
  echo "lxcveth" >> ${LOG}

  echo "starting lxc iperf server"
  vnoded -l $SERVER.log -p $SERVER.pid -c $SERVER
  ip link add name veth0.1 type veth peer name veth0
  ip link set veth0 netns `cat $SERVER.pid`
  vcmd -c $SERVER -- ifconfig veth0 $SERVERIP/24
  vcmd -c $SERVER -- iperf -s -y c >> ${LOG} &

  echo "starting lxc iperf client"
  vnoded -l $CLIENT.log -p $CLIENT.pid -c $CLIENT
  ip link set veth0.1 netns `cat $CLIENT.pid`
  vcmd -c $CLIENT -- ifconfig veth0.1 $CLIENTIP/24

  i=1
  while [ $i -le $NUMRUNS ]; do
      echo "run $i/$NUMRUNS:"
      vcmd -c $CLIENT -- iperf -t ${RUNTIME} -c ${SERVERIP}
      sleep 0.3
      i=$((i+1))
  done
  
  sleep 1
  echo "stopping lxc iperf server"
  vcmd -c $SERVER -- killall -v iperf
  echo "stopping containers"
  kill -9 `cat $SERVER.pid`
  kill -9 `cat $CLIENT.pid`

  echo "cleaning up"
  rm -f ${SERVER}*
  rm -f ${CLIENT}*
}

#
#  lxc1( client veth:):veth---bridge---veth:(:veth server )lxc2
#
lxcbrtest () {
  SERVERIP=10.0.0.1
  CLIENTIP=10.0.0.2
  SERVER=/tmp/${0}-server
  CLIENT=/tmp/${0}-client
  BRIDGE="lxcbrtest"

  echo ">> lxc bridge iperf test"
  echo "lxcbr" >> ${LOG}

  echo "building bridge"
  brctl addbr $BRIDGE
  brctl stp   $BRIDGE off  # disable spanning tree protocol
  brctl setfd $BRIDGE 0  # disable forwarding delay
  ip link set $BRIDGE up

  echo "starting lxc iperf server"
  vnoded -l $SERVER.log -p $SERVER.pid -c $SERVER
  ip link add name veth0.1 type veth peer name veth0
  ip link set veth0 netns `cat $SERVER.pid`
  vcmd -c $SERVER -- ifconfig veth0 $SERVERIP/24
  brctl addif $BRIDGE veth0.1
  ip link set veth0.1 up
  vcmd -c $SERVER -- iperf -s -y c >> ${LOG} &

  echo "starting lxc iperf client"
  vnoded -l $CLIENT.log -p $CLIENT.pid -c $CLIENT
  ip link add name veth1.1 type veth peer name veth1
  ip link set veth1 netns `cat $CLIENT.pid`
  vcmd -c $CLIENT -- ifconfig veth1 $CLIENTIP/24
  brctl addif $BRIDGE veth1.1
  ip link set veth1.1 up

  i=1
  while [ $i -le $NUMRUNS ]; do
      echo "run $i/$NUMRUNS:"
      vcmd -c $CLIENT -- iperf -t ${RUNTIME} -c ${SERVERIP}
      sleep 0.3
      i=$((i+1))
  done
  
  sleep 1
  echo "stopping lxc iperf server"
  vcmd -c $SERVER -- killall -v iperf
  echo "stopping containers"
  kill -9 `cat $SERVER.pid`
  kill -9 `cat $CLIENT.pid`
 
  echo "cleaning up"
  ip link set $BRIDGE down
  brctl delbr $BRIDGE
  rm -f ${SERVER}*
  rm -f ${CLIENT}*
}

#
#  n1---n2---n3--- ... ---nN
#       N nodes (N-2 hops) in chain with static routing
#
chaintest () {
  NUMNODES=$1
  SERVERIP=10.83.$NUMNODES.1

  if [ -d /tmp/pycore.* ]; then
      echo "/tmp/pycore.* already exists, skipping chaintest $NUMNODES"
      return
  fi

  echo ">> n=$NUMNODES node chain iperf test"
  echo "chain$NUMNODES" >> ${LOG}

  echo "running external chain CORE script with '-n $NUMNODES'"
  python iperf-performance-chain.py -n $NUMNODES

  echo "starting lxc iperf server on node $NUMNODES"
  vcmd -c /tmp/pycore.*/n$NUMNODES -- iperf -s -y c >> ${LOG} &

  echo "starting lxc iperf client"
  i=1
  while [ $i -le $NUMRUNS ]; do
      echo "run $i/$NUMRUNS:"
      vcmd -c /tmp/pycore.*/n1 -- iperf -t ${RUNTIME} -c ${SERVERIP}
      sleep 0.3
      i=$((i+1))
  done
  
  sleep 1
  echo "stopping lxc iperf server"
  vcmd -c /tmp/pycore.*/n$NUMNODES -- killall -v iperf
  echo "cleaning up"
  core-cleanup
}
if [ "z$1" != "z" ]; then
  echo "This script takes no parameters and must be run as root."
  exit 1
fi
if [ `id -u` != 0 ]; then
  echo "This script must be run as root."
  exit 1
fi


#
#  N lxc clients >---bridge---veth:(:veth server )
#
clientstest () {
  NUMCLIENTS=$1
  SERVERIP=10.0.0.1
  SERVER=/tmp/${0}-server
  BRIDGE="lxcbrtest"

  echo ">> n=$NUMCLIENTS clients iperf test"
  echo "clients$NUMCLIENTS" >> ${LOG}

  echo "building bridge"
  brctl addbr $BRIDGE
  brctl stp   $BRIDGE off  # disable spanning tree protocol
  brctl setfd $BRIDGE 0  # disable forwarding delay
  ip link set $BRIDGE up

  echo "starting lxc iperf server"
  vnoded -l $SERVER.log -p $SERVER.pid -c $SERVER
  ip link add name veth0.1 type veth peer name veth0
  ip link set veth0 netns `cat $SERVER.pid`
  vcmd -c $SERVER -- ifconfig veth0 $SERVERIP/24
  brctl addif $BRIDGE veth0.1
  ip link set veth0.1 up
  vcmd -c $SERVER -- iperf -s -y c >> ${LOG} &

  i=1
  CLIENTS=""
  while [ $i -le $NUMCLIENTS ]; do
      echo "starting lxc iperf client $i/$NUMCLIENTS"
      CLIENT=/tmp/${0}-client$i
      CLIENTIP=10.0.0.1$i
      vnoded -l $CLIENT.log -p $CLIENT.pid -c $CLIENT
      ip link add name veth1.$i type veth peer name veth1
      ip link set veth1 netns `cat $CLIENT.pid`
      vcmd -c $CLIENT -- ifconfig veth1 $CLIENTIP/24
      brctl addif $BRIDGE veth1.$i
      ip link set veth1.$i up
      i=$((i+1))
      CLIENTS="$CLIENTS $CLIENT"
  done

  j=1
  while [ $j -le $NUMRUNS ]; do
      echo "run $j/$NUMRUNS iperf:"
      for CLIENT in $CLIENTS; do
          vcmd -c $CLIENT -- iperf -t ${RUNTIME} -c ${SERVERIP} &
      done
      sleep ${RUNTIME} 1
      j=$((j+1))
  done
  
  sleep 1
  echo "stopping lxc iperf server"
  vcmd -c $SERVER -- killall -v iperf
  echo "stopping containers"
  kill -9 `cat $SERVER.pid`
  for CLIENT in $CLIENTS; do
      kill -9 `cat $CLIENT.pid`
  done
  # time needed for processes/containers to shut down
  sleep 2
 
  echo "cleaning up"
  ip link set $BRIDGE down
  brctl delbr $BRIDGE
  rm -f ${SERVER}*
  rm -f /tmp/${0}-client*
  # time needed for bridge clean-up
  sleep 1
}

#
# run all tests
#
loopbacktest
lxcvethtest
lxcbrtest
chaintest 5
chaintest 10
clientstest 5
clientstest 10
clientstest 15

mv ${LOG} ${PWD}/${0}-${STAMP}.log
echo "===> results in ${PWD}/${0}-${STAMP}.log"
