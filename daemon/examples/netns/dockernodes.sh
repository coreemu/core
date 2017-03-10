#!/bin/sh -e
# Below is a transcript of creating two emulated nodes and connecting them 
# together with a wired link. It should cleanup after itself but you can run
# the core-cleanup script to make sure.
# This script connects a core emulated node to two docker containers set to
# be in the same node. The first time you run this if docker does not already have
# the images it will download it. This could take some time depending on your internet
# connection.

# create node 1 namespace container
nodeid=$(vnoded -c /tmp/n1.ctl -l /tmp/n1.log -p /tmp/n1.pid)
# create a virtual Ethernet (veth) pair, installing one end into node 1
ip link add name n1.0.1 type veth peer name n1.0
ip link set n1.0 netns `cat /tmp/n1.pid`
vcmd -c /tmp/n1.ctl -- /bin/sh -e -c \
    "ip link set lo up && ip link set n1.0 name eth0 up && ip addr add 10.0.0.1/24 dev eth0"

# create node 2 as a docker container
# This uses an image from docker hub with apache set up.
dockerid=$(docker run --net=none --cap-add=NET_ADMIN -d httpd)
dockerpid=$(docker inspect -f '{{.State.Pid}}' $dockerid)
# create a virtual Ethernet (veth) pair, installing one end into node 2
ip link add name n2.0.1 type veth peer name n2.0
ip link set n2.0 netns $dockerpid
docker exec -it $dockerid /bin/bash -c "/sbin/ip link set n2.0 name eth0 up && /sbin/ip addr add 10.0.0.2/24 dev eth0"

# create another docker container which will be added to node 2
# must use a different port so we use another docker hub image that responds on port 8080
# docker takes care of placing it in the same network namespace by providing the other container id
dockerid2=$(docker run -d --net=container:$dockerid google/nodejs-hello)

# bridge together nodes 1 and 2 using the other end of each veth pair
brctl addbr b.1.1
brctl setfd b.1.1 0
brctl addif b.1.1 n1.0.1
brctl addif b.1.1 n2.0.1
ip link set n1.0.1 up
ip link set n2.0.1 up
ip link set b.1.1 up

# Give the containers a little time to come up
sleep 2

# display connectivity and ping from node 1 to node 2
# Check the tow docker services run on node 2
brctl show
vcmd -c /tmp/n1.ctl -- curl http://10.0.0.2
vcmd -c /tmp/n1.ctl -- curl http://10.0.0.2:8080 && echo
vcmd -c /tmp/n1.ctl -- ping -c 5 10.0.0.2

# remove the links
ip link delete b.1.1
ip link delete n2.0.1
ip link delete n1.0.1

# Stop and remove the docker containers
docker stop $dockerid $dockerid2
docker rm $dockerid $dockerid2

# kill the vnoded
kill -9 $nodeid