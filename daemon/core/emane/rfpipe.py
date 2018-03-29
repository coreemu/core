"""
rfpipe.py: EMANE RF-PIPE model for CORE
"""

from core.emane.emanemodel import EmaneModel
from core.enumerations import ConfigDataTypes


class EmaneRfPipeModel(EmaneModel):
    # model name
    name = "emane_rfpipe"
    library = "rfpipemaclayer"

    # mac configuration
    xml_path = "/usr/share/emane/xml/models/mac/rfpipe"
    _config_mac = [
        ("datarate", ConfigDataTypes.UINT64.value, "1M", "", "data rate (bps)"),
        ("delay", ConfigDataTypes.FLOAT.value, "0.0", "", "transmission delay (sec)"),
        ("enablepromiscuousmode", ConfigDataTypes.BOOL.value, "0", "True,False", "enable promiscuous mode"),
        ("flowcontrolenable", ConfigDataTypes.BOOL.value, "0", "On,Off", "enable traffic flow control"),
        ("flowcontroltokens", ConfigDataTypes.UINT16.value, "10", "", "number of flow control tokens"),
        ("jitter", ConfigDataTypes.FLOAT.value, "0.0", "", "transmission jitter (sec)"),
        ("neighbormetricdeletetime", ConfigDataTypes.FLOAT.value, "60.0", "",
         "R2RI neighbor table inactivity time (sec)"),
        ("pcrcurveuri", ConfigDataTypes.STRING.value, "%s/rfpipepcr.xml" % xml_path, "", "SINR/PCR curve file"),
        ("radiometricenable", ConfigDataTypes.BOOL.value, "0", "On,Off", "report radio metrics via R2RI"),
        ("radiometricreportinterval", ConfigDataTypes.FLOAT.value, "1.0", "",
         "R2RI radio metric report interval (sec)"),
    ]
