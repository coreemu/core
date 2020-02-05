# XORP routing suite

* Table of Contents
{:toc}

## Overview

XORP is an open networking platform that supports OSPF, RIP, BGP, OLSR, VRRP, PIM, IGMP (Multicast) and other routing protocols.  Most protocols support IPv4 and IPv6 where applicable.  It is known to work on various Linux distributions and flavors of BSD.

XORP started life as a project at the ICSI Center for Open Networking (ICON) at the International Computer Science Institute in Berkeley, California, USA, and spent some time with the team at XORP, Inc.  It is now maintained and improved on a volunteer basis by a core of long-term XORP developers and some newer contributors.

XORP's primary goal is to be an open platform for networking protocol implementations and an alternative to proprietary and closed networking products in the marketplace today. It is the only open source platform to offer integrated multicast capability.

XORP design philosophy is:
  * modularity
  * extensibility
  * performance
  * robustness
This is achieved by carefully separating functionalities into independent modules, and by providing an API for each module.

XORP divides into two subsystems. The higher-level ("user-level") subsystem consists of the routing protocols. The lower-level ("kernel") manages the forwarding path, and provides APIs for the higher-level to access.

User-level XORP uses multi-process architecture with one process per routing protocol, and a novel inter-process communication mechanism called XRL (XORP Resource Locator).

The lower-level subsystem can use traditional UNIX kernel forwarding, or Click modular router. The modularity and independency of the lower-level from the user-level subsystem allows for its easily replacement with other solutions including high-end hardware-based forwarding engines.

## Installation

In order to be able to install the XORP Routing Suite, you must first install scons in order to compile it.
```shell
sudo apt-get install scons
```
Then, download XORP from its official [release web page](http://www.xorp.org/releases/current/).
```shell
http://www.xorp.org/releases/current/
cd xorp
sudo apt-get install libssl-dev ncurses-dev
scons
scons install
```
