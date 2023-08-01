from typing import Dict, List

from core.config import Configuration
from core.configservice.base import ConfigService, ConfigServiceMode, ShadowDir


class ChatAppService(ConfigService):
    name: str = "ChatApp Server"
    group: str = "ChatApp"
    directories: List[str] = []
    files: List[str] = ["chatapp.sh"]
    executables: List[str] = []
    dependencies: List[str] = []
    startup: List[str] = [f"bash {files[0]}"]
    validate: List[str] = []
    shutdown: List[str] = []
    validation_mode: ConfigServiceMode = ConfigServiceMode.BLOCKING
    default_configs: List[Configuration] = []
    modes: Dict[str, Dict[str, str]] = {}
    shadow_directories: List[ShadowDir] = []

    def get_text_template(self, _name: str) -> str:
        return """
        export PATH=$PATH:/usr/local/bin
        PYTHONUNBUFFERED=1 chatapp-server > chatapp.log 2>&1 &
        """
