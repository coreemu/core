"""
Incorporate grpc into python tkinter GUI
"""
import getpass
import json
import logging
import os
import tkinter as tk
from collections.abc import Iterable
from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING, Optional

import grpc

from core.api.grpc import client, configservices_pb2, core_pb2
from core.api.grpc.wrappers import (
    ConfigOption,
    ConfigService,
    ConfigServiceDefaults,
    EmaneModelConfig,
    Event,
    ExceptionEvent,
    Link,
    LinkEvent,
    LinkType,
    MessageType,
    Node,
    NodeEvent,
    NodeServiceData,
    NodeType,
    Position,
    Server,
    ServiceConfig,
    ServiceFileConfig,
    Session,
    SessionLocation,
    SessionState,
    ThroughputsEvent,
)
from core.gui import nodeutils as nutils
from core.gui.appconfig import XMLS_PATH, CoreServer, Observer
from core.gui.dialogs.emaneinstall import EmaneInstallDialog
from core.gui.dialogs.mobilityplayer import MobilityPlayer
from core.gui.dialogs.sessions import SessionsDialog
from core.gui.graph.edges import CanvasEdge
from core.gui.graph.node import CanvasNode
from core.gui.interface import InterfaceManager
from core.gui.nodeutils import NodeDraw

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.gui.app import Application

GUI_SOURCE = "gui"
CPU_USAGE_DELAY = 3


def to_dict(config: dict[str, ConfigOption]) -> dict[str, str]:
    return {x: y.value for x, y in config.items()}


class CoreClient:
    def __init__(self, app: "Application", proxy: bool) -> None:
        """
        Create a CoreGrpc instance
        """
        self.app: "Application" = app
        self.master: tk.Tk = app.master
        self._client: client.CoreGrpcClient = client.CoreGrpcClient(proxy=proxy)
        self.session: Optional[Session] = None
        self.user = getpass.getuser()

        # menu options
        self.show_throughputs: tk.BooleanVar = tk.BooleanVar(value=False)

        # global service settings
        self.services: dict[str, set[str]] = {}
        self.config_services_groups: dict[str, set[str]] = {}
        self.config_services: dict[str, ConfigService] = {}

        # loaded configuration data
        self.emane_models: list[str] = []
        self.servers: dict[str, CoreServer] = {}
        self.custom_nodes: dict[str, NodeDraw] = {}
        self.custom_observers: dict[str, Observer] = {}
        self.read_config()

        # helpers
        self.iface_to_edge: dict[tuple[int, ...], CanvasEdge] = {}
        self.ifaces_manager: InterfaceManager = InterfaceManager(self.app)
        self.observer: Optional[str] = None

        # session data
        self.mobility_players: dict[int, MobilityPlayer] = {}
        self.canvas_nodes: dict[int, CanvasNode] = {}
        self.links: dict[str, CanvasEdge] = {}
        self.handling_throughputs: Optional[grpc.Future] = None
        self.handling_cpu_usage: Optional[grpc.Future] = None
        self.handling_events: Optional[grpc.Future] = None

    @property
    def client(self) -> client.CoreGrpcClient:
        if self.session:
            if not self._client.check_session(self.session.id):
                throughputs_enabled = self.handling_throughputs is not None
                self.cancel_throughputs()
                self.cancel_events()
                self._client.create_session(self.session.id)
                self.handling_events = self._client.events(
                    self.session.id, self.handle_events
                )
                if throughputs_enabled:
                    self.enable_throughputs()
            self.setup_cpu_usage()
        return self._client

    def set_canvas_node(self, node: Node, canvas_node: CanvasNode) -> None:
        self.canvas_nodes[node.id] = canvas_node

    def get_canvas_node(self, node_id: int) -> CanvasNode:
        return self.canvas_nodes[node_id]

    def reset(self) -> None:
        # helpers
        self.ifaces_manager.reset()
        self.iface_to_edge.clear()
        # session data
        self.canvas_nodes.clear()
        self.links.clear()
        self.close_mobility_players()
        self.mobility_players.clear()
        # clear streams
        self.cancel_throughputs()
        self.cancel_events()

    def close_mobility_players(self) -> None:
        for mobility_player in self.mobility_players.values():
            mobility_player.close()

    def set_observer(self, value: Optional[str]) -> None:
        self.observer = value

    def read_config(self) -> None:
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

    def handle_events(self, event: Event) -> None:
        if not self.session or event.source == GUI_SOURCE:
            return
        if event.session_id != self.session.id:
            logger.warning(
                "ignoring event session(%s) current(%s)",
                event.session_id,
                self.session.id,
            )
            return
        if event.link_event:
            self.app.after(0, self.handle_link_event, event.link_event)
        elif event.session_event:
            logger.info("session event: %s", event)
            session_event = event.session_event
            if session_event.event <= SessionState.SHUTDOWN.value:
                self.session.state = SessionState(session_event.event)
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
                logger.warning("unknown session event: %s", session_event)
        elif event.node_event:
            self.app.after(0, self.handle_node_event, event.node_event)
        elif event.config_event:
            logger.info("config event: %s", event)
        elif event.exception_event:
            self.handle_exception_event(event.exception_event)
        else:
            logger.info("unhandled event: %s", event)

    def handle_link_event(self, event: LinkEvent) -> None:
        logger.debug("Link event: %s", event)
        node1_id = event.link.node1_id
        node2_id = event.link.node2_id
        if node1_id == node2_id:
            logger.warning("ignoring links with loops: %s", event)
            return
        canvas_node1 = self.canvas_nodes[node1_id]
        canvas_node2 = self.canvas_nodes[node2_id]
        if event.link.type == LinkType.WIRELESS:
            if event.message_type == MessageType.ADD:
                self.app.manager.add_wireless_edge(
                    canvas_node1, canvas_node2, event.link
                )
            elif event.message_type == MessageType.DELETE:
                self.app.manager.delete_wireless_edge(
                    canvas_node1, canvas_node2, event.link
                )
            elif event.message_type == MessageType.NONE:
                self.app.manager.update_wireless_edge(
                    canvas_node1, canvas_node2, event.link
                )
            else:
                logger.warning("unknown link event: %s", event)
        else:
            if event.message_type == MessageType.ADD:
                self.app.manager.add_wired_edge(canvas_node1, canvas_node2, event.link)
            elif event.message_type == MessageType.DELETE:
                self.app.manager.delete_wired_edge(event.link)
            elif event.message_type == MessageType.NONE:
                self.app.manager.update_wired_edge(event.link)
            else:
                logger.warning("unknown link event: %s", event)

    def handle_node_event(self, event: NodeEvent) -> None:
        logger.debug("node event: %s", event)
        node = event.node
        if event.message_type == MessageType.NONE:
            canvas_node = self.canvas_nodes[node.id]
            x = node.position.x
            y = node.position.y
            canvas_node.move(x, y)
            if node.icon and node.icon != canvas_node.core_node.icon:
                canvas_node.update_icon(node.icon)
        elif event.message_type == MessageType.DELETE:
            canvas_node = self.canvas_nodes[node.id]
            canvas_node.canvas_delete()
        elif event.message_type == MessageType.ADD:
            if node.id in self.session.nodes:
                logger.error("core node already exists: %s", node)
            self.app.manager.add_core_node(node)
        else:
            logger.warning("unknown node event: %s", event)

    def enable_throughputs(self) -> None:
        if not self.handling_throughputs:
            self.handling_throughputs = self.client.throughputs(
                self.session.id, self.handle_throughputs
            )

    def cancel_throughputs(self) -> None:
        if self.handling_throughputs:
            self.handling_throughputs.cancel()
            self.handling_throughputs = None
            self.app.manager.clear_throughputs()

    def cancel_events(self) -> None:
        if self.handling_events:
            self.handling_events.cancel()
            self.handling_events = None

    def cancel_cpu_usage(self) -> None:
        if self.handling_cpu_usage:
            self.handling_cpu_usage.cancel()
            self.handling_cpu_usage = None

    def setup_cpu_usage(self) -> None:
        if self.handling_cpu_usage and self.handling_cpu_usage.running():
            return
        if self.handling_cpu_usage:
            self.handling_cpu_usage.cancel()
        self.handling_cpu_usage = self._client.cpu_usage(
            CPU_USAGE_DELAY, self.handle_cpu_event
        )

    def handle_throughputs(self, event: ThroughputsEvent) -> None:
        if event.session_id != self.session.id:
            logger.warning(
                "ignoring throughput event session(%s) current(%s)",
                event.session_id,
                self.session.id,
            )
            return
        logger.debug("handling throughputs event: %s", event)
        self.app.after(0, self.app.manager.set_throughputs, event)

    def handle_cpu_event(self, event: core_pb2.CpuUsageEvent) -> None:
        self.app.after(0, self.app.statusbar.set_cpu, event.usage)

    def handle_exception_event(self, event: ExceptionEvent) -> None:
        logger.info("exception event: %s", event)
        self.app.statusbar.add_alert(event)

    def update_session_title(self) -> None:
        title_file = self.session.file.name if self.session.file else ""
        self.master.title(f"CORE Session({self.session.id}) {title_file}")

    def join_session(self, session_id: int) -> None:
        logger.info("joining session(%s)", session_id)
        self.reset()
        try:
            self.session = self.client.get_session(session_id)
            self.session.user = self.user
            self.update_session_title()
            self.handling_events = self.client.events(
                self.session.id, self.handle_events
            )
            self.ifaces_manager.joined(self.session.links)
            self.app.manager.join(self.session)
            if self.is_runtime():
                self.show_mobility_players()
            self.app.after(0, self.app.joined_session_update)
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Join Session Error", e)

    def is_runtime(self) -> bool:
        return self.session and self.session.state == SessionState.RUNTIME

    def create_new_session(self) -> None:
        """
        Create a new session
        """
        try:
            session = self.client.create_session()
            logger.info("created session: %s", session.id)
            self.join_session(session.id)
            location_config = self.app.guiconfig.location
            self.session.location = SessionLocation(
                x=location_config.x,
                y=location_config.y,
                z=location_config.z,
                lat=location_config.lat,
                lon=location_config.lon,
                alt=location_config.alt,
                scale=location_config.scale,
            )
        except grpc.RpcError as e:
            self.app.show_grpc_exception("New Session Error", e)

    def delete_session(self, session_id: int = None) -> None:
        if session_id is None and not self.session:
            return
        if session_id is None:
            session_id = self.session.id
        try:
            response = self.client.delete_session(session_id)
            logger.info("deleted session(%s), Result: %s", session_id, response)
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Delete Session Error", e)

    def setup(self, session_id: int = None) -> None:
        """
        Query sessions, if there exist any, prompt whether to join one
        """
        try:
            self.client.connect()
            # get current core configurations services/config services
            core_config = self.client.get_config()
            self.emane_models = sorted(core_config.emane_models)
            for service in core_config.services:
                group_services = self.services.setdefault(service.group, set())
                group_services.add(service.name)
            for service in core_config.config_services:
                self.config_services[service.name] = service
                group_services = self.config_services_groups.setdefault(
                    service.group, set()
                )
                group_services.add(service.name)
            # join provided session, create new session, or show dialog to select an
            # existing session
            sessions = self.client.get_sessions()
            if session_id:
                session_ids = {x.id for x in sessions}
                if session_id not in session_ids:
                    self.app.show_error(
                        "Join Session Error",
                        f"{session_id} does not exist",
                        blocking=True,
                    )
                    self.app.close()
                else:
                    self.join_session(session_id)
            else:
                if not sessions:
                    self.create_new_session()
                else:
                    dialog = SessionsDialog(self.app, True)
                    dialog.show()
        except grpc.RpcError as e:
            logger.exception("core setup error")
            self.app.show_grpc_exception("Setup Error", e, blocking=True)
            self.app.close()

    def edit_node(self, core_node: Node) -> None:
        try:
            self.client.move_node(
                self.session.id, core_node.id, core_node.position, source=GUI_SOURCE
            )
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Edit Node Error", e)

    def get_links(self, definition: bool = False) -> list[Link]:
        if not definition:
            self.ifaces_manager.set_macs([x.link for x in self.links.values()])
        links = []
        for edge in self.links.values():
            link = edge.link
            if not definition:
                node1 = self.session.nodes[link.node1_id]
                node2 = self.session.nodes[link.node2_id]
                if nutils.is_container(node1) and link.iface1 and not link.iface1.mac:
                    link.iface1.mac = self.ifaces_manager.next_mac()
                if nutils.is_container(node2) and link.iface2 and not link.iface2.mac:
                    link.iface2.mac = self.ifaces_manager.next_mac()
            links.append(link)
            if edge.asymmetric_link:
                links.append(edge.asymmetric_link)
        return links

    def start_session(self, definition: bool = False) -> tuple[bool, list[str]]:
        self.session.links = self.get_links(definition)
        self.session.metadata = self.get_metadata()
        self.session.servers.clear()
        for server in self.servers.values():
            self.session.servers.append(Server(name=server.name, host=server.address))
        result = False
        exceptions = []
        try:
            result, exceptions = self.client.start_session(self.session, definition)
            logger.info(
                "start session(%s) definition(%s), result: %s",
                self.session.id,
                definition,
                result,
            )
            if self.show_throughputs.get():
                self.enable_throughputs()
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Start Session Error", e)
        return result, exceptions

    def stop_session(self, session_id: int = None) -> bool:
        session_id = session_id or self.session.id
        self.cancel_throughputs()
        result = False
        try:
            result = self.client.stop_session(session_id)
            logger.info("stopped session(%s), result: %s", session_id, result)
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Stop Session Error", e)
        return result

    def show_mobility_players(self) -> None:
        for node in self.session.nodes.values():
            if not nutils.is_mobility(node):
                continue
            if node.mobility_config:
                mobility_player = MobilityPlayer(self.app, node)
                self.mobility_players[node.id] = mobility_player
                mobility_player.show()

    def get_metadata(self) -> dict[str, str]:
        # create canvas data
        canvas_config = self.app.manager.get_metadata()
        canvas_config = json.dumps(canvas_config)

        # create shapes data
        shapes = []
        for canvas in self.app.manager.all():
            for shape in canvas.shapes.values():
                shapes.append(shape.metadata())
        shapes = json.dumps(shapes)

        # create edges config
        edges_config = []
        for edge in self.links.values():
            if not edge.is_customized():
                continue
            edge_config = dict(token=edge.token, width=edge.width, color=edge.color)
            edges_config.append(edge_config)
        edges_config = json.dumps(edges_config)

        # create hidden metadata
        hidden = [x.core_node.id for x in self.canvas_nodes.values() if x.hidden]
        hidden = json.dumps(hidden)

        # save metadata
        return dict(
            canvas=canvas_config, shapes=shapes, edges=edges_config, hidden=hidden
        )

    def launch_terminal(self, node_id: int) -> None:
        try:
            terminal = self.app.guiconfig.preferences.terminal
            if not terminal:
                messagebox.showerror(
                    "Terminal Error",
                    "No terminal set, please set within the preferences menu",
                    parent=self.app,
                )
                return
            node_term = self.client.get_node_terminal(self.session.id, node_id)
            cmd = f"{terminal} {node_term} &"
            logger.info("launching terminal %s", cmd)
            os.system(cmd)
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Node Terminal Error", e)

    def get_xml_dir(self) -> str:
        return str(self.session.file.parent) if self.session.file else str(XMLS_PATH)

    def save_xml(self, file_path: Path = None) -> bool:
        """
        Save core session as to an xml file
        """
        if not file_path and not self.session.file:
            logger.error("trying to save xml for session with no file")
            return False
        if not file_path:
            file_path = self.session.file
        result = False
        try:
            if not self.is_runtime():
                logger.debug("sending session data to the daemon")
                result, exceptions = self.start_session(definition=True)
                if not result:
                    message = "\n".join(exceptions)
                    self.app.show_exception_data(
                        "Session Definition Exception",
                        "Failed to define session",
                        message,
                    )
            self.client.save_xml(self.session.id, str(file_path))
            if self.session.file != file_path:
                self.session.file = file_path
                self.update_session_title()
            logger.info("saved xml file %s", file_path)
            result = True
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Save XML Error", e)
        return result

    def open_xml(self, file_path: Path) -> None:
        """
        Open core xml
        """
        try:
            result, session_id = self._client.open_xml(file_path)
            logger.info(
                "open xml file %s, result(%s) session(%s)",
                file_path,
                result,
                session_id,
            )
            self.join_session(session_id)
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Open XML Error", e)

    def get_node_service(self, node_id: int, service_name: str) -> NodeServiceData:
        node_service = self.client.get_node_service(
            self.session.id, node_id, service_name
        )
        logger.debug(
            "get node(%s) service(%s): %s", node_id, service_name, node_service
        )
        return node_service

    def get_node_service_file(
        self, node_id: int, service_name: str, file_name: str
    ) -> str:
        data = self.client.get_node_service_file(
            self.session.id, node_id, service_name, file_name
        )
        logger.debug(
            "get service file for node(%s), service: %s, file: %s, data: %s",
            node_id,
            service_name,
            file_name,
            data,
        )
        return data

    def close(self) -> None:
        """
        Clean ups when done using grpc
        """
        logger.debug("close grpc")
        self.client.close()

    def next_node_id(self) -> int:
        """
        Get the next usable node id.
        """
        i = 1
        while True:
            if i not in self.session.nodes:
                break
            i += 1
        return i

    def create_node(
        self, x: float, y: float, node_type: NodeType, model: str
    ) -> Optional[Node]:
        """
        Add node, with information filled in, to grpc manager
        """
        node_id = self.next_node_id()
        position = Position(x=x, y=y)
        image = None
        if nutils.has_image(node_type):
            image = "ubuntu:latest"
        emane = None
        if node_type == NodeType.EMANE:
            if not self.emane_models:
                dialog = EmaneInstallDialog(self.app)
                dialog.show()
                return
            emane = self.emane_models[0]
            name = f"emane{node_id}"
        elif node_type == NodeType.WIRELESS_LAN:
            name = f"wlan{node_id}"
        elif node_type in [NodeType.RJ45, NodeType.TUNNEL]:
            name = "unassigned"
        else:
            name = f"n{node_id}"
        node = Node(
            id=node_id,
            type=node_type,
            name=name,
            model=model,
            position=position,
            image=image,
            emane=emane,
        )
        if nutils.is_custom(node):
            services = nutils.get_custom_services(self.app.guiconfig, model)
            node.config_services = set(services)
        # assign default services to CORE node
        else:
            services = self.session.default_services.get(model)
            if services:
                node.config_services = set(services)
        logger.info(
            "add node(%s) to session(%s), coordinates(%s, %s)",
            node.name,
            self.session.id,
            x,
            y,
        )
        self.session.nodes[node.id] = node
        return node

    def deleted_canvas_nodes(self, canvas_nodes: list[CanvasNode]) -> None:
        """
        remove the nodes selected by the user and anything related to that node
        such as link, configurations, interfaces
        """
        for canvas_node in canvas_nodes:
            node = canvas_node.core_node
            del self.canvas_nodes[node.id]
            del self.session.nodes[node.id]

    def deleted_canvas_edges(self, edges: Iterable[CanvasEdge]) -> None:
        links = []
        for edge in edges:
            del self.links[edge.token]
            links.append(edge.link)
        self.ifaces_manager.removed(links)

    def save_edge(self, edge: CanvasEdge) -> None:
        self.links[edge.token] = edge
        src_node = edge.src.core_node
        dst_node = edge.dst.core_node
        if edge.link.iface1:
            src_iface_id = edge.link.iface1.id
            self.iface_to_edge[(src_node.id, src_iface_id)] = edge
        if edge.link.iface2:
            dst_iface_id = edge.link.iface2.id
            self.iface_to_edge[(dst_node.id, dst_iface_id)] = edge

    def get_wlan_configs(self) -> list[tuple[int, dict[str, str]]]:
        configs = []
        for node in self.session.nodes.values():
            if node.type != NodeType.WIRELESS_LAN:
                continue
            if not node.wlan_config:
                continue
            config = ConfigOption.to_dict(node.wlan_config)
            configs.append((node.id, config))
        return configs

    def get_mobility_configs(self) -> list[tuple[int, dict[str, str]]]:
        configs = []
        for node in self.session.nodes.values():
            if not nutils.is_mobility(node):
                continue
            if not node.mobility_config:
                continue
            config = ConfigOption.to_dict(node.mobility_config)
            configs.append((node.id, config))
        return configs

    def get_emane_model_configs(self) -> list[EmaneModelConfig]:
        configs = []
        for node in self.session.nodes.values():
            for key, config in node.emane_model_configs.items():
                model, iface_id = key
                # config = ConfigOption.to_dict(config)
                if iface_id is None:
                    iface_id = -1
                config = EmaneModelConfig(
                    node_id=node.id, model=model, iface_id=iface_id, config=config
                )
                configs.append(config)
        return configs

    def get_service_configs(self) -> list[ServiceConfig]:
        configs = []
        for node in self.session.nodes.values():
            if not nutils.is_container(node):
                continue
            if not node.service_configs:
                continue
            for name, config in node.service_configs.items():
                config = ServiceConfig(
                    node_id=node.id,
                    service=name,
                    files=config.configs,
                    directories=config.dirs,
                    startup=config.startup,
                    validate=config.validate,
                    shutdown=config.shutdown,
                )
                configs.append(config)
        return configs

    def get_service_file_configs(self) -> list[ServiceFileConfig]:
        configs = []
        for node in self.session.nodes.values():
            if not nutils.is_container(node):
                continue
            if not node.service_file_configs:
                continue
            for service, file_configs in node.service_file_configs.items():
                for file, data in file_configs.items():
                    config = ServiceFileConfig(node.id, service, file, data)
                    configs.append(config)
        return configs

    def get_config_service_rendered(self, node_id: int, name: str) -> dict[str, str]:
        return self.client.get_config_service_rendered(self.session.id, node_id, name)

    def get_config_service_defaults(
        self, node_id: int, name: str
    ) -> ConfigServiceDefaults:
        return self.client.get_config_service_defaults(self.session.id, node_id, name)

    def get_config_service_configs_proto(
        self,
    ) -> list[configservices_pb2.ConfigServiceConfig]:
        config_service_protos = []
        for node in self.session.nodes.values():
            if not nutils.is_container(node):
                continue
            if not node.config_service_configs:
                continue
            for name, service_config in node.config_service_configs.items():
                config_proto = configservices_pb2.ConfigServiceConfig(
                    node_id=node.id,
                    name=name,
                    templates=service_config.templates,
                    config=service_config.config,
                )
                config_service_protos.append(config_proto)
        return config_service_protos

    def run(self, node_id: int) -> str:
        logger.info("running node(%s) cmd: %s", node_id, self.observer)
        _, output = self.client.node_command(self.session.id, node_id, self.observer)
        return output

    def get_wlan_config(self, node_id: int) -> dict[str, ConfigOption]:
        config = self.client.get_wlan_config(self.session.id, node_id)
        logger.debug(
            "get wlan configuration from node %s, result configuration: %s",
            node_id,
            config,
        )
        return config

    def get_wireless_config(self, node_id: int) -> dict[str, ConfigOption]:
        return self.client.get_wireless_config(self.session.id, node_id)

    def get_mobility_config(self, node_id: int) -> dict[str, ConfigOption]:
        config = self.client.get_mobility_config(self.session.id, node_id)
        logger.debug(
            "get mobility config from node %s, result configuration: %s",
            node_id,
            config,
        )
        return config

    def get_emane_model_config(
        self, node_id: int, model: str, iface_id: int = None
    ) -> dict[str, ConfigOption]:
        if iface_id is None:
            iface_id = -1
        config = self.client.get_emane_model_config(
            self.session.id, node_id, model, iface_id
        )
        logger.debug(
            "get emane model config: node id: %s, EMANE model: %s, "
            "interface: %s, config: %s",
            node_id,
            model,
            iface_id,
            config,
        )
        return config

    def execute_script(self, script: str, options: str) -> None:
        session_id = self.client.execute_script(script, options)
        logger.info("execute python script %s", session_id)
        if session_id != -1:
            self.join_session(session_id)

    def add_link(self, link: Link) -> None:
        result, _, _ = self.client.add_link(self.session.id, link, source=GUI_SOURCE)
        logger.debug("added link: %s", result)
        if not result:
            logger.error("error adding link: %s", link)

    def edit_link(self, link: Link) -> None:
        result = self.client.edit_link(self.session.id, link, source=GUI_SOURCE)
        if not result:
            logger.error("error editing link: %s", link)
