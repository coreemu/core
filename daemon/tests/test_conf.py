from core.conf import ConfigurableOptions
from core.conf import Configuration
from core.enumerations import ConfigDataTypes


class TestConfigurableOptions(ConfigurableOptions):
    name_one = "value1"
    name_two = "value2"
    configuration_maps = {}

    @classmethod
    def configurations(cls):
        return [
            Configuration(
                _id=TestConfigurableOptions.name_one,
                _type=ConfigDataTypes.STRING,
                label=TestConfigurableOptions.name_one
            ),
            Configuration(
                _id=TestConfigurableOptions.name_two,
                _type=ConfigDataTypes.STRING,
                label=TestConfigurableOptions.name_two
            )
        ]


class TestConf:
    def test_configurable_options_default(self):
        # given
        configurable_options = TestConfigurableOptions()

        # when
        default_values = TestConfigurableOptions.default_values()
        instance_default_values = configurable_options.default_values()

        # then
        assert len(default_values) == 2
        assert TestConfigurableOptions.name_one in default_values
        assert TestConfigurableOptions.name_two in default_values
        assert len(instance_default_values) == 2
        assert TestConfigurableOptions.name_one in instance_default_values
        assert TestConfigurableOptions.name_two in instance_default_values

    def test_nodes(self):
        # given
        config_manager = TestConfigurableOptions()
        test_config = {1: 2}
        node_id = 1
        config_manager.set_configs(test_config)
        config_manager.set_configs(test_config, node_id=node_id)

        # when
        nodes = config_manager.nodes()

        # then
        assert len(nodes) == 1
        assert node_id in nodes

    def test_config_reset_all(self):
        # given
        config_manager = TestConfigurableOptions()
        test_config = {1: 2}
        node_id = 1
        config_manager.set_configs(test_config)
        config_manager.set_configs(test_config, node_id=node_id)

        # when
        config_manager.config_reset()

        # then
        assert not config_manager.configuration_maps

    def test_config_reset_node(self):
        # given
        config_manager = TestConfigurableOptions()
        test_config = {1: 2}
        node_id = 1
        config_manager.set_configs(test_config)
        config_manager.set_configs(test_config, node_id=node_id)

        # when
        config_manager.config_reset(node_id)

        # then
        assert node_id not in config_manager.configuration_maps
        assert config_manager.get_configs()

    def test_configs_setget(self):
        # given
        config_manager = TestConfigurableOptions()
        test_config = {1: 2}
        node_id = 1
        config_manager.set_configs(test_config)
        config_manager.set_configs(test_config, node_id=node_id)

        # when
        default_config = config_manager.get_configs()
        node_config = config_manager.get_configs(node_id)

        # then
        assert default_config
        assert node_config

    def test_config_setget(self):
        # given
        config_manager = TestConfigurableOptions()
        name = "test"
        value = "1"
        node_id = 1
        config_manager.set_config(name, value)
        config_manager.set_config(name, value, node_id=node_id)

        # when
        defaults_value = config_manager.get_config(name)
        node_value = config_manager.get_config(name, node_id=node_id)

        # then
        assert defaults_value == value
        assert node_value == value
