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


class OsInfo:
    def __init__(self, name: OsName, like: OsLike, version: str) -> None:
        self.name: OsName = name
        self.like: OsLike = like
        self.version: str = version


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
            key, value = line.split("=")
            d[key] = value.strip('"')
    name_value = d["ID"]
    like_value = d["ID_LIKE"]
    try:
        name = OsName(name_value)
        like = OsLike(like_value)
    except ValueError:
        print(f"unsupported os({name_value}) like({like_value})")
        sys.exit(1)
    version = d["VERSION_ID"]
    return OsInfo(name, like, version)


def install_system(c: Context, os_info: OsInfo) -> None:
    print("installing system dependencies...")
    if os_info.like == OsLike.DEBIAN:
        c.run(
            "sudo apt install -y automake pkg-config gcc libev-dev ebtables iproute2 "
            "ethtool tk python3-tk", hide=True
        )


def install_grpcio(c: Context) -> None:
    print("installing grpcio-tools...")
    c.run("python3 -m pip install --user grpcio-tools", hide=True)


def build(c: Context) -> None:
    print("building core...")
    c.run("./bootstrap.sh", hide=True)
    c.run("./configure", hide=True)
    c.run("make -j", hide=True)


def install_core(c: Context) -> None:
    print("installing vcmd...")
    with c.cd(VCMD_DIR):
        c.run("sudo make install", hide=True)
    print("installing gui...")
    with c.cd(GUI_DIR):
        c.run("sudo make install", hide=True)


def install_poetry(c: Context, dev: bool) -> None:
    print("installing poetry...")
    c.run("pipx install poetry", hide=True)
    args = "" if dev else "--no-dev"
    with c.cd(DAEMON_DIR):
        print("installing core environment using poetry...")
        c.run(f"poetry install {args}", hide=True)
        if dev:
            c.run("poetry run pre-commit install")


def install_ospf_mdr(c: Context, os_info: OsInfo) -> None:
    if c.run("which zebra"):
        print("quagga already installed, skipping ospf mdr")
        return
    if os_info.like == OsLike.DEBIAN:
        c.run("sudo apt install -y libtool gawk libreadline-dev")
    clone_dir = "/tmp/ospf-mdr"
    c.run(
        f"git clone https://github.com/USNavalResearchLaboratory/ospf-mdr {clone_dir}"
    )
    with c.cd(clone_dir):
        c.run("./bootstrap.sh")
        c.run(
            "./configure --disable-doc --enable-user=root --enable-group=root "
            "--with-cflags=-ggdb --sysconfdir=/usr/local/etc/quagga --enable-vtysh "
            "--localstatedir=/var/run/quagga"
        )
        c.run("make -j")
        c.run("sudo make install")


@task
def install(c, dev=False):
    """
    install core
    """
    os_info = get_os()
    install_system(c, os_info)
    install_grpcio(c)
    build(c)
    install_core(c)
    install_poetry(c, dev)
    install_ospf_mdr(c, os_info)


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
