import pytest

from core.emulator.coreemu import CoreEmu
from core.emulator.data import IpPrefixes
from core.emulator.enumerations import EventTypes


@pytest.fixture(scope="session")
def global_session():
    core = CoreEmu()
    session = core.create_session()
    yield session
    core.shutdown()


@pytest.fixture
def session(global_session):
    global_session.set_state(EventTypes.CONFIGURATION_STATE)
    yield global_session
    global_session.clear()


@pytest.fixture(scope="session")
def ip_prefixes():
    return IpPrefixes(ip4_prefix="10.0.0.0/24")
