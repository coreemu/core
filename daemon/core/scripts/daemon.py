"""
core-daemon: the CORE daemon is a server process that receives CORE API
messages and instantiates emulated nodes and networks within the kernel. Various
message handlers are defined and some support for sending messages.
"""

import argparse
import logging
import os
import time
from configparser import ConfigParser
from pathlib import Path

from core import constants
from core.api.grpc.server import CoreGrpcServer
from core.constants import CORE_CONF_DIR, COREDPY_VERSION
from core.emulator.coreemu import CoreEmu
from core.utils import load_logging_config

logger = logging.getLogger(__name__)


def banner():
    """
    Output the program banner printed to the terminal or log file.

    :return: nothing
    """
    logger.info("CORE daemon v.%s started %s", constants.COREDPY_VERSION, time.ctime())


def cored(cfg):
    """
    Start the CoreServer object and enter the server loop.

    :param dict cfg: core configuration
    :return: nothing
    """
    # initialize grpc api
    coreemu = CoreEmu(cfg)
    grpc_server = CoreGrpcServer(coreemu)
    address_config = cfg["grpcaddress"]
    port_config = cfg["grpcport"]
    grpc_address = f"{address_config}:{port_config}"
    grpc_server.listen(grpc_address)


def get_merged_config(filename):
    """
    Return a configuration after merging config file and command-line arguments.

    :param str filename: file name to merge configuration settings with
    :return: merged configuration
    :rtype: dict
    """
    # these are the defaults used in the config file
    default_log = os.path.join(constants.CORE_CONF_DIR, "logging.conf")
    default_grpc_port = "50051"
    default_address = "localhost"
    defaults = {
        "grpcport": default_grpc_port,
        "grpcaddress": default_address,
        "logfile": default_log,
    }
    parser = argparse.ArgumentParser(
        description=f"CORE daemon v.{COREDPY_VERSION} instantiates Linux network namespace nodes."
    )
    parser.add_argument(
        "-f",
        "--configfile",
        dest="configfile",
        help=f"read config from specified file; default = {filename}",
    )
    parser.add_argument(
        "--ovs",
        action="store_true",
        help="enable experimental ovs mode, default is false",
    )
    parser.add_argument(
        "--grpc-port",
        dest="grpcport",
        help=f"grpc port to listen on; default {default_grpc_port}",
    )
    parser.add_argument(
        "--grpc-address",
        dest="grpcaddress",
        help=f"grpc address to listen on; default {default_address}",
    )
    parser.add_argument(
        "-l", "--logfile", help=f"core logging configuration; default {default_log}"
    )
    # parse command line options
    args = parser.parse_args()
    # convert ovs to internal format
    args.ovs = "1" if args.ovs else "0"
    # read the config file
    if args.configfile is not None:
        filename = args.configfile
    del args.configfile
    cfg = ConfigParser(defaults)
    cfg.read(filename)
    section = "core-daemon"
    if not cfg.has_section(section):
        cfg.add_section(section)
    # merge argparse with configparser
    for opt in vars(args):
        val = getattr(args, opt)
        if val is not None:
            cfg.set(section, opt, str(val))
    return dict(cfg.items(section))


def main():
    """
    Main program startup.

    :return: nothing
    """
    cfg = get_merged_config(f"{CORE_CONF_DIR}/core.conf")
    log_config_path = Path(cfg["logfile"])
    load_logging_config(log_config_path)
    banner()
    try:
        cored(cfg)
    except KeyboardInterrupt:
        logger.info("keyboard interrupt, stopping core daemon")


if __name__ == "__main__":
    main()
