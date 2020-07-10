import os

from invoke import task

UBUNTU = "ubuntu"
CENTOS = "centos"
DAEMON_DIR = "daemon"
VCMD_DIR = "netns"
GUI_DIR = "gui"


def get_python(c):
    with c.cd(DAEMON_DIR):
        venv = c.run("poetry env info -p", hide=True).stdout.strip()
        return os.path.join(venv, "bin", "python")


def get_pytest(c):
    with c.cd(DAEMON_DIR):
        venv = c.run("poetry env info -p", hide=True).stdout.strip()
        return os.path.join(venv, "bin", "pytest")


def get_os():
    d = {}
    with open("/etc/os-release", "r") as f:
        for line in f.readlines():
            line = line.strip()
            key, value = line.split("=")
            d[key] = value
    return d["ID"]


@task
def install(c):
    """
    install core
    """
    # get os
    os_name = get_os()
    # install system dependencies
    print("installing system dependencies...")
    if os_name == UBUNTU:
        c.run(
            "sudo apt install -y automake pkg-config gcc libev-dev ebtables iproute2 "
            "ethtool tk python3-tk", hide=True
        )
    else:
        raise Exception(f"unsupported os: {os_name}")
    # install grpcio-tools for building proto files
    print("installing grpcio-tools...")
    c.run("python3 -m pip install --user grpcio-tools", hide=True)
    # build core
    print("building core...")
    c.run("./bootstrap.sh", hide=True)
    c.run("./configure", hide=True)
    c.run("make -j", hide=True)
    # install vcmd
    print("installing vcmd...")
    with c.cd(VCMD_DIR):
        c.run("sudo make install", hide=True)
    # install vcmd
    print("installing gui...")
    with c.cd(GUI_DIR):
        c.run("sudo make install", hide=True)
    # install poetry environment
    print("installing poetry...")
    c.run("pipx install poetry", hide=True)
    with c.cd(DAEMON_DIR):
        print("installing core environment using poetry...")
        c.run("poetry install", hide=True)


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
