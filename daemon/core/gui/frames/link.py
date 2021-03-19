import tkinter as tk
from typing import TYPE_CHECKING, Optional

from core.api.grpc.wrappers import Interface
from core.gui.frames.base import DetailsFrame, InfoFrameBase
from core.gui.utils import bandwidth_text

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.edges import CanvasEdge
    from core.gui.graph.node import CanvasNode
    from core.gui.graph.edges import CanvasWirelessEdge


def get_iface(canvas_node: "CanvasNode", net_id: int) -> Optional[Interface]:
    iface = None
    for edge in canvas_node.edges:
        link = edge.link
        if link.node1_id == net_id:
            iface = link.iface2
        elif link.node2_id == net_id:
            iface = link.iface1
    return iface


class EdgeInfoFrame(InfoFrameBase):
    def __init__(
        self, master: tk.BaseWidget, app: "Application", edge: "CanvasEdge"
    ) -> None:
        super().__init__(master, app)
        self.edge: "CanvasEdge" = edge

    def draw(self) -> None:
        self.columnconfigure(0, weight=1)
        link = self.edge.link
        options = link.options
        src_node = self.app.core.session.nodes[link.node1_id]
        dst_node = self.app.core.session.nodes[link.node2_id]

        frame = DetailsFrame(self)
        frame.grid(sticky=tk.EW)
        frame.add_detail("Source", src_node.name)
        iface1 = link.iface1
        if iface1:
            mac = iface1.mac if iface1.mac else "auto"
            frame.add_detail("MAC", mac)
            ip4 = f"{iface1.ip4}/{iface1.ip4_mask}" if iface1.ip4 else ""
            frame.add_detail("IP4", ip4)
            ip6 = f"{iface1.ip6}/{iface1.ip6_mask}" if iface1.ip6 else ""
            frame.add_detail("IP6", ip6)

        frame.add_separator()
        frame.add_detail("Destination", dst_node.name)
        iface2 = link.iface2
        if iface2:
            mac = iface2.mac if iface2.mac else "auto"
            frame.add_detail("MAC", mac)
            ip4 = f"{iface2.ip4}/{iface2.ip4_mask}" if iface2.ip4 else ""
            frame.add_detail("IP4", ip4)
            ip6 = f"{iface2.ip6}/{iface2.ip6_mask}" if iface2.ip6 else ""
            frame.add_detail("IP6", ip6)

        if link.options:
            frame.add_separator()
            bandwidth = bandwidth_text(options.bandwidth)
            frame.add_detail("Bandwidth", bandwidth)
            frame.add_detail("Delay", f"{options.delay} us")
            frame.add_detail("Jitter", f"\u00B1{options.jitter} us")
            frame.add_detail("Loss", f"{options.loss}%")
            frame.add_detail("Duplicate", f"{options.dup}%")


class WirelessEdgeInfoFrame(InfoFrameBase):
    def __init__(
        self, master: tk.BaseWidget, app: "Application", edge: "CanvasWirelessEdge"
    ) -> None:
        super().__init__(master, app)
        self.edge: "CanvasWirelessEdge" = edge

    def draw(self) -> None:
        link = self.edge.link
        src_node = self.edge.src.core_node
        dst_node = self.edge.dst.core_node

        # find interface for each node connected to network
        net_id = link.network_id
        iface1 = get_iface(self.edge.src, net_id)
        iface2 = get_iface(self.edge.dst, net_id)

        frame = DetailsFrame(self)
        frame.grid(sticky=tk.EW)
        frame.add_detail("Source", src_node.name)
        if iface1:
            mac = iface1.mac if iface1.mac else "auto"
            frame.add_detail("MAC", mac)
            ip4 = f"{iface1.ip4}/{iface1.ip4_mask}" if iface1.ip4 else ""
            frame.add_detail("IP4", ip4)
            ip6 = f"{iface1.ip6}/{iface1.ip6_mask}" if iface1.ip6 else ""
            frame.add_detail("IP6", ip6)

        frame.add_separator()
        frame.add_detail("Destination", dst_node.name)
        if iface2:
            mac = iface2.mac if iface2.mac else "auto"
            frame.add_detail("MAC", mac)
            ip4 = f"{iface2.ip4}/{iface2.ip4_mask}" if iface2.ip4 else ""
            frame.add_detail("IP4", ip4)
            ip6 = f"{iface2.ip6}/{iface2.ip6_mask}" if iface2.ip6 else ""
            frame.add_detail("IP6", ip6)
