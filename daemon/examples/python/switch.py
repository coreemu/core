import datetime
import logging
import parser

from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes
from core.emulator.enumerations import EventTypes, NodeTypes


def example(args):
    # ip generator for example
    prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu()
    session = coreemu.create_session()

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE)

    # create switch network node
    switch = session.add_node(_type=NodeTypes.SWITCH)

    # create nodes
    for _ in range(args.nodes):
        node = session.add_node()
        interface = prefixes.create_interface(node)
        session.add_link(node.id, switch.id, interface_one=interface)

    # instantiate session
    session.instantiate()

    # get nodes to run example
    first_node = session.get_node(2)
    last_node = session.get_node(args.nodes + 1)

    logging.info("starting iperf server on node: %s", first_node.name)
    first_node.cmd("iperf -s -D")
    first_node_address = prefixes.ip4_address(first_node)
    logging.info("node %s connecting to %s", last_node.name, first_node_address)
    output = last_node.cmd(f"iperf -t {args.time} -c {first_node_address}")
    logging.info(output)
    first_node.cmd("killall -9 iperf")

    # shutdown session
    coreemu.shutdown()


def main():
    logging.basicConfig(level=logging.INFO)
    args = parser.parse("switch")
    start = datetime.datetime.now()
    logging.info("running switch example: nodes(%s) time(%s)", args.nodes, args.time)
    example(args)
    logging.info("elapsed time: %s", datetime.datetime.now() - start)


if __name__ == "__main__":
    main()
