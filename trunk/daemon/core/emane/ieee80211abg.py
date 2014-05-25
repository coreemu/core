#
# CORE
# Copyright (c)2010-2014 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
ieee80211abg.py: EMANE IEEE 802.11abg model for CORE
'''

import sys
import string
try:
    from emanesh.events import EventService
except:
    pass
from core.api import coreapi
from core.constants import *
from emane import EmaneModel
from universal import EmaneUniversalModel

class EmaneIeee80211abgModel(EmaneModel):
    def __init__(self, session, objid = None, verbose = False):
        EmaneModel.__init__(self, session, objid, verbose)

    # model name
    _name = "emane_ieee80211abg"
    _80211rates = '1 1 Mbps,2 2 Mbps,3 5.5 Mbps,4 11 Mbps,5 6 Mbps,' + \
         '6 9 Mbps,7 12 Mbps,8 18 Mbps,9 24 Mbps,10 36 Mbps,11 48 Mbps,' + \
         '12 54 Mbps'
    if 'EventService' in globals():
        xml_path = '/usr/share/emane/xml/models/mac/ieee80211abg'
    else:
        xml_path = "/usr/share/emane/models/ieee80211abg/xml"

    # MAC parameters
    _confmatrix_mac_base = [
        ("mode", coreapi.CONF_DATA_TYPE_UINT8, '0',
         '0 802.11b (DSSS only),1 802.11b (DSSS only),' + \
         '2 802.11a or g (OFDM),3 802.11b/g (DSSS and OFDM)', 'mode'),
        ("enablepromiscuousmode", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off', 'enable promiscuous mode'),
        ("distance", coreapi.CONF_DATA_TYPE_UINT32, '1000',
         '', 'max distance (m)'),
        ("unicastrate", coreapi.CONF_DATA_TYPE_UINT8, '4', _80211rates,
         'unicast rate (Mbps)'),
        ("multicastrate", coreapi.CONF_DATA_TYPE_UINT8, '1', _80211rates,
         'multicast rate (Mbps)'),
        ("rtsthreshold", coreapi.CONF_DATA_TYPE_UINT16, '0',
         '', 'RTS threshold (bytes)'),
        ("pcrcurveuri", coreapi.CONF_DATA_TYPE_STRING,
         '%s/ieee80211pcr.xml' % xml_path,
         '', 'SINR/PCR curve file'),
        ("flowcontrolenable", coreapi.CONF_DATA_TYPE_BOOL, '0', 
         'On,Off', 'enable traffic flow control'),
        ("flowcontroltokens", coreapi.CONF_DATA_TYPE_UINT16, '10', 
         '', 'number of flow control tokens'),
    ]
    _confmatrix_mac_081 = [
        ("wmmenable", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off', 'WiFi Multimedia (WMM)'),
        ("queuesize", coreapi.CONF_DATA_TYPE_STRING, '0:255 1:255 2:255 3:255',
         '', 'queue size (0-4:size)'),
        ("cwmin", coreapi.CONF_DATA_TYPE_STRING, '0:32 1:32 2:16 3:8',
         '', 'min contention window (0-4:minw)'),
        ("cwmax", coreapi.CONF_DATA_TYPE_STRING, '0:1024 1:1024 2:64 3:16',
         '', 'max contention window (0-4:maxw)'),
        ("aifs", coreapi.CONF_DATA_TYPE_STRING, '0:2 1:2 2:2 3:1',
         '', 'arbitration inter frame space (0-4:aifs)'),
        ("txop", coreapi.CONF_DATA_TYPE_STRING, '0:0 1:0 2:0 3:0',
         '', 'txop (0-4:usec)'),
        ("retrylimit", coreapi.CONF_DATA_TYPE_STRING, '0:3 1:3 2:3 3:3',
         '', 'retry limit (0-4:numretries)'),
    ]
    _confmatrix_mac_091 = []
    if 'EventService' in globals():
        _confmatrix_mac = _confmatrix_mac_base + _confmatrix_mac_091
    else:
        _confmatrix_mac = _confmatrix_mac_base + _confmatrix_mac_081
    # PHY parameters from Universal PHY
    _confmatrix_phy = EmaneUniversalModel._confmatrix 

    _confmatrix = _confmatrix_mac + _confmatrix_phy
    # value groupings
    _confgroups = "802.11 MAC Parameters:1-%d|Universal PHY Parameters:%d-%d" \
            % (len(_confmatrix_mac), len(_confmatrix_mac) + 1, len(_confmatrix))

    def buildnemxmlfiles(self, e, ifc):
        ''' Build the necessary nem, mac, and phy XMLs in the given path.
            If an individual NEM has a nonstandard config, we need to build
            that file also. Otherwise the WLAN-wide
            nXXemane_ieee80211abgnem.xml, nXXemane_ieee80211abgemac.xml,
            nXXemane_ieee80211abgphy.xml are used.
        '''
        # use the network-wide config values or interface(NEM)-specific values?
        if ifc is None:
            values = e.getconfig(self.objid, self._name,
                                 self.getdefaultvalues())[1]
        else:
            nodenum = ifc.node.objid
            values = e.getconfig(nodenum, self._name, None)[1]
            if values is None:
                # do not build specific files for this NEM when config is same
                # as the network
                return
        nemdoc = e.xmldoc("nem")
        nem = nemdoc.getElementsByTagName("nem").pop()
        nem.setAttribute("name", "ieee80211abg NEM")
        mactag = nemdoc.createElement("mac")
        mactag.setAttribute("definition", self.macxmlname(ifc))
        nem.appendChild(mactag)
        phytag = nemdoc.createElement("phy")
        phytag.setAttribute("definition", self.phyxmlname(ifc))
        nem.appendChild(phytag)
        e.xmlwrite(nemdoc, self.nemxmlname(ifc))

        macdoc = e.xmldoc("mac")
        mac = macdoc.getElementsByTagName("mac").pop()
        mac.setAttribute("name", "ieee80211abg MAC")
        mac.setAttribute("library", "ieee80211abgmaclayer")

        names = self.getnames()
        macnames = names[:len(self._confmatrix_mac)]
        phynames = names[len(self._confmatrix_mac):]

        # append all MAC options to macdoc
        map( lambda n: mac.appendChild(e.xmlparam(macdoc, n, \
                                       self.valueof(n, values))), macnames)
        e.xmlwrite(macdoc, self.macxmlname(ifc))

        phydoc = EmaneUniversalModel.getphydoc(e, self, values, phynames)
        e.xmlwrite(phydoc, self.phyxmlname(ifc))

