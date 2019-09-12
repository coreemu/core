"""
Defines the base logic for nodes used within core.
"""

import errno
import logging
import os
import random
import shutil
import signal
import socket
import string
import threading
from socket import AF_INET, AF_INET6

from builtins import range

from core import CoreCommandError, utils
from core import constants
from core.emulator.data import NodeData, LinkData
from core.emulator.enumerations import NodeTypes, LinkTypes
from core.nodes import client, nodeutils, ipaddress
from core.nodes.interface import TunTap, CoreInterface
from core.nodes.interface import Veth

_DEFAULT_MTU = 1500

utils.check_executables([constants.IP_BIN])


class NodeBase(object):
    """
    Base class for CORE nodes (nodes and networks)
    """
    apitype = None

    # TODO: appears start has no usage, verify and remove
    def __init__(self, session, _id=None, name=None, start=True):
        """
        Creates a PyCoreObj instance.

        :param core.emulator.session.Session session: CORE session object
        :param int _id: id
        :param str name: object name
        :param bool start: start value
        :return:
        """

        self.session = session
        if _id is None:
            _id = session.get_node_id()
        self.id = _id
        if name is None:
            name = "o%s" % self.id
        self.name = name
        self.type = None
        self.server = None
        self.services = None
        # ifindex is key, PyCoreNetIf instance is value
        self._netif = {}
        self.ifindex = 0
        self.canvas = None
        self.icon = None
        self.opaque = None
        self.position = Position()

    def startup(self):
        """
        Each object implements its own startup method.

        :return: nothing
        """
        raise NotImplementedError

    def shutdown(self):
        """
        Each object implements its own shutdown method.

        :return: nothing
        """
        raise NotImplementedError

    def setposition(self, x=None, y=None, z=None):
        """
        Set the (x,y,z) position of the object.

        :param float x: x position
        :param float y: y position
        :param float z: z position
        :return: True if position changed, False otherwise
        :rtype: bool
        """
        return self.position.set(x=x, y=y, z=z)

    def getposition(self):
        """
        Return an (x,y,z) tuple representing this object's position.

        :return: x,y,z position tuple
        :rtype: tuple
        """
        return self.position.get()

    def ifname(self, ifindex):
        """
        Retrieve interface name for index.

        :param int ifindex: interface index
        :return: interface name
        :rtype: str
        """
        return self._netif[ifindex].name

    def netifs(self, sort=False):
        """
        Retrieve network interfaces, sorted if desired.

        :param bool sort: boolean used to determine if interfaces should be sorted
        :return: network interfaces
        :rtype: list
        """
        if sort:
            return [self._netif[x] for x in sorted(self._netif)]
        else:
            return self._netif.values()

    def numnetif(self):
        """
        Return the attached interface count.

        :return: number of network interfaces
        :rtype: int
        """
        return len(self._netif)

    def getifindex(self, netif):
        """
        Retrieve index for an interface.

        :param core.nodes.interface.CoreInterface netif: interface to get index for
        :return: interface index if found, -1 otherwise
        :rtype: int
        """

        for ifindex in self._netif:
            if self._netif[ifindex] is netif:
                return ifindex

        return -1

    def newifindex(self):
        """
        Create a new interface index.

        :return: interface index
        :rtype: int
        """
        while self.ifindex in self._netif:
            self.ifindex += 1
        ifindex = self.ifindex
        self.ifindex += 1
        return ifindex

    def data(self, message_type, lat=None, lon=None, alt=None):
        """
        Build a data object for this node.

        :param message_type: purpose for the data object we are creating
        :param str lat: latitude
        :param str lon: longitude
        :param str alt: altitude
        :return: node data object
        :rtype: core.emulator.data.NodeData
        """
        if self.apitype is None:
            return None

        x, y, _ = self.getposition()
        model = self.type
        emulation_server = self.server

        services = self.services
        if services is not None:
            services = "|".join([service.name for service in services])

        node_data = NodeData(
            message_type=message_type,
            id=self.id,
            node_type=self.apitype,
            name=self.name,
            emulation_id=self.id,
            canvas=self.canvas,
            icon=self.icon,
            opaque=self.opaque,
            x_position=x,
            y_position=y,
            latitude=lat,
            longitude=lon,
            altitude=alt,
            model=model,
            emulation_server=emulation_server,
            services=services
        )

        return node_data

    def all_link_data(self, flags):
        """
        Build CORE Link data for this object. There is no default
        method for PyCoreObjs as PyCoreNodes do not implement this but
        PyCoreNets do.

        :param flags: message flags
        :return: list of link data
        :rtype: core.data.LinkData
        """
        return []


class CoreNodeBase(NodeBase):
    """
    Base class for CORE nodes.
    """

    def __init__(self, session, _id=None, name=None, start=True):
        """
        Create a CoreNodeBase instance.

        :param core.emulator.session.Session session: CORE session object
        :param int _id: object id
        :param str name: object name
        :param bool start: boolean for starting
        """
        super(CoreNodeBase, self).__init__(session, _id, name, start=start)
        self.services = []
        self.nodedir = None
        self.tmpnodedir = False

    def addservice(self, service):
        """
        Add a services to the service list.

        :param core.services.coreservices.CoreService service: service to add
        :return: nothing
        """
        if service is not None:
            self.services.append(service)

    def makenodedir(self):
        """
        Create the node directory.

        :return: nothing
        """
        if self.nodedir is None:
            self.nodedir = os.path.join(self.session.session_dir, self.name + ".conf")
            os.makedirs(self.nodedir)
            self.tmpnodedir = True
        else:
            self.tmpnodedir = False

    def rmnodedir(self):
        """
        Remove the node directory, unless preserve directory has been set.

        :return: nothing
        """
        preserve = self.session.options.get_config("preservedir") == "1"
        if preserve:
            return

        if self.tmpnodedir:
            shutil.rmtree(self.nodedir, ignore_errors=True)

    def addnetif(self, netif, ifindex):
        """
        Add network interface to node and set the network interface index if successful.

        :param core.nodes.interface.CoreInterface netif: network interface to add
        :param int ifindex: interface index
        :return: nothing
        """
        if ifindex in self._netif:
            raise ValueError("ifindex %s already exists" % ifindex)
        self._netif[ifindex] = netif
        # TODO: this should have probably been set ahead, seems bad to me, check for failure and fix
        netif.netindex = ifindex

    def delnetif(self, ifindex):
        """
        Delete a network interface

        :param int ifindex: interface index to delete
        :return: nothing
        """
        if ifindex not in self._netif:
            raise ValueError("ifindex %s does not exist" % ifindex)
        netif = self._netif.pop(ifindex)
        netif.shutdown()
        del netif

    # TODO: net parameter is not used, remove
    def netif(self, ifindex, net=None):
        """
        Retrieve network interface.

        :param int ifindex: index of interface to retrieve
        :param core.nodes.interface.CoreInterface net: network node
        :return: network interface, or None if not found
        :rtype: core.nodes.interface.CoreInterface
        """
        if ifindex in self._netif:
            return self._netif[ifindex]
        else:
            return None

    def attachnet(self, ifindex, net):
        """
        Attach a network.

        :param int ifindex: interface of index to attach
        :param core.nodes.interface.CoreInterface net: network to attach
        :return:
        """
        if ifindex not in self._netif:
            raise ValueError("ifindex %s does not exist" % ifindex)
        self._netif[ifindex].attachnet(net)

    def detachnet(self, ifindex):
        """
        Detach network interface.

        :param int ifindex: interface index to detach
        :return: nothing
        """
        if ifindex not in self._netif:
            raise ValueError("ifindex %s does not exist" % ifindex)
        self._netif[ifindex].detachnet()

    def setposition(self, x=None, y=None, z=None):
        """
        Set position.

        :param x: x position
        :param y: y position
        :param z: z position
        :return: nothing
        """
        changed = super(CoreNodeBase, self).setposition(x, y, z)
        if changed:
            for netif in self.netifs(sort=True):
                netif.setposition(x, y, z)

    def commonnets(self, obj, want_ctrl=False):
        """
        Given another node or net object, return common networks between
        this node and that object. A list of tuples is returned, with each tuple
        consisting of (network, interface1, interface2).

        :param obj: object to get common network with
        :param want_ctrl: flag set to determine if control network are wanted
        :return: tuples of common networks
        :rtype: list
        """
        common = []
        for netif1 in self.netifs():
            if not want_ctrl and hasattr(netif1, "control"):
                continue
            for netif2 in obj.netifs():
                if netif1.net == netif2.net:
                    common.append((netif1.net, netif1, netif2))

        return common

    def check_cmd(self, args):
        """
        Runs shell command on node.

        :param list[str]|str args: command to run
        :return: combined stdout and stderr
        :rtype: str
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        raise NotImplementedError

    def cmd(self, args, wait=True):
        """
        Runs shell command on node, with option to not wait for a result.

        :param list[str]|str args: command to run
        :param bool wait: wait for command to exit, defaults to True
        :return: exit status for command
        :rtype: int
        """
        raise NotImplementedError

    def cmd_output(self, args):
        """
        Runs shell command on node and get exit status and output.

        :param list[str]|str args: command to run
        :return: exit status and combined stdout and stderr
        :rtype: tuple[int, str]
        """
        raise NotImplementedError

    def termcmdstring(self, sh):
        """
        Create a terminal command string.

        :param str sh: shell to execute command in
        :return: str
        """
        raise NotImplementedError


class CoreNode(CoreNodeBase):
    """
    Provides standard core node logic.
    """
    apitype = NodeTypes.DEFAULT.value
    valid_address_types = {"inet", "inet6", "inet6link"}

    def __init__(self, session, _id=None, name=None, nodedir=None, bootsh="boot.sh", start=True):
        """
        Create a CoreNode instance.

        :param core.emulator.session.Session session: core session instance
        :param int _id: object id
        :param str name: object name
        :param str nodedir: node directory
        :param str bootsh: boot shell to use
        :param bool start: start flag
        """
        super(CoreNode, self).__init__(session, _id, name, start)
        self.nodedir = nodedir
        self.ctrlchnlname = os.path.abspath(os.path.join(self.session.session_dir, self.name))
        self.client = None
        self.pid = None
        self.up = False
        self.lock = threading.RLock()
        self._mounts = []
        self.bootsh = bootsh
        if start:
            self.startup()

    def alive(self):
        """
        Check if the node is alive.

        :return: True if node is alive, False otherwise
        :rtype: bool
        """
        try:
            os.kill(self.pid, 0)
        except OSError:
            return False

        return True

    def startup(self):
        """
        Start a new namespace node by invoking the vnoded process that
        allocates a new namespace. Bring up the loopback device and set
        the hostname.

        :return: nothing
        """
        with self.lock:
            self.makenodedir()
            if self.up:
                raise ValueError("starting a node that is already up")

            # create a new namespace for this node using vnoded
            vnoded = [
                constants.VNODED_BIN,
                "-v",
                "-c", self.ctrlchnlname,
                "-l", self.ctrlchnlname + ".log",
                "-p", self.ctrlchnlname + ".pid"
            ]
            if self.nodedir:
                vnoded += ["-C", self.nodedir]
            env = self.session.get_environment(state=False)
            env["NODE_NUMBER"] = str(self.id)
            env["NODE_NAME"] = str(self.name)

            output = utils.check_cmd(vnoded, env=env)
            self.pid = int(output)

            # create vnode client
            self.client = client.VnodeClient(self.name, self.ctrlchnlname)

            # bring up the loopback interface
            logging.debug("bringing up loopback interface")
            self.network_cmd([constants.IP_BIN, "link", "set", "lo", "up"])

            # set hostname for node
            logging.debug("setting hostname: %s", self.name)
            self.network_cmd(["hostname", self.name])

            # mark node as up
            self.up = True

            # create private directories
            self.privatedir("/var/run")
            self.privatedir("/var/log")

    def shutdown(self):
        """
        Shutdown logic for simple lxc nodes.

        :return: nothing
        """
        # nothing to do if node is not up
        if not self.up:
            return

        with self.lock:
            try:
                # unmount all targets (NOTE: non-persistent mount namespaces are
                # removed by the kernel when last referencing process is killed)
                self._mounts = []

                # shutdown all interfaces
                for netif in self.netifs():
                    netif.shutdown()

                # attempt to kill node process and wait for termination of children
                try:
                    os.kill(self.pid, signal.SIGTERM)
                    os.waitpid(self.pid, 0)
                except OSError as e:
                    if e.errno != 10:
                        logging.exception("error killing process")

                # remove node directory if present
                try:
                    os.unlink(self.ctrlchnlname)
                except OSError as e:
                    # no such file or directory
                    if e.errno != errno.ENOENT:
                        logging.exception("error removing node directory")

                # clear interface data, close client, and mark self and not up
                self._netif.clear()
                self.client.close()
                self.up = False
            except OSError:
                logging.exception("error during shutdown")
            finally:
                self.rmnodedir()

    def cmd(self, args, wait=True):
        """
        Runs shell command on node, with option to not wait for a result.

        :param list[str]|str args: command to run
        :param bool wait: wait for command to exit, defaults to True
        :return: exit status for command
        :rtype: int
        """
        return self.client.cmd(args, wait)

    def cmd_output(self, args):
        """
        Runs shell command on node and get exit status and output.

        :param list[str]|str args: command to run
        :return: exit status and combined stdout and stderr
        :rtype: tuple[int, str]
        """
        return self.client.cmd_output(args)

    def network_cmd(self, args):
        """
        Runs a command for a node that is used to configure and setup network interfaces.

        :param list[str]|str args: command to run
        :return: combined stdout and stderr
        :rtype: str
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        return self.check_cmd(args)

    def check_cmd(self, args):
        """
        Runs shell command on node.

        :param list[str]|str args: command to run
        :return: combined stdout and stderr
        :rtype: str
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        return self.client.check_cmd(args)

    def termcmdstring(self, sh="/bin/sh"):
        """
        Create a terminal command string.

        :param str sh: shell to execute command in
        :return: str
        """
        return self.client.termcmdstring(sh)

    def privatedir(self, path):
        """
        Create a private directory.

        :param str path: path to create
        :return: nothing
        """
        if path[0] != "/":
            raise ValueError("path not fully qualified: %s" % path)
        hostpath = os.path.join(self.nodedir, os.path.normpath(path).strip("/").replace("/", "."))
        os.mkdir(hostpath)
        self.mount(hostpath, path)

    def mount(self, source, target):
        """
        Create and mount a directory.

        :param str source: source directory to mount
        :param str target: target directory to create
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        source = os.path.abspath(source)
        logging.info("node(%s) mounting: %s at %s", self.name, source, target)
        cmd = 'mkdir -p "%s" && %s -n --bind "%s" "%s"' % (target, constants.MOUNT_BIN, source, target)
        status, output = self.client.shcmd_result(cmd)
        if status:
            raise CoreCommandError(status, cmd, output)
        self._mounts.append((source, target))

    def newifindex(self):
        """
        Retrieve a new interface index.

        :return: new interface index
        :rtype: int
        """
        with self.lock:
            return super(CoreNode, self).newifindex()

    def newveth(self, ifindex=None, ifname=None, net=None):
        """
        Create a new interface.

        :param int ifindex: index for the new interface
        :param str ifname: name for the new interface
        :param core.nodes.base.CoreNetworkBase net: network to associate interface with
        :return: nothing
        """
        with self.lock:
            if ifindex is None:
                ifindex = self.newifindex()

            if ifname is None:
                ifname = "eth%d" % ifindex

            sessionid = self.session.short_session_id()

            try:
                suffix = "%x.%s.%s" % (self.id, ifindex, sessionid)
            except TypeError:
                suffix = "%s.%s.%s" % (self.id, ifindex, sessionid)

            localname = "veth" + suffix
            if len(localname) >= 16:
                raise ValueError("interface local name (%s) too long" % localname)

            name = localname + "p"
            if len(name) >= 16:
                raise ValueError("interface name (%s) too long" % name)

            veth = Veth(node=self, name=name, localname=localname, net=net, start=self.up)

            if self.up:
                utils.check_cmd([constants.IP_BIN, "link", "set", veth.name, "netns", str(self.pid)])
                self.network_cmd([constants.IP_BIN, "link", "set", veth.name, "name", ifname])
                self.network_cmd([constants.ETHTOOL_BIN, "-K", ifname, "rx", "off", "tx", "off"])

            veth.name = ifname

            if self.up:
                # TODO: potentially find better way to query interface ID
                # retrieve interface information
                output = self.network_cmd([constants.IP_BIN, "link", "show", veth.name])
                logging.debug("interface command output: %s", output)
                output = output.split("\n")
                veth.flow_id = int(output[0].strip().split(":")[0]) + 1
                logging.debug("interface flow index: %s - %s", veth.name, veth.flow_id)
                # TODO: mimic packed hwaddr
                # veth.hwaddr = MacAddress.from_string(output[1].strip().split()[1])
                logging.debug("interface mac: %s - %s", veth.name, veth.hwaddr)

            try:
                # add network interface to the node. If unsuccessful, destroy the network interface and raise exception.
                self.addnetif(veth, ifindex)
            except ValueError as e:
                veth.shutdown()
                del veth
                raise e

            return ifindex

    def newtuntap(self, ifindex=None, ifname=None, net=None):
        """
        Create a new tunnel tap.

        :param int ifindex: interface index
        :param str ifname: interface name
        :param net: network to associate with
        :return: interface index
        :rtype: int
        """
        with self.lock:
            if ifindex is None:
                ifindex = self.newifindex()

            if ifname is None:
                ifname = "eth%d" % ifindex

            sessionid = self.session.short_session_id()
            localname = "tap%s.%s.%s" % (self.id, ifindex, sessionid)
            name = ifname
            tuntap = TunTap(node=self, name=name, localname=localname, net=net, start=self.up)

            try:
                self.addnetif(tuntap, ifindex)
            except ValueError as e:
                tuntap.shutdown()
                del tuntap
                raise e

            return ifindex

    def sethwaddr(self, ifindex, addr):
        """
        Set hardware addres for an interface.

        :param int ifindex: index of interface to set hardware address for
        :param core.nodes.ipaddress.MacAddress addr: hardware address to set
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        self._netif[ifindex].sethwaddr(addr)
        if self.up:
            args = [constants.IP_BIN, "link", "set", "dev", self.ifname(ifindex), "address", str(addr)]
            self.network_cmd(args)

    def addaddr(self, ifindex, addr):
        """
        Add interface address.

        :param int ifindex: index of interface to add address to
        :param str addr: address to add to interface
        :return: nothing
        """
        if self.up:
            # check if addr is ipv6
            if ":" in str(addr):
                args = [constants.IP_BIN, "addr", "add", str(addr), "dev", self.ifname(ifindex)]
                self.network_cmd(args)
            else:
                args = [constants.IP_BIN, "addr", "add", str(addr), "broadcast", "+", "dev", self.ifname(ifindex)]
                self.network_cmd(args)

        self._netif[ifindex].addaddr(addr)

    def deladdr(self, ifindex, addr):
        """
        Delete address from an interface.

        :param int ifindex: index of interface to delete address from
        :param str addr: address to delete from interface
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        try:
            self._netif[ifindex].deladdr(addr)
        except ValueError:
            logging.exception("trying to delete unknown address: %s" % addr)

        if self.up:
            self.network_cmd([constants.IP_BIN, "addr", "del", str(addr), "dev", self.ifname(ifindex)])

    def delalladdr(self, ifindex, address_types=None):
        """
        Delete all addresses from an interface.

        :param int ifindex: index of interface to delete address types from
        :param tuple[str] address_types: address types to delete
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        if not address_types:
            address_types = self.valid_address_types

        interface_name = self.ifname(ifindex)
        addresses = self.client.getaddr(interface_name, rescan=True)

        for address_type in address_types:
            if address_type not in self.valid_address_types:
                raise ValueError("addr type must be in: %s" % " ".join(self.valid_address_types))
            for address in addresses[address_type]:
                self.deladdr(ifindex, address)

        # update cached information
        self.client.getaddr(interface_name, rescan=True)

    def ifup(self, ifindex):
        """
        Bring an interface up.

        :param int ifindex: index of interface to bring up
        :return: nothing
        """
        if self.up:
            self.network_cmd([constants.IP_BIN, "link", "set", self.ifname(ifindex), "up"])

    def newnetif(self, net=None, addrlist=None, hwaddr=None, ifindex=None, ifname=None):
        """
        Create a new network interface.

        :param core.nodes.base.CoreNetworkBase net: network to associate with
        :param list addrlist: addresses to add on the interface
        :param core.nodes.ipaddress.MacAddress hwaddr: hardware address to set for interface
        :param int ifindex: index of interface to create
        :param str ifname: name for interface
        :return: interface index
        :rtype: int
        """
        if not addrlist:
            addrlist = []

        with self.lock:
            # TODO: see if you can move this to emane specific code
            if nodeutils.is_node(net, NodeTypes.EMANE):
                ifindex = self.newtuntap(ifindex=ifindex, ifname=ifname, net=net)
                # TUN/TAP is not ready for addressing yet; the device may
                #   take some time to appear, and installing it into a
                #   namespace after it has been bound removes addressing;
                #   save addresses with the interface now
                self.attachnet(ifindex, net)
                netif = self.netif(ifindex)
                netif.sethwaddr(hwaddr)
                for address in utils.make_tuple(addrlist):
                    netif.addaddr(address)
                return ifindex
            else:
                ifindex = self.newveth(ifindex=ifindex, ifname=ifname, net=net)

            if net is not None:
                self.attachnet(ifindex, net)

            if hwaddr:
                self.sethwaddr(ifindex, hwaddr)

            for address in utils.make_tuple(addrlist):
                self.addaddr(ifindex, address)

            self.ifup(ifindex)
            return ifindex

    def connectnode(self, ifname, othernode, otherifname):
        """
        Connect a node.

        :param str ifname: name of interface to connect
        :param core.nodes.CoreNodeBase othernode: node to connect to
        :param str otherifname: interface name to connect to
        :return: nothing
        """
        tmplen = 8
        tmp1 = "tmp." + "".join([random.choice(string.ascii_lowercase) for _ in range(tmplen)])
        tmp2 = "tmp." + "".join([random.choice(string.ascii_lowercase) for _ in range(tmplen)])
        utils.check_cmd([constants.IP_BIN, "link", "add", "name", tmp1, "type", "veth", "peer", "name", tmp2])

        utils.check_cmd([constants.IP_BIN, "link", "set", tmp1, "netns", str(self.pid)])
        self.network_cmd([constants.IP_BIN, "link", "set", tmp1, "name", ifname])
        interface = CoreInterface(node=self, name=ifname, mtu=_DEFAULT_MTU)
        self.addnetif(interface, self.newifindex())

        utils.check_cmd([constants.IP_BIN, "link", "set", tmp2, "netns", str(othernode.pid)])
        othernode.network_cmd([constants.IP_BIN, "link", "set", tmp2, "name", otherifname])
        other_interface = CoreInterface(node=othernode, name=otherifname, mtu=_DEFAULT_MTU)
        othernode.addnetif(other_interface, othernode.newifindex())

    def addfile(self, srcname, filename):
        """
        Add a file.

        :param str srcname: source file name
        :param str filename: file name to add
        :return: nothing
        :raises CoreCommandError: when a non-zero exit status occurs
        """
        logging.info("adding file from %s to %s", srcname, filename)
        directory = os.path.dirname(filename)

        cmd = 'mkdir -p "%s" && mv "%s" "%s" && sync' % (directory, srcname, filename)
        status, output = self.client.shcmd_result(cmd)
        if status:
            raise CoreCommandError(status, cmd, output)

    def hostfilename(self, filename):
        """
        Return the name of a node"s file on the host filesystem.

        :param str filename: host file name
        :return: path to file
        """
        dirname, basename = os.path.split(filename)
        if not basename:
            raise ValueError("no basename for filename: %s" % filename)
        if dirname and dirname[0] == "/":
            dirname = dirname[1:]
        dirname = dirname.replace("/", ".")
        dirname = os.path.join(self.nodedir, dirname)
        return os.path.join(dirname, basename)

    def opennodefile(self, filename, mode="w"):
        """
        Open a node file, within it"s directory.

        :param str filename: file name to open
        :param str mode: mode to open file in
        :return: open file
        :rtype: file
        """
        hostfilename = self.hostfilename(filename)
        dirname, _basename = os.path.split(hostfilename)
        if not os.path.isdir(dirname):
            os.makedirs(dirname, mode=0o755)
        return open(hostfilename, mode)

    def nodefile(self, filename, contents, mode=0o644):
        """
        Create a node file with a given mode.

        :param str filename: name of file to create
        :param contents: contents of file
        :param int mode: mode for file
        :return: nothing
        """
        with self.opennodefile(filename, "w") as open_file:
            open_file.write(contents)
            os.chmod(open_file.name, mode)
            logging.info("node(%s) added file: %s; mode: 0%o", self.name, open_file.name, mode)

    def nodefilecopy(self, filename, srcfilename, mode=None):
        """
        Copy a file to a node, following symlinks and preserving metadata.
        Change file mode if specified.

        :param str filename: file name to copy file to
        :param str srcfilename: file to copy
        :param int mode: mode to copy to
        :return: nothing
        """
        hostfilename = self.hostfilename(filename)
        shutil.copy2(srcfilename, hostfilename)
        if mode is not None:
            os.chmod(hostfilename, mode)
        logging.info("node(%s) copied file: %s; mode: %s", self.name, hostfilename, mode)


class CoreNetworkBase(NodeBase):
    """
    Base class for networks
    """
    linktype = LinkTypes.WIRED.value

    def __init__(self, session, _id, name, start=True):
        """
        Create a CoreNetworkBase instance.

        :param core.emulator.session.Session session: CORE session object
        :param int _id: object id
        :param str name: object name
        :param bool start: should object start
        """
        super(CoreNetworkBase, self).__init__(session, _id, name, start=start)
        self._linked = {}
        self._linked_lock = threading.Lock()

    def startup(self):
        """
        Each object implements its own startup method.

        :return: nothing
        """
        raise NotImplementedError

    def shutdown(self):
        """
        Each object implements its own shutdown method.

        :return: nothing
        """
        raise NotImplementedError

    def attach(self, netif):
        """
        Attach network interface.

        :param core.nodes.interface.CoreInterface netif: network interface to attach
        :return: nothing
        """
        i = self.newifindex()
        self._netif[i] = netif
        netif.netifi = i
        with self._linked_lock:
            self._linked[netif] = {}

    def detach(self, netif):
        """
        Detach network interface.

        :param core.nodes.interface.CoreInterface netif: network interface to detach
        :return: nothing
        """
        del self._netif[netif.netifi]
        netif.netifi = None
        with self._linked_lock:
            del self._linked[netif]

    def all_link_data(self, flags):
        """
        Build link data objects for this network. Each link object describes a link
        between this network and a node.
        """
        all_links = []

        # build a link message from this network node to each node having a
        # connected interface
        for netif in self.netifs(sort=True):
            if not hasattr(netif, "node"):
                continue
            linked_node = netif.node
            uni = False
            if linked_node is None:
                # two layer-2 switches/hubs linked together via linknet()
                if not hasattr(netif, "othernet"):
                    continue
                linked_node = netif.othernet
                if linked_node.id == self.id:
                    continue
                netif.swapparams('_params_up')
                upstream_params = netif.getparams()
                netif.swapparams('_params_up')
                if netif.getparams() != upstream_params:
                    uni = True

            unidirectional = 0
            if uni:
                unidirectional = 1

            interface2_ip4 = None
            interface2_ip4_mask = None
            interface2_ip6 = None
            interface2_ip6_mask = None
            for address in netif.addrlist:
                ip, _sep, mask = address.partition("/")
                mask = int(mask)
                if ipaddress.is_ipv4_address(ip):
                    family = AF_INET
                    ipl = socket.inet_pton(family, ip)
                    interface2_ip4 = ipaddress.IpAddress(af=family, address=ipl)
                    interface2_ip4_mask = mask
                else:
                    family = AF_INET6
                    ipl = socket.inet_pton(family, ip)
                    interface2_ip6 = ipaddress.IpAddress(af=family, address=ipl)
                    interface2_ip6_mask = mask

            link_data = LinkData(
                message_type=flags,
                node1_id=self.id,
                node2_id=linked_node.id,
                link_type=self.linktype,
                unidirectional=unidirectional,
                interface2_id=linked_node.getifindex(netif),
                interface2_mac=netif.hwaddr,
                interface2_ip4=interface2_ip4,
                interface2_ip4_mask=interface2_ip4_mask,
                interface2_ip6=interface2_ip6,
                interface2_ip6_mask=interface2_ip6_mask,
                delay=netif.getparam("delay"),
                bandwidth=netif.getparam("bw"),
                dup=netif.getparam("duplicate"),
                jitter=netif.getparam("jitter"),
                per=netif.getparam("loss")
            )

            all_links.append(link_data)

            if not uni:
                continue

            netif.swapparams('_params_up')
            link_data = LinkData(
                message_type=0,
                node1_id=linked_node.id,
                node2_id=self.id,
                unidirectional=1,
                delay=netif.getparam("delay"),
                bandwidth=netif.getparam("bw"),
                dup=netif.getparam("duplicate"),
                jitter=netif.getparam("jitter"),
                per=netif.getparam("loss")
            )
            netif.swapparams('_params_up')

            all_links.append(link_data)

        return all_links


class Position(object):
    """
    Helper class for Cartesian coordinate position
    """

    def __init__(self, x=None, y=None, z=None):
        """
        Creates a Position instance.

        :param x: x position
        :param y: y position
        :param z: z position
        :return:
        """
        self.x = x
        self.y = y
        self.z = z

    def set(self, x=None, y=None, z=None):
        """
        Returns True if the position has actually changed.

        :param float x: x position
        :param float y: y position
        :param float z: z position
        :return: True if position changed, False otherwise
        :rtype: bool
        """
        if self.x == x and self.y == y and self.z == z:
            return False
        self.x = x
        self.y = y
        self.z = z
        return True

    def get(self):
        """
        Retrieve x,y,z position.

        :return: x,y,z position tuple
        :rtype: tuple
        """
        return self.x, self.y, self.z
