# import itertools

from core import services
from core.emane.nodes import EmaneNode
from core.misc.ipaddress import Ipv4Prefix
from core.netns.nodes import CoreNode
from core.session import Session


class IdGen(object):
    def __init__(self):
        self.id = 0

    def next(self):
        self.id += 1
        return self.id


class FutureIpv4Prefix(Ipv4Prefix):
    def get_address(self, node_id):
        address = self.addr(node_id)
        return "%s/%s" % (address, self.prefixlen)


class FutureSession(Session):
    def __init__(self, session_id, config=None, persistent=True, mkdir=True):
        super(FutureSession, self).__init__(session_id, config, persistent, mkdir)

        # set master
        self.master = True

        # object management
        self.object_id_gen = IdGen()

        # set default services
        self.services.defaultservices = {
            "mdr": ("zebra", "OSPFv3MDR", "IPForward"),
            "PC": ("DefaultRoute",),
            "prouter": ("zebra", "OSPFv2", "OSPFv3", "IPForward"),
            "router": ("zebra", "OSPFv2", "OSPFv3", "IPForward"),
            "host": ("DefaultRoute", "SSH"),
        }

    def create_node(self, cls, name=None, model=None):
        object_id = self.object_id_gen.next()

        if not name:
            name = "%s%s" % (cls.__name__, object_id)

        node = self.add_object(cls=cls, name=name, objid=object_id)
        node.type = model
        if node.type:
            self.services.addservicestonode(node, node.type, services_str=None)

        return node

    def create_emane_node(self, name=None):
        return self.create_node(cls=CoreNode, name=name, model="mdr")

    def create_emane_network(self, model, geo_reference, geo_scale=None, name=None):
        """
        Convenience method for creating an emane network.

        :param model: emane model to use for emane network
        :param geo_reference: geo reference point to use for emane node locations
        :param geo_scale: geo scale to use for emane node locations, defaults to 1.0
        :param name: name for emane network, defaults to node class name
        :return: create emane network
        """
        # required to be set for emane to function properly
        self.location.setrefgeo(*geo_reference)
        if geo_scale:
            self.location.refscale = geo_scale

        # create and return network
        emane_network = self.create_node(cls=EmaneNode, name=name)
        self.set_emane_model(emane_network, model)
        return emane_network

    def set_emane_model(self, emane_node, model):
        """
        Set emane model for a given emane node.

        :param emane_node: emane node to set model for
        :param model: emane model to set
        :return: nothing
        """
        values = list(model.getdefaultvalues())
        self.emane.setconfig(emane_node.objid, model.name, values)


class CoreEmu(object):
    """
    Provides logic for creating and configuring CORE sessions and the nodes within them.
    """

    def __init__(self, config=None):
        # configuration
        self.config = config

        # session management
        self.session_id_gen = IdGen()
        self.sessions = {}

        # load default services
        services.load()

    def create_session(self):
        """
        Create a new CORE session.

        :return: created session
        :rtype: FutureSession
        """
        session_id = self.session_id_gen.next()
        return FutureSession(session_id, config=self.config)

    def set_wireless_model(self, node, model):
        """
        Convenience method for setting a wireless model.

        :param node: node to set wireless model for
        :param core.mobility.WirelessModel model: wireless model to set node to
        :return: nothing
        """
        values = list(model.getdefaultvalues())
        node.setmodel(model, values)

    def wireless_link_all(self, network, nodes):
        """
        Link all nodes to the provided wireless network.

        :param network: wireless network to link nodes to
        :param nodes: nodes to link to wireless network
        :return: nothing
        """
        for node in nodes:
            for common_network, interface_one, interface_two in node.commonnets(network):
                common_network.link(interface_one, interface_two)

    def add_interface(self, network, node, prefix):
        """
        Convenience method for adding an interface with a prefix based on node id.

        :param network: network to add interface with
        :param node: node to add interface to
        :param prefix: prefix to get address from for interface
        :return: created interface
        """
        address = prefix.get_address(node.objid)
        interface_index = node.newnetif(network, [address])
        return node.netif(interface_index)
