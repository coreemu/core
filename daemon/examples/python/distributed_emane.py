"""
Example for scripting a standalone distributed EMANE session that does not interact
with the GUI.
"""

import argparse
import logging

from core.emane.models.ieee80211abg import EmaneIeee80211abgModel
from core.emane.nodes import EmaneNet
from core.emulator.coreemu import CoreEmu
from core.emulator.data import IpPrefixes, NodeOptions
from core.emulator.enumerations import EventTypes
from core.nodes.base import CoreNode


def parse(name):
    parser = argparse.ArgumentParser(description=f"Run {name} example")
    parser.add_argument(
        "-a",
        "--address",
        help="local address that distributed servers will use for gre tunneling",
    )
    parser.add_argument(
        "-s", "--server", help="distributed server to use for creating nodes"
    )
    options = parser.parse_args()
    return options


def main(args):
    # ip generator for example
    prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu(
        {
            "controlnet": "core1:172.16.1.0/24 core2:172.16.2.0/24 core3:172.16.3.0/24 "
            "core4:172.16.4.0/24 core5:172.16.5.0/24",
            "distributed_address": args.address,
        }
    )
    session = coreemu.create_session()

    # initialize distributed
    server_name = "core2"
    session.distributed.add_server(server_name, args.server)

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE)

    # create local node, switch, and remote nodes
    options = NodeOptions(model="mdr")
    options.set_position(0, 0)
    node1 = session.add_node(CoreNode, options=options)
    emane_net = session.add_node(EmaneNet)
    session.emane.set_model(emane_net, EmaneIeee80211abgModel)
    options.server = server_name
    node2 = session.add_node(CoreNode, options=options)

    # create node interfaces and link
    interface1_data = prefixes.create_iface(node1)
    interface2_data = prefixes.create_iface(node2)
    session.add_link(node1.id, emane_net.id, iface1_data=interface1_data)
    session.add_link(node2.id, emane_net.id, iface1_data=interface2_data)

    # instantiate session
    session.instantiate()

    # pause script for verification
    input("press enter for shutdown")

    # shutdown session
    coreemu.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    args = parse(__file__)
    main(args)
