import os
import time

import pytest

from core.grpc import core_pb2
from core.enumerations import NodeTypes, EventTypes
from core.grpc.client import CoreGrpcClient

MODELS = [
    "router",
    "host",
    "PC",
    "mdr",
]

NET_TYPES = [
    NodeTypes.SWITCH,
    NodeTypes.HUB,
    NodeTypes.WIRELESS_LAN
]


class TestGrpc:
    @pytest.mark.parametrize("session_id", [None, 6013])
    def test_create_session(self, grpc_server, session_id):
        # given
        client = CoreGrpcClient()

        # when
        with client.context_connect():
            response = client.create_session(session_id)

        # then
        assert isinstance(response.id, int)
        assert isinstance(response.state, int)
        session = grpc_server.coreemu.sessions.get(response.id)
        assert session is not None
        assert session.state == response.state
        if session_id is not None:
            assert response.id == session_id
            assert session.session_id == session_id

    def test_delete_session(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.delete_session(session.session_id)

        # then
        assert response.result is True
        assert grpc_server.coreemu.sessions.get(session.session_id) is None

    def test_get_session(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()
        session.add_node()
        session.set_state(EventTypes.DEFINITION_STATE)

        # then
        with client.context_connect():
            response = client.get_session(session.session_id)

        # then
        assert response.session.state == core_pb2.DEFINITION
        assert len(response.session.nodes) == 1
        assert len(response.session.links) == 0

    def test_get_sessions(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.get_sessions()

        # then
        found_session = None
        for current_session in response.sessions:
            if current_session.id == session.session_id:
                found_session = current_session
                break
        assert len(response.sessions) == 1
        assert found_session is not None

    def test_get_session_options(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.get_session_options(session.session_id)

        # then
        assert len(response.groups) > 0

    def test_get_session_location(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.get_session_location(session.session_id)

        # then
        assert response.scale == 1.0
        assert response.position.x == 0
        assert response.position.y == 0
        assert response.position.z == 0
        assert response.position.lat == 0
        assert response.position.lon == 0
        assert response.position.alt == 0

    def test_set_session_location(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        scale = 2
        xyz = (1, 1, 1)
        lat_lon_alt = (1, 1, 1)
        with client.context_connect():
            response = client.set_session_location(
                session.session_id,
                x=xyz[0], y=xyz[1], z=xyz[2],
                lat=lat_lon_alt[0], lon=lat_lon_alt[1], alt=lat_lon_alt[2],
                scale=scale
            )

        # then
        assert response.result is True
        assert session.location.refxyz == xyz
        assert session.location.refscale == scale
        assert session.location.refgeo == lat_lon_alt

    def test_set_session_options(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        option = "enablerj45"
        value = "1"
        with client.context_connect():
            response = client.set_session_options(session.session_id, {option: value})

        # then
        assert response.result is True
        assert session.options.get_config(option) == value

    def test_set_session_state(self, grpc_server):
        # given
        client = CoreGrpcClient()
        session = grpc_server.coreemu.create_session()

        # then
        with client.context_connect():
            response = client.set_session_state(session.session_id, EventTypes.DEFINITION_STATE)

        # then
        assert response.result is True
        assert session.state == EventTypes.DEFINITION_STATE.value
