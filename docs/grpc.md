# gRPC API

* Table of Contents
{:toc}

[gRPC](https://grpc.io/) is a client/server API for interfacing with CORE
and used by the python GUI for driving all functionality. It is dependent
on having a running `core-daemon` instance to be leveraged.

A python client can be created from the raw generated grpc files included
with CORE or one can leverage a provided gRPC client that helps encapsulate
some of the functionality to try and help make things easier.

## Python Client

A python client wrapper is provided at
[CoreGrpcClient](https://github.com/coreemu/core/blob/master/daemon/core/api/grpc/client.py)
to help provide some conveniences when using the API.

### Client HTTP Proxy

Since gRPC is HTTP2 based, proxy configurations can cause issues. By default
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
a `core.api.grpc.core_pb2.Interface` class instead with appropriate information.

Manually creating gRPC interface data:
```python
from core.api.grpc import core_pb2
# id is optional and will set to the next available id
# name is optional and will default to eth<id>
# mac is optional and will result in a randomly generated mac
iface_data = core_pb2.Interface(
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
from core.api.grpc import core_pb2

def event_listener(event):
    print(event)

# provide no events to listen to all events
core.events(session_id, event_listener)

# provide events to listen to specific events
core.events(session_id, event_listener, [core_pb2.EventType.NODE])
```

### Configuring Links

Links can be configured at the time of creation or during runtime.

```python
from core.api.grpc import core_pb2

# configuring when creating a link
# below are the currently supported configuration options
# bandwidth in bps
# delay in us
# duplicate in %
# jitter in us
# loss in %
options = core_pb2.LinkOptions(
    bandwidth=54_000_000,
    delay=5000,
    dup=5,
    loss=5.5,
    jitter=0,
)
core.add_link(session_id, n1_id, n2_id, iface1_data, iface2_data, options)

# configuring during runtime
core.edit_link(session_id, n1_id, n2_id, iface1_id, iface2_id, options)
```

### Peer to Peer Example
```python
# required imports
from core.api.grpc import client
from core.api.grpc.core_pb2 import Node, NodeType, Position, SessionState

# interface helper
iface_helper = client.InterfaceHelper(ip4_prefix="10.0.0.0/24", ip6_prefix="2001::/64")

# create grpc client and connect
core = client.CoreGrpcClient()
core.connect()

# create session and get id
response = core.create_session()
session_id = response.session_id

# change session state to configuration so that nodes get started when added
core.set_session_state(session_id, SessionState.CONFIGURATION)

# create node one
position = Position(x=100, y=100)
n1 = Node(type=NodeType.DEFAULT, position=position, model="PC")
response = core.add_node(session_id, n1)
n1_id = response.node_id

# create node two
position = Position(x=300, y=100)
n2 = Node(type=NodeType.DEFAULT, position=position, model="PC")
response = core.add_node(session_id, n2)
n2_id = response.node_id

# links nodes together
iface1 = iface_helper.create_iface(n1_id, 0)
iface2 = iface_helper.create_iface(n2_id, 0)
core.add_link(session_id, n1_id, n2_id, iface1, iface2)

# change session state
core.set_session_state(session_id, SessionState.INSTANTIATION)
```

### Switch/Hub Example
```python
# required imports
from core.api.grpc import client
from core.api.grpc.core_pb2 import Node, NodeType, Position, SessionState

# interface helper
iface_helper = client.InterfaceHelper(ip4_prefix="10.0.0.0/24", ip6_prefix="2001::/64")

# create grpc client and connect
core = client.CoreGrpcClient()
core.connect()

# create session and get id
response = core.create_session()
session_id = response.session_id

# change session state to configuration so that nodes get started when added
core.set_session_state(session_id, SessionState.CONFIGURATION)

# create switch node
position = Position(x=200, y=200)
switch = Node(type=NodeType.SWITCH, position=position)
response = core.add_node(session_id, switch)
switch_id = response.node_id

# create node one
position = Position(x=100, y=100)
n1 = Node(type=NodeType.DEFAULT, position=position, model="PC")
response = core.add_node(session_id, n1)
n1_id = response.node_id

# create node two
position = Position(x=300, y=100)
n2 = Node(type=NodeType.DEFAULT, position=position, model="PC")
response = core.add_node(session_id, n2)
n2_id = response.node_id

# links nodes to switch
iface1 = iface_helper.create_iface(n1_id, 0)
core.add_link(session_id, n1_id, switch_id, iface1)
iface1 = iface_helper.create_iface(n2_id, 0)
core.add_link(session_id, n2_id, switch_id, iface1)

# change session state
core.set_session_state(session_id, SessionState.INSTANTIATION)
```

### WLAN Example
```python
# required imports
from core.api.grpc import client
from core.api.grpc.core_pb2 import Node, NodeType, Position, SessionState

# interface helper
iface_helper = client.InterfaceHelper(ip4_prefix="10.0.0.0/24", ip6_prefix="2001::/64")

# create grpc client and connect
core = client.CoreGrpcClient()
core.connect()

# create session and get id
response = core.create_session()
session_id = response.session_id

# change session state to configuration so that nodes get started when added
core.set_session_state(session_id, SessionState.CONFIGURATION)

# create wlan node
position = Position(x=200, y=200)
wlan = Node(type=NodeType.WIRELESS_LAN, position=position)
response = core.add_node(session_id, wlan)
wlan_id = response.node_id

# create node one
position = Position(x=100, y=100)
n1 = Node(type=NodeType.DEFAULT, position=position, model="mdr")
response = core.add_node(session_id, n1)
n1_id = response.node_id

# create node two
position = Position(x=300, y=100)
n2 = Node(type=NodeType.DEFAULT, position=position, model="mdr")
response = core.add_node(session_id, n2)
n2_id = response.node_id

# configure wlan using a dict mapping currently
# support values as strings
core.set_wlan_config(session_id, wlan_id, {
    "range": "280",
    "bandwidth": "55000000",
    "delay": "6000",
    "jitter": "5",
    "error": "5",
})

# links nodes to wlan
iface1 = iface_helper.create_iface(n1_id, 0)
core.add_link(session_id, n1_id, wlan_id, iface1)
iface1 = iface_helper.create_iface(n2_id, 0)
core.add_link(session_id, n2_id, wlan_id, iface1)

# change session state
core.set_session_state(session_id, SessionState.INSTANTIATION)
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
from core.api.grpc.core_pb2 import Node, NodeType, Position, SessionState
from core.emane.ieee80211abg import EmaneIeee80211abgModel

# interface helper
iface_helper = client.InterfaceHelper(ip4_prefix="10.0.0.0/24", ip6_prefix="2001::/64")

# create grpc client and connect
core = client.CoreGrpcClient()
core.connect()

# create session and get id
response = core.create_session()
session_id = response.session_id

# change session state to configuration so that nodes get started when added
core.set_session_state(session_id, SessionState.CONFIGURATION)

# create emane node
position = Position(x=200, y=200)
emane = Node(type=NodeType.EMANE, position=position, emane=EmaneIeee80211abgModel.name)
response = core.add_node(session_id, emane)
emane_id = response.node_id

# create node one
position = Position(x=100, y=100)
n1 = Node(type=NodeType.DEFAULT, position=position, model="mdr")
response = core.add_node(session_id, n1)
n1_id = response.node_id

# create node two
position = Position(x=300, y=100)
n2 = Node(type=NodeType.DEFAULT, position=position, model="mdr")
response = core.add_node(session_id, n2)
n2_id = response.node_id

# configure general emane settings
core.set_emane_config(session_id, {
    "eventservicettl": "2"
})

# configure emane model settings
# using a dict mapping currently support values as strings
core.set_emane_model_config(session_id, emane_id, EmaneIeee80211abgModel.name, {
    "unicastrate": "3",
})

# links nodes to emane
iface1 = iface_helper.create_iface(n1_id, 0)
core.add_link(session_id, n1_id, emane_id, iface1)
iface1 = iface_helper.create_iface(n2_id, 0)
core.add_link(session_id, n2_id, emane_id, iface1)

# change session state
core.set_session_state(session_id, SessionState.INSTANTIATION)
```

EMANE Model Configuration:
```python
# emane network specific config
core.set_emane_model_config(session_id, emane_id, EmaneIeee80211abgModel.name, {
    "unicastrate": "3",
})

# node specific config
core.set_emane_model_config(session_id, node_id, EmaneIeee80211abgModel.name, {
    "unicastrate": "3",
})

# node interface specific config
core.set_emane_model_config(session_id, node_id, EmaneIeee80211abgModel.name, {
    "unicastrate": "3",
}, iface_id)
```

## Configuring a Service

TBD

## File Examples

File versions of these examples can be found
[here](https://github.com/coreemu/core/tree/master/daemon/examples/grpc).
These examples will create a session using the gRPC API when the core-daemon is running.

You can then switch to and attach to these sessions using either of the CORE GUIs.
