#!/usr/bin/python
#
# run iperf to measure the effective throughput between two nodes when
# n nodes are connected to a virtual wlan; run test for testsec
# and repeat for minnodes <= n <= maxnodes with a step size of
# nodestep

import datetime

import parser
from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes
from core.enumerations import NodeTypes, EventTypes
from core.netns import nodes


def example(options):
    # ip generator for example
    prefixes = IpPrefixes(ip4_prefix="10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu()
    session = coreemu.create_session()

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE)

    node1 = session.add_object(cls=nodes.CoreNode, name="n1")
    node2 = session.add_object(cls=nodes.CoreNode, name="n2")
    dock1 = session.add_object(cls=nodes.DockerNetNode, name="docker1")
    node1.newnetif(dock1, ["10.0.0.1/24"])
    node2.newnetif(dock1, ["10.0.0.2/24"])

    node1.client.icmd(["ping", "-c", "5", "10.0.0.2"])


    # # create switch network node
    # switch = session.add_node(_type=NodeTypes.SWITCH)
    #
    # # create nodes
    # for _ in xrange(options.nodes):
    #     node = session.add_node()
    #     interface = prefixes.create_interface(node)
    #     session.add_link(node.objid, switch.objid, interface_one=interface)
    #
    # # instantiate session
    # session.instantiate()
    #
    # # get nodes to run example
    # first_node = session.get_object(2)
    # last_node = session.get_object(options.nodes + 1)
    #
    # print "starting iperf server on node: %s" % first_node.name
    # first_node.cmd(["iperf", "-s", "-D"])
    # first_node_address = prefixes.ip4_address(first_node)
    # print "node %s connecting to %s" % (last_node.name, first_node_address)
    # last_node.client.icmd(["iperf", "-t", str(options.time), "-c", first_node_address])
    # first_node.cmd(["killall", "-9", "iperf"])

    # shutdown session
    coreemu.shutdown()


def main():
    options = parser.parse_options("switch")

    start = datetime.datetime.now()
    print "running switch example: nodes(%s) time(%s)" % (options.nodes, options.time)
    example(options)
    print "elapsed time: %s" % (datetime.datetime.now() - start)


if __name__ == "__main__":
    main()
