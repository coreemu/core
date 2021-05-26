# required imports
from core.api.grpc import client
from core.api.grpc.wrappers import NodeType, Position
from core.emane.models.ieee80211abg import EmaneIeee80211abgModel

# interface helper
iface_helper = client.InterfaceHelper(ip4_prefix="10.0.0.0/24", ip6_prefix="2001::/64")

# create grpc client and connect
core = client.CoreGrpcClient()
core.connect()

# add session
session = core.create_session()

# create nodes
position = Position(x=200, y=200)
emane = session.add_node(
    1, _type=NodeType.EMANE, position=position, emane=EmaneIeee80211abgModel.name
)
position = Position(x=100, y=100)
node1 = session.add_node(2, model="mdr", position=position)
position = Position(x=300, y=100)
node2 = session.add_node(3, model="mdr", position=position)

# create links
iface1 = iface_helper.create_iface(node1.id, 0)
session.add_link(node1=node1, node2=emane, iface1=iface1)
iface1 = iface_helper.create_iface(node2.id, 0)
session.add_link(node1=node2, node2=emane, iface1=iface1)

# setup emane configurations using a dict mapping currently support values as strings
emane.set_emane_model(
    EmaneIeee80211abgModel.name, {"eventservicettl": "2", "unicastrate": "3"}
)

# start session
core.start_session(session)
