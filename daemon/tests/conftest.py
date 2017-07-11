"""
Unit test fixture module.
"""
import os
import pytest

from core.session import Session
from core.misc import ipaddress
from core.misc import nodemaps
from core.misc import nodeutils
from core.netns import nodes
from core.services import quagga
from core.services import utility


class Core(object):
    def __init__(self, session, ip_prefix):
        self.session = session
        self.ip_prefix = ip_prefix
        self.current_ip = 1
        self.nodes = {}
        self.node_ips = {}

    def create_node(self, name, cls=nodes.CoreNode, objid=None, position=None, services=None, model=""):
        node = self.session.add_object(cls=cls, name=name, objid=objid)
        if model:
            node.type = model
        if position:
            node.setposition(*position)
        if services:
            self.session.services.addservicestonode(node, model, services)
        self.nodes[name] = node

    def add_interface(self, network, name):
        node_ip = self.ip_prefix.addr(self.current_ip)
        self.current_ip += 1
        self.node_ips[name] = node_ip
        node = self.nodes[name]
        interface_id = node.newnetif(network, ["%s/%s" % (node_ip, self.ip_prefix.prefixlen)])
        return node.netif(interface_id)

    def get_node(self, name):
        """
        Retrieve node from current session.

        :param str name: name of node to retrieve
        :return: core node
        :rtype: core.netns.nodes.CoreNode
        """
        return self.nodes[name]

    def get_ip(self, name):
        return self.node_ips[name]

    def link(self, network, from_interface, to_interface):
        network.link(from_interface, to_interface)

    def configure_link(self, network, interface_one, interface_two, values, unidirectional=False):
        network.linkconfig(netif=interface_one, netif2=interface_two, **values)

        if not unidirectional:
            network.linkconfig(netif=interface_two, netif2=interface_one, **values)

    def ping(self, from_name, to_name):
        from_node = self.nodes[from_name]
        to_ip = str(self.get_ip(to_name))
        return from_node.cmd(["ping", "-c", "3", to_ip])

    def ping_output(self, from_name, to_name):
        from_node = self.nodes[from_name]
        to_ip = str(self.get_ip(to_name))
        vcmd, stdin, stdout, stderr = from_node.popen(["ping", "-i", "0.05", "-c", "3", to_ip])
        return stdout.read().strip()

    def iping(self, from_name, to_name):
        from_node = self.nodes[from_name]
        to_ip = str(self.get_ip(to_name))
        from_node.icmd(["ping", "-i", "0.01", "-c", "10", to_ip])

    def iperf(self, from_name, to_name):
        from_node = self.nodes[from_name]
        to_node = self.nodes[to_name]
        to_ip = str(self.get_ip(to_name))

        # run iperf server, run client, kill iperf server
        vcmd, stdin, stdout, stderr = to_node.popen(["iperf", "-s", "-u", "-y", "C"])
        from_node.cmd(["iperf", "-u", "-t", "5", "-c", to_ip])
        to_node.cmd(["killall", "-9", "iperf"])

        return stdout.read().strip()

    def assert_nodes(self):
        for node in self.nodes.itervalues():
            assert os.path.exists(node.nodedir)

    def create_link_network(self):
        # create switch
        ptp_node = self.session.add_object(cls=nodes.PtpNet)

        # create nodes
        self.create_node("n1")
        self.create_node("n2")

        # add interfaces
        interface_one = self.add_interface(ptp_node, "n1")
        interface_two = self.add_interface(ptp_node, "n2")

        # instantiate session
        self.session.instantiate()

        # assert node directories created
        self.assert_nodes()

        return ptp_node, interface_one, interface_two

    def set_emane_model(self, emane_node, emane_model):
        # set the emane model
        values = emane_model.getdefaultvalues()
        self.session.emane.setconfig(emane_node.objid, emane_model.name, values)


@pytest.fixture()
def session():
    # configure default nodes
    node_map = nodemaps.CLASSIC_NODES
    nodeutils.set_node_map(node_map)

    # create and return session
    session_fixture = Session(1, persistent=True)
    assert os.path.exists(session_fixture.session_dir)
    yield session_fixture

    # cleanup
    print "shutting down session"
    session_fixture.shutdown()
    assert not os.path.exists(session_fixture.session_dir)


@pytest.fixture()
def session_emane():
    # configure default nodes
    node_map = nodemaps.CLASSIC_NODES
    nodeutils.set_node_map(node_map)

    # create and return session
    session_fixture = Session(1, persistent=True)
    assert os.path.exists(session_fixture.session_dir)

    # load emane services
    quagga.load_services()
    utility.load_services()

    # set location
    session_fixture.master = True
    session_fixture.location.setrefgeo(47.57917, -122.13232, 2.00000)
    session_fixture.location.refscale = 150.0

    # load emane models
    session_fixture.emane.loadmodels()

    # return session fixture
    yield session_fixture

    # cleanup
    print "shutting down session"
    session_fixture.shutdown()
    assert not os.path.exists(session_fixture.session_dir)


@pytest.fixture(scope="module")
def ip_prefix():
    return ipaddress.Ipv4Prefix("10.83.0.0/16")


@pytest.fixture()
def core(session, ip_prefix):
    return Core(session, ip_prefix)


@pytest.fixture()
def core_emane(session_emane, ip_prefix):
    return Core(session_emane, ip_prefix)
