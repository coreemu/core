#
# CORE
# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: core-dev@pf.itd.nrl.navy.mil 
#
'''
vnode.py: SimpleJailNode and JailNode classes that implement the FreeBSD
jail-based virtual node.
'''

import os, signal, sys, subprocess, threading, string
import random, time
from core.misc.utils import *
from core.constants import *
from core.coreobj import PyCoreObj, PyCoreNode, PyCoreNetIf, Position
from core.emane.nodes import EmaneNode
from core.bsd.netgraph import *

checkexec([IFCONFIG_BIN, VIMAGE_BIN])

class VEth(PyCoreNetIf):
    def __init__(self, node, name, localname, mtu = 1500, net = None,
                 start = True):
        PyCoreNetIf.__init__(self, node = node, name = name, mtu = mtu)
        # name is the device name (e.g. ngeth0, ngeth1, etc.) before it is
        # installed in a node; the Netgraph name is renamed to localname
        # e.g. before install: name = ngeth0 localname = n0_0_123
        #      after install:  name = eth0   localname = n0_0_123
        self.localname = localname
        self.ngid = None
        self.net = None
        self.pipe = None
        self.addrlist = []
        self.hwaddr = None
        self.up = False
        self.hook = "ether"
        if start:
            self.startup()

    def startup(self):
        hookstr = "%s %s" % (self.hook, self.hook)
        ngname, ngid = createngnode(type="eiface", hookstr=hookstr,
                                    name=self.localname)
        self.name = ngname
        self.ngid = ngid
        check_call([IFCONFIG_BIN, ngname, "up"])
        self.up = True

    def shutdown(self):
        if not self.up:
            return
        destroyngnode(self.localname)
        self.up = False

    def attachnet(self, net):
        if self.net:
            self.detachnet()
            self.net = None
        net.attach(self)
        self.net = net

    def detachnet(self):
        if self.net is not None:
            self.net.detach(self)

    def addaddr(self, addr):
        self.addrlist.append(addr)

    def deladdr(self, addr):
        self.addrlist.remove(addr)

    def sethwaddr(self, addr):
        self.hwaddr = addr

class TunTap(PyCoreNetIf):
    '''TUN/TAP virtual device in TAP mode'''
    def __init__(self, node, name, localname, mtu = None, net = None,
                 start = True):
        raise NotImplementedError

class SimpleJailNode(PyCoreNode):
    def __init__(self, session, objid = None, name = None, nodedir = None,
                 verbose = False):
        PyCoreNode.__init__(self, session, objid, name)
        self.nodedir = nodedir
        self.verbose = verbose
        self.pid = None
        self.up = False
        self.lock = threading.RLock()
        self._mounts = []

    def startup(self):
        if self.up:
            raise Exception, "already up"
        vimg = [VIMAGE_BIN, "-c", self.name]
        try:
            os.spawnlp(os.P_WAIT, VIMAGE_BIN, *vimg)
        except OSError:
            raise Exception, ("vimage command not found while running: %s" % \
                    vimg)
        self.info("bringing up loopback interface")
        self.cmd([IFCONFIG_BIN, "lo0", "127.0.0.1"])
        self.info("setting hostname: %s" % self.name)
        self.cmd(["hostname", self.name])
        self.cmd([SYSCTL_BIN, "vfs.morphing_symlinks=1"])
        self.up = True

    def shutdown(self):
        if not self.up:
            return
        for netif in self.netifs():
            netif.shutdown()
        self._netif.clear()
        del self.session
        vimg = [VIMAGE_BIN, "-d", self.name]
        try:
            os.spawnlp(os.P_WAIT, VIMAGE_BIN, *vimg)
        except OSError:
            raise Exception, ("vimage command not found while running: %s" % \
                    vimg)
        self.up = False

    def cmd(self, args, wait = True):
        if wait:
            mode = os.P_WAIT
        else:
            mode = os.P_NOWAIT
        tmp = call([VIMAGE_BIN, self.name] + args, cwd=self.nodedir)
        if not wait:
            tmp = None
        if tmp:
            self.warn("cmd exited with status %s: %s" % (tmp, str(args)))
        return tmp

    def cmdresult(self, args, wait = True):
        cmdid, cmdin, cmdout, cmderr = self.popen(args)
        result = cmdout.read()
        result += cmderr.read()
        cmdin.close()
        cmdout.close()
        cmderr.close()
        if wait:
            status = cmdid.wait()
        else:
            status = 0
        return (status, result)

    def popen(self, args):
        cmd = [VIMAGE_BIN, self.name]
        cmd.extend(args)
        tmp = subprocess.Popen(cmd, stdin = subprocess.PIPE,
                                stdout = subprocess.PIPE,
                                stderr = subprocess.PIPE, cwd=self.nodedir)
        return tmp, tmp.stdin, tmp.stdout, tmp.stderr

    def icmd(self, args):
        return os.spawnlp(os.P_WAIT, VIMAGE_BIN, VIMAGE_BIN, self.name, *args) 

    def term(self, sh = "/bin/sh"):
        return os.spawnlp(os.P_WAIT, "xterm", "xterm", "-ut", 
                        "-title", self.name, "-e", VIMAGE_BIN, self.name, sh) 

    def termcmdstring(self, sh = "/bin/sh"):
        ''' We add 'sudo' to the command string because the GUI runs as a
            normal user.
        '''
        return "cd %s && sudo %s %s %s" % (self.nodedir, VIMAGE_BIN, self.name, sh)

    def shcmd(self, cmdstr, sh = "/bin/sh"):
        return self.cmd([sh, "-c", cmdstr])

    def boot(self):
        pass

    def mount(self, source, target):
        source = os.path.abspath(source)
        self.info("mounting %s at %s" % (source, target))
        self.addsymlink(path=target, file=None)

    def umount(self, target):
        self.info("unmounting '%s'" % target)

    def newveth(self, ifindex = None, ifname = None, net = None):
        self.lock.acquire()
        try:
            if ifindex is None:
                ifindex = self.newifindex()
            if ifname is None:
                ifname = "eth%d" % ifindex
            sessionid = self.session.shortsessionid()
            name = "n%s_%s_%s" % (self.objid, ifindex, sessionid)
            localname = name 
            ifclass = VEth
            veth = ifclass(node = self, name = name, localname = localname,
                           mtu = 1500, net = net, start = self.up)
            if self.up:
                # install into jail
                check_call([IFCONFIG_BIN, veth.name, "vnet", self.name])
                # rename from "ngeth0" to "eth0"
                self.cmd([IFCONFIG_BIN, veth.name, "name", ifname])
            veth.name = ifname
            try:
                self.addnetif(veth, ifindex)
            except:
                veth.shutdown()
                del veth
                raise
            return ifindex
        finally:
            self.lock.release()

    def sethwaddr(self, ifindex, addr):
        self._netif[ifindex].sethwaddr(addr)
        if self.up:
            self.cmd([IFCONFIG_BIN, self.ifname(ifindex), "link",
                str(addr)])

    def addaddr(self, ifindex, addr):
        if self.up:
            if ':' in addr:
                family = "inet6"
            else:
                family = "inet"
            self.cmd([IFCONFIG_BIN, self.ifname(ifindex), family, "alias",
                str(addr)])
        self._netif[ifindex].addaddr(addr)

    def deladdr(self, ifindex, addr):
        try:
            self._netif[ifindex].deladdr(addr)
        except ValueError:
            self.warn("trying to delete unknown address: %s" % addr)
        if self.up:
            if ':' in addr:
                family = "inet6"
            else:
                family = "inet"
            self.cmd([IFCONFIG_BIN, self.ifname(ifindex), family, "-alias",
                str(addr)])

    valid_deladdrtype = ("inet", "inet6", "inet6link")
    def delalladdr(self, ifindex, addrtypes = valid_deladdrtype):
        addr = self.getaddr(self.ifname(ifindex), rescan = True)
        for t in addrtypes:
            if t not in self.valid_deladdrtype:
                raise ValueError, "addr type must be in: " + \
                    " ".join(self.valid_deladdrtype)
            for a in addr[t]:
                self.deladdr(ifindex, a)
        # update cached information
        self.getaddr(self.ifname(ifindex), rescan = True)

    def ifup(self, ifindex):
        if self.up:
            self.cmd([IFCONFIG_BIN, self.ifname(ifindex), "up"])

    def newnetif(self, net = None, addrlist = [], hwaddr = None,
                 ifindex = None, ifname = None):
        self.lock.acquire()
        try:
            ifindex = self.newveth(ifindex = ifindex, ifname = ifname,
                                       net = net)
            if net is not None:
                self.attachnet(ifindex, net)
            if hwaddr:
                self.sethwaddr(ifindex, hwaddr)
            for addr in maketuple(addrlist):
                self.addaddr(ifindex, addr)
            self.ifup(ifindex)
            return ifindex
        finally:
            self.lock.release()

    def attachnet(self, ifindex, net):
        self._netif[ifindex].attachnet(net)

    def detachnet(self, ifindex):
        self._netif[ifindex].detachnet()

    def addfile(self, srcname, filename):
        shcmd = "mkdir -p $(dirname '%s') && mv '%s' '%s' && sync" % \
            (filename, srcname, filename)
        self.shcmd(shcmd)

    def getaddr(self, ifname, rescan = False):
        return None
        #return self.vnodeclient.getaddr(ifname = ifname, rescan = rescan)

    def addsymlink(self, path, file):
        ''' Create a symbolic link from /path/name/file ->
            /tmp/pycore.nnnnn/@.conf/path.name/file
        '''
        dirname = path
        if dirname and dirname[0] == "/":
            dirname = dirname[1:]
        dirname = dirname.replace("/", ".")
        if file:
            pathname = os.path.join(path, file)
            sym = os.path.join(self.session.sessiondir, "@.conf", dirname, file)
        else:
            pathname = path
            sym = os.path.join(self.session.sessiondir, "@.conf", dirname)

        if os.path.islink(pathname):
            if os.readlink(pathname) == sym:
                # this link already exists - silently return
                return
            os.unlink(pathname)
        else:
            if os.path.exists(pathname):
                self.warn("did not create symlink for %s since path " \
                          "exists on host" % pathname)
                return
        self.info("creating symlink %s -> %s" % (pathname, sym))
        os.symlink(sym, pathname)

class JailNode(SimpleJailNode):

    def __init__(self, session, objid = None, name = None,
                 nodedir = None, bootsh = "boot.sh", verbose = False,
                 start = True):
        super(JailNode, self).__init__(session = session, objid = objid,
                                      name = name, nodedir = nodedir,
                                      verbose = verbose)
        self.bootsh = bootsh
        if not start:
            return
        # below here is considered node startup/instantiation code
        self.makenodedir()
        self.startup()

    def boot(self):
        self.session.services.bootnodeservices(self)

    def validate(self):
        self.session.services.validatenodeservices(self)

    def startup(self):
        self.lock.acquire()
        try:
            super(JailNode, self).startup()
            #self.privatedir("/var/run")
            #self.privatedir("/var/log")
        finally:
            self.lock.release()

    def shutdown(self):
        if not self.up:
            return
        self.lock.acquire()
        # services are instead stopped when session enters datacollect state
        #self.session.services.stopnodeservices(self)
        try:
            super(JailNode, self).shutdown()
        finally:
            self.rmnodedir()
            self.lock.release()

    def privatedir(self, path):
        if path[0] != "/":
            raise ValueError, "path not fully qualified: " + path
        hostpath = os.path.join(self.nodedir, path[1:].replace("/", "."))
        try:
            os.mkdir(hostpath)
        except OSError:
            pass
        except Exception, e:
            raise Exception, e
        self.mount(hostpath, path)

    def opennodefile(self, filename, mode = "w"):
        dirname, basename = os.path.split(filename)
        #self.addsymlink(path=dirname, file=basename)
        if not basename:
            raise ValueError, "no basename for filename: " + filename
        if dirname and dirname[0] == "/":
            dirname = dirname[1:]
        dirname = dirname.replace("/", ".")
        dirname = os.path.join(self.nodedir, dirname)
        if not os.path.isdir(dirname):
            os.makedirs(dirname, mode = 0755)
        hostfilename = os.path.join(dirname, basename)
        return open(hostfilename, mode)

    def nodefile(self, filename, contents, mode = 0644):
        f = self.opennodefile(filename, "w")
        f.write(contents)
        os.chmod(f.name, mode)
        f.close()
        self.info("created nodefile: '%s'; mode: 0%o" % (f.name, mode))

