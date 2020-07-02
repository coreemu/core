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
from core.errors import CoreError
from core.nodes.interface import CoreInterface
from core.nodes.network import CtrlNet
from core.xml import corexml

if TYPE_CHECKING:
    from core.emane.emanemanager import EmaneManager
    from core.emane.emanemodel import EmaneModel

_MAC_PREFIX = "02:02"


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


def build_platform_xml(
    emane_manager: "EmaneManager",
    control_net: CtrlNet,
    emane_net: EmaneNet,
    iface: CoreInterface,
    nem_id: int,
) -> None:
    """
    Create platform xml for a specific node.

    :param emane_manager: emane manager with emane
        configurations
    :param control_net: control net node for this emane
        network
    :param emane_net: emane network associated with interface
    :param iface: interface running emane
    :param nem_id: nem id to use for this interface
    :return: the next nem id that can be used for creating platform xml files
    """
    # build nem xml
    nem_definition = nem_file_name(iface)
    nem_element = etree.Element(
        "nem", id=str(nem_id), name=iface.localname, definition=nem_definition
    )

    # check if this is an external transport, get default config if an interface
    # specific one does not exist
    config = emane_manager.get_iface_config(emane_net, iface)
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
        transport_file = transport_file_name(iface, transport_type)
        transport_element = etree.SubElement(
            nem_element, "transport", definition=transport_file
        )
        add_param(transport_element, "device", iface.name)

    # determine platform element to add xml to
    key = iface.node.id
    if iface.transport_type == TransportType.RAW:
        key = "host"
        otadev = control_net.brname
        eventdev = control_net.brname
    else:
        otadev = None
        eventdev = None
    platform_element = etree.Element("platform")
    if otadev:
        emane_manager.set_config("otamanagerdevice", otadev)
    if eventdev:
        emane_manager.set_config("eventservicedevice", eventdev)
    for configuration in emane_manager.emane_config.emulator_config:
        name = configuration.id
        value = emane_manager.get_config(name)
        add_param(platform_element, name, value)
    platform_element.append(nem_element)
    emane_net.setnemid(iface, nem_id)
    mac = _MAC_PREFIX + ":00:00:"
    mac += f"{(nem_id >> 8) & 0xFF:02X}:{nem_id & 0xFF:02X}"
    iface.set_mac(mac)

    doc_name = "platform"
    server = None
    if key == "host":
        file_name = "platform.xml"
        file_path = os.path.join(emane_manager.session.session_dir, file_name)
    else:
        node = iface.node
        file_name = f"{iface.name}-platform.xml"
        file_path = os.path.join(node.nodedir, file_name)
        server = node.server
    create_file(platform_element, doc_name, file_path, server)


def build_model_xmls(
    manager: "EmaneManager", emane_net: EmaneNet, iface: CoreInterface
) -> None:
    """
    Generate emane xml files required for node.

    :param manager: emane manager with emane
        configurations
    :param emane_net: emane network associated with interface
    :param iface: interface to create emane xml for
    :return: nothing
    """
    # build XML for specific interface (NEM) configs
    # check for interface specific emane configuration and write xml files
    config = manager.get_iface_config(emane_net, iface)
    emane_net.model.build_xml_files(config, iface)

    # check transport type needed for interface
    need_virtual = False
    need_raw = False
    vtype = TransportType.VIRTUAL
    rtype = TransportType.RAW
    if iface.transport_type == TransportType.VIRTUAL:
        need_virtual = True
        vtype = iface.transport_type
    else:
        need_raw = True
        rtype = iface.transport_type
    if need_virtual:
        build_transport_xml(manager, emane_net, iface, vtype)
    if need_raw:
        build_transport_xml(manager, emane_net, iface, rtype)


def build_transport_xml(
    manager: "EmaneManager",
    emane_net: EmaneNet,
    iface: CoreInterface,
    transport_type: TransportType,
) -> None:
    """
    Build transport xml file for node and transport type.

    :param manager: emane manager with emane configurations
    :param emane_net: emane network associated with interface
    :param iface: interface to build transport xml for
    :param transport_type: transport type to build xml for
    :return: nothing
    """
    transport_element = etree.Element(
        "transport",
        name=f"{transport_type.value.capitalize()} Transport",
        library=f"trans{transport_type.value.lower()}",
    )
    add_param(transport_element, "bitrate", "0")

    # get emane model cnfiguration
    config = manager.get_iface_config(emane_net, iface)
    flowcontrol = config.get("flowcontrolenable", "0") == "1"
    if transport_type == TransportType.VIRTUAL:
        device_path = "/dev/net/tun_flowctl"
        if not os.path.exists(device_path):
            device_path = "/dev/net/tun"
        add_param(transport_element, "devicepath", device_path)
        if flowcontrol:
            add_param(transport_element, "flowcontrolenable", "on")
    doc_name = "transport"
    node = iface.node
    file_name = transport_file_name(iface, transport_type)
    file_path = os.path.join(node.nodedir, file_name)
    create_file(transport_element, doc_name, file_path)
    manager.session.distributed.execute(
        lambda x: create_file(transport_element, doc_name, file_path, x)
    )


def create_phy_xml(
    emane_model: "EmaneModel",
    config: Dict[str, str],
    file_path: str,
    server: Optional[DistributedServer],
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
    create_file(phy_element, "phy", file_path, server)


def create_mac_xml(
    emane_model: "EmaneModel",
    config: Dict[str, str],
    file_path: str,
    server: Optional[DistributedServer],
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
        raise CoreError("must define emane model library")
    mac_element = etree.Element(
        "mac", name=f"{emane_model.name} MAC", library=emane_model.mac_library
    )
    add_configurations(
        mac_element, emane_model.mac_config, config, emane_model.config_ignore
    )
    create_file(mac_element, "mac", file_path, server)


def create_nem_xml(
    emane_model: "EmaneModel",
    config: Dict[str, str],
    nem_file: str,
    transport_definition: str,
    mac_definition: str,
    phy_definition: str,
    server: Optional[DistributedServer],
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
    create_file(nem_element, "nem", nem_file, server)


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


def transport_file_name(iface: CoreInterface, transport_type: TransportType) -> str:
    """
    Create name for a transport xml file.

    :param iface: interface running emane
    :param transport_type: transport type to generate transport file
    :return: transport xml file name
    """
    return f"{iface.name}-trans-{transport_type.value}.xml"


def nem_file_name(iface: CoreInterface) -> str:
    """
    Return the string name for the NEM XML file, e.g. "eth0-nem.xml"

    :param iface: interface running emane
    :return: nem xm file name
    """
    append = ""
    if iface and iface.transport_type == TransportType.RAW:
        append = "-raw"
    return f"{iface.name}-nem{append}.xml"


def shim_file_name(iface: CoreInterface = None) -> str:
    """
    Return the string name for the SHIM XML file, e.g. "eth0-shim.xml"

    :param iface: interface running emane
    :return: shim xml file name
    """
    return f"{iface.name}-shim.xml"


def mac_file_name(iface: CoreInterface) -> str:
    """
    Return the string name for the MAC XML file, e.g. "eth0-mac.xml"

    :param iface: interface running emane
    :return: mac xml file name
    """
    return f"{iface.name}-mac.xml"


def phy_file_name(iface: CoreInterface) -> str:
    """
    Return the string name for the PHY XML file, e.g. "eth0-phy.xml"

    :param iface: interface running emane
    :return: phy xml file name
    """
    return f"{iface.name}-phy.xml"
