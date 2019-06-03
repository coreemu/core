"""
client.py: implementation of the VnodeClient class for issuing commands
over a control channel to the vnoded process running in a network namespace.
The control channel can be accessed via calls to the vcmd Python module or
by invoking the vcmd shell command.
"""

import logging
import os

from subprocess import Popen, PIPE

from core import CoreCommandError, utils
from core import constants


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
        self._addr = {}

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

    def cmd(self, args, wait=True):
        """
        Execute a command on a node and return the status (return code).

        :param list[str]|str args: command arguments
        :param bool wait: wait for command to end or not
        :return: command status
        :rtype: int
        """
        self._verify_connection()
        args = utils.split_args(args)

        # run command, return process when not waiting
        cmd = self._cmd_args() + args
        logging.info("cmd wait(%s): %s", wait, cmd)
        p = Popen(cmd, stdout=PIPE, stderr=PIPE)
        if not wait:
            return 0

        # wait for and return exit status
        return p.wait()

    def cmd_output(self, args):
        """
        Execute a command on a node and return a tuple containing the
        exit status and result string. stderr output
        is folded into the stdout result string.

        :param list[str]|str args: command to run
        :return: command status and combined stdout and stderr output
        :rtype: tuple[int, str]
        """
        p, stdin, stdout, stderr = self.popen(args)
        stdin.close()
        output = stdout.read() + stderr.read()
        stdout.close()
        stderr.close()
        status = p.wait()
        return status, output.decode("utf-8").strip()

    def check_cmd(self, args):
        """
        Run command and return exit status and combined stdout and stderr.

        :param list[str]|str args: command to run
        :return: combined stdout and stderr
        :rtype: str
        :raises core.CoreCommandError: when there is a non-zero exit status
        """
        status, output = self.cmd_output(args)
        if status != 0:
            raise CoreCommandError(status, args, output)
        return output.strip()

    def popen(self, args):
        """
        Execute a popen command against the node.

        :param list[str]|str args: command arguments
        :return: popen object, stdin, stdout, and stderr
        :rtype: tuple
        """
        self._verify_connection()
        args = utils.split_args(args)
        # if isinstance(args, list):
        #     args = " ".join(args)
        cmd = self._cmd_args() + args
        logging.info("popen: %s", cmd)
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
        return os.spawnlp(os.P_WAIT, constants.VCMD_BIN, constants.VCMD_BIN, "-c", self.ctrlchnlname, "--", *args)

    def redircmd(self, infd, outfd, errfd, args, wait=True):
        """
        Execute a command on a node with standard input, output, and
        error redirected according to the given file descriptors.

        :param infd: stdin file descriptor
        :param outfd: stdout file descriptor
        :param errfd: stderr file descriptor
        :param list[str]|str args: command arguments
        :param bool wait: wait flag
        :return: command status
        :rtype: int
        """
        self._verify_connection()

        # run command, return process when not waiting
        args = utils.split_args(args)
        cmd = self._cmd_args() + args
        logging.info("redircmd: %s", cmd)
        p = Popen(cmd, stdin=infd, stdout=outfd, stderr=errfd)

        if not wait:
            return p

        # wait for and return exit status
        status = p.wait()
        if status:
            logging.warning("cmd exited with status %s: %s", status, args)
        return status

    def term(self, sh="/bin/sh"):
        """
        Open a terminal on a node.

        :param str sh: shell to open terminal with
        :return: terminal command result
        :rtype: int
        """
        args = ("xterm", "-ut", "-title", self.name, "-e", constants.VCMD_BIN, "-c", self.ctrlchnlname, "--", sh)
        if "SUDO_USER" in os.environ:
            args = ("su", "-s", "/bin/sh", "-c",
                    "exec " + " ".join(map(lambda x: "'%s'" % x, args)),
                    os.environ["SUDO_USER"])
        return os.spawnvp(os.P_NOWAIT, args[0], args)

    def termcmdstring(self, sh="/bin/sh"):
        """
        Create a terminal command string.

        :param str sh: shell to execute command in
        :return: str
        """
        return "%s -c %s -- %s" % (constants.VCMD_BIN, self.ctrlchnlname, sh)

    def shcmd(self, cmd, sh="/bin/sh"):
        """
        Execute a shell command.

        :param str cmd: command string
        :param str sh: shell to run command in
        :return: command result
        :rtype: int
        """
        return self.cmd([sh, "-c", cmd])

    def shcmd_result(self, cmd, sh="/bin/sh"):
        """
        Execute a shell command and return the exist status and combined output.

        :param str cmd: shell command to run
        :param str sh: shell to run command in
        :return: exist status and combined output
        :rtype: tuple[int, str]
        """
        return self.cmd_output([sh, "-c", cmd])

    def getaddr(self, ifname, rescan=False):
        """
        Get address for interface on node.

        :param str ifname: interface name to get address for
        :param bool rescan: rescan flag
        :return: interface information
        :rtype: dict
        """
        if ifname in self._addr and not rescan:
            return self._addr[ifname]

        interface = {"ether": [], "inet": [], "inet6": [], "inet6link": []}
        args = [constants.IP_BIN, "addr", "show", "dev", ifname]
        p, stdin, stdout, stderr = self.popen(args)
        stdin.close()

        for line in stdout:
            line = line.strip().split()
            if line[0] == "link/ether":
                interface["ether"].append(line[1])
            elif line[0] == "inet":
                interface["inet"].append(line[1])
            elif line[0] == "inet6":
                if line[3] == "global":
                    interface["inet6"].append(line[1])
                elif line[3] == "link":
                    interface["inet6link"].append(line[1])
                else:
                    logging.warning("unknown scope: %s" % line[3])

        err = stderr.read()
        stdout.close()
        stderr.close()
        status = p.wait()
        if status:
            logging.warning("nonzero exist status (%s) for cmd: %s", status, args)
        if err:
            logging.warning("error output: %s", err)
        self._addr[ifname] = interface
        return interface

    def netifstats(self, ifname=None):
        """
        Retrieve network interface state.

        :param str ifname: name of interface to get state for
        :return: interface state information
        :rtype: dict
        """
        stats = {}
        args = ["cat", "/proc/net/dev"]
        p, stdin, stdout, stderr = self.popen(args)
        stdin.close()
        # ignore first line
        stdout.readline()
        # second line has count names
        tmp = stdout.readline().decode("utf-8").strip().split("|")
        rxkeys = tmp[1].split()
        txkeys = tmp[2].split()
        for line in stdout:
            line = line.decode("utf-8").strip().split()
            devname, tmp = line[0].split(":")
            if tmp:
                line.insert(1, tmp)
            stats[devname] = {"rx": {}, "tx": {}}
            field = 1
            for count in rxkeys:
                stats[devname]["rx"][count] = int(line[field])
                field += 1
            for count in txkeys:
                stats[devname]["tx"][count] = int(line[field])
                field += 1
        err = stderr.read()
        stdout.close()
        stderr.close()
        status = p.wait()
        if status:
            logging.warning("nonzero exist status (%s) for cmd: %s", status, args)
        if err:
            logging.warning("error output: %s", err)
        if ifname is not None:
            return stats[ifname]
        else:
            return stats
