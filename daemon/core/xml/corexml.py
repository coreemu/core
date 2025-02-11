import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from lxml import etree

from core import utils
from core.config import Configuration
from core.emane.nodes import EmaneNet, EmaneOptions
from core.emulator.data import InterfaceData, LinkOptions
from core.emulator.enumerations import EventTypes, NodeTypes
from core.errors import CoreXmlError
from core.nodes.base import (
    CoreNetworkBase,
    CoreNodeBase,
    CoreNodeOptions,
    NodeBase,
    Position,
)
from core.nodes.docker import DockerNode, DockerOptions
from core.nodes.interface import CoreInterface
from core.nodes.network import GreTapBridge, WlanNode
from core.nodes.physical import Rj45Node
from core.nodes.podman import PodmanNode, PodmanOptions
from core.nodes.wireless import WirelessNode

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emane.emanemodel import EmaneModel
    from core.emulator.session import Session

    EmaneModelType = type[EmaneModel]
T = TypeVar("T")


def write_xml_file(
    xml_element: etree.Element, file_path: Path, doctype: str = None
) -> None:
    xml_data = etree.tostring(
        xml_element,
        xml_declaration=True,
        pretty_print=True,
        encoding="UTF-8",
        doctype=doctype,
    )
    with file_path.open("wb") as f:
        f.write(xml_data)


def get_type(element: etree.Element, name: str, _type: Generic[T]) -> T | None:
    value = element.get(name)
    if value is not None:
        value = _type(value)
    return value


def get_float(element: etree.Element, name: str) -> float | None:
    return get_type(element, name, float)


def get_int(element: etree.Element, name: str) -> int | None:
    return get_type(element, name, int)


def add_attribute(element: etree.Element, name: str, value: Any) -> None:
    if value is not None:
        element.set(name, str(value))


def create_iface_data(iface_element: etree.Element) -> InterfaceData:
    iface_id = int(iface_element.get("id"))
    name = iface_element.get("name")
    mac = iface_element.get("mac")
    ip4 = iface_element.get("ip4")
    ip4_mask = get_int(iface_element, "ip4_mask")
    ip6 = iface_element.get("ip6")
    ip6_mask = get_int(iface_element, "ip6_mask")
    return InterfaceData(
        id=iface_id,
        name=name,
        mac=mac,
        ip4=ip4,
        ip4_mask=ip4_mask,
        ip6=ip6,
        ip6_mask=ip6_mask,
    )


def create_emane_model_config(
    node_id: int,
    model: "EmaneModelType",
    config: dict[str, str],
    iface_id: int | None,
) -> etree.Element:
    emane_element = etree.Element("emane_configuration")
    add_attribute(emane_element, "node", node_id)
    add_attribute(emane_element, "iface", iface_id)
    add_attribute(emane_element, "model", model.name)
    platform_element = etree.SubElement(emane_element, "platform")
    for platform_config in model.platform_config:
        value = config[platform_config.id]
        add_configuration(platform_element, platform_config.id, value)
    mac_element = etree.SubElement(emane_element, "mac")
    for mac_config in model.mac_config:
        value = config[mac_config.id]
        add_configuration(mac_element, mac_config.id, value)
    phy_element = etree.SubElement(emane_element, "phy")
    for phy_config in model.phy_config:
        value = config[phy_config.id]
        add_configuration(phy_element, phy_config.id, value)
    external_element = etree.SubElement(emane_element, "external")
    for external_config in model.external_config:
        value = config[external_config.id]
        add_configuration(external_element, external_config.id, value)
    return emane_element


def add_configuration(parent: etree.Element, name: str, value: str) -> None:
    config_element = etree.SubElement(parent, "configuration")
    add_attribute(config_element, "name", name)
    add_attribute(config_element, "value", value)


class NodeElement:
    def __init__(self, session: "Session", node: NodeBase, element_name: str) -> None:
        self.session: "Session" = session
        self.node: NodeBase = node
        self.element: etree.Element = etree.Element(element_name)
        add_attribute(self.element, "id", node.id)
        add_attribute(self.element, "name", node.name)
        server = self.node.server.name if self.node.server else None
        add_attribute(self.element, "server", server)
        add_attribute(self.element, "icon", node.icon)
        add_attribute(self.element, "canvas", node.canvas)
        self.add_position()

    def add_position(self) -> None:
        x = self.node.position.x
        y = self.node.position.y
        z = self.node.position.z
        lat, lon, alt = None, None, None
        if x is not None and y is not None:
            lat, lon, alt = self.session.location.getgeo(x, y, z)
        position = etree.SubElement(self.element, "position")
        add_attribute(position, "x", x)
        add_attribute(position, "y", y)
        add_attribute(position, "z", z)
        add_attribute(position, "lat", lat)
        add_attribute(position, "lon", lon)
        add_attribute(position, "alt", alt)


class DeviceElement(NodeElement):
    def __init__(self, session: "Session", node: CoreNodeBase) -> None:
        super().__init__(session, node, "device")
        self.node: CoreNodeBase = node
        add_attribute(self.element, "type", node.model)
        self.add_class()
        self.add_services()

    def add_class(self) -> None:
        clazz = ""
        image = ""
        compose = ""
        compose_name = ""
        if isinstance(self.node, (DockerNode, PodmanNode)):
            clazz = "docker" if isinstance(self.node, DockerNode) else "podman"
            image = self.node.image
            compose = self.node.compose
            compose_name = self.node.compose_name
        add_attribute(self.element, "class", clazz)
        add_attribute(self.element, "image", image)
        add_attribute(self.element, "compose", compose)
        add_attribute(self.element, "compose_name", compose_name)

    def add_services(self) -> None:
        service_elements = etree.Element("services")
        for name, service in self.node.services.items():
            etree.SubElement(service_elements, "service", name=name)
        if service_elements.getchildren():
            self.element.append(service_elements)


class NetworkElement(NodeElement):
    def __init__(self, session: "Session", node: NodeBase) -> None:
        super().__init__(session, node, "network")
        if isinstance(self.node, WlanNode):
            if self.node.wireless_model:
                add_attribute(self.element, "model", self.node.wireless_model.name)
            if self.node.mobility:
                add_attribute(self.element, "mobility", self.node.mobility.name)
        if isinstance(self.node, EmaneNet):
            if self.node.wireless_model:
                add_attribute(self.element, "model", self.node.wireless_model.name)
            if self.node.mobility:
                add_attribute(self.element, "mobility", self.node.mobility.name)
        if isinstance(self.node, GreTapBridge):
            add_attribute(self.element, "grekey", self.node.grekey)
        if isinstance(self.node, WirelessNode):
            config = self.node.get_config()
            self.add_wireless_config(config)
        self.add_type()

    def add_type(self) -> None:
        node_type = self.session.get_node_type(type(self.node))
        add_attribute(self.element, "type", node_type.name)

    def add_wireless_config(self, config: dict[str, Configuration]) -> None:
        wireless_element = etree.SubElement(self.element, "wireless")
        for config_item in config.values():
            add_configuration(wireless_element, config_item.id, config_item.default)


class CoreXmlWriter:
    def __init__(self, session: "Session") -> None:
        self.session: "Session" = session
        self.scenario: etree.Element = etree.Element("scenario")
        self.networks: etree.SubElement = etree.SubElement(self.scenario, "networks")
        self.devices: etree.SubElement = etree.SubElement(self.scenario, "devices")
        self.write_session()

    def write_session(self) -> None:
        # generate xml content
        self.write_nodes()
        self.write_links()
        self.write_mobility_configs()
        self.write_emane_configs()
        self.write_service_configs()
        self.write_session_origin()
        self.write_servers()
        self.write_session_hooks()
        self.write_session_options()
        self.write_session_metadata()
        self.write_default_services()

    def get_data(self) -> bytes:
        xml_tree = etree.ElementTree(self.scenario)
        return etree.tostring(
            xml_tree, xml_declaration=True, pretty_print=True, encoding="UTF-8"
        )

    def write(self, path: Path) -> None:
        data = self.get_data()
        path.write_bytes(data)

    def write_session_origin(self) -> None:
        # origin: geolocation of cartesian coordinate 0,0,0
        lat, lon, alt = self.session.location.refgeo
        origin = etree.Element("session_origin")
        add_attribute(origin, "lat", lat)
        add_attribute(origin, "lon", lon)
        add_attribute(origin, "alt", alt)
        has_origin = len(origin.items()) > 0
        if has_origin:
            self.scenario.append(origin)
            refscale = self.session.location.refscale
            if refscale != 1.0:
                add_attribute(origin, "scale", refscale)
            if self.session.location.refxyz != (0.0, 0.0, 0.0):
                x, y, z = self.session.location.refxyz
                add_attribute(origin, "x", x)
                add_attribute(origin, "y", y)
                add_attribute(origin, "z", z)

    def write_servers(self) -> None:
        servers = etree.Element("servers")
        for server in self.session.distributed.servers.values():
            server_element = etree.SubElement(servers, "server")
            add_attribute(server_element, "name", server.name)
            add_attribute(server_element, "address", server.host)
        if servers.getchildren():
            self.scenario.append(servers)

    def write_session_hooks(self) -> None:
        # hook scripts
        hooks = etree.Element("session_hooks")
        for state in sorted(
            self.session.hook_manager.script_hooks, key=lambda x: x.value
        ):
            state_hooks = self.session.hook_manager.script_hooks[state]
            for file_name, data in sorted(state_hooks.items()):
                hook = etree.SubElement(hooks, "hook")
                add_attribute(hook, "name", file_name)
                add_attribute(hook, "state", state.value)
                hook.text = data
        if hooks.getchildren():
            self.scenario.append(hooks)

    def write_session_options(self) -> None:
        option_elements = etree.Element("session_options")
        for option in self.session.options.options:
            value = self.session.options.get(option.id)
            add_configuration(option_elements, option.id, value)
        if option_elements.getchildren():
            self.scenario.append(option_elements)

    def write_session_metadata(self) -> None:
        # metadata
        metadata_elements = etree.Element("session_metadata")
        config = self.session.metadata
        if not config:
            return
        for key in config:
            value = config[key]
            add_configuration(metadata_elements, key, value)
        if metadata_elements.getchildren():
            self.scenario.append(metadata_elements)

    def write_emane_configs(self) -> None:
        emane_configurations = etree.Element("emane_configurations")
        for node_id, model_configs in self.session.emane.node_configs.items():
            node_id, iface_id = utils.parse_iface_config_id(node_id)
            for model_name, config in model_configs.items():
                logger.debug(
                    "writing emane config node(%s) model(%s)", node_id, model_name
                )
                model_class = self.session.emane.get_model(model_name)
                emane_configuration = create_emane_model_config(
                    node_id, model_class, config, iface_id
                )
                emane_configurations.append(emane_configuration)
        if emane_configurations.getchildren():
            self.scenario.append(emane_configurations)

    def write_mobility_configs(self) -> None:
        mobility_configurations = etree.Element("mobility_configurations")
        for node_id in self.session.mobility.nodes():
            all_configs = self.session.mobility.get_all_configs(node_id)
            if not all_configs:
                continue
            for model_name in all_configs:
                config = all_configs[model_name]
                logger.debug(
                    "writing mobility config node(%s) model(%s)", node_id, model_name
                )
                mobility_configuration = etree.SubElement(
                    mobility_configurations, "mobility_configuration"
                )
                add_attribute(mobility_configuration, "node", node_id)
                add_attribute(mobility_configuration, "model", model_name)
                for name in config:
                    value = config[name]
                    add_configuration(mobility_configuration, name, value)
        if mobility_configurations.getchildren():
            self.scenario.append(mobility_configurations)

    def write_service_configs(self) -> None:
        service_configurations = etree.Element("service_configurations")
        for node in self.session.nodes.values():
            if not isinstance(node, CoreNodeBase):
                continue
            for name, service in node.services.items():
                service_element = etree.Element("service", name=name)
                add_attribute(service_element, "node", node.id)
                if service.custom_config:
                    configs_element = etree.SubElement(service_element, "configs")
                    for key, value in service.custom_config.items():
                        etree.SubElement(
                            configs_element, "config", key=key, value=value
                        )
                if service.custom_templates:
                    templates_element = etree.SubElement(service_element, "templates")
                    for template_name, template in service.custom_templates.items():
                        template_element = etree.SubElement(
                            templates_element, "template", name=template_name
                        )
                        template_element.text = etree.CDATA(template)
                if service.custom_config or service.custom_templates:
                    service_configurations.append(service_element)
        if service_configurations.getchildren():
            self.scenario.append(service_configurations)

    def write_default_services(self) -> None:
        models = etree.Element("default_services")
        for model, services in []:
            model = etree.SubElement(models, "node", type=model)
            for service in services:
                etree.SubElement(model, "service", name=service)
        if models.getchildren():
            self.scenario.append(models)

    def write_nodes(self) -> None:
        for node in self.session.nodes.values():
            # network node
            is_network_or_rj45 = isinstance(node, (CoreNetworkBase, Rj45Node))
            if is_network_or_rj45:
                self.write_network(node)
            # device node
            elif isinstance(node, CoreNodeBase):
                self.write_device(node)

    def write_network(self, node: NodeBase) -> None:
        network = NetworkElement(self.session, node)
        self.networks.append(network.element)

    def write_links(self) -> None:
        link_elements = etree.Element("links")
        for core_link in self.session.link_manager.links():
            node1, iface1 = core_link.node1, core_link.iface1
            node2, iface2 = core_link.node2, core_link.iface2
            unidirectional = core_link.is_unidirectional()
            link_element = self.create_link_element(
                node1, iface1, node2, iface2, core_link.options(), unidirectional
            )
            link_elements.append(link_element)
            if unidirectional:
                link_element = self.create_link_element(
                    node2, iface2, node1, iface1, iface2.options, unidirectional
                )
                link_elements.append(link_element)
        if link_elements.getchildren():
            self.scenario.append(link_elements)

    def write_device(self, node: CoreNodeBase) -> None:
        device = DeviceElement(self.session, node)
        self.devices.append(device.element)

    def create_iface_element(
        self, element_name: str, iface: CoreInterface
    ) -> etree.Element:
        iface_element = etree.Element(element_name)
        # check if interface is connected to emane
        if isinstance(iface.node, CoreNodeBase) and isinstance(iface.net, EmaneNet):
            nem_id = self.session.emane.get_nem_id(iface)
            add_attribute(iface_element, "nem", nem_id)
        ip4 = iface.get_ip4()
        ip4_mask = None
        if ip4:
            ip4_mask = ip4.prefixlen
            ip4 = str(ip4.ip)
        ip6 = iface.get_ip6()
        ip6_mask = None
        if ip6:
            ip6_mask = ip6.prefixlen
            ip6 = str(ip6.ip)
        add_attribute(iface_element, "id", iface.id)
        add_attribute(iface_element, "name", iface.name)
        add_attribute(iface_element, "mac", iface.mac)
        add_attribute(iface_element, "ip4", ip4)
        add_attribute(iface_element, "ip4_mask", ip4_mask)
        add_attribute(iface_element, "ip6", ip6)
        add_attribute(iface_element, "ip6_mask", ip6_mask)
        return iface_element

    def create_link_element(
        self,
        node1: NodeBase,
        iface1: CoreInterface | None,
        node2: NodeBase,
        iface2: CoreInterface | None,
        options: LinkOptions,
        unidirectional: bool,
    ) -> etree.Element:
        link_element = etree.Element("link")
        add_attribute(link_element, "node1", node1.id)
        add_attribute(link_element, "node2", node2.id)
        # check for interface one
        if iface1 is not None:
            iface1 = self.create_iface_element("iface1", iface1)
            link_element.append(iface1)
        # check for interface two
        if iface2 is not None:
            iface2 = self.create_iface_element("iface2", iface2)
            link_element.append(iface2)
        # check for options, don't write for emane/wlan links
        is_node1_wireless = isinstance(node1, (WlanNode, EmaneNet, WirelessNode))
        is_node2_wireless = isinstance(node2, (WlanNode, EmaneNet, WirelessNode))
        if not (is_node1_wireless or is_node2_wireless):
            unidirectional = 1 if unidirectional else 0
            options_element = etree.Element("options")
            add_attribute(options_element, "delay", options.delay)
            add_attribute(options_element, "bandwidth", options.bandwidth)
            add_attribute(options_element, "loss", options.loss)
            add_attribute(options_element, "dup", options.dup)
            add_attribute(options_element, "jitter", options.jitter)
            add_attribute(options_element, "mer", options.mer)
            add_attribute(options_element, "burst", options.burst)
            add_attribute(options_element, "mburst", options.mburst)
            add_attribute(options_element, "unidirectional", unidirectional)
            add_attribute(options_element, "key", options.key)
            add_attribute(options_element, "buffer", options.buffer)
            if options_element.items():
                link_element.append(options_element)
        return link_element


class CoreXmlReader:
    def __init__(self, session: "Session") -> None:
        self.session: "Session" = session
        self.scenario: etree.ElementTree | None = None

    def read(self, file_path: Path) -> None:
        xml_tree = etree.parse(str(file_path))
        self.scenario = xml_tree.getroot()
        # read xml session content
        self.read_default_services()
        self.read_session_metadata()
        self.read_session_options()
        self.read_session_hooks()
        self.read_servers()
        self.read_session_origin()
        self.read_mobility_configs()
        self.read_nodes()
        self.read_links()
        self.read_emane_configs()
        self.read_service_configs()

    def read_default_services(self) -> None:
        default_services = self.scenario.find("default_services")
        if default_services is None:
            return
        for node in default_services.iterchildren():
            model = node.get("type")
            services = []
            for service in node.iterchildren():
                services.append(service.get("name"))
            logger.info("reading default services for nodes(%s): %s", model, services)

    def read_session_metadata(self) -> None:
        session_metadata = self.scenario.find("session_metadata")
        if session_metadata is None:
            return
        configs = {}
        for data in session_metadata.iterchildren():
            name = data.get("name")
            value = data.get("value")
            configs[name] = value
        logger.info("reading session metadata: %s", configs)
        self.session.metadata = configs

    def read_session_options(self) -> None:
        session_options = self.scenario.find("session_options")
        if session_options is None:
            return
        xml_config = {}
        for configuration in session_options.iterchildren():
            name = configuration.get("name")
            value = configuration.get("value")
            xml_config[name] = value
        logger.info("reading session options: %s", xml_config)
        self.session.options.update(xml_config)
        self.session.parse_options()

    def read_session_hooks(self) -> None:
        session_hooks = self.scenario.find("session_hooks")
        if session_hooks is None:
            return
        for hook in session_hooks.iterchildren():
            name = hook.get("name")
            state = get_int(hook, "state")
            state = EventTypes(state)
            data = hook.text
            logger.info("reading hook: state(%s) name(%s)", state, name)
            self.session.add_hook(state, name, data)

    def read_servers(self) -> None:
        servers = self.scenario.find("servers")
        if servers is None:
            return
        for server in servers.iterchildren():
            name = server.get("name")
            address = server.get("address")
            logger.info("reading server: name(%s) address(%s)", name, address)
            self.session.distributed.add_server(name, address)

    def read_session_origin(self) -> None:
        session_origin = self.scenario.find("session_origin")
        if session_origin is None:
            return
        lat = get_float(session_origin, "lat")
        lon = get_float(session_origin, "lon")
        alt = get_float(session_origin, "alt")
        if all([lat, lon, alt]):
            logger.info("reading session reference geo: %s, %s, %s", lat, lon, alt)
            self.session.location.setrefgeo(lat, lon, alt)
        scale = get_float(session_origin, "scale")
        if scale:
            logger.info("reading session reference scale: %s", scale)
            self.session.location.refscale = scale
        x = get_float(session_origin, "x")
        y = get_float(session_origin, "y")
        z = get_float(session_origin, "z")
        if all([x, y]):
            logger.info("reading session reference xyz: %s, %s, %s", x, y, z)
            self.session.location.refxyz = (x, y, z)

    def read_emane_configs(self) -> None:
        emane_configurations = self.scenario.find("emane_configurations")
        if emane_configurations is None:
            return
        for emane_configuration in emane_configurations.iterchildren():
            node_id = get_int(emane_configuration, "node")
            iface_id = get_int(emane_configuration, "iface")
            model_name = emane_configuration.get("model")
            configs = {}
            # validate node and model
            node = self.session.nodes.get(node_id)
            if not node:
                raise CoreXmlError(f"node for emane config doesn't exist: {node_id}")
            self.session.emane.get_model(model_name)
            if iface_id is not None and iface_id not in node.ifaces:
                raise CoreXmlError(
                    f"invalid interface id({iface_id}) for node({node.name})"
                )
            # read and set emane model configuration
            platform_configuration = emane_configuration.find("platform")
            for config in platform_configuration.iterchildren():
                name = config.get("name")
                value = config.get("value")
                configs[name] = value
            mac_configuration = emane_configuration.find("mac")
            for config in mac_configuration.iterchildren():
                name = config.get("name")
                value = config.get("value")
                configs[name] = value
            phy_configuration = emane_configuration.find("phy")
            for config in phy_configuration.iterchildren():
                name = config.get("name")
                value = config.get("value")
                configs[name] = value
            external_configuration = emane_configuration.find("external")
            for config in external_configuration.iterchildren():
                name = config.get("name")
                value = config.get("value")
                configs[name] = value
            logger.info(
                "reading emane configuration node(%s) model(%s)", node_id, model_name
            )
            node_id = utils.iface_config_id(node_id, iface_id)
            self.session.emane.set_config(node_id, model_name, configs)

    def read_mobility_configs(self) -> None:
        mobility_configurations = self.scenario.find("mobility_configurations")
        if mobility_configurations is None:
            return
        for mobility_configuration in mobility_configurations.iterchildren():
            node_id = get_int(mobility_configuration, "node")
            model_name = mobility_configuration.get("model")
            configs = {}
            for config in mobility_configuration.iterchildren():
                name = config.get("name")
                value = config.get("value")
                configs[name] = value
            logger.info(
                "reading mobility configuration node(%s) model(%s)", node_id, model_name
            )
            self.session.mobility.set_model_config(node_id, model_name, configs)

    def read_nodes(self) -> None:
        device_elements = self.scenario.find("devices")
        if device_elements is not None:
            for device_element in device_elements.iterchildren():
                self.read_device(device_element)
        network_elements = self.scenario.find("networks")
        if network_elements is not None:
            for network_element in network_elements.iterchildren():
                self.read_network(network_element)

    def read_device(self, device_element: etree.Element) -> None:
        node_id = get_int(device_element, "id")
        name = device_element.get("name")
        model = device_element.get("type")
        icon = device_element.get("icon")
        clazz = device_element.get("class")
        image = device_element.get("image")
        compose = device_element.get("compose")
        compose_name = device_element.get("compose_name")
        server = device_element.get("server")
        canvas = get_int(device_element, "canvas")
        node_type = NodeTypes.DEFAULT
        if clazz == "docker":
            node_type = NodeTypes.DOCKER
        elif clazz == "podman":
            node_type = NodeTypes.PODMAN
        _class = self.session.get_node_class(node_type)
        options = _class.create_options()
        options.icon = icon
        options.canvas = canvas
        # check for special options
        if isinstance(options, CoreNodeOptions):
            options.model = model
            service_elements = device_element.find("services")
            if service_elements is None:
                service_elements = device_element.find("configservices")
            if service_elements is not None:
                options.services.extend(
                    x.get("name") for x in service_elements.iterchildren()
                )
        if isinstance(options, (DockerOptions, PodmanOptions)):
            options.image = image
            options.compose = compose
            options.compose_name = compose_name
        # get position information
        position_element = device_element.find("position")
        position = None
        if position_element is not None:
            position = Position()
            x = get_float(position_element, "x")
            y = get_float(position_element, "y")
            if all([x, y]):
                position.set(x, y)
            lat = get_float(position_element, "lat")
            lon = get_float(position_element, "lon")
            alt = get_float(position_element, "alt")
            if all([lat, lon, alt]):
                position.set_geo(lon, lat, alt)
        logger.info("reading node id(%s) model(%s) name(%s)", node_id, model, name)
        self.session.add_node(_class, node_id, name, server, position, options)

    def read_network(self, network_element: etree.Element) -> None:
        node_id = get_int(network_element, "id")
        name = network_element.get("name")
        server = network_element.get("server")
        node_type = NodeTypes[network_element.get("type")]
        _class = self.session.get_node_class(node_type)
        options = _class.create_options()
        options.canvas = get_int(network_element, "canvas")
        options.icon = network_element.get("icon")
        if isinstance(options, EmaneOptions):
            options.emane_model = network_element.get("model")
        position_element = network_element.find("position")
        position = None
        if position_element is not None:
            position = Position()
            x = get_float(position_element, "x")
            y = get_float(position_element, "y")
            if all([x, y]):
                position.set(x, y)
            lat = get_float(position_element, "lat")
            lon = get_float(position_element, "lon")
            alt = get_float(position_element, "alt")
            if all([lat, lon, alt]):
                position.set_geo(lon, lat, alt)
        logger.info(
            "reading node id(%s) node_type(%s) name(%s)", node_id, node_type, name
        )
        node = self.session.add_node(_class, node_id, name, server, position, options)
        if isinstance(node, WirelessNode):
            wireless_element = network_element.find("wireless")
            if wireless_element is not None:
                config = {}
                for config_element in wireless_element.iterchildren():
                    name = config_element.get("name")
                    value = config_element.get("value")
                    config[name] = value
                node.set_config(config)

    def read_service_configs(self) -> None:
        service_configs = self.scenario.find("service_configurations")
        if service_configs is None:
            service_configs = self.scenario.find("configservice_configurations")
        if service_configs is None:
            return
        for service_element in service_configs.iterchildren():
            name = service_element.get("name")
            node_id = get_int(service_element, "node")
            node = self.session.get_node(node_id, CoreNodeBase)
            service = node.services[name]
            configs_element = service_element.find("configs")
            if configs_element is not None:
                config = {}
                for config_element in configs_element.iterchildren():
                    key = config_element.get("key")
                    value = config_element.get("value")
                    config[key] = value
                service.set_config(config)
            templates_element = service_element.find("templates")
            if templates_element is not None:
                for template_element in templates_element.iterchildren():
                    name = template_element.get("name")
                    template = template_element.text
                    logger.info(
                        "loading xml template(%s): %s", type(template), template
                    )
                    service.set_template(name, template)

    def read_links(self) -> None:
        link_elements = self.scenario.find("links")
        if link_elements is None:
            return
        node_sets = set()
        for link_element in link_elements.iterchildren():
            node1_id = get_int(link_element, "node1")
            if node1_id is None:
                node1_id = get_int(link_element, "node_one")
            node2_id = get_int(link_element, "node2")
            if node2_id is None:
                node2_id = get_int(link_element, "node_two")
            node_set = frozenset((node1_id, node2_id))
            iface1_element = link_element.find("iface1")
            if iface1_element is None:
                iface1_element = link_element.find("interface_one")
            iface1_data = None
            if iface1_element is not None:
                iface1_data = create_iface_data(iface1_element)
            iface2_element = link_element.find("iface2")
            if iface2_element is None:
                iface2_element = link_element.find("interface_two")
            iface2_data = None
            if iface2_element is not None:
                iface2_data = create_iface_data(iface2_element)
            options_element = link_element.find("options")
            options = LinkOptions()
            if options_element is not None:
                options.bandwidth = get_int(options_element, "bandwidth")
                options.burst = get_int(options_element, "burst")
                options.delay = get_int(options_element, "delay")
                options.dup = get_int(options_element, "dup")
                options.mer = get_int(options_element, "mer")
                options.mburst = get_int(options_element, "mburst")
                options.jitter = get_int(options_element, "jitter")
                options.key = get_int(options_element, "key")
                options.loss = get_float(options_element, "loss")
                if options.loss is None:
                    options.loss = get_float(options_element, "per")
                options.unidirectional = get_int(options_element, "unidirectional") == 1
                options.buffer = get_int(options_element, "buffer")
            if options.unidirectional and node_set in node_sets:
                logger.info("updating link node1(%s) node2(%s)", node1_id, node2_id)
                self.session.update_link(
                    node1_id, node2_id, iface1_data.id, iface2_data.id, options
                )
            else:
                logger.info("adding link node1(%s) node2(%s)", node1_id, node2_id)
                self.session.add_link(
                    node1_id, node2_id, iface1_data, iface2_data, options
                )
            node_sets.add(node_set)
