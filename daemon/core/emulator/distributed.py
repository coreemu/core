import logging

from core.errors import CoreCommandError


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
    if env is None:
        result = server.run(cmd, hide=False)
    else:
        result = server.run(cmd, hide=False, env=env, replace_env=True)
    if result.exited:
        raise CoreCommandError(
            result.exited, result.command, result.stdout, result.stderr
        )
    return result.stdout.strip()
