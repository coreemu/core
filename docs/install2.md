# CORE Installation

* Table of Contents
{:toc}

## Overview

CORE provides a script to help automate installing all required software
to build and run, including a python virtual environment to run it all in.

The following tools will be leveraged during installation:

|Tool|Description|
|---|---|
|pip|used to install pipx|
|pipx|used to install standalone python tools (invoke, poetry)|
|invoke|used to run provided tasks (install, daemon, gui, tests, etc)|
|poetry|used to install the managed python virtual environment for running CORE|

## Required Hardware

Any computer capable of running Linux should be able to run CORE. Since the physical machine will be hosting numerous
containers, as a general rule you should select a machine having as much RAM and CPU resources as possible.

## Supported Linux Distributions

Plan is to support recent Ubuntu and CentOS LTS releases.

Verified:
* Ubuntu - 18.04, 20.04
* CentOS - 7.8, 8.0*

> **NOTE:** Ubuntu 20.04 requires installing legacy ebtables for WLAN
> functionality

> **NOTE:** CentOS 8 does not provide legacy ebtables support, WLAN will not
> function properly

## Utility Requirements

* iproute2 4.5+ is a requirement for bridge related commands
* ebtables not backed by nftables

## Automated Installation

> **NOTE:** installs OSPF MDR

> **NOTE:** sets up script files using the prefix provided

> **NOTE:** install a systemd service file to /lib/systemd/system/core-daemon.service

```shell
# clone CORE repo
git clone https://github.com/coreemu/core.git
cd core

# run install script
# script usage: install.sh [-d] [-v]
#
# -v enable verbose install
# -d enable developer install
# -p install prefix, defaults to /usr/local
./install.sh
```

## Manual Installation

> **NOTE:** install OSPF MDR by manual instructions below

```shell
# clone CORE repo
git clone https://github.com/coreemu/core.git
cd core

# install python3 and venv support
# ubuntu
sudo apt install -y python3-pip python3-venv
# centos
sudo yum install -y python3-pip

# install system dependencies
# ubuntu
sudo apt install -y automake pkg-config gcc libev-dev ebtables iproute2 \
    ethtool tk python3-tk
# centos
sudo yum install -y automake pkgconf-pkg-config gcc gcc-c++ libev-devel \
    iptables-ebtables iproute python3-devel python3-tkinter tk ethtool \
    make kernel-modules-extra

# install grpcio-tools
python3 -m pip install --user grpcio==1.27.2 grpcio-tools==1.27.2

# build core
./bootstrap.sh
# centos requires --prefix=/usr
./configure
make
sudo make install

# install pipx, may need to restart terminal after ensurepath
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# install poetry
pipx install poetry

# install poetry virtual environment
cd daemon
poetry install --no-dev
cd ..

# install invoke to run helper tasks
pipx install invoke

# install core scripts leveraging poetry virtual environment
# centos requires --prefix=/usr
inv install-scripts

# optionally install systemd service file
# centos requires --prefix=/usr
inv install-service
```

## Manually Install OSPF MDR (Routing Support)

Virtual networks generally require some form of routing in order to work (e.g. to automatically populate routing
tables for routing packets from one subnet to another.) CORE builds OSPF routing protocol configurations by
default when the blue router node type is used.

* [OSPF MANET Designated Routers](https://github.com/USNavalResearchLaboratory/ospf-mdr) (MDR) - the Quagga routing
suite with a modified version of OSPFv3, optimized for use with mobile wireless networks. The **mdr** node type
(and the MDR service) requires this variant of Quagga.

```shell
# system dependencies
# ubuntu
sudo apt install -y libtool gawk libreadline-dev
# centos
sudo yum install -y libtool gawk readline-devel

# build and install
git clone https://github.com/USNavalResearchLaboratory/ospf-mdr
cd ospf-mdr
./bootstrap.sh
./configure --disable-doc --enable-user=root --enable-group=root --with-cflags=-ggdb \
    --sysconfdir=/usr/local/etc/quagga --enable-vtysh \
    --localstatedir=/var/run/quagga
make
sudo make install
```

## Manually Install EMANE

EMANE can be installed from deb or RPM packages or from source. See the
[EMANE GitHub](https://github.com/adjacentlink/emane) for full details.

Here are quick instructions for installing all EMANE packages for Ubuntu 18.04:
```shell
# install dependencies
# ubuntu
sudo apt-get install libssl-dev libxml-libxml-perl libxml-simple-perl
wget https://adjacentlink.com/downloads/emane/emane-1.2.5-release-1.ubuntu-18_04.amd64.tar.gz
tar xzf emane-1.2.5-release-1.ubuntu-18_04.amd64.tar.gz
# install base emane packages
sudo dpkg -i emane-1.2.5-release-1/deb/ubuntu-18_04/amd64/emane*.deb
# install python3 bindings
sudo dpkg -i emane-1.2.5-release-1/deb/ubuntu-18_04/amd64/python3*.deb
```

## Using Invoke Tasks

The invoke tool installed by way of pipx provides conveniences for running
CORE tasks to help ensure usage of the create python virtual environment.

```shell
Available tasks:

  cleanup      run core-cleanup removing leftover core nodes, bridges, directories
  daemon       start core-daemon
  gui          start core-pygui
  install      install core
  test         run core tests
  test-emane   run core emane tests
  test-mock    run core tests using mock to avoid running as sudo
```

Example running the core-daemon task from the root of the repo:
```shell
inv daemon
```

Some tasks are wrappers around command line tools and requires running
them with a slight variation for compatibility. You can enter the
poetry shell to run the script natively.

```shell
# running core-cli as a task requires all options to be provided
# within a string
inv cli "query session -i 1"

# entering the poetry shell to use core-cli natively
cd $REPO/daemon
poetry shell
core-cli query session -i 1

# exit the shell
exit
```
