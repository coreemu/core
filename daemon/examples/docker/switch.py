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
        options = NodeOptions(model=None, image="ubuntu")

        # create switch
        switch = session.add_node(_type=NodeTypes.SWITCH)

        # node one
        node_one = session.add_node(_type=NodeTypes.DOCKER, node_options=options)
        interface_one = prefixes.create_interface(node_one)

        # node two
        node_two = session.add_node(_type=NodeTypes.DOCKER, node_options=options)
        interface_two = prefixes.create_interface(node_two)

        # node three
        node_three = session.add_node()
        interface_three = prefixes.create_interface(node_three)

        # add links
        session.add_link(node_one.id, switch.id, interface_one)
        session.add_link(node_two.id, switch.id, interface_two)
        session.add_link(node_three.id, switch.id, interface_three)

        # instantiate
        session.instantiate()
    finally:
        input("continue to shutdown")
        coreemu.shutdown()
