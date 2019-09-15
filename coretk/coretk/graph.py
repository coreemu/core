import enum
import tkinter as tk

from PIL import Image, ImageTk


class GraphMode(enum.Enum):
    SELECT = 0
    EDGE = 1
    NODE = 2


class CanvasGraph(tk.Canvas):
    images = {}

    @classmethod
    def load(cls, name, file_path):
        image = Image.open(file_path)
        tk_image = ImageTk.PhotoImage(image)
        cls.images[name] = tk_image

    def __init__(self, master=None, cnf=None, **kwargs):
        if cnf is None:
            cnf = {}
        kwargs["highlightthickness"] = 0
        super().__init__(master, cnf, **kwargs)
        self.mode = GraphMode.SELECT
        self.selected = None
        self.node_context = None
        self.nodes = {}
        self.edges = {}
        self.drawing_edge = None
        self.setup_menus()
        self.setup_bindings()

    def setup_menus(self):
        self.node_context = tk.Menu(self.master)
        self.node_context.add_command(label="One")
        self.node_context.add_command(label="Two")
        self.node_context.add_command(label="Three")

    def setup_bindings(self):
        self.bind("<ButtonPress-1>", self.click_press)
        self.bind("<ButtonRelease-1>", self.click_release)
        self.bind("<B1-Motion>", self.click_motion)
        self.bind("<Button-3>", self.context)
        self.bind("e", self.set_mode)
        self.bind("s", self.set_mode)
        self.bind("n", self.set_mode)

    def canvas_xy(self, event):
        x = self.canvasx(event.x)
        y = self.canvasy(event.y)
        return x, y

    def get_selected(self, event):
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
        self.focus_set()
        self.selected = self.get_selected(event)
        print(f"click release selected: {self.selected}")
        if self.mode == GraphMode.EDGE:
            self.handle_edge_release(event)
        elif self.mode == GraphMode.NODE:
            x, y = self.canvas_xy(event)
            self.add_node(x, y, "Node", "switch")

    def handle_edge_release(self, event):
        edge = self.drawing_edge
        self.drawing_edge = None

        # not drawing edge return
        if edge is None:
            return

        # edge dst must be a node
        print(f"current selected: {self.selected}")
        print(f"current nodes: {self.find_withtag('node')}")
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
        print(f"drawing edge token: {edge.token}")
        if edge.token in self.edges:
            edge.delete()
        else:
            self.edges[edge.token] = edge
            node_src = self.nodes[edge.src]
            node_src.edges.add(edge)
            node_dst = self.nodes[edge.dst]
            node_dst.edges.add(edge)

        print(f"edges: {self.find_withtag('edge')}")

    def click_press(self, event):
        print(f"click press: {event}")
        selected = self.get_selected(event)
        is_node = selected in self.find_withtag("node")
        if self.mode == GraphMode.EDGE and is_node:
            x, y = self.coords(selected)
            self.drawing_edge = CanvasEdge(x, y, x, y, selected, self)

    def click_motion(self, event):
        if self.mode == GraphMode.EDGE and self.drawing_edge is not None:
            x2, y2 = self.canvas_xy(event)
            x1, y1, _, _ = self.coords(self.drawing_edge.id)
            self.coords(self.drawing_edge.id, x1, y1, x2, y2)

    def context(self, event):
        selected = self.get_selected(event)
        nodes = self.find_withtag("node")
        if selected in nodes:
            print(f"node context: {selected}")
            self.node_context.post(event.x_root, event.y_root)

    def set_mode(self, event):
        print(f"mode event: {event}")
        if event.char == "e":
            self.mode = GraphMode.EDGE
        elif event.char == "s":
            self.mode = GraphMode.SELECT
        elif event.char == "n":
            self.mode = GraphMode.NODE
        print(f"graph mode: {self.mode}")

    def add_node(self, x, y, name, image_name):
        image = self.images[image_name]
        node = CanvasNode(x, y, name, image, self)
        self.nodes[node.id] = node
        return node


class CanvasEdge:
    width = 3

    def __init__(self, x1, y1, x2, y2, src, canvas):
        self.src = src
        self.dst = None
        self.canvas = canvas
        self.id = self.canvas.create_line(x1, y1, x2, y2, tags="edge", width=self.width)
        self.token = None
        self.canvas.tag_lower(self.id)

    def complete(self, dst, x, y):
        self.dst = dst
        self.token = tuple(sorted((self.src, self.dst)))
        x1, y1, _, _ = self.canvas.coords(self.id)
        self.canvas.coords(self.id, x1, y1, x, y)

    def delete(self):
        self.canvas.delete(self.id)


class CanvasNode:
    def __init__(self, x, y, name, image, canvas):
        self.name = name
        self.image = image
        self.canvas = canvas
        self.id = self.canvas.create_image(
            x, y, anchor=tk.CENTER, image=self.image, tags="node"
        )
        self.text_id = self.canvas.create_text(x, y + 20, text=self.name)
        self.canvas.tag_bind(self.id, "<ButtonPress-1>", self.click_press)
        self.canvas.tag_bind(self.id, "<ButtonRelease-1>", self.click_release)
        self.canvas.tag_bind(self.id, "<B1-Motion>", self.motion)
        self.canvas.tag_bind(self.id, "<Button-3>", self.context)
        self.edges = set()
        self.moving = None

    def click_press(self, event):
        print(f"click press {self.name}: {event}")
        self.moving = self.canvas.canvas_xy(event)

    def click_release(self, event):
        print(f"click release {self.name}: {event}")
        self.moving = None

    def motion(self, event):
        if self.canvas.mode == GraphMode.EDGE:
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
        print(f"context click {self.name}: {event}")
