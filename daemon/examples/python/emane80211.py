"""
This is a standalone script to run a small EMANE scenario and will not interact
with the GUI. You also must have installed OSPF MDR as noted in the documentation
installation page.
"""

import logging
import time

from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes, NodeOptions
from core.emulator.enumerations import EventTypes, NodeTypes
from core.nodes.base import CoreNode

NODES = 2
EMANE_DELAY = 10


def main():
    # ip generator for example
    prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu()
    session = coreemu.create_session()

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE)

    # create emane network node, emane determines connectivity based on
    # location, so the session and nodes must be configured to provide one
    session.set_location(47.57917, -122.13232, 2.00000, 1.0)
    options = NodeOptions()
    options.set_position(80, 50)
    emane_network = session.add_node(_type=NodeTypes.EMANE, options=options, _id=100)
    session.emane.set_model(emane_network, EmaneIeee80211abgModel)

    # create nodes
    options = NodeOptions(model="mdr")
    for i in range(NODES):
        node = session.add_node(options=options)
        node.setposition(x=150 * (i + 1), y=150)
        interface = prefixes.create_interface(node)
        session.add_link(node.id, emane_network.id, interface_one=interface)

    # instantiate session
    session.instantiate()

    # OSPF MDR requires some time for routes to be created
    logging.info("waiting %s seconds for OSPF MDR to create routes", EMANE_DELAY)
    time.sleep(EMANE_DELAY)

    # get nodes to run example
    first_node = session.get_node(1, CoreNode)
    last_node = session.get_node(NODES, CoreNode)
    address = prefixes.ip4_address(first_node)
    logging.info("node %s pinging %s", last_node.name, address)
    output = last_node.cmd(f"ping -c 3 {address}")
    logging.info(output)

    # shutdown session
    coreemu.shutdown()


if __name__ == "__main__" or __name__ == "__builtin__":
    logging.basicConfig(level=logging.INFO)
    main()
