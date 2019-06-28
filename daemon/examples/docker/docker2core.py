import logging

from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes
from core.emulator.enumerations import NodeTypes, EventTypes


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    coreemu = CoreEmu()
    session = coreemu.create_session()
    session.set_state(EventTypes.CONFIGURATION_STATE)

    try:
        # create nodes one
        prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")
        node_one = session.add_node(_type=NodeTypes.DOCKER)
        session.services.add_services(node_one, node_one.type, ["SSH"])
        logging.info("docker node(%s): %s", node_one.name, node_one.services)
        interface_one = prefixes.create_interface(node_one)

        # create nodes two
        node_two = session.add_node()
        interface_two = prefixes.create_interface(node_two)

        # add link
        session.add_link(node_one.id, node_two.id, interface_one, interface_two)

        # instantiate
        logging.info("INSTANTIATE")
        logging.info("docker node(%s): %s", node_one.name, node_one.services)
        session.instantiate()
    finally:
        input("continue to shutdown")
        coreemu.shutdown()
