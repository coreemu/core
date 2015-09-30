#
# CORE
# Copyright (c)2010-2014 the Boeing Company.
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
try:
    from emanesh.events import EventService
except:
    pass
from core.api import coreapi
from core.constants import *
from emane import Emane, EmaneModel

try:
    import emaneeventservice
    import emaneeventcommeffect
except Exception, e:
    pass

class EmaneCommEffectModel(EmaneModel):
    def __init__(self, session, objid = None, verbose = False):
        EmaneModel.__init__(self, session, objid, verbose)

    # model name
    _name = "emane_commeffect"
    # CommEffect parameters
    _confmatrix_shim_base = [
        ("filterfile", coreapi.CONF_DATA_TYPE_STRING, '',
         '', 'filter file'),
        ("groupid", coreapi.CONF_DATA_TYPE_UINT32, '0',
         '', 'NEM Group ID'),
        ("enablepromiscuousmode", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off', 'enable promiscuous mode'),
        ("receivebufferperiod", coreapi.CONF_DATA_TYPE_FLOAT, '1.0',
         '', 'receivebufferperiod'),
    ]
    _confmatrix_shim_081 = [
        ("defaultconnectivity", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off', 'defaultconnectivity'),
        ("enabletighttimingmode", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off', 'enable tight timing mode'),
    ]
    _confmatrix_shim_091 = [
        ("defaultconnectivitymode", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off', 'defaultconnectivity'),
    ]
    if Emane.version >= Emane.EMANE091:
        _confmatrix_shim = _confmatrix_shim_base + _confmatrix_shim_091
    else:
        _confmatrix_shim = _confmatrix_shim_base + _confmatrix_shim_081

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
        e.appendtransporttonem(nemdoc, nem, self.objid, ifc)
        nem.appendChild(e.xmlshimdefinition(nemdoc, self.shimxmlname(ifc)))
        e.xmlwrite(nemdoc, self.nemxmlname(ifc))

    def linkconfig(self, netif, bw = None, delay = None,
                loss = None, duplicate = None, jitter = None, netif2 = None):
        ''' Generate CommEffect events when a Link Message is received having
        link parameters.
        '''
        if self.session.emane.version >= self.session.emane.EMANE091:
            raise NotImplementedError, \
                  "CommEffect linkconfig() not implemented for EMANE 0.9.1+"
        def z(x):
            ''' Helper to use 0 for None values. '''
            if type(x) is str:
                x = float(x)
            if x is None:
                return 0
            else:
                return int(x)

        service = self.session.emane.service
        if service is None:
            self.session.warn("%s: EMANE event service unavailable" % \
                              self._name)
            return
        if netif is None or netif2 is None:
            self.session.warn("%s: missing NEM information" % self._name)
            return
        # TODO: batch these into multiple events per transmission
        # TODO: may want to split out seconds portion of delay and jitter
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



