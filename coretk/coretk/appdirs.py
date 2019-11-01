import logging
import shutil
from pathlib import Path

# gui home paths
HOME_PATH = Path.home().joinpath(".coretk")
BACKGROUNDS_PATH = HOME_PATH.joinpath("backgrounds")
CUSTOM_EMANE_PATH = HOME_PATH.joinpath("custom_emane")
CUSTOM_SERVICE_PATH = HOME_PATH.joinpath("custom_services")
ICONS_PATH = HOME_PATH.joinpath("icons")
MOBILITY_PATH = HOME_PATH.joinpath("mobility")
XML_PATH = HOME_PATH.joinpath("xml")
CONFIG_PATH = HOME_PATH.joinpath("gui.yaml")

# local paths
LOCAL_ICONS_PATH = Path(__file__).parent.joinpath("icons").absolute()
LOCAL_BACKGROUND_PATH = Path(__file__).parent.joinpath("backgrounds").absolute()


def check_directory():
    if HOME_PATH.exists():
        logging.info("~/.coretk exists")
        return
    logging.info("creating ~/.coretk")
    HOME_PATH.mkdir()
    BACKGROUNDS_PATH.mkdir()
    CUSTOM_EMANE_PATH.mkdir()
    CUSTOM_SERVICE_PATH.mkdir()
    ICONS_PATH.mkdir()
    MOBILITY_PATH.mkdir()
    XML_PATH.mkdir()
    for image in LOCAL_ICONS_PATH.glob("*"):
        new_image = ICONS_PATH.joinpath(image.name)
        shutil.copy(image, new_image)
    for background in LOCAL_BACKGROUND_PATH.glob("*"):
        new_background = BACKGROUNDS_PATH.joinpath(background.name)
        shutil.copy(background, new_background)
    with CONFIG_PATH.open("w") as f:
        f.write("# gui config")
