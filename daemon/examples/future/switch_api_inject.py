#!/usr/bin/python
#
# run iperf to measure the effective throughput between two nodes when
# n nodes are connected to a virtual wlan; run test for testsec
# and repeat for minnodes <= n <= maxnodes with a step size of
# nodestep

from core.enumerations import NodeTypes, EventTypes
from core.future.futuredata import IpPrefixes, NodeOptions


def example(nodes):
    # ip generator for example
    prefixes = IpPrefixes("10.83.0.0/16")

    # create emulator instance for creating sessions and utility methods
    coreemu = globals()["coreemu"]
    session = coreemu.create_session(master=True)

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE.value)

    # create switch network node
    node_options = NodeOptions(_type=NodeTypes.SWITCH)
    switch = session.add_node(node_options)

    # create nodes
    for _ in xrange(nodes):
        node_options = NodeOptions(_type=NodeTypes.DEFAULT.value)
        node = session.add_node(node_options)
        interface = prefixes.create_interface(node)
        session.add_link(node.objid, switch.objid, interface_one=interface)

    # instantiate session
    session.instantiate()


if __name__ in {"__main__", "__builtin__"}:
    example(2)
