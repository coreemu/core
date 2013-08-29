#
# CORE
# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Tom Goff <thomas.goff@boeing.com>
#
'''
vnodeclient.py: implementation of the VnodeClient class for issuing commands
over a control channel to the vnoded process running in a network namespace.
The control channel can be accessed via calls to the vcmd Python module or
by invoking the vcmd shell command.
'''

import os, stat, sys
from core.constants import *

USE_VCMD_MODULE = True

if USE_VCMD_MODULE:
    import vcmd
else:
    import subprocess

VCMD = os.path.join(CORE_SBIN_DIR, "vcmd")

class VnodeClient(object):
    def __init__(self, name, ctrlchnlname):
        self.name = name
        self.ctrlchnlname = ctrlchnlname
        if USE_VCMD_MODULE:
            self.cmdchnl = vcmd.VCmd(self.ctrlchnlname)
        else:
            self.cmdchnl = None
        self._addr = {}

    def warn(self, msg):
        print >> sys.stderr, "%s: %s" % (self.name, msg)

    def connected(self):
        if USE_VCMD_MODULE:
            return self.cmdchnl.connected()
        else:
            return True

    def cmd(self, args, wait = True):
        ''' Execute a command on a node and return the status (return code).
        '''
        if USE_VCMD_MODULE:
            if not self.cmdchnl.connected():
                raise ValueError, "self.cmdchnl not connected"
            tmp = self.cmdchnl.qcmd(args)
            if not wait:
                return tmp
            tmp = tmp.wait()
        else:
            if wait:
                mode = os.P_WAIT
            else:
                mode = os.P_NOWAIT
            tmp = os.spawnlp(mode, VCMD, VCMD, "-c",
                             self.ctrlchnlname, "-q", "--", *args)
            if not wait:
                return tmp
        if tmp:
            self.warn("cmd exited with status %s: %s" % (tmp, str(args)))
        return tmp

    def cmdresult(self, args):
        ''' Execute a command on a node and return a tuple containing the
            exit status and result string. stderr output
            is folded into the stdout result string.
        '''
        cmdid, cmdin, cmdout, cmderr = self.popen(args)
        result = cmdout.read()
        result += cmderr.read()
        cmdin.close()
        cmdout.close()
        cmderr.close()
        status = cmdid.wait()
        return (status, result)

    def popen(self, args):
        if USE_VCMD_MODULE:
            if not self.cmdchnl.connected():
                raise ValueError, "self.cmdchnl not connected"
            return self.cmdchnl.popen(args)
        else:
            cmd = [VCMD, "-c", self.ctrlchnlname, "--"]
            cmd.extend(args)
            tmp = subprocess.Popen(cmd, stdin = subprocess.PIPE,
                                   stdout = subprocess.PIPE,
                                   stderr = subprocess.PIPE)
            return tmp, tmp.stdin, tmp.stdout, tmp.stderr

    def icmd(self, args):
        return os.spawnlp(os.P_WAIT, VCMD, VCMD, "-c", self.ctrlchnlname,
                          "--", *args)

    def redircmd(self, infd, outfd, errfd, args, wait = True):
        '''
        Execute a command on a node with standard input, output, and
        error redirected according to the given file descriptors.
        '''
        if not USE_VCMD_MODULE:
            raise NotImplementedError
        if not self.cmdchnl.connected():
            raise ValueError, "self.cmdchnl not connected"
        tmp = self.cmdchnl.redircmd(infd, outfd, errfd, args)
        if not wait:
            return tmp
        tmp = tmp.wait()
        if tmp:
            self.warn("cmd exited with status %s: %s" % (tmp, str(args)))
        return tmp

    def term(self, sh = "/bin/sh"):
        return os.spawnlp(os.P_NOWAIT, "xterm", "xterm", "-ut",
                          "-title", self.name, "-e",
                          VCMD, "-c", self.ctrlchnlname, "--", sh)

    def termcmdstring(self, sh = "/bin/sh"):
        return "%s -c %s -- %s" % (VCMD, self.ctrlchnlname, sh)

    def shcmd(self, cmdstr, sh = "/bin/sh"):
        return self.cmd([sh, "-c", cmdstr])

    def getaddr(self, ifname, rescan = False):
        if ifname in self._addr and not rescan:
            return self._addr[ifname]
        tmp = {"ether": [], "inet": [], "inet6": [], "inet6link": []}
        cmd = [IP_BIN, "addr", "show", "dev", ifname]
        cmdid, cmdin, cmdout, cmderr = self.popen(cmd)
        cmdin.close()
        for line in cmdout:
            line = line.strip().split()
            if line[0] == "link/ether":
                tmp["ether"].append(line[1])
            elif line[0] == "inet":
                tmp["inet"].append(line[1])
            elif line[0] == "inet6":
                if line[3] == "global":
                    tmp["inet6"].append(line[1])
                elif line[3] == "link":
                    tmp["inet6link"].append(line[1])
                else:
                    self.warn("unknown scope: %s" % line[3])
            else:
                pass
        err = cmderr.read()
        cmdout.close()
        cmderr.close()
        status = cmdid.wait()
        if status:
            self.warn("nonzero exist status (%s) for cmd: %s" % (status, cmd))
        if err:
            self.warn("error output: %s" % err)
        self._addr[ifname] = tmp
        return tmp

    def netifstats(self, ifname = None):
        stats = {}
        cmd = ["cat", "/proc/net/dev"]
        cmdid, cmdin, cmdout, cmderr = self.popen(cmd)
        cmdin.close()
        # ignore first line
        cmdout.readline()
        # second line has count names
        tmp = cmdout.readline().strip().split("|")
        rxkeys = tmp[1].split()
        txkeys = tmp[2].split()
        for line in cmdout:
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
        err = cmderr.read()
        cmdout.close()
        cmderr.close()
        status = cmdid.wait()
        if status:
            self.warn("nonzero exist status (%s) for cmd: %s" % (status, cmd))
        if err:
            self.warn("error output: %s" % err)
        if ifname is not None:
            return stats[ifname]
        else:
            return stats

def createclients(sessiondir, clientcls = VnodeClient,
                  cmdchnlfilterfunc = None):
    direntries = map(lambda x: os.path.join(sessiondir, x),
                     os.listdir(sessiondir))
    cmdchnls = filter(lambda x: stat.S_ISSOCK(os.stat(x).st_mode), direntries)
    if cmdchnlfilterfunc:
        cmdchnls = filter(cmdchnlfilterfunc, cmdchnls)
    cmdchnls.sort()
    return map(lambda x: clientcls(os.path.basename(x), x), cmdchnls)

def createremoteclients(sessiondir, clientcls = VnodeClient,
                  filterfunc = None):
    ''' Creates remote VnodeClients, for nodes emulated on other machines. The
    session.Broker writes a n1.conf/server file having the server's info.
    '''
    direntries = map(lambda x: os.path.join(sessiondir, x),
                     os.listdir(sessiondir))
    nodedirs = filter(lambda x: stat.S_ISDIR(os.stat(x).st_mode), direntries)
    nodedirs = filter(lambda x: os.path.exists(os.path.join(x, "server")), 
                      nodedirs)
    if filterfunc:
        nodedirs = filter(filterfunc, nodedirs)
    nodedirs.sort()
    return map(lambda x: clientcls(x), nodedirs)
