import logging
import os
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

from lxml import etree

from core import utils
from core.config import Configuration
from core.emane.nodes import EmaneNet
from core.emulator.distributed import DistributedServer
from core.emulator.enumerations import TransportType
from core.nodes.interface import CoreInterface
from core.nodes.network import CtrlNet
from core.xml import corexml

if TYPE_CHECKING:
    from core.emane.emanemanager import EmaneManager
    from core.emane.emanemodel import EmaneModel

_hwaddr_prefix = "02:02"


def is_external(config: Dict[str, str]) -> bool:
    """
    Checks if the configuration is for an external transport.

    :param config: configuration to check
    :return: True if external, False otherwise
    """
    return config.get("external") == "1"


def _value_to_params(value: str) -> Optional[Tuple[str]]:
    """
    Helper to convert a parameter to a parameter tuple.

    :param value: value string to convert to tuple
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


def create_file(
    xml_element: etree.Element,
    doc_name: str,
    file_path: str,
    server: DistributedServer = None,
) -> None:
    """
    Create xml file.

    :param xml_element: root element to write to file
    :param doc_name: name to use in the emane doctype
    :param file_path: file path to write xml file to
    :param server: remote server node
            will run on, default is None for localhost
    :return: nothing
    """
    doctype = (
        f'<!DOCTYPE {doc_name} SYSTEM "file:///usr/share/emane/dtd/{doc_name}.dtd">'
    )
    if server is not None:
        temp = NamedTemporaryFile(delete=False)
        create_file(xml_element, doc_name, temp.name)
        temp.close()
        server.remote_put(temp.name, file_path)
        os.unlink(temp.name)
    else:
        corexml.write_xml_file(xml_element, file_path, doctype=doctype)


def add_param(xml_element: etree.Element, name: str, value: str) -> None:
    """
    Add emane configuration parameter to xml element.

    :param xml_element: element to append parameter to
    :param name: name of parameter
    :param value: value for parameter
    :return: nothing
    """
    etree.SubElement(xml_element, "param", name=name, value=value)


def add_configurations(
    xml_element: etree.Element,
    configurations: List[Configuration],
    config: Dict[str, str],
    config_ignore: Set,
) -> None:
    """
    Add emane model configurations to xml element.

    :param xml_element: xml element to add emane configurations to
    :param configurations: configurations to add to xml
    :param config: configuration values
    :param config_ignore: configuration options to ignore
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


def build_node_platform_xml(
    emane_manager: "EmaneManager",
    control_net: CtrlNet,
    node: EmaneNet,
    nem_id: int,
    platform_xmls: Dict[str, etree.Element],
) -> int:
    """
    Create platform xml for a specific node.

    :param emane_manager: emane manager with emane
        configurations
    :param control_net: control net node for this emane
        network
    :param node: node to write platform xml for
    :param nem_id: nem id to use for interfaces for this node
    :param platform_xmls: stores platform xml elements to append nem entries to
    :return: the next nem id that can be used for creating platform xml files
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
        return nem_id

    for iface in node.get_ifaces():
        logging.debug(
            "building platform xml for interface(%s) nem_id(%s)", iface.name, nem_id
        )
        # build nem xml
        nem_definition = nem_file_name(node.model, iface)
        nem_element = etree.Element(
            "nem", id=str(nem_id), name=iface.localname, definition=nem_definition
        )

        # check if this is an external transport, get default config if an interface
        # specific one does not exist
        config = emane_manager.get_iface_config(node.model.id, iface, node.model.name)

        if is_external(config):
            nem_element.set("transport", "external")
            platform_endpoint = "platformendpoint"
            add_param(nem_element, platform_endpoint, config[platform_endpoint])
            transport_endpoint = "transportendpoint"
            add_param(nem_element, transport_endpoint, config[transport_endpoint])
        else:
            # build transport xml
            transport_type = iface.transport_type
            if not transport_type:
                logging.info("warning: %s interface type unsupported!", iface.name)
                transport_type = TransportType.RAW
            transport_file = transport_file_name(node.id, transport_type)
            transport_element = etree.SubElement(
                nem_element, "transport", definition=transport_file
            )

            # add transport parameter
            add_param(transport_element, "device", iface.name)

        # add nem entry
        nem_entries[iface] = nem_element

        # merging code
        key = iface.node.id
        if iface.transport_type == TransportType.RAW:
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

        node.setnemid(iface, nem_id)
        macstr = _hwaddr_prefix + ":00:00:"
        macstr += f"{(nem_id >> 8) & 0xFF:02X}:{nem_id & 0xFF:02X}"
        iface.sethwaddr(macstr)

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
            file_name = f"platform{key}.xml"
            file_path = os.path.join(emane_manager.session.session_dir, file_name)
            linked_node = emane_manager.session.nodes[key]
            create_file(platform_element, doc_name, file_path, linked_node.server)

    return nem_id


def build_xml_files(emane_manager: "EmaneManager", node: EmaneNet) -> None:
    """
    Generate emane xml files required for node.

    :param emane_manager: emane manager with emane
        configurations
    :param node: node to write platform xml for
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
    vtype = TransportType.VIRTUAL
    rtype = TransportType.RAW

    for iface in node.get_ifaces():
        # check for interface specific emane configuration and write xml files
        config = emane_manager.get_iface_config(node.model.id, iface, node.model.name)
        if config:
            node.model.build_xml_files(config, iface)

        # check transport type needed for interface
        if iface.transport_type == TransportType.VIRTUAL:
            need_virtual = True
            vtype = iface.transport_type
        else:
            need_raw = True
            rtype = iface.transport_type

    if need_virtual:
        build_transport_xml(emane_manager, node, vtype)

    if need_raw:
        build_transport_xml(emane_manager, node, rtype)


def build_transport_xml(
    emane_manager: "EmaneManager", node: EmaneNet, transport_type: TransportType
) -> None:
    """
    Build transport xml file for node and transport type.

    :param emane_manager: emane manager with emane
        configurations
    :param node: node to write platform xml for
    :param transport_type: transport type to build xml for
    :return: nothing
    """
    transport_element = etree.Element(
        "transport",
        name=f"{transport_type.value.capitalize()} Transport",
        library=f"trans{transport_type.value.lower()}",
    )

    # add bitrate
    add_param(transport_element, "bitrate", "0")

    # get emane model cnfiguration
    config = emane_manager.get_configs(node.id, node.model.name)
    flowcontrol = config.get("flowcontrolenable", "0") == "1"

    if transport_type == TransportType.VIRTUAL:
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
    emane_manager.session.distributed.execute(
        lambda x: create_file(transport_element, doc_name, file_path, x)
    )


def create_phy_xml(
    emane_model: "EmaneModel",
    config: Dict[str, str],
    file_path: str,
    server: DistributedServer,
) -> None:
    """
    Create the phy xml document.

    :param emane_model: emane model to create xml
    :param config: all current configuration values
    :param file_path: path to write file to
    :param server: remote server node
            will run on, default is None for localhost
    :return: nothing
    """
    phy_element = etree.Element("phy", name=f"{emane_model.name} PHY")
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
        emane_model.session.distributed.execute(
            lambda x: create_file(phy_element, "phy", file_path, x)
        )


def create_mac_xml(
    emane_model: "EmaneModel",
    config: Dict[str, str],
    file_path: str,
    server: DistributedServer,
) -> None:
    """
    Create the mac xml document.

    :param emane_model: emane model to create xml
    :param config: all current configuration values
    :param file_path: path to write file to
    :param server: remote server node
            will run on, default is None for localhost
    :return: nothing
    """
    if not emane_model.mac_library:
        raise ValueError("must define emane model library")

    mac_element = etree.Element(
        "mac", name=f"{emane_model.name} MAC", library=emane_model.mac_library
    )
    add_configurations(
        mac_element, emane_model.mac_config, config, emane_model.config_ignore
    )
    create_file(mac_element, "mac", file_path)
    if server is not None:
        create_file(mac_element, "mac", file_path, server)
    else:
        create_file(mac_element, "mac", file_path)
        emane_model.session.distributed.execute(
            lambda x: create_file(mac_element, "mac", file_path, x)
        )


def create_nem_xml(
    emane_model: "EmaneModel",
    config: Dict[str, str],
    nem_file: str,
    transport_definition: str,
    mac_definition: str,
    phy_definition: str,
    server: DistributedServer,
) -> None:
    """
    Create the nem xml document.

    :param emane_model: emane model to create xml
    :param config: all current configuration values
    :param nem_file: nem file path to write
    :param transport_definition: transport file definition path
    :param mac_definition: mac file definition path
    :param phy_definition: phy file definition path
    :param server: remote server node
            will run on, default is None for localhost
    :return: nothing
    """
    nem_element = etree.Element("nem", name=f"{emane_model.name} NEM")
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
        emane_model.session.distributed.execute(
            lambda x: create_file(nem_element, "nem", nem_file, x)
        )


def create_event_service_xml(
    group: str,
    port: str,
    device: str,
    file_directory: str,
    server: DistributedServer = None,
) -> None:
    """
    Create a emane event service xml file.

    :param group: event group
    :param port: event port
    :param device: event device
    :param file_directory: directory to create  file in
    :param server: remote server node
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


def transport_file_name(node_id: int, transport_type: TransportType) -> str:
    """
    Create name for a transport xml file.

    :param node_id: node id to generate transport file name for
    :param transport_type: transport type to generate transport file
    :return:
    """
    return f"n{node_id}trans{transport_type.value}.xml"


def _basename(emane_model: "EmaneModel", iface: CoreInterface = None) -> str:
    """
    Create name that is leveraged for configuration file creation.

    :param emane_model: emane model to create name for
    :param iface: interface for this model
    :return: basename used for file creation
    """
    name = f"n{emane_model.id}"

    if iface:
        node_id = iface.node.id
        if emane_model.session.emane.get_iface_config(node_id, iface, emane_model.name):
            name = iface.localname.replace(".", "_")

    return f"{name}{emane_model.name}"


def nem_file_name(emane_model: "EmaneModel", iface: CoreInterface = None) -> str:
    """
    Return the string name for the NEM XML file, e.g. "n3rfpipenem.xml"

    :param emane_model: emane model to create file
    :param iface: interface for this model
    :return: nem xml filename
    """
    basename = _basename(emane_model, iface)
    append = ""
    if iface and iface.transport_type == TransportType.RAW:
        append = "_raw"
    return f"{basename}nem{append}.xml"


def shim_file_name(emane_model: "EmaneModel", iface: CoreInterface = None) -> str:
    """
    Return the string name for the SHIM XML file, e.g. "commeffectshim.xml"

    :param emane_model: emane model to create file
    :param iface: interface for this model
    :return: shim xml filename
    """
    name = _basename(emane_model, iface)
    return f"{name}shim.xml"


def mac_file_name(emane_model: "EmaneModel", iface: CoreInterface = None) -> str:
    """
    Return the string name for the MAC XML file, e.g. "n3rfpipemac.xml"

    :param emane_model: emane model to create file
    :param iface: interface for this model
    :return: mac xml filename
    """
    name = _basename(emane_model, iface)
    return f"{name}mac.xml"


def phy_file_name(emane_model: "EmaneModel", iface: CoreInterface = None) -> str:
    """
    Return the string name for the PHY XML file, e.g. "n3rfpipephy.xml"

    :param emane_model: emane model to create file
    :param iface: interface for this model
    :return: phy xml filename
    """
    name = _basename(emane_model, iface)
    return f"{name}phy.xml"
