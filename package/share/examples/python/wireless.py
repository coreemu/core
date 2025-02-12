# required imports
import logging

from core.emulator.coreemu import CoreEmu
from core.emulator.data import InterfaceData
from core.emulator.enumerations import EventTypes
from core.nodes.base import CoreNode, Position
from core.nodes.network import WlanNode

# enable info logging
logging.basicConfig(level=logging.INFO)

# create emulator instance for creating sessions and utility methods
coreemu = CoreEmu()
session = coreemu.create_session()

# must be in configuration state for nodes to start
session.set_state(EventTypes.CONFIGURATION_STATE)

# create wireless
position = Position(x=200, y=200)
wireless = session.add_node(WlanNode, position=position)

# create nodes
options = CoreNode.create_options()
options.model = "mdr"
position = Position(x=100, y=100)
n1 = session.add_node(CoreNode, position=position, options=options)
options = CoreNode.create_options()
options.model = "mdr"
position = Position(x=300, y=100)
n2 = session.add_node(CoreNode, position=position, options=options)

# link nodes to wireless
iface1 = InterfaceData(ip4="10.0.0.1", ip4_mask=32, ip6="2001::1", ip6_mask=128)
session.add_link(n1.id, wireless.id, iface1)
iface1 = InterfaceData(ip4="10.0.0.2", ip4_mask=32, ip6="2001::2", ip6_mask=128)
session.add_link(n2.id, wireless.id, iface1)

# start session
session.instantiate()

# do whatever you like here
input("press enter to shutdown")

# stop session
session.shutdown()
