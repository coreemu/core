* Table of Contents

## Overview

[gRPC](https://grpc.io/) is a client/server API for interfacing with CORE
and used by the python GUI for driving all functionality. It is dependent
on having a running `core-daemon` instance to be leveraged.

A python client can be created from the raw generated grpc files included
with CORE or one can leverage a provided gRPC client that helps encapsulate
some functionality to try and help make things easier.

## Python Client

A python client wrapper is provided at
[CoreGrpcClient](https://github.com/coreemu/core/blob/master/daemon/core/api/grpc/client.py)
to help provide some conveniences when using the API.

### Client HTTP Proxy

Since gRPC is HTTP2 based, proxy configurations can cause issues. By default,
the client disables proxy support to avoid issues when a proxy is present.
You can enable and properly account for this issue when needed.

## Proto Files

Proto files are used to define the API and protobuf messages that are used for
interfaces with this API.

They can be found
[here](https://github.com/coreemu/core/tree/master/daemon/proto/core/api/grpc)
to see the specifics of
what is going on and response message values that would be returned.

## Examples

### Node Models

When creating nodes of type `NodeType.DEFAULT` these are the default models
and the services they map to.

* mdr
    * zebra, OSPFv3MDR, IPForward
* PC
    * DefaultRoute
* router
    * zebra, OSPFv2, OSPFv3, IPForward
* host
    * DefaultRoute, SSH

### Interface Helper

There is an interface helper class that can be leveraged for convenience
when creating interface data for nodes. Alternatively one can manually create
a `core.api.grpc.wrappers.Interface` class instead with appropriate information.

Manually creating gRPC client interface:

```python
from core.api.grpc.wrappers import Interface

# id is optional and will set to the next available id
# name is optional and will default to eth<id>
# mac is optional and will result in a randomly generated mac
iface = Interface(
    id=0,
    name="eth0",
    ip4="10.0.0.1",
    ip4_mask=24,
    ip6="2001::",
    ip6_mask=64,
)
```

Leveraging the interface helper class:

```python
from core.api.grpc import client

iface_helper = client.InterfaceHelper(ip4_prefix="10.0.0.0/24", ip6_prefix="2001::/64")
# node_id is used to get an ip4/ip6 address indexed from within the above prefixes
# iface_id is required and used exactly for that
# name is optional and would default to eth<id>
# mac is optional and will result in a randomly generated mac
iface_data = iface_helper.create_iface(
    node_id=1, iface_id=0, name="eth0", mac="00:00:00:00:aa:00"
)
```

### Listening to Events

Various events that can occur within a session can be listened to.

Event types:

* session - events for changes in session state and mobility start/stop/pause
* node - events for node movements and icon changes
* link - events for link configuration changes and wireless link add/delete
* config - configuration events when legacy gui joins a session
* exception - alert/error events
* file - file events when the legacy gui joins a session

```python
from core.api.grpc import client
from core.api.grpc.wrappers import EventType


def event_listener(event):
    print(event)


# create grpc client and connect
core = client.CoreGrpcClient()
core.connect()

# add session
session = core.create_session()

# provide no events to listen to all events
core.events(session.id, event_listener)

# provide events to listen to specific events
core.events(session.id, event_listener, [EventType.NODE])
```

### Configuring Links

Links can be configured at the time of creation or during runtime.

Currently supported configuration options:

* bandwidth (bps)
* delay (us)
* duplicate (%)
* jitter (us)
* loss (%)

```python
from core.api.grpc import client
from core.api.grpc.wrappers import LinkOptions, Position

# interface helper
iface_helper = client.InterfaceHelper(ip4_prefix="10.0.0.0/24", ip6_prefix="2001::/64")

# create grpc client and connect
core = client.CoreGrpcClient()
core.connect()

# add session
session = core.create_session()

# create nodes
position = Position(x=100, y=100)
node1 = session.add_node(1, position=position)
position = Position(x=300, y=100)
node2 = session.add_node(2, position=position)

# configuring when creating a link
options = LinkOptions(
    bandwidth=54_000_000,
    delay=5000,
    dup=5,
    loss=5.5,
    jitter=0,
)
iface1 = iface_helper.create_iface(node1.id, 0)
iface2 = iface_helper.create_iface(node2.id, 0)
link = session.add_link(node1=node1, node2=node2, iface1=iface1, iface2=iface2)

# configuring during runtime
link.options.loss = 10.0
core.edit_link(session.id, link)
```

### Peer to Peer Example

```python
# required imports
from core.api.grpc import client
from core.api.grpc.wrappers import Position

# interface helper
iface_helper = client.InterfaceHelper(ip4_prefix="10.0.0.0/24", ip6_prefix="2001::/64")

# create grpc client and connect
core = client.CoreGrpcClient()
core.connect()

# add session
session = core.create_session()

# create nodes
position = Position(x=100, y=100)
node1 = session.add_node(1, position=position)
position = Position(x=300, y=100)
node2 = session.add_node(2, position=position)

# create link
iface1 = iface_helper.create_iface(node1.id, 0)
iface2 = iface_helper.create_iface(node2.id, 0)
session.add_link(node1=node1, node2=node2, iface1=iface1, iface2=iface2)

# start session
core.start_session(session)
```

### Switch/Hub Example

```python
# required imports
from core.api.grpc import client
from core.api.grpc.wrappers import NodeType, Position

# interface helper
iface_helper = client.InterfaceHelper(ip4_prefix="10.0.0.0/24", ip6_prefix="2001::/64")

# create grpc client and connect
core = client.CoreGrpcClient()
core.connect()

# add session
session = core.create_session()

# create nodes
position = Position(x=200, y=200)
switch = session.add_node(1, _type=NodeType.SWITCH, position=position)
position = Position(x=100, y=100)
node1 = session.add_node(2, position=position)
position = Position(x=300, y=100)
node2 = session.add_node(3, position=position)

# create links
iface1 = iface_helper.create_iface(node1.id, 0)
session.add_link(node1=node1, node2=switch, iface1=iface1)
iface1 = iface_helper.create_iface(node2.id, 0)
session.add_link(node1=node2, node2=switch, iface1=iface1)

# start session
core.start_session(session)
```

### WLAN Example

```python
# required imports
from core.api.grpc import client
from core.api.grpc.wrappers import NodeType, Position

# interface helper
iface_helper = client.InterfaceHelper(ip4_prefix="10.0.0.0/24", ip6_prefix="2001::/64")

# create grpc client and connect
core = client.CoreGrpcClient()
core.connect()

# add session
session = core.create_session()

# create nodes
position = Position(x=200, y=200)
wlan = session.add_node(1, _type=NodeType.WIRELESS_LAN, position=position)
position = Position(x=100, y=100)
node1 = session.add_node(2, model="mdr", position=position)
position = Position(x=300, y=100)
node2 = session.add_node(3, model="mdr", position=position)

# create links
iface1 = iface_helper.create_iface(node1.id, 0)
session.add_link(node1=node1, node2=wlan, iface1=iface1)
iface1 = iface_helper.create_iface(node2.id, 0)
session.add_link(node1=node2, node2=wlan, iface1=iface1)

# set wlan config using a dict mapping currently
# support values as strings
wlan.set_wlan(
    {
        "range": "280",
        "bandwidth": "55000000",
        "delay": "6000",
        "jitter": "5",
        "error": "5",
    }
)

# start session
core.start_session(session)
```

### EMANE Example

For EMANE you can import and use one of the existing models and
use its name for configuration.

Current models:

* core.emane.ieee80211abg.EmaneIeee80211abgModel
* core.emane.rfpipe.EmaneRfPipeModel
* core.emane.tdma.EmaneTdmaModel
* core.emane.bypass.EmaneBypassModel

Their configurations options are driven dynamically from parsed EMANE manifest files
from the installed version of EMANE.

Options and their purpose can be found at the [EMANE Wiki](https://github.com/adjacentlink/emane/wiki).

If configuring EMANE global settings or model mac/phy specific settings, any value not provided
will use the defaults. When no configuration is used, the defaults are used.

```python
# required imports
from core.api.grpc import client
from core.api.grpc.wrappers import NodeType, Position
from core.emane.models.ieee80211abg import EmaneIeee80211abgModel

# interface helper
iface_helper = client.InterfaceHelper(ip4_prefix="10.0.0.0/24", ip6_prefix="2001::/64")

# create grpc client and connect
core = client.CoreGrpcClient()
core.connect()

# add session
session = core.create_session()

# create nodes
position = Position(x=200, y=200)
emane = session.add_node(
    1, _type=NodeType.EMANE, position=position, emane=EmaneIeee80211abgModel.name
)
position = Position(x=100, y=100)
node1 = session.add_node(2, model="mdr", position=position)
position = Position(x=300, y=100)
node2 = session.add_node(3, model="mdr", position=position)

# create links
iface1 = iface_helper.create_iface(node1.id, 0)
session.add_link(node1=node1, node2=emane, iface1=iface1)
iface1 = iface_helper.create_iface(node2.id, 0)
session.add_link(node1=node2, node2=emane, iface1=iface1)

# setting emane specific emane model configuration
emane.set_emane_model(EmaneIeee80211abgModel.name, {
    "eventservicettl": "2",
    "unicastrate": "3",
})

# start session
core.start_session(session)
```

EMANE Model Configuration:

```python
# emane network specific config, set on an emane node
# this setting applies to all nodes connected
emane.set_emane_model(EmaneIeee80211abgModel.name, {"unicastrate": "3"})

# node specific config for an individual node connected to an emane network
node.set_emane_model(EmaneIeee80211abgModel.name, {"unicastrate": "3"})

# node interface specific config for an individual node connected to an emane network
node.set_emane_model(EmaneIeee80211abgModel.name, {"unicastrate": "3"}, iface_id=0)
```

## Configuring a Service

Services help generate and run bash scripts on nodes for a given purpose.

Configuring the files of a service results in a specific hard coded script being
generated, instead of the default scripts, that may leverage dynamic generation.

The following features can be configured for a service:

* files - files that will be generated
* directories - directories that will be mounted unique to the node
* startup - commands to run start a service
* validate - commands to run to validate a service
* shutdown - commands to run to stop a service

Editing service properties:

```python
# configure a service, for a node, for a given session
node.service_configs[service_name] = NodeServiceData(
    configs=["file1.sh", "file2.sh"],
    directories=["/etc/node"],
    startup=["bash file1.sh"],
    validate=[],
    shutdown=[],
)
```

When editing a service file, it must be the name of `config`
file that the service will generate.

Editing a service file:

```python
# to edit the contents of a generated file you can specify
# the service, the file name, and its contents
file_configs = node.service_file_configs.setdefault(service_name, {})
file_configs[file_name] = "echo hello world"
```

## File Examples

File versions of the network examples can be found
[here](https://github.com/coreemu/core/tree/master/package/examples/grpc).
These examples will create a session using the gRPC API when the core-daemon is running.

You can then switch to and attach to these sessions using either of the CORE GUIs.
