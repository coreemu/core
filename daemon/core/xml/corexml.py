import logging

from lxml import etree

import core.nodes.base
import core.nodes.physical
from core.emulator.emudata import InterfaceData, LinkOptions, NodeOptions
from core.emulator.enumerations import NodeTypes
from core.nodes import nodeutils
from core.nodes.base import CoreNetworkBase
from core.nodes.ipaddress import MacAddress


def write_xml_file(xml_element, file_path, doctype=None):
    xml_data = etree.tostring(xml_element, xml_declaration=True, pretty_print=True, encoding="UTF-8", doctype=doctype)
    with open(file_path, "wb") as xml_file:
        xml_file.write(xml_data)


def get_type(element, name, _type):
    value = element.get(name)
    if value is not None:
        value = _type(value)
    return value


def get_float(element, name):
    return get_type(element, name, float)


def get_int(element, name):
    return get_type(element, name, int)


def add_attribute(element, name, value):
    if value is not None:
        element.set(name, str(value))


def create_interface_data(interface_element):
    interface_id = int(interface_element.get("id"))
    name = interface_element.get("name")
    mac = interface_element.get("mac")
    if mac:
        mac = MacAddress.from_string(mac)
    ip4 = interface_element.get("ip4")
    ip4_mask = get_int(interface_element, "ip4_mask")
    ip6 = interface_element.get("ip6")
    ip6_mask = get_int(interface_element, "ip6_mask")
    return InterfaceData(interface_id, name, mac, ip4, ip4_mask, ip6, ip6_mask)


def create_emane_config(node_id, emane_config, config):
    emane_configuration = etree.Element("emane_configuration")
    add_attribute(emane_configuration, "node", node_id)
    add_attribute(emane_configuration, "model", "emane")

    emulator_element = etree.SubElement(emane_configuration, "emulator")
    for emulator_config in emane_config.emulator_config:
        value = config[emulator_config.id]
        add_configuration(emulator_element, emulator_config.id, value)

    nem_element = etree.SubElement(emane_configuration, "nem")
    for nem_config in emane_config.nem_config:
        value = config[nem_config.id]
        add_configuration(nem_element, nem_config.id, value)

    return emane_configuration


def create_emane_model_config(node_id, model, config):
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


def add_configuration(parent, name, value):
    config_element = etree.SubElement(parent, "configuration")
    add_attribute(config_element, "name", name)
    add_attribute(config_element, "value", value)


class NodeElement(object):
    def __init__(self, session, node, element_name):
        self.session = session
        self.node = node
        self.element = etree.Element(element_name)
        add_attribute(self.element, "id", node.id)
        add_attribute(self.element, "name", node.name)
        add_attribute(self.element, "icon", node.icon)
        add_attribute(self.element, "canvas", node.canvas)
        self.add_position()

    def add_position(self):
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


class ServiceElement(object):
    def __init__(self, service):
        self.service = service
        self.element = etree.Element("service")
        add_attribute(self.element, "name", service.name)
        self.add_directories()
        self.add_startup()
        self.add_validate()
        self.add_shutdown()
        self.add_files()

    def add_directories(self):
        # get custom directories
        directories = etree.Element("directories")
        for directory in self.service.dirs:
            directory_element = etree.SubElement(directories, "directory")
            directory_element.text = directory

        if directories.getchildren():
            self.element.append(directories)

    def add_files(self):
        # get custom files
        file_elements = etree.Element("files")
        for file_name in self.service.config_data:
            data = self.service.config_data[file_name]
            file_element = etree.SubElement(file_elements, "file")
            add_attribute(file_element, "name", file_name)
            file_element.text = data

        if file_elements.getchildren():
            self.element.append(file_elements)

    def add_startup(self):
        # get custom startup
        startup_elements = etree.Element("startups")
        for startup in self.service.startup:
            startup_element = etree.SubElement(startup_elements, "startup")
            startup_element.text = startup

        if startup_elements.getchildren():
            self.element.append(startup_elements)

    def add_validate(self):
        # get custom validate
        validate_elements = etree.Element("validates")
        for validate in self.service.validate:
            validate_element = etree.SubElement(validate_elements, "validate")
            validate_element.text = validate

        if validate_elements.getchildren():
            self.element.append(validate_elements)

    def add_shutdown(self):
        # get custom shutdown
        shutdown_elements = etree.Element("shutdowns")
        for shutdown in self.service.shutdown:
            shutdown_element = etree.SubElement(shutdown_elements, "shutdown")
            shutdown_element.text = shutdown

        if shutdown_elements.getchildren():
            self.element.append(shutdown_elements)


class DeviceElement(NodeElement):
    def __init__(self, session, node):
        super(DeviceElement, self).__init__(session, node, "device")
        add_attribute(self.element, "type", node.type)
        self.add_services()

    def add_services(self):
        service_elements = etree.Element("services")
        for service in self.node.services:
            etree.SubElement(service_elements, "service", name=service.name)

        if service_elements.getchildren():
            self.element.append(service_elements)


class NetworkElement(NodeElement):
    def __init__(self, session, node):
        super(NetworkElement, self).__init__(session, node, "network")
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

    def add_type(self):
        if self.node.apitype:
            node_type = NodeTypes(self.node.apitype).name
        else:
            node_type = self.node.__class__.__name__
        add_attribute(self.element, "type", node_type)


class CoreXmlWriter(object):
    def __init__(self, session):
        self.session = session
        self.scenario = etree.Element("scenario")
        self.networks = None
        self.devices = None
        self.write_session()

    def write_session(self):
        # generate xml content
        links = self.write_nodes()
        self.write_links(links)
        self.write_mobility_configs()
        self.write_emane_configs()
        self.write_service_configs()
        self.write_session_origin()
        self.write_session_hooks()
        self.write_session_options()
        self.write_session_metadata()
        self.write_default_services()

    def write(self, file_name):
        self.scenario.set("name", file_name)

        # write out generated xml
        xml_tree = etree.ElementTree(self.scenario)
        xml_tree.write(file_name, xml_declaration=True, pretty_print=True, encoding="UTF-8")

    def write_session_origin(self):
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

    def write_session_hooks(self):
        # hook scripts
        hooks = etree.Element("session_hooks")
        for state in sorted(self.session._hooks.keys()):
            for file_name, data in self.session._hooks[state]:
                hook = etree.SubElement(hooks, "hook")
                add_attribute(hook, "name", file_name)
                add_attribute(hook, "state", state)
                hook.text = data

        if hooks.getchildren():
            self.scenario.append(hooks)

    def write_session_options(self):
        option_elements = etree.Element("session_options")
        options_config = self.session.options.get_configs()
        if not options_config:
            return

        default_options = self.session.options.default_values()
        for _id in default_options:
            default_value = default_options[_id]
            # TODO: should we just save the current config regardless, since it may change?
            value = options_config[_id]
            if value != default_value:
                add_configuration(option_elements, _id, value)

        if option_elements.getchildren():
            self.scenario.append(option_elements)

    def write_session_metadata(self):
        # metadata
        metadata_elements = etree.Element("session_metadata")
        config = self.session.metadata.get_configs()
        if not config:
            return

        for _id in config:
            value = config[_id]
            add_configuration(metadata_elements, _id, value)

        if metadata_elements.getchildren():
            self.scenario.append(metadata_elements)

    def write_emane_configs(self):
        emane_configurations = etree.Element("emane_configurations")
        for node_id in self.session.emane.nodes():
            all_configs = self.session.emane.get_all_configs(node_id)
            if not all_configs:
                continue

            for model_name in all_configs:
                config = all_configs[model_name]
                logging.info("writing emane config node(%s) model(%s)", node_id, model_name)
                if model_name == -1:
                    emane_configuration = create_emane_config(node_id, self.session.emane.emane_config, config)
                else:
                    model = self.session.emane.models[model_name]
                    emane_configuration = create_emane_model_config(node_id, model, config)
                emane_configurations.append(emane_configuration)

        if emane_configurations.getchildren():
            self.scenario.append(emane_configurations)

    def write_mobility_configs(self):
        mobility_configurations = etree.Element("mobility_configurations")
        for node_id in self.session.mobility.nodes():
            all_configs = self.session.mobility.get_all_configs(node_id)
            if not all_configs:
                continue

            for model_name in all_configs:
                config = all_configs[model_name]
                logging.info("writing mobility config node(%s) model(%s)", node_id, model_name)
                mobility_configuration = etree.SubElement(mobility_configurations, "mobility_configuration")
                add_attribute(mobility_configuration, "node", node_id)
                add_attribute(mobility_configuration, "model", model_name)
                for name in config:
                    value = config[name]
                    add_configuration(mobility_configuration, name, value)

        if mobility_configurations.getchildren():
            self.scenario.append(mobility_configurations)

    def write_service_configs(self):
        service_configurations = etree.Element("service_configurations")
        service_configs = self.session.services.all_configs()
        for node_id, service in service_configs:
            service_element = ServiceElement(service)
            add_attribute(service_element.element, "node", node_id)
            service_configurations.append(service_element.element)

        if service_configurations.getchildren():
            self.scenario.append(service_configurations)

    def write_default_services(self):
        node_types = etree.Element("default_services")
        for node_type in self.session.services.default_services:
            services = self.session.services.default_services[node_type]
            node_type = etree.SubElement(node_types, "node", type=node_type)
            for service in services:
                etree.SubElement(node_type, "service", name=service)

        if node_types.getchildren():
            self.scenario.append(node_types)

    def write_nodes(self):
        self.networks = etree.SubElement(self.scenario, "networks")
        self.devices = etree.SubElement(self.scenario, "devices")

        links = []
        for node_id in self.session.nodes:
            node = self.session.nodes[node_id]
            # network node
            is_network_or_rj45 = isinstance(node, (core.nodes.base.CoreNetworkBase, core.nodes.physical.Rj45Node))
            is_controlnet = nodeutils.is_node(node, NodeTypes.CONTROL_NET)
            if is_network_or_rj45 and not is_controlnet:
                self.write_network(node)
            # device node
            elif isinstance(node, core.nodes.base.CoreNodeBase):
                self.write_device(node)
            else:
                logging.error("unknown node: %s", node)

            # add known links
            links.extend(node.all_link_data(0))

        return links

    def write_network(self, node):
        # ignore p2p and other nodes that are not part of the api
        if not node.apitype:
            logging.warning("ignoring node with no apitype: %s", node)
            return

        network = NetworkElement(self.session, node)
        self.networks.append(network.element)

    def write_links(self, links):
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

    def write_device(self, node):
        device = DeviceElement(self.session, node)
        self.devices.append(device.element)

    def create_interface_element(self, element_name, node_id, interface_id, mac, ip4, ip4_mask, ip6, ip6_mask):
        interface = etree.Element(element_name)
        node = self.session.get_node(node_id)
        interface_name = None
        if not isinstance(node, CoreNetworkBase):
            node_interface = node.netif(interface_id)
            interface_name = node_interface.name

            # check if emane interface
            if nodeutils.is_node(node_interface.net, NodeTypes.EMANE):
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

    def create_link_element(self, link_data):
        link_element = etree.Element("link")
        add_attribute(link_element, "node_one", link_data.node1_id)
        add_attribute(link_element, "node_two", link_data.node2_id)

        # check for interface one
        if link_data.interface1_id is not None:
            interface_one = self.create_interface_element(
                "interface_one",
                link_data.node1_id,
                link_data.interface1_id,
                link_data.interface1_mac,
                link_data.interface1_ip4,
                link_data.interface1_ip4_mask,
                link_data.interface1_ip6,
                link_data.interface1_ip6_mask
            )
            link_element.append(interface_one)

        # check for interface two
        if link_data.interface2_id is not None:
            interface_two = self.create_interface_element(
                "interface_two",
                link_data.node2_id,
                link_data.interface2_id,
                link_data.interface2_mac,
                link_data.interface2_ip4,
                link_data.interface2_ip4_mask,
                link_data.interface2_ip6,
                link_data.interface2_ip6_mask
            )
            link_element.append(interface_two)

        # check for options
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


class CoreXmlReader(object):
    def __init__(self, session):
        self.session = session
        self.scenario = None

    def read(self, file_name):
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
        self.read_emane_configs()
        self.read_nodes()
        self.read_links()

    def read_default_services(self):
        default_services = self.scenario.find("default_services")
        if default_services is None:
            return

        for node in default_services.iterchildren():
            node_type = node.get("type")
            services = []
            for service in node.iterchildren():
                services.append(service.get("name"))
            logging.info("reading default services for nodes(%s): %s", node_type, services)
            self.session.services.default_services[node_type] = services

    def read_session_metadata(self):
        session_metadata = self.scenario.find("session_metadata")
        if session_metadata is None:
            return

        configs = {}
        for data in session_metadata.iterchildren():
            name = data.get("name")
            value = data.get("value")
            configs[name] = value
        logging.info("reading session metadata: %s", configs)
        self.session.metadata.set_configs(configs)

    def read_session_options(self):
        session_options = self.scenario.find("session_options")
        if session_options is None:
            return

        configs = {}
        for config in session_options.iterchildren():
            name = config.get("name")
            value = config.get("value")
            configs[name] = value
        logging.info("reading session options: %s", configs)
        self.session.options.set_configs(configs)

    def read_session_hooks(self):
        session_hooks = self.scenario.find("session_hooks")
        if session_hooks is None:
            return

        for hook in session_hooks.iterchildren():
            name = hook.get("name")
            state = hook.get("state")
            data = hook.text
            hook_type = "hook:%s" % state
            logging.info("reading hook: state(%s) name(%s)", state, name)
            self.session.set_hook(hook_type, file_name=name, source_name=None, data=data)

    def read_session_origin(self):
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

    def read_service_configs(self):
        service_configurations = self.scenario.find("service_configurations")
        if service_configurations is None:
            return

        for service_configuration in service_configurations.iterchildren():
            node_id = get_int(service_configuration, "node")
            service_name = service_configuration.get("name")
            logging.info("reading custom service(%s) for node(%s)", service_name, node_id)
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
                service.validate = tuple(x.text for x in validate_elements.iterchildren())

            shutdown_elements = service_configuration.find("shutdowns")
            if shutdown_elements is not None:
                service.shutdown = tuple(x.text for x in shutdown_elements.iterchildren())

            file_elements = service_configuration.find("files")
            if file_elements is not None:
                for file_element in file_elements.iterchildren():
                    name = file_element.get("name")
                    data = file_element.text
                    service.config_data[name] = data

    def read_emane_configs(self):
        emane_configurations = self.scenario.find("emane_configurations")
        if emane_configurations is None:
            return

        for emane_configuration in emane_configurations.iterchildren():
            node_id = get_int(emane_configuration, "node")
            model_name = emane_configuration.get("model")
            configs = {}

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

            logging.info("reading emane configuration node(%s) model(%s)", node_id, model_name)
            self.session.emane.set_model_config(node_id, model_name, configs)

    def read_mobility_configs(self):
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

            logging.info("reading mobility configuration node(%s) model(%s)", node_id, model_name)
            self.session.mobility.set_model_config(node_id, model_name, configs)

    def read_nodes(self):
        device_elements = self.scenario.find("devices")
        if device_elements is not None:
            for device_element in device_elements.iterchildren():
                self.read_device(device_element)

        network_elements = self.scenario.find("networks")
        if network_elements is not None:
            for network_element in network_elements.iterchildren():
                self.read_network(network_element)

    def read_device(self, device_element):
        node_id = get_int(device_element, "id")
        name = device_element.get("name")
        model = device_element.get("type")
        node_options = NodeOptions(name, model)

        service_elements = device_element.find("services")
        if service_elements is not None:
            node_options.services = [x.get("name") for x in service_elements.iterchildren()]

        position_element = device_element.find("position")
        if position_element is not None:
            x = get_int(position_element, "x")
            y = get_int(position_element, "y")
            if all([x, y]):
                node_options.set_position(x, y)

            lat = get_float(position_element, "lat")
            lon = get_float(position_element, "lon")
            alt = get_float(position_element, "alt")
            if all([lat, lon, alt]):
                node_options.set_location(lat, lon, alt)

        logging.info("reading node id(%s) model(%s) name(%s)", node_id, model, name)
        self.session.add_node(_id=node_id, node_options=node_options)

    def read_network(self, network_element):
        node_id = get_int(network_element, "id")
        name = network_element.get("name")
        node_type = NodeTypes[network_element.get("type")]
        node_options = NodeOptions(name)

        position_element = network_element.find("position")
        if position_element is not None:
            x = get_int(position_element, "x")
            y = get_int(position_element, "y")
            if all([x, y]):
                node_options.set_position(x, y)

            lat = get_float(position_element, "lat")
            lon = get_float(position_element, "lon")
            alt = get_float(position_element, "alt")
            if all([lat, lon, alt]):
                node_options.set_location(lat, lon, alt)

        logging.info("reading node id(%s) node_type(%s) name(%s)", node_id, node_type, name)
        self.session.add_node(_type=node_type, _id=node_id, node_options=node_options)

    def read_links(self):
        link_elements = self.scenario.find("links")
        if link_elements is None:
            return

        node_sets = set()
        for link_element in link_elements.iterchildren():
            node_one = get_int(link_element, "node_one")
            node_two = get_int(link_element, "node_two")
            node_set = frozenset((node_one, node_two))

            interface_one_element = link_element.find("interface_one")
            interface_one = None
            if interface_one_element is not None:
                interface_one = create_interface_data(interface_one_element)

            interface_two_element = link_element.find("interface_two")
            interface_two = None
            if interface_two_element is not None:
                interface_two = create_interface_data(interface_two_element)

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
                logging.info("updating link node_one(%s) node_two(%s): %s", node_one, node_two, link_options)
                self.session.update_link(node_one, node_two, interface_one.id, interface_two.id, link_options)
            else:
                logging.info("adding link node_one(%s) node_two(%s): %s", node_one, node_two, link_options)
                self.session.add_link(node_one, node_two, interface_one, interface_two, link_options)

            node_sets.add(node_set)
