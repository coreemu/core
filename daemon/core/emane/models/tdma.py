"""
tdma.py: EMANE TDMA model bindings for CORE
"""

import logging
from pathlib import Path
from typing import Set

from core import constants, utils
from core.config import Configuration
from core.emane import emanemodel
from core.emulator.enumerations import ConfigDataTypes

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
    config_ignore: Set[str] = {schedule_name}

    @classmethod
    def load(cls, emane_prefix: Path) -> None:
        cls.mac_defaults["pcrcurveuri"] = str(
            emane_prefix
            / "share/emane/xml/models/mac/tdmaeventscheduler/tdmabasemodelpcr.xml"
        )
        super().load(emane_prefix)
        config_item = Configuration(
            id=cls.schedule_name,
            type=ConfigDataTypes.STRING,
            default=str(cls.default_schedule),
            label="TDMA schedule file (core)",
        )
        cls.mac_config.insert(0, config_item)

    def post_startup(self) -> None:
        """
        Logic to execute after the emane manager is finished with startup.

        :return: nothing
        """
        # get configured schedule
        config = self.session.emane.get_config(self.id, self.name)
        if not config:
            return
        schedule = Path(config[self.schedule_name])
        if not schedule.is_file():
            logger.warning("ignoring invalid tdma schedule: %s", schedule)
            return
        # initiate tdma schedule
        event_device = self.session.emane.event_device
        logger.info(
            "setting up tdma schedule: schedule(%s) device(%s)", schedule, event_device
        )
        utils.cmd(f"emaneevent-tdmaschedule -i {event_device} {schedule}")
