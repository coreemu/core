# CORE Developer's Guide

* Table of Contents
{:toc}

## Repository Overview

The CORE source consists of several different programming languages for historical reasons.
Current development focuses on the Python modules and daemon. Here is a brief description of the source directories.

| Directory | Description |
|---|---|
|corefx|JavaFX based GUI using gRPC API to replace legacy GUI|
|daemon|Python CORE daemon code that handles receiving API calls and creating containers|
|docs|Markdown Documentation currently hosted on GitHub|
|gui|Tcl/Tk GUI|
|man|Template files for creating man pages for various CORE command line utilities|
|netns|Python C extension modules for creating CORE containers|
|ns3|Experimental python ns3 script support for running CORE|
|scripts|Template files used for running CORE as a service|

## Getting started

Overview for setting up the pipenv environment, building core, installing the GUI and netns, then running
the core-daemon for development.

### Setup Python Environment

To leverage the dev environment you need python 3.6+.

```shell
# change to daemon directory
cd $REPO/daemon

# install pipenv
pip3 install pipenv

# setup a virtual environment and install all required development dependencies
python3 -m pipenv install --dev

# setup python variable using pipenv created python
export PYTHON=$(python3 -m pipenv --py)
```

### Build CORE

```shell
# clone core
git clone https://github.com/coreemu/core.git
cd core

# build core
./bootstrap.sh
./configure --prefix=/usr
make
```

### Install netns and GUI

Below commands assume your development will be focused on the daemon.

```shell
# install GUI
cd $REPO/gui
sudo make install

# install netns scripts
cd $REPO/netns
sudo make install
```

### Running CORE

This will run the core-daemon server using the configuration files within the repo.

```shell
python3 -m pipenv run coredev
```

## The CORE API

The CORE API is used between different components of CORE for communication. The GUI communicates with the CORE daemon 
using the API. One emulation server communicates with another using the API. The API also allows other systems to 
interact with the CORE emulation. The API allows another system to add, remove, or modify nodes and links, and enables 
executing commands on the emulated systems. Wireless link parameters are updated on-the-fly based on node positions.

CORE listens on a local TCP port for API messages. The other system could be software running locally or another 
machine accessible across the network.

The CORE API is currently specified in a separate document, available from the CORE website.

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
brctl show
# view the netem rules used for applying link effects
tc qdisc show
# view the rules that make the wireless LAN work
ebtables -L
```

### Example Command Usage

Below is a transcript of creating two emulated nodes and connecting them together with a wired link:

```shell
# create node 1 namespace container
vnoded -c /tmp/n1.ctl -l /tmp/n1.log -p /tmp/n1.pid
# create a virtual Ethernet (veth) pair, installing one end into node 1
ip link add name n1.0.1 type veth peer name n1.0
ip link set n1.0 netns `cat /tmp/n1.pid`
vcmd -c /tmp/n1.ctl -- ip link set lo up
vcmd -c /tmp/n1.ctl -- ip link set n1.0 name eth0 up
vcmd -c /tmp/n1.ctl -- ip addr add 10.0.0.1/24 dev eth0

# create node 2 namespace container
vnoded -c /tmp/n2.ctl -l /tmp/n2.log -p /tmp/n2.pid
# create a virtual Ethernet (veth) pair, installing one end into node 2
ip link add name n2.0.1 type veth peer name n2.0
ip link set n2.0 netns `cat /tmp/n2.pid`
vcmd -c /tmp/n2.ctl -- ip link set lo up
vcmd -c /tmp/n2.ctl -- ip link set n2.0 name eth0 up
vcmd -c /tmp/n2.ctl -- ip addr add 10.0.0.2/24 eth0

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
```

The above example script can be found as *twonodes.sh* in the *examples/netns* directory. Use *core-cleanup* to clean 
up after the script.
