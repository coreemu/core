"""
CoreToolbar help to draw on canvas, and make grpc client call
"""


class CoreToolbarHelp:
    def __init__(self, app):
        self.app = app

    def add_nodes(self):
        """
        add the nodes stored in grpc manager
        :return: nothing
        """
        manager = self.app.core_grpc.manager
        for node in manager.nodes.values():
            self.app.core_grpc.add_node(
                node.type, node.model, int(node.x), int(node.y), node.name, node.node_id
            )

    def add_edges(self):
        """
        add the edges stored in grpc manager
        :return:
        """
        manager = self.app.core_grpc.manager
        for edge in manager.edges.values():
            self.app.core_grpc.add_link(
                edge.id1, edge.id2, edge.type1, edge.type2, edge
            )
