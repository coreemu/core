#!/usr/bin/python

# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# author: Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
howmanynodes.py - This is a CORE script that creates network namespace nodes
having one virtual Ethernet interface connected to a bridge. It continues to
add nodes until an exception occurs. The number of nodes per bridge can be
specified. 
'''

import optparse, sys, os, datetime, time, shutil
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
from core.constants import *

GBD = 1024.0 * 1024.0

def linuxversion():
    ''' Return a string having the Linux kernel version.
    '''
    f = open('/proc/version', 'r')
    v = f.readline().split()
    version_str = ' '.join(v[:3])
    f.close()
    return version_str

MEMKEYS = ('total', 'free', 'buff', 'cached', 'stotal', 'sfree')
def memfree():
    ''' Returns kilobytes memory [total, free, buff, cached, stotal, sfree].
        useful stats are:
            free memory = free + buff + cached
            swap used = stotal - sfree
    '''
    f = open('/proc/meminfo', 'r')
    lines = f.readlines()
    f.close()
    kbs = {}
    for k in MEMKEYS:
        kbs[k] = 0
    for l in lines:
        if l[:9] == "MemTotal:":
            kbs['total'] = int(l.split()[1])
        elif l[:8] == "MemFree:":
            kbs['free'] = int(l.split()[1])
        elif l[:8] == "Buffers:":
            kbs['buff'] = int(l.split()[1])
        elif l[:8] == "Cached:":
            kbs['cache'] = int(l.split()[1])
        elif l[:10] == "SwapTotal:":
            kbs['stotal'] = int(l.split()[1])
        elif l[:9] == "SwapFree:":
            kbs['sfree'] = int(l.split()[1])
            break
    return kbs

# node list (count from 1)
nodelist = [None]
switchlist = []


def main():
    usagestr = "usage: %prog [-h] [options] [args]"
    parser = optparse.OptionParser(usage = usagestr)
    parser.set_defaults(waittime = 0.2, numnodes = 0, bridges = 0, retries = 0,
                        logfile = None, services = None)

    parser.add_option("-w", "--waittime", dest = "waittime", type = float,
                      help = "number of seconds to wait between node creation" \
                      " (default = %s)" % parser.defaults["waittime"])
    parser.add_option("-n", "--numnodes", dest = "numnodes", type = int,
                      help = "number of nodes (default = unlimited)")
    parser.add_option("-b", "--bridges", dest = "bridges", type = int,
                      help = "number of nodes per bridge; 0 = one bridge " \
                      "(def. = %s)" % parser.defaults["bridges"])
    parser.add_option("-r", "--retry", dest = "retries", type = int,
                      help = "number of retries on error (default = %s)" % \
                      parser.defaults["retries"])
    parser.add_option("-l", "--log", dest = "logfile", type = str,
                      help = "log memory usage to this file (default = %s)" % \
                      parser.defaults["logfile"])
    parser.add_option("-s", "--services", dest = "services", type = str,
                      help = "pipe-delimited list of services added to each " \
                      "node (default = %s)\n(Example: 'zebra|OSPFv2|OSPFv3|" \
                      "vtysh|IPForward')" % parser.defaults["services"])

    def usage(msg = None, err = 0):
        sys.stdout.write("\n")
        if msg:
            sys.stdout.write(msg + "\n\n")
        parser.print_help()
        sys.exit(err)

    (options, args) = parser.parse_args()

    for a in args:
        sys.stderr.write("ignoring command line argument: '%s'\n" % a)

    start = datetime.datetime.now()
    prefix = ipaddr.IPv4Prefix("10.83.0.0/16")

    print "Testing how many network namespace nodes this machine can create."
    print " - %s" % linuxversion()
    mem = memfree()
    print " - %.02f GB total memory (%.02f GB swap)" % \
            (mem['total']/GBD, mem['stotal']/GBD)
    print " - using IPv4 network prefix %s" % prefix
    print " - using wait time of %s" % options.waittime
    print " - using %d nodes per bridge" % options.bridges
    print " - will retry %d times on failure" % options.retries
    print " - adding these services to each node: %s" % options.services
    print " "

    lfp = None
    if options.logfile is not None:
        # initialize a csv log file header
        lfp = open(options.logfile, "a")
        lfp.write("# log from howmanynodes.py %s\n" % time.ctime())
        lfp.write("# options = %s\n#\n" % options)
        lfp.write("# numnodes,%s\n" % ','.join(MEMKEYS))
        lfp.flush()

    session = pycore.Session(persistent=True)
    switch = session.addobj(cls = pycore.nodes.SwitchNode)
    switchlist.append(switch)
    print "Added bridge %s (%d)." % (switch.brname, len(switchlist))

    i = 0
    retry_count = options.retries
    while True:
        i += 1
        # optionally add a bridge (options.bridges nodes per bridge)
        try:
            if options.bridges > 0 and switch.numnetif() >= options.bridges:
                switch = session.addobj(cls = pycore.nodes.SwitchNode)
                switchlist.append(switch)
                print "\nAdded bridge %s (%d) for node %d." % \
                       (switch.brname, len(switchlist), i)
        except Exception, e:
            print "At %d bridges (%d nodes) caught exception:\n%s\n" % \
                    (len(switchlist), i-1, e)
            break
        # create a node
        try:
            n = session.addobj(cls = pycore.nodes.LxcNode, name = "n%d" % i)
            n.newnetif(switch, ["%s/%s" % (prefix.addr(i), prefix.prefixlen)])
            n.cmd([SYSCTL_BIN, "net.ipv4.icmp_echo_ignore_broadcasts=0"])
            if options.services is not None:
                session.services.addservicestonode(n, "", options.services,
                                                   verbose=False)
                n.boot()
            nodelist.append(n)
            if i % 25 == 0:
                print "\n%s nodes created " % i,
                mem = memfree()
                free = mem['free'] + mem['buff'] + mem['cached']
                swap = mem['stotal'] - mem['sfree']
                print "(%.02f/%.02f GB free/swap)" % (free/GBD , swap/GBD),
                if lfp:
                    lfp.write("%d," % i)
                    lfp.write("%s\n" % ','.join(str(mem[x]) for x in MEMKEYS))
                    lfp.flush()
            else:
                sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(options.waittime)
        except Exception, e:
            print "At %d nodes caught exception:\n" % i, e
            if retry_count > 0:
                print "\nWill retry creating node %d." % i
                shutil.rmtree(n.nodedir, ignore_errors = True)
                retry_count -= 1
                i -= 1
                time.sleep(options.waittime)
                continue
            else:
                print "Stopping at %d nodes!" % i
                break

        if i == options.numnodes:
            print "Stopping at %d nodes due to numnodes option." % i
            break
        # node creation was successful at this point
        retry_count = options.retries

    if lfp:
        lfp.flush()
        lfp.close()

    print "elapsed time: %s" % (datetime.datetime.now() - start)
    print "Use the core-cleanup script to remove nodes and bridges."

if __name__ == "__main__":
    main()
