#!/usr/bin/python
#
# run iperf to measure the effective throughput between two nodes when
# n nodes are connected to a virtual wlan; run test for testsec
# and repeat for minnodes <= n <= maxnodes with a step size of
# nodestep

import datetime

import parser
from core.future.coreemu import CoreEmu
from core.future.futuredata import IpPrefixes
from core.mobility import BasicRangeModel
from core.netns.nodes import WlanNode, CoreNode


def example(options):
    # ip generator for example
    prefixes = IpPrefixes("10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu()
    session = coreemu.create_session()

    # create wlan network node
    wlan_network = session.create_node(cls=WlanNode)
    coreemu.set_wireless_model(wlan_network, BasicRangeModel)

    # create nodes
    wireless_nodes = []
    for _ in xrange(options.nodes):
        node = session.create_node(cls=CoreNode)
        coreemu.add_interface(wlan_network, node, prefixes)
        wireless_nodes.append(node)

    # link all created nodes with the wireless network
    coreemu.wireless_link_all(wlan_network, wireless_nodes)

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
