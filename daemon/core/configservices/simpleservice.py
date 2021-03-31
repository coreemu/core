from typing import Dict, List

from core.config import Configuration
from core.configservice.base import ConfigService, ConfigServiceMode
from core.emulator.enumerations import ConfigDataTypes


class SimpleService(ConfigService):
    name: str = "Simple"
    group: str = "SimpleGroup"
    directories: List[str] = ["/etc/quagga", "/usr/local/lib"]
    files: List[str] = ["test1.sh", "test2.sh"]
    executables: List[str] = []
    dependencies: List[str] = []
    startup: List[str] = []
    validate: List[str] = []
    shutdown: List[str] = []
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = [
        Configuration(id="value1", type=ConfigDataTypes.STRING, label="Text"),
        Configuration(id="value2", type=ConfigDataTypes.BOOL, label="Boolean"),
        Configuration(
            id="value3",
            type=ConfigDataTypes.STRING,
            label="Multiple Choice",
            options=["value1", "value2", "value3"],
        ),
    ]
    modes: Dict[str, Dict[str, str]] = {
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
