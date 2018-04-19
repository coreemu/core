import os

import core.services
from core import logger
from core.coreobj import PyCoreNode, PyCoreNet
from core.data import NodeData
from core.emane.nodes import EmaneNode
from core.enumerations import NodeTypes, EventTypes, LinkTypes
from core.misc import nodeutils
from core.misc.ipaddress import Ipv4Prefix
from core.netns.nodes import CoreNode
from core.session import Session
from core.xml.xmlparser import core_document_parser
from core.xml.xmlwriter import core_document_writer


class InterfaceData(object):
    def __init__(self, _id, name, mac, ip4, ip4_mask, ip6, ip6_mask):
        self.id = _id
        self.name = name
        self.mac = mac
        self.ip4 = ip4
        self.ip4_mask = ip4_mask
        self.ip6 = ip6
        self.ip6_mask = ip6_mask

    def has_ip4(self):
        return all([self.ip4, self.ip4_mask])

    def has_ip6(self):
        return all([self.ip6, self.ip6_mask])

    def ip4_address(self):
        if self.has_ip4():
            return "%s/%s" % (self.ip4, self.ip4_mask)
        else:
            return None

    def ip6_address(self):
        if self.has_ip6():
            return "%s/%s" % (self.ip6, self.ip6_mask)
        else:
            return None

    def get_addresses(self):
        ip4 = self.ip4_address()
        ip6 = self.ip6_address()
        return [i for i in [ip4, ip6] if i]


def get_interfaces(link_data):
    interface_one = InterfaceData(
        _id=link_data.interface1_id,
        name=link_data.interface1_name,
        mac=link_data.interface1_mac,
        ip4=link_data.interface1_ip4,
        ip4_mask=link_data.interface1_ip4_mask,
        ip6=link_data.interface1_ip6,
        ip6_mask=link_data.interface1_ip6_mask,
    )
    interface_two = InterfaceData(
        _id=link_data.interface2_id,
        name=link_data.interface2_name,
        mac=link_data.interface2_mac,
        ip4=link_data.interface2_ip4,
        ip4_mask=link_data.interface2_ip4_mask,
        ip6=link_data.interface2_ip6,
        ip6_mask=link_data.interface2_ip6_mask,
    )
    return interface_one, interface_two


def create_interface(node, network, addresses, interface_data):
    """
    Create an interface for a node on a network using provided interface data.

    :param node: node to create interface for
    :param network: network to associate interface with
    :param list[str] addresses:
    :param InterfaceData interface_data: interface data
    :return:
    """
    node.newnetif(
        network,
        addrlist=addresses,
        hwaddr=interface_data.mac,
        ifindex=interface_data.id,
        ifname=interface_data.name
    )
    return node.netif(interface_data.id, network)


def link_config(network, interface, link_data, devname=None, interface_two=None):
    config = {
        "netif": interface,
        "bw": link_data.bandwidth,
        "delay": link_data.delay,
        "loss": link_data.per,
        "duplicate": link_data.dup,
        "jitter": link_data.jitter,
        "netif2": interface_two
    }

    # hacky check here, because physical and emane nodes do not conform to the same linkconfig interface
    if not nodeutils.is_node(network, [NodeTypes.EMANE, NodeTypes.PHYSICAL]):
        config["devname"] = devname

    network.linkconfig(**config)


def is_net_node(node):
    """
    Convenience method for testing if a legacy core node is considered a network node.

    :param object node: object to test against
    :return: True if object is an instance of a network node, False otherwise
    :rtype: bool
    """
    return isinstance(node, PyCoreNet)


def is_core_node(node):
    """
    Convenience method for testing if a legacy core node is considered a core node.

    :param object node: object to test against
    :return: True if object is an instance of a core node, False otherwise
    :rtype: bool
    """
    return isinstance(node, PyCoreNode)


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
        self.node_id_gen = IdGen()

        # set default services
        self.services.defaultservices = {
            "mdr": ("zebra", "OSPFv3MDR", "IPForward"),
            "PC": ("DefaultRoute",),
            "prouter": ("zebra", "OSPFv2", "OSPFv3", "IPForward"),
            "router": ("zebra", "OSPFv2", "OSPFv3", "IPForward"),
            "host": ("DefaultRoute", "SSH"),
        }

    def link_nodes(self, link_data):
        logger.info("link message between node1(%s:%s) and node2(%s:%s)",
                    link_data.node1_id, link_data.interface1_id, link_data.node2_id, link_data.interface2_id)

        # values to fill
        net_one = None
        net_two = None

        # retrieve node one
        n1_id = link_data.node1_id
        n2_id = link_data.node2_id
        node_one = self.get_object(n1_id)
        node_two = self.get_object(n2_id)

        # both node ids are provided
        tunnel = self.broker.gettunnel(n1_id, n2_id)
        logger.info("tunnel between nodes: %s", tunnel)
        if nodeutils.is_node(tunnel, NodeTypes.TAP_BRIDGE):
            net_one = tunnel
            if tunnel.remotenum == n1_id:
                node_one = None
            else:
                node_two = None
        # PhysicalNode connected via GreTap tunnel; uses adoptnetif() below
        elif tunnel:
            if tunnel.remotenum == n1_id:
                node_one = None
            else:
                node_two = None

        if is_net_node(node_one):
            if not net_one:
                net_one = node_one
            else:
                net_two = node_one
            node_one = None

        if is_net_node(node_two):
            if not net_one:
                net_one = node_two
            else:
                net_two = node_two
            node_two = None

        logger.info("link node types n1(%s) n2(%s) net1(%s) net2(%s) tunnel(%s)",
                    node_one, node_two, net_one, net_two, tunnel)
        return node_one, node_two, net_one, net_two, tunnel

    # TODO: this doesn't appear to ever be used, EMANE or basic wireless range
    def _link_wireless(self, objects, connect):
        """
        Objects to deal with when connecting/disconnecting wireless links.

        :param list objects: possible objects to deal with
        :param bool connect: link interfaces if True, unlink otherwise
        :return: nothing
        """
        objects = [x for x in objects if x]
        if len(objects) < 2:
            raise ValueError("wireless link failure: %s", objects)
        logger.info("handling wireless linking objects(%) connect(%s)", objects, connect)
        common_networks = objects[0].commonnets(objects[1])
        for common_network, interface_one, interface_two in common_networks:
            if not nodeutils.is_node(common_network, [NodeTypes.WIRELESS_LAN, NodeTypes.EMANE]):
                logger.info("skipping common network that is not wireless/emane: %s", common_network)
                continue

            logger.info("wireless linking connect(%s): %s - %s", connect, interface_one, interface_two)
            if connect:
                common_network.link(interface_one, interface_two)
            else:
                common_network.unlink(interface_one, interface_two)
        else:
            raise ValueError("no common network found for wireless link/unlink")

    def link_add(self, link_data):
        # interface data
        interface_one_data, interface_two_data = get_interfaces(link_data)

        # get node objects identified by link data
        node_one, node_two, net_one, net_two, tunnel = self.link_nodes(link_data)

        if node_one:
            node_one.lock.acquire()
        if node_two:
            node_two.lock.acquire()

        try:
            # wireless link
            if link_data.link_type == LinkTypes.WIRELESS.value:
                objects = [node_one, node_two, net_one, net_two]
                self._link_wireless(objects, connect=True)
            # wired link
            else:
                # 2 nodes being linked, ptp network
                if all([node_one, node_two]) and not net_one:
                    ptp_class = nodeutils.get_node_class(NodeTypes.PEER_TO_PEER)
                    start = self.state > EventTypes.DEFINITION_STATE.value
                    net_one = self.add_object(cls=ptp_class, start=start)

                # node to network
                if node_one and net_one:
                    addresses = []
                    addresses.extend(interface_one_data.get_addresses())
                    addresses.extend(interface_two_data.get_addresses())
                    interface = create_interface(node_one, net_one, addresses, interface_one_data)
                    link_config(net_one, interface, link_data)

                # network to node
                if node_two and net_one:
                    addresses = []
                    addresses.extend(interface_one_data.get_addresses())
                    addresses.extend(interface_two_data.get_addresses())
                    interface = create_interface(node_two, net_one, addresses, interface_two_data)
                    if not link_data.unidirectional:
                        link_config(net_one, interface, link_data)

                # network to network
                if net_one and net_two:
                    if nodeutils.is_node(net_two, NodeTypes.RJ45):
                        interface = net_two.linknet(net_one)
                    else:
                        interface = net_one.linknet(net_two)

                    link_config(net_one, interface, link_data)

                    if not link_data.unidirectional:
                        interface.swapparams("_params_up")
                        link_config(net_two, interface, link_data, devname=interface.name)
                        interface.swapparams("_params_up")

                # a tunnel was found for the nodes
                addresses = []
                if not node_one and net_one:
                    addresses.extend(interface_one_data.get_addresses())

                if not node_two and net_two:
                    addresses.extend(interface_two_data.get_addresses())

                # tunnel node logic
                key = link_data.key
                if key and nodeutils.is_node(net_one, NodeTypes.TUNNEL):
                    net_one.setkey(key)
                    if addresses:
                        net_one.addrconfig(addresses)
                if key and nodeutils.is_node(net_two, NodeTypes.TUNNEL):
                    net_two.setkey(key)
                    if addresses:
                        net_two.addrconfig(addresses)

                if not net_one and not net_two and (not node_one or not node_two):
                    addresses = []
                    if node_one and nodeutils.is_node(node_one, NodeTypes.PHYSICAL):
                        addresses.extend(interface_one_data.get_addresses())
                        node_one.adoptnetif(tunnel, link_data.interface1_id, link_data.interface1_mac, addresses)
                        link_config(node_one, tunnel, link_data)
                    elif node_two and nodeutils.is_node(node_two, NodeTypes.PHYSICAL):
                        addresses.extend(interface_two_data.get_addresses())
                        node_two.adoptnetif(tunnel, link_data.interface2_id, link_data.interface2_mac, addresses)
                        link_config(node_two, tunnel, link_data)
        finally:
            if node_one:
                node_one.lock.release()
            if node_two:
                node_two.lock.release()

    def link_delete(self, link_data):
        # interface data
        interface_one_data, interface_two_data = get_interfaces(link_data)

        # get node objects identified by link data
        node_one, node_two, net_one, net_two, tunnel = self.link_nodes(link_data)

        if node_one:
            node_one.lock.acquire()
        if node_two:
            node_two.lock.acquire()

        try:
            # wireless link
            if link_data.link_type == LinkTypes.WIRELESS.value:
                objects = [node_one, node_two, net_one, net_two]
                self._link_wireless(objects, connect=False)
            # wired link
            else:
                if all([node_one, node_two]):
                    # TODO: fix this for the case where ifindex[1,2] are not specified
                    # a wired unlink event, delete the connecting bridge
                    interface_one = node_one.netif(interface_one_data.id)
                    interface_two = node_two.netif(interface_two_data.id)

                    # get interfaces from common network, if no network node
                    # otherwise get interfaces between a node and network
                    if not interface_one and not interface_two:
                        common_networks = node_one.commonnets(node_two)
                        for network, common_interface_one, common_interface_two in common_networks:
                            if (net_one and network == net_one) or not net_one:
                                interface_one = common_interface_one
                                interface_two = common_interface_two
                                break

                    if all([interface_one, interface_two]) and any([interface_one.net, interface_two.net]):
                        if interface_one.net != interface_two.net and all([interface_one.up, interface_two.up]):
                            raise ValueError("no common network found")
                        net_one = interface_one.net
                        interface_one.detachnet()
                        interface_two.detachnet()
                        if net_one.numnetif() == 0:
                            self.delete_object(net_one.objid)
                        node_one.delnetif(interface_one_data.id)
                        node_two.delnetif(interface_two_data.id)
        finally:
            if node_one:
                node_one.lock.release()
            if node_two:
                node_two.lock.release()

    def link_update(self, link_data):
        # interface data
        interface_one_data, interface_two_data = get_interfaces(link_data)

        # get node objects identified by link data
        node_one, node_two, net_one, net_two, tunnel = self.link_nodes(link_data)

        if node_one:
            node_one.lock.acquire()
        if node_two:
            node_two.lock.acquire()

        try:
            # wireless link
            if link_data.link_type == LinkTypes.WIRELESS.value:
                raise ValueError("cannot update wireless link")
            else:
                if not node_one and not node_two:
                    if net_one and net_two:
                        # modify link between nets
                        interface = net_one.getlinknetif(net_two)
                        upstream = False

                        if not interface:
                            upstream = True
                            interface = net_two.getlinknetif(net_one)

                        if not interface:
                            raise ValueError("modify unknown link between nets")

                        if upstream:
                            interface.swapparams("_params_up")
                            link_config(net_one, interface, link_data, devname=interface.name)
                            interface.swapparams("_params_up")
                        else:
                            link_config(net_one, interface, link_data)

                        if not link_data.unidirectional:
                            if upstream:
                                link_config(net_two, interface, link_data)
                            else:
                                interface.swapparams("_params_up")
                                link_config(net_two, interface, link_data, devname=interface.name)
                                interface.swapparams("_params_up")
                    else:
                        raise ValueError("modify link for unknown nodes")
                elif not node_one:
                    # node1 = layer 2node, node2 = layer3 node
                    interface = node_two.netif(interface_two_data.id, net_one)
                    link_config(net_one, interface, link_data)
                elif not node_two:
                    # node2 = layer 2node, node1 = layer3 node
                    interface = node_one.netif(interface_one_data.id, net_one)
                    link_config(net_one, interface, link_data)
                else:
                    common_networks = node_one.commonnets(node_two)
                    for net_one, interface_one, interface_two in common_networks:
                        if interface_one_data.id and interface_one_data.id != node_one.getifindex(interface_one):
                            continue

                        link_config(net_one, interface_one, link_data, interface_two=interface_two)
                        if not link_data.unidirectional:
                            link_config(net_one, interface_two, link_data, interface_two=interface_one)
                    else:
                        raise ValueError("no common network found")
        finally:
            if node_one:
                node_one.lock.release()
            if node_two:
                node_two.lock.release()

    def node_add(self, node_data):
        """
        Add a node to the session, based on the provided node data.

        :param core.data.NodeData node_data: data to create node with
        :return: nothing
        """

        # retrieve node class for given node type
        try:
            node_type = NodeTypes(node_data.node_type)
            node_class = nodeutils.get_node_class(node_type)
        except KeyError:
            logger.error("invalid node type to create: %s", node_data.node_type)
            return None

        # set node start based on current session state, override and check when rj45
        start = self.state > EventTypes.DEFINITION_STATE.value
        enable_rj45 = getattr(self.options, "enablerj45", "0") == "1"
        if node_type == NodeTypes.RJ45 and not enable_rj45:
            start = False

        # determine node id
        node_id = node_data.id
        if not node_id:
            node_id = self.node_id_gen.next()

        # generate name if not provided
        name = node_data.name
        if not name:
            name = "%s%s" % (node_class.__name__, node_id)

        # create node
        node = self.add_object(cls=node_class, objid=node_id, name=name, start=start)

        # set node attributes
        node.type = node_data.model or "router"
        node.icon = node_data.icon
        node.canvas = node_data.canvas
        node.opaque = node_data.opaque

        # set node position and broadcast it
        self.node_set_position(node, node_data)

        # add services to default and physical nodes only
        services = node_data.services
        if node_type in [NodeTypes.DEFAULT, NodeTypes.PHYSICAL]:
            logger.info("setting model (%s) with services (%s)", node.type, services)
            self.services.addservicestonode(node, node.type, services)

        # boot nodes if created after runtime, LcxNodes, Physical, and RJ45 are all PyCoreNodes
        is_boot_node = isinstance(node, PyCoreNode) and not nodeutils.is_node(node, NodeTypes.RJ45)
        if self.state == EventTypes.RUNTIME_STATE.value and is_boot_node:
            self.write_objects()
            self.add_remove_control_interface(node=node, remove=False)

            # TODO: common method to both Physical and LxcNodes, but not the common PyCoreNode
            node.boot()

        # return node id, in case it was generated
        return node_id

    def node_update(self, node_data):
        try:
            # get node to update
            node = self.get_object(node_data.id)

            # set node position and broadcast it
            self.node_set_position(node, node_data)

            # update attributes
            node.canvas = node_data.canvas
            node.icon = node_data.icon
        except KeyError:
            logger.error("failure to update node that does not exist: %s", node_data.id)

    def node_delete(self, node_id):
        # delete node and check for session shutdown if a node was removed
        result = self.custom_delete_object(node_id)
        if result:
            self.check_shutdown()
        return result

    def node_set_position(self, node, node_data):
        # extract location values
        x = node_data.x_position
        y = node_data.y_position
        lat = node_data.latitude
        lon = node_data.longitude
        alt = node_data.altitude

        # check if we need to generate position from lat/lon/alt
        has_empty_position = all(i is None for i in [x, y])
        has_lat_lon_alt = all(i is not None for i in [lat, lon, alt])
        using_lat_lon_alt = has_empty_position and has_lat_lon_alt
        if using_lat_lon_alt:
            x, y, _ = self.location.getxyz(lat, lon, alt)

        # set position and broadcast
        node.setposition(x, y, None)

        # broadcast updated location when using lat/lon/alt
        if using_lat_lon_alt:
            self.broadcast_node_location(node)

    def broadcast_node_location(self, node):
        """
        Broadcast node location to all listeners.

        :param core.netns.nodes.PyCoreObj node: node to broadcast location for
        :return: nothing
        """
        node_data = NodeData(
            message_type=0,
            id=node.objid,
            x_position=node.position.x,
            y_position=node.position.y
        )
        self.broadcast_node(node_data)

    def shutdown(self):
        self.set_state(state=EventTypes.DATACOLLECT_STATE.value, send_event=True)
        self.set_state(state=EventTypes.SHUTDOWN_STATE.value, send_event=True)
        super(FutureSession, self).shutdown()

    def custom_delete_object(self, object_id):
        """
        Remove an emulation object.

        :param int object_id: object id to remove
        :return: True if object deleted, False otherwise
        """
        result = False
        with self._objects_lock:
            if object_id in self.objects:
                obj = self.objects.pop(object_id)
                obj.shutdown()
                result = True
        return result

    def is_active(self):
        return self.state in {EventTypes.RUNTIME_STATE.value, EventTypes.DATACOLLECT_STATE.value}

    def open_xml(self, file_name, start=False):
        """
        Import a session from the EmulationScript XML format.

        :param str file_name: xml file to load session from
        :param bool start: instantiate session if true, false otherwise
        :return: nothing
        """
        # clear out existing session
        self.clear()

        # set default node class when one is not provided
        node_class = nodeutils.get_node_class(NodeTypes.DEFAULT)
        options = {"start": start, "nodecls": node_class}
        core_document_parser(self, file_name, options)
        if start:
            self.name = os.path.basename(file_name)
            self.file_name = file_name
            self.instantiate()

    def save_xml(self, file_name, version):
        """
        Export a session to the EmulationScript XML format.

        :param str file_name: file name to write session xml to
        :param str version: xml version type
        :return: nothing
        """
        doc = core_document_writer(self, version)
        doc.writexml(file_name)

    def hook_add(self, state, file_name, source_name, data):
        """
        Store a hook from a received file message.

        :param int state: when to run hook
        :param str file_name: file name for hook
        :param str source_name: source name
        :param data: hook data
        :return: nothing
        """
        # hack to conform with old logic until updated
        state = ":%s" % state
        self.set_hook(state, file_name, source_name, data)

    def node_service_file(self, node_id, service_name, file_name, source_name, data):
        # hack to conform with old logic until updated
        service_name = ":%s" % service_name
        self.services.setservicefile(node_id, service_name, file_name, source_name, data)

    def node_file(self, node_id, source_name, file_name, data):
        node = self.get_object(node_id)

        if source_name is not None:
            node.addfile(source_name, file_name)
        elif data is not None:
            node.nodefile(file_name, data)

    def clear(self):
        self.delete_objects()
        self.del_hooks()
        self.broker.reset()

    def start_events(self):
        self.event_loop.run()

    def services_event(self, event_data):
        self.services.handleevent(event_data)

    def mobility_event(self, event_data):
        self.mobility.handleevent(event_data)

    def create_node(self, cls, name=None, model=None):
        object_id = self.node_id_gen.next()

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
        core.services.load()

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
