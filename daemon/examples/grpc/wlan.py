# required imports
from core.api.grpc import client
from core.api.grpc.core_pb2 import Node, NodeType, Position, SessionState

# interface helper
iface_helper = client.InterfaceHelper(ip4_prefix="10.0.0.0/24", ip6_prefix="2001::/64")

# create grpc client and connect
core = client.CoreGrpcClient()
core.connect()

# create session and get id
response = core.create_session()
session_id = response.session_id

# change session state to configuration so that nodes get started when added
core.set_session_state(session_id, SessionState.CONFIGURATION)

# create wlan node
position = Position(x=200, y=200)
wlan = Node(type=NodeType.WIRELESS_LAN, position=position)
response = core.add_node(session_id, wlan)
wlan_id = response.node_id

# create node one
position = Position(x=100, y=100)
n1 = Node(type=NodeType.DEFAULT, position=position, model="mdr")
response = core.add_node(session_id, n1)
n1_id = response.node_id

# create node two
position = Position(x=300, y=100)
n2 = Node(type=NodeType.DEFAULT, position=position, model="mdr")
response = core.add_node(session_id, n2)
n2_id = response.node_id

# configure wlan using a dict mapping currently
# support values as strings
core.set_wlan_config(
    session_id,
    wlan_id,
    {
        "range": "280",
        "bandwidth": "55000000",
        "delay": "6000",
        "jitter": "5",
        "error": "5",
    },
)

# links nodes to wlan
iface1 = iface_helper.create_iface(n1_id, 0)
core.add_link(session_id, n1_id, wlan_id, iface1)
iface1 = iface_helper.create_iface(n2_id, 0)
core.add_link(session_id, n2_id, wlan_id, iface1)

# change session state
core.set_session_state(session_id, SessionState.INSTANTIATION)
