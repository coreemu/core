import enum
import logging
import tkinter as tk

from core.api.grpc import core_pb2
from coretk.canvasaction import CanvasAction
from coretk.graph_helper import GraphHelper, WlanAntennaManager
from coretk.images import Images
from coretk.interface import Interface
from coretk.linkinfo import LinkInfo, Throughput
from coretk.wirelessconnection import WirelessConnection


class GraphMode(enum.Enum):
    SELECT = 0
    EDGE = 1
    PICKNODE = 2
    NODE = 3
    OTHER = 4


CORE_NODES = ["router"]
CORE_WIRED_NETWORK_NODES = []
CORE_WIRELESS_NODE = ["wlan"]
CORE_EMANE = ["emane"]


class CanvasGraph(tk.Canvas):
    def __init__(self, master, core_grpc, cnf=None, **kwargs):
        if cnf is None:
            cnf = {}
        kwargs["highlightthickness"] = 0
        super().__init__(master, cnf, **kwargs)
        self.mode = GraphMode.SELECT
        self.draw_node_image = None
        self.draw_node_name = None
        self.selected = None
        self.node_context = None
        self.nodes = {}
        self.edges = {}
        self.drawing_edge = None
        self.grid = None
        self.meters_per_pixel = 1.5
        self.canvas_action = CanvasAction(master, self)
        self.setup_menus()
        self.setup_bindings()
        self.draw_grid()
        self.core_grpc = core_grpc
        self.helper = GraphHelper(self, core_grpc)
        self.throughput_draw = Throughput(self, core_grpc)
        self.wireless_draw = WirelessConnection(self, core_grpc)
        self.is_node_context_opened = False

    def setup_menus(self):
        self.node_context = tk.Menu(self.master)
        self.node_context.add_command(
            label="Configure", command=self.canvas_action.display_node_configuration
        )
        self.node_context.add_command(label="Select adjacent")
        self.node_context.add_command(label="Create link to")
        self.node_context.add_command(label="Assign to")
        self.node_context.add_command(label="Move to")
        self.node_context.add_command(label="Cut")
        self.node_context.add_command(label="Copy")
        self.node_context.add_command(label="Paste")
        self.node_context.add_command(label="Delete")
        self.node_context.add_command(label="Hide")
        self.node_context.add_command(label="Services")

    def canvas_reset_and_redraw(self, session):
        """
        Reset the private variables CanvasGraph object, redraw nodes given the new grpc
        client.

        :param core.api.grpc.core_pb2.Session session: session to draw
        :return: nothing
        """
        # delete any existing drawn items
        self.helper.delete_canvas_components()

        # set the private variables to default value
        self.mode = GraphMode.SELECT
        self.draw_node_image = None
        self.draw_node_name = None
        self.selected = None
        self.node_context = None
        self.nodes = {}
        self.edges = {}
        self.drawing_edge = None
        self.draw_existing_component(session)

    def setup_bindings(self):
        """
        Bind any mouse events or hot keys to the matching action

        :return: nothing
        """
        self.bind("<ButtonPress-1>", self.click_press)
        self.bind("<ButtonRelease-1>", self.click_release)
        self.bind("<B1-Motion>", self.click_motion)
        self.bind("<Button-3>", self.context)

    def draw_grid(self, width=1000, height=800):
        """
        Create grid

        :param int width: the width
        :param int height: the height

        :return: nothing
        """
        self.grid = self.create_rectangle(
            0,
            0,
            width,
            height,
            outline="#000000",
            fill="#ffffff",
            width=1,
            tags="rectangle",
        )
        self.tag_lower(self.grid)
        for i in range(0, width, 27):
            self.create_line(i, 0, i, height, dash=(2, 4), tags="gridline")
        for i in range(0, height, 27):
            self.create_line(0, i, width, i, dash=(2, 4), tags="gridline")

    def draw_existing_component(self, session):
        """
        Draw existing node and update the information in grpc manager to match

        :return: nothing
        """
        core_id_to_canvas_id = {}
        # redraw existing nodes
        for node in session.nodes:
            # peer to peer node is not drawn on the GUI
            if node.type != core_pb2.NodeType.PEER_TO_PEER:
                # draw nodes on the canvas
                image, name = Images.convert_type_and_model_to_image(
                    node.type, node.model
                )
                n = CanvasNode(
                    node.position.x, node.position.y, image, name, self, node.id
                )
                self.nodes[n.id] = n
                core_id_to_canvas_id[node.id] = n.id

                # store the node in grpc manager
                self.core_grpc.manager.add_preexisting_node(n, session.id, node, name)

        # draw existing links
        for link in session.links:
            n1 = self.nodes[core_id_to_canvas_id[link.node_one_id]]
            n2 = self.nodes[core_id_to_canvas_id[link.node_two_id]]
            if link.type == core_pb2.LinkType.WIRED:
                e = CanvasEdge(
                    n1.x_coord,
                    n1.y_coord,
                    n2.x_coord,
                    n2.y_coord,
                    n1.id,
                    self,
                    is_wired=True,
                )
            elif link.type == core_pb2.LinkType.WIRELESS:
                e = CanvasEdge(
                    n1.x_coord,
                    n1.y_coord,
                    n2.x_coord,
                    n2.y_coord,
                    n1.id,
                    self,
                    is_wired=False,
                )
            edge_token = tuple(sorted((n1.id, n2.id)))
            e.token = edge_token
            e.dst = n2.id
            n1.edges.add(e)
            n2.edges.add(e)
            self.edges[e.token] = e
            self.core_grpc.manager.add_edge(session.id, e.token, n1.id, n2.id)

            self.helper.redraw_antenna(link, n1, n2)

            # TODO add back the link info to grpc manager also redraw
            grpc_if1 = link.interface_one
            grpc_if2 = link.interface_two
            ip4_src = None
            ip4_dst = None
            ip6_src = None
            ip6_dst = None
            if grpc_if1 is not None:
                ip4_src = grpc_if1.ip4
                ip6_src = grpc_if1.ip6
            if grpc_if2 is not None:
                ip4_dst = grpc_if2.ip4
                ip6_dst = grpc_if2.ip6
            e.link_info = LinkInfo(
                canvas=self,
                edge=e,
                ip4_src=ip4_src,
                ip6_src=ip6_src,
                ip4_dst=ip4_dst,
                ip6_dst=ip6_dst,
            )

            # TODO will include throughput and ipv6 in the future
            if1 = Interface(grpc_if1.name, grpc_if1.ip4, ifid=grpc_if1.id)
            if2 = Interface(grpc_if2.name, grpc_if2.ip4, ifid=grpc_if2.id)
            self.core_grpc.manager.edges[e.token].interface_1 = if1
            self.core_grpc.manager.edges[e.token].interface_2 = if2
            self.core_grpc.manager.nodes[
                core_id_to_canvas_id[link.node_one_id]
            ].interfaces.append(if1)
            self.core_grpc.manager.nodes[
                core_id_to_canvas_id[link.node_two_id]
            ].interfaces.append(if2)

        # lift the nodes so they on top of the links
        for i in self.find_withtag("node"):
            self.lift(i)

    # def delete_components(self):
    #     tags = ["node", "edge", "linkinfo", "nodename"]
    #     for i in tags:
    #         for id in self.find_withtag(i):
    #             self.delete(id)

    def canvas_xy(self, event):
        """
        Convert window coordinate to canvas coordinate

        :param event:
        :rtype: (int, int)
        :return: x, y canvas coordinate
        """
        x = self.canvasx(event.x)
        y = self.canvasy(event.y)
        return x, y

    def get_selected(self, event):
        """
        Retrieve the item id that is on the mouse position

        :param event: mouse event
        :rtype: int
        :return: the item that the mouse point to
        """
        overlapping = self.find_overlapping(event.x, event.y, event.x, event.y)
        nodes = set(self.find_withtag("node"))
        selected = None
        for _id in overlapping:
            if self.drawing_edge and self.drawing_edge.id == _id:
                continue

            if _id in nodes:
                selected = _id
                break

            if selected is None:
                selected = _id

        return selected

    def click_release(self, event):
        """
        Draw a node or finish drawing an edge according to the current graph mode

        :param event: mouse event
        :return: nothing
        """
        if self.is_node_context_opened:
            self.node_context.unpost()
            self.is_node_context_opened = False
        else:
            self.focus_set()
            self.selected = self.get_selected(event)
            logging.debug(f"click release selected: {self.selected}")
            if self.mode == GraphMode.EDGE:
                self.handle_edge_release(event)
            elif self.mode == GraphMode.NODE:
                x, y = self.canvas_xy(event)
                self.add_node(x, y, self.draw_node_image, self.draw_node_name)
            elif self.mode == GraphMode.PICKNODE:
                self.mode = GraphMode.NODE

    def handle_edge_release(self, event):
        edge = self.drawing_edge
        self.drawing_edge = None

        # not drawing edge return
        if edge is None:
            return

        # edge dst must be a node
        logging.debug(f"current selected: {self.selected}")
        logging.debug(f"current nodes: {self.find_withtag('node')}")
        is_node = self.selected in self.find_withtag("node")
        if not is_node:
            edge.delete()
            return

        # edge dst is same as src, delete edge
        if edge.src == self.selected:
            edge.delete()

        # set dst node and snap edge to center
        x, y = self.coords(self.selected)
        edge.complete(self.selected, x, y)
        logging.debug(f"drawing edge token: {edge.token}")
        if edge.token in self.edges:
            edge.delete()
        else:
            self.edges[edge.token] = edge
            node_src = self.nodes[edge.src]
            node_src.edges.add(edge)
            node_dst = self.nodes[edge.dst]
            node_dst.edges.add(edge)

            self.core_grpc.manager.add_edge(
                self.core_grpc.session_id, edge.token, node_src.id, node_dst.id
            )

            # draw link info on the edge
            if1 = self.core_grpc.manager.edges[edge.token].interface_1
            if2 = self.core_grpc.manager.edges[edge.token].interface_2
            ip4_and_prefix_1 = None
            ip4_and_prefix_2 = None
            if if1 is not None:
                ip4_and_prefix_1 = if1.ip4_and_prefix
            if if2 is not None:
                ip4_and_prefix_2 = if2.ip4_and_prefix
            edge.link_info = LinkInfo(
                self,
                edge,
                ip4_src=ip4_and_prefix_1,
                ip6_src=None,
                ip4_dst=ip4_and_prefix_2,
                ip6_dst=None,
            )

        logging.debug(f"edges: {self.find_withtag('edge')}")

    def click_press(self, event):
        """
        Start drawing an edge if mouse click is on a node

        :param event: mouse event
        :return: nothing
        """
        logging.debug(f"click press: {event}")
        selected = self.get_selected(event)
        is_node = selected in self.find_withtag("node")
        if self.mode == GraphMode.EDGE and is_node:
            x, y = self.coords(selected)
            self.drawing_edge = CanvasEdge(x, y, x, y, selected, self)

    def click_motion(self, event):
        """
        Redraw drawing edge according to the current position of the mouse

        :param event: mouse event
        :return: nothing
        """
        if self.mode == GraphMode.EDGE and self.drawing_edge is not None:
            x2, y2 = self.canvas_xy(event)
            x1, y1, _, _ = self.coords(self.drawing_edge.id)
            self.coords(self.drawing_edge.id, x1, y1, x2, y2)

    def context(self, event):
        if not self.is_node_context_opened:
            selected = self.get_selected(event)
            nodes = self.find_withtag("node")
            if selected in nodes:
                logging.debug(f"node context: {selected}")
                self.node_context.post(event.x_root, event.y_root)
                self.canvas_action.node_to_show_config = self.nodes[selected]
            self.is_node_context_opened = True
        else:
            self.node_context.unpost()
            self.is_node_context_opened = False

    def add_node(self, x, y, image, node_name):
        plot_id = self.find_all()[0]
        if self.selected == plot_id:
            node = CanvasNode(
                x=x,
                y=y,
                image=image,
                node_type=node_name,
                canvas=self,
                core_id=self.core_grpc.manager.peek_id(),
            )
            self.nodes[node.id] = node
            self.core_grpc.manager.add_node(
                self.core_grpc.session_id, node.id, x, y, node_name
            )
            return node


class CanvasEdge:
    """
    Canvas edge class
    """

    width = 1.4

    def __init__(self, x1, y1, x2, y2, src, canvas, is_wired=None):
        """
        Create an instance of canvas edge object
        :param int x1: source x-coord
        :param int y1: source y-coord
        :param int x2: destination x-coord
        :param int y2: destination y-coord
        :param int src: source id
        :param tkinter.Canvas canvas: canvas object
        """
        self.src = src
        self.dst = None
        self.canvas = canvas

        if is_wired is None or is_wired is True:
            self.id = self.canvas.create_line(
                x1, y1, x2, y2, tags="edge", width=self.width, fill="#ff0000"
            )
        else:
            self.id = self.canvas.create_line(
                x1,
                y1,
                x2,
                y2,
                tags="edge",
                width=self.width,
                fill="#ff0000",
                state=tk.HIDDEN,
            )
        self.token = None

        # link info object
        self.link_info = None
        self.throughput = None
        self.wired = is_wired
        # TODO resolve this
        # self.canvas.tag_lower(self.id)

    def complete(self, dst, x, y):
        self.dst = dst
        self.token = tuple(sorted((self.src, self.dst)))
        x1, y1, _, _ = self.canvas.coords(self.id)
        self.canvas.coords(self.id, x1, y1, x, y)
        self.canvas.helper.draw_wireless_case(self.src, self.dst, self)
        self.canvas.lift(self.src)
        self.canvas.lift(self.dst)

    def delete(self):
        self.canvas.delete(self.id)


class CanvasNode:
    def __init__(self, x, y, image, node_type, canvas, core_id):
        self.image = image
        self.node_type = node_type
        self.canvas = canvas
        self.id = self.canvas.create_image(
            x, y, anchor=tk.CENTER, image=self.image, tags="node"
        )
        self.core_id = core_id
        self.x_coord = x
        self.y_coord = y
        self.name = f"N{self.core_id}"
        self.text_id = self.canvas.create_text(
            x, y + 20, text=self.name, tags="nodename"
        )
        self.antenna_draw = WlanAntennaManager(self.canvas, self.id)

        self.canvas.tag_bind(self.id, "<ButtonPress-1>", self.click_press)
        self.canvas.tag_bind(self.id, "<ButtonRelease-1>", self.click_release)
        self.canvas.tag_bind(self.id, "<B1-Motion>", self.motion)
        self.canvas.tag_bind(self.id, "<Button-3>", self.context)
        self.canvas.tag_bind(self.id, "<Double-Button-1>", self.double_click)

        self.edges = set()
        self.wlans = []
        self.moving = None

    def double_click(self, event):
        node_id = self.canvas.core_grpc.manager.nodes[self.id].node_id
        state = self.canvas.core_grpc.get_session_state()
        if state == core_pb2.SessionState.RUNTIME:
            self.canvas.core_grpc.launch_terminal(node_id)
        else:
            self.canvas.canvas_action.display_configuration(self)
            # if self.node_type in CORE_NODES:
            #     self.canvas.canvas_action.node_to_show_config = self
            #     self.canvas.canvas_action.display_node_configuration()
            # elif self.node_type in CORE_WIRED_NETWORK_NODES:
            #     return
            # elif self.node_type in CORE_WIRELESS_NODE:
            #     return
            # elif self

    def update_coords(self):
        self.x_coord, self.y_coord = self.canvas.coords(self.id)

    def click_press(self, event):
        logging.debug(f"click press {self.name}: {event}")
        self.moving = self.canvas.canvas_xy(event)
        # return "break"

    def click_release(self, event):
        logging.debug(f"click release {self.name}: {event}")
        self.update_coords()
        self.canvas.core_grpc.manager.update_node_location(
            self.id, self.x_coord, self.y_coord
        )
        self.moving = None

    def motion(self, event):
        if self.canvas.mode == GraphMode.EDGE or self.canvas.mode == GraphMode.NODE:
            return
        x, y = self.canvas.canvas_xy(event)
        moving_x, moving_y = self.moving
        offset_x, offset_y = x - moving_x, y - moving_y
        self.moving = x, y

        old_x, old_y = self.canvas.coords(self.id)
        self.canvas.move(self.id, offset_x, offset_y)
        self.canvas.move(self.text_id, offset_x, offset_y)
        self.antenna_draw.update_antennas_position(offset_x, offset_y)

        new_x, new_y = self.canvas.coords(self.id)

        if self.canvas.core_grpc.get_session_state() == core_pb2.SessionState.RUNTIME:
            self.canvas.core_grpc.edit_node(self.core_id, int(new_x), int(new_y))

        for edge in self.edges:
            x1, y1, x2, y2 = self.canvas.coords(edge.id)
            if x1 == old_x and y1 == old_y:
                self.canvas.coords(edge.id, new_x, new_y, x2, y2)
            else:
                self.canvas.coords(edge.id, x1, y1, new_x, new_y)
            edge.link_info.recalculate_info()
            # self.canvas.core_grpc.throughput_draw.update_throughtput_location(edge)

        self.canvas.helper.update_wlan_connection(
            old_x, old_y, new_x, new_y, self.wlans
        )

    def context(self, event):
        logging.debug(f"context click {self.name}: {event}")
