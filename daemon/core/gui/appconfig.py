import os
import shutil
from pathlib import Path
from typing import List, Optional

import yaml

# gui home paths
from core.gui import themes

HOME_PATH = Path.home().joinpath(".coretk")
BACKGROUNDS_PATH = HOME_PATH.joinpath("backgrounds")
CUSTOM_EMANE_PATH = HOME_PATH.joinpath("custom_emane")
CUSTOM_SERVICE_PATH = HOME_PATH.joinpath("custom_services")
ICONS_PATH = HOME_PATH.joinpath("icons")
MOBILITY_PATH = HOME_PATH.joinpath("mobility")
XMLS_PATH = HOME_PATH.joinpath("xmls")
CONFIG_PATH = HOME_PATH.joinpath("gui.yaml")
LOG_PATH = HOME_PATH.joinpath("gui.log")
SCRIPT_PATH = HOME_PATH.joinpath("scripts")

# local paths
DATA_PATH = Path(__file__).parent.joinpath("data")
LOCAL_ICONS_PATH = DATA_PATH.joinpath("icons").absolute()
LOCAL_BACKGROUND_PATH = DATA_PATH.joinpath("backgrounds").absolute()
LOCAL_XMLS_PATH = DATA_PATH.joinpath("xmls").absolute()
LOCAL_MOBILITY_PATH = DATA_PATH.joinpath("mobility").absolute()

# configuration data
TERMINALS = {
    "xterm": "xterm -e",
    "aterm": "aterm -e",
    "eterm": "eterm -e",
    "rxvt": "rxvt -e",
    "konsole": "konsole -e",
    "lxterminal": "lxterminal -e",
    "xfce4-terminal": "xfce4-terminal -x",
    "gnome-terminal": "gnome-terminal --window --",
}
EDITORS = ["$EDITOR", "vim", "emacs", "gedit", "nano", "vi"]


class IndentDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


class CustomNode(yaml.YAMLObject):
    yaml_tag = "!CustomNode"
    yaml_loader = yaml.SafeLoader

    def __init__(self, name: str, image: str, services: List[str]) -> None:
        self.name = name
        self.image = image
        self.services = services


class CoreServer(yaml.YAMLObject):
    yaml_tag = "!CoreServer"
    yaml_loader = yaml.SafeLoader

    def __init__(self, name: str, address: str) -> None:
        self.name = name
        self.address = address


class Observer(yaml.YAMLObject):
    yaml_tag = "!Observer"
    yaml_loader = yaml.SafeLoader

    def __init__(self, name: str, cmd: str) -> None:
        self.name = name
        self.cmd = cmd


class PreferencesConfig(yaml.YAMLObject):
    yaml_tag = "!PreferencesConfig"
    yaml_loader = yaml.SafeLoader

    def __init__(
        self,
        editor: str = EDITORS[1],
        terminal: str = None,
        theme: str = themes.THEME_DARK,
        gui3d: str = "/usr/local/bin/std3d.sh",
        width: int = 1000,
        height: int = 750,
    ) -> None:
        self.theme = theme
        self.editor = editor
        self.terminal = terminal
        self.gui3d = gui3d
        self.width = width
        self.height = height


class LocationConfig(yaml.YAMLObject):
    yaml_tag = "!LocationConfig"
    yaml_loader = yaml.SafeLoader

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
        self.x = x
        self.y = y
        self.z = z
        self.lat = lat
        self.lon = lon
        self.alt = alt
        self.scale = scale


class IpConfigs(yaml.YAMLObject):
    yaml_tag = "!IpConfigs"
    yaml_loader = yaml.SafeLoader

    def __init__(
        self,
        ip4: str = None,
        ip6: str = None,
        ip4s: List[str] = None,
        ip6s: List[str] = None,
    ) -> None:
        if ip4s is None:
            ip4s = ["10.0.0.0", "192.168.0.0", "172.16.0.0"]
        self.ip4s = ip4s
        if ip6s is None:
            ip6s = ["2001::", "2002::", "a::"]
        self.ip6s = ip6s
        if ip4 is None:
            ip4 = self.ip4s[0]
        self.ip4 = ip4
        if ip6 is None:
            ip6 = self.ip6s[0]
        self.ip6 = ip6


class GuiConfig(yaml.YAMLObject):
    yaml_tag = "!GuiConfig"
    yaml_loader = yaml.SafeLoader

    def __init__(
        self,
        preferences: PreferencesConfig = None,
        location: LocationConfig = None,
        servers: List[CoreServer] = None,
        nodes: List[CustomNode] = None,
        recentfiles: List[str] = None,
        observers: List[Observer] = None,
        scale: float = 1.0,
        ips: IpConfigs = None,
        mac: str = "00:00:00:aa:00:00",
    ) -> None:
        if preferences is None:
            preferences = PreferencesConfig()
        self.preferences = preferences
        if location is None:
            location = LocationConfig()
        self.location = location
        if servers is None:
            servers = []
        self.servers = servers
        if nodes is None:
            nodes = []
        self.nodes = nodes
        if recentfiles is None:
            recentfiles = []
        self.recentfiles = recentfiles
        if observers is None:
            observers = []
        self.observers = observers
        self.scale = scale
        if ips is None:
            ips = IpConfigs()
        self.ips = ips
        self.mac = mac


def copy_files(current_path, new_path) -> None:
    for current_file in current_path.glob("*"):
        new_file = new_path.joinpath(current_file.name)
        shutil.copy(current_file, new_file)


def find_terminal() -> Optional[str]:
    for term in sorted(TERMINALS):
        cmd = TERMINALS[term]
        if shutil.which(term):
            return cmd
    return None


def check_directory() -> None:
    if HOME_PATH.exists():
        return
    HOME_PATH.mkdir()
    BACKGROUNDS_PATH.mkdir()
    CUSTOM_EMANE_PATH.mkdir()
    CUSTOM_SERVICE_PATH.mkdir()
    ICONS_PATH.mkdir()
    MOBILITY_PATH.mkdir()
    XMLS_PATH.mkdir()
    SCRIPT_PATH.mkdir()

    copy_files(LOCAL_ICONS_PATH, ICONS_PATH)
    copy_files(LOCAL_BACKGROUND_PATH, BACKGROUNDS_PATH)
    copy_files(LOCAL_XMLS_PATH, XMLS_PATH)
    copy_files(LOCAL_MOBILITY_PATH, MOBILITY_PATH)

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
        return yaml.load(f, Loader=yaml.SafeLoader)


def save(config: GuiConfig) -> None:
    with CONFIG_PATH.open("w") as f:
        yaml.dump(config, f, Dumper=IndentDumper, default_flow_style=False)
