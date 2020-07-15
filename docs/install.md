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

> **NOTE:** CentOS 8 does not have the netem kernel mod available by default

CentOS 8 Enabled netem:
```shell
sudo yum update
# restart into updated kernel
sudo yum install -y kernel-modules-extra
sudo modprobe sch_netem
```

## Utility Requirements

* iproute2 4.5+ is a requirement for bridge related commands
* ebtables not backed by nftables

## Automated Installation

The automated install will install the various tools needed to help automate
the CORE installation (python3, pip, pipx, invoke, poetry). The script will
also automatically clone, build, and install the latest version of OSPF MDR.
Finally it will install CORE scripts and a systemd service, which have
been modified to use the installed poetry created virtual environment.

After installation has completed you should be able to run the various
CORE scripts for running core.

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

Below is an example of more formal manual steps that can be taken to install
CORE. You can also just install invoke and run `inv install` alone to simulate
what is done using `install.sh`.

The last two steps help install core scripts modified to leverage the installed
poetry virtual environment and setup a systemd based service, if desired.

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

## Installed Scripts

These scripts will be installed from the automated `install.sh` script or
using `inv install` manually.

| Name | Description |
|---|---|
| core-daemon | runs the backed core server providing TLV and gRPC APIs |
| core-gui | runs the legacy tcl/tk based GUI |
| core-pygui | runs the new python/tk based GUI |
| core-cleanup | tool to help removed lingering core created containers, bridges, directories |
| core-imn-to-xml | tool to help automate converting a .imn file to .xml format |
| core-route-monitor | tool to help monitor traffic across nodes and feed that to SDT |
| core-service-update | tool to update automate modifying a legacy service to match current naming |
| coresendmsg | tool to send TLV API commands from command line |
| core-cli | tool to query, open xml files, and send commands using gRPC |
| core-manage | tool to add, remove, or check for services, models, and node types |

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

# install emane python bindings into the core virtual environment
cd $REPO/daemon
poetry run pip install $EMANE_REPO/src/python
```

## Using Invoke Tasks

The invoke tool installed by way of pipx provides conveniences for running
CORE tasks to help ensure usage of the create python virtual environment.

```shell
Available tasks:

  cleanup           run core-cleanup removing leftover core nodes, bridges, directories
  cli               run core-cli used to query and modify a running session
  daemon            start core-daemon
  gui               start core-pygui
  install           install core, poetry, scripts, service, and ospf mdr
  install-scripts   install core script files, modified to leverage virtual environment
  install-service   install systemd core service
  test              run core tests
  test-emane        run core emane tests
  test-mock         run core tests using mock to avoid running as sudo
  uninstall         uninstall core
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

## Running User Scripts

If you create your own scripts to run CORE directly in python or using gRPC/TLV
APIs you will need to make sure you are running them within context of the
poetry install virtual environment.

> **NOTE:** the following assumes CORE has been installed successfully

One way to do this would be to enable to environments shell.
```shell
cd $REPO/daemon
poetry shell
python run /path/to/script.py
```

Another way would be to run the script directly by way of poetry.
```shell
cd $REPO/daemon
poetry run python /path/to/script.py
```
