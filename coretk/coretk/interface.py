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
        return "02:00:00:%02x:%02x:%02x" % (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 225),
        )


class InterfaceManager:
    def __init__(self):
        self.addresses = list(ipaddress.ip_network("10.0.0.0/24").hosts())
        self.index = 0

    def get_address(self):
        """
        Retrieve a new ipv4 address

        :return:
        """
        i = self.index
        self.index = self.index + 1
        return self.addresses[i]
