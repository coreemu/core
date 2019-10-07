import logging
import pdb

from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import NodeOptions
from core.emulator.enumerations import EventTypes


def main():
    # ip generator for example
    # prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu()
    session = coreemu.create_session()

    # initialize distributed
    session.add_distributed("core2")
    session.init_distributed()

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE)

    # create switch network node
    # switch = session.add_node(_type=NodeTypes.SWITCH)

    # create nodes
    options = NodeOptions()
    options.emulation_server = "core2"
    session.add_node(node_options=options)
    # interface = prefixes.create_interface(node_one)
    # session.add_link(node_one.id, switch.id, interface_one=interface)

    session.add_node()
    # interface = prefixes.create_interface(node_two)
    # session.add_link(node_two.id, switch.id, interface_one=interface)

    # instantiate session
    session.instantiate()

    # print("starting iperf server on node: %s" % node_one.name)
    # node_one.cmd(["iperf", "-s", "-D"])
    # node_one_address = prefixes.ip4_address(node_one)
    #
    # print("node %s connecting to %s" % (node_two.name, node_one_address))
    # node_two.client.icmd(["iperf", "-t", "10", "-c", node_one_address])
    # node_one.cmd(["killall", "-9", "iperf"])

    pdb.set_trace()

    # shutdown session
    coreemu.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
