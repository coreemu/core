"""
CoreToolbar help to draw on canvas, and make grpc client call
"""
from core.api.grpc.client import core_pb2


class ToolbarHelper:
    def __init__(self, app):
        self.app = app

    def get_node_list(self):
        """
        form a list node protobuf nodes to pass in start_session in grpc

        :return: nothing
        """
        nodes = []
        for node in self.app.core.nodes.values():
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
        links = []
        for edge in self.app.core.edges.values():
            interface_one = self.app.core.create_interface(edge.type1, edge.interface_1)
            interface_two = self.app.core.create_interface(edge.type2, edge.interface_2)
            link = core_pb2.Link(
                node_one_id=edge.id1,
                node_two_id=edge.id2,
                type=core_pb2.LinkType.WIRED,
                interface_one=interface_one,
                interface_two=interface_two,
            )
            links.append(link)

        return links

    def get_wlan_configuration_list(self):
        """
        form a list of wlan configuration to pass to start_session

        :return: nothing
        """
        configs = []
        manager_configs = self.app.core.wlanconfig_management.configurations
        for key in manager_configs:
            cnf = core_pb2.WlanConfig(node_id=key, config=manager_configs[key])
            configs.append(cnf)
        return configs

    def get_mobility_configuration_list(self):
        """
        form a list of mobility configuration to pass to start_session

        :return: nothing
        """
        configs = []
        core = self.app.canvas.core
        manager_configs = core.mobilityconfig_management.configurations
        for key in manager_configs:
            cnf = core_pb2.MobilityConfig(node_id=key, config=manager_configs[key])
            configs.append(cnf)
        return configs

    def get_emane_configuration_list(self):
        """
        form a list of emane configuration for the nodes

        :return: nothing
        """
        configs = []
        manager_configs = self.app.core.emaneconfig_management.configurations
        for key, value in manager_configs.items():
            config = {x: value[1][x].value for x in value[1]}
            configs.append(
                core_pb2.EmaneModelConfig(
                    node_id=key[0], interface_id=key[1], model=value[0], config=config
                )
            )
        return configs

    def gui_start_session(self):
        nodes = self.get_node_list()
        links = self.get_link_list()
        wlan_configs = self.get_wlan_configuration_list()
        mobility_configs = self.get_mobility_configuration_list()

        # get emane config (global configuration)
        pb_emane_config = self.app.core.emane_config
        emane_config = {x: pb_emane_config[x].value for x in pb_emane_config}

        # get emane configuration list
        emane_model_configs = self.get_emane_configuration_list()

        self.app.core.start_session(
            nodes,
            links,
            wlan_configs=wlan_configs,
            mobility_configs=mobility_configs,
            emane_config=emane_config,
            emane_model_configs=emane_model_configs,
        )
