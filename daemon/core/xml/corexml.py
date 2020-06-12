import logging
from typing import TYPE_CHECKING, Any, Dict, Generic, List, Optional, Type, TypeVar

from lxml import etree

import core.nodes.base
import core.nodes.physical
from core.emane.nodes import EmaneNet
from core.emulator.data import LinkData
from core.emulator.emudata import InterfaceData, LinkOptions, NodeOptions
from core.emulator.enumerations import EventTypes, NodeTypes
from core.errors import CoreXmlError
from core.nodes.base import CoreNodeBase, NodeBase
from core.nodes.docker import DockerNode
from core.nodes.lxd import LxcNode
from core.nodes.network import CtrlNet, WlanNode
from core.services.coreservices import CoreService

if TYPE_CHECKING:
    from core.emane.emanemodel import EmaneModel
    from core.emulator.session import Session

    EmaneModelType = Type[EmaneModel]
T = TypeVar("T")


def write_xml_file(
    xml_element: etree.Element, file_path: str, doctype: str = None
) -> None:
    xml_data = etree.tostring(
        xml_element,
        xml_declaration=True,
        pretty_print=True,
        encoding="UTF-8",
        doctype=doctype,
    )
    with open(file_path, "wb") as xml_file:
        xml_file.write(xml_data)


def get_type(element: etree.Element, name: str, _type: Generic[T]) -> Optional[T]:
    value = element.get(name)
    if value is not None:
        value = _type(value)
    return value


def get_float(element: etree.Element, name: str) -> float:
    return get_type(element, name, float)


def get_int(element: etree.Element, name: str) -> int:
    return get_type(element, name, int)


def add_attribute(element: etree.Element, name: str, value: Any) -> None:
    if value is not None:
        element.set(name, str(value))


def create_interface_data(interface_element: etree.Element) -> InterfaceData:
    interface_id = int(interface_element.get("id"))
    name = interface_element.get("name")
    mac = interface_element.get("mac")
    ip4 = interface_element.get("ip4")
    ip4_mask = get_int(interface_element, "ip4_mask")
    ip6 = interface_element.get("ip6")
    ip6_mask = get_int(interface_element, "ip6_mask")
    return InterfaceData(
        id=interface_id,
        name=name,
        mac=mac,
        ip4=ip4,
        ip4_mask=ip4_mask,
        ip6=ip6,
        ip6_mask=ip6_mask,
    )


def create_emane_config(session: "Session") -> etree.Element:
    emane_configuration = etree.Element("emane_global_configuration")
    config = session.emane.get_configs()
    emulator_element = etree.SubElement(emane_configuration, "emulator")
    for emulator_config in session.emane.emane_config.emulator_config:
        value = config[emulator_config.id]
        add_configuration(emulator_element, emulator_config.id, value)
    core_element = etree.SubElement(emane_configuration, "core")
    for core_config in session.emane.emane_config.core_config:
        value = config[core_config.id]
        add_configuration(core_element, core_config.id, value)
    return emane_configuration


def create_emane_model_config(
    node_id: int, model: "EmaneModelType", config: Dict[str, str]
) -> etree.Element:
    emane_element = etree.Element("emane_configuration")
    add_attribute(emane_element, "node", node_id)
    add_attribute(emane_element, "model", model.name)

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


class ServiceElement:
    def __init__(self, service: Type[CoreService]) -> None:
        self.service: Type[CoreService] = service
        self.element: etree.Element = etree.Element("service")
        add_attribute(self.element, "name", service.name)
        self.add_directories()
        self.add_startup()
        self.add_validate()
        self.add_shutdown()
        self.add_files()

    def add_directories(self) -> None:
        # get custom directories
        directories = etree.Element("directories")
        for directory in self.service.dirs:
            directory_element = etree.SubElement(directories, "directory")
            directory_element.text = directory

        if directories.getchildren():
            self.element.append(directories)

    def add_files(self) -> None:
        file_elements = etree.Element("files")
        for file_name in self.service.config_data:
            data = self.service.config_data[file_name]
            file_element = etree.SubElement(file_elements, "file")
            add_attribute(file_element, "name", file_name)
            file_element.text = etree.CDATA(data)
        if file_elements.getchildren():
            self.element.append(file_elements)

    def add_startup(self) -> None:
        # get custom startup
        startup_elements = etree.Element("startups")
        for startup in self.service.startup:
            startup_element = etree.SubElement(startup_elements, "startup")
            startup_element.text = startup

        if startup_elements.getchildren():
            self.element.append(startup_elements)

    def add_validate(self) -> None:
        # get custom validate
        validate_elements = etree.Element("validates")
        for validate in self.service.validate:
            validate_element = etree.SubElement(validate_elements, "validate")
            validate_element.text = validate

        if validate_elements.getchildren():
            self.element.append(validate_elements)

    def add_shutdown(self) -> None:
        # get custom shutdown
        shutdown_elements = etree.Element("shutdowns")
        for shutdown in self.service.shutdown:
            shutdown_element = etree.SubElement(shutdown_elements, "shutdown")
            shutdown_element.text = shutdown

        if shutdown_elements.getchildren():
            self.element.append(shutdown_elements)


class DeviceElement(NodeElement):
    def __init__(self, session: "Session", node: NodeBase) -> None:
        super().__init__(session, node, "device")
        add_attribute(self.element, "type", node.type)
        self.add_class()
        self.add_services()

    def add_class(self) -> None:
        clazz = ""
        image = ""
        if isinstance(self.node, DockerNode):
            clazz = "docker"
            image = self.node.image
        elif isinstance(self.node, LxcNode):
            clazz = "lxc"
            image = self.node.image
        add_attribute(self.element, "class", clazz)
        add_attribute(self.element, "image", image)

    def add_services(self) -> None:
        service_elements = etree.Element("services")
        for service in self.node.services:
            etree.SubElement(service_elements, "service", name=service.name)
        if service_elements.getchildren():
            self.element.append(service_elements)

        config_service_elements = etree.Element("configservices")
        for name, service in self.node.config_services.items():
            etree.SubElement(config_service_elements, "service", name=name)
        if config_service_elements.getchildren():
            self.element.append(config_service_elements)


class NetworkElement(NodeElement):
    def __init__(self, session: "Session", node: NodeBase) -> None:
        super().__init__(session, node, "network")
        model = getattr(self.node, "model", None)
        if model:
            add_attribute(self.element, "model", model.name)
        mobility = getattr(self.node, "mobility", None)
        if mobility:
            add_attribute(self.element, "mobility", mobility.name)
        grekey = getattr(self.node, "grekey", None)
        if grekey and grekey is not None:
            add_attribute(self.element, "grekey", grekey)
        self.add_type()

    def add_type(self) -> None:
        if self.node.apitype:
            node_type = self.node.apitype.name
        else:
            node_type = self.node.__class__.__name__
        add_attribute(self.element, "type", node_type)


class CoreXmlWriter:
    def __init__(self, session: "Session") -> None:
        self.session: "Session" = session
        self.scenario: etree.Element = etree.Element("scenario")
        self.networks: etree.SubElement = etree.SubElement(self.scenario, "networks")
        self.devices: etree.SubElement = etree.SubElement(self.scenario, "devices")
        self.write_session()

    def write_session(self) -> None:
        # generate xml content
        links = self.write_nodes()
        self.write_links(links)
        self.write_mobility_configs()
        self.write_emane_configs()
        self.write_service_configs()
        self.write_configservice_configs()
        self.write_session_origin()
        self.write_session_hooks()
        self.write_session_options()
        self.write_session_metadata()
        self.write_default_services()

    def write(self, file_name: str) -> None:
        self.scenario.set("name", file_name)

        # write out generated xml
        xml_tree = etree.ElementTree(self.scenario)
        xml_tree.write(
            file_name, xml_declaration=True, pretty_print=True, encoding="UTF-8"
        )

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

    def write_session_hooks(self) -> None:
        # hook scripts
        hooks = etree.Element("session_hooks")
        for state in sorted(self.session._hooks, key=lambda x: x.value):
            for file_name, data in self.session._hooks[state]:
                hook = etree.SubElement(hooks, "hook")
                add_attribute(hook, "name", file_name)
                add_attribute(hook, "state", state.value)
                hook.text = data

        if hooks.getchildren():
            self.scenario.append(hooks)

    def write_session_options(self) -> None:
        option_elements = etree.Element("session_options")
        options_config = self.session.options.get_configs()
        if not options_config:
            return

        default_options = self.session.options.default_values()
        for _id in default_options:
            default_value = default_options[_id]
            value = options_config.get(_id, default_value)
            add_configuration(option_elements, _id, value)

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
        emane_global_configuration = create_emane_config(self.session)
        self.scenario.append(emane_global_configuration)
        emane_configurations = etree.Element("emane_configurations")
        for node_id in self.session.emane.nodes():
            all_configs = self.session.emane.get_all_configs(node_id)
            if not all_configs:
                continue
            for model_name in all_configs:
                config = all_configs[model_name]
                logging.debug(
                    "writing emane config node(%s) model(%s)", node_id, model_name
                )
                model = self.session.emane.models[model_name]
                emane_configuration = create_emane_model_config(node_id, model, config)
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
                logging.debug(
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
        service_configs = self.session.services.all_configs()
        for node_id, service in service_configs:
            service_element = ServiceElement(service)
            add_attribute(service_element.element, "node", node_id)
            service_configurations.append(service_element.element)

        if service_configurations.getchildren():
            self.scenario.append(service_configurations)

    def write_configservice_configs(self) -> None:
        service_configurations = etree.Element("configservice_configurations")
        for node in self.session.nodes.values():
            if not isinstance(node, CoreNodeBase):
                continue
            for name, service in node.config_services.items():
                service_element = etree.SubElement(
                    service_configurations, "service", name=name
                )
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
        if service_configurations.getchildren():
            self.scenario.append(service_configurations)

    def write_default_services(self) -> None:
        node_types = etree.Element("default_services")
        for node_type in self.session.services.default_services:
            services = self.session.services.default_services[node_type]
            node_type = etree.SubElement(node_types, "node", type=node_type)
            for service in services:
                etree.SubElement(node_type, "service", name=service)

        if node_types.getchildren():
            self.scenario.append(node_types)

    def write_nodes(self) -> List[LinkData]:
        links = []
        for node_id in self.session.nodes:
            node = self.session.nodes[node_id]
            # network node
            is_network_or_rj45 = isinstance(
                node, (core.nodes.base.CoreNetworkBase, core.nodes.physical.Rj45Node)
            )
            is_controlnet = isinstance(node, CtrlNet)
            if is_network_or_rj45 and not is_controlnet:
                self.write_network(node)
            # device node
            elif isinstance(node, core.nodes.base.CoreNodeBase):
                self.write_device(node)

            # add known links
            links.extend(node.all_link_data())
        return links

    def write_network(self, node: NodeBase) -> None:
        # ignore p2p and other nodes that are not part of the api
        if not node.apitype:
            return

        network = NetworkElement(self.session, node)
        self.networks.append(network.element)

    def write_links(self, links: List[LinkData]) -> None:
        link_elements = etree.Element("links")
        # add link data
        for link_data in links:
            # skip basic range links
            if link_data.interface1_id is None and link_data.interface2_id is None:
                continue

            link_element = self.create_link_element(link_data)
            link_elements.append(link_element)

        if link_elements.getchildren():
            self.scenario.append(link_elements)

    def write_device(self, node: NodeBase) -> None:
        device = DeviceElement(self.session, node)
        self.devices.append(device.element)

    def create_interface_element(
        self,
        element_name: str,
        node_id: int,
        interface_id: int,
        mac: str,
        ip4: str,
        ip4_mask: int,
        ip6: str,
        ip6_mask: int,
    ) -> etree.Element:
        interface = etree.Element(element_name)
        node = self.session.get_node(node_id, NodeBase)
        interface_name = None
        if isinstance(node, CoreNodeBase):
            node_interface = node.netif(interface_id)
            interface_name = node_interface.name

            # check if emane interface
            if isinstance(node_interface.net, EmaneNet):
                nem = node_interface.net.getnemid(node_interface)
                add_attribute(interface, "nem", nem)

        add_attribute(interface, "id", interface_id)
        add_attribute(interface, "name", interface_name)
        add_attribute(interface, "mac", mac)
        add_attribute(interface, "ip4", ip4)
        add_attribute(interface, "ip4_mask", ip4_mask)
        add_attribute(interface, "ip6", ip6)
        add_attribute(interface, "ip6_mask", ip6_mask)
        return interface

    def create_link_element(self, link_data: LinkData) -> etree.Element:
        link_element = etree.Element("link")
        add_attribute(link_element, "node_one", link_data.node1_id)
        add_attribute(link_element, "node_two", link_data.node2_id)

        # check for interface one
        if link_data.interface1_id is not None:
            interface1 = self.create_interface_element(
                "interface_one",
                link_data.node1_id,
                link_data.interface1_id,
                link_data.interface1_mac,
                link_data.interface1_ip4,
                link_data.interface1_ip4_mask,
                link_data.interface1_ip6,
                link_data.interface1_ip6_mask,
            )
            link_element.append(interface1)

        # check for interface two
        if link_data.interface2_id is not None:
            interface2 = self.create_interface_element(
                "interface_two",
                link_data.node2_id,
                link_data.interface2_id,
                link_data.interface2_mac,
                link_data.interface2_ip4,
                link_data.interface2_ip4_mask,
                link_data.interface2_ip6,
                link_data.interface2_ip6_mask,
            )
            link_element.append(interface2)

        # check for options, don't write for emane/wlan links
        node1 = self.session.get_node(link_data.node1_id, NodeBase)
        node2 = self.session.get_node(link_data.node2_id, NodeBase)
        is_node1_wireless = isinstance(node1, (WlanNode, EmaneNet))
        is_node2_wireless = isinstance(node2, (WlanNode, EmaneNet))
        if not any([is_node1_wireless, is_node2_wireless]):
            options = etree.Element("options")
            add_attribute(options, "delay", link_data.delay)
            add_attribute(options, "bandwidth", link_data.bandwidth)
            add_attribute(options, "per", link_data.per)
            add_attribute(options, "dup", link_data.dup)
            add_attribute(options, "jitter", link_data.jitter)
            add_attribute(options, "mer", link_data.mer)
            add_attribute(options, "burst", link_data.burst)
            add_attribute(options, "mburst", link_data.mburst)
            add_attribute(options, "type", link_data.link_type)
            add_attribute(options, "gui_attributes", link_data.gui_attributes)
            add_attribute(options, "unidirectional", link_data.unidirectional)
            add_attribute(options, "emulation_id", link_data.emulation_id)
            add_attribute(options, "network_id", link_data.network_id)
            add_attribute(options, "key", link_data.key)
            add_attribute(options, "opaque", link_data.opaque)
            add_attribute(options, "session", link_data.session)
            if options.items():
                link_element.append(options)

        return link_element


class CoreXmlReader:
    def __init__(self, session: "Session") -> None:
        self.session: "Session" = session
        self.scenario: Optional[etree.ElementTree] = None

    def read(self, file_name: str) -> None:
        xml_tree = etree.parse(file_name)
        self.scenario = xml_tree.getroot()

        # read xml session content
        self.read_default_services()
        self.read_session_metadata()
        self.read_session_options()
        self.read_session_hooks()
        self.read_session_origin()
        self.read_service_configs()
        self.read_mobility_configs()
        self.read_emane_global_config()
        self.read_nodes()
        self.read_emane_configs()
        self.read_configservice_configs()
        self.read_links()

    def read_default_services(self) -> None:
        default_services = self.scenario.find("default_services")
        if default_services is None:
            return

        for node in default_services.iterchildren():
            node_type = node.get("type")
            services = []
            for service in node.iterchildren():
                services.append(service.get("name"))
            logging.info(
                "reading default services for nodes(%s): %s", node_type, services
            )
            self.session.services.default_services[node_type] = services

    def read_session_metadata(self) -> None:
        session_metadata = self.scenario.find("session_metadata")
        if session_metadata is None:
            return

        configs = {}
        for data in session_metadata.iterchildren():
            name = data.get("name")
            value = data.get("value")
            configs[name] = value
        logging.info("reading session metadata: %s", configs)
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
        logging.info("reading session options: %s", xml_config)
        config = self.session.options.get_configs()
        config.update(xml_config)

    def read_session_hooks(self) -> None:
        session_hooks = self.scenario.find("session_hooks")
        if session_hooks is None:
            return

        for hook in session_hooks.iterchildren():
            name = hook.get("name")
            state = get_int(hook, "state")
            state = EventTypes(state)
            data = hook.text
            logging.info("reading hook: state(%s) name(%s)", state, name)
            self.session.add_hook(state, name, data)

    def read_session_origin(self) -> None:
        session_origin = self.scenario.find("session_origin")
        if session_origin is None:
            return

        lat = get_float(session_origin, "lat")
        lon = get_float(session_origin, "lon")
        alt = get_float(session_origin, "alt")
        if all([lat, lon, alt]):
            logging.info("reading session reference geo: %s, %s, %s", lat, lon, alt)
            self.session.location.setrefgeo(lat, lon, alt)

        scale = get_float(session_origin, "scale")
        if scale:
            logging.info("reading session reference scale: %s", scale)
            self.session.location.refscale = scale

        x = get_float(session_origin, "x")
        y = get_float(session_origin, "y")
        z = get_float(session_origin, "z")
        if all([x, y]):
            logging.info("reading session reference xyz: %s, %s, %s", x, y, z)
            self.session.location.refxyz = (x, y, z)

    def read_service_configs(self) -> None:
        service_configurations = self.scenario.find("service_configurations")
        if service_configurations is None:
            return

        for service_configuration in service_configurations.iterchildren():
            node_id = get_int(service_configuration, "node")
            service_name = service_configuration.get("name")
            logging.info(
                "reading custom service(%s) for node(%s)", service_name, node_id
            )
            self.session.services.set_service(node_id, service_name)
            service = self.session.services.get_service(node_id, service_name)

            directory_elements = service_configuration.find("directories")
            if directory_elements is not None:
                service.dirs = tuple(x.text for x in directory_elements.iterchildren())

            startup_elements = service_configuration.find("startups")
            if startup_elements is not None:
                service.startup = tuple(x.text for x in startup_elements.iterchildren())

            validate_elements = service_configuration.find("validates")
            if validate_elements is not None:
                service.validate = tuple(
                    x.text for x in validate_elements.iterchildren()
                )

            shutdown_elements = service_configuration.find("shutdowns")
            if shutdown_elements is not None:
                service.shutdown = tuple(
                    x.text for x in shutdown_elements.iterchildren()
                )

            file_elements = service_configuration.find("files")
            if file_elements is not None:
                files = set(service.configs)
                for file_element in file_elements.iterchildren():
                    name = file_element.get("name")
                    data = file_element.text
                    service.config_data[name] = data
                    files.add(name)
                service.configs = tuple(files)

    def read_emane_global_config(self) -> None:
        emane_global_configuration = self.scenario.find("emane_global_configuration")
        if emane_global_configuration is None:
            return
        emulator_configuration = emane_global_configuration.find("emulator")
        configs = {}
        for config in emulator_configuration.iterchildren():
            name = config.get("name")
            value = config.get("value")
            configs[name] = value
        core_configuration = emane_global_configuration.find("core")
        for config in core_configuration.iterchildren():
            name = config.get("name")
            value = config.get("value")
            configs[name] = value
        self.session.emane.set_configs(config=configs)

    def read_emane_configs(self) -> None:
        emane_configurations = self.scenario.find("emane_configurations")
        if emane_configurations is None:
            return

        for emane_configuration in emane_configurations.iterchildren():
            node_id = get_int(emane_configuration, "node")
            model_name = emane_configuration.get("model")
            configs = {}

            # validate node and model
            node = self.session.nodes.get(node_id)
            if not node:
                raise CoreXmlError(f"node for emane config doesn't exist: {node_id}")
            if not isinstance(node, EmaneNet):
                raise CoreXmlError(f"invalid node for emane config: {node.name}")
            model = self.session.emane.models.get(model_name)
            if not model:
                raise CoreXmlError(f"invalid emane model: {model_name}")
            node.setmodel(model, {})

            # read and set emane model configuration
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

            logging.info(
                "reading emane configuration node(%s) model(%s)", node_id, model_name
            )
            self.session.emane.set_model_config(node_id, model_name, configs)

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

            logging.info(
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
        options = NodeOptions(name=name, model=model, image=image, icon=icon)

        node_type = NodeTypes.DEFAULT
        if clazz == "docker":
            node_type = NodeTypes.DOCKER
        elif clazz == "lxc":
            node_type = NodeTypes.LXC
        _class = self.session.get_node_class(node_type)

        service_elements = device_element.find("services")
        if service_elements is not None:
            options.services = [x.get("name") for x in service_elements.iterchildren()]

        config_service_elements = device_element.find("configservices")
        if config_service_elements is not None:
            options.config_services = [
                x.get("name") for x in config_service_elements.iterchildren()
            ]

        position_element = device_element.find("position")
        if position_element is not None:
            x = get_float(position_element, "x")
            y = get_float(position_element, "y")
            if all([x, y]):
                options.set_position(x, y)

            lat = get_float(position_element, "lat")
            lon = get_float(position_element, "lon")
            alt = get_float(position_element, "alt")
            if all([lat, lon, alt]):
                options.set_location(lat, lon, alt)

        logging.info("reading node id(%s) model(%s) name(%s)", node_id, model, name)
        self.session.add_node(_class, node_id, options)

    def read_network(self, network_element: etree.Element) -> None:
        node_id = get_int(network_element, "id")
        name = network_element.get("name")
        node_type = NodeTypes[network_element.get("type")]
        _class = self.session.get_node_class(node_type)
        icon = network_element.get("icon")
        options = NodeOptions(name=name, icon=icon)

        position_element = network_element.find("position")
        if position_element is not None:
            x = get_float(position_element, "x")
            y = get_float(position_element, "y")
            if all([x, y]):
                options.set_position(x, y)

            lat = get_float(position_element, "lat")
            lon = get_float(position_element, "lon")
            alt = get_float(position_element, "alt")
            if all([lat, lon, alt]):
                options.set_location(lat, lon, alt)

        logging.info(
            "reading node id(%s) node_type(%s) name(%s)", node_id, node_type, name
        )
        self.session.add_node(_class, node_id, options)

    def read_configservice_configs(self) -> None:
        configservice_configs = self.scenario.find("configservice_configurations")
        if configservice_configs is None:
            return

        for configservice_element in configservice_configs.iterchildren():
            name = configservice_element.get("name")
            node_id = get_int(configservice_element, "node")
            node = self.session.get_node(node_id, CoreNodeBase)
            service = node.config_services[name]

            configs_element = configservice_element.find("configs")
            if configs_element is not None:
                config = {}
                for config_element in configs_element.iterchildren():
                    key = config_element.get("key")
                    value = config_element.get("value")
                    config[key] = value
                service.set_config(config)

            templates_element = configservice_element.find("templates")
            if templates_element is not None:
                for template_element in templates_element.iterchildren():
                    name = template_element.get("name")
                    template = template_element.text
                    logging.info(
                        "loading xml template(%s): %s", type(template), template
                    )
                    service.set_template(name, template)

    def read_links(self) -> None:
        link_elements = self.scenario.find("links")
        if link_elements is None:
            return

        node_sets = set()
        for link_element in link_elements.iterchildren():
            node1_id = get_int(link_element, "node_one")
            node2_id = get_int(link_element, "node_two")
            node_set = frozenset((node1_id, node2_id))

            interface1_element = link_element.find("interface_one")
            interface1_data = None
            if interface1_element is not None:
                interface1_data = create_interface_data(interface1_element)

            interface2_element = link_element.find("interface_two")
            interface2_data = None
            if interface2_element is not None:
                interface2_data = create_interface_data(interface2_element)

            options_element = link_element.find("options")
            link_options = LinkOptions()
            if options_element is not None:
                link_options.bandwidth = get_int(options_element, "bandwidth")
                link_options.burst = get_int(options_element, "burst")
                link_options.delay = get_int(options_element, "delay")
                link_options.dup = get_int(options_element, "dup")
                link_options.mer = get_int(options_element, "mer")
                link_options.mburst = get_int(options_element, "mburst")
                link_options.jitter = get_int(options_element, "jitter")
                link_options.key = get_int(options_element, "key")
                link_options.per = get_float(options_element, "per")
                link_options.unidirectional = get_int(options_element, "unidirectional")
                link_options.session = options_element.get("session")
                link_options.emulation_id = get_int(options_element, "emulation_id")
                link_options.network_id = get_int(options_element, "network_id")
                link_options.opaque = options_element.get("opaque")
                link_options.gui_attributes = options_element.get("gui_attributes")

            if link_options.unidirectional == 1 and node_set in node_sets:
                logging.info("updating link node1(%s) node2(%s)", node1_id, node2_id)
                self.session.update_link(
                    node1_id,
                    node2_id,
                    interface1_data.id,
                    interface2_data.id,
                    link_options,
                )
            else:
                logging.info("adding link node1(%s) node2(%s)", node1_id, node2_id)
                self.session.add_link(
                    node1_id, node2_id, interface1_data, interface2_data, link_options
                )

            node_sets.add(node_set)
