"""
tdma.py: EMANE TDMA model bindings for CORE
"""

import os

from core import constants
from core import logger
from core.emane.emanemodel import EmaneModel
from core.emane.universal import EmaneUniversalModel
from core.enumerations import ConfigDataTypes
from core.misc import utils


class EmaneTdmaModel(EmaneModel):
    # model name
    name = "emane_tdma"
    xml_path = "/usr/share/emane/xml/models/mac/tdmaeventscheduler"
    schedule_name = "schedule"
    default_schedule = os.path.join(constants.CORE_DATA_DIR, "examples", "tdma", "schedule.xml")

    # MAC parameters
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

    # PHY parameters from Universal PHY
    _config_phy = EmaneUniversalModel.config_matrix

    config_matrix = _config_mac + _config_phy

    # value groupings
    config_groups = "TDMA MAC Parameters:1-%d|Universal PHY Parameters:%d-%d" % (
        len(_config_mac), len(_config_mac) + 1, len(config_matrix))

    def __init__(self, session, object_id=None):
        EmaneModel.__init__(self, session, object_id)

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
        schedule = self.valueof(EmaneTdmaModel.schedule_name, values)

        event_device = emane_manager.event_device

        # initiate tdma schedule
        logger.info("setting up tdma schedule: schedule(%s) device(%s)", schedule, event_device)
        utils.check_cmd(["emaneevent-tdmaschedule", "-i", event_device, schedule])

    def build_xml_files(self, emane_manager, interface):
        """
        Build the necessary nem, mac, and phy XMLs in the given path.
        If an individual NEM has a nonstandard config, we need to build
        that file also. Otherwise the WLAN-wide nXXemane_tdmanem.xml,
        nXXemane_tdmamac.xml, nXXemane_tdmaphy.xml are used.

        :param core.emane.emanemanager.EmaneManager emane_manager: core emane manager
        :param interface: interface for the emane node
        :return: nothing
        """
        values = emane_manager.getifcconfig(self.object_id, self.name, self.getdefaultvalues(), interface)
        if values is None:
            return

        # retrieve xml names
        nem_name = self.nem_name(interface)
        mac_name = self.mac_name(interface)
        phy_name = self.phy_name(interface)

        nem_document = emane_manager.xmldoc("nem")
        nem_element = nem_document.getElementsByTagName("nem").pop()
        nem_element.setAttribute("name", "TDMA NEM")
        emane_manager.appendtransporttonem(nem_document, nem_element, self.object_id, interface)

        mac_element = nem_document.createElement("mac")
        mac_element.setAttribute("definition", mac_name)
        nem_element.appendChild(mac_element)

        phy_element = nem_document.createElement("phy")
        phy_element.setAttribute("definition", phy_name)
        nem_element.appendChild(phy_element)

        emane_manager.xmlwrite(nem_document, nem_name)

        names = list(self.getnames())
        mac_names = names[:len(self._config_mac)]
        phy_names = names[len(self._config_mac):]

        # make any changes to the mac/phy names here to e.g. exclude them from the XML output
        mac_names.remove(EmaneTdmaModel.schedule_name)

        mac_document = emane_manager.xmldoc("mac")
        mac_element = mac_document.getElementsByTagName("mac").pop()
        mac_element.setAttribute("name", "TDMA MAC")
        mac_element.setAttribute("library", "tdmaeventschedulerradiomodel")
        for name in mac_names:
            value = self.valueof(name, values)
            param = emane_manager.xmlparam(mac_document, name, value)
            mac_element.appendChild(param)
        emane_manager.xmlwrite(mac_document, mac_name)

        phydoc = EmaneUniversalModel.get_phy_doc(emane_manager, self, values, phy_names)
        emane_manager.xmlwrite(phydoc, phy_name)
