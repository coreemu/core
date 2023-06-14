from core.api.grpc import client
from core.api.grpc.wrappers import Position, NodeType
from core.emane.models.ieee80211abg import EmaneIeee80211abgModel


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
    position = Position(x=375, y=500)
    emane_net = session.add_node(
        _id=1,
        _type=NodeType.EMANE,
        name="emane1",
        position=position,
        emane=EmaneIeee80211abgModel.name,
    )
    position = Position(x=250, y=250)
    node2 = session.add_node(_id=2, model="mdr", name="n2", position=position)
    node2.config_services.add("ChatApp Server")
    position = Position(x=500, y=250)
    node3 = session.add_node(_id=3, model="mdr", name="n3", position=position)

    # create links to emane
    node2_iface = iface_helper.create_iface(node_id=node2.id, iface_id=0)
    node2_iface.ip4 = "10.0.0.1"
    node2_iface.ip4_mask = 32
    node2_iface.ip6 = "2001::1"
    node2_iface.ip6_mask = 128
    session.add_link(node1=node2, node2=emane_net, iface1=node2_iface)
    node3_iface = iface_helper.create_iface(node_id=node3.id, iface_id=0)
    node3_iface.ip4 = "10.0.0.2"
    node3_iface.ip4_mask = 32
    node3_iface.ip6 = "2001::2"
    node3_iface.ip6_mask = 128
    session.add_link(node1=node3, node2=emane_net, iface1=node3_iface)

    # start session
    core.start_session(session=session)


if __name__ == "__main__":
    main()
