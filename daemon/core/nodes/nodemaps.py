"""
Provides default node maps that can be used to run core with.
"""
import core.nodes.base
import core.nodes.docker
import core.nodes.network
import core.nodes.physical
from core.emane.nodes import EmaneNet
from core.emane.nodes import EmaneNode
from core.emulator.enumerations import NodeTypes
from core.nodes.network import GreTapBridge
from core.nodes import physical

# legacy core nodes, that leverage linux bridges
NODES = {
    NodeTypes.DEFAULT: core.nodes.base.CoreNode,
    NodeTypes.PHYSICAL: physical.PhysicalNode,
    NodeTypes.TBD: None,
    NodeTypes.SWITCH: core.nodes.network.SwitchNode,
    NodeTypes.HUB: core.nodes.network.HubNode,
    NodeTypes.WIRELESS_LAN: core.nodes.network.WlanNode,
    NodeTypes.RJ45: core.nodes.physical.Rj45Node,
    NodeTypes.TUNNEL: core.nodes.network.TunnelNode,
    NodeTypes.KTUNNEL: None,
    NodeTypes.EMANE: EmaneNode,
    NodeTypes.EMANE_NET: EmaneNet,
    NodeTypes.TAP_BRIDGE: GreTapBridge,
    NodeTypes.PEER_TO_PEER: core.nodes.network.PtpNet,
    NodeTypes.CONTROL_NET: core.nodes.network.CtrlNet,
    NodeTypes.DOCKER: core.nodes.docker.DockerNode
}
