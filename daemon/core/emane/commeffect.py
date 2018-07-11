"""
commeffect.py: EMANE CommEffect model for CORE
"""

import os

from lxml import etree

from core import logger
from core.conf import ConfigGroup
from core.emane import emanemanifest
from core.emane import emanemodel
from core.xml import emanexml

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

    # comm effect does not need the default phy and external configurations
    phy_config = ()
    external_config = ()

    @classmethod
    def configurations(cls):
        return cls.config_shim

    @classmethod
    def config_groups(cls):
        return [
            ConfigGroup("CommEffect SHIM Parameters", 1, len(cls.configurations()))
        ]

    def build_xml_files(self, config, interface=None):
        """
        Build the necessary nem and commeffect XMLs in the given path.
        If an individual NEM has a nonstandard config, we need to build
        that file also. Otherwise the WLAN-wide
        nXXemane_commeffectnem.xml, nXXemane_commeffectshim.xml are used.

        :param dict config: emane model configuration for the node and interface
        :param interface: interface for the emane node
        :return: nothing
        """
        # retrieve xml names
        nem_name = emanexml.nem_file_name(self, interface)
        shim_name = emanexml.shim_file_name(self, interface)

        # create and write nem document
        nem_element = etree.Element("nem", name="%s NEM" % self.name, type="unstructured")
        transport_type = "virtual"
        if interface and interface.transport_type == "raw":
            transport_type = "raw"
        transport_file = emanexml.transport_file_name(self.object_id, transport_type)
        etree.SubElement(nem_element, "transport", definition=transport_file)

        # set shim configuration
        etree.SubElement(nem_element, "shim", definition=shim_name)

        nem_file = os.path.join(self.session.session_dir, nem_name)
        emanexml.create_file(nem_element, "nem", nem_file)

        # create and write shim document
        shim_element = etree.Element("shim", name="%s SHIM" % self.name, library=self.shim_library)

        # append all shim options (except filterfile) to shimdoc
        for configuration in self.config_shim:
            name = configuration.id
            if name == "filterfile":
                continue
            value = config[name]
            emanexml.add_param(shim_element, name, value)

        # empty filterfile is not allowed
        ff = config["filterfile"]
        if ff.strip() != "":
            emanexml.add_param(shim_element, "filterfile", ff)

        shim_file = os.path.join(self.session.session_dir, shim_name)
        emanexml.create_file(shim_element, "shim", shim_file)

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
