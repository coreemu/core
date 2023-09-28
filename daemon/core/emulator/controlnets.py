import logging
from typing import TYPE_CHECKING, Optional

from core import utils
from core.emulator.data import InterfaceData
from core.emulator.sessionconfig import SessionConfig
from core.errors import CoreError
from core.nodes.base import CoreNode
from core.nodes.interface import DEFAULT_MTU
from core.nodes.network import CtrlNet

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.session import Session

CTRL_NET_ID: int = 9001
CTRL_NET_IFACE_ID: int = 99
ETC_HOSTS_PATH: str = "/etc/hosts"
DEFAULT_PREFIX_LIST: list[str] = [
    "172.16.0.0/24 172.16.1.0/24 172.16.2.0/24 172.16.3.0/24 172.16.4.0/24",
    "172.17.0.0/24 172.17.1.0/24 172.17.2.0/24 172.17.3.0/24 172.17.4.0/24",
    "172.18.0.0/24 172.18.1.0/24 172.18.2.0/24 172.18.3.0/24 172.18.4.0/24",
    "172.19.0.0/24 172.19.1.0/24 172.19.2.0/24 172.19.3.0/24 172.19.4.0/24",
]


def control_net_id(index: int) -> int:
    """
    Returns control net id to use, based on provided index.

    :param index: index to get control net id for
    :return: control net id
    """
    return CTRL_NET_ID + index


class ControlNetManager:
    def __init__(self, session: "Session") -> None:
        self.session: "Session" = session
        self.etc_hosts_header: str = f"CORE session {self.session.id} host entries"
        self.etc_hosted_enabled: bool = False
        self.net_prefixes: dict[int, Optional[str]] = {}
        self.net_ifaces: dict[int, Optional[str]] = {}
        self.updown_script: Optional[str] = None
        self.parse_options(session.options)

    def parse_options(self, options: SessionConfig) -> None:
        """
        Parse session options for current settings to use.

        :param options: options to parse
        :return: nothing
        """
        self.etc_hosted_enabled: bool = options.get_bool("update_etc_hosts", False)
        default_net = options.get("controlnet") or None
        self.net_prefixes = {
            0: (options.get("controlnet0") or None) or default_net,
            1: options.get("controlnet1") or None,
            2: options.get("controlnet2") or None,
            3: options.get("controlnet3") or None,
        }
        self.net_ifaces = {
            0: None,
            1: options.get("controlnetif1") or None,
            2: options.get("controlnetif2") or None,
            3: options.get("controlnetif3") or None,
        }
        self.updown_script = options.get("controlnet_updown_script") or None

    def update_etc_hosts(self) -> None:
        """
        Add the IP addresses of control interfaces to the /etc/hosts file.

        :return: nothing
        """
        if not self.etc_hosted_enabled:
            return
        control_net = self.get_net(0)
        entries = ""
        for iface in control_net.get_ifaces():
            name = iface.node.name
            for ip in iface.ips():
                entries += f"{ip.ip} {name}\n"
        logger.info("adding entries to /etc/hosts")
        utils.file_munge(ETC_HOSTS_PATH, self.etc_hosts_header, entries)

    def clear_etc_hosts(self) -> None:
        """
        Clear IP addresses of control interfaces from the /etc/hosts file.

        :return: nothing
        """
        if not self.etc_hosted_enabled:
            return
        logger.info("removing /etc/hosts file entries")
        utils.file_demunge(ETC_HOSTS_PATH, self.etc_hosts_header)

    def get_net_index(self, dev: str) -> int:
        """
        Retrieve control net index.

        :param dev: device to get control net index for
        :return: control net index, -1 otherwise
        """
        if dev[0:4] == "ctrl" and int(dev[4]) in (0, 1, 2, 3):
            index = int(dev[4])
            if index == 0:
                return index
            if index < 4 and self.net_prefixes[index] is not None:
                return index
        return -1

    def get_net(self, index: int) -> Optional[CtrlNet]:
        """
        Retrieve a control net based on index.

        :param index: control net index
        :return: control net when available, None otherwise
        """
        try:
            _id = control_net_id(index)
            return self.session.get_node(_id, CtrlNet)
        except CoreError:
            return None

    def add_net(self, index: int, conf_required: bool = True) -> Optional[CtrlNet]:
        """
        Create a control network bridge as necessary. The conf_reqd flag,
        when False, causes a control network bridge to be added even if
        one has not been configured.

        :param index: network index to add
        :param conf_required: flag to check if conf is required
        :return: control net node
        """
        logger.info(
            "checking to add control net index(%s) conf_required(%s)",
            index,
            conf_required,
        )
        # check for valid index
        if not (0 <= index <= 3):
            raise CoreError(f"invalid control net index({index})")
        # return any existing control net bridge
        control_net = self.get_net(index)
        if control_net:
            logger.info("control net index(%s) already exists", index)
            return control_net
        # retrieve prefix for current index
        index_prefix = self.net_prefixes[index]
        if not index_prefix:
            if conf_required:
                return None
            else:
                index_prefix = DEFAULT_PREFIX_LIST[index]
        # retrieve valid prefix from old style values
        prefixes = index_prefix.split()
        if len(prefixes) > 1:
            # a list of per-host prefixes is provided
            try:
                prefix = prefixes[0].split(":", 1)[1]
            except IndexError:
                prefix = prefixes[0]
        else:
            prefix = prefixes[0]
        # use the updown script for control net 0 only
        updown_script = None
        if index == 0:
            updown_script = self.updown_script
        # build a new controlnet bridge
        _id = control_net_id(index)
        server_iface = self.net_ifaces[index]
        logger.info(
            "adding controlnet(%s) prefix(%s) updown(%s) server interface(%s)",
            _id,
            prefix,
            updown_script,
            server_iface,
        )
        options = CtrlNet.create_options()
        options.prefix = prefix
        options.updown_script = updown_script
        options.serverintf = server_iface
        control_net = self.session.create_node(CtrlNet, False, _id, options=options)
        control_net.brname = f"ctrl{index}.{self.session.short_session_id()}"
        control_net.startup()
        return control_net

    def remove_net(self, index: int) -> None:
        """
        Removes control net.

        :param index: index of control net to remove
        :return: nothing
        """
        control_net = self.get_net(index)
        if control_net:
            logger.info("removing control net index(%s)", index)
            self.session.delete_node(control_net.id)

    def add_iface(self, node: CoreNode, index: int) -> None:
        """
        Adds a control net interface to a node.

        :param node: node to add control net interface to
        :param index: index of control net to add interface to
        :return: nothing
        :raises CoreError: if control net doesn't exist, interface already exists,
            or there is an error creating the interface
        """
        control_net = self.get_net(index)
        if not control_net:
            raise CoreError(f"control net index({index}) does not exist")
        iface_id = CTRL_NET_IFACE_ID + index
        if node.ifaces.get(iface_id):
            raise CoreError(f"control iface({iface_id}) already exists")
        try:
            logger.info(
                "node(%s) adding control net index(%s) interface(%s)",
                node.name,
                index,
                iface_id,
            )
            ip4 = control_net.prefix[node.id]
            ip4_mask = control_net.prefix.prefixlen
            iface_data = InterfaceData(
                id=iface_id,
                name=f"ctrl{index}",
                mac=utils.random_mac(),
                ip4=ip4,
                ip4_mask=ip4_mask,
                mtu=DEFAULT_MTU,
            )
            iface = node.create_iface(iface_data)
            control_net.attach(iface)
            iface.control = True
        except ValueError:
            raise CoreError(
                f"error adding control net interface to node({node.id}), "
                f"invalid control net prefix({control_net.prefix}), "
                "a longer prefix length may be required"
            )
