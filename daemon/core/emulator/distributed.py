"""
Defines distributed server functionality.
"""

import logging
import os
import threading
from tempfile import NamedTemporaryFile

from fabric import Connection
from invoke import UnexpectedExit

from core.errors import CoreCommandError

LOCK = threading.Lock()


class DistributedServer(object):
    """
    Provides distributed server interactions.
    """

    def __init__(self, name, host):
        """
        Create a DistributedServer instance.

        :param str name: convenience name to associate with host
        :param str host: host to connect to
        """
        self.name = name
        self.host = host
        self.conn = Connection(host, user="root")
        self.lock = threading.Lock()

    def remote_cmd(self, cmd, env=None, cwd=None, wait=True):
        """
        Run command remotely using server connection.

        :param str cmd: command to run
        :param dict env: environment for remote command, default is None
        :param str cwd: directory to run command in, defaults to None, which is the
            user's home directory
        :param bool wait: True to wait for status, False to background process
        :return: stdout when success
        :rtype: str
        :raises CoreCommandError: when a non-zero exit status occurs
        """

        replace_env = env is not None
        if not wait:
            cmd += " &"
        logging.info(
            "remote cmd server(%s) cwd(%s) wait(%s): %s", self.host, cwd, wait, cmd
        )
        try:
            if cwd is None:
                result = self.conn.run(
                    cmd, hide=False, env=env, replace_env=replace_env
                )
            else:
                with self.conn.cd(cwd):
                    result = self.conn.run(
                        cmd, hide=False, env=env, replace_env=replace_env
                    )
            return result.stdout.strip()
        except UnexpectedExit as e:
            stdout, stderr = e.streams_for_display()
            raise CoreCommandError(e.result.exited, cmd, stdout, stderr)

    def remote_put(self, source, destination):
        """
        Push file to remote server.

        :param str source: source file to push
        :param str destination: destination file location
        :return: nothing
        """
        with self.lock:
            self.conn.put(source, destination)

    def remote_put_temp(self, destination, data):
        """
        Remote push file contents to a remote server, using a temp file as an
        intermediate step.

        :param str destination: file destination for data
        :param str data: data to store in remote file
        :return: nothing
        """
        with self.lock:
            temp = NamedTemporaryFile(delete=False)
            temp.write(data.encode("utf-8"))
            temp.close()
            self.conn.put(temp.name, destination)
            os.unlink(temp.name)
