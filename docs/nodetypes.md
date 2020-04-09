# CORE Node Types

* Table of Contents
{:toc}

## Overview

Different node types can be configured in CORE, and each node type has a
*machine type* that indicates how the node will be represented at run time.
Different machine types allow for different virtualization options.

## Netns Nodes

The *netns* machine type is the default. This is for nodes that will be
backed by Linux network namespaces. This default machine type is very
lightweight, providing a minimum amount of virtualization in order to
emulate a network. Another reason this is designated as the default
machine type is because this virtualization technology typically
requires no changes to the kernel; it is available out-of-the-box from the
latest mainstream Linux distributions.

## Physical Nodes

The *physical* machine type is used for nodes that represent a real Linux-based
machine that will participate in the emulated network scenario. This is
typically used, for example, to incorporate racks of server machines from an
emulation testbed. A physical node is one that is running the CORE daemon
(*core-daemon*), but will not be further partitioned into virtual machines.
Services that are run on the physical node do not run in an isolated or
virtualized environment, but directly on the operating system.

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
