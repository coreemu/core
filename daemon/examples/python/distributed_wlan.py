import logging
import pdb
import sys

from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes, NodeOptions
from core.emulator.enumerations import EventTypes, NodeTypes
from core.location.mobility import BasicRangeModel


def main():
    address = sys.argv[1]
    remote = sys.argv[2]

    # ip generator for example
    prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu({"distributed_address": address})
    session = coreemu.create_session()

    # initialize distributed
    server_name = "core2"
    session.distributed.add_server(server_name, remote)

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE)

    # create local node, switch, and remote nodes
    options = NodeOptions()
    options.set_position(0, 0)
    options.emulation_server = server_name
    node_one = session.add_node(node_options=options)
    wlan = session.add_node(_type=NodeTypes.WIRELESS_LAN)
    session.mobility.set_model(wlan, BasicRangeModel)
    node_two = session.add_node(node_options=options)

    # create node interfaces and link
    interface_one = prefixes.create_interface(node_one)
    interface_two = prefixes.create_interface(node_two)
    session.add_link(node_one.id, wlan.id, interface_one=interface_one)
    session.add_link(node_two.id, wlan.id, interface_one=interface_two)

    # instantiate session
    session.instantiate()

    # pause script for verification
    pdb.set_trace()

    # shutdown session
    coreemu.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
