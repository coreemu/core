"""
commeffect.py: EMANE CommEffect model for CORE
"""

from core import logger
from core.emane import emanemanifest
from core.emane import emanemodel

try:
    from emane.events.commeffectevent import CommEffectEvent
except ImportError:
    try:
        from emanesh.events.commeffectevent import CommEffectEvent
    except ImportError:
        logger.warn("compatible emane python bindings not installed")


def convert_none(x):
    """
    Helper to use 0 for None values.
    """
    if type(x) is str:
        x = float(x)
    if x is None:
        return 0
    else:
        return int(x)


class EmaneCommEffectModel(emanemodel.EmaneModel):
    name = "emane_commeffect"

    shim_library = "commeffectshim"
    shim_xml = "/usr/share/emane/manifest/commeffectshim.xml"
    shim_defaults = {}
    config_shim = emanemanifest.parse(shim_xml, shim_defaults)

    config_groups_override = "CommEffect SHIM Parameters:1-%d" % len(config_shim)
    config_matrix_override = config_shim

    def build_xml_files(self, emane_manager, interface):
        """
        Build the necessary nem and commeffect XMLs in the given path.
        If an individual NEM has a nonstandard config, we need to build
        that file also. Otherwise the WLAN-wide
        nXXemane_commeffectnem.xml, nXXemane_commeffectshim.xml are used.

        :param core.emane.emanemanager.EmaneManager emane_manager: core emane manager
        :param interface: interface for the emane node
        :return: nothing
        """
        values = emane_manager.getifcconfig(self.object_id, self.name, self.getdefaultvalues(), interface)
        if values is None:
            return

        # retrieve xml names
        nem_name = self.nem_name(interface)
        shim_name = self.shim_name(interface)

        nem_document = emane_manager.xmldoc("nem")
        nem_element = nem_document.getElementsByTagName("nem").pop()
        nem_element.setAttribute("name", "%s NEM" % self.name)
        nem_element.setAttribute("type", "unstructured")
        emane_manager.appendtransporttonem(nem_document, nem_element, self.object_id, interface)

        shim_xml = emane_manager.xmlshimdefinition(nem_document, shim_name)
        nem_element.appendChild(shim_xml)
        emane_manager.xmlwrite(nem_document, nem_name)

        names = self.getnames()
        shim_names = list(names)
        shim_names.remove("filterfile")

        shim_document = emane_manager.xmldoc("shim")
        shim_element = shim_document.getElementsByTagName("shim").pop()
        shim_element.setAttribute("name", "%s SHIM" % self.name)
        shim_element.setAttribute("library", self.shim_library)

        # append all shim options (except filterfile) to shimdoc
        for name in shim_names:
            value = self.valueof(name, values)
            param = emane_manager.xmlparam(shim_document, name, value)
            shim_element.appendChild(param)

        # empty filterfile is not allowed
        ff = self.valueof("filterfile", values)
        if ff.strip() != "":
            shim_element.appendChild(emane_manager.xmlparam(shim_document, "filterfile", ff))
        emane_manager.xmlwrite(shim_document, shim_name)

    def linkconfig(self, netif, bw=None, delay=None, loss=None, duplicate=None, jitter=None, netif2=None):
        """
        Generate CommEffect events when a Link Message is received having
        link parameters.
        """
        service = self.session.emane.service
        if service is None:
            logger.warn("%s: EMANE event service unavailable", self.name)
            return

        if netif is None or netif2 is None:
            logger.warn("%s: missing NEM information", self.name)
            return

        # TODO: batch these into multiple events per transmission
        # TODO: may want to split out seconds portion of delay and jitter
        event = CommEffectEvent()
        emane_node = self.session.get_object(self.object_id)
        nemid = emane_node.getnemid(netif)
        nemid2 = emane_node.getnemid(netif2)
        mbw = bw
        logger.info("sending comm effect event")
        event.append(
            nemid,
            latency=convert_none(delay),
            jitter=convert_none(jitter),
            loss=convert_none(loss),
            duplicate=convert_none(duplicate),
            unicast=long(convert_none(bw)),
            broadcast=long(convert_none(mbw))
        )
        service.publish(nemid2, event)
