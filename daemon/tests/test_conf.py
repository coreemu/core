import pytest

from core.config import (
    ConfigString,
    ConfigurableManager,
    ConfigurableOptions,
    ModelManager,
)
from core.emane.models.ieee80211abg import EmaneIeee80211abgModel
from core.emulator.session import Session
from core.location.mobility import BasicRangeModel
from core.nodes.network import WlanNode


class TestConfigurableOptions(ConfigurableOptions):
    name1 = "value1"
    name2 = "value2"
    options = [ConfigString(id=name1, label=name1), ConfigString(id=name2, label=name2)]


class TestConf:
    def test_configurable_options_default(self):
        # given
        configurable_options = TestConfigurableOptions()

        # when
        default_values = TestConfigurableOptions.default_values()
        instance_default_values = configurable_options.default_values()

        # then
        assert len(default_values) == 2
        assert TestConfigurableOptions.name1 in default_values
        assert TestConfigurableOptions.name2 in default_values
        assert len(instance_default_values) == 2
        assert TestConfigurableOptions.name1 in instance_default_values
        assert TestConfigurableOptions.name2 in instance_default_values

    def test_nodes(self):
        # given
        config_manager = ConfigurableManager()
        test_config = {"1": "2"}
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
        config_manager = ConfigurableManager()
        test_config = {"1": "2"}
        node_id = 1
        config_manager.set_configs(test_config)
        config_manager.set_configs(test_config, node_id=node_id)

        # when
        config_manager.config_reset()

        # then
        assert not config_manager.node_configurations

    def test_config_reset_node(self):
        # given
        config_manager = ConfigurableManager()
        test_config = {"1": "2"}
        node_id = 1
        config_manager.set_configs(test_config)
        config_manager.set_configs(test_config, node_id=node_id)

        # when
        config_manager.config_reset(node_id)

        # then
        assert not config_manager.get_configs(node_id=node_id)
        assert config_manager.get_configs()

    def test_configs_setget(self):
        # given
        config_manager = ConfigurableManager()
        test_config = {"1": "2"}
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
        config_manager = ConfigurableManager()
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

    def test_model_setget_config(self):
        # given
        manager = ModelManager()
        manager.models[BasicRangeModel.name] = BasicRangeModel

        # when
        manager.set_model_config(1, BasicRangeModel.name)

        # then
        assert manager.get_model_config(1, BasicRangeModel.name)

    def test_model_set_config_error(self):
        # given
        manager = ModelManager()
        manager.models[BasicRangeModel.name] = BasicRangeModel
        bad_name = "bad-model"

        # when/then
        with pytest.raises(ValueError):
            manager.set_model_config(1, bad_name)

    def test_model_get_config_error(self):
        # given
        manager = ModelManager()
        manager.models[BasicRangeModel.name] = BasicRangeModel
        bad_name = "bad-model"

        # when/then
        with pytest.raises(ValueError):
            manager.get_model_config(1, bad_name)

    def test_model_set(self, session: Session):
        # given
        wlan_node = session.add_node(WlanNode)

        # when
        session.mobility.set_model(wlan_node, BasicRangeModel)

        # then
        assert session.mobility.get_model_config(wlan_node.id, BasicRangeModel.name)

    def test_model_set_error(self, session: Session):
        # given
        wlan_node = session.add_node(WlanNode)

        # when / then
        with pytest.raises(ValueError):
            session.mobility.set_model(wlan_node, EmaneIeee80211abgModel)

    def test_get_models(self, session: Session):
        # given
        wlan_node = session.add_node(WlanNode)
        session.mobility.set_model(wlan_node, BasicRangeModel)

        # when
        models = session.mobility.get_models(wlan_node)

        # then
        assert models
        assert len(models) == 1
