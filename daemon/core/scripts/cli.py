import json
import sys
from argparse import (
    ArgumentDefaultsHelpFormatter,
    ArgumentParser,
    ArgumentTypeError,
    Namespace,
)
from functools import wraps
from pathlib import Path
from typing import Any, Optional

import grpc
import netaddr
from google.protobuf.json_format import MessageToDict
from netaddr import EUI, AddrFormatError, IPNetwork

from core.api.grpc.client import CoreGrpcClient
from core.api.grpc.wrappers import (
    ConfigOption,
    Geo,
    Interface,
    Link,
    LinkOptions,
    Node,
    NodeType,
    Position,
)

NODE_TYPES = [x.name for x in NodeType if x != NodeType.PEER_TO_PEER]


def protobuf_to_json(message: Any) -> dict[str, Any]:
    return MessageToDict(
        message, including_default_value_fields=True, preserving_proto_field_name=True
    )


def print_json(data: Any) -> None:
    data = json.dumps(data, indent=2)
    print(data)


def coreclient(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        core = CoreGrpcClient()
        try:
            with core.context_connect():
                return func(core, *args, **kwargs)
        except grpc.RpcError as e:
            print(f"grpc error: {e.details()}")

    return wrapper


def mac_type(value: str) -> str:
    try:
        mac = EUI(value, dialect=netaddr.mac_unix_expanded)
        return str(mac)
    except AddrFormatError:
        raise ArgumentTypeError(f"invalid mac address: {value}")


def ip4_type(value: str) -> IPNetwork:
    try:
        ip = IPNetwork(value)
        if not netaddr.valid_ipv4(str(ip.ip)):
            raise ArgumentTypeError(f"invalid ip4 address: {value}")
        return ip
    except AddrFormatError:
        raise ArgumentTypeError(f"invalid ip4 address: {value}")


def ip6_type(value: str) -> IPNetwork:
    try:
        ip = IPNetwork(value)
        if not netaddr.valid_ipv6(str(ip.ip)):
            raise ArgumentTypeError(f"invalid ip6 address: {value}")
        return ip
    except AddrFormatError:
        raise ArgumentTypeError(f"invalid ip6 address: {value}")


def position_type(value: str) -> tuple[float, float]:
    error = "invalid position, must be in the format: float,float"
    try:
        values = [float(x) for x in value.split(",")]
    except ValueError:
        raise ArgumentTypeError(error)
    if len(values) != 2:
        raise ArgumentTypeError(error)
    x, y = values
    return x, y


def geo_type(value: str) -> tuple[float, float, float]:
    error = "invalid geo, must be in the format: float,float,float"
    try:
        values = [float(x) for x in value.split(",")]
    except ValueError:
        raise ArgumentTypeError(error)
    if len(values) != 3:
        raise ArgumentTypeError(error)
    lon, lat, alt = values
    return lon, lat, alt


def file_type(value: str) -> Path:
    path = Path(value)
    if not path.is_file():
        raise ArgumentTypeError(f"invalid file: {value}")
    return path


def get_current_session(core: CoreGrpcClient, session_id: Optional[int]) -> int:
    if session_id:
        return session_id
    sessions = core.get_sessions()
    if not sessions:
        print("no current session to interact with")
        sys.exit(1)
    return sessions[0].id


def create_iface(
    iface_id: int, mac: str, ip4_net: IPNetwork, ip6_net: IPNetwork
) -> Interface:
    ip4 = str(ip4_net.ip) if ip4_net else None
    ip4_mask = ip4_net.prefixlen if ip4_net else None
    ip6 = str(ip6_net.ip) if ip6_net else None
    ip6_mask = ip6_net.prefixlen if ip6_net else None
    return Interface(
        id=iface_id, mac=mac, ip4=ip4, ip4_mask=ip4_mask, ip6=ip6, ip6_mask=ip6_mask
    )


def print_iface_header() -> None:
    print("ID  | MAC Address       | IP4 Address        | IP6 Address")


def print_iface(iface: Interface) -> None:
    iface_ip4 = f"{iface.ip4}/{iface.ip4_mask}" if iface.ip4 else ""
    iface_ip6 = f"{iface.ip6}/{iface.ip6_mask}" if iface.ip6 else ""
    print(f"{iface.id:<3} | {iface.mac:<17} | {iface_ip4:<18} | {iface_ip6}")


@coreclient
def get_wlan_config(core: CoreGrpcClient, args: Namespace) -> None:
    session_id = get_current_session(core, args.session)
    config = core.get_wlan_config(session_id, args.node)
    if args.json:
        print_json(ConfigOption.to_dict(config))
    else:
        size = 0
        for option in config.values():
            size = max(size, len(option.name))
        print(f"{'Name':<{size}.{size}} | Value")
        for option in config.values():
            print(f"{option.name:<{size}.{size}} | {option.value}")


@coreclient
def set_wlan_config(core: CoreGrpcClient, args: Namespace) -> None:
    session_id = get_current_session(core, args.session)
    config = {}
    if args.bandwidth:
        config["bandwidth"] = str(args.bandwidth)
    if args.delay:
        config["delay"] = str(args.delay)
    if args.loss:
        config["error"] = str(args.loss)
    if args.jitter:
        config["jitter"] = str(args.jitter)
    if args.range:
        config["range"] = str(args.range)
    result = core.set_wlan_config(session_id, args.node, config)
    if args.json:
        print_json(dict(result=result))
    else:
        print(f"set wlan config: {result}")


@coreclient
def open_xml(core: CoreGrpcClient, args: Namespace) -> None:
    result, session_id = core.open_xml(args.file, args.start)
    if args.json:
        print_json(dict(result=result, session_id=session_id))
    else:
        print(f"opened xml: {result},{session_id}")


@coreclient
def query_sessions(core: CoreGrpcClient, args: Namespace) -> None:
    sessions = core.get_sessions()
    if args.json:
        sessions = [protobuf_to_json(x.to_proto()) for x in sessions]
        print_json(sessions)
    else:
        print("Session ID | Session State | Nodes")
        for session in sessions:
            print(f"{session.id:<10} | {session.state.name:<13} | {session.nodes}")


@coreclient
def query_session(core: CoreGrpcClient, args: Namespace) -> None:
    session = core.get_session(args.id)
    if args.json:
        session = protobuf_to_json(session.to_proto())
        print_json(session)
    else:
        print("Nodes")
        print("ID      | Name    | Type    | XY        | Geo")
        for node in session.nodes.values():
            xy_pos = f"{int(node.position.x)},{int(node.position.y)}"
            geo_pos = f"{node.geo.lon:.7f},{node.geo.lat:.7f},{node.geo.alt:f}"
            print(
                f"{node.id:<7} | {node.name[:7]:<7} | {node.type.name[:7]:<7} | {xy_pos:<9} | {geo_pos}"
            )
        print("\nLinks")
        for link in session.links:
            n1 = session.nodes[link.node1_id].name
            n2 = session.nodes[link.node2_id].name
            print("Node   | ", end="")
            print_iface_header()
            print(f"{n1:<6} | ", end="")
            if link.iface1:
                print_iface(link.iface1)
            else:
                print()
            print(f"{n2:<6} | ", end="")
            if link.iface2:
                print_iface(link.iface2)
            else:
                print()
            print()


@coreclient
def query_node(core: CoreGrpcClient, args: Namespace) -> None:
    session = core.get_session(args.id)
    node, ifaces, _ = core.get_node(args.id, args.node)
    if args.json:
        node = protobuf_to_json(node.to_proto())
        ifaces = [protobuf_to_json(x.to_proto()) for x in ifaces]
        print_json(dict(node=node, ifaces=ifaces))
    else:
        print("ID      | Name    | Type    | XY        | Geo")
        xy_pos = f"{int(node.position.x)},{int(node.position.y)}"
        geo_pos = f"{node.geo.lon:.7f},{node.geo.lat:.7f},{node.geo.alt:f}"
        print(
            f"{node.id:<7} | {node.name[:7]:<7} | {node.type.name[:7]:<7} | {xy_pos:<9} | {geo_pos}"
        )
        if ifaces:
            print("Interfaces")
            print("Connected To | ", end="")
            print_iface_header()
            for iface in ifaces:
                if iface.net_id == node.id:
                    if iface.node_id:
                        name = session.nodes[iface.node_id].name
                    else:
                        name = session.nodes[iface.net2_id].name
                else:
                    net_node = session.nodes.get(iface.net_id)
                    name = net_node.name if net_node else ""
                print(f"{name:<12} | ", end="")
                print_iface(iface)


@coreclient
def delete_session(core: CoreGrpcClient, args: Namespace) -> None:
    result = core.delete_session(args.id)
    if args.json:
        print_json(dict(result=result))
    else:
        print(f"delete session({args.id}): {result}")


@coreclient
def add_node(core: CoreGrpcClient, args: Namespace) -> None:
    session_id = get_current_session(core, args.session)
    node_type = NodeType[args.type]
    pos = None
    if args.pos:
        x, y = args.pos
        pos = Position(x=x, y=y)
    geo = None
    if args.geo:
        lon, lat, alt = args.geo
        geo = Geo(lon=lon, lat=lat, alt=alt)
    node = Node(
        id=args.id,
        name=args.name,
        type=node_type,
        model=args.model,
        emane=args.emane,
        icon=args.icon,
        image=args.image,
        position=pos,
        geo=geo,
    )
    node_id = core.add_node(session_id, node)
    if args.json:
        print_json(dict(node_id=node_id))
    else:
        print(f"created node: {node_id}")


@coreclient
def edit_node(core: CoreGrpcClient, args: Namespace) -> None:
    session_id = get_current_session(core, args.session)
    result = core.edit_node(session_id, args.id, args.icon)
    if args.json:
        print_json(dict(result=result))
    else:
        print(f"edit node: {result}")


@coreclient
def move_node(core: CoreGrpcClient, args: Namespace) -> None:
    session_id = get_current_session(core, args.session)
    pos = None
    if args.pos:
        x, y = args.pos
        pos = Position(x=x, y=y)
    geo = None
    if args.geo:
        lon, lat, alt = args.geo
        geo = Geo(lon=lon, lat=lat, alt=alt)
    result = core.move_node(session_id, args.id, pos, geo)
    if args.json:
        print_json(dict(result=result))
    else:
        print(f"move node: {result}")


@coreclient
def delete_node(core: CoreGrpcClient, args: Namespace) -> None:
    session_id = get_current_session(core, args.session)
    result = core.delete_node(session_id, args.id)
    if args.json:
        print_json(dict(result=result))
    else:
        print(f"deleted node: {result}")


@coreclient
def add_link(core: CoreGrpcClient, args: Namespace) -> None:
    session_id = get_current_session(core, args.session)
    iface1 = None
    if args.iface1_id is not None:
        iface1 = create_iface(
            args.iface1_id, args.iface1_mac, args.iface1_ip4, args.iface1_ip6
        )
    iface2 = None
    if args.iface2_id is not None:
        iface2 = create_iface(
            args.iface2_id, args.iface2_mac, args.iface2_ip4, args.iface2_ip6
        )
    options = LinkOptions(
        bandwidth=args.bandwidth,
        loss=args.loss,
        jitter=args.jitter,
        delay=args.delay,
        dup=args.duplicate,
        unidirectional=args.uni,
    )
    link = Link(args.node1, args.node2, iface1=iface1, iface2=iface2, options=options)
    result, iface1, iface2 = core.add_link(session_id, link)
    if args.json:
        iface1 = protobuf_to_json(iface1.to_proto())
        iface2 = protobuf_to_json(iface2.to_proto())
        print_json(dict(result=result, iface1=iface1, iface2=iface2))
    else:
        print(f"add link: {result}")


@coreclient
def edit_link(core: CoreGrpcClient, args: Namespace) -> None:
    session_id = get_current_session(core, args.session)
    options = LinkOptions(
        bandwidth=args.bandwidth,
        loss=args.loss,
        jitter=args.jitter,
        delay=args.delay,
        dup=args.duplicate,
        unidirectional=args.uni,
    )
    iface1 = Interface(args.iface1)
    iface2 = Interface(args.iface2)
    link = Link(args.node1, args.node2, iface1=iface1, iface2=iface2, options=options)
    result = core.edit_link(session_id, link)
    if args.json:
        print_json(dict(result=result))
    else:
        print(f"edit link: {result}")


@coreclient
def delete_link(core: CoreGrpcClient, args: Namespace) -> None:
    session_id = get_current_session(core, args.session)
    iface1 = Interface(args.iface1)
    iface2 = Interface(args.iface2)
    link = Link(args.node1, args.node2, iface1=iface1, iface2=iface2)
    result = core.delete_link(session_id, link)
    if args.json:
        print_json(dict(result=result))
    else:
        print(f"delete link: {result}")


def setup_sessions_parser(parent) -> None:
    parser = parent.add_parser("session", help="session interactions")
    parser.formatter_class = ArgumentDefaultsHelpFormatter
    parser.add_argument("-i", "--id", type=int, help="session id to use", required=True)
    subparsers = parser.add_subparsers(help="session commands")
    subparsers.required = True
    subparsers.dest = "command"

    delete_parser = subparsers.add_parser("delete", help="delete a session")
    delete_parser.formatter_class = ArgumentDefaultsHelpFormatter
    delete_parser.set_defaults(func=delete_session)


def setup_node_parser(parent) -> None:
    parser = parent.add_parser("node", help="node interactions")
    parser.formatter_class = ArgumentDefaultsHelpFormatter
    parser.add_argument("-s", "--session", type=int, help="session to interact with")
    subparsers = parser.add_subparsers(help="node commands")
    subparsers.required = True
    subparsers.dest = "command"

    add_parser = subparsers.add_parser("add", help="add a node")
    add_parser.formatter_class = ArgumentDefaultsHelpFormatter
    add_parser.add_argument("-i", "--id", type=int, help="id to use, optional")
    add_parser.add_argument("-n", "--name", help="name to use, optional")
    add_parser.add_argument(
        "-t", "--type", choices=NODE_TYPES, default="DEFAULT", help="type of node"
    )
    add_parser.add_argument(
        "-m", "--model", help="used to determine services, optional"
    )
    group = add_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-p", "--pos", type=position_type, help="x,y position")
    group.add_argument("-g", "--geo", type=geo_type, help="lon,lat,alt position")
    add_parser.add_argument("-ic", "--icon", help="icon to use, optional")
    add_parser.add_argument("-im", "--image", help="container image, optional")
    add_parser.add_argument(
        "-e", "--emane", help="emane model, only required for emane nodes"
    )
    add_parser.set_defaults(func=add_node)

    edit_parser = subparsers.add_parser("edit", help="edit a node")
    edit_parser.formatter_class = ArgumentDefaultsHelpFormatter
    edit_parser.add_argument("-i", "--id", type=int, help="id to use", required=True)
    edit_parser.add_argument("-ic", "--icon", help="icon to use, optional")
    edit_parser.set_defaults(func=edit_node)

    move_parser = subparsers.add_parser("move", help="move a node")
    move_parser.formatter_class = ArgumentDefaultsHelpFormatter
    move_parser.add_argument(
        "-i", "--id", type=int, help="id to use, optional", required=True
    )
    group = move_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-p", "--pos", type=position_type, help="x,y position")
    group.add_argument("-g", "--geo", type=geo_type, help="lon,lat,alt position")
    move_parser.set_defaults(func=move_node)

    delete_parser = subparsers.add_parser("delete", help="delete a node")
    delete_parser.formatter_class = ArgumentDefaultsHelpFormatter
    delete_parser.add_argument("-i", "--id", type=int, help="node id", required=True)
    delete_parser.set_defaults(func=delete_node)


def setup_link_parser(parent) -> None:
    parser = parent.add_parser("link", help="link interactions")
    parser.formatter_class = ArgumentDefaultsHelpFormatter
    parser.add_argument("-s", "--session", type=int, help="session to interact with")
    subparsers = parser.add_subparsers(help="link commands")
    subparsers.required = True
    subparsers.dest = "command"

    add_parser = subparsers.add_parser("add", help="add a node")
    add_parser.formatter_class = ArgumentDefaultsHelpFormatter
    add_parser.add_argument("-n1", "--node1", type=int, help="node1 id", required=True)
    add_parser.add_argument("-n2", "--node2", type=int, help="node2 id", required=True)
    add_parser.add_argument("-i1-i", "--iface1-id", type=int, help="node1 interface id")
    add_parser.add_argument(
        "-i1-m", "--iface1-mac", type=mac_type, help="node1 interface mac"
    )
    add_parser.add_argument(
        "-i1-4", "--iface1-ip4", type=ip4_type, help="node1 interface ip4"
    )
    add_parser.add_argument(
        "-i1-6", "--iface1-ip6", type=ip6_type, help="node1 interface ip6"
    )
    add_parser.add_argument("-i2-i", "--iface2-id", type=int, help="node2 interface id")
    add_parser.add_argument(
        "-i2-m", "--iface2-mac", type=mac_type, help="node2 interface mac"
    )
    add_parser.add_argument(
        "-i2-4", "--iface2-ip4", type=ip4_type, help="node2 interface ip4"
    )
    add_parser.add_argument(
        "-i2-6", "--iface2-ip6", type=ip6_type, help="node2 interface ip6"
    )
    add_parser.add_argument("-b", "--bandwidth", type=int, help="bandwidth (bps)")
    add_parser.add_argument("-l", "--loss", type=float, help="loss (%%)")
    add_parser.add_argument("-j", "--jitter", type=int, help="jitter (us)")
    add_parser.add_argument("-de", "--delay", type=int, help="delay (us)")
    add_parser.add_argument("-du", "--duplicate", type=int, help="duplicate (%%)")
    add_parser.add_argument(
        "-u", "--uni", action="store_true", help="is link unidirectional?"
    )
    add_parser.set_defaults(func=add_link)

    edit_parser = subparsers.add_parser("edit", help="edit a link")
    edit_parser.formatter_class = ArgumentDefaultsHelpFormatter
    edit_parser.add_argument("-n1", "--node1", type=int, help="node1 id", required=True)
    edit_parser.add_argument("-n2", "--node2", type=int, help="node2 id", required=True)
    edit_parser.add_argument("-i1", "--iface1", type=int, help="node1 interface id")
    edit_parser.add_argument("-i2", "--iface2", type=int, help="node2 interface id")
    edit_parser.add_argument("-b", "--bandwidth", type=int, help="bandwidth (bps)")
    edit_parser.add_argument("-l", "--loss", type=float, help="loss (%%)")
    edit_parser.add_argument("-j", "--jitter", type=int, help="jitter (us)")
    edit_parser.add_argument("-de", "--delay", type=int, help="delay (us)")
    edit_parser.add_argument("-du", "--duplicate", type=int, help="duplicate (%%)")
    edit_parser.add_argument(
        "-u", "--uni", action="store_true", help="is link unidirectional?"
    )
    edit_parser.set_defaults(func=edit_link)

    delete_parser = subparsers.add_parser("delete", help="delete a link")
    delete_parser.formatter_class = ArgumentDefaultsHelpFormatter
    delete_parser.add_argument(
        "-n1", "--node1", type=int, help="node1 id", required=True
    )
    delete_parser.add_argument(
        "-n2", "--node2", type=int, help="node1 id", required=True
    )
    delete_parser.add_argument("-i1", "--iface1", type=int, help="node1 interface id")
    delete_parser.add_argument("-i2", "--iface2", type=int, help="node2 interface id")
    delete_parser.set_defaults(func=delete_link)


def setup_query_parser(parent) -> None:
    parser = parent.add_parser("query", help="query interactions")
    subparsers = parser.add_subparsers(help="query commands")
    subparsers.required = True
    subparsers.dest = "command"

    sessions_parser = subparsers.add_parser("sessions", help="query current sessions")
    sessions_parser.formatter_class = ArgumentDefaultsHelpFormatter
    sessions_parser.set_defaults(func=query_sessions)

    session_parser = subparsers.add_parser("session", help="query session")
    session_parser.formatter_class = ArgumentDefaultsHelpFormatter
    session_parser.add_argument(
        "-i", "--id", type=int, help="session to query", required=True
    )
    session_parser.set_defaults(func=query_session)

    node_parser = subparsers.add_parser("node", help="query node")
    node_parser.formatter_class = ArgumentDefaultsHelpFormatter
    node_parser.add_argument(
        "-i", "--id", type=int, help="session to query", required=True
    )
    node_parser.add_argument(
        "-n", "--node", type=int, help="node to query", required=True
    )
    node_parser.set_defaults(func=query_node)


def setup_xml_parser(parent) -> None:
    parser = parent.add_parser("xml", help="open session xml")
    parser.formatter_class = ArgumentDefaultsHelpFormatter
    parser.add_argument(
        "-f", "--file", type=file_type, help="xml file to open", required=True
    )
    parser.add_argument("-s", "--start", action="store_true", help="start the session?")
    parser.set_defaults(func=open_xml)


def setup_wlan_parser(parent) -> None:
    parser = parent.add_parser("wlan", help="wlan specific interactions")
    parser.formatter_class = ArgumentDefaultsHelpFormatter
    parser.add_argument("-s", "--session", type=int, help="session to interact with")
    subparsers = parser.add_subparsers(help="link commands")
    subparsers.required = True
    subparsers.dest = "command"

    get_parser = subparsers.add_parser("get", help="get wlan configuration")
    get_parser.formatter_class = ArgumentDefaultsHelpFormatter
    get_parser.add_argument("-n", "--node", type=int, help="wlan node", required=True)
    get_parser.set_defaults(func=get_wlan_config)

    set_parser = subparsers.add_parser("set", help="set wlan configuration")
    set_parser.formatter_class = ArgumentDefaultsHelpFormatter
    set_parser.add_argument("-n", "--node", type=int, help="wlan node", required=True)
    set_parser.add_argument("-b", "--bandwidth", type=int, help="bandwidth (bps)")
    set_parser.add_argument("-d", "--delay", type=int, help="delay (us)")
    set_parser.add_argument("-l", "--loss", type=float, help="loss (%%)")
    set_parser.add_argument("-j", "--jitter", type=int, help="jitter (us)")
    set_parser.add_argument("-r", "--range", type=int, help="range (pixels)")
    set_parser.set_defaults(func=set_wlan_config)


def main() -> None:
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "-js", "--json", action="store_true", help="print responses to terminal as json"
    )
    subparsers = parser.add_subparsers(help="supported commands")
    subparsers.required = True
    subparsers.dest = "command"
    setup_sessions_parser(subparsers)
    setup_node_parser(subparsers)
    setup_link_parser(subparsers)
    setup_query_parser(subparsers)
    setup_xml_parser(subparsers)
    setup_wlan_parser(subparsers)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
