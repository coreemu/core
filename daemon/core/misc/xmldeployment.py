import socket
import subprocess
import os
import xmlutils

from core.netns import nodes
from core.misc import ipaddr
from core import constants

class CoreDeploymentWriter(object):
    def __init__(self, dom, root, session):
        self.dom = dom
        self.root = root
        self.session = session
        self.hostname = socket.gethostname()
        if self.session.emane.version < self.session.emane.EMANE092:
            self.transport = None
            self.platform = None

    @staticmethod
    def get_ipv4_addresses(hostname):
        if hostname == 'localhost':
            addr_list = []
            cmd = (constants.IP_BIN, '-o', '-f', 'inet', 'addr', 'show')
            output = subprocess.check_output(cmd)
            for line in output.split(os.linesep):
                split = line.split()
                if not split:
                    continue
                addr = split[3]
                if not addr.startswith('127.'):
                    addr_list.append(addr)
            return addr_list
        else:
            # TODO: handle other hosts
            raise NotImplementedError
            
    @staticmethod
    def get_interface_names(hostname):
        '''Uses same methodology of get_ipv4_addresses() to get
           parallel list of interface names to go with ...'''
        if hostname == 'localhost':
            iface_list = []
            cmd = (constants.IP_BIN, '-o', '-f', 'inet', 'addr', 'show')
            output = subprocess.check_output(cmd)
            for line in output.split(os.linesep):
                split = line.split()
                if not split:
                    continue
                ifaceName = split[1]
                addr = split[3]
                if not addr.startswith('127.'):
                    iface_list.append(ifaceName)
            return iface_list
        else:
            # TODO: handle other hosts
            raise NotImplementedError
            
    @staticmethod
    def find_device(scenario, name):
        tagName = ('device', 'host', 'router')
        for d in xmlutils.iterDescendantsWithAttribute(scenario, tagName,
                                                       'name', name):
            return d
        return None

    @staticmethod
    def find_interface(device, name):
        for i in xmlutils.iterDescendantsWithAttribute(device, 'interface',
                                                       'name', name):
            return i
        return None

    def add_deployment(self):
        testbed = self.dom.createElement('container')
        testbed.setAttribute('name', 'TestBed')
        testbed.setAttribute('id', 'TestBed')
        self.root.baseEle.appendChild(testbed)
        nodelist = []
        for obj in self.session.objs():
            if isinstance(obj, nodes.PyCoreNode):
                nodelist.append(obj)
        name = self.hostname
        ipv4_addresses = self.get_ipv4_addresses('localhost')
        iface_names = self.get_interface_names('localhost')
        testhost = self.add_physical_host(testbed, name, ipv4_addresses, iface_names)
        for n in nodelist:
            self.add_virtual_host(testhost, n)
        # TODO: handle other servers
        #   servers = self.session.broker.getservernames()
        #   servers.remove('localhost')

    def add_child_element(self, parent, tagName):
        el = self.dom.createElement(tagName)
        parent.appendChild(el)
        return el

    def add_child_element_with_nameattr(self, parent, tagName,
                                        name, setid = True):
        el = self.add_child_element(parent, tagName)
        el.setAttribute('name', name)
        if setid:
            el.setAttribute('id', '%s/%s' % (parent.getAttribute('id'), name))
        return el

    def add_address(self, parent, address_type, address_str, address_iface=None):
        el = self.add_child_element(parent, 'address')
        el.setAttribute('type', address_type)
        if address_iface is not None:
            el.setAttribute('iface', address_iface)
        el.appendChild(self.dom.createTextNode(address_str))
        return el

    def add_type(self, parent, type_str):
        el = self.add_child_element(parent, 'type')
        el.appendChild(self.dom.createTextNode(type_str))
        return el

    def add_platform(self, parent, name):
        el = self.add_child_element_with_nameattr(parent,
                                                  'emanePlatform', name)
        return el

    def add_transport(self, parent, name):
        el = self.add_child_element_with_nameattr(parent, 'transport', name)
        return el

    def add_nem(self, parent, name):
        el = self.add_child_element_with_nameattr(parent, 'nem', name)
        return el

    def add_parameter(self, parent, name, val):
        el = self.add_child_element_with_nameattr(parent, 'parameter',
                                                  name, False)
        el.appendChild(self.dom.createTextNode(val))
        return el

    def add_mapping(self, parent, maptype, mapref):
        el = self.add_child_element(parent, 'mapping')
        el.setAttribute('type', maptype)
        el.setAttribute('ref', mapref)
        return el

    def add_host(self, parent, name):
        el = self.add_child_element_with_nameattr(parent, 'testHost', name)
        return el

    def add_physical_host(self, parent, name, ipv4_addresses, iface_names):
        el = self.add_host(parent, name)
        self.add_type(el, 'physical')
        for i in range(0, len(ipv4_addresses)):
            addr = ipv4_addresses[i]
            if iface_names:
                ifaceName = iface_names[i]
            else:
                ifaceName = None
            self.add_address(el, 'IPv4', addr, ifaceName)
        return el

    def add_virtual_host(self, parent, obj):
        assert isinstance(obj, nodes.PyCoreNode)
        el = self.add_host(parent, obj.name)
        device = self.find_device(self.root.baseEle, obj.name)
        if device is None:
            self.session.warn('corresponding XML device not found for %s' %
                              (obj.name))
            return
        self.add_mapping(device, 'testHost', el.getAttribute('id'))
        self.add_type(el, 'virtual')
        for netif in obj.netifs():
            for address in netif.addrlist:
                addr, slash, prefixlen= address.partition('/')
                if ipaddr.isIPv4Address(addr):
                    addr_type = 'IPv4'
                elif ipaddr.isIPv6Address(addr):
                    addr_type = 'IPv6'
                else:
                    raise NotImplementedError
                self.add_address(el, addr_type, address, netif.name)
            if isinstance(netif.net, nodes.EmaneNode):
                nem = self.add_emane_interface(parent, el, netif)
                interface = self.find_interface(device, netif.name)
                self.add_mapping(interface, 'nem', nem.getAttribute('id'))
        return el

    def add_emane_interface(self, physical_host, virtual_host, netif,
                            platform_name = 'p1', transport_name = 't1'):
        nemid = netif.net.nemidmap[netif]
        if self.session.emane.version < self.session.emane.EMANE092:
            if self.platform is None:
                self.platform = \
                    self.add_platform(physical_host, name = platform_name)
            platform = self.platform
            if self.transport is None:
                self.transport = \
                    self.add_transport(physical_host, name = transport_name)
            transport = self.transport
        else:
            platform = self.add_platform(virtual_host, name = platform_name)
            transport = self.add_transport(virtual_host, name = transport_name)
        nem_name = 'nem%s' % nemid
        nem = self.add_nem(platform, nem_name)
        self.add_parameter(nem, 'nemid', str(nemid))
        self.add_mapping(transport, 'nem', nem.getAttribute('id'))
        return nem
