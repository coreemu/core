#
# CORE
# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: core-dev@pf.itd.nrl.navy.mil 
#
'''
netgraph.py: Netgraph helper functions; for now these are wrappers around
ngctl commands.
'''

import subprocess
from core.misc.utils import *
from core.constants import *

checkexec([NGCTL_BIN])

def createngnode(type, hookstr, name=None):
    ''' Create a new Netgraph node of type and optionally assign name. The
        hook string hookstr should contain two names. This is a string so
        other commands may be inserted after the two names.
        Return the name and netgraph ID of the new node.
    '''
    hook1 = hookstr.split()[0]
    ngcmd = "mkpeer %s %s \n show .%s" % (type, hookstr, hook1)
    cmd = [NGCTL_BIN, "-f", "-"]
    cmdid = subprocess.Popen(cmd, stdin = subprocess.PIPE,
                             stdout = subprocess.PIPE,
                             stderr = subprocess.PIPE)
    cmdid.stdin.write(ngcmd)
    cmdid.stdin.close()
    result = cmdid.stdout.read()
    result += cmdid.stderr.read()
    cmdid.stdout.close()
    cmdid.stderr.close()
    status = cmdid.wait()
    if status > 0:
        raise Exception, "error creating Netgraph node %s (%s): %s" % \
            (type, ngcmd, result)
    results = result.split()
    ngname = results[1]
    ngid = results[5]
    if name:
        check_call([NGCTL_BIN, "name", "[0x%s]:" % ngid, name])
    return (ngname, ngid)

def destroyngnode(name):
    ''' Shutdown a Netgraph node having the given name.
    '''
    check_call([NGCTL_BIN, "shutdown", "%s:" % name])

def connectngnodes(name1, name2, hook1, hook2):
    ''' Connect two hooks of two Netgraph nodes given by their names.
    '''
    node1 = "%s:" % name1
    node2 = "%s:" % name2
    check_call([NGCTL_BIN, "connect", node1, node2, hook1, hook2])

def ngmessage(name, msg):
    ''' Send a Netgraph message to the node named name.
    '''
    cmd = [NGCTL_BIN, "msg", "%s:" % name] + msg
    check_call(cmd)

def ngloadkernelmodule(name):
    ''' Load a kernel module by invoking kldstat. This is needed for the 
        ng_ether module which automatically creates Netgraph nodes when loaded.
    '''
    mutecall(["kldload", name])
