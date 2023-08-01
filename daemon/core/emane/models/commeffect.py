"""
commeffect.py: EMANE CommEffect model for CORE
"""

import logging
from pathlib import Path

from lxml import etree

from core.config import ConfigGroup, Configuration
from core.emane import emanemanifest, emanemodel
from core.emulator.data import LinkOptions
from core.nodes.interface import CoreInterface
from core.xml import emanexml

logger = logging.getLogger(__name__)

try:
    from emane.events.commeffectevent import CommEffectEvent
except ImportError:
    try:
        from emanesh.events.commeffectevent import CommEffectEvent
    except ImportError:
        CommEffectEvent = None
        logger.debug("compatible emane python bindings not installed")


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
    shim_defaults: dict[str, str] = {}
    config_shim: list[Configuration] = []

    # comm effect does not need the default phy and external configurations
    phy_config: list[Configuration] = []
    external_config: list[Configuration] = []

    @classmethod
    def load(cls, emane_prefix: Path) -> None:
        cls._load_platform_config(emane_prefix)
        shim_xml_path = emane_prefix / "share/emane/manifest" / cls.shim_xml
        cls.config_shim = emanemanifest.parse(shim_xml_path, cls.shim_defaults)

    @classmethod
    def configurations(cls) -> list[Configuration]:
        return cls.platform_config + cls.config_shim

    @classmethod
    def config_groups(cls) -> list[ConfigGroup]:
        platform_len = len(cls.platform_config)
        return [
            ConfigGroup("Platform Parameters", 1, platform_len),
            ConfigGroup(
                "CommEffect SHIM Parameters",
                platform_len + 1,
                len(cls.configurations()),
            ),
        ]

    def build_xml_files(self, config: dict[str, str], iface: CoreInterface) -> None:
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
        emanexml.create_node_file(iface.node, nem_element, "nem", nem_name)

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
        emanexml.create_node_file(iface.node, shim_element, "shim", shim_name)

        # create transport xml
        emanexml.create_transport_xml(iface, config)

    def linkconfig(
        self, iface: CoreInterface, options: LinkOptions, iface2: CoreInterface = None
    ) -> None:
        """
        Generate CommEffect events when a Link Message is received having
        link parameters.
        """
        if iface is None or iface2 is None:
            logger.warning("%s: missing NEM information", self.name)
            return
        # TODO: batch these into multiple events per transmission
        # TODO: may want to split out seconds portion of delay and jitter
        event = CommEffectEvent()
        nem1 = self.session.emane.get_nem_id(iface)
        nem2 = self.session.emane.get_nem_id(iface2)
        logger.info("sending comm effect event")
        event.append(
            nem1,
            latency=convert_none(options.delay),
            jitter=convert_none(options.jitter),
            loss=convert_none(options.loss),
            duplicate=convert_none(options.dup),
            unicast=int(convert_none(options.bandwidth)),
            broadcast=int(convert_none(options.bandwidth)),
        )
        self.session.emane.publish_event(nem2, event)
