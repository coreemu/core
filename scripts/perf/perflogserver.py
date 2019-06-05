#!/usr/bin/env python
#
# (c)2011-2012 the Boeing Company
#

"""
perflogserver.py - CORE server and node performace metrics logger and alarmer
server metrics: loadave1, 5, 15, mem, used cpu% of total, cpu1, cpu2, ..., cpun
node metrics: throughput, mem, cpu total, usr, sys, wait
"""

import commands
import optparse
import os
import signal
import sys
import time


def readfile(fname):
    lines = []
    try:
        f = open(fname, "r")
    except IOError:
        if options.timestamp == True:
            print(str(time.time()),)
        print("ERROR: failed to open file %s\n" % fname)
    else:
        lines = f.readlines()
        f.close()
    return lines


def numcpus():
    lines = readfile("/proc/stat")
    n = 0
    for l in lines[1:]:
        if l[:3] != "cpu":
            break
        n += 1
    return n


def handler(signum, frame):
    print("stop timestamp:", str(time.time()) + ", cyclecount=", cyclecount, ", caught signal", signum)
    sys.exit(0)


class ServerMetrics(object):
    def __init__(self):
        self.smetrics = {"serverloadavg1": 0.0,
                         "serverloadavg5": 0.0,
                         "serverloadavg15": 0.0,
                         "serverusedmemory": 0.0,
                         "serverusedcputime": 0.0,
                         "processorusedcputime": []}

    def setvalues(self, val):
        """
        Set values from val = (nump, ldavg1, ldavg5, adavg15, mem, cpu, p1cpu, p2cpu...).
        """
        self.smetrics["serverloadavg1"] = val[0]
        self.smetrics["serverloadavg5"] = val[1]
        self.smetrics["serverloadavg15"] = val[2]
        self.smetrics["serverusedmemory"] = val[4]
        self.smetrics["serverusedcputime"] = val[5]

        pcpu = []
        for ind in range(5, len(val)):
            pcpu.append(val[ind])
        self.smetrics["processorusedcputime"] = pcpu

    def setvalue(self, key, val):
        self.smetrics[key] = val

    def getvalue(self, key):
        return self.smetrics[key]

    def getkeys(self):
        return self.smetrics.keys()

    def tocsv(self):
        rv = "Server"
        for k in self.smetrics:
            if isinstance(self.smetrics[k], float):
                rv += ", %.2f" % self.smetrics[k]
            else:
                if isinstance(self.smetrics[k], list):
                    values = ", ".join(str(round(x, 2)) for x in self.smetrics[k])
                    rv += ", [%s]" % values
                else:
                    rv += ", " + str(self.smetrics[k])
        return rv


def readserverthresholds(filename):
    if filename is None:
        return

    lines = readfile(filename)
    for l in lines:
        mval = l.strip().split('=')
        if len(mval) > 1:
            thekey = mval[0].strip()
            theval = mval[1].strip()
            if thekey in serverthresholds.getkeys():
                serverthresholds.setvalue(thekey, float(theval))


def checkserverthreshold(metricval):
    """
    Print out an alarm if a ServerMetrics value crosses threshold.
    """
    for key in serverthresholds.getkeys():
        if key == "processorusedcputime":
            pcpus = metricval.getvalue(key)
            for ind, pcpu in enumerate(pcpus):
                if pcpu > serverthresholds.getvalue(key):
                    alarm = ["server", os.uname()[1], str(ind) + key,
                             "%.2f" % pcpus[ind], ">", serverthresholds.getvalue(key)]
                    if options.timestamp:
                        print(str(time.time()) + ",",)
                    print(", ".join(str(x) for x in alarm))
        else:
            if metricval.getvalue(key) > serverthresholds.getvalue(key):
                alarm = ["server", os.uname()[1], key,
                         "%.2f" % metricval.getvalue(key), ">", serverthresholds.getvalue(key)]
                if options.timestamp:
                    print(str(time.time()) + ",",)
                print(", ".join(str(x) for x in alarm))


def collectservercputimes():
    """
    Return cpu times in ticks of this server total and each processor 3*(1+#cpu) columns
    (user+nice, sys, idle) from each /proc/stat cpu lines assume columns are:
        cpu# user nice sys idle iowait irq softirq steal guest (man 5 proc)
    """
    rval = {}
    lines = readfile("/proc/stat")
    for i in range(ncpus + 1):
        items = lines[i].split()
        user, nice, sys, idle = [int(x) for x in items[1:5]]
        rval[i] = [user+nice, sys, idle]
    return rval


def csvservercputimes(cputimes):
    """
    Return a csv string of this server total and each processor's cpu times
    (usr, sys, idle) in ticks.
    """
    rval = ''
    for i in range(len(cputimes)):
        rval += ", ".join(str(x) for x in cputimes[i])
    return rval


def calcservercputimes(cputimea, cputimeb):
    """
    Return cpu used/total % of this server total and each processor (1+#cpu columns).
    """
    p = {}
    for n in range(ncpus + 1):
        p[n] = []
        for i in range(len(cputimea[n])):
            p[n].append(cputimeb[n][i] - cputimea[n][i])
        # cpu times total delta
        total = sum(p[n])
        if total == 0:
            p[n] = 0.0
        else:
            p[n] = 100 - ((100.0 * p[n][-1]) / total)
    return p


def collectservermems():
    """
    Return memory (total, free) in KB from proc/meminfo.
    """
    lines = readfile("/proc/meminfo")
    mem = [x.split() for x in lines[0:2]]
    return [int(x) for x in zip(*mem)[1]]


def csvservermems(mems):
    """
    Return a csv string of this server memory (total, free).
    """
    return ", ".join(str(x) for x in mems)


def calcserverusedmem(mems):
    """
    Return int(100*(MemTotal-MemFree)/MemTotal) from /proc/meminfo.
    """
    return 100 * (mems[0] - mems[1]) / mems[0]


def collectservermetrics(cputimes, mems, thresholdcheck):
    """
    Return ServerMetrics object with a dictionary of
    loadavg1,loadavg5,loadavg15, usedmem%, usedcpu% for total, cpu1, cpu2, ...
    """
    metricval = []
    ldavgs = os.getloadavg()
    for v in ldavgs:
        metricval.append(v)
    metricval.append(calcserverusedmem(mems))

    for i in range(ncpus + 1):
        metricval.append(cputimes[i])

    srvmetrics = ServerMetrics()
    srvmetrics.setvalues(metricval)

    if thresholdcheck:
        checkserverthreshold(srvmetrics)

    return srvmetrics


def csvservermetrics(srvmetrics):
    """
    Return a csv string of ServerMetrics.tocsv()
    loadavg1,loadavg5,loadavg15, usedmem%, usedcpu% for total, cpu1, cpu2, ...
    """
    rv = ""
    if options.timestamp:
        rv = str(time.time()) + ", "
    rv += srvmetrics.tocsv()
    return rv


def csvserverbaseline():
    """
    Return a csv string of raw server metrics data: memfree, memtotal, cpuused, cpusystem, cpuidle.
    """
    return "memory (total, free) = " + csvservermems(collectservermems()) + "\ncputime (used, sys, idl) = " + csvservercputimes(collectservercputimes())


class NodeMetrics(object):
    def __init__(self):
        self.nmetrics = {"nodethroughput": 0.0,
                         "nodeusedmemory": 0.0,
                         "nodetotalcpu": 0.0,
                         "nodeusercpu": 0.0,
                         "nodesystemcpu": 0.0,
                         "nodewaitcpu": 0.0}

    def setvalues(self, val):
        """
        Set values from val = (throughput, mem, tcpu, ucpu, scpu, wcpu).
        """
        self.nmetrics["nodethroughput"] = val[0]
        self.nmetrics["nodeusedmemory"] = val[1]
        self.nmetrics["nodetotalcpu"] = val[2]
        self.nmetrics["nodeusercpu"] = val[3]
        self.nmetrics["nodesystemcpu"] = val[4]
        self.nmetrics["nodewaitcpu"] = val[5]

    def setvalue(self, key, val):
        self.nmetrics[key] = val

    def getvalue(self, key):
        return self.nmetrics[key]

    def getkeys(self):
        return self.nmetrics.keys()

    def tocsv(self):
        return ", ".join(str(x) for x in self.nmetrics.values())


class LogSession(object):
    def __init__(self):
        self.nodethresholds = NodeMetrics()
        # set node threshold default values:
        # nodethroughput=20.0, nodeusedmemory=15.0, nodetotalcpu=90.0,
        # nodeusercpu=30.0, nodewaitcpu=50.0, nodesystemcpu=20.0}
        self.nodethresholds.setvalues([20.0, 15.0, 90.0, 30.0, 50.0, 20.0])
        if options.configfile is not None:
            self.readnodethresholds(options.configfile)
        self.pids = {}
        self.nodemetricsA = {}
        self.nodemetricsB = {}
        self.nodemetricsC = {}

    def getpids(self):
        """
        Return dict of all CORE session pids in a dict using node name as the keys
        parent pid (vnoded) is the first value.
        """
        self.pids = {}
        nodes = commands.getstatusoutput(
            "ls /tmp/pycore.%s/*pid" % options.session)
        if nodes[0] != 0:
            return

        nodes = nodes[1].split('\n')
        for nod in nodes:
            nodename = nod.split('/')[-1].strip(".pid")
            self.pids[nodename] = commands.getoutput("cat %s" % nod)

        # do not expect failure of this command
        procs = commands.getoutput('ps -eo ppid,pid,comm').split('\n')

        # build self.pids dict with key=nodename and val="ppid,pid,cmd"
        for nname in self.pids:
            if self.pids[nname] == "":
                if options.timestamp == True:
                    print(str(time.time()),)
                print("ERROR: null vnoded pid of node: %s" % nname)
            else:
                childprocs = []
                ppid = self.pids[nname]
                for proc in procs:
                    val = proc.split()
                    if ppid == val[1]:
                        childprocs.append([val[1], val[2]])
                    if ppid == val[0]:
                        childprocs.append([val[1], val[2]])
                    self.pids[nname] = childprocs
        return self.pids

    def printsesspids(self):
        if self.pids == {}:
            return {}
        for pp in self.pids:
            if self.pids[pp] != []:
                for ap in range(len(self.pids[pp]) - 1):
                    # ap pid
                    print(", " + self.pids[pp][ap][0],)
                    # ap cmd
                    print(", " + self.pids[pp][ap][1],)
                    procmetrics = [str(x) for x in self.pids[pp][ap][-1]]
                    print(", " + ", ".join(procmetrics),)
                nodemetrics = [str(x) for x in self.pids[pp][-1]]
                print(", " + ", ".join(nodemetrics))

    def getprocessmetrics(self, pid):
        """
        Return [cpu#, vsize(kb), ttime, utime, stime, wtime]
        from a /proc/pid/stat (a single line file) assume columns are:
        pid(0) comm(1) state ppid pgrp sess tty_nr tpgid flags
        minflt cmiflt majflt cmajflt # utime(12) stime cutime cstime
        priority nice num_threads itrealvalue starttime vsize(22) rss rsslim
        startcode endcode startstack kstkesp signal blocked sigignore sigcatch
        wchan nswap cnswap exit_signal processor(38) rt_priority
        policy ioblock guest_time cguest_time (man 5 proc)
        """
        rval = {}
        lines = readfile("/proc/" + pid + "/stat")
        if lines == []:
            return rval
        items = lines[0].split()
        utime, stime, cutime, cstime = [int(x) for x in items[13:17]]
        rval = (items[38],      	# last run processor
                int(items[22])/1000, 		# process virtual mem in kb
                utime + stime + cutime + cstime,  # totoal time
                utime,          		# user time
                stime,          		# system time
                cutime + cstime)		# wait time
        return rval

    def getnodethroughput(self, pid):
        """
        Return node throughput of total receive and transmit packets in kb.
        """
        lines = readfile("/proc/" + pid + "/net/dev")
        if lines == []:
            return -0.00
        ifs = [x.split() for x in lines[2:]]
        ifm = zip(*ifs)
        rv = sum(int(x) for x in ifm[1])  # received bytes
        tr = sum(int(x) for x in ifm[9])  # transmited bytes
        return (rv + tr)/1000

    def getnodemetrics(self, mindex):
        """
        Return NodeMetrics with indexed by nodename, values are rows of
         [ [ppid, vnoded, [cpu#, vmem(kb), ttime, utime, stime, wtime]],
          [cpid, cmd,    [cpu#,  vmem(kb), ttime, utime, stime, wtime]], ... ,
          [thrput, vmem(kb), ttime, utime, stime, wtime]]
        """
        if mindex == 'a':
            metricref = self.nodemetricsA
        else:
            metricref = self.nodemetricsB

        self.getpids()
        if self.pids == {}:
            return {}

        for nod in self.pids:
            nmetric = NodeMetrics()
            nmetric.__init__()
            nodeapps = {}
            for ap in range(len(self.pids[nod])):  # get each process metrics
                procm = self.getprocessmetrics(self.pids[nod][ap][0])
                if procm == []:
                    if options.timestamp == True:
                        print(str(time.time()),)
                    print("WARNING: transient process", self.pids[nod][ap][1],
                          "/", self.pids[nod][ap][0], "on node %s" % nod)
                else:
                    nodeapps[ap] = procm
                    self.pids[nod][ap].append(nodeapps[ap])
            processm = zip(*nodeapps.values())  # get overall node metrics
            if len(processm) > 0:
                nmetric.setvalues((self.getnodethroughput(self.pids[nod][0][0]),
                                   # vsize(kb)
                                   sum(int(x) for x in processm[1]),
                                   # ttime
                                   sum(int(x) for x in processm[2]),
                                   # utime
                                   sum(int(x) for x in processm[3]),
                                   # stime
                                   sum(int(x) for x in processm[4]),
                                   sum(int(x) for x in processm[5])))  # wtime
                metricref[nod] = nmetric
        return metricref

    def setnodemetricsC(self, key, val):
        self.nodemetricsC[key] = val

    def printnodemetrics(self, mindex):
        if mindex == 'c':
            mm = self.nodemetricsC
        else:
            if mindex == 'a':
                mm = self.nodemetricsA
            else:
                mm = self.nodemetricsB

        for k in self.nodemetricsC:
            if options.timestamp:
                print(str(time.time()) + ",",)
            print(k, ",", mm[k].tocsv())

    def readnodethresholds(self, filename):
        if filename is None:
            return
        lines = readfile(filename)
        for l in lines:
            mval = l.strip().split('=')
            if len(mval) > 1:
                thekey = mval[0].strip()
                theval = mval[1].strip()
                if thekey in self.nodethresholds.getkeys():
                    self.nodethresholds.setvalue(thekey, float(theval))

    def checknodethresholds(self, nname):
        calcm = self.nodemetricsC[nname]
        for keyname in self.nodethresholds.getkeys():
            if float(calcm.getvalue(keyname)) > float(self.nodethresholds.getvalue(keyname)):
                alarm = ["node", nname + "/" + self.pids[nname][0][0], keyname,
                         calcm.getvalue(keyname), ">", self.nodethresholds.getvalue(keyname)]
                if options.timestamp:
                    print(str(time.time()) + ",",)
                print(", ".join(str(x) for x in alarm))

    def calcnodemetrics(self, cputimea, cputimeb, mems):
        """
        Return a dict of nodemetrics indexed by node name
        nodemetrics[nodename][-1] = node/host%.
        """
        p = []
        for i in range(len(cputimeb[0])):
            p.append(cputimeb[0][i] - cputimea[0][i])
        hostusedcpu = p[0] + p[1]
        hostusedmem = mems[0] - mems[1]
        if hostusedcpu == 0:
            print("WARNING: host used cpu = 0, ", p[0], p[1])
            hostusedcpu = 1
        if hostusedmem == 0:
            print("WARNING: host used mem = 0, ", mems[0], mems[1])
            hostusedmem = 1

        nodesa = self.nodemetricsA
        nodesb = self.nodemetricsB
        for nod in nodesb:
            calcm = self.nodemetricsC
            calcm = NodeMetrics()
            calcm.__init__()
            if (nod in nodesa):
                try:
                    if (nodesb[nod] == []) | (nodesa[nod] == []) | \
                       (False == isinstance(nodesb[nod], NodeMetrics)) |  \
                       (False == isinstance(nodesa[nod], NodeMetrics)):
                        if options.timestamp == True:
                            print(str(time.time()),)
                        print("Warning: nodes %s is not fully instanciated" % nod)
                    else:
                        # calc throughput kbps
                        calcm.setvalue("nodethroughput", "%.2f" % (8 * (nodesb[nod].getvalue("nodethroughput")
                                                                        - nodesa[nod].getvalue("nodethroughput")) / options.interval))
                        # calc mem node used / host used
                        calcm.setvalue("nodeusedmemory", "%.2f" % (
                            100.0 * (nodesb[nod].getvalue("nodeusedmemory") / hostusedmem)))

                        # calc total cpu time node / host
                        calcm.setvalue("nodetotalcpu", "%.2f" % (100.0 * (nodesb[nod].getvalue("nodetotalcpu")
                                                                          - nodesa[nod].getvalue("nodetotalcpu")) / hostusedcpu))
                        # calc user cpu time node / host
                        calcm.setvalue("nodeusercpu", "%.2f" % (100.0 * (nodesb[nod].getvalue("nodeusercpu")
                                                                         - nodesa[nod].getvalue("nodeusercpu")) / hostusedcpu))
                        # calc system cpu time node / host
                        calcm.setvalue("nodesystemcpu", "%.2f" % (100.0 * (nodesb[nod].getvalue("nodesystemcpu")
                                                                           - nodesa[nod].getvalue("nodesystemcpu")) / hostusedcpu))
                        # calc waitcpu time node / host
                        calcm.setvalue("nodewaitcpu", "%.2f" % (100.0 * (nodesb[nod].getvalue("nodewaitcpu")
                                                                         - nodesa[nod].getvalue("nodewaitcpu")) / hostusedcpu))
                        logsession.nodemetricsC[nod] = calcm

                        if options.alarm is not None:
                            logsession.checknodethresholds(nod)
                except IndexError:
                    pass
            else:
                print("Warning: transient node %s " % nod)

        return nodesb


def main():
    usagestr = "%prog [-h] [options] [args]\n\nLog server and optional CORE session metrics to stdout."
    parser = optparse.OptionParser(usage=usagestr)
    parser.set_defaults(interval=2, timestamp=False,
                        configfile="/etc/core/perflogserver.conf",
                        alarm=True, session=None)
    parser.add_option("-i", "--interval", dest="interval", type=int,
                      help="seconds to wait between samples; default=%s" % parser.defaults["interval"])
    parser.add_option("-t", "--timestamp", action="store_true",
                      dest="timestamp",
                      help="include timestamp on each line")
    parser.add_option("-c", "--configfile", dest="configfile",
                      type="string",
                      help="read threshold values from the specified file;default=%s" % parser.defaults["configfile"])
    parser.add_option("-a", "--alarm", action="store_true",
                      dest="alarm",
                      help="generate alarms based threshold check on each cycle")
    parser.add_option("-s", "--session", dest="session", type=int,
                      help="CORE session id; default=%s" % parser.defaults["session"])
    global options
    global ncpus
    global serverthresholds
    global logsession
    global cyclecount

    options, _args = parser.parse_args()

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    ncpus = numcpus()

    # server threshold dictionary - a ServerMetrics instant with default values
    serverthresholds = ServerMetrics()
    # set to server threshold default values: serverloadavg1=3.5,
    # serverloadavg5=3.5, serverloadavg15=3.5, serverusedmemory=80.0,
    # serverusedcputime=80.0, processorusedcputime=90.0
    serverthresholds.setvalues([3.5, 3.5, 3.5, 80.0, 80.0, 90.0])
    if options.alarm is True:
        # read server threshold values from configuration file
        readserverthresholds(options.configfile)

    if options.session is not None:
        logsession = LogSession()

    # mark host log baseline
    print("server: ", ", ".join(str(x) for x in os.uname()), ",", ncpus, "CPU cores")
    print("start timestamp:", time.time(), ", baseline data: ")
    print(csvserverbaseline())
    print("server metrics: ", ", ".join(str(x) for x in serverthresholds.getkeys()))
    if options.session is not None:
        print("node metrics: nodename, ", ", ".join(str(x) for x in logsession.nodethresholds.getkeys()))

    cyclecount = 0
    while True:
        cputimea = collectservercputimes()
        if options.session is not None:
            nodesa = logsession.getnodemetrics("a")
        time.sleep(options.interval)
        cputimeb = collectservercputimes()
        mems = collectservermems()
        calccputime = calcservercputimes(cputimea, cputimeb)
        m = csvservermetrics(collectservermetrics(
            calccputime, mems, options.alarm))
        print(m)

        if options.session is not None:
            nodesb = logsession.getnodemetrics('b')
            if nodesb != {}:
                logsession.calcnodemetrics(cputimea, cputimeb, mems)
                logsession.printnodemetrics('c')

        sys.stdout.flush()
        cyclecount = cyclecount + 1


if __name__ == "__main__":
    main()
