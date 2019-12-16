"""
Incorporate grpc into python tkinter GUI
"""
import json
import logging
import os
import time
from pathlib import Path

import grpc

from core.api.grpc import client, core_pb2
from coretk import appconfig
from coretk.dialogs.mobilityplayer import MobilityPlayer
from coretk.dialogs.sessions import SessionsDialog
from coretk.errors import show_grpc_error
from coretk.graph import tags
from coretk.graph.shape import AnnotationData, Shape
from coretk.graph.shapeutils import ShapeType
from coretk.interface import InterfaceManager
from coretk.nodeutils import NodeDraw, NodeUtils

OBSERVERS = {
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


class CoreServer:
    def __init__(self, name, address, port):
        self.name = name
        self.address = address
        self.port = port


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
        self.services = {}
        self.default_services = {}
        self.emane_models = []
        self.observer = None

        # loaded configuration data
        self.servers = {}
        self.custom_nodes = {}
        self.custom_observers = {}
        self.read_config()

        # helpers
        self.interface_to_edge = {}
        self.interfaces_manager = InterfaceManager(self.app)

        # session data
        self.state = None
        self.canvas_nodes = {}
        self.location = None
        self.links = {}
        self.hooks = {}
        self.wlan_configs = {}
        self.mobility_configs = {}
        self.emane_model_configs = {}
        self.emane_config = None
        self.service_configs = {}
        self.file_configs = {}
        self.mobility_players = {}
        self.throughput = False

    def reset(self):
        # helpers
        self.interfaces_manager.reset()
        self.interface_to_edge.clear()
        # session data
        self.canvas_nodes.clear()
        self.links.clear()
        self.hooks.clear()
        self.wlan_configs.clear()
        self.mobility_configs.clear()
        self.emane_model_configs.clear()
        self.emane_config = None
        self.service_configs.clear()
        self.file_configs.clear()
        self.mobility_players.clear()

    def set_observer(self, value):
        self.observer = value

    def read_config(self):
        # read distributed server
        for config in self.app.guiconfig.get("servers", []):
            server = CoreServer(config["name"], config["address"], config["port"])
            self.servers[server.name] = server

        # read custom nodes
        for config in self.app.guiconfig.get("nodes", []):
            name = config["name"]
            image_file = config["image"]
            services = set(config["services"])
            node_draw = NodeDraw.from_custom(name, image_file, services)
            self.custom_nodes[name] = node_draw

        # read observers
        for config in self.app.guiconfig.get("observers", []):
            observer = Observer(config["name"], config["cmd"])
            self.custom_observers[observer.name] = observer

    def handle_events(self, event):
        if event.HasField("link_event"):
            logging.info("link event: %s", event)
            self.handle_link_event(event.link_event)
        elif event.HasField("session_event"):
            logging.info("session event: %s", event)
            session_event = event.session_event
            if session_event.event <= core_pb2.SessionState.SHUTDOWN:
                self.state = event.session_event.event
            elif session_event.event in {7, 8, 9}:
                node_id = session_event.node_id
                dialog = self.mobility_players.get(node_id)
                if dialog:
                    if session_event.event == 7:
                        dialog.set_play()
                    elif session_event.event == 8:
                        dialog.set_stop()
                    else:
                        dialog.set_pause()
            else:
                logging.warning("unknown session event: %s", session_event)
        elif event.HasField("node_event"):
            self.handle_node_event(event.node_event)
        elif event.HasField("config_event"):
            logging.info("config event: %s", event)
        elif event.HasField("exception_event"):
            self.handle_exception_event(event.exception_event)
        else:
            logging.info("unhandled event: %s", event)

    def handle_link_event(self, event):
        node_one_id = event.link.node_one_id
        node_two_id = event.link.node_two_id
        canvas_node_one = self.canvas_nodes[node_one_id]
        canvas_node_two = self.canvas_nodes[node_two_id]

        if event.message_type == core_pb2.MessageType.ADD:
            self.app.canvas.add_wireless_edge(canvas_node_one, canvas_node_two)
        elif event.message_type == core_pb2.MessageType.DELETE:
            self.app.canvas.delete_wireless_edge(canvas_node_one, canvas_node_two)
        else:
            logging.warning("unknown link event: %s", event.message_type)

    def handle_node_event(self, event):
        if event.source == "gui":
            return
        node_id = event.node.id
        x = event.node.position.x
        y = event.node.position.y
        canvas_node = self.canvas_nodes[node_id]
        canvas_node.move(x, y)

    def handle_throughputs(self, event):
        if self.throughput:
            self.app.canvas.throughput_draw.process_grpc_throughput_event(
                event.interface_throughputs
            )

    def handle_exception_event(self, event):
        logging.info("exception event: %s", event)
        self.app.statusbar.core_alarms.append(event)

    def join_session(self, session_id, query_location=True):
        # update session and title
        self.session_id = session_id
        self.master.title(f"CORE Session({self.session_id})")

        # clear session data
        self.reset()

        # get session data
        try:
            response = self.client.get_session(self.session_id)
            session = response.session
            self.state = session.state
            self.client.events(self.session_id, self.handle_events)
            self.client.throughputs(self.handle_throughputs)

            # get location
            if query_location:
                response = self.client.get_session_location(self.session_id)
                self.location = response.location

            # get emane models
            response = self.client.get_emane_models(self.session_id)
            self.emane_models = response.models

            # get hooks
            response = self.client.get_hooks(self.session_id)
            for hook in response.hooks:
                self.hooks[hook.file] = hook

            # get mobility configs
            response = self.client.get_mobility_configs(self.session_id)
            for node_id in response.configs:
                node_config = response.configs[node_id].config
                self.mobility_configs[node_id] = node_config

            # get emane config
            response = self.client.get_emane_config(self.session_id)
            self.emane_config = response.config

            # get emane model config
            response = self.client.get_emane_model_configs(self.session_id)
            for config in response.configs:
                interface = None
                if config.interface != -1:
                    interface = config.interface
                self.set_emane_model_config(
                    config.node_id, config.model, config.config, interface
                )

            # get wlan configurations
            response = self.client.get_wlan_configs(self.session_id)
            for _id in response.configs:
                mapped_config = response.configs[_id]
                self.wlan_configs[_id] = mapped_config.config

            # get service configurations
            response = self.client.get_node_service_configs(self.session_id)
            for config in response.configs:
                service_configs = self.service_configs.setdefault(config.node_id, {})
                service_configs[config.service] = config.data
                logging.info("service file configs: %s", config.files)
                for file_name in config.files:
                    file_configs = self.file_configs.setdefault(config.node_id, {})
                    files = file_configs.setdefault(config.service, {})
                    data = config.files[file_name]
                    files[file_name] = data

            # draw session
            self.app.canvas.reset_and_redraw(session)

            # get metadata
            response = self.client.get_session_metadata(self.session_id)
            self.parse_metadata(response.config)
        except grpc.RpcError as e:
            show_grpc_error(e)

        # update ui to represent current state
        if self.is_runtime():
            self.app.toolbar.runtime_frame.tkraise()
            self.app.toolbar.click_runtime_selection()
        else:
            self.app.toolbar.design_frame.tkraise()
            self.app.toolbar.click_selection()
        self.app.statusbar.progress_bar.stop()

    def is_runtime(self):
        return self.state == core_pb2.SessionState.RUNTIME

    def parse_metadata(self, config):
        # canvas setting
        canvas_config = config.get("canvas")
        logging.info("canvas metadata: %s", canvas_config)
        if canvas_config:
            canvas_config = json.loads(canvas_config)

            gridlines = canvas_config.get("gridlines", True)
            self.app.canvas.show_grid.set(gridlines)

            fit_image = canvas_config.get("fit_image", False)
            self.app.canvas.adjust_to_dim.set(fit_image)

            wallpaper_style = canvas_config.get("wallpaper-style", 1)
            self.app.canvas.scale_option.set(wallpaper_style)

            width = self.app.guiconfig["preferences"]["width"]
            height = self.app.guiconfig["preferences"]["height"]
            dimensions = canvas_config.get("dimensions", [width, height])
            self.app.canvas.redraw_canvas(dimensions)

            wallpaper = canvas_config.get("wallpaper")
            if wallpaper:
                wallpaper = str(appconfig.BACKGROUNDS_PATH.joinpath(wallpaper))
            self.app.canvas.set_wallpaper(wallpaper)
        else:
            self.app.canvas.redraw_canvas()
            self.app.canvas.set_wallpaper(None)

        # load saved shapes
        shapes_config = config.get("shapes")
        if shapes_config:
            shapes_config = json.loads(shapes_config)
            for shape_config in shapes_config:
                logging.info("loading shape: %s", shape_config)
                shape_type = shape_config["type"]
                try:
                    shape_type = ShapeType(shape_type)
                    coords = shape_config["iconcoords"]
                    data = AnnotationData(
                        shape_config["label"],
                        shape_config["fontfamily"],
                        shape_config["fontsize"],
                        shape_config["labelcolor"],
                        shape_config["color"],
                        shape_config["border"],
                        shape_config["width"],
                        shape_config["bold"],
                        shape_config["italic"],
                        shape_config["underline"],
                    )
                    shape = Shape(
                        self.app, self.app.canvas, shape_type, *coords, data=data
                    )
                    self.app.canvas.shapes[shape.id] = shape
                except ValueError:
                    logging.exception("unknown shape: %s", shape_type)

        for tag in tags.ABOVE_WALLPAPER_TAGS:
            self.app.canvas.tag_raise(tag)

    def create_new_session(self):
        """
        Create a new session

        :return: nothing
        """
        try:
            response = self.client.create_session()
            logging.info("created session: %s", response)
            location_config = self.app.guiconfig["location"]
            self.location = core_pb2.SessionLocation(
                x=location_config["x"],
                y=location_config["y"],
                z=location_config["z"],
                lat=location_config["lat"],
                lon=location_config["lon"],
                alt=location_config["alt"],
                scale=location_config["scale"],
            )
            self.join_session(response.session_id, query_location=False)
        except grpc.RpcError as e:
            show_grpc_error(e)

    def delete_session(self, session_id=None):
        if session_id is None:
            session_id = self.session_id
        try:
            response = self.client.delete_session(session_id)
            logging.info("deleted session result: %s", response)
        except grpc.RpcError as e:
            show_grpc_error(e)

    def set_up(self):
        """
        Query sessions, if there exist any, prompt whether to join one

        :return: existing sessions
        """
        try:
            self.client.connect()

            # get service information
            response = self.client.get_services()
            for service in response.services:
                group_services = self.services.setdefault(service.group, set())
                group_services.add(service.name)

            # if there are no sessions, create a new session, else join a session
            response = self.client.get_sessions()
            logging.info("current sessions: %s", response)
            sessions = response.sessions
            if len(sessions) == 0:
                self.create_new_session()
            else:
                dialog = SessionsDialog(self.app, self.app)
                dialog.show()

            response = self.client.get_service_defaults(self.session_id)
            self.default_services = {
                x.node_type: set(x.services) for x in response.defaults
            }
        except grpc.RpcError as e:
            show_grpc_error(e)
            self.app.close()

    def edit_node(self, core_node):
        try:
            self.client.edit_node(
                self.session_id, core_node.id, core_node.position, source="gui"
            )
        except grpc.RpcError as e:
            show_grpc_error(e)

    def start_session(self):
        nodes = [x.core_node for x in self.canvas_nodes.values()]
        links = list(self.links.values())
        wlan_configs = self.get_wlan_configs_proto()
        mobility_configs = self.get_mobility_configs_proto()
        emane_model_configs = self.get_emane_model_configs_proto()
        hooks = list(self.hooks.values())
        service_configs = self.get_service_configs_proto()
        file_configs = self.get_service_file_configs_proto()
        if self.emane_config:
            emane_config = {x: self.emane_config[x].value for x in self.emane_config}
        else:
            emane_config = None

        start = time.perf_counter()
        try:
            response = self.client.start_session(
                self.session_id,
                nodes,
                links,
                self.location,
                hooks,
                emane_config,
                emane_model_configs,
                wlan_configs,
                mobility_configs,
                service_configs,
                file_configs,
            )
            self.set_metadata()
            process_time = time.perf_counter() - start
            logging.debug(
                "start session(%s), result: %s", self.session_id, response.result
            )
            self.app.statusbar.start_session_callback(process_time)

            # display mobility players
            for node_id, config in self.mobility_configs.items():
                canvas_node = self.canvas_nodes[node_id]
                mobility_player = MobilityPlayer(
                    self.app, self.app, canvas_node, config
                )
                mobility_player.show()
                self.mobility_players[node_id] = mobility_player
        except grpc.RpcError as e:
            show_grpc_error(e)

    def stop_session(self, session_id=None):
        if not session_id:
            session_id = self.session_id
        start = time.perf_counter()
        try:
            response = self.client.stop_session(session_id)
            logging.debug(
                "stopped session(%s), result: %s", session_id, response.result
            )
            process_time = time.perf_counter() - start
            self.app.statusbar.stop_session_callback(process_time)
        except grpc.RpcError as e:
            show_grpc_error(e)

    def set_metadata(self):
        # create canvas data
        wallpaper = None
        if self.app.canvas.wallpaper_file:
            wallpaper = Path(self.app.canvas.wallpaper_file).name
        canvas_config = {
            "wallpaper": wallpaper,
            "wallpaper-style": self.app.canvas.scale_option.get(),
            "gridlines": self.app.canvas.show_grid.get(),
            "fit_image": self.app.canvas.adjust_to_dim.get(),
            "dimensions": self.app.canvas.current_dimensions,
        }
        canvas_config = json.dumps(canvas_config)

        # create shapes data
        shapes = []
        for shape in self.app.canvas.shapes.values():
            shapes.append(shape.metadata())
        shapes = json.dumps(shapes)

        metadata = {"canvas": canvas_config, "shapes": shapes}
        response = self.client.set_session_metadata(self.session_id, metadata)
        logging.info("set session metadata: %s", response)

    def launch_terminal(self, node_id):
        try:
            response = self.client.get_node_terminal(self.session_id, node_id)
            logging.info("get terminal %s", response.terminal)
            os.system(f"xterm -e {response.terminal} &")
        except grpc.RpcError as e:
            show_grpc_error(e)

    def save_xml(self, file_path):
        """
        Save core session as to an xml file

        :param str file_path: file path that user pick
        :return: nothing
        """
        try:
            if self.state != core_pb2.SessionState.RUNTIME:
                logging.debug(
                    "session state not runtime, send session data to the daemon..."
                )
                self.send_data()
            response = self.client.save_xml(self.session_id, file_path)
            logging.info("saved xml(%s): %s", file_path, response)
        except grpc.RpcError as e:
            show_grpc_error(e)

    def open_xml(self, file_path):
        """
        Open core xml

        :param str file_path: file to open
        :return: session id
        """
        try:
            response = self.client.open_xml(file_path)
            logging.debug("open xml: %s", response)
            self.join_session(response.session_id)
        except grpc.RpcError as e:
            show_grpc_error(e)

    def get_node_service(self, node_id, service_name):
        response = self.client.get_node_service(self.session_id, node_id, service_name)
        logging.debug("get node service %s", response)
        return response.service

    def set_node_service(self, node_id, service_name, startups, validations, shutdowns):
        response = self.client.set_node_service(
            self.session_id, node_id, service_name, startups, validations, shutdowns
        )
        logging.debug("set node service %s", response)
        response = self.client.get_node_service(self.session_id, node_id, service_name)
        logging.debug("get node service : %s", response)
        return response.service

    def get_node_service_file(self, node_id, service_name, file_name):
        response = self.client.get_node_service_file(
            self.session_id, node_id, service_name, file_name
        )
        logging.debug("get service file %s", response)
        return response.data

    def set_node_service_file(self, node_id, service_name, file_name, data):
        response = self.client.set_node_service_file(
            self.session_id, node_id, service_name, file_name, data
        )
        logging.debug("set node service file %s", response)

    def create_nodes_and_links(self):
        """
        create nodes and links that have not been created yet

        :return: nothing
        """
        node_protos = [x.core_node for x in self.canvas_nodes.values()]
        link_protos = list(self.links.values())
        if self.state != core_pb2.SessionState.DEFINITION:
            self.client.set_session_state(
                self.session_id, core_pb2.SessionState.DEFINITION
            )

        self.client.set_session_state(self.session_id, core_pb2.SessionState.DEFINITION)
        for node_proto in node_protos:
            response = self.client.add_node(self.session_id, node_proto)
            logging.debug("create node: %s", response)
        for link_proto in link_protos:
            response = self.client.add_link(
                self.session_id,
                link_proto.node_one_id,
                link_proto.node_two_id,
                link_proto.interface_one,
                link_proto.interface_two,
                link_proto.options,
            )
            logging.debug("create link: %s", response)

    def send_data(self):
        """
        send to daemon all session info, but don't start the session

        :return: nothing
        """
        self.create_nodes_and_links()
        for config_proto in self.get_wlan_configs_proto():
            self.client.set_wlan_config(
                self.session_id, config_proto.node_id, config_proto.config
            )
        for config_proto in self.get_mobility_configs_proto():
            self.client.set_mobility_config(
                self.session_id, config_proto.node_id, config_proto.config
            )
        for config_proto in self.get_service_configs_proto():
            self.client.set_node_service(
                self.session_id,
                config_proto.node_id,
                config_proto.service,
                config_proto.startup,
                config_proto.validate,
                config_proto.shutdown,
            )
        for config_proto in self.get_service_file_configs_proto():
            self.client.set_node_service_file(
                self.session_id,
                config_proto.node_id,
                config_proto.service,
                config_proto.file,
                config_proto.data,
            )
        for hook in self.hooks.values():
            self.client.add_hook(self.session_id, hook.state, hook.file, hook.data)
        for config_proto in self.get_emane_model_configs_proto():
            self.client.set_emane_model_config(
                self.session_id,
                config_proto.node_id,
                config_proto.model,
                config_proto.config,
                config_proto.interface_id,
            )
        if self.emane_config:
            config = {x: self.emane_config[x].value for x in self.emane_config}
            self.client.set_emane_config(self.session_id, config)

    def close(self):
        """
        Clean ups when done using grpc

        :return: nothing
        """
        logging.debug("close grpc")
        self.client.close()

    def next_node_id(self):
        """
        Get the next usable node id.

        :return: the next id to be used
        :rtype: int
        """
        i = 1
        while True:
            if i not in self.canvas_nodes:
                break
            i += 1
        return i

    def create_node(self, x, y, node_type, model):
        """
        Add node, with information filled in, to grpc manager

        :param int x: x coord
        :param int y: y coord
        :param core_pb2.NodeType node_type: node type
        :param str model: node model
        :return: nothing
        """
        node_id = self.next_node_id()
        position = core_pb2.Position(x=x, y=y)
        image = None
        if NodeUtils.is_image_node(node_type):
            image = "ubuntu:latest"
        emane = None
        if node_type == core_pb2.NodeType.EMANE:
            emane = self.emane_models[0]
        node = core_pb2.Node(
            id=node_id,
            type=node_type,
            name=f"n{node_id}",
            model=model,
            position=position,
            image=image,
            emane=emane,
        )
        logging.debug(
            "adding node to core session: %s, coords: (%s, %s), name: %s",
            self.session_id,
            x,
            y,
            node.name,
        )
        return node

    def delete_graph_nodes(self, canvas_nodes):
        """
        remove the nodes selected by the user and anything related to that node
        such as link, configurations, interfaces

        :param list canvas_nodes: list of nodes to delete
        :return: nothing
        """
        edges = set()
        for canvas_node in canvas_nodes:
            node_id = canvas_node.core_node.id
            if node_id not in self.canvas_nodes:
                logging.error("unknown node: %s", node_id)
                continue
            del self.canvas_nodes[node_id]
            if node_id in self.mobility_configs:
                del self.mobility_configs[node_id]
            if node_id in self.wlan_configs:
                del self.wlan_configs[node_id]
            for key in list(self.emane_model_configs):
                node_id, _, _ = key
                if node_id == node_id:
                    del self.emane_model_configs[key]

            for edge in canvas_node.edges:
                if edge in edges:
                    continue
                edges.add(edge)
                if edge.token not in self.links:
                    logging.error("unknown edge: %s", edge.token)
                del self.links[edge.token]

    def create_interface(self, canvas_node):
        node = canvas_node.core_node
        ip4, ip6, prefix = self.interfaces_manager.get_ips(node.id)
        interface_id = len(canvas_node.interfaces)
        name = f"eth{interface_id}"
        interface = core_pb2.Interface(
            id=interface_id, name=name, ip4=ip4, ip4mask=prefix, ip6=ip6, ip6mask=prefix
        )
        canvas_node.interfaces.append(interface)
        logging.debug(
            "create node(%s) interface IPv4: %s, name: %s",
            node.name,
            interface.ip4,
            interface.name,
        )
        return interface

    def create_link(self, edge, canvas_src_node, canvas_dst_node):
        """
        Create core link for a pair of canvas nodes, with token referencing
        the canvas edge.

        :param edge: edge for link
        :param canvas_src_node: canvas node one
        :param canvas_dst_node: canvas node two

        :return: nothing
        """
        src_node = canvas_src_node.core_node
        dst_node = canvas_dst_node.core_node

        # determine subnet
        self.interfaces_manager.determine_subnet(canvas_src_node, canvas_dst_node)

        src_interface = None
        if NodeUtils.is_container_node(src_node.type):
            src_interface = self.create_interface(canvas_src_node)
            edge.src_interface = src_interface
            self.interface_to_edge[(src_node.id, src_interface.id)] = edge.token

        dst_interface = None
        if NodeUtils.is_container_node(dst_node.type):
            dst_interface = self.create_interface(canvas_dst_node)
            edge.dst_interface = dst_interface
            self.interface_to_edge[(dst_node.id, dst_interface.id)] = edge.token

        link = core_pb2.Link(
            type=core_pb2.LinkType.WIRED,
            node_one_id=src_node.id,
            node_two_id=dst_node.id,
            interface_one=src_interface,
            interface_two=dst_interface,
        )
        self.links[edge.token] = link
        return link

    def get_wlan_configs_proto(self):
        configs = []
        for node_id, config in self.wlan_configs.items():
            config = {x: config[x].value for x in config}
            wlan_config = core_pb2.WlanConfig(node_id=node_id, config=config)
            configs.append(wlan_config)
        return configs

    def get_mobility_configs_proto(self):
        configs = []
        for node_id, config in self.mobility_configs.items():
            config = {x: config[x].value for x in config}
            mobility_config = core_pb2.MobilityConfig(node_id=node_id, config=config)
            configs.append(mobility_config)
        return configs

    def get_emane_model_configs_proto(self):
        configs = []
        for key, config in self.emane_model_configs.items():
            node_id, model, interface = key
            config = {x: config[x].value for x in config}
            if interface is None:
                interface = -1
            config_proto = core_pb2.EmaneModelConfig(
                node_id=node_id, interface_id=interface, model=model, config=config
            )
            configs.append(config_proto)
        return configs

    def get_service_configs_proto(self):
        configs = []
        for node_id, services in self.service_configs.items():
            for name, config in services.items():
                config_proto = core_pb2.ServiceConfig(
                    node_id=node_id,
                    service=name,
                    startup=config.startup,
                    validate=config.validate,
                    shutdown=config.shutdown,
                )
                configs.append(config_proto)
        return configs

    def get_service_file_configs_proto(self):
        configs = []
        for (node_id, file_configs) in self.file_configs.items():
            for service, file_config in file_configs.items():
                for file, data in file_config.items():
                    config_proto = core_pb2.ServiceFileConfig(
                        node_id=node_id, service=service, file=file, data=data
                    )
                    configs.append(config_proto)
        return configs

    def run(self, node_id):
        logging.info("running node(%s) cmd: %s", node_id, self.observer)
        return self.client.node_command(self.session_id, node_id, self.observer).output

    def get_wlan_config(self, node_id):
        config = self.wlan_configs.get(node_id)
        if not config:
            response = self.client.get_wlan_config(self.session_id, node_id)
            config = response.config
        return config

    def get_mobility_config(self, node_id):
        config = self.mobility_configs.get(node_id)
        if not config:
            response = self.client.get_mobility_config(self.session_id, node_id)
            config = response.config
        return config

    def get_emane_model_config(self, node_id, model, interface=None):
        logging.info("getting emane model config: %s %s %s", node_id, model, interface)
        config = self.emane_model_configs.get((node_id, model, interface))
        if not config:
            if interface is None:
                interface = -1
            response = self.client.get_emane_model_config(
                self.session_id, node_id, model, interface
            )
            config = response.config
        return config

    def set_emane_model_config(self, node_id, model, config, interface=None):
        logging.info("setting emane model config: %s %s %s", node_id, model, interface)
        self.emane_model_configs[(node_id, model, interface)] = config
