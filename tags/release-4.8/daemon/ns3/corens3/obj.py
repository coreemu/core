#
# CORE
# Copyright (c)2011-2013 the Boeing Company.
# See the LICENSE file included in this directory.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
ns3.py: defines classes for running emulations with ns-3 simulated networks.
'''

import sys, os, threading, time

from core.netns.nodes import CoreNode
from core.coreobj import PyCoreNet
from core.session import Session
from core.misc import ipaddr
from core.constants import *
from core.misc.utils import maketuple, check_call
from core.api import coreapi
from core.mobility import WayPointMobility

try:
    import ns.core
except Exception, e:
    print "Could not locate the ns-3 Python bindings!"
    print "Try running again from within the ns-3 './waf shell'\n"
    raise Exception, e
import ns.lte
import ns.mobility
import ns.network
import ns.internet
import ns.tap_bridge
import ns.wifi
import ns.wimax


ns.core.GlobalValue.Bind("SimulatorImplementationType",
                         ns.core.StringValue("ns3::RealtimeSimulatorImpl"))
ns.core.GlobalValue.Bind("ChecksumEnabled", ns.core.BooleanValue("true"))

class CoreNs3Node(CoreNode, ns.network.Node):
    ''' The CoreNs3Node is both a CoreNode backed by a network namespace and
    an ns-3 Node simulator object. When linked to simulated networks, the TunTap
    device will be used.
    '''
    def __init__(self, *args, **kwds):
        ns.network.Node.__init__(self)
        objid = self.GetId() + 1  # ns-3 ID starts at 0, CORE uses 1
        if 'objid' not in kwds:
            kwds['objid'] = objid
        CoreNode.__init__(self, *args, **kwds)

    def newnetif(self, net = None, addrlist = [], hwaddr = None,
                 ifindex = None, ifname = None):
        ''' Add a network interface. If we are attaching to a CoreNs3Net, this
        will be a TunTap. Otherwise dispatch to CoreNode.newnetif().
        '''
        if not isinstance(net, CoreNs3Net):
            return CoreNode.newnetif(self, net, addrlist, hwaddr, ifindex, 
                                    ifname)
        ifindex = self.newtuntap(ifindex = ifindex, ifname = ifname, net = net) 
        self.attachnet(ifindex, net)
        netif = self.netif(ifindex)
        netif.sethwaddr(hwaddr)
        for addr in maketuple(addrlist):
            netif.addaddr(addr)
        
        addrstr = netif.addrlist[0]
        (addr, mask) = addrstr.split('/')
        tap = net._tapdevs[netif]
        tap.SetAttribute("IpAddress",
                         ns.network.Ipv4AddressValue(ns.network.Ipv4Address(addr)))
        tap.SetAttribute("Netmask",
                         ns.network.Ipv4MaskValue(ns.network.Ipv4Mask("/" + mask)))
        ns.core.Simulator.Schedule(ns.core.Time('0'), netif.install)
        return ifindex
        
    def getns3position(self):
        ''' Return the ns-3 (x, y, z) position of a node.
        '''
        try:
            mm = self.GetObject(ns.mobility.MobilityModel.GetTypeId())
            pos = mm.GetPosition()
            return (pos.x, pos.y, pos.z)
        except AttributeError:
            self.warn("ns-3 mobility model not found")
            return (0,0,0)

    def setns3position(self, x, y, z):
        ''' Set the ns-3 (x, y, z) position of a node.
        '''
        try:
            mm = self.GetObject(ns.mobility.MobilityModel.GetTypeId())
            if z is None:
                z = 0.0
            pos = mm.SetPosition(ns.core.Vector(x, y, z))
        except AttributeError:
            self.warn("ns-3 mobility model not found, not setting position")

class CoreNs3Net(PyCoreNet):
    ''' The CoreNs3Net is a helper PyCoreNet object. Networks are represented
    entirely in simulation with the TunTap device bridging the emulated and
    simulated worlds.
    '''
    apitype = coreapi.CORE_NODE_WLAN
    linktype = coreapi.CORE_LINK_WIRELESS
    type = "wlan" # icon used

    def __init__(self, session, objid = None, name = None, verbose = False, 
                        start = True, policy = None):
        PyCoreNet.__init__(self, session, objid, name)
        self.tapbridge = ns.tap_bridge.TapBridgeHelper()
        self._ns3devs = {}
        self._tapdevs = {}

    def attach(self, netif):
        ''' Invoked from netif.attach(). Create a TAP device using the TapBridge
        object. Call getns3dev() to get model-specific device.
        '''
        self._netif[netif] = netif
        self._linked[netif] = {}
        ns3dev = self.getns3dev(netif.node)
        tap = self.tapbridge.Install(netif.node, ns3dev) 
        tap.SetMode(ns.tap_bridge.TapBridge.CONFIGURE_LOCAL)
        tap.SetAttribute("DeviceName", ns.core.StringValue(netif.localname))
        self._ns3devs[netif] = ns3dev
        self._tapdevs[netif] = tap
    
    def getns3dev(self, node):
        ''' Implement depending on network helper. Install this network onto
        the given node and return the device. Register the ns3 device into
        self._ns3devs
        '''
        raise NotImplementedError
        
    def findns3dev(self, node):
        ''' Given a node, return the interface and ns3 device associated with
        this network.
        '''
        for netif in node.netifs():
            if netif in self._ns3devs:
                return netif, self._ns3devs[netif]
        return None, None

    def shutdown(self):
        ''' Session.shutdown() will invoke this.
        '''
        pass
        
    def usecorepositions(self):
        ''' Set position callbacks for interfaces on this net so the CORE GUI
        can update the ns-3 node position when moved with the mouse.
        '''
        for netif in self.netifs():
            netif.poshook = self.setns3position
            
    def setns3position(self, netif, x, y, z):
        #print "setns3position: %s (%s, %s, %s)" % (netif.node.name, x, y, z)
        netif.node.setns3position(x, y, z)


class Ns3LteNet(CoreNs3Net):
    def __init__(self, *args, **kwds):
        ''' Uses a LteHelper to create an ns-3 based LTE network.
        '''
        CoreNs3Net.__init__(self, *args, **kwds)
        self.lte = ns.lte.LteHelper()
        # enhanced NodeB node list
        self.enbnodes = []
        self.dlsubchannels = None
        self.ulsubchannels = None

    def setsubchannels(self, downlink, uplink):
        ''' Set the downlink/uplink subchannels, which are a list of ints.
        These should be set prior to using CoreNs3Node.newnetif().
        '''
        self.dlsubchannels = downlink
        self.ulsubchannels = uplink
        
    def setnodeb(self, node):
        ''' Mark the given node as a nodeb (base transceiver station)
        '''
        self.enbnodes.append(node)
    
    def linknodeb(self, node, nodeb, mob, mobb):
        ''' Register user equipment with a nodeb.
        Optionally install mobility model while we have the ns-3 devs handy.
        '''
        (tmp, nodebdev) = self.findns3dev(nodeb)
        (tmp, dev) = self.findns3dev(node)
        if nodebdev is None or dev is None:
            raise KeyError, "ns-3 device for node not found"
        self.lte.RegisterUeToTheEnb(dev, nodebdev)
        if mob:
            self.lte.AddMobility(dev.GetPhy(), mob)
        if mobb:
            self.lte.AddDownlinkChannelRealization(mobb, mob, dev.GetPhy())
        
    def getns3dev(self, node):
        ''' Get the ns3 NetDevice using the LteHelper.
        '''
        if node in self.enbnodes:
            devtype = ns.lte.LteHelper.DEVICE_TYPE_ENODEB
        else:
            devtype = ns.lte.LteHelper.DEVICE_TYPE_USER_EQUIPMENT
        nodes = ns.network.NodeContainer(node)
        devs = self.lte.Install(nodes, devtype)
        devs.Get(0).GetPhy().SetDownlinkSubChannels(self.dlsubchannels)
        devs.Get(0).GetPhy().SetUplinkSubChannels(self.ulsubchannels)
        return devs.Get(0)

    def attach(self, netif):
        ''' Invoked from netif.attach(). Create a TAP device using the TapBridge
        object. Call getns3dev() to get model-specific device.
        '''
        self._netif[netif] = netif
        self._linked[netif] = {}
        ns3dev = self.getns3dev(netif.node)
        self.tapbridge.SetAttribute("Mode", ns.core.StringValue("UseLocal"))
        #self.tapbridge.SetAttribute("Mode",
        #                ns.core.IntegerValue(ns.tap_bridge.TapBridge.USE_LOCAL))
        tap = self.tapbridge.Install(netif.node, ns3dev) 
        #tap.SetMode(ns.tap_bridge.TapBridge.USE_LOCAL)
        print "using TAP device %s for %s/%s" % \
            (netif.localname, netif.node.name, netif.name)
        check_call(['tunctl', '-t', netif.localname, '-n'])
        #check_call([IP_BIN, 'link', 'set', 'dev', netif.localname, \
        #    'address', '%s' % netif.hwaddr])
        check_call([IP_BIN, 'link', 'set', netif.localname, 'up'])
        tap.SetAttribute("DeviceName", ns.core.StringValue(netif.localname))
        self._ns3devs[netif] = ns3dev
        self._tapdevs[netif] = tap

class Ns3WifiNet(CoreNs3Net):
    def __init__(self, *args, **kwds):
        ''' Uses a WifiHelper to create an ns-3 based Wifi network.
        '''
        rate = kwds.pop('rate', 'OfdmRate54Mbps')
        CoreNs3Net.__init__(self, *args, **kwds)
        self.wifi = ns.wifi.WifiHelper().Default()
        self.wifi.SetStandard(ns.wifi.WIFI_PHY_STANDARD_80211a)
        self.wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                          "DataMode", 
                                          ns.core.StringValue(rate),
                                          "NonUnicastMode",
                                          ns.core.StringValue(rate))
        self.mac = ns.wifi.NqosWifiMacHelper.Default()
        self.mac.SetType("ns3::AdhocWifiMac")

        channel = ns.wifi.YansWifiChannelHelper.Default()
        self.phy = ns.wifi.YansWifiPhyHelper.Default()
        self.phy.SetChannel(channel.Create())

    def getns3dev(self, node):
        ''' Get the ns3 NetDevice using the WifiHelper.
        '''
        devs = self.wifi.Install(self.phy, self.mac, node)
        return devs.Get(0)
    
        
class Ns3WimaxNet(CoreNs3Net):
    def __init__(self, *args, **kwds):
        CoreNs3Net.__init__(self, *args, **kwds)
        self.wimax = ns.wimax.WimaxHelper()
        self.scheduler = ns.wimax.WimaxHelper.SCHED_TYPE_SIMPLE
        self.phy = ns.wimax.WimaxHelper.SIMPLE_PHY_TYPE_OFDM
        # base station node list
        self.bsnodes = []
    
    def setbasestation(self, node):
        self.bsnodes.append(node)
        
    def getns3dev(self, node):
        if node in self.bsnodes:
            devtype = ns.wimax.WimaxHelper.DEVICE_TYPE_BASE_STATION
        else:
            devtype = ns.wimax.WimaxHelper.DEVICE_TYPE_SUBSCRIBER_STATION
        nodes = ns.network.NodeContainer(node)
        devs = self.wimax.Install(nodes, devtype, self.phy, self.scheduler)
        if node not in self.bsnodes:
            devs.Get(0).SetModulationType(ns.wimax.WimaxPhy.MODULATION_TYPE_QAM16_12)
        # debug
        self.wimax.EnableAscii("wimax-device-%s" % node.name, devs)
        return devs.Get(0)
            
    @staticmethod
    def ipv4netifaddr(netif):
        for addr in netif.addrlist:
            if ':' in addr:
                continue # skip ipv6
            ip = ns.network.Ipv4Address(addr.split('/')[0])
            mask = ns.network.Ipv4Mask('/' + addr.split('/')[1])
            return (ip, mask)
        return (None, None)
            

    def addflow(self, node1, node2, upclass, downclass):
        ''' Add a Wimax service flow between two nodes.
        '''
        (netif1, ns3dev1) = self.findns3dev(node1)
        (netif2, ns3dev2) = self.findns3dev(node2)
        if not netif1 or not netif2:
            raise ValueError, "interface not found"
        (addr1, mask1) = self.ipv4netifaddr(netif1)
        (addr2, mask2) = self.ipv4netifaddr(netif2)
        clargs1 = (addr1, mask1, addr2, mask2) + downclass 
        clargs2 = (addr2, mask2, addr1, mask1) + upclass 
        clrec1 = ns.wimax.IpcsClassifierRecord(*clargs1)
        clrec2 = ns.wimax.IpcsClassifierRecord(*clargs2)
        ns3dev1.AddServiceFlow( \
                self.wimax.CreateServiceFlow(ns.wimax.ServiceFlow.SF_DIRECTION_DOWN,
                                             ns.wimax.ServiceFlow.SF_TYPE_RTPS, clrec1))
        ns3dev1.AddServiceFlow( \
                self.wimax.CreateServiceFlow(ns.wimax.ServiceFlow.SF_DIRECTION_UP,
                                             ns.wimax.ServiceFlow.SF_TYPE_RTPS, clrec2))
        ns3dev2.AddServiceFlow( \
                self.wimax.CreateServiceFlow(ns.wimax.ServiceFlow.SF_DIRECTION_DOWN,
                                             ns.wimax.ServiceFlow.SF_TYPE_RTPS, clrec2))
        ns3dev2.AddServiceFlow( \
                self.wimax.CreateServiceFlow(ns.wimax.ServiceFlow.SF_DIRECTION_UP,
                                             ns.wimax.ServiceFlow.SF_TYPE_RTPS, clrec1))


class Ns3Session(Session):
    ''' A Session that starts an ns-3 simulation thread.
    '''
    def __init__(self, persistent = False, duration=600):
        self.duration = duration
        self.nodes = ns.network.NodeContainer()
        self.mobhelper = ns.mobility.MobilityHelper()
        Session.__init__(self, persistent = persistent)

    def run(self, vis=False):
        ''' Run the ns-3 simulation and return the simulator thread.
        '''
        def runthread():
            ns.core.Simulator.Stop(ns.core.Seconds(self.duration))
            print "running ns-3 simulation for %d seconds" % self.duration
            if vis:
                try:
                    import visualizer
                except ImportError:
                    print "visualizer is not available"
                    ns.core.Simulator.Run()
                else:
                    visualizer.start()
            else:
                ns.core.Simulator.Run()
        #self.evq.run() # event queue may have WayPointMobility events
        self.setstate(coreapi.CORE_EVENT_RUNTIME_STATE, info=True,
                      sendevent=True)
        t = threading.Thread(target = runthread)
        t.daemon = True
        t.start()
        return t
        
    def shutdown(self):
        # TODO: the following line tends to segfault ns-3 (and therefore
        #       core-daemon)
        ns.core.Simulator.Destroy()
        Session.shutdown(self)

    def addnode(self, name):
        ''' A convenience helper for Session.addobj(), for adding CoreNs3Nodes
        to this session. Keeps a NodeContainer for later use.
        '''
        n = self.addobj(cls = CoreNs3Node, name=name)
        self.nodes.Add(n)
        return n
        
    def setupconstantmobility(self):
        ''' Install a ConstantPositionMobilityModel.
        '''
        palloc = ns.mobility.ListPositionAllocator()
        for i in xrange(self.nodes.GetN()):
            (x, y, z) = ((100.0 * i) + 50, 200.0, 0.0)
            palloc.Add(ns.core.Vector(x, y, z))
            node = self.nodes.Get(i)
            node.position.set(x, y, z)
        self.mobhelper.SetPositionAllocator(palloc)
        self.mobhelper.SetMobilityModel("ns3::ConstantPositionMobilityModel")
        self.mobhelper.Install(self.nodes)
        
    def setuprandomwalkmobility(self, bounds, time=10, speed=25.0):
        ''' Set up the random walk mobility model within a bounding box.
           - bounds is the max (x, y, z) boundary
           - time is the number of seconds to maintain the current speed
             and direction
           - speed is the maximum speed, with node speed randomly chosen
             from [0, speed]
        '''
        (x, y, z) = map(float, bounds)
        self.mobhelper.SetPositionAllocator("ns3::RandomBoxPositionAllocator",
            "X",
            ns.core.StringValue("ns3::UniformRandomVariable[Min=0|Max=%s]" % x),
            "Y",
            ns.core.StringValue("ns3::UniformRandomVariable[Min=0|Max=%s]" % y),
            "Z",
            ns.core.StringValue("ns3::UniformRandomVariable[Min=0|Max=%s]" % z))
        self.mobhelper.SetMobilityModel("ns3::RandomWalk2dMobilityModel",
                "Mode", ns.core.StringValue("Time"),
                "Time", ns.core.StringValue("%ss" % time),
                "Speed",
                ns.core.StringValue("ns3::UniformRandomVariable[Min=0|Max=%s]" \
                                     % speed),
                "Bounds", ns.core.StringValue("0|%s|0|%s" % (x, y)))
        self.mobhelper.Install(self.nodes)
        
    def startns3mobility(self, refresh_ms=300):
        ''' Start a thread that updates CORE nodes based on their ns-3
        positions.
        '''
        self.setstate(coreapi.CORE_EVENT_INSTANTIATION_STATE)
        self.mobilitythread = threading.Thread(
                                        target=self.ns3mobilitythread,
                                        args=(refresh_ms,))
        self.mobilitythread.daemon = True
        self.mobilitythread.start()

    def ns3mobilitythread(self, refresh_ms):
        ''' Thread target that updates CORE nodes every refresh_ms based on
        their ns-3 positions.
        '''
        valid_states = (coreapi.CORE_EVENT_RUNTIME_STATE,
                        coreapi.CORE_EVENT_INSTANTIATION_STATE)
        while self.getstate() in valid_states:
            for i in xrange(self.nodes.GetN()):
                node = self.nodes.Get(i)
                (x, y, z) = node.getns3position()
                if (x, y, z) == node.position.get():
                    continue
                # from WayPointMobility.setnodeposition(node, x, y, z)
                node.position.set(x, y, z)
                msg = node.tonodemsg(flags=0)
                self.broadcastraw(None, msg)
                self.sdt.updatenode(node.objid, flags=0, x=x, y=y, z=z)
            time.sleep(0.001 * refresh_ms)

    def setupmobilitytracing(self, net, filename, nodes, verbose=False):
        ''' Start a tracing thread using the ASCII output from the ns3 
        mobility helper.
        '''
        net.mobility = WayPointMobility(session=self, objid=net.objid,
                                        verbose=verbose, values=None)
        net.mobility.setendtime()
        net.mobility.refresh_ms = 300
        net.mobility.empty_queue_stop = False
        of = ns.network.OutputStreamWrapper(filename, filemode=777)
        self.mobhelper.EnableAsciiAll(of)
        self.mobilitytracethread = threading.Thread(target=self.mobilitytrace,
                                        args=(net, filename, nodes, verbose))
        self.mobilitytracethread.daemon = True
        self.mobilitytracethread.start()

    def mobilitytrace(self, net, filename, nodes, verbose):
        nodemap = {}
        # move nodes to initial positions
        for node in nodes:
            (x,y,z) = node.getns3position()
            net.mobility.setnodeposition(node, x, y, z)
            nodemap[node.GetId()] = node

        if verbose:
            self.info("mobilitytrace opening '%s'" % filename)
        try:
            f = open(filename)
            f.seek(0,2)
        except Exception, e:
            self.warn("mobilitytrace error opening '%s': %s" % (filename, e))
        sleep = 0.001
        kickstart = True
        while True:
            if self.getstate() != coreapi.CORE_EVENT_RUNTIME_STATE:
                break
            line = f.readline()
            if not line:
                time.sleep(sleep)
                if sleep < 1.0:
                    sleep += 0.001
                continue
            sleep = 0.001
            items = dict(map(lambda x: x.split('='), line.split()))
            if verbose:
                self.info("trace: %s %s %s" % \
                             (items['node'], items['pos'], items['vel']))
            (x, y, z) = map(float, items['pos'].split(':'))
            vel = map(float, items['vel'].split(':'))
            node = nodemap[int(items['node'])]
            net.mobility.addwaypoint(time=0, nodenum=node.objid,
                                     x=x, y=y, z=z, speed=vel)
            if kickstart:
                kickstart = False
                self.evq.add_event(0, net.mobility.start)
                self.evq.run()
            else:
                if net.mobility.state != net.mobility.STATE_RUNNING:
                    net.mobility.state = net.mobility.STATE_RUNNING
                    self.evq.add_event(0, net.mobility.runround)
            
        f.close()


