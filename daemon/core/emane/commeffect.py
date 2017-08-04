"""
commeffect.py: EMANE CommEffect model for CORE
"""

from core import emane
from core.emane.emanemodel import EmaneModel
from core.enumerations import ConfigDataTypes
from core.misc import log

logger = log.get_logger(__name__)

try:
    import emaneeventservice
    import emaneeventcommeffect
except ImportError:
    logger.error("error importing emaneeventservice and emaneeventcommeffect")


class EmaneCommEffectModel(EmaneModel):
    def __init__(self, session, object_id=None):
        EmaneModel.__init__(self, session, object_id)

    # model name
    name = "emane_commeffect"
    # CommEffect parameters
    _confmatrix_shim_base = [
        ("filterfile", ConfigDataTypes.STRING.value, "",
         "", "filter file"),
        ("groupid", ConfigDataTypes.UINT32.value, "0",
         "", "NEM Group ID"),
        ("enablepromiscuousmode", ConfigDataTypes.BOOL.value, "0",
         "On,Off", "enable promiscuous mode"),
        ("receivebufferperiod", ConfigDataTypes.FLOAT.value, "1.0",
         "", "receivebufferperiod"),
    ]
    _confmatrix_shim_081 = [
        ("defaultconnectivity", ConfigDataTypes.BOOL.value, "0",
         "On,Off", "defaultconnectivity"),
        ("enabletighttimingmode", ConfigDataTypes.BOOL.value, "0",
         "On,Off", "enable tight timing mode"),
    ]
    _confmatrix_shim_091 = [
        ("defaultconnectivitymode", ConfigDataTypes.BOOL.value, "0",
         "On,Off", "defaultconnectivity"),
    ]
    if emane.VERSION >= emane.EMANE091:
        _confmatrix_shim = _confmatrix_shim_base + _confmatrix_shim_091
    else:
        _confmatrix_shim = _confmatrix_shim_base + _confmatrix_shim_081

    config_matrix = _confmatrix_shim
    # value groupings
    config_groups = "CommEffect SHIM Parameters:1-%d" % len(_confmatrix_shim)

    def buildnemxmlfiles(self, e, ifc):
        """
        Build the necessary nem and commeffect XMLs in the given path.
        If an individual NEM has a nonstandard config, we need to build
        that file also. Otherwise the WLAN-wide
        nXXemane_commeffectnem.xml, nXXemane_commeffectshim.xml are used.
        """
        values = e.getifcconfig(self.object_id, self.name, self.getdefaultvalues(), ifc)
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
        map(lambda n: shim.appendChild(e.xmlparam(shimdoc, n, self.valueof(n, values))), shimnames)
        # empty filterfile is not allowed
        ff = self.valueof("filterfile", values)
        if ff.strip() != "":
            shim.appendChild(e.xmlparam(shimdoc, "filterfile", ff))
        e.xmlwrite(shimdoc, self.shimxmlname(ifc))

        nemdoc = e.xmldoc("nem")
        nem = nemdoc.getElementsByTagName("nem").pop()
        nem.setAttribute("name", "commeffect NEM")
        nem.setAttribute("type", "unstructured")
        e.appendtransporttonem(nemdoc, nem, self.object_id, ifc)
        nem.appendChild(e.xmlshimdefinition(nemdoc, self.shimxmlname(ifc)))
        e.xmlwrite(nemdoc, self.nemxmlname(ifc))

    def linkconfig(self, netif, bw=None, delay=None,
                   loss=None, duplicate=None, jitter=None, netif2=None):
        """
        Generate CommEffect events when a Link Message is received having
        link parameters.
        """
        if emane.VERSION >= emane.EMANE091:
            raise NotImplementedError("CommEffect linkconfig() not implemented for EMANE 0.9.1+")

        def z(x):
            """
            Helper to use 0 for None values.
            """
            if type(x) is str:
                x = float(x)
            if x is None:
                return 0
            else:
                return int(x)

        service = self.session.emane.service
        if service is None:
            logger.warn("%s: EMANE event service unavailable" % self.name)
            return
        if netif is None or netif2 is None:
            logger.warn("%s: missing NEM information" % self.name)
            return
        # TODO: batch these into multiple events per transmission
        # TODO: may want to split out seconds portion of delay and jitter
        event = emaneeventcommeffect.EventCommEffect(1)
        index = 0
        e = self.session.get_object(self.object_id)
        nemid = e.getnemid(netif)
        nemid2 = e.getnemid(netif2)
        mbw = bw

        event.set(index, nemid, 0, z(delay), 0, z(jitter), z(loss),
                  z(duplicate), long(z(bw)), long(z(mbw)))
        service.publish(emaneeventcommeffect.EVENT_ID,
                        emaneeventservice.PLATFORMID_ANY,
                        nemid2, emaneeventservice.COMPONENTID_ANY,
                        event.export())
