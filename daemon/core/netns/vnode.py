"""
vnode.py: PyCoreNode and LxcNode classes that implement the network namespace
virtual node.
"""

import os
import random
import shutil
import signal
import string
import subprocess
import threading

from core import constants
from core.coreobj import PyCoreNetIf
from core.coreobj import PyCoreNode
from core.enumerations import NodeTypes
from core.misc import log
from core.misc import nodeutils
from core.misc import utils
from core.netns import vnodeclient
from core.netns.vif import TunTap
from core.netns.vif import VEth

logger = log.get_logger(__name__)

utils.check_executables([constants.IP_BIN])


class SimpleLxcNode(PyCoreNode):
    def __init__(self, session, objid=None, name=None, nodedir=None, start=True):
        PyCoreNode.__init__(self, session, objid, name, start=start)
        self.nodedir = nodedir
        self.ctrlchnlname = os.path.abspath(os.path.join(self.session.session_dir, self.name))
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
        """
        Start a new namespace node by invoking the vnoded process that
        allocates a new namespace. Bring up the loopback device and set
        the hostname.
        """
        if self.up:
            raise Exception("already up")
        vnoded = ["%s/vnoded" % constants.CORE_SBIN_DIR, "-v", "-c", self.ctrlchnlname,
                  "-l", self.ctrlchnlname + ".log",
                  "-p", self.ctrlchnlname + ".pid"]
        if self.nodedir:
            vnoded += ["-C", self.nodedir]
        env = self.session.get_environment(state=False)
        env['NODE_NUMBER'] = str(self.objid)
        env['NODE_NAME'] = str(self.name)

        try:
            tmp = subprocess.Popen(vnoded, stdout=subprocess.PIPE, env=env)
        except OSError:
            msg = "error running vnoded command: %s" % vnoded
            logger.exception("SimpleLxcNode.startup(): %s", msg)
            raise Exception(msg)

        try:
            self.pid = int(tmp.stdout.read())
            tmp.stdout.close()
        except ValueError:
            msg = "vnoded failed to create a namespace; "
            msg += "check kernel support and user priveleges"
            logger.exception("SimpleLxcNode.startup(): %s", msg)

        if tmp.wait():
            raise Exception("command failed: %s" % vnoded)

        self.vnodeclient = vnodeclient.VnodeClient(self.name, self.ctrlchnlname)
        logger.info("bringing up loopback interface")
        self.cmd([constants.IP_BIN, "link", "set", "lo", "up"])
        logger.info("setting hostname: %s" % self.name)
        self.cmd(["hostname", self.name])
        self.up = True

    def shutdown(self):
        # nothing to do if node is not up
        if not self.up:
            return

        # unmount all targets
        while self._mounts:
            source, target = self._mounts.pop(-1)
            self.umount(target)

        # shutdown all interfaces
        for netif in self.netifs():
            netif.shutdown()

        # attempt to kill node process and wait for termination of children
        try:
            os.kill(self.pid, signal.SIGTERM)
            os.waitpid(self.pid, 0)
        except OSError:
            logger.exception("error killing process")

        # remove node directory if present
        try:
            if os.path.exists(self.ctrlchnlname):
                os.unlink(self.ctrlchnlname)
        except OSError:
            logger.exception("error removing file")

        # clear interface data, close client, and mark self and not up
        self._netif.clear()
        self.vnodeclient.close()
        self.up = False

    def cmd(self, args, wait=True):
        return self.vnodeclient.cmd(args, wait)

    def cmdresult(self, args):
        return self.vnodeclient.cmdresult(args)

    def popen(self, args):
        return self.vnodeclient.popen(args)

    def icmd(self, args):
        return self.vnodeclient.icmd(args)

    def redircmd(self, infd, outfd, errfd, args, wait=True):
        return self.vnodeclient.redircmd(infd, outfd, errfd, args, wait)

    def term(self, sh="/bin/sh"):
        return self.vnodeclient.term(sh=sh)

    def termcmdstring(self, sh="/bin/sh"):
        return self.vnodeclient.termcmdstring(sh=sh)

    def shcmd(self, cmdstr, sh="/bin/sh"):
        return self.vnodeclient.shcmd(cmdstr, sh=sh)

    def boot(self):
        pass

    def mount(self, source, target):
        source = os.path.abspath(source)
        logger.info("mounting %s at %s" % (source, target))
        try:
            shcmd = "mkdir -p '%s' && %s -n --bind '%s' '%s'" % \
                    (target, constants.MOUNT_BIN, source, target)
            self.shcmd(shcmd)
            self._mounts.append((source, target))
        except:
            logger.exception("mounting failed for %s at %s", source, target)

    def umount(self, target):
        logger.info("unmounting '%s'" % target)
        try:
            self.cmd([constants.UMOUNT_BIN, "-n", "-l", target])
        except:
            logger.exception("unmounting failed for %s" % target)

    def newifindex(self):
        with self.lock:
            return PyCoreNode.newifindex(self)

    def newveth(self, ifindex=None, ifname=None, net=None):
        self.lock.acquire()
        try:
            if ifindex is None:
                ifindex = self.newifindex()

            if ifname is None:
                ifname = "eth%d" % ifindex

            sessionid = self.session.short_session_id()

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
            veth = VEth(node=self, name=name, localname=localname, mtu=1500, net=net, start=self.up)

            if self.up:
                subprocess.check_call([constants.IP_BIN, "link", "set", veth.name, "netns", str(self.pid)])
                self.cmd([constants.IP_BIN, "link", "set", veth.name, "name", ifname])

            veth.name = ifname

            # retrieve interface information
            result, output = self.cmdresult(["ip", "link", "show", veth.name])
            logger.info("interface command output: %s", output)
            output = output.split("\n")
            veth.flow_id = int(output[0].strip().split(":")[0]) + 1
            logger.info("interface flow index: %s - %s", veth.name, veth.flow_id)
            veth.hwaddr = output[1].strip().split()[1]
            logger.info("interface mac: %s - %s", veth.name, veth.hwaddr)

            try:
                self.addnetif(veth, ifindex)
            except:
                veth.shutdown()
                del veth
                raise

            return ifindex
        finally:
            self.lock.release()

    def newtuntap(self, ifindex=None, ifname=None, net=None):
        self.lock.acquire()
        try:
            if ifindex is None:
                ifindex = self.newifindex()
            if ifname is None:
                ifname = "eth%d" % ifindex
            sessionid = self.session.short_session_id()
            localname = "tap%s.%s.%s" % (self.objid, ifindex, sessionid)
            name = ifname
            ifclass = TunTap
            tuntap = ifclass(node=self, name=name, localname=localname,
                             mtu=1500, net=net, start=self.up)
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
            (status, result) = self.cmdresult([constants.IP_BIN, "link", "set", "dev",
                                               self.ifname(ifindex), "address", str(addr)])
            if status:
                logger.error("error setting MAC address %s", str(addr))

    def addaddr(self, ifindex, addr):
        if self.up:
            self.cmd([constants.IP_BIN, "addr", "add", str(addr),
                      "dev", self.ifname(ifindex)])
        self._netif[ifindex].addaddr(addr)

    def deladdr(self, ifindex, addr):
        try:
            self._netif[ifindex].deladdr(addr)
        except ValueError:
            logger.exception("trying to delete unknown address: %s" % addr)

        if self.up:
            self.cmd([constants.IP_BIN, "addr", "del", str(addr), "dev", self.ifname(ifindex)])

    valid_deladdrtype = ("inet", "inet6", "inet6link")

    def delalladdr(self, ifindex, addrtypes=valid_deladdrtype):
        addr = self.getaddr(self.ifname(ifindex), rescan=True)
        for t in addrtypes:
            if t not in self.valid_deladdrtype:
                raise ValueError("addr type must be in: " + " ".join(self.valid_deladdrtype))
            for a in addr[t]:
                self.deladdr(ifindex, a)
        # update cached information
        self.getaddr(self.ifname(ifindex), rescan=True)

    def ifup(self, ifindex):
        if self.up:
            self.cmd([constants.IP_BIN, "link", "set", self.ifname(ifindex), "up"])

    def newnetif(self, net=None, addrlist=[], hwaddr=None,
                 ifindex=None, ifname=None):
        self.lock.acquire()
        try:
            if nodeutils.is_node(net, NodeTypes.EMANE):
                ifindex = self.newtuntap(ifindex=ifindex, ifname=ifname,
                                         net=net)
                # TUN/TAP is not ready for addressing yet; the device may
                #   take some time to appear, and installing it into a
                #   namespace after it has been bound removes addressing;
                #   save addresses with the interface now
                self.attachnet(ifindex, net)
                netif = self.netif(ifindex)
                netif.sethwaddr(hwaddr)
                for addr in utils.maketuple(addrlist):
                    netif.addaddr(addr)
                return ifindex
            else:
                ifindex = self.newveth(ifindex=ifindex, ifname=ifname, net=net)

            if net is not None:
                self.attachnet(ifindex, net)

            if hwaddr:
                self.sethwaddr(ifindex, hwaddr)

            for addr in utils.maketuple(addrlist):
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
        subprocess.check_call([constants.IP_BIN, "link", "add", "name", tmp1,
                               "type", "veth", "peer", "name", tmp2])

        subprocess.call([constants.IP_BIN, "link", "set", tmp1, "netns", str(self.pid)])
        self.cmd([constants.IP_BIN, "link", "set", tmp1, "name", ifname])
        self.addnetif(PyCoreNetIf(self, ifname), self.newifindex())

        subprocess.check_call([constants.IP_BIN, "link", "set", tmp2, "netns", str(othernode.pid)])
        othernode.cmd([constants.IP_BIN, "link", "set", tmp2, "name", otherifname])
        othernode.addnetif(PyCoreNetIf(othernode, otherifname),
                           othernode.newifindex())

    def addfile(self, srcname, filename):
        shcmd = "mkdir -p $(dirname '%s') && mv '%s' '%s' && sync" % \
                (filename, srcname, filename)
        self.shcmd(shcmd)

    def getaddr(self, ifname, rescan=False):
        return self.vnodeclient.getaddr(ifname=ifname, rescan=rescan)

    def netifstats(self, ifname=None):
        return self.vnodeclient.netifstats(ifname=ifname)


class LxcNode(SimpleLxcNode):
    def __init__(self, session, objid=None, name=None,
                 nodedir=None, bootsh="boot.sh", start=True):
        super(LxcNode, self).__init__(session=session, objid=objid,
                                      name=name, nodedir=nodedir, start=start)
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
        except OSError:
            logger.exception("error during LxcNode.startup()")
        finally:
            self.lock.release()

    def shutdown(self):
        if not self.up:
            return
        self.lock.acquire()
        # services are instead stopped when session enters datacollect state
        # self.session.services.stopnodeservices(self)
        try:
            super(LxcNode, self).shutdown()
        finally:
            self.rmnodedir()
            self.lock.release()

    def privatedir(self, path):
        if path[0] != "/":
            raise ValueError("path not fully qualified: %s" % path)
        hostpath = os.path.join(self.nodedir, os.path.normpath(path).strip('/').replace('/', '.'))

        try:
            os.mkdir(hostpath)
        except OSError:
            logger.exception("error creating directory: %s", hostpath)

        self.mount(hostpath, path)

    def hostfilename(self, filename):
        """
        Return the name of a node's file on the host filesystem.
        """
        dirname, basename = os.path.split(filename)
        if not basename:
            raise ValueError, "no basename for filename: " + filename
        if dirname and dirname[0] == "/":
            dirname = dirname[1:]
        dirname = dirname.replace("/", ".")
        dirname = os.path.join(self.nodedir, dirname)
        return os.path.join(dirname, basename)

    def opennodefile(self, filename, mode="w"):
        hostfilename = self.hostfilename(filename)
        dirname, basename = os.path.split(hostfilename)
        if not os.path.isdir(dirname):
            os.makedirs(dirname, mode=0755)
        return open(hostfilename, mode)

    def nodefile(self, filename, contents, mode=0644):
        f = self.opennodefile(filename, "w")
        f.write(contents)
        os.chmod(f.name, mode)
        f.close()
        logger.info("created nodefile: '%s'; mode: 0%o" % (f.name, mode))

    def nodefilecopy(self, filename, srcfilename, mode=None):
        """
        Copy a file to a node, following symlinks and preserving metadata.
        Change file mode if specified.
        """
        hostfilename = self.hostfilename(filename)
        shutil.copy2(srcfilename, hostfilename)
        if mode is not None:
            os.chmod(hostfilename, mode)
        logger.info("copied nodefile: '%s'; mode: %s" % (hostfilename, mode))
