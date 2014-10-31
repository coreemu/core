#
# CORE
# Copyright (c)2014 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Stuart Marsden
#          Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
''' Docker service allows running docker containers within CORE nodes.

The running of Docker within a CORE node allows for additional extensibility to
the CORE services. This allows network applications and protocols to be easily
packaged and run on any node.

This service that will add a new group to the services list. This
will have a service called Docker which will just start the docker service
within the node but not run anything. It will also scan all docker images on
the host machine. If any are tagged with 'core' then they will be added as a
service to the Docker group. The image will then be auto run if that service is
selected.

This requires a recent version of Docker. This was tested using a PPA on Ubuntu
 with version 1.2.0. The version in the standard Ubuntu repo is to old for 
this purpose (we need --net host).

It also requires docker-py (https://pypi.python.org/pypi/docker-py) which can be
installed with 'pip install docker-py'. This is used to interface with Docker
from the python service.

An example use case is to pull an image from Docker.com. A test image has been
uploaded for this purpose:

sudo docker pull stuartmarsden/multicastping

This downloads an image which is based on Ubuntu 14.04 with python and twisted.
It runs a simple program that sends a multicast ping and listens and records
any it receives.

In order for this to appear as a docker service it must be tagged with core.
Find out the id by running 'sudo docker images'. You should see all installed
images and the one you want looks like this:

stuartmarsden/multicastping    latest              4833487e66d2        20 hours
ago        487 MB

The id will be different on your machine so use it in the following command:

sudo docker tag 4833487e66d2 stuartmarsden/multicastping:core

This image will be listed in the services after we restart the core-daemon: 

sudo service core-daemon restart

You can set up a simple network with a number of PCs connected to a switch. Set
the stuartmarsden/multicastping service for all the PCs. When started they will
all begin sending Multicast pings. 

In order to see what is happening you can go in to the terminal of a node and
look at the docker log. Easy shorthand is:

docker logs $(docker ps -q)

Which just shows the log of the running docker container (usually just one per
node). I have added this as an observer node to my setup: Name: docker logs
Command: bash -c 'docker logs $(docker ps -q) | tail -20'

So I can just hover over to see the log which looks like this:

Datagram 'Client: Ping' received from ('10.0.0.20', 8005)
Datagram 'Client: Ping' received from ('10.0.5.21', 8005)
Datagram 'Client: Ping' received from ('10.0.3.20', 8005)
Datagram 'Client: Ping' received from ('10.0.4.20', 8005)
Datagram 'Client: Ping' received from ('10.0.4.20', 8005)
Datagram 'Client: Ping' received from ('10.0.1.21', 8005)
Datagram 'Client: Ping' received from ('10.0.4.21', 8005)
Datagram 'Client: Ping' received from ('10.0.4.21', 8005)
Datagram 'Client: Ping' received from ('10.0.5.20', 8005)
Datagram 'Client: Ping' received from ('10.0.0.21', 8005)
Datagram 'Client: Ping' received from ('10.0.3.21', 8005)
Datagram 'Client: Ping' received from ('10.0.0.20', 8005)
Datagram 'Client: Ping' received from ('10.0.5.21', 8005)
Datagram 'Client: Ping' received from ('10.0.3.20', 8005)
Datagram 'Client: Ping' received from ('10.0.4.20', 8005)
Datagram 'Client: Ping' received from ('10.0.4.20', 8005)
Datagram 'Client: Ping' received from ('10.0.1.21', 8005)
Datagram 'Client: Ping' received from ('10.0.4.21', 8005)
Datagram 'Client: Ping' received from ('10.0.4.21', 8005)
Datagram 'Client: Ping' received from ('10.0.5.20', 8005)

Limitations:

1. Docker images must be downloaded on the host as usually a CORE node does not 
   have access to the internet.
2. Each node isolates running containers (keeps things simple)
3. Recent version of docker needed so that --net host can be used. This does 
   not further abstract the network within a node and allows multicast which 
   is not enabled within Docker containers at the moment.
4. The core-daemon must be restarted for new images to show up.
5. A Docker-daemon is run within each node but the images are shared. This
   does mean that the daemon attempts to access an SQLlite database within the
   host. At startup all the nodes will try to access this and it will be locked
   for most due to contention. The service just does a hackish wait for 1 second
   and retry. This means all the docker containers can take a while to come up
   depending on how many nodes you have.  

'''

import os
import sys
try:
    from docker import Client
except Exception:
    pass

from core.service import CoreService, addservice
from core.misc.ipaddr import IPv4Prefix, IPv6Prefix

class DockerService(CoreService):
    ''' This is a service which will allow running docker containers in a CORE
        node. 
    '''
    _name = "Docker"
    _group = "Docker"
    _depends = ()
    _dirs = ('/var/lib/docker/containers/', '/run/shm', '/run/resolvconf',)
    _configs = ('docker.sh', )
    _startindex = 50
    _startup = ('sh docker.sh',)
    _shutdown = ('service docker stop', )
    # Container image to start
    _image = ""

    @classmethod
    def generateconfig(cls, node, filename, services):
        ''' Returns a string having contents of a docker.sh script that
            can be modified to start a specific docker image.
        '''
        cfg = "#!/bin/sh\n"
        cfg += "# auto-generated by Docker (docker.py)\n"
        # Docker likes to think it has DNS set up or it complains. 
        #   Unless your network was attached to the Internet this is
        #   non-functional but hides error messages.
        cfg += 'echo "nameserver 8.8.8.8" > /run/resolvconf/resolv.conf\n'
        # Starts the docker service. In Ubuntu this is docker.io; in other
        #   distros may just be docker
        cfg += 'service docker start\n'
        cfg += "# you could add a command to start a image here eg:\n"
        if not cls._image:
            cfg += "# docker run -d --net host --name coreDock <imagename>\n"
        else:
            cfg += """\
result=1
until [ $result -eq 0 ]; do
  docker run -d --net host --name coreDock %s
  result=$?
  # this is to alleviate contention to docker's SQLite database
  sleep 0.3
done
""" % (cls._image, )
        return cfg

addservice(DockerService)

# This auto-loads Docker images having a :core tag, adding them to the list
# of services under the "Docker" group.
if 'Client' in globals():
    client = Client(version='1.10')
    images = client.images()
    del client
else:
    images = []
for image in images:
    if u'<none>' in image['RepoTags'][0]:
        continue
    for repo in image['RepoTags']:
        if u':core' not in repo:
            continue
        dockerid = repo.encode('ascii','ignore').split(':')[0]
        SubClass = type('SubClass', (DockerService,),
                        {'_name': dockerid, '_image': dockerid})
        addservice(SubClass)
del images
