import os
import shutil
from pathlib import Path

import yaml

from core.gui import themes

HOME_PATH: Path = Path.home().joinpath(".coregui")
BACKGROUNDS_PATH: Path = HOME_PATH.joinpath("backgrounds")
CUSTOM_EMANE_PATH: Path = HOME_PATH.joinpath("custom_emane")
CUSTOM_SERVICE_PATH: Path = HOME_PATH.joinpath("custom_services")
ICONS_PATH: Path = HOME_PATH.joinpath("icons")
MOBILITY_PATH: Path = HOME_PATH.joinpath("mobility")
XMLS_PATH: Path = HOME_PATH.joinpath("xmls")
CONFIG_PATH: Path = HOME_PATH.joinpath("config.yaml")
LOG_PATH: Path = HOME_PATH.joinpath("gui.log")
SCRIPT_PATH: Path = HOME_PATH.joinpath("scripts")

# local paths
DATA_PATH: Path = Path(__file__).parent.joinpath("data")
LOCAL_ICONS_PATH: Path = DATA_PATH.joinpath("icons").absolute()
LOCAL_BACKGROUND_PATH: Path = DATA_PATH.joinpath("backgrounds").absolute()
LOCAL_XMLS_PATH: Path = DATA_PATH.joinpath("xmls").absolute()
LOCAL_MOBILITY_PATH: Path = DATA_PATH.joinpath("mobility").absolute()

# configuration data
TERMINALS: dict[str, str] = {
    "xterm": "xterm -e",
    "aterm": "aterm -e",
    "eterm": "eterm -e",
    "rxvt": "rxvt -e",
    "konsole": "konsole -e",
    "lxterminal": "lxterminal -e",
    "xfce4-terminal": "xfce4-terminal -x",
    "gnome-terminal": "gnome-terminal --window --",
}
EDITORS: list[str] = ["$EDITOR", "vim", "emacs", "gedit", "nano", "vi"]


class IndentDumper(yaml.Dumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        super().increase_indent(flow, False)


class CustomNode(yaml.YAMLObject):
    yaml_tag: str = "!CustomNode"
    yaml_loader: type[yaml.SafeLoader] = yaml.SafeLoader

    def __init__(self, name: str, image: str, services: list[str]) -> None:
        self.name: str = name
        self.image: str = image
        self.services: list[str] = services


class CoreServer(yaml.YAMLObject):
    yaml_tag: str = "!CoreServer"
    yaml_loader: type[yaml.SafeLoader] = yaml.SafeLoader

    def __init__(self, name: str, address: str) -> None:
        self.name: str = name
        self.address: str = address


class Observer(yaml.YAMLObject):
    yaml_tag: str = "!Observer"
    yaml_loader: type[yaml.SafeLoader] = yaml.SafeLoader

    def __init__(self, name: str, cmd: str) -> None:
        self.name: str = name
        self.cmd: str = cmd


class NodeCommand(yaml.YAMLObject):
    yaml_tag: str = "!NodeCommand"
    yaml_loader: type[yaml.SafeLoader] = yaml.SafeLoader

    def __init__(self, name: str, cmd: str, wait: bool) -> None:
        self.name: str = name
        self.cmd: str = cmd
        self.wait: bool = wait

    @classmethod
    def from_yaml(cls, loader, node):
        data = loader.construct_mapping(node)
        return cls(
            name=data.get("name", ""),
            cmd=data.get("cmd", ""),
            wait=data.get("wait", True),
        )


class PreferencesConfig(yaml.YAMLObject):
    yaml_tag: str = "!PreferencesConfig"
    yaml_loader: type[yaml.SafeLoader] = yaml.SafeLoader

    def __init__(
        self,
        editor: str = EDITORS[1],
        terminal: str = None,
        theme: str = themes.THEME_DARK,
        gui3d: str = "/usr/local/bin/std3d.sh",
        width: int = 1000,
        height: int = 750,
    ) -> None:
        self.theme: str = theme
        self.editor: str = editor
        self.terminal: str = terminal
        self.gui3d: str = gui3d
        self.width: int = width
        self.height: int = height


class LocationConfig(yaml.YAMLObject):
    yaml_tag: str = "!LocationConfig"
    yaml_loader: type[yaml.SafeLoader] = yaml.SafeLoader

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        lat: float = 47.5791667,
        lon: float = -122.132322,
        alt: float = 2.0,
        scale: float = 150.0,
    ) -> None:
        self.x: float = x
        self.y: float = y
        self.z: float = z
        self.lat: float = lat
        self.lon: float = lon
        self.alt: float = alt
        self.scale: float = scale


class IpConfigs(yaml.YAMLObject):
    yaml_tag: str = "!IpConfigs"
    yaml_loader: type[yaml.SafeLoader] = yaml.SafeLoader

    def __init__(self, **kwargs) -> None:
        self.__setstate__(kwargs)

    def __setstate__(self, kwargs):
        self.ip4s: list[str] = kwargs.get(
            "ip4s", ["10.0.0.0", "192.168.0.0", "172.16.0.0"]
        )
        self.ip4: str = kwargs.get("ip4", self.ip4s[0])
        self.ip6s: list[str] = kwargs.get("ip6s", ["2001::", "2002::", "a::"])
        self.ip6: str = kwargs.get("ip6", self.ip6s[0])
        self.enable_ip4: bool = kwargs.get("enable_ip4", True)
        self.enable_ip6: bool = kwargs.get("enable_ip6", True)


class GuiConfig(yaml.YAMLObject):
    yaml_tag: str = "!GuiConfig"
    yaml_loader: type[yaml.SafeLoader] = yaml.SafeLoader

    def __init__(
        self,
        preferences: PreferencesConfig = None,
        location: LocationConfig = None,
        servers: list[CoreServer] = None,
        nodes: list[CustomNode] = None,
        recentfiles: list[str] = None,
        observers: list[Observer] = None,
        scale: float = 1.0,
        ips: IpConfigs = None,
        mac: str = "00:00:00:aa:00:00",
        node_commands: list[NodeCommand] = None,
    ) -> None:
        if preferences is None:
            preferences = PreferencesConfig()
        self.preferences: PreferencesConfig = preferences
        if location is None:
            location = LocationConfig()
        self.location: LocationConfig = location
        if servers is None:
            servers = []
        self.servers: list[CoreServer] = servers
        if nodes is None:
            nodes = []
        self.nodes: list[CustomNode] = nodes
        if recentfiles is None:
            recentfiles = []
        self.recentfiles: list[str] = recentfiles
        if observers is None:
            observers = []
        self.observers: list[Observer] = observers
        self.scale: float = scale
        if ips is None:
            ips = IpConfigs()
        self.ips: IpConfigs = ips
        self.mac: str = mac
        self.node_commands: list[NodeCommand] = node_commands or []

    @classmethod
    def from_yaml(cls, loader, node):
        values = loader.construct_mapping(node, deep=True)
        return cls(**values)


def copy_files(current_path: Path, new_path: Path) -> None:
    for current_file in current_path.glob("*"):
        new_file = new_path.joinpath(current_file.name)
        if not new_file.exists():
            shutil.copy(current_file, new_file)


def find_terminal() -> str | None:
    for term in sorted(TERMINALS):
        cmd = TERMINALS[term]
        if shutil.which(term):
            return cmd
    return None


def check_directory() -> None:
    HOME_PATH.mkdir(exist_ok=True)
    BACKGROUNDS_PATH.mkdir(exist_ok=True)
    CUSTOM_EMANE_PATH.mkdir(exist_ok=True)
    CUSTOM_SERVICE_PATH.mkdir(exist_ok=True)
    ICONS_PATH.mkdir(exist_ok=True)
    MOBILITY_PATH.mkdir(exist_ok=True)
    XMLS_PATH.mkdir(exist_ok=True)
    SCRIPT_PATH.mkdir(exist_ok=True)
    copy_files(LOCAL_ICONS_PATH, ICONS_PATH)
    copy_files(LOCAL_BACKGROUND_PATH, BACKGROUNDS_PATH)
    copy_files(LOCAL_XMLS_PATH, XMLS_PATH)
    copy_files(LOCAL_MOBILITY_PATH, MOBILITY_PATH)
    if not CONFIG_PATH.exists():
        terminal = find_terminal()
        if "EDITOR" in os.environ:
            editor = EDITORS[0]
        else:
            editor = EDITORS[1]
        preferences = PreferencesConfig(editor, terminal)
        config = GuiConfig(preferences=preferences)
        save(config)


def read() -> GuiConfig:
    with CONFIG_PATH.open("r") as f:
        return yaml.safe_load(f)


def save(config: GuiConfig) -> None:
    with CONFIG_PATH.open("w") as f:
        yaml.dump(config, f, Dumper=IndentDumper, default_flow_style=False)
