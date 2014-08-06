#!/bin/sh
# Below is a transcript of creating two emulated nodes and connecting them 
# together with a wired link. You can run the core-cleanup script to clean
# up after this script.

# create node 1 namespace container
vnoded -c /tmp/n1.ctl -l /tmp/n1.log -p /tmp/n1.pid
# create a virtual Ethernet (veth) pair, installing one end into node 1
ip link add name n1.0.1 type veth peer name n1.0
ip link set n1.0 netns `cat /tmp/n1.pid`
vcmd -c /tmp/n1.ctl -- ip link set n1.0 name eth0
vcmd -c /tmp/n1.ctl -- ifconfig eth0 10.0.0.1/24 

# create node 2 namespace container
vnoded -c /tmp/n2.ctl -l /tmp/n2.log -p /tmp/n2.pid
# create a virtual Ethernet (veth) pair, installing one end into node 2
ip link add name n2.0.1 type veth peer name n2.0
ip link set n2.0 netns `cat /tmp/n2.pid`
vcmd -c /tmp/n2.ctl -- ip link set n2.0 name eth0
vcmd -c /tmp/n2.ctl -- ifconfig eth0 10.0.0.2/24 

# bridge together nodes 1 and 2 using the other end of each veth pair
brctl addbr b.1.1
brctl setfd b.1.1 0
brctl addif b.1.1 n1.0.1
brctl addif b.1.1 n2.0.1
ip link set n1.0.1 up
ip link set n2.0.1 up
ip link set b.1.1 up

# display connectivity and ping from node 1 to node 2
brctl show
vcmd -c /tmp/n1.ctl -- ping 10.0.0.2
