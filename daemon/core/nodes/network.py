"""
Defines network nodes used within core.
"""

import logging
import threading
from collections import OrderedDict
from pathlib import Path
from queue import Queue
from typing import TYPE_CHECKING, Dict, List, Optional, Type

import netaddr

from core import utils
from core.emulator.data import InterfaceData, LinkData
from core.emulator.enumerations import (
    LinkTypes,
    MessageFlags,
    NetworkPolicy,
    NodeTypes,
    RegisterTlvs,
)
from core.errors import CoreCommandError, CoreError
from core.executables import NFTABLES
from core.nodes.base import CoreNetworkBase, CoreNode
from core.nodes.interface import CoreInterface, GreTap, Veth
from core.nodes.netclient import get_net_client

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.distributed import DistributedServer
    from core.emulator.session import Session
    from core.location.mobility import WirelessModel, WayPointMobility

    WirelessModelType = Type[WirelessModel]

LEARNING_DISABLED: int = 0


class SetQueue(Queue):
    """
    Set backed queue to avoid duplicate submissions.
    """

    def _init(self, maxsize):
        self.queue: OrderedDict = OrderedDict()

    def _put(self, item):
        self.queue[item] = None

    def _get(self):
        key, _ = self.queue.popitem(last=False)
        return key


class NftablesQueue:
    """
    Helper class for queuing up nftables commands into rate-limited
    atomic commits. This improves performance and reliability when there are
    many WLAN link updates.
    """

    # update rate is every 300ms
    rate: float = 0.3
    atomic_file: str = "/tmp/pycore.nftables.atomic"
    chain: str = "forward"

    def __init__(self) -> None:
        """
        Initialize the helper class, but don't start the update thread
        until a WLAN is instantiated.
        """
        self.running: bool = False
        self.run_thread: Optional[threading.Thread] = None
        # this lock protects cmds and updates lists
        self.lock: threading.Lock = threading.Lock()
        # list of pending nftables commands
        self.cmds: List[str] = []
        # list of WLANs requiring update
        self.updates: SetQueue = SetQueue()

    def start(self) -> None:
        """
        Start thread to listen for updates for the provided network.

        :return: nothing
        """
        with self.lock:
            if not self.running:
                self.running = True
                self.run_thread = threading.Thread(target=self.run, daemon=True)
                self.run_thread.start()

    def stop(self) -> None:
        """
        Stop updates for network, when no networks remain, stop update thread.

        :return: nothing
        """
        with self.lock:
            if self.running:
                self.running = False
                self.updates.put(None)
                self.run_thread.join()
                self.run_thread = None

    def run(self) -> None:
        """
        Thread target that looks for networks needing update, and
        rate limits the amount of nftables activity. Only one userspace program
        should use nftables at any given time, or results can be unpredictable.

        :return: nothing
        """
        while self.running:
            net = self.updates.get()
            if net is None:
                break
            self.build_cmds(net)
            self.commit(net)

    def commit(self, net: "CoreNetwork") -> None:
        """
        Commit changes to nftables for the provided network.

        :param net: network to commit nftables changes
        :return: nothing
        """
        if not self.cmds:
            return
        # write out nft commands to file
        for cmd in self.cmds:
            net.host_cmd(f"echo {cmd} >> {self.atomic_file}", shell=True)
        # read file as atomic change
        net.host_cmd(f"{NFTABLES} -f {self.atomic_file}")
        # remove file
        net.host_cmd(f"rm -f {self.atomic_file}")
        self.cmds.clear()

    def update(self, net: "CoreNetwork") -> None:
        """
        Flag this network has an update, so the nftables chain will be rebuilt.

        :param net: wlan network
        :return: nothing
        """
        self.updates.put(net)

    def delete_table(self, net: "CoreNetwork") -> None:
        """
        Delete nftable bridge rule table.

        :param net: network to delete table for
        :return: nothing
        """
        with self.lock:
            net.host_cmd(f"{NFTABLES} delete table bridge {net.brname}")

    def build_cmds(self, net: "CoreNetwork") -> None:
        """
        Inspect linked nodes for a network, and rebuild the nftables chain commands.

        :param net: network to build commands for
        :return: nothing
        """
        with net.linked_lock:
            if net.has_nftables_chain:
                self.cmds.append(f"flush table bridge {net.brname}")
            else:
                net.has_nftables_chain = True
                policy = net.policy.value.lower()
                self.cmds.append(f"add table bridge {net.brname}")
                self.cmds.append(
                    f"add chain bridge {net.brname} {self.chain} {{type filter hook "
                    f"forward priority -1\\; policy {policy}\\;}}"
                )
            # add default rule to accept all traffic not for this bridge
            self.cmds.append(
                f"add rule bridge {net.brname} {self.chain} "
                f"ibriport != {net.brname} accept"
            )
            # rebuild the chain
            for iface1, v in net.linked.items():
                for iface2, linked in v.items():
                    policy = None
                    if net.policy == NetworkPolicy.DROP and linked:
                        policy = "accept"
                    elif net.policy == NetworkPolicy.ACCEPT and not linked:
                        policy = "drop"
                    if policy:
                        self.cmds.append(
                            f"add rule bridge {net.brname} {self.chain} "
                            f"iif {iface1.localname} oif {iface2.localname} "
                            f"{policy}"
                        )
                        self.cmds.append(
                            f"add rule bridge {net.brname} {self.chain} "
                            f"oif {iface1.localname} iif {iface2.localname} "
                            f"{policy}"
                        )


# a global object because all networks share the same queue
# cannot have multiple threads invoking the nftables commnd
nft_queue: NftablesQueue = NftablesQueue()


class CoreNetwork(CoreNetworkBase):
    """
    Provides linux bridge network functionality for core nodes.
    """

    policy: NetworkPolicy = NetworkPolicy.DROP

    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        server: "DistributedServer" = None,
        policy: NetworkPolicy = None,
    ) -> None:
        """
        Creates a LxBrNet instance.

        :param session: core session instance
        :param _id: object id
        :param name: object name
        :param server: remote server node
            will run on, default is None for localhost
        :param policy: network policy
        """
        super().__init__(session, _id, name, server)
        if name is None:
            name = str(self.id)
        if policy is not None:
            self.policy: NetworkPolicy = policy
        self.name: Optional[str] = name
        sessionid = self.session.short_session_id()
        self.brname: str = f"b.{self.id}.{sessionid}"
        self.has_nftables_chain: bool = False

    def host_cmd(
        self,
        args: str,
        env: Dict[str, str] = None,
        cwd: Path = None,
        wait: bool = True,
        shell: bool = False,
    ) -> str:
        """
        Runs a command that is used to configure and setup the network on the host
        system and all configured distributed servers.

        :param args: command to run
        :param env: environment to run command with
        :param cwd: directory to run command in
        :param wait: True to wait for status, False otherwise
        :param shell: True to use shell, False otherwise
        :return: combined stdout and stderr
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        logger.debug("network node(%s) cmd", self.name)
        output = utils.cmd(args, env, cwd, wait, shell)
        self.session.distributed.execute(lambda x: x.remote_cmd(args, env, cwd, wait))
        return output

    def startup(self) -> None:
        """
        Linux bridge startup logic.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        self.net_client.create_bridge(self.brname)
        if self.mtu > 0:
            self.net_client.set_mtu(self.brname, self.mtu)
        self.has_nftables_chain = False
        self.up = True
        nft_queue.start()

    def shutdown(self) -> None:
        """
        Linux bridge shutdown logic.

        :return: nothing
        """
        if not self.up:
            return
        nft_queue.stop()
        try:
            self.net_client.delete_bridge(self.brname)
            if self.has_nftables_chain:
                nft_queue.delete_table(self)
        except CoreCommandError:
            logging.exception("error during shutdown")
        # removes veth pairs used for bridge-to-bridge connections
        for iface in self.get_ifaces():
            iface.shutdown()
        self.ifaces.clear()
        self.linked.clear()
        self.up = False

    def attach(self, iface: CoreInterface) -> None:
        """
        Attach a network interface.

        :param iface: network interface to attach
        :return: nothing
        """
        if self.up:
            iface.net_client.set_iface_master(self.brname, iface.localname)
        super().attach(iface)

    def detach(self, iface: CoreInterface) -> None:
        """
        Detach a network interface.

        :param iface: network interface to detach
        :return: nothing
        """
        if self.up:
            iface.net_client.delete_iface(self.brname, iface.localname)
        super().detach(iface)

    def is_linked(self, iface1: CoreInterface, iface2: CoreInterface) -> bool:
        """
        Determine if the provided network interfaces are linked.

        :param iface1: interface one
        :param iface2: interface two
        :return: True if interfaces are linked, False otherwise
        """
        # check if the network interfaces are attached to this network
        if self.ifaces[iface1.net_id] != iface1:
            raise ValueError(f"inconsistency for interface {iface1.name}")
        if self.ifaces[iface2.net_id] != iface2:
            raise ValueError(f"inconsistency for interface {iface2.name}")
        try:
            linked = self.linked[iface1][iface2]
        except KeyError:
            if self.policy == NetworkPolicy.ACCEPT:
                linked = True
            elif self.policy == NetworkPolicy.DROP:
                linked = False
            else:
                raise Exception(f"unknown policy: {self.policy.value}")
            self.linked[iface1][iface2] = linked
        return linked

    def unlink(self, iface1: CoreInterface, iface2: CoreInterface) -> None:
        """
        Unlink two interfaces, resulting in adding or removing filtering rules.

        :param iface1: interface one
        :param iface2: interface two
        :return: nothing
        """
        with self.linked_lock:
            if not self.is_linked(iface1, iface2):
                return
            self.linked[iface1][iface2] = False
        nft_queue.update(self)

    def link(self, iface1: CoreInterface, iface2: CoreInterface) -> None:
        """
        Link two interfaces together, resulting in adding or removing
        filtering rules.

        :param iface1: interface one
        :param iface2: interface two
        :return: nothing
        """
        with self.linked_lock:
            if self.is_linked(iface1, iface2):
                return
            self.linked[iface1][iface2] = True
        nft_queue.update(self)

    def linknet(self, net: CoreNetworkBase) -> CoreInterface:
        """
        Link this bridge with another by creating a veth pair and installing
        each device into each bridge.

        :param net: network to link with
        :return: created interface
        """
        sessionid = self.session.short_session_id()
        try:
            _id = f"{self.id:x}"
        except TypeError:
            _id = str(self.id)
        try:
            net_id = f"{net.id:x}"
        except TypeError:
            net_id = str(net.id)
        localname = f"veth{_id}.{net_id}.{sessionid}"
        name = f"veth{net_id}.{_id}.{sessionid}"
        iface = Veth(self.session, name, localname)
        if self.up:
            iface.startup()
        self.attach(iface)
        if net.up and net.brname:
            iface.net_client.set_iface_master(net.brname, iface.name)
        i = net.next_iface_id()
        net.ifaces[i] = iface
        with net.linked_lock:
            net.linked[iface] = {}
        iface.net = self
        iface.othernet = net
        return iface

    def get_linked_iface(self, net: CoreNetworkBase) -> Optional[CoreInterface]:
        """
        Return the interface of that links this net with another net
        (that were linked using linknet()).

        :param net: interface to get link for
        :return: interface the provided network is linked to
        """
        for iface in self.get_ifaces():
            if iface.othernet == net:
                return iface
        return None

    def add_ips(self, ips: List[str]) -> None:
        """
        Add ip addresses on the bridge in the format "10.0.0.1/24".

        :param ips: ip address to add
        :return: nothing
        """
        if not self.up:
            return
        for ip in ips:
            self.net_client.create_address(self.brname, ip)

    def custom_iface(self, node: CoreNode, iface_data: InterfaceData) -> CoreInterface:
        raise CoreError(f"{type(self).__name__} does not support, custom interfaces")


class GreTapBridge(CoreNetwork):
    """
    A network consisting of a bridge with a gretap device for tunneling to
    another system.
    """

    def __init__(
        self,
        session: "Session",
        remoteip: str = None,
        _id: int = None,
        name: str = None,
        policy: NetworkPolicy = NetworkPolicy.ACCEPT,
        localip: str = None,
        ttl: int = 255,
        key: int = None,
        server: "DistributedServer" = None,
    ) -> None:
        """
        Create a GreTapBridge instance.

        :param session: core session instance
        :param remoteip: remote address
        :param _id: object id
        :param name: object name
        :param policy: network policy
        :param localip: local address
        :param ttl: ttl value
        :param key: gre tap key
        :param server: remote server node
            will run on, default is None for localhost
        """
        CoreNetwork.__init__(self, session, _id, name, server, policy)
        if key is None:
            key = self.session.id ^ self.id
        self.grekey: int = key
        self.localnum: Optional[int] = None
        self.remotenum: Optional[int] = None
        self.remoteip: Optional[str] = remoteip
        self.localip: Optional[str] = localip
        self.ttl: int = ttl
        self.gretap: Optional[GreTap] = None
        if self.remoteip is not None:
            self.gretap = GreTap(
                session,
                remoteip,
                key=self.grekey,
                node=self,
                localip=localip,
                ttl=ttl,
                mtu=self.mtu,
            )

    def startup(self) -> None:
        """
        Creates a bridge and adds the gretap device to it.

        :return: nothing
        """
        super().startup()
        if self.gretap:
            self.gretap.startup()
            self.attach(self.gretap)

    def shutdown(self) -> None:
        """
        Detach the gretap device and remove the bridge.

        :return: nothing
        """
        if self.gretap:
            self.detach(self.gretap)
            self.gretap.shutdown()
            self.gretap = None
        super().shutdown()

    def add_ips(self, ips: List[str]) -> None:
        """
        Set the remote tunnel endpoint. This is a one-time method for
        creating the GreTap device, which requires the remoteip at startup.
        The 1st address in the provided list is remoteip, 2nd optionally
        specifies localip.

        :param ips: address list
        :return: nothing
        """
        if self.gretap:
            raise CoreError(f"gretap already exists for {self.name}")
        remoteip = ips[0].split("/")[0]
        localip = None
        if len(ips) > 1:
            localip = ips[1].split("/")[0]
        self.gretap = GreTap(
            self.session,
            remoteip,
            key=self.grekey,
            localip=localip,
            ttl=self.ttl,
            mtu=self.mtu,
        )
        self.startup()
        self.attach(self.gretap)

    def setkey(self, key: int, iface_data: InterfaceData) -> None:
        """
        Set the GRE key used for the GreTap device. This needs to be set
        prior to instantiating the GreTap device (before addrconfig).

        :param key: gre key
        :param iface_data: interface data for setting up tunnel key
        :return: nothing
        """
        self.grekey = key
        ips = iface_data.get_ips()
        if ips:
            self.add_ips(ips)


class CtrlNet(CoreNetwork):
    """
    Control network functionality.
    """

    policy: NetworkPolicy = NetworkPolicy.ACCEPT
    # base control interface index
    CTRLIF_IDX_BASE: int = 99
    DEFAULT_PREFIX_LIST: List[str] = [
        "172.16.0.0/24 172.16.1.0/24 172.16.2.0/24 172.16.3.0/24 172.16.4.0/24",
        "172.17.0.0/24 172.17.1.0/24 172.17.2.0/24 172.17.3.0/24 172.17.4.0/24",
        "172.18.0.0/24 172.18.1.0/24 172.18.2.0/24 172.18.3.0/24 172.18.4.0/24",
        "172.19.0.0/24 172.19.1.0/24 172.19.2.0/24 172.19.3.0/24 172.19.4.0/24",
    ]

    def __init__(
        self,
        session: "Session",
        prefix: str,
        _id: int = None,
        name: str = None,
        hostid: int = None,
        server: "DistributedServer" = None,
        assign_address: bool = True,
        updown_script: str = None,
        serverintf: str = None,
    ) -> None:
        """
        Creates a CtrlNet instance.

        :param session: core session instance
        :param _id: node id
        :param name: node namee
        :param prefix: control network ipv4 prefix
        :param hostid: host id
        :param server: remote server node
            will run on, default is None for localhost
        :param assign_address: assigned address
        :param updown_script: updown script
        :param serverintf: server interface
        :return:
        """
        self.prefix: netaddr.IPNetwork = netaddr.IPNetwork(prefix).cidr
        self.hostid: Optional[int] = hostid
        self.assign_address: bool = assign_address
        self.updown_script: Optional[str] = updown_script
        self.serverintf: Optional[str] = serverintf
        super().__init__(session, _id, name, server)

    def add_addresses(self, index: int) -> None:
        """
        Add addresses used for created control networks,

        :param index: starting address index
        :return: nothing
        """
        use_ovs = self.session.use_ovs()
        address = self.prefix[index]
        current = f"{address}/{self.prefix.prefixlen}"
        net_client = get_net_client(use_ovs, utils.cmd)
        net_client.create_address(self.brname, current)
        servers = self.session.distributed.servers
        for name in servers:
            server = servers[name]
            index -= 1
            address = self.prefix[index]
            current = f"{address}/{self.prefix.prefixlen}"
            net_client = get_net_client(use_ovs, server.remote_cmd)
            net_client.create_address(self.brname, current)

    def startup(self) -> None:
        """
        Startup functionality for the control network.

        :return: nothing
        :raises CoreCommandError: when there is a command exception
        """
        if self.net_client.existing_bridges(self.id):
            raise CoreError(f"old bridges exist for node: {self.id}")

        super().startup()
        logger.info("added control network bridge: %s %s", self.brname, self.prefix)

        if self.hostid and self.assign_address:
            self.add_addresses(self.hostid)
        elif self.assign_address:
            self.add_addresses(-2)

        if self.updown_script:
            logger.info(
                "interface %s updown script (%s startup) called",
                self.brname,
                self.updown_script,
            )
            self.host_cmd(f"{self.updown_script} {self.brname} startup")

        if self.serverintf:
            self.net_client.set_iface_master(self.brname, self.serverintf)

    def shutdown(self) -> None:
        """
        Control network shutdown.

        :return: nothing
        """
        if self.serverintf is not None:
            try:
                self.net_client.delete_iface(self.brname, self.serverintf)
            except CoreCommandError:
                logger.exception(
                    "error deleting server interface %s from bridge %s",
                    self.serverintf,
                    self.brname,
                )

        if self.updown_script is not None:
            try:
                logger.info(
                    "interface %s updown script (%s shutdown) called",
                    self.brname,
                    self.updown_script,
                )
                self.host_cmd(f"{self.updown_script} {self.brname} shutdown")
            except CoreCommandError:
                logger.exception("error issuing shutdown script shutdown")

        super().shutdown()

    def links(self, flags: MessageFlags = MessageFlags.NONE) -> List[LinkData]:
        """
        Do not include CtrlNet in link messages describing this session.

        :param flags: message flags
        :return: list of link data
        """
        return []


class PtpNet(CoreNetwork):
    """
    Peer to peer network node.
    """

    policy: NetworkPolicy = NetworkPolicy.ACCEPT

    def attach(self, iface: CoreInterface) -> None:
        """
        Attach a network interface, but limit attachment to two interfaces.

        :param iface: network interface
        :return: nothing
        """
        if len(self.ifaces) >= 2:
            raise CoreError("ptp links support at most 2 network interfaces")
        super().attach(iface)

    def links(self, flags: MessageFlags = MessageFlags.NONE) -> List[LinkData]:
        """
        Build CORE API TLVs for a point-to-point link. One Link message
        describes this network.

        :param flags: message flags
        :return: list of link data
        """
        all_links = []
        if len(self.ifaces) != 2:
            return all_links
        ifaces = self.get_ifaces()
        iface1 = ifaces[0]
        iface2 = ifaces[1]
        unidirectional = 0 if iface1.local_options == iface2.local_options else 1
        iface1_data = iface1.get_data()
        iface2_data = iface2.get_data()
        link_data = LinkData(
            message_type=flags,
            type=self.linktype,
            node1_id=iface1.node.id,
            node2_id=iface2.node.id,
            iface1=iface1_data,
            iface2=iface2_data,
            options=iface1.local_options,
        )
        link_data.options.unidirectional = unidirectional
        all_links.append(link_data)
        # build a 2nd link message for the upstream link parameters
        # (swap if1 and if2)
        if unidirectional:
            link_data = LinkData(
                message_type=MessageFlags.NONE,
                type=self.linktype,
                node1_id=iface2.node.id,
                node2_id=iface1.node.id,
                iface1=InterfaceData(id=iface2_data.id),
                iface2=InterfaceData(id=iface1_data.id),
                options=iface2.local_options,
            )
            link_data.options.unidirectional = unidirectional
            all_links.append(link_data)
        return all_links


class SwitchNode(CoreNetwork):
    """
    Provides switch functionality within a core node.
    """

    apitype: NodeTypes = NodeTypes.SWITCH
    policy: NetworkPolicy = NetworkPolicy.ACCEPT
    type: str = "lanswitch"


class HubNode(CoreNetwork):
    """
    Provides hub functionality within a core node, forwards packets to all bridge
    ports by turning off MAC address learning.
    """

    apitype: NodeTypes = NodeTypes.HUB
    policy: NetworkPolicy = NetworkPolicy.ACCEPT
    type: str = "hub"

    def startup(self) -> None:
        """
        Startup for a hub node, that disables mac learning after normal startup.

        :return: nothing
        """
        super().startup()
        self.net_client.set_mac_learning(self.brname, LEARNING_DISABLED)


class WlanNode(CoreNetwork):
    """
    Provides wireless lan functionality within a core node.
    """

    apitype: NodeTypes = NodeTypes.WIRELESS_LAN
    linktype: LinkTypes = LinkTypes.WIRED
    policy: NetworkPolicy = NetworkPolicy.DROP
    type: str = "wlan"

    def __init__(
        self,
        session: "Session",
        _id: int = None,
        name: str = None,
        server: "DistributedServer" = None,
        policy: NetworkPolicy = None,
    ) -> None:
        """
        Create a WlanNode instance.

        :param session: core session instance
        :param _id: node id
        :param name: node name
        :param server: remote server node
            will run on, default is None for localhost
        :param policy: wlan policy
        """
        super().__init__(session, _id, name, server, policy)
        # wireless and mobility models (BasicRangeModel, Ns2WaypointMobility)
        self.model: Optional[WirelessModel] = None
        self.mobility: Optional[WayPointMobility] = None

    def startup(self) -> None:
        """
        Startup for a wlan node, that disables mac learning after normal startup.

        :return: nothing
        """
        super().startup()
        nft_queue.update(self)

    def attach(self, iface: CoreInterface) -> None:
        """
        Attach a network interface.

        :param iface: network interface
        :return: nothing
        """
        super().attach(iface)
        if self.model:
            iface.poshook = self.model.position_callback
            iface.setposition()

    def setmodel(self, model: "WirelessModelType", config: Dict[str, str]):
        """
        Sets the mobility and wireless model.

        :param model: wireless model to set to
        :param config: configuration for model being set
        :return: nothing
        """
        logger.debug("node(%s) setting model: %s", self.name, model.name)
        if model.config_type == RegisterTlvs.WIRELESS:
            self.model = model(session=self.session, _id=self.id)
            for iface in self.get_ifaces():
                iface.poshook = self.model.position_callback
                iface.setposition()
            self.updatemodel(config)
        elif model.config_type == RegisterTlvs.MOBILITY:
            self.mobility = model(session=self.session, _id=self.id)
            self.mobility.update_config(config)

    def update_mobility(self, config: Dict[str, str]) -> None:
        if not self.mobility:
            raise CoreError(f"no mobility set to update for node({self.name})")
        self.mobility.update_config(config)

    def updatemodel(self, config: Dict[str, str]) -> None:
        if not self.model:
            raise CoreError(f"no model set to update for node({self.name})")
        logger.debug(
            "node(%s) updating model(%s): %s", self.id, self.model.name, config
        )
        self.model.update_config(config)
        for iface in self.get_ifaces():
            iface.setposition()

    def links(self, flags: MessageFlags = MessageFlags.NONE) -> List[LinkData]:
        """
        Retrieve all link data.

        :param flags: message flags
        :return: list of link data
        """
        links = super().links(flags)
        if self.model:
            links.extend(self.model.links(flags))
        return links


class TunnelNode(GreTapBridge):
    """
    Provides tunnel functionality in a core node.
    """

    apitype: NodeTypes = NodeTypes.TUNNEL
    policy: NetworkPolicy = NetworkPolicy.ACCEPT
    type: str = "tunnel"
