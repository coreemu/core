"""
client.py: implementation of the VnodeClient class for issuing commands
over a control channel to the vnoded process running in a network namespace.
The control channel can be accessed via calls using the vcmd shell.
"""

import logging
import os
from subprocess import PIPE, Popen

from core import constants, utils
from core.errors import CoreCommandError


class VnodeClient(object):
    """
    Provides client functionality for interacting with a virtual node.
    """

    def __init__(self, name, ctrlchnlname):
        """
        Create a VnodeClient instance.

        :param str name: name for client
        :param str ctrlchnlname: control channel name
        """
        self.name = name
        self.ctrlchnlname = ctrlchnlname

    def _verify_connection(self):
        """
        Checks that the vcmd client is properly connected.

        :return: nothing
        :raises IOError: when not connected
        """
        if not self.connected():
            raise IOError("vcmd not connected")

    def connected(self):
        """
        Check if node is connected or not.

        :return: True if connected, False otherwise
        :rtype: bool
        """
        return True

    def close(self):
        """
        Close the client connection.

        :return: nothing
        """
        pass

    def _cmd_args(self):
        return [constants.VCMD_BIN, "-c", self.ctrlchnlname, "--"]

    def check_cmd(self, args, wait=True):
        """
        Run command and return exit status and combined stdout and stderr.

        :param list[str]|str args: command to run
        :param bool wait: True to wait for command status, False otherwise
        :return: combined stdout and stderr
        :rtype: str
        :raises core.CoreCommandError: when there is a non-zero exit status
        """
        p, stdin, stdout, stderr = self.popen(args)
        stdin.close()
        output = stdout.read() + stderr.read()
        output = output.decode("utf-8").strip()
        stdout.close()
        stderr.close()
        status = p.wait()
        if wait and status != 0:
            raise CoreCommandError(status, args, output)
        return output

    def popen(self, args):
        """
        Execute a popen command against the node.

        :param list[str]|str args: command arguments
        :return: popen object, stdin, stdout, and stderr
        :rtype: tuple
        """
        self._verify_connection()
        args = utils.split_args(args)
        cmd = self._cmd_args() + args
        logging.debug("popen: %s", cmd)
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, stdin=PIPE)
        return p, p.stdin, p.stdout, p.stderr

    def icmd(self, args):
        """
        Execute an icmd against a node.

        :param list[str]|str args: command arguments
        :return: command result
        :rtype: int
        """
        args = utils.split_args(args)
        return os.spawnlp(
            os.P_WAIT,
            constants.VCMD_BIN,
            constants.VCMD_BIN,
            "-c",
            self.ctrlchnlname,
            "--",
            *args
        )

    def term(self, sh="/bin/sh"):
        """
        Open a terminal on a node.

        :param str sh: shell to open terminal with
        :return: terminal command result
        :rtype: int
        """
        args = (
            "xterm",
            "-ut",
            "-title",
            self.name,
            "-e",
            constants.VCMD_BIN,
            "-c",
            self.ctrlchnlname,
            "--",
            sh,
        )
        if "SUDO_USER" in os.environ:
            args = (
                "su",
                "-s",
                "/bin/sh",
                "-c",
                "exec " + " ".join(map(lambda x: "'%s'" % x, args)),
                os.environ["SUDO_USER"],
            )
        return os.spawnvp(os.P_NOWAIT, args[0], args)

    def termcmdstring(self, sh="/bin/sh"):
        """
        Create a terminal command string.

        :param str sh: shell to execute command in
        :return: str
        """
        return "%s -c %s -- %s" % (constants.VCMD_BIN, self.ctrlchnlname, sh)
