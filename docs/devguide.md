# CORE Developer's Guide

* Table of Contents
{:toc}

## Repository Overview

The CORE source consists of several different programming languages for historical reasons.
Current development focuses on the Python modules and daemon. Here is a brief description of the source directories.

| Directory | Description |
|---|---|
|daemon|Python CORE daemon code that handles receiving API calls and creating containers|
|docs|Markdown Documentation currently hosted on GitHub|
|gui|Tcl/Tk GUI|
|man|Template files for creating man pages for various CORE command line utilities|
|netns|Python C extension modules for creating CORE containers|
|scripts|Template files used for running CORE as a service|

## Getting started

To setup CORE for develop we will leverage to automated install script.


## Clone CORE Repo

```shell
cd ~/Documents
git clone https://github.com/coreemu/core.git
cd core
git checkout develop
```

## Install the Development Environment

This command will automatically install system dependencies, clone and build OSPF-MDR,
build CORE, setup the CORE pipenv environment, and install pre-commit hooks.

This script is currently compatible with Ubuntu and CentOS, tested on Ubuntu 18.04 and
CentOS 7.6. The script also currently defaults to using python3.6, but a different
version of python can be targeted if python3.6 is not available on your system.

```shell
# default dev install using python3.6
./install.sh -d

# providing a newer python version for ubuntu
./install.sh -d -v 3.7

# providing a newer python version for centos
./install.sh -d -v 37
```

### pre-commit

pre-commit hooks help automate running tools to check modified code. Every time a commit is made
python utilities will be ran to check validity of code, potentially failing and backing out the commit.
These changes are currently mandated as part of the current CI, so add the changes and commit again.

### Adding EMANE to Pipenv

EMANE bindings are not available through pip, you will need to build and install from source.

[Build EMANE](https://github.com/adjacentlink/emane/wiki/Build#general-build-instructions)

```shell
# clone emane repo
git clone https://github.com/adjacentlink/emane.git

# install emane build deps
sudo apt install libxml2-dev libprotobuf-dev uuid-dev libpcap-dev protobuf-compiler

# build emane
./autogen.sh
./configure --prefix=/usr
make -j8

# install emane binding in pipenv
# NOTE: this will mody pipenv Pipfiles and we do not want that, use git checkout -- Pipfile*, to remove changes
python3 -m pipenv pip install $EMANEREPO/src/python
```

## Running CORE

Commands below can be used to run the core-daemon, the new core gui, and tests.

```shell
# runs for daemon
sudo python3 -m pipenv run core

# runs coretk gui
python3 -m pipenv run coretk

# runs mocked unit tests
python3 -m pipenv run test-mock
```

## Linux Network Namespace Commands

Linux network namespace containers are often managed using the *Linux Container Tools* or *lxc-tools* package.
The lxc-tools website is available here http://lxc.sourceforge.net/ for more information.  CORE does not use these
management utilities, but includes its own set of tools for instantiating and configuring network namespace containers.
This section describes these tools.

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
any bridges or *ebtables* rules.  With a *-d* option, it will also kill any running CORE daemon.

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
ebtables -L
```
