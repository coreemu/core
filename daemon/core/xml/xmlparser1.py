import random
from xml.dom.minidom import Node
from xml.dom.minidom import parse

from core import constants
from core import logger
from core.conf import ConfigShim
from core.enumerations import NodeTypes
from core.misc import nodeutils
from core.misc.ipaddress import MacAddress
from core.service import ServiceManager
from core.xml import xmlutils


class CoreDocumentParser1(object):
    layer2_device_types = 'hub', 'switch'
    layer3_device_types = 'host', 'router'
    device_types = layer2_device_types + layer3_device_types

    # TODO: support CORE interface classes:
    #   RJ45Node
    #   TunnelNode

    def __init__(self, session, filename, options):
        """
        Creates an CoreDocumentParser1 object.

        :param core.session.Session session:
        :param str filename: file name to open and parse
        :param dict options: parsing options
        :return:
        """
        logger.info("creating xml parser: file (%s) options(%s)", filename, options)
        self.session = session
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

    @staticmethod
    def get_scenario(dom):
        scenario = xmlutils.get_first_child_by_tag_name(dom, 'scenario')
        if not scenario:
            raise ValueError('no scenario element found')
        version = scenario.getAttribute('version')
        if version and version != '1.0':
            raise ValueError('unsupported scenario version found: \'%s\'' % version)
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
        """
        Get a, possibly new, object id (node number) corresponding to
        the given XML string id.
        """
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
        """
        Return id, name attributes for the given XML element.  These
        attributes are common to nodes and networks.
        """
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
        for interface in xmlutils.iter_children_with_attribute(element, 'member', 'type', 'interface'):
            if_id = xmlutils.get_child_text_trim(interface)
            assert if_id  # XXX for testing
            if not if_id:
                continue
            device, if_name = self.find_device_with_interface(if_id)
            assert device, 'no device for if_id: %s' % if_id  # XXX for testing
            if device:
                yield device, if_name

    def network_class(self, network, network_type):
        """
        Return the corresponding CORE network class for the given
        network/network_type.
        """
        if network_type in ['ethernet', 'satcom']:
            return nodeutils.get_node_class(NodeTypes.PEER_TO_PEER)
        elif network_type == 'wireless':
            channel = xmlutils.get_first_child_by_tag_name(network, 'channel')
            if channel:
                # use an explicit CORE type if it exists
                coretype = xmlutils.get_first_child_text_trim_with_attribute(channel, 'type', 'domain', 'CORE')
                if coretype:
                    if coretype == 'basic_range':
                        return nodeutils.get_node_class(NodeTypes.WIRELESS_LAN)
                    elif coretype.startswith('emane'):
                        return nodeutils.get_node_class(NodeTypes.EMANE)
                    else:
                        logger.warn('unknown network type: \'%s\'', coretype)
                        return xmlutils.xml_type_to_node_class(coretype)
            return nodeutils.get_node_class(NodeTypes.WIRELESS_LAN)
        logger.warn('unknown network type: \'%s\'', network_type)
        return None

    def create_core_object(self, objcls, objid, objname, element, node_type):
        obj = self.session.add_object(cls=objcls, objid=objid, name=objname, start=self.start)
        logger.info('added object objid=%s name=%s cls=%s' % (objid, objname, objcls))
        self.set_object_position(obj, element)
        self.set_object_presentation(obj, element, node_type)
        return obj

    def get_core_object(self, idstr):
        if idstr and idstr in self.objidmap:
            objid = self.objidmap[idstr]
            return self.session.get_object(objid)
        return None

    def parse_network_plan(self):
        # parse the scenario in the following order:
        #   1. layer-2 devices
        #   2. other networks (ptp/wlan)
        #   3. layer-3 devices
        self.parse_layer2_devices()
        self.parse_networks()
        self.parse_layer3_devices()

    def set_ethernet_link_parameters(self, channel, link_params, mobility_model_name, mobility_params):
        # save link parameters for later use, indexed by the tuple
        # (device_id, interface_name)
        for dev, if_name in self.iter_network_member_devices(channel):
            if self.device_type(dev) in self.device_types:
                dev_id = dev.getAttribute('id')
                key = (dev_id, if_name)
                self.link_params[key] = link_params
        if mobility_model_name or mobility_params:
            raise NotImplementedError

    def set_wireless_link_parameters(self, channel, link_params, mobility_model_name, mobility_params):
        network = self.find_channel_network(channel)
        network_id = network.getAttribute('id')
        if network_id in self.objidmap:
            nodenum = self.objidmap[network_id]
        else:
            logger.warn('unknown network: %s', network.toxml('utf-8'))
            assert False  # XXX for testing
        model_name = xmlutils.get_first_child_text_trim_with_attribute(channel, 'type', 'domain', 'CORE')
        if not model_name:
            model_name = 'basic_range'
        if model_name == 'basic_range':
            mgr = self.session.mobility
        elif model_name.startswith('emane'):
            mgr = self.session.emane
        else:
            # TODO: any other config managers?
            raise NotImplementedError
        logger.info("setting wireless link params: node(%s) model(%s) mobility_model(%s)",
                    nodenum, model_name, mobility_model_name)
        mgr.setconfig_keyvalues(nodenum, model_name, link_params.items())
        if mobility_model_name and mobility_params:
            mgr.setconfig_keyvalues(nodenum, mobility_model_name, mobility_params.items())

    def link_layer2_devices(self, device1, ifname1, device2, ifname2):
        """
        Link two layer-2 devices together.
        """
        devid1 = device1.getAttribute('id')
        dev1 = self.get_core_object(devid1)
        devid2 = device2.getAttribute('id')
        dev2 = self.get_core_object(devid2)
        assert dev1 and dev2  # XXX for testing
        if dev1 and dev2:
            # TODO: review this
            if nodeutils.is_node(dev2, NodeTypes.RJ45):
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
        for parameter in xmlutils.iter_children_with_name(parent, 'parameter'):
            param_name = parameter.getAttribute('name')
            assert param_name  # XXX for testing
            if not param_name:
                continue
            # TODO: consider supporting unicode; for now convert
            # to an ascii string
            param_name = str(param_name)
            param_val = cls.parse_xml_value(xmlutils.get_child_text_trim(parameter))
            # TODO: check if the name already exists?
            if param_name and param_val:
                params[param_name] = param_val
        return params

    def parse_network_channel(self, channel):
        element = self.search_for_element(channel, 'type', lambda x: not x.hasAttributes())
        channel_type = xmlutils.get_child_text_trim(element)
        link_params = self.parse_parameter_children(channel)

        mobility = xmlutils.get_first_child_by_tag_name(channel, 'CORE:mobility')
        if mobility:
            mobility_model_name = xmlutils.get_first_child_text_trim_by_tag_name(mobility, 'type')
            mobility_params = self.parse_parameter_children(mobility)
        else:
            mobility_model_name = None
            mobility_params = None

        if channel_type == 'wireless':
            self.set_wireless_link_parameters(channel, link_params, mobility_model_name, mobility_params)
        elif channel_type == 'ethernet':
            # TODO: maybe this can be done in the loop below to avoid
            # iterating through channel members multiple times
            self.set_ethernet_link_parameters(channel, link_params, mobility_model_name, mobility_params)
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
        """
        Each network element should have an 'id' and 'name' attribute
        and include the following child elements:

            type	(one)
            member	(zero or more with type="interface" or type="channel")
            channel	(zero or more)
        """
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
            net_type = xmlutils.get_first_child_text_trim_by_tag_name(network, 'type')
            if not net_type:
                logger.warn('no network type found for network: \'%s\'', network.toxml('utf-8'))
                assert False  # XXX for testing
            net_cls = self.network_class(network, net_type)
            objid, net_name = self.get_common_attributes(network)
            logger.info('parsing network: name=%s id=%s' % (net_name, objid))
            if objid in self.session.objects:
                return
            n = self.create_core_object(net_cls, objid, net_name, network, None)

        # handle channel parameters
        for channel in xmlutils.iter_children_with_name(network, 'channel'):
            self.parse_network_channel(channel)

    def parse_networks(self):
        """
        Parse all 'network' elements.
        """
        for network in xmlutils.iter_descendants_with_name(self.scenario, 'network'):
            self.parse_network(network)

    def parse_addresses(self, interface):
        mac = []
        ipv4 = []
        ipv6 = []
        hostname = []
        for address in xmlutils.iter_children_with_name(interface, 'address'):
            addr_type = address.getAttribute('type')
            if not addr_type:
                msg = 'no type attribute found for address ' \
                      'in interface: \'%s\'' % interface.toxml('utf-8')
                logger.warn(msg)
                assert False  # XXX for testing
            addr_text = xmlutils.get_child_text_trim(address)
            if not addr_text:
                msg = 'no text found for address ' \
                      'in interface: \'%s\'' % interface.toxml('utf-8')
                logger.warn(msg)
                assert False  # XXX for testing
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
                logger.warn(msg)
                assert False  # XXX for testing
        return mac, ipv4, ipv6, hostname

    def parse_interface(self, node, device_id, interface):
        """
        Each interface can have multiple 'address' elements.
        """
        if_name = interface.getAttribute('name')
        network = self.find_interface_network_object(interface)
        if not network:
            msg = 'skipping node \'%s\' interface \'%s\': ' \
                  'unknown network' % (node.name, if_name)
            logger.warn(msg)
            assert False  # XXX for testing
        mac, ipv4, ipv6, hostname = self.parse_addresses(interface)
        if mac:
            hwaddr = MacAddress.from_string(mac[0])
        else:
            hwaddr = None
        ifindex = node.newnetif(network, addrlist=ipv4 + ipv6, hwaddr=hwaddr, ifindex=None, ifname=if_name)
        # TODO: 'hostname' addresses are unused
        msg = 'node \'%s\' interface \'%s\' connected ' \
              'to network \'%s\'' % (node.name, if_name, network.name)
        logger.info(msg)
        # set link parameters for wired links
        if nodeutils.is_node(network, (NodeTypes.HUB, NodeTypes.PEER_TO_PEER, NodeTypes.SWITCH)):
            netif = node.netif(ifindex)
            self.set_wired_link_parameters(network, netif, device_id)

    def set_wired_link_parameters(self, network, netif, device_id, netif_name=None):
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
                network.linkconfig(netif, bw=bw, delay=delay, loss=loss, duplicate=duplicate, jitter=jitter)
            else:
                for k, v in link_params.iteritems():
                    netif.setparam(k, v)

    @staticmethod
    def search_for_element(node, tag_name, match=None):
        """
        Search the given node and all ancestors for an element named
        tagName that satisfies the given matching function.
        """
        while True:
            for child in xmlutils.iter_children(node, Node.ELEMENT_NODE):
                if child.tagName == tag_name and (match is None or match(child)):
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
            return xmlutils.get_child_text_trim(alias)
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
        network_id = xmlutils.get_first_child_text_trim_with_attribute(interface, 'member', 'type', 'network')
        if not network_id:
            # support legacy notation: <interface net="netid" ...
            network_id = interface.getAttribute('net')
        obj = self.get_core_object(network_id)
        if obj:
            # the network_id should exist for ptp or wlan/emane networks
            return obj
        # the network should correspond to a layer-2 device if the
        # network_id does not exist
        channel_id = xmlutils.get_first_child_text_trim_with_attribute(interface, 'member', 'type', 'channel')
        if not network_id or not channel_id:
            return None
        network = xmlutils.get_first_child_with_attribute(self.scenario, 'network', 'id', network_id)
        if not network:
            return None
        channel = xmlutils.get_first_child_with_attribute(network, 'channel', 'id', channel_id)
        if not channel:
            return None
        device = None
        for dev, if_name in self.iter_network_member_devices(channel):
            if self.device_type(dev) in self.layer2_device_types:
                assert not device  # XXX
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
            logger.warn('limiting negative x position of \'%s\' to zero: %s' % (obj.name, x))
            x = 0.0
        if y < 0.0:
            logger.warn('limiting negative y position of \'%s\' to zero: %s' % (obj.name, y))
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
            logger.warn('limiting negative x position of \'%s\' to zero: %s' % (obj.name, x))
            x = 0.0
        if y < 0.0:
            logger.warn('limiting negative y position of \'%s\' to zero: %s' % (obj.name, y))
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
            logger.warn('limiting negative x position of \'%s\' to zero: %s' % (obj.name, x))
            x = 0.0
        if y < 0.0:
            logger.warn('limiting negative y position of \'%s\' to zero: %s' % (obj.name, y))
            y = 0.0
        obj.setposition(x, y, z)

    def set_object_position(self, obj, element):
        """
        Set the x,y,x position of obj from the point associated with
        the given element.
        """
        point = self.find_point(element)
        if not point:
            return False
        point_type = point.getAttribute('type')
        if not point_type:
            msg = 'no type attribute found for point: \'%s\'' % \
                  point.toxml('utf-8')
            logger.warn(msg)
            assert False  # XXX for testing
        elif point_type == 'pixel':
            self.set_object_position_pixel(obj, point)
        elif point_type == 'gps':
            self.set_object_position_gps(obj, point)
        elif point_type == 'cart':
            self.set_object_position_cartesian(obj, point)
        else:
            logger.warn("skipping unknown point type: '%s'" % point_type)
            assert False  # XXX for testing

        logger.info('set position of %s from point element: \'%s\'', obj.name, point.toxml('utf-8'))
        return True

    def parse_device_service(self, service, node):
        name = service.getAttribute('name')
        session_service = ServiceManager.get(name)
        if not session_service:
            assert False  # XXX for testing
        values = []
        startup_idx = service.getAttribute('startup_idx')
        if startup_idx:
            values.append('startidx=%s' % startup_idx)
        startup_time = service.getAttribute('start_time')
        if startup_time:
            values.append('starttime=%s' % startup_time)
        dirs = []
        for directory in xmlutils.iter_children_with_name(service, 'directory'):
            dirname = directory.getAttribute('name')
            dirs.append(str(dirname))
        if dirs:
            values.append("dirs=%s" % dirs)
        startup = []
        shutdown = []
        validate = []
        for command in xmlutils.iter_children_with_name(service, 'command'):
            command_type = command.getAttribute('type')
            command_text = xmlutils.get_child_text_trim(command)
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
        for f in xmlutils.iter_children_with_name(service, 'file'):
            filename = f.getAttribute('name')
            if not filename:
                continue
            filenames.append(filename)
            data = xmlutils.get_child_text_trim(f)
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
            values = ConfigShim.str_to_dict(values)
            self.session.services.setcustomservice(node.objid, session_service, values)

        # NOTE: if a custom service is used, setservicefile() must be
        # called after the custom service exists
        for typestr, filename, data in files:
            self.session.services.setservicefile(
                nodenum=node.objid,
                type=typestr,
                filename=filename,
                srcname=None,
                data=data
            )
        return str(name)

    def parse_device_services(self, services, node):
        """
        Use session.services manager to store service customizations
        before they are added to a node.
        """
        service_names = []
        for service in xmlutils.iter_children_with_name(services, 'service'):
            name = self.parse_device_service(service, node)
            if name:
                service_names.append(name)
        return '|'.join(service_names)

    def add_device_services(self, node, device, node_type):
        """
        Add services to the given node.
        """
        services = xmlutils.get_first_child_by_tag_name(device, 'CORE:services')
        if services:
            services_str = self.parse_device_services(services, node)
            logger.info('services for node \'%s\': %s' % (node.name, services_str))
        elif node_type in self.default_services:
            services_str = None  # default services will be added
        else:
            return
        self.session.services.addservicestonode(
            node=node,
            nodetype=node_type,
            services_str=services_str
        )

    def set_object_presentation(self, obj, element, node_type):
        # defaults from the CORE GUI
        default_icons = {
            'router': 'router.gif',
            'host': 'host.gif',
            'PC': 'pc.gif',
            'mdr': 'mdr.gif',
        }
        icon_set = False
        for child in xmlutils.iter_children_with_name(element, 'CORE:presentation'):
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
        coretype = xmlutils.get_first_child_text_trim_with_attribute(device, 'type', 'domain', 'CORE')
        if coretype:
            return coretype
        return self.device_type(device)

    def find_device_with_interface(self, interface_id):
        # TODO: suport generic 'device' elements
        for device in xmlutils.iter_descendants_with_name(self.scenario, self.device_types):
            interface = xmlutils.get_first_child_with_attribute(device, 'interface', 'id', interface_id)
            if interface:
                if_name = interface.getAttribute('name')
                return device, if_name
        return None, None

    def parse_layer2_device(self, device):
        objid, device_name = self.get_common_attributes(device)
        logger.info('parsing layer-2 device: name=%s id=%s' % (device_name, objid))

        try:
            return self.session.get_object(objid)
        except KeyError:
            logger.exception("error geting object: %s", objid)

        device_type = self.device_type(device)
        if device_type == 'hub':
            device_class = nodeutils.get_node_class(NodeTypes.HUB)
        elif device_type == 'switch':
            device_class = nodeutils.get_node_class(NodeTypes.SWITCH)
        else:
            logger.warn('unknown layer-2 device type: \'%s\'' % device_type)
            assert False  # XXX for testing

        n = self.create_core_object(device_class, objid, device_name, device, None)
        return n

    def parse_layer3_device(self, device):
        objid, device_name = self.get_common_attributes(device)
        logger.info('parsing layer-3 device: name=%s id=%s', device_name, objid)

        try:
            return self.session.get_object(objid)
        except KeyError:
            logger.exception("error getting session object: %s", objid)

        device_cls = self.nodecls
        core_node_type = self.core_node_type(device)
        n = self.create_core_object(device_cls, objid, device_name, device, core_node_type)
        n.type = core_node_type
        self.add_device_services(n, device, core_node_type)
        for interface in xmlutils.iter_children_with_name(device, 'interface'):
            self.parse_interface(n, device.getAttribute('id'), interface)
        return n

    def parse_layer2_devices(self):
        """
        Parse all layer-2 device elements.  A device can be: 'switch',
        'hub'.
        """
        # TODO: suport generic 'device' elements
        for device in xmlutils.iter_descendants_with_name(self.scenario, self.layer2_device_types):
            self.parse_layer2_device(device)

    def parse_layer3_devices(self):
        """
        Parse all layer-3 device elements.  A device can be: 'host',
        'router'.
        """
        # TODO: suport generic 'device' elements
        for device in xmlutils.iter_descendants_with_name(self.scenario, self.layer3_device_types):
            self.parse_layer3_device(device)

    def parse_session_origin(self, session_config):
        """
        Parse the first origin tag and set the CoreLocation reference
        point appropriately.
        """
        # defaults from the CORE GUI
        self.session.location.setrefgeo(47.5791667, -122.132322, 2.0)
        self.session.location.refscale = 150.0
        origin = xmlutils.get_first_child_by_tag_name(session_config, 'origin')
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
        point = xmlutils.get_first_child_text_trim_by_tag_name(origin, 'point')
        if point:
            xyz = point.split(',')
            if len(xyz) == 2:
                xyz.append('0.0')
            if len(xyz) == 3:
                self.session.location.refxyz = (float(xyz[0]), float(xyz[1]), float(xyz[2]))
                self.location_refxyz_set = True

    def parse_session_options(self, session_config):
        options = xmlutils.get_first_child_by_tag_name(session_config, 'options')
        if not options:
            return
        params = self.parse_parameter_children(options)
        for name, value in params.iteritems():
            if name and value:
                self.session.options.set_config(str(name), str(value))

    def parse_session_hooks(self, session_config):
        """
        Parse hook scripts.
        """
        hooks = xmlutils.get_first_child_by_tag_name(session_config, 'hooks')
        if not hooks:
            return
        for hook in xmlutils.iter_children_with_name(hooks, 'hook'):
            filename = hook.getAttribute('name')
            state = hook.getAttribute('state')
            data = xmlutils.get_child_text_trim(hook)
            if data is None:
                data = ''  # allow for empty file
            hook_type = "hook:%s" % state
            self.session.set_hook(hook_type, file_name=str(filename), source_name=None, data=str(data))

    def parse_session_metadata(self, session_config):
        metadata = xmlutils.get_first_child_by_tag_name(session_config, 'metadata')
        if not metadata:
            return
        params = self.parse_parameter_children(metadata)
        for name, value in params.iteritems():
            if name and value:
                self.session.metadata.add_item(str(name), str(value))

    def parse_session_config(self):
        session_config = xmlutils.get_first_child_by_tag_name(self.scenario, 'CORE:sessionconfig')
        if not session_config:
            return
        self.parse_session_origin(session_config)
        self.parse_session_options(session_config)
        self.parse_session_hooks(session_config)
        self.parse_session_metadata(session_config)

    def parse_default_services(self):
        # defaults from the CORE GUI
        self.default_services = {
            'router': ['zebra', 'OSPFv2', 'OSPFv3', 'IPForward'],
            'host': ['DefaultRoute', 'SSH'],
            'PC': ['DefaultRoute', ],
            'mdr': ['zebra', 'OSPFv3MDR', 'IPForward'],
        }
        default_services = xmlutils.get_first_child_by_tag_name(self.scenario, 'CORE:defaultservices')
        if not default_services:
            return
        for device in xmlutils.iter_children_with_name(default_services, 'device'):
            device_type = device.getAttribute('type')
            if not device_type:
                logger.warn('parse_default_services: no type attribute found for device')
                continue
            services = []
            for service in xmlutils.iter_children_with_name(device, 'service'):
                name = service.getAttribute('name')
                if name:
                    services.append(str(name))
            self.default_services[device_type] = services
        # store default services for the session
        for t, s in self.default_services.iteritems():
            self.session.services.defaultservices[t] = s
            logger.info('default services for node type \'%s\' set to: %s' % (t, s))
