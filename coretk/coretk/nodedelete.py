"""
manage deletion
"""


class CanvasComponentManagement:
    def __init__(self, canvas, core):
        self.app = core
        self.canvas = canvas

        # dictionary that maps node to box
        self.selected = {}

    def node_select(self, canvas_node, choose_multiple=False):
        """
        create a bounding box when a node is selected

        :param coretk.graph.CanvasNode canvas_node: canvas node object
        :return: nothing
        """

        if not choose_multiple:
            self.delete_current_bbox()

        # draw a bounding box if node hasn't been selected yet
        if canvas_node.id not in self.selected:
            x0, y0, x1, y1 = self.canvas.bbox(canvas_node.id)
            bbox_id = self.canvas.create_rectangle(
                (x0 - 6, y0 - 6, x1 + 6, y1 + 6), activedash=True, dash="-"
            )
            self.selected[canvas_node.id] = bbox_id

    def node_drag(self, canvas_node, offset_x, offset_y):
        self.canvas.move(self.selected[canvas_node.id], offset_x, offset_y)

    def delete_current_bbox(self):
        for bbid in self.selected.values():
            self.canvas.delete(bbid)
        self.selected.clear()

    def delete_selected_nodes(self):
        selected_nodes = list(self.selected.keys())
        edges = set()
        for n in selected_nodes:
            edges = edges.union(self.canvas.nodes[n].edges)
        edge_canvas_ids = [x.id for x in edges]
        edge_tokens = [x.token for x in edges]
        link_infos = [x.link_info.id1 for x in edges] + [x.link_info.id2 for x in edges]

        for i in edge_canvas_ids:
            self.canvas.itemconfig(i, state="hidden")

        for i in link_infos:
            self.canvas.itemconfig(i, state="hidden")

        for cnid, bbid in self.selected.items():
            self.canvas.itemconfig(cnid, state="hidden")
            self.canvas.itemconfig(bbid, state="hidden")
            self.canvas.itemconfig(self.canvas.nodes[cnid].text_id, state="hidden")
        self.selected.clear()
        return selected_nodes, edge_tokens
