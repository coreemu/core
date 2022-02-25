
# (BETA) Python GUI

* Table of Contents
{:toc}

![](static/core-pygui.png)

## Overview

The GUI is used to draw nodes and network devices on a canvas, linking them
together to create an emulated network session.

After pressing the start button, CORE will proceed through these phases,
staying in the **runtime** phase.  After the session is stopped, CORE will
proceed to the **data collection** phase before tearing down the emulated
state.

CORE can be customized to perform any action at each state. See the
**Hooks...** entry on the [Session Menu](#session-menu) for details about
when these session states are reached.

## Prerequisites

Beyond installing CORE, you must have the CORE daemon running.  This is done
on the command line with either systemd or sysv.

```shell
# systemd service
sudo systemctl daemon-reload
sudo systemctl start core-daemon

# sysv service
sudo service core-daemon start

# direct invocation
sudo core-daemon
```

## GUI Files

> **NOTE:** Previously the BETA GUI placed files under ~/.coretk, this has been
> updated to be ~/.coregui. The prior config file named ~/.coretk/gui.yaml is
> also now known as ~/.coregui/config.yaml and has a slightly different format

The GUI will create a directory in your home directory on first run called
~/.coregui. This directory will help layout various files that the GUI may use.

* .coregui/
  * backgrounds/
    * place backgrounds used for display in the GUI
  * custom_emane/
    * place to keep custom emane models to use with the core-daemon
  * custom_services/
    * place to keep custom services to use with the core-daemon
  * icons/
    * icons the GUI uses along with customs icons desired
  * mobility/
    * place to keep custom mobility files
  * scripts/
    * place to keep core related scripts
  * xmls/
    * place to keep saved session xml files
  * gui.log
    * log file when running the gui, look here when issues occur for exceptions etc
  * config.yaml
    * configuration file used to save/load various gui related settings (custom nodes, layouts, addresses, etc)

## Modes of Operation

The CORE GUI has two primary modes of operation, **Edit** and **Execute**
modes. Running the GUI, by typing **core-pygui** with no options, starts in
Edit mode. Nodes are drawn on a blank canvas using the toolbar on the left
and configured from right-click menus or by double-clicking them. The GUI
does not need to be run as root.

Once editing is complete, pressing the green **Start** button instantiates
the topology and enters Execute mode. In execute mode,
the user can interact with the running emulated machines by double-clicking or
right-clicking on them. The editing toolbar disappears and is replaced by an
execute toolbar, which provides tools while running the emulation. Pressing
the red **Stop** button will destroy the running emulation and return CORE
to Edit mode.

Once the emulation is running, the GUI can be closed, and a prompt will appear
asking if the emulation should be terminated. The emulation may be left
running and the GUI can reconnect to an existing session at a later time.

The GUI can be run as a normal user on Linux.

The python GUI currently provides the following options on startup.

```shell
usage: core-pygui [-h] [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [-p]

CORE Python GUI

optional arguments:
  -h, --help            show this help message and exit
  -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        logging level
  -p, --proxy           enable proxy
```

## Toolbar

The toolbar is a row of buttons that runs vertically along the left side of the
CORE GUI window. The toolbar changes depending on the mode of operation.

### Editing Toolbar

When CORE is in Edit mode (the default), the vertical Editing Toolbar exists on
the left side of the CORE window. Below are brief descriptions for each toolbar
item, starting from the top. Most of the tools are grouped into related
sub-menus, which appear when you click on their group icon.

| Icon                         | Name           | Description                                                                            |
|------------------------------|----------------|----------------------------------------------------------------------------------------|
| ![](static/pygui/select.png) | Selection Tool | Tool for selecting, moving, configuring nodes.                                         |
| ![](static/pygui/start.png)  | Start Button   | Starts Execute mode, instantiates the emulation.                                       |
| ![](static/pygui/link.png)   | Link           | Allows network links to be drawn between two nodes by clicking and dragging the mouse. |

### CORE Nodes

These nodes will create a new node container and run associated services.

| Icon                         | Name    | Description                                                                  |
|------------------------------|---------|------------------------------------------------------------------------------|
| ![](static/pygui/router.png) | Router  | Runs Quagga OSPFv2 and OSPFv3 routing to forward packets.                    |
| ![](static/pygui/host.png)   | Host    | Emulated server machine having a default route, runs SSH server.             |
| ![](static/pygui/pc.png)     | PC      | Basic emulated machine having a default route, runs no processes by default. |
| ![](static/pygui/mdr.png)    | MDR     | Runs Quagga OSPFv3 MDR routing for MANET-optimized routing.                  |
| ![](static/pygui/router.png) | PRouter | Physical router represents a real testbed machine.                           |

### Network Nodes

These nodes are mostly used to create a Linux bridge that serves the
purpose described below.

| Icon                            | Name         | Description                                                                                                                                                                                                                                        |
|---------------------------------|--------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ![](static/pygui/hub.png)       | Hub          | Ethernet hub forwards incoming packets to every connected node.                                                                                                                                                                                    |
| ![](static/pygui/lanswitch.png) | Switch       | Ethernet switch intelligently forwards incoming packets to attached hosts using an Ethernet address hash table.                                                                                                                                    |
| ![](static/pygui/wlan.png)      | Wireless LAN | When routers are connected to this WLAN node, they join a wireless network and an antenna is drawn instead of a connecting line; the WLAN node typically controls connectivity between attached wireless nodes based on the distance between them. |
| ![](static/pygui/rj45.png)      | RJ45         | RJ45 Physical Interface Tool, emulated nodes can be linked to real physical interfaces; using this tool, real networks and devices can be physically connected to the live-running emulation.                                                      |
| ![](static/pygui/tunnel.png)    | Tunnel       | Tool allows connecting together more than one CORE emulation using GRE tunnels.                                                                                                                                                                    |

### Annotation Tools

| Icon                            | Name      | Description                                                         |
|---------------------------------|-----------|---------------------------------------------------------------------|
| ![](static/pygui/marker.png)    | Marker    | For drawing marks on the canvas.                                    |
| ![](static/pygui/oval.png)      | Oval      | For drawing circles on the canvas that appear in the background.    |
| ![](static/pygui/rectangle.png) | Rectangle | For drawing rectangles on the canvas that appear in the background. |
| ![](static/pygui/text.png)      | Text      | For placing text captions on the canvas.                            |

### Execution Toolbar

When the Start button is pressed, CORE switches to Execute mode, and the Edit
toolbar on the left of the CORE window is replaced with the Execution toolbar
Below are the items on this toolbar, starting from the top.

| Icon                         | Name           | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
|------------------------------|----------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ![](static/pygui/stop.png)   | Stop Button    | Stops Execute mode, terminates the emulation, returns CORE to edit mode.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| ![](static/pygui/select.png) | Selection Tool | In Execute mode, the Selection Tool can be used for moving nodes around the canvas, and double-clicking on a node will open a shell window for that node; right-clicking on a node invokes a pop-up menu of run-time options for that node.                                                                                                                                                                                                                                                                                                                                                                 |
| ![](static/pygui/marker.png) | Marker         | For drawing freehand lines on the canvas, useful during demonstrations; markings are not saved.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| ![](static/pygui/run.png)    | Run Tool       | This tool allows easily running a command on all or a subset of all nodes. A list box allows selecting any of the nodes. A text entry box allows entering any command. The command should return immediately, otherwise the display will block awaiting response. The *ping* command, for example, with no parameters, is not a good idea. The result of each command is displayed in a results box. The first occurrence of the special text "NODE" will be replaced with the node name. The command will not be attempted to run on nodes that are not routers, PCs, or hosts, even if they are selected. |

## Menu

The menubar runs along the top of the CORE GUI window and provides access to a
variety of features. Some of the menus are detachable, such as the *Widgets*
menu, by clicking the dashed line at the top.

### File Menu

The File menu contains options for manipulating the **.imn** Configuration
Files. Generally, these menu items should not be used in Execute mode.

| Option                | Description                                                                                                                                                                                                                                                                                                                                                 |
|-----------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| New Session           | This starts a new session with an empty canvas.                                                                                                                                                                                                                                                                                                             |
| Save                  | Saves the current topology. If you have not yet specified a file name, the Save As dialog box is invoked.                                                                                                                                                                                                                                                   |
| Save As               | Invokes the Save As dialog box for selecting a new **.xml** file for saving the current configuration in the XML file.                                                                                                                                                                                                                                      |
| Open                  | Invokes the File Open dialog box for selecting a new XML file to open.                                                                                                                                                                                                                                                                                      |
| Recently used files   | Above the Quit menu command is a list of recently use files, if any have been opened. You can clear this list in the Preferences dialog box. You can specify the number of files to keep in this list from the Preferences dialog. Click on one of the file names listed to open that configuration file.                                                   |
| Execute Python Script | Invokes a File Open dialog box for selecting a Python script to run and automatically connect to. After a selection is made, a Python Script Options dialog box is invoked to allow for command-line options to be added. The Python script must create a new CORE Session and add this session to the daemon's list of sessions in order for this to work. |
| Quit                  | The Quit command should be used to exit the CORE GUI. CORE may prompt for termination if you are currently in Execute mode. Preferences and the recently-used files list are saved.                                                                                                                                                                         |

### Edit Menu

| Option                   | Description                                                                                                                                                                                                                                                                                                                                                                                                                                 |
|--------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Preferences              | Invokes the Preferences dialog box.                                                                                                                                                                                                                                                                                                                                                                                                         |
| Custom Nodes             | Custom node creation dialog box.                                                                                                                                                                                                                                                                                                                                                                                                            |
| Undo                     | (Disabled) Attempts to undo the last edit in edit mode.                                                                                                                                                                                                                                                                                                                                                                                     |
| Redo                     | (Disabled) Attempts to redo an edit that has been undone.                                                                                                                                                                                                                                                                                                                                                                                   |
| Cut, Copy, Paste, Delete | Used to cut, copy, paste, and delete a selection. When nodes are pasted, their node numbers are automatically incremented, and existing links are preserved with new IP addresses assigned. Services and their customizations are copied to the new node, but care should be taken as node IP addresses have changed with possibly old addresses remaining in any custom service configurations. Annotations may also be copied and pasted. |

### Canvas Menu

The canvas menu provides commands related to the editing canvas.

| Option     | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
|------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Size/scale | Invokes a Canvas Size and Scale dialog that allows configuring the canvas size, scale, and geographic reference point. The size controls allow changing the width and height of the current canvas, in pixels or meters. The scale allows specifying how many meters are equivalent to 100 pixels. The reference point controls specify the latitude, longitude, and altitude reference point used to convert between geographic and Cartesian coordinate systems. By clicking the *Save as default* option, all new canvases will be created with these properties. The default canvas size can also be changed in the Preferences dialog box. |
| Wallpaper  | Used for setting the canvas background image.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |

### View Menu

The View menu features items for toggling on and off their display on the canvas.

| Option          | Description                       |
|-----------------|-----------------------------------|
| Interface Names | Display interface names on links. |
| IPv4 Addresses  | Display IPv4 addresses on links.  |
| IPv6 Addresses  | Display IPv6 addresses on links.  |
| Node Labels     | Display node names.               |
| Link Labels     | Display link labels.              |
| Annotations     | Display annotations.              |
| Canvas Grid     | Display the canvas grid.          |

### Tools Menu

The tools menu lists different utility functions.

| Option        | Description                                                                                                                                                                                                                                        |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Find          | Display find dialog used for highlighting a node on the canvas.                                                                                                                                                                                    |
| Auto Grid     | Automatically layout nodes in a grid.                                                                                                                                                                                                              |
| IP addresses  | Invokes the IP Addresses dialog box for configuring which IPv4/IPv6 prefixes are used when automatically addressing new interfaces.                                                                                                                |
| MAC addresses | Invokes the MAC Addresses dialog box for configuring the starting number used as the lowest byte when generating each interface MAC address. This value should be changed when tunneling between CORE emulations to prevent MAC address conflicts. |

### Widgets Menu

Widgets are GUI elements that allow interaction with a running emulation.
Widgets typically automate the running of commands on emulated nodes to report
status information of some type and display this on screen.

#### Periodic Widgets

These Widgets are those available from the main *Widgets* menu. More than one
of these Widgets may be run concurrently. An event loop fires once every second
that the emulation is running. If one of these Widgets is enabled, its periodic
routine will be invoked at this time. Each Widget may have a configuration
dialog box which is also accessible from the *Widgets* menu.

Here are some standard widgets:

* **Adjacency** - displays router adjacency states for Quagga's OSPFv2 and OSPFv3
  routing protocols. A line is drawn from each router halfway to the router ID
  of an adjacent router. The color of the line is based on the OSPF adjacency
  state such as Two-way or Full. To learn about the different colors, see the
  *Configure Adjacency...* menu item. The **vtysh** command is used to
  dump OSPF neighbor information.
  Only half of the line is drawn because each
  router may be in a different adjacency state with respect to the other.
* **Throughput** - displays the kilobits-per-second throughput above each link,
  using statistics gathered from the ng_pipe Netgraph node that implements each
  link. If the throughput exceeds a certain threshold, the link will become
  highlighted. For wireless nodes which broadcast data to all nodes in range,
  the throughput rate is displayed next to the node and the node will become
  circled if the threshold is exceeded.

#### Observer Widgets

These Widgets are available from the **Observer Widgets** submenu of the
**Widgets** menu, and from the Widgets Tool on the toolbar. Only one Observer Widget may
be used at a time. Mouse over a node while the session is running to pop up
an informational display about that node.

Available Observer Widgets include IPv4 and IPv6 routing tables, socket
information, list of running processes, and OSPFv2/v3 neighbor information.

Observer Widgets may be edited by the user and rearranged. Choosing
**Widgets->Observer Widgets->Edit Observers** from the Observer Widget menu will
invoke the Observer Widgets dialog. A list of Observer Widgets is displayed along
with up and down arrows for rearranging the list. Controls are available for
renaming each widget, for changing the command that is run during mouse over, and
for adding and deleting items from the list. Note that specified commands should
return immediately to avoid delays in the GUI display. Changes are saved to a
**config.yaml** file in the CORE configuration directory.

### Session Menu

The Session Menu has entries for starting, stopping, and managing sessions,
in addition to global options such as node types, comments, hooks, servers,
and options.

| Option   | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
|----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Sessions | Invokes the CORE Sessions dialog box containing a list of active CORE sessions in the daemon. Basic session information such as name, node count, start time, and a thumbnail are displayed. This dialog allows connecting to different sessions, shutting them down, or starting a new session.                                                                                                                                                                    |
| Servers  | Invokes the CORE emulation servers dialog for configuring.                                                                                                                                                                                                                                                                                                                                                                                                          |
| Options  | Presents per-session options, such as the IPv4 prefix to be used, if any, for a control network the ability to preserve the session directory; and an on/off switch for SDT3D support.                                                                                                                                                                                                                                                                              |
| Hooks    | Invokes the CORE Session Hooks window where scripts may be configured for a particular session state. The session states are defined in the [table](#session-states) below. The top of the window has a list of configured hooks, and buttons on the bottom left allow adding, editing, and removing hook scripts. The new or edit button will open a hook script editing window.  A hook script is a shell script invoked on the host (not within a virtual node). |

#### Session States

| State         | Description                                                                                                                                                                          |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Definition    | Used by the GUI to tell the backend to clear any state.                                                                                                                              |
| Configuration | When the user presses the *Start* button, node, link, and other configuration data is sent to the backend. This state is also reached when the user customizes a service.            |
| Instantiation | After configuration data has been sent, just before the nodes are created.                                                                                                           |
| Runtime       | All nodes and networks have been built and are running. (This is the same state at which the previously-named *global experiment script* was run.)                                   |
| Datacollect   | The user has pressed the *Stop* button, but before services have been stopped and nodes have been shut down. This is a good time to collect log files and other data from the nodes. |
| Shutdown      | All nodes and networks have been shut down and destroyed.                                                                                                                            |

### Help Menu

| Option                   | Description                                                   |
|--------------------------|---------------------------------------------------------------|
| CORE Github (www)        | Link to the CORE GitHub page.                                 |
| CORE Documentation (www) | Lnk to the CORE Documentation page.                           |
| About                    | Invokes the About dialog box for viewing version information. |

## Connecting with Physical Networks

CORE's emulated networks run in real time, so they can be connected to live
physical networks. The RJ45 tool and the Tunnel tool help with connecting to
the real world. These tools are available from the **Link-layer nodes** menu.

When connecting two or more CORE emulations together, MAC address collisions
should be avoided. CORE automatically assigns MAC addresses to interfaces when
the emulation is started, starting with **00:00:00:aa:00:00** and incrementing
the bottom byte. The starting byte should be changed on the second CORE machine
using the **Tools->MAC Addresses** option the menu.

### RJ45 Tool

The RJ45 node in CORE represents a physical interface on the real CORE machine.
Any real-world network device can be connected to the interface and communicate
with the CORE nodes in real time.

The main drawback is that one physical interface is required for each
connection. When the physical interface is assigned to CORE, it may not be used
for anything else. Another consideration is that the computer or network that
you are connecting to must be co-located with the CORE machine.

To place an RJ45 connection, click on the **Link-layer nodes** toolbar and select
the **RJ45 Tool** from the submenu. Click on the canvas near the node you want to
connect to. This could be a router, hub, switch, or WLAN, for example. Now
click on the *Link Tool* and draw a link between the RJ45 and the other node.
The RJ45 node will display "UNASSIGNED". Double-click the RJ45 node to assign a
physical interface. A list of available interfaces will be shown, and one may
be selected by double-clicking its name in the list, or an interface name may
be entered into the text box.

> **NOTE:** When you press the Start button to instantiate your topology, the
   interface assigned to the RJ45 will be connected to the CORE topology. The
   interface can no longer be used by the system.

Multiple RJ45 nodes can be used within CORE and assigned to the same physical
interface if 802.1x VLANs are used. This allows for more RJ45 nodes than
physical ports are available, but the (e.g. switching) hardware connected to
the physical port must support the VLAN tagging, and the available bandwidth
will be shared.

You need to create separate VLAN virtual devices on the Linux host,
and then assign these devices to RJ45 nodes inside of CORE. The VLANning is
actually performed outside of CORE, so when the CORE emulated node receives a
packet, the VLAN tag will already be removed.

Here are example commands for creating VLAN devices under Linux:

```shell
ip link add link eth0 name eth0.1 type vlan id 1
ip link add link eth0 name eth0.2 type vlan id 2
ip link add link eth0 name eth0.3 type vlan id 3
```

### Tunnel Tool

The tunnel tool builds GRE tunnels between CORE emulations or other hosts.
Tunneling can be helpful when the number of physical interfaces is limited or
when the peer is located on a different network. Also a physical interface does
not need to be dedicated to CORE as with the RJ45 tool.

The peer GRE tunnel endpoint may be another CORE machine or another
host that supports GRE tunneling. When placing a Tunnel node, initially
the node will display "UNASSIGNED". This text should be replaced with the IP
address of the tunnel peer. This is the IP address of the other CORE machine or
physical machine, not an IP address of another virtual node.

> **NOTE:** Be aware of possible MTU (Maximum Transmission Unit) issues with GRE devices. The *gretap* device
   has an interface MTU of 1,458 bytes; when joined to a Linux bridge, the
   bridge's MTU
   becomes 1,458 bytes. The Linux bridge will not perform fragmentation for
   large packets if other bridge ports have a higher MTU such as 1,500 bytes.

The GRE key is used to identify flows with GRE tunneling. This allows multiple
GRE tunnels to exist between that same pair of tunnel peers. A unique number
should be used when multiple tunnels are used with the same peer. When
configuring the peer side of the tunnel, ensure that the matching keys are
used.

Here are example commands for building the other end of a tunnel on a Linux
machine. In this example, a router in CORE has the virtual address
**10.0.0.1/24** and the CORE host machine has the (real) address
**198.51.100.34/24**.  The Linux box
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

### Communicating with the Host Machine

The host machine that runs the CORE GUI and/or daemon is not necessarily
accessible from a node. Running an X11 application on a node, for example,
requires some channel of communication for the application to connect with
the X server for graphical display. There are several different ways to
connect from the node to the host and vice versa.

#### Control Network

The quickest way to connect with the host machine through the primary control
network.

With a control network, the host can launch an X11 application on a node.
To run an X11 application on the node, the **SSH** service can be enabled on
the node, and SSH with X11 forwarding can be used from the host to the node.

```shell
# SSH from host to node n5 to run an X11 app
ssh -X 172.16.0.5 xclock
```

Note that the **coresendmsg** utility can be used for a node to send
messages to the CORE daemon running on the host (if the **listenaddr = 0.0.0.0**
is set in the **/etc/core/core.conf** file) to interact with the running
emulation. For example, a node may move itself or other nodes, or change
its icon based on some node state.

#### Other Methods

There are still other ways to connect a host with a node. The RJ45 Tool
can be used in conjunction with a dummy interface to access a node:

```shell
sudo modprobe dummy numdummies=1
```

A **dummy0** interface should appear on the host. Use the RJ45 tool assigned
to **dummy0**, and link this to a node in your scenario. After starting the
session, configure an address on the host.

```shell
sudo ip link show type bridge
# determine bridge name from the above command
# assign an IP address on the same network as the linked node
sudo ip addr add 10.0.1.2/24 dev b.48304.34658
```

In the example shown above, the host will have the address **10.0.1.2** and
the node linked to the RJ45 may have the address **10.0.1.1**.

## Building Sample Networks

### Wired Networks

Wired networks are created using the **Link Tool** to draw a link between two
nodes. This automatically draws a red line representing an Ethernet link and
creates new interfaces on network-layer nodes.

Double-click on the link to invoke the **link configuration** dialog box. Here
you can change the Bandwidth, Delay, Loss, and Duplicate
rate parameters for that link. You can also modify the color and width of the
link, affecting its display.

Link-layer nodes are provided for modeling wired networks. These do not create
a separate network stack when instantiated, but are implemented using Linux bridging.
These are the hub, switch, and wireless LAN nodes. The hub copies each packet from
the incoming link to every connected link, while the switch behaves more like an
Ethernet switch and keeps track of the Ethernet address of the connected peer,
forwarding unicast traffic only to the appropriate ports.

The wireless LAN (WLAN) is covered in the next section.

### Wireless Networks

The wireless LAN node allows you to build wireless networks where moving nodes
around affects the connectivity between them. Connection between a pair of nodes is stronger
when the nodes are closer while connection is weaker when the nodes are further away.
The wireless LAN, or WLAN, node appears as a small cloud. The WLAN offers
several levels of wireless emulation fidelity, depending on your modeling needs.

The WLAN tool can be extended with plug-ins for different levels of wireless
fidelity. The basic on/off range is the default setting available on all
platforms. Other plug-ins offer higher fidelity at the expense of greater
complexity and CPU usage. The availability of certain plug-ins varies depending
on platform. See the table below for a brief overview of wireless model types.


| Model | Type    | Supported Platform(s) | Fidelity | Description                                                                   |
|-------|---------|-----------------------|----------|-------------------------------------------------------------------------------|
| Basic | on/off  | Linux                 | Low      | Ethernet bridging with nftables                                               |
| EMANE | Plug-in | Linux                 | High     | TAP device connected to EMANE emulator with pluggable MAC and PHY radio types |

To quickly build a wireless network, you can first place several router nodes
onto the canvas. If you have the
Quagga MDR software installed, it is
recommended that you use the **mdr** node type for reduced routing overhead. Next
choose the **WLAN** from the **Link-layer nodes** submenu. First set the
desired WLAN parameters by double-clicking the cloud icon. Then you can link
all selected right-clicking on the WLAN and choosing **Link to Selected**.

Linking a router to the WLAN causes a small antenna to appear, but no red link
line is drawn. Routers can have multiple wireless links and both wireless and
wired links (however, you will need to manually configure route
redistribution.) The mdr node type will generate a routing configuration that
enables OSPFv3 with MANET extensions. This is a Boeing-developed extension to
Quagga's OSPFv3 that reduces flooding overhead and optimizes the flooding
procedure for mobile ad-hoc (MANET) networks.

The default configuration of the WLAN is set to use the basic range model. Having this model
selected causes **core-daemon** to calculate the distance between nodes based
on screen pixels. A numeric range in screen pixels is set for the wireless
network using the **Range** slider. When two wireless nodes are within range of
each other, a green line is drawn between them and they are linked.  Two
wireless nodes that are farther than the range pixels apart are not linked.
During Execute mode, users may move wireless nodes around by clicking and
dragging them, and wireless links will be dynamically made or broken.

The **EMANE Nodes** leverage available EMANE models to use for wireless networking.
See the [EMANE](emane.md) chapter for details on using EMANE.

### Mobility Scripting

CORE has a few ways to script mobility.

| Option       | Description                                                                                                                                                                     |
|--------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ns-2 script  | The script specifies either absolute positions or waypoints with a velocity. Locations are given with Cartesian coordinates.                                                    |
| CORE API     | An external entity can move nodes by sending CORE API Node messages with updated X,Y coordinates; the **coresendmsg** utility allows a shell script to generate these messages. |
| EMANE events | See [EMANE](emane.md) for details on using EMANE scripts to move nodes around. Location information is typically given as latitude, longitude, and altitude.                    |

For the first method, you can create a mobility script using a text
editor, or using a tool such as [BonnMotion](http://net.cs.uni-bonn.de/wg/cs/applications/bonnmotion/),  and associate the script with one of the wireless
using the WLAN configuration dialog box. Click the *ns-2 mobility script...*
button, and set the *mobility script file* field in the resulting *ns2script*
configuration dialog.

Here is an example for creating a BonnMotion script for 10 nodes:

```shell
bm -f sample RandomWaypoint -n 10 -d 60 -x 1000 -y 750
bm NSFile -f sample
# use the resulting 'sample.ns_movements' file in CORE
```

When the Execute mode is started and one of the WLAN nodes has a mobility
script, a mobility script window will appear. This window contains controls for
starting, stopping, and resetting the running time for the mobility script. The
**loop** checkbox causes the script to play continuously. The **resolution** text
box contains the number of milliseconds between each timer event; lower values
cause the mobility to appear smoother but consumes greater CPU time.

The format of an ns-2 mobility script looks like:

```shell
# nodes: 3, max time: 35.000000, max x: 600.00, max y: 600.00
$node_(2) set X_ 144.0
$node_(2) set Y_ 240.0
$node_(2) set Z_ 0.00
$ns_ at 1.00 "$node_(2) setdest 130.0 280.0 15.0"
```

The first three lines set an initial position for node 2. The last line in the
above example causes node 2 to move towards the destination **(130, 280)** at
speed **15**. All units are screen coordinates, with speed in units per second.
The total script time is learned after all nodes have reached their waypoints.
Initially, the time slider in the mobility script dialog will not be
accurate.

Examples mobility scripts (and their associated topology files) can be found
in the **configs/** directory.

## Alerts

The alerts button is located in the bottom right-hand corner
of the status bar in the CORE GUI. This will change colors to indicate one or
more problems with the running emulation. Clicking on the alerts button will invoke the
alerts dialog.

The alerts dialog contains a list of alerts received from
the CORE daemon. An alert has a time, severity level, optional node number,
and source. When the alerts button is red, this indicates one or more fatal
exceptions. An alert with a fatal severity level indicates that one or more
of the basic pieces of emulation could not be created, such as failure to
create a bridge or namespace, or the failure to launch EMANE processes for an
EMANE-based network.

Clicking on an alert displays details for that
exceptio. The exception source is a text string
to help trace where the exception occurred; "service:UserDefined" for example,
would appear for a failed validation command with the UserDefined service.

A button is available at the bottom of the dialog for clearing the exception
list.

## Customizing your Topology's Look

Several annotation tools are provided for changing the way your topology is
presented. Captions may be added with the Text tool. Ovals and rectangles may
be drawn in the background, helpful for visually grouping nodes together.

During live demonstrations the marker tool may be helpful for drawing temporary
annotations on the canvas that may be quickly erased. A size and color palette
appears at the bottom of the toolbar when the marker tool is selected. Markings
are only temporary and are not saved in the topology file.

The basic node icons can be replaced with a custom image of your choice. Icons
appear best when they use the GIF or PNG format with a transparent background.
To change a node's icon, double-click the node to invoke its configuration
dialog and click on the button to the right of the node name that shows the
node's current icon.

A background image for the canvas may be set using the *Wallpaper...* option
from the *Canvas* menu. The image may be centered, tiled, or scaled to fit the
canvas size. An existing terrain, map, or network diagram could be used as a
background, for example, with CORE nodes drawn on top.
