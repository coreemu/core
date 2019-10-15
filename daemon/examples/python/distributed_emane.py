import logging
import pdb
import sys

from core.emane.ieee80211abg import EmaneIeee80211abgModel
from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes, NodeOptions
from core.emulator.enumerations import EventTypes, NodeTypes


def main():
    address = sys.argv[1]
    remote = sys.argv[2]

    # ip generator for example
    prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu(
        {
            "controlnet": "core1:172.16.1.0/24 core2:172.16.2.0/24 core3:172.16.3.0/24 "
            "core4:172.16.4.0/24 core5:172.16.5.0/24",
            "distributed_address": address,
        }
    )
    session = coreemu.create_session()

    # initialize distributed
    server_name = "core2"
    session.add_distributed(server_name, remote)

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE)

    # create local node, switch, and remote nodes
    options = NodeOptions(model="mdr")
    options.set_position(0, 0)
    node_one = session.add_node(node_options=options)
    emane_net = session.add_node(_type=NodeTypes.EMANE)
    session.emane.set_model(emane_net, EmaneIeee80211abgModel)
    options.emulation_server = server_name
    node_two = session.add_node(node_options=options)

    # create node interfaces and link
    interface_one = prefixes.create_interface(node_one)
    interface_two = prefixes.create_interface(node_two)
    session.add_link(node_one.id, emane_net.id, interface_one=interface_one)
    session.add_link(node_two.id, emane_net.id, interface_one=interface_two)

    # instantiate session
    try:
        session.instantiate()
    except Exception:
        logging.exception("error during instantiate")

    # pause script for verification
    pdb.set_trace()

    # shutdown session
    coreemu.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
