import logging

from core.emulator.coreemu import CoreEmu
from core.emulator.data import IpPrefixes, NodeOptions
from core.emulator.enumerations import EventTypes
from core.nodes.base import CoreNode
from core.nodes.lxd import LxcNode
from core.nodes.network import SwitchNode

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    coreemu = CoreEmu()
    session = coreemu.create_session()
    session.set_state(EventTypes.CONFIGURATION_STATE)

    try:
        prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")
        options = NodeOptions(image="ubuntu")

        # create switch
        switch = session.add_node(SwitchNode)

        # node one
        node1 = session.add_node(LxcNode, options=options)
        interface1_data = prefixes.create_iface(node1)

        # node two
        node2 = session.add_node(LxcNode, options=options)
        interface2_data = prefixes.create_iface(node2)

        # node three
        node3 = session.add_node(CoreNode)
        interface3_data = prefixes.create_iface(node3)

        # add links
        session.add_link(node1.id, switch.id, interface1_data)
        session.add_link(node2.id, switch.id, interface2_data)
        session.add_link(node3.id, switch.id, interface3_data)

        # instantiate
        session.instantiate()
    finally:
        input("continue to shutdown")
        coreemu.shutdown()
