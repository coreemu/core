import ipaddress
import random


class Interface:
    def __init__(self, name, ipv4, ifid=None):
        """
        Create an interface instance

        :param str name: interface name
        :param str ip4: IPv4
        :param str mac: MAC address
        :param int ifid: interface id
        """
        self.name = name
        self.ipv4 = ipv4
        self.ip4prefix = 24
        self.ip4_and_prefix = ipv4 + "/" + str(self.ip4prefix)
        self.mac = self.random_mac_address()
        self.id = ifid

    def random_mac_address(self):
        """
        create a random MAC address for an interface

        :return: nothing
        """
        return "02:00:00:%02x:%02x:%02x" % (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 225),
        )


class SubnetAddresses:
    def __init__(self, network, addresses):
        self.network = network
        self.address = addresses
        self.address_index = 0

    def get_new_ip_address(self):
        ipaddr = self.address[self.address_index]
        self.address_index = self.address_index + 1
        return ipaddr


class InterfaceManager:
    def __init__(self):
        # self.prefix = None
        self.core_subnets = list(
            ipaddress.ip_network("10.0.0.0/12").subnets(prefixlen_diff=12)
        )
        self.subnet_index = 0
        self.address_index = 0

        # self.network = ipaddress.ip_network("10.0.0.0/24")
        # self.addresses = list(self.network.hosts())
        self.network = None
        self.addresses = None
        # self.start_interface_manager()

    def start_interface_manager(self):
        self.subnet_index = 0
        self.network = self.core_subnets[self.subnet_index]
        self.subnet_index = self.subnet_index + 1
        self.addresses = list(self.network.hosts())
        self.address_index = 0

    def get_address(self):
        """
        Retrieve a new ipv4 address

        :return:
        """
        # i = self.index
        # self.address_index = self.index + 1
        # return self.addresses[i]
        ipaddr = self.addresses[self.address_index]
        self.address_index = self.address_index + 1
        return ipaddr

    def new_subnet(self):
        self.network = self.core_subnets[self.subnet_index]
        # self.subnet_index = self.subnet_index + 1
        self.addresses = list(self.network.hosts())
        # self.address_index = 0

    # def new_subnet(self):
    #     """
    #     retrieve a new subnet
    #     :return:
    #     """
    #     if self.prefix is None:
    #         self.prefix =
    #         self.addresses = list(ipaddress.ip_network("10.0.0.0/24").hosts())
