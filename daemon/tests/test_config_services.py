from pathlib import Path
from unittest import mock

import pytest

from core.config import ConfigBool, ConfigString
from core.configservice.base import (
    ConfigService,
    ConfigServiceBootError,
    ConfigServiceMode,
)
from core.errors import CoreCommandError, CoreError

TEMPLATE_TEXT = "echo hello"


class MyService(ConfigService):
    name = "MyService"
    group = "MyGroup"
    directories = ["/usr/local/lib"]
    files = ["test.sh"]
    executables = []
    dependencies = []
    startup = [f"sh {files[0]}"]
    validate = [f"pidof {files[0]}"]
    shutdown = [f"pkill {files[0]}"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = [
        ConfigString(id="value1", label="Text"),
        ConfigBool(id="value2", label="Boolean"),
        ConfigString(
            id="value3", label="Multiple Choice", options=["value1", "value2", "value3"]
        ),
    ]
    modes = {
        "mode1": {"value1": "value1", "value2": "0", "value3": "value2"},
        "mode2": {"value1": "value2", "value2": "1", "value3": "value3"},
        "mode3": {"value1": "value3", "value2": "0", "value3": "value1"},
    }

    def get_text_template(self, name: str) -> str:
        return TEMPLATE_TEXT


class TestConfigServices:
    def test_set_template(self):
        # given
        node = mock.MagicMock()
        text = "echo custom"
        service = MyService(node)

        # when
        service.set_template(MyService.files[0], text)

        # then
        assert MyService.files[0] in service.custom_templates
        assert service.custom_templates[MyService.files[0]] == text

    def test_create_directories(self):
        # given
        node = mock.MagicMock()
        service = MyService(node)

        # when
        service.create_dirs()

        # then
        directory = Path(MyService.directories[0])
        node.create_dir.assert_called_with(directory)

    def test_create_files_custom(self):
        # given
        node = mock.MagicMock()
        service = MyService(node)
        text = "echo custom"
        service.set_template(MyService.files[0], text)

        # when
        service.create_files()

        # then
        file_path = Path(MyService.files[0])
        node.create_file.assert_called_with(file_path, text)

    def test_create_files_text(self):
        # given
        node = mock.MagicMock()
        service = MyService(node)

        # when
        service.create_files()

        # then
        file_path = Path(MyService.files[0])
        node.create_file.assert_called_with(file_path, TEMPLATE_TEXT)

    def test_run_startup(self):
        # given
        node = mock.MagicMock()
        wait = True
        service = MyService(node)

        # when
        service.run_startup(wait=wait)

        # then
        node.cmd.assert_called_with(MyService.startup[0], wait=wait)

    def test_run_startup_exception(self):
        # given
        node = mock.MagicMock()
        node.cmd.side_effect = CoreCommandError(1, "error")
        service = MyService(node)

        # when
        with pytest.raises(ConfigServiceBootError):
            service.run_startup(wait=True)

    def test_shutdown(self):
        # given
        node = mock.MagicMock()
        service = MyService(node)

        # when
        service.stop()

        # then
        node.cmd.assert_called_with(MyService.shutdown[0])

    def test_run_validation(self):
        # given
        node = mock.MagicMock()
        service = MyService(node)

        # when
        service.run_validation()

        # then
        node.cmd.assert_called_with(MyService.validate[0])

    def test_run_validation_timer(self):
        # given
        node = mock.MagicMock()
        service = MyService(node)
        service.validation_mode = ConfigServiceMode.TIMER
        service.validation_timer = 0

        # when
        service.run_validation()

        # then
        node.cmd.assert_called_with(MyService.validate[0])

    def test_run_validation_timer_exception(self):
        # given
        node = mock.MagicMock()
        node.cmd.side_effect = CoreCommandError(1, "error")
        service = MyService(node)
        service.validation_mode = ConfigServiceMode.TIMER
        service.validation_period = 0
        service.validation_timer = 0

        # when
        with pytest.raises(ConfigServiceBootError):
            service.run_validation()

    def test_run_validation_non_blocking(self):
        # given
        node = mock.MagicMock()
        service = MyService(node)
        service.validation_mode = ConfigServiceMode.NON_BLOCKING
        service.validation_period = 0
        service.validation_timer = 0

        # when
        service.run_validation()

        # then
        node.cmd.assert_called_with(MyService.validate[0])

    def test_run_validation_non_blocking_exception(self):
        # given
        node = mock.MagicMock()
        node.cmd.side_effect = CoreCommandError(1, "error")
        service = MyService(node)
        service.validation_mode = ConfigServiceMode.NON_BLOCKING
        service.validation_period = 0
        service.validation_timer = 0

        # when
        with pytest.raises(ConfigServiceBootError):
            service.run_validation()

    def test_render_config(self):
        # given
        node = mock.MagicMock()
        service = MyService(node)

        # when
        config = service.render_config()

        # then
        assert config == {"value1": "", "value2": "", "value3": ""}

    def test_render_config_custom(self):
        # given
        node = mock.MagicMock()
        service = MyService(node)
        custom_config = {"value1": "1", "value2": "2", "value3": "3"}
        service.set_config(custom_config)

        # when
        config = service.render_config()

        # then
        assert config == custom_config

    def test_set_config(self):
        # given
        node = mock.MagicMock()
        service = MyService(node)
        custom_config = {"value1": "1", "value2": "2", "value3": "3"}

        # when
        service.set_config(custom_config)

        # then
        assert service.custom_config == custom_config

    def test_set_config_exception(self):
        # given
        node = mock.MagicMock()
        service = MyService(node)
        custom_config = {"value4": "1"}

        # when
        with pytest.raises(CoreError):
            service.set_config(custom_config)

    def test_start_blocking(self):
        # given
        node = mock.MagicMock()
        service = MyService(node)
        service.create_dirs = mock.MagicMock()
        service.create_files = mock.MagicMock()
        service.run_startup = mock.MagicMock()
        service.run_validation = mock.MagicMock()
        service.wait_validation = mock.MagicMock()

        # when
        service.start()

        # then
        service.create_files.assert_called_once()
        service.create_dirs.assert_called_once()
        service.run_startup.assert_called_once()
        service.run_validation.assert_not_called()
        service.wait_validation.assert_not_called()

    def test_start_timer(self):
        # given
        node = mock.MagicMock()
        service = MyService(node)
        service.validation_mode = ConfigServiceMode.TIMER
        service.create_dirs = mock.MagicMock()
        service.create_files = mock.MagicMock()
        service.run_startup = mock.MagicMock()
        service.run_validation = mock.MagicMock()
        service.wait_validation = mock.MagicMock()

        # when
        service.start()

        # then
        service.create_files.assert_called_once()
        service.create_dirs.assert_called_once()
        service.run_startup.assert_called_once()
        service.run_validation.assert_not_called()
        service.wait_validation.assert_called_once()

    def test_start_non_blocking(self):
        # given
        node = mock.MagicMock()
        service = MyService(node)
        service.validation_mode = ConfigServiceMode.NON_BLOCKING
        service.create_dirs = mock.MagicMock()
        service.create_files = mock.MagicMock()
        service.run_startup = mock.MagicMock()
        service.run_validation = mock.MagicMock()
        service.wait_validation = mock.MagicMock()

        # when
        service.start()

        # then
        service.create_files.assert_called_once()
        service.create_dirs.assert_called_once()
        service.run_startup.assert_called_once()
        service.run_validation.assert_called_once()
        service.wait_validation.assert_not_called()
