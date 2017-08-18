"""
netgraph.py: Netgraph helper functions; for now these are wrappers around
ngctl commands.
"""

import subprocess

from core import constants
from core.misc import utils

utils.check_executables([constants.NGCTL_BIN])


def createngnode(node_type, hookstr, name=None):
    """
    Create a new Netgraph node of type and optionally assign name. The
    hook string hookstr should contain two names. This is a string so
    other commands may be inserted after the two names.
    Return the name and netgraph ID of the new node.

    :param node_type: node type to create
    :param hookstr: hook string
    :param name: name
    :return: name and id
    :rtype: tuple
    """
    hook1 = hookstr.split()[0]
    ngcmd = "mkpeer %s %s \n show .%s" % (node_type, hookstr, hook1)
    cmd = [constants.NGCTL_BIN, "-f", "-"]
    cmdid = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    # err will always be None
    result, err = cmdid.communicate(input=ngcmd)
    status = cmdid.wait()
    if status > 0:
        raise Exception("error creating Netgraph node %s (%s): %s" % (node_type, ngcmd, result))
    results = result.split()
    ngname = results[1]
    ngid = results[5]
    if name:
        subprocess.check_call([constants.NGCTL_BIN, "name", "[0x%s]:" % ngid, name])
    return ngname, ngid


def destroyngnode(name):
    """
    Shutdown a Netgraph node having the given name.

    :param str name: node name
    :return: nothing
    """
    subprocess.check_call([constants.NGCTL_BIN, "shutdown", "%s:" % name])


def connectngnodes(name1, name2, hook1, hook2):
    """
    Connect two hooks of two Netgraph nodes given by their names.

    :param str name1: name one
    :param str name2: name two
    :param str hook1: hook one
    :param str hook2: hook two
    :return: nothing
    """
    node1 = "%s:" % name1
    node2 = "%s:" % name2
    subprocess.check_call([constants.NGCTL_BIN, "connect", node1, node2, hook1, hook2])


def ngmessage(name, msg):
    """
    Send a Netgraph message to the node named name.

    :param str name: node name
    :param list msg: message
    :return: nothing
    """
    cmd = [constants.NGCTL_BIN, "msg", "%s:" % name] + msg
    subprocess.check_call(cmd)


def ngloadkernelmodule(name):
    """
    Load a kernel module by invoking kldstat. This is needed for the
    ng_ether module which automatically creates Netgraph nodes when loaded.

    :param str name: module name
    :return: nothing
    """
    utils.mutecall(["kldload", name])
