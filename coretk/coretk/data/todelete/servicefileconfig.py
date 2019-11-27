"""
service file configuration
"""


class ServiceFileConfig:
    def __init__(self):
        # dict(node_id:dict(service:dict(filename, data)))
        self.configurations = {}

    # def set_service_configs(self, node_id, service_name, file_configs):
    #     """
    #     store file configs
    #
    #     :param int node_id: node id
    #     :param str service_name: service name
    #     :param dict(str, str) file_configs: map of service file to its data
    #     :return: nothing
    #     """
    #     for key, value in file_configs.items():
    #         self.configurations[node_id][service_name][key] = value

    def set_custom_service_file_config(self, node_id, service_name, file_name, data):
        """
        store file config

        :param int node_id: node id
        :param str service_name: service name
        :param str file_name: file name
        :param str data: data
        :return: nothing
        """
        if node_id not in self.configurations:
            self.configurations[node_id] = {}
        if service_name not in self.configurations[node_id]:
            self.configurations[node_id][service_name] = {}
        self.configurations[node_id][service_name][file_name] = data
