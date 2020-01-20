from core.configservice.base import ConfigService, ConfigServiceMode


class SimpleService(ConfigService):
    name = "Simple"
    group = "SimpleGroup"
    directories = []
    files = ["test1.sh"]
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
            # sample script
            # node id(${node.id}) name(${node.name})
            echo hello
            """
