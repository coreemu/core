"""
Describes what an example service could be
"""
from core.config import ConfigString, ConfigBool, Configuration
from core.services.base import CoreService, ShadowDir, ServiceMode


# class that subclasses ConfigService
class ExampleService(CoreService):
    # unique name for your service within CORE
    name: str = "Example"
    # the group your service is associated with, used for display in GUI
    group: str = "ExampleGroup"
    # directories that the service should shadow mount, hiding the system directory
    directories: list[str] = ["/usr/local/core"]
    # files that this service should generate, defaults to nodes home directory
    # or can provide an absolute path to a mounted directory
    files: list[str] = ["example-start.sh"]
    # executables that should exist on path, that this service depends on
    executables: list[str] = []
    # other services that this service depends on, defines service start order
    dependencies: list[str] = []
    # commands to run to start this service
    startup: list[str] = []
    # commands to run to validate this service
    validate: list[str] = []
    # commands to run to stop this service
    shutdown: list[str] = []
    # validation mode, blocking, non-blocking, and timer
    validation_mode: ServiceMode = ServiceMode.BLOCKING
    # configurable values that this service can use, for file generation
    default_configs: list[Configuration] = [
        ConfigString(id="value1", label="Text"),
        ConfigBool(id="value2", label="Boolean"),
        ConfigString(id="value3", label="Multiple Choice",
                     options=["value1", "value2", "value3"]),
    ]
    # sets of values to set for the configuration defined above, can be used to
    # provide convenient sets of values to typically use
    modes: dict[str, dict[str, str]] = {
        "mode1": {"value1": "value1", "value2": "0", "value3": "value2"},
        "mode2": {"value1": "value2", "value2": "1", "value3": "value3"},
        "mode3": {"value1": "value3", "value2": "0", "value3": "value1"},
    }
    # defines directories that this service can help shadow within a node
    shadow_directories: list[ShadowDir] = []

    def get_text_template(self, name: str) -> str:
        """
        This function is used to return a string template that will be rendered
        by the templating engine. Available variables will be node and any other
        key/value pairs returned by the "data()" function.

        :param name: name of file to get template for
        :return: string template
        """
        return """
        # sample script 1
        # node id(${node.id}) name(${node.name})
        # config: ${config}
        echo hello
        """
