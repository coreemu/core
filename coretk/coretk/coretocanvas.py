"""
provide mapping from core to canvas
"""
import logging


class CoreToCanvasMapping:
    def __init__(self):
        self.core_id_to_canvas_id = {}
        self.core_node_and_interface_to_canvas_edge = {}
        # self.edge_id_to_canvas_token = {}

    def map_node_and_interface_to_canvas_edge(self, nid, iid, edge_token):
        self.core_node_and_interface_to_canvas_edge[tuple([nid, iid])] = edge_token

    def get_token_from_node_and_interface(self, nid, iid):
        key = tuple([nid, iid])
        if key in self.core_node_and_interface_to_canvas_edge:
            return self.core_node_and_interface_to_canvas_edge[key]
        else:
            logging.error("invalid key")
            return None

    def map_core_id_to_canvas_id(self, core_nid, canvas_nid):
        if core_nid not in self.core_id_to_canvas_id:
            self.core_id_to_canvas_id[core_nid] = canvas_nid
        else:
            logging.debug("key already existed")

    def get_canvas_id_from_core_id(self, core_id):
        if core_id in self.core_id_to_canvas_id:
            return self.core_id_to_canvas_id[core_id]
        else:
            logging.debug("invalid key")
            return None

    # def add_mapping(self, core_id, canvas_id):
    #     if core_id not in self.core_id_to_canvas_id:
    #         self.core_id_to_canvas_id[core_id] = canvas_id
    #     else:
    #         logging.error("key already mapped")
    #
    # def delete_mapping(self, core_id):
    #     result = self.core_id_to_canvas_id.pop(core_id, None)
    #     return result
