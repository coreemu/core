from invoke import task


@task
def daemon(c):
    """
    Runs core-daemon.
    """
    with c.cd("daemon"):
        poetry = c.run("which poetry").stdout.strip()
        c.run(
            f"sudo {poetry} run scripts/core-daemon "
            "-f data/core.conf -l data/logging.conf"
        )


@task
def gui(c):
    """
    Run core-pygui.
    """
    with c.cd("daemon"):
        c.run("poetry run scripts/core-pygui")


@task
def test(c):
    """
    Run core tests.
    """
    with c.cd("daemon"):
        poetry = c.run("which poetry").stdout.strip()
        c.run(f"sudo {poetry} run pytest -v --lf -x tests", pty=True)


@task
def test_mock(c):
    """
    Run core tests using mock to avoid running as sudo.
    """
    with c.cd("daemon"):
        c.run("poetry run pytest -v --mock --lf -x tests", pty=True)


@task
def test_emane(c):
    """
    Run core emane tests.
    """
    with c.cd("daemon"):
        poetry = c.run("which poetry").stdout.strip()
        c.run(f"sudo {poetry} run pytest -v --lf -x tests/emane", pty=True)
