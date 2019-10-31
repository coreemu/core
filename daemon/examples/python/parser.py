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
        "-t",
        "--time",
        type=int,
        default=DEFAULT_TIME,
        help="example iperf run time in seconds",
    )

    args = parser.parse_args()

    if args.nodes < 2:
        parser.error(f"invalid min number of nodes: {args.nodes}")
    if args.time < 1:
        parser.error(f"invalid test time: {args.time}")

    return args
