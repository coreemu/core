import os
import time

import pytest

from core.grpc import core_pb2
from core.enumerations import NodeTypes
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
    def test_create_session(self, grpc_server):
        # given
        client = CoreGrpcClient()

        # when
        with client.context_connect():
            response = client.create_session()

        # then
        assert isinstance(response.id, int)
        assert isinstance(response.state, int)
        session = grpc_server.coreemu.sessions.get(response.id)
        assert session is not None
        assert session.state == response.state

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
