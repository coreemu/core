#
# CORE
# Copyright (c)2011-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Tom Goff <thomas.goff@boeing.com>
#          Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
vif.py: PyCoreNetIf classes that implement the interfaces available
under Linux.
'''

import os, signal, shutil, sys, subprocess, vnodeclient, threading, string
import random, time
from core.api import coreapi
from core.misc.utils import *
from core.constants import *
from core.coreobj import PyCoreObj, PyCoreNode, PyCoreNetIf, Position
from core.emane.nodes import EmaneNode

checkexec([IP_BIN])

class VEth(PyCoreNetIf):
    def __init__(self, node, name, localname, mtu = 1500, net = None,
                 start = True):
        # note that net arg is ignored
        PyCoreNetIf.__init__(self, node = node, name = name, mtu = mtu)
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
    def __init__(self, node, name, localname, mtu = 1500, net = None,
                 start = True):
        PyCoreNetIf.__init__(self, node = node, name = name, mtu = mtu)
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
        #check_call(["tunctl", "-t", self.name])
        # self.install()
        self.up = True

    def shutdown(self):
        if not self.up:
            return
        self.node.cmd([IP_BIN, "-6", "addr", "flush", "dev", self.name])
        #if self.name:
        #    mutedetach(["tunctl", "-d", self.localname])
        self.up = False

    def install(self):
        ''' Install this TAP into its namespace. This is not done from the
            startup() method but called at a later time when a userspace
            program (running on the host) has had a chance to open the socket
            end of the TAP.
        '''
        netns = str(self.node.pid)
        # check for presence of device - tap device may not appear right away
        # waits ~= stime * ( 2 ** attempts) seconds 
        attempts = 9
        stime = 0.01
        while attempts > 0:
            try:
                mutecheck_call([IP_BIN, "link", "show", self.localname])
                break
            except Exception, e:
                msg = "ip link show %s error (%d): %s" % \
                        (self.localname, attempts, e)
                if attempts > 1:
                    msg += ", retrying..."
                self.node.info(msg)
            time.sleep(stime)
            stime *= 2
            attempts -= 1
        # install tap device into namespace
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
        for addr in self.addrlist:
            self.node.cmd([IP_BIN, "addr", "add", str(addr),
                  "dev", self.name])
        self.node.cmd([IP_BIN, "link", "set", self.name,  "up"])

class GreTap(PyCoreNetIf):
    ''' GRE TAP device for tunneling between emulation servers.
        Uses the "gretap" tunnel device type from Linux which is a GRE device
        having a MAC address. The MAC address is required for bridging.
    '''
    def __init__(self, node = None, name = None, session = None, mtu = 1458,
                 remoteip = None, objid = None, localip = None, ttl = 255,
                 key = None, start = True):
        PyCoreNetIf.__init__(self, node = node, name = name, mtu = mtu)
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
