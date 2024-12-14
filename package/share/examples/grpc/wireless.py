from core.api.grpc import client
from core.api.grpc.wrappers import NodeType, Position, Interface

# create grpc client and connect
core = client.CoreGrpcClient()
core.connect()

# add session
session = core.create_session()

# create nodes
position = Position(x=200, y=200)
wlan = session.add_node(1, _type=NodeType.WIRELESS, position=position)
position = Position(x=100, y=100)
node1 = session.add_node(2, model="mdr", position=position)
position = Position(x=300, y=100)
node2 = session.add_node(3, model="mdr", position=position)

# create links
iface1 = Interface(id=0, ip4="10.0.0.1", ip4_mask=24, ip6="2001::1", ip6_mask=128)
session.add_link(node1=node1, node2=wlan, iface1=iface1)
iface1 = Interface(id=0, ip4="10.0.0.2", ip4_mask=24, ip6="2001::2", ip6_mask=128)
session.add_link(node1=node2, node2=wlan, iface1=iface1)

# start session
core.start_session(session)
