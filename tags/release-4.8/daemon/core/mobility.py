#
# CORE
# Copyright (c)2011-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
mobility.py: mobility helpers for moving nodes and calculating wireless range.
'''
import sys, os, time, string, math, threading
import heapq
from core.api import coreapi
from core.conf import ConfigurableManager, Configurable
from core.coreobj import PyCoreNode
from core.misc.utils import check_call
from core.misc.ipaddr import IPAddr

class MobilityManager(ConfigurableManager):
    ''' Member of session class for handling configuration data for mobility and
    range models.
    '''
    _name = "MobilityManager"
    _type = coreapi.CORE_TLV_REG_WIRELESS
    
    def __init__(self, session):
        ConfigurableManager.__init__(self, session)
        self.verbose = self.session.getcfgitembool('verbose', False)
        # configurations for basic range, indexed by WLAN node number, are
        # stored in self.configs
        # mapping from model names to their classes
        self._modelclsmap = {}
        # dummy node objects for tracking position of nodes on other servers
        self.phys = {}
        self.physnets = {}
        self.session.broker.handlers += (self.physnodehandlelink, )
        self.register()

    def startup(self, nodenums=None):
        ''' Session is transitioning from instantiation to runtime state.
        Instantiate any mobility models that have been configured for a WLAN.
        '''
        if nodenums is None:
            nodenums = self.configs.keys()
            
        for nodenum in nodenums:
            try:
                n = self.session.obj(nodenum)
            except KeyError:
                self.session.warn("Skipping mobility configuration for unknown"
                                "node %d." % nodenum)
                continue
            if nodenum not in self.configs:
                self.session.warn("Missing mobility configuration for node "
                                  "%d." % nodenum)
                continue
            v = self.configs[nodenum]
            for model in v:
                try:
                    cls = self._modelclsmap[model[0]]
                except KeyError:
                    self.session.warn("Skipping mobility configuration for "
                                      "unknown model '%s'" % model[0])
                    continue
                n.setmodel(cls, model[1])
            if self.session.master:
                self.installphysnodes(n)
            if n.mobility:
                self.session.evq.add_event(0.0, n.mobility.startup)
        return ()


    def reset(self):
        ''' Reset all configs.
        '''
        self.clearconfig(nodenum=None)
        
    def setconfig(self, nodenum, conftype, values):
        ''' Normal setconfig() with check for run-time updates for WLANs.
        '''
        super(MobilityManager, self).setconfig(nodenum, conftype, values)
        if self.session is None:
            return
        if self.session.getstate() == coreapi.CORE_EVENT_RUNTIME_STATE:
            try:
                n = self.session.obj(nodenum)
            except KeyError:
                self.session.warn("Skipping mobility configuration for unknown"
                                "node %d." % nodenum)
            n.updatemodel(conftype, values)

    def register(self):
        ''' Register models as configurable object(s) with the Session object.
        '''
        models = [BasicRangeModel, Ns2ScriptedMobility]
        for m in models:
            self.session.addconfobj(m._name, m._type, m.configure_mob)
            self._modelclsmap[m._name] = m
    
    def handleevent(self, msg):
        ''' Handle an Event Message used to start, stop, or pause 
            mobility scripts for a given WlanNode.
        '''
        eventtype = msg.gettlv(coreapi.CORE_TLV_EVENT_TYPE)
        nodenum = msg.gettlv(coreapi.CORE_TLV_EVENT_NODE)
        name = msg.gettlv(coreapi.CORE_TLV_EVENT_NAME)
        try:
            node = self.session.obj(nodenum)
        except KeyError:
            self.session.warn("Ignoring event for model '%s', unknown node " \
                              "'%s'" % (name, nodenum))
            return
        
        # name is e.g. "mobility:ns2script"
        models = name[9:].split(',')
        for m in models:
            try:
                cls = self._modelclsmap[m]
            except KeyError:
                self.session.warn("Ignoring event for unknown model '%s'" % m)
                continue
                _name = "waypoint"
            if cls._type == coreapi.CORE_TLV_REG_WIRELESS:
                model = node.mobility
            elif cls._type == coreapi.CORE_TLV_REG_MOBILITY:
                model = node.mobility
            else:
                continue
            if model is None:
                self.session.warn("Ignoring event, %s has no model" % node.name)
                continue
            if cls._name != model._name:
                self.session.warn("Ignoring event for %s wrong model %s,%s" % \
                                  (node.name, cls._name, model._name))
                continue
            
            if eventtype == coreapi.CORE_EVENT_STOP or \
                eventtype == coreapi.CORE_EVENT_RESTART:
                model.stop(move_initial=True)
            if eventtype == coreapi.CORE_EVENT_START or \
                eventtype == coreapi.CORE_EVENT_RESTART:
                model.start()
            if eventtype == coreapi.CORE_EVENT_PAUSE:
                model.pause()
                
    def sendevent(self, model):
        ''' Send an event message on behalf of a mobility model.
            This communicates the current and end (max) times to the GUI.
        '''
        if model.state == model.STATE_STOPPED:
            eventtype = coreapi.CORE_EVENT_STOP
        elif model.state == model.STATE_RUNNING:
            eventtype = coreapi.CORE_EVENT_START
        elif model.state == model.STATE_PAUSED:
            eventtype = coreapi.CORE_EVENT_PAUSE
        data = "start=%d" % int(model.lasttime - model.timezero)
        data += " end=%d" % int(model.endtime)
        tlvdata = ""
        tlvdata += coreapi.CoreEventTlv.pack(coreapi.CORE_TLV_EVENT_NODE,
                                             model.objid)
        tlvdata += coreapi.CoreEventTlv.pack(coreapi.CORE_TLV_EVENT_TYPE,
                                             eventtype)
        tlvdata += coreapi.CoreEventTlv.pack(coreapi.CORE_TLV_EVENT_NAME,
                                             "mobility:%s" % model._name)
        tlvdata += coreapi.CoreEventTlv.pack(coreapi.CORE_TLV_EVENT_DATA,
                                             data)
        tlvdata += coreapi.CoreEventTlv.pack(coreapi.CORE_TLV_EVENT_TIME,
                                             "%s" % time.time())
        msg = coreapi.CoreEventMessage.pack(0, tlvdata)
        try:
            self.session.broadcastraw(None, msg)
        except Exception, e:
            self.warn("Error sending Event Message: %s" % e)
    
    def updatewlans(self, moved, moved_netifs):
        ''' A mobility script has caused nodes in the 'moved' list to move.
            Update every WlanNode. This saves range calculations if the model
            were to recalculate for each individual node movement.
        '''
        for nodenum in self.configs:
            try:
                n = self.session.obj(nodenum)
            except KeyError:
                continue
            if n.model:
                n.model.update(moved, moved_netifs)
    
    def addphys(self, netnum, node):
        ''' Keep track of PhysicalNodes and which network they belong to.
        '''
        nodenum = node.objid
        self.phys[nodenum] = node
        if netnum not in self.physnets:
            self.physnets[netnum] = [nodenum,]
        else:
            self.physnets[netnum].append(nodenum)
        
    def physnodehandlelink(self,  msg):
        ''' Broker handler. Snoop Link add messages to get
            node numbers of PhyiscalNodes and their nets.
            Physical nodes exist only on other servers, but a shadow object is
            created here for tracking node position.
        '''
        if msg.msgtype == coreapi.CORE_API_LINK_MSG and \
           msg.flags & coreapi.CORE_API_ADD_FLAG:
            nn = msg.nodenumbers()
            # first node is always link layer node in Link add message
            if nn[0] not in self.session.broker.nets:
                return
            if nn[1] in self.session.broker.phys:
                # record the fact that this PhysicalNode is linked to a net
                dummy = PyCoreNode(session=self.session, objid=nn[1],
                                  name="n%d" % nn[1], start=False)
                self.addphys(nn[0], dummy)
            
    def physnodeupdateposition(self, msg):
        ''' Snoop node messages belonging to physical nodes. The dummy object
        in self.phys[] records the node position.
        '''
        nodenum = msg.nodenumbers()[0]
        try:
            dummy = self.phys[nodenum]
            nodexpos = msg.gettlv(coreapi.CORE_TLV_NODE_XPOS)
            nodeypos = msg.gettlv(coreapi.CORE_TLV_NODE_YPOS)
            dummy.setposition(nodexpos, nodeypos, None)
        except KeyError:
            pass
    
    def installphysnodes(self, net):
        ''' After installing a mobility model on a net, include any physical
        nodes that we have recorded. Use the GreTap tunnel to the physical node
        as the node's interface.
        '''
        try:
            nodenums = self.physnets[net.objid]
        except KeyError:
            return
        for nodenum in nodenums:
            node = self.phys[nodenum]
            servers = self.session.broker.getserversbynode(nodenum)
            (host, port, sock) = self.session.broker.getserver(servers[0])
            netif = self.session.broker.gettunnel(net.objid, IPAddr.toint(host))
            node.addnetif(netif, 0)
            netif.node = node
            (x,y,z) = netif.node.position.get()
            netif.poshook(netif, x, y, z)


class WirelessModel(Configurable):
    ''' Base class used by EMANE models and the basic range model. 
    Used for managing arbitrary configuration parameters.
    '''
    _type = coreapi.CORE_TLV_REG_WIRELESS
    _bitmap = None
    _positioncallback = None

    def __init__(self, session, objid, verbose = False, values = None):
        Configurable.__init__(self, session, objid)
        self.verbose = verbose
        # 'values' can be retrieved from a ConfigurableManager, or used here
        # during initialization, depending on the model.
    
    def tolinkmsgs(self, flags):
        ''' May be used if the model can populate the GUI with wireless (green)
            link lines.
        '''
        return []
        
    def update(self, moved, moved_netifs):
        raise NotImplementedError
        
    def updateconfig(self, values):
        ''' For run-time updates of model config.
        Returns True when self._positioncallback() and self.setlinkparams()
        should be invoked.
        '''
        return False


class BasicRangeModel(WirelessModel):
    ''' Basic Range wireless model, calculates range between nodes and links
    and unlinks nodes based on this distance. This was formerly done from
    the GUI.
    '''
    _name = "basic_range"

    # configuration parameters are
    #  ( 'name', 'type', 'default', 'possible-value-list', 'caption')
    _confmatrix = [
        ("range", coreapi.CONF_DATA_TYPE_UINT32, '275',
         '', 'wireless range (pixels)'),
        ("bandwidth", coreapi.CONF_DATA_TYPE_UINT32, '54000', 
         '', 'bandwidth (bps)'),
        ("jitter", coreapi.CONF_DATA_TYPE_FLOAT, '0.0', 
         '', 'transmission jitter (usec)'),
        ("delay", coreapi.CONF_DATA_TYPE_FLOAT, '5000.0', 
         '', 'transmission delay (usec)'),
        ("error", coreapi.CONF_DATA_TYPE_FLOAT, '0.0', 
         '', 'error rate (%)'),
    ]

    # value groupings
    _confgroups = "Basic Range Parameters:1-%d" % len(_confmatrix)
    
    def __init__(self, session, objid, verbose = False, values=None):
        ''' Range model is only instantiated during runtime.
        '''
        super(BasicRangeModel, self).__init__(session = session, objid = objid,
                                              verbose = verbose)
        self.wlan = session.obj(objid)
        self._netifs = {}
        self._netifslock = threading.Lock()
        if values is None:
            values = session.mobility.getconfig(objid, self._name,
                                            self.getdefaultvalues())[1]
        self.range = float(self.valueof("range",  values))
        if self.verbose:
            self.session.info("Basic range model configured for WLAN %d using" \
                " range %d" % (objid, self.range))
        self.valuestolinkparams(values)

    def valuestolinkparams(self, values):
        self.bw = int(self.valueof("bandwidth", values))
        if self.bw == 0.0:
            self.bw = None
        self.delay = float(self.valueof("delay", values))
        if self.delay == 0.0:
            self.delay = None
        self.loss = float(self.valueof("error", values))
        if self.loss == 0.0:
            self.loss = None
        self.jitter = float(self.valueof("jitter", values))
        if self.jitter == 0.0:
            self.jitter = None

    @classmethod
    def configure_mob(cls, session, msg):
        ''' Handle configuration messages for setting up a model.
        Pass the MobilityManager object as the manager object.
        '''
        return cls.configure(session.mobility, msg)
        
    def setlinkparams(self):
        ''' Apply link parameters to all interfaces. This is invoked from
        WlanNode.setmodel() after the position callback has been set.
        '''
        with self._netifslock:
            for netif in self._netifs:
                self.wlan.linkconfig(netif, bw=self.bw, delay=self.delay,
                                    loss=self.loss, duplicate=None,
                                    jitter=self.jitter)

    def get_position(self, netif):
        with self._netifslock:
            return self._netifs[netif]

    def set_position(self, netif, x = None, y = None, z = None):
        ''' A node has moved; given an interface, a new (x,y,z) position has
        been set; calculate the new distance between other nodes and link or
        unlink node pairs based on the configured range.
        '''
        #print "set_position(%s, x=%s, y=%s, z=%s)" % (netif.localname, x, y, z)
        self._netifslock.acquire()
        self._netifs[netif] = (x, y, z)
        if x is None or y is None:
            self._netifslock.release()
            return
        for netif2 in self._netifs:
            self.calclink(netif, netif2)
        self._netifslock.release()
    
    _positioncallback = set_position

    def update(self, moved, moved_netifs):
        ''' Node positions have changed without recalc. Update positions from
        node.position, then re-calculate links for those that have moved.
        Assumes bidirectional links, with one calculation per node pair, where
        one of the nodes has moved.
        '''
        with self._netifslock:
            while len(moved_netifs):
                netif = moved_netifs.pop()
                (nx, ny, nz) = netif.node.getposition()
                if netif in self._netifs:
                    self._netifs[netif] = (nx, ny, nz)
                for netif2 in self._netifs:
                    if netif2 in moved_netifs:
                        continue
                    self.calclink(netif, netif2)

    def calclink(self, netif, netif2):
        ''' Helper used by set_position() and update() to
            calculate distance between two interfaces and perform
            linking/unlinking. Sends link/unlink messages and updates the
            WlanNode's linked dict.
        '''
        if netif == netif2:
            return
        try:
            (x, y, z) = self._netifs[netif]    
            (x2, y2, z2) = self._netifs[netif2]
        except KeyError:
            return
        if x2 is None or y2 is None:
            return
        
        d = self.calcdistance( (x,y,z), (x2,y2,z2) )
        # ordering is important, to keep the wlan._linked dict organized
        a = min(netif, netif2)
        b = max(netif, netif2)
        try:
            self.wlan._linked_lock.acquire()
            linked = self.wlan.linked(a, b)
        except KeyError:
            return
        finally:
            self.wlan._linked_lock.release()
        if d > self.range:
            if linked:
                self.wlan.unlink(a, b)
                self.sendlinkmsg(a, b, unlink=True)
        else:
            if not linked:
                self.wlan.link(a, b)
                self.sendlinkmsg(a, b)


    @staticmethod
    def calcdistance(p1, p2):
        ''' Calculate the distance between two three-dimensional points.
        '''
        a = p1[0] - p2[0]
        b = p1[1] - p2[1]
        c = 0
        if p1[2] is not None and p2[2] is not None:
            c = p1[2] - p2[2]
        return math.hypot(math.hypot(a, b), c)
        
    def updateconfig(self, values):
        ''' Configuration has changed during runtime.
        MobilityManager.setconfig() -> WlanNode.updatemodel() -> 
        WirelessModel.updateconfig()
        '''
        self.valuestolinkparams(values)
        self.range = float(self.valueof("range",  values))        
        return True
        
    def linkmsg(self, netif, netif2, flags):
        ''' Create a wireless link/unlink API message.
        '''
        n1 = netif.localname.split('.')[0]
        n2 = netif2.localname.split('.')[0]        
        tlvdata = coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_N1NUMBER,
                                            netif.node.objid)
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_N2NUMBER,
                                            netif2.node.objid)
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_NETID,
                                            self.wlan.objid)
        #tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_IF1NUM,
        #                                    netif.index)
        #tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_IF2NUM,
        #                                    netif2.index)
        tlvdata += coreapi.CoreLinkTlv.pack(coreapi.CORE_TLV_LINK_TYPE,
                                            coreapi.CORE_LINK_WIRELESS)
        return coreapi.CoreLinkMessage.pack(flags, tlvdata)
        
    def sendlinkmsg(self, netif, netif2, unlink=False):
        ''' Send a wireless link/unlink API message to the GUI.
        '''
        if unlink:
            flags = coreapi.CORE_API_DEL_FLAG
        else:
            flags = coreapi.CORE_API_ADD_FLAG
        msg = self.linkmsg(netif, netif2, flags)
        self.session.broadcastraw(src=None, data=msg)
        self.session.sdt.updatelink(netif.node.objid, netif2.node.objid, flags,
                                    wireless=True)

    def tolinkmsgs(self, flags):
        ''' Return a list of wireless link messages for when the GUI reconnects.
        '''
        r = []
        with self.wlan._linked_lock:
            for a in self.wlan._linked:
                for b in self.wlan._linked[a]:
                    if self.wlan._linked[a][b]:
                        r.append(self.linkmsg(a, b, flags))
        return r

class WayPointMobility(WirelessModel):
    ''' Abstract class for mobility models that set node waypoints.
    '''
    _name = "waypoint"
    _type = coreapi.CORE_TLV_REG_MOBILITY
    
    STATE_STOPPED = 0
    STATE_RUNNING = 1
    STATE_PAUSED = 2
    
    class WayPoint(object):
        def __init__(self, time, nodenum, coords, speed):
            self.time = time
            self.nodenum = nodenum
            self.coords = coords
            self.speed = speed
        
        def __cmp__(self, other):
            tmp = cmp(self.time, other.time)
            if tmp == 0:
                tmp = cmp(self.nodenum, other.nodenum)
            return tmp

    def __init__(self, session, objid, verbose = False, values = None):
        super(WayPointMobility, self).__init__(session = session, objid = objid,
                                               verbose = verbose, values = values)
        self.state = self.STATE_STOPPED
        self.queue = []
        self.queue_copy = []
        self.points = {}
        self.initial = {}
        self.lasttime = None
        self.endtime = None
        self.wlan = session.obj(objid)
        # these are really set in child class via confmatrix
        self.loop = False
        self.refresh_ms = 50
        # flag whether to stop scheduling when queue is empty
        #  (ns-3 sets this to False as new waypoints may be added from trace)
        self.empty_queue_stop = True
    
    def runround(self):
        ''' Advance script time and move nodes.
        '''
        if self.state != self.STATE_RUNNING:
            return        
        t = self.lasttime
        self.lasttime = time.time()
        now = self.lasttime - self.timezero
        dt = self.lasttime - t
        #print "runround(now=%.2f, dt=%.2f)" % (now, dt)
        
        # keep current waypoints up-to-date
        self.updatepoints(now)
        
        if not len(self.points):
            if len(self.queue):
                # more future waypoints, allow time for self.lasttime update
                nexttime = self.queue[0].time - now
                if nexttime > (0.001 * self.refresh_ms):
                    nexttime -= (0.001 * self.refresh_ms)
                self.session.evq.add_event(nexttime, self.runround)
                return
            else:
                # no more waypoints or queued items, loop?
                if not self.empty_queue_stop:
                    # keep running every refresh_ms, even with empty queue
                    self.session.evq.add_event(0.001 * self.refresh_ms, self.runround)
                    return
                if not self.loopwaypoints():
                    return self.stop(move_initial=False)
                if not len(self.queue):
                    # prevent busy loop
                    return
                return self.run()
        
        # only move netifs attached to self.wlan, or all nodenum in script?
        moved = []
        moved_netifs = []
        for netif in self.wlan.netifs():
            node = netif.node
            if self.movenode(node, dt):
                moved.append(node)
                moved_netifs.append(netif)
        
        # calculate all ranges after moving nodes; this saves calculations
        #self.wlan.model.update(moved)
        self.session.mobility.updatewlans(moved, moved_netifs)
        
        # TODO: check session state
        self.session.evq.add_event(0.001 * self.refresh_ms, self.runround)

    def run(self):
        self.timezero = time.time()
        self.lasttime = self.timezero - (0.001 * self.refresh_ms)
        self.movenodesinitial()
        self.runround()
        self.session.mobility.sendevent(self)

    def movenode(self, node, dt):
        ''' Calculate next node location and update its coordinates. 
            Returns True if the node's position has changed.
        '''
        if node.objid not in self.points:
            return False
        x1, y1, z1 = node.getposition()
        x2, y2, z2 = self.points[node.objid].coords
        speed = self.points[node.objid].speed
        # instantaneous move (prevents dx/dy == 0.0 below)
        if speed == 0:
            self.setnodeposition(node, x2, y2, z2)
            del self.points[node.objid]
            return True
        # speed can be a velocity vector (ns3 mobility) or speed value
        if isinstance(speed, (float, int)):
            # linear speed value
            alpha = math.atan2(y2 - y1, x2 - x1)
            sx = speed * math.cos(alpha)
            sy = speed * math.sin(alpha)
        else:
            # velocity vector
            sx = speed[0]
            sy = speed[1]

        # calculate dt * speed = distance moved
        dx = sx * dt
        dy = sy * dt
        # prevent overshoot
        if abs(dx) > abs(x2 - x1):
            dx = x2 - x1
        if abs(dy) > abs(y2 - y1):
            dy = y2 - y1
        if dx == 0.0 and dy == 0.0:
            if self.endtime < (self.lasttime - self.timezero):
                # the last node to reach the last waypoint determines this
                # script's endtime
                self.endtime = self.lasttime - self.timezero
            del self.points[node.objid]
            return False
        #print "node %s dx,dy= <%s, %d>" % (node.name, dx, dy)
        if (x1 + dx) < 0.0:
            dx = 0.0 - x1
        if (y1 + dy) < 0.0:
            dy = 0.0 - y1
        self.setnodeposition(node, x1 + dx, y1 + dy, z1)
        return True
        
    def movenodesinitial(self):
        ''' Move nodes to their initial positions. Then calculate the ranges.
        '''
        moved = []
        moved_netifs = []
        for netif in self.wlan.netifs():
            node = netif.node
            if node.objid not in self.initial:
                continue
            (x, y, z) = self.initial[node.objid].coords
            self.setnodeposition(node, x, y, z)
            moved.append(node)
            moved_netifs.append(netif)
        #self.wlan.model.update(moved)
        self.session.mobility.updatewlans(moved, moved_netifs)

    def addwaypoint(self, time, nodenum, x, y, z, speed):
        ''' Waypoints are pushed to a heapq, sorted by time.
        '''
        #print "addwaypoint: %s %s %s,%s,%s %s" % (time, nodenum, x, y, z, speed)
        wp = self.WayPoint(time, nodenum, coords=(x,y,z), speed=speed)
        heapq.heappush(self.queue, wp)
        
    def addinitial(self, nodenum, x, y, z):
        ''' Record initial position in a dict.
        '''
        wp = self.WayPoint(0, nodenum, coords=(x,y,z), speed=0)
        self.initial[nodenum] = wp
        
    def updatepoints(self, now):
        ''' Move items from self.queue to self.points when their time has come.
        '''
        while len(self.queue):
            if self.queue[0].time > now:
                break            
            wp = heapq.heappop(self.queue)
            self.points[wp.nodenum] = wp
    
    def copywaypoints(self):
        ''' Store backup copy of waypoints for looping and stopping.
        '''
        self.queue_copy = list(self.queue)
    
    def loopwaypoints(self):
        ''' Restore backup copy of waypoints when looping.
        '''
        self.queue = list(self.queue_copy)
        return self.loop

    def setnodeposition(self, node, x, y, z):
        ''' Helper to move a node, notify any GUI (connected session handlers),
            without invoking the interface poshook callback that may perform
            range calculation.
        '''
        # this would cause PyCoreNetIf.poshook() callback (range calculation)
        #node.setposition(x, y, z)
        node.position.set(x, y, z)
        msg = node.tonodemsg(flags=0)
        self.session.broadcastraw(None, msg)
        self.session.sdt.updatenode(node.objid, flags=0, x=x, y=y, z=z)
        
    def setendtime(self):
        ''' Set self.endtime to the time of the last waypoint in the queue of
            waypoints. This is just an estimate. The endtime will later be 
            adjusted, after one round of the script has run, to be the time
            that the last moving node has reached its final waypoint.
        '''
        try:
            self.endtime = self.queue[-1].time
        except IndexError:
            self.endtime = 0

    def start(self):
        ''' Run the script from the beginning or unpause from where it
            was before.
        '''
        laststate = self.state
        self.state = self.STATE_RUNNING
        if laststate == self.STATE_STOPPED or laststate == self.STATE_RUNNING:
            self.loopwaypoints()
            self.timezero = 0
            self.lasttime = 0
            self.run()
        elif laststate == self.STATE_PAUSED:
            now = time.time()
            self.timezero += now - self.lasttime
            self.lasttime = now - (0.001 * self.refresh_ms)
            self.runround()
        
    def stop(self, move_initial=True):
        ''' Stop the script and move nodes to initial positions.
        '''
        self.state = self.STATE_STOPPED
        self.loopwaypoints()
        self.timezero = 0
        self.lasttime = 0
        if move_initial:
            self.movenodesinitial()
        self.session.mobility.sendevent(self)
    
    def pause(self):
        ''' Pause the script; pause time is stored to self.lasttime.
        '''
        self.state = self.STATE_PAUSED
        self.lasttime = time.time()


class Ns2ScriptedMobility(WayPointMobility):
    ''' Handles the ns-2 script format, generated by scengen/setdest or
        BonnMotion.
    '''
    _name = "ns2script"

    _confmatrix = [
        ("file", coreapi.CONF_DATA_TYPE_STRING, '',
         '', 'mobility script file'),
        ("refresh_ms", coreapi.CONF_DATA_TYPE_UINT32, '50', 
         '', 'refresh time (ms)'),
        ("loop", coreapi.CONF_DATA_TYPE_BOOL, '1', 
         'On,Off', 'loop'),
        ("autostart", coreapi.CONF_DATA_TYPE_STRING, '', 
         '', 'auto-start seconds (0.0 for runtime)'),
        ("map", coreapi.CONF_DATA_TYPE_STRING, '',
         '', 'node mapping (optional, e.g. 0:1,1:2,2:3)'),
        ("script_start", coreapi.CONF_DATA_TYPE_STRING, '',
         '', 'script file to run upon start'),
        ("script_pause", coreapi.CONF_DATA_TYPE_STRING, '',
         '', 'script file to run upon pause'),
        ("script_stop", coreapi.CONF_DATA_TYPE_STRING, '',
         '', 'script file to run upon stop'),
    ]
    _confgroups = "ns-2 Mobility Script Parameters:1-%d" % len(_confmatrix)

    def __init__(self, session, objid, verbose = False, values = None):
        ''' 
        '''
        super(Ns2ScriptedMobility, self).__init__(session = session, objid = objid,
                                                  verbose = verbose, values = values)
        self._netifs = {}
        self._netifslock = threading.Lock()
        if values is None:
            values = session.mobility.getconfig(objid, self._name,
                                                self.getdefaultvalues())[1]
        self.file = self.valueof("file",  values)
        self.refresh_ms = int(self.valueof("refresh_ms", values))
        self.loop = (self.valueof("loop", values).lower() == "on")
        self.autostart = self.valueof("autostart", values)
        self.parsemap(self.valueof("map", values))
        self.script_start = self.valueof("script_start", values)
        self.script_pause = self.valueof("script_pause", values)
        self.script_stop = self.valueof("script_stop", values)
        if self.verbose:
            self.session.info("ns-2 scripted mobility configured for WLAN %d" \
                              " using file: %s" % (objid, self.file))
        self.readscriptfile()
        self.copywaypoints()
        self.setendtime()

    @classmethod
    def configure_mob(cls, session, msg):
        ''' Handle configuration messages for setting up a model.
        Pass the MobilityManager object as the manager object.
        '''
        return cls.configure(session.mobility, msg)
        
    def readscriptfile(self):
        ''' Read in mobility script from a file. This adds waypoints to a
            priority queue, sorted by waypoint time. Initial waypoints are
            stored in a separate dict.
        '''
        filename = self.findfile(self.file)
        try:
            f = open(filename, 'r')
        except IOError, e:
            self.session.warn("ns-2 scripted mobility failed to load file " \
                              " '%s' (%s)" % (self.file, e))
            return
        if self.verbose:
            self.session.info("reading ns-2 script file: %s" % filename)
        ln = 0
        ix = iy = iz = None
        inodenum = None
        for line in f:
            ln += 1
            if line[:2] != '$n':
                continue
            try:
                if line[:8] == "$ns_ at ":
                    if ix is not None and iy is not None:
                        self.addinitial(self.map(inodenum), ix, iy, iz)
                        ix = iy = iz = None
                    # waypoints:
                    #    $ns_ at 1.00 "$node_(6) setdest 500.0 178.0 25.0"
                    parts = line.split()
                    time = float(parts[2])
                    nodenum = parts[3][1+parts[3].index('('):parts[3].index(')')]
                    x = float(parts[5])
                    y = float(parts[6])
                    z = None
                    speed = float(parts[7].strip('"'))
                    self.addwaypoint(time, self.map(nodenum), x, y, z, speed)
                elif line[:7] == "$node_(":
                    # initial position (time=0, speed=0):
                    #    $node_(6) set X_ 780.0
                    parts = line.split()
                    time = 0.0
                    nodenum = parts[0][1+parts[0].index('('):parts[0].index(')')]
                    if parts[2] == 'X_':
                        if ix is not None and iy is not None:
                            self.addinitial(self.map(inodenum), ix, iy, iz)
                            ix = iy = iz = None
                        ix = float(parts[3])
                    elif parts[2] == 'Y_':
                        iy = float(parts[3])
                    elif parts[2] == 'Z_':
                        iz = float(parts[3])
                        self.addinitial(self.map(nodenum), ix, iy, iz)
                        ix = iy = iz = None
                    inodenum = nodenum
                else:
                    raise ValueError
            except ValueError, e:
                self.session.warn("skipping line %d of file %s '%s' (%s)" % \
                                  (ln, self.file, line, e))
                continue
        if ix is not None and iy is not None:
            self.addinitial(self.map(inodenum), ix, iy, iz)
    
    def findfile(self, fn):
        ''' Locate a script file. If the specified file doesn't exist, look in the
            same directory as the scenario file (session.filename), or in the default
            configs directory (~/.core/configs). This allows for sample files without
            absolute pathnames.
        '''
        if os.path.exists(fn):
            return fn
        if self.session.filename is not None:
            d = os.path.dirname(self.session.filename)
            sessfn = os.path.join(d, fn)
            if (os.path.exists(sessfn)):
                return sessfn
        if self.session.user is not None:
            userfn = os.path.join('/home', self.session.user, '.core', 'configs', fn)
            if (os.path.exists(userfn)):
                return userfn
        return fn
        
    def parsemap(self, mapstr):
        ''' Parse a node mapping string, given as a configuration parameter.
        '''
        self.nodemap = {}
        if mapstr.strip() == '':
            return
        for pair in mapstr.split(','):
            parts = pair.split(':')
            try:
                if len(parts) != 2:
                    raise ValueError
                self.nodemap[int(parts[0])] = int(parts[1])
            except ValueError:
                self.session.warn("ns-2 mobility node map error")
                return
        
    def map(self, nodenum):
        ''' Map one node number (from a script file) to another.
        '''
        nodenum = int(nodenum)
        try:
            return self.nodemap[nodenum]
        except KeyError:
            return nodenum
            
    def startup(self):
        ''' Start running the script if autostart is enabled.
            Move node to initial positions when any autostart time is specified.
            Ignore the script if autostart is an empty string (can still be
            started via GUI controls).
        '''
        if self.autostart == '':
            if self.verbose:
                self.session.info("not auto-starting ns-2 script for %s" % \
                                  self.wlan.name)
            return
        try:
            t = float(self.autostart)
        except ValueError:
            self.session.warn("Invalid auto-start seconds specified '%s' for " \
                              "%s" % (self.autostart, self.wlan.name))
            return
        self.movenodesinitial()
        if self.verbose:
            self.session.info("scheduling ns-2 script for %s autostart at %s" \
                              % (self.wlan.name, t))
        self.state = self.STATE_RUNNING
        self.session.evq.add_event(t, self.run)

    def start(self):
        ''' Handle the case when un-paused.
        '''
        laststate = self.state
        super(Ns2ScriptedMobility, self).start()
        if laststate == self.STATE_PAUSED:
            self.statescript("unpause")

    def run(self):
        ''' Start is pressed or autostart is triggered.
        '''
        super(Ns2ScriptedMobility, self).run()
        self.statescript("run")
        
    def pause(self):
        super(Ns2ScriptedMobility, self).pause()
        self.statescript("pause")
        
    def stop(self, move_initial=True):
        super(Ns2ScriptedMobility, self).stop(move_initial=move_initial)
        self.statescript("stop")
        
    def statescript(self, typestr):
        filename = None
        if typestr == "run" or typestr == "unpause":
            filename = self.script_start
        elif typestr == "pause":
            filename = self.script_pause
        elif typestr == "stop":
            filename = self.script_stop
        if filename is None or filename == '':
            return
        filename = self.findfile(filename)
        try:
            check_call(["/bin/sh", filename, typestr], 
                       cwd=self.session.sessiondir,
                       env=self.session.getenviron())
        except Exception, e:
            self.session.warn("Error running script '%s' for WLAN state %s: " \
                             "%s" % (filename, typestr, e))

        
