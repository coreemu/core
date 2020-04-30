"""
tdma.py: EMANE TDMA model bindings for CORE
"""

import logging
import os

from core import constants, utils
from core.config import Configuration
from core.emane import emanemodel
from core.emulator.enumerations import ConfigDataTypes


class EmaneTdmaModel(emanemodel.EmaneModel):
    # model name
    name = "emane_tdma"

    # mac configuration
    mac_library = "tdmaeventschedulerradiomodel"
    mac_xml = "tdmaeventschedulerradiomodel.xml"

    # add custom schedule options and ignore it when writing emane xml
    schedule_name = "schedule"
    default_schedule = os.path.join(
        constants.CORE_DATA_DIR, "examples", "tdma", "schedule.xml"
    )
    config_ignore = {schedule_name}

    @classmethod
    def load(cls, emane_prefix: str) -> None:
        cls.mac_defaults["pcrcurveuri"] = os.path.join(
            emane_prefix,
            "share/emane/xml/models/mac/tdmaeventscheduler/tdmabasemodelpcr.xml",
        )
        super().load(emane_prefix)
        cls.mac_config.insert(
            0,
            Configuration(
                _id=cls.schedule_name,
                _type=ConfigDataTypes.STRING,
                default=cls.default_schedule,
                label="TDMA schedule file (core)",
            ),
        )

    def post_startup(self) -> None:
        """
        Logic to execute after the emane manager is finished with startup.

        :return: nothing
        """
        # get configured schedule
        config = self.session.emane.get_configs(node_id=self.id, config_type=self.name)
        if not config:
            return
        schedule = config[self.schedule_name]

        # get the set event device
        event_device = self.session.emane.event_device

        # initiate tdma schedule
        logging.info(
            "setting up tdma schedule: schedule(%s) device(%s)", schedule, event_device
        )
        args = f"emaneevent-tdmaschedule -i {event_device} {schedule}"
        utils.cmd(args)
