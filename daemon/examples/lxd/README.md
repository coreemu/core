# LXD Support

Information on how LXD can be leveraged and included to create
nodes based on LXC containers and images to interface with
existing CORE nodes, when needed.

## Installation

```shell
sudo snap install lxd
```

## Configuration

Initialize LXD and say no to adding a default bridge.

```shell
sudo lxd init
```

## Group Setup

To use LXC nodes within the python GUI, you will need to make sure the user running the GUI is a member of the
lxd group.

```shell
# add group if does not exist
sudo groupadd lxd

# add user to group
sudo usermod -aG lxd $USER

# to get this change to take effect, log out and back in or run the following
newgrp lxd
```

## Tools and Versions Tested With

* LXD 3.14
* nsenter from util-linux 2.31.1

## Examples

This directory provides a few small examples creating LXC nodes
using LXD and linking them to themselves or with standard CORE nodes.
