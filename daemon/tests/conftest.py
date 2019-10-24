"""
Unit test fixture module.
"""

import threading
import time

import mock
import pytest
from mock.mock import MagicMock

from core.api.grpc.client import InterfaceHelper
from core.api.grpc.server import CoreGrpcServer
from core.api.tlv.coreapi import CoreConfMessage, CoreEventMessage
from core.api.tlv.corehandlers import CoreHandler
from core.api.tlv.coreserver import CoreServer
from core.emulator.coreemu import CoreEmu
from core.emulator.emudata import IpPrefixes
from core.emulator.enumerations import CORE_API_PORT, ConfigTlvs, EventTlvs, EventTypes
from core.emulator.session import Session
from core.nodes import ipaddress
from core.nodes.base import CoreNode

EMANE_SERVICES = "zebra|OSPFv3MDR|IPForward"


class CoreServerTest:
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

        # have broker handle a configuration state change
        self.session.set_state(EventTypes.DEFINITION_STATE)
        message = CoreEventMessage.create(
            0, [(EventTlvs.TYPE, EventTypes.CONFIGURATION_STATE.value)]
        )
        self.request_handler.handle_message(message)

        # add broker server for distributed core
        distributed = f"{self.distributed_server}:{distributed_address}:{self.port}"
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
                (ConfigTlvs.VALUES, "0|0|47.5766974863|-122.125920191|0.0|150.0"),
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


class PatchManager:
    def __init__(self):
        self.patches = []

    def patch_obj(self, _cls, attribute):
        p = mock.patch.object(_cls, attribute)
        p.start()
        self.patches.append(p)

    def patch(self, func):
        p = mock.patch(func)
        p.start()
        self.patches.append(p)

    def shutdown(self):
        for p in self.patches:
            p.stop()


@pytest.fixture(scope="session")
def patcher(request):
    patch_manager = PatchManager()
    if request.config.getoption("mock"):
        patch_manager.patch("os.mkdir")
        patch_manager.patch("core.utils.cmd")
        patch_manager.patch("core.nodes.netclient.get_net_client")
        patch_manager.patch_obj(CoreNode, "nodefile")
        patch_manager.patch_obj(Session, "write_state")
    yield patch_manager
    patch_manager.shutdown()


@pytest.fixture(scope="session")
def global_coreemu(patcher):
    coreemu = CoreEmu(config={"emane_prefix": "/usr"})
    yield coreemu
    coreemu.shutdown()


@pytest.fixture(scope="session")
def global_session(request, patcher, global_coreemu):
    mkdir = not request.config.getoption("mock")
    session = Session(1000, {"emane_prefix": "/usr"}, mkdir)
    yield session
    session.shutdown()


@pytest.fixture(scope="session")
def ip_prefixes():
    return IpPrefixes(ip4_prefix="10.83.0.0/16")


@pytest.fixture(scope="session")
def interface_helper():
    return InterfaceHelper(ip4_prefix="10.83.0.0/16")


@pytest.fixture(scope="module")
def module_grpc(global_coreemu):
    grpc_server = CoreGrpcServer(global_coreemu)
    thread = threading.Thread(target=grpc_server.listen, args=("localhost:50051",))
    thread.daemon = True
    thread.start()
    time.sleep(0.1)
    yield grpc_server
    grpc_server.server.stop(None)


@pytest.fixture(scope="module")
def module_cored(request, patcher):
    mkdir = not request.config.getoption("mock")
    server = CoreServerTest(mkdir)
    server.setup_handler()
    yield server
    server.shutdown()


@pytest.fixture
def grpc_server(module_grpc):
    yield module_grpc
    module_grpc.coreemu.shutdown()


@pytest.fixture
def session(global_session):
    global_session.set_state(EventTypes.CONFIGURATION_STATE)
    yield global_session
    global_session.clear()
    global_session.location.reset()
    global_session.services.reset()
    global_session.mobility.config_reset()
    global_session.emane.config_reset()


@pytest.fixture
def cored(module_cored):
    session = module_cored.session
    module_cored.server.coreemu.sessions[session.id] = session
    yield module_cored
    session.clear()
    session.location.reset()
    session.services.reset()
    session.mobility.config_reset()
    session.emane.config_reset()


def pytest_addoption(parser):
    parser.addoption("--distributed", help="distributed server address")
    parser.addoption("--mock", action="store_true", help="run without mocking")


def pytest_generate_tests(metafunc):
    distributed_param = "distributed_address"
    if distributed_param in metafunc.fixturenames:
        distributed_address = metafunc.config.getoption("distributed")
        metafunc.parametrize(distributed_param, [distributed_address])
