"""
Defines Emane Models used within CORE.
"""

from core import logger
from core.emane.universal import EmaneUniversalModel
from core.misc import utils
from core.mobility import WirelessModel
from core.xml import xmlutils


class EmaneModel(WirelessModel):
    """
    EMANE models inherit from this parent class, which takes care of
    handling configuration messages based on the list of
    configurable parameters. Helper functions also live here.
    """
    _config_mac = []
    _config_phy = EmaneUniversalModel.config_matrix
    library = None
    config_ignore = set()

    def __init__(self, session, object_id=None):
        WirelessModel.__init__(self, session, object_id)

    @property
    def config_matrix(self):
        return self._config_mac + self._config_phy

    @property
    def config_groups(self):
        mac_len = len(self._config_mac)
        config_len = len(self.config_matrix)
        return "MAC Parameters:1-%d|PHY Parameters:%d-%d" % (mac_len, mac_len + 1, config_len)

    def build_xml_files(self, emane_manager, interface):
        """
        Builds xml files for emane. Includes a nem.xml file that points to both mac.xml and phy.xml definitions.

        :param core.emane.emanemanager.EmaneManager emane_manager: core emane manager
        :param interface: interface for the emane node
        :return: nothing
        """
        # retrieve configuration values
        values = emane_manager.getifcconfig(self.object_id, self.name, self.getdefaultvalues(), interface)
        if values is None:
            return

        # create document and write to disk
        nem_name = self.nem_name(interface)
        nem_document = self.create_nem_doc(emane_manager, interface)
        emane_manager.xmlwrite(nem_document, nem_name)

        # create mac document and write to disk
        mac_name = self.mac_name(interface)
        mac_document = self.create_mac_doc(emane_manager, values)
        if mac_document:
            emane_manager.xmlwrite(mac_document, mac_name)

        # create phy document and write to disk
        phy_name = self.phy_name(interface)
        phy_document = self.create_phy_doc(emane_manager, values)
        if phy_document:
            emane_manager.xmlwrite(phy_document, phy_name)

    def create_nem_doc(self, emane_manager, interface):
        mac_name = self.mac_name(interface)
        phy_name = self.phy_name(interface)

        nem_document = emane_manager.xmldoc("nem")
        nem_element = nem_document.getElementsByTagName("nem").pop()
        nem_element.setAttribute("name", "%s NEM" % self.name)
        emane_manager.appendtransporttonem(nem_document, nem_element, self.object_id, interface)

        mac_element = nem_document.createElement("mac")
        mac_element.setAttribute("definition", mac_name)
        nem_element.appendChild(mac_element)

        phy_element = nem_document.createElement("phy")
        phy_element.setAttribute("definition", phy_name)
        nem_element.appendChild(phy_element)

        return nem_document

    def create_mac_doc(self, emane_manager, values):
        names = list(self.getnames())
        mac_names = names[:len(self._config_mac)]

        mac_document = emane_manager.xmldoc("mac")
        mac_element = mac_document.getElementsByTagName("mac").pop()
        mac_element.setAttribute("name", "%s MAC" % self.name)

        if not self.library:
            raise ValueError("must define emane model library")
        mac_element.setAttribute("library", self.library)

        for name in mac_names:
            if name in self.config_ignore:
                continue
            value = self.valueof(name, values)
            param = emane_manager.xmlparam(mac_document, name, value)
            mac_element.appendChild(param)

        return mac_document

    def create_phy_doc(self, emane_manager, values):
        names = list(self.getnames())
        phy_names = names[len(self._config_mac):]
        return EmaneUniversalModel.get_phy_doc(emane_manager, self, values, phy_names)

    @classmethod
    def configure_emane(cls, session, config_data):
        """
        Handle configuration messages for configuring an emane model.

        :param core.session.Session session: session to configure emane
        :param core.conf.ConfigData config_data: configuration data for carrying out a configuration
        """
        return cls.configure(session.emane, config_data)

    def post_startup(self, emane_manager):
        """
        Logic to execute after the emane manager is finished with startup.

        :param core.emane.emanemanager.EmaneManager emane_manager: emane manager for the session
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
        emane_manager = self.session.emane

        if interface:
            node_id = interface.node.objid
            if emane_manager.getifcconfig(node_id, self.name, None, interface) is not None:
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

    @staticmethod
    def value_to_params(doc, name, value):
        """
        Helper to convert a parameter to a paramlist. Returns an XML paramlist, or None if the value does not expand to
        multiple values.

        :param xml.dom.minidom.Document doc: xml document
        :param name: name of element for params
        :param str value: value string to convert to tuple
        :return: xml document with added params or None, when an invalid value has been provided
        """
        try:
            values = utils.make_tuple_fromstr(value, str)
        except SyntaxError:
            logger.exception("error in value string to param list")
            return None

        if not hasattr(values, "__iter__"):
            return None

        if len(values) < 2:
            return None

        return xmlutils.add_param_list_to_parent(doc, parent=None, name=name, values=values)
