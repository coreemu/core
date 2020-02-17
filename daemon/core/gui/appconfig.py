import os
import shutil
from pathlib import Path

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

# local paths
DATA_PATH = Path(__file__).parent.joinpath("data")
LOCAL_ICONS_PATH = DATA_PATH.joinpath("icons").absolute()
LOCAL_BACKGROUND_PATH = DATA_PATH.joinpath("backgrounds").absolute()
LOCAL_XMLS_PATH = DATA_PATH.joinpath("xmls").absolute()
LOCAL_MOBILITY_PATH = DATA_PATH.joinpath("mobility").absolute()

# configuration data
TERMINALS = [
    "$TERM",
    "gnome-terminal --window --",
    "lxterminal -e",
    "konsole -e",
    "xterm -e",
    "aterm -e",
    "eterm -e",
    "rxvt -e",
    "xfce4-terminal -x",
]
EDITORS = ["$EDITOR", "vim", "emacs", "gedit", "nano", "vi"]


class IndentDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def copy_files(current_path, new_path):
    for current_file in current_path.glob("*"):
        new_file = new_path.joinpath(current_file.name)
        shutil.copy(current_file, new_file)


def check_directory():
    if HOME_PATH.exists():
        return
    HOME_PATH.mkdir()
    BACKGROUNDS_PATH.mkdir()
    CUSTOM_EMANE_PATH.mkdir()
    CUSTOM_SERVICE_PATH.mkdir()
    ICONS_PATH.mkdir()
    MOBILITY_PATH.mkdir()
    XMLS_PATH.mkdir()

    copy_files(LOCAL_ICONS_PATH, ICONS_PATH)
    copy_files(LOCAL_BACKGROUND_PATH, BACKGROUNDS_PATH)
    copy_files(LOCAL_XMLS_PATH, XMLS_PATH)
    copy_files(LOCAL_MOBILITY_PATH, MOBILITY_PATH)

    if "TERM" in os.environ:
        terminal = TERMINALS[0]
    else:
        terminal = TERMINALS[1]
    if "EDITOR" in os.environ:
        editor = EDITORS[0]
    else:
        editor = EDITORS[1]
    config = {
        "preferences": {
            "theme": themes.THEME_DARK,
            "editor": editor,
            "terminal": terminal,
            "gui3d": "/usr/local/bin/std3d.sh",
            "width": 1000,
            "height": 750,
        },
        "location": {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "lat": 47.5791667,
            "lon": -122.132322,
            "alt": 2.0,
            "scale": 150.0,
        },
        "servers": [{"name": "example", "address": "127.0.0.1", "port": 50051}],
        "nodes": [],
        "recentfiles": [],
        "observers": [{"name": "hello", "cmd": "echo hello"}],
        "scale": 1.0,
    }
    save(config)


def read():
    with CONFIG_PATH.open("r") as f:
        return yaml.load(f, Loader=yaml.SafeLoader)


def save(config):
    with CONFIG_PATH.open("w") as f:
        yaml.dump(config, f, Dumper=IndentDumper, default_flow_style=False)
