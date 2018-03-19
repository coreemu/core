"""
commeffect.py: EMANE CommEffect model for CORE
"""

from core import logger
from core.emane.emanemodel import EmaneModel
from core.enumerations import ConfigDataTypes

try:
    from emanesh.events.commeffectevent import CommEffectEvent
except ImportError:
    try:
        from emane.events.commeffectevent import CommEffectEvent
    except ImportError:
        logger.info("emane 0.9.1+ not found")


def convert_none(x):
    """
    Helper to use 0 for None values.
    """
    if type(x) is str:
        x = float(x)
    if x is None:
        return 0
    else:
        return int(x)


class EmaneCommEffectModel(EmaneModel):
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
    _confmatrix_shim_091 = [
        ("defaultconnectivitymode", ConfigDataTypes.BOOL.value, "0",
         "On,Off", "defaultconnectivity"),
    ]
    _confmatrix_shim = _confmatrix_shim_base + _confmatrix_shim_091

    config_matrix = _confmatrix_shim
    # value groupings
    config_groups = "CommEffect SHIM Parameters:1-%d" % len(_confmatrix_shim)

    def __init__(self, session, object_id=None):
        EmaneModel.__init__(self, session, object_id)

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

    def linkconfig(self, netif, bw=None, delay=None, loss=None, duplicate=None, jitter=None, netif2=None):
        """
        Generate CommEffect events when a Link Message is received having
        link parameters.
        """
        service = self.session.emane.service
        if service is None:
            logger.warn("%s: EMANE event service unavailable", self.name)
            return

        if netif is None or netif2 is None:
            logger.warn("%s: missing NEM information", self.name)
            return

        # TODO: batch these into multiple events per transmission
        # TODO: may want to split out seconds portion of delay and jitter
        event = CommEffectEvent()
        emane_node = self.session.get_object(self.object_id)
        nemid = emane_node.getnemid(netif)
        nemid2 = emane_node.getnemid(netif2)
        mbw = bw

        event.append(
            nemid,
            latency=convert_none(delay),
            jitter=convert_none(jitter),
            loss=convert_none(loss),
            duplicate=convert_none(duplicate),
            unicast=long(convert_none(bw)),
            broadcast=long(convert_none(mbw))
        )
        service.publish(nemid2, event)
