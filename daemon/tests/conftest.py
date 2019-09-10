"""
Unit test fixture module.
"""

import os
import threading
import time

import pytest
from core.api.grpc.client import InterfaceHelper
from core.api.grpc.server import CoreGrpcServer
from core.api.tlv.coreapi import CoreConfMessage, CoreEventMessage
from core.api.tlv.corehandlers import CoreHandler
from core.api.tlv.coreserver import CoreServer
from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes
from core.emulator.enumerations import CORE_API_PORT, ConfigTlvs, EventTlvs, EventTypes
from core.nodes import ipaddress
from core.services.coreservices import ServiceManager
from mock.mock import MagicMock

EMANE_SERVICES = "zebra|OSPFv3MDR|IPForward"


class CoreServerTest(object):
    def __init__(self, port=CORE_API_PORT):
        self.host = "localhost"
        self.port = port
        address = (self.host, self.port)
        self.server = CoreServer(
            address, CoreHandler, {"numthreads": 1, "daemonize": False}
        )

        self.distributed_server = "core2"
        self.prefix = ipaddress.Ipv4Prefix("10.83.0.0/16")
        self.session = None
        self.request_handler = None

    def setup_handler(self):
        self.session = self.server.coreemu.create_session(1)
        request_mock = MagicMock()
        request_mock.fileno = MagicMock(return_value=1)
        self.request_handler = CoreHandler(request_mock, "", self.server)
        self.request_handler.session = self.session
        self.request_handler.add_session_handlers()

    def setup(self, distributed_address):
        # validate address
        assert distributed_address, "distributed server address was not provided"

        # create session
        self.session = self.server.coreemu.create_session(1)

        # create request handler
        request_mock = MagicMock()
        request_mock.fileno = MagicMock(return_value=1)
        self.request_handler = CoreHandler(request_mock, "", self.server)
        self.request_handler.session = self.session
        self.request_handler.add_session_handlers()
        self.session.broker.session_clients.append(self.request_handler)

        # have broker handle a configuration state change
        self.session.set_state(EventTypes.DEFINITION_STATE)
        message = CoreEventMessage.create(
            0, [(EventTlvs.TYPE, EventTypes.CONFIGURATION_STATE.value)]
        )
        self.request_handler.handle_message(message)

        # add broker server for distributed core
        distributed = "%s:%s:%s" % (
            self.distributed_server,
            distributed_address,
            self.port,
        )
        message = CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "broker"),
                (ConfigTlvs.TYPE, 0),
                (ConfigTlvs.DATA_TYPES, (10,)),
                (ConfigTlvs.VALUES, distributed),
            ],
        )
        self.request_handler.handle_message(message)

        # set session location
        message = CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.OBJECT, "location"),
                (ConfigTlvs.TYPE, 0),
                (ConfigTlvs.DATA_TYPES, (9, 9, 9, 9, 9, 9)),
                (ConfigTlvs.VALUES, "0|0| 47.5766974863|-122.125920191|0.0|150.0"),
            ],
        )
        self.request_handler.handle_message(message)

        # set services for host nodes
        message = CoreConfMessage.create(
            0,
            [
                (ConfigTlvs.SESSION, str(self.session.id)),
                (ConfigTlvs.OBJECT, "services"),
                (ConfigTlvs.TYPE, 0),
                (ConfigTlvs.DATA_TYPES, (10, 10, 10)),
                (ConfigTlvs.VALUES, "host|DefaultRoute|SSH"),
            ],
        )
        self.request_handler.handle_message(message)

    def shutdown(self):
        self.server.coreemu.shutdown()
        self.server.server_close()


@pytest.fixture
def grpc_server():
    coremu = CoreEmu()
    grpc_server = CoreGrpcServer(coremu)
    thread = threading.Thread(target=grpc_server.listen, args=("localhost:50051",))
    thread.daemon = True
    thread.start()
    time.sleep(0.1)
    yield grpc_server
    coremu.shutdown()
    grpc_server.server.stop(None)


@pytest.fixture
def session():
    # use coreemu and create a session
    coreemu = CoreEmu(config={"emane_prefix": "/usr"})
    session_fixture = coreemu.create_session()
    session_fixture.set_state(EventTypes.CONFIGURATION_STATE)
    assert os.path.exists(session_fixture.session_dir)

    # return created session
    yield session_fixture

    # clear session configurations
    session_fixture.location.reset()
    session_fixture.services.reset()
    session_fixture.mobility.config_reset()
    session_fixture.emane.config_reset()

    # shutdown coreemu
    coreemu.shutdown()

    # clear services, since they will be reloaded
    ServiceManager.services.clear()


@pytest.fixture(scope="module")
def ip_prefixes():
    return IpPrefixes(ip4_prefix="10.83.0.0/16")


@pytest.fixture(scope="module")
def interface_helper():
    return InterfaceHelper(ip4_prefix="10.83.0.0/16")


@pytest.fixture()
def cored():
    # create and return server
    server = CoreServerTest()
    yield server

    # cleanup
    server.shutdown()

    # cleanup services
    ServiceManager.services.clear()


@pytest.fixture()
def coreserver():
    # create and return server
    server = CoreServerTest()
    server.setup_handler()
    yield server

    # cleanup
    server.shutdown()

    # cleanup services
    ServiceManager.services.clear()


def ping(from_node, to_node, ip_prefixes, count=3):
    address = ip_prefixes.ip4_address(to_node)
    return from_node.cmd(["ping", "-c", str(count), address])


def pytest_addoption(parser):
    parser.addoption("--distributed", help="distributed server address")


def pytest_generate_tests(metafunc):
    distributed_param = "distributed_address"
    if distributed_param in metafunc.fixturenames:
        distributed_address = metafunc.config.getoption("distributed")
        metafunc.parametrize(distributed_param, [distributed_address])
