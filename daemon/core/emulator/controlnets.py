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
DEFAULT_PREFIX_LIST: dict[int, str] = {
    0: "172.16.0.0/24 172.16.1.0/24 172.16.2.0/24 172.16.3.0/24 172.16.4.0/24",
    1: "172.17.0.0/24 172.17.1.0/24 172.17.2.0/24 172.17.3.0/24 172.17.4.0/24",
    2: "172.18.0.0/24 172.18.1.0/24 172.18.2.0/24 172.18.3.0/24 172.18.4.0/24",
    3: "172.19.0.0/24 172.19.1.0/24 172.19.2.0/24 172.19.3.0/24 172.19.4.0/24",
}


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

    def get_net_id(self, dev: str) -> int:
        """
        Retrieve control net id.

        :param dev: device to get control net id for
        :return: control net id, -1 otherwise
        """
        if dev[0:4] == "ctrl" and int(dev[4]) in (0, 1, 2, 3):
            _id = int(dev[4])
            if _id == 0:
                return _id
            if _id < 4 and self.net_prefixes[_id] is not None:
                return _id
        return -1

    def get_net(self, _id: int) -> Optional[CtrlNet]:
        """
        Retrieve a control net based on id.

        :param _id: id of control net to retrieve
        :return: control net when available, None otherwise
        """
        return self.session.control_nodes.get(_id)

    def setup_nets(self) -> None:
        """
        Setup all configured control nets.

        :return: nothing
        """
        for _id, prefix in self.net_prefixes.items():
            if prefix:
                self.add_net(_id)

    def add_net(self, _id: int, conf_required: bool = True) -> Optional[CtrlNet]:
        """
        Create a control network bridge as necessary. The conf_reqd flag,
        when False, causes a control network bridge to be added even if
        one has not been configured.

        :param _id: id of control net to add
        :param conf_required: flag to check if conf is required
        :return: control net node
        """
        logger.info(
            "checking to add control net(%s) conf_required(%s)", _id, conf_required
        )
        # check for valid id
        if not (0 <= _id <= 3):
            raise CoreError(f"invalid control net id({_id})")
        # return any existing control net bridge
        control_net = self.get_net(_id)
        if control_net:
            logger.info("control net(%s) already exists", _id)
            return control_net
        # retrieve prefix for current id
        id_prefix = self.net_prefixes[_id]
        if not id_prefix:
            if conf_required:
                return None
            else:
                id_prefix = DEFAULT_PREFIX_LIST[_id]
        # retrieve valid prefix from old style values
        prefixes = id_prefix.split()
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
        if _id == 0:
            updown_script = self.updown_script
        # build a new controlnet bridge
        server_iface = self.net_ifaces[_id]
        return self.session.create_control_net(_id, prefix, updown_script, server_iface)

    def remove_nets(self) -> None:
        """
        Removes control nets.

        :return: nothing
        """
        for _id in self.net_prefixes:
            control_net = self.session.control_nodes.pop(_id, None)
            if control_net:
                logger.info("shutting down control net(%s)", _id)
                control_net.shutdown()

    def setup_ifaces(self, node: CoreNode) -> None:
        """
        Setup all configured control net interfaces for node.

        :param node: node to configure control net interfaces for
        :return: nothing
        """
        for _id in self.net_prefixes:
            if self.get_net(_id):
                self.add_iface(node, _id)

    def add_iface(self, node: CoreNode, _id: int) -> None:
        """
        Adds a control net interface to a node.

        :param node: node to add control net interface to
        :param _id: id of control net to add interface to
        :return: nothing
        :raises CoreError: if control net doesn't exist, interface already exists,
            or there is an error creating the interface
        """
        control_net = self.get_net(_id)
        if not control_net:
            raise CoreError(f"control net id({_id}) does not exist")
        iface_id = CTRL_NET_IFACE_ID + _id
        if node.ifaces.get(iface_id):
            return
        try:
            logger.info(
                "node(%s) adding control net id(%s) interface(%s)",
                node.name,
                _id,
                iface_id,
            )
            ip4 = control_net.prefix[node.id]
            ip4_mask = control_net.prefix.prefixlen
            iface_data = InterfaceData(
                id=iface_id,
                name=f"ctrl{_id}",
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
