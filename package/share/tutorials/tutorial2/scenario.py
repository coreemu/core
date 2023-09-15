from core.api.grpc import client
from core.api.grpc.wrappers import NodeType, Position


def main():
    # interface helper
    iface_helper = client.InterfaceHelper(
        ip4_prefix="10.0.0.0/24", ip6_prefix="2001::/64"
    )

    # create grpc client and connect
    core = client.CoreGrpcClient()
    core.connect()

    # add session
    session = core.create_session()

    # create nodes
    position = Position(x=200, y=200)
    wlan = session.add_node(
        1, name="wlan1", _type=NodeType.WIRELESS_LAN, position=position
    )
    position = Position(x=100, y=100)
    node1 = session.add_node(2, name="n2", model="mdr", position=position)
    position = Position(x=300, y=100)
    node2 = session.add_node(3, name="n3", model="mdr", position=position)
    position = Position(x=500, y=100)
    node3 = session.add_node(4, name="n4", model="mdr", position=position)

    # create links
    iface1 = iface_helper.create_iface(node1.id, 0)
    session.add_link(node1=node1, node2=wlan, iface1=iface1)
    iface1 = iface_helper.create_iface(node2.id, 0)
    session.add_link(node1=node2, node2=wlan, iface1=iface1)
    iface1 = iface_helper.create_iface(node3.id, 0)
    session.add_link(node1=node3, node2=wlan, iface1=iface1)

    # start session
    core.start_session(session)


if __name__ == "__main__":
    main()
