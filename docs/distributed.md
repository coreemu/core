# CORE - Distributed Emulation

* Table of Contents
{:toc}

## Overview

A large emulation scenario can be deployed on multiple emulation servers and
controlled by a single GUI. The GUI, representing the entire topology, can be
run on one of the emulation servers or on a separate machine.

Each machine that will act as an emulation server would ideally have the
 same version of CORE installed. It is not important to have the GUI component 
 but the CORE Python daemon **core-daemon** needs to be installed.
 
**NOTE: The server that the GUI connects with is referred to as 
the master server.**

## Configuring Listen Address

First we need to configure the **core-daemon** on all servers to listen on an
interface over the network. The simplest way would be updating the core 
configuration file to listen on all interfaces. Alternatively, configure it to
listen to the specific interface you desire by supplying the correct address.

The **listenaddr** configuration should be set to the address of the interface
that should receive CORE API control commands from the other servers; 
setting **listenaddr = 0.0.0.0** causes the Python daemon to listen on all
interfaces. CORE uses TCP port **4038** by default to communicate from the 
controlling machine (with GUI) to the emulation servers. Make sure that 
firewall rules are configured as necessary to allow this traffic.

```shell
# open configuration file
vi /etc/core/core.conf

# within core.conf
[core-daemon]
listenaddr = 0.0.0.0
```

## Enabling Remote SSH Shells

### Update GUI Terminal Program

**Edit -> Preferences... -> Terminal program:**

Currently recommend setting this to **xterm -e** as the default 
**gnome-terminal** will not work.

May need to install xterm if, not already installed.

```shell
sudo apt install xterm
```

### Setup SSH

In order to easily open shells on the emulation servers, the servers should be
running an SSH server, and public key login should be enabled. This is
accomplished by generating an SSH key for your user on all servers being used
for distributed emulation, if you do not already have one. Then copying your
master server public key to the authorized_keys file on all other servers that
will be used to help drive the distributed emulation. When double-clicking on a
node during runtime, instead of opening a local shell, the GUI will attempt to
SSH to the emulation server to run an interactive shell. 

You need to have the same user defined on each server, since the user used 
for these remote shells is the same user that is running the CORE GUI.

```shell
# install openssh-server
sudo apt install openssh-server

# generate ssh if needed
ssh-keygen -o -t rsa -b 4096

# copy public key to authorized_keys file
ssh-copy-id user@server
# or
scp ~/.ssh/id_rsa.pub username@server:~/.ssh/authorized_keys
```

## Add Emulation Servers in GUI

Within the core-gui navigate to menu option:

**Session -> Emulation servers...**

Within the dialog box presented, add or modify an existing server if present
to use the name, address, and port for the a server you plan to use.

Server configurations are loaded and written to in a configuration file for
the GUI.

**~/.core/servers.conf**
```conf
# name address port
server2 192.168.0.2 4038
```

## Assigning Nodes

The user needs to assign nodes to emulation servers in the scenario. Making no
assignment means the node will be emulated on the master server
In the configuration window of every node, a drop-down box located between
the *Node name* and the *Image* button will select the name of the emulation
server. By default, this menu shows *(none)*, indicating that the node will
be emulated locally on the master. When entering Execute mode, the CORE GUI
will deploy the node on its assigned emulation server.

Another way to assign emulation servers is to select one or more nodes using
the select tool (shift-click to select multiple), and right-click one of the
nodes and choose *Assign to...*.

The **CORE emulation servers** dialog box may also be used to assign nodes to
servers. The assigned server name appears in parenthesis next to the node name.
To assign all nodes to one of the servers, click on the server name and then
the **all nodes** button. Servers that have assigned nodes are shown in blue in
the server list. Another option is to first select a subset of nodes, then open
the **CORE emulation servers** box and use the **selected nodes** button.

**IMPORTANT: Leave the nodes unassigned if they are to be run on the master 
server. Do not explicitly assign the nodes to the master server.**

## GUI Visualization

If there is a link between two nodes residing on different servers, the GUI
will draw the link with a dashed line.

## Concerns and Limitations

Wireless nodes, i.e. those connected to a WLAN node, can be assigned to
different emulation servers and participate in the same wireless network
only if an EMANE model is used for the WLAN. The basic range model does 
not work across multiple servers due to the Linux bridging and ebtables 
rules that are used.

**NOTE: The basic range wireless model does not support distributed emulation,
but EMANE does.**
 
When nodes are linked across servers **core-daemons** will automatically 
create necessary tunnels between the nodes when executed. Care should be taken
to arrange the topology such that the number of tunnels is minimized. The 
tunnels carry data between servers to connect nodes as specified in the topology.
These tunnels are created using GRE tunneling, similar to the Tunnel Tool.

### EMANE Configuration and Issues

EMANE needs to have controlnet configured in **core.conf** in order to startup correctly.
The names before the addresses need to match the servers configured in 
**~/.core/servers.conf** previously.

```shell
controlnet = core1:172.16.1.0/24 core2:172.16.2.0/24 core3:172.16.3.0/24 core4:172.16.4.0/24 core5:172.16.5.0/24
```

EMANE appears to require location events for nodes to be sync'ed across
all EMANE instances for nodes to find each other. Using an EMANE eel file
for your scenario can help clear this up, which might be desired anyway.

* https://github.com/adjacentlink/emane/wiki/EEL-Generator

You can also move nodes within the GUI to help trigger location events from
CORE when the **core.conf** settings below is used. Assuming the nodes
did not find each other by default and you are not using an eel file.

```shell
emane_event_generate = True
```

## Distributed Checklist

1. Install the same version of the CORE daemon on all servers.
1. Set **listenaddr** configuration in all of the server's core.conf files,
then start (or restart) the daemon.
1. Installed and configure public-key SSH access on all servers (if you want to use
double-click shells or Widgets.)
1. Assign nodes to desired servers, empty for master server
1. Press the **Start** button to launch the distributed emulation.
