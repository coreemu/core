import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

from lxml import etree

from core import utils
from core.config import Configuration
from core.emane.nodes import EmaneNet
from core.emulator.distributed import DistributedServer
from core.errors import CoreError
from core.nodes.base import CoreNode, CoreNodeBase
from core.nodes.interface import CoreInterface
from core.xml import corexml

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
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
        logger.exception("error in value string to param list")
    return None


def create_file(
    xml_element: etree.Element,
    doc_name: str,
    file_path: Path,
    server: DistributedServer = None,
) -> None:
    """
    Create xml file.

    :param xml_element: root element to write to file
    :param doc_name: name to use in the emane doctype
    :param file_path: file path to write xml file to
    :param server: remote server to create file on
    :return: nothing
    """
    doctype = (
        f'<!DOCTYPE {doc_name} SYSTEM "file:///usr/share/emane/dtd/{doc_name}.dtd">'
    )
    if server:
        temp = NamedTemporaryFile(delete=False)
        temp_path = Path(temp.name)
        corexml.write_xml_file(xml_element, temp_path, doctype=doctype)
        temp.close()
        server.remote_put(temp_path, file_path)
        temp_path.unlink()
    else:
        corexml.write_xml_file(xml_element, file_path, doctype=doctype)


def create_node_file(
    node: CoreNodeBase, xml_element: etree.Element, doc_name: str, file_name: str
) -> None:
    """
    Create emane xml for an interface.

    :param node: node running emane
    :param xml_element: root element to write to file
    :param doc_name: name to use in the emane doctype
    :param file_name: name of xml file
    :return:
    """
    if isinstance(node, CoreNode):
        file_path = node.directory / file_name
    else:
        file_path = node.session.directory / file_name
    create_file(xml_element, doc_name, file_path, node.server)


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
    nem_id: int,
    nem_port: int,
    emane_net: EmaneNet,
    iface: CoreInterface,
    config: Dict[str, str],
) -> None:
    """
    Create platform xml for a nem/interface.

    :param nem_id: nem id for current node/interface
    :param nem_port: control port to configure for emane
    :param emane_net: emane network associate with node and interface
    :param iface: node interface to create platform xml for
    :param config: emane configuration for interface
    :return: nothing
    """
    # create top level platform element
    platform_element = etree.Element("platform")
    for configuration in emane_net.model.platform_config:
        name = configuration.id
        value = config[configuration.id]
        add_param(platform_element, name, value)
    add_param(
        platform_element, emane_net.model.platform_controlport, f"0.0.0.0:{nem_port}"
    )

    # build nem xml
    nem_definition = nem_file_name(iface)
    nem_element = etree.Element(
        "nem", id=str(nem_id), name=iface.localname, definition=nem_definition
    )

    # create model based xml files
    emane_net.model.build_xml_files(config, iface)

    # check if this is an external transport
    if is_external(config):
        nem_element.set("transport", "external")
        platform_endpoint = "platformendpoint"
        add_param(nem_element, platform_endpoint, config[platform_endpoint])
        transport_endpoint = "transportendpoint"
        add_param(nem_element, transport_endpoint, config[transport_endpoint])

    # define transport element
    transport_name = transport_file_name(iface)
    transport_element = etree.SubElement(
        nem_element, "transport", definition=transport_name
    )
    add_param(transport_element, "device", iface.name)

    # add nem element to platform element
    platform_element.append(nem_element)

    # generate and assign interface mac address based on nem id
    mac = _MAC_PREFIX + ":00:00:"
    mac += f"{(nem_id >> 8) & 0xFF:02X}:{nem_id & 0xFF:02X}"
    iface.set_mac(mac)

    doc_name = "platform"
    file_name = platform_file_name(iface)
    create_node_file(iface.node, platform_element, doc_name, file_name)


def create_transport_xml(iface: CoreInterface, config: Dict[str, str]) -> None:
    """
    Build transport xml file for node and transport type.

    :param iface: interface to build transport xml for
    :param config: all current configuration values
    :return: nothing
    """
    transport_type = iface.transport_type
    transport_element = etree.Element(
        "transport",
        name=f"{transport_type.value.capitalize()} Transport",
        library=f"trans{transport_type.value.lower()}",
    )
    add_param(transport_element, "bitrate", "0")

    # get emane model cnfiguration
    flowcontrol = config.get("flowcontrolenable", "0") == "1"
    if isinstance(iface.node, CoreNode):
        device_path = "/dev/net/tun_flowctl"
        if not iface.node.path_exists(device_path):
            device_path = "/dev/net/tun"
        add_param(transport_element, "devicepath", device_path)
        if flowcontrol:
            add_param(transport_element, "flowcontrolenable", "on")
    doc_name = "transport"
    transport_name = transport_file_name(iface)
    create_node_file(iface.node, transport_element, doc_name, transport_name)


def create_phy_xml(
    emane_model: "EmaneModel", iface: CoreInterface, config: Dict[str, str]
) -> None:
    """
    Create the phy xml document.

    :param emane_model: emane model to create xml
    :param iface: interface to create xml for
    :param config: all current configuration values
    :return: nothing
    """
    phy_element = etree.Element("phy", name=f"{emane_model.name} PHY")
    if emane_model.phy_library:
        phy_element.set("library", emane_model.phy_library)
    add_configurations(
        phy_element, emane_model.phy_config, config, emane_model.config_ignore
    )
    file_name = phy_file_name(iface)
    create_node_file(iface.node, phy_element, "phy", file_name)


def create_mac_xml(
    emane_model: "EmaneModel", iface: CoreInterface, config: Dict[str, str]
) -> None:
    """
    Create the mac xml document.

    :param emane_model: emane model to create xml
    :param iface: interface to create xml for
    :param config: all current configuration values
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
    file_name = mac_file_name(iface)
    create_node_file(iface.node, mac_element, "mac", file_name)


def create_nem_xml(
    emane_model: "EmaneModel", iface: CoreInterface, config: Dict[str, str]
) -> None:
    """
    Create the nem xml document.

    :param emane_model: emane model to create xml
    :param iface: interface to create xml for
    :param config: all current configuration values
    :return: nothing
    """
    nem_element = etree.Element("nem", name=f"{emane_model.name} NEM")
    if is_external(config):
        nem_element.set("type", "unstructured")
    else:
        transport_name = transport_file_name(iface)
        etree.SubElement(nem_element, "transport", definition=transport_name)
    mac_name = mac_file_name(iface)
    etree.SubElement(nem_element, "mac", definition=mac_name)
    phy_name = phy_file_name(iface)
    etree.SubElement(nem_element, "phy", definition=phy_name)
    nem_name = nem_file_name(iface)
    create_node_file(iface.node, nem_element, "nem", nem_name)


def create_event_service_xml(
    group: str,
    port: str,
    device: str,
    file_directory: Path,
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
    file_path = file_directory / "libemaneeventservice.xml"
    create_file(event_element, "emaneeventmsgsvc", file_path, server)


def transport_file_name(iface: CoreInterface) -> str:
    """
    Create name for a transport xml file.

    :param iface: interface running emane
    :return: transport xml file name
    """
    return f"{iface.name}-trans-{iface.transport_type.value}.xml"


def nem_file_name(iface: CoreInterface) -> str:
    """
    Return the string name for the NEM XML file, e.g. "eth0-nem.xml"

    :param iface: interface running emane
    :return: nem xm file name
    """
    append = "-raw" if not isinstance(iface.node, CoreNode) else ""
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


def platform_file_name(iface: CoreInterface) -> str:
    return f"{iface.name}-platform.xml"
