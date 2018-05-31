#!/usr/bin/python
#
# Make two nodes and a DockerNetNode. Connect them and then try pulling a web page from them.
# You should pull the latest nginx image before you try this: docker pull nginx
# otherwise it will not be ready in time for us. You only need to do this once.

import datetime
import os
import time


from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes
from core.enumerations import EventTypes
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

    node1 = session.add_object(cls=nodes.CoreNode, name="n1", objid=11)
    switch1 = session.add_object(cls=nodes.SwitchNode, name="s1", objid=12)
    dock1 = session.add_object(cls=nodes.DockerNetNode, name=docker_net, subnet=str(prefixes.ip4), objid=13)
    switch1.linknet(dock1)
    node1_net = node1.newnetif(switch1, prefixes.create_interface(node1).ip4_address())

    # Make a 1MB binary file which we will download
    with open(os.path.join(session.session_dir, "largeFile"), 'wb') as fout:
        fout.write(os.urandom(1024 * 1024))

    docker_id = utils.check_cmd(["docker", "run", "-d", "--net="+docker_net, "--ip="+str(prefixes.ip4.min_addr() + 1),
                    "-v", session.session_dir + ":/usr/share/nginx/html:ro", "nginx"])

    # Give docker time to come to life. First run it may download images and this will not be long enough.
    print "Giving 5 seconds for nginx container to start"
    time.sleep(5)

    # We download at various bandwidths
    for i in [100, 10, 1]:
        dock1.linkconfig(node1.netif(node1_net, switch1), bw=(i * 1024 * 1024))
        print "Setting bandwidth to {}Mbps".format(i)
        start = datetime.datetime.now()
        status, output = node1.client.cmd_output(["wget", str(prefixes.ip4.min_addr() + 1) + "/largeFile"])
        # Show the last line with the throughput
        print output.splitlines()[-1]
        node1.client.cmd_output(["rm", "largeFile"])
        print "elapsed time: %s" % (datetime.datetime.now() - start)

    utils.check_cmd(["docker", "rm", "-f", docker_id])
    coreemu.shutdown()


if __name__ == "__main__":
    main()
