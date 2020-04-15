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


def interface_label(interface: core_pb2.Interface) -> str:
    label = ""
    if interface.ip4:
        label = f"{interface.ip4}/{interface.ip4mask}"
    if interface.ip6:
        label = f"{label}\n{interface.ip6}/{interface.ip6mask}"
    return label


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
        self.middle_label = None
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
        self.move_src(src_x, src_y)

    def middle_label_pos(self) -> Tuple[float, float]:
        _, _, x, y, _, _ = self.canvas.coords(self.id)
        return x, y

    def middle_label_text(self, text: str) -> None:
        if self.middle_label is None:
            x, y = self.middle_label_pos()
            self.middle_label = self.canvas.create_text(
                x, y, font=self.canvas.app.edge_font, text=text
            )
        else:
            self.canvas.itemconfig(self.middle_label, text=text)

    def move_node(self, node_id: int, x: float, y: float) -> None:
        if self.src == node_id:
            self.move_src(x, y)
        else:
            self.move_dst(x, y)

    def move_dst(self, x: float, y: float) -> None:
        dst_pos = (x, y)
        src_x, src_y, _, _, _, _ = self.canvas.coords(self.id)
        src_pos = (src_x, src_y)
        self.moved(src_pos, dst_pos)

    def move_src(self, x: float, y: float) -> None:
        src_pos = (x, y)
        _, _, _, _, dst_x, dst_y = self.canvas.coords(self.id)
        dst_pos = (dst_x, dst_y)
        self.moved(src_pos, dst_pos)

    def moved(self, src_pos: Tuple[float, float], dst_pos: Tuple[float, float]) -> None:
        arc_pos = self._get_arcpoint(src_pos, dst_pos)
        self.canvas.coords(self.id, *src_pos, *arc_pos, *dst_pos)
        if self.middle_label:
            self.canvas.coords(self.middle_label, *arc_pos)

    def delete(self) -> None:
        self.canvas.delete(self.id)
        self.canvas.delete(self.middle_label)


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
        self.src_interface = None
        self.dst_interface = None
        self.text_src = None
        self.text_dst = None
        self.link = None
        self.asymmetric_link = None
        self.throughput = None
        self.draw(src_pos, dst_pos)
        self.set_binding()

    def move_node(self, node_id: int, x: float, y: float) -> None:
        super().move_node(node_id, x, y)
        self.update_labels()

    def set_binding(self) -> None:
        self.canvas.tag_bind(self.id, "<ButtonRelease-3>", self.create_context)

    def set_link(self, link) -> None:
        self.link = link
        self.draw_labels()

    def get_coordinates(self) -> [float, float, float, float]:
        x1, y1, _, _, x2, y2 = self.canvas.coords(self.id)
        v1 = x2 - x1
        v2 = y2 - y1
        ux = TEXT_DISTANCE * v1
        uy = TEXT_DISTANCE * v2
        x1 = x1 + ux
        y1 = y1 + uy
        x2 = x2 - ux
        y2 = y2 - uy
        return x1, y1, x2, y2

    def create_labels(self) -> Tuple[str, str]:
        label_one = None
        if self.link.HasField("interface_one"):
            label_one = interface_label(self.link.interface_one)
        label_two = None
        if self.link.HasField("interface_two"):
            label_two = interface_label(self.link.interface_two)
        return label_one, label_two

    def draw_labels(self) -> None:
        x1, y1, x2, y2 = self.get_coordinates()
        label_one, label_two = self.create_labels()
        self.text_src = self.canvas.create_text(
            x1,
            y1,
            text=label_one,
            justify=tk.CENTER,
            font=self.canvas.app.edge_font,
            tags=tags.LINK_INFO,
        )
        self.text_dst = self.canvas.create_text(
            x2,
            y2,
            text=label_two,
            justify=tk.CENTER,
            font=self.canvas.app.edge_font,
            tags=tags.LINK_INFO,
        )

    def redraw(self) -> None:
        super().redraw()
        label_one, label_two = self.create_labels()
        self.canvas.itemconfig(self.text_src, text=label_one)
        self.canvas.itemconfig(self.text_dst, text=label_two)

    def update_labels(self) -> None:
        """
        Move edge labels based on current position.
        """
        x1, y1, x2, y2 = self.get_coordinates()
        self.canvas.coords(self.text_src, x1, y1)
        self.canvas.coords(self.text_dst, x2, y2)

    def set_throughput(self, throughput: float) -> None:
        throughput = 0.001 * throughput
        text = f"{throughput:.3f} kbps"
        self.middle_label_text(text)
        self.canvas.addtag(self.middle_label, tags.THROUGHPUT)
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
        x, y = self.canvas.coords(self.dst)
        self.move_dst(x, y)
        self.check_wireless()
        self.canvas.tag_raise(self.src)
        self.canvas.tag_raise(self.dst)
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

    def delete(self) -> None:
        logging.debug("Delete canvas edge, id: %s", self.id)
        super().delete()
        self.canvas.delete(self.text_src)
        self.canvas.delete(self.text_dst)

    def reset(self) -> None:
        self.canvas.delete(self.middle_label)
        self.middle_label = None
        self.canvas.itemconfig(self.id, fill=self.color, width=self.scaled_width())

    def create_context(self, event: tk.Event) -> None:
        context = tk.Menu(self.canvas)
        themes.style_menu(context)
        context.add_command(label="Configure", command=self.configure)
        context.add_command(label="Delete")
        context.add_command(label="Split")
        context.add_command(label="Merge")
        if self.canvas.app.core.is_runtime():
            context.entryconfigure(1, state="disabled")
            context.entryconfigure(2, state="disabled")
            context.entryconfigure(3, state="disabled")
        context.post(event.x_root, event.y_root)

    def configure(self) -> None:
        dialog = LinkConfigurationDialog(self.canvas, self.canvas.app, self)
        dialog.show()
