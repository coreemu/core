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
        edges = set()
        node_ids = []
        for node_id in list(self.selected):
            bbox_id = self.selected[node_id]
            canvas_node = self.canvas.nodes.pop(node_id)
            node_ids.append(canvas_node.core_node.id)
            self.canvas.delete(node_id)
            self.canvas.delete(bbox_id)
            self.canvas.delete(canvas_node.text_id)
            for edge in canvas_node.edges:
                if edge in edges:
                    continue
                edges.add(edge)
                self.canvas.edges.pop(edge.token)
                self.canvas.delete(edge.id)
                self.canvas.delete(edge.link_info.id1)
                self.canvas.delete(edge.link_info.id2)
                other_id = edge.src
                other_interface = edge.src_interface
                if edge.src == node_id:
                    other_id = edge.dst
                    other_interface = edge.dst_interface
                other_node = self.canvas.nodes[other_id]
                other_node.edges.remove(edge)
                other_node.interfaces.remove(other_interface)
        self.selected.clear()
        return node_ids, edges
