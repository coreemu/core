from core.emane.nodes import EmaneNode
from core.services.coreservices import CoreService
from core.xml import emanexml


class EmaneTransportService(CoreService):
    name = "transportd"
    executables = ("emanetransportd", "emanegentransportxml")
    group = "EMANE"
    dependencies = ()
    dirs = ()
    configs = ("emanetransport.sh",)
    startup = ("sh %s" % configs[0],)
    validate = ("pidof %s" % executables[0],)
    validation_timer = 0.5
    shutdown = ("killall %s" % executables[0],)

    @classmethod
    def generate_config(cls, node, filename):
        if filename == cls.configs[0]:
            transport_commands = []
            for interface in node.netifs(sort=True):
                network_node = node.session.get_node(interface.net.id)
                if isinstance(network_node, EmaneNode):
                    config = node.session.emane.get_configs(
                        network_node.id, network_node.model.name
                    )
                    if config and emanexml.is_external(config):
                        nem_id = network_node.getnemid(interface)
                        command = (
                            "emanetransportd -r -l 0 -d ../transportdaemon%s.xml"
                            % nem_id
                        )
                        transport_commands.append(command)
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
