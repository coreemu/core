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

TEMPLATES_DIR: str = "templates"


class ConfigServiceMode(enum.Enum):
    BLOCKING = 0
    NON_BLOCKING = 1
    TIMER = 2


class ConfigServiceBootError(Exception):
    pass


class ConfigService(abc.ABC):
    """
    Base class for creating configurable services.
    """

    # validation period in seconds, how frequent validation is attempted
    validation_period: float = 0.5

    # time to wait in seconds for determining if service started successfully
    validation_timer: int = 5

    def __init__(self, node: CoreNode) -> None:
        """
        Create ConfigService instance.

        :param node: node this service is assigned to
        """
        self.node: CoreNode = node
        class_file = inspect.getfile(self.__class__)
        templates_path = pathlib.Path(class_file).parent.joinpath(TEMPLATES_DIR)
        self.templates: TemplateLookup = TemplateLookup(directories=templates_path)
        self.config: Dict[str, Configuration] = {}
        self.custom_templates: Dict[str, str] = {}
        self.custom_config: Dict[str, str] = {}
        configs = self.default_configs[:]
        self._define_config(configs)

    @staticmethod
    def clean_text(text: str) -> str:
        """
        Returns space stripped text for string literals, while keeping space
        indentations.

        :param text: text to clean
        :return: cleaned text
        """
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
        """
        Creates services files/directories, runs startup, and validates based on
        validation mode.

        :return: nothing
        :raises ConfigServiceBootError: when there is an error starting service
        """
        logging.info("node(%s) service(%s) starting...", self.node.name, self.name)
        self.create_dirs()
        self.create_files()
        wait = self.validation_mode == ConfigServiceMode.BLOCKING
        self.run_startup(wait)
        if not wait:
            if self.validation_mode == ConfigServiceMode.TIMER:
                self.wait_validation()
            else:
                self.run_validation()

    def stop(self) -> None:
        """
        Stop service using shutdown commands.

        :return: nothing
        """
        for cmd in self.shutdown:
            try:
                self.node.cmd(cmd)
            except CoreCommandError:
                logging.exception(
                    f"node({self.node.name}) service({self.name}) "
                    f"failed shutdown: {cmd}"
                )

    def restart(self) -> None:
        """
        Restarts service by running stop and then start.

        :return: nothing
        """
        self.stop()
        self.start()

    def create_dirs(self) -> None:
        """
        Creates directories for service.

        :return: nothing
        :raises CoreError: when there is a failure creating a directory
        """
        for directory in self.directories:
            try:
                self.node.privatedir(directory)
            except (CoreCommandError, ValueError):
                raise CoreError(
                    f"node({self.node.name}) service({self.name}) "
                    f"failure to create service directory: {directory}"
                )

    def data(self) -> Dict[str, Any]:
        """
        Returns key/value data, used when rendering file templates.

        :return: key/value template data
        """
        return {}

    def set_template(self, name: str, template: str) -> None:
        """
        Store custom template to render for a given file.

        :param name: file to store custom template for
        :param template: custom template to render
        :return: nothing
        """
        self.custom_templates[name] = template

    def get_text_template(self, name: str) -> str:
        """
        Retrieves text based template for files that do not have a file based template.

        :param name: name of file to get template for
        :return: template to render
        """
        raise CoreError(f"service({self.name}) unknown template({name})")

    def get_templates(self) -> Dict[str, str]:
        """
        Retrieves mapping of file names to templates for all cases, which
        includes custom templates, file templates, and text templates.

        :return: mapping of files to templates
        """
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
        """
        Creates service files inside associated node.

        :return: nothing
        """
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
        """
        Run startup commands for service on node.

        :param wait: wait successful command exit status when True, ignore status
            otherwise
        :return: nothing
        :raises ConfigServiceBootError: when a command that waits fails
        """
        for cmd in self.startup:
            try:
                self.node.cmd(cmd, wait=wait)
            except CoreCommandError as e:
                raise ConfigServiceBootError(
                    f"node({self.node.name}) service({self.name}) failed startup: {e}"
                )

    def wait_validation(self) -> None:
        """
        Waits for a period of time to consider service started successfully.

        :return: nothing
        """
        time.sleep(self.validation_timer)

    def run_validation(self) -> None:
        """
        Runs validation commands for service on node.

        :return: nothing
        :raises ConfigServiceBootError: if there is a validation failure
        """
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

            if cmds and time.monotonic() - start > self.validation_timer:
                raise ConfigServiceBootError(
                    f"node({self.node.name}) service({self.name}) failed to validate"
                )

    def _render(self, template: Template, data: Dict[str, Any] = None) -> str:
        """
        Renders template providing all associated data to template.

        :param template: template to render
        :param data: service specific defined data for template
        :return: rendered template
        """
        if data is None:
            data = {}
        return template.render_unicode(
            node=self.node, config=self.render_config(), **data
        )

    def render_text(self, text: str, data: Dict[str, Any] = None) -> str:
        """
        Renders text based template providing all associated data to template.

        :param text: text to render
        :param data: service specific defined data for template
        :return: rendered template
        """
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
        """
        Renders file based template  providing all associated data to template.

        :param basename:  base name for file to render
        :param data: service specific defined data for template
        :return: rendered template
        """
        try:
            template = self.templates.get_template(basename)
            return self._render(template, data)
        except Exception:
            raise CoreError(
                f"node({self.node.name}) service({self.name}) "
                f"{exceptions.text_error_template().render_template()}"
            )

    def _define_config(self, configs: List[Configuration]) -> None:
        """
        Initializes default configuration data.

        :param configs: configs to initialize
        :return: nothing
        """
        for config in configs:
            self.config[config.id] = config

    def render_config(self) -> Dict[str, str]:
        """
        Returns configuration data key/value pairs for rendering a template.

        :return: nothing
        """
        if self.custom_config:
            return self.custom_config
        else:
            return {k: v.default for k, v in self.config.items()}

    def set_config(self, data: Dict[str, str]) -> None:
        """
        Set configuration data from key/value pairs.

        :param data: configuration key/values to set
        :return: nothing
        :raise CoreError: when an unknown configuration value is given
        """
        for key, value in data.items():
            if key not in self.config:
                raise CoreError(f"unknown config: {key}")
            self.custom_config[key] = value
