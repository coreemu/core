#
# CORE
# Copyright (c) 2015 the Boeing Company.
# See the LICENSE file included in this distribution.
#

import sys
import random
from core.netns import nodes
from core import constants
from core.misc.ipaddr import MacAddr
from xml.dom.minidom import parse
from xmlutils import *

class CoreDocumentParser1(object):

    layer2_device_types = 'hub', 'switch'
    layer3_device_types = 'host', 'router'
    device_types = layer2_device_types + layer3_device_types

    # TODO: support CORE interface classes:
    #   RJ45Node
    #   TunnelNode

    def __init__(self, session, filename, options):
        self.session = session
        self.verbose = self.session.getcfgitembool('verbose', False)
        self.filename = filename
        if 'dom' in options:
            # this prevents parsing twice when detecting file versions
            self.dom = options['dom']
        else:
            self.dom = parse(filename)
        self.start = options['start']
        self.nodecls = options['nodecls']
        self.scenario = self.get_scenario(self.dom)
        self.location_refgeo_set = False
        self.location_refxyz_set = False
        # saved link parameters saved when parsing networks and applied later
        self.link_params = {}
        # map from id-string to objid, for files having node names but
        # not node numbers
        self.objidmap = {}
        self.objids = set()
        self.default_services = {}
        if self.scenario:
            self.parse_scenario()

    def info(self, msg):
        s = 'XML parsing \'%s\': %s' % (self.filename, msg)
        if self.session:
            self.session.info(s)
        else:
            sys.stdout.write(s + '\n')

    def warn(self, msg):
        s = 'WARNING XML parsing \'%s\': %s' % (self.filename, msg)
        if self.session:
            self.session.warn(s)
        else:
            sys.stderr.write(s + '\n')

    @staticmethod
    def get_scenario(dom):
        scenario = getFirstChildByTagName(dom, 'scenario')
        if not scenario:
            raise ValueError, 'no scenario element found'
        version = scenario.getAttribute('version')
        if version and version != '1.0':
            raise ValueError, \
                'unsupported scenario version found: \'%s\'' % version
        return scenario

    def parse_scenario(self):
        self.parse_default_services()
        self.parse_session_config()
        self.parse_network_plan()

    def assign_id(self, idstr, idval):
        if idstr in self.objidmap:
            assert self.objidmap[idstr] == idval and idval in self.objids
            return
        self.objidmap[idstr] = idval
        self.objids.add(idval)

    def rand_id(self):
        while True:
            x = random.randint(0, 0xffff)
            if x not in self.objids:
                return x

    def get_id(self, idstr):
        '''\
        Get a, possibly new, object id (node number) corresponding to
        the given XML string id.
        '''
        if not idstr:
            idn = self.rand_id()
            self.objids.add(idn)
            return idn
        elif idstr in self.objidmap:
            return self.objidmap[idstr]
        else:
            try:
                idn = int(idstr)
            except ValueError:
                idn = self.rand_id()
            self.assign_id(idstr, idn)
            return idn

    def get_common_attributes(self, node):
        '''\
        Return id, name attributes for the given XML element.  These
        attributes are common to nodes and networks.
        '''
        idstr = node.getAttribute('id')
        # use an explicit set COREID if it exists
        coreid = self.find_core_id(node)
        if coreid:
            idn = int(coreid)
            if idstr:
                self.assign_id(idstr, idn)
        else:
            idn = self.get_id(idstr)
        # TODO: consider supporting unicode; for now convert to an
        # ascii string
        namestr = str(node.getAttribute('name'))
        return idn, namestr

    def iter_network_member_devices(self, element):
        # element can be a network or a channel
        for interface in iterChildrenWithAttribute(element, 'member',
                                                   'type', 'interface'):
            if_id = getChildTextTrim(interface)
            assert if_id        # XXX for testing
            if not if_id:
                continue
            device, if_name = self.find_device_with_interface(if_id)
            assert device, 'no device for if_id: %s' % if_id # XXX for testing
            if device:
                yield device, if_name

    def network_class(self, network, network_type):
        '''\
        Return the corresponding CORE network class for the given
        network/network_type.
        '''
        if network_type == 'ethernet':
            return nodes.PtpNet
        elif network_type == 'satcom':
            return nodes.PtpNet
        elif network_type == 'wireless':
            channel = getFirstChildByTagName(network, 'channel')
            if channel:
                # use an explicit CORE type if it exists
                coretype = getFirstChildTextTrimWithAttribute(channel, 'type',
                                                              'domain', 'CORE')
                if coretype:
                    if coretype == 'basic_range':
                        return nodes.WlanNode
                    elif coretype.startswith('emane'):
                        return nodes.EmaneNode
                    else:
                        self.warn('unknown network type: \'%s\'' % coretype)
                        return xmltypetonodeclass(self.session, coretype)
            return nodes.WlanNode
        self.warn('unknown network type: \'%s\'' % network_type)
        return None

    def create_core_object(self, objcls, objid, objname, element, node_type):
        obj = self.session.addobj(cls = objcls, objid = objid,
                                  name = objname, start = self.start)
        if self.verbose:
            self.info('added object objid=%s name=%s cls=%s' % \
                          (objid, objname, objcls))
        self.set_object_position(obj, element)
        self.set_object_presentation(obj, element, node_type)
        return obj

    def get_core_object(self, idstr):
        if idstr and idstr in self.objidmap:
            objid = self.objidmap[idstr]
            return self.session.obj(objid)
        return None

    def parse_network_plan(self):
        # parse the scenario in the following order:
        #   1. layer-2 devices
        #   2. other networks (ptp/wlan)
        #   3. layer-3 devices
        self.parse_layer2_devices()
        self.parse_networks()
        self.parse_layer3_devices()

    def set_ethernet_link_parameters(self, channel, link_params,
                                     mobility_model_name, mobility_params):
        # save link parameters for later use, indexed by the tuple
        # (device_id, interface_name)
        for dev, if_name in self.iter_network_member_devices(channel):
            if self.device_type(dev) in self.device_types:
                dev_id = dev.getAttribute('id')
                key = (dev_id, if_name)
                self.link_params[key] = link_params
        if mobility_model_name or mobility_params:
            raise NotImplementedError

    def set_wireless_link_parameters(self, channel, link_params,
                                     mobility_model_name, mobility_params):
        network = self.find_channel_network(channel)
        network_id = network.getAttribute('id')
        if network_id in self.objidmap:
            nodenum = self.objidmap[network_id]
        else:
            self.warn('unknown network: %s' % network.toxml('utf-8'))
            assert False        # XXX for testing
            return
        model_name = getFirstChildTextTrimWithAttribute(channel, 'type',
                                                        'domain', 'CORE')
        if not model_name:
            model_name = 'basic_range'
        if model_name == 'basic_range':
            mgr = self.session.mobility
        elif model_name.startswith('emane'):
            mgr = self.session.emane
        elif model_name.startswith('xen'):
            mgr = self.session.xen
        else:
            # TODO: any other config managers?
            raise NotImplementedError
        mgr.setconfig_keyvalues(nodenum, model_name, link_params.items())
        if mobility_model_name and mobility_params:
            mgr.setconfig_keyvalues(nodenum, mobility_model_name,
                                    mobility_params.items())

    def link_layer2_devices(self, device1, ifname1, device2, ifname2):
        '''\
        Link two layer-2 devices together.
        '''
        devid1 = device1.getAttribute('id')
        dev1 = self.get_core_object(devid1)
        devid2 = device2.getAttribute('id')
        dev2 = self.get_core_object(devid2)
        assert dev1 and dev2    # XXX for testing
        if dev1 and dev2:
            # TODO: review this
            if isinstance(dev2, nodes.RJ45Node):
                # RJ45 nodes have different linknet()
                netif = dev2.linknet(dev1)
            else:
                netif = dev1.linknet(dev2)
            self.set_wired_link_parameters(dev1, netif, devid1, ifname1)

    @classmethod
    def parse_xml_value(cls, valtext):
        if not valtext:
            return None
        try:
            if not valtext.translate(None, '0123456789'):
                val = int(valtext)
            else:
                val = float(valtext)
        except ValueError:
            val = str(valtext)
        return val

    @classmethod
    def parse_parameter_children(cls, parent):
        params = {}
        for parameter in iterChildrenWithName(parent, 'parameter'):
            param_name = parameter.getAttribute('name')
            assert param_name   # XXX for testing
            if not param_name:
                continue
            # TODO: consider supporting unicode; for now convert
            # to an ascii string
            param_name = str(param_name)
            param_val = cls.parse_xml_value(getChildTextTrim(parameter))
            # TODO: check if the name already exists?
            if param_name and param_val:
                params[param_name] = param_val
        return params

    def parse_network_channel(self, channel):
        element = self.search_for_element(channel, 'type',
                                          lambda x: not x.hasAttributes())
        channel_type = getChildTextTrim(element)
        link_params = self.parse_parameter_children(channel)

        mobility = getFirstChildByTagName(channel, 'CORE:mobility')
        if mobility:
            mobility_model_name = \
                getFirstChildTextTrimByTagName(mobility, 'type')
            mobility_params = self.parse_parameter_children(mobility)
        else:
            mobility_model_name = None
            mobility_params = None
        if channel_type == 'wireless':
            self.set_wireless_link_parameters(channel, link_params,
                                              mobility_model_name,
                                              mobility_params)
        elif channel_type == 'ethernet':
            # TODO: maybe this can be done in the loop below to avoid
            # iterating through channel members multiple times
            self.set_ethernet_link_parameters(channel, link_params,
                                              mobility_model_name,
                                              mobility_params)
        else:
            raise NotImplementedError
        layer2_device = []
        for dev, if_name in self.iter_network_member_devices(channel):
            if self.device_type(dev) in self.layer2_device_types:
                layer2_device.append((dev, if_name))
        assert len(layer2_device) <= 2
        if len(layer2_device) == 2:
            self.link_layer2_devices(layer2_device[0][0], layer2_device[0][1],
                                     layer2_device[1][0], layer2_device[1][1])

    def parse_network(self, network):
        '''\
        Each network element should have an 'id' and 'name' attribute
        and include the following child elements:

            type	(one)
            member	(zero or more with type="interface" or type="channel")
            channel	(zero or more)
        '''
        layer2_members = set()
        layer3_members = 0
        for dev, if_name in self.iter_network_member_devices(network):
            if not dev:
                continue
            devtype = self.device_type(dev)
            if devtype in self.layer2_device_types:
                layer2_members.add(dev)
            elif devtype in self.layer3_device_types:
                layer3_members += 1
            else:
                raise NotImplementedError
        if len(layer2_members) == 0:
            net_type = getFirstChildTextTrimByTagName(network, 'type')
            if not net_type:
                msg = 'no network type found for network: \'%s\'' % \
                    network.toxml('utf-8')
                self.warn(msg)
                assert False    # XXX for testing
                return
            net_cls = self.network_class(network, net_type)
            objid, net_name = self.get_common_attributes(network)
            if self.verbose:
                self.info('parsing network: %s %s' % (net_name, objid))
            if objid in self.session._objs:
                return
            n = self.create_core_object(net_cls, objid, net_name,
                                        network, None)
        # handle channel parameters
        for channel in iterChildrenWithName(network, 'channel'):
            self.parse_network_channel(channel)

    def parse_networks(self):
        '''\
        Parse all 'network' elements.
        '''
        for network in iterDescendantsWithName(self.scenario, 'network'):
            self.parse_network(network)

    def parse_addresses(self, interface):
        mac = []
        ipv4 = []
        ipv6= []
        hostname = []
        for address in iterChildrenWithName(interface, 'address'):
            addr_type = address.getAttribute('type')
            if not addr_type:
                msg = 'no type attribute found for address ' \
                    'in interface: \'%s\'' % interface.toxml('utf-8')
                self.warn(msg)
                assert False    # XXX for testing
                continue
            addr_text = getChildTextTrim(address)
            if not addr_text:
                msg = 'no text found for address ' \
                    'in interface: \'%s\'' % interface.toxml('utf-8')
                self.warn(msg)
                assert False    # XXX for testing
                continue
            if addr_type == 'mac':
                mac.append(addr_text)
            elif addr_type == 'IPv4':
                ipv4.append(addr_text)
            elif addr_type == 'IPv6':
                ipv6.append(addr_text)
            elif addr_type == 'hostname':
                hostname.append(addr_text)
            else:
                msg = 'skipping unknown address type \'%s\' in ' \
                    'interface: \'%s\'' % (addr_type, interface.toxml('utf-8'))
                self.warn(msg)
                assert False    # XXX for testing
                continue
        return mac, ipv4, ipv6, hostname

    def parse_interface(self, node, device_id, interface):
        '''\
        Each interface can have multiple 'address' elements.
        '''
        if_name = interface.getAttribute('name')
        network = self.find_interface_network_object(interface)
        if not network:
            msg = 'skipping node \'%s\' interface \'%s\': ' \
                'unknown network' % (node.name, if_name)
            self.warn(msg)
            assert False    # XXX for testing
            return
        mac, ipv4, ipv6, hostname = self.parse_addresses(interface)
        if mac:
            hwaddr = MacAddr.fromstring(mac[0])
        else:
            hwaddr = None
        ifindex = node.newnetif(network, addrlist = ipv4 + ipv6,
                                hwaddr = hwaddr, ifindex = None,
                                ifname = if_name)
        # TODO: 'hostname' addresses are unused
        if self.verbose:
            msg = 'node \'%s\' interface \'%s\' connected ' \
                'to network \'%s\'' % (node.name, if_name, network.name)
            self.info(msg)
        # set link parameters for wired links
        if isinstance(network,
                      (nodes.HubNode, nodes.PtpNet, nodes.SwitchNode)):
            netif = node.netif(ifindex)
            self.set_wired_link_parameters(network, netif, device_id)

    def set_wired_link_parameters(self, network, netif,
                                  device_id, netif_name = None):
        if netif_name is None:
            netif_name = netif.name
        key = (device_id, netif_name)
        if key in self.link_params:
            link_params = self.link_params[key]
            if self.start:
                bw = link_params.get('bw')
                delay = link_params.get('delay')
                loss = link_params.get('loss')
                duplicate = link_params.get('duplicate')
                jitter = link_params.get('jitter')
                network.linkconfig(netif, bw = bw, delay = delay, loss = loss,
                                   duplicate = duplicate, jitter = jitter)
            else:
                for k, v in link_params.iteritems():
                    netif.setparam(k, v)

    @staticmethod
    def search_for_element(node, tagName, match = None):
        '''\
        Search the given node and all ancestors for an element named
        tagName that satisfies the given matching function.
        '''
        while True:
            for child in iterChildren(node, Node.ELEMENT_NODE):
                if child.tagName == tagName and \
                        (match is None or match(child)):
                    return child
            node = node.parentNode
            if not node:
                break
        return None

    @classmethod
    def find_core_id(cls, node):
        def match(x):
            domain = x.getAttribute('domain')
            return domain == 'COREID'
        alias = cls.search_for_element(node, 'alias', match)
        if alias:
            return getChildTextTrim(alias)
        return None

    @classmethod
    def find_point(cls, node):
        return cls.search_for_element(node, 'point')

    @staticmethod
    def find_channel_network(channel):
        p = channel.parentNode
        if p and p.tagName == 'network':
            return p
        return None

    def find_interface_network_object(self, interface):
        network_id = getFirstChildTextTrimWithAttribute(interface, 'member',
                                                        'type', 'network')
        if not network_id:
            # support legacy notation: <interface net="netid" ...
            network_id = interface.getAttribute('net')
        obj = self.get_core_object(network_id)
        if obj:
            # the network_id should exist for ptp or wlan/emane networks
            return obj
        # the network should correspond to a layer-2 device if the
        # network_id does not exist
        channel_id = getFirstChildTextTrimWithAttribute(interface, 'member',
                                                        'type', 'channel')
        if not network_id or not channel_id:
            return None
        network = getFirstChildWithAttribute(self.scenario, 'network',
                                             'id', network_id)
        if not network:
            return None
        channel = getFirstChildWithAttribute(network, 'channel',
                                             'id', channel_id)
        if not channel:
            return None
        device = None
        for dev, if_name in self.iter_network_member_devices(channel):
            if self.device_type(dev) in self.layer2_device_types:
                assert not device # XXX
                device = dev
        if device:
            obj = self.get_core_object(device.getAttribute('id'))
            if obj:
                return obj
        return None

    def set_object_position_pixel(self, obj, point):
        x = float(point.getAttribute('x'))
        y = float(point.getAttribute('y'))
        z = point.getAttribute('z')
        if z:
            z = float(z)
        else:
            z = 0.0
        # TODO: zMode is unused
        # z_mode = point.getAttribute('zMode'))
        if x < 0.0:
            self.warn('limiting negative x position of \'%s\' to zero: %s' %
                      (obj.name, x))
            x = 0.0
        if y < 0.0:
            self.warn('limiting negative y position of \'%s\' to zero: %s' %
                      (obj.name, y))
            y = 0.0
        obj.setposition(x, y, z)

    def set_object_position_gps(self, obj, point):
        lat = float(point.getAttribute('lat'))
        lon = float(point.getAttribute('lon'))
        zalt = point.getAttribute('z')
        if zalt:
            zalt = float(zalt)
        else:
            zalt = 0.0
        # TODO: zMode is unused
        # z_mode = point.getAttribute('zMode'))
        if not self.location_refgeo_set:
            # for x,y,z conversion, we need a reasonable refpt; this
            # picks the first coordinates as the origin
            self.session.location.setrefgeo(lat, lon, zalt)
            self.location_refgeo_set = True
        x, y, z = self.session.location.getxyz(lat, lon, zalt)
        if x < 0.0:
            self.warn('limiting negative x position of \'%s\' to zero: %s' %
                      (obj.name, x))
            x = 0.0
        if y < 0.0:
            self.warn('limiting negative y position of \'%s\' to zero: %s' %
                      (obj.name, y))
            y = 0.0
        obj.setposition(x, y, z)

    def set_object_position_cartesian(self, obj, point):
        # TODO: review this
        xm = float(point.getAttribute('x'))
        ym = float(point.getAttribute('y'))
        zm = point.getAttribute('z')
        if zm:
            zm = float(zm)
        else:
            zm = 0.0
        # TODO: zMode is unused
        # z_mode = point.getAttribute('zMode'))
        if not self.location_refxyz_set:
            self.session.location.refxyz = xm, ym, zm
            self.location_refxyz_set = True
        # need to convert meters to pixels
        x = self.session.location.m2px(xm) + self.session.location.refxyz[0]
        y = self.session.location.m2px(ym) + self.session.location.refxyz[1]
        z = self.session.location.m2px(zm) + self.session.location.refxyz[2]
        if x < 0.0:
            self.warn('limiting negative x position of \'%s\' to zero: %s' %
                      (obj.name, x))
            x = 0.0
        if y < 0.0:
            self.warn('limiting negative y position of \'%s\' to zero: %s' %
                      (obj.name, y))
            y = 0.0
        obj.setposition(x, y, z)

    def set_object_position(self, obj, element):
        '''\
        Set the x,y,x position of obj from the point associated with
        the given element.
        '''
        point = self.find_point(element)
        if not point:
            return False
        point_type = point.getAttribute('type')
        if not point_type:
            msg = 'no type attribute found for point: \'%s\'' % \
                point.toxml('utf-8')
            self.warn(msg)
            assert False    # XXX for testing
            return False
        elif point_type == 'pixel':
            self.set_object_position_pixel(obj, point)
        elif point_type == 'gps':
            self.set_object_position_gps(obj, point)
        elif point_type == 'cart':
            self.set_object_position_cartesian(obj, point)
        else:
            self.warn("skipping unknown point type: '%s'" % point_type)
            assert False    # XXX for testing
            return False
        if self.verbose:
            msg = 'set position of %s from point element: \'%s\'' % \
                (obj.name, point.toxml('utf-8'))
            self.info(msg)
        return True

    def parse_device_service(self, service, node):
        name = service.getAttribute('name')
        session_service = self.session.services.getservicebyname(name)
        if not session_service:
            assert False        # XXX for testing
            return None
        values = []
        startup_idx = service.getAttribute('startup_idx')
        if startup_idx:
            values.append('startidx=%s' % startup_idx)
        startup_time = service.getAttribute('start_time')
        if startup_time:
            values.append('starttime=%s' % startup_time)
        dirs = []
        for directory in iterChildrenWithName(service, 'directory'):
            dirname = directory.getAttribute('name')
            dirs.append(str(dirname))
        if dirs:
            values.append("dirs=%s" % dirs)
        startup = []
        shutdown = []
        validate = []
        for command in iterChildrenWithName(service, 'command'):
            command_type = command.getAttribute('type')
            command_text = getChildTextTrim(command)
            if not command_text:
                continue
            if command_type == 'start':
                startup.append(str(command_text))
            elif command_type == 'stop':
                shutdown.append(str(command_text))
            elif command_type == 'validate':
                validate.append(str(command_text))
        if startup:
            values.append('cmdup=%s' % startup)
        if shutdown:
            values.append('cmddown=%s' % shutdown)
        if validate:
            values.append('cmdval=%s' % validate)
        filenames = []
        files = []
        for f in iterChildrenWithName(service, 'file'):
            filename = f.getAttribute('name')
            if not filename:
                continue;
            filenames.append(filename)
            data = getChildTextTrim(f)
            if data:
                data = str(data)
            else:
                data = None
            typestr = 'service:%s:%s' % (name, filename)
            files.append((typestr, filename, data))
        if filenames:
            values.append('files=%s' % filenames)
        custom = service.getAttribute('custom')
        if custom and custom.lower() == 'true':
            self.session.services.setcustomservice(node.objid,
                                                   session_service, values)
        # NOTE: if a custom service is used, setservicefile() must be
        # called after the custom service exists
        for typestr, filename, data in files:
            self.session.services.setservicefile(nodenum = node.objid,
                                                 type = typestr,
                                                 filename = filename,
                                                 srcname = None,
                                                 data = data)
        return str(name)

    def parse_device_services(self, services, node):
        '''\
        Use session.services manager to store service customizations
        before they are added to a node.
        '''
        service_names = []
        for service in iterChildrenWithName(services, 'service'):
            name = self.parse_device_service(service, node)
            if name:
                service_names.append(name)
        return '|'.join(service_names)

    def add_device_services(self, node, device, node_type):
        '''\
        Add services to the given node.
        '''
        services = getFirstChildByTagName(device, 'CORE:services')
        if services:
            services_str = self.parse_device_services(services, node)
            if self.verbose:
                self.info('services for node \'%s\': %s' % \
                              (node.name, services_str))
        elif node_type in self.default_services:
            services_str = None # default services will be added
        else:
            return
        self.session.services.addservicestonode(node = node,
                                                nodetype = node_type,
                                                services_str = services_str,
                                                verbose = self.verbose)

    def set_object_presentation(self, obj, element, node_type):
        # defaults from the CORE GUI
        default_icons = {
            'router': 'router.gif',
            'host': 'host.gif',
            'PC': 'pc.gif',
            'mdr': 'mdr.gif',
            # 'prouter': 'router_green.gif',
            # 'xen': 'xen.gif'
            }
        icon_set = False
        for child in iterChildrenWithName(element, 'CORE:presentation'):
            canvas = child.getAttribute('canvas')
            if canvas:
                obj.canvas = int(canvas)
            icon = child.getAttribute('icon')
            if icon:
                icon = str(icon).replace("$CORE_DATA_DIR",
                                         constants.CORE_DATA_DIR)
                obj.icon = icon
                icon_set = True
        if not icon_set and node_type in default_icons:
            obj.icon = default_icons[node_type]

    def device_type(self, device):
        if device.tagName in self.device_types:
            return device.tagName
        return None

    def core_node_type(self, device):
        # use an explicit CORE type if it exists
        coretype = getFirstChildTextTrimWithAttribute(device, 'type',
                                                      'domain', 'CORE')
        if coretype:
            return coretype
        return self.device_type(device)

    def find_device_with_interface(self, interface_id):
        # TODO: suport generic 'device' elements
        for device in iterDescendantsWithName(self.scenario,
                                              self.device_types):
            interface = getFirstChildWithAttribute(device, 'interface',
                                                   'id', interface_id)
            if interface:
                if_name = interface.getAttribute('name')
                return device, if_name
        return None, None

    def parse_layer2_device(self, device):
        objid, device_name = self.get_common_attributes(device)
        if self.verbose:
            self.info('parsing layer-2 device: %s %s' % (device_name, objid))
        try:
            return self.session.obj(objid)
        except KeyError:
            pass
        device_type = self.device_type(device)
        if device_type == 'hub':
            device_class = nodes.HubNode
        elif device_type == 'switch':
            device_class = nodes.SwitchNode
        else:
            self.warn('unknown layer-2 device type: \'%s\'' % device_type)
            assert False        # XXX for testing
            return None
        n = self.create_core_object(device_class, objid, device_name,
                                    device, None)
        return n

    def parse_layer3_device(self, device):
        objid, device_name = self.get_common_attributes(device)
        if self.verbose:
            self.info('parsing layer-3 device: %s %s' % (device_name, objid))
        try:
            return self.session.obj(objid)
        except KeyError:
            pass
        device_cls = self.nodecls
        core_node_type = self.core_node_type(device)
        n = self.create_core_object(device_cls, objid, device_name,
                                    device, core_node_type)
        n.type = core_node_type
        self.add_device_services(n, device, core_node_type)
        for interface in iterChildrenWithName(device, 'interface'):
            self.parse_interface(n, device.getAttribute('id'), interface)
        return n

    def parse_layer2_devices(self):
        '''\
        Parse all layer-2 device elements.  A device can be: 'switch',
        'hub'.
        '''
        # TODO: suport generic 'device' elements
        for device in iterDescendantsWithName(self.scenario,
                                              self.layer2_device_types):
            self.parse_layer2_device(device)

    def parse_layer3_devices(self):
        '''\
        Parse all layer-3 device elements.  A device can be: 'host',
        'router'.
        '''
        # TODO: suport generic 'device' elements
        for device in iterDescendantsWithName(self.scenario,
                                              self.layer3_device_types):
            self.parse_layer3_device(device)

    def parse_session_origin(self, session_config):
        '''\
        Parse the first origin tag and set the CoreLocation reference
        point appropriately.
        '''
        # defaults from the CORE GUI
        self.session.location.setrefgeo(47.5791667, -122.132322, 2.0)
        self.session.location.refscale = 150.0
        origin = getFirstChildByTagName(session_config, 'origin')
        if not origin:
            return
        lat = origin.getAttribute('lat')
        lon = origin.getAttribute('lon')
        alt = origin.getAttribute('alt')
        if lat and lon and alt:
            self.session.location.setrefgeo(float(lat), float(lon), float(alt))
            self.location_refgeo_set = True
        scale100 = origin.getAttribute("scale100")
        if scale100:
            self.session.location.refscale = float(scale100)
        point = getFirstChildTextTrimByTagName(origin, 'point')
        if point:
            xyz = point.split(',')
            if len(xyz) == 2:
                xyz.append('0.0')
            if len(xyz) == 3:
                self.session.location.refxyz = \
                    (float(xyz[0]), float(xyz[1]), float(xyz[2]))
                self.location_refxyz_set = True

    def parse_session_options(self, session_config):
        options = getFirstChildByTagName(session_config, 'options')
        if not options:
            return
        params = self.parse_parameter_children(options)
        for name, value in params.iteritems():
            if name and value:
                setattr(self.session.options, str(name), str(value))

    def parse_session_hooks(self, session_config):
        '''\
        Parse hook scripts.
        '''
        hooks = getFirstChildByTagName(session_config, 'hooks')
        if not hooks:
            return
        for hook in iterChildrenWithName(hooks, 'hook'):
            filename = hook.getAttribute('name')
            state = hook.getAttribute('state')
            data = getChildTextTrim(hook)
            if data is None:
                data = ''       # allow for empty file
            hook_type = "hook:%s" % state
            self.session.sethook(hook_type, filename = str(filename),
                                 srcname = None, data = str(data))

    def parse_session_metadata(self, session_config):
        metadata = getFirstChildByTagName(session_config, 'metadata')
        if not metadata:
            return
        params = self.parse_parameter_children(metadata)
        for name, value in params.iteritems():
            if name and value:
                self.session.metadata.additem(str(name), str(value))

    def parse_session_config(self):
        session_config = \
            getFirstChildByTagName(self.scenario, 'CORE:sessionconfig')
        if not session_config:
            return
        self.parse_session_origin(session_config)
        self.parse_session_options(session_config)
        self.parse_session_hooks(session_config)
        self.parse_session_metadata(session_config)

    def parse_default_services(self):
        # defaults from the CORE GUI
        self.default_services = {
            'router': ['zebra', 'OSPFv2', 'OSPFv3', 'vtysh', 'IPForward'],
            'host': ['DefaultRoute', 'SSH'],
            'PC': ['DefaultRoute',],
            'mdr': ['zebra', 'OSPFv3MDR', 'vtysh', 'IPForward'],
            # 'prouter': ['zebra', 'OSPFv2', 'OSPFv3', 'vtysh', 'IPForward'],
            # 'xen': ['zebra', 'OSPFv2', 'OSPFv3', 'vtysh', 'IPForward'],
            }
        default_services = \
            getFirstChildByTagName(self.scenario, 'CORE:defaultservices')
        if not default_services:
            return
        for device in iterChildrenWithName(default_services, 'device'):
            device_type = device.getAttribute('type')
            if not device_type:
                self.warn('parse_default_services: no type attribute ' \
                              'found for device')
                continue
            services = []
            for service in iterChildrenWithName(device, 'service'):
                name = service.getAttribute('name')
                if name:
                    services.append(str(name))
            self.default_services[device_type] = services
        # store default services for the session
        for t, s in self.default_services.iteritems():
            self.session.services.defaultservices[t] = s
            if self.verbose:
                self.info('default services for node type \'%s\' ' \
                              'set to: %s' % (t, s))
