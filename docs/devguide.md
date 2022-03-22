# CORE Developer's Guide

* Table of Contents
{:toc}

## Repository Overview

The CORE source consists of several different programming languages for
historical reasons. Current development focuses on the Python modules and
daemon. Here is a brief description of the source directories.

| Directory | Description                                                                          |
|-----------|--------------------------------------------------------------------------------------|
| daemon    | Python CORE daemon/gui code that handles receiving API calls and creating containers |
| docs      | Markdown Documentation currently hosted on GitHub                                    |
| gui       | Tcl/Tk GUI                                                                           |
| man       | Template files for creating man pages for various CORE command line utilities        |
| netns     | C program for creating CORE containers                                               |

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
build CORE, setup the CORE poetry environment, and install pre-commit hooks. You can
refer to the [install docs](install.md) for issues related to different distributions.

```shell
./install -d
```

### pre-commit

pre-commit hooks help automate running tools to check modified code. Every time a commit is made
python utilities will be ran to check validity of code, potentially failing and backing out the commit.
These changes are currently mandated as part of the current CI, so add the changes and commit again.

## Running CORE

You can now run core as you normally would, or leverage some of the invoke tasks to
conveniently run tests, etc.

```shell
# run core-daemon
sudo core-daemon

# run python gui
core-pygui

# run tcl gui
core-gui

# run mocked unit tests
cd <CORE_REPO>
inv test-mock
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
any bridges or *nftables* rules.  With a *-d* option, it will also kill any running CORE daemon.

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
