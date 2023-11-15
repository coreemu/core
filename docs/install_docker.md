# Overview

CORE can be installed into and ran from a Docker container. This section will cover how you can build and run
CORE from a Docker based image.

## Build Image

You can leverage one of the provided Dockerfiles to build a CORE based image. Since CORE nodes will leverage software
available within the system for a given use case, make sure to update and build the Dockerfile with desired software.

The example Dockerfiles are not meant to be an end all solution, but a solid starting point for running CORE.

Provided Dockerfiles:

* Dockerfile.centos - CentOS 7, CORE from source, OSPF MDR, and EMANE
* Dockerfile.centos-package - CentOS 7, CORE from local package, OSPF MDR, and EMANE
* Dockerfile.ubuntu - Ubuntu 22.04, CORE from source, OSPF MDR, and EMANE
* Dockerfile.ubuntu-package - Ubuntu 22.04, CORE from local package, OSPF MDR, and EMANE

```shell
# clone core
git clone https://github.com/coreemu/core.git
# build image
cd core
sudo docker build -t core -f dockerfiles/<Dockerfile> .
```

For the example files that build from source, you can have it build from develop or another branch.
```shell
sudo docker build -t core --build-arg BRANCH=develop -f dockerfiles/<Dockerfile> .
```

## Run Container

There are some required parameters when starting a CORE based Docker container for CORE to function properly. These
are shown below in the run command.

```shell
# start container into the background and run the core-daemon by default
sudo docker run -itd --name core -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix:rw --privileged --entrypoint core-daemon core
# enable xhost access to the root user, this will allow you to run the core-gui from the container
xhost +local:root
# launch core-gui from the running container launched previously
sudo docker exec -it core core-gui
```
