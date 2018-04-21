#!/usr/bin/python
#
# run iperf to measure the effective throughput between two nodes when
# n nodes are connected to a virtual wlan; run test for testsec
# and repeat for minnodes <= n <= maxnodes with a step size of
# nodestep

import datetime

import parser
from core.data import NodeData, LinkData
from core.enumerations import NodeTypes, EventTypes
from core.future.coreemu import FutureIpv4Prefix, CoreEmu


def example(options):
    # ip generator for example
    prefix = FutureIpv4Prefix("10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu()
    session = coreemu.create_session(master=True)

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE.value)

    # create switch network node
    node_data = NodeData(node_type=NodeTypes.SWITCH.value)
    switch_id = session.node_add(node_data)

    # create nodes
    for _ in xrange(options.nodes):
        node_data = NodeData(node_type=NodeTypes.DEFAULT.value)
        node_id = session.node_add(node_data)
        node = session.get_object(node_id)
        inteface_index = node.newifindex()
        address = prefix.addr(node_id)
        link_data = LinkData(
            node1_id=node_id,
            node2_id=switch_id,
            interface1_id=inteface_index,
            interface1_ip4=str(address),
            interface1_ip4_mask=prefix.prefixlen,
        )
        session.link_add(link_data)

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
    coreemu.shutdown()


def main():
    options = parser.parse_options("switch")

    start = datetime.datetime.now()
    print "running switch example: nodes(%s) time(%s)" % (options.nodes, options.time)
    example(options)
    print "elapsed time: %s" % (datetime.datetime.now() - start)


if __name__ == "__main__":
    main()
