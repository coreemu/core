"""
This is a standalone script to run a small switch based scenario and will not
interact with the GUI.
"""

import logging

from core.emulator.coreemu import CoreEmu
from core.emulator.data import IpPrefixes
from core.emulator.enumerations import EventTypes
from core.nodes.base import CoreNode
from core.nodes.network import SwitchNode

NODES = 2


def main():
    # ip generator for example
    prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu()
    session = coreemu.create_session()

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE)

    # create switch network node
    switch = session.add_node(SwitchNode, _id=100)

    # create nodes
    for _ in range(NODES):
        node = session.add_node(CoreNode)
        interface = prefixes.create_iface(node)
        session.add_link(node.id, switch.id, iface1_data=interface)

    # instantiate session
    session.instantiate()

    # get nodes to run example
    first_node = session.get_node(1, CoreNode)
    last_node = session.get_node(NODES, CoreNode)
    address = prefixes.ip4_address(first_node)
    logging.info("node %s pinging %s", last_node.name, address)
    output = last_node.cmd(f"ping -c 3 {address}")
    logging.info(output)

    # shutdown session
    coreemu.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
