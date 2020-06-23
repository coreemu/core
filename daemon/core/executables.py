from typing import List

VNODED_BIN: str = "vnoded"
VCMD_BIN: str = "vcmd"
SYSCTL_BIN: str = "sysctl"
IP_BIN: str = "ip"
ETHTOOL_BIN: str = "ethtool"
TC_BIN: str = "tc"
EBTABLES_BIN: str = "ebtables"
MOUNT_BIN: str = "mount"
UMOUNT_BIN: str = "umount"
OVS_BIN: str = "ovs-vsctl"

COMMON_REQUIREMENTS: List[str] = [
    SYSCTL_BIN,
    IP_BIN,
    ETHTOOL_BIN,
    TC_BIN,
    EBTABLES_BIN,
    MOUNT_BIN,
    UMOUNT_BIN,
]
VCMD_REQUIREMENTS: List[str] = [VNODED_BIN, VCMD_BIN]
OVS_REQUIREMENTS: List[str] = [OVS_BIN]
