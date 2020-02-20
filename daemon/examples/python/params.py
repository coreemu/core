import argparse

DEFAULT_NODES = 2
DEFAULT_TIME = 10
DEFAULT_STEP = 1


def parse(name):
    parser = argparse.ArgumentParser(description=f"Run {name} example")
    parser.add_argument(
        "-n",
        "--nodes",
        type=int,
        default=DEFAULT_NODES,
        help="number of nodes to create in this example",
    )
    parser.add_argument(
        "-c",
        "--count",
        type=int,
        default=DEFAULT_TIME,
        help="number of time to ping node",
    )

    args = parser.parse_args()

    if args.nodes < 2:
        parser.error(f"invalid min number of nodes: {args.nodes}")
    if args.count < 1:
        parser.error(f"invalid ping count({args.count}), count must be greater than 0")

    return args
