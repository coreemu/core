from core.configservice.base import ConfigService, ConfigServiceMode


class SimpleService(ConfigService):
    name = "Simple"
    group = "SimpleGroup"
    directories = []
    executables = []
    dependencies = []
    startup = []
    validate = []
    shutdown = []
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []

    def create_files(self):
        text = """
        # sample script
        # node id(${node.id}) name(${node.name})
        echo hello
        """
        self.render_text("test1.sh", text)
