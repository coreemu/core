#
# CORE
# Copyright (c)2011-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
'''
xen.py: implementation of the XenNode and XenVEth classes that support 
generating Xen domUs based on an ISO image and persistent configuration area
'''

from core.netns.vnet import *
from core.netns.vnode import LxcNode
from core.coreobj import PyCoreObj, PyCoreNode, PyCoreNetIf
from core.misc.ipaddr import *
from core.misc.utils import *
from core.constants import *
from core.api import coreapi
from core.netns.vif import TunTap
from core.emane.nodes import EmaneNode

try:
    import parted
except ImportError, e:
    #print "Failed to load parted Python module required by Xen support."
    #print "Error was:", e
    raise ImportError

import base64
import crypt
import subprocess
try:
    import fsimage
except ImportError, e:
    # fix for fsimage under Ubuntu
    sys.path.append("/usr/lib/xen-default/lib/python")
    try:
        import fsimage
    except ImportError, e:
        #print "Failed to load fsimage Python module required by Xen support."
        #print "Error was:", e
        raise ImportError
        


import os
import time
import shutil
import string

# XXX move these out to config file
AWK_PATH = "/bin/awk"
KPARTX_PATH = "/sbin/kpartx"
LVCREATE_PATH = "/sbin/lvcreate"
LVREMOVE_PATH = "/sbin/lvremove"
LVCHANGE_PATH = "/sbin/lvchange"
MKFSEXT4_PATH = "/sbin/mkfs.ext4"
MKSWAP_PATH = "/sbin/mkswap"
TAR_PATH = "/bin/tar"
SED_PATH = "/bin/sed"
XM_PATH = "/usr/sbin/xm"
UDEVADM_PATH = "/sbin/udevadm"

class XenVEth(PyCoreNetIf):
    def __init__(self, node, name, localname, mtu = 1500, net = None,
                 start = True, hwaddr = None):
        # note that net arg is ignored
        PyCoreNetIf.__init__(self, node = node, name = name, mtu = mtu)
        self.localname = localname
        self.up = False
        self.hwaddr = hwaddr
        if start:
            self.startup()

    def startup(self):
        cmd = [XM_PATH, 'network-attach', self.node.vmname,
               'vifname=%s' % self.localname, 'script=vif-core']
        if self.hwaddr is not None:
            cmd.append('mac=%s' % self.hwaddr)
        check_call(cmd)
        check_call([IP_BIN, "link", "set", self.localname, "up"])
        self.up = True

    def shutdown(self):
        if not self.up:
            return
        if self.localname:
            if self.hwaddr is not None:
                pass
                # this should be doable, but some argument isn't a string
                #check_call([XM_PATH, 'network-detach', self.node.vmname,
                #           self.hwaddr])
        self.up = False


class XenNode(PyCoreNode):
    apitype = coreapi.CORE_NODE_XEN

    FilesToIgnore = frozenset([
        #'ipforward.sh',
        'quaggaboot.sh',
    ])

    FilesRedirection = {
        'ipforward.sh' : '/core-tmp/ipforward.sh',
    }

    CmdsToIgnore = frozenset([
        #'sh ipforward.sh',
        #'sh quaggaboot.sh zebra',
        #'sh quaggaboot.sh ospfd',
        #'sh quaggaboot.sh ospf6d',
        'sh quaggaboot.sh vtysh',
        'killall zebra',
        'killall ospfd',
        'killall ospf6d',
        'pidof zebra', 'pidof ospfd', 'pidof ospf6d',
    ])

    def RedirCmd_ipforward(self):
        sysctlFile = open(os.path.join(self.mountdir, self.etcdir,
                                       'sysctl.conf'), 'a')
        p1 = subprocess.Popen([AWK_PATH,
                               '/^\/sbin\/sysctl -w/ {print $NF}',
                               os.path.join(self.nodedir,
                                            'core-tmp/ipforward.sh') ],
                              stdout=sysctlFile)
        p1.wait()
        sysctlFile.close()

    def RedirCmd_zebra(self):
        check_call([SED_PATH, '-i', '-e', 's/^zebra=no/zebra=yes/',
                   os.path.join(self.mountdir, self.etcdir, 'quagga/daemons')])
    def RedirCmd_ospfd(self):
        check_call([SED_PATH, '-i', '-e', 's/^ospfd=no/ospfd=yes/',
                   os.path.join(self.mountdir, self.etcdir, 'quagga/daemons')])
    def RedirCmd_ospf6d(self):
        check_call([SED_PATH, '-i', '-e',
                   's/^ospf6d=no/ospf6d=yes/',
                    os.path.join(self.mountdir, self.etcdir, 'quagga/daemons')])

    CmdsRedirection = {
        'sh ipforward.sh' : RedirCmd_ipforward,
        'sh quaggaboot.sh zebra' : RedirCmd_zebra,
        'sh quaggaboot.sh ospfd' : RedirCmd_ospfd,
        'sh quaggaboot.sh ospf6d' : RedirCmd_ospf6d,
    }

    # CoreNode: no __init__, take from LxcNode & SimpleLxcNode
    def __init__(self, session, objid = None, name = None,
                 nodedir = None, bootsh = "boot.sh", verbose = False,
                 start = True, model = None,
                 vgname = None, ramsize = None, disksize = None, 
                 isofile = None):
        # SimpleLxcNode initialization
        PyCoreNode.__init__(self, session = session, objid = objid, name = name,
                            verbose = verbose)
        self.nodedir = nodedir
        self.model = model
        # indicates startup() has been invoked and disk has been initialized
        self.up = False
        # indicates boot() has been invoked and domU is running
        self.booted = False
        self.ifindex = 0
        self.lock = threading.RLock()
        self._netif = {}
        # domU name
        self.vmname = "c" + str(session.sessionid) + "-" + name
        # LVM volume group name
        self.vgname = self.getconfigitem('vg_name', vgname)
        # LVM logical volume name
        self.lvname = self.vmname + '-'
        # LVM logical volume device path name
        self.lvpath = os.path.join('/dev', self.vgname, self.lvname)
        self.disksize = self.getconfigitem('disk_size', disksize)
        self.ramsize = int(self.getconfigitem('ram_size', ramsize))
        self.isofile = self.getconfigitem('iso_file', isofile)
        # temporary mount point for paused VM persistent filesystem
        self.mountdir = None
        self.etcdir = self.getconfigitem('etc_path')

        # TODO: remove this temporary hack
        self.FilesRedirection['/usr/local/etc/quagga/Quagga.conf'] = \
            os.path.join(self.getconfigitem('mount_path'), self.etcdir,
                        'quagga/Quagga.conf')

        # LxcNode initialization
        # self.makenodedir()
        if self.nodedir is None:
            self.nodedir = \
                os.path.join(session.sessiondir, self.name + ".conf")
            self.mountdir = self.nodedir + self.getconfigitem('mount_path')
            if not os.path.isdir(self.mountdir):
                os.makedirs(self.mountdir)
            self.tmpnodedir = True
        else:
            raise Exception, "Xen PVM node requires a temporary nodedir"
            self.tmpnodedir = False
        self.bootsh = bootsh
        if start:
            self.startup()

    def getconfigitem(self, name, default=None):
        ''' Configuration items come from the xen.conf file and/or input from
            the GUI, and are stored in the session using the XenConfigManager
            object. self.model is used to identify particular profiles 
            associated with a node type in the GUI.
        '''
        return self.session.xen.getconfigitem(name=name, model=self.model,
                                              node=self, value=default)

    # from class LxcNode (also SimpleLxcNode)
    def startup(self):
        self.warn("XEN PVM startup() called: preparing disk for %s" % self.name)
        self.lock.acquire()
        try:
            if self.up:
                raise Exception, "already up"
            self.createlogicalvolume()
            self.createpartitions()
            persistdev = self.createfilesystems()
            check_call([MOUNT_BIN, '-t', 'ext4', persistdev, self.mountdir]) 
            self.untarpersistent(tarname=self.getconfigitem('persist_tar_iso'),
                                 iso=True)
            self.setrootpassword(pw = self.getconfigitem('root_password'))
            self.sethostname(old='UBASE', new=self.name)
            self.setupssh(keypath=self.getconfigitem('ssh_key_path'))
            self.createvm()
            self.up = True
        finally:
            self.lock.release()

    # from class LxcNode (also SimpleLxcNode)
    def boot(self):
        self.warn("XEN PVM boot() called")

        self.lock.acquire()
        if not self.up:
            raise Exception, "Can't boot VM without initialized disk"

        if self.booted:
            self.lock.release()
            return

        self.session.services.bootnodeservices(self)
        tarname = self.getconfigitem('persist_tar')
        if tarname:
            self.untarpersistent(tarname=tarname, iso=False)

        try:
            check_call([UMOUNT_BIN, self.mountdir])
            self.unmount_all(self.mountdir)
            check_call([UDEVADM_PATH, 'settle'])
            check_call([KPARTX_PATH, '-d', self.lvpath])

            #time.sleep(5)
            #time.sleep(1)

            # unpause VM
            if self.verbose:
                self.warn("XEN PVM boot() unpause domU %s" % self.vmname)
            mutecheck_call([XM_PATH, 'unpause', self.vmname])

            self.booted = True
        finally:
            self.lock.release()

    def validate(self):
        self.session.services.validatenodeservices(self)
        
    # from class LxcNode (also SimpleLxcNode)
    def shutdown(self):
        self.warn("XEN PVM shutdown() called")
        if not self.up:
            return
        self.lock.acquire()
        try:
            if self.up:
                # sketch from SimpleLxcNode
                for netif in self.netifs():
                    netif.shutdown()

                try:
                    # RJE XXX what to do here
                    if self.booted:
                        mutecheck_call([XM_PATH, 'destroy', self.vmname])
                        self.booted = False
                except OSError:
                    pass
                except subprocess.CalledProcessError:
                    # ignore this error too, the VM may have exited already
                    pass

                # discard LVM volume
                lvmRemoveCount = 0
                while os.path.exists(self.lvpath):
                    try:
                        check_call([UDEVADM_PATH, 'settle'])
                        mutecall([LVCHANGE_PATH, '-an', self.lvpath])
                        lvmRemoveCount += 1
                        mutecall([LVREMOVE_PATH, '-f', self.lvpath])
                    except OSError:
                        pass
                if (lvmRemoveCount > 1):
                    self.warn("XEN PVM shutdown() required %d lvremove " \
                              "executions." % lvmRemoveCount)

                self._netif.clear()
                del self.session

                self.up = False

        finally:
            self.rmnodedir()
            self.lock.release()

    def createlogicalvolume(self):
        ''' Create a logical volume for this Xen domU. Called from startup().
        '''
        if os.path.exists(self.lvpath):
            raise Exception, "LVM volume already exists"
        mutecheck_call([LVCREATE_PATH, '--size', self.disksize,
                        '--name', self.lvname, self.vgname])

    def createpartitions(self):
        ''' Partition the LVM volume into persistent and swap partitions
            using the parted module.
        '''
        dev = parted.Device(path=self.lvpath)
        dev.removeFromCache()
        disk = parted.freshDisk(dev, 'msdos')
        constraint = parted.Constraint(device=dev)
        persist_size = int(0.75 * constraint.maxSize);
        self.createpartition(device=dev, disk=disk, start=1,
                         end=(persist_size - 1) , type="ext4")
        self.createpartition(device=dev, disk=disk, start=persist_size,
                         end=(constraint.maxSize - 1) , type="linux-swap(v1)")
        disk.commit()

    def createpartition(self, device, disk, start, end, type):
        ''' Create a single partition of the specified type and size and add
            it to the disk object, using the parted module.
        '''
        geo = parted.Geometry(device=device, start=start, end=end)
        fs = parted.FileSystem(type=type, geometry=geo)
        part = parted.Partition(disk=disk, fs=fs, type=parted.PARTITION_NORMAL,
                                geometry=geo)
        constraint = parted.Constraint(exactGeom=geo)
        disk.addPartition(partition=part, constraint=constraint)

    def createfilesystems(self):
        ''' Make an ext4 filesystem and swap space. Return the device name for
            the persistent partition so we can mount it.
        '''
        output = subprocess.Popen([KPARTX_PATH, '-l', self.lvpath],
                                  stdout=subprocess.PIPE).communicate()[0]
        lines = output.splitlines()
        persistdev = '/dev/mapper/' + lines[0].strip().split(' ')[0].strip()
        swapdev = '/dev/mapper/' + lines[1].strip().split(' ')[0].strip()
        check_call([KPARTX_PATH, '-a', self.lvpath])
        mutecheck_call([MKFSEXT4_PATH, '-L', 'persist', persistdev])
        mutecheck_call([MKSWAP_PATH, '-f', '-L', 'swap', swapdev])
        return persistdev

    def untarpersistent(self, tarname, iso):
        ''' Unpack a persistent template tar file to the mounted mount dir.
            Uses fsimage library to read from an ISO file.
        '''
        tarname = tarname.replace('%h', self.name) # filename may use hostname
        if iso:
            try:
                fs = fsimage.open(self.isofile, 0)
            except IOError, e:
                self.warn("Failed to open ISO file: %s (%s)" % (self.isofile,e))
                return
            try:
                tardata = fs.open_file(tarname).read();
            except IOError, e:
                self.warn("Failed to open tar file: %s (%s)" % (tarname, e))
                return
            finally:
                del fs;
        else:
            try:
                f = open(tarname)
                tardata = f.read()
                f.close()
            except IOError, e:
                self.warn("Failed to open tar file: %s (%s)" % (tarname, e))
                return
        p = subprocess.Popen([TAR_PATH, '-C', self.mountdir, '--numeric-owner',
                             '-xf', '-'], stdin=subprocess.PIPE)
        p.communicate(input=tardata)
        p.wait()

    def setrootpassword(self, pw):
        ''' Set the root password by updating the shadow password file that
            is on the filesystem mounted in the temporary area.
        '''
        saltedpw = crypt.crypt(pw, '$6$'+base64.b64encode(os.urandom(12)))
        check_call([SED_PATH, '-i', '-e',
                   '/^root:/s_^root:\([^:]*\):_root:' + saltedpw + ':_',
                   os.path.join(self.mountdir, self.etcdir, 'shadow')])

    def sethostname(self, old, new):
        ''' Set the hostname by updating the hostname and hosts files that
            reside on the filesystem mounted in the temporary area.
        '''
        check_call([SED_PATH, '-i', '-e', 's/%s/%s/' % (old, new),
                   os.path.join(self.mountdir, self.etcdir, 'hostname')])
        check_call([SED_PATH, '-i', '-e', 's/%s/%s/' % (old, new),
                   os.path.join(self.mountdir, self.etcdir, 'hosts')])

    def setupssh(self, keypath):
        ''' Configure SSH access by installing host keys and a system-wide
            authorized_keys file.
        '''
        sshdcfg = os.path.join(self.mountdir, self.etcdir, 'ssh/sshd_config')
        check_call([SED_PATH, '-i', '-e',
                   's/PermitRootLogin no/PermitRootLogin yes/', sshdcfg])
        sshdir = os.path.join(self.getconfigitem('mount_path'), self.etcdir,
                              'ssh')
        sshdir = sshdir.replace('/','\\/') # backslash slashes for use in sed
        check_call([SED_PATH, '-i', '-e',
                   's/#AuthorizedKeysFile        %h\/.ssh\/authorized_keys/' + \
                   'AuthorizedKeysFile ' + sshdir + '\/authorized_keys/',
                    sshdcfg])
        for f in ('ssh_host_rsa_key','ssh_host_rsa_key.pub','authorized_keys'):
            src = os.path.join(keypath, f)
            dst = os.path.join(self.mountdir, self.etcdir, 'ssh', f)
            shutil.copy(src, dst)
            if f[-3:] != "pub":
                os.chmod(dst, 0600)

    def createvm(self):
        ''' Instantiate a *paused* domU VM
            Instantiate it now, so we can add network interfaces,
            pause it so we can have the filesystem open for configuration.
        '''
        args = [XM_PATH, 'create', os.devnull, '--paused']
        args.extend(['name=' + self.vmname, 'memory=' + str(self.ramsize)])
        args.append('disk=tap:aio:' + self.isofile + ',hda,r')
        args.append('disk=phy:' + self.lvpath + ',hdb,w')
        args.append('bootloader=pygrub')
        bootargs = '--kernel=/isolinux/vmlinuz --ramdisk=/isolinux/initrd'
        args.append('bootargs=' + bootargs)
        for action in ('poweroff', 'reboot', 'suspend', 'crash', 'halt'):
            args.append('on_%s=destroy' % action)
        args.append('extra=' + self.getconfigitem('xm_create_extra'))
        mutecheck_call(args)

    # from class LxcNode
    def privatedir(self, path):
        #self.warn("XEN PVM privatedir() called")
        # Do nothing, Xen PVM nodes are fully private
        pass

    # from class LxcNode
    def opennodefile(self, filename, mode = "w"):
        self.warn("XEN PVM opennodefile() called")
        raise Exception, "Can't open VM file with opennodefile()"

    # from class LxcNode
    # open a file on a paused Xen node
    def openpausednodefile(self, filename, mode = "w"):
        dirname, basename = os.path.split(filename)
        if not basename:
            raise ValueError, "no basename for filename: " + filename
        if dirname and dirname[0] == "/":
            dirname = dirname[1:]
        #dirname = dirname.replace("/", ".")
        dirname = os.path.join(self.nodedir, dirname)
        if not os.path.isdir(dirname):
            os.makedirs(dirname, mode = 0755)
        hostfilename = os.path.join(dirname, basename)
        return open(hostfilename, mode)

    # from class LxcNode
    def nodefile(self, filename, contents, mode = 0644):
        if filename in self.FilesToIgnore:
            #self.warn("XEN PVM nodefile(filename=%s) ignored" % [filename])
            return

        if filename in self.FilesRedirection:
            redirFilename = self.FilesRedirection[filename]
            self.warn("XEN PVM nodefile(filename=%s) redirected to %s" % (filename, redirFilename))
            filename = redirFilename
            
        self.warn("XEN PVM nodefile(filename=%s) called" % [filename])
        self.lock.acquire()
        if not self.up:
            self.lock.release()
            raise Exception, "Can't access VM file as VM disk isn't ready"
            return

        if self.booted:
            self.lock.release()
            raise Exception, "Can't access VM file as VM is already running"
            return

        try:
            f = self.openpausednodefile(filename, "w")
            f.write(contents)
            os.chmod(f.name, mode)
            f.close()
            self.info("created nodefile: '%s'; mode: 0%o" % (f.name, mode))
        finally:
            self.lock.release()

    # from class SimpleLxcNode
    def alive(self):
        # is VM running?
        return False # XXX

    def cmd(self, args, wait = True):
        cmdAsString = string.join(args, ' ')
        if cmdAsString in self.CmdsToIgnore:
            #self.warn("XEN PVM cmd(args=[%s]) called and ignored" % cmdAsString)
            return 0
        if cmdAsString in self.CmdsRedirection:
            self.CmdsRedirection[cmdAsString](self)
            return 0

        self.warn("XEN PVM cmd(args=[%s]) called, but not yet implemented" % cmdAsString)
        return 0 

    def cmdresult(self, args):
        cmdAsString = string.join(args, ' ')
        if cmdAsString in self.CmdsToIgnore:
            #self.warn("XEN PVM cmd(args=[%s]) called and ignored" % cmdAsString)
            return (0, "")
        self.warn("XEN PVM cmdresult(args=[%s]) called, but not yet implemented" % cmdAsString)
        return (0, "")

    def popen(self, args):
        cmdAsString = string.join(args, ' ')
        self.warn("XEN PVM popen(args=[%s]) called, but not yet implemented" % cmdAsString)
        return

    def icmd(self, args):
        cmdAsString = string.join(args, ' ')
        self.warn("XEN PVM icmd(args=[%s]) called, but not yet implemented" % cmdAsString)
        return

    def term(self, sh = "/bin/sh"):
        self.warn("XEN PVM term() called, but not yet implemented")
        return

    def termcmdstring(self, sh = "/bin/sh"):
        ''' We may add 'sudo' to the command string because the GUI runs as a
            normal user. Use SSH if control interface is available, otherwise
            use Xen console with a keymapping for easy login.
        '''
        controlifc = None
        for ifc in self.netifs():
            if hasattr(ifc, 'control') and ifc.control == True:
                controlifc = ifc
                break
        cmd = "xterm "
        # use SSH if control interface is available
        if controlifc:
            controlip = controlifc.addrlist[0].split('/')[0]
            cmd += "-e ssh root@%s" % controlip
            return cmd
        # otherwise use 'xm console' 
        #pw = self.getconfigitem('root_password')
        #cmd += "-xrm 'XTerm*VT100.translations: #override <Key>F1: "
        #cmd += "string(\"root\\n\") \\n <Key>F2: string(\"%s\\n\")' " % pw
        cmd += "-e sudo %s console %s" % (XM_PATH, self.vmname)
        return cmd

    def shcmd(self, cmdstr, sh = "/bin/sh"):
        self.warn("XEN PVM shcmd(args=[%s]) called, but not yet implemented" % cmdstr)
        return

    # from class SimpleLxcNode
    def info(self, msg):
        if self.verbose:
            print "%s: %s" % (self.name, msg)
            sys.stdout.flush()

    # from class SimpleLxcNode
    def warn(self, msg):
        print >> sys.stderr, "%s: %s" % (self.name, msg)
        sys.stderr.flush()

    def mount(self, source, target):
        self.warn("XEN PVM Nodes can't bind-mount filesystems")

    def umount(self, target):
        self.warn("XEN PVM Nodes can't bind-mount filesystems")

    def newifindex(self):
        self.lock.acquire()
        try:
            while self.ifindex in self._netif:
                self.ifindex += 1
            ifindex = self.ifindex
            self.ifindex += 1
            return ifindex
        finally:
            self.lock.release()

    def getifindex(self, netif):
        for ifindex in self._netif:
            if self._netif[ifindex] is netif:
                return ifindex
        return -1

    def addnetif(self, netif, ifindex):
        self.warn("XEN PVM addnetif() called")
        PyCoreNode.addnetif(self, netif, ifindex)

    def delnetif(self, ifindex):
        self.warn("XEN PVM delnetif() called")
        PyCoreNode.delnetif(self, ifindex)

    def newveth(self, ifindex = None, ifname = None, net = None, hwaddr = None):
        self.warn("XEN PVM newveth(ifindex=%s, ifname=%s) called" %
                  (ifindex, ifname))

        self.lock.acquire()
        try:
            if ifindex is None:
                ifindex = self.newifindex()
            if ifname is None:
                ifname = "eth%d" % ifindex
            sessionid = self.session.shortsessionid()
            name = "n%s.%s.%s" % (self.objid, ifindex, sessionid)
            localname = "n%s.%s.%s" % (self.objid, ifname, sessionid)
            ifclass = XenVEth
            veth = ifclass(node = self, name = name, localname = localname,
                           mtu = 1500, net = net, hwaddr = hwaddr)

            veth.name = ifname
            try:
                self.addnetif(veth, ifindex)
            except:
                veth.shutdown()
                del veth
                raise
            return ifindex
        finally:
            self.lock.release()

    def newtuntap(self, ifindex = None, ifname = None, net = None):
        self.warn("XEN PVM newtuntap() called but not implemented")

    def sethwaddr(self, ifindex, addr):
        self._netif[ifindex].sethwaddr(addr)
        if self.up:
            pass
            #self.cmd([IP_BIN, "link", "set", "dev", self.ifname(ifindex),
            #    "address", str(addr)])

    def addaddr(self, ifindex, addr):
        if self.up:
            pass
            # self.cmd([IP_BIN, "addr", "add", str(addr),
            #       "dev", self.ifname(ifindex)])
        self._netif[ifindex].addaddr(addr)

    def deladdr(self, ifindex, addr):
        try:
            self._netif[ifindex].deladdr(addr)
        except ValueError:
            self.warn("trying to delete unknown address: %s" % addr)
        if self.up:
            pass
            # self.cmd([IP_BIN, "addr", "del", str(addr),
            #       "dev", self.ifname(ifindex)])

    valid_deladdrtype = ("inet", "inet6", "inet6link")
    def delalladdr(self, ifindex, addrtypes = valid_deladdrtype):
        addr = self.getaddr(self.ifname(ifindex), rescan = True)
        for t in addrtypes:
            if t not in self.valid_deladdrtype:
                raise ValueError, "addr type must be in: " + \
                    " ".join(self.valid_deladdrtype)
            for a in addr[t]:
                self.deladdr(ifindex, a)
        # update cached information
        self.getaddr(self.ifname(ifindex), rescan = True)

    # Xen PVM relies on boot process to bring up links
    #def ifup(self, ifindex):
    #    if self.up:
    #        self.cmd([IP_BIN, "link", "set", self.ifname(ifindex), "up"])

    def newnetif(self, net = None, addrlist = [], hwaddr = None,
                 ifindex = None, ifname = None):
        self.warn("XEN PVM newnetif(ifindex=%s, ifname=%s) called" %
                  (ifindex, ifname))

        self.lock.acquire()

        if not self.up:
            self.lock.release()
            raise Exception, "Can't access add veth as VM disk isn't ready"
            return

        if self.booted:
            self.lock.release()
            raise Exception, "Can't access add veth as VM is already running"
            return

        try:
            if isinstance(net, EmaneNode):
                raise Exception, "Xen PVM doesn't yet support Emane nets"

                # ifindex = self.newtuntap(ifindex = ifindex, ifname = ifname,
                #                          net = net)
                # # TUN/TAP is not ready for addressing yet; the device may
                # #   take some time to appear, and installing it into a
                # #   namespace after it has been bound removes addressing;
                # #   save addresses with the interface now
                # self.attachnet(ifindex, net)
                # netif = self.netif(ifindex)
                # netif.sethwaddr(hwaddr)
                # for addr in maketuple(addrlist):
                #     netif.addaddr(addr)
                # return ifindex
            else:
                ifindex = self.newveth(ifindex = ifindex, ifname = ifname,
                                       net = net, hwaddr = hwaddr)
            if net is not None:
                self.attachnet(ifindex, net)

            rulefile = os.path.join(self.getconfigitem('mount_path'),
                                    self.etcdir,
                                    'udev/rules.d/70-persistent-net.rules')
            f = self.openpausednodefile(rulefile, "a")
            f.write('\n# Xen PVM virtual interface #%s %s with MAC address %s\n' % (ifindex, self.ifname(ifindex), hwaddr))
            # Using MAC address as we're now loading PVM net driver "early"
            # OLD: Would like to use MAC address, but udev isn't working with paravirtualized NICs.  Perhaps the "set hw address" isn't triggering a rescan.
            f.write('SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", ATTR{address}=="%s", KERNEL=="eth*", NAME="%s"\n' % (hwaddr, self.ifname(ifindex)))
            #f.write('SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", DEVPATH=="/devices/vif-%s/?*", KERNEL=="eth*", NAME="%s"\n' % (ifindex, self.ifname(ifindex)))
            f.close()

            if hwaddr:
                self.sethwaddr(ifindex, hwaddr)
            for addr in maketuple(addrlist):
                self.addaddr(ifindex, addr)
            #self.ifup(ifindex)
            return ifindex
        finally:
            self.lock.release()

    def connectnode(self, ifname, othernode, otherifname):
        self.warn("XEN PVM connectnode() called")

        # tmplen = 8
        # tmp1 = "tmp." + "".join([random.choice(string.ascii_lowercase)
        #                          for x in xrange(tmplen)])
        # tmp2 = "tmp." + "".join([random.choice(string.ascii_lowercase)
        #                          for x in xrange(tmplen)])
        # check_call([IP_BIN, "link", "add", "name", tmp1,
        #             "type", "veth", "peer", "name", tmp2])
        #
        # check_call([IP_BIN, "link", "set", tmp1, "netns", str(self.pid)])
        # self.cmd([IP_BIN, "link", "set", tmp1, "name", ifname])
        # self.addnetif(PyCoreNetIf(self, ifname), self.newifindex())
        #
        # check_call([IP_BIN, "link", "set", tmp2, "netns", str(othernode.pid)])
        # othernode.cmd([IP_BIN, "link", "set", tmp2, "name", otherifname])
        # othernode.addnetif(PyCoreNetIf(othernode, otherifname),
        #                    othernode.newifindex())

    def addfile(self, srcname, filename):
        self.lock.acquire()
        if not self.up:
            self.lock.release()
            raise Exception, "Can't access VM file as VM disk isn't ready"
            return

        if self.booted:
            self.lock.release()
            raise Exception, "Can't access VM file as VM is already running"
            return

        if filename in self.FilesToIgnore:
            #self.warn("XEN PVM addfile(filename=%s) ignored" % [filename])
            return

        if filename in self.FilesRedirection:
            redirFilename = self.FilesRedirection[filename]
            self.warn("XEN PVM addfile(filename=%s) redirected to %s" % (filename, redirFilename))
            filename = redirFilename

        try:
            fin = open(srcname, "r")
            contents = fin.read()
            fin.close()

            fout = self.openpausednodefile(filename, "w")
            fout.write(contents)
            os.chmod(fout.name, mode)
            fout.close()
            self.info("created nodefile: '%s'; mode: 0%o" % (fout.name, mode))
        finally:
            self.lock.release()

        self.warn("XEN PVM addfile(filename=%s) called" % [filename])

        #shcmd = "mkdir -p $(dirname '%s') && mv '%s' '%s' && sync" % \
        #    (filename, srcname, filename)
        #self.shcmd(shcmd)

    def unmount_all(self, path):
        ''' Namespaces inherit the host mounts, so we need to ensure that all
            namespaces have unmounted our temporary mount area so that the
            kpartx command will succeed.
        '''
        # Session.bootnodes() already has self.session._objslock
        for o in self.session.objs():
            if not isinstance(o, LxcNode):
                continue
            o.umount(path)

