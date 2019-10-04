import enum
import logging
import tkinter as tk

from core.api.grpc import core_pb2
from coretk.grpcmanagement import GrpcManager
from coretk.images import Images


class GraphMode(enum.Enum):
    SELECT = 0
    EDGE = 1
    PICKNODE = 2
    NODE = 3
    OTHER = 4


class CanvasGraph(tk.Canvas):
    def __init__(self, master=None, grpc=None, cnf=None, **kwargs):
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
        self.setup_menus()
        self.setup_bindings()
        self.draw_grid()
        self.core_grpc = grpc
        self.grpc_manager = GrpcManager()
        self.draw_existing_component()

    def setup_menus(self):
        self.node_context = tk.Menu(self.master)
        self.node_context.add_command(label="One")
        self.node_context.add_command(label="Two")
        self.node_context.add_command(label="Three")

    def setup_bindings(self):
        """
        Bind any mouse events or hot keys to the matching action

        :return: nothing
        """
        self.bind("<ButtonPress-1>", self.click_press)
        self.bind("<ButtonRelease-1>", self.click_release)
        self.bind("<B1-Motion>", self.click_motion)
        self.bind("<Button-3>", self.context)
        # self.bind("e", self.set_mode)
        # self.bind("s", self.set_mode)
        # self.bind("n", self.set_mode)

    def draw_grid(self, width=1000, height=750):
        """
        Create grid

        :param int width: the width
        :param int height: the height

        :return: nothing
        """
        rectangle_id = self.create_rectangle(
            0,
            0,
            width,
            height,
            outline="#000000",
            fill="#ffffff",
            width=1,
            tags="rectangle",
        )
        self.tag_lower(rectangle_id)
        for i in range(0, width, 27):
            self.create_line(i, 0, i, height, dash=(2, 4), tags="grid line")
        for i in range(0, height, 27):
            self.create_line(0, i, width, i, dash=(2, 4), tags="grid line")

    def draw_existing_component(self):
        """
        Draw existing node and update the information in grpc manager to match

        :return: nothing
        """
        core_id_to_canvas_id = {}

        session_id = self.core_grpc.session_id
        session = self.core_grpc.core.get_session(session_id).session
        # nodes = response.session.nodes
        # if len(nodes) > 0:
        for node in session.nodes:
            # peer to peer node is not drawn on the GUI
            if node.type != core_pb2.NodeType.PEER_TO_PEER:
                image, name = Images.convert_type_and_model_to_image(
                    node.type, node.model
                )
                n = CanvasNode(node.position.x, node.position.y, image, self, node.id)
                self.nodes[n.id] = n
                core_id_to_canvas_id[node.id] = n.id
                self.grpc_manager.add_preexisting_node(n, session_id, node, name)
        self.grpc_manager.update_reusable_id()
        # draw existing links
        # links = response.session.links
        for link in session.links:
            n1 = self.nodes[core_id_to_canvas_id[link.node_one_id]]
            n2 = self.nodes[core_id_to_canvas_id[link.node_two_id]]
            e = CanvasEdge(n1.x_coord, n1.y_coord, n2.x_coord, n2.y_coord, n1.id, self)
            self.edges[e.token] = e
            self.grpc_manager.add_edge(session_id, e.token, n1.id, n2.id)
        # lift the nodes so they on top of the links
        for i in core_id_to_canvas_id.values():
            self.lift(i)

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

            self.grpc_manager.add_edge(
                self.core_grpc.get_session_id(), edge.token, node_src.id, node_dst.id
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
        selected = self.get_selected(event)
        nodes = self.find_withtag("node")
        if selected in nodes:
            logging.debug(f"node context: {selected}")
            self.node_context.post(event.x_root, event.y_root)

    def add_node(self, x, y, image, node_name):
        node = CanvasNode(
            x=x, y=y, image=image, canvas=self, core_id=self.grpc_manager.peek_id()
        )
        self.nodes[node.id] = node
        self.grpc_manager.add_node(
            self.core_grpc.get_session_id(), node.id, x, y, node_name
        )
        return node


class CanvasEdge:
    """
    Canvas edge class
    """

    width = 3

    def __init__(self, x1, y1, x2, y2, src, canvas):
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
        self.id = self.canvas.create_line(x1, y1, x2, y2, tags="edge", width=self.width)
        self.token = None

        # TODO resolve this
        # self.canvas.tag_lower(self.id)

    def complete(self, dst, x, y):
        self.dst = dst
        self.token = tuple(sorted((self.src, self.dst)))
        x1, y1, _, _ = self.canvas.coords(self.id)
        self.canvas.coords(self.id, x1, y1, x, y)
        self.canvas.lift(self.src)
        self.canvas.lift(self.dst)

    def delete(self):
        self.canvas.delete(self.id)


class CanvasNode:
    def __init__(self, x, y, image, canvas, core_id):
        self.image = image
        self.canvas = canvas
        self.id = self.canvas.create_image(
            x, y, anchor=tk.CENTER, image=self.image, tags="node"
        )
        self.core_id = core_id
        self.x_coord = x
        self.y_coord = y
        self.name = f"Node {self.core_id}"
        self.text_id = self.canvas.create_text(x, y + 20, text=self.name)
        self.canvas.tag_bind(self.id, "<ButtonPress-1>", self.click_press)
        self.canvas.tag_bind(self.id, "<ButtonRelease-1>", self.click_release)
        self.canvas.tag_bind(self.id, "<B1-Motion>", self.motion)
        self.canvas.tag_bind(self.id, "<Button-3>", self.context)
        self.edges = set()
        self.moving = None

    #
    # def get_coords(self):
    #     return self.x_coord, self.y_coord

    def update_coords(self):
        self.x_coord, self.y_coord = self.canvas.coords(self.id)

    def click_press(self, event):
        logging.debug(f"click press {self.name}: {event}")
        self.moving = self.canvas.canvas_xy(event)

    def click_release(self, event):
        logging.debug(f"click release {self.name}: {event}")
        self.update_coords()
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
        new_x, new_y = self.canvas.coords(self.id)
        for edge in self.edges:
            x1, y1, x2, y2 = self.canvas.coords(edge.id)
            if x1 == old_x and y1 == old_y:
                self.canvas.coords(edge.id, new_x, new_y, x2, y2)
            else:
                self.canvas.coords(edge.id, x1, y1, new_x, new_y)

    def context(self, event):
        logging.debug(f"context click {self.name}: {event}")
