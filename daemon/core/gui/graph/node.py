import functools
import logging
import tkinter as tk
from typing import TYPE_CHECKING

import grpc

from core.api.grpc import core_pb2
from core.api.grpc.core_pb2 import NodeType
from core.gui import themes
from core.gui.dialogs.emaneconfig import EmaneConfigDialog
from core.gui.dialogs.mobilityconfig import MobilityConfigDialog
from core.gui.dialogs.nodeconfig import NodeConfigDialog
from core.gui.dialogs.nodeconfigservice import NodeConfigServiceDialog
from core.gui.dialogs.nodeservice import NodeServiceDialog
from core.gui.dialogs.wlanconfig import WlanConfigDialog
from core.gui.errors import show_grpc_error
from core.gui.graph import tags
from core.gui.graph.edges import CanvasEdge
from core.gui.graph.tooltip import CanvasTooltip
from core.gui.images import ImageEnum, Images
from core.gui.nodeutils import ANTENNA_SIZE, NodeUtils

if TYPE_CHECKING:
    from core.gui.app import Application
    from PIL.ImageTk import PhotoImage

NODE_TEXT_OFFSET = 5


class CanvasNode:
    def __init__(
        self,
        app: "Application",
        x: float,
        y: float,
        core_node: core_pb2.Node,
        image: "PhotoImage",
    ):
        self.app = app
        self.canvas = app.canvas
        self.image = image
        self.core_node = core_node
        self.id = self.canvas.create_image(
            x, y, anchor=tk.CENTER, image=self.image, tags=tags.NODE
        )
        label_y = self._get_label_y()
        self.text_id = self.canvas.create_text(
            x,
            label_y,
            text=self.core_node.name,
            tags=tags.NODE_LABEL,
            font=self.app.icon_text_font,
            fill="#0000CD",
            state=self.canvas.show_node_labels.state(),
        )
        self.tooltip = CanvasTooltip(self.canvas)
        self.edges = set()
        self.interfaces = []
        self.wireless_edges = set()
        self.antennas = []
        self.antenna_images = {}
        # possible configurations
        self.emane_model_configs = {}
        self.wlan_config = {}
        self.mobility_config = {}
        self.service_configs = {}
        self.service_file_configs = {}
        self.config_service_configs = {}
        self.setup_bindings()

    def setup_bindings(self):
        self.canvas.tag_bind(self.id, "<Double-Button-1>", self.double_click)
        self.canvas.tag_bind(self.id, "<Enter>", self.on_enter)
        self.canvas.tag_bind(self.id, "<Leave>", self.on_leave)

    def delete(self):
        logging.debug("Delete canvas node for %s", self.core_node)
        self.canvas.delete(self.id)
        self.canvas.delete(self.text_id)
        self.delete_antennas()

    def add_antenna(self):
        x, y = self.canvas.coords(self.id)
        offset = len(self.antennas) * 8 * self.app.app_scale
        img = Images.get(ImageEnum.ANTENNA, int(ANTENNA_SIZE * self.app.app_scale))
        antenna_id = self.canvas.create_image(
            x - 16 + offset,
            y - int(23 * self.app.app_scale),
            anchor=tk.CENTER,
            image=img,
            tags=tags.ANTENNA,
        )
        self.antennas.append(antenna_id)
        self.antenna_images[antenna_id] = img

    def delete_antenna(self):
        """
        delete one antenna
        """
        logging.debug("Delete an antenna on %s", self.core_node.name)
        if self.antennas:
            antenna_id = self.antennas.pop()
            self.canvas.delete(antenna_id)
            self.antenna_images.pop(antenna_id, None)

    def delete_antennas(self):
        """
        delete all antennas
        """
        logging.debug("Remove all antennas for %s", self.core_node.name)
        for antenna_id in self.antennas:
            self.canvas.delete(antenna_id)
        self.antennas.clear()
        self.antenna_images.clear()

    def redraw(self):
        self.canvas.itemconfig(self.id, image=self.image)
        self.canvas.itemconfig(self.text_id, text=self.core_node.name)
        for edge in self.edges:
            edge.redraw()

    def _get_label_y(self):
        image_box = self.canvas.bbox(self.id)
        return image_box[3] + NODE_TEXT_OFFSET

    def scale_text(self):
        text_bound = self.canvas.bbox(self.text_id)
        prev_y = (text_bound[3] + text_bound[1]) / 2
        new_y = self._get_label_y()
        self.canvas.move(self.text_id, 0, new_y - prev_y)

    def move(self, x: int, y: int):
        x, y = self.canvas.get_scaled_coords(x, y)
        current_x, current_y = self.canvas.coords(self.id)
        x_offset = x - current_x
        y_offset = y - current_y
        self.motion(x_offset, y_offset, update=False)

    def motion(self, x_offset: int, y_offset: int, update: bool = True):
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

    def on_enter(self, event: tk.Event):
        if self.app.core.is_runtime() and self.app.core.observer:
            self.tooltip.text.set("waiting...")
            self.tooltip.on_enter(event)
            try:
                output = self.app.core.run(self.core_node.id)
                self.tooltip.text.set(output)
            except grpc.RpcError as e:
                show_grpc_error(e, self.app, self.app)

    def on_leave(self, event: tk.Event):
        self.tooltip.on_leave(event)

    def double_click(self, event: tk.Event):
        if self.app.core.is_runtime():
            self.canvas.core.launch_terminal(self.core_node.id)
        else:
            self.show_config()

    def create_context(self) -> tk.Menu:
        is_wlan = self.core_node.type == NodeType.WIRELESS_LAN
        is_emane = self.core_node.type == NodeType.EMANE
        context = tk.Menu(self.canvas)
        themes.style_menu(context)
        if self.app.core.is_runtime():
            context.add_command(label="Configure", command=self.show_config)
            if NodeUtils.is_container_node(self.core_node.type):
                context.add_command(label="Services", state=tk.DISABLED)
                context.add_command(label="Config Services", state=tk.DISABLED)
            if is_wlan:
                context.add_command(label="WLAN Config", command=self.show_wlan_config)
            if is_wlan and self.core_node.id in self.app.core.mobility_players:
                context.add_command(
                    label="Mobility Player", command=self.show_mobility_player
                )
            context.add_command(label="Select Adjacent", state=tk.DISABLED)
            if NodeUtils.is_container_node(self.core_node.type):
                context.add_command(label="Shell Window", state=tk.DISABLED)
                context.add_command(label="Tcpdump", state=tk.DISABLED)
                context.add_command(label="Tshark", state=tk.DISABLED)
                context.add_command(label="Wireshark", state=tk.DISABLED)
                context.add_command(label="View Log", state=tk.DISABLED)
        else:
            context.add_command(label="Configure", command=self.show_config)
            if NodeUtils.is_container_node(self.core_node.type):
                context.add_command(label="Services", command=self.show_services)
                context.add_command(
                    label="Config Services", command=self.show_config_services
                )
            if is_emane:
                context.add_command(
                    label="EMANE Config", command=self.show_emane_config
                )
            if is_wlan:
                context.add_command(label="WLAN Config", command=self.show_wlan_config)
                context.add_command(
                    label="Mobility Config", command=self.show_mobility_config
                )
            if NodeUtils.is_wireless_node(self.core_node.type):
                context.add_command(
                    label="Link To Selected", command=self.wireless_link_selected
                )
                context.add_command(label="Select Members", state=tk.DISABLED)
            unlink_menu = tk.Menu(context)
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
            context.add_cascade(label="Unlink", menu=unlink_menu)
            edit_menu = tk.Menu(context)
            themes.style_menu(edit_menu)
            edit_menu.add_command(label="Cut", command=self.click_cut)
            edit_menu.add_command(label="Copy", command=self.canvas_copy)
            edit_menu.add_command(label="Delete", command=self.canvas_delete)
            context.add_cascade(label="Edit", menu=edit_menu)
        return context

    def click_cut(self) -> None:
        self.canvas_copy()
        self.canvas_delete()

    def click_unlink(self, edge: CanvasEdge) -> None:
        self.canvas.delete_edge(edge)
        self.app.core.deleted_graph_edges([edge])

    def canvas_delete(self) -> None:
        self.canvas.clear_selection()
        self.canvas.selection[self.id] = self
        self.canvas.delete_selected_objects()

    def canvas_copy(self) -> None:
        self.canvas.clear_selection()
        self.canvas.selection[self.id] = self
        self.canvas.copy()

    def show_config(self):
        self.canvas.context = None
        dialog = NodeConfigDialog(self.app, self.app, self)
        dialog.show()

    def show_wlan_config(self):
        self.canvas.context = None
        dialog = WlanConfigDialog(self.app, self.app, self)
        if not dialog.has_error:
            dialog.show()

    def show_mobility_config(self):
        self.canvas.context = None
        dialog = MobilityConfigDialog(self.app, self.app, self)
        if not dialog.has_error:
            dialog.show()

    def show_mobility_player(self):
        self.canvas.context = None
        mobility_player = self.app.core.mobility_players[self.core_node.id]
        mobility_player.show()

    def show_emane_config(self):
        self.canvas.context = None
        dialog = EmaneConfigDialog(self.app, self.app, self)
        dialog.show()

    def show_services(self):
        self.canvas.context = None
        dialog = NodeServiceDialog(self.app.master, self.app, self)
        dialog.show()

    def show_config_services(self):
        self.canvas.context = None
        dialog = NodeConfigServiceDialog(self.app.master, self.app, self)
        dialog.show()

    def has_emane_link(self, interface_id: int) -> core_pb2.Node:
        result = None
        for edge in self.edges:
            if self.id == edge.src:
                other_id = edge.dst
                edge_interface_id = edge.src_interface.id
            else:
                other_id = edge.src
                edge_interface_id = edge.dst_interface.id
            if edge_interface_id != interface_id:
                continue
            other_node = self.canvas.nodes[other_id]
            if other_node.core_node.type == NodeType.EMANE:
                result = other_node.core_node
                break
        return result

    def wireless_link_selected(self):
        self.canvas.context = None
        for canvas_nid in [
            x for x in self.canvas.selection if "node" in self.canvas.gettags(x)
        ]:
            core_node = self.canvas.nodes[canvas_nid].core_node
            if core_node.type == core_pb2.NodeType.DEFAULT and core_node.model == "mdr":
                self.canvas.create_edge(self, self.canvas.nodes[canvas_nid])
        self.canvas.clear_selection()

    def scale_antennas(self):
        for i in range(len(self.antennas)):
            antenna_id = self.antennas[i]
            image = Images.get(
                ImageEnum.ANTENNA, int(ANTENNA_SIZE * self.app.app_scale)
            )
            self.canvas.itemconfig(antenna_id, image=image)
            self.antenna_images[antenna_id] = image
            node_x, node_y = self.canvas.coords(self.id)
            x, y = self.canvas.coords(antenna_id)
            dx = node_x - 16 + (i * 8 * self.app.app_scale) - x
            dy = node_y - int(23 * self.app.app_scale) - y
            self.canvas.move(antenna_id, dx, dy)
