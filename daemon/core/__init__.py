import json
import logging
import logging.config
import os

from core import constants

log_config_path = os.path.join(constants.CORE_CONF_DIR, "logging.conf")
with open(log_config_path, "r") as log_config_file:
    log_config = json.load(log_config_file)
    logging.config.dictConfig(log_config)

#logging.basicConfig(format="%(asctime)s - %(levelname)s - %(module)s:%(funcName)s - %(message)s", level=logging.DEBUG)
logger = logging.getLogger()
