import json
import logging.config
import os
import subprocess

from core import constants

# setup default null handler
logging.getLogger(__name__).addHandler(logging.NullHandler())


def load_logging_config(config_path=None):
    """
    Load CORE logging configuration file.

    :param str config_path: path to logging config file,
        when None defaults to /etc/core/logging.conf
    :return: nothing
    """
    if not config_path:
        config_path = os.path.join(constants.CORE_CONF_DIR, "logging.conf")
    with open(config_path, "r") as log_config_file:
        log_config = json.load(log_config_file)
        logging.config.dictConfig(log_config)


class CoreCommandError(subprocess.CalledProcessError):
    """
    Used when encountering internal CORE command errors.
    """

    def __str__(self):
        return "Command(%s), Status(%s):\n%s" % (self.cmd, self.returncode, self.output)
