import sys

from core.api.grpc import client, wrappers
from core.api.grpc.wrappers import NodeType, Position


def main():
    if len(sys.argv) != 2:
        print("usage core-python scenario.py <interface-name>")
        exit()

    # interface helper
    iface_helper = client.InterfaceHelper(
        ip4_prefix="10.0.0.0/24",
        ip6_prefix="2001::/64",
    )

    # create grpc client and connect
    core = client.CoreGrpcClient()
    core.connect()

    # add session
    session = core.create_session()

    # create nodes
    position = Position(x=100, y=100)
    node1 = session.add_node(1, name="n1", position=position)
    position = Position(x=300, y=100)
    rj45 = session.add_node(2, name=sys.argv[1], _type=NodeType.RJ45, position=position)

    # create link
    iface1 = iface_helper.create_iface(node1.id, 0)
    iface1.ip4 = "10.0.0.20"
    iface1.ip6 = "2001::14"
    rj45_iface1 = wrappers.Interface(0)
    session.add_link(node1=node1, node2=rj45, iface1=iface1, iface2=rj45_iface1)

    # start session
    core.start_session(session)


if __name__ == "__main__":
    main()
