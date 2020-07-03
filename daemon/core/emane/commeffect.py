"""
commeffect.py: EMANE CommEffect model for CORE
"""

import logging
import os
from typing import Dict, List

from lxml import etree

from core.config import ConfigGroup, Configuration
from core.emane import emanemanifest, emanemodel
from core.emane.nodes import EmaneNet
from core.emulator.data import LinkOptions
from core.nodes.interface import CoreInterface
from core.xml import emanexml

try:
    from emane.events.commeffectevent import CommEffectEvent
except ImportError:
    try:
        from emanesh.events.commeffectevent import CommEffectEvent
    except ImportError:
        CommEffectEvent = None
        logging.debug("compatible emane python bindings not installed")


def convert_none(x: float) -> int:
    """
    Helper to use 0 for None values.
    """
    if isinstance(x, str):
        x = float(x)
    if x is None:
        return 0
    else:
        return int(x)


class EmaneCommEffectModel(emanemodel.EmaneModel):
    name: str = "emane_commeffect"
    shim_library: str = "commeffectshim"
    shim_xml: str = "commeffectshim.xml"
    shim_defaults: Dict[str, str] = {}
    config_shim: List[Configuration] = []

    # comm effect does not need the default phy and external configurations
    phy_config: List[Configuration] = []
    external_config: List[Configuration] = []

    @classmethod
    def load(cls, emane_prefix: str) -> None:
        shim_xml_path = os.path.join(emane_prefix, "share/emane/manifest", cls.shim_xml)
        cls.config_shim = emanemanifest.parse(shim_xml_path, cls.shim_defaults)

    @classmethod
    def configurations(cls) -> List[Configuration]:
        return cls.config_shim

    @classmethod
    def config_groups(cls) -> List[ConfigGroup]:
        return [ConfigGroup("CommEffect SHIM Parameters", 1, len(cls.configurations()))]

    def build_xml_files(self, config: Dict[str, str], iface: CoreInterface) -> None:
        """
        Build the necessary nem and commeffect XMLs in the given path.
        If an individual NEM has a nonstandard config, we need to build
        that file also. Otherwise the WLAN-wide
        nXXemane_commeffectnem.xml, nXXemane_commeffectshim.xml are used.

        :param config: emane model configuration for the node and interface
        :param iface: interface for the emane node
        :return: nothing
        """
        # create and write nem document
        nem_element = etree.Element("nem", name=f"{self.name} NEM", type="unstructured")
        transport_name = emanexml.transport_file_name(iface)
        etree.SubElement(nem_element, "transport", definition=transport_name)

        # set shim configuration
        nem_name = emanexml.nem_file_name(iface)
        shim_name = emanexml.shim_file_name(iface)
        etree.SubElement(nem_element, "shim", definition=shim_name)
        emanexml.create_iface_file(iface, nem_element, "nem", nem_name)

        # create and write shim document
        shim_element = etree.Element(
            "shim", name=f"{self.name} SHIM", library=self.shim_library
        )

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
        emanexml.create_iface_file(iface, shim_element, "shim", shim_name)

        # create transport xml
        emanexml.create_transport_xml(iface, config)

    def linkconfig(
        self, iface: CoreInterface, options: LinkOptions, iface2: CoreInterface = None
    ) -> None:
        """
        Generate CommEffect events when a Link Message is received having
        link parameters.
        """
        service = self.session.emane.service
        if service is None:
            logging.warning("%s: EMANE event service unavailable", self.name)
            return

        if iface is None or iface2 is None:
            logging.warning("%s: missing NEM information", self.name)
            return

        # TODO: batch these into multiple events per transmission
        # TODO: may want to split out seconds portion of delay and jitter
        event = CommEffectEvent()
        emane_node = self.session.get_node(self.id, EmaneNet)
        nemid = emane_node.getnemid(iface)
        nemid2 = emane_node.getnemid(iface2)
        logging.info("sending comm effect event")
        event.append(
            nemid,
            latency=convert_none(options.delay),
            jitter=convert_none(options.jitter),
            loss=convert_none(options.loss),
            duplicate=convert_none(options.dup),
            unicast=int(convert_none(options.bandwidth)),
            broadcast=int(convert_none(options.bandwidth)),
        )
        service.publish(nemid2, event)
