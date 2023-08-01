import abc
import enum
import inspect
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from mako import exceptions
from mako.lookup import TemplateLookup
from mako.template import Template

from core.config import Configuration
from core.errors import CoreCommandError, CoreError
from core.nodes.base import CoreNode

logger = logging.getLogger(__name__)
TEMPLATES_DIR: str = "templates"


def get_template_path(file_path: Path) -> str:
    """
    Utility to convert a given file path to a valid template path format.

    :param file_path: file path to convert
    :return: template path
    """
    if file_path.is_absolute():
        template_path = str(file_path.relative_to("/"))
    else:
        template_path = str(file_path)
    return template_path


class ConfigServiceMode(enum.Enum):
    BLOCKING = 0
    NON_BLOCKING = 1
    TIMER = 2


class ConfigServiceBootError(Exception):
    pass


class ConfigServiceTemplateError(Exception):
    pass


@dataclass
class ShadowDir:
    path: str
    src: Optional[str] = None
    templates: bool = False
    has_node_paths: bool = False


class ConfigService(abc.ABC):
    """
    Base class for creating configurable services.
    """

    # validation period in seconds, how frequent validation is attempted
    validation_period: float = 0.5

    # time to wait in seconds for determining if service started successfully
    validation_timer: int = 5

    # directories to shadow and copy files from
    shadow_directories: list[ShadowDir] = []

    def __init__(self, node: CoreNode) -> None:
        """
        Create ConfigService instance.

        :param node: node this service is assigned to
        """
        self.node: CoreNode = node
        class_file = inspect.getfile(self.__class__)
        templates_path = Path(class_file).parent.joinpath(TEMPLATES_DIR)
        self.templates: TemplateLookup = TemplateLookup(directories=templates_path)
        self.config: dict[str, Configuration] = {}
        self.custom_templates: dict[str, str] = {}
        self.custom_config: dict[str, str] = {}
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
    def directories(self) -> list[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def files(self) -> list[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def default_configs(self) -> list[Configuration]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def modes(self) -> dict[str, dict[str, str]]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def executables(self) -> list[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def dependencies(self) -> list[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def startup(self) -> list[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def validate(self) -> list[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def shutdown(self) -> list[str]:
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
        logger.info("node(%s) service(%s) starting...", self.node.name, self.name)
        self.create_shadow_dirs()
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
                logger.exception(
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

    def create_shadow_dirs(self) -> None:
        """
        Creates a shadow of a host system directory recursively
        to be mapped and live within a node.

        :return: nothing
        :raises CoreError: when there is a failure creating a directory or file
        """
        for shadow_dir in self.shadow_directories:
            # setup shadow and src paths, using node unique paths when configured
            shadow_path = Path(shadow_dir.path)
            if shadow_dir.src is None:
                src_path = shadow_path
            else:
                src_path = Path(shadow_dir.src)
            if shadow_dir.has_node_paths:
                src_path = src_path / self.node.name
            # validate shadow and src paths
            if not shadow_path.is_absolute():
                raise CoreError(f"shadow dir({shadow_path}) is not absolute")
            if not src_path.is_absolute():
                raise CoreError(f"shadow source dir({src_path}) is not absolute")
            if not src_path.is_dir():
                raise CoreError(f"shadow source dir({src_path}) does not exist")
            # create root of the shadow path within node
            logger.info(
                "node(%s) creating shadow directory(%s) src(%s) node paths(%s) "
                "templates(%s)",
                self.node.name,
                shadow_path,
                src_path,
                shadow_dir.has_node_paths,
                shadow_dir.templates,
            )
            self.node.create_dir(shadow_path)
            # find all directories and files to create
            dir_paths = []
            file_paths = []
            for path in src_path.rglob("*"):
                shadow_src_path = shadow_path / path.relative_to(src_path)
                if path.is_dir():
                    dir_paths.append(shadow_src_path)
                else:
                    file_paths.append((path, shadow_src_path))
            # create all directories within node
            for path in dir_paths:
                self.node.create_dir(path)
            # create all files within node, from templates when configured
            data = self.data()
            templates = TemplateLookup(directories=src_path)
            for path, dst_path in file_paths:
                if shadow_dir.templates:
                    template = templates.get_template(path.name)
                    rendered = self._render(template, data)
                    self.node.create_file(dst_path, rendered)
                else:
                    self.node.copy_file(path, dst_path)

    def create_dirs(self) -> None:
        """
        Creates directories for service.

        :return: nothing
        :raises CoreError: when there is a failure creating a directory
        """
        logger.debug("creating config service directories")
        for directory in sorted(self.directories):
            dir_path = Path(directory)
            try:
                self.node.create_dir(dir_path)
            except (CoreCommandError, CoreError):
                raise CoreError(
                    f"node({self.node.name}) service({self.name}) "
                    f"failure to create service directory: {directory}"
                )

    def data(self) -> dict[str, Any]:
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

    def get_templates(self) -> dict[str, str]:
        """
        Retrieves mapping of file names to templates for all cases, which
        includes custom templates, file templates, and text templates.

        :return: mapping of files to templates
        """
        templates = {}
        for file in self.files:
            file_path = Path(file)
            template_path = get_template_path(file_path)
            if file in self.custom_templates:
                template = self.custom_templates[file]
                template = self.clean_text(template)
            elif self.templates.has_template(template_path):
                template = self.templates.get_template(template_path).source
            else:
                try:
                    template = self.get_text_template(file)
                except Exception as e:
                    raise ConfigServiceTemplateError(
                        f"node({self.node.name}) service({self.name}) file({file}) "
                        f"failure getting template: {e}"
                    )
                template = self.clean_text(template)
            templates[file] = template
        return templates

    def get_rendered_templates(self) -> dict[str, str]:
        templates = {}
        data = self.data()
        for file in sorted(self.files):
            rendered = self._get_rendered_template(file, data)
            templates[file] = rendered
        return templates

    def _get_rendered_template(self, file: str, data: dict[str, Any]) -> str:
        file_path = Path(file)
        template_path = get_template_path(file_path)
        if file in self.custom_templates:
            text = self.custom_templates[file]
            rendered = self.render_text(text, data)
        elif self.templates.has_template(template_path):
            rendered = self.render_template(template_path, data)
        else:
            try:
                text = self.get_text_template(file)
            except Exception as e:
                raise ConfigServiceTemplateError(
                    f"node({self.node.name}) service({self.name}) file({file}) "
                    f"failure getting template: {e}"
                )
            rendered = self.render_text(text, data)
        return rendered

    def create_files(self) -> None:
        """
        Creates service files inside associated node.

        :return: nothing
        """
        data = self.data()
        for file in sorted(self.files):
            logger.debug(
                "node(%s) service(%s) template(%s)", self.node.name, self.name, file
            )
            rendered = self._get_rendered_template(file, data)
            file_path = Path(file)
            self.node.create_file(file_path, rendered)

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
                logger.debug(
                    f"node({self.node.name}) service({self.name}) "
                    f"validate command failed: {cmd}"
                )
                time.sleep(self.validation_period)

            if cmds and time.monotonic() - start > self.validation_timer:
                raise ConfigServiceBootError(
                    f"node({self.node.name}) service({self.name}) failed to validate"
                )

    def _render(self, template: Template, data: dict[str, Any] = None) -> str:
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

    def render_text(self, text: str, data: dict[str, Any] = None) -> str:
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

    def render_template(self, template_path: str, data: dict[str, Any] = None) -> str:
        """
        Renders file based template  providing all associated data to template.

        :param template_path: path of file to render
        :param data: service specific defined data for template
        :return: rendered template
        """
        try:
            template = self.templates.get_template(template_path)
            return self._render(template, data)
        except Exception:
            raise CoreError(
                f"node({self.node.name}) service({self.name}) file({template_path})"
                f"{exceptions.text_error_template().render_unicode()}"
            )

    def _define_config(self, configs: list[Configuration]) -> None:
        """
        Initializes default configuration data.

        :param configs: configs to initialize
        :return: nothing
        """
        for config in configs:
            self.config[config.id] = config

    def render_config(self) -> dict[str, str]:
        """
        Returns configuration data key/value pairs for rendering a template.

        :return: nothing
        """
        if self.custom_config:
            return self.custom_config
        else:
            return {k: v.default for k, v in self.config.items()}

    def set_config(self, data: dict[str, str]) -> None:
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
