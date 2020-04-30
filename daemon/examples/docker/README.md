# Docker Support

Information on how Docker can be leveraged and included to create
nodes based on Docker containers and images to interface with
existing CORE nodes, when needed.

## Installation

```shell
sudo apt install docker.io
```

## Configuration

Custom configuration required to avoid iptable rules being added and removing
the need for the default docker network, since core will be orchestrating
connections between nodes.

Place the file below in **/etc/docker/**
* daemon.json

## Group Setup

To use Docker nodes within the python GUI, you will need to make sure the user running the GUI is a member of the
docker group.

```shell
# add group if does not exist
sudo groupadd docker

# add user to group
sudo usermod -aG docker $USER

# to get this change to take effect, log out and back in or run the following
newgrp docker
```

## Tools and Versions Tested With

* Docker version 18.09.5, build e8ff056
* nsenter from util-linux 2.31.1

## Examples

This directory provides a few small examples creating Docker nodes
and linking them to themselves or with standard CORE nodes.
