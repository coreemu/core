import logging
from typing import TYPE_CHECKING, Dict, Tuple

from core.emulator.data import LinkOptions
from core.emulator.links import CoreLink
from core.errors import CoreError
from core.executables import NFTABLES
from core.nodes.base import CoreNetworkBase
from core.nodes.interface import CoreInterface
from core.nodes.network import PtpNet

if TYPE_CHECKING:
    from core.emulator.session import Session
    from core.emulator.distributed import DistributedServer

logger = logging.getLogger(__name__)


class WirelessNode(CoreNetworkBase):
    def __init__(
        self,
        session: "Session",
        _id: int,
        name: str,
        server: "DistributedServer" = None,
    ):
        super().__init__(session, _id, name, server)
        self.bridges: Dict[int, Tuple[CoreInterface, str]] = {}
        self.links: Dict[Tuple[int, int], CoreLink] = {}

    def startup(self) -> None:
        if self.up:
            return
        self.up = True

    def shutdown(self) -> None:
        while self.bridges:
            _, (_, bridge_name) = self.bridges.popitem()
            self.net_client.delete_bridge(bridge_name)
            self.host_cmd(f"{NFTABLES} delete table bridge {bridge_name}")
        while self.links:
            key, core_link = self.links.popitem()
            core_link.iface1.shutdown()
            core_link.iface2.shutdown()
            core_link.ptp.shutdown()
        self.up = False

    def attach(self, iface: CoreInterface) -> None:
        super().attach(iface)
        logging.info("attaching node(%s) iface(%s)", iface.node.name, iface.name)
        if self.up:
            # create node unique bridge
            bridge_name = f"wb{iface.node.id}.{self.id}.{self.session.id}"
            self.net_client.create_bridge(bridge_name)
            # setup initial bridge rules
            self.host_cmd(f'{NFTABLES} "add table bridge {bridge_name}"')
            self.host_cmd(
                f"{NFTABLES} "
                f"'add chain bridge {bridge_name} forward {{type filter hook "
                f"forward priority -1; policy drop;}}'"
            )
            self.host_cmd(
                f"{NFTABLES} "
                f"'add rule bridge {bridge_name} forward "
                f"ibriport != {bridge_name} accept'"
            )
            # associate node iface with bridge
            iface.net_client.set_iface_master(bridge_name, iface.localname)
            # assign position callback
            iface.poshook = self.position_callback
            # save created bridge
            self.bridges[iface.node.id] = (iface, bridge_name)

    def post_startup(self) -> None:
        routes = {}
        for node_id, (iface, bridge_name) in self.bridges.items():
            for onode_id, (oiface, obridge_name) in self.bridges.items():
                if node_id == onode_id:
                    continue
                if node_id < onode_id:
                    node1, node2 = iface.node, oiface.node
                    bridge1, bridge2 = bridge_name, obridge_name
                else:
                    node1, node2 = oiface.node, iface.node
                    bridge1, bridge2 = obridge_name, bridge_name
                key = (node1.id, node2.id)
                if key in self.links:
                    continue
                # create node to node link
                session_id = self.session.short_session_id()
                name1 = f"we{self.id}.{node1.id}.{node2.id}.{session_id}"
                name2 = f"we{self.id}.{node2.id}.{node1.id}.{session_id}"
                iface1 = CoreInterface(0, name1, f"{name1}p", self.session.use_ovs())
                iface1.startup()
                iface2 = CoreInterface(0, name2, f"{name2}p", self.session.use_ovs())
                iface2.startup()
                link_name = f"wl{node1.id}.{node2.id}.{self.session.id}"
                ptp = PtpNet(self.session)
                ptp.brname = link_name
                ptp.startup()
                ptp.attach(iface1)
                ptp.attach(iface2)
                core_link = CoreLink(node1, iface1, node2, iface2, ptp)
                self.links[key] = core_link
                # assign ifaces to respective bridges
                self.net_client.set_iface_master(bridge1, iface1.name)
                self.net_client.set_iface_master(bridge2, iface2.name)
                # track bridge routes
                node1_routes = routes.setdefault(node1.id, set())
                node1_routes.add(name1)
                node2_routes = routes.setdefault(node2.id, set())
                node2_routes.add(name2)
        for node_id, ifaces in routes.items():
            iface, bridge_name = self.bridges[node_id]
            ifaces = ",".join(ifaces)
            # out routes
            self.host_cmd(
                f"{NFTABLES} "
                f'"add rule bridge {bridge_name} forward '
                f"iif {iface.localname} oif {{{ifaces}}} "
                f'accept"'
            )
            # in routes
            self.host_cmd(
                f"{NFTABLES} "
                f'"add rule bridge {bridge_name} forward '
                f"iif {{{ifaces}}} oif {iface.localname} "
                f'accept"'
            )

    def link_control(self, node1_id: int, node2_id: int, linked: bool) -> None:
        key = (node1_id, node2_id) if node1_id < node2_id else (node2_id, node1_id)
        core_link = self.links.get(key)
        if not core_link:
            raise CoreError(f"invalid node links node1({node1_id}) node2({node2_id})")
        ptp = core_link.ptp
        iface1, iface2 = core_link.iface1, core_link.iface2
        if linked:
            ptp.attach(iface1)
            ptp.attach(iface2)
        else:
            ptp.detach(iface1)
            ptp.detach(iface2)

    def link_config(
        self,
        node1_id: int,
        node2_id: int,
        iface1_options: LinkOptions,
        iface2_options: LinkOptions,
    ) -> None:
        key = (node1_id, node2_id) if node1_id < node2_id else (node2_id, node1_id)
        core_link = self.links.get(key)
        if not core_link:
            raise CoreError(f"invalid node links node1({node1_id}) node2({node2_id})")
        iface1, iface2 = core_link.iface1, core_link.iface2
        iface1.options.update(iface1_options)
        iface1.set_config()
        iface2.options.update(iface2_options)
        iface2.set_config()

    def position_callback(self, iface: CoreInterface) -> None:
        logger.info(
            "received position callback for node(%s) iface(%s)",
            iface.node.name,
            iface.name,
        )

    def adopt_iface(self, iface: CoreInterface, name: str) -> None:
        raise CoreError(f"{type(self)} does not support adopt interface")
