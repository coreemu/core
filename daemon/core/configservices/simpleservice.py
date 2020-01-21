from core.configservice.base import ConfigService, ConfigServiceMode


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
    default_configs = []

    def get_text(self, name: str) -> str:
        if name == "test1.sh":
            return """
            # sample script 1
            # node id(${node.id}) name(${node.name})
            echo hello
            """
        elif name == "test2.sh":
            return """
            # sample script 2
            # node id(${node.id}) name(${node.name})
            echo hello2
            """
