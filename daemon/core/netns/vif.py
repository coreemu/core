#
# CORE
# Copyright (c)2011-2014 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Tom Goff <thomas.goff@boeing.com>
#          Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
vif.py: PyCoreNetIf classes that implement the interfaces available
under Linux.
'''

import time
from core.api import coreapi
from core.misc.utils import checkexec, check_call, mutedetach, mutecall
from core.constants import IP_BIN
from core.coreobj import PyCoreNetIf
from core.emane.nodes import EmaneNode

checkexec([IP_BIN])


class VEth(PyCoreNetIf):
    def __init__(self, node, name, localname, mtu=1500, net=None,
                 start=True):
        # note that net arg is ignored
        PyCoreNetIf.__init__(self, node=node, name=name, mtu=mtu)
        self.localname = localname
        self.up = False
        if start:
            self.startup()

    def startup(self):
        check_call([IP_BIN, "link", "add", "name", self.localname,
                    "type", "veth", "peer", "name", self.name])
        check_call([IP_BIN, "link", "set", self.localname, "up"])
        self.up = True

    def shutdown(self):
        if not self.up:
            return
        if self.node:
            self.node.cmd([IP_BIN, "-6", "addr", "flush", "dev", self.name])
        if self.localname:
            mutedetach([IP_BIN, "link", "delete", self.localname])
        self.up = False


class TunTap(PyCoreNetIf):
    ''' TUN/TAP virtual device in TAP mode
    '''
    def __init__(self, node, name, localname, mtu=1500, net=None,
                 start=True):
        PyCoreNetIf.__init__(self, node=node, name=name, mtu=mtu)
        self.localname = localname
        self.up = False
        self.transport_type = "virtual"
        if start:
            self.startup()

    def startup(self):
        # TODO: more sophisticated TAP creation here
        #   Debian does not support -p (tap) option, RedHat does.
        # For now, this is disabled to allow the TAP to be created by another
        # system (e.g. EMANE's emanetransportd)
        # check_call(["tunctl", "-t", self.name])
        # self.install()
        self.up = True

    def shutdown(self):
        if not self.up:
            return
        self.node.cmd([IP_BIN, "-6", "addr", "flush", "dev", self.name])
        # if self.name:
        #     mutedetach(["tunctl", "-d", self.localname])
        self.up = False

    def waitfor(self, func, attempts=10, maxretrydelay=0.25):
        '''\
        Wait for func() to return zero with exponential backoff
        '''
        delay = 0.01
        for i in xrange(1, attempts + 1):
            r = func()
            if r == 0:
                return
            msg = 'attempt %s failed with nonzero exit status %s' % (i, r)
            if i < attempts + 1:
                msg += ', retrying...'
                self.node.info(msg)
                time.sleep(delay)
                delay = delay + delay
                if delay > maxretrydelay:
                    delay = maxretrydelay
            else:
                msg += ', giving up'
                self.node.info(msg)
        raise RuntimeError, 'command failed after %s attempts' % attempts

    def waitfordevicelocal(self):
        '''\
        Check for presence of a local device - tap device may not
        appear right away waits
        '''
        def localdevexists():
            cmd = (IP_BIN, 'link', 'show', self.localname)
            return mutecall(cmd)
        self.waitfor(localdevexists)

    def waitfordevicenode(self):
        '''\
        Check for presence of a node device - tap device may not
        appear right away waits
        '''
        def nodedevexists():
            cmd = (IP_BIN, 'link', 'show', self.name)
            return self.node.cmd(cmd)
        count = 0
        while True:
            try:
                self.waitfor(nodedevexists)
                break
            except RuntimeError:
                # check if this is an EMANE interface; if so, continue
                # waiting if EMANE is still running
                if count < 5 and isinstance(self.net, EmaneNode) and \
                   self.node.session.emane.emanerunning(self.node):
                    count += 1
                else:
                    raise

    def install(self):
        ''' Install this TAP into its namespace. This is not done from the
            startup() method but called at a later time when a userspace
            program (running on the host) has had a chance to open the socket
            end of the TAP.
        '''
        self.waitfordevicelocal()
        netns = str(self.node.pid)
        try:
            check_call([IP_BIN, "link", "set", self.localname, "netns", netns])
        except Exception, e:
            msg = "error installing TAP interface %s, command:" % self.localname
            msg += "ip link set %s netns %s" % (self.localname, netns)
            self.node.exception(coreapi.CORE_EXCP_LEVEL_ERROR, self.localname, msg)
            self.node.warn(msg)
            return
        self.node.cmd([IP_BIN, "link", "set", self.localname,
                       "name", self.name])
        self.node.cmd([IP_BIN, "link", "set", self.name,  "up"])

    def setaddrs(self):
        ''' Set interface addresses based on self.addrlist.
        '''
        self.waitfordevicenode()
        for addr in self.addrlist:
            self.node.cmd([IP_BIN, "addr", "add", str(addr),
                          "dev", self.name])


class GreTap(PyCoreNetIf):
    ''' GRE TAP device for tunneling between emulation servers.
        Uses the "gretap" tunnel device type from Linux which is a GRE device
        having a MAC address. The MAC address is required for bridging.
    '''
    def __init__(self, node=None, name=None, session=None, mtu=1458,
                 remoteip=None, objid=None, localip=None, ttl=255,
                 key=None, start=True):
        PyCoreNetIf.__init__(self, node=node, name=name, mtu=mtu)
        self.session = session
        if objid is None:
            # from PyCoreObj
            objid = (((id(self) >> 16) ^ (id(self) & 0xffff)) & 0xffff)
        self.objid = objid
        sessionid = self.session.shortsessionid()
        # interface name on the local host machine
        self.localname = "gt.%s.%s" % (self.objid, sessionid)
        self.transport_type = "raw"
        if not start:
            self.up = False
            return

        if remoteip is None:
            raise ValueError, "missing remote IP required for GRE TAP device"
        cmd = ("ip", "link", "add", self.localname, "type", "gretap",
               "remote", str(remoteip))
        if localip:
            cmd += ("local", str(localip))
        if ttl:
            cmd += ("ttl", str(ttl))
        if key:
            cmd += ("key", str(key))
        check_call(cmd)
        cmd = ("ip", "link", "set", self.localname, "up")
        check_call(cmd)
        self.up = True

    def shutdown(self):
        if self.localname:
            cmd = ("ip", "link", "set", self.localname, "down")
            check_call(cmd)
            cmd = ("ip", "link", "del", self.localname)
            check_call(cmd)
            self.localname = None

    def tonodemsg(self, flags):
        return None

    def tolinkmsgs(self, flags):
        return []
