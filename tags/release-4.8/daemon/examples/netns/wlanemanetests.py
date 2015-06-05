#!/usr/bin/python

# Copyright (c)2011-2014 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
wlanemanetests.py - This script tests the performance of the WLAN device in
CORE by measuring various metrics:
    - delay experienced when pinging end-to-end
    - maximum TCP throughput achieved using iperf end-to-end
    - the CPU used and loss experienced when running an MGEN flow of UDP traffic

All MANET nodes are arranged in a row, so that any given node can only 
communicate with the node to its right or to its left. Performance is measured
using traffic that travels across each hop in the network. Static /32 routing
is used instead of any dynamic routing protocol.

Various underlying network types are tested:
    - bridged (the CORE default, uses ebtables)
    - bridged with netem (add link effects to the bridge using tc queues)
    - EMANE bypass - the bypass model just forwards traffic
    - EMANE RF-PIPE - the bandwidth (bitrate) is set very high / no restrictions
    - EMANE RF-PIPE - bandwidth is set similar to netem case
    - EMANE RF-PIPE - default connectivity is off and pathloss events are
                      generated to connect the nodes in a line

Results are printed/logged in CSV format.

'''

import os, sys, time, optparse, datetime, math
from string import Template
try:
    from core import pycore
except ImportError:
    # hack for Fedora autoconf that uses the following pythondir:
    if "/usr/lib/python2.6/site-packages" in sys.path:
        sys.path.append("/usr/local/lib/python2.6/site-packages")
    if "/usr/lib64/python2.6/site-packages" in sys.path:
        sys.path.append("/usr/local/lib64/python2.6/site-packages")
    if "/usr/lib/python2.7/site-packages" in sys.path:
        sys.path.append("/usr/local/lib/python2.7/site-packages")
    if "/usr/lib64/python2.7/site-packages" in sys.path:
        sys.path.append("/usr/local/lib64/python2.7/site-packages")
    from core import pycore
from core.misc import ipaddr
from core.misc.utils import mutecall
from core.constants import QUAGGA_STATE_DIR
from core.emane.emane import Emane
from core.emane.bypass import EmaneBypassModel
from core.emane.rfpipe import EmaneRfPipeModel

try:
    import emaneeventservice
    import emaneeventpathloss
except Exception, e:
    try:
        from emanesh.events import EventService
        from emanesh.events import PathlossEvent
    except Exception, e2:
        raise ImportError, "failed to import EMANE Python bindings:\n%s\n%s" % \
                           (e, e2)

# global Experiment object (for interaction with 'python -i')
exp = None

# move these to core.misc.utils
def readstat():
    f = open("/proc/stat", "r")
    lines = f.readlines()
    f.close()
    return lines

def numcpus():
    lines = readstat()
    n = 0
    for l in lines[1:]:
        if l[:3] != "cpu":
            break
        n += 1
    return n

def getcputimes(line):
    # return (user, nice, sys, idle) from a /proc/stat cpu line
    # assume columns are:
    # cpu# user nice sys idle iowait irq softirq steal guest (man 5 proc)
    items = line.split()
    (user, nice, sys, idle) = map(lambda(x): int(x), items[1:5])
    return [user, nice, sys, idle]

def calculatecpu(timesa, timesb):
    for i in range(len(timesa)):
        timesb[i] -= timesa[i]
    total = sum(timesb)
    if total == 0:
        return 0.0
    else:
        # subtract % time spent in idle time
        return 100 - ((100.0 * timesb[-1]) / total)

# end move these to core.misc.utils

class Cmd(object):
    ''' Helper class for running a command on a node and parsing the result. '''
    args = ""
    def __init__(self, node, verbose=False):
        ''' Initialize with a CoreNode (LxcNode) '''
        self.id = None
        self.stdin = None
        self.out = None
        self.node = node
        self.verbose = verbose
    
    def info(self,  msg):
        ''' Utility method for writing output to stdout.'''
        print msg
        sys.stdout.flush()

    def warn(self, msg):
        ''' Utility method for writing output to stderr. '''
        print >> sys.stderr, "XXX %s:" % self.node.name,  msg
        sys.stderr.flush()
        
    def run(self):
        ''' This is the primary method used for running this command. '''
        self.open()
        status = self.id.wait()
        r = self.parse()
        self.cleanup()
        return r
        
    def open(self):
        ''' Exceute call to node.popen(). '''
        self.id, self.stdin, self.out, self.err = \
               self.node.popen((self.args))
    
    def parse(self):
        ''' This method is overloaded by child classes and should return some
            result.
        '''
        return None
    
    def cleanup(self):
        ''' Close the Popen channels.'''
        self.stdin.close()
        self.out.close()
        self.err.close()
        tmp = self.id.wait()
        if tmp:
            self.warn("nonzero exit status:", tmp)


class ClientServerCmd(Cmd):
    ''' Helper class for running a command on a node and parsing the result. '''
    args = ""
    client_args = ""
    def __init__(self, node, client_node, verbose=False):
        ''' Initialize with two CoreNodes, node is the server '''
        Cmd.__init__(self, node, verbose)
        self.client_node = client_node
    
    def run(self):
        ''' Run the server command, then the client command, then
        kill the server '''
        self.open() # server
        self.client_open() # client
        status = self.client_id.wait()
        self.node.cmdresult(['killall', self.args[0]]) # stop the server
        r = self.parse()
        self.cleanup()
        return r
        
    def client_open(self):
        ''' Exceute call to client_node.popen(). '''
        self.client_id, self.client_stdin, self.client_out, self.client_err = \
               self.client_node.popen((self.client_args))
    
    def parse(self):
        ''' This method is overloaded by child classes and should return some
            result.
        '''
        return None
    
    def cleanup(self):
        ''' Close the Popen channels.'''
        self.stdin.close()
        self.out.close()
        self.err.close()
        tmp = self.id.wait()
        if tmp:
            self.warn("nonzero exit status: %s" % tmp)
            self.warn("command was: %s" % ((self.args, )))


class PingCmd(Cmd):
    ''' Test latency using ping.
    '''
    def __init__(self, node, verbose=False, addr=None, count=50, interval=0.1, ):
        Cmd.__init__(self, node, verbose)
        self.addr = addr
        self.count = count
        self.interval = interval
        self.args = ['ping', '-q', '-c', '%s' % count, '-i', '%s' % interval,
                     addr]

    def run(self):
        if self.verbose:
            self.info("%s initial test ping (max 1 second)..." % self.node.name)
        (status, result) = self.node.cmdresult(["ping", "-q", "-c", "1", "-w",
                                                "1", self.addr])
        if status != 0:
            self.warn("initial ping from %s to %s failed! result:\n%s" % \
                      (self.node.name, self.addr, result))
            return (0.0, 0.0)
        if self.verbose:
            self.info("%s pinging %s (%d seconds)..." % \
                  (self.node.name, self.addr, self.count * self.interval))
        return Cmd.run(self)

    def parse(self):
        lines = self.out.readlines()
        avg_latency = 0
        mdev = 0
        try:
            stats_str = lines[-1].split('=')[1]
            stats = stats_str.split('/')
            avg_latency = float(stats[1])
            mdev = float(stats[3].split(' ')[0])
        except Exception, e:
            self.warn("ping parsing exception: %s" % e)
        return (avg_latency, mdev)

class IperfCmd(ClientServerCmd):
    ''' Test throughput using iperf.
    '''
    def __init__(self, node, client_node, verbose=False, addr=None, time=10):
        # node is the server
        ClientServerCmd.__init__(self, node, client_node, verbose)
        self.addr = addr
        self.time = time
        # -s server, -y c CSV report output
        self.args = ["iperf", "-s", "-y", "c"]
        self.client_args = ["iperf", "-c", self.addr, "-t", "%s" % self.time]

    def run(self):
        if self.verbose:
            self.info("Launching the iperf server on %s..." % self.node.name)
            self.info("Running the iperf client on %s (%s seconds)..." % \
                  (self.client_node.name, self.time))
        return ClientServerCmd.run(self)

    def parse(self):
        lines = self.out.readlines()
        try:
            bps = int(lines[-1].split(',')[-1].strip('\n'))
        except Exception, e:
            self.warn("iperf parsing exception: %s" % e)
            bps = 0
        return bps
        
class MgenCmd(ClientServerCmd):
    ''' Run a test traffic flow using an MGEN sender and receiver.
    '''
    def __init__(self, node, client_node, verbose=False, addr=None, time=10,
                 rate=512):
        ClientServerCmd.__init__(self, node, client_node, verbose)
        self.addr = addr
        self.time = time
        self.args = ['mgen', 'event', 'listen udp 5000', 'output',
            '/var/log/mgen.log']
        self.rate = rate
        sendevent = "ON 1 UDP DST %s/5000 PERIODIC [%s]" % \
                (addr, self.mgenrate(self.rate))
        stopevent = "%s OFF 1" % time
        self.client_args = ['mgen', 'event', sendevent, 'event', stopevent,
            'output', '/var/log/mgen.log']

    @staticmethod
    def mgenrate(kbps):
        ''' Return a MGEN periodic rate string for the given kilobits-per-sec.
            Assume 1500 byte MTU, 20-byte IP + 8-byte UDP headers, leaving
            1472 bytes for data.
        '''
        bps = (kbps / 8) * 1000.0
        maxdata = 1472
        pps = math.ceil(bps / maxdata)
        return "%s %s" % (pps, maxdata)

    def run(self):
        if self.verbose:
            self.info("Launching the MGEN receiver on %s..." % self.node.name)
            self.info("Running the MGEN sender on %s (%s seconds)..." % \
                  (self.client_node.name, self.time))
        return ClientServerCmd.run(self)
        
    def cleanup(self):
        ''' Close the Popen channels.'''
        self.stdin.close()
        self.out.close()
        self.err.close()
        tmp = self.id.wait() # non-zero mgen exit status OK
        
    def parse(self):
        ''' Check MGEN receiver's log file for packet sequence numbers, and
            return the percentage of lost packets.
        '''
        logfile = os.path.join(self.node.nodedir, 'var.log/mgen.log')
        f = open(logfile, 'r')
        numlost = 0
        lastseq = 0
        for line in f.readlines():
            fields = line.split()
            if fields[1] != 'RECV':
                continue
            try:
                seq = int(fields[4].split('>')[1])
            except:
                self.info("Unexpected MGEN line:\n%s" % fields)
            if seq > (lastseq + 1):
                numlost += seq - (lastseq + 1)
            lastseq = seq
        f.close()
        if lastseq > 0:
            loss = 100.0 * numlost / lastseq
        else:
            loss = 0
        if self.verbose:
            self.info("Receiver log shows %d of %d packets lost" % \
                      (numlost, lastseq))
        return loss


class Experiment(object):
    ''' Experiment object to organize tests. 
    '''
    def __init__(self,  opt,  start):
        ''' Initialize with opt and start time. '''
        self.session = None
        # node list
        self.nodes = []
        # WLAN network
        self.net = None
        self.verbose = opt.verbose
        # dict from OptionParser
        self.opt = opt
        self.start = start
        self.numping = opt.numping
        self.numiperf = opt.numiperf
        self.nummgen = opt.nummgen
        self.logbegin()
    
    def info(self,  msg):
        ''' Utility method for writing output to stdout. '''
        print msg
        sys.stdout.flush()
        self.log(msg)

    def warn(self, msg):
        ''' Utility method for writing output to stderr. '''
        print >> sys.stderr, msg
        sys.stderr.flush()
        self.log(msg)
    
    def logbegin(self):
        ''' Start logging. '''
        self.logfp = None
        if not self.opt.logfile:
            return
        self.logfp = open(self.opt.logfile, "w")
        self.log("%s begin: %s\n" % (sys.argv[0], self.start.ctime()))
        self.log("%s args: %s\n" % (sys.argv[0], sys.argv[1:]))
        (sysname, rel, ver, machine, nodename) = os.uname()
        self.log("%s %s %s %s on %s" % (sysname, rel, ver, machine, nodename))
    
    def logend(self):
        ''' End logging. '''
        if not self.logfp:
            return
        end = datetime.datetime.now()
        self.log("%s end: %s (%s)\n" % \
                 (sys.argv[0], end.ctime(),  end - self.start))
        self.logfp.flush()
        self.logfp.close()
        self.logfp = None
        
    def log(self, msg):
        ''' Write to the log file, if any. '''
        if not self.logfp:
            return
        print >> self.logfp,  msg

    def reset(self):
        ''' Prepare for another experiment run.
        '''
        if self.session:
            self.session.shutdown()
            del self.session
            self.session = None
        self.nodes = []
        self.net = None
        
    def createbridgedsession(self,  numnodes, verbose = False):
        ''' Build a topology consisting of the given number of LxcNodes
            connected to a WLAN.
        '''
        # IP subnet
        prefix = ipaddr.IPv4Prefix("10.0.0.0/16")
        self.session = pycore.Session()
        # emulated network
        self.net = self.session.addobj(cls = pycore.nodes.WlanNode,
                                       name = "wlan1")
        prev = None
        for i in xrange(1, numnodes + 1):
            addr = "%s/%s" % (prefix.addr(i), 32)
            tmp = self.session.addobj(cls = pycore.nodes.CoreNode, objid = i,
                                      name = "n%d" % i)
            tmp.newnetif(self.net, [addr])
            self.nodes.append(tmp)
            self.session.services.addservicestonode(tmp, "router",
                                                    "IPForward", self.verbose)
            self.session.services.bootnodeservices(tmp)
            self.staticroutes(i, prefix, numnodes)
                    
            # link each node in a chain, with the previous node
            if prev:
                self.net.link(prev.netif(0), tmp.netif(0))
            prev = tmp
    
    def createemanesession(self, numnodes, verbose = False, cls = None, 
                           values = None):
        ''' Build a topology consisting of the given number of LxcNodes
            connected to an EMANE WLAN.
        '''
        prefix = ipaddr.IPv4Prefix("10.0.0.0/16")
        self.session = pycore.Session()
        self.session.node_count = str(numnodes + 1)
        self.session.master = True
        self.session.location.setrefgeo(47.57917,-122.13232,2.00000)
        self.session.location.refscale = 150.0
        self.session.cfg['emane_models'] = "RfPipe, Ieee80211abg, Bypass"
        self.session.emane.loadmodels()
        self.net = self.session.addobj(cls = pycore.nodes.EmaneNode,
                                       objid = numnodes + 1, name = "wlan1")
        self.net.verbose = verbose
        #self.session.emane.addobj(self.net)
        for i in xrange(1, numnodes + 1):
            addr = "%s/%s" % (prefix.addr(i), 32)
            tmp = self.session.addobj(cls = pycore.nodes.CoreNode, objid = i,
                                      name = "n%d" % i)
            #tmp.setposition(i * 20, 50, None)
            tmp.setposition(50, 50, None)
            tmp.newnetif(self.net, [addr])
            self.nodes.append(tmp)
            self.session.services.addservicestonode(tmp, "router",
                                                    "IPForward", self.verbose)

        if values is None:
            values = cls.getdefaultvalues()
        self.session.emane.setconfig(self.net.objid, cls._name, values)
        self.session.instantiate()

        self.info("waiting %s sec (TAP bring-up)" % 2)
        time.sleep(2)

        for i in xrange(1, numnodes + 1):
            tmp = self.nodes[i-1]
            self.session.services.bootnodeservices(tmp)
            self.staticroutes(i, prefix, numnodes)
                    
    
    def setnodes(self):
        ''' Set the sender and receiver nodes for use in this experiment,
            along with the address of the receiver to be used.
        '''
        self.firstnode = self.nodes[0]
        self.lastnode = self.nodes[-1]
        self.lastaddr = self.lastnode.netif(0).addrlist[0].split('/')[0]


    def staticroutes(self, i, prefix, numnodes):
        ''' Add static routes on node number i to the other nodes in the chain.
        '''
        routecmd = ["/sbin/ip", "route", "add"]
        node = self.nodes[i-1]
        neigh_left = ""
        neigh_right = ""
        # add direct interface routes first
        if i > 1:
            neigh_left = "%s" % prefix.addr(i - 1)
            cmd = routecmd + [neigh_left, "dev", node.netif(0).name]
            (status, result) = node.cmdresult(cmd)
            if status != 0:
                self.warn("failed to add interface route: %s" % cmd)
        if i < numnodes:
            neigh_right = "%s" % prefix.addr(i + 1)
            cmd = routecmd + [neigh_right, "dev", node.netif(0).name]
            (status, result) = node.cmdresult(cmd)
            if status != 0:
                self.warn("failed to add interface route: %s" % cmd)

        # add static routes to all other nodes via left/right neighbors
        for j in xrange(1, numnodes + 1):
            if abs(j - i) < 2:
                continue
            addr = "%s" % prefix.addr(j)
            if j < i:
                gw = neigh_left
            else:
                gw = neigh_right
            cmd = routecmd + [addr, "via", gw]
            (status, result) = node.cmdresult(cmd)
            if status != 0:
                self.warn("failed to add route: %s" % cmd)

    def setpathloss(self, numnodes):
        ''' Send EMANE pathloss events to connect all NEMs in a chain.
        '''
        if self.session.emane.version < self.session.emane.EMANE091:
            service = emaneeventservice.EventService()
            e = emaneeventpathloss.EventPathloss(1)
            old = True
        else:
            if self.session.emane.version == self.session.emane.EMANE091:
                dev = 'lo'
            else:
                dev = self.session.obj('ctrlnet').brname
            service = EventService(eventchannel=("224.1.2.8", 45703, dev),
                                   otachannel=None)
            old = False

        for i in xrange(1, numnodes + 1):
            rxnem = i
            # inform rxnem that it can hear node to the left with 10dB noise
            txnem = rxnem - 1
            if txnem > 0:
                if old:
                    e.set(0, txnem, 10.0, 10.0)
                    service.publish(emaneeventpathloss.EVENT_ID,
                                emaneeventservice.PLATFORMID_ANY, rxnem,
                                emaneeventservice.COMPONENTID_ANY, e.export())
                else:
                    e = PathlossEvent()
                    e.append(txnem, forward=10.0, reverse=10.0)
                    service.publish(rxnem, e)
            # inform rxnem that it can hear node to the right with 10dB noise
            txnem = rxnem + 1
            if txnem > numnodes:
                continue
            if old:
                e.set(0, txnem, 10.0, 10.0)
                service.publish(emaneeventpathloss.EVENT_ID,
                                emaneeventservice.PLATFORMID_ANY, rxnem,
                                emaneeventservice.COMPONENTID_ANY, e.export())
            else:
                e = PathlossEvent()
                e.append(txnem, forward=10.0, reverse=10.0)
                service.publish(rxnem, e)

    def setneteffects(self, bw = None, delay = None):
        ''' Set link effects for all interfaces attached to the network node.
        '''
        if not self.net:
            self.warn("failed to set effects: no network node")
            return
        for netif in self.net.netifs():
            self.net.linkconfig(netif, bw = bw, delay = delay)

    def runalltests(self, title=""):
        ''' Convenience helper to run all defined experiment tests.
            If tests are run multiple times, this returns the average of
            those runs.
        '''
        duration = self.opt.duration
        rate = self.opt.rate
        if len(title) > 0:
            self.info("----- running %s tests (duration=%s, rate=%s) -----" % \
                      (title, duration, rate))
        (latency, mdev, throughput, cpu, loss) = (0,0,0,0,0)

        self.info("number of runs: ping=%d, iperf=%d, mgen=%d" % \
                  (self.numping, self.numiperf, self.nummgen))

        if self.numping > 0:
            (latency, mdev) = self.pingtest(count=self.numping)

        if self.numiperf > 0:
            throughputs = []
            for i in range(1, self.numiperf + 1):
                throughput = self.iperftest(time=duration)
                if self.numiperf > 1:
                    throughputs += throughput
                time.sleep(1) # iperf is very CPU intensive
            if self.numiperf > 1:
                throughput = sum(throughputs) / len(throughputs)
                self.info("throughputs=%s" % ["%.2f" % v for v in throughputs])

        if self.nummgen > 0:
            cpus = []
            losses = []
            for i in range(1, self.nummgen + 1):
                (cpu, loss) = self.cputest(time=duration, rate=rate)
                if self.nummgen > 1:
                    cpus += cpu,
                    losses += loss,
            if self.nummgen > 1:
                cpu = sum(cpus) / len(cpus)
                loss = sum(losses) / len(losses)
                self.info("cpus=%s" % ["%.2f" % v for v in cpus])
                self.info("losses=%s" % ["%.2f" % v for v in losses])

        return (latency, mdev, throughput, cpu, loss)

    def pingtest(self, count=50):
        ''' Ping through a chain of nodes and report the average latency.
        '''
        p = PingCmd(node=self.firstnode, verbose=self.verbose, 
                    addr = self.lastaddr, count=count, interval=0.1).run()
        (latency, mdev) = p
        self.info("latency (ms): %.03f, %.03f" % (latency, mdev))
        return p

    def iperftest(self, time=10):
        ''' Run iperf through a chain of nodes and report the maximum
            throughput.
        '''
        bps = IperfCmd(node=self.lastnode, client_node=self.firstnode,
                       verbose=False, addr=self.lastaddr, time=time).run()
        self.info("throughput (bps): %s" % bps)
        return bps

    def cputest(self, time=10, rate=512):
        ''' Run MGEN through a chain of nodes and report the CPU usage and
            percent of lost packets. Rate is in kbps.
        '''
        if self.verbose:
            self.info("%s initial test ping (max 1 second)..." % \
                      self.firstnode.name)
        (status, result) = self.firstnode.cmdresult(["ping", "-q", "-c", "1",
                                                     "-w", "1", self.lastaddr])
        if status != 0:
            self.warn("initial ping from %s to %s failed! result:\n%s" % \
                      (self.firstnode.name, self.lastaddr, result))
            return (0.0, 0.0)
        lines = readstat()
        cpustart = getcputimes(lines[0])
        loss = MgenCmd(node=self.lastnode, client_node=self.firstnode,
                       verbose=False, addr=self.lastaddr,
                       time=time, rate=rate).run()
        lines = readstat()
        cpuend = getcputimes(lines[0])
        percent = calculatecpu(cpustart, cpuend)
        self.info("CPU usage (%%): %.02f, %.02f loss" % (percent, loss))
        return percent, loss

def main():
    ''' Main routine when running from command-line.
    '''
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage = usagestr)
    parser.set_defaults(numnodes = 10, delay = 3, duration = 10, rate = 512,
                        verbose = False,
                        numping = 50, numiperf = 1, nummgen = 1)

    parser.add_option("-d", "--delay", dest = "delay", type = float,
                      help = "wait time before testing")
    parser.add_option("-l", "--logfile", dest = "logfile", type = str,
                      help = "log detailed output to the specified file")
    parser.add_option("-n", "--numnodes", dest = "numnodes", type = int,
                      help = "number of nodes")
    parser.add_option("-r", "--rate", dest = "rate", type = float,
                      help = "kbps rate to use for MGEN CPU tests")
    parser.add_option("--numping", dest = "numping", type = int,
                      help = "number of ping latency test runs")
    parser.add_option("--numiperf", dest = "numiperf", type = int,
                      help = "number of iperf throughput test runs")
    parser.add_option("--nummgen", dest = "nummgen", type = int,
                      help = "number of MGEN CPU tests runs")
    parser.add_option("-t", "--time", dest = "duration", type = int,
                      help = "duration in seconds of throughput and CPU tests")
    parser.add_option("-v", "--verbose", dest = "verbose",
                      action = "store_true", help = "be more verbose")

    def usage(msg = None, err = 0):
        sys.stdout.write("\n")
        if msg:
            sys.stdout.write(msg + "\n\n")
        parser.print_help()
        sys.exit(err)

    # parse command line opt
    (opt, args) = parser.parse_args()

    if opt.numnodes < 2:
        usage("invalid numnodes: %s" % opt.numnodes)
    if opt.delay < 0.0:
        usage("invalid delay: %s" % opt.delay)
    if opt.rate < 0.0:
        usage("invalid rate: %s" % opt.rate)

    for a in args:
        sys.stderr.write("ignoring command line argument: '%s'\n" % a)

    results = {}
    starttime = datetime.datetime.now()
    exp = Experiment(opt = opt, start=starttime)
    exp.info("Starting wlanemanetests.py tests %s" % starttime.ctime())

    # system sanity checks here
    emanever, emaneverstr = Emane.detectversionfromcmd()
    if opt.verbose:
        exp.info("Detected EMANE version %s" % (emaneverstr,))

    # bridged
    exp.info("setting up bridged tests 1/2 no link effects")
    exp.info("creating topology: numnodes = %s" % \
                (opt.numnodes, ))
    exp.createbridgedsession(numnodes=opt.numnodes, verbose=opt.verbose)
    exp.setnodes()
    exp.info("waiting %s sec (node/route bring-up)" % opt.delay)
    time.sleep(opt.delay)
    results['0 bridged'] = exp.runalltests("bridged")
    exp.info("done; elapsed time: %s" % (datetime.datetime.now() - exp.start))

    # bridged with netem
    exp.info("setting up bridged tests 2/2 with netem")
    exp.setneteffects(bw=54000000, delay=0)
    exp.info("waiting %s sec (queue bring-up)" % opt.delay)
    results['1.0 netem'] = exp.runalltests("netem")
    exp.info("shutting down bridged session")

    # bridged with netem (1 Mbps,200ms)
    exp.info("setting up bridged tests 3/2 with netem")
    exp.setneteffects(bw=1000000, delay=20000)
    exp.info("waiting %s sec (queue bring-up)" % opt.delay)
    results['1.2 netem_1M'] = exp.runalltests("netem_1M")
    exp.info("shutting down bridged session")

    # bridged with netem (54 kbps,500ms)
    exp.info("setting up bridged tests 3/2 with netem")
    exp.setneteffects(bw=54000, delay=100000)
    exp.info("waiting %s sec (queue bring-up)" % opt.delay)
    results['1.4 netem_54K'] = exp.runalltests("netem_54K")
    exp.info("shutting down bridged session")
    exp.reset()

    # EMANE bypass model
    exp.info("setting up EMANE tests 1/2 with bypass model")
    exp.createemanesession(numnodes=opt.numnodes, verbose=opt.verbose,
                           cls=EmaneBypassModel, values=None)
    exp.setnodes()
    exp.info("waiting %s sec (node/route bring-up)" % opt.delay)
    time.sleep(opt.delay)
    results['2.0 bypass'] = exp.runalltests("bypass")
    exp.info("shutting down bypass session")
    exp.reset()
    
    exp.info("waiting %s sec (between EMANE tests)" % opt.delay)
    time.sleep(opt.delay)

    # EMANE RF-PIPE model: no restrictions (max datarate)
    exp.info("setting up EMANE tests 2/4 with RF-PIPE model")
    rfpipevals = list(EmaneRfPipeModel.getdefaultvalues())
    rfpnames = EmaneRfPipeModel.getnames()
    rfpipevals[ rfpnames.index('datarate') ] = '4294967295' # max value
    if emanever < Emane.EMANE091:
        rfpipevals[ rfpnames.index('pathlossmode') ] = '2ray'
        rfpipevals[ rfpnames.index('defaultconnectivitymode') ] = '1'
    else:
        rfpipevals[ rfpnames.index('propagationmodel') ] = '2ray'
    exp.createemanesession(numnodes=opt.numnodes, verbose=opt.verbose,
                          cls=EmaneRfPipeModel, values=rfpipevals)
    exp.setnodes()
    exp.info("waiting %s sec (node/route bring-up)" % opt.delay)
    time.sleep(opt.delay)
    results['3.0 rfpipe'] = exp.runalltests("rfpipe")
    exp.info("shutting down RF-PIPE session")
    exp.reset()

    # EMANE RF-PIPE model: 54M datarate
    exp.info("setting up EMANE tests 3/4 with RF-PIPE model 54M")
    rfpipevals = list(EmaneRfPipeModel.getdefaultvalues())
    rfpnames = EmaneRfPipeModel.getnames()
    rfpipevals[ rfpnames.index('datarate') ] = '54000000'
    # TX delay != propagation delay
    #rfpipevals[ rfpnames.index('delay') ] = '5000'
    if emanever < Emane.EMANE091:
        rfpipevals[ rfpnames.index('pathlossmode') ] = '2ray'
        rfpipevals[ rfpnames.index('defaultconnectivitymode') ] = '1'
    else:
        rfpipevals[ rfpnames.index('propagationmodel') ] = '2ray'
    exp.createemanesession(numnodes=opt.numnodes, verbose=opt.verbose,
                          cls=EmaneRfPipeModel, values=rfpipevals)
    exp.setnodes()
    exp.info("waiting %s sec (node/route bring-up)" % opt.delay)
    time.sleep(opt.delay)
    results['4.0 rfpipe54m'] = exp.runalltests("rfpipe54m")
    exp.info("shutting down RF-PIPE session")
    exp.reset()

    # EMANE RF-PIPE model:  54K datarate
    exp.info("setting up EMANE tests 4/4 with RF-PIPE model pathloss")
    rfpipevals = list(EmaneRfPipeModel.getdefaultvalues())
    rfpnames = EmaneRfPipeModel.getnames()
    rfpipevals[ rfpnames.index('datarate') ] = '54000'
    if emanever < Emane.EMANE091:
        rfpipevals[ rfpnames.index('pathlossmode') ] = 'pathloss'
        rfpipevals[ rfpnames.index('defaultconnectivitymode') ] = '0'
    else:
        rfpipevals[ rfpnames.index('propagationmodel') ] = 'precomputed'
    exp.createemanesession(numnodes=opt.numnodes, verbose=opt.verbose,
                          cls=EmaneRfPipeModel, values=rfpipevals)
    exp.setnodes()
    exp.info("waiting %s sec (node/route bring-up)" % opt.delay)
    time.sleep(opt.delay)
    exp.info("sending pathloss events to govern connectivity")
    exp.setpathloss(opt.numnodes)
    results['5.0 pathloss'] = exp.runalltests("pathloss")
    exp.info("shutting down RF-PIPE session")
    exp.reset()

    # EMANE RF-PIPE model (512K, 200ms)
    exp.info("setting up EMANE tests 4/4 with RF-PIPE model pathloss")
    rfpipevals = list(EmaneRfPipeModel.getdefaultvalues())
    rfpnames = EmaneRfPipeModel.getnames()
    rfpipevals[ rfpnames.index('datarate') ] = '512000'
    rfpipevals[ rfpnames.index('delay') ] = '200'
    rfpipevals[ rfpnames.index('pathlossmode') ] = 'pathloss'
    rfpipevals[ rfpnames.index('defaultconnectivitymode') ] = '0'
    exp.createemanesession(numnodes=opt.numnodes, verbose=opt.verbose,
                          cls=EmaneRfPipeModel, values=rfpipevals)
    exp.setnodes()
    exp.info("waiting %s sec (node/route bring-up)" % opt.delay)
    time.sleep(opt.delay)
    exp.info("sending pathloss events to govern connectivity")
    exp.setpathloss(opt.numnodes)
    results['5.1 pathloss'] = exp.runalltests("pathloss")
    exp.info("shutting down RF-PIPE session")
    exp.reset()
  
    # summary of results in CSV format
    exp.info("----- summary of results (%s nodes, rate=%s, duration=%s) -----" \
             % (opt.numnodes, opt.rate, opt.duration))
    exp.info("netname:latency,mdev,throughput,cpu,loss")

    for test in sorted(results.keys()):
        (latency, mdev, throughput, cpu, loss) = results[test]
        exp.info("%s:%.03f,%.03f,%d,%.02f,%.02f" % \
                 (test, latency, mdev, throughput, cpu,loss))

    exp.logend()
    return exp

if __name__ == "__main__":
    exp = main()
