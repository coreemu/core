#!/usr/bin/python
#
# run iperf to measure the effective throughput between two nodes when
# n nodes are connected to a virtual wlan; run test for testsec
# and repeat for minnodes <= n <= maxnodes with a step size of
# nodestep

import datetime

import parser
from core.future.coreemu import FutureIpv4Prefix, CoreEmu
from core.netns.nodes import CoreNode, SwitchNode


def example(options):
    # ip generator for example
    prefix = FutureIpv4Prefix("10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu()
    session = coreemu.create_session()

    # create switch network node
    switch_network = session.create_node(cls=SwitchNode)

    # create nodes
    for _ in xrange(options.nodes):
        node = session.create_node(cls=CoreNode)
        coreemu.add_interface(switch_network, node, prefix)

    # instantiate session
    session.instantiate()

    # get nodes to run example
    first_node = session.get_object(2)
    last_node = session.get_object(options.nodes + 1)

    print "starting iperf server on node: %s" % first_node.name
    first_node.cmd(["iperf", "-s", "-D"])
    address = str(prefix.addr(first_node.objid))
    print "node %s connecting to %s" % (last_node.name, address)
    last_node.client.icmd(["iperf", "-t", str(options.time), "-c", address])
    first_node.cmd(["killall", "-9", "iperf"])

    # shutdown session
    session.shutdown()


def main():
    options = parser.parse_options("switch")

    start = datetime.datetime.now()
    print "running switch example: nodes(%s) time(%s)" % (options.nodes, options.time)
    example(options)
    print "elapsed time: %s" % (datetime.datetime.now() - start)


if __name__ == "__main__":
    main()
