from core.api.grpc import client
from core.api.grpc.wrappers import Position


def main():
    # interface helper
    iface_helper = client.InterfaceHelper(
        ip4_prefix="10.0.0.0/24",
        ip6_prefix="2001::/64",
    )

    # create grpc client and connect
    core = client.CoreGrpcClient()
    core.connect()

    # create session
    session = core.create_session()

    # create nodes
    position = Position(x=250, y=250)
    node1 = session.add_node(_id=1, name="n1", position=position)
    position = Position(x=500, y=250)
    node2 = session.add_node(_id=2, name="n2", position=position)

    # create link
    node1_iface = iface_helper.create_iface(node_id=node1.id, iface_id=0)
    node1_iface.ip4 = "10.0.0.20"
    node1_iface.ip6 = "2001::14"
    node2_iface = iface_helper.create_iface(node_id=node2.id, iface_id=0)
    node2_iface.ip4 = "10.0.0.21"
    node2_iface.ip6 = "2001::15"
    session.add_link(node1=node1, node2=node2, iface1=node1_iface, iface2=node2_iface)

    # start session
    core.start_session(session=session)


if __name__ == "__main__":
    main()
