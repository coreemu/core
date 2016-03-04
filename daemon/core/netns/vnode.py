#
# CORE
# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Tom Goff <thomas.goff@boeing.com>
#          Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
vnode.py: PyCoreNode and LxcNode classes that implement the network namespace
virtual node.
'''

import os, signal, sys, subprocess, vnodeclient, threading, string, shutil
import random, time
from core.api import coreapi
from core.misc.utils import *
from core.constants import *
from core.coreobj import PyCoreObj, PyCoreNode, PyCoreNetIf, Position
from core.netns.vif import VEth, TunTap
from core.emane.nodes import EmaneNode

checkexec([IP_BIN])

class SimpleLxcNode(PyCoreNode):
    def __init__(self, session, objid = None, name = None, nodedir = None,
                 verbose = False, start = True):
        PyCoreNode.__init__(self, session, objid, name, verbose=verbose,
                            start=start)
        self.nodedir = nodedir
        self.ctrlchnlname = \
            os.path.abspath(os.path.join(self.session.sessiondir, self.name))
        self.vnodeclient = None
        self.pid = None
        self.up = False
        self.lock = threading.RLock()
        self._mounts = []

    def alive(self):
        try:
            os.kill(self.pid, 0)
        except OSError:
            return False
        return True

    def startup(self):
        ''' Start a new namespace node by invoking the vnoded process that
            allocates a new namespace. Bring up the loopback device and set
            the hostname.
        '''
        if self.up:
            raise Exception, "already up"
        vnoded = ["%s/vnoded" % CORE_SBIN_DIR, "-v", "-c", self.ctrlchnlname,
                  "-l", self.ctrlchnlname + ".log",
                  "-p", self.ctrlchnlname + ".pid"]
        if self.nodedir:
            vnoded += ["-C", self.nodedir]
        env = self.session.getenviron(state=False)
        env['NODE_NUMBER'] = str(self.objid)
        env['NODE_NAME'] = str(self.name)

        try:
            tmp = subprocess.Popen(vnoded, stdout = subprocess.PIPE, env = env)
        except OSError, e:
            msg = "error running vnoded command: %s (%s)" % (vnoded, e)
            self.exception(coreapi.CORE_EXCP_LEVEL_FATAL,
                "SimpleLxcNode.startup()", msg)
            raise Exception, msg
        try:
            self.pid = int(tmp.stdout.read())
            tmp.stdout.close()
        except Exception:
            msg = "vnoded failed to create a namespace; "
            msg += "check kernel support and user priveleges"
            self.exception(coreapi.CORE_EXCP_LEVEL_FATAL,
                           "SimpleLxcNode.startup()", msg)
        if tmp.wait():
            raise Exception, ("command failed: %s" % vnoded)
        self.vnodeclient = vnodeclient.VnodeClient(self.name,
                                                   self.ctrlchnlname)
        self.info("bringing up loopback interface")
        self.cmd([IP_BIN, "link", "set", "lo", "up"])
        self.info("setting hostname: %s" % self.name)
        self.cmd(["hostname", self.name])
        self.up = True

    def shutdown(self):
        if not self.up:
            return
        while self._mounts:
            source, target = self._mounts.pop(-1)
            self.umount(target)
        for netif in self.netifs():
            netif.shutdown()
        try:
            os.kill(self.pid, signal.SIGTERM)
            os.waitpid(self.pid, 0)
        except OSError:
            pass
        try:
            os.unlink(self.ctrlchnlname)
        except OSError:
            pass
        self._netif.clear()
        self.vnodeclient.close()
        self.up = False

    def cmd(self, args, wait = True):
        return self.vnodeclient.cmd(args, wait)

    def cmdresult(self, args):
        return self.vnodeclient.cmdresult(args)

    def popen(self, args):
        return self.vnodeclient.popen(args)

    def icmd(self, args):
        return self.vnodeclient.icmd(args)

    def redircmd(self, infd, outfd, errfd, args, wait = True):
        return self.vnodeclient.redircmd(infd, outfd, errfd, args, wait)

    def term(self, sh = "/bin/sh"):
        return self.vnodeclient.term(sh = sh)

    def termcmdstring(self, sh = "/bin/sh"):
        return self.vnodeclient.termcmdstring(sh = sh)

    def shcmd(self, cmdstr, sh = "/bin/sh"):
        return self.vnodeclient.shcmd(cmdstr, sh = sh)

    def boot(self):
        pass

    def mount(self, source, target):
        source = os.path.abspath(source)
        self.info("mounting %s at %s" % (source, target))
        try:
            shcmd = "mkdir -p '%s' && %s -n --bind '%s' '%s'" % \
                (target, MOUNT_BIN, source, target)
            self.shcmd(shcmd)
            self._mounts.append((source, target))
        except:
            self.warn("mounting failed for %s at %s" % (source, target))

    def umount(self, target):
        self.info("unmounting '%s'" % target)
        try:
            self.cmd([UMOUNT_BIN, "-n", "-l", target])
        except:
            self.warn("unmounting failed for %s" % target)

    def newifindex(self):
        with self.lock:
            return PyCoreNode.newifindex(self)

    def newveth(self, ifindex = None, ifname = None, net = None):
        self.lock.acquire()
        try:
            if ifindex is None:
                ifindex = self.newifindex()
            if ifname is None:
                ifname = "eth%d" % ifindex
            sessionid = self.session.shortsessionid()
            try:
                suffix = '%x.%s.%s' % (self.objid, ifindex, sessionid)
            except TypeError:
                suffix = '%s.%s.%s' % (self.objid, ifindex, sessionid)
            localname = 'veth' + suffix
            if len(localname) >= 16:
                raise ValueError, "interface local name '%s' too long" % \
                        localname
            name = localname + 'p'
            if len(name) >= 16:
                raise ValueError, "interface name '%s' too long" % name
            ifclass = VEth
            veth = ifclass(node = self, name = name, localname = localname,
                           mtu = 1500, net = net, start = self.up)
            if self.up:
                check_call([IP_BIN, "link", "set", veth.name,
                            "netns", str(self.pid)])
                self.cmd([IP_BIN, "link", "set", veth.name, "name", ifname])
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

    def newtuntap(self, ifindex = None, ifname = None, net = None):
        self.lock.acquire()
        try:
            if ifindex is None:
                ifindex = self.newifindex()
            if ifname is None:
                ifname = "eth%d" % ifindex
            sessionid = self.session.shortsessionid()
            localname = "tap%s.%s.%s" % (self.objid, ifindex, sessionid)
            name = ifname
            ifclass = TunTap
            tuntap = ifclass(node = self, name = name, localname = localname,
                             mtu = 1500, net = net, start = self.up)
            try:
                self.addnetif(tuntap, ifindex)
            except:
                tuntap.shutdown()
                del tuntap
                raise
            return ifindex
        finally:
            self.lock.release()

    def sethwaddr(self, ifindex, addr):
        self._netif[ifindex].sethwaddr(addr)
        if self.up:
            (status, result) = self.cmdresult([IP_BIN, "link", "set", "dev",
                                    self.ifname(ifindex), "address", str(addr)])
            if status:
                self.exception(coreapi.CORE_EXCP_LEVEL_ERROR,
                    "SimpleLxcNode.sethwaddr()",
                    "error setting MAC address %s" % str(addr))
    def addaddr(self, ifindex, addr):
        if self.up:
            self.cmd([IP_BIN, "addr", "add", str(addr),
                  "dev", self.ifname(ifindex)])
        self._netif[ifindex].addaddr(addr)

    def deladdr(self, ifindex, addr):
        try:
            self._netif[ifindex].deladdr(addr)
        except ValueError:
            self.warn("trying to delete unknown address: %s" % addr)
        if self.up:
            self.cmd([IP_BIN, "addr", "del", str(addr),
                  "dev", self.ifname(ifindex)])

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
            self.cmd([IP_BIN, "link", "set", self.ifname(ifindex), "up"])

    def newnetif(self, net = None, addrlist = [], hwaddr = None,
                 ifindex = None, ifname = None):
        self.lock.acquire()
        try:
            if isinstance(net, EmaneNode):
                ifindex = self.newtuntap(ifindex = ifindex, ifname = ifname,
                                         net = net)
                # TUN/TAP is not ready for addressing yet; the device may
                #   take some time to appear, and installing it into a
                #   namespace after it has been bound removes addressing;
                #   save addresses with the interface now
                self.attachnet(ifindex, net)
                netif = self.netif(ifindex)
                netif.sethwaddr(hwaddr)
                for addr in maketuple(addrlist):
                    netif.addaddr(addr)
                return ifindex
            else:
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

    def connectnode(self, ifname, othernode, otherifname):
        tmplen = 8
        tmp1 = "tmp." + "".join([random.choice(string.ascii_lowercase)
                                 for x in xrange(tmplen)])
        tmp2 = "tmp." + "".join([random.choice(string.ascii_lowercase)
                                 for x in xrange(tmplen)])
        check_call([IP_BIN, "link", "add", "name", tmp1,
                    "type", "veth", "peer", "name", tmp2])

        check_call([IP_BIN, "link", "set", tmp1, "netns", str(self.pid)])
        self.cmd([IP_BIN, "link", "set", tmp1, "name", ifname])
        self.addnetif(PyCoreNetIf(self, ifname), self.newifindex())

        check_call([IP_BIN, "link", "set", tmp2, "netns", str(othernode.pid)])
        othernode.cmd([IP_BIN, "link", "set", tmp2, "name", otherifname])
        othernode.addnetif(PyCoreNetIf(othernode, otherifname),
                           othernode.newifindex())

    def addfile(self, srcname, filename):
        shcmd = "mkdir -p $(dirname '%s') && mv '%s' '%s' && sync" % \
            (filename, srcname, filename)
        self.shcmd(shcmd)

    def getaddr(self, ifname, rescan = False):
        return self.vnodeclient.getaddr(ifname = ifname, rescan = rescan)

    def netifstats(self, ifname = None):
        return self.vnodeclient.netifstats(ifname = ifname)


class LxcNode(SimpleLxcNode):
    def __init__(self, session, objid = None, name = None,
                 nodedir = None, bootsh = "boot.sh", verbose = False,
                 start = True):
        super(LxcNode, self).__init__(session = session, objid = objid,
                                      name = name, nodedir = nodedir,
                                      verbose = verbose, start = start)
        self.bootsh = bootsh
        if start:
            self.startup()

    def boot(self):
        self.session.services.bootnodeservices(self)
        
    def validate(self):
        self.session.services.validatenodeservices(self)

    def startup(self):
        self.lock.acquire()
        try:
            self.makenodedir()
            super(LxcNode, self).startup()
            self.privatedir("/var/run")
            self.privatedir("/var/log")
        except OSError, e:
            self.warn("Error with LxcNode.startup(): %s" % e)
            self.exception(coreapi.CORE_EXCP_LEVEL_ERROR,
                "LxcNode.startup()", "%s" % e)
        finally:
            self.lock.release()

    def shutdown(self):
        if not self.up:
            return
        self.lock.acquire()
        # services are instead stopped when session enters datacollect state
        #self.session.services.stopnodeservices(self)
        try:
            super(LxcNode, self).shutdown()
        finally:
            self.rmnodedir()
            self.lock.release()

    def privatedir(self, path):
        if path[0] != "/":
            raise ValueError, "path not fully qualified: " + path
        hostpath = os.path.join(self.nodedir,
                                os.path.normpath(path).strip('/').replace('/', '.'))
        try:
            os.mkdir(hostpath)
        except OSError:
            pass
        except Exception, e:
            raise Exception, e
        self.mount(hostpath, path)

    def hostfilename(self, filename):
        ''' Return the name of a node's file on the host filesystem.
        '''
        dirname, basename = os.path.split(filename)
        if not basename:
            raise ValueError, "no basename for filename: " + filename
        if dirname and dirname[0] == "/":
            dirname = dirname[1:]
        dirname = dirname.replace("/", ".")
        dirname = os.path.join(self.nodedir, dirname)
        return os.path.join(dirname, basename)

    def opennodefile(self, filename, mode = "w"):
        hostfilename = self.hostfilename(filename)
        dirname, basename = os.path.split(hostfilename)
        if not os.path.isdir(dirname):
            os.makedirs(dirname, mode = 0755)
        return open(hostfilename, mode)

    def nodefile(self, filename, contents, mode = 0644):
        f = self.opennodefile(filename, "w")
        f.write(contents)
        os.chmod(f.name, mode)
        f.close()
        self.info("created nodefile: '%s'; mode: 0%o" % (f.name, mode))
        
    def nodefilecopy(self, filename, srcfilename, mode = None):
        ''' Copy a file to a node, following symlinks and preserving metadata.
        Change file mode if specified.
        '''
        hostfilename = self.hostfilename(filename)
        shutil.copy2(srcfilename, hostfilename)
        if mode is not None:
            os.chmod(hostfilename, mode)
        self.info("copied nodefile: '%s'; mode: %s" % (hostfilename, mode))
        

