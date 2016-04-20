#
# CORE
# Copyright (c)2010-2016 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Tom Goff <thomas.goff@boeing.com>
#          Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
vnet.py: PyCoreNet and LxBrNet classes that implement virtual networks using
Linux Ethernet bridging and ebtables rules.
'''

import traceback

import os, sys, threading, time, subprocess

from core.api import coreapi
from core.misc.utils import *
from core.constants import *
from core.coreobj import PyCoreNet, PyCoreObj
from core.netns.vif import VEth, GreTap

checkexec([BRCTL_BIN, IP_BIN, EBTABLES_BIN, TC_BIN])

ebtables_lock = threading.Lock()

class EbtablesQueue(object):
    ''' Helper class for queuing up ebtables commands into rate-limited
    atomic commits. This improves performance and reliability when there are
    many WLAN link updates.
    '''
    # update rate is every 300ms
    rate = 0.3
    # ebtables
    atomic_file = "/tmp/pycore.ebtables.atomic"
    
    def __init__(self):
        ''' Initialize the helper class, but don't start the update thread
        until a WLAN is instantiated.
        '''
        self.doupdateloop = False
        self.updatethread = None
        # this lock protects cmds and updates lists
        self.updatelock = threading.Lock()
        # list of pending ebtables commands
        self.cmds = []
        # list of WLANs requiring update
        self.updates = []
        # timestamps of last WLAN update; this keeps track of WLANs that are
        # using this queue
        self.last_update_time = {}
        
    def startupdateloop(self, wlan):
        ''' Kick off the update loop; only needs to be invoked once.
        '''
        self.updatelock.acquire()
        self.last_update_time[wlan] = time.time()
        self.updatelock.release()
        if self.doupdateloop:
            return
        self.doupdateloop = True
        self.updatethread = threading.Thread(target = self.updateloop)
        self.updatethread.daemon = True
        self.updatethread.start()
    
    def stopupdateloop(self, wlan):
        ''' Kill the update loop thread if there are no more WLANs using it.
        '''
        self.updatelock.acquire()
        try:
            del self.last_update_time[wlan]
        except KeyError:
            pass
        self.updatelock.release()
        if len(self.last_update_time) > 0:
            return
        self.doupdateloop = False
        if self.updatethread:
            self.updatethread.join()
            self.updatethread = None
    
    def ebatomiccmd(self, cmd):
        ''' Helper for building ebtables atomic file command list.
        '''
        r = [EBTABLES_BIN, "--atomic-file", self.atomic_file]
        if cmd:
            r.extend(cmd)
        return r
        
    def lastupdate(self, wlan):
        ''' Return the time elapsed since this WLAN was last updated.
        '''
        try:
            elapsed = time.time() - self.last_update_time[wlan]
        except KeyError:
            self.last_update_time[wlan] = time.time()
            elapsed = 0.0
        return elapsed
    
    def updated(self, wlan):
        ''' Keep track of when this WLAN was last updated.
        '''
        self.last_update_time[wlan] = time.time()
        self.updates.remove(wlan)
        
    def updateloop(self):
        ''' Thread target that looks for WLANs needing update, and
        rate limits the amount of ebtables activity. Only one userspace program
        should use ebtables at any given time, or results can be unpredictable.
        '''
        while self.doupdateloop:
            self.updatelock.acquire()
            for wlan in self.updates:
                ''' 
                Check if wlan is from a previously closed session. Because of the 
                rate limiting scheme employed here, this may happen if a new session 
                is started soon after closing a previous session.
                '''
                try:
                    wlan.session
                except:
                    # Just mark as updated to remove from self.updates. 
                    self.updated(wlan)
                    continue
                if self.lastupdate(wlan) > self.rate:
                    self.buildcmds(wlan)
                    #print "ebtables commit %d rules" % len(self.cmds)
                    self.ebcommit(wlan)
                    self.updated(wlan)
            self.updatelock.release()
            time.sleep(self.rate)
    
    def ebcommit(self, wlan):
        ''' Perform ebtables atomic commit using commands built in the
        self.cmds list.
        '''
        # save kernel ebtables snapshot to a file
        cmd = self.ebatomiccmd(["--atomic-save",])
        try:
            check_call(cmd)
        except Exception, e:
            self.eberror(wlan, "atomic-save (%s)" % cmd, e)
            # no atomic file, exit
            return
        # modify the table file using queued ebtables commands
        for c in self.cmds:
            cmd = self.ebatomiccmd(c)
            try:
                check_call(cmd)
            except Exception, e:
                self.eberror(wlan, "cmd=%s" % cmd, e)
                pass
        self.cmds = []
        # commit the table file to the kernel
        cmd = self.ebatomiccmd(["--atomic-commit",])
        try:
            check_call(cmd)
            os.unlink(self.atomic_file)
        except Exception, e:
            self.eberror(wlan, "atomic-commit (%s)" % cmd, e)
        
    def ebchange(self, wlan):
        ''' Flag a change to the given WLAN's _linked dict, so the ebtables
        chain will be rebuilt at the next interval.
        '''
        self.updatelock.acquire()
        if wlan not in self.updates:
            self.updates.append(wlan)
        self.updatelock.release()
    
    def buildcmds(self, wlan):
        ''' Inspect a _linked dict from a wlan, and rebuild the ebtables chain
        for that WLAN.
        '''
        wlan._linked_lock.acquire()
        # flush the chain
        self.cmds.extend([["-F", wlan.brname],])
        # rebuild the chain
        for (netif1, v) in wlan._linked.items():
            for (netif2, linked) in v.items():
                if wlan.policy == "DROP" and linked:
                    self.cmds.extend([["-A", wlan.brname, "-i", netif1.localname,
                        "-o", netif2.localname, "-j", "ACCEPT"],
                        ["-A", wlan.brname, "-o", netif1.localname,
                        "-i", netif2.localname, "-j", "ACCEPT"]])
                elif wlan.policy == "ACCEPT" and not linked:
                    self.cmds.extend([["-A", wlan.brname, "-i", netif1.localname,
                        "-o", netif2.localname, "-j", "DROP"],
                        ["-A", wlan.brname, "-o", netif1.localname,
                        "-i", netif2.localname, "-j", "DROP"]])
        wlan._linked_lock.release()
    
    def eberror(self, wlan, source, error):
        ''' Log an ebtables command error and send an exception.
        '''
        if not wlan:
            return
        wlan.exception(coreapi.CORE_EXCP_LEVEL_ERROR, wlan.brname,
                       "ebtables command error: %s\n%s\n" % (source, error))
        

# a global object because all WLANs share the same queue
# cannot have multiple threads invoking the ebtables commnd
ebq = EbtablesQueue()

def ebtablescmds(call, cmds):
    ebtables_lock.acquire()
    try:
        for cmd in cmds:
            call(cmd)
    finally:
        ebtables_lock.release()

class LxBrNet(PyCoreNet):

    policy = "DROP"

    def __init__(self, session, objid = None, name = None, verbose = False,
                        start = True, policy = None):
        PyCoreNet.__init__(self, session, objid, name, verbose, start)
        if name is None:
            name = str(self.objid)
        if policy is not None:
            self.policy = policy
        self.name = name
        sessionid = self.session.shortsessionid()
        self.brname = "b.%s.%s" % (str(self.objid), sessionid)
        self.up = False
        if start:
            self.startup()
            ebq.startupdateloop(self)

    def startup(self):
        try:
            check_call([BRCTL_BIN, "addbr", self.brname])
        except Exception, e:
            self.exception(coreapi.CORE_EXCP_LEVEL_FATAL, self.brname,
                           "Error adding bridge: %s" % e)
        try:
            # turn off spanning tree protocol and forwarding delay
            check_call([BRCTL_BIN, "stp", self.brname, "off"])
            check_call([BRCTL_BIN, "setfd", self.brname, "0"])
            check_call([IP_BIN, "link", "set", self.brname, "up"])
            # create a new ebtables chain for this bridge
            ebtablescmds(check_call, [
                [EBTABLES_BIN, "-N", self.brname, "-P", self.policy],
                [EBTABLES_BIN, "-A", "FORWARD",
                "--logical-in", self.brname, "-j", self.brname]])
            # turn off multicast snooping so mcast forwarding occurs w/o IGMP joins
            snoop = "/sys/devices/virtual/net/%s/bridge/multicast_snooping" % \
                self.brname
            if os.path.exists(snoop):
                open(snoop, "w").write('0')
        except Exception, e:
            self.exception(coreapi.CORE_EXCP_LEVEL_WARNING, self.brname,
                           "Error setting bridge parameters: %s" % e)

        self.up = True

    def shutdown(self):
        if not self.up:
            return
        ebq.stopupdateloop(self)
        mutecall([IP_BIN, "link", "set", self.brname, "down"])
        mutecall([BRCTL_BIN, "delbr", self.brname])
        ebtablescmds(mutecall, [
            [EBTABLES_BIN, "-D", "FORWARD",
             "--logical-in", self.brname, "-j", self.brname],
            [EBTABLES_BIN, "-X", self.brname]])
        for netif in self.netifs():
            # removes veth pairs used for bridge-to-bridge connections
            netif.shutdown()
        self._netif.clear()
        self._linked.clear()
        del self.session
        self.up = False

    def attach(self, netif):
        if self.up:
            try:
                check_call([BRCTL_BIN, "addif", self.brname, netif.localname])
                check_call([IP_BIN, "link", "set", netif.localname, "up"])
            except Exception, e:
                self.exception(coreapi.CORE_EXCP_LEVEL_ERROR, self.brname,
                               "Error joining interface %s to bridge %s: %s" % \
                               (netif.localname, self.brname, e))
                return
        PyCoreNet.attach(self, netif)

    def detach(self, netif):
        if self.up:
            try:
                check_call([BRCTL_BIN, "delif", self.brname, netif.localname])
            except Exception, e:
                self.exception(coreapi.CORE_EXCP_LEVEL_ERROR, self.brname,
                               "Error removing interface %s from bridge %s: %s" % \
                               (netif.localname, self.brname, e))
                return
        PyCoreNet.detach(self, netif)

    def linked(self, netif1, netif2):
        # check if the network interfaces are attached to this network
        if self._netif[netif1.netifi] != netif1:
            raise ValueError, "inconsistency for netif %s" % netif1.name
        if self._netif[netif2.netifi] != netif2:
            raise ValueError, "inconsistency for netif %s" % netif2.name
        try:
            linked = self._linked[netif1][netif2]
        except KeyError:
            if self.policy == "ACCEPT":
                linked = True
            elif self.policy == "DROP":
                linked = False
            else:
                raise Exception, "unknown policy: %s" % self.policy
            self._linked[netif1][netif2] = linked
        return linked

    def unlink(self, netif1, netif2):
        ''' Unlink two PyCoreNetIfs, resulting in adding or removing ebtables
        filtering rules.
        '''
        self._linked_lock.acquire()
        if not self.linked(netif1, netif2):
            self._linked_lock.release()
            return
        self._linked[netif1][netif2] = False
        self._linked_lock.release()
        ebq.ebchange(self)

    def link(self, netif1, netif2):
        ''' Link two PyCoreNetIfs together, resulting in adding or removing
        ebtables filtering rules.
        '''
        self._linked_lock.acquire()
        if self.linked(netif1, netif2):
            self._linked_lock.release()
            return
        self._linked[netif1][netif2] = True
        self._linked_lock.release()
        ebq.ebchange(self)

    def linkconfig(self, netif, bw = None, delay = None,
                   loss = None, duplicate = None, jitter = None, netif2 = None,
                   devname = None):
        ''' Configure link parameters by applying tc queuing disciplines on the
            interface.
        '''
        
        sys.stderr.write("enter linkconfig() ...\n")
        traceback.print_stack()
        
        if devname is None:
            devname = netif.localname
        tc = [TC_BIN, "qdisc", "replace", "dev", devname]
        parent = ["root"]
        changed = False
        if netif.setparam('bw', bw):
            # from tc-tbf(8): minimum value for burst is rate / kernel_hz
            if bw is not None:
                burst = max(2 * netif.mtu, bw / 1000)
                limit = 0xffff # max IP payload
                tbf = ["tbf", "rate", str(bw),
                       "burst", str(burst), "limit", str(limit)]
            if bw > 0:
                if self.up:
                    if (self.verbose):
                        self.info("linkconfig: %s" % \
                                  ([tc + parent + ["handle", "1:"] + tbf],))
                    check_call(tc + parent + ["handle", "1:"] + tbf)
                netif.setparam('has_tbf', True)
                changed = True
            elif netif.getparam('has_tbf') and bw <= 0:
                tcd = [] + tc
                tcd[2] = "delete"
                if self.up:
                    check_call(tcd + parent)
                netif.setparam('has_tbf', False)
                # removing the parent removes the child
                netif.setparam('has_netem', False)
                changed = True
        if netif.getparam('has_tbf'):
            parent = ["parent", "1:1"]
        netem = ["netem"]
        changed = max(changed, netif.setparam('delay', delay))
        if loss is not None:
            loss = float(loss)
        changed = max(changed, netif.setparam('loss', loss))
        if duplicate is not None:
            duplicate = float(duplicate)
        changed = max(changed, netif.setparam('duplicate', duplicate))
        changed = max(changed, netif.setparam('jitter', jitter))
        if not changed:
            return
        # jitter and delay use the same delay statement
        if delay is not None:
            netem += ["delay", "%sus" % delay]
        if jitter is not None:
            if delay is None:
                netem += ["delay", "0us", "%sus" % jitter, "25%"]
            else:
                netem += ["%sus" % jitter, "25%"]
        
        if loss is not None:
            netem += ["loss", "%s%%" % min(loss, 100)]
        if duplicate is not None:
            netem += ["duplicate", "%s%%" % min(duplicate, 100)]
        if delay <= 0 and jitter <= 0 and loss <= 0 and duplicate <= 0:
            # possibly remove netem if it exists and parent queue wasn't removed
            if not netif.getparam('has_netem'):
                return
            tc[2] = "delete"
            if self.up:
                if self.verbose:
                    self.info("linkconfig: %s" % \
                              ([tc + parent + ["handle", "10:"]],))
                check_call(tc + parent + ["handle", "10:"])
            netif.setparam('has_netem', False)
        elif len(netem) > 1:
            if self.up:
                if self.verbose:
                    self.info("linkconfig: %s" % \
                              ([tc + parent + ["handle", "10:"] + netem],))
                check_call(tc + parent + ["handle", "10:"] + netem)
            netif.setparam('has_netem', True)

    def linknet(self, net):
        ''' Link this bridge with another by creating a veth pair and installing
            each device into each bridge.
        '''
        sessionid = self.session.shortsessionid()
        try:
            self_objid = '%x' % self.objid
        except TypeError:
            self_objid = '%s' % self.objid
        try:
            net_objid = '%x' % net.objid
        except TypeError:
            net_objid = '%s' % net.objid
        localname = 'veth%s.%s.%s' % (self_objid, net_objid, sessionid)
        if len(localname) >= 16:
            raise ValueError, "interface local name '%s' too long" % \
                localname
        name = 'veth%s.%s.%s' % (net_objid, self_objid, sessionid)
        if len(name) >= 16:
            raise ValueError, "interface name '%s' too long" % name
        netif = VEth(node = None, name = name, localname = localname,
                     mtu = 1500, net = self, start = self.up)        
        self.attach(netif)
        if net.up:
            # this is similar to net.attach() but uses netif.name instead 
            # of localname
            check_call([BRCTL_BIN, "addif", net.brname, netif.name])
            check_call([IP_BIN, "link", "set", netif.name, "up"])
        i = net.newifindex()
        net._netif[i] = netif
        with net._linked_lock:
            net._linked[netif] = {}
        netif.net = self
        netif.othernet = net
        return netif
        
    def getlinknetif(self, net):
        ''' Return the interface of that links this net with another net
        (that were linked using linknet()).
        '''
        for netif in self.netifs():
            if hasattr(netif, 'othernet') and netif.othernet == net:
                return netif
        return None

    def addrconfig(self, addrlist):
        ''' Set addresses on the bridge.
        '''
        if not self.up:
            return
        for addr in addrlist:
            try:
                check_call([IP_BIN, "addr", "add", str(addr), "dev", self.brname])
            except Exception, e:
                self.exception(coreapi.CORE_EXCP_LEVEL_ERROR, self.brname,
                               "Error adding IP address: %s" % e)

class GreTapBridge(LxBrNet):
    ''' A network consisting of a bridge with a gretap device for tunneling to 
        another system.
    '''
    def __init__(self, session, remoteip = None, objid = None, name = None,
                 policy = "ACCEPT", localip = None, ttl = 255, key = None,
                 verbose = False, start = True):
        LxBrNet.__init__(self, session = session, objid = objid,
                      name = name, verbose = verbose, policy = policy,
                      start = False)
        self.grekey = key
        if self.grekey is None:
            self.grekey = self.session.sessionid ^ self.objid
        self.localnum = None
        self.remotenum = None
        self.remoteip = remoteip
        self.localip = localip
        self.ttl = ttl
        if remoteip is None:
            self.gretap = None
        else:
            self.gretap = GreTap(node = self, name = None, session = session,
                                    remoteip = remoteip, objid = None, localip = localip, ttl = ttl,
                                    key = self.grekey)
        if start:
            self.startup()

    def startup(self):
        ''' Creates a bridge and adds the gretap device to it.
        '''
        LxBrNet.startup(self)
        if self.gretap:
            self.attach(self.gretap)

    def shutdown(self):
        ''' Detach the gretap device and remove the bridge.
        '''
        if self.gretap:
            self.detach(self.gretap)
            self.gretap.shutdown()
            self.gretap = None
        LxBrNet.shutdown(self)
    
    def addrconfig(self, addrlist):
        ''' Set the remote tunnel endpoint. This is a one-time method for 
            creating the GreTap device, which requires the remoteip at startup.
            The 1st address in the provided list is remoteip, 2nd optionally
            specifies localip.
        '''
        if self.gretap:
            raise ValueError, "gretap already exists for %s" % self.name
        remoteip = addrlist[0].split('/')[0]
        localip = None
        if len(addrlist) > 1:
            localip = addrlist[1].split('/')[0]
        self.gretap = GreTap(session = self.session, remoteip = remoteip,
                             objid = None, name = None,
                             localip = localip, ttl = self.ttl, key = self.grekey)
        self.attach(self.gretap)

    def setkey(self, key):
        ''' Set the GRE key used for the GreTap device. This needs to be set
            prior to instantiating the GreTap device (before addrconfig).
        '''
        self.grekey = key
