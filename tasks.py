import os
import sys
from enum import Enum

from invoke import task, Context

DAEMON_DIR: str = "daemon"
VCMD_DIR: str = "netns"
GUI_DIR: str = "gui"


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


def get_python(c: Context) -> str:
    with c.cd(DAEMON_DIR):
        venv = c.run("poetry env info -p", hide=True).stdout.strip()
        return os.path.join(venv, "bin", "python")


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
            d[key] = value.strip('"')
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
    print("installing system dependencies...")
    if os_info.like == OsLike.DEBIAN:
        c.run(
            "sudo apt install -y automake pkg-config gcc libev-dev ebtables iproute2 "
            "ethtool tk python3-tk",
            hide=hide
        )
    elif os_info.like == OsLike.REDHAT:
        c.run(
            "sudo yum install -y automake pkgconf-pkg-config gcc gcc-c++ libev-devel "
            "iptables-ebtables iproute python3-devel python3-tkinter tk ethtool make "
            "kernel-modules-extra",
            hide=hide
        )
        # centos 8+ does not support netem by default
        if os_info.name == OsName.CENTOS and os_info.version >= 8:
            c.run("sudo yum install -y kernel-modules-extra", hide=hide)
            if not c.run("sudo modprobe sch_netem", warn=True, hide=hide):
                print("ERROR: you need to install the latest kernel")
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
            print("ERROR: unable to setup required ebtables-legacy, WLAN will not work")


def install_grpcio(c: Context, hide: bool) -> None:
    print("installing grpcio-tools...")
    c.run(
        "python3 -m pip install --only-binary \":all:\" --user grpcio-tools", hide=hide
    )


def build(c: Context, os_info: OsInfo, hide: bool) -> None:
    print("building core...")
    c.run("./bootstrap.sh", hide=hide)
    prefix = "--prefix=/usr" if os_info.like == OsLike.REDHAT else ""
    c.run(f"./configure {prefix}", hide=hide)
    c.run("make -j$(nproc)", hide=hide)


def install_core(c: Context, hide: bool) -> None:
    print("installing core vcmd...")
    with c.cd(VCMD_DIR):
        c.run("sudo make install", hide=hide)
    print("installing core gui...")
    with c.cd(GUI_DIR):
        c.run("sudo make install", hide=hide)


def install_poetry(c: Context, dev: bool, hide: bool) -> None:
    print("installing poetry...")
    c.run("pipx install poetry", hide=hide)
    args = "" if dev else "--no-dev"
    with c.cd(DAEMON_DIR):
        print("installing core environment using poetry...")
        c.run(f"poetry install {args}", hide=hide)
        if dev:
            c.run("poetry run pre-commit install", hide=hide)


def install_ospf_mdr(c: Context, os_info: OsInfo, hide: bool) -> None:
    if c.run("which zebra", warn=True, hide=hide):
        print("quagga already installed, skipping ospf mdr")
        return
    print("installing ospf mdr dependencies...")
    if os_info.like == OsLike.DEBIAN:
        c.run("sudo apt install -y libtool gawk libreadline-dev git", hide=hide)
    elif os_info.like == OsLike.REDHAT:
        c.run("sudo yum install -y libtool gawk readline-devel git", hide=hide)
    print("cloning ospf mdr...")
    clone_dir = "/tmp/ospf-mdr"
    c.run(
        f"git clone https://github.com/USNavalResearchLaboratory/ospf-mdr {clone_dir}",
        hide=hide
    )
    with c.cd(clone_dir):
        print("building ospf mdr...")
        c.run("./bootstrap.sh", hide=hide)
        c.run(
            "./configure --disable-doc --enable-user=root --enable-group=root "
            "--with-cflags=-ggdb --sysconfdir=/usr/local/etc/quagga --enable-vtysh "
            "--localstatedir=/var/run/quagga",
            hide=hide
        )
        c.run("make -j$(nproc)", hide=hide)
        print("installing ospf mdr...")
        c.run("sudo make install", hide=hide)


@task
def install(c, dev=False, verbose=False):
    """
    install core
    """
    hide = not verbose
    os_info = get_os()
    install_system(c, os_info, hide)
    install_grpcio(c, hide)
    build(c, os_info, hide)
    install_core(c, hide)
    install_poetry(c, dev, hide)
    install_ospf_mdr(c, os_info, hide)
    print("please open a new terminal or re-login to leverage invoke for running core")
    print("# run daemon")
    print("inv daemon")
    print("# run gui")
    print("inv gui")


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
