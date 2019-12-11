import tkinter as tk
from tkinter import font

import grpc

from core.api.grpc.core_pb2 import NodeType
from coretk.dialogs.emaneconfig import EmaneConfigDialog
from coretk.dialogs.mobilityconfig import MobilityConfigDialog
from coretk.dialogs.nodeconfig import NodeConfigDialog
from coretk.dialogs.nodeservice import NodeService
from coretk.dialogs.wlanconfig import WlanConfigDialog
from coretk.errors import show_grpc_error
from coretk.graph import tags
from coretk.graph.tooltip import CanvasTooltip
from coretk.nodeutils import NodeUtils

NODE_TEXT_OFFSET = 5


class CanvasNode:
    def __init__(self, app, core_node, image):
        self.app = app
        self.canvas = app.canvas
        self.image = image
        self.core_node = core_node
        x = self.core_node.position.x
        y = self.core_node.position.y
        self.id = self.canvas.create_image(
            x, y, anchor=tk.CENTER, image=self.image, tags=tags.NODE
        )
        text_font = font.Font(family="TkIconFont", size=12)
        label_y = self._get_label_y()
        self.text_id = self.canvas.create_text(
            x,
            label_y,
            text=self.core_node.name,
            tags=tags.NODE_NAME,
            font=text_font,
            fill="#0000CD",
        )
        self.tooltip = CanvasTooltip(self.canvas)
        self.edges = set()
        self.interfaces = []
        self.wireless_edges = set()
        self.antennae = []
        self.setup_bindings()

    def setup_bindings(self):
        self.canvas.tag_bind(self.id, "<Double-Button-1>", self.double_click)
        self.canvas.tag_bind(self.id, "<Enter>", self.on_enter)
        self.canvas.tag_bind(self.id, "<Leave>", self.on_leave)

    def delete(self):
        self.canvas.delete(self.id)
        self.canvas.delete(self.text_id)
        self.delete_antennae()

    def add_antenna(self):
        x, y = self.canvas.coords(self.id)
        offset = len(self.antennae) * 8
        antenna_id = self.canvas.create_image(
            x - 16 + offset,
            y - 23,
            anchor=tk.CENTER,
            image=NodeUtils.ANTENNA_ICON,
            tags=tags.ANTENNA,
        )
        self.antennae.append(antenna_id)

    def delete_antenna(self):
        """
        delete one antenna

        :return: nothing
        """
        if self.antennae:
            antenna_id = self.antennae.pop()
            self.canvas.delete(antenna_id)

    def delete_antennae(self):
        """
        delete all antennas

        :return: nothing
        """
        for antenna_id in self.antennae:
            self.canvas.delete(antenna_id)
        self.antennae.clear()

    def redraw(self):
        self.canvas.itemconfig(self.id, image=self.image)
        self.canvas.itemconfig(self.text_id, text=self.core_node.name)

    def _get_label_y(self):
        image_box = self.canvas.bbox(self.id)
        return image_box[3] + NODE_TEXT_OFFSET

    def move(self, x, y):
        x_offset = x - self.core_node.position.x
        y_offset = y - self.core_node.position.y
        self.motion(x_offset, y_offset, update=False)

    def motion(self, x_offset, y_offset, update=True):
        self.canvas.move(self.id, x_offset, y_offset)
        self.canvas.move(self.text_id, x_offset, y_offset)
        self.canvas.move_selection(self.id, x_offset, y_offset)
        x, y = self.canvas.coords(self.id)
        self.core_node.position.x = int(x)
        self.core_node.position.y = int(y)

        # move antennae
        for antenna_id in self.antennae:
            self.canvas.move(antenna_id, x_offset, y_offset)

        # move edges
        for edge in self.edges:
            x1, y1, x2, y2 = self.canvas.coords(edge.id)
            if edge.src == self.id:
                self.canvas.coords(edge.id, x, y, x2, y2)
            else:
                self.canvas.coords(edge.id, x1, y1, x, y)
            self.canvas.throughput_draw.move(edge)
            edge.link_info.recalculate_info()

        for edge in self.wireless_edges:
            x1, y1, x2, y2 = self.canvas.coords(edge.id)
            if edge.src == self.id:
                self.canvas.coords(edge.id, x, y, x2, y2)
            else:
                self.canvas.coords(edge.id, x1, y1, x, y)

        # update core with new location
        if self.app.core.is_runtime() and update:
            self.app.core.edit_node(self.core_node)

    def on_enter(self, event):
        if self.app.core.is_runtime() and self.app.core.observer:
            self.tooltip.text.set("waiting...")
            self.tooltip.on_enter(event)
            try:
                output = self.app.core.run(self.core_node.id)
                self.tooltip.text.set(output)
            except grpc.RpcError as e:
                show_grpc_error(e)

    def on_leave(self, event):
        self.tooltip.on_leave(event)

    def double_click(self, event):
        if self.app.core.is_runtime():
            self.canvas.core.launch_terminal(self.core_node.id)
        else:
            self.show_config()

    def update_coords(self):
        x, y = self.canvas.coords(self.id)
        self.core_node.position.x = int(x)
        self.core_node.position.y = int(y)

    def create_context(self):
        is_wlan = self.core_node.type == NodeType.WIRELESS_LAN
        is_emane = self.core_node.type == NodeType.EMANE
        context = tk.Menu(self.canvas)
        if self.app.core.is_runtime():
            context.add_command(label="Configure", command=self.show_config)
            if NodeUtils.is_container_node(self.core_node.type):
                context.add_command(label="Services", state=tk.DISABLED)
            if is_wlan and self.core_node.id in self.app.core.mobility_players:
                context.add_command(
                    label="Mobility Player", command=self.show_mobility_player
                )
            context.add_command(label="Select Adjacent", state=tk.DISABLED)
            context.add_command(label="Hide", state=tk.DISABLED)
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
                context.add_command(label="Link To All MDRs", state=tk.DISABLED)
                context.add_command(label="Select Members", state=tk.DISABLED)
            context.add_command(label="Select Adjacent", state=tk.DISABLED)
            context.add_command(label="Create Link To", state=tk.DISABLED)
            context.add_command(label="Assign To", state=tk.DISABLED)
            context.add_command(label="Move To", state=tk.DISABLED)
            context.add_command(label="Cut", state=tk.DISABLED)
            context.add_command(label="Copy", state=tk.DISABLED)
            context.add_command(label="Paste", state=tk.DISABLED)
            context.add_command(label="Delete", state=tk.DISABLED)
            context.add_command(label="Hide", state=tk.DISABLED)
        return context

    def show_config(self):
        self.canvas.context = None
        dialog = NodeConfigDialog(self.app, self.app, self)
        dialog.show()

    def show_wlan_config(self):
        self.canvas.context = None
        dialog = WlanConfigDialog(self.app, self.app, self)
        dialog.show()

    def show_mobility_config(self):
        self.canvas.context = None
        dialog = MobilityConfigDialog(self.app, self.app, self)
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
        dialog = NodeService(self.app.master, self.app, self)
        dialog.show()
