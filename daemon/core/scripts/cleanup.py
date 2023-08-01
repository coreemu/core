import argparse
import os
import subprocess
import sys
import time


def check_root() -> None:
    if os.geteuid() != 0:
        print("permission denied, run this script as root")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="helps cleanup lingering core processes and files",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-d", "--daemon", action="store_true", help="also kill core-daemon"
    )
    return parser.parse_args()


def cleanup_daemon() -> None:
    print("killing core-daemon process ... ", end="")
    result = subprocess.call("pkill -9 core-daemon", shell=True)
    if result:
        print("not found")
    else:
        print("done")


def cleanup_nodes() -> None:
    print("killing vnoded processes ... ", end="")
    result = subprocess.call("pkill -KILL vnoded", shell=True)
    if result:
        print("none found")
    else:
        time.sleep(1)
        print("done")


def cleanup_emane() -> None:
    print("killing emane processes ... ", end="")
    result = subprocess.call("pkill emane", shell=True)
    if result:
        print("none found")
    else:
        print("done")


def cleanup_sessions() -> None:
    print("removing session directories ... ", end="")
    result = subprocess.call("rm -rf /tmp/pycore*", shell=True)
    if result:
        print("none found")
    else:
        print("done")


def cleanup_interfaces() -> None:
    print("cleaning up devices")
    output = subprocess.check_output("ip -br link show", shell=True)
    lines = output.decode().strip().split("\n")
    for line in lines:
        values = line.split()
        name = values[0]
        if (
            name.startswith("veth")
            or name.startswith("beth")
            or name.startswith("gt.")
            or name.startswith("b.")
            or name.startswith("ctrl")
        ):
            name = name.split("@")[0]
            result = subprocess.call(f"ip link delete {name}", shell=True)
            if result:
                print(f"failed to remove {name}")
            else:
                print(f"removed {name}")
            if name.startswith("b."):
                result = subprocess.call(
                    f"nft delete table bridge {name}",
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=True,
                )
                if not result:
                    print(f"cleared nft rules for {name}")


def main() -> None:
    check_root()
    args = parse_args()
    if args.daemon:
        cleanup_daemon()
    cleanup_nodes()
    cleanup_emane()
    cleanup_interfaces()
    cleanup_sessions()


if __name__ == "__main__":
    main()
