import json
import logging
import logging.config
import os
import subprocess

from core import constants

# setup logging
log_config_path = os.path.join(constants.CORE_CONF_DIR, "logging.conf")
with open(log_config_path, "r") as log_config_file:
    log_config = json.load(log_config_file)
    logging.config.dictConfig(log_config)

logger = logging.getLogger()


class CoreCommandError(subprocess.CalledProcessError):
    """
    Used when encountering internal CORE command errors.
    """

    def __str__(self):
        return "Command(%s), Status(%s):\n%s" % (self.cmd, self.returncode, self.output)
