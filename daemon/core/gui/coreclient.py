"""
Incorporate grpc into python tkinter GUI
"""
import json
import logging
import os
from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional

import grpc

from core.api.grpc import client, common_pb2, configservices_pb2, core_pb2
from core.api.grpc.emane_pb2 import EmaneModelConfig
from core.api.grpc.mobility_pb2 import MobilityConfig
from core.api.grpc.services_pb2 import NodeServiceData, ServiceConfig, ServiceFileConfig
from core.api.grpc.wlan_pb2 import WlanConfig
from core.gui import appconfig
from core.gui.dialogs.emaneinstall import EmaneInstallDialog
from core.gui.dialogs.error import ErrorDialog
from core.gui.dialogs.mobilityplayer import MobilityPlayer
from core.gui.dialogs.sessions import SessionsDialog
from core.gui.graph.edges import CanvasEdge
from core.gui.graph.node import CanvasNode
from core.gui.graph.shape import AnnotationData, Shape
from core.gui.graph.shapeutils import ShapeType
from core.gui.interface import InterfaceManager
from core.gui.nodeutils import NodeDraw, NodeUtils

if TYPE_CHECKING:
    from core.gui.app import Application

GUI_SOURCE = "gui"


class CoreClient:
    def __init__(self, app: "Application", proxy: bool):
        """
        Create a CoreGrpc instance
        """
        self._client = client.CoreGrpcClient(proxy=proxy)
        self.session_id = None
        self.node_ids = []
        self.app = app
        self.master = app.master
        self.services = {}
        self.config_services_groups = {}
        self.config_services = {}
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
        self.emane_config = None
        self.mobility_players = {}
        self.handling_throughputs = None
        self.handling_events = None
        self.xml_dir = None
        self.xml_file = None

    @property
    def client(self):
        if self.session_id:
            response = self._client.check_session(self.session_id)
            if not response.result:
                throughputs_enabled = self.handling_throughputs is not None
                self.cancel_throughputs()
                self.cancel_events()
                self._client.create_session(self.session_id)
                self.handling_events = self._client.events(
                    self.session_id, self.handle_events
                )
                if throughputs_enabled:
                    self.enable_throughputs()
        return self._client

    def reset(self):
        # helpers
        self.interfaces_manager.reset()
        self.interface_to_edge.clear()
        # session data
        self.canvas_nodes.clear()
        self.links.clear()
        self.hooks.clear()
        self.emane_config = None
        self.close_mobility_players()
        self.mobility_players.clear()
        # clear streams
        self.cancel_throughputs()
        self.cancel_events()

    def close_mobility_players(self):
        for mobility_player in self.mobility_players.values():
            mobility_player.close()

    def set_observer(self, value: str):
        self.observer = value

    def read_config(self):
        # read distributed servers
        for server in self.app.guiconfig.servers:
            self.servers[server.name] = server

        # read custom nodes
        for custom_node in self.app.guiconfig.nodes:
            node_draw = NodeDraw.from_custom(custom_node)
            self.custom_nodes[custom_node.name] = node_draw

        # read observers
        for observer in self.app.guiconfig.observers:
            self.custom_observers[observer.name] = observer

    def handle_events(self, event: core_pb2.Event):
        if event.session_id != self.session_id:
            logging.warning(
                "ignoring event session(%s) current(%s)",
                event.session_id,
                self.session_id,
            )
            return

        if event.HasField("link_event"):
            self.app.after(0, self.handle_link_event, event.link_event)
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
            self.app.after(0, self.handle_node_event, event.node_event)
        elif event.HasField("config_event"):
            logging.info("config event: %s", event)
        elif event.HasField("exception_event"):
            self.handle_exception_event(event)
        else:
            logging.info("unhandled event: %s", event)

    def handle_link_event(self, event: core_pb2.LinkEvent):
        logging.debug("Link event: %s", event)
        node1_id = event.link.node1_id
        node2_id = event.link.node2_id
        if node1_id == node2_id:
            logging.warning("ignoring links with loops: %s", event)
            return
        canvas_node1 = self.canvas_nodes[node1_id]
        canvas_node2 = self.canvas_nodes[node2_id]
        if event.message_type == core_pb2.MessageType.ADD:
            self.app.canvas.add_wireless_edge(canvas_node1, canvas_node2, event.link)
        elif event.message_type == core_pb2.MessageType.DELETE:
            self.app.canvas.delete_wireless_edge(canvas_node1, canvas_node2, event.link)
        elif event.message_type == core_pb2.MessageType.NONE:
            self.app.canvas.update_wireless_edge(canvas_node1, canvas_node2, event.link)
        else:
            logging.warning("unknown link event: %s", event)

    def handle_node_event(self, event: core_pb2.NodeEvent):
        logging.debug("node event: %s", event)
        if event.source == GUI_SOURCE:
            return
        node_id = event.node.id
        x = event.node.position.x
        y = event.node.position.y
        canvas_node = self.canvas_nodes[node_id]
        canvas_node.move(x, y)

    def enable_throughputs(self):
        self.handling_throughputs = self.client.throughputs(
            self.session_id, self.handle_throughputs
        )

    def cancel_throughputs(self):
        if self.handling_throughputs:
            self.handling_throughputs.cancel()
            self.handling_throughputs = None

    def cancel_events(self):
        if self.handling_events:
            self.handling_events.cancel()
            self.handling_events = None

    def handle_throughputs(self, event: core_pb2.ThroughputsEvent):
        if event.session_id != self.session_id:
            logging.warning(
                "ignoring throughput event session(%s) current(%s)",
                event.session_id,
                self.session_id,
            )
            return
        logging.debug("handling throughputs event: %s", event)
        self.app.after(0, self.app.canvas.set_throughputs, event)

    def handle_exception_event(self, event: core_pb2.ExceptionEvent):
        logging.info("exception event: %s", event)
        self.app.statusbar.core_alarms.append(event)

    def join_session(self, session_id: int, query_location: bool = True):
        logging.info("join session(%s)", session_id)
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
            self.handling_events = self.client.events(
                self.session_id, self.handle_events
            )

            # get session service defaults
            response = self.client.get_service_defaults(self.session_id)
            self.default_services = {
                x.node_type: set(x.services) for x in response.defaults
            }

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

            # get emane config
            response = self.client.get_emane_config(self.session_id)
            self.emane_config = response.config

            # update interface manager
            self.interfaces_manager.joined(session.links)

            # draw session
            self.app.canvas.reset_and_redraw(session)

            # get mobility configs
            response = self.client.get_mobility_configs(self.session_id)
            for node_id in response.configs:
                config = response.configs[node_id].config
                canvas_node = self.canvas_nodes[node_id]
                canvas_node.mobility_config = dict(config)

            # get emane model config
            response = self.client.get_emane_model_configs(self.session_id)
            for config in response.configs:
                interface = None
                if config.interface != -1:
                    interface = config.interface
                canvas_node = self.canvas_nodes[config.node_id]
                canvas_node.emane_model_configs[(config.model, interface)] = dict(
                    config.config
                )

            # get wlan configurations
            response = self.client.get_wlan_configs(self.session_id)
            for _id in response.configs:
                mapped_config = response.configs[_id]
                canvas_node = self.canvas_nodes[_id]
                canvas_node.wlan_config = dict(mapped_config.config)

            # get service configurations
            response = self.client.get_node_service_configs(self.session_id)
            for config in response.configs:
                canvas_node = self.canvas_nodes[config.node_id]
                canvas_node.service_configs[config.service] = config.data
                logging.debug("service file configs: %s", config.files)
                for file_name in config.files:
                    data = config.files[file_name]
                    files = canvas_node.service_file_configs.setdefault(
                        config.service, {}
                    )
                    files[file_name] = data

            # get config service configurations
            response = self.client.get_node_config_service_configs(self.session_id)
            for config in response.configs:
                canvas_node = self.canvas_nodes[config.node_id]
                service_config = canvas_node.config_service_configs.setdefault(
                    config.name, {}
                )
                if config.templates:
                    service_config["templates"] = config.templates
                if config.config:
                    service_config["config"] = config.config

            # get metadata
            response = self.client.get_session_metadata(self.session_id)
            self.parse_metadata(response.config)
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Join Session Error", e)

        # organize canvas
        self.app.canvas.organize()

        # update ui to represent current state
        self.app.after(0, self.app.joined_session_update)

    def is_runtime(self) -> bool:
        return self.state == core_pb2.SessionState.RUNTIME

    def parse_metadata(self, config: Dict[str, str]):
        # canvas setting
        canvas_config = config.get("canvas")
        logging.debug("canvas metadata: %s", canvas_config)
        if canvas_config:
            canvas_config = json.loads(canvas_config)
            gridlines = canvas_config.get("gridlines", True)
            self.app.canvas.show_grid.set(gridlines)
            fit_image = canvas_config.get("fit_image", False)
            self.app.canvas.adjust_to_dim.set(fit_image)
            wallpaper_style = canvas_config.get("wallpaper-style", 1)
            self.app.canvas.scale_option.set(wallpaper_style)
            width = self.app.guiconfig.preferences.width
            height = self.app.guiconfig.preferences.height
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

    def create_new_session(self):
        """
        Create a new session
        """
        try:
            response = self.client.create_session()
            logging.info("created session: %s", response)
            location_config = self.app.guiconfig.location
            self.location = core_pb2.SessionLocation(
                x=location_config.x,
                y=location_config.y,
                z=location_config.z,
                lat=location_config.lat,
                lon=location_config.lon,
                alt=location_config.alt,
                scale=location_config.scale,
            )
            self.join_session(response.session_id, query_location=False)
        except grpc.RpcError as e:
            self.app.show_grpc_exception("New Session Error", e)

    def delete_session(self, session_id: int = None):
        if session_id is None:
            session_id = self.session_id
        try:
            response = self.client.delete_session(session_id)
            logging.info("deleted session(%s), Result: %s", session_id, response)
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Delete Session Error", e)

    def setup(self):
        """
        Query sessions, if there exist any, prompt whether to join one
        """
        try:
            self.client.connect()
            # get service information
            response = self.client.get_services()
            for service in response.services:
                group_services = self.services.setdefault(service.group, set())
                group_services.add(service.name)

            # get config service informations
            response = self.client.get_config_services()
            for service in response.services:
                self.config_services[service.name] = service
                group_services = self.config_services_groups.setdefault(
                    service.group, set()
                )
                group_services.add(service.name)

            # if there are no sessions, create a new session, else join a session
            response = self.client.get_sessions()
            sessions = response.sessions
            if len(sessions) == 0:
                self.create_new_session()
            else:
                dialog = SessionsDialog(self.app, True)
                dialog.show()
        except grpc.RpcError as e:
            logging.exception("core setup error")
            dialog = ErrorDialog(self.app, "Setup Error", e.details())
            dialog.show()
            self.app.close()

    def edit_node(self, core_node: core_pb2.Node):
        try:
            self.client.edit_node(
                self.session_id, core_node.id, core_node.position, source=GUI_SOURCE
            )
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Edit Node Error", e)

    def start_session(self) -> core_pb2.StartSessionResponse:
        self.interfaces_manager.reset_mac()
        nodes = [x.core_node for x in self.canvas_nodes.values()]
        links = []
        for edge in self.links.values():
            link = core_pb2.Link()
            link.CopyFrom(edge.link)
            if link.HasField("interface1") and not link.interface1.mac:
                link.interface1.mac = self.interfaces_manager.next_mac()
            if link.HasField("interface2") and not link.interface2.mac:
                link.interface2.mac = self.interfaces_manager.next_mac()
            links.append(link)
        wlan_configs = self.get_wlan_configs_proto()
        mobility_configs = self.get_mobility_configs_proto()
        emane_model_configs = self.get_emane_model_configs_proto()
        hooks = list(self.hooks.values())
        service_configs = self.get_service_configs_proto()
        file_configs = self.get_service_file_configs_proto()
        asymmetric_links = [
            x.asymmetric_link for x in self.links.values() if x.asymmetric_link
        ]
        config_service_configs = self.get_config_service_configs_proto()
        if self.emane_config:
            emane_config = {x: self.emane_config[x].value for x in self.emane_config}
        else:
            emane_config = None
        response = core_pb2.StartSessionResponse(result=False)
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
                asymmetric_links,
                config_service_configs,
            )
            logging.info(
                "start session(%s), result: %s", self.session_id, response.result
            )
            if response.result:
                self.set_metadata()
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Start Session Error", e)
        return response

    def stop_session(self, session_id: int = None) -> core_pb2.StartSessionResponse:
        if not session_id:
            session_id = self.session_id
        response = core_pb2.StopSessionResponse(result=False)
        try:
            response = self.client.stop_session(session_id)
            logging.info("stopped session(%s), result: %s", session_id, response)
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Stop Session Error", e)
        return response

    def show_mobility_players(self):
        for canvas_node in self.canvas_nodes.values():
            if canvas_node.core_node.type != core_pb2.NodeType.WIRELESS_LAN:
                continue
            if canvas_node.mobility_config:
                mobility_player = MobilityPlayer(
                    self.app, canvas_node, canvas_node.mobility_config
                )
                node_id = canvas_node.core_node.id
                self.mobility_players[node_id] = mobility_player
                mobility_player.show()

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
        logging.info("set session metadata %s, result: %s", metadata, response)

    def launch_terminal(self, node_id: int):
        try:
            terminal = self.app.guiconfig.preferences.terminal
            if not terminal:
                messagebox.showerror(
                    "Terminal Error",
                    "No terminal set, please set within the preferences menu",
                    parent=self.app,
                )
                return
            response = self.client.get_node_terminal(self.session_id, node_id)
            cmd = f"{terminal} {response.terminal} &"
            logging.info("launching terminal %s", cmd)
            os.system(cmd)
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Node Terminal Error", e)

    def save_xml(self, file_path: str):
        """
        Save core session as to an xml file
        """
        try:
            if self.state != core_pb2.SessionState.RUNTIME:
                logging.debug("Send session data to the daemon")
                self.send_data()
            response = self.client.save_xml(self.session_id, file_path)
            logging.info("saved xml file %s, result: %s", file_path, response)
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Save XML Error", e)

    def open_xml(self, file_path: str):
        """
        Open core xml
        """
        try:
            response = self._client.open_xml(file_path)
            logging.info("open xml file %s, response: %s", file_path, response)
            self.join_session(response.session_id)
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Open XML Error", e)

    def get_node_service(self, node_id: int, service_name: str) -> NodeServiceData:
        response = self.client.get_node_service(self.session_id, node_id, service_name)
        logging.debug(
            "get node(%s) %s service, response: %s", node_id, service_name, response
        )
        return response.service

    def set_node_service(
        self,
        node_id: int,
        service_name: str,
        dirs: List[str],
        files: List[str],
        startups: List[str],
        validations: List[str],
        shutdowns: List[str],
    ) -> NodeServiceData:
        response = self.client.set_node_service(
            self.session_id,
            node_id,
            service_name,
            directories=dirs,
            files=files,
            startup=startups,
            validate=validations,
            shutdown=shutdowns,
        )
        logging.info(
            "Set %s service for node(%s), files: %s, Startup: %s, Validation: %s, Shutdown: %s, Result: %s",
            service_name,
            node_id,
            files,
            startups,
            validations,
            shutdowns,
            response,
        )
        response = self.client.get_node_service(self.session_id, node_id, service_name)
        return response.service

    def get_node_service_file(
        self, node_id: int, service_name: str, file_name: str
    ) -> str:
        response = self.client.get_node_service_file(
            self.session_id, node_id, service_name, file_name
        )
        logging.debug(
            "get service file for node(%s), service: %s, file: %s, result: %s",
            node_id,
            service_name,
            file_name,
            response,
        )
        return response.data

    def set_node_service_file(
        self, node_id: int, service_name: str, file_name: str, data: str
    ):
        response = self.client.set_node_service_file(
            self.session_id, node_id, service_name, file_name, data
        )
        logging.info(
            "set node(%s) service file, service: %s, file: %s, data: %s, result: %s",
            node_id,
            service_name,
            file_name,
            data,
            response,
        )

    def create_nodes_and_links(self):
        """
        create nodes and links that have not been created yet
        """
        node_protos = [x.core_node for x in self.canvas_nodes.values()]
        link_protos = [x.link for x in self.links.values()]
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
                link_proto.node1_id,
                link_proto.node2_id,
                link_proto.interface1,
                link_proto.interface2,
                link_proto.options,
            )
            logging.debug("create link: %s", response)

    def send_data(self):
        """
        send to daemon all session info, but don't start the session
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
                startup=config_proto.startup,
                validate=config_proto.validate,
                shutdown=config_proto.shutdown,
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

        self.set_metadata()

    def close(self):
        """
        Clean ups when done using grpc
        """
        logging.debug("close grpc")
        self.client.close()

    def next_node_id(self) -> int:
        """
        Get the next usable node id.
        """
        i = 1
        while True:
            if i not in self.canvas_nodes:
                break
            i += 1
        return i

    def create_node(
        self, x: float, y: float, node_type: core_pb2.NodeType, model: str
    ) -> Optional[core_pb2.Node]:
        """
        Add node, with information filled in, to grpc manager
        """
        node_id = self.next_node_id()
        position = core_pb2.Position(x=x, y=y)
        image = None
        if NodeUtils.is_image_node(node_type):
            image = "ubuntu:latest"
        emane = None
        if node_type == core_pb2.NodeType.EMANE:
            if not self.emane_models:
                dialog = EmaneInstallDialog(self.app)
                dialog.show()
                return
            emane = self.emane_models[0]
            name = f"EMANE{node_id}"
        elif node_type == core_pb2.NodeType.WIRELESS_LAN:
            name = f"WLAN{node_id}"
        elif node_type in [core_pb2.NodeType.RJ45, core_pb2.NodeType.TUNNEL]:
            name = "UNASSIGNED"
        else:
            name = f"n{node_id}"
        node = core_pb2.Node(
            id=node_id,
            type=node_type,
            name=name,
            model=model,
            position=position,
            image=image,
            emane=emane,
        )
        if NodeUtils.is_custom(node_type, model):
            services = NodeUtils.get_custom_node_services(self.app.guiconfig, model)
            node.services[:] = services
        # assign default services to CORE node
        else:
            services = self.default_services.get(model)
            if services:
                node.services[:] = services
        logging.info(
            "add node(%s) to session(%s), coordinates(%s, %s)",
            node.name,
            self.session_id,
            x,
            y,
        )
        return node

    def deleted_graph_nodes(self, canvas_nodes: List[core_pb2.Node]):
        """
        remove the nodes selected by the user and anything related to that node
        such as link, configurations, interfaces
        """
        for canvas_node in canvas_nodes:
            node_id = canvas_node.core_node.id
            del self.canvas_nodes[node_id]

    def deleted_graph_edges(self, edges: Iterable[CanvasEdge]) -> None:
        links = []
        for edge in edges:
            del self.links[edge.token]
            links.append(edge.link)
        self.interfaces_manager.removed(links)

    def create_interface(self, canvas_node: CanvasNode) -> core_pb2.Interface:
        node = canvas_node.core_node
        ip4, ip6 = self.interfaces_manager.get_ips(node)
        ip4_mask = self.interfaces_manager.ip4_mask
        ip6_mask = self.interfaces_manager.ip6_mask
        interface_id = canvas_node.next_interface_id()
        name = f"eth{interface_id}"
        interface = core_pb2.Interface(
            id=interface_id,
            name=name,
            ip4=ip4,
            ip4mask=ip4_mask,
            ip6=ip6,
            ip6mask=ip6_mask,
        )
        logging.info(
            "create node(%s) interface(%s) IPv4(%s) IPv6(%s)",
            node.name,
            interface.name,
            interface.ip4,
            interface.ip6,
        )
        return interface

    def create_link(
        self, edge: CanvasEdge, canvas_src_node: CanvasNode, canvas_dst_node: CanvasNode
    ):
        """
        Create core link for a pair of canvas nodes, with token referencing
        the canvas edge.
        """
        src_node = canvas_src_node.core_node
        dst_node = canvas_dst_node.core_node

        # determine subnet
        self.interfaces_manager.determine_subnets(canvas_src_node, canvas_dst_node)

        src_interface = None
        if NodeUtils.is_container_node(src_node.type):
            src_interface = self.create_interface(canvas_src_node)
            self.interface_to_edge[(src_node.id, src_interface.id)] = edge.token

        dst_interface = None
        if NodeUtils.is_container_node(dst_node.type):
            dst_interface = self.create_interface(canvas_dst_node)
            self.interface_to_edge[(dst_node.id, dst_interface.id)] = edge.token

        link = core_pb2.Link(
            type=core_pb2.LinkType.WIRED,
            node1_id=src_node.id,
            node2_id=dst_node.id,
            interface1=src_interface,
            interface2=dst_interface,
        )
        # assign after creating link proto, since interfaces are copied
        if src_interface:
            interface1 = link.interface1
            edge.src_interface = interface1
            canvas_src_node.interfaces[interface1.id] = interface1
        if dst_interface:
            interface2 = link.interface2
            edge.dst_interface = interface2
            canvas_dst_node.interfaces[interface2.id] = interface2
        edge.set_link(link)
        self.links[edge.token] = edge
        logging.info("Add link between %s and %s", src_node.name, dst_node.name)

    def get_wlan_configs_proto(self) -> List[WlanConfig]:
        configs = []
        for canvas_node in self.canvas_nodes.values():
            if canvas_node.core_node.type != core_pb2.NodeType.WIRELESS_LAN:
                continue
            if not canvas_node.wlan_config:
                continue
            config = canvas_node.wlan_config
            config = {x: config[x].value for x in config}
            node_id = canvas_node.core_node.id
            wlan_config = WlanConfig(node_id=node_id, config=config)
            configs.append(wlan_config)
        return configs

    def get_mobility_configs_proto(self) -> List[MobilityConfig]:
        configs = []
        for canvas_node in self.canvas_nodes.values():
            if canvas_node.core_node.type != core_pb2.NodeType.WIRELESS_LAN:
                continue
            if not canvas_node.mobility_config:
                continue
            config = canvas_node.mobility_config
            config = {x: config[x].value for x in config}
            node_id = canvas_node.core_node.id
            mobility_config = MobilityConfig(node_id=node_id, config=config)
            configs.append(mobility_config)
        return configs

    def get_emane_model_configs_proto(self) -> List[EmaneModelConfig]:
        configs = []
        for canvas_node in self.canvas_nodes.values():
            if canvas_node.core_node.type != core_pb2.NodeType.EMANE:
                continue
            node_id = canvas_node.core_node.id
            for key, config in canvas_node.emane_model_configs.items():
                model, interface = key
                config = {x: config[x].value for x in config}
                if interface is None:
                    interface = -1
                config_proto = EmaneModelConfig(
                    node_id=node_id, interface_id=interface, model=model, config=config
                )
                configs.append(config_proto)
        return configs

    def get_service_configs_proto(self) -> List[ServiceConfig]:
        configs = []
        for canvas_node in self.canvas_nodes.values():
            if not NodeUtils.is_container_node(canvas_node.core_node.type):
                continue
            if not canvas_node.service_configs:
                continue
            node_id = canvas_node.core_node.id
            for name, config in canvas_node.service_configs.items():
                config_proto = ServiceConfig(
                    node_id=node_id,
                    service=name,
                    directories=config.dirs,
                    files=config.configs,
                    startup=config.startup,
                    validate=config.validate,
                    shutdown=config.shutdown,
                )
                configs.append(config_proto)
        return configs

    def get_service_file_configs_proto(self) -> List[ServiceFileConfig]:
        configs = []
        for canvas_node in self.canvas_nodes.values():
            if not NodeUtils.is_container_node(canvas_node.core_node.type):
                continue
            if not canvas_node.service_file_configs:
                continue
            node_id = canvas_node.core_node.id
            for service, file_configs in canvas_node.service_file_configs.items():
                for file, data in file_configs.items():
                    config_proto = ServiceFileConfig(
                        node_id=node_id, service=service, file=file, data=data
                    )
                    configs.append(config_proto)
        return configs

    def get_config_service_configs_proto(
        self
    ) -> List[configservices_pb2.ConfigServiceConfig]:
        config_service_protos = []
        for canvas_node in self.canvas_nodes.values():
            if not NodeUtils.is_container_node(canvas_node.core_node.type):
                continue
            if not canvas_node.config_service_configs:
                continue
            node_id = canvas_node.core_node.id
            for name, service_config in canvas_node.config_service_configs.items():
                config = service_config.get("config", {})
                config_proto = configservices_pb2.ConfigServiceConfig(
                    node_id=node_id,
                    name=name,
                    templates=service_config["templates"],
                    config=config,
                )
                config_service_protos.append(config_proto)
        return config_service_protos

    def run(self, node_id: int) -> str:
        logging.info("running node(%s) cmd: %s", node_id, self.observer)
        return self.client.node_command(self.session_id, node_id, self.observer).output

    def get_wlan_config(self, node_id: int) -> Dict[str, common_pb2.ConfigOption]:
        response = self.client.get_wlan_config(self.session_id, node_id)
        config = response.config
        logging.debug(
            "get wlan configuration from node %s, result configuration: %s",
            node_id,
            config,
        )
        return dict(config)

    def get_mobility_config(self, node_id: int) -> Dict[str, common_pb2.ConfigOption]:
        response = self.client.get_mobility_config(self.session_id, node_id)
        config = response.config
        logging.debug(
            "get mobility config from node %s, result configuration: %s",
            node_id,
            config,
        )
        return dict(config)

    def get_emane_model_config(
        self, node_id: int, model: str, interface: int = None
    ) -> Dict[str, common_pb2.ConfigOption]:
        if interface is None:
            interface = -1
        response = self.client.get_emane_model_config(
            self.session_id, node_id, model, interface
        )
        config = response.config
        logging.debug(
            "get emane model config: node id: %s, EMANE model: %s, interface: %s, config: %s",
            node_id,
            model,
            interface,
            config,
        )
        return dict(config)

    def execute_script(self, script):
        response = self.client.execute_script(script)
        logging.info("execute python script %s", response)
        if response.session_id != -1:
            self.join_session(response.session_id)
