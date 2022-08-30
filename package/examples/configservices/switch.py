import logging

from core.emulator.coreemu import CoreEmu
from core.emulator.data import IpPrefixes
from core.emulator.enumerations import EventTypes
from core.nodes.base import CoreNode
from core.nodes.network import SwitchNode

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # setup basic network
    prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")
    coreemu = CoreEmu()
    session = coreemu.create_session()
    session.set_state(EventTypes.CONFIGURATION_STATE)
    switch = session.add_node(SwitchNode)

    # node one
    options = CoreNode.create_options()
    options.config_services = ["DefaultRoute", "IPForward"]
    node1 = session.add_node(CoreNode, options=options)
    interface = prefixes.create_iface(node1)
    session.add_link(node1.id, switch.id, iface1_data=interface)

    # node two
    node2 = session.add_node(CoreNode, options=options)
    interface = prefixes.create_iface(node2)
    session.add_link(node2.id, switch.id, iface1_data=interface)

    # start session and run services
    session.instantiate()

    input("press enter to exit")
    session.shutdown()
