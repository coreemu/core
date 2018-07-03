"""
Defines Emane Models used within CORE.
"""
import os

from lxml import etree

from core import logger
from core.conf import ConfigGroup
from core.emane import emanemanifest
from core.misc import utils
from core.mobility import WirelessModel
from core.xml import corexml


def emane_xml_doctype(name):
    """
    Create emane xml doctype for xml files.

    :param str name: name for xml doctype
    :return: emane xml doctype
    :rtype: str
    """
    return '<!DOCTYPE %s SYSTEM "file:///usr/share/emane/dtd/%s.dtd">' % (name, name)


def add_emane_configurations(xml_element, configurations, config, config_ignore):
    """


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
        params = lxml_value_to_params(value)
        if params:
            params_element = etree.SubElement(xml_element, "paramlist", name=name)
            for param in params:
                etree.SubElement(params_element, "item", value=param)
        else:
            etree.SubElement(xml_element, "param", name=name, value=value)


def lxml_value_to_params(value):
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
        logger.exception("error in value string to param list")
    return None


# def value_to_params(doc, name, value):
#     """
#     Helper to convert a parameter to a paramlist. Returns an XML paramlist, or None if the value does not expand to
#     multiple values.
#
#     :param xml.dom.minidom.Document doc: xml document
#     :param name: name of element for params
#     :param str value: value string to convert to tuple
#     :return: xml document with added params or None, when an invalid value has been provided
#     """
#     try:
#         values = utils.make_tuple_fromstr(value, str)
#     except SyntaxError:
#         logger.exception("error in value string to param list")
#         return None
#
#     if not hasattr(values, "__iter__"):
#         return None
#
#     if len(values) < 2:
#         return None
#
#     return xmlutils.add_param_list_to_parent(doc, parent=None, name=name, values=values)


class EmaneModel(WirelessModel):
    """
    EMANE models inherit from this parent class, which takes care of
    handling configuration messages based on the list of
    configurable parameters. Helper functions also live here.
    """
    # default mac configuration settings
    mac_library = None
    mac_xml = None
    mac_defaults = {}
    mac_config = []

    # default phy configuration settings, using the universal model
    phy_library = None
    phy_xml = "/usr/share/emane/manifest/emanephy.xml"
    phy_defaults = {
        "subid": "1",
        "propagationmodel": "2ray",
        "noisemode": "none"
    }
    phy_config = emanemanifest.parse(phy_xml, phy_defaults)

    config_ignore = set()
    config_groups_override = None
    configurations_override = None

    @classmethod
    def configurations(cls):
        return cls.mac_config + cls.phy_config

    @classmethod
    def config_groups(cls):
        mac_len = len(cls.mac_config)
        config_len = len(cls.configurations())
        return [
            ConfigGroup("MAC Parameters", 1, mac_len),
            ConfigGroup("PHY Parameters", mac_len + 1, config_len)
        ]

    def build_xml_files(self, emane_manager, interface):
        """
        Builds xml files for emane. Includes a nem.xml file that points to both mac.xml and phy.xml definitions.

        :param core.emane.emanemanager.EmaneManager emane_manager: core emane manager
        :param interface: interface for the emane node
        :return: nothing
        """
        # retrieve configuration values
        config = emane_manager.getifcconfig(self.object_id, interface, self.name)
        if not config:
            return

        # create document and write to disk
        self.create_nem_doc(interface)

        # create mac document and write to disk
        self.create_mac_doc(interface, config)

        # create phy document and write to disk
        self.create_phy_doc(interface, config)

    def create_nem_doc(self, interface):
        """
        Create the nem xml document.

        :param interface: interface for the emane node
        :return: nothing
        """
        nem_element = etree.Element("nem", name="%s NEM" % self.name)

        # add transport
        transport_type = "virtual"
        if interface and interface.transport_type == "raw":
            transport_type = "raw"
        transport_type = "n%strans%s.xml" % (self.object_id, transport_type)
        etree.SubElement(nem_element, "transport", definition=transport_type)

        # create mac
        mac_name = self.mac_name(interface)
        etree.SubElement(nem_element, "mac", definition=mac_name)

        # create phy
        phy_name = self.phy_name(interface)
        etree.SubElement(nem_element, "phy", definition=phy_name)

        # write out xml
        nem_name = self.nem_name(interface)
        self.create_file(nem_element, nem_name, "nem")

    def create_mac_doc(self, interface, config):
        """
        Create the mac xml document.

        :param interface: interface for the emane node
        :param dict config: all current configuration values, mac + phy
        :return: nothing
        """
        if not self.mac_library:
            raise ValueError("must define emane model library")

        mac_element = etree.Element("mac", name="%s MAC" % self.name, library=self.mac_library)
        add_emane_configurations(mac_element, self.mac_config, config, self.config_ignore)

        # write out xml
        mac_name = self.mac_name(interface)
        self.create_file(mac_element, mac_name, "mac")

    def create_phy_doc(self, interface, config):
        """
        Create the phy xml document.

        :param interface: interface for the emane node
        :param dict config: all current configuration values, mac + phy
        :return: nothing
        """
        phy_element = etree.Element("phy", name="%s PHY" % self.name)
        if self.phy_library:
            phy_element.set("library", self.phy_library)

        add_emane_configurations(phy_element, self.phy_config, config, self.config_ignore)

        # write out xml
        phy_name = self.phy_name(interface)
        self.create_file(phy_element, phy_name, "phy")

    def create_file(self, xml_element, file_name, doc_name):
        file_path = os.path.join(self.session.session_dir, file_name)
        doctype = emane_xml_doctype(doc_name)
        corexml.write_xml_file(xml_element, file_path, doctype=doctype)

    def post_startup(self):
        """
        Logic to execute after the emane manager is finished with startup.

        :return: nothing
        """
        logger.info("emane model(%s) has no post setup tasks", self.name)

    def build_nem_xml(self, doc, emane_node, interface):
        """
        Build the NEM definition that goes into the platform.xml file.

        This returns an XML element that will be added to the <platform/> element.

        This default method supports per-interface config (e.g. <nem definition="n2_0_63emane_rfpipe.xml" id="1">
        or per-EmaneNode config (e.g. <nem definition="n1emane_rfpipe.xml" id="1">.

        This can be overriden by a model for NEM flexibility; n is the EmaneNode.

            <nem name="NODE-001" definition="rfpipenem.xml">

        :param xml.dom.minidom.Document doc: xml document
        :param core.emane.nodes.EmaneNode emane_node: emane node to get information from
        :param interface: interface for the emane node
        :return: created platform xml
        """
        # if this netif contains a non-standard (per-interface) config,
        #  then we need to use a more specific xml file here
        nem_name = self.nem_name(interface)
        nem = doc.createElement("nem")
        nem.setAttribute("name", interface.localname)
        nem.setAttribute("definition", nem_name)
        return nem

    def build_transport_xml(self, doc, emane_node, interface):
        """
        Build the transport definition that goes into the platform.xml file.
        This returns an XML element that will be added to the nem definition.
        This default method supports raw and virtual transport types, but may be
        overridden by a model to support the e.g. pluggable virtual transport.

            <transport definition="transvirtual.xml" group="1">
               <param name="device" value="n1.0.158" />
            </transport>

        :param xml.dom.minidom.Document doc: xml document
        :param core.emane.nodes.EmaneNode emane_node: emane node to get information from
        :param interface: interface for the emane node
        :return: created transport xml
        """
        transport_type = interface.transport_type
        if not transport_type:
            logger.info("warning: %s interface type unsupported!", interface.name)
            transport_type = "raw"
        transport_name = emane_node.transportxmlname(transport_type)

        transport = doc.createElement("transport")
        transport.setAttribute("definition", transport_name)

        param = doc.createElement("param")
        param.setAttribute("name", "device")
        param.setAttribute("value", interface.name)

        transport.appendChild(param)
        return transport

    def _basename(self, interface=None):
        """
        Create name that is leveraged for configuration file creation.

        :param interface: interface for this model
        :return: basename used for file creation
        :rtype: str
        """
        name = "n%s" % self.object_id

        if interface:
            node_id = interface.node.objid
            if self.session.emane.getifcconfig(node_id, interface, self.name):
                name = interface.localname.replace(".", "_")

        return "%s%s" % (name, self.name)

    def nem_name(self, interface=None):
        """
        Return the string name for the NEM XML file, e.g. "n3rfpipenem.xml"

        :param interface: interface for this model
        :return: nem xml filename
        :rtype: str
        """
        basename = self._basename(interface)
        append = ""
        if interface and interface.transport_type == "raw":
            append = "_raw"
        return "%snem%s.xml" % (basename, append)

    def shim_name(self, interface=None):
        """
        Return the string name for the SHIM XML file, e.g. "commeffectshim.xml"

        :param interface: interface for this model
        :return: shim xml filename
        :rtype: str
        """
        return "%sshim.xml" % self._basename(interface)

    def mac_name(self, interface=None):
        """
        Return the string name for the MAC XML file, e.g. "n3rfpipemac.xml"

        :param interface: interface for this model
        :return: mac xml filename
        :rtype: str
        """
        return "%smac.xml" % self._basename(interface)

    def phy_name(self, interface=None):
        """
        Return the string name for the PHY XML file, e.g. "n3rfpipephy.xml"

        :param interface: interface for this model
        :return: phy xml filename
        :rtype: str
        """
        return "%sphy.xml" % self._basename(interface)

    def update(self, moved, moved_netifs):
        """
        Invoked from MobilityModel when nodes are moved; this causes
        emane location events to be generated for the nodes in the moved
        list, making EmaneModels compatible with Ns2ScriptedMobility.

        :param bool moved: were nodes moved
        :param list moved_netifs: interfaces that were moved
        :return:
        """
        try:
            wlan = self.session.get_object(self.object_id)
            wlan.setnempositions(moved_netifs)
        except KeyError:
            logger.exception("error during update")

    def linkconfig(self, netif, bw=None, delay=None, loss=None, duplicate=None, jitter=None, netif2=None):
        """
        Invoked when a Link Message is received. Default is unimplemented.

        :param core.netns.vif.Veth netif: interface one
        :param bw: bandwidth to set to
        :param delay: packet delay to set to
        :param loss: packet loss to set to
        :param duplicate: duplicate percentage to set to
        :param jitter: jitter to set to
        :param core.netns.vif.Veth netif2: interface two
        :return: nothing
        """
        logger.warn("emane model(%s) does not support link configuration", self.name)
