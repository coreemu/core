# CORE Developer's Guide

## Overview

The CORE source consists of several programming languages for
historical reasons. Current development focuses on the Python modules and
daemon. Here is a brief description of the source directories.

| Directory | Description                                                                          |
|-----------|--------------------------------------------------------------------------------------|
| daemon    | Python CORE daemon/gui code that handles receiving API calls and creating containers |
| docs      | Markdown Documentation currently hosted on GitHub                                    |
| man       | Template files for creating man pages for various CORE command line utilities        |
| netns     | C program for creating CORE containers                                               |

## Getting started

To setup CORE for develop we will leverage to automated install script.

## Install the Development Environment

The current recommended development environment is Ubuntu 22.04. This section
covers a complete example for installing CORE on a clean install. It will help
setup CORE in development mode, OSPF MDR, and EMANE.

``` shell
# install system packages
sudo apt-get update -y
sudo apt-get install -y ca-certificates git sudo wget tzdata libpcap-dev libpcre3-dev \
    libprotobuf-dev libxml2-dev protobuf-compiler unzip uuid-dev iproute2 iputils-ping \
    tcpdump

# install core
cd ~/Documents
git clone https://github.com/coreemu/core
cd core
./setup.sh
source ~/.bashrc
inv install -d

# install emane
cd ~/Documents
wget https://adjacentlink.com/downloads/emane/emane-1.5.1-release-1.ubuntu-22_04.amd64.tar.gz
tar xf emane-1.5.1-release-1.ubuntu-22_04.amd64.tar.gz
cd emane-1.5.1-release-1/debs/ubuntu-22_04/amd64
sudo apt-get install -y ./openstatistic*.deb ./emane*.deb ./python3-emane_*.deb

# install emane python bindings
cd ~/Documents
wget https://github.com/protocolbuffers/protobuf/releases/download/v3.19.6/protoc-3.19.6-linux-x86_64.zip
mkdir protoc
unzip protoc-3.19.6-linux-x86_64.zip -d protoc
git clone https://github.com/adjacentlink/emane.git
cd emane
git checkout v1.5.1
./autogen.sh
./configure --prefix=/usr
cd src/python
PATH=~/Documents/protoc/bin:$PATH make
sudo /opt/core/venv/bin/python -m pip install .
```

### pre-commit

pre-commit hooks help automate running tools to check modified code. Every time a commit is made
python utilities will be run to check validity of code, potentially failing and backing out the commit.
These changes are currently mandated as part of the current CI, so add the changes and commit again.

## Running CORE

You can now run core as you normally would, or leverage some of the invoke tasks to
conveniently run tests, etc.

```shell
# run core-daemon
sudo core-daemon

# run gui
core-gui

# run mocked unit tests
cd <CORE_REPO>
inv test-mock
```

## Linux Network Namespace Commands

CORE includes its own set of tools for instantiating and configuring network namespace
containers. This section describes these tools.

### vnoded

The *vnoded* daemon is the program used to create a new namespace, and listen on a control channel for commands that
may instantiate other processes. This daemon runs as PID 1 in the container. It is launched automatically by the CORE
daemon. The control channel is a UNIX domain socket usually named */tmp/pycore.23098/n3*, for node 3 running on CORE
session 23098, for example. Root privileges are required for creating a new namespace.

### vcmd

The *vcmd* program is used to connect to the *vnoded* daemon in a Linux network namespace, for running commands in the
namespace. The CORE daemon uses the same channel for setting up a node and running processes within it. This program
has two required arguments, the control channel name, and the command line to be run within the namespace. This command
does not need to run with root privileges.

When you double-click on a node in a running emulation, CORE will open a shell window for that node using a command
such as:

```shell
gnome-terminal -e vcmd -c /tmp/pycore.50160/n1 -- bash
```

Similarly, the IPv4 routes Observer Widget will run a command to display the routing table using a command such as:

```shell
vcmd -c /tmp/pycore.50160/n1 -- /sbin/ip -4 ro
```

### core-cleanup script

A script named *core-cleanup* is provided to clean up any running CORE emulations. It will attempt to kill any
remaining vnoded processes, kill any EMANE processes, remove the :file:`/tmp/pycore.*` session directories, and remove
any bridges or *nftables* rules. With a *-d* option, it will also kill any running CORE daemon.

### netns command

The *netns* command is not used by CORE directly. This utility can be used to run a command in a new network namespace
for testing purposes. It does not open a control channel for receiving further commands.

### Other Useful Commands

Here are some other Linux commands that are useful for managing the Linux network namespace emulation.

```shell
# view the Linux bridging setup
ip link show type bridge
# view the netem rules used for applying link effects
tc qdisc show
# view the rules that make the wireless LAN work
nft list ruleset
```
