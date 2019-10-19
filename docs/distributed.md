# CORE - Distributed Emulation

* Table of Contents
{:toc}

## Overview

A large emulation scenario can be deployed on multiple emulation servers and
controlled by a single GUI. The GUI, representing the entire topology, can be
run on one of the emulation servers or on a separate machine.

Each machine that will act as an emulation will require the installation of a distributed CORE package and
some configuration to allow SSH as root.

## Configuring SSH

Distributed CORE works using the python fabric library to run commands on remote servers over SSH.

### Remote GUI Terminals

You need to have the same user defined on each server, since the user used 
for these remote shells is the same user that is running the CORE GUI.

**Edit -> Preferences... -> Terminal program:**

Currently recommend setting this to **xterm -e** as the default 
**gnome-terminal** will not work.

May need to install xterm if, not already installed.

```shell
sudo apt install xterm
```

### Distributed Server SSH Configuration

First the distributed servers must be configured to allow passwordless root login over SSH.

On distributed server:
```shelll
# install openssh-server
sudo apt install openssh-server

# open sshd config
vi /etc/ssh/sshd_config

# verify these configurations in file
PermitRootLogin yes
PasswordAuthentication yes

# restart sshd
sudo systemctl restart sshd
```

On master server:
```shell
# install package if needed
sudo apt install openssh-client

# generate ssh key if needed
ssh-keygen -o -t rsa -b 4096 -f ~/.ssh/core

# copy public key to authorized_keys file
ssh-copy-id -i ~/.ssh/core root@server

# configure fabric to use the core ssh key
sudo vi /etc/fabric.yml
``` 

On distributed server:
```shell
# open sshd config
vi /etc/ssh/sshd_config

# change configuration for root login to without password
PermitRootLogin without-password

# restart sshd
sudo systemctl restart sshd
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
the select tool (ctrl-click to select multiple), and right-click one of the
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

```shell
emane_event_generate = True
```

## Distributed Checklist

1. Install CORE on master server
1. Install distributed CORE package on all servers needed
1. Installed and configure public-key SSH access on all servers (if you want to use
double-click shells or Widgets.) for both the GUI user (for terminals) and root for running CORE commands
1. Choose the servers that participate in distributed emulation.
1. Assign nodes to desired servers, empty for master server.
1. Press the **Start** button to launch the distributed emulation.
