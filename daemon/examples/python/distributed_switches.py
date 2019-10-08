import logging
import pdb
import sys

from core.emulator.coreemu import CoreEmu
from core.emulator.enumerations import EventTypes, NodeTypes


def main():
    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu()
    session = coreemu.create_session()

    # initialize distributed
    address = sys.argv[1]
    remote = sys.argv[2]
    session.address = address
    session.add_distributed(remote)

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE)

    # create local node, switch, and remote nodes
    switch_one = session.add_node(_type=NodeTypes.SWITCH)
    switch_two = session.add_node(_type=NodeTypes.SWITCH)

    # create not interfaces and link
    session.add_link(switch_one.id, switch_two.id)

    # instantiate session
    session.instantiate()

    # pause script for verification
    pdb.set_trace()

    # shutdown session
    coreemu.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
