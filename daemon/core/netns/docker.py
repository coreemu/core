"""
DrBrNet that create docker briidge networks and then link to them using
Linux Ethernet bridging.
"""

from core import constants
from core import logger
from core.coreobj import PyCoreNet
from core.misc import ipaddress
from core.misc import utils
from core.netns.vnet import LxBrNet


class DrBrNet(LxBrNet):

    def __init__(self, session, objid=None, name=None, start=True, docker_name=None, subnet=None, gateway=None):
        """
        Creates a DrBrNet instance.

        :param core.session.Session session: core session instance
        :param int objid: object id
        :param str name: object name
        :param bool start: start flag
        :param str docker_name: docker network name uses name if not set
        :param str subnet: This gives the subnet to docker which will assign IPs to connecting containers
        :param str gateway: Docker sets this as the gateway to containers calculated from subnet if not given
        """
        if constants.DOCKER_BIN is None:
            raise ValueError("Docker needs to be installed.")
        # We skip the parent method and jump straight to the grandparent to avoid unwanted bridge creation.
        PyCoreNet.__init__(self, session, objid, name, start)
        if name is None:
            name = str(self.objid)
        self.name = name
        if docker_name is None:
            docker_name = name
        self.docker_name = docker_name

        # Lets check if a docker network exists with that name
        status, _ = utils.cmd_output([constants.DOCKER_BIN, "network", "inspect", self.docker_name])
        if status == 0:
            # The network already exists
            self.existing = True
        else:
            # Create the network
            create_cmd = [constants.DOCKER_BIN, "network", "create"]
            if subnet is not None:
                if gateway is None:
                    gateway = str(ipaddress.Ipv4Prefix(subnet).min_addr())
                create_cmd += ["--subnet", subnet, "--gateway", gateway]
            utils.check_cmd(create_cmd + [self.docker_name])
            self.existing = False
        if start:
            self.startup()

        self.brname = None

        # We find the actual bridge name by getting the gateway and matching it to the bridge
        # The bridge names are usually named by the br_<DOCKER iD> but can be set manually
        # through docker so this way should catch both.
        network_gateway = utils.check_cmd(["docker", "inspect", "-f", "'{{range .IPAM.Config}}{{.Gateway}}{{end}}'",
                                           self.docker_name])
        network_gateway = network_gateway.replace('\'', '')
        addresses = utils.check_cmd([constants.IP_BIN, "-br", "a"])
        for address in addresses.splitlines():
            if network_gateway in address:
                self.brname = address.split()[0]
                break

        if self.brname is None:
            raise ValueError("Failed to find the docker bridge name")

    def startup(self):
        """
        Docker network startup logic.

        :return: nothing
        """
        # TODO: Create the network here ?
        self.up = True

    def shutdown(self):
        """
        Docker network shutdown logic.

        :return: nothing
        """
        if not self.up:
            return

        if not self.existing:
            status, _ = utils.cmd_output([constants.DOCKER_BIN, "network", "rm", self.docker_name])
            if status <> 0:
                logger.warn("Could not remove network probably has containers attached.")

        # removes veth pairs used for bridge-to-bridge connections
        for netif in self.netifs():
            netif.shutdown()

        self._netif.clear()
        self._linked.clear()
        del self.session
        self.up = False
