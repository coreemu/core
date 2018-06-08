from core.conf import NewConfigurableManager, ConfigurableOptions, Configuration
from core.enumerations import ConfigDataTypes


class TestConfigurableOptions(ConfigurableOptions):
    name_one = "value1"
    name_two = "value2"

    @classmethod
    def configurations(cls):
        return [
            Configuration(_id=TestConfigurableOptions.name_one, _type=ConfigDataTypes.STRING, label="value1"),
            Configuration(_id=TestConfigurableOptions.name_two, _type=ConfigDataTypes.STRING, label="value2")
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
        config_manager = NewConfigurableManager()
        test_config = {1: 2}
        node_id = 1
        config_manager.set_configs(test_config)
        config_manager.set_configs(test_config, node_id=node_id)

        # when
        nodes = config_manager.nodes()

        # then
        assert len(nodes) == 1
        assert nodes[0] == node_id

    def test_config_reset_all(self):
        # given
        config_manager = NewConfigurableManager()
        test_config = {1: 2}
        node_id = 1
        config_manager.set_configs(test_config)
        config_manager.set_configs(test_config, node_id=node_id)

        # when
        config_manager.config_reset()

        # then
        assert not config_manager._configuration_maps

    def test_config_reset_node(self):
        # given
        config_manager = NewConfigurableManager()
        test_config = {1: 2}
        node_id = 1
        config_manager.set_configs(test_config)
        config_manager.set_configs(test_config, node_id=node_id)

        # when
        config_manager.config_reset(node_id)

        # then
        assert not config_manager.get_configs(node_id)

    def test_configs_setget(self):
        # given
        config_manager = NewConfigurableManager()
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
        config_manager = NewConfigurableManager()
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

    def test_all_configs(self):
        # given
        config_manager = NewConfigurableManager()
        name = "test"
        value_one = "1"
        value_two = "2"
        node_id = 1
        config_one = "config1"
        config_two = "config2"
        config_manager.set_config(name, value_one, config_type=config_one)
        config_manager.set_config(name, value_two, config_type=config_two)
        config_manager.set_config(name, value_one, node_id=node_id, config_type=config_one)
        config_manager.set_config(name, value_two, node_id=node_id, config_type=config_two)

        # when
        defaults_value_one = config_manager.get_config(name, config_type=config_one)
        defaults_value_two = config_manager.get_config(name, config_type=config_two)
        node_value_one = config_manager.get_config(name, node_id=node_id, config_type=config_one)
        node_value_two = config_manager.get_config(name, node_id=node_id, config_type=config_two)
        default_all_configs = config_manager.get_config_types()
        node_all_configs = config_manager.get_config_types(node_id=node_id)

        # then
        assert defaults_value_one == value_one
        assert defaults_value_two == value_two
        assert node_value_one == value_one
        assert node_value_two == value_two
        assert len(default_all_configs) == 2
        assert config_one in default_all_configs
        assert config_two in default_all_configs
        assert len(node_all_configs) == 2
        assert config_one in node_all_configs
        assert config_two in node_all_configs
