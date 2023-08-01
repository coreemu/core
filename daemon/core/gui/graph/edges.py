import functools
import logging
import math
import tkinter as tk
from typing import TYPE_CHECKING, Optional, Union

from core.api.grpc.wrappers import Interface, Link
from core.gui import nodeutils, themes
from core.gui.dialogs.linkconfig import LinkConfigurationDialog
from core.gui.frames.link import EdgeInfoFrame, WirelessEdgeInfoFrame
from core.gui.graph import tags
from core.gui.utils import bandwidth_text, delay_jitter_text

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.graph import CanvasGraph
    from core.gui.graph.manager import CanvasManager
    from core.gui.graph.node import CanvasNode, ShadowNode

TEXT_DISTANCE: int = 60
EDGE_WIDTH: int = 3
EDGE_COLOR: str = "#ff0000"
EDGE_LOSS: float = 100.0
WIRELESS_WIDTH: float = 3
WIRELESS_COLOR: str = "#009933"
ARC_DISTANCE: int = 50


def create_wireless_token(src: int, dst: int, network: int) -> str:
    if src < dst:
        node1, node2 = src, dst
    else:
        node1, node2 = dst, src
    return f"{node1}-{node2}-{network}"


def create_edge_token(link: Link) -> str:
    iface1_id = link.iface1.id if link.iface1 else 0
    iface2_id = link.iface2.id if link.iface2 else 0
    if link.node1_id < link.node2_id:
        node1 = link.node1_id
        node1_iface = iface1_id
        node2 = link.node2_id
        node2_iface = iface2_id
    else:
        node1 = link.node2_id
        node1_iface = iface2_id
        node2 = link.node1_id
        node2_iface = iface1_id
    return f"{node1}-{node1_iface}-{node2}-{node2_iface}"


def node_label_positions(
    src_x: int, src_y: int, dst_x: int, dst_y: int
) -> tuple[tuple[float, float], tuple[float, float]]:
    v_x, v_y = dst_x - src_x, dst_y - src_y
    v_len = math.sqrt(v_x**2 + v_y**2)
    if v_len == 0:
        u_x, u_y = 0.0, 0.0
    else:
        u_x, u_y = v_x / v_len, v_y / v_len
    offset_x, offset_y = TEXT_DISTANCE * u_x, TEXT_DISTANCE * u_y
    return (src_x + offset_x, src_y + offset_y), (dst_x - offset_x, dst_y - offset_y)


def arc_edges(edges) -> None:
    if not edges:
        return
    mid_index = len(edges) // 2
    if mid_index == 0:
        arc_step = ARC_DISTANCE
    else:
        arc_step = ARC_DISTANCE / mid_index
    # below edges
    arc = 0
    for edge in edges[:mid_index]:
        arc -= arc_step
        edge.arc = arc
        edge.redraw()
    # mid edge
    if len(edges) % 2 != 0:
        arc = 0
        edge = edges[mid_index]
        edge.arc = arc
        edge.redraw()
        mid_index += 1
    # above edges
    arc = 0
    for edge in edges[mid_index:]:
        arc += arc_step
        edge.arc = arc
        edge.redraw()


class Edge:
    tag: str = tags.EDGE

    def __init__(
        self, app: "Application", src: "CanvasNode", dst: "CanvasNode" = None
    ) -> None:
        self.app: "Application" = app
        self.manager: CanvasManager = app.manager
        self.id: Optional[int] = None
        self.id2: Optional[int] = None
        self.src: "CanvasNode" = src
        self.src_shadow: Optional[ShadowNode] = None
        self.dst: Optional["CanvasNode"] = dst
        self.dst_shadow: Optional[ShadowNode] = None
        self.link: Optional[Link] = None
        self.arc: int = 0
        self.token: Optional[str] = None
        self.src_label: Optional[int] = None
        self.src_label2: Optional[int] = None
        self.middle_label: Optional[int] = None
        self.middle_label2: Optional[int] = None
        self.dst_label: Optional[int] = None
        self.dst_label2: Optional[int] = None
        self.color: str = EDGE_COLOR
        self.width: int = EDGE_WIDTH
        self.linked_wireless: bool = False
        self.hidden: bool = False
        if self.dst:
            self.linked_wireless = self.src.is_wireless() or self.dst.is_wireless()

    def scaled_width(self) -> float:
        return self.width * self.app.app_scale

    def _get_arcpoint(
        self, src_pos: tuple[float, float], dst_pos: tuple[float, float]
    ) -> tuple[float, float]:
        src_x, src_y = src_pos
        dst_x, dst_y = dst_pos
        mp_x = (src_x + dst_x) / 2
        mp_y = (src_y + dst_y) / 2
        slope_denominator = src_x - dst_x
        slope_numerator = src_y - dst_y
        # vertical line
        if slope_denominator == 0:
            return mp_x + self.arc, mp_y
        # horizontal line
        if slope_numerator == 0:
            return mp_x, mp_y + self.arc
        # everything else
        m = slope_numerator / slope_denominator
        perp_m = -1 / m
        b = mp_y - (perp_m * mp_x)
        # get arc x and y
        offset = math.sqrt(self.arc**2 / (1 + (1 / m**2)))
        arc_x = mp_x
        if self.arc >= 0:
            arc_x += offset
        else:
            arc_x -= offset
        arc_y = (perp_m * arc_x) + b
        return arc_x, arc_y

    def arc_common_edges(self) -> None:
        common_edges = list(self.src.edges & self.dst.edges)
        common_edges += list(self.src.wireless_edges & self.dst.wireless_edges)
        arc_edges(common_edges)

    def has_shadows(self) -> bool:
        # still drawing
        if not self.dst:
            return False
        return self.src.canvas != self.dst.canvas

    def draw(self, state: str) -> None:
        if not self.has_shadows():
            dst = self.dst if self.dst else self.src
            self.id = self.draw_edge(self.src.canvas, self.src, dst, state)
        elif self.linked_wireless:
            if self.src.is_wireless():
                self.src_shadow = self.dst.canvas.get_shadow(self.src)
                self.id2 = self.draw_edge(
                    self.dst.canvas, self.src_shadow, self.dst, state
                )
            if self.dst.is_wireless():
                self.dst_shadow = self.src.canvas.get_shadow(self.dst)
                self.id = self.draw_edge(
                    self.src.canvas, self.src, self.dst_shadow, state
                )
        else:
            # draw shadow nodes and 2 lines
            self.src_shadow = self.dst.canvas.get_shadow(self.src)
            self.dst_shadow = self.src.canvas.get_shadow(self.dst)
            self.id = self.draw_edge(self.src.canvas, self.src, self.dst_shadow, state)
            self.id2 = self.draw_edge(self.dst.canvas, self.src_shadow, self.dst, state)
        self.src.canvas.organize()
        if self.has_shadows():
            self.dst.canvas.organize()

    def draw_edge(
        self,
        canvas: "CanvasGraph",
        src: Union["CanvasNode", "ShadowNode"],
        dst: Union["CanvasNode", "ShadowNode"],
        state: str,
    ) -> int:
        src_pos = src.position()
        dst_pos = dst.position()
        arc_pos = self._get_arcpoint(src_pos, dst_pos)
        return canvas.create_line(
            *src_pos,
            *arc_pos,
            *dst_pos,
            smooth=True,
            tags=self.tag,
            width=self.scaled_width(),
            fill=self.color,
            state=state,
        )

    def redraw(self) -> None:
        self.src.canvas.itemconfig(self.id, width=self.scaled_width(), fill=self.color)
        self.move_src()
        if self.id2:
            self.dst.canvas.itemconfig(
                self.id2, width=self.scaled_width(), fill=self.color
            )
            self.move_dst()

    def middle_label_text(self, text: str) -> None:
        if self.middle_label is None:
            _, _, x, y, _, _ = self.src.canvas.coords(self.id)
            self.middle_label = self.src.canvas.create_text(
                x,
                y,
                font=self.app.edge_font,
                text=text,
                tags=tags.LINK_LABEL,
                justify=tk.CENTER,
                state=self.manager.show_link_labels.state(),
            )
            if self.id2:
                _, _, x, y, _, _ = self.dst.canvas.coords(self.id2)
                self.middle_label2 = self.dst.canvas.create_text(
                    x,
                    y,
                    font=self.app.edge_font,
                    text=text,
                    tags=tags.LINK_LABEL,
                    justify=tk.CENTER,
                    state=self.manager.show_link_labels.state(),
                )
        else:
            self.src.canvas.itemconfig(self.middle_label, text=text)
            if self.middle_label2:
                self.dst.canvas.itemconfig(self.middle_label2, text=text)

    def clear_middle_label(self) -> None:
        self.src.canvas.delete(self.middle_label)
        self.middle_label = None
        if self.middle_label2:
            self.dst.canvas.delete(self.middle_label2)
            self.middle_label2 = None

    def src_label_text(self, text: str) -> None:
        if self.src_label is None and self.src_label2 is None:
            if self.id:
                src_x, src_y, _, _, dst_x, dst_y = self.src.canvas.coords(self.id)
                src_pos, _ = node_label_positions(src_x, src_y, dst_x, dst_y)
                self.src_label = self.src.canvas.create_text(
                    *src_pos,
                    text=text,
                    justify=tk.CENTER,
                    font=self.app.edge_font,
                    tags=tags.LINK_LABEL,
                    state=self.manager.show_link_labels.state(),
                )
            if self.id2:
                src_x, src_y, _, _, dst_x, dst_y = self.dst.canvas.coords(self.id2)
                src_pos, _ = node_label_positions(src_x, src_y, dst_x, dst_y)
                self.src_label2 = self.dst.canvas.create_text(
                    *src_pos,
                    text=text,
                    justify=tk.CENTER,
                    font=self.app.edge_font,
                    tags=tags.LINK_LABEL,
                    state=self.manager.show_link_labels.state(),
                )
        else:
            if self.src_label:
                self.src.canvas.itemconfig(self.src_label, text=text)
            if self.src_label2:
                self.dst.canvas.itemconfig(self.src_label2, text=text)

    def dst_label_text(self, text: str) -> None:
        if self.dst_label is None and self.dst_label2 is None:
            if self.id:
                src_x, src_y, _, _, dst_x, dst_y = self.src.canvas.coords(self.id)
                _, dst_pos = node_label_positions(src_x, src_y, dst_x, dst_y)
                self.dst_label = self.src.canvas.create_text(
                    *dst_pos,
                    text=text,
                    justify=tk.CENTER,
                    font=self.app.edge_font,
                    tags=tags.LINK_LABEL,
                    state=self.manager.show_link_labels.state(),
                )
            if self.id2:
                src_x, src_y, _, _, dst_x, dst_y = self.dst.canvas.coords(self.id2)
                _, dst_pos = node_label_positions(src_x, src_y, dst_x, dst_y)
                self.dst_label2 = self.dst.canvas.create_text(
                    *dst_pos,
                    text=text,
                    justify=tk.CENTER,
                    font=self.app.edge_font,
                    tags=tags.LINK_LABEL,
                    state=self.manager.show_link_labels.state(),
                )
        else:
            if self.dst_label:
                self.src.canvas.itemconfig(self.dst_label, text=text)
            if self.dst_label2:
                self.dst.canvas.itemconfig(self.dst_label2, text=text)

    def drawing(self, pos: tuple[float, float]) -> None:
        src_x, src_y, _, _, _, _ = self.src.canvas.coords(self.id)
        src_pos = src_x, src_y
        self.moved(src_pos, pos)

    def move_node(self, node: "CanvasNode") -> None:
        if self.src == node:
            self.move_src()
        else:
            self.move_dst()

    def move_shadow(self, node: "ShadowNode") -> None:
        if self.src_shadow == node:
            self.move_src_shadow()
        elif self.dst_shadow == node:
            self.move_dst_shadow()

    def move_src_shadow(self) -> None:
        if not self.id2:
            return
        _, _, _, _, dst_x, dst_y = self.dst.canvas.coords(self.id2)
        dst_pos = dst_x, dst_y
        self.moved2(self.src_shadow.position(), dst_pos)

    def move_dst_shadow(self) -> None:
        if not self.id:
            return
        src_x, src_y, _, _, _, _ = self.src.canvas.coords(self.id)
        src_pos = src_x, src_y
        self.moved(src_pos, self.dst_shadow.position())

    def move_dst(self) -> None:
        if self.dst.is_wireless() and self.has_shadows():
            return
        dst_pos = self.dst.position()
        if self.id2:
            src_x, src_y, _, _, _, _ = self.dst.canvas.coords(self.id2)
            src_pos = src_x, src_y
            self.moved2(src_pos, dst_pos)
        elif self.id:
            src_x, src_y, _, _, _, _ = self.dst.canvas.coords(self.id)
            src_pos = src_x, src_y
            self.moved(src_pos, dst_pos)

    def move_src(self) -> None:
        if not self.id:
            return
        _, _, _, _, dst_x, dst_y = self.src.canvas.coords(self.id)
        dst_pos = dst_x, dst_y
        self.moved(self.src.position(), dst_pos)

    def moved(self, src_pos: tuple[float, float], dst_pos: tuple[float, float]) -> None:
        arc_pos = self._get_arcpoint(src_pos, dst_pos)
        self.src.canvas.coords(self.id, *src_pos, *arc_pos, *dst_pos)
        if self.middle_label:
            self.src.canvas.coords(self.middle_label, *arc_pos)
        src_x, src_y, _, _, dst_x, dst_y = self.src.canvas.coords(self.id)
        src_pos, dst_pos = node_label_positions(src_x, src_y, dst_x, dst_y)
        if self.src_label:
            self.src.canvas.coords(self.src_label, *src_pos)
        if self.dst_label:
            self.src.canvas.coords(self.dst_label, *dst_pos)

    def moved2(
        self, src_pos: tuple[float, float], dst_pos: tuple[float, float]
    ) -> None:
        arc_pos = self._get_arcpoint(src_pos, dst_pos)
        self.dst.canvas.coords(self.id2, *src_pos, *arc_pos, *dst_pos)
        if self.middle_label2:
            self.dst.canvas.coords(self.middle_label2, *arc_pos)
        src_x, src_y, _, _, dst_x, dst_y = self.dst.canvas.coords(self.id2)
        src_pos, dst_pos = node_label_positions(src_x, src_y, dst_x, dst_y)
        if self.src_label2:
            self.dst.canvas.coords(self.src_label2, *src_pos)
        if self.dst_label2:
            self.dst.canvas.coords(self.dst_label2, *dst_pos)

    def delete(self) -> None:
        logger.debug("deleting canvas edge, id: %s", self.id)
        self.src.canvas.delete(self.id)
        self.src.canvas.delete(self.src_label)
        self.src.canvas.delete(self.dst_label)
        if self.dst:
            self.dst.canvas.delete(self.id2)
            self.dst.canvas.delete(self.src_label2)
            self.dst.canvas.delete(self.dst_label2)
        if self.src_shadow and self.src_shadow.should_delete():
            self.src_shadow.delete()
            self.src_shadow = None
        if self.dst_shadow and self.dst_shadow.should_delete():
            self.dst_shadow.delete()
            self.dst_shadow = None
        self.clear_middle_label()
        self.id = None
        self.id2 = None
        self.src_label = None
        self.src_label2 = None
        self.dst_label = None
        self.dst_label2 = None
        if self.dst:
            self.arc_common_edges()

    def hide(self) -> None:
        self.hidden = True
        if self.src_shadow:
            self.src_shadow.hide()
        if self.dst_shadow:
            self.dst_shadow.hide()
        self.src.canvas.itemconfigure(self.id, state=tk.HIDDEN)
        self.src.canvas.itemconfigure(self.src_label, state=tk.HIDDEN)
        self.src.canvas.itemconfigure(self.dst_label, state=tk.HIDDEN)
        self.src.canvas.itemconfigure(self.middle_label, state=tk.HIDDEN)
        if self.id2:
            self.dst.canvas.itemconfigure(self.id2, state=tk.HIDDEN)
            self.dst.canvas.itemconfigure(self.src_label2, state=tk.HIDDEN)
            self.dst.canvas.itemconfigure(self.dst_label2, state=tk.HIDDEN)
            self.dst.canvas.itemconfigure(self.middle_label2, state=tk.HIDDEN)

    def show(self) -> None:
        self.hidden = False
        if self.src_shadow:
            self.src_shadow.show()
        if self.dst_shadow:
            self.dst_shadow.show()
        self.src.canvas.itemconfigure(self.id, state=tk.NORMAL)
        state = self.manager.show_link_labels.state()
        self.set_labels(state)

    def set_labels(self, state: str) -> None:
        self.src.canvas.itemconfigure(self.src_label, state=state)
        self.src.canvas.itemconfigure(self.dst_label, state=state)
        self.src.canvas.itemconfigure(self.middle_label, state=state)
        if self.id2:
            self.dst.canvas.itemconfigure(self.id2, state=state)
            self.dst.canvas.itemconfigure(self.src_label2, state=state)
            self.dst.canvas.itemconfigure(self.dst_label2, state=state)
            self.dst.canvas.itemconfigure(self.middle_label2, state=state)

    def other_node(self, node: "CanvasNode") -> "CanvasNode":
        if self.src == node:
            return self.dst
        elif self.dst == node:
            return self.src
        else:
            raise ValueError(f"node({node.core_node.name}) does not belong to edge")

    def other_iface(self, node: "CanvasNode") -> Optional[Interface]:
        if self.src == node:
            return self.link.iface2 if self.link else None
        elif self.dst == node:
            return self.link.iface1 if self.link else None
        else:
            raise ValueError(f"node({node.core_node.name}) does not belong to edge")

    def iface(self, node: "CanvasNode") -> Optional[Interface]:
        if self.src == node:
            return self.link.iface1 if self.link else None
        elif self.dst == node:
            return self.link.iface2 if self.link else None
        else:
            raise ValueError(f"node({node.core_node.name}) does not belong to edge")


class CanvasWirelessEdge(Edge):
    tag = tags.WIRELESS_EDGE

    def __init__(
        self,
        app: "Application",
        src: "CanvasNode",
        dst: "CanvasNode",
        network_id: int,
        token: str,
        link: Link,
    ) -> None:
        logger.debug("drawing wireless link from node %s to node %s", src, dst)
        super().__init__(app, src, dst)
        self.src.wireless_edges.add(self)
        self.dst.wireless_edges.add(self)
        self.network_id: int = network_id
        self.link: Link = link
        self.token: str = token
        self.width: float = WIRELESS_WIDTH
        color = link.color if link.color else WIRELESS_COLOR
        self.color: str = color
        state = self.manager.show_wireless.state()
        self.draw(state)
        if link.label:
            self.middle_label_text(link.label)
        if self.src.hidden or self.dst.hidden:
            self.hide()
        self.set_binding()
        self.arc_common_edges()

    def set_binding(self) -> None:
        self.src.canvas.tag_bind(self.id, "<Button-1>", self.show_info)
        if self.id2 is not None:
            self.dst.canvas.tag_bind(self.id2, "<Button-1>", self.show_info)

    def show_info(self, _event: tk.Event) -> None:
        self.app.display_info(WirelessEdgeInfoFrame, app=self.app, edge=self)

    def delete(self) -> None:
        self.src.wireless_edges.discard(self)
        self.dst.wireless_edges.remove(self)
        super().delete()


class CanvasEdge(Edge):
    """
    Canvas edge class
    """

    def __init__(
        self, app: "Application", src: "CanvasNode", dst: "CanvasNode" = None
    ) -> None:
        """
        Create an instance of canvas edge object
        """
        super().__init__(app, src, dst)
        self.text_src: Optional[int] = None
        self.text_dst: Optional[int] = None
        self.asymmetric_link: Optional[Link] = None
        self.throughput: Optional[float] = None
        self.draw(tk.NORMAL)

    def is_customized(self) -> bool:
        return self.width != EDGE_WIDTH or self.color != EDGE_COLOR

    def set_bindings(self) -> None:
        if self.id:
            show_context = functools.partial(self.show_context, self.src.canvas)
            self.src.canvas.tag_bind(self.id, "<ButtonRelease-3>", show_context)
            self.src.canvas.tag_bind(self.id, "<Button-1>", self.show_info)
        if self.id2:
            show_context = functools.partial(self.show_context, self.dst.canvas)
            self.dst.canvas.tag_bind(self.id2, "<ButtonRelease-3>", show_context)
            self.dst.canvas.tag_bind(self.id2, "<Button-1>", self.show_info)

    def iface_label(self, iface: Interface) -> str:
        label = ""
        if iface.name and self.manager.show_iface_names.get():
            label = f"{iface.name}"
        if iface.ip4 and self.manager.show_ip4s.get():
            label = f"{label}\n" if label else ""
            label += f"{iface.ip4}/{iface.ip4_mask}"
        if iface.ip6 and self.manager.show_ip6s.get():
            label = f"{label}\n" if label else ""
            label += f"{iface.ip6}/{iface.ip6_mask}"
        return label

    def create_node_labels(self) -> tuple[str, str]:
        label1 = None
        if self.link.iface1:
            label1 = self.iface_label(self.link.iface1)
        label2 = None
        if self.link.iface2:
            label2 = self.iface_label(self.link.iface2)
        return label1, label2

    def draw_labels(self) -> None:
        src_text, dst_text = self.create_node_labels()
        self.src_label_text(src_text)
        self.dst_label_text(dst_text)
        if not self.linked_wireless:
            self.draw_link_options()

    def redraw(self) -> None:
        super().redraw()
        self.draw_labels()

    def show(self) -> None:
        super().show()
        self.check_visibility()

    def check_visibility(self) -> None:
        state = tk.NORMAL
        hide_links = self.manager.show_links.state() == tk.HIDDEN
        if self.linked_wireless or hide_links:
            state = tk.HIDDEN
        elif self.link.options:
            hide_loss = self.manager.show_loss_links.state() == tk.HIDDEN
            should_hide = self.link.options.loss >= EDGE_LOSS
            if hide_loss and should_hide:
                state = tk.HIDDEN
        if self.id:
            self.src.canvas.itemconfigure(self.id, state=state)
        if self.id2:
            self.dst.canvas.itemconfigure(self.id2, state=state)

    def set_throughput(self, throughput: float) -> None:
        throughput = 0.001 * throughput
        text = f"{throughput:.3f} kbps"
        self.middle_label_text(text)
        if throughput > self.manager.throughput_threshold:
            color = self.manager.throughput_color
            width = self.manager.throughput_width
        else:
            color = self.color
            width = self.scaled_width()
        self.src.canvas.itemconfig(self.id, fill=color, width=width)
        if self.id2:
            self.dst.canvas.itemconfig(self.id2, fill=color, width=width)

    def clear_throughput(self) -> None:
        self.clear_middle_label()
        if not self.linked_wireless:
            self.draw_link_options()

    def complete(self, dst: "CanvasNode", link: Link = None) -> None:
        logger.debug(
            "completing wired link from node(%s) to node(%s)",
            self.src.core_node.name,
            dst.core_node.name,
        )
        self.dst = dst
        self.linked_wireless = self.src.is_wireless() or self.dst.is_wireless()
        self.set_bindings()
        self.check_wireless()
        if link is None:
            link = self.app.core.ifaces_manager.create_link(self)
        if link.iface1 and not nodeutils.is_rj45(self.src.core_node):
            iface1 = link.iface1
            self.src.ifaces[iface1.id] = iface1
        if link.iface2 and not nodeutils.is_rj45(self.dst.core_node):
            iface2 = link.iface2
            self.dst.ifaces[iface2.id] = iface2
        self.token = create_edge_token(link)
        self.link = link
        self.src.edges.add(self)
        self.dst.edges.add(self)
        if not self.linked_wireless:
            self.arc_common_edges()
        self.draw_labels()
        self.check_visibility()
        self.app.core.save_edge(self)
        self.src.canvas.organize()
        if self.has_shadows():
            self.dst.canvas.organize()
        self.manager.edges[self.token] = self

    def check_wireless(self) -> None:
        if not self.linked_wireless:
            return
        if self.id:
            self.src.canvas.itemconfig(self.id, state=tk.HIDDEN)
            self.src.canvas.dtag(self.id, tags.EDGE)
        if self.id2:
            self.dst.canvas.itemconfig(self.id2, state=tk.HIDDEN)
            self.dst.canvas.dtag(self.id2, tags.EDGE)
        # add antenna to node
        if self.src.is_wireless() and not self.dst.is_wireless():
            self.dst.add_antenna()
        elif not self.src.is_wireless() and self.dst.is_wireless():
            self.src.add_antenna()
        else:
            self.src.add_antenna()

    def reset(self) -> None:
        if self.middle_label:
            self.src.canvas.delete(self.middle_label)
            self.middle_label = None
        if self.middle_label2:
            self.dst.canvas.delete(self.middle_label2)
            self.middle_label2 = None
        if self.id:
            self.src.canvas.itemconfig(
                self.id, fill=self.color, width=self.scaled_width()
            )
        if self.id2:
            self.dst.canvas.itemconfig(
                self.id2, fill=self.color, width=self.scaled_width()
            )

    def show_info(self, _event: tk.Event) -> None:
        self.app.display_info(EdgeInfoFrame, app=self.app, edge=self)

    def show_context(self, canvas: "CanvasGraph", event: tk.Event) -> None:
        context: tk.Menu = tk.Menu(canvas)
        themes.style_menu(context)
        context.add_command(label="Configure", command=self.click_configure)
        context.add_command(label="Delete", command=self.click_delete)
        state = tk.DISABLED if self.app.core.is_runtime() else tk.NORMAL
        context.entryconfigure(1, state=state)
        context.tk_popup(event.x_root, event.y_root)

    def click_delete(self) -> None:
        self.delete()

    def click_configure(self) -> None:
        dialog = LinkConfigurationDialog(self.app, self)
        dialog.show()

    def draw_link_options(self):
        if not self.link.options:
            return
        options = self.link.options
        asym_options = None
        if self.asymmetric_link and self.asymmetric_link.options:
            asym_options = self.asymmetric_link.options
        lines = []
        # bandwidth
        if options.bandwidth > 0:
            bandwidth_line = bandwidth_text(options.bandwidth)
            if asym_options and asym_options.bandwidth > 0:
                bandwidth_line += f" / {bandwidth_text(asym_options.bandwidth)}"
            lines.append(bandwidth_line)
        # delay/jitter
        dj_line = delay_jitter_text(options.delay, options.jitter)
        if dj_line and asym_options:
            asym_dj_line = delay_jitter_text(asym_options.delay, asym_options.jitter)
            if asym_dj_line:
                dj_line += f" / {asym_dj_line}"
        if dj_line:
            lines.append(dj_line)
        # loss
        if options.loss > 0:
            loss_line = f"loss={options.loss}%"
            if asym_options and asym_options.loss > 0:
                loss_line += f" / loss={asym_options.loss}%"
            lines.append(loss_line)
        # duplicate
        if options.dup > 0:
            dup_line = f"dup={options.dup}%"
            if asym_options and asym_options.dup > 0:
                dup_line += f" / dup={asym_options.dup}%"
            lines.append(dup_line)
        label = "\n".join(lines)
        self.middle_label_text(label)

    def delete(self) -> None:
        self.src.edges.discard(self)
        if self.dst:
            self.dst.edges.discard(self)
            if self.link.iface1 and not nodeutils.is_rj45(self.src.core_node):
                del self.src.ifaces[self.link.iface1.id]
            if self.link.iface2 and not nodeutils.is_rj45(self.dst.core_node):
                del self.dst.ifaces[self.link.iface2.id]
            if self.src.is_wireless():
                self.dst.delete_antenna()
            if self.dst.is_wireless():
                self.src.delete_antenna()
            self.app.core.deleted_canvas_edges([self])
        super().delete()
        self.manager.edges.pop(self.token, None)
