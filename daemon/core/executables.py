from typing import List

BASH: str = "bash"
VNODED: str = "vnoded"
VCMD: str = "vcmd"
SYSCTL: str = "sysctl"
IP: str = "ip"
ETHTOOL: str = "ethtool"
TC: str = "tc"
MOUNT: str = "mount"
UMOUNT: str = "umount"
OVS_VSCTL: str = "ovs-vsctl"
TEST: str = "test"
NFTABLES: str = "nft"

COMMON_REQUIREMENTS: List[str] = [
    BASH,
    NFTABLES,
    ETHTOOL,
    IP,
    MOUNT,
    SYSCTL,
    TC,
    UMOUNT,
    TEST,
]
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
