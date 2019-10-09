import logging
import threading

from core.errors import CoreCommandError

LOCK = threading.Lock()


def remote_cmd(server, cmd, env=None):
    """
    Run command remotely using server connection.

    :param fabric.connection.Connection server: remote server node will run on,
        default is None for localhost
    :param str cmd: command to run
    :param dict env: environment for remote command, default is None
    :return: stdout when success
    :rtype: str
    :raises CoreCommandError: when a non-zero exit status occurs
    """
    logging.info("remote cmd server(%s): %s", server, cmd)
    with LOCK:
        if env is None:
            result = server.run(cmd, hide=False)
        else:
            result = server.run(cmd, hide=False, env=env, replace_env=True)
    if result.exited:
        raise CoreCommandError(
            result.exited, result.command, result.stdout, result.stderr
        )
    return result.stdout.strip()


def remote_put(server, source, destination):
    with LOCK:
        server.put(source, destination)
