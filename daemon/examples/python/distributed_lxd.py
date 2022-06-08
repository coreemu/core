"""
Example for scripting a standalone distributed LXD session that does not interact
with the GUI.
"""

import argparse
import logging

from core.emulator.coreemu import CoreEmu
from core.emulator.data import IpPrefixes
from core.emulator.enumerations import EventTypes
from core.nodes.lxd import LxcNode


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
    coreemu = CoreEmu({"distributed_address": args.address})
    session = coreemu.create_session()

    # initialize distributed
    server_name = "core2"
    session.distributed.add_server(server_name, args.server)

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE)

    # create local node, switch, and remote nodes
    options = LxcNode.create_options()
    options.image = "ubuntu:18.04"
    node1 = session.add_node(LxcNode, options=options)
    options.server = server_name
    node2 = session.add_node(LxcNode, options=options)

    # create node interfaces and link
    interface1_data = prefixes.create_iface(node1)
    interface2_data = prefixes.create_iface(node2)
    session.add_link(node1.id, node2.id, interface1_data, interface2_data)

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
