# CORE Node Types

* Table of Contents
{:toc}

## Overview

Different node types can be used within CORE, each with their own
tradeoffs and functionality.

## CORE Nodes

CORE nodes are the standard node type typically used in CORE. They are
backed by Linux network namespaces. They use very little system resources
in order to emulate a network. They do however share the hosts file system
as they do not get their own. CORE nodes will have a directory uniquely
created for them as a place to keep their files and mounted directories
(`/tmp/pycore.<session id>/<node name.conf`),
which will usually be wiped and removed upon shutdown.

## Docker Nodes

Docker nodes provide a convenience for running nodes using predefind images
and filesystems that CORE nodes do not provide. Details for using Docker
nodes can be found [here](docker.md).

## LXC Nodes

LXC nodes provide a convenience for running nodes using predefind images
and filesystems that CORE nodes do not provide. Details for using LXC
nodes can be found [here](lxc.md).

## Physical Nodes

The *physical* machine type is used for nodes that represent a real Linux-based
machine that will participate in the emulated network scenario. This is
typically used, for example, to incorporate racks of server machines from an
emulation testbed. A physical node is one that is running the CORE daemon
(*core-daemon*), but will not be further partitioned into containers.
Services that are run on the physical node do not run in an isolated
environment, but directly on the operating system.

Physical nodes must be assigned to servers, the same way nodes are assigned to
emulation servers with *Distributed Emulation*. The list of available physical
nodes currently shares the same dialog box and list as the emulation servers,
accessed using the *Emulation Servers...* entry from the *Session* menu.

Support for physical nodes is under development and may be improved in future
releases. Currently, when any node is linked to a physical node, a dashed line
is drawn to indicate network tunneling. A GRE tunneling interface will be
created on the physical node and used to tunnel traffic to and from the
emulated world.

Double-clicking on a physical node during runtime opens a terminal with an
SSH shell to that node. Users should configure public-key SSH login as done
with emulation servers.
