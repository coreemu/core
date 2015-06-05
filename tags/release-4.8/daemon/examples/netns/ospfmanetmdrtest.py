#!/usr/bin/python

# Copyright (c)2011-2014 the Boeing Company.
# See the LICENSE file included in this distribution.

# create a random topology running OSPFv3 MDR, wait and then check
# that all neighbor states are either full or two-way, and check the routes
# in zebra vs those installed in the kernel.

import os, sys, random, time, optparse, datetime
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

# this is the /etc/core/core.conf default
quagga_sbin_search = ("/usr/local/sbin", "/usr/sbin", "/usr/lib/quagga")
quagga_path = "zebra"

# sanity check that zebra is installed
try:
    for p in quagga_sbin_search:
        if os.path.exists(os.path.join(p, "zebra")):
            quagga_path = p
            break
    mutecall([os.path.join(quagga_path, "zebra"),
             "-u", "root", "-g", "root", "-v"])
except OSError:
    sys.stderr.write("ERROR: running zebra failed\n")
    sys.exit(1)

class ManetNode(pycore.nodes.LxcNode):
    """ An Lxc namespace node configured for Quagga OSPFv3 MANET MDR
    """
    conftemp = Template("""\
interface eth0
  ip address $ipaddr
  ipv6 ospf6 instance-id 65
  ipv6 ospf6 hello-interval 2
  ipv6 ospf6 dead-interval 6
  ipv6 ospf6 retransmit-interval 5
  ipv6 ospf6 network manet-designated-router
  ipv6 ospf6 diffhellos
  ipv6 ospf6 adjacencyconnectivity biconnected
  ipv6 ospf6 lsafullness mincostlsa
!
router ospf6
  router-id $routerid
  interface eth0 area 0.0.0.0
!
ip forwarding
""")

    confdir = "/usr/local/etc/quagga"

    def __init__(self, core, ipaddr, routerid = None,
                 objid = None, name = None, nodedir = None):
        if routerid is None:
            routerid = ipaddr.split("/")[0]
        self.ipaddr = ipaddr
        self.routerid = routerid
        pycore.nodes.LxcNode.__init__(self, core, objid, name, nodedir)
        self.privatedir(self.confdir)
        self.privatedir(QUAGGA_STATE_DIR)

    def qconf(self):
        return self.conftemp.substitute(ipaddr = self.ipaddr,
                                        routerid = self.routerid)

    def config(self):
        filename = os.path.join(self.confdir, "Quagga.conf")
        f = self.opennodefile(filename, "w")
        f.write(self.qconf())
        f.close()
        tmp = self.bootscript()
        if tmp:
            self.nodefile(self.bootsh, tmp, mode = 0755)

    def boot(self):
        self.config()
        self.session.services.bootnodeservices(self)

    def bootscript(self):
        return """\
#!/bin/sh -e

STATEDIR=%s

waitfile()
{
    fname=$1

    i=0
    until [ -e $fname ]; do
        i=$(($i + 1))
        if [ $i -eq 10 ]; then
            echo "file not found: $fname" >&2
            exit 1
        fi
        sleep 0.1
    done
}

mkdir -p $STATEDIR

%s/zebra -d -u root -g root
waitfile $STATEDIR/zebra.vty

%s/ospf6d -d -u root -g root
waitfile $STATEDIR/ospf6d.vty

vtysh -b
""" % (QUAGGA_STATE_DIR, quagga_path, quagga_path)

class Route(object):
    """ Helper class for organzing routing table entries. """
    def __init__(self, prefix = None, gw = None, metric = None):
	try:
            self.prefix = ipaddr.IPv4Prefix(prefix)
        except Exception, e:
            raise ValueError, "Invalid prefix given to Route object: %s\n%s" % \
                     (prefix, e)
        self.gw = gw
        self.metric = metric

    def __eq__(self, other):
        try:
            return self.prefix == other.prefix and self.gw == other.gw and \
                   self.metric == other.metric
        except:
            return False

    def __str__(self):
        return "(%s,%s,%s)" % (self.prefix, self.gw, self.metric)

    @staticmethod
    def key(r):
        if not r.prefix:
            return 0
        return r.prefix.prefix


class ManetExperiment(object):
    """ A class for building an MDR network and checking and logging its state.
    """
    def __init__(self,  options,  start):
        """ Initialize with options and start time. """
        self.session = None
        # node list
        self.nodes = []
        # WLAN network
        self.net = None
        self.verbose = options.verbose
        # dict from OptionParser
        self.options = options
        self.start = start
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
        """ Start logging. """
        self.logfp = None
        if not self.options.logfile:
            return
        self.logfp = open(self.options.logfile, "w")
        self.log("ospfmanetmdrtest begin: %s\n" % self.start.ctime())
    
    def logend(self):
        """ End logging. """
        if not self.logfp:
            return
        end = datetime.datetime.now()
        self.log("ospfmanetmdrtest end: %s (%s)\n" % \
                 (end.ctime(),  end - self.start))
        self.logfp.flush()
        self.logfp.close()
        self.logfp = None
        
    def log(self, msg):
        """ Write to the log file, if any. """
        if not self.logfp:
            return
        print >> self.logfp,  msg
        
    def logdata(self, nbrs,  mdrs,  lsdbs,  krs,  zrs):
        """ Dump experiment parameters and data to the log file. """
        self.log("ospfmantetmdrtest data:")
        self.log("----- parameters -----")
        self.log("%s" % self.options)
        self.log("----- neighbors -----")
        for rtrid in sorted(nbrs.keys()):
            self.log("%s: %s" % (rtrid,  nbrs[rtrid]))
        self.log("----- mdr levels -----")
        self.log(mdrs)
        self.log("----- link state databases -----")
        for rtrid in sorted(lsdbs.keys()):
            self.log("%s lsdb:" % rtrid)
            for line in lsdbs[rtrid].split("\n"):
                self.log(line)
        self.log("----- kernel routes -----")
        for rtrid in sorted(krs.keys()):
            msg = rtrid + ": "
            for rt in krs[rtrid]:
                msg += "%s" % rt
            self.log(msg)
        self.log("----- zebra routes -----")
        for rtrid in sorted(zrs.keys()):
            msg = rtrid + ": "
            for rt in zrs[rtrid]:
                msg += "%s" % rt
            self.log(msg)
    
    def topology(self,  numnodes, linkprob, verbose = False):
        """ Build a topology consisting of the given number of  ManetNodes
            connected to a WLAN and probabilty of links and set
            the session, WLAN, and node list objects.
        """
        # IP subnet
        prefix = ipaddr.IPv4Prefix("10.14.0.0/16")
        self.session = pycore.Session()
        # emulated network
        self.net = self.session.addobj(cls = pycore.nodes.WlanNode)
        for i in xrange(1, numnodes + 1):
            addr = "%s/%s" % (prefix.addr(i), 32)
            tmp = self.session.addobj(cls = ManetNode, ipaddr = addr, objid= "%d" % i, name = "n%d" % i)
            tmp.newnetif(self.net, [addr])
            self.nodes.append(tmp)
        # connect nodes with probability linkprob
        for i in xrange(numnodes):
            for j in xrange(i + 1, numnodes):
                r = random.random()
                if r < linkprob:
                    if self.verbose:
                        self.info("linking (%d,%d)" % (i, j))
                    self.net.link(self.nodes[i].netif(0), self.nodes[j].netif(0))
            # force one link to avoid partitions (should check if this is needed)
            j = i
            while j == i:
                j = random.randint(0, numnodes - 1)
            if self.verbose:
                self.info("linking (%d,%d)" % (i, j))
            self.net.link(self.nodes[i].netif(0), self.nodes[j].netif(0))
            self.nodes[i].boot()
        # run the boot.sh script on all nodes to start Quagga
        for i in xrange(numnodes):
            self.nodes[i].cmd(["./%s" % self.nodes[i].bootsh])

    def compareroutes(self, node, kr, zr):
        """ Compare two lists of Route objects.
        """
        kr.sort(key=Route.key)
        zr.sort(key=Route.key)
        if kr != zr:
            self.warn("kernel and zebra routes differ")
            if self.verbose:
                msg =  "kernel: "
                for r in kr:
                    msg += "%s " % r                    
                msg += "\nzebra: "
                for r in zr:
                    msg += "%s " % r
                self.warn(msg)
        else:
            self.info("  kernel and zebra routes match")

    def comparemdrlevels(self, nbrs, mdrs):
        """ Check that all routers form a connected dominating set, i.e. all
            routers are either MDR, BMDR, or adjacent to one.
        """
        msg = "All routers form a CDS"
        for n in self.nodes:
            if mdrs[n.routerid] != "OTHER":
                continue
            connected = False
            for nbr in nbrs[n.routerid]:
                if mdrs[nbr] == "MDR" or mdrs[nbr] == "BMDR":
                    connected = True
                    break
            if not connected:
                msg = "All routers do not form a CDS"
                self.warn("XXX %s: not in CDS; neighbors: %s" % \
                          (n.routerid, nbrs[n.routerid]))
        if self.verbose:
            self.info(msg)

    def comparelsdbs(self, lsdbs):
        """ Check LSDBs for consistency.
        """
        msg = "LSDBs of all routers are consistent"
        prev = self.nodes[0]
        for n in self.nodes:
            db = lsdbs[n.routerid]
            if lsdbs[prev.routerid] != db:
                msg = "LSDBs of all routers are not consistent"
                self.warn("XXX LSDBs inconsistent for %s and %s" % \
                           (n.routerid, prev.routerid))
                i = 0
                for entry in lsdbs[n.routerid].split("\n"):
                    preventries = lsdbs[prev.routerid].split("\n")
                    try:
                        preventry = preventries[i]
                    except IndexError:
                        preventry = None                    
                    if entry != preventry:                        
                        self.warn("%s: %s" % (n.routerid, entry))
                        self.warn("%s: %s" % (prev.routerid, preventry))
                    i += 1
            prev = n
        if self.verbose:
            self.info(msg)

    def checknodes(self):
        """ Check the neighbor state and routing tables of all nodes. """
        nbrs = {}
        mdrs = {}
        lsdbs = {}
        krs = {}
        zrs = {}
        v = self.verbose
        for n in self.nodes:
            self.info("checking %s" % n.name)
            nbrs[n.routerid] = Ospf6NeighState(n,  verbose=v).run()
            krs[n.routerid] = KernelRoutes(n,  verbose=v).run()
            zrs[n.routerid] = ZebraRoutes(n,  verbose=v).run()
            self.compareroutes(n, krs[n.routerid], zrs[n.routerid])
            mdrs[n.routerid] = Ospf6MdrLevel(n,  verbose=v).run()
            lsdbs[n.routerid] = Ospf6Database(n,  verbose=v).run()
        self.comparemdrlevels(nbrs, mdrs)
        self.comparelsdbs(lsdbs)
        self.logdata(nbrs,  mdrs,  lsdbs,  krs,  zrs)

class Cmd:
    """ Helper class for running a command on a node and parsing the result. """
    args = ""
    def __init__(self, node, verbose=False):
        """ Initialize with a CoreNode (LxcNode) """
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
        print >> sys.stderr, "XXX %s:" % self.node.routerid,  msg
        sys.stderr.flush()
        
    def run(self):
        """ This is the primary method used for running this command. """
        self.open()
        r = self.parse()
        self.cleanup()
        return r
        
    def open(self):
        """ Exceute call to node.popen(). """
        self.id, self.stdin, self.out, self.err = \
               self.node.popen((self.args))
    
    def parse(self):
        """ This method is overloaded by child classes and should return some
            result.
        """
        return None
    
    def cleanup(self):
        """ Close the Popen channels."""
        self.stdin.close()
        self.out.close()
        self.err.close()
        tmp = self.id.wait()
        if tmp:
            self.warn("nonzero exit status:", tmp)

class VtyshCmd(Cmd):
    """ Runs a vtysh command. """
    def open(self):
        args = ("vtysh",  "-c",  self.args)
        self.id, self.stdin, self.out, self.err = self.node.popen((args))
        
class Ospf6NeighState(VtyshCmd):
    """ Check a node for OSPFv3 neighbors in the full/two-way states. """
    args = "show ipv6 ospf6 neighbor"
    
    def parse(self):
        self.out.readline()                   # skip first line
        nbrlist = []
        for line in self.out:
            field = line.split()
            nbr = field[0]
            state = field[3].split("/")[0]
            if not state.lower() in ("full", "twoway"):
                self.warn("neighbor %s state: %s" % (nbr, state))
            nbrlist.append(nbr)

        if len(nbrlist) == 0:
            self.warn("no neighbors")
        if self.verbose:
            self.info("  %s has %d neighbors" % (self.node.routerid, len(nbrlist)))
        return nbrlist

class Ospf6MdrLevel(VtyshCmd):
    """ Retrieve the OSPFv3 MDR level for a node. """
    args = "show ipv6 ospf6 mdrlevel"
    
    def parse(self):
        line = self.out.readline()
       # TODO: handle multiple interfaces
        field = line.split()
        mdrlevel = field[4]
        if not mdrlevel in ("MDR", "BMDR", "OTHER"):
            self.warn("mdrlevel: %s" % mdrlevel)
        if self.verbose:
            self.info("  %s is %s" % (self.node.routerid, mdrlevel))
        return mdrlevel

class Ospf6Database(VtyshCmd):
    """ Retrieve the OSPFv3 LSDB summary for a node. """
    args = "show ipv6 ospf6 database"
    
    def parse(self):
        db = "" 
        for line in self.out:
            field = line.split()
            if len(field) < 8:
                continue
            # filter out Age and Duration columns
            filtered = field[:3] + field[4:7]
            db += " ".join(filtered) + "\n"
        return db

class ZebraRoutes(VtyshCmd):
    """ Return a list of Route objects for a node based on its zebra
        routing table.
    """
    args = "show ip route"
    
    def parse(self):
        for i in xrange(0,3):
            self.out.readline()                   # skip first three lines
        r = []
        prefix = None
        for line in self.out:
            field = line.split()
            if len(field) < 1:
                continue
            # only use OSPFv3 selected FIB routes
            elif field[0][:2] == "o>":
                prefix = field[1]
                metric = field[2].split("/")[1][:-1]
                if field[0][2:] != "*":
                    continue
                if field[3] == "via":
                    gw = field[4][:-1]
                else:
                    gw = field[6][:-1]
                r.append(Route(prefix, gw, metric))
                prefix = None
            elif prefix and field[0] == "*":
                # already have prefix and metric from previous line
                gw = field[2][:-1]
                r.append(Route(prefix, gw, metric))
                prefix = None

        if len(r) == 0:
            self.warn("no zebra routes")
        if self.verbose:
            self.info("  %s has %d zebra routes" % (self.node.routerid, len(r)))
        return r

class KernelRoutes(Cmd):
    """ Return a list of Route objects for a node based on its kernel 
        routing table.
    """
    args = ("/sbin/ip",  "route",  "show")
    
    def parse(self):
        r = []
        prefix = None
        for line in self.out:
            field = line.split()
            if field[0] == "nexthop":
                if not prefix:
                    # this saves only the first nexthop entry if multiple exist
                    continue
            else:
                prefix = field[0]
                metric = field[-1]
            tmp = prefix.split("/")
            if len(tmp) < 2:
                prefix += "/32"
            if field[1] == "proto":
                # nexthop entry is on the next line
                continue
            gw = field[2]   # nexthop IP or interface
            r.append(Route(prefix, gw, metric))
            prefix = None

        if len(r) == 0:
            self.warn("no kernel routes")
        if self.verbose:
            self.info("  %s has %d kernel routes" % (self.node.routerid, len(r)))
        return r

def main():
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage = usagestr)
    parser.set_defaults(numnodes = 10, linkprob = 0.35, delay = 20, seed = None)

    parser.add_option("-n", "--numnodes", dest = "numnodes", type = int,
                      help = "number of nodes")
    parser.add_option("-p", "--linkprob", dest = "linkprob", type = float,
                      help = "link probabilty")
    parser.add_option("-d", "--delay", dest = "delay", type = float,
                      help = "wait time before checking")
    parser.add_option("-s", "--seed", dest = "seed", type = int,
                      help = "specify integer to use for random seed")
    parser.add_option("-v", "--verbose", dest = "verbose",
                      action = "store_true", help = "be more verbose")
    parser.add_option("-l", "--logfile", dest = "logfile", type = str,
                      help = "log detailed output to the specified file")

    def usage(msg = None, err = 0):
        sys.stdout.write("\n")
        if msg:
            sys.stdout.write(msg + "\n\n")
        parser.print_help()
        sys.exit(err)

    # parse command line options
    (options, args) = parser.parse_args()

    if options.numnodes < 2:
        usage("invalid numnodes: %s" % options.numnodes)
    if options.linkprob <= 0.0 or options.linkprob > 1.0:
        usage("invalid linkprob: %s" % options.linkprob)
    if options.delay < 0.0:
        usage("invalid delay: %s" % options.delay)

    for a in args:
        sys.stderr.write("ignoring command line argument: '%s'\n" % a)

    if options.seed:
        random.seed(options.seed)

    me = ManetExperiment(options = options, start=datetime.datetime.now())
    me.info("creating topology: numnodes = %s; linkprob = %s" % \
                (options.numnodes, options.linkprob))
    me.topology(options.numnodes, options.linkprob)
    
    me.info("waiting %s sec" % options.delay)
    time.sleep(options.delay)
    me.info("checking neighbor state and routes")
    me.checknodes()
    me.info("done")
    me.info("elapsed time: %s" % (datetime.datetime.now() - me.start))
    me.logend()
    
    return me

if __name__ == "__main__":
    me = main()
