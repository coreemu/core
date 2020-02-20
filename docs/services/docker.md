# Docker

* Table of Contents
{:toc}

## Overview

Docker service allows running docker containers within CORE nodes.
The running of Docker within a CORE node allows for additional extensibility to
the CORE services. This allows network applications and protocols to be easily
packaged and run on any node.

This service will add a new group to the services list. This will have a service called Docker which will just start the docker service within the node but not run anything. It will also scan all docker images on the host machine. If any are tagged with 'core' then they will be added as a service to the Docker group. The image will then be auto run if that service is selected.

This requires a recent version of Docker. This was tested using a PPA on Ubuntu with version 1.2.0. The version in the standard Ubuntu repo is to old for this purpose (we need --net host).

## Docker Installation

To use Docker services, you must first install the Docker python image. This is used to interface with Docker from the python service.

```shell
sudo apt-get install docker.io
sudo apt-get install python-pip
pip install docker-py
```
Once everything runs successfully, a Docker group under services will appear. An example use case is to pull an image from [Docker](https://hub.docker.com/). A test image has been uploaded for this purpose:
```shell
sudo docker pull stuartmarsden/multicastping
```
This downloads an image which is based on Ubuntu 14.04 with python and twisted. It runs a simple program that sends a multicast ping and listens and records any it receives. In order for this to appear as a docker service it must be tagged with core.
Find out the id by running 'sudo docker images'. You should see all installed images and the one you want looks like this:
```shell
stuartmarsden/multicastping    latest              4833487e66d2        20 hours
ago        487 MB
```
The id will be different on your machine so use it in the following command:
```shell
sudo docker tag 4833487e66d2 stuartmarsden/multicastping:core
```
This image will be listed in the services after we restart the core-daemon:
```shell
sudo service core-daemon restart
```
