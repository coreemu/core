from invoke import task


@task
def core(c):
    c.run(
        "poetry run sudo python3 scripts/core-daemon "
        "-f data/core.conf -l data/logging.conf"
    )


@task
def core_pygui(c):
    c.run("poetry run python3 scripts/core-pygui")
