"""
vnodeclient.py: implementation of the VnodeClient class for issuing commands
over a control channel to the vnoded process running in a network namespace.
The control channel can be accessed via calls to the vcmd Python module or
by invoking the vcmd shell command.
"""

import os

import vcmd

from core import constants
from core import logger

VCMD = os.path.join(constants.CORE_BIN_DIR, "vcmd")


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
        self.cmdchnl = vcmd.VCmd(self.ctrlchnlname)
        self._addr = {}

    def _verify_connection(self):
        """
        Checks that the vcmd client is properly connected.

        :return: nothing
        :raises ValueError: when not connected
        """
        if not self.connected():
            raise ValueError("vcmd not connected")

    def connected(self):
        """
        Check if node is connected or not.

        :return: True if connected, False otherwise
        :rtype: bool
        """
        return self.cmdchnl.connected()

    def close(self):
        """
        Close the client connection.

        :return: nothing
        """
        self.cmdchnl.close()

    def cmd(self, args, wait=True):
        """
        Execute a command on a node and return the status (return code).

        :param list args: command arguments
        :param bool wait: wait for command to end or not
        :return: command status
        :rtype: int
        """
        self._verify_connection()

        # run command, return process when not waiting
        p = self.cmdchnl.qcmd(args)
        if not wait:
            return p

        # wait for and return exit status
        status = p.wait()
        if status:
            logger.warn("cmd exited with status %s: %s", status, args)
        return status

    def cmdresult(self, args):
        """
        Execute a command on a node and return a tuple containing the
        exit status and result string. stderr output
        is folded into the stdout result string.

        :param list args: command arguments
        :return: command status and combined stdout and stderr output
        :rtype: tuple[int, str]
        """
        self._verify_connection()

        p, stdin, stdout, stderr = self.popen(args)
        output = stdout.read() + stderr.read()
        stdin.close()
        stdout.close()
        stderr.close()
        status = p.wait()

        return status, output

    def popen(self, args):
        """
        Execute a popen command against the node.

        :param list args: command arguments
        :return: popen object, stdin, stdout, and stderr
        :rtype: tuple
        """
        self._verify_connection()
        return self.cmdchnl.popen(args)

    def icmd(self, args):
        """
        Execute an icmd against a node.

        :param list args: command arguments
        :return: command result
        :rtype: int
        """
        return os.spawnlp(os.P_WAIT, VCMD, VCMD, "-c", self.ctrlchnlname, "--", *args)

    def redircmd(self, infd, outfd, errfd, args, wait=True):
        """
        Execute a command on a node with standard input, output, and
        error redirected according to the given file descriptors.

        :param infd: stdin file descriptor
        :param outfd: stdout file descriptor
        :param errfd: stderr file descriptor
        :param list args: command arguments
        :param bool wait: wait flag
        :return: command status
        :rtype: int
        """
        self._verify_connection()

        # run command, return process when not waiting
        p = self.cmdchnl.redircmd(infd, outfd, errfd, args)
        if not wait:
            return p

        # wait for and return exit status
        status = p.wait()
        if status:
            logger.warn("cmd exited with status %s: %s", status, args)
        return status

    def term(self, sh="/bin/sh"):
        """
        Open a terminal on a node.

        :param str sh: shell to open terminal with
        :return: terminal command result
        :rtype: int
        """
        cmd = ("xterm", "-ut", "-title", self.name, "-e", VCMD, "-c", self.ctrlchnlname, "--", sh)
        if "SUDO_USER" in os.environ:
            cmd = ("su", "-s", "/bin/sh", "-c",
                   "exec " + " ".join(map(lambda x: "'%s'" % x, cmd)),
                   os.environ["SUDO_USER"])
        return os.spawnvp(os.P_NOWAIT, cmd[0], cmd)

    def termcmdstring(self, sh="/bin/sh"):
        """
        Create a terminal command string.

        :param str sh: shell to execute command in
        :return: str
        """
        return "%s -c %s -- %s" % (VCMD, self.ctrlchnlname, sh)

    def shcmd(self, cmdstr, sh="/bin/sh"):
        """
        Execute a shell command.

        :param str cmdstr: command string
        :param str sh: shell to run command in
        :return: command result
        :rtype: int
        """
        return self.cmd([sh, "-c", cmdstr])

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
        cmd = [constants.IP_BIN, "addr", "show", "dev", ifname]
        p, stdin, stdout, stderr = self.popen(cmd)
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
                    logger.warn("unknown scope: %s" % line[3])

        err = stderr.read()
        stdout.close()
        stderr.close()
        status = p.wait()
        if status:
            logger.warn("nonzero exist status (%s) for cmd: %s", status, cmd)
        if err:
            logger.warn("error output: %s", err)
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
        cmd = ["cat", "/proc/net/dev"]
        p, stdin, stdout, stderr = self.popen(cmd)
        stdin.close()
        # ignore first line
        stdout.readline()
        # second line has count names
        tmp = stdout.readline().strip().split("|")
        rxkeys = tmp[1].split()
        txkeys = tmp[2].split()
        for line in stdout:
            line = line.strip().split()
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
            logger.warn("nonzero exist status (%s) for cmd: %s", status, cmd)
        if err:
            logger.warn("error output: %s", err)
        if ifname is not None:
            return stats[ifname]
        else:
            return stats
