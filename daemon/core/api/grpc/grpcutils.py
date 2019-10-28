import asyncio
import logging
import time

from core.emulator.emudata import NodeOptions
from core.emulator.enumerations import NodeTypes


def add_node_data(node_proto):
    _id = node_proto.id
    _type = node_proto.type
    if _type is None:
        _type = NodeTypes.DEFAULT.value
    _type = NodeTypes(_type)

    options = NodeOptions(name=node_proto.name, model=node_proto.model)
    options.icon = node_proto.icon
    options.opaque = node_proto.opaque
    options.image = node_proto.image
    options.services = node_proto.services
    if node_proto.server:
        options.server = node_proto.server

    position = node_proto.position
    options.set_position(position.x, position.y)
    options.set_location(position.lat, position.lon, position.alt)
    return _type, _id, options


async def async_add_node(session, node_proto):
    _type, _id, options = add_node_data(node_proto)
    session.add_node(_type=_type, _id=_id, options=options)


async def create_nodes(loop, session, node_protos):
    tasks = []
    for node_proto in node_protos:
        task = loop.create_task(async_add_node(session, node_proto))
        tasks.append(task)

    start = time.monotonic()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total = time.monotonic() - start

    logging.info(f"created nodes time: {total}")
    return results


def sync_create_nodes(session, node_protos):
    start = time.monotonic()
    for node_proto in node_protos:
        _type, _id, options = add_node_data(node_proto)
        session.add_node(_type=_type, _id=_id, options=options)
    total = time.monotonic() - start
    logging.info(f"created nodes time: {total}")
