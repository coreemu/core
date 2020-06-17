import logging
import math
import tkinter as tk
from typing import TYPE_CHECKING, Any, Tuple

from core.api.grpc import core_pb2
from core.gui import themes
from core.gui.dialogs.linkconfig import LinkConfigurationDialog
from core.gui.graph import tags
from core.gui.nodeutils import NodeUtils

if TYPE_CHECKING:
    from core.gui.graph.graph import CanvasGraph

TEXT_DISTANCE = 0.30
EDGE_WIDTH = 3
EDGE_COLOR = "#ff0000"
WIRELESS_WIDTH = 1.5
WIRELESS_COLOR = "#009933"
ARC_DISTANCE = 50


def create_edge_token(src: int, dst: int, network: int = None) -> Tuple[int, ...]:
    values = [src, dst]
    if network is not None:
        values.append(network)
    return tuple(sorted(values))


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
    tag = tags.EDGE

    def __init__(self, canvas: "CanvasGraph", src: int, dst: int = None) -> None:
        self.canvas = canvas
        self.id = None
        self.src = src
        self.dst = dst
        self.arc = 0
        self.token = None
        self.src_label = None
        self.middle_label = None
        self.dst_label = None
        self.color = EDGE_COLOR
        self.width = EDGE_WIDTH

    @classmethod
    def create_token(cls, src: int, dst: int) -> Tuple[int, ...]:
        return tuple(sorted([src, dst]))

    def scaled_width(self) -> float:
        return self.width * self.canvas.app.app_scale

    def _get_arcpoint(
        self, src_pos: Tuple[float, float], dst_pos: Tuple[float, float]
    ) -> Tuple[float, float]:
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
        offset = math.sqrt(self.arc ** 2 / (1 + (1 / m ** 2)))
        arc_x = mp_x
        if self.arc >= 0:
            arc_x += offset
        else:
            arc_x -= offset
        arc_y = (perp_m * arc_x) + b
        return arc_x, arc_y

    def draw(self, src_pos: Tuple[float, float], dst_pos: Tuple[float, float]) -> None:
        arc_pos = self._get_arcpoint(src_pos, dst_pos)
        self.id = self.canvas.create_line(
            *src_pos,
            *arc_pos,
            *dst_pos,
            smooth=True,
            tags=self.tag,
            width=self.scaled_width(),
            fill=self.color,
        )

    def redraw(self):
        self.canvas.itemconfig(self.id, width=self.scaled_width(), fill=self.color)
        src_x, src_y, _, _, _, _ = self.canvas.coords(self.id)
        src_pos = src_x, src_y
        self.move_src(src_pos)

    def middle_label_pos(self) -> Tuple[float, float]:
        _, _, x, y, _, _ = self.canvas.coords(self.id)
        return x, y

    def middle_label_text(self, text: str) -> None:
        if self.middle_label is None:
            x, y = self.middle_label_pos()
            self.middle_label = self.canvas.create_text(
                x,
                y,
                font=self.canvas.app.edge_font,
                text=text,
                tags=tags.LINK_LABEL,
                state=self.canvas.show_link_labels.state(),
            )
        else:
            self.canvas.itemconfig(self.middle_label, text=text)

    def node_label_positions(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        src_x, src_y, _, _, dst_x, dst_y = self.canvas.coords(self.id)
        v1 = dst_x - src_x
        v2 = dst_y - src_y
        ux = TEXT_DISTANCE * v1
        uy = TEXT_DISTANCE * v2
        src_x = src_x + ux
        src_y = src_y + uy
        dst_x = dst_x - ux
        dst_y = dst_y - uy
        return (src_x, src_y), (dst_x, dst_y)

    def src_label_text(self, text: str) -> None:
        if self.src_label is None:
            src_pos, _ = self.node_label_positions()
            self.src_label = self.canvas.create_text(
                *src_pos,
                text=text,
                justify=tk.CENTER,
                font=self.canvas.app.edge_font,
                tags=tags.LINK_LABEL,
                state=self.canvas.show_link_labels.state(),
            )
        else:
            self.canvas.itemconfig(self.src_label, text=text)

    def dst_label_text(self, text: str) -> None:
        if self.dst_label is None:
            _, dst_pos = self.node_label_positions()
            self.dst_label = self.canvas.create_text(
                *dst_pos,
                text=text,
                justify=tk.CENTER,
                font=self.canvas.app.edge_font,
                tags=tags.LINK_LABEL,
                state=self.canvas.show_link_labels.state(),
            )
        else:
            self.canvas.itemconfig(self.dst_label, text=text)

    def move_node(self, node_id: int, pos: Tuple[float, float]) -> None:
        if self.src == node_id:
            self.move_src(pos)
        else:
            self.move_dst(pos)

    def move_dst(self, dst_pos: Tuple[float, float]) -> None:
        src_x, src_y, _, _, _, _ = self.canvas.coords(self.id)
        src_pos = src_x, src_y
        self.moved(src_pos, dst_pos)

    def move_src(self, src_pos: Tuple[float, float]) -> None:
        _, _, _, _, dst_x, dst_y = self.canvas.coords(self.id)
        dst_pos = dst_x, dst_y
        self.moved(src_pos, dst_pos)

    def moved(self, src_pos: Tuple[float, float], dst_pos: Tuple[float, float]) -> None:
        arc_pos = self._get_arcpoint(src_pos, dst_pos)
        self.canvas.coords(self.id, *src_pos, *arc_pos, *dst_pos)
        if self.middle_label:
            self.canvas.coords(self.middle_label, *arc_pos)
        src_pos, dst_pos = self.node_label_positions()
        if self.src_label:
            self.canvas.coords(self.src_label, *src_pos)
        if self.dst_label:
            self.canvas.coords(self.dst_label, *dst_pos)

    def delete(self) -> None:
        logging.debug("deleting canvas edge, id: %s", self.id)
        self.canvas.delete(self.id)
        self.canvas.delete(self.src_label)
        self.canvas.delete(self.middle_label)
        self.canvas.delete(self.dst_label)
        self.id = None
        self.src_label = None
        self.middle_label = None
        self.dst_label = None


class CanvasWirelessEdge(Edge):
    tag = tags.WIRELESS_EDGE

    def __init__(
        self,
        canvas: "CanvasGraph",
        src: int,
        dst: int,
        src_pos: Tuple[float, float],
        dst_pos: Tuple[float, float],
        token: Tuple[Any, ...],
    ) -> None:
        logging.debug("drawing wireless link from node %s to node %s", src, dst)
        super().__init__(canvas, src, dst)
        self.token = token
        self.width = WIRELESS_WIDTH
        self.color = WIRELESS_COLOR
        self.draw(src_pos, dst_pos)


class CanvasEdge(Edge):
    """
    Canvas edge class
    """

    def __init__(
        self,
        canvas: "CanvasGraph",
        src: int,
        src_pos: Tuple[float, float],
        dst_pos: Tuple[float, float],
    ) -> None:
        """
        Create an instance of canvas edge object
        """
        super().__init__(canvas, src)
        self.src_iface = None
        self.dst_iface = None
        self.text_src = None
        self.text_dst = None
        self.link = None
        self.asymmetric_link = None
        self.throughput = None
        self.draw(src_pos, dst_pos)
        self.set_binding()
        self.context = tk.Menu(self.canvas)
        self.create_context()

    def create_context(self):
        themes.style_menu(self.context)
        self.context.add_command(label="Configure", command=self.click_configure)
        self.context.add_command(label="Delete", command=self.click_delete)

    def set_binding(self) -> None:
        self.canvas.tag_bind(self.id, "<ButtonRelease-3>", self.show_context)

    def set_link(self, link) -> None:
        self.link = link
        self.draw_labels()

    def iface_label(self, iface: core_pb2.Interface) -> str:
        label = ""
        if iface.name and self.canvas.show_iface_names.get():
            label = f"{iface.name}"
        if iface.ip4 and self.canvas.show_ip4s.get():
            label = f"{label}\n" if label else ""
            label += f"{iface.ip4}/{iface.ip4_mask}"
        if iface.ip6 and self.canvas.show_ip6s.get():
            label = f"{label}\n" if label else ""
            label += f"{iface.ip6}/{iface.ip6_mask}"
        return label

    def create_node_labels(self) -> Tuple[str, str]:
        label1 = None
        if self.link.HasField("iface1"):
            label1 = self.iface_label(self.link.iface1)
        label2 = None
        if self.link.HasField("iface2"):
            label2 = self.iface_label(self.link.iface2)
        return label1, label2

    def draw_labels(self) -> None:
        src_text, dst_text = self.create_node_labels()
        self.src_label_text(src_text)
        self.dst_label_text(dst_text)

    def redraw(self) -> None:
        super().redraw()
        self.draw_labels()

    def set_throughput(self, throughput: float) -> None:
        throughput = 0.001 * throughput
        text = f"{throughput:.3f} kbps"
        self.middle_label_text(text)
        if throughput > self.canvas.throughput_threshold:
            color = self.canvas.throughput_color
            width = self.canvas.throughput_width
        else:
            color = self.color
            width = self.scaled_width()
        self.canvas.itemconfig(self.id, fill=color, width=width)

    def complete(self, dst: int) -> None:
        self.dst = dst
        self.token = create_edge_token(self.src, self.dst)
        dst_pos = self.canvas.coords(self.dst)
        self.move_dst(dst_pos)
        self.check_wireless()
        logging.debug("Draw wired link from node %s to node %s", self.src, dst)

    def is_wireless(self) -> bool:
        src_node = self.canvas.nodes[self.src]
        dst_node = self.canvas.nodes[self.dst]
        src_node_type = src_node.core_node.type
        dst_node_type = dst_node.core_node.type
        is_src_wireless = NodeUtils.is_wireless_node(src_node_type)
        is_dst_wireless = NodeUtils.is_wireless_node(dst_node_type)

        # update the wlan/EMANE network
        wlan_network = self.canvas.wireless_network
        if is_src_wireless and not is_dst_wireless:
            if self.src not in wlan_network:
                wlan_network[self.src] = set()
            wlan_network[self.src].add(self.dst)
        elif not is_src_wireless and is_dst_wireless:
            if self.dst not in wlan_network:
                wlan_network[self.dst] = set()
            wlan_network[self.dst].add(self.src)
        return is_src_wireless or is_dst_wireless

    def check_wireless(self) -> None:
        if self.is_wireless():
            self.canvas.itemconfig(self.id, state=tk.HIDDEN)
            self._check_antenna()

    def _check_antenna(self) -> None:
        src_node = self.canvas.nodes[self.src]
        dst_node = self.canvas.nodes[self.dst]
        src_node_type = src_node.core_node.type
        dst_node_type = dst_node.core_node.type
        is_src_wireless = NodeUtils.is_wireless_node(src_node_type)
        is_dst_wireless = NodeUtils.is_wireless_node(dst_node_type)
        if is_src_wireless or is_dst_wireless:
            if is_src_wireless and not is_dst_wireless:
                dst_node.add_antenna()
            elif not is_src_wireless and is_dst_wireless:
                src_node.add_antenna()
            else:
                src_node.add_antenna()

    def reset(self) -> None:
        self.canvas.delete(self.middle_label)
        self.middle_label = None
        self.canvas.itemconfig(self.id, fill=self.color, width=self.scaled_width())

    def show_context(self, event: tk.Event) -> None:
        state = tk.DISABLED if self.canvas.core.is_runtime() else tk.NORMAL
        self.context.entryconfigure(1, state=state)
        self.context.tk_popup(event.x_root, event.y_root)

    def click_delete(self):
        self.canvas.delete_edge(self)

    def click_configure(self) -> None:
        dialog = LinkConfigurationDialog(self.canvas.app, self)
        dialog.show()
