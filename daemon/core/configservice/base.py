import abc
import enum
import inspect
import logging
import pathlib
import time
from typing import Any, Dict, List

from mako import exceptions
from mako.lookup import TemplateLookup
from mako.template import Template

from core.config import Configuration
from core.errors import CoreCommandError, CoreError
from core.nodes.base import CoreNode

TEMPLATES_DIR = "templates"


class ConfigServiceMode(enum.Enum):
    BLOCKING = 0
    NON_BLOCKING = 1
    TIMER = 2


class ConfigServiceBootError(Exception):
    pass


class ConfigService(abc.ABC):
    # validation period in seconds, how frequent validation is attempted
    validation_period = 0.5

    # time to wait in seconds for determining if service started successfully
    validation_timer = 5

    def __init__(self, node: CoreNode) -> None:
        self.node = node
        class_file = inspect.getfile(self.__class__)
        templates_path = pathlib.Path(class_file).parent.joinpath(TEMPLATES_DIR)
        self.templates = TemplateLookup(directories=templates_path)
        self.config = {}
        self.custom_templates = {}
        self.custom_config = {}
        configs = self.default_configs[:]
        self._define_config(configs)

    @staticmethod
    def clean_text(text: str) -> str:
        return inspect.cleandoc(text)

    @property
    @abc.abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def group(self) -> str:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def directories(self) -> List[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def files(self) -> List[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def default_configs(self) -> List[Configuration]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def modes(self) -> Dict[str, Dict[str, str]]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def executables(self) -> List[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def dependencies(self) -> List[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def startup(self) -> List[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def validate(self) -> List[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def shutdown(self) -> List[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def validation_mode(self) -> ConfigServiceMode:
        raise NotImplementedError

    def start(self) -> None:
        logging.info("node(%s) service(%s) starting...", self.node.name, self.name)
        self.create_dirs()
        self.create_files()
        wait = self.validation_mode == ConfigServiceMode.BLOCKING
        self.run_startup(wait)
        if not wait:
            if self.validation_mode == ConfigServiceMode.TIMER:
                time.sleep(self.validation_timer)
            else:
                self.run_validation()

    def stop(self) -> None:
        for cmd in self.shutdown:
            try:
                self.node.cmd(cmd)
            except CoreCommandError:
                logging.exception(
                    f"node({self.node.name}) service({self.name}) "
                    f"failed shutdown: {cmd}"
                )

    def restart(self) -> None:
        self.stop()
        self.start()

    def create_dirs(self) -> None:
        for directory in self.directories:
            try:
                self.node.privatedir(directory)
            except (CoreCommandError, ValueError):
                raise CoreError(
                    f"node({self.node.name}) service({self.name}) "
                    f"failure to create service directory: {directory}"
                )

    def data(self) -> Dict[str, Any]:
        return {}

    def set_template(self, name: str, template: str) -> None:
        self.custom_templates[name] = template

    def get_text_template(self, name: str) -> str:
        raise CoreError(f"service({self.name}) unknown template({name})")

    def get_templates(self) -> Dict[str, str]:
        templates = {}
        for name in self.files:
            basename = pathlib.Path(name).name
            if name in self.custom_templates:
                template = self.custom_templates[name]
                template = self.clean_text(template)
            elif self.templates.has_template(basename):
                template = self.templates.get_template(basename).source
            else:
                template = self.get_text_template(name)
                template = self.clean_text(template)
            templates[name] = template
        return templates

    def create_files(self) -> None:
        data = self.data()
        for name in self.files:
            basename = pathlib.Path(name).name
            if name in self.custom_templates:
                text = self.custom_templates[name]
                rendered = self.render_text(text, data)
            elif self.templates.has_template(basename):
                rendered = self.render_template(basename, data)
            else:
                text = self.get_text_template(name)
                rendered = self.render_text(text, data)
            logging.debug(
                "node(%s) service(%s) template(%s): \n%s",
                self.node.name,
                self.name,
                name,
                rendered,
            )
            self.node.nodefile(name, rendered)

    def run_startup(self, wait: bool) -> None:
        for cmd in self.startup:
            try:
                self.node.cmd(cmd, wait=wait)
            except CoreCommandError as e:
                raise ConfigServiceBootError(
                    f"node({self.node.name}) service({self.name}) failed startup: {e}"
                )

    def run_validation(self) -> None:
        start = time.monotonic()
        cmds = self.validate[:]
        index = 0
        while cmds:
            cmd = cmds[index]
            try:
                self.node.cmd(cmd)
                del cmds[index]
                index += 1
            except CoreCommandError:
                logging.debug(
                    f"node({self.node.name}) service({self.name}) "
                    f"validate command failed: {cmd}"
                )
                time.sleep(self.validation_period)

            if cmds and time.monotonic() - start > 0:
                raise ConfigServiceBootError(
                    f"node({self.node.name}) service({self.name}) failed to validate"
                )

    def _render(self, template: Template, data: Dict[str, Any] = None) -> str:
        if data is None:
            data = {}
        return template.render_unicode(
            node=self.node, config=self.render_config(), **data
        )

    def render_text(self, text: str, data: Dict[str, Any] = None) -> str:
        text = self.clean_text(text)
        try:
            template = Template(text)
            return self._render(template, data)
        except Exception:
            raise CoreError(
                f"node({self.node.name}) service({self.name}) "
                f"{exceptions.text_error_template().render_unicode()}"
            )

    def render_template(self, basename: str, data: Dict[str, Any] = None) -> str:
        try:
            template = self.templates.get_template(basename)
            return self._render(template, data)
        except Exception:
            raise CoreError(
                f"node({self.node.name}) service({self.name}) "
                f"{exceptions.text_error_template().render_template()}"
            )

    def _define_config(self, configs: List[Configuration]) -> None:
        for config in configs:
            self.config[config.id] = config

    def render_config(self) -> Dict[str, str]:
        if self.custom_config:
            return self.custom_config
        else:
            return {k: v.default for k, v in self.config.items()}

    def set_config(self, data: Dict[str, str]) -> None:
        for key, value in data.items():
            if key not in self.config:
                raise CoreError(f"unknown config: {key}")
            self.custom_config[key] = value
