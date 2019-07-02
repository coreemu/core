import logging

from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes, NodeOptions
from core.emulator.enumerations import NodeTypes, EventTypes


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    coreemu = CoreEmu()
    session = coreemu.create_session()
    session.set_state(EventTypes.CONFIGURATION_STATE)

    try:
        prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")
        options = NodeOptions(image="ubuntu")
        options.services = ["SSH"]

        # create node one
        node_one = session.add_node(_type=NodeTypes.LXC, node_options=options)
        interface_one = prefixes.create_interface(node_one)

        # create node two
        node_two = session.add_node()
        interface_two = prefixes.create_interface(node_two)

        # add link
        session.add_link(node_one.id, node_two.id, interface_one, interface_two)

        # instantiate
        session.instantiate()
    finally:
        input("continue to shutdown")
        coreemu.shutdown()
