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


def get_requirements(use_ovs: bool) -> List[str]:
    """
    Retrieve executable requirements needed to run CORE.

    :param use_ovs: True if OVS is being used, False otherwise
    :return: list of executable requirements
    """
    requirements = COMMON_REQUIREMENTS
    if use_ovs:
        requirements += OVS_REQUIREMENTS
    else:
        requirements += VCMD_REQUIREMENTS
    return requirements
