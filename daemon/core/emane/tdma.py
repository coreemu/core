"""
tdma.py: EMANE TDMA model bindings for CORE
"""

import os

from core import constants
from core import logger
from core.emane.emanemodel import EmaneModel
from core.enumerations import ConfigDataTypes
from core.misc import utils


class EmaneTdmaModel(EmaneModel):
    # model name
    name = "emane_tdma"
    library = "tdmaeventschedulerradiomodel"

    # mac configuration
    xml_path = "/usr/share/emane/xml/models/mac/tdmaeventscheduler"
    schedule_name = "schedule"
    default_schedule = os.path.join(constants.CORE_DATA_DIR, "examples", "tdma", "schedule.xml")
    config_ignore = {schedule_name}
    _config_mac = [
        (schedule_name, ConfigDataTypes.STRING.value, default_schedule, "", "TDMA schedule file"),
        ("enablepromiscuousmode", ConfigDataTypes.BOOL.value, "0", "True,False", "enable promiscuous mode"),
        ("flowcontrolenable", ConfigDataTypes.BOOL.value, "0", "On,Off", "enable traffic flow control"),
        ("flowcontroltokens", ConfigDataTypes.UINT16.value, "10", "", "number of flow control tokens"),
        ("fragmentcheckthreshold", ConfigDataTypes.UINT16.value, "2", "",
         "rate in seconds for check if fragment reassembly efforts should be abandoned"),
        ("fragmenttimeoutthreshold", ConfigDataTypes.UINT16.value, "5", "",
         "threshold in seconds to wait for another packet fragment for reassembly"),
        ("neighbormetricdeletetime", ConfigDataTypes.FLOAT.value, "60.0", "",
         "neighbor RF reception timeout for removal from neighbor table (sec)"),
        ("neighbormetricupdateinterval", ConfigDataTypes.FLOAT.value, "1.0", "",
         "neighbor table update interval (sec)"),
        ("pcrcurveuri", ConfigDataTypes.STRING.value, "%s/tdmabasemodelpcr.xml" % xml_path, "", "SINR/PCR curve file"),
        ("queue.aggregationenable", ConfigDataTypes.BOOL.value, "1", "On,Off", "enable transmit packet aggregation"),
        ("queue.aggregationslotthreshold", ConfigDataTypes.FLOAT.value, "90.0", "",
         "percentage of a slot that must be filled in order to conclude aggregation"),
        ("queue.depth", ConfigDataTypes.UINT16.value, "256", "",
         "size of the per service class downstream packet queues (packets)"),
        ("queue.fragmentationenable", ConfigDataTypes.BOOL.value, "1", "On,Off",
         "enable packet fragmentation (over multiple slots)"),
        ("queue.strictdequeueenable", ConfigDataTypes.BOOL.value, "0", "On,Off",
         "enable strict dequeueing to specified queues  only"),
    ]

    def post_startup(self, emane_manager):
        """
        Logic to execute after the emane manager is finished with startup.

        :param core.emane.emanemanager.EmaneManager emane_manager: emane manager for the session
        :return: nothing
        """
        # get configured schedule
        values = emane_manager.getconfig(self.object_id, self.name, self.getdefaultvalues())[1]
        if values is None:
            return
        schedule = self.valueof(self.schedule_name, values)

        event_device = emane_manager.event_device

        # initiate tdma schedule
        logger.info("setting up tdma schedule: schedule(%s) device(%s)", schedule, event_device)
        utils.check_cmd(["emaneevent-tdmaschedule", "-i", event_device, schedule])
