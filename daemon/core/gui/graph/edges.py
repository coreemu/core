import logging
import tkinter as tk
from tkinter.font import Font
from typing import TYPE_CHECKING, Any, Tuple

from core.gui import themes
from core.gui.dialogs.linkconfig import LinkConfigurationDialog
from core.gui.graph import tags
from core.gui.nodeutils import EdgeUtils, NodeUtils

if TYPE_CHECKING:
    from core.gui.graph.graph import CanvasGraph

TEXT_DISTANCE = 0.30
EDGE_WIDTH = 3
EDGE_COLOR = "#ff0000"


class CanvasWirelessEdge:
    def __init__(
        self,
        token: Tuple[Any, ...],
        position: Tuple[float, float, float, float],
        src: int,
        dst: int,
        canvas: "CanvasGraph",
    ):
        logging.debug("Draw wireless link from node %s to node %s", src, dst)
        self.token = token
        self.src = src
        self.dst = dst
        self.canvas = canvas
        self.id = self.canvas.create_line(
            *position, tags=tags.WIRELESS_EDGE, width=1.5, fill="#009933"
        )

    def delete(self):
        self.canvas.delete(self.id)


class CanvasEdge:
    """
    Canvas edge class
    """

    def __init__(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        src: int,
        canvas: "CanvasGraph",
    ):
        """
        Create an instance of canvas edge object
        """
        self.src = src
        self.dst = None
        self.src_interface = None
        self.dst_interface = None
        self.canvas = canvas
        self.id = self.canvas.create_line(
            x1, y1, x2, y2, tags=tags.EDGE, width=EDGE_WIDTH, fill=EDGE_COLOR
        )
        self.text_src = None
        self.text_dst = None
        self.text_middle = None
        self.token = None
        self.font = Font(size=8)
        self.link = None
        self.asymmetric_link = None
        self.throughput = None
        self.set_binding()

    def set_binding(self):
        self.canvas.tag_bind(self.id, "<ButtonRelease-3>", self.create_context)

    def set_link(self, link):
        self.link = link
        self.draw_labels()

    def get_coordinates(self) -> [float, float, float, float]:
        x1, y1, x2, y2 = self.canvas.coords(self.id)
        v1 = x2 - x1
        v2 = y2 - y1
        ux = TEXT_DISTANCE * v1
        uy = TEXT_DISTANCE * v2
        x1 = x1 + ux
        y1 = y1 + uy
        x2 = x2 - ux
        y2 = y2 - uy
        return x1, y1, x2, y2

    def get_midpoint(self) -> [float, float]:
        x1, y1, x2, y2 = self.canvas.coords(self.id)
        x = (x1 + x2) / 2
        y = (y1 + y2) / 2
        return x, y

    def draw_labels(self):
        x1, y1, x2, y2 = self.get_coordinates()
        label_one = None
        if self.link.HasField("interface_one"):
            label_one = (
                f"{self.link.interface_one.ip4}/{self.link.interface_one.ip4mask}\n"
                f"{self.link.interface_one.ip6}/{self.link.interface_one.ip6mask}\n"
            )
        label_two = None
        if self.link.HasField("interface_two"):
            label_two = (
                f"{self.link.interface_two.ip4}/{self.link.interface_two.ip4mask}\n"
                f"{self.link.interface_two.ip6}/{self.link.interface_two.ip6mask}\n"
            )
        self.text_src = self.canvas.create_text(
            x1,
            y1,
            text=label_one,
            justify=tk.CENTER,
            font=self.font,
            tags=tags.LINK_INFO,
        )
        self.text_dst = self.canvas.create_text(
            x2,
            y2,
            text=label_two,
            justify=tk.CENTER,
            font=self.font,
            tags=tags.LINK_INFO,
        )

    def update_labels(self):
        """
        Move edge labels based on current position.
        """
        x1, y1, x2, y2 = self.get_coordinates()
        self.canvas.coords(self.text_src, x1, y1)
        self.canvas.coords(self.text_dst, x2, y2)
        if self.text_middle is not None:
            x, y = self.get_midpoint()
            self.canvas.coords(self.text_middle, x, y)

    def set_throughput(self, throughput: float):
        throughput = 0.001 * throughput
        value = f"{throughput:.3f} kbps"
        if self.text_middle is None:
            x, y = self.get_midpoint()
            self.text_middle = self.canvas.create_text(
                x, y, tags=tags.THROUGHPUT, font=self.font, text=value
            )
        else:
            self.canvas.itemconfig(self.text_middle, text=value)

        if throughput > self.canvas.throughput_threshold:
            color = self.canvas.throughput_color
            width = self.canvas.throughput_width
        else:
            color = EDGE_COLOR
            width = EDGE_WIDTH
        self.canvas.itemconfig(self.id, fill=color, width=width)

    def complete(self, dst: int):
        self.dst = dst
        self.token = EdgeUtils.get_token(self.src, self.dst)
        x, y = self.canvas.coords(self.dst)
        x1, y1, _, _ = self.canvas.coords(self.id)
        self.canvas.coords(self.id, x1, y1, x, y)
        self.check_wireless()
        self.canvas.tag_raise(self.src)
        self.canvas.tag_raise(self.dst)
        logging.debug("Draw wired link from node %s to node %s", self.src, dst)

    def is_wireless(self) -> [bool, bool]:
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

    def check_wireless(self):
        if self.is_wireless():
            self.canvas.itemconfig(self.id, state=tk.HIDDEN)
            self._check_antenna()

    def _check_antenna(self):
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

    def delete(self):
        logging.debug("Delete canvas edge, id: %s", self.id)
        self.canvas.delete(self.id)
        if self.link:
            self.canvas.delete(self.text_src)
            self.canvas.delete(self.text_dst)
        self.canvas.delete(self.text_middle)

    def reset(self):
        self.canvas.delete(self.text_middle)
        self.text_middle = None
        self.canvas.itemconfig(self.id, fill=EDGE_COLOR, width=EDGE_WIDTH)

    def create_context(self, event: tk.Event):
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

    def configure(self):
        dialog = LinkConfigurationDialog(self.canvas, self.canvas.app, self)
        dialog.show()
