from core.enumerations import LinkTypes
from core.misc.ipaddress import Ipv4Prefix
from core.misc.ipaddress import Ipv6Prefix
from core.misc.ipaddress import MacAddress


class NodeOptions(object):
    """
    Options for creating and updating nodes within core.
    """

    def __init__(self, name=None, model="router"):
        """
        Create a NodeOptions object.

        :param str name: name of node, defaults to node class name postfix with its id
        :param str model: defines services for default and physical nodes, defaults to "router"
        """
        self.name = name
        self.model = model
        self.canvas = None
        self.icon = None
        self.opaque = None
        self.services = []
        self.x = None
        self.y = None
        self.lat = None
        self.lon = None
        self.alt = None
        self.emulation_id = None
        self.emulation_server = None

    def set_position(self, x, y):
        """
        Convenience method for setting position.

        :param float x: x position
        :param float y: y position
        :return: nothing
        """
        self.x = x
        self.y = y

    def set_location(self, lat, lon, alt):
        """
        Convenience method for setting location.

        :param float lat: latitude
        :param float lon: longitude
        :param float alt: altitude
        :return: nothing
        """
        self.lat = lat
        self.lon = lon
        self.alt = alt


class LinkOptions(object):
    """
    Options for creating and updating links within core.
    """

    def __init__(self, _type=LinkTypes.WIRED):
        """
        Create a LinkOptions object.

        :param core.enumerations.LinkTypes _type: type of link, defaults to wired
        """
        self.type = _type
        self.session = None
        self.delay = None
        self.bandwidth = None
        self.per = None
        self.dup = None
        self.jitter = None
        self.mer = None
        self.burst = None
        self.mburst = None
        self.gui_attributes = None
        self.unidirectional = None
        self.emulation_id = None
        self.network_id = None
        self.key = None
        self.opaque = None


class IpPrefixes(object):
    """
    Convenience class to help generate IP4 and IP6 addresses for nodes within CORE.
    """

    def __init__(self, ip4_prefix=None, ip6_prefix=None):
        """
        Creates an IpPrefixes object.

        :param str ip4_prefix: ip4 prefix to use for generation
        :param str ip6_prefix: ip6 prefix to use for generation
        :raises ValueError: when both ip4 and ip6 prefixes have not been provided
        """
        if not ip4_prefix and not ip6_prefix:
            raise ValueError("ip4 or ip6 must be provided")

        self.ip4 = None
        if ip4_prefix:
            self.ip4 = Ipv4Prefix(ip4_prefix)
        self.ip6 = None
        if ip6_prefix:
            self.ip6 = Ipv6Prefix(ip6_prefix)

    def ip4_address(self, node):
        """
        Convenience method to return the IP4 address for a node.

        :param node: node to get IP4 address for
        :return: IP4 address or None
        :rtype: str
        """
        if not self.ip4:
            raise ValueError("ip4 prefixes have not been set")
        return str(self.ip4.addr(node.id))

    def ip6_address(self, node):
        """
        Convenience method to return the IP6 address for a node.

        :param node: node to get IP6 address for
        :return: IP4 address or None
        :rtype: str
        """
        if not self.ip6:
            raise ValueError("ip6 prefixes have not been set")
        return str(self.ip6.addr(node.id))

    def create_interface(self, node, name=None, mac=None):
        """
        Creates interface data for linking nodes, using the nodes unique id for generation, along with a random
        mac address, unless provided.

        :param core.coreobj.PyCoreNode node: node to create interface for
        :param str name: name to set for interface, default is eth{id}
        :param str mac: mac address to use for this interface, default is random generation
        :return: new interface data for the provided node
        :rtype: InterfaceData
        """
        # interface id
        inteface_id = node.newifindex()

        # generate ip4 data
        ip4 = None
        ip4_mask = None
        if self.ip4:
            ip4 = str(self.ip4.addr(node.id))
            ip4_mask = self.ip4.prefixlen

        # generate ip6 data
        ip6 = None
        ip6_mask = None
        if self.ip6:
            ip6 = str(self.ip6.addr(node.id))
            ip6_mask = self.ip6.prefixlen

        # random mac
        if not mac:
            mac = MacAddress.random()

        return InterfaceData(
            _id=inteface_id,
            name=name,
            ip4=ip4,
            ip4_mask=ip4_mask,
            ip6=ip6,
            ip6_mask=ip6_mask,
            mac=mac
        )


class InterfaceData(object):
    """
    Convenience class for storing interface data.
    """

    def __init__(self, _id, name, mac, ip4, ip4_mask, ip6, ip6_mask):
        """
        Creates an InterfaceData object.

        :param int _id: interface id
        :param str name: name for interface
        :param core.misc.ipaddress.MacAddress mac: mac address
        :param str ip4: ipv4 address
        :param int ip4_mask: ipv4 bit mask
        :param str ip6: ipv6 address
        :param int ip6_mask: ipv6 bit mask
        """
        self.id = _id
        self.name = name
        self.mac = mac
        self.ip4 = ip4
        self.ip4_mask = ip4_mask
        self.ip6 = ip6
        self.ip6_mask = ip6_mask

    def has_ip4(self):
        return all([self.ip4, self.ip4_mask])

    def has_ip6(self):
        return all([self.ip6, self.ip6_mask])

    def ip4_address(self):
        if self.has_ip4():
            return "%s/%s" % (self.ip4, self.ip4_mask)
        else:
            return None

    def ip6_address(self):
        if self.has_ip6():
            return "%s/%s" % (self.ip6, self.ip6_mask)
        else:
            return None

    def get_addresses(self):
        ip4 = self.ip4_address()
        ip6 = self.ip6_address()
        return [i for i in [ip4, ip6] if i]
