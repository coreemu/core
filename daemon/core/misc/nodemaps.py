"""
Provides default node maps that can be used to run core with.
"""

from core.emane.nodes import EmaneNet
from core.emane.nodes import EmaneNode
from core.enumerations import NodeTypes
from core.netns import nodes
from core.netns.vnet import GreTapBridge
from core.phys import pnodes

# legacy core nodes, that leverage linux bridges
NODES = {
    NodeTypes.DEFAULT: nodes.CoreNode,
    NodeTypes.PHYSICAL: pnodes.PhysicalNode,
    NodeTypes.TBD: None,
    NodeTypes.SWITCH: nodes.SwitchNode,
    NodeTypes.HUB: nodes.HubNode,
    NodeTypes.WIRELESS_LAN: nodes.WlanNode,
    NodeTypes.RJ45: nodes.RJ45Node,
    NodeTypes.TUNNEL: nodes.TunnelNode,
    NodeTypes.KTUNNEL: None,
    NodeTypes.EMANE: EmaneNode,
    NodeTypes.EMANE_NET: EmaneNet,
    NodeTypes.TAP_BRIDGE: GreTapBridge,
    NodeTypes.PEER_TO_PEER: nodes.PtpNet,
    NodeTypes.CONTROL_NET: nodes.CtrlNet
}
