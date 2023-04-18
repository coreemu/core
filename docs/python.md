# Python API

## Overview

Writing your own Python scripts offers a rich programming environment with
complete control over all aspects of the emulation.

The scripts need to be ran with root privileges because they create new network
namespaces. In general, a CORE Python script does not connect to the CORE
daemon, in fact the *core-daemon* is just another Python script that uses
the CORE Python modules and exchanges messages with the GUI.

## Examples

### Node Models

When creating nodes of type `core.nodes.base.CoreNode` these are the default models
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
a `core.emulator.data.InterfaceData` class instead with appropriate information.

Manually creating interface data:

```python
from core.emulator.data import InterfaceData

# id is optional and will set to the next available id
# name is optional and will default to eth<id>
# mac is optional and will result in a randomly generated mac
iface_data = InterfaceData(
    id=0,
    name="eth0",
    ip4="10.0.0.1",
    ip4_mask=24,
    ip6="2001::",
    ip6_mask=64,
)
```

Leveraging the interface prefixes helper class:

```python
from core.emulator.data import IpPrefixes

ip_prefixes = IpPrefixes(ip4_prefix="10.0.0.0/24", ip6_prefix="2001::/64")
# node is used to get an ip4/ip6 address indexed from within the above prefixes
# name is optional and would default to eth<id>
# mac is optional and will result in a randomly generated mac
iface_data = ip_prefixes.create_iface(
    node=node, name="eth0", mac="00:00:00:00:aa:00"
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
def event_listener(event):
    print(event)


# add an event listener to event type you want to listen to
# each handler will receive an object unique to that type
session.event_handlers.append(event_listener)
session.exception_handlers.append(event_listener)
session.node_handlers.append(event_listener)
session.link_handlers.append(event_listener)
session.file_handlers.append(event_listener)
session.config_handlers.append(event_listener)
```

### Configuring Links

Links can be configured at the time of creation or during runtime.

Currently supported configuration options:

* bandwidth (bps)
* delay (us)
* dup (%)
* jitter (us)
* loss (%)

```python
from core.emulator.data import LinkOptions

# configuring when creating a link
options = LinkOptions(
    bandwidth=54_000_000,
    delay=5000,
    dup=5,
    loss=5.5,
    jitter=0,
)
session.add_link(n1_id, n2_id, iface1_data, iface2_data, options)

# configuring during runtime
session.update_link(n1_id, n2_id, iface1_id, iface2_id, options)
```

### Peer to Peer Example

```python
# required imports
from core.emulator.coreemu import CoreEmu
from core.emulator.data import IpPrefixes
from core.emulator.enumerations import EventTypes
from core.nodes.base import CoreNode, Position

# ip nerator for example
ip_prefixes = IpPrefixes(ip4_prefix="10.0.0.0/24")

# create emulator instance for creating sessions and utility methods
coreemu = CoreEmu()
session = coreemu.create_session()

# must be in configuration state for nodes to start, when using "node_add" below
session.set_state(EventTypes.CONFIGURATION_STATE)

# create nodes
position = Position(x=100, y=100)
n1 = session.add_node(CoreNode, position=position)
position = Position(x=300, y=100)
n2 = session.add_node(CoreNode, position=position)

# link nodes together
iface1 = ip_prefixes.create_iface(n1)
iface2 = ip_prefixes.create_iface(n2)
session.add_link(n1.id, n2.id, iface1, iface2)

# start session
session.instantiate()

# do whatever you like here
input("press enter to shutdown")

# stop session
session.shutdown()
```

### Switch/Hub Example

```python
# required imports
from core.emulator.coreemu import CoreEmu
from core.emulator.data import IpPrefixes
from core.emulator.enumerations import EventTypes
from core.nodes.base import CoreNode, Position
from core.nodes.network import SwitchNode

# ip nerator for example
ip_prefixes = IpPrefixes(ip4_prefix="10.0.0.0/24")

# create emulator instance for creating sessions and utility methods
coreemu = CoreEmu()
session = coreemu.create_session()

# must be in configuration state for nodes to start, when using "node_add" below
session.set_state(EventTypes.CONFIGURATION_STATE)

# create switch
position = Position(x=200, y=200)
switch = session.add_node(SwitchNode, position=position)

# create nodes
position = Position(x=100, y=100)
n1 = session.add_node(CoreNode, position=position)
position = Position(x=300, y=100)
n2 = session.add_node(CoreNode, position=position)

# link nodes to switch
iface1 = ip_prefixes.create_iface(n1)
session.add_link(n1.id, switch.id, iface1)
iface1 = ip_prefixes.create_iface(n2)
session.add_link(n2.id, switch.id, iface1)

# start session
session.instantiate()

# do whatever you like here
input("press enter to shutdown")

# stop session
session.shutdown()
```

### WLAN Example

```python
# required imports
from core.emulator.coreemu import CoreEmu
from core.emulator.data import IpPrefixes
from core.emulator.enumerations import EventTypes
from core.location.mobility import BasicRangeModel
from core.nodes.base import CoreNode, Position
from core.nodes.network import WlanNode

# ip nerator for example
ip_prefixes = IpPrefixes(ip4_prefix="10.0.0.0/24")

# create emulator instance for creating sessions and utility methods
coreemu = CoreEmu()
session = coreemu.create_session()

# must be in configuration state for nodes to start, when using "node_add" below
session.set_state(EventTypes.CONFIGURATION_STATE)

# create wlan
position = Position(x=200, y=200)
wlan = session.add_node(WlanNode, position=position)

# create nodes
options = CoreNode.create_options()
options.model = "mdr"
position = Position(x=100, y=100)
n1 = session.add_node(CoreNode, position=position, options=options)
position = Position(x=300, y=100)
n2 = session.add_node(CoreNode, position=position, options=options)

# configuring wlan
session.mobility.set_model_config(wlan.id, BasicRangeModel.name, {
    "range": "280",
    "bandwidth": "55000000",
    "delay": "6000",
    "jitter": "5",
    "error": "5",
})

# link nodes to wlan
iface1 = ip_prefixes.create_iface(n1)
session.add_link(n1.id, wlan.id, iface1)
iface1 = ip_prefixes.create_iface(n2)
session.add_link(n2.id, wlan.id, iface1)

# start session
session.instantiate()

# do whatever you like here
input("press enter to shutdown")

# stop session
session.shutdown()
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
from core.emane.models.ieee80211abg import EmaneIeee80211abgModel
from core.emane.nodes import EmaneNet
from core.emulator.coreemu import CoreEmu
from core.emulator.data import IpPrefixes
from core.emulator.enumerations import EventTypes
from core.nodes.base import CoreNode, Position

# ip nerator for example
ip_prefixes = IpPrefixes(ip4_prefix="10.0.0.0/24")

# create emulator instance for creating sessions and utility methods
coreemu = CoreEmu()
session = coreemu.create_session()

# location information is required to be set for emane
session.location.setrefgeo(47.57917, -122.13232, 2.0)
session.location.refscale = 150.0

# must be in configuration state for nodes to start, when using "node_add" below
session.set_state(EventTypes.CONFIGURATION_STATE)

# create emane
options = EmaneNet.create_options()
options.emane_model = EmaneIeee80211abgModel.name
position = Position(x=200, y=200)
emane = session.add_node(EmaneNet, position=position, options=options)

# create nodes
options = CoreNode.create_options()
options.model = "mdr"
position = Position(x=100, y=100)
n1 = session.add_node(CoreNode, position=position, options=options)
position = Position(x=300, y=100)
n2 = session.add_node(CoreNode, position=position, options=options)

# configure general emane settings
config = session.emane.get_configs()
config.update({
    "eventservicettl": "2"
})

# configure emane model settings
# using a dict mapping currently support values as strings
session.emane.set_model_config(emane.id, EmaneIeee80211abgModel.name, {
    "unicastrate": "3",
})

# link nodes to emane
iface1 = ip_prefixes.create_iface(n1)
session.add_link(n1.id, emane.id, iface1)
iface1 = ip_prefixes.create_iface(n2)
session.add_link(n2.id, emane.id, iface1)

# start session
session.instantiate()

# do whatever you like here
input("press enter to shutdown")

# stop session
session.shutdown()
```

EMANE Model Configuration:

```python
from core import utils

# standardized way to retrieve an appropriate config id
# iface id can be omitted, to allow a general configuration for a model, per node
config_id = utils.iface_config_id(node.id, iface_id)
# set emane configuration for the config id
session.emane.set_config(config_id, EmaneIeee80211abgModel.name, {
    "unicastrate": "3",
})
```

## Configuring a Service

Services help generate and run bash scripts on nodes for a given purpose.

Configuring the files of a service results in a specific hard coded script being
generated, instead of the default scripts, that may leverage dynamic generation.

The following features can be configured for a service:

* configs - files that will be generated
* dirs - directories that will be mounted unique to the node
* startup - commands to run start a service
* validate - commands to run to validate a service
* shutdown - commands to run to stop a service

Editing service properties:

```python
# configure a service, for a node, for a given session
session.services.set_service(node_id, service_name)
service = session.services.get_service(node_id, service_name)
service.configs = ("file1.sh", "file2.sh")
service.dirs = ("/etc/node",)
service.startup = ("bash file1.sh",)
service.validate = ()
service.shutdown = ()
```

When editing a service file, it must be the name of `config`
file that the service will generate.

Editing a service file:

```python
# to edit the contents of a generated file you can specify
# the service, the file name, and its contents
session.services.set_service_file(
    node_id,
    service_name,
    file_name,
    "echo hello",
)
```

## File Examples

File versions of the network examples can be found
[here](https://github.com/coreemu/core/tree/master/package/examples/python).

## Executing Scripts from GUI

To execute a python script from a GUI you need have the following.

The builtin name check here to know it is being executed from the GUI, this can
be avoided if your script does not use a name check.

```python
if __name__ in ["__main__", "__builtin__"]:
    main()
```

A script can add sessions to the core-daemon. A global *coreemu* variable is
exposed to the script pointing to the *CoreEmu* object.

The example below has a fallback to a new CoreEmu object, in the case you would
like to run the script standalone, outside of the core-daemon.

```python
coreemu = globals().get("coreemu") or CoreEmu()
session = coreemu.create_session()
```
