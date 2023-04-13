"""
tdma.py: EMANE TDMA model bindings for CORE
"""

import logging
from pathlib import Path

from core import constants, utils
from core.config import ConfigString
from core.emane import emanemodel
from core.emane.nodes import EmaneNet
from core.nodes.interface import CoreInterface

logger = logging.getLogger(__name__)


class EmaneTdmaModel(emanemodel.EmaneModel):
    # model name
    name: str = "emane_tdma"

    # mac configuration
    mac_library: str = "tdmaeventschedulerradiomodel"
    mac_xml: str = "tdmaeventschedulerradiomodel.xml"

    # add custom schedule options and ignore it when writing emane xml
    schedule_name: str = "schedule"
    default_schedule: Path = (
        constants.CORE_DATA_DIR / "examples" / "tdma" / "schedule.xml"
    )
    config_ignore: set[str] = {schedule_name}

    @classmethod
    def load(cls, emane_prefix: Path) -> None:
        cls.mac_defaults["pcrcurveuri"] = str(
            emane_prefix
            / "share/emane/xml/models/mac/tdmaeventscheduler/tdmabasemodelpcr.xml"
        )
        super().load(emane_prefix)
        config_item = ConfigString(
            id=cls.schedule_name,
            default=str(cls.default_schedule),
            label="TDMA schedule file (core)",
        )
        cls.mac_config.insert(0, config_item)

    def post_startup(self, iface: CoreInterface) -> None:
        # get configured schedule
        emane_net = self.session.get_node(self.id, EmaneNet)
        config = self.session.emane.get_iface_config(emane_net, iface)
        schedule = Path(config[self.schedule_name])
        if not schedule.is_file():
            logger.error("ignoring invalid tdma schedule: %s", schedule)
            return
        # initiate tdma schedule
        nem_id = self.session.emane.get_nem_id(iface)
        if not nem_id:
            logger.error("could not find nem for interface")
            return
        service = self.session.emane.nem_service.get(nem_id)
        if service:
            device = service.device
            logger.info(
                "setting up tdma schedule: schedule(%s) device(%s)", schedule, device
            )
            utils.cmd(f"emaneevent-tdmaschedule -i {device} {schedule}")
