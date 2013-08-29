#
# CORE
# Copyright (c)2010-2013 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#          Randy Charland <rcharland@ll.mit.edu>
#
'''
commeffect.py: EMANE CommEffect model for CORE
'''

import sys
import string
from core.api import coreapi

from core.constants import *
from emane import EmaneModel

try:
    import emaneeventservice
    import emaneeventcommeffect
except Exception, e:
    pass 

def z(x):
    ''' Helper to use 0 for None values. '''
    if x is None:
        return 0
    else:
        return x

class EmaneCommEffectModel(EmaneModel):
    def __init__(self, session, objid = None, verbose = False):
        EmaneModel.__init__(self, session, objid, verbose)

    # model name
    _name = "emane_commeffect"
    # CommEffect parameters
    _confmatrix_shim = [
        ("defaultconnectivity", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off', 'defaultconnectivity'),
        ("filterfile", coreapi.CONF_DATA_TYPE_STRING, '',
         '', 'filter file'),
        ("groupid", coreapi.CONF_DATA_TYPE_UINT32, '0',
         '', 'NEM Group ID'),
        ("enablepromiscuousmode", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off', 'enable promiscuous mode'),
        ("enabletighttimingmode", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off', 'enable tight timing mode'),
        ("receivebufferperiod", coreapi.CONF_DATA_TYPE_FLOAT, '1.0',
         '', 'receivebufferperiod'),
    ]

    _confmatrix = _confmatrix_shim
    # value groupings
    _confgroups = "CommEffect SHIM Parameters:1-%d" \
            % len(_confmatrix_shim)

    def buildnemxmlfiles(self, e, ifc):
        ''' Build the necessary nem and commeffect XMLs in the given path.
            If an individual NEM has a nonstandard config, we need to build
            that file also. Otherwise the WLAN-wide
            nXXemane_commeffectnem.xml, nXXemane_commeffectshim.xml are used.
        '''
        values = e.getifcconfig(self.objid, self._name,
                                self.getdefaultvalues(), ifc)
        if values is None:
            return
        shimdoc = e.xmldoc("shim")
        shim = shimdoc.getElementsByTagName("shim").pop()
        shim.setAttribute("name", "commeffect SHIM")
        shim.setAttribute("library", "commeffectshim")

        names = self.getnames()
        shimnames = list(names[:len(self._confmatrix_shim)])
        shimnames.remove("filterfile")

        # append all shim options (except filterfile) to shimdoc
        map( lambda n: shim.appendChild(e.xmlparam(shimdoc, n, \
                                       self.valueof(n, values))), shimnames)
        # empty filterfile is not allowed
        ff = self.valueof("filterfile", values)
        if ff.strip() != '':
            shim.appendChild(e.xmlparam(shimdoc, "filterfile", ff))        
        e.xmlwrite(shimdoc, self.shimxmlname(ifc))

        nemdoc = e.xmldoc("nem")
        nem = nemdoc.getElementsByTagName("nem").pop()
        nem.setAttribute("name", "commeffect NEM")
        nem.setAttribute("type", "unstructured")
        nem.appendChild(e.xmlshimdefinition(nemdoc, self.shimxmlname(ifc)))
        e.xmlwrite(nemdoc, self.nemxmlname(ifc))

    def linkconfig(self, netif, bw = None, delay = None,
                loss = None, duplicate = None, jitter = None, netif2 = None):
        ''' Generate CommEffect events when a Link Message is received having
        link parameters.
        '''
        service = self.session.emane.service
        if service is None:
            self.session.warn("%s: EMANE event service unavailable" % \
                              self._name)
            return
        if netif is None or netif2 is None:
            self.session.warn("%s: missing NEM information" % self._name)
            return
        # TODO: batch these into multiple events per transmission
        event = emaneeventcommeffect.EventCommEffect(1)
        index = 0
        e = self.session.obj(self.objid)
        nemid = e.getnemid(netif)
        nemid2 = e.getnemid(netif2)
        mbw = bw

        event.set(index, nemid, 0, z(delay), 0, z(jitter), z(loss),
                  z(duplicate), long(z(bw)), long(z(mbw)))
        service.publish(emaneeventcommeffect.EVENT_ID,
                        emaneeventservice.PLATFORMID_ANY,
                        nemid2, emaneeventservice.COMPONENTID_ANY,
                        event.export())



