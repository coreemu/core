"""
CoreToolbar help to draw on canvas, and make grpc client call
"""


class CoreToolbarHelp:
    def __init__(self, application):
        self.application = application
        self.core_grpc = application.core_grpc

    def add_nodes(self):
        """
        add the nodes stored in grpc manager
        :return: nothing
        """
        grpc_manager = self.application.canvas.grpc_manager
        for node in grpc_manager.nodes.values():
            self.application.core_grpc.add_node(
                node.type, node.model, int(node.x), int(node.y), node.name, node.node_id
            )

    def add_edges(self):
        """
        add the edges stored in grpc manager
        :return:
        """
        grpc_manager = self.application.canvas.grpc_manager
        for edge in grpc_manager.edges.values():
            self.application.core_grpc.add_link(
                edge.id1, edge.id2, edge.type1, edge.type2, edge
            )
