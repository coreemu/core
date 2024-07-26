import argparse
import logging
from logging.handlers import TimedRotatingFileHandler

from core import utils
from core.gui import appconfig, images
from core.gui.app import Application


def main() -> None:
    # parse flags
    parser = argparse.ArgumentParser(description="CORE Python GUI")
    parser.add_argument(
        "-l",
        "--level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="logging level",
    )
    parser.add_argument("-p", "--proxy", action="store_true", help="enable proxy")
    parser.add_argument("-s", "--session", type=int, help="session id to join")
    parser.add_argument(
        "--create-dir", action="store_true", help="create gui directory and exit"
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
    args = parser.parse_args()

    # check home directory exists and create if necessary
    appconfig.check_directory()
    if args.create_dir:
        return

    # setup logging
    log_format = "%(asctime)s - %(levelname)s - %(module)s:%(funcName)s - %(message)s"
    stream_handler = logging.StreamHandler()
    file_handler = TimedRotatingFileHandler(
        filename=appconfig.LOG_PATH, when="D", backupCount=5
    )
    log_level = logging.getLevelName(args.level)
    logging.basicConfig(
        level=log_level, format=log_format, handlers=[stream_handler, file_handler]
    )
    logging.getLogger("PIL").setLevel(logging.ERROR)

    # enable xhost for root
    if utils.which("xhost", False):
        utils.cmd("xhost +SI:localuser:root")

    # start app
    print(args.proxy, args.grpcaddress, args.grpcport, args.session)
    images.load_all()
    app = Application(args.proxy, args.grpcaddress, args.grpcport, args.session)
    app.mainloop()


if __name__ == "__main__":
    main()
