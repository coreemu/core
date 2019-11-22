"""
service node configuration
"""
import logging
from tkinter import messagebox

import grpc


class ServiceNodeConfig:
    def __init__(self, app):
        self.app = app
        # dict(node_id:dict(service:node_service_config_proto))
        # maps node to all of its service configuration
        self.configurations = {}
        # dict(node_id:set(str))
        # maps node to current configurations
        self.current_services = {}
        self.default_services = {}

    # todo rewrite, no need self.default services
    def node_default_services_configuration(self, node_id, node_model):
        """
        set the default configurations for the default services of a node

        :param coretk.graph.CanvasNode canvas_node: canvas node object
        :return: nothing
        """
        session_id = self.app.core.session_id
        client = self.app.core.client

        if len(self.default_services) == 0:
            response = client.get_service_defaults(session_id)
            logging.info("session default services: %s", response)
            for default in response.defaults:
                self.default_services[default.node_type] = default.services

        self.configurations[node_id] = {}

        self.current_services[node_id] = set()
        for default in self.default_services[node_model]:
            response = client.get_node_service(session_id, node_id, default)
            logging.info(
                "servicenodeconfig.py get node service (%s), result: %s",
                node_id,
                response,
            )
            self.configurations[node_id][default] = response.service
            self.current_services[node_id].add(default)

    def node_new_service_configuration(self, node_id, service_name):
        """
        store node's configuration if a new service is added from the GUI

        :param int node_id: node id
        :param str service_name: service name
        :return: nothing
        """
        try:
            config = self.app.core.get_node_service(node_id, service_name)
        except grpc.RpcError:
            messagebox.showerror("Service problem", "Service not found")
            return False
        if node_id not in self.configurations:
            self.configurations[node_id] = {}
        if node_id not in self.current_services:
            self.current_services[node_id] = set()
        if service_name not in self.configurations[node_id]:
            self.configurations[node_id][service_name] = config
        self.current_services[node_id].add(service_name)
        return True

    def node_custom_service_configuration(self, node_id, service_name):
        self.configurations[node_id][service_name] = self.app.core.get_node_service(
            node_id, service_name
        )

    def node_service_custom_configuration(
        self, node_id, service_name, startups, validates, shutdowns
    ):
        self.app.core.set_node_service(
            node_id, service_name, startups, validates, shutdowns
        )
        config = self.app.core.get_node_service(node_id, service_name)
        self.configurations[node_id][service_name] = config
