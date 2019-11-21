"""
emane model configurations
"""
import logging


class EmaneModelNodeConfig:
    def __init__(self, app):
        """
        create an instance for EmaneModelNodeConfig

        :param app: application
        """
        # dict(tuple(node_id, interface_id, model) : config)
        self.configurations = {}

        # dict(int, list(int)) stores emane node maps to mdr nodes that are linked to that emane node
        self.links = {}

        self.app = app

    def set_default_config(self, node_id):
        """
        set a default emane configuration for a newly created emane

        :param int node_id: node id
        :return: nothing
        """
        session_id = self.app.core.session_id
        client = self.app.core.client
        default_emane_model = self.app.core.emane_models[0]
        response = client.get_emane_model_config(
            session_id, node_id, default_emane_model
        )
        logging.info(
            "emanemodelnodeconfig.py get emane model config (%s), result: %s",
            node_id,
            response,
        )
        self.configurations[tuple([node_id, None])] = tuple(
            [default_emane_model, response.config]
        )
        self.links[node_id] = []

    def set_default_for_mdr(self, emane_node_id, mdr_node_id, interface_id):
        """
        set emane configuration of an mdr node on the correct interface

        :param int emane_node_id: emane node id
        :param int mdr_node_id: mdr node id
        :param int interface_id: interface id
        :return: nothing
        """
        self.configurations[tuple([mdr_node_id, interface_id])] = self.configurations[
            tuple([emane_node_id, None])
        ]
        self.links[emane_node_id].append(tuple([mdr_node_id, interface_id]))

    def set_custom_emane_cloud_config(self, emane_node_id, model_name):
        """
        set custom configuration for an emane node, if model is changed, update the nodes connected to that emane node

        :param int emane_node_id: emane node id
        :param str model_name: model name
        :return: nothing
        """
        prev_model_name = self.configurations[tuple([emane_node_id, None])][0]
        session_id = self.app.core.session_id
        response = self.app.core.client.get_emane_model_config(
            session_id, emane_node_id, model_name
        )
        self.configurations[tuple([emane_node_id, None])] = tuple(
            [model_name, response.config]
        )

        if prev_model_name != model_name:
            for k in self.links[emane_node_id]:
                self.configurations[k] = tuple([model_name, response.config])
