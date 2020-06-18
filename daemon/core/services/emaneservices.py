from typing import Tuple

from core.emane.nodes import EmaneNet
from core.errors import CoreError
from core.nodes.base import CoreNode
from core.services.coreservices import CoreService
from core.xml import emanexml


class EmaneTransportService(CoreService):
    name: str = "transportd"
    group: str = "EMANE"
    executables: Tuple[str, ...] = ("emanetransportd", "emanegentransportxml")
    dependencies: Tuple[str, ...] = ()
    dirs: Tuple[str, ...] = ()
    configs: Tuple[str, ...] = ("emanetransport.sh",)
    startup: Tuple[str, ...] = ("sh %s" % configs[0],)
    validate: Tuple[str, ...] = ("pidof %s" % executables[0],)
    validation_timer: float = 0.5
    shutdown: Tuple[str, ...] = ("killall %s" % executables[0],)

    @classmethod
    def generate_config(cls, node: CoreNode, filename: str) -> str:
        if filename == cls.configs[0]:
            transport_commands = []
            for iface in node.get_ifaces():
                try:
                    network_node = node.session.get_node(iface.net.id, EmaneNet)
                    config = node.session.emane.get_configs(
                        network_node.id, network_node.model.name
                    )
                    if config and emanexml.is_external(config):
                        nem_id = network_node.getnemid(iface)
                        command = (
                            "emanetransportd -r -l 0 -d ../transportdaemon%s.xml"
                            % nem_id
                        )
                        transport_commands.append(command)
                except CoreError:
                    pass
            transport_commands = "\n".join(transport_commands)
            return """
emanegentransportxml -o ../ ../platform%s.xml
%s
""" % (
                node.id,
                transport_commands,
            )
        else:
            raise ValueError
