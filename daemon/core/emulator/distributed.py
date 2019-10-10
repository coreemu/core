import logging
import os
import threading
from tempfile import NamedTemporaryFile

from invoke import UnexpectedExit

from core.errors import CoreCommandError

LOCK = threading.Lock()


def remote_cmd(server, cmd, env=None, cwd=None, wait=True):
    """
    Run command remotely using server connection.

    :param fabric.connection.Connection server: remote server node will run on,
        default is None for localhost
    :param str cmd: command to run
    :param dict env: environment for remote command, default is None
    :param str cwd: directory to run command in, defaults to None, which is the user's
        home directory
    :param bool wait: True to wait for status, False to background process
    :return: stdout when success
    :rtype: str
    :raises CoreCommandError: when a non-zero exit status occurs
    """

    replace_env = env is not None
    if not wait:
        cmd += " &"
    logging.info(
        "remote cmd server(%s) cwd(%s) wait(%s): %s", server.host, cwd, wait, cmd
    )
    try:
        with LOCK:
            if cwd is None:
                result = server.run(cmd, hide=False, env=env, replace_env=replace_env)
            else:
                with server.cd(cwd):
                    result = server.run(
                        cmd, hide=False, env=env, replace_env=replace_env
                    )
        return result.stdout.strip()
    except UnexpectedExit as e:
        stdout, stderr = e.streams_for_display()
        raise CoreCommandError(e.result.exited, cmd, stdout, stderr)


def remote_put(server, source, destination):
    with LOCK:
        server.put(source, destination)


def remote_put_temp(server, destination, data):
    with LOCK:
        temp = NamedTemporaryFile(delete=False)
        temp.write(data.encode("utf-8"))
        temp.close()
        server.put(temp.name, destination)
        os.unlink(temp.name)
