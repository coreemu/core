"""
core-daemon: the CORE daemon is a server process that receives CORE API
messages and instantiates emulated nodes and networks within the kernel. Various
message handlers are defined and some support for sending messages.
"""

import argparse
import json
import logging
import logging.config
import time
from configparser import ConfigParser
from pathlib import Path

from core import constants
from core.api.grpc.server import CoreGrpcServer
from core.constants import COREDPY_VERSION
from core.emulator.coreemu import CoreEmu

logger = logging.getLogger(__name__)

DEFAULT_GRPC_PORT: str = "50051"
DEFAULT_GRPC_ADDRESS: str = "localhost"
DEFAULT_LOG_CONFIG: Path = constants.CORE_CONF_DIR / "logging.conf"
DEFAULT_CORE_CONFIG: Path = constants.CORE_CONF_DIR / "core.conf"


def file_path(value: str) -> Path:
    """
    Checks value for being a valid file path.

    :param value: file path to check
    :return: valid file path
    """
    path = Path(value)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"{path} does not exist")
    return path


def load_logging_config(config_path: Path, debug: bool) -> None:
    """
    Load CORE logging configuration file.

    :param config_path: path to logging config file
    :param debug: enable debug logging
    :return: nothing
    """
    with config_path.open("r") as f:
        log_config = json.load(f)
    if debug:
        log_config["loggers"]["core"]["level"] = "DEBUG"
    logging.config.dictConfig(log_config)


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


def get_merged_config(args: argparse.Namespace) -> dict[str, str]:
    """
    Return a configuration after merging config file and command-line arguments.

    :param args: command line arguments
    :return: merged configuration
    :rtype: dict
    """
    # these are the defaults used in the config file
    defaults = dict(logfile=args.log_config)
    # read the config file
    cfg = ConfigParser(defaults)
    cfg.read(args.config)
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
    # parse arguments
    parser = argparse.ArgumentParser(
        description=f"CORE daemon v.{COREDPY_VERSION}",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="convenience for quickly enabling DEBUG logging",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=file_path,
        default=DEFAULT_CORE_CONFIG,
        help="CORE configuration file",
    )
    parser.add_argument(
        "-l",
        "--log-config",
        type=file_path,
        default=DEFAULT_LOG_CONFIG,
        help="CORE logging configuration file",
    )
    parser.add_argument(
        "--grpc-port",
        dest="grpcport",
        help="override grpc port to listen on",
    )
    parser.add_argument(
        "--grpc-address",
        dest="grpcaddress",
        help="override grpc address to listen on",
    )
    parser.add_argument(
        "--ovs",
        action="store_true",
        help="enable experimental ovs mode",
    )
    args = parser.parse_args()
    # convert ovs to internal format
    args.ovs = "1" if args.ovs else "0"
    # validate files exist
    if not args.log_config.is_file():
        raise FileNotFoundError(f"{args.log_config} does not exist")
    if not args.config.is_file():
        raise FileNotFoundError(f"{args.config} does not exist")
    cfg = get_merged_config(args)
    log_config_path = Path(cfg["logfile"])
    load_logging_config(log_config_path, args.debug)
    banner()
    try:
        cored(cfg)
    except KeyboardInterrupt:
        logger.info("keyboard interrupt, stopping core daemon")


if __name__ == "__main__":
    main()
