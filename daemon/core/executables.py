from typing import List

BASH: str = "bash"
ETHTOOL: str = "ethtool"
IP: str = "ip"
MOUNT: str = "mount"
NFTABLES: str = "nft"
OVS_VSCTL: str = "ovs-vsctl"
SYSCTL: str = "sysctl"
TC: str = "tc"
TEST: str = "test"
UMOUNT: str = "umount"
VCMD: str = "vcmd"
VNODED: str = "vnoded"

COMMON_REQUIREMENTS: List[str] = [
    BASH,
    ETHTOOL,
    IP,
    MOUNT,
    NFTABLES,
    SYSCTL,
    TC,
    TEST,
    UMOUNT,
    VCMD,
    VNODED,
]
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
    return requirements
