import ipaddress


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
        self.core_subnets = list(
            ipaddress.ip_network("10.0.0.0/12").subnets(prefixlen_diff=12)
        )
        self.subnet_index = 0
        self.address_index = 0
        self.network = None
        self.addresses = None

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
        ipaddr = self.addresses[self.address_index]
        self.address_index = self.address_index + 1
        return ipaddr

    def new_subnet(self):
        self.network = self.core_subnets[self.subnet_index]
        self.addresses = list(self.network.hosts())
