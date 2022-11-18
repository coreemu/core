import argparse
import logging
import sys
from pathlib import Path

from core.player import CorePlayer

logger = logging.getLogger(__name__)


def path_type(value: str) -> Path:
    file_path = Path(value)
    if not file_path.is_file():
        raise argparse.ArgumentTypeError(f"file does not exist: {value}")
    return file_path


def parse_args() -> argparse.Namespace:
    """
    Setup and parse command line arguments.

    :return: parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="core player runs files that can move nodes and send commands",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-f", "--file", required=True, type=path_type, help="core file to play"
    )
    parser.add_argument(
        "-s",
        "--session",
        type=int,
        help="session to play to, first found session otherwise",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    player = CorePlayer(args.file)
    result = player.init(args.session)
    if not result:
        sys.exit(1)
    player.start()


if __name__ == "__main__":
    main()
