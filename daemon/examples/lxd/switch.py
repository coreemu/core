import logging

from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes, NodeOptions
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
        node_one = session.add_node(LxcNode, options=options)
        interface_one = prefixes.create_interface(node_one)

        # node two
        node_two = session.add_node(LxcNode, options=options)
        interface_two = prefixes.create_interface(node_two)

        # node three
        node_three = session.add_node(CoreNode)
        interface_three = prefixes.create_interface(node_three)

        # add links
        session.add_link(node_one.id, switch.id, interface_one)
        session.add_link(node_two.id, switch.id, interface_two)
        session.add_link(node_three.id, switch.id, interface_three)

        # instantiate
        session.instantiate()
    finally:
        input("continue to shutdown")
        coreemu.shutdown()
