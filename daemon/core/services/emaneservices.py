from core.emane.nodes import EmaneNet
from core.nodes.base import CoreNode
from core.services.coreservices import CoreService
from core.xml import emanexml


class EmaneTransportService(CoreService):
    name: str = "transportd"
    group: str = "EMANE"
    executables: tuple[str, ...] = ("emanetransportd", "emanegentransportxml")
    dependencies: tuple[str, ...] = ()
    dirs: tuple[str, ...] = ()
    configs: tuple[str, ...] = ("emanetransport.sh",)
    startup: tuple[str, ...] = (f"bash {configs[0]}",)
    validate: tuple[str, ...] = (f"pidof {executables[0]}",)
    validation_timer: float = 0.5
    shutdown: tuple[str, ...] = (f"killall {executables[0]}",)

    @classmethod
    def generate_config(cls, node: CoreNode, filename: str) -> str:
        emane_manager = node.session.emane
        cfg = ""
        for iface in node.get_ifaces():
            if not isinstance(iface.net, EmaneNet):
                continue
            emane_net = iface.net
            config = emane_manager.get_iface_config(emane_net, iface)
            if emanexml.is_external(config):
                nem_id = emane_manager.get_nem_id(iface)
                cfg += f"emanegentransportxml {iface.name}-platform.xml\n"
                cfg += f"emanetransportd -r -l 0 -d transportdaemon{nem_id}.xml\n"
        return cfg
