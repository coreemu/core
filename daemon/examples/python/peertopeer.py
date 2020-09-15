# required imports
from core.emulator.coreemu import CoreEmu
from core.emulator.data import IpPrefixes, NodeOptions
from core.emulator.enumerations import EventTypes
from core.nodes.base import CoreNode

# ip nerator for example
ip_prefixes = IpPrefixes(ip4_prefix="10.0.0.0/24")

# create emulator instance for creating sessions and utility methods
coreemu = CoreEmu()
session = coreemu.create_session()

# must be in configuration state for nodes to start, when using "node_add" below
session.set_state(EventTypes.CONFIGURATION_STATE)

# create nodes
options = NodeOptions(x=100, y=100)
n1 = session.add_node(CoreNode, options=options)
options = NodeOptions(x=300, y=100)
n2 = session.add_node(CoreNode, options=options)

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
