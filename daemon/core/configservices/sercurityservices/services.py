from core.configservice.base import ConfigService, ConfigServiceMode

GROUP_NAME = "Security"


class VpnClient(ConfigService):
    name = "VPNClient"
    group = GROUP_NAME
    directories = []
    files = ["vpnclient.sh"]
    executables = ["openvpn", "ip", "killall"]
    dependencies = []
    startup = ["sh vpnclient.sh"]
    validate = ["pidof openvpn"]
    shutdown = ["killall openvpn"]
    validation_mode = ConfigServiceMode.BLOCKING
    default_configs = []
    modes = {}
