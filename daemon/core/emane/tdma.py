
#
# CORE
# Copyright (c)2013 Company.
# See the LICENSE file included in this distribution.
#
# author: Name <email@company.com>
#
'''
tdma.py: EMANE TDMA model bindings for CORE
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

class EmaneTdmaModel(EmaneModel):
    def __init__(self, session, objid = None, verbose = False):
        EmaneModel.__init__(self, session, objid, verbose)

    # model name
    _name = "emane_tdma"
    if Emane.version >= Emane.EMANE101:
        xml_path = '/usr/share/emane/xml/models/mac/tdmaeventscheduler'
    else:
        raise Exception("EMANE TDMA requires EMANE 1.0.1 or greater")
    
    
    # MAC parameters
    _confmatrix_mac = [
        ("enablepromiscuousmode", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'True,False', 'enable promiscuous mode'),
        ("flowcontrolenable", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off', 'enable traffic flow control'),
        ("flowcontroltokens", coreapi.CONF_DATA_TYPE_UINT16, '10',
         '', 'number of flow control tokens'),
        ("fragmentcheckthreshold", coreapi.CONF_DATA_TYPE_UINT16, '2',
         '', 'rate in seconds for check if fragment reassembly efforts should be abandoned'),
        ("fragmenttimeoutthreshold", coreapi.CONF_DATA_TYPE_UINT16, '5',
         '', 'threshold in seconds to wait for another packet fragment for reassembly'),
        ('neighbormetricdeletetime', coreapi.CONF_DATA_TYPE_FLOAT, '60.0',
         '', 'neighbor RF reception timeout for removal from neighbor table (sec)'),
        ('neighbormetricupdateinterval', coreapi.CONF_DATA_TYPE_FLOAT, '1.0',
         '', 'neighbor table update interval (sec)'),
        ("pcrcurveuri", coreapi.CONF_DATA_TYPE_STRING, '%s/tdmabasemodelpcr.xml' % xml_path, 
         '', 'SINR/PCR curve file'),
        ("queue.aggregationenable", coreapi.CONF_DATA_TYPE_BOOL, '1',
         'On,Off', 'enable transmit packet aggregation'),
        ('queue.aggregationslotthreshold', coreapi.CONF_DATA_TYPE_FLOAT, '90.0',
         '', 'percentage of a slot that must be filled in order to conclude aggregation'),
        ("queue.depth", coreapi.CONF_DATA_TYPE_UINT16, '256',
         '', 'size of the per service class downstream packet queues (packets)'),
        ("queue.fragmentationenable", coreapi.CONF_DATA_TYPE_BOOL, '1',
         'On,Off', 'enable packet fragmentation (over multiple slots)'),
        ("queue.strictdequeueenable", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off', 'enable strict dequeueing to specified queues  only'),
    ]

    # PHY parameters from Universal PHY
    _confmatrix_phy = EmaneUniversalModel._confmatrix 

    _confmatrix = _confmatrix_mac + _confmatrix_phy

    # value groupings
    _confgroups = "TDMA MAC Parameters:1-%d|Universal PHY Parameters:%d-%d" % \
                  (len(_confmatrix_mac), len(_confmatrix_mac) + 1, len(_confmatrix))

    def buildnemxmlfiles(self, e, ifc):
        ''' Build the necessary nem, mac, and phy XMLs in the given path.
            If an individual NEM has a nonstandard config, we need to build
            that file also. Otherwise the WLAN-wide nXXemane_tdmanem.xml,
            nXXemane_tdmamac.xml, nXXemane_tdmaphy.xml are used.
        '''
        values = e.getifcconfig(self.objid, self._name,
                                self.getdefaultvalues(), ifc)
        if values is None:
            return
        nemdoc = e.xmldoc("nem")
        nem = nemdoc.getElementsByTagName("nem").pop()
        nem.setAttribute("name", "TDMA NEM")
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
        # make any changes to the mac/phy names here to e.g. exclude them from
        # the XML output

        macdoc = e.xmldoc("mac")
        mac = macdoc.getElementsByTagName("mac").pop()
        mac.setAttribute("name", "TDMA MAC")
        mac.setAttribute("library", "tdmaeventschedulerradiomodel")
        # append MAC options to macdoc
        map(lambda n: mac.appendChild(e.xmlparam(macdoc, n, \
                                      self.valueof(n, values))), macnames)
        e.xmlwrite(macdoc, self.macxmlname(ifc))

        phydoc = EmaneUniversalModel.getphydoc(e, self, values, phynames)
        e.xmlwrite(phydoc, self.phyxmlname(ifc))

