from typing import List

VNODED: str = "vnoded"
VCMD: str = "vcmd"
SYSCTL: str = "sysctl"
IP: str = "ip"
ETHTOOL: str = "ethtool"
TC: str = "tc"
EBTABLES: str = "ebtables"
MOUNT: str = "mount"
UMOUNT: str = "umount"
OVS_VSCTL: str = "ovs-vsctl"

COMMON_REQUIREMENTS: List[str] = [SYSCTL, IP, ETHTOOL, TC, EBTABLES, MOUNT, UMOUNT]
VCMD_REQUIREMENTS: List[str] = [VNODED, VCMD]
OVS_REQUIREMENTS: List[str] = [OVS_VSCTL]
