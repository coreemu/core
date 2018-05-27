#!/usr/bin/python
#
# run iperf to measure the effective throughput between two nodes when
# n nodes are connected to a virtual wlan; run test for testsec
# and repeat for minnodes <= n <= maxnodes with a step size of
# nodestep

import datetime
import time

import parser
from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes
from core.enumerations import NodeTypes, EventTypes
from core.netns import nodes
from core.misc import utils


def main():
    # ip generator for example
    prefixes = IpPrefixes(ip4_prefix="10.0.0.0/16")
    docker_net = "docker1"

    # create emulator instance for creating sessions and utility methods
    coreemu = CoreEmu()
    session = coreemu.create_session()

    # must be in configuration state for nodes to start, when using "node_add" below
    session.set_state(EventTypes.CONFIGURATION_STATE)

    node1 = session.add_object(cls=nodes.CoreNode, name="n1")
    node2 = session.add_object(cls=nodes.CoreNode, name="n2")
    dock1 = session.add_object(cls=nodes.DockerNetNode, name=docker_net, subnet=str(prefixes.ip4))
    node1_net = node1.newnetif(dock1, prefixes.create_interface(node1).ip4_address())
    node2.newnetif(dock1, prefixes.create_interface(node2).ip4_address())
    docker_id = utils.check_cmd(["docker", "run", "-d", "--net="+docker_net, "--ip="+str(prefixes.ip4.min_addr() + 1),
                    "nginx"])

    # Give docker time to come to life. First run it may download images and this will not be long enough.
    time.sleep(5)

    print "Going to request web with no network effects"
    start = datetime.datetime.now()
    node1.client.icmd(["wget", "-O", "-", str(prefixes.ip4.min_addr() + 1)])
    print "elapsed time: %s" % (datetime.datetime.now() - start)

    # TODO: Have not yet implemented linkconfig for docker network
    time.sleep(5)

    print "Going to request web with network effects"
    start = datetime.datetime.now()
    node1.client.icmd(["wget", "-O", "-", str(prefixes.ip4.min_addr() + 1)])
    print "elapsed time: %s" % (datetime.datetime.now() - start)

    utils.check_cmd(["docker", "rm", "-f", docker_id])
    coreemu.shutdown()


if __name__ == "__main__":
    main()
