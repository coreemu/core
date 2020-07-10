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
            "ethtool tk python3-tk", hide=hide
        )


def install_grpcio(c: Context, os_info: OsInfo, hide: bool) -> None:
    print("installing grpcio-tools...")
    if os_info.like == OsLike.REDHAT:
        c.run("sudo yum install -y python3-devel", hide=hide)
    c.run("python3 -m pip install --user grpcio-tools", hide=hide)


def build(c: Context, hide: bool) -> None:
    print("building core...")
    c.run("./bootstrap.sh", hide=hide)
    c.run("./configure", hide=hide)
    c.run("make", hide=hide)


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
            c.run("poetry run pre-commit install")


def install_ospf_mdr(c: Context, os_info: OsInfo, hide: bool) -> None:
    if c.run("which zebra", warn=True, hide=hide):
        print("quagga already installed, skipping ospf mdr")
        return
    print("installing ospf mdr dependencies...")
    if os_info.like == OsLike.DEBIAN:
        c.run("sudo apt install -y libtool gawk libreadline-dev", hide=hide)
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
        c.run("make", hide=hide)
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
    install_grpcio(c, os_info, hide)
    build(c, hide)
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
