from core.configservice.base import ConfigService, ConfigServiceMode

GROUP_NAME = "Security"


class VpnClient(ConfigService):
    name = "VPNClient"
    group = GROUP_NAME
    directories = []
    executables = ["openvpn", "ip", "killall"]
    dependencies = []
    startup = ["sh vpnclient.sh"]
    validate = ["pidof openvpn"]
    shutdown = ["killall openvpn"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []

    def create_files(self):
        self.render_template("vpnclient.sh")
