# Hardware In The Loop

## Overview

In some cases it may be impossible or impractical to run software using CORE
nodes alone. You may need to bring in external hardware into the network.
CORE's emulated networks run in real time, so they can be connected to live
physical networks. The RJ45 tool and the Tunnel tool help with connecting to
the real world. These tools are available from the **Link Layer Nodes** menu.

When connecting two or more CORE emulations together, MAC address collisions
should be avoided. CORE automatically assigns MAC addresses to interfaces when
the emulation is started, starting with **00:00:00:aa:00:00** and incrementing
the bottom byte. The starting byte should be changed on the second CORE machine
using the **Tools->MAC Addresses** option the menu.

## RJ45 Node

CORE provides the RJ45 node, which represents a physical
interface within the host that is running CORE. Any real-world network
devices can be connected to the interface and communicate with the CORE nodes in real time.

The main drawback is that one physical interface is required for each
connection. When the physical interface is assigned to CORE, it may not be used
for anything else. Another consideration is that the computer or network that
you are connecting to must be co-located with the CORE machine.

### GUI Usage

To place an RJ45 connection, click on the **Link Layer Nodes** toolbar and select
the **RJ45 Node** from the options. Click on the canvas, where you would like
the nodes to place. Now click on the **Link Tool** and draw a link between the RJ45
and the other node you wish to be connected to. The RJ45 node will display "UNASSIGNED".
Double-click the RJ45 node to assign a physical interface. A list of available
interfaces will be shown, and one may be selected, then selecting **Apply**.

!!! note

    When you press the Start button to instantiate your topology, the
    interface assigned to the RJ45 will be connected to the CORE topology. The
    interface can no longer be used by the system.

### Multiple RJ45s with One Interface (VLAN)

It is possible to have multiple RJ45 nodes using the same physical interface
by leveraging 802.1x VLANs. This allows for more RJ45 nodes than physical ports
are available, but the (e.g. switching) hardware connected to the physical port
must support the VLAN tagging, and the available bandwidth will be shared.

You need to create separate VLAN virtual devices on the Linux host,
and then assign these devices to RJ45 nodes inside of CORE. The VLANing is
actually performed outside of CORE, so when the CORE emulated node receives a
packet, the VLAN tag will already be removed.

Here are example commands for creating VLAN devices under Linux:

```shell
ip link add link eth0 name eth0.1 type vlan id 1
ip link add link eth0 name eth0.2 type vlan id 2
ip link add link eth0 name eth0.3 type vlan id 3
```

## Tunnel Tool

The tunnel tool builds GRE tunnels between CORE emulations or other hosts.
Tunneling can be helpful when the number of physical interfaces is limited or
when the peer is located on a different network. In this case a physical interface does
not need to be dedicated to CORE as with the RJ45 tool.

The peer GRE tunnel endpoint may be another CORE machine or another
host that supports GRE tunneling. When placing a Tunnel node, initially
the node will display "UNASSIGNED". This text should be replaced with the IP
address of the tunnel peer. This is the IP address of the other CORE machine or
physical machine, not an IP address of another virtual node.

!!! note

    Be aware of possible MTU (Maximum Transmission Unit) issues with GRE devices.
    The *gretap* device has an interface MTU of 1,458 bytes; when joined to a Linux
    bridge, the bridge's MTU becomes 1,458 bytes. The Linux bridge will not perform
    fragmentation for large packets if other bridge ports have a higher MTU such
    as 1,500 bytes.

The GRE key is used to identify flows with GRE tunneling. This allows multiple
GRE tunnels to exist between that same pair of tunnel peers. A unique number
should be used when multiple tunnels are used with the same peer. When
configuring the peer side of the tunnel, ensure that the matching keys are
used.

### Example Usage

Here are example commands for building the other end of a tunnel on a Linux
machine. In this example, a router in CORE has the virtual address
**10.0.0.1/24** and the CORE host machine has the (real) address
**198.51.100.34/24**. The Linux box
that will connect with the CORE machine is reachable over the (real) network
at **198.51.100.76/24**.
The emulated router is linked with the Tunnel Node. In the
Tunnel Node configuration dialog, the address **198.51.100.76** is entered, with
the key set to **1**. The gretap interface on the Linux box will be assigned
an address from the subnet of the virtual router node,
**10.0.0.2/24**.

```shell
# these commands are run on the tunnel peer
sudo ip link add gt0 type gretap remote 198.51.100.34 local 198.51.100.76 key 1
sudo ip addr add 10.0.0.2/24 dev gt0
sudo ip link set dev gt0 up
```

Now the virtual router should be able to ping the Linux machine:

```shell
# from the CORE router node
ping 10.0.0.2
```

And the Linux machine should be able to ping inside the CORE emulation:

```shell
# from the tunnel peer
ping 10.0.0.1
```

To debug this configuration, **tcpdump** can be run on the gretap devices, or
on the physical interfaces on the CORE or Linux machines. Make sure that a
firewall is not blocking the GRE traffic.
