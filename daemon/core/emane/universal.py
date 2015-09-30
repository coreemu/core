#
# CORE
# Copyright (c)2010-2014 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
universal.py: EMANE Universal PHY model for CORE. Enumerates configuration items
used for the Universal PHY.
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

class EmaneUniversalModel(EmaneModel):
    ''' This Univeral PHY model is meant to be imported by other models,
        not instantiated.
    '''
    def __init__(self, session, objid = None, verbose = False):
        raise SyntaxError

    _name = "emane_universal"
    _xmlname = "universalphy"
    _xmllibrary = "universalphylayer"

    # universal PHY parameters
    _confmatrix_base = [
        ("bandwidth", coreapi.CONF_DATA_TYPE_UINT64, '1M',
          '', 'rf bandwidth (hz)'),
        ("frequency", coreapi.CONF_DATA_TYPE_UINT64, '2.347G',
         '','frequency (Hz)'),
        ("frequencyofinterest", coreapi.CONF_DATA_TYPE_UINT64, '2.347G',
         '','frequency of interest (Hz)'),
        ("subid", coreapi.CONF_DATA_TYPE_UINT16, '1',
         '','subid'),
        ("systemnoisefigure", coreapi.CONF_DATA_TYPE_FLOAT, '4.0',
         '','system noise figure (dB)'),
        ("txpower", coreapi.CONF_DATA_TYPE_FLOAT, '0.0',
         '','transmit power (dBm)'),
    ]
    _confmatrix_081 = [
        ("antennagain", coreapi.CONF_DATA_TYPE_FLOAT, '0.0',
         '','antenna gain (dBi)'),
        ("antennaazimuth", coreapi.CONF_DATA_TYPE_FLOAT, '0.0',
         '','antenna azimuth (deg)'),
        ("antennaelevation", coreapi.CONF_DATA_TYPE_FLOAT, '0.0',
         '','antenna elevation (deg)'),
        ("antennaprofileid", coreapi.CONF_DATA_TYPE_STRING, '1',
         '','antenna profile ID'),
        ("antennaprofilemanifesturi", coreapi.CONF_DATA_TYPE_STRING, '',
         '','antenna profile manifest URI'),
        ("antennaprofileenable", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off','antenna profile mode'),
        ("defaultconnectivitymode", coreapi.CONF_DATA_TYPE_BOOL, '1',
         'On,Off','default connectivity'),
        ("frequencyofinterestfilterenable", coreapi.CONF_DATA_TYPE_BOOL, '1',
         'On,Off','frequency of interest filter enable'),
        ("noiseprocessingmode", coreapi.CONF_DATA_TYPE_BOOL, '0',
         'On,Off','enable noise processing'),
        ("pathlossmode", coreapi.CONF_DATA_TYPE_STRING, '2ray',
         'pathloss,2ray,freespace','path loss mode'),
    ]
    _confmatrix_091 = [
        ("fixedantennagain", coreapi.CONF_DATA_TYPE_FLOAT, '0.0',
         '','antenna gain (dBi)'),
        ("fixedantennagainenable", coreapi.CONF_DATA_TYPE_BOOL, '1',
         'On,Off','enable fixed antenna gain'),
        ("noisemode", coreapi.CONF_DATA_TYPE_STRING, 'none',
         'none,all,outofband','noise processing mode'),
        ("noisebinsize", coreapi.CONF_DATA_TYPE_UINT64, '20',
         '','noise bin size in microseconds'),
        ("propagationmodel", coreapi.CONF_DATA_TYPE_STRING, '2ray',
         'precomputed,2ray,freespace','path loss mode'),
    ]
    if Emane.version >= Emane.EMANE091:
        _confmatrix = _confmatrix_base + _confmatrix_091
    else:
        _confmatrix = _confmatrix_base + _confmatrix_081

    # old parameters
    _confmatrix_ver074 = [
        ("antennaazimuthbeamwidth", coreapi.CONF_DATA_TYPE_FLOAT, '360.0',
         '','azimith beam width (deg)'),
        ("antennaelevationbeamwidth", coreapi.CONF_DATA_TYPE_FLOAT, '180.0',
         '','elevation beam width (deg)'),
        ("antennatype", coreapi.CONF_DATA_TYPE_STRING, 'omnidirectional',
         'omnidirectional,unidirectional','antenna type'),
        ]

    # parameters that require unit conversion for 0.7.4
    _update_ver074 = ("bandwidth", "frequency", "frequencyofinterest")
    # parameters that should be removed for 0.7.4
    _remove_ver074 = ("antennaprofileenable", "antennaprofileid",
                      "antennaprofilemanifesturi",
                      "frequencyofinterestfilterenable")


    @classmethod
    def getphydoc(cls, e, mac, values, phynames):
        phydoc = e.xmldoc("phy")
        phy = phydoc.getElementsByTagName("phy").pop()
        phy.setAttribute("name", cls._xmlname)
        if e.version < e.EMANE091:
            phy.setAttribute("library", cls._xmllibrary)
        # EMANE 0.7.4 suppport - to be removed when 0.7.4 support is deprecated
        if e.version == e.EMANE074:
            names = mac.getnames()
            values = list(values)
            phynames = list(phynames)
            # update units for some parameters
            for p in cls._update_ver074:
                i = names.index(p)
                # these all happen to be KHz, so 1000 is used
                values[i] = cls.emane074_fixup(values[i], 1000)
            # remove new incompatible options
            for p in cls._remove_ver074:
                phynames.remove(p)
            # insert old options with their default values
            for old in cls._confmatrix_ver074:
                phy.appendChild(e.xmlparam(phydoc, old[0], old[2]))

        frequencies = None
        if e.version >= e.EMANE091:
            name = "frequencyofinterest"
            value = mac.valueof(name, values)
            frequencies = cls.valuestrtoparamlist(phydoc, name, value)
            if frequencies:
                phynames = list(phynames)
                phynames.remove("frequencyofinterest")

        # append all PHY options to phydoc
        map( lambda n: phy.appendChild(e.xmlparam(phydoc, n, \
                                       mac.valueof(n, values))), phynames)
        if frequencies:
            phy.appendChild(frequencies)
        return phydoc


