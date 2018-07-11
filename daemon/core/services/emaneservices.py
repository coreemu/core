from core.enumerations import NodeTypes
from core.misc import nodeutils
from core.service import CoreService
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
                network_node = node.session.get_object(interface.net.objid)
                if nodeutils.is_node(network_node, NodeTypes.EMANE):
                    if not node.session.emane.has_configs(network_node.objid):
                        continue
                    all_configs = node.session.emane.get_all_configs(network_node.objid)
                    config = all_configs.get(network_node.model.name)
                    if emanexml.is_external(config):
                        nem_id = network_node.getnemid(interface)
                        command = "emanetransportd -r -l 0 -d ../transportdaemon%s.xml" % nem_id
                        transport_commands.append(command)
            transport_commands = "\n".join(transport_commands)
            return """
emanegentransportxml -o ../ ../platform%s.xml
%s
""" % (node.objid, transport_commands)
        else:
            raise ValueError
