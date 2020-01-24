from core.config import Configuration
from core.configservice.base import ConfigService, ConfigServiceMode
from core.emulator.enumerations import ConfigDataTypes


class SimpleService(ConfigService):
    name = "Simple"
    group = "SimpleGroup"
    directories = ["/etc/quagga", "/usr/local/lib"]
    files = ["test1.sh", "test2.sh"]
    executables = []
    dependencies = []
    startup = []
    validate = []
    shutdown = []
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = [
        Configuration(_id="value1", _type=ConfigDataTypes.STRING, label="Text"),
        Configuration(_id="value2", _type=ConfigDataTypes.BOOL, label="Boolean"),
        Configuration(
            _id="value3",
            _type=ConfigDataTypes.STRING,
            label="Multiple Choice",
            options=["value1", "value2", "value3"],
        ),
    ]
    modes = {
        "mode1": {"value1": "value1", "value2": "0", "value3": "value2"},
        "mode2": {"value1": "value2", "value2": "1", "value3": "value3"},
        "mode3": {"value1": "value3", "value2": "0", "value3": "value1"},
    }

    def get_text_template(self, name: str) -> str:
        if name == "test1.sh":
            return """
            # sample script 1
            # node id(${node.id}) name(${node.name})
            # config: ${config}
            echo hello
            """
        elif name == "test2.sh":
            return """
            # sample script 2
            # node id(${node.id}) name(${node.name})
            # config: ${config}
            echo hello2
            """
