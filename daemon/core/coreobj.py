"""
Defines the basic objects for CORE emulation: the PyCoreObj base class, along with PyCoreNode,
PyCoreNet, and PyCoreNetIf.
"""

import os
import shutil
import socket
import threading
from socket import AF_INET
from socket import AF_INET6

from core.data import NodeData, LinkData
from core.enumerations import LinkTypes
from core.misc import ipaddress


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


class PyCoreObj(object):
    """
    Base class for CORE objects (nodes and networks)
    """
    apitype = None

    # TODO: appears start has no usage, verify and remove
    def __init__(self, session, objid=None, name=None, start=True):
        """
        Creates a PyCoreObj instance.

        :param core.session.Session session: CORE session object
        :param int objid: object id
        :param str name: object name
        :param bool start: start value
        :return:
        """

        self.session = session
        if objid is None:
            objid = session.get_object_id()
        self.objid = objid
        if name is None:
            name = "o%s" % self.objid
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
            return map(lambda k: self._netif[k], sorted(self._netif.keys()))
        else:
            return self._netif.itervalues()

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

        :param PyCoreNetIf netif: interface to get index for
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
        :rtype: core.data.NodeData
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
            id=self.objid,
            node_type=self.apitype,
            name=self.name,
            emulation_id=self.objid,
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


class PyCoreNode(PyCoreObj):
    """
    Base class for CORE nodes.
    """

    def __init__(self, session, objid=None, name=None, start=True):
        """
        Create a PyCoreNode instance.

        :param core.session.Session session: CORE session object
        :param int objid: object id
        :param str name: object name
        :param bool start: boolean for starting
        """
        super(PyCoreNode, self).__init__(session, objid, name, start=start)
        self.services = []
        self.nodedir = None
        self.tmpnodedir = False

    def addservice(self, service):
        """
        Add a services to the service list.

        :param core.service.CoreService service: service to add
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

        :param PyCoreNetIf netif: network interface to add
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
        :param PyCoreNetIf net: network node
        :return: network interface, or None if not found
        :rtype: PyCoreNetIf
        """
        if ifindex in self._netif:
            return self._netif[ifindex]
        else:
            return None

    def attachnet(self, ifindex, net):
        """
        Attach a network.

        :param int ifindex: interface of index to attach
        :param PyCoreNetIf net: network to attach
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
        changed = super(PyCoreNode, self).setposition(x, y, z)
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


class PyCoreNet(PyCoreObj):
    """
    Base class for networks
    """
    linktype = LinkTypes.WIRED.value

    def __init__(self, session, objid, name, start=True):
        """
        Create a PyCoreNet instance.

        :param core.session.Session session: CORE session object
        :param int objid: object id
        :param str name: object name
        :param bool start: should object start
        """
        super(PyCoreNet, self).__init__(session, objid, name, start=start)
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

        :param PyCoreNetIf netif: network interface to attach
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

        :param PyCoreNetIf netif: network interface to detach
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
            otherobj = netif.node
            uni = False
            if otherobj is None:
                # two layer-2 switches/hubs linked together via linknet()
                if not hasattr(netif, "othernet"):
                    continue
                otherobj = netif.othernet
                if otherobj.objid == self.objid:
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
                node1_id=self.objid,
                node2_id=otherobj.objid,
                link_type=self.linktype,
                unidirectional=unidirectional,
                interface2_id=otherobj.getifindex(netif),
                interface2_mac=netif.hwaddr,
                interface2_ip4=interface2_ip4,
                interface2_ip4_mask=interface2_ip4_mask,
                interface2_ip6=interface2_ip6,
                interface2_ip6_mask=interface2_ip6_mask,
                delay=netif.getparam("delay"),
                bandwidth=netif.getparam("bw"),
                dup=netif.getparam("duplicate"),
                jitter=netif.getparam("jitter")
            )

            all_links.append(link_data)

            if not uni:
                continue

            netif.swapparams('_params_up')
            link_data = LinkData(
                message_type=0,
                node1_id=otherobj.objid,
                node2_id=self.objid,
                unidirectional=1,
                delay=netif.getparam("delay"),
                bandwidth=netif.getparam("bw"),
                dup=netif.getparam("duplicate"),
                jitter=netif.getparam("jitter")
            )
            netif.swapparams('_params_up')

            all_links.append(link_data)

        return all_links


class PyCoreNetIf(object):
    """
    Base class for network interfaces.
    """

    def __init__(self, node, name, mtu):
        """
        Creates a PyCoreNetIf instance.

        :param core.coreobj.PyCoreNode node: node for interface
        :param str name: interface name
        :param mtu: mtu value
        """

        self.node = node
        self.name = name
        if not isinstance(mtu, (int, long)):
            raise ValueError
        self.mtu = mtu
        self.net = None
        self._params = {}
        self.addrlist = []
        self.hwaddr = None
        # placeholder position hook
        self.poshook = lambda a, b, c, d: None
        # used with EMANE
        self.transport_type = None
        # interface index on the network
        self.netindex = None
        # index used to find flow data
        self.flow_id = None

    def startup(self):
        """
        Startup method for the interface.

        :return: nothing
        """
        pass

    def shutdown(self):
        """
        Shutdown method for the interface.

        :return: nothing
        """
        pass

    def attachnet(self, net):
        """
        Attach network.

        :param core.coreobj.PyCoreNet net: network to attach
        :return: nothing
        """
        if self.net:
            self.detachnet()
            self.net = None

        net.attach(self)
        self.net = net

    def detachnet(self):
        """
        Detach from a network.

        :return: nothing
        """
        if self.net is not None:
            self.net.detach(self)

    def addaddr(self, addr):
        """
        Add address.

        :param str addr: address to add
        :return: nothing
        """

        self.addrlist.append(addr)

    def deladdr(self, addr):
        """
        Delete address.

        :param str addr: address to delete
        :return: nothing
        """
        self.addrlist.remove(addr)

    def sethwaddr(self, addr):
        """
        Set hardware address.

        :param core.misc.ipaddress.MacAddress addr: hardware address to set to.
        :return: nothing
        """
        self.hwaddr = addr

    def getparam(self, key):
        """
        Retrieve a parameter from the, or None if the parameter does not exist.

        :param key: parameter to get value for
        :return: parameter value
        """
        return self._params.get(key)

    def getparams(self):
        """
        Return (key, value) pairs for parameters.
        """
        parameters = []
        for k in sorted(self._params.keys()):
            parameters.append((k, self._params[k]))
        return parameters

    def setparam(self, key, value):
        """
        Set a parameter value, returns True if the parameter has changed.

        :param key: parameter name to set
        :param value: parameter value
        :return: True if parameter changed, False otherwise
        """
        # treat None and 0 as unchanged values
        current_value = self._params.get(key)
        if current_value == value or current_value <= 0 and value <= 0:
            return False

        self._params[key] = value
        return True

    def swapparams(self, name):
        """
        Swap out parameters dict for name. If name does not exist,
        intialize it. This is for supporting separate upstream/downstream
        parameters when two layer-2 nodes are linked together.

        :param str name: name of parameter to swap
        :return: nothing
        """
        tmp = self._params
        if not hasattr(self, name):
            setattr(self, name, {})
        self._params = getattr(self, name)
        setattr(self, name, tmp)

    def setposition(self, x, y, z):
        """
        Dispatch position hook handler.

        :param x: x position
        :param y: y position
        :param z: z position
        :return: nothing
        """
        self.poshook(self, x, y, z)
