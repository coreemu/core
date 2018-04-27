import atexit
import os
import signal
import sys

import core.services
from core import logger
from core.coreobj import PyCoreNet
from core.coreobj import PyCoreNode
from core.data import NodeData
from core.enumerations import EventTypes
from core.enumerations import LinkTypes
from core.enumerations import NodeTypes
from core.future.futuredata import LinkOptions
from core.future.futuredata import NodeOptions
from core.misc import nodemaps
from core.misc import nodeutils
from core.session import Session
from core.xml.xmlparser import core_document_parser
from core.xml.xmlwriter import core_document_writer


def signal_handler(signal_number, _):
    """
    Handle signals and force an exit with cleanup.

    :param int signal_number: signal number
    :param _: ignored
    :return: nothing
    """
    logger.info("caught signal: %s", signal_number)
    sys.exit(signal_number)


signal.signal(signal.SIGHUP, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGUSR1, signal_handler)
signal.signal(signal.SIGUSR2, signal_handler)


def create_interface(node, network, interface_data):
    """
    Create an interface for a node on a network using provided interface data.

    :param node: node to create interface for
    :param network: network to associate interface with
    :param core.future.futuredata.InterfaceData interface_data: interface data
    :return: created interface
    """
    node.newnetif(
        network,
        addrlist=interface_data.get_addresses(),
        hwaddr=interface_data.mac,
        ifindex=interface_data.id,
        ifname=interface_data.name
    )
    return node.netif(interface_data.id, network)


def link_config(network, interface, link_options, devname=None, interface_two=None):
    """
    Convenience method for configuring a link,

    :param network: network to configure link for
    :param interface: interface to configure
    :param core.future.futuredata.LinkOptions link_options: data to configure link with
    :param str devname: device name, default is None
    :param interface_two: other interface associated, default is None
    :return: nothing
    """
    config = {
        "netif": interface,
        "bw": link_options.bandwidth,
        "delay": link_options.delay,
        "loss": link_options.per,
        "duplicate": link_options.dup,
        "jitter": link_options.jitter,
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
    def __init__(self, _id=0):
        self.id = _id

    def next(self):
        self.id += 1
        return self.id


class FutureSession(Session):
    def __init__(self, session_id, config=None, mkdir=True):
        super(FutureSession, self).__init__(session_id, config, mkdir)

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

    def _link_nodes(self, node_one_id, node_two_id):
        """
        Convenience method for retrieving nodes within link data.

        :param int node_one_id: node one id
        :param int node_two_id: node two id
        :return: nodes, network nodes if present, and tunnel if present
        :rtype: tuple
        """
        logger.debug("link message between node1(%s) and node2(%s)", node_one_id, node_two_id)

        # values to fill
        net_one = None
        net_two = None

        # retrieve node one
        node_one = self.get_object(node_one_id)
        node_two = self.get_object(node_two_id)

        # both node ids are provided
        tunnel = self.broker.gettunnel(node_one_id, node_two_id)
        logger.debug("tunnel between nodes: %s", tunnel)
        if nodeutils.is_node(tunnel, NodeTypes.TAP_BRIDGE):
            net_one = tunnel
            if tunnel.remotenum == node_one_id:
                node_one = None
            else:
                node_two = None
        # physical node connected via gre tap tunnel
        elif tunnel:
            if tunnel.remotenum == node_one_id:
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

        logger.debug("link node types n1(%s) n2(%s) net1(%s) net2(%s) tunnel(%s)",
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
        logger.debug("handling wireless linking objects(%) connect(%s)", objects, connect)
        common_networks = objects[0].commonnets(objects[1])
        if not common_networks:
            raise ValueError("no common network found for wireless link/unlink")

        for common_network, interface_one, interface_two in common_networks:
            if not nodeutils.is_node(common_network, [NodeTypes.WIRELESS_LAN, NodeTypes.EMANE]):
                logger.info("skipping common network that is not wireless/emane: %s", common_network)
                continue

            logger.info("wireless linking connect(%s): %s - %s", connect, interface_one, interface_two)
            if connect:
                common_network.link(interface_one, interface_two)
            else:
                common_network.unlink(interface_one, interface_two)

    def add_link(self, node_one_id, node_two_id, interface_one=None, interface_two=None, link_options=LinkOptions()):
        """
        Add a link between nodes.

        :param int node_one_id: node one id
        :param int node_two_id: node two id
        :param core.future.futuredata.InterfaceData interface_one: node one interface data, defaults to none
        :param core.future.futuredata.InterfaceData interface_two: node two interface data, defaults to none
        :param core.future.futuredata.LinkOptions link_options: data for creating link, defaults to no options
        :return:
        """
        # get node objects identified by link data
        node_one, node_two, net_one, net_two, tunnel = self._link_nodes(node_one_id, node_two_id)

        if node_one:
            node_one.lock.acquire()
        if node_two:
            node_two.lock.acquire()

        try:
            # wireless link
            if link_options.type == LinkTypes.WIRELESS:
                objects = [node_one, node_two, net_one, net_two]
                self._link_wireless(objects, connect=True)
            # wired link
            else:
                # 2 nodes being linked, ptp network
                if all([node_one, node_two]) and not net_one:
                    logger.info("adding link for peer to peer nodes: %s - %s", node_one.name, node_two.name)
                    ptp_class = nodeutils.get_node_class(NodeTypes.PEER_TO_PEER)
                    start = self.state > EventTypes.DEFINITION_STATE.value
                    net_one = self.add_object(cls=ptp_class, start=start)

                # node to network
                if node_one and net_one:
                    logger.info("adding link from node to network: %s - %s", node_one.name, net_one.name)
                    interface = create_interface(node_one, net_one, interface_one)
                    link_config(net_one, interface, link_options)

                # network to node
                if node_two and net_one:
                    logger.info("adding link from network to node: %s - %s", node_two.name, net_one.name)
                    interface = create_interface(node_two, net_one, interface_two)
                    if not link_options.unidirectional:
                        link_config(net_one, interface, link_options)

                # network to network
                if net_one and net_two:
                    logger.info("adding link from network to network: %s", net_one.name, net_two.name)
                    if nodeutils.is_node(net_two, NodeTypes.RJ45):
                        interface = net_two.linknet(net_one)
                    else:
                        interface = net_one.linknet(net_two)

                    link_config(net_one, interface, link_options)

                    if not link_options.unidirectional:
                        interface.swapparams("_params_up")
                        link_config(net_two, interface, link_options, devname=interface.name)
                        interface.swapparams("_params_up")

                # a tunnel node was found for the nodes
                addresses = []
                if not node_one and all([net_one, interface_one]):
                    addresses.extend(interface_one.get_addresses())

                if not node_two and all([net_two, interface_two]):
                    addresses.extend(interface_two.get_addresses())

                # tunnel node logic
                key = link_options.key
                if key and nodeutils.is_node(net_one, NodeTypes.TUNNEL):
                    logger.info("setting tunnel key for: %s", net_one.name)
                    net_one.setkey(key)
                    if addresses:
                        net_one.addrconfig(addresses)
                if key and nodeutils.is_node(net_two, NodeTypes.TUNNEL):
                    logger.info("setting tunnel key for: %s", net_two.name)
                    net_two.setkey(key)
                    if addresses:
                        net_two.addrconfig(addresses)

                # physical node connected with tunnel
                if not net_one and not net_two and (node_one or node_two):
                    if node_one and nodeutils.is_node(node_one, NodeTypes.PHYSICAL):
                        logger.info("adding link for physical node: %s", node_one.name)
                        addresses = interface_one.get_addresses()
                        node_one.adoptnetif(tunnel, interface_one.id, interface_one.mac, addresses)
                        link_config(node_one, tunnel, link_options)
                    elif node_two and nodeutils.is_node(node_two, NodeTypes.PHYSICAL):
                        logger.info("adding link for physical node: %s", node_two.name)
                        addresses = interface_two.get_addresses()
                        node_two.adoptnetif(tunnel, interface_two.id, interface_two.mac, addresses)
                        link_config(node_two, tunnel, link_options)
        finally:
            if node_one:
                node_one.lock.release()
            if node_two:
                node_two.lock.release()

    def delete_link(self, node_one_id, node_two_id, interface_one_id, interface_two_id, link_type=LinkTypes.WIRED):
        """
        Delete a link between nodes.

        :param int node_one_id: node one id
        :param int node_two_id: node two id
        :param int interface_one_id: interface id for node one
        :param int interface_two_id: interface id for node two
        :param core.enumerations.LinkTypes link_type: link type to delete
        :return: nothing
        """
        # interface data
        # interface_one_data, interface_two_data = get_interfaces(link_data)

        # get node objects identified by link data
        node_one, node_two, net_one, net_two, tunnel = self._link_nodes(node_one_id, node_two_id)

        if node_one:
            node_one.lock.acquire()
        if node_two:
            node_two.lock.acquire()

        try:
            # wireless link
            if link_type == LinkTypes.WIRELESS:
                objects = [node_one, node_two, net_one, net_two]
                self._link_wireless(objects, connect=False)
            # wired link
            else:
                if all([node_one, node_two]):
                    # TODO: fix this for the case where ifindex[1,2] are not specified
                    # a wired unlink event, delete the connecting bridge
                    interface_one = node_one.netif(interface_one_id)
                    interface_two = node_two.netif(interface_two_id)

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

                        logger.info("deleting link node(%s):interface(%s) node(%s):interface(%s)",
                                    node_one.name, interface_one.name, node_two.name, interface_two.name)
                        net_one = interface_one.net
                        interface_one.detachnet()
                        interface_two.detachnet()
                        if net_one.numnetif() == 0:
                            self.delete_object(net_one.objid)
                        node_one.delnetif(interface_one.netindex)
                        node_two.delnetif(interface_two.netindex)
        finally:
            if node_one:
                node_one.lock.release()
            if node_two:
                node_two.lock.release()

    def update_link(self, node_one_id, node_two_id, link_options, interface_one_id=None, interface_two_id=None):
        """
        Update link information between nodes.

        :param int node_one_id: node one id
        :param int node_two_id: node two id
        :param int interface_one_id: interface id for node one
        :param int interface_two_id: interface id for node two
        :param core.future.futuredata.LinkOptions link_options: data to update link with
        :return: nothing
        """
        # interface data
        # interface_one_data, interface_two_data = get_interfaces(link_data)

        # get node objects identified by link data
        node_one, node_two, net_one, net_two, tunnel = self._link_nodes(node_one_id, node_two_id)

        if node_one:
            node_one.lock.acquire()
        if node_two:
            node_two.lock.acquire()

        try:
            # wireless link
            if link_options.type == LinkTypes.WIRELESS.value:
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
                            link_config(net_one, interface, link_options, devname=interface.name)
                            interface.swapparams("_params_up")
                        else:
                            link_config(net_one, interface, link_options)

                        if not link_options.unidirectional:
                            if upstream:
                                link_config(net_two, interface, link_options)
                            else:
                                interface.swapparams("_params_up")
                                link_config(net_two, interface, link_options, devname=interface.name)
                                interface.swapparams("_params_up")
                    else:
                        raise ValueError("modify link for unknown nodes")
                elif not node_one:
                    # node1 = layer 2node, node2 = layer3 node
                    interface = node_two.netif(interface_two_id, net_one)
                    link_config(net_one, interface, link_options)
                elif not node_two:
                    # node2 = layer 2node, node1 = layer3 node
                    interface = node_one.netif(interface_one_id, net_one)
                    link_config(net_one, interface, link_options)
                else:
                    common_networks = node_one.commonnets(node_two)
                    if not common_networks:
                        raise ValueError("no common network found")

                    for net_one, interface_one, interface_two in common_networks:
                        if interface_one_id is not None and interface_one_id != node_one.getifindex(interface_one):
                            continue

                        link_config(net_one, interface_one, link_options, interface_two=interface_two)
                        if not link_options.unidirectional:
                            link_config(net_one, interface_two, link_options, interface_two=interface_one)

        finally:
            if node_one:
                node_one.lock.release()
            if node_two:
                node_two.lock.release()

    def add_node(self, _type=NodeTypes.DEFAULT, _id=None, node_options=NodeOptions()):
        """
        Add a node to the session, based on the provided node data.

        :param core.enumerations.NodeTypes _type: type of node to create
        :param int _id: id for node, defaults to None for generated id
        :param core.future.futuredata.NodeOptions node_options: data to create node with
        :return: created node
        """

        # retrieve node class for given node type
        try:
            node_class = nodeutils.get_node_class(_type)
        except KeyError:
            logger.error("invalid node type to create: %s", _type)
            return None

        # set node start based on current session state, override and check when rj45
        start = self.state > EventTypes.DEFINITION_STATE.value
        enable_rj45 = getattr(self.options, "enablerj45", "0") == "1"
        if _type == NodeTypes.RJ45 and not enable_rj45:
            start = False

        # determine node id
        if not _id:
            while True:
                _id = self.node_id_gen.next()
                if _id not in self.objects:
                    break

        # generate name if not provided
        name = node_options.name
        if not name:
            name = "%s%s" % (node_class.__name__, _id)

        # create node
        logger.info("creating node(%s) id(%s) name(%s) start(%s)", node_class.__name__, _id, name, start)
        node = self.add_object(cls=node_class, objid=_id, name=name, start=start)

        # set node attributes
        node.icon = node_options.icon
        node.canvas = node_options.canvas
        node.opaque = node_options.opaque

        # set node position and broadcast it
        self.set_node_position(node, node_options)

        # add services to default and physical nodes only
        if _type in [NodeTypes.DEFAULT, NodeTypes.PHYSICAL]:
            node.type = node_options.model
            logger.debug("set node type: %s", node.type)
            services = "|".join(node_options.services) or None
            self.services.addservicestonode(node, node.type, services)

        # boot nodes if created after runtime, LcxNodes, Physical, and RJ45 are all PyCoreNodes
        is_boot_node = isinstance(node, PyCoreNode) and not nodeutils.is_node(node, NodeTypes.RJ45)
        if self.state == EventTypes.RUNTIME_STATE.value and is_boot_node:
            self.write_objects()
            self.add_remove_control_interface(node=node, remove=False)

            # TODO: common method to both Physical and LxcNodes, but not the common PyCoreNode
            node.boot()

        return node

    def update_node(self, node_id, node_options):
        """
        Update node information.

        :param int node_id: id of node to update
        :param core.future.futuredata.NodeOptions node_options: data to update node with
        :return: True if node updated, False otherwise
        :rtype: bool
        """
        result = False
        try:
            # get node to update
            node = self.get_object(node_id)

            # set node position and broadcast it
            self.set_node_position(node, node_options)

            # update attributes
            node.canvas = node_options.canvas
            node.icon = node_options.icon

            # set node as updated successfully
            result = True
        except KeyError:
            logger.error("failure to update node that does not exist: %s", node_options.id)

        return result

    def delete_node(self, node_id):
        """
        Delete a node from the session and check if session should shutdown, if no nodes are left.

        :param int node_id: id of node to delete
        :return: True if node deleted, False otherwise
        :rtype: bool
        """
        # delete node and check for session shutdown if a node was removed
        result = self.custom_delete_object(node_id)
        if result:
            self.check_shutdown()
        return result

    def set_node_position(self, node, node_options):
        """
        Set position for a node, use lat/lon/alt if needed.

        :param node: node to set position for
        :param core.future.futuredata.NodeOptions node_options: data for node
        :return: nothing
        """
        # extract location values
        x = node_options.x
        y = node_options.y
        lat = node_options.lat
        lon = node_options.lon
        alt = node_options.alt

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

    def start_mobility(self, node_ids=None):
        """
        Start mobility for the provided node ids.

        :param list[int] node_ids: nodes to start mobility for
        :return: nothing
        """
        self.mobility.startup(node_ids)

    def shutdown(self):
        """
        Shutdown session.

        :return: nothing
        """
        self.set_state(EventTypes.DATACOLLECT_STATE, send_event=True)
        self.set_state(EventTypes.SHUTDOWN_STATE, send_event=True)
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
        """
        Determine if this session is considered to be active. (Runtime or Data collect states)

        :return: True if active, False otherwise
        """
        result = self.state in {EventTypes.RUNTIME_STATE.value, EventTypes.DATACOLLECT_STATE.value}
        logger.info("checking if session is active: %s", result)
        return result

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

    def add_hook(self, state, file_name, source_name, data):
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

    def add_node_service_file(self, node_id, service_name, file_name, source_name, data):
        """
        Add a service file for a node.

        :param int node_id: node to add service file to
        :param str service_name: service file to add
        :param str file_name: file name to use
        :param str source_name: source file
        :param str data: file data to save
        :return: nothing
        """
        # hack to conform with old logic until updated
        service_name = ":%s" % service_name
        self.services.setservicefile(node_id, service_name, file_name, source_name, data)

    def add_node_file(self, node_id, source_name, file_name, data):
        """
        Add a file to a node.

        :param int node_id: node to add file to
        :param str source_name: source file name
        :param str file_name: file name to add
        :param str data: file data
        :return: nothing
        """

        node = self.get_object(node_id)

        if source_name is not None:
            node.addfile(source_name, file_name)
        elif data is not None:
            node.nodefile(file_name, data)

    def clear(self):
        """
        Clear all CORE session data. (objects, hooks, broker)

        :return: nothing
        """
        self.delete_objects()
        self.del_hooks()
        self.broker.reset()

    def start_events(self):
        """
        Start event loop.

        :return: nothing
        """
        self.event_loop.run()

    def services_event(self, event_data):
        """
        Handle a service event.

        :param core.data.EventData event_data: event data to handle
        :return:
        """
        self.services.handleevent(event_data)

    def mobility_event(self, event_data):
        """
        Handle a mobility event.

        :param core.data.EventData event_data: event data to handle
        :return: nothing
        """
        self.mobility.handleevent(event_data)

    def create_wireless_node(self, _id=None, node_options=NodeOptions()):
        """
        Create a wireless node for use within an wireless/EMANE networks.

        :param int _id: int for node, defaults to None and will be generated
        :param core.future.futuredata.NodeOptions node_options: options for emane node, model will always be "mdr"
        :return: new emane node
        :rtype: core.netns.nodes.CoreNode
        """
        node_options.model = "mdr"
        return self.add_node(_type=NodeTypes.DEFAULT, _id=_id, node_options=node_options)

    def create_emane_network(self, model, geo_reference, geo_scale=None, node_options=NodeOptions()):
        """
        Convenience method for creating an emane network.

        :param model: emane model to use for emane network
        :param geo_reference: geo reference point to use for emane node locations
        :param geo_scale: geo scale to use for emane node locations, defaults to 1.0
        :param core.future.futuredata.NodeOptions node_options: options for emane node being created
        :return: create emane network
        """
        # required to be set for emane to function properly
        self.location.setrefgeo(*geo_reference)
        if geo_scale:
            self.location.refscale = geo_scale

        # create and return network
        emane_network = self.add_node(_type=NodeTypes.EMANE, node_options=node_options)
        self.set_emane_model(emane_network, model)
        return emane_network

    def set_emane_model(self, emane_node, emane_model):
        """
        Set emane model for a given emane node.

        :param emane_node: emane node to set model for
        :param emane_model: emane model to set
        :return: nothing
        """
        values = list(emane_model.getdefaultvalues())
        self.emane.setconfig(emane_node.objid, emane_model.name, values)

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


class CoreEmu(object):
    """
    Provides logic for creating and configuring CORE sessions and the nodes within them.
    """

    def __init__(self, config=None):
        """
        Create a CoreEmu object.

        :param dict config: configuration options
        """
        # configuration
        self.config = config

        # session management
        self.session_id_gen = IdGen(_id=59999)
        self.sessions = {}

        # set default nodes
        # set default node map
        node_map = nodemaps.NODES
        nodeutils.set_node_map(node_map)

        # load default services
        core.services.load()

        # catch exit event
        atexit.register(self.shutdown)

    def update_nodes(self, node_map):
        """
        Updates node map used by core.

        :param dict node_map: node map to update existing node map with
        :return: nothing
        """
        nodeutils.update_node_map(node_map)

    def shutdown(self):
        """
        Shutdown all CORE session.

        :return: nothing
        """
        logger.info("shutting down all session")
        sessions = self.sessions.copy()
        self.sessions.clear()
        for session in sessions.itervalues():
            session.shutdown()

    def create_session(self, _id=None, master=True):
        """
        Create a new CORE session, set to master if running standalone.

        :param int _id: session id for new session
        :param bool master: sets session to master
        :return: created session
        :rtype: FutureSession
        """

        session_id = _id
        if not session_id:
            while True:
                session_id = self.session_id_gen.next()
                if session_id not in self.sessions:
                    break

        session = FutureSession(session_id, config=self.config)
        logger.info("created session: %s", session_id)
        if master:
            session.master = True

        self.sessions[session_id] = session
        return session

    def delete_session(self, _id):
        """
        Shutdown and delete a CORE session.

        :param int _id: session id to delete
        :return: True if deleted, False otherwise
        :rtype: bool
        """
        logger.info("deleting session: %s", _id)
        session = self.sessions.pop(_id, None)
        result = False
        if session:
            logger.info("shutting session down: %s", _id)
            session.shutdown()
            result = True
        else:
            logger.error("session to delete did not exist: %s", _id)

        return result
