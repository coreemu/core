"""
CoreToolbar help to draw on canvas, and make grpc client call
"""
from core.api.grpc.client import core_pb2


class CoreToolbarHelp:
    def __init__(self, application):
        self.application = application
        self.core_grpc = application.core_grpc

    def get_node_list(self):
        """
        form a list node protobuf nodes to pass in start_session in grpc

        :return: nothing
        """
        grpc_manager = self.application.canvas.grpc_manager

        # list(core_pb2.Node)
        nodes = []

        for node in grpc_manager.nodes.values():
            pos = core_pb2.Position(x=int(node.x), y=int(node.y))
            n = core_pb2.Node(
                id=node.node_id, type=node.type, position=pos, model=node.model
            )
            nodes.append(n)
        return nodes

    def get_link_list(self):
        """
        form a list of links to pass into grpc start session

        :rtype: list(core_pb2.Link)
        :return: list of protobuf links
        """
        grpc_manager = self.application.canvas.grpc_manager

        # list(core_bp2.Link)
        links = []
        for edge in grpc_manager.edges.values():
            interface_one = self.application.core_grpc.create_interface(
                edge.type1, edge.interface_1
            )
            interface_two = self.application.core_grpc.create_interface(
                edge.type2, edge.interface_2
            )
            # TODO for now only consider the basic cases
            if (
                edge.type1 == core_pb2.NodeType.WIRELESS_LAN
                or edge.type2 == core_pb2.NodeType.WIRELESS_LAN
            ):
                link_type = core_pb2.LinkType.WIRELESS
            else:
                link_type = core_pb2.LinkType.WIRED
            link = core_pb2.Link(
                node_one_id=edge.id1,
                node_two_id=edge.id2,
                type=link_type,
                interface_one=interface_one,
                interface_two=interface_two,
            )
            links.append(link)
            # self.id1 = edge.id1
            # self.id2 = edge.id2
            # self.type = link_type
            # self.if1 = interface_one
            # self.if2 = interface_two

        return links

    def get_wlan_configuration_list(self):
        configs = []
        grpc_manager = self.application.canvas.grpc_manager
        manager_configs = grpc_manager.wlanconfig_management.configurations
        for key in manager_configs:
            cnf = core_pb2.WlanConfig(node_id=key, config=manager_configs[key])
            configs.append(cnf)
        return configs

    def gui_start_session(self):
        # list(core_pb2.Node)
        nodes = self.get_node_list()

        # list(core_bp2.Link)
        links = self.get_link_list()

        # print(links[0])
        wlan_configs = self.get_wlan_configuration_list()
        # print(wlan_configs)
        self.core_grpc.start_session(nodes, links, wlan_configs=wlan_configs)
        # self.core_grpc.core.add_link(self.core_grpc.session_id, self.id1, self.id2, self.if1, self.if2)
        # res = self.core_grpc.core.get_wlan_config(self.core_grpc.session_id, 1)

        # res = self.core_grpc.core.get_session(self.core_grpc.session_id).session
        # print(res)
        # res = self.core_grpc.core.get_wlan_config(self.core_grpc.session_id, 1)

        # print(res)

    # def add_nodes(self):
    #     """
    #     add the nodes stored in grpc manager
    #     :return: nothing
    #     """
    #     grpc_manager = self.application.canvas.grpc_manager
    #     for node in grpc_manager.nodes.values():
    #         self.application.core_grpc.add_node(
    #             node.type, node.model, int(node.x), int(node.y), node.name, node.node_id
    #         )
    #
    # def add_edges(self):
    #     """
    #     add the edges stored in grpc manager
    #     :return:
    #     """
    #     grpc_manager = self.application.canvas.grpc_manager
    #     for edge in grpc_manager.edges.values():
    #         self.application.core_grpc.add_link(
    #             edge.id1, edge.id2, edge.type1, edge.type2, edge
    #         )
