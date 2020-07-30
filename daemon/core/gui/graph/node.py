import functools
import logging
import tkinter as tk
from typing import TYPE_CHECKING, Dict, List, Set

import grpc
from PIL.ImageTk import PhotoImage

from core.gui import themes
from core.gui.dialogs.emaneconfig import EmaneConfigDialog
from core.gui.dialogs.mobilityconfig import MobilityConfigDialog
from core.gui.dialogs.nodeconfig import NodeConfigDialog
from core.gui.dialogs.nodeconfigservice import NodeConfigServiceDialog
from core.gui.dialogs.nodeservice import NodeServiceDialog
from core.gui.dialogs.wlanconfig import WlanConfigDialog
from core.gui.frames.node import NodeInfoFrame
from core.gui.graph import tags
from core.gui.graph.edges import CanvasEdge, CanvasWirelessEdge
from core.gui.graph.tooltip import CanvasTooltip
from core.gui.images import ImageEnum
from core.gui.nodeutils import ANTENNA_SIZE, NodeUtils
from core.gui.wrappers import Interface, Node, NodeType

if TYPE_CHECKING:
    from core.gui.app import Application
    from core.gui.graph.graph import CanvasGraph

NODE_TEXT_OFFSET: int = 5


class CanvasNode:
    def __init__(
        self, app: "Application", x: float, y: float, core_node: Node, image: PhotoImage
    ):
        self.app: "Application" = app
        self.canvas: "CanvasGraph" = app.canvas
        self.image: PhotoImage = image
        self.core_node: Node = core_node
        self.id: int = self.canvas.create_image(
            x, y, anchor=tk.CENTER, image=self.image, tags=tags.NODE
        )
        label_y = self._get_label_y()
        label = self.get_label()
        self.text_id: int = self.canvas.create_text(
            x,
            label_y,
            text=label,
            tags=tags.NODE_LABEL,
            font=self.app.icon_text_font,
            fill="#0000CD",
            state=self.canvas.show_node_labels.state(),
        )
        self.tooltip: CanvasTooltip = CanvasTooltip(self.canvas)
        self.edges: Set[CanvasEdge] = set()
        self.ifaces: Dict[int, Interface] = {}
        self.wireless_edges: Set[CanvasWirelessEdge] = set()
        self.antennas: List[int] = []
        self.antenna_images: Dict[int, PhotoImage] = {}
        self.setup_bindings()
        self.context: tk.Menu = tk.Menu(self.canvas)
        themes.style_menu(self.context)

    def next_iface_id(self) -> int:
        i = 0
        while i in self.ifaces:
            i += 1
        return i

    def setup_bindings(self) -> None:
        self.canvas.tag_bind(self.id, "<Double-Button-1>", self.double_click)
        self.canvas.tag_bind(self.id, "<Enter>", self.on_enter)
        self.canvas.tag_bind(self.id, "<Leave>", self.on_leave)
        self.canvas.tag_bind(self.id, "<ButtonRelease-3>", self.show_context)
        self.canvas.tag_bind(self.id, "<Button-1>", self.show_info)

    def delete(self) -> None:
        logging.debug("Delete canvas node for %s", self.core_node)
        self.canvas.delete(self.id)
        self.canvas.delete(self.text_id)
        self.delete_antennas()

    def add_antenna(self) -> None:
        x, y = self.canvas.coords(self.id)
        offset = len(self.antennas) * 8 * self.app.app_scale
        img = self.app.get_icon(ImageEnum.ANTENNA, ANTENNA_SIZE)
        antenna_id = self.canvas.create_image(
            x - 16 + offset,
            y - int(23 * self.app.app_scale),
            anchor=tk.CENTER,
            image=img,
            tags=tags.ANTENNA,
        )
        self.antennas.append(antenna_id)
        self.antenna_images[antenna_id] = img

    def delete_antenna(self) -> None:
        """
        delete one antenna
        """
        logging.debug("Delete an antenna on %s", self.core_node.name)
        if self.antennas:
            antenna_id = self.antennas.pop()
            self.canvas.delete(antenna_id)
            self.antenna_images.pop(antenna_id, None)

    def delete_antennas(self) -> None:
        """
        delete all antennas
        """
        logging.debug("Remove all antennas for %s", self.core_node.name)
        for antenna_id in self.antennas:
            self.canvas.delete(antenna_id)
        self.antennas.clear()
        self.antenna_images.clear()

    def get_label(self) -> str:
        label = self.core_node.name
        if self.core_node.server:
            label = f"{self.core_node.name}({self.core_node.server})"
        return label

    def redraw(self) -> None:
        self.canvas.itemconfig(self.id, image=self.image)
        label = self.get_label()
        self.canvas.itemconfig(self.text_id, text=label)
        for edge in self.edges:
            edge.redraw()

    def _get_label_y(self) -> int:
        image_box = self.canvas.bbox(self.id)
        return image_box[3] + NODE_TEXT_OFFSET

    def scale_text(self) -> None:
        text_bound = self.canvas.bbox(self.text_id)
        prev_y = (text_bound[3] + text_bound[1]) / 2
        new_y = self._get_label_y()
        self.canvas.move(self.text_id, 0, new_y - prev_y)

    def move(self, x: float, y: float) -> None:
        x, y = self.canvas.get_scaled_coords(x, y)
        current_x, current_y = self.canvas.coords(self.id)
        x_offset = x - current_x
        y_offset = y - current_y
        self.motion(x_offset, y_offset, update=False)

    def motion(self, x_offset: float, y_offset: float, update: bool = True) -> None:
        original_position = self.canvas.coords(self.id)
        self.canvas.move(self.id, x_offset, y_offset)
        pos = self.canvas.coords(self.id)

        # check new position
        bbox = self.canvas.bbox(self.id)
        if not self.canvas.valid_position(*bbox):
            self.canvas.coords(self.id, original_position)
            return

        # move test and selection box
        self.canvas.move(self.text_id, x_offset, y_offset)
        self.canvas.move_selection(self.id, x_offset, y_offset)

        # move antennae
        for antenna_id in self.antennas:
            self.canvas.move(antenna_id, x_offset, y_offset)

        # move edges
        for edge in self.edges:
            edge.move_node(self.id, pos)
        for edge in self.wireless_edges:
            edge.move_node(self.id, pos)

        # set actual coords for node and update core is running
        real_x, real_y = self.canvas.get_actual_coords(*pos)
        self.core_node.position.x = real_x
        self.core_node.position.y = real_y
        if self.app.core.is_runtime() and update:
            self.app.core.edit_node(self.core_node)

    def on_enter(self, event: tk.Event) -> None:
        is_runtime = self.app.core.is_runtime()
        has_observer = self.app.core.observer is not None
        is_container = NodeUtils.is_container_node(self.core_node.type)
        if is_runtime and has_observer and is_container:
            self.tooltip.text.set("waiting...")
            self.tooltip.on_enter(event)
            try:
                output = self.app.core.run(self.core_node.id)
                self.tooltip.text.set(output)
            except grpc.RpcError as e:
                self.app.show_grpc_exception("Observer Error", e)

    def on_leave(self, event: tk.Event) -> None:
        self.tooltip.on_leave(event)

    def double_click(self, event: tk.Event) -> None:
        if self.app.core.is_runtime():
            if NodeUtils.is_container_node(self.core_node.type):
                self.canvas.core.launch_terminal(self.core_node.id)
        else:
            self.show_config()

    def show_info(self, _event: tk.Event) -> None:
        self.app.display_info(NodeInfoFrame, app=self.app, canvas_node=self)

    def show_context(self, event: tk.Event) -> None:
        # clear existing menu
        self.context.delete(0, tk.END)
        is_wlan = self.core_node.type == NodeType.WIRELESS_LAN
        is_emane = self.core_node.type == NodeType.EMANE
        is_mobility = is_wlan or is_emane
        if self.app.core.is_runtime():
            self.context.add_command(label="Configure", command=self.show_config)
            if is_emane:
                self.context.add_command(
                    label="EMANE Config", command=self.show_emane_config
                )
            if is_wlan:
                self.context.add_command(
                    label="WLAN Config", command=self.show_wlan_config
                )
            if is_mobility and self.core_node.id in self.app.core.mobility_players:
                self.context.add_command(
                    label="Mobility Player", command=self.show_mobility_player
                )
        else:
            self.context.add_command(label="Configure", command=self.show_config)
            if NodeUtils.is_container_node(self.core_node.type):
                self.context.add_command(label="Services", command=self.show_services)
                self.context.add_command(
                    label="Config Services", command=self.show_config_services
                )
            if is_emane:
                self.context.add_command(
                    label="EMANE Config", command=self.show_emane_config
                )
            if is_wlan:
                self.context.add_command(
                    label="WLAN Config", command=self.show_wlan_config
                )
            if is_mobility:
                self.context.add_command(
                    label="Mobility Config", command=self.show_mobility_config
                )
            if NodeUtils.is_wireless_node(self.core_node.type):
                self.context.add_command(
                    label="Link To Selected", command=self.wireless_link_selected
                )
            unlink_menu = tk.Menu(self.context)
            for edge in self.edges:
                other_id = edge.src
                if self.id == other_id:
                    other_id = edge.dst
                other_node = self.canvas.nodes[other_id]
                func_unlink = functools.partial(self.click_unlink, edge)
                unlink_menu.add_command(
                    label=other_node.core_node.name, command=func_unlink
                )
            themes.style_menu(unlink_menu)
            self.context.add_cascade(label="Unlink", menu=unlink_menu)
            edit_menu = tk.Menu(self.context)
            themes.style_menu(edit_menu)
            edit_menu.add_command(label="Cut", command=self.click_cut)
            edit_menu.add_command(label="Copy", command=self.canvas_copy)
            edit_menu.add_command(label="Delete", command=self.canvas_delete)
            self.context.add_cascade(label="Edit", menu=edit_menu)
        self.context.tk_popup(event.x_root, event.y_root)

    def click_cut(self) -> None:
        self.canvas_copy()
        self.canvas_delete()

    def click_unlink(self, edge: CanvasEdge) -> None:
        self.canvas.delete_edge(edge)
        self.app.default_info()

    def canvas_delete(self) -> None:
        self.canvas.clear_selection()
        self.canvas.select_object(self.id)
        self.canvas.delete_selected_objects()

    def canvas_copy(self) -> None:
        self.canvas.clear_selection()
        self.canvas.select_object(self.id)
        self.canvas.copy()

    def show_config(self) -> None:
        dialog = NodeConfigDialog(self.app, self)
        dialog.show()

    def show_wlan_config(self) -> None:
        dialog = WlanConfigDialog(self.app, self)
        if not dialog.has_error:
            dialog.show()

    def show_mobility_config(self) -> None:
        dialog = MobilityConfigDialog(self.app, self.core_node)
        if not dialog.has_error:
            dialog.show()

    def show_mobility_player(self) -> None:
        mobility_player = self.app.core.mobility_players[self.core_node.id]
        mobility_player.show()

    def show_emane_config(self) -> None:
        dialog = EmaneConfigDialog(self.app, self.core_node)
        dialog.show()

    def show_services(self) -> None:
        dialog = NodeServiceDialog(self.app, self.core_node)
        dialog.show()

    def show_config_services(self) -> None:
        dialog = NodeConfigServiceDialog(self.app, self.core_node)
        dialog.show()

    def has_emane_link(self, iface_id: int) -> Node:
        result = None
        for edge in self.edges:
            if self.id == edge.src:
                other_id = edge.dst
                edge_iface_id = edge.src_iface.id
            else:
                other_id = edge.src
                edge_iface_id = edge.dst_iface.id
            if edge_iface_id != iface_id:
                continue
            other_node = self.canvas.nodes[other_id]
            if other_node.core_node.type == NodeType.EMANE:
                result = other_node.core_node
                break
        return result

    def wireless_link_selected(self) -> None:
        nodes = [x for x in self.canvas.selection if x in self.canvas.nodes]
        for node_id in nodes:
            canvas_node = self.canvas.nodes[node_id]
            self.canvas.create_edge(self, canvas_node)
        self.canvas.clear_selection()

    def scale_antennas(self) -> None:
        for i in range(len(self.antennas)):
            antenna_id = self.antennas[i]
            image = self.app.get_icon(ImageEnum.ANTENNA, ANTENNA_SIZE)
            self.canvas.itemconfig(antenna_id, image=image)
            self.antenna_images[antenna_id] = image
            node_x, node_y = self.canvas.coords(self.id)
            x, y = self.canvas.coords(antenna_id)
            dx = node_x - 16 + (i * 8 * self.app.app_scale) - x
            dy = node_y - int(23 * self.app.app_scale) - y
            self.canvas.move(antenna_id, dx, dy)
