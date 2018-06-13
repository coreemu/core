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
from core.mobility import BasicRangeModel


def example(options):
    # ip generator for example
    prefixes = IpPrefixes("10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu()
    session = coreemu.create_session()

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE)

    # create wlan network node
    wlan = session.add_node(_type=NodeTypes.WIRELESS_LAN)
    session.mobility.set_model(wlan, BasicRangeModel)

    # create nodes
    wireless_nodes = []
    for _ in xrange(options.nodes):
        node = session.add_node()
        interface = prefixes.create_interface(node)
        session.add_link(node.objid, wlan.objid, interface_one=interface)
        wireless_nodes.append(node)

    # link all created nodes with the wireless network
    session.wireless_link_all(wlan, wireless_nodes)

    # instantiate session
    session.instantiate()

    # get nodes for example run
    first_node = session.get_object(2)
    last_node = session.get_object(options.nodes + 1)

    print "starting iperf server on node: %s" % first_node.name
    first_node.cmd(["iperf", "-s", "-D"])
    address = prefixes.ip4_address(first_node)
    print "node %s connecting to %s" % (last_node.name, address)
    last_node.client.icmd(["iperf", "-t", str(options.time), "-c", address])
    first_node.cmd(["killall", "-9", "iperf"])

    # shutdown session
    coreemu.shutdown()


def main():
    options = parser.parse_options("wlan")

    start = datetime.datetime.now()
    print "running wlan example: nodes(%s) time(%s)" % (options.nodes, options.time)
    example(options)
    print "elapsed time: %s" % (datetime.datetime.now() - start)


if __name__ == "__main__":
    main()
