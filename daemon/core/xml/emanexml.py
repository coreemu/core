import logging
import os
from tempfile import NamedTemporaryFile

from lxml import etree

from core import utils
from core.nodes.ipaddress import MacAddress
from core.xml import corexml

_hwaddr_prefix = "02:02"


def is_external(config):
    """
    Checks if the configuration is for an external transport.

    :param dict config: configuration to check
    :return: True if external, False otherwise
    :rtype: bool
    """
    return config.get("external") == "1"


def _value_to_params(value):
    """
    Helper to convert a parameter to a parameter tuple.

    :param str value: value string to convert to tuple
    :return: parameter tuple, None otherwise
    """
    try:
        values = utils.make_tuple_fromstr(value, str)

        if not hasattr(values, "__iter__"):
            return None

        if len(values) < 2:
            return None

        return values

    except SyntaxError:
        logging.exception("error in value string to param list")
    return None


def create_file(xml_element, doc_name, file_path, server=None):
    """
    Create xml file.

    :param lxml.etree.Element xml_element: root element to write to file
    :param str doc_name: name to use in the emane doctype
    :param str file_path: file path to write xml file to
    :param core.emulator.distributed.DistributedServer server: remote server node
            will run on, default is None for localhost
    :return: nothing
    """
    doctype = (
        '<!DOCTYPE %(doc_name)s SYSTEM "file:///usr/share/emane/dtd/%(doc_name)s.dtd">'
        % {"doc_name": doc_name}
    )
    if server is not None:
        temp = NamedTemporaryFile(delete=False)
        create_file(xml_element, doc_name, temp.name)
        temp.close()
        server.remote_put(temp.name, file_path)
        os.unlink(temp.name)
    else:
        corexml.write_xml_file(xml_element, file_path, doctype=doctype)


def add_param(xml_element, name, value):
    """
    Add emane configuration parameter to xml element.

    :param lxml.etree.Element xml_element: element to append parameter to
    :param str name: name of parameter
    :param str value: value for parameter
    :return: nothing
    """
    etree.SubElement(xml_element, "param", name=name, value=value)


def add_configurations(xml_element, configurations, config, config_ignore):
    """
    Add emane model configurations to xml element.

    :param lxml.etree.Element xml_element: xml element to add emane configurations to
    :param list[core.config.Configuration] configurations: configurations to add to xml
    :param dict config: configuration values
    :param set config_ignore: configuration options to ignore
    :return:
    """
    for configuration in configurations:
        # ignore custom configurations
        name = configuration.id
        if name in config_ignore:
            continue

        # check if value is a multi param
        value = str(config[name])
        params = _value_to_params(value)
        if params:
            params_element = etree.SubElement(xml_element, "paramlist", name=name)
            for param in params:
                etree.SubElement(params_element, "item", value=param)
        else:
            add_param(xml_element, name, value)


def build_node_platform_xml(emane_manager, control_net, node, nem_id, platform_xmls):
    """
    Create platform xml for a specific node.

    :param core.emane.emanemanager.EmaneManager emane_manager: emane manager with emane
        configurations
    :param core.nodes.network.CtrlNet control_net: control net node for this emane
        network
    :param core.emane.nodes.EmaneNet node: node to write platform xml for
    :param int nem_id: nem id to use for interfaces for this node
    :param dict platform_xmls: stores platform xml elements to append nem entries to
    :return: the next nem id that can be used for creating platform xml files
    :rtype: int
    """
    logging.debug(
        "building emane platform xml for node(%s) nem_id(%s): %s",
        node,
        nem_id,
        node.name,
    )
    nem_entries = {}

    if node.model is None:
        logging.warning("warning: EMANE network %s has no associated model", node.name)
        return nem_entries

    for netif in node.netifs():
        logging.debug(
            "building platform xml for interface(%s) nem_id(%s)", netif.name, nem_id
        )
        # build nem xml
        nem_definition = nem_file_name(node.model, netif)
        nem_element = etree.Element(
            "nem", id=str(nem_id), name=netif.localname, definition=nem_definition
        )

        # check if this is an external transport, get default config if an interface
        # specific one does not exist
        config = emane_manager.getifcconfig(node.model.id, netif, node.model.name)

        if is_external(config):
            nem_element.set("transport", "external")
            platform_endpoint = "platformendpoint"
            add_param(nem_element, platform_endpoint, config[platform_endpoint])
            transport_endpoint = "transportendpoint"
            add_param(nem_element, transport_endpoint, config[transport_endpoint])
        else:
            # build transport xml
            transport_type = netif.transport_type
            if not transport_type:
                logging.info("warning: %s interface type unsupported!", netif.name)
                transport_type = "raw"
            transport_file = transport_file_name(node.id, transport_type)
            transport_element = etree.SubElement(
                nem_element, "transport", definition=transport_file
            )

            # add transport parameter
            add_param(transport_element, "device", netif.name)

        # add nem entry
        nem_entries[netif] = nem_element

        # merging code
        key = netif.node.id
        if netif.transport_type == "raw":
            key = "host"
            otadev = control_net.brname
            eventdev = control_net.brname
        else:
            otadev = None
            eventdev = None

        platform_element = platform_xmls.get(key)
        if platform_element is None:
            platform_element = etree.Element("platform")

            if otadev:
                emane_manager.set_config("otamanagerdevice", otadev)

            if eventdev:
                emane_manager.set_config("eventservicedevice", eventdev)

            # append all platform options (except starting id) to doc
            for configuration in emane_manager.emane_config.emulator_config:
                name = configuration.id
                if name == "platform_id_start":
                    continue

                value = emane_manager.get_config(name)
                add_param(platform_element, name, value)

            # add platform xml
            platform_xmls[key] = platform_element

        platform_element.append(nem_element)

        node.setnemid(netif, nem_id)
        macstr = _hwaddr_prefix + ":00:00:"
        macstr += "%02X:%02X" % ((nem_id >> 8) & 0xFF, nem_id & 0xFF)
        netif.sethwaddr(MacAddress.from_string(macstr))

        # increment nem id
        nem_id += 1

    doc_name = "platform"
    for key in sorted(platform_xmls.keys()):
        platform_element = platform_xmls[key]
        if key == "host":
            file_name = "platform.xml"
            file_path = os.path.join(emane_manager.session.session_dir, file_name)
            create_file(platform_element, doc_name, file_path)
        else:
            file_name = "platform%d.xml" % key
            file_path = os.path.join(emane_manager.session.session_dir, file_name)
            linked_node = emane_manager.session.nodes[key]
            create_file(platform_element, doc_name, file_path, linked_node.server)

    return nem_id


def build_xml_files(emane_manager, node):
    """
    Generate emane xml files required for node.

    :param core.emane.emanemanager.EmaneManager emane_manager: emane manager with emane
        configurations
    :param core.emane.nodes.EmaneNet node: node to write platform xml for
    :return: nothing
    """
    logging.debug("building all emane xml for node(%s): %s", node, node.name)
    if node.model is None:
        return

    # get model configurations
    config = emane_manager.get_configs(node.model.id, node.model.name)
    if not config:
        return

    # build XML for overall network EMANE configs
    node.model.build_xml_files(config)

    # build XML for specific interface (NEM) configs
    need_virtual = False
    need_raw = False
    vtype = "virtual"
    rtype = "raw"

    for netif in node.netifs():
        # check for interface specific emane configuration and write xml files
        config = emane_manager.getifcconfig(node.model.id, netif, node.model.name)
        if config:
            node.model.build_xml_files(config, netif)

        # check transport type needed for interface
        if "virtual" in netif.transport_type:
            need_virtual = True
            vtype = netif.transport_type
        else:
            need_raw = True
            rtype = netif.transport_type

    if need_virtual:
        build_transport_xml(emane_manager, node, vtype)

    if need_raw:
        build_transport_xml(emane_manager, node, rtype)


def build_transport_xml(emane_manager, node, transport_type):
    """
    Build transport xml file for node and transport type.

    :param core.emane.emanemanager.EmaneManager emane_manager: emane manager with emane
        configurations
    :param core.emane.nodes.EmaneNet node: node to write platform xml for
    :param str transport_type: transport type to build xml for
    :return: nothing
    """
    transport_element = etree.Element(
        "transport",
        name="%s Transport" % transport_type.capitalize(),
        library="trans%s" % transport_type.lower(),
    )

    # add bitrate
    add_param(transport_element, "bitrate", "0")

    # get emane model cnfiguration
    config = emane_manager.get_configs(node.id, node.model.name)
    flowcontrol = config.get("flowcontrolenable", "0") == "1"

    if "virtual" in transport_type.lower():
        device_path = "/dev/net/tun_flowctl"
        if not os.path.exists(device_path):
            device_path = "/dev/net/tun"
        add_param(transport_element, "devicepath", device_path)

        if flowcontrol:
            add_param(transport_element, "flowcontrolenable", "on")

    doc_name = "transport"
    file_name = transport_file_name(node.id, transport_type)
    file_path = os.path.join(emane_manager.session.session_dir, file_name)
    create_file(transport_element, doc_name, file_path)
    for name in emane_manager.session.servers:
        server = emane_manager.session.servers[name]
        create_file(transport_element, doc_name, file_path, server)


def create_phy_xml(emane_model, config, file_path, server):
    """
    Create the phy xml document.

    :param core.emane.emanemodel.EmaneModel emane_model: emane model to create xml
    :param dict config: all current configuration values
    :param str file_path: path to write file to
    :param core.emulator.distributed.DistributedServer server: remote server node
            will run on, default is None for localhost
    :return: nothing
    """
    phy_element = etree.Element("phy", name="%s PHY" % emane_model.name)
    if emane_model.phy_library:
        phy_element.set("library", emane_model.phy_library)

    add_configurations(
        phy_element, emane_model.phy_config, config, emane_model.config_ignore
    )
    create_file(phy_element, "phy", file_path)
    if server is not None:
        create_file(phy_element, "phy", file_path, server)
    else:
        create_file(phy_element, "phy", file_path)
        for name in emane_model.session.servers:
            server = emane_model.session.servers[name]
            create_file(phy_element, "phy", file_path, server)


def create_mac_xml(emane_model, config, file_path, server):
    """
    Create the mac xml document.

    :param core.emane.emanemodel.EmaneModel emane_model: emane model to create xml
    :param dict config: all current configuration values
    :param str file_path: path to write file to
    :param core.emulator.distributed.DistributedServer server: remote server node
            will run on, default is None for localhost
    :return: nothing
    """
    if not emane_model.mac_library:
        raise ValueError("must define emane model library")

    mac_element = etree.Element(
        "mac", name="%s MAC" % emane_model.name, library=emane_model.mac_library
    )
    add_configurations(
        mac_element, emane_model.mac_config, config, emane_model.config_ignore
    )
    create_file(mac_element, "mac", file_path)
    if server is not None:
        create_file(mac_element, "mac", file_path, server)
    else:
        create_file(mac_element, "mac", file_path)
        for name in emane_model.session.servers:
            server = emane_model.session.servers[name]
            create_file(mac_element, "mac", file_path, server)


def create_nem_xml(
    emane_model,
    config,
    nem_file,
    transport_definition,
    mac_definition,
    phy_definition,
    server,
):
    """
    Create the nem xml document.

    :param core.emane.emanemodel.EmaneModel emane_model: emane model to create xml
    :param dict config: all current configuration values
    :param str nem_file: nem file path to write
    :param str transport_definition: transport file definition path
    :param str mac_definition: mac file definition path
    :param str phy_definition: phy file definition path
    :param core.emulator.distributed.DistributedServer server: remote server node
            will run on, default is None for localhost
    :return: nothing
    """
    nem_element = etree.Element("nem", name="%s NEM" % emane_model.name)
    if is_external(config):
        nem_element.set("type", "unstructured")
    else:
        etree.SubElement(nem_element, "transport", definition=transport_definition)
    etree.SubElement(nem_element, "mac", definition=mac_definition)
    etree.SubElement(nem_element, "phy", definition=phy_definition)
    if server is not None:
        create_file(nem_element, "nem", nem_file, server)
    else:
        create_file(nem_element, "nem", nem_file)
        for name in emane_model.session.servers:
            server = emane_model.session.servers[name]
            create_file(nem_element, "nem", nem_file, server)


def create_event_service_xml(group, port, device, file_directory, server=None):
    """
    Create a emane event service xml file.

    :param str group: event group
    :param str port: event port
    :param str device: event device
    :param str file_directory: directory to create  file in
    :param core.emulator.distributed.DistributedServer server: remote server node
            will run on, default is None for localhost
    :return: nothing
    """
    event_element = etree.Element("emaneeventmsgsvc")
    for name, value in (
        ("group", group),
        ("port", port),
        ("device", device),
        ("mcloop", "1"),
        ("ttl", "32"),
    ):
        sub_element = etree.SubElement(event_element, name)
        sub_element.text = value
    file_name = "libemaneeventservice.xml"
    file_path = os.path.join(file_directory, file_name)
    create_file(event_element, "emaneeventmsgsvc", file_path, server)


def transport_file_name(node_id, transport_type):
    """
    Create name for a transport xml file.

    :param int node_id: node id to generate transport file name for
    :param str transport_type: transport type to generate transport file
    :return:
    """
    return "n%strans%s.xml" % (node_id, transport_type)


def _basename(emane_model, interface=None):
    """
    Create name that is leveraged for configuration file creation.

    :param interface: interface for this model
    :return: basename used for file creation
    :rtype: str
    """
    name = "n%s" % emane_model.id

    if interface:
        node_id = interface.node.id
        if emane_model.session.emane.getifcconfig(node_id, interface, emane_model.name):
            name = interface.localname.replace(".", "_")

    return "%s%s" % (name, emane_model.name)


def nem_file_name(emane_model, interface=None):
    """
    Return the string name for the NEM XML file, e.g. "n3rfpipenem.xml"

    :param core.emane.emanemodel.EmaneModel emane_model: emane model to create file
    :param interface: interface for this model
    :return: nem xml filename
    :rtype: str
    """
    basename = _basename(emane_model, interface)
    append = ""
    if interface and interface.transport_type == "raw":
        append = "_raw"
    return "%snem%s.xml" % (basename, append)


def shim_file_name(emane_model, interface=None):
    """
    Return the string name for the SHIM XML file, e.g. "commeffectshim.xml"

    :param core.emane.emanemodel.EmaneModel emane_model: emane model to create file
    :param interface: interface for this model
    :return: shim xml filename
    :rtype: str
    """
    return "%sshim.xml" % _basename(emane_model, interface)


def mac_file_name(emane_model, interface=None):
    """
    Return the string name for the MAC XML file, e.g. "n3rfpipemac.xml"

    :param core.emane.emanemodel.EmaneModel emane_model: emane model to create file
    :param interface: interface for this model
    :return: mac xml filename
    :rtype: str
    """
    return "%smac.xml" % _basename(emane_model, interface)


def phy_file_name(emane_model, interface=None):
    """
    Return the string name for the PHY XML file, e.g. "n3rfpipephy.xml"

    :param core.emane.emanemodel.EmaneModel emane_model: emane model to create file
    :param interface: interface for this model
    :return: phy xml filename
    :rtype: str
    """
    return "%sphy.xml" % _basename(emane_model, interface)
