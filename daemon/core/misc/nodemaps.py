from core.emane.nodes import EmaneNet
from core.emane.nodes import EmaneNode
from core.enumerations import NodeTypes
from core.netns import nodes
from core.netns import openvswitch
from core.netns.vnet import GreTapBridge
from core.phys import pnodes
from core.xen import xen

CLASSIC_NODES = {
    NodeTypes.DEFAULT: nodes.CoreNode,
    NodeTypes.PHYSICAL: pnodes.PhysicalNode,
    NodeTypes.XEN: xen.XenNode,
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

OVS_NODES = {
    NodeTypes.DEFAULT: nodes.CoreNode,
    NodeTypes.PHYSICAL: pnodes.PhysicalNode,
    NodeTypes.XEN: xen.XenNode,
    NodeTypes.TBD: None,
    NodeTypes.SWITCH: openvswitch.OvsSwitchNode,
    NodeTypes.HUB: openvswitch.OvsHubNode,
    NodeTypes.WIRELESS_LAN: openvswitch.OvsWlanNode,
    NodeTypes.RJ45: nodes.RJ45Node,
    NodeTypes.TUNNEL: openvswitch.OvsTunnelNode,
    NodeTypes.KTUNNEL: None,
    NodeTypes.EMANE: EmaneNode,
    NodeTypes.EMANE_NET: EmaneNet,
    NodeTypes.TAP_BRIDGE: openvswitch.OvsGreTapBridge,
    NodeTypes.PEER_TO_PEER: openvswitch.OvsPtpNet,
    NodeTypes.CONTROL_NET: openvswitch.OvsCtrlNet
}
