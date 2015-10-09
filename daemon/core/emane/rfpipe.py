#
# CORE
# Copyright (c)2010-2014 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#          Harry Bullen <hbullen@i-a-i.com>
#
'''
rfpipe.py: EMANE RF-PIPE model for CORE
'''

import sys
import string
try:
    from emanesh.events import EventService
except:
    pass
from core.api import coreapi
from core.constants import *
from emane import Emane, EmaneModel
from universal import EmaneUniversalModel

class EmaneRfPipeModel(EmaneModel):
    def __init__(self, session, objid = None, verbose = False):
        EmaneModel.__init__(self, session, objid, verbose)

    # model name
    _name = "emane_rfpipe"
    if Emane.version >= Emane.EMANE091:
        xml_path = '/usr/share/emane/xml/models/mac/rfpipe'
    else:
        xml_path = "/usr/share/emane/models/rfpipe/xml"

    # configuration parameters are
    #  ( 'name', 'type', 'default', 'possible-value-list', 'caption')
    # MAC parameters
    _confmatrix_mac_base = [
        ("enablepromiscuousmode", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'True,False', 'enable promiscuous mode'),
        ("datarate", coreapi.CONF_DATA_TYPE_UINT32, '1M',
         '', 'data rate (bps)'),
        ("flowcontrolenable", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off', 'enable traffic flow control'),
        ("flowcontroltokens", coreapi.CONF_DATA_TYPE_UINT16, '10',
         '', 'number of flow control tokens'),
        ("pcrcurveuri", coreapi.CONF_DATA_TYPE_STRING,
         '%s/rfpipepcr.xml' % xml_path,
         '', 'SINR/PCR curve file'),
    ]
    _confmatrix_mac_081 = [
        ("jitter", coreapi.CONF_DATA_TYPE_FLOAT, '0.0',
         '', 'transmission jitter (usec)'),
        ("delay", coreapi.CONF_DATA_TYPE_FLOAT, '0.0',
         '', 'transmission delay (usec)'),
        ("transmissioncontrolmap", coreapi.CONF_DATA_TYPE_STRING, '',
         '', 'tx control map (nem:rate:freq:tx_dBm)'),
        ("enabletighttiming", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off', 'enable tight timing for pkt delay'),
    ]
    _confmatrix_mac_091 = [
        ("jitter", coreapi.CONF_DATA_TYPE_FLOAT, '0.0',
         '', 'transmission jitter (sec)'),
        ("delay", coreapi.CONF_DATA_TYPE_FLOAT, '0.0',
         '', 'transmission delay (sec)'),
        ('radiometricenable', coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off', 'report radio metrics via R2RI'),
        ('radiometricreportinterval', coreapi.CONF_DATA_TYPE_FLOAT, '1.0',
         '', 'R2RI radio metric report interval (sec)'),
        ('neighbormetricdeletetime', coreapi.CONF_DATA_TYPE_FLOAT, '60.0',
         '', 'R2RI neighbor table inactivity time (sec)'),
    ]
    if Emane.version >= Emane.EMANE091:
        _confmatrix_mac = _confmatrix_mac_base + _confmatrix_mac_091
    else:
        _confmatrix_mac = _confmatrix_mac_base + _confmatrix_mac_081

    # PHY parameters from Universal PHY
    _confmatrix_phy = EmaneUniversalModel._confmatrix

    _confmatrix = _confmatrix_mac + _confmatrix_phy

    # value groupings
    _confgroups = "RF-PIPE MAC Parameters:1-%d|Universal PHY Parameters:%d-%d" \
           % ( len(_confmatrix_mac), len(_confmatrix_mac) + 1, len(_confmatrix))

    def buildnemxmlfiles(self, e, ifc):
        ''' Build the necessary nem, mac, and phy XMLs in the given path.
            If an individual NEM has a nonstandard config, we need to build
            that file also. Otherwise the WLAN-wide nXXemane_rfpipenem.xml,
            nXXemane_rfpipemac.xml, nXXemane_rfpipephy.xml are used.
        '''
        values = e.getifcconfig(self.objid, self._name,
                                self.getdefaultvalues(), ifc)
        if values is None:
            return
        nemdoc = e.xmldoc("nem")
        nem = nemdoc.getElementsByTagName("nem").pop()
        nem.setAttribute("name", "RF-PIPE NEM")
        e.appendtransporttonem(nemdoc, nem, self.objid, ifc)
        mactag = nemdoc.createElement("mac")
        mactag.setAttribute("definition", self.macxmlname(ifc))
        nem.appendChild(mactag)
        phytag = nemdoc.createElement("phy")
        phytag.setAttribute("definition", self.phyxmlname(ifc))
        nem.appendChild(phytag)
        e.xmlwrite(nemdoc, self.nemxmlname(ifc))

        names = list(self.getnames())
        macnames = names[:len(self._confmatrix_mac)]
        phynames = names[len(self._confmatrix_mac):]

        macdoc = e.xmldoc("mac")
        mac = macdoc.getElementsByTagName("mac").pop()
        mac.setAttribute("name", "RF-PIPE MAC")
        mac.setAttribute("library", "rfpipemaclayer")
        if e.version < e.EMANE091 and \
           self.valueof("transmissioncontrolmap", values) is "":
            macnames.remove("transmissioncontrolmap")
        # EMANE 0.7.4 support
        if e.version == e.EMANE074:
            # convert datarate from bps to kbps
            i = names.index('datarate')
            values = list(values)
            values[i] = self.emane074_fixup(values[i], 1000)
        # append MAC options to macdoc
        map( lambda n: mac.appendChild(e.xmlparam(macdoc, n, \
                                       self.valueof(n, values))), macnames)
        e.xmlwrite(macdoc, self.macxmlname(ifc))

        phydoc = EmaneUniversalModel.getphydoc(e, self, values, phynames)
        e.xmlwrite(phydoc, self.phyxmlname(ifc))

