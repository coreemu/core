# LXD Support

Information on how LXD can be leveraged and included to create
nodes based on LXC containers and images to interface with
existing CORE nodes, when needed.

# Installation

```shell
sudo snap install lxd
```

# Configuration

Initialize LXD and say no to adding a default bridge.

```shell
sudo lxd init
```

# Tools and Versions Tested With

* LXD 3.14
* nsenter from util-linux 2.31.1

# Examples

This directory provides a few small examples creating LXC nodes
using LXD and linking them to themselves or with standard CORE nodes.
