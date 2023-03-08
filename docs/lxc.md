# LXC Support

## Overview

LXC nodes are provided by way of LXD to create nodes using predefined
images and provide file system separation.

## Installation

### Debian Systems

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
