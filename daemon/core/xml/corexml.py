from lxml import etree

from core import coreobj
from core.enumerations import NodeTypes
from core.misc import ipaddress
from core.misc import nodeutils
from core.netns import nodes


def add_attribute(element, name, value):
    if value is not None:
        element.set(name, str(value))


def create_emane_config(node_id, emane_config, config):
    emane_configuration = etree.Element("emane_configuration")
    add_attribute(emane_configuration, "node", node_id)
    add_attribute(emane_configuration, "model", "emane")
    emulator_element = etree.SubElement(emane_configuration, "emulator")
    for emulator_config in emane_config.emulator_config:
        config_element = etree.SubElement(emulator_element, "configuration")
        value = config[emulator_config.id]
        add_attribute(config_element, "name", emulator_config.id)
        add_attribute(config_element, "value", value)

    nem_element = etree.SubElement(emane_configuration, "nem")
    for nem_config in emane_config.nem_config:
        config_element = etree.SubElement(nem_element, "configuration")
        value = config[nem_config.id]
        add_attribute(config_element, "name", nem_config.id)
        add_attribute(config_element, "value", value)

    return emane_configuration


def create_emane_model_config(node_id, model, config):
    emane_element = etree.Element("emane_configuration")
    add_attribute(emane_element, "node", node_id)
    add_attribute(emane_element, "model", model.name)

    mac_element = etree.SubElement(emane_element, "mac")
    for mac_config in model.mac_config:
        config_element = etree.SubElement(mac_element, "configuration")
        value = config[mac_config.id]
        add_attribute(config_element, "name", mac_config.id)
        add_attribute(config_element, "value", value)

    phy_element = etree.SubElement(emane_element, "phy")
    for phy_config in model.phy_config:
        config_element = etree.SubElement(phy_element, "configuration")
        value = config[phy_config.id]
        add_attribute(config_element, "name", phy_config.id)
        add_attribute(config_element, "value", value)

    return emane_element


def get_endpoints(node):
    endpoints = []
    for interface in node.netifs(sort=True):
        endpoint = get_endpoint(node, interface)
        endpoints.append(endpoint)
    return endpoints


def get_endpoint(node, interface):
    l2devport = None
    othernet = getattr(interface, "othernet", None)

    # reference interface of node that is part of this network
    if interface.net.objid == node.objid and interface.node:
        params = interface.getparams()
        if nodeutils.is_node(interface.net, (NodeTypes.HUB, NodeTypes.SWITCH)):
            l2devport = "%s/e%s" % (interface.net.name, interface.netindex)
        endpoint_id = "%s/%s" % (interface.node.name, interface.name)
        endpoint = Endpoint(
            node,
            interface,
            "interface",
            endpoint_id,
            l2devport,
            params
        )
    # references another node connected to this network
    elif othernet and othernet.objid == node.objid:
        interface.swapparams("_params_up")
        params = interface.getparams()
        interface.swapparams("_params_up")
        l2devport = "%s/e%s" % (othernet.name, interface.netindex)
        endpoint_id = "%s/%s/%s" % (node.name, interface.node.name, interface.netindex)
        endpoint = Endpoint(
            interface.net,
            interface,
            "interface",
            endpoint_id,
            l2devport,
            params
        )
    else:
        endpoint = Endpoint(
            node,
            interface,
        )

    return endpoint


def get_downstream_l2_devices(node):
    all_endpoints = []
    l2_devices = [node]
    current_endpoint = get_endpoints(node)
    all_endpoints.extend(current_endpoint)
    for endpoint in current_endpoint:
        if endpoint.type and endpoint.network.objid != node.objid:
            new_l2_devices, new_endpoints = get_downstream_l2_devices(endpoint.network)
            l2_devices.extend(new_l2_devices)
            all_endpoints.extend(new_endpoints)
    return l2_devices, all_endpoints


def create_link_element(link_data):
    link_element = etree.Element("link")
    add_attribute(link_element, "node_one", link_data.node1_id)
    add_attribute(link_element, "node_two", link_data.node2_id)

    # check for interface one
    interface_one = etree.Element("interface_one")
    add_attribute(interface_one, "id", link_data.interface1_id)
    add_attribute(interface_one, "name", link_data.interface1_name)
    add_attribute(interface_one, "mac", link_data.interface1_mac)
    add_attribute(interface_one, "ip4", link_data.interface1_ip4)
    add_attribute(interface_one, "ip4_mask", link_data.interface1_ip4_mask)
    add_attribute(interface_one, "ip6", link_data.interface1_ip6)
    add_attribute(interface_one, "ip6_mask", link_data.interface1_ip6_mask)
    if interface_one.items():
        link_element.append(interface_one)

    # check for interface two
    interface_two = etree.Element("interface_two")
    add_attribute(interface_two, "id", link_data.interface2_id)
    add_attribute(interface_two, "name", link_data.interface2_name)
    add_attribute(interface_two, "mac", link_data.interface2_mac)
    add_attribute(interface_two, "ip4", link_data.interface2_ip4)
    add_attribute(interface_two, "ip4_mask", link_data.interface2_ip4_mask)
    add_attribute(interface_two, "ip6", link_data.interface2_ip6)
    add_attribute(interface_two, "ip6_mask", link_data.interface2_ip6_mask)
    if interface_two.items():
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
    if options.items():
        link_element.append(options)

    return link_element


class Endpoint(object):
    def __init__(self, network, interface, _type=None, _id=None, l2devport=None, params=None):
        self.network = network
        self.interface = interface
        self.type = _type
        self.id = _id
        self.l2devport = l2devport
        self.params = params


class NodeElement(object):
    def __init__(self, session, node, element_name):
        self.session = session
        self.node = node
        self.element = etree.Element(element_name)
        add_attribute(self.element, "id", node.objid)
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


class InterfaceElement(object):
    def __init__(self, session, node, interface):
        self.session = session
        self.node = node
        self.interface = interface
        self.element = etree.Element("interface")
        add_attribute(self.element, "id", interface.netindex)
        add_attribute(self.element, "name", interface.name)
        mac = etree.SubElement(self.element, "mac")
        mac.text = str(interface.hwaddr)
        self.add_mtu()
        self.addresses = etree.SubElement(self.element, "addresses")
        self.add_addresses()
        self.add_model()

    def add_mtu(self):
        # check to add mtu
        if self.interface.mtu and self.interface.mtu != 1500:
            add_attribute(self.element, "mtu", self.interface.mtu)

    def add_model(self):
        # check for emane specific interface configuration
        net_model = None
        if self.interface.net and hasattr(self.interface.net, "model"):
            net_model = self.interface.net.model

        if net_model and net_model.name.startswith("emane_"):
            config = self.session.emane.getifcconfig(self.node.objid, self.interface, net_model.name)
            if config:
                emane_element = create_emane_model_config(net_model, config)
                self.element.append(emane_element)

    def add_addresses(self):
        for address in self.interface.addrlist:
            ip, mask = address.split("/")
            if ipaddress.is_ipv4_address(ip):
                address_type = "IPv4"
            else:
                address_type = "IPv6"
            address_element = etree.SubElement(self.addresses, "address")
            add_attribute(address_element, "type", address_type)
            address_element.text = str(address)


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
        for file_name, data in self.service.config_data.iteritems():
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
        # self.add_interfaces()
        self.add_services()

    def add_services(self):
        service_elements = etree.Element("services")
        for service in self.node.services:
            etree.SubElement(service_elements, "service", name=service.name)

        if service_elements.getchildren():
            self.element.append(service_elements)

    def add_interfaces(self):
        interfaces = etree.Element("interfaces")
        for interface in self.node.netifs(sort=True):
            interface_element = InterfaceElement(self.session, self.node, interface)
            interfaces.append(interface_element.element)

        if interfaces.getchildren():
            self.element.append(interfaces)


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
        # self.endpoints = get_endpoints(self.node)
        # self.l2_devices = self.get_l2_devices()
        # self.add_configs()

    def add_type(self):
        if self.node.apitype:
            node_type = NodeTypes(self.node.apitype).name
        else:
            node_type = self.node.__class__.__name__
        add_attribute(self.element, "type", node_type)

    def get_l2_devices(self):
        l2_devices = []
        found_l2_devices = []
        found_endpoints = []
        if nodeutils.is_node(self.node, (NodeTypes.SWITCH, NodeTypes.HUB)):
            for endpoint in self.endpoints:
                if endpoint.type and endpoint.network.objid != self.node.objid:
                    downstream_l2_devices, downstream_endpoints = get_downstream_l2_devices(endpoint.network)
                    found_l2_devices.extend(downstream_l2_devices)
                    found_endpoints.extend(downstream_endpoints)

            for l2_device in found_l2_devices:
                pass

            self.endpoints.extend(found_endpoints)
        return l2_devices

    def add_peer_to_peer_config(self):
        pass

    def add_switch_hub_tunnel_config(self):
        pass

    def add_configs(self):
        if nodeutils.is_node(self.node, NodeTypes.PEER_TO_PEER):
            self.add_peer_to_peer_config()
        elif nodeutils.is_node(self.node, (NodeTypes.SWITCH, NodeTypes.HUB, NodeTypes.TUNNEL)):
            self.add_switch_hub_tunnel_config()


class CoreXmlWriter(object):
    def __init__(self, session):
        self.session = session
        self.scenario = None
        self.networks = None
        self.devices = None

    def write(self, file_name):
        self.scenario = etree.Element("scenario", name=file_name)
        self.networks = etree.SubElement(self.scenario, "networks")
        self.devices = etree.SubElement(self.scenario, "devices")
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

        with open(file_name, "w") as xml_file:
            data = etree.tostring(self.scenario, xml_declaration=True, pretty_print=True, encoding="UTF-8")
            xml_file.write(data)

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
        # options
        options = etree.Element("session_options")
        # TODO: should we just save the current config regardless, since it may change?
        options_config = self.session.options.get_configs()
        for _id, default_value in self.session.options.default_values().iteritems():
            value = options_config[_id]
            if value != default_value:
                option = etree.SubElement(options, "option")
                add_attribute(option, "name", _id)
                add_attribute(option, "value", value)

        if options.getchildren():
            self.scenario.append(options)

    def write_session_metadata(self):
        # metadata
        metadata = etree.Element("session_metadata")
        for _id, value in self.session.metadata.get_configs().iteritems():
            data = etree.SubElement(metadata, "data")
            add_attribute(data, "name", _id)
            add_attribute(data, "value", value)

        if metadata.getchildren():
            self.scenario.append(metadata)

    def write_emane_configs(self):
        emane_configurations = etree.Element("emane_configurations")
        for node_id in self.session.emane.nodes():
            all_configs = self.session.emane.get_all_configs(node_id)
            for model_name, config in all_configs.iteritems():
                if model_name == -1:
                    emane_configuration = create_emane_config(node_id, self.session.emane_config, config)
                else:
                    model = self.session.emane.models[model_name]
                    emane_configuration = create_emane_model_config(node_id, model, config)
                emane_configurations.append(emane_configuration)

        if emane_configurations.getchildren():
            self.scenario.append(emane_configurations)

    def write_mobility_configs(self):
        mobility_configurations = etree.Element("mobility_configurations")
        for node_id in self.session.mobility.nodes():
            all_configs = self.session.emane.get_all_configs(node_id)
            for model_name, config in all_configs.iteritems():
                mobility_configuration = etree.SubElement(mobility_configurations, "mobility_configuration")
                add_attribute(mobility_configuration, "node", node_id)
                add_attribute(mobility_configuration, "model", model_name)
                for name, value in config.iteritems():
                    config_element = etree.SubElement(mobility_configuration, "configuration")
                    add_attribute(config_element, "name", name)
                    add_attribute(config_element, "value", value)

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
        for node_type, services in self.session.services.default_services.iteritems():
            node_type = etree.SubElement(node_types, "node", type=node_type)
            for service in services:
                etree.SubElement(node_type, "service", name=service)

        if node_types.getchildren():
            self.scenario.append(node_types)

    def write_nodes(self):
        links = []
        for node in self.session.objects.itervalues():
            # network node
            if isinstance(node, coreobj.PyCoreNet) and not nodeutils.is_node(node, NodeTypes.CONTROL_NET):
                self.write_network(node)
            # device node
            elif isinstance(node, nodes.PyCoreNode):
                self.write_device(node)

            # add known links
            links.extend(node.all_link_data(0))

        return links

    def write_network(self, node):
        # ignore p2p and other nodes that are not part of the api
        if not node.apitype:
            return

        # ignore nodes tied to a different network
        if nodeutils.is_node(node, (NodeTypes.SWITCH, NodeTypes.HUB)):
            for netif in node.netifs(sort=True):
                othernet = getattr(netif, "othernet", None)
                if othernet and othernet.objid != node.objid:
                    return

        network = NetworkElement(self.session, node)
        self.networks.append(network.element)

    def write_links(self, links):
        link_elements = etree.Element("links")
        # add link data
        for link_data in links:
            # skip basic range links
            if not link_data.interface1_id and not link_data.interface2_id:
                continue

            link_element = create_link_element(link_data)
            link_elements.append(link_element)

        if link_elements.getchildren():
            self.scenario.append(link_elements)

    def write_device(self, node):
        device = DeviceElement(self.session, node)
        self.devices.append(device.element)
