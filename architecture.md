# CORE Architecture

## Main Components

* CORE Daemon
  * Manages emulation sessions
  * Builds the emulated networks using kernel virtualization for nodes and some form of bridging and packet manipulation for virtual networks
  * Nodes and networks come together via interfaces installed on nodes 
  * Controlled via the CORE GUI
  * Written in python and can be scripted, given direct control of scenarios
* CORE GUI
  * GUI and daemon communicate using a custom, asynchronous, sockets-based API, known as the CORE API 
  * Drag and drop creation for nodes and network interfaces
  * Can launch terminals for emulated nodes in running scenarios
  * Can save/open scenario files to recreate previous sessions
  * TCL/TK program

![](static/core-architecture.jpg)

## How Does it Work?

A CORE node is a lightweight virtual machine. The CORE framework runs on Linux. CORE uses Linux network namespace virtualization to build virtual nodes, and ties them together with virtual networks using Linux Ethernet bridging.

### Linux

Linux network namespaces (also known as netns, LXC, or [Linux containers](http://lxc.sourceforge.net/)) is the primary virtualization technique used by CORE. LXC has been part of the mainline Linux kernel since 2.6.24. Most recent Linux distributions have namespaces-enabled kernels out of the box. A namespace is created using the ```clone()``` system call. Each namespace has its own process environment and private network stack. Network namespaces share the same filesystem in CORE.

CORE combines these namespaces with Linux Ethernet bridging to form networks. Link characteristics are applied using Linux Netem queuing disciplines. Ebtables is Ethernet frame filtering on Linux bridges. Wireless networks are emulated by controlling which interfaces can send and receive with ebtables rules.

## Prior Work

The Tcl/Tk CORE GUI was originally derived from the open source [IMUNES](http://imunes.net) project from the University of Zagreb as a custom project within Boeing Research and Technology's Network Technology research group in 2004. Since then they have developed the CORE framework to use Linux virtualization, have developed a Python framework, and made numerous user- and kernel-space developments, such as support for wireless networks, IPsec, the ability to distribute emulations, simulation integration, and more. The IMUNES project also consists of userspace and kernel components.

## Open Source Project and Resources

CORE has been released by Boeing to the open source community under the BSD license. If you find CORE useful for your work, please contribute back to the project. Contributions can be as simple as reporting a bug, dropping a line of encouragement or technical suggestions to the mailing lists, or can also include submitting patches or maintaining aspects of the tool. For contributing to CORE, please visit [CORE GitHub](https://github.com/coreemu/core).
