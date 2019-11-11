"""
Incorporate grpc into python tkinter GUI
"""
import logging
import os

from core.api.grpc import client, core_pb2
from coretk.coretocanvas import CoreToCanvasMapping
from coretk.dialogs.sessions import SessionsDialog
from coretk.emaneodelnodeconfig import EmaneModelNodeConfig
from coretk.images import Images
from coretk.interface import Interface, InterfaceManager
from coretk.mobilitynodeconfig import MobilityNodeConfig
from coretk.wlannodeconfig import WlanNodeConfig

NETWORK_NODES = {"switch", "hub", "wlan", "rj45", "tunnel", "emane"}
DEFAULT_NODES = {"router", "host", "PC", "mdr", "prouter"}
OBSERVER_WIDGETS = {
    "processes": "ps",
    "ifconfig": "ifconfig",
    "IPV4 Routes": "ip -4 ro",
    "IPV6 Routes": "ip -6 ro",
    "Listening sockets": "netstat -tuwnl",
    "IPv4 MFC entries": "ip -4 mroute show",
    "IPv6 MFC entries": "ip -6 mroute show",
    "firewall rules": "iptables -L",
    "IPSec policies": "setkey -DP",
}


class Node:
    def __init__(self, session_id, node_id, node_type, model, x, y, name):
        """
        Create an instance of a node

        :param int session_id: session id
        :param int node_id: node id
        :param core_pb2.NodeType node_type: node type
        :param int x: x coordinate
        :param int y: coordinate
        :param str name: node name
        """
        self.session_id = session_id
        self.node_id = node_id
        self.type = node_type
        self.x = x
        self.y = y
        self.model = model
        self.name = name
        self.interfaces = []


class Edge:
    def __init__(self, session_id, node_id_1, node_type_1, node_id_2, node_type_2):
        """
        Create an instance of an edge
        :param int session_id: session id
        :param int node_id_1: node 1 id
        :param int node_type_1: node 1 type
        :param core_pb2.NodeType node_id_2: node 2 id
        :param core_pb2.NodeType node_type_2: node 2 type
        """
        self.session_id = session_id
        self.id1 = node_id_1
        self.id2 = node_id_2
        self.type1 = node_type_1
        self.type2 = node_type_2
        self.interface_1 = None
        self.interface_2 = None


class CoreServer:
    def __init__(self, name, address, port):
        self.name = name
        self.address = address
        self.port = port


class CustomNode:
    def __init__(self, name, image, image_file, services):
        self.name = name
        self.image = image
        self.image_file = image_file
        self.services = services


class Observer:
    def __init__(self, name, cmd):
        self.name = name
        self.cmd = cmd


class CoreClient:
    def __init__(self, app):
        """
        Create a CoreGrpc instance
        """
        self.client = client.CoreGrpcClient()
        self.session_id = None
        self.node_ids = []
        self.app = app
        self.master = app.master
        self.interface_helper = None
        self.services = {}
        self.observer = None

        # loaded configuration data
        self.servers = {}
        self.custom_nodes = {}
        self.custom_observers = {}
        self.read_config()

        # data for managing the current session
        self.state = None
        self.nodes = {}
        self.edges = {}
        self.hooks = {}
        self.id = 1
        self.reusable = []
        self.preexisting = set()
        self.interfaces_manager = InterfaceManager()
        self.core_mapping = CoreToCanvasMapping()
        self.wlanconfig_management = WlanNodeConfig()
        self.mobilityconfig_management = MobilityNodeConfig()
        self.emaneconfig_management = EmaneModelNodeConfig(app)
        self.emane_config = None

    def set_observer(self, value):
        self.observer = value

    def read_config(self):
        # read distributed server
        for config in self.app.config.get("servers", []):
            server = CoreServer(config["name"], config["address"], config["port"])
            self.servers[server.name] = server

        # read custom nodes
        for config in self.app.config.get("nodes", []):
            image_file = config["image"]
            image = Images.get_custom(image_file)
            custom_node = CustomNode(
                config["name"], image, image_file, set(config["services"])
            )
            self.custom_nodes[custom_node.name] = custom_node

        # read observers
        for config in self.app.config.get("observers", []):
            observer = Observer(config["name"], config["cmd"])
            self.custom_observers[observer.name] = observer

    def handle_events(self, event):
        logging.info("event: %s", event)
        if event.HasField("link_event"):
            self.app.canvas.wireless_draw.hangle_link_event(event.link_event)
        elif event.HasField("session_event"):
            if event.session_event.event <= core_pb2.SessionState.SHUTDOWN:
                self.state = event.session_event.event

    def handle_throughputs(self, event):
        interface_throughputs = event.interface_throughputs
        for i in interface_throughputs:
            print("")
        return
        throughputs_belong_to_session = []
        for if_tp in interface_throughputs:
            if if_tp.node_id in self.node_ids:
                throughputs_belong_to_session.append(if_tp)
        self.throughput_draw.process_grpc_throughput_event(
            throughputs_belong_to_session
        )

    def join_session(self, session_id):
        # update session and title
        self.session_id = session_id
        self.master.title(f"CORE Session({self.session_id})")

        # clear session data
        self.reusable.clear()
        self.preexisting.clear()
        self.nodes.clear()
        self.edges.clear()
        self.hooks.clear()
        self.wlanconfig_management.configurations.clear()
        self.mobilityconfig_management.configurations.clear()
        self.emane_config = None

        # get session data
        response = self.client.get_session(self.session_id)
        logging.info("joining session(%s): %s", self.session_id, response)
        session = response.session
        self.state = session.state
        self.client.events(self.session_id, self.handle_events)

        # get hooks
        response = self.client.get_hooks(self.session_id)
        logging.info("joined session hooks: %s", response)
        for hook in response.hooks:
            self.hooks[hook.file] = hook

        # get wlan configs
        for node in session.nodes:
            if node.type == core_pb2.NodeType.WIRELESS_LAN:
                response = self.client.get_wlan_config(self.session_id, node.id)
                logging.info("wlan config(%s): %s", node.id, response)
                node_config = response.config
                config = {x: node_config[x].value for x in node_config}
                self.wlanconfig_management.configurations[node.id] = config

        # get mobility configs
        response = self.client.get_mobility_configs(self.session_id)
        logging.info("mobility configs: %s", response)
        for node_id in response.configs:
            node_config = response.configs[node_id].config
            config = {x: node_config[x].value for x in node_config}
            self.mobilityconfig_management.configurations[node_id] = config

        # get emane config
        response = self.client.get_emane_config(self.session_id)
        logging.info("emane config: %s", response)
        self.emane_config = response.config

        # get emane model config

        # determine next node id and reusable nodes
        max_id = 1
        for node in session.nodes:
            if node.id > max_id:
                max_id = node.id
            self.preexisting.add(node.id)
        self.id = max_id
        for i in range(1, self.id):
            if i not in self.preexisting:
                self.reusable.append(i)

        # draw session
        self.app.canvas.canvas_reset_and_redraw(session)

        # draw tool bar appropritate with session state
        if self.is_runtime():
            self.app.toolbar.runtime_frame.tkraise()
        else:
            self.app.toolbar.design_frame.tkraise()

    def is_runtime(self):
        return self.state == core_pb2.SessionState.RUNTIME

    def create_new_session(self):
        """
        Create a new session

        :return: nothing
        """
        response = self.client.create_session()
        logging.info("created session: %s", response)
        self.join_session(response.session_id)

    def delete_session(self, custom_sid=None):
        if custom_sid is None:
            sid = self.session_id
        else:
            sid = custom_sid
        response = self.client.delete_session(sid)
        logging.info("Deleted session result: %s", response)

    def shutdown_session(self, custom_sid=None):
        if custom_sid is None:
            sid = self.session_id
        else:
            sid = custom_sid
        s = self.client.get_session(sid).session
        # delete links and nodes from running session
        if s.state == core_pb2.SessionState.RUNTIME:
            self.client.set_session_state(
                self.session_id, core_pb2.SessionState.DATACOLLECT
            )
            self.delete_links(sid)
            self.delete_nodes(sid)
        self.delete_session(sid)

    def set_up(self):
        """
        Query sessions, if there exist any, prompt whether to join one

        :return: existing sessions
        """
        self.client.connect()

        # get service information
        response = self.client.get_services()
        for service in response.services:
            group_services = self.services.setdefault(service.group, [])
            group_services.append(service)

        # if there are no sessions, create a new session, else join a session
        response = self.client.get_sessions()
        logging.info("current sessions: %s", response)
        sessions = response.sessions
        if len(sessions) == 0:
            self.create_new_session()
        else:
            dialog = SessionsDialog(self.app, self.app)
            dialog.show()

    def get_session_state(self):
        response = self.client.get_session(self.session_id)
        # logging.info("get session: %s", response)
        return response.session.state

    def edit_node(self, node_id, x, y):
        position = core_pb2.Position(x=x, y=y)
        response = self.client.edit_node(self.session_id, node_id, position)
        logging.info("updated node id %s: %s", node_id, response)

    def delete_nodes(self, delete_session=None):
        if delete_session is None:
            sid = self.session_id
        else:
            sid = delete_session
        for node in self.client.get_session(sid).session.nodes:
            response = self.client.delete_node(self.session_id, node.id)
            logging.info("delete nodes %s", response)

    def delete_links(self, delete_session=None):
        if delete_session is None:
            sid = self.session_id
        else:
            sid = delete_session

        for link in self.client.get_session(sid).session.links:
            response = self.client.delete_link(
                self.session_id,
                link.node_one_id,
                link.node_two_id,
                link.interface_one.id,
                link.interface_two.id,
            )
            logging.info("delete links %s", response)

    def start_session(self):
        nodes = self.get_nodes_proto()
        links = self.get_links_proto()
        wlan_configs = self.get_wlan_configs_proto()
        mobility_configs = self.get_mobility_configs_proto()
        emane_model_configs = self.get_emane_model_configs_proto()
        hooks = list(self.hooks.values())
        if self.emane_config:
            emane_config = {x: self.emane_config[x].value for x in self.emane_config}
        else:
            emane_config = None
        response = self.client.start_session(
            self.session_id,
            nodes,
            links,
            hooks=hooks,
            wlan_configs=wlan_configs,
            emane_config=emane_config,
            emane_model_configs=emane_model_configs,
            mobility_configs=mobility_configs,
        )
        logging.debug("Start session %s, result: %s", self.session_id, response.result)

    def stop_session(self):
        response = self.client.stop_session(session_id=self.session_id)
        logging.debug("coregrpc.py Stop session, result: %s", response.result)

    # # TODO no need, might get rid of this
    # def add_link(self, id1, id2, type1, type2, edge):
    #     """
    #     Grpc client request add link
    #
    #     :param int session_id: session id
    #     :param int id1: node 1 core id
    #     :param core_pb2.NodeType type1: node 1 core node type
    #     :param int id2: node 2 core id
    #     :param core_pb2.NodeType type2: node 2 core node type
    #     :return: nothing
    #     """
    #     if1 = self.create_interface(type1, edge.interface_1)
    #     if2 = self.create_interface(type2, edge.interface_2)
    #     response = self.client.add_link(self.session_id, id1, id2, if1, if2)
    #     logging.info("created link: %s", response)

    def launch_terminal(self, node_id):
        response = self.client.get_node_terminal(self.session_id, node_id)
        logging.info("get terminal %s", response.terminal)
        os.system("xterm -e %s &" % response.terminal)

    def save_xml(self, file_path):
        """
        Save core session as to an xml file

        :param str file_path: file path that user pick
        :return: nothing
        """
        response = self.client.save_xml(self.session_id, file_path)
        logging.info("coregrpc.py save xml %s", response)
        self.client.events(self.session_id, self.handle_events)

    def open_xml(self, file_path):
        """
        Open core xml

        :param str file_path: file to open
        :return: session id
        """
        response = self.client.open_xml(file_path)
        logging.debug("open xml: %s", response)
        self.join_session(response.session_id)

    def close(self):
        """
        Clean ups when done using grpc

        :return: nothing
        """
        logging.debug("Close grpc")
        self.client.close()

    def peek_id(self):
        """
        Peek the next id to be used

        :return: nothing
        """
        if len(self.reusable) == 0:
            return self.id
        else:
            return self.reusable[0]

    def get_id(self):
        """
        Get the next node id as well as update id status and reusable ids

        :rtype: int
        :return: the next id to be used
        """
        if len(self.reusable) == 0:
            new_id = self.id
            self.id = self.id + 1
            return new_id
        else:
            return self.reusable.pop(0)

    def is_model_node(self, name):
        return name in DEFAULT_NODES or name in self.custom_nodes

    def add_graph_node(self, session_id, canvas_id, x, y, name):
        """
        Add node, with information filled in, to grpc manager

        :param int session_id: session id
        :param int canvas_id: node's canvas id
        :param int x: x coord
        :param int y: y coord
        :param str name: node type
        :return: nothing
        """
        node_type = None
        node_model = None
        if name in NETWORK_NODES:
            if name == "switch":
                node_type = core_pb2.NodeType.SWITCH
            elif name == "hub":
                node_type = core_pb2.NodeType.HUB
            elif name == "wlan":
                node_type = core_pb2.NodeType.WIRELESS_LAN
            elif name == "rj45":
                node_type = core_pb2.NodeType.RJ45
            elif name == "emane":
                node_type = core_pb2.NodeType.EMANE
            elif name == "tunnel":
                node_type = core_pb2.NodeType.TUNNEL
            elif name == "emane":
                node_type = core_pb2.NodeType.EMANE
        elif self.is_model_node(name):
            node_type = core_pb2.NodeType.DEFAULT
            node_model = name
        else:
            logging.error("invalid node name: %s", name)
        nid = self.get_id()
        create_node = Node(session_id, nid, node_type, node_model, x, y, name)

        # set default configuration for wireless node
        self.wlanconfig_management.set_default_config(node_type, nid)
        self.mobilityconfig_management.set_default_configuration(node_type, nid)

        # set default emane configuration for emane node
        if node_type == core_pb2.NodeType.EMANE:
            self.emaneconfig_management.set_default_config(nid)

        self.nodes[canvas_id] = create_node
        self.core_mapping.map_core_id_to_canvas_id(nid, canvas_id)
        logging.debug(
            "Adding node to core.. session id: %s, coords: (%s, %s), name: %s",
            session_id,
            x,
            y,
            name,
        )

    def delete_wanted_graph_nodes(self, canvas_ids, tokens):
        """
        remove the nodes selected by the user and anything related to that node
        such as link, configurations, interfaces

        :param list(int) canvas_ids: list of canvas node ids
        :return: nothing
        """
        # keep reference to the core ids
        core_node_ids = [self.nodes[x].node_id for x in canvas_ids]
        node_interface_pairs = []

        # delete the nodes
        for i in canvas_ids:
            try:
                n = self.nodes.pop(i)
                self.reusable.append(n.node_id)
            except KeyError:
                logging.error("coreclient.py INVALID NODE CANVAS ID")

        self.reusable.sort()

        # delete the edges and interfaces
        for i in tokens:
            try:
                e = self.edges.pop(i)
                if e.interface_1 is not None:
                    node_interface_pairs.append(tuple([e.id1, e.interface_1.id]))
                if e.interface_2 is not None:
                    node_interface_pairs.append(tuple([e.id2, e.interface_2.id]))

            except KeyError:
                logging.error("coreclient.py invalid edge token ")

        # delete global emane config if there no longer exist any emane cloud
        if core_pb2.NodeType.EMANE not in [x.type for x in self.nodes.values()]:
            self.emane_config = None

        # delete any mobility configuration, wlan configuration
        for i in core_node_ids:
            if i in self.mobilityconfig_management.configurations:
                self.mobilityconfig_management.configurations.pop(i)
            if i in self.wlanconfig_management.configurations:
                self.wlanconfig_management.configurations.pop(i)

        # delete emane configurations
        for i in node_interface_pairs:
            if i in self.emaneconfig_management.configurations:
                self.emaneconfig_management.configurations.pop(i)
        for i in core_node_ids:
            if tuple([i, None]) in self.emaneconfig_management.configurations:
                self.emaneconfig_management.configurations.pop(tuple([i, None]))

    def add_preexisting_node(self, canvas_node, session_id, core_node, name):
        """
        Add preexisting nodes to grpc manager

        :param str name: node_type
        :param core_pb2.Node core_node: core node grpc message
        :param coretk.graph.CanvasNode canvas_node: canvas node
        :param int session_id: session id
        :return: nothing
        """

        # update the next available id
        core_id = core_node.id
        if self.id is None or core_id >= self.id:
            self.id = core_id + 1
        self.preexisting.add(core_id)
        n = Node(
            session_id,
            core_id,
            core_node.type,
            core_node.model,
            canvas_node.x_coord,
            canvas_node.y_coord,
            name,
        )
        self.nodes[canvas_node.id] = n

    def update_node_location(self, canvas_id, new_x, new_y):
        """
        update node

        :param int canvas_id: canvas id of that node
        :param int new_x: new x coord
        :param int new_y: new y coord
        :return: nothing
        """
        self.nodes[canvas_id].x = new_x
        self.nodes[canvas_id].y = new_y

    def update_reusable_id(self):
        """
        Update available id for reuse

        :return: nothing
        """
        if len(self.preexisting) > 0:
            for i in range(1, self.id):
                if i not in self.preexisting:
                    self.reusable.append(i)

            self.preexisting.clear()
            logging.debug("Next id: %s, Reusable: %s", self.id, self.reusable)

    def create_interface(self, node_type, gui_interface):
        """
        create a protobuf interface given the interface object stored by the programmer

        :param core_bp2.NodeType type: node type
        :param coretk.interface.Interface gui_interface: the programmer's interface object
        :rtype: core_bp2.Interface
        :return: protobuf interface object
        """
        if node_type != core_pb2.NodeType.DEFAULT:
            return None
        else:
            interface = core_pb2.Interface(
                id=gui_interface.id,
                name=gui_interface.name,
                mac=gui_interface.mac,
                ip4=gui_interface.ipv4,
                ip4mask=gui_interface.ip4prefix,
            )
            logging.debug("create interface: %s", interface)
            return interface

    def create_edge_interface(self, edge, src_canvas_id, dst_canvas_id):
        """
        Create the interface for the two end of an edge, add a copy to node's interfaces

        :param coretk.coreclient.Edge edge: edge to add interfaces to
        :param int src_canvas_id: canvas id for the source node
        :param int dst_canvas_id: canvas id for the destination node
        :return: nothing
        """
        src_interface = None
        dst_interface = None
        print("create interface")
        self.interfaces_manager.new_subnet()

        src_node = self.nodes[src_canvas_id]
        if self.is_model_node(src_node.model):
            ifid = len(src_node.interfaces)
            name = "eth" + str(ifid)
            src_interface = Interface(
                name=name, ifid=ifid, ipv4=str(self.interfaces_manager.get_address())
            )
            self.nodes[src_canvas_id].interfaces.append(src_interface)
            logging.debug(
                "Create source interface 1... IP: %s, name: %s",
                src_interface.ipv4,
                src_interface.name,
            )

        dst_node = self.nodes[dst_canvas_id]
        if self.is_model_node(dst_node.model):
            ifid = len(dst_node.interfaces)
            name = "eth" + str(ifid)
            dst_interface = Interface(
                name=name, ifid=ifid, ipv4=str(self.interfaces_manager.get_address())
            )
            self.nodes[dst_canvas_id].interfaces.append(dst_interface)
            logging.debug(
                "Create destination interface... IP: %s, name: %s",
                dst_interface.ipv4,
                dst_interface.name,
            )

        edge.interface_1 = src_interface
        edge.interface_2 = dst_interface
        return src_interface, dst_interface

    def add_edge(self, session_id, token, canvas_id_1, canvas_id_2):
        """
        Add an edge to grpc manager

        :param int session_id: core session id
        :param tuple(int, int) token: edge's identification in the canvas
        :param int canvas_id_1: canvas id of source node
        :param int canvas_id_2: canvas_id of destination node

        :return: nothing
        """
        node_one = self.nodes[canvas_id_1]
        node_two = self.nodes[canvas_id_2]
        if canvas_id_1 in self.nodes and canvas_id_2 in self.nodes:
            edge = Edge(
                session_id,
                node_one.node_id,
                node_one.type,
                node_two.node_id,
                node_two.type,
            )
            self.edges[token] = edge
            src_interface, dst_interface = self.create_edge_interface(
                edge, canvas_id_1, canvas_id_2
            )
            node_one_id = node_one.node_id
            node_two_id = node_two.node_id

            # provide a way to get an edge from a core node and an interface id
            if src_interface is not None:
                self.core_mapping.map_node_and_interface_to_canvas_edge(
                    node_one_id, src_interface.id, token
                )

            if dst_interface is not None:
                self.core_mapping.map_node_and_interface_to_canvas_edge(
                    node_two_id, dst_interface.id, token
                )

            if (
                node_one.type == core_pb2.NodeType.EMANE
                and node_two.type == core_pb2.NodeType.DEFAULT
            ):
                if node_two.model == "mdr":
                    self.emaneconfig_management.set_default_for_mdr(
                        node_one.node_id, node_two.node_id, dst_interface.id
                    )
            elif (
                node_two.type == core_pb2.NodeType.EMANE
                and node_one.type == core_pb2.NodeType.DEFAULT
            ):
                if node_one.model == "mdr":
                    self.emaneconfig_management.set_default_for_mdr(
                        node_two.node_id, node_one.node_id, src_interface.id
                    )

        else:
            logging.error("grpcmanagement.py INVALID CANVAS NODE ID")

    def get_nodes_proto(self):
        nodes = []
        for node in self.nodes.values():
            pos = core_pb2.Position(x=int(node.x), y=int(node.y))
            proto_node = core_pb2.Node(
                id=node.node_id, type=node.type, position=pos, model=node.model
            )
            nodes.append(proto_node)
        return nodes

    def get_links_proto(self):
        links = []
        for edge in self.edges.values():
            interface_one = self.create_interface(edge.type1, edge.interface_1)
            interface_two = self.create_interface(edge.type2, edge.interface_2)
            link = core_pb2.Link(
                node_one_id=edge.id1,
                node_two_id=edge.id2,
                type=core_pb2.LinkType.WIRED,
                interface_one=interface_one,
                interface_two=interface_two,
            )
            links.append(link)
        return links

    def get_wlan_configs_proto(self):
        configs = []
        wlan_configs = self.wlanconfig_management.configurations
        for node_id in wlan_configs:
            config = wlan_configs[node_id]
            config_proto = core_pb2.WlanConfig(node_id=node_id, config=config)
            configs.append(config_proto)
        return configs

    def get_mobility_configs_proto(self):
        configs = []
        mobility_configs = self.mobilityconfig_management.configurations
        for node_id in mobility_configs:
            config = mobility_configs[node_id]
            config_proto = core_pb2.MobilityConfig(node_id=node_id, config=config)
            configs.append(config_proto)
        return configs

    def get_emane_model_configs_proto(self):
        configs = []
        emane_configs = self.emaneconfig_management.configurations
        for key, value in emane_configs.items():
            node_id, interface_id = key
            model, options = value
            config = {x: options[x].value for x in options}
            config_proto = core_pb2.EmaneModelConfig(
                node_id=node_id, interface_id=interface_id, model=model, config=config
            )
            configs.append(config_proto)
        return configs

    def run(self, node_id):
        logging.info("running node(%s) cmd: %s", node_id, self.observer)
        return self.client.node_command(self.session_id, node_id, self.observer).output
