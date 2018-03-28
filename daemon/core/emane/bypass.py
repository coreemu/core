"""
EMANE Bypass model for CORE
"""

from core.emane.emanemodel import EmaneModel
from core.enumerations import ConfigDataTypes


class EmaneBypassModel(EmaneModel):
    name = "emane_bypass"
    config_matrix = [
        ("none", ConfigDataTypes.BOOL.value, "0", "True,False",
         "There are no parameters for the bypass model."),
    ]

    # value groupings
    config_groups = "Bypass Parameters:1-1"

    def __init__(self, session, object_id=None):
        EmaneModel.__init__(self, session, object_id)

    def build_xml_files(self, emane_manager, interface):
        """
        Build the necessary nem, mac, and phy XMLs in the given path.
        If an individual NEM has a nonstandard config, we need to build
        that file also. Otherwise the WLAN-wide nXXemane_bypassnem.xml,
        nXXemane_bypassmac.xml, nXXemane_bypassphy.xml are used.

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

        # create nem document
        nem_document = emane_manager.xmldoc("nem")
        nem_element = nem_document.getElementsByTagName("nem").pop()
        nem_element.setAttribute("name", "BYPASS NEM")
        emane_manager.appendtransporttonem(nem_document, nem_element, self.object_id, interface)

        # create link to mac definition
        mac_element = nem_document.createElement("mac")
        mac_element.setAttribute("definition", mac_name)
        nem_element.appendChild(mac_element)

        # create link to phy definition
        phy_element = nem_document.createElement("phy")
        phy_element.setAttribute("definition", phy_name)
        nem_element.appendChild(phy_element)

        # write nem document
        emane_manager.xmlwrite(nem_document, nem_name)

        # create and write mac document
        mac_document = emane_manager.xmldoc("mac")
        mac_element = mac_document.getElementsByTagName("mac").pop()
        mac_element.setAttribute("name", "BYPASS MAC")
        mac_element.setAttribute("library", "bypassmaclayer")
        emane_manager.xmlwrite(mac_document, mac_name)

        # create and write phy document
        phy_document = emane_manager.xmldoc("phy")
        phy_element = phy_document.getElementsByTagName("phy").pop()
        phy_element.setAttribute("name", "BYPASS PHY")
        phy_element.setAttribute("library", "bypassphylayer")
        emane_manager.xmlwrite(phy_document, phy_name)
