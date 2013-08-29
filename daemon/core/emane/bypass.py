#
# CORE
# Copyright (c)2011-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
bypass.py: EMANE Bypass model for CORE
'''

import sys
import string
from core.api import coreapi

from core.constants import *
from emane import EmaneModel

class EmaneBypassModel(EmaneModel):
    def __init__(self, session, objid = None, verbose = False):
        EmaneModel.__init__(self, session, objid, verbose)

    _name = "emane_bypass"
    _confmatrix = [
        ("none",coreapi.CONF_DATA_TYPE_BOOL, '0',
         'True,False','There are no parameters for the bypass model.'),
    ]

    # value groupings
    _confgroups = "Bypass Parameters:1-1" 

    def buildnemxmlfiles(self, e, ifc):
        ''' Build the necessary nem, mac, and phy XMLs in the given path.
            If an individual NEM has a nonstandard config, we need to build
            that file also. Otherwise the WLAN-wide nXXemane_bypassnem.xml,
            nXXemane_bypassmac.xml, nXXemane_bypassphy.xml are used.
        '''
        values = e.getifcconfig(self.objid, self._name,
                                self.getdefaultvalues(), ifc)
        if values is None:
            return
        nemdoc = e.xmldoc("nem")
        nem = nemdoc.getElementsByTagName("nem").pop()
        nem.setAttribute("name", "BYPASS NEM")
        mactag = nemdoc.createElement("mac")
        mactag.setAttribute("definition", self.macxmlname(ifc))
        nem.appendChild(mactag)
        phytag = nemdoc.createElement("phy")
        phytag.setAttribute("definition", self.phyxmlname(ifc))
        nem.appendChild(phytag)
        e.xmlwrite(nemdoc, self.nemxmlname(ifc))

        macdoc = e.xmldoc("mac")
        mac = macdoc.getElementsByTagName("mac").pop()
        mac.setAttribute("name", "BYPASS MAC")
        mac.setAttribute("library", "bypassmaclayer")
        e.xmlwrite(macdoc, self.macxmlname(ifc))

        phydoc = e.xmldoc("phy")
        phy = phydoc.getElementsByTagName("phy").pop()
        phy.setAttribute("name", "BYPASS PHY")
        phy.setAttribute("library", "bypassphylayer")
        e.xmlwrite(phydoc, self.phyxmlname(ifc))


