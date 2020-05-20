"""
This is a standalone script to run a small WLAN based scenario and will not
interact with the GUI.
"""

import logging

from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes, NodeOptions
from core.emulator.enumerations import EventTypes, NodeTypes
from core.location.mobility import BasicRangeModel
from core.nodes.base import CoreNode

NODES = 2


def main():
    # ip generator for example
    prefixes = IpPrefixes("10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu()
    session = coreemu.create_session()

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE)

    # create wlan network node
    wlan = session.add_node(_type=NodeTypes.WIRELESS_LAN, _id=100)
    session.mobility.set_model(wlan, BasicRangeModel)

    # create nodes, must set a position for wlan basic range model
    options = NodeOptions(model="mdr")
    options.set_position(0, 0)
    for _ in range(NODES):
        node = session.add_node(options=options)
        interface = prefixes.create_interface(node)
        session.add_link(node.id, wlan.id, interface_one=interface)

    # instantiate session
    session.instantiate()

    # get nodes for example run
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
