.. This file is part of the CORE Manual
   (c)2012-2013 the Boeing Company

.. _Developer's_Guide:

*****************
Developer's Guide
*****************

This section contains advanced usage information, intended for developers and
others who are comfortable with the command line.

.. _Coding_Standard:

Coding Standard
===============

The coding standard and style guide for the CORE project are maintained online.
Please refer to the `coding standard
<http://code.google.com/p/coreemu/wiki/Hacking>`_ posted on the CORE Wiki.

.. _Source_Code_Guide:

Source Code Guide
=================

The CORE source consists of several different programming languages for
historical reasons. Current development focuses on the Python modules and
daemon. Here is a brief description of the source directories.

These are being actively developed as of CORE |version|:

* *gui* - Tcl/Tk GUI. This uses Tcl/Tk because of its roots with the IMUNES
  project.
* *daemon* - Python modules are found in the :file:`daemon/core` directory, the
  daemon under :file:`daemon/sbin/core-daemon`, and Python extension modules for
  Linux Network Namespace support are in :file:`daemon/src`.
* *doc* - Documentation for the manual lives here in reStructuredText format.
* *packaging* - Control files and script for building CORE packages are here.

These directories are not so actively developed:

* *kernel* - patches and modules mostly related to FreeBSD.

.. _The_CORE_API:

The CORE API
============

.. index:: CORE; API

.. index:: API

.. index:: remote API

The CORE API is used between different components of CORE for communication.
The GUI communicates with the CORE daemon using the API. One emulation server
communicates with another using the API. The API also allows other systems to
interact with the CORE emulation. The API allows another system to add, remove,
or modify nodes and links, and enables executing commands on the emulated
systems. On FreeBSD, the API is used for enhancing the wireless LAN
calculations. Wireless link parameters are updated on-the-fly based on node
positions.

CORE listens on a local TCP port for API messages. The other system could be
software running locally or another machine accessible across the network.

The CORE API is currently specified in a separate document, available from the
CORE website.

.. _Linux_network_namespace_Commands:

Linux network namespace Commands
================================

.. index:: lxctools

Linux network namespace containers are often managed using the *Linux Container
Tools* or *lxc-tools* package. The lxc-tools website is available here
`<http://lxc.sourceforge.net/>`_ for more information.  CORE does not use these
management utilities, but includes its own set of tools for instantiating and
configuring network namespace containers. This section describes these tools.

.. index:: vnoded

The *vnoded* daemon is the program used to create a new namespace, and
listen on a control channel for commands that may instantiate other processes.
This daemon runs as PID 1 in the container. It is launched automatically by
the CORE daemon. The control channel is a UNIX domain socket usually named
:file:`/tmp/pycore.23098/n3`, for node 3 running on CORE 
session 23098, for example. Root privileges are required for creating a new
namespace.

.. index:: vcmd

The *vcmd* program is used to connect to the *vnoded* daemon in a Linux network
namespace, for running commands in the namespace. The CORE daemon
uses the same channel for setting up a node and running processes within it.
This program has two
required arguments, the control channel name, and the command line to be run
within the namespace. This command does not need to run with root privileges.

When you double-click
on a node in a running emulation, CORE will open a shell window for that node
using a command such as:
::

  gnome-terminal -e vcmd -c /tmp/pycore.50160/n1 -- bash
  

Similarly, the IPv4 routes Observer Widget will run a command to display the routing table using a command such as:
::

  vcmd -c /tmp/pycore.50160/n1 -- /sbin/ip -4 ro
  

.. index:: core-cleanup

A script named *core-cleanup* is provided to clean up any running CORE
emulations. It will attempt to kill any remaining vnoded processes, kill any
EMANE processes, remove the :file:`/tmp/pycore.*` session directories, and
remove any bridges or *ebtables* rules.  With a *-d* option, it will also kill
any running CORE daemon.

.. index:: netns

The *netns* command is not used by CORE directly. This utility can be used to
run a command in a new network namespace for testing purposes. It does not open
a control channel for receiving further commands.

Here are some other Linux commands that are useful for managing the Linux
network namespace emulation.
::

  # view the Linux bridging setup
  brctl show
  # view the netem rules used for applying link effects
  tc qdisc show
  # view the rules that make the wireless LAN work
  ebtables -L
  

Below is a transcript of creating two emulated nodes and connecting them together with a wired link:

.. index:: create nodes from command-line

.. index:: command-line

::

  # create node 1 namespace container
  vnoded -c /tmp/n1.ctl -l /tmp/n1.log -p /tmp/n1.pid
  # create a virtual Ethernet (veth) pair, installing one end into node 1
  ip link add name n1.0.1 type veth peer name n1.0
  ip link set n1.0 netns `cat /tmp/n1.pid`
  vcmd -c /tmp/n1.ctl -- ip link set n1.0 name eth0
  vcmd -c /tmp/n1.ctl -- ifconfig eth0 10.0.0.1/24 

  # create node 2 namespace container
  vnoded -c /tmp/n2.ctl -l /tmp/n2.log -p /tmp/n2.pid
  # create a virtual Ethernet (veth) pair, installing one end into node 2
  ip link add name n2.0.1 type veth peer name n2.0
  ip link set n2.0 netns `cat /tmp/n2.pid`
  vcmd -c /tmp/n2.ctl -- ip link set n2.0 name eth0
  vcmd -c /tmp/n2.ctl -- ifconfig eth0 10.0.0.2/24 

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
  

The above example script can be found as :file:`twonodes.sh` in the
:file:`examples/netns` directory. Use *core-cleanup* to clean up after the
script.

.. _FreeBSD_Commands:

FreeBSD Commands
================


.. index:: vimage
.. index:: ngctl
.. index:: Netgraph
.. _FreeBSD_Kernel_Commands:

FreeBSD Kernel Commands
-----------------------

The FreeBSD kernel emulation controlled by CORE is realized through several
userspace commands. The CORE GUI itself could be thought of as a glorified
script that dispatches these commands to build and manage the kernel emulation.


* **vimage** - the vimage command, short for "virtual image", is used to
  create lightweight virtual machines and execute commands within the virtual
  image context. On a FreeBSD CORE machine, see the *vimage(8)* man page for
  complete details. The vimage command comes from the VirtNet project which
  virtualizes the FreeBSD network stack.


* **ngctl** - the ngctl command, short for "netgraph control", creates
  Netgraph nodes and hooks, connects them together, and allows for various
  interactions with the Netgraph nodes. See the *ngctl(8)* man page for
  complete details. The ngctl command is built-in to FreeBSD because the
  Netgraph system is part of the kernel.

Both commands must be run as root.
Some example usage of the *vimage* command follows below.
::

  vimage			# displays the current virtual image
  vimage -l			# lists running virtual images
  vimage e0_n0 ps aux	# list the processes running on node 0
  for i in 1 2 3 4 5
  do				# execute a command on all nodes
    vimage e0_n$i sysctl -w net.inet.ip.redirect=0
  done
  

The *ngctl* command is more complex, due to the variety of Netgraph nodes
available and each of their options.
::

  ngctl l			# list active Netgraph nodes
  ngctl show e0_n8:		# display node hook information
  ngctl msg e0_n0-n1: getstats # get pkt count statistics from a pipe node
  ngctl shutdown \\[0x0da3\\]: # shut down unnamed node using hex node ID
  

There are many other combinations of commands not shown here. See the online
manual (man) pages for complete details. 

Below is a transcript of creating two emulated nodes, `router0` and `router1`,
and connecting them together with a link:

.. index:: create nodes from command-line

.. index:: command-line

::

  # create node 0
  vimage -c e0_n0
  vimage e0_n0 hostname router0
  ngctl mkpeer eiface ether ether
  vimage -i e0_n0 ngeth0 eth0
  vimage e0_n0 ifconfig eth0 link 40:00:aa:aa:00:00
  vimage e0_n0 ifconfig lo0 inet localhost
  vimage e0_n0 sysctl net.inet.ip.forwarding=1
  vimage e0_n0 sysctl net.inet6.ip6.forwarding=1
  vimage e0_n0 ifconfig eth0 mtu 1500

  # create node 1
  vimage -c e0_n1
  vimage e0_n1 hostname router1
  ngctl mkpeer eiface ether ether
  vimage -i e0_n1 ngeth1 eth0
  vimage e0_n1 ifconfig eth0 link 40:00:aa:aa:0:1
  vimage e0_n1 ifconfig lo0 inet localhost
  vimage e0_n1 sysctl net.inet.ip.forwarding=1
  vimage e0_n1 sysctl net.inet6.ip6.forwarding=1
  vimage e0_n1 ifconfig eth0 mtu 1500

  # create a link between n0 and n1
  ngctl mkpeer eth0@e0_n0: pipe ether upper
  ngctl name eth0@e0_n0:ether e0_n0-n1
  ngctl connect e0_n0-n1: eth0@e0_n1: lower ether
  ngctl msg e0_n0-n1: setcfg \\
    {{ bandwidth=100000000 delay=0  upstream={ BER=0 dupl
  icate=0 }  downstream={ BER=0 duplicate=0 } }}
  ngctl msg e0_n0-n1: setcfg {{ downstream={ fifo=1 } }}
  ngctl msg e0_n0-n1: setcfg {{ downstream={ droptail=1 } }}
  ngctl msg e0_n0-n1: setcfg {{ downstream={ queuelen=50 } }}
  ngctl msg e0_n0-n1: setcfg {{ upstream={ fifo=1 } }}
  ngctl msg e0_n0-n1: setcfg {{ upstream={ droptail=1 } }}
  ngctl msg e0_n0-n1: setcfg {{ upstream={ queuelen=50 } }}
  

Other FreeBSD commands that may be of interest:
.. index:: FreeBSD commands

* **kldstat**, **kldload**, **kldunload** - list, load, and unload
  FreeBSD kernel modules
* **sysctl** - display and modify various pieces of kernel state
* **pkg_info**, **pkg_add**, **pkg_delete** - list, add, or remove
  FreeBSD software packages.
* **vtysh** - start a Quagga CLI for router configuration

Netgraph Nodes
--------------

.. index:: Netgraph

.. index:: Netgraph nodes

Each Netgraph node implements a protocol or processes data in some well-defined
manner (see the `netgraph(4)` man page).  The netgraph source code is located
in `/usr/src/sys/netgraph`.  There you might discover additional nodes that
implement some desired functionality, that have not yet been included in CORE.
Using certain kernel commands, you can likely include these types of nodes into
your CORE emulation.

The following Netgraph nodes are used by CORE:

* **ng_bridge** - switch node performs Ethernet bridging

* **ng_cisco** - Cisco HDLC serial links

* **ng_eiface** - virtual Ethernet interface that is assigned to each virtual machine

* **ng_ether** - physical Ethernet devices, used by the RJ45 tool

* **ng_hub** - hub node

* **ng_pipe** - used for wired Ethernet links, imposes packet delay, bandwidth restrictions, and other link characteristics

* **ng_socket** - socket used by *ngctl* utility

* **ng_wlan** - wireless LAN node


