"""
Defines Emane Models used within CORE.
"""

from core import emane
from core.misc import log
from core.misc import utils
from core.mobility import WirelessModel
from core.xml import xmlutils

logger = log.get_logger(__name__)


class EmaneModel(WirelessModel):
    """
    EMANE models inherit from this parent class, which takes care of
    handling configuration messages based on the _confmatrix list of
    configurable parameters. Helper functions also live here.
    """
    _prefix = {'y': 1e-24,  # yocto
               'z': 1e-21,  # zepto
               'a': 1e-18,  # atto
               'f': 1e-15,  # femto
               'p': 1e-12,  # pico
               'n': 1e-9,  # nano
               'u': 1e-6,  # micro
               'm': 1e-3,  # mili
               'c': 1e-2,  # centi
               'd': 1e-1,  # deci
               'k': 1e3,  # kilo
               'M': 1e6,  # mega
               'G': 1e9,  # giga
               'T': 1e12,  # tera
               'P': 1e15,  # peta
               'E': 1e18,  # exa
               'Z': 1e21,  # zetta
               'Y': 1e24,  # yotta
               }

    @classmethod
    def configure_emane(cls, session, config_data):
        """
        Handle configuration messages for setting up a model.
        Pass the Emane object as the manager object.

        :param core.session.Session session: session to configure emane
        :param core.conf.ConfigData config_data: configuration data for carrying out a configuration
        """
        return cls.configure(session.emane, config_data)

    @classmethod
    def emane074_fixup(cls, value, div=1.0):
        """
        Helper for converting 0.8.1 and newer values to EMANE 0.7.4
        compatible values.
        NOTE: This should be removed when support for 0.7.4 has been
        deprecated.
        """
        if div == 0:
            return "0"
        if type(value) is not str:
            return str(value / div)
        if value.endswith(tuple(cls._prefix.keys())):
            suffix = value[-1]
            value = float(value[:-1]) * cls._prefix[suffix]
        return str(int(value / div))

    def buildnemxmlfiles(self, e, ifc):
        """
        Build the necessary nem, mac, and phy XMLs in the given path.
        """
        raise NotImplementedError

    def buildplatformxmlnementry(self, doc, n, ifc):
        """
        Build the NEM definition that goes into the platform.xml file.
        This returns an XML element that will be added to the <platform/> element.
        This default method supports per-interface config
          (e.g. <nem definition="n2_0_63emane_rfpipe.xml" id="1"> or per-EmaneNode
        config (e.g. <nem definition="n1emane_rfpipe.xml" id="1">.
        This can be overriden by a model for NEM flexibility; n is the EmaneNode.
        """
        nem = doc.createElement("nem")
        nem.setAttribute("name", ifc.localname)
        # if this netif contains a non-standard (per-interface) config,
        #  then we need to use a more specific xml file here
        nem.setAttribute("definition", self.nemxmlname(ifc))
        return nem

    def buildplatformxmltransportentry(self, doc, n, ifc):
        """
        Build the transport definition that goes into the platform.xml file.
        This returns an XML element that will added to the nem definition.
        This default method supports raw and virtual transport types, but may be
        overriden by a model to support the e.g. pluggable virtual transport.
        n is the EmaneNode.
        """
        ttype = ifc.transport_type
        if not ttype:
            logger.info("warning: %s interface type unsupported!" % ifc.name)
            ttype = "raw"
        trans = doc.createElement("transport")
        trans.setAttribute("definition", n.transportxmlname(ttype))
        if emane.VERSION < emane.EMANE092:
            trans.setAttribute("group", "1")
        param = doc.createElement("param")
        param.setAttribute("name", "device")
        if ttype == "raw":
            # raw RJ45 name e.g. 'eth0'
            param.setAttribute("value", ifc.name)
        else:
            # virtual TAP name e.g. 'n3.0.17'
            param.setAttribute("value", ifc.localname)
            if emane.VERSION > emane.EMANE091:
                param.setAttribute("value", ifc.name)

        trans.appendChild(param)
        return trans

    def basename(self, interface=None):
        """
        Return the string that other names are based on.
        If a specific config is stored for a node's interface, a unique
        filename is needed; otherwise the name of the EmaneNode is used.
        """
        emane = self.session.emane
        name = "n%s" % self.object_id
        if interface is not None:
            nodenum = interface.node.objid
            # Adamson change - use getifcconfig() to get proper result
            # if emane.getconfig(nodenum, self._name, None)[1] is not None:
            if emane.getifcconfig(nodenum, self.name, None, interface) is not None:
                name = interface.localname.replace('.', '_')
        return "%s%s" % (name, self.name)

    def nemxmlname(self, interface=None):
        """
        Return the string name for the NEM XML file, e.g. 'n3rfpipenem.xml'
        """
        append = ""
        if emane.VERSION > emane.EMANE091:
            if interface and interface.transport_type == "raw":
                append = "_raw"
        return "%snem%s.xml" % (self.basename(interface), append)

    def shimxmlname(self, ifc=None):
        """
        Return the string name for the SHIM XML file, e.g. 'commeffectshim.xml'
        """
        return "%sshim.xml" % self.basename(ifc)

    def macxmlname(self, ifc=None):
        """
        Return the string name for the MAC XML file, e.g. 'n3rfpipemac.xml'
        """
        return "%smac.xml" % self.basename(ifc)

    def phyxmlname(self, ifc=None):
        """
        Return the string name for the PHY XML file, e.g. 'n3rfpipephy.xml'
        """
        return "%sphy.xml" % self.basename(ifc)

    def update(self, moved, moved_netifs):
        """
        invoked from MobilityModel when nodes are moved; this causes
        EMANE location events to be generated for the nodes in the moved
        list, making EmaneModels compatible with Ns2ScriptedMobility
        """
        try:
            wlan = self.session.get_object(self.object_id)
            wlan.setnempositions(moved_netifs)
        except KeyError:
            logger.exception("error during update")

    def linkconfig(self, netif, bw=None, delay=None, loss=None, duplicate=None, jitter=None, netif2=None):
        """
        Invoked when a Link Message is received. Default is unimplemented.
        """
        warntxt = "EMANE model %s does not support link " % self.name
        warntxt += "configuration, dropping Link Message"
        logger.warn(warntxt)

    @staticmethod
    def valuestrtoparamlist(dom, name, value):
        """
        Helper to convert a parameter to a paramlist.
        Returns a an XML paramlist, or None if the value does not expand to
        multiple values.
        """
        try:
            values = utils.maketuplefromstr(value, str)
        except SyntaxError:
            logger.exception("error in value string to param list")
            return None

        if not hasattr(values, '__iter__'):
            return None

        if len(values) < 2:
            return None

        return xmlutils.add_param_list_to_parent(dom, parent=None, name=name, values=values)
