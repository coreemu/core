import logging
import math
import tkinter as tk
from typing import TYPE_CHECKING, Optional, Tuple

from core.api.grpc.wrappers import Interface, Link
from core.gui import themes
from core.gui.dialogs.linkconfig import LinkConfigurationDialog
from core.gui.frames.link import EdgeInfoFrame, WirelessEdgeInfoFrame
from core.gui.graph import tags
from core.gui.nodeutils import NodeUtils
from core.gui.utils import bandwidth_text, delay_jitter_text

if TYPE_CHECKING:
    from core.gui.graph.graph import CanvasGraph

TEXT_DISTANCE: int = 60
EDGE_WIDTH: int = 3
EDGE_COLOR: str = "#ff0000"
EDGE_LOSS: float = 100.0
WIRELESS_WIDTH: float = 3
WIRELESS_COLOR: str = "#009933"
ARC_DISTANCE: int = 50


def create_wireless_token(src: int, dst: int, network: int) -> str:
    return f"{src}-{dst}-{network}"


def create_edge_token(src: int, dst: int, link: Link) -> str:
    iface1_id = link.iface1.id if link.iface1 else None
    iface2_id = link.iface2.id if link.iface2 else None
    return f"{src}-{iface1_id}-{dst}-{iface2_id}"


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

    def __init__(self, canvas: "CanvasGraph", src: int, dst: int = None) -> None:
        self.canvas = canvas
        self.id: Optional[int] = None
        self.src: int = src
        self.dst: int = dst
        self.arc: int = 0
        self.token: Optional[str] = None
        self.src_label: Optional[int] = None
        self.middle_label: Optional[int] = None
        self.dst_label: Optional[int] = None
        self.color: str = EDGE_COLOR
        self.width: int = EDGE_WIDTH

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

    def draw(
        self, src_pos: Tuple[float, float], dst_pos: Tuple[float, float], state: str
    ) -> None:
        arc_pos = self._get_arcpoint(src_pos, dst_pos)
        self.id = self.canvas.create_line(
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
                justify=tk.CENTER,
                state=self.canvas.show_link_labels.state(),
            )
        else:
            self.canvas.itemconfig(self.middle_label, text=text)

    def clear_middle_label(self) -> None:
        self.canvas.delete(self.middle_label)
        self.middle_label = None

    def node_label_positions(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        src_x, src_y, _, _, dst_x, dst_y = self.canvas.coords(self.id)
        v_x, v_y = dst_x - src_x, dst_y - src_y
        v_len = math.sqrt(v_x ** 2 + v_y ** 2)
        if v_len == 0:
            u_x, u_y = 0.0, 0.0
        else:
            u_x, u_y = v_x / v_len, v_y / v_len
        offset_x, offset_y = TEXT_DISTANCE * u_x, TEXT_DISTANCE * u_y
        return (
            (src_x + offset_x, src_y + offset_y),
            (dst_x - offset_x, dst_y - offset_y),
        )

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
        self.canvas.delete(self.dst_label)
        self.clear_middle_label()
        self.id = None
        self.src_label = None
        self.dst_label = None


class CanvasWirelessEdge(Edge):
    tag = tags.WIRELESS_EDGE

    def __init__(
        self,
        canvas: "CanvasGraph",
        src: int,
        dst: int,
        network_id: int,
        token: str,
        src_pos: Tuple[float, float],
        dst_pos: Tuple[float, float],
        link: Link,
    ) -> None:
        logging.debug("drawing wireless link from node %s to node %s", src, dst)
        super().__init__(canvas, src, dst)
        self.network_id: int = network_id
        self.link: Link = link
        self.token: str = token
        self.width: float = WIRELESS_WIDTH
        color = link.color if link.color else WIRELESS_COLOR
        self.color: str = color
        self.draw(src_pos, dst_pos, self.canvas.show_wireless.state())
        if link.label:
            self.middle_label_text(link.label)
        self.set_binding()

    def set_binding(self) -> None:
        self.canvas.tag_bind(self.id, "<Button-1>", self.show_info)

    def show_info(self, _event: tk.Event) -> None:
        self.canvas.app.display_info(
            WirelessEdgeInfoFrame, app=self.canvas.app, edge=self
        )


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
        self.text_src: Optional[int] = None
        self.text_dst: Optional[int] = None
        self.link: Optional[Link] = None
        self.linked_wireless: bool = False
        self.asymmetric_link: Optional[Link] = None
        self.throughput: Optional[float] = None
        self.draw(src_pos, dst_pos, tk.NORMAL)
        self.set_binding()
        self.context: tk.Menu = tk.Menu(self.canvas)
        self.create_context()

    def create_context(self) -> None:
        themes.style_menu(self.context)
        self.context.add_command(label="Configure", command=self.click_configure)
        self.context.add_command(label="Delete", command=self.click_delete)

    def set_binding(self) -> None:
        self.canvas.tag_bind(self.id, "<ButtonRelease-3>", self.show_context)
        self.canvas.tag_bind(self.id, "<Button-1>", self.show_info)

    def iface_label(self, iface: Interface) -> str:
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

    def check_options(self) -> None:
        if self.link.options.loss == EDGE_LOSS:
            state = tk.HIDDEN
            self.canvas.addtag_withtag(tags.LOSS_EDGES, self.id)
        else:
            state = tk.NORMAL
            self.canvas.dtag(self.id, tags.LOSS_EDGES)
        if self.canvas.show_loss_links.state() == tk.HIDDEN:
            self.canvas.itemconfigure(self.id, state=state)

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

    def clear_throughput(self) -> None:
        self.clear_middle_label()
        if not self.linked_wireless:
            self.draw_link_options()

    def complete(self, dst: int, linked_wireless: bool) -> None:
        self.dst = dst
        self.linked_wireless = linked_wireless
        dst_pos = self.canvas.coords(self.dst)
        self.move_dst(dst_pos)
        self.check_wireless()
        logging.debug("draw wired link from node %s to node %s", self.src, dst)

    def check_wireless(self) -> None:
        if self.linked_wireless:
            self.canvas.itemconfig(self.id, state=tk.HIDDEN)
            self.canvas.dtag(self.id, tags.EDGE)
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

    def show_info(self, _event: tk.Event) -> None:
        self.canvas.app.display_info(EdgeInfoFrame, app=self.canvas.app, edge=self)

    def show_context(self, event: tk.Event) -> None:
        state = tk.DISABLED if self.canvas.core.is_runtime() else tk.NORMAL
        self.context.entryconfigure(1, state=state)
        self.context.tk_popup(event.x_root, event.y_root)

    def click_delete(self) -> None:
        self.canvas.delete_edge(self)

    def click_configure(self) -> None:
        dialog = LinkConfigurationDialog(self.canvas.app, self)
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
