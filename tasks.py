import inspect
import itertools
import os
import sys
import threading
import time
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

from invoke import task, Context

DAEMON_DIR: str = "daemon"
DEFAULT_PREFIX: str = "/usr/local"


class Progress:
    cycles = itertools.cycle(["-", "/", "|", "\\"])

    def __init__(self, verbose: bool) -> None:
        self.verbose: bool = verbose
        self.thread: Optional[threading.Thread] = None
        self.running: bool = False

    @contextmanager
    def start(self, message: str) -> None:
        if not self.verbose:
            print(f"{message} ... ", end="")
            self.running = True
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
        yield
        self.stop()

    def run(self) -> None:
        while self.running:
            sys.stdout.write(next(self.cycles))
            sys.stdout.flush()
            sys.stdout.write("\b")
            time.sleep(0.1)

    def stop(self) -> None:
        if not self.verbose:
            print("done")
        if self.thread:
            self.running = False
            self.thread.join()
            self.thread = None


class OsName(Enum):
    UBUNTU = "ubuntu"
    CENTOS = "centos"


class OsLike(Enum):
    DEBIAN = "debian"
    REDHAT = "rhel fedora"


class OsInfo:
    def __init__(self, name: OsName, like: OsLike, version: float) -> None:
        self.name: OsName = name
        self.like: OsLike = like
        self.version: float = version


def get_python(c: Context, warn: bool = False) -> str:
    with c.cd(DAEMON_DIR):
        r = c.run("poetry env info -p", warn=warn, hide=True)
        if r.ok:
            venv = r.stdout.strip()
            return os.path.join(venv, "bin", "python")
        else:
            return ""


def get_pytest(c: Context) -> str:
    with c.cd(DAEMON_DIR):
        venv = c.run("poetry env info -p", hide=True).stdout.strip()
        return os.path.join(venv, "bin", "pytest")


def get_os() -> OsInfo:
    d = {}
    with open("/etc/os-release", "r") as f:
        for line in f.readlines():
            line = line.strip()
            if not line:
                continue
            key, value = line.split("=")
            d[key] = value.strip("\"")
    name_value = d["ID"]
    like_value = d["ID_LIKE"]
    version_value = d["VERSION_ID"]
    try:
        name = OsName(name_value)
        like = OsLike(like_value)
        version = float(version_value)
    except ValueError:
        print(
            f"unsupported os({name_value}) like({like_value}) version({version_value}"
        )
        sys.exit(1)
    return OsInfo(name, like, version)


def install_system(c: Context, os_info: OsInfo, hide: bool) -> None:
    if os_info.like == OsLike.DEBIAN:
        c.run(
            "sudo apt install -y automake pkg-config gcc libev-dev ebtables "
            "iproute2 ethtool tk python3-tk",
            hide=hide
        )
    elif os_info.like == OsLike.REDHAT:
        c.run(
            "sudo yum install -y automake pkgconf-pkg-config gcc gcc-c++ "
            "libev-devel iptables-ebtables iproute python3-devel python3-tkinter "
            "tk ethtool make",
            hide=hide
        )
        # centos 8+ does not support netem by default
        if os_info.name == OsName.CENTOS and os_info.version >= 8:
            c.run("sudo yum install -y kernel-modules-extra", hide=hide)
            if not c.run("sudo modprobe sch_netem", warn=True, hide=hide):
                print("\nERROR: you need to install the latest kernel")
                print("run the following, restart, and try again")
                print("sudo yum update")
                sys.exit(1)

    # attempt to setup legacy ebtables when an nftables based version is found
    r = c.run("ebtables -V", hide=hide)
    if "nf_tables" in r.stdout:
        if not c.run(
            "sudo update-alternatives --set ebtables /usr/sbin/ebtables-legacy",
            warn=True,
            hide=hide
        ):
            print(
                "\nWARNING: unable to setup ebtables-legacy, WLAN will not work"
            )


def install_grpcio(c: Context, hide: bool) -> None:
    c.run(
        "python3 -m pip install --user grpcio==1.27.2 grpcio-tools==1.27.2",
        hide=hide,
    )


def build_core(c: Context, hide: bool, prefix: str = DEFAULT_PREFIX) -> None:
    c.run("./bootstrap.sh", hide=hide)
    c.run(f"./configure --prefix={prefix}", hide=hide)
    c.run("make -j$(nproc)", hide=hide)


def install_core(c: Context, hide: bool) -> None:
    c.run("sudo make install", hide=hide)


def install_poetry(c: Context, dev: bool, hide: bool) -> None:
    c.run("pipx install poetry", hide=hide)
    args = "" if dev else "--no-dev"
    with c.cd(DAEMON_DIR):
        c.run(f"poetry install {args}", hide=hide)
        if dev:
            c.run("poetry run pre-commit install", hide=hide)


def install_ospf_mdr(c: Context, os_info: OsInfo, hide: bool) -> None:
    if c.run("which zebra", warn=True, hide=hide):
        print("\nquagga already installed, skipping ospf mdr")
        return
    if os_info.like == OsLike.DEBIAN:
        c.run("sudo apt install -y libtool gawk libreadline-dev git", hide=hide)
    elif os_info.like == OsLike.REDHAT:
        c.run("sudo yum install -y libtool gawk readline-devel git", hide=hide)
    clone_dir = "/tmp/ospf-mdr"
    c.run(
        f"git clone https://github.com/USNavalResearchLaboratory/ospf-mdr {clone_dir}",
        hide=hide
    )
    with c.cd(clone_dir):
        c.run("./bootstrap.sh", hide=hide)
        c.run(
            "./configure --disable-doc --enable-user=root --enable-group=root "
            "--with-cflags=-ggdb --sysconfdir=/usr/local/etc/quagga --enable-vtysh "
            "--localstatedir=/var/run/quagga",
            hide=hide
        )
        c.run("make -j$(nproc)", hide=hide)
        c.run("sudo make install", hide=hide)


@task
def install_service(c, verbose=False, prefix=DEFAULT_PREFIX):
    """
    install systemd core service
    """
    hide = not verbose
    bin_dir = Path(prefix).joinpath("bin")
    systemd_dir = Path("/lib/systemd/system/")
    service_file = systemd_dir.joinpath("core-daemon.service")
    if systemd_dir.exists():
        service_data = inspect.cleandoc(f"""
            [Unit]
            Description=Common Open Research Emulator Service
            After=network.target

            [Service]
            Type=simple
            ExecStart={bin_dir}/core-daemon
            TasksMax=infinity

            [Install]
            WantedBy=multi-user.target
            """)
        temp = NamedTemporaryFile("w", delete=False)
        temp.write(service_data)
        temp.close()
        c.run(f"sudo cp {temp.name} {service_file}", hide=hide)
    else:
        print(f"ERROR: systemd service path not found: {systemd_dir}")


@task
def install_scripts(c, verbose=False, prefix=DEFAULT_PREFIX):
    """
    install core script files, modified to leverage virtual environment
    """
    hide = not verbose
    python = get_python(c)
    bin_dir = Path(prefix).joinpath("bin")
    for script in Path("daemon/scripts").iterdir():
        dest = bin_dir.joinpath(script.name)
        with open(script, "r") as f:
            lines = f.readlines()
        first = lines[0].strip()
        # modify python scripts to point to virtual environment
        if first == "#!/usr/bin/env python3":
            lines[0] = f"#!{python}\n"
            temp = NamedTemporaryFile("w", delete=False)
            for line in lines:
                temp.write(line)
            temp.close()
            c.run(f"sudo cp {temp.name} {dest}", hide=hide)
            c.run(f"sudo chmod 755 {dest}", hide=hide)
            os.unlink(temp.name)
        # copy normal links
        else:
            c.run(f"sudo cp {script} {dest}", hide=hide)

    # install core configuration file
    config_dir = "/etc/core"
    c.run(f"sudo mkdir -p {config_dir}", hide=hide)
    c.run(f"sudo cp -n daemon/data/core.conf {config_dir}", hide=hide)
    c.run(f"sudo cp -n daemon/data/logging.conf {config_dir}", hide=hide)


@task
def install(c, dev=False, verbose=False, prefix=DEFAULT_PREFIX):
    """
    install core, poetry, scripts, service, and ospf mdr
    """
    c.run("sudo -v", hide=True)
    print(f"installing core with prefix: {prefix}")
    p = Progress(verbose)
    hide = not verbose
    os_info = get_os()
    with p.start("installing system dependencies"):
        install_system(c, os_info, hide)
    with p.start("installing system grpcio-tools"):
        install_grpcio(c, hide)
    with p.start("building core"):
        build_core(c, hide, prefix)
    with p.start("installing vcmd/gui"):
        install_core(c, hide)
    with p.start("installing poetry virtual environment"):
        install_poetry(c, dev, hide)
    with p.start("installing scripts and /etc/core"):
        install_scripts(c, hide, prefix)
    with p.start("installing systemd service"):
        install_service(c, hide, prefix)
    with p.start("installing ospf mdr"):
        install_ospf_mdr(c, os_info, hide)
    print("\nyou may need to open a new terminal to leverage invoke for running core")


@task
def install_emane(c, verbose=False):
    """
    install emane and the python bindings
    """
    c.run("sudo -v", hide=True)
    p = Progress(verbose)
    hide = not verbose
    os_info = get_os()
    emane_dir = "/tmp/emane"
    with p.start("installing system dependencies"):
        if os_info.like == OsLike.DEBIAN:
            c.run(
                "sudo apt install -y gcc g++ automake libtool libxml2-dev "
                "libprotobuf-dev libpcap-dev libpcre3-dev uuid-dev pkg-config "
                "protobuf-compiler git python3-protobuf python3-setuptools",
                hide=hide,
            )
        elif os_info.like == OsLike.REDHAT:
            c.run(
                "sudo yum install -y autoconf automake git libtool libxml2-devel "
                "libpcap-devel pcre-devel libuuid-devel make gcc-c++ "
                "python3-setuptools",
                hide=hide,
            )
    with p.start("cloning emane"):
        c.run(
            f"git clone https://github.com/adjacentlink/emane.git {emane_dir}",
            hide=hide
        )
    with p.start("building emane"):
        with c.cd(emane_dir):
            c.run("./autogen.sh", hide=hide)
            c.run("PYTHON=python3 ./configure --prefix=/usr", hide=hide)
            c.run("make -j$(nproc)", hide=hide)
    with p.start("installing emane"):
        with c.cd(emane_dir):
            c.run("sudo make install", hide=hide)
    with p.start("installing python binding for core"):
        with c.cd(DAEMON_DIR):
            c.run(f"poetry run pip install {emane_dir}/src/python", hide=hide)


@task
def uninstall(c, dev=False, verbose=False, prefix=DEFAULT_PREFIX):
    """
    uninstall core
    """
    hide = not verbose
    p = Progress(verbose)
    c.run("sudo -v", hide=True)
    with p.start("uninstalling core"):
        c.run("sudo make uninstall", hide=hide)

    with p.start("cleaning build directory"):
        c.run("make clean", hide=hide)
        c.run("./bootstrap.sh clean", hide=hide)

    python = get_python(c, warn=True)
    if python:
        with c.cd(DAEMON_DIR):
            if dev:
                with p.start("uninstalling pre-commit"):
                    c.run("poetry run pre-commit uninstall", hide=hide)
            with p.start("uninstalling poetry virtual environment"):
                c.run(f"poetry env remove {python}", hide=hide)

    # remove installed files
    bin_dir = Path(prefix).joinpath("bin")
    with p.start("uninstalling script files"):
        for script in Path("daemon/scripts").iterdir():
            dest = bin_dir.joinpath(script.name)
            c.run(f"sudo rm -f {dest}", hide=hide)

    # install service
    systemd_dir = Path("/lib/systemd/system/")
    service_name = "core-daemon.service"
    service_file = systemd_dir.joinpath(service_name)
    if service_file.exists():
        with p.start(f"uninstalling service {service_file}"):
            c.run(f"sudo systemctl disable {service_name}", hide=hide)
            c.run(f"sudo rm -f {service_file}", hide=hide)


@task
def daemon(c):
    """
    start core-daemon
    """
    python = get_python(c)
    with c.cd(DAEMON_DIR):
        c.run(
            f"sudo {python} scripts/core-daemon "
            "-f data/core.conf -l data/logging.conf",
            pty=True
        )


@task
def gui(c):
    """
    start core-pygui
    """
    with c.cd(DAEMON_DIR):
        c.run("poetry run scripts/core-pygui", pty=True)


@task
def cli(c, args):
    """
    run core-cli used to query and modify a running session
    """
    with c.cd(DAEMON_DIR):
        c.run(f"poetry run scripts/core-cli {args}", pty=True)


@task
def cleanup(c):
    """
    run core-cleanup removing leftover core nodes, bridges, directories
    """
    print("running core-cleanup...")
    c.run(f"sudo daemon/scripts/core-cleanup", pty=True)


@task
def test(c):
    """
    run core tests
    """
    pytest = get_pytest(c)
    with c.cd(DAEMON_DIR):
        c.run(f"sudo {pytest} -v --lf -x tests", pty=True)


@task
def test_mock(c):
    """
    run core tests using mock to avoid running as sudo
    """
    with c.cd(DAEMON_DIR):
        c.run("poetry run pytest -v --mock --lf -x tests", pty=True)


@task
def test_emane(c):
    """
    run core emane tests
    """
    pytest = get_pytest(c)
    with c.cd(DAEMON_DIR):
        c.run(f"{pytest} -v --lf -x tests/emane", pty=True)
