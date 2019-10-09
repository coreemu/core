import logging
import pdb
import sys

from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes, NodeOptions
from core.emulator.enumerations import EventTypes, NodeTypes


def main():
    # ip generator for example
    prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu()
    session = coreemu.create_session()

    # set controlnet
    session.options.set_config("controlnet", "172.16.0.0/24")

    # initialize distributed
    address = sys.argv[1]
    remote = sys.argv[2]
    session.address = address
    session.add_distributed(remote)

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE)

    # create local node, switch, and remote nodes
    node_one = session.add_node()
    switch = session.add_node(_type=NodeTypes.SWITCH)
    options = NodeOptions()
    options.emulation_server = remote
    node_two = session.add_node(node_options=options)

    # create node interfaces and link
    interface_one = prefixes.create_interface(node_one)
    interface_two = prefixes.create_interface(node_two)
    session.add_link(node_one.id, switch.id, interface_one=interface_one)
    session.add_link(node_two.id, switch.id, interface_one=interface_two)

    # instantiate session
    session.instantiate()

    # pause script for verification
    pdb.set_trace()

    # shutdown session
    coreemu.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
