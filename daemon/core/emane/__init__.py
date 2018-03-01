import subprocess

from core import logger
from core.misc import utils

EMANEUNK = 0
EMANE074 = 7
EMANE081 = 8
EMANE091 = 91
EMANE092 = 92
EMANE093 = 93
EMANE101 = 101

VERSION = None
VERSIONSTR = None


def emane_version():
    """
    Return the locally installed EMANE version identifier and string.
    """
    global VERSION
    global VERSIONSTR
    cmd = ("emane", "--version")

    try:
        status, result = utils.cmd_output(cmd)
    except (OSError, subprocess.CalledProcessError):
        logger.exception("error checking emane version")
        status = -1
        result = ""

    VERSION = EMANEUNK
    if status == 0:
        if result.startswith("0.7.4"):
            VERSION = EMANE074
        elif result.startswith("0.8.1"):
            VERSION = EMANE081
        elif result.startswith("0.9.1"):
            VERSION = EMANE091
        elif result.startswith("0.9.2"):
            VERSION = EMANE092
        elif result.startswith("0.9.3"):
            VERSION = EMANE093
        elif result.startswith("1.0.1"):
            VERSION = EMANE101

    VERSIONSTR = result.strip()


# set version variables for the Emane class
emane_version()
