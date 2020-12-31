import functools
import logging
import math
import tkinter as tk
from typing import TYPE_CHECKING, Optional, Tuple

from PIL.ImageTk import PhotoImage

from core.api.grpc.wrappers import Interface, Link
from core.gui import themes
from core.gui.dialogs.linkconfig import LinkConfigurationDialog
from core.gui.frames.link import EdgeInfoFrame, WirelessEdgeInfoFrame
from core.gui.graph import tags
from core.gui.images import ImageEnum
from core.gui.nodeutils import ICON_SIZE, NodeUtils
from core.gui.utils import bandwidth_text, delay_jitter_text

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.graph import CanvasGraph
    from core.gui.graph.manager import CanvasManager
    from core.gui.graph.node import CanvasNode

TEXT_DISTANCE: int = 60
EDGE_WIDTH: int = 3
EDGE_COLOR: str = "#ff0000"
EDGE_LOSS: float = 100.0
WIRELESS_WIDTH: float = 3
WIRELESS_COLOR: str = "#009933"
ARC_DISTANCE: int = 50


def create_wireless_token(src: int, dst: int, network: int) -> str:
    return f"{src}-{dst}-{network}"


def create_edge_token(link: Link) -> str:
    iface1_id = link.iface1.id if link.iface1 else 0
    iface2_id = link.iface2.id if link.iface2 else 0
    return f"{link.node1_id}-{iface1_id}-{link.node2_id}-{iface2_id}"


def node_label_positions(
    src_x: int, src_y: int, dst_x: int, dst_y: int
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    v_x, v_y = dst_x - src_x, dst_y - src_y
    v_len = math.sqrt(v_x ** 2 + v_y ** 2)
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


class ShadowNode:
    def __init__(
        self, app: "Application", canvas: "CanvasGraph", node: "CanvasNode"
    ) -> None:
        self.app: "Application" = app
        self.canvas: "CanvasGraph" = canvas
        self.node: "CanvasNode" = node
        self.id: Optional[int] = None
        self.text_id: Optional[int] = None
        self.image: PhotoImage = self.app.get_icon(ImageEnum.ROUTER, ICON_SIZE)
        self.draw()

    def draw(self) -> None:
        x, y = self.node.position()
        self.id: int = self.canvas.create_image(
            x, y, anchor=tk.CENTER, image=self.image, tags=tags.NODE
        )
        self.text_id = self.canvas.create_text(
            x,
            y + 20,
            text=f"{self.node.get_label()} [{self.node.canvas.id}]",
            tags=tags.NODE_LABEL,
            font=self.app.icon_text_font,
            fill="#0000CD",
            state=self.app.manager.show_node_labels.state(),
            justify=tk.CENTER,
        )
        self.canvas.shadow_nodes[self.id] = self

    def position(self) -> Tuple[int, int]:
        return self.canvas.coords(self.id)

    def motion(self, x_offset, y_offset) -> None:
        original_position = self.position()
        self.canvas.move(self.id, x_offset, y_offset)

        # check new position
        bbox = self.canvas.bbox(self.id)
        if not self.canvas.valid_position(*bbox):
            self.canvas.coords(self.id, original_position)
            return

        # move text and selection box
        self.canvas.move(self.text_id, x_offset, y_offset)
        self.canvas.move_selection(self.id, x_offset, y_offset)

        # move edges
        for edge in self.node.edges:
            edge.move_shadow(self)
        for edge in self.node.wireless_edges:
            edge.move_shadow(self)

    def delete(self):
        self.canvas.shadow_nodes.pop(self.id, None)
        self.canvas.delete(self.id)
        self.canvas.delete(self.text_id)


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

    def scaled_width(self) -> float:
        return self.width * self.app.app_scale

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

    def arc_common_edges(self) -> None:
        common_edges = list(self.src.edges & self.dst.edges)
        common_edges += list(self.src.wireless_edges & self.dst.wireless_edges)
        arc_edges(common_edges)

    def is_same_canvas(self) -> bool:
        # actively drawing same canvas link
        if not self.dst:
            return True
        return self.src.canvas == self.dst.canvas

    def draw(self, state: str) -> None:
        src_pos = self.src.position()
        if self.is_same_canvas():
            dst_pos = src_pos
            if self.dst:
                dst_pos = self.dst.position()
            arc_pos = self._get_arcpoint(src_pos, dst_pos)
            self.id = self.src.canvas.create_line(
                *src_pos,
                *arc_pos,
                *dst_pos,
                smooth=True,
                tags=self.tag,
                width=self.scaled_width(),
                fill=self.color,
                state=state,
            )
        else:
            # draw shadow nodes and 2 lines
            dst_pos = self.dst.position()
            arc_pos = self._get_arcpoint(src_pos, dst_pos)
            self.src_shadow = ShadowNode(self.app, self.dst.canvas, self.src)
            self.dst_shadow = ShadowNode(self.app, self.src.canvas, self.dst)
            self.id = self.src.canvas.create_line(
                *src_pos,
                *arc_pos,
                *dst_pos,
                smooth=True,
                tags=self.tag,
                width=self.scaled_width(),
                fill=self.color,
                state=state,
            )
            self.id2 = self.dst.canvas.create_line(
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
        # src_x, src_y, _, _, _, _ = self.src.canvas.coords(self.id)
        # src_pos = src_x, src_y
        self.move_src()
        if not self.is_same_canvas():
            self.dst.canvas.itemconfig(
                self.id2, width=self.scaled_width(), fill=self.color
            )
            # src_x, src_y, _, _, _, _ = self.dst.canvas.coords(self.id2)
            # src_pos = src_x, src_y
            # self.move_src(src_pos)
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
            if not self.is_same_canvas():
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
            if not self.is_same_canvas():
                self.dst.canvas.itemconfig(self.middle_label2, text=text)

    def clear_middle_label(self) -> None:
        self.src.canvas.delete(self.middle_label)
        self.middle_label = None
        if not self.is_same_canvas():
            self.dst.canvas.delete(self.middle_label2)
            self.middle_label2 = None

    def src_label_text(self, text: str) -> None:
        if self.src_label is None:
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
            if not self.is_same_canvas():
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
            self.src.canvas.itemconfig(self.src_label, text=text)
            if not self.is_same_canvas():
                self.dst.canvas.itemconfig(self.src_label2, text=text)

    def dst_label_text(self, text: str) -> None:
        if self.dst_label is None:
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
            if not self.is_same_canvas():
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
            self.src.canvas.itemconfig(self.dst_label, text=text)
            if not self.is_same_canvas():
                self.dst.canvas.itemconfig(self.dst_label2, text=text)

    def drawing(self, pos: Tuple[float, float]) -> None:
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
        else:
            self.move_dst_shadow()

    def move_src_shadow(self) -> None:
        _, _, _, _, dst_x, dst_y = self.dst.canvas.coords(self.id2)
        dst_pos = dst_x, dst_y
        self.moved2(self.src_shadow.position(), dst_pos)

    def move_dst_shadow(self) -> None:
        src_x, src_y, _, _, _, _ = self.src.canvas.coords(self.id)
        src_pos = src_x, src_y
        self.moved(src_pos, self.dst_shadow.position())

    def move_dst(self) -> None:
        src_x, src_y, _, _, _, _ = self.dst.canvas.coords(self.id)
        src_pos = src_x, src_y
        dst_pos = self.dst.position()
        if self.is_same_canvas():
            self.moved(src_pos, dst_pos)
        else:
            self.moved2(src_pos, dst_pos)

    def move_src(self) -> None:
        _, _, _, _, dst_x, dst_y = self.src.canvas.coords(self.id)
        dst_pos = dst_x, dst_y
        self.moved(self.src.position(), dst_pos)

    def moved(self, src_pos: Tuple[float, float], dst_pos: Tuple[float, float]) -> None:
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
        self, src_pos: Tuple[float, float], dst_pos: Tuple[float, float]
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
        logging.debug("deleting canvas edge, id: %s", self.id)
        self.src.canvas.delete(self.id)
        self.src.canvas.delete(self.src_label)
        self.src.canvas.delete(self.dst_label)
        if self.dst:
            self.dst.canvas.delete(self.id2)
            self.dst.canvas.delete(self.src_label2)
            self.dst.canvas.delete(self.dst_label2)
        if self.src_shadow:
            self.src_shadow.delete()
            self.src_shadow = None
        if self.dst_shadow:
            self.dst_shadow.delete()
            self.dst_shadow = None
        self.clear_middle_label()
        self.id = None
        self.id2 = None
        self.src_label = None
        self.src_label2 = None
        self.dst_label = None
        self.dst_label2 = None
        self.manager.edges.pop(self.token, None)


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
        logging.debug("drawing wireless link from node %s to node %s", src, dst)
        super().__init__(app, src, dst)
        self.network_id: int = network_id
        self.link: Link = link
        self.token: str = token
        self.width: float = WIRELESS_WIDTH
        color = link.color if link.color else WIRELESS_COLOR
        self.color: str = color
        self.draw(self.manager.show_wireless.state())
        if link.label:
            self.middle_label_text(link.label)
        self.set_binding()

    def set_binding(self) -> None:
        self.src.canvas.tag_bind(self.id, "<Button-1>", self.show_info)
        if self.id2 is not None:
            self.dst.canvas.tag_bind(self.id2, "<Button-1>", self.show_info)

    def show_info(self, _event: tk.Event) -> None:
        self.app.display_info(WirelessEdgeInfoFrame, app=self.app, edge=self)


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
        self.link: Optional[Link] = None
        self.linked_wireless: bool = False
        self.asymmetric_link: Optional[Link] = None
        self.throughput: Optional[float] = None
        self.draw(tk.NORMAL)
        self.set_binding()

    def is_customized(self) -> bool:
        return self.width != EDGE_WIDTH or self.color != EDGE_COLOR

    def set_binding(self) -> None:
        show_context = functools.partial(self.show_info, self.src.canvas)
        self.src.canvas.tag_bind(self.id, "<ButtonRelease-3>", show_context)
        self.src.canvas.tag_bind(self.id, "<Button-1>", self.show_info)
        if self.dst and not self.is_same_canvas():
            show_context = functools.partial(self.show_info, self.dst.canvas)
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
        if not self.link.options:
            return
        if self.link.options.loss == EDGE_LOSS:
            state = tk.HIDDEN
            self.src.canvas.addtag_withtag(tags.LOSS_EDGES, self.id)
            if not self.is_same_canvas():
                self.dst.canvas.addtag_withtag(tags.LOSS_EDGES, self.id2)
        else:
            state = tk.NORMAL
            self.src.canvas.dtag(self.id, tags.LOSS_EDGES)
            if not self.is_same_canvas():
                self.dst.canvas.dtag(self.id2, tags.LOSS_EDGES)
        if self.manager.show_loss_links.state() == tk.HIDDEN:
            self.src.canvas.itemconfigure(self.id, state=state)
            if not self.is_same_canvas():
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
        if not self.is_same_canvas():
            self.dst.canvas.itemconfig(self.id2, fill=color, width=width)

    def clear_throughput(self) -> None:
        self.clear_middle_label()
        if not self.linked_wireless:
            self.draw_link_options()

    def complete(self, dst: "CanvasNode", linked_wireless: bool) -> None:
        self.dst = dst
        self.linked_wireless = linked_wireless
        self.move_dst()
        self.check_wireless()
        logging.debug("draw wired link from node %s to node %s", self.src, dst)

    def check_wireless(self) -> None:
        if not self.linked_wireless:
            return
        self.src.canvas.itemconfig(self.id, state=tk.HIDDEN)
        self.src.canvas.dtag(self.id, tags.EDGE)
        self._check_antenna()
        if not self.is_same_canvas():
            self.dst.canvas.itemconfig(self.id2, state=tk.HIDDEN)
            self.dst.canvas.dtag(self.id2, tags.EDGE)
            self._check_antenna()

    def _check_antenna(self) -> None:
        src_node_type = self.src.core_node.type
        dst_node_type = self.dst.core_node.type
        is_src_wireless = NodeUtils.is_wireless_node(src_node_type)
        is_dst_wireless = NodeUtils.is_wireless_node(dst_node_type)
        if is_src_wireless or is_dst_wireless:
            if is_src_wireless and not is_dst_wireless:
                self.dst.add_antenna()
            elif not is_src_wireless and is_dst_wireless:
                self.src.add_antenna()
            else:
                self.src.add_antenna()

    def reset(self) -> None:
        self.src.canvas.delete(self.middle_label)
        self.middle_label = None
        self.src.canvas.itemconfig(self.id, fill=self.color, width=self.scaled_width())
        if not self.is_same_canvas():
            self.dst.canvas.delete(self.middle_label2)
            self.middle_label2 = None
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
        super().delete()
        self.src.edges.discard(self)
        if self.link.iface1:
            del self.src.ifaces[self.link.iface1.id]
        if self.dst:
            self.dst.edges.discard(self)
            if self.link.iface2:
                del self.dst.ifaces[self.link.iface2.id]
            src_wireless = NodeUtils.is_wireless_node(self.src.core_node.type)
            if src_wireless:
                self.dst.delete_antenna()
            dst_wireless = NodeUtils.is_wireless_node(self.dst.core_node.type)
            if dst_wireless:
                self.src.delete_antenna()
            self.app.core.deleted_canvas_edges([self])
        self.arc_common_edges()
