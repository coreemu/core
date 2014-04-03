.. This file is part of the CORE Manual
   (c)2012-2013 the Boeing Company

.. _Introduction:

************
Introduction
************

The Common Open Research Emulator (CORE) is a tool for building virtual
networks. As an emulator, CORE builds a representation of a real computer
network that runs in real time, as opposed to simulation, where abstract models
are used. The live-running emulation can be connected to physical networks and
routers.  It provides an environment for running real applications and
protocols, taking advantage of virtualization provided by the Linux or FreeBSD
operating systems.

Some of its key features are:

.. index::
   single: key features

* efficient and scalable
* runs applications and protocols without modification
* easy-to-use GUI
* highly customizable

CORE is typically used for network and protocol research,
demonstrations, application and platform testing, evaluating networking
scenarios, security studies, and increasing the size of physical test networks.

.. index::
   single: CORE; components of
   single: CORE; API
   single: API
   single: CORE; GUI

.. _Architecture:

Architecture
============
The main components of CORE are shown in :ref:`core-architecture`. A
*CORE daemon* (backend) manages emulation sessions. It builds emulated networks
using kernel virtualization for virtual nodes and some form of bridging and
packet manipulation for virtual networks. The nodes and networks come together
via interfaces installed on nodes. The daemon is controlled via the
graphical user interface, the *CORE GUI* (frontend).
The daemon uses Python modules
that can be imported directly by Python scripts.
The GUI and the daemon communicate using a custom,
asynchronous, sockets-based API, known as the *CORE API*. The dashed line
in the figure notionally depicts the user-space and kernel-space separation.
The components the user interacts with are colored blue: GUI, scripts, or
command-line tools.

The system is modular to allow mixing different components. The virtual
networks component, for example, can be realized with other network
simulators and emulators, such as ns-3 and EMANE.
Different types of kernel virtualization are supported.
Another example is how a session can be designed and started using
the GUI, and continue to run in "headless" operation with the GUI closed.
The CORE API is sockets based,
to allow the possibility of running different components on different physical
machines.

.. _core-architecture:

.. figure:: figures/core-architecture.*
   :alt: CORE architecture diagram
   :align: center

   CORE Architecture

The CORE GUI is a Tcl/Tk program; it is started using the command
``core-gui``. The CORE daemon, named ``core-daemon``,
is usually started via the init script
(``/etc/init.d/core-daemon`` or ``core-daemon.service``,
depending on platform.)
The CORE daemon manages sessions of virtual
nodes and networks, of which other scripts and utilities may be used for
further control.


.. _How_Does_It_Work?:

How Does it Work?
=================

A CORE node is a lightweight virtual machine. The CORE framework runs on Linux
and FreeBSD systems. The primary platform used for development is Linux.

.. index::
   single: Linux; virtualization
   single: Linux; containers
   single: LXC
   single: network namespaces

* :ref:`Linux` CORE uses Linux network namespace virtualization to build virtual nodes, and ties them together with virtual networks using Linux Ethernet bridging. 
* :ref:`FreeBSD` CORE uses jails with a network stack virtualization kernel option to build virtual nodes, and ties them together with virtual networks using BSD's Netgraph system.


.. _Linux:

Linux
-----
Linux network namespaces (also known as netns, LXC, or `Linux containers
<http://lxc.sourceforge.net/>`_) is the primary virtualization
technique used by CORE. LXC has been part of the mainline Linux kernel since
2.6.24. Recent Linux distributions such as Fedora and Ubuntu have
namespaces-enabled kernels out of the box, so the kernel does not need to be
patched or recompiled.
A namespace is created using the ``clone()`` system call. Similar
to the BSD jails, each namespace has its own process environment and private
network stack. Network namespaces share the same filesystem in CORE.

.. index::
   single: Linux; bridging
   single: Linux; networking
   single: ebtables

CORE combines these namespaces with Linux Ethernet bridging
to form networks. Link characteristics are applied using Linux Netem queuing
disciplines. Ebtables is Ethernet frame filtering on Linux bridges. Wireless
networks are emulated by controlling which interfaces can send and receive with
ebtables rules.


.. _FreeBSD:

FreeBSD
-------

.. index::
   single: FreeBSD; Network stack virtualization
   single: FreeBSD; jails
   single: FreeBSD; vimages

FreeBSD jails provide an isolated process space, a virtual environment for
running programs. Starting with FreeBSD 8.0, a new `vimage` kernel option
extends BSD jails so that each jail can have its own virtual network stack --
its own networking variables such as addresses, interfaces, routes, counters,
protocol state, socket information, etc. The existing networking algorithms and
code paths are intact but operate on this virtualized state. 

Each jail plus network stack forms a lightweight virtual machine. These are
named jails or *virtual images* (or *vimages*) and are created using a the
``jail`` or ``vimage`` command. Unlike traditional virtual
machines, vimages do not feature entire operating systems running on emulated
hardware. All of the vimages will share the same processor, memory, clock, and
other system resources. Because the actual hardware is not emulated and network
packets can be passed by reference through the in-kernel Netgraph system,
vimages are quite lightweight and a single system can accommodate numerous
instances.

Virtual network stacks in FreeBSD were historically available as a patch to the
FreeBSD 4.11 and 7.0 kernels, and the VirtNet project [#f1]_ [#f2]_
added this functionality to the
mainline 8.0-RELEASE and newer kernels.

.. index::
   single: FreeBSD; Netgraph 

The FreeBSD Operating System kernel features a graph-based
networking subsystem named Netgraph. The netgraph(4) manual page quoted below
best defines this system: 

  The netgraph system provides a uniform and modular system for the 
  implementation of kernel objects which perform various networking functions.
  The objects, known as nodes, can be arranged into arbitrarily complicated
  graphs.  Nodes have hooks which are used to connect two nodes together,
  forming the edges in the graph.  Nodes communicate along the edges to
  process data, implement protocols, etc.

  The aim of netgraph is to supplement rather than replace the existing
  kernel networking infrastructure.

.. index::
   single: IMUNES
   single: VirtNet
   single: prior work

.. rubric:: Footnotes
.. [#f1] http://www.nlnet.nl/project/virtnet/
.. [#f2] http://www.imunes.net/virtnet/

.. _Prior_Work:

Prior Work
==========

The Tcl/Tk CORE GUI was originally derived from the open source 
`IMUNES <http://www.tel.fer.hr/imunes/>`_ 
project from the University of Zagreb
as a custom project within Boeing Research and Technology's Network
Technology research group in 2004. Since then they have developed the CORE
framework to use not only FreeBSD but Linux virtualization, have developed a
Python framework, and made numerous user- and kernel-space developments, such
as support for wireless networks, IPsec, the ability to distribute emulations,
simulation integration, and more. The IMUNES project also consists of userspace
and kernel components. Originally, one had to download and apply a patch for
the FreeBSD 4.11 kernel, but the more recent 
`VirtNet <http://www.nlnet.nl/project/virtnet/>`_
effort has brought network stack
virtualization to the more modern FreeBSD 8.x kernel.

.. _Open_Source_Project_and_Resources:

Open Source Project and Resources
=================================
.. index::
   single: open source project
   single: license
   single: website
   single: supplemental website
   single: contributing

CORE has been released by Boeing to the open source community under the BSD
license. If you find CORE useful for your work, please contribute back to the
project. Contributions can be as simple as reporting a bug, dropping a line of
encouragement or technical suggestions to the mailing lists, or can also
include submitting patches or maintaining aspects of the tool. For details on
contributing to CORE, please visit the
`wiki <http://code.google.com/p/coreemu/wiki/Home, wiki>`_.

Besides this manual, there are other additional resources available online:

* `CORE website <http://www.nrl.navy.mil/itd/ncs/products/core>`_ - main project page containing demos, downloads, and mailing list information.
* `CORE supplemental website <http://code.google.com/p/coreemu/>`_ - supplemental Google Code page with a quickstart guide, wiki, bug tracker, and screenshots.

.. index::
   single: wiki
   single: CORE; wiki

The `CORE wiki <http://code.google.com/p/coreemu/wiki/Home>`_ is a good place to check for the latest documentation and tips.

Goals
-----
These are the Goals of the CORE project; they are similar to what we consider to be the :ref:`key features <Introduction>`.

#. Ease of use - In a few clicks the user should have a running network.
#. Efficiency and scalability - A node is more lightweight than a full virtual machine. Tens of nodes should be possible on a standard laptop computer.
#. Software re-use - Re-use real implementation code, protocols, networking stacks.
#. Networking - CORE is focused on emulating networks and offers various ways to connect the running emulation with real or simulated networks.
#. Hackable - The source code is available and easy to understand and modify.

Non-Goals
---------
This is a list of Non-Goals, specific things that people may be interested in but are not areas that we will pursue.


#. Reinventing the wheel - Where possible, CORE reuses existing open source components such as virtualization, Netgraph, netem, bridging, Quagga, etc.
#. 1,000,000 nodes -	While the goal of CORE is to provide efficient, scalable network emulation, there is no set goal of N number of nodes. There are realistic limits on what a machine can handle as its resources are divided amongst virtual nodes. We will continue to make things more efficient and let the user determine the right number of nodes based on available hardware and the activities each node is performing.
#. Solves every problem - CORE is about emulating networking layers 3-7 using virtual network stacks in the Linux or FreeBSD operating systems.
#. Hardware-specific - CORE itself is not an instantiation of hardware, a testbed, or a specific laboratory setup; it should run on commodity laptop and desktop PCs, in addition to high-end server hardware.


