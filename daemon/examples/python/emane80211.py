# required imports
from core.emane.models.ieee80211abg import EmaneIeee80211abgModel
from core.emane.nodes import EmaneNet
from core.emulator.coreemu import CoreEmu
from core.emulator.data import IpPrefixes, NodeOptions
from core.emulator.enumerations import EventTypes
from core.nodes.base import CoreNode

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
options = NodeOptions(x=200, y=200, emane=EmaneIeee80211abgModel.name)
emane = session.add_node(EmaneNet, options=options)

# create nodes
options = NodeOptions(model="mdr", x=100, y=100)
n1 = session.add_node(CoreNode, options=options)
options = NodeOptions(model="mdr", x=300, y=100)
n2 = session.add_node(CoreNode, options=options)

# configure general emane settings
config = session.emane.get_configs()
config.update({"eventservicettl": "2"})

# configure emane model settings
# using a dict mapping currently support values as strings
session.emane.set_model_config(
    emane.id, EmaneIeee80211abgModel.name, {"unicastrate": "3"}
)

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
