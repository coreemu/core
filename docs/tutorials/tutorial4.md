# Tutorial 4 - Tests

## Overview

A use case for CORE would be to help automate integration tests for running
software within a network. This tutorial covers using CORE with the python
pytest testing framework. It will show how you can define tests, for different
use cases to validate software and outcomes within a defined network. Using
pytest, you would create tests using all the standard pytest functionality.
Creating a test file, and then defining test functions to run. For these tests,
we are leveraging the CORE library directly and the API it provides.

Refer to the [pytest documentation](https://docs.pytest.org) for indepth
information on how to write tests with pytest.

## Files

A directory is used for containing your tests. Within this directory we need a
**conftest.py**, which pytest will pick up to help define and provide
test fixtures, which will be leveraged within our tests.

* tests
    * conftest.py - file used by pytest to define fixtures, which can be shared across tests
    * test_ping.py - defines test classes/functions to run

## Test Fixtures

Below are the definitions for fixture you can define to facilitate and make
creating CORE based tests easier.

The global session fixture creates one **CoreEmu** object for the entire
test session, yields it for testing, and calls shutdown when everything
is over.

``` python
@pytest.fixture(scope="session")
def global_session():
    core = CoreEmu()
    session = core.create_session()
    session.set_state(EventTypes.CONFIGURATION_STATE)
    yield session
    core.shutdown()
```

The regular session fixture leverages the global session fixture. It
will set the correct state for each test case, yield the session for a test,
and then clear the session after a test finishes to prepare for the next
test.

``` python
@pytest.fixture
def session(global_session):
    global_session.set_state(EventTypes.CONFIGURATION_STATE)
    yield global_session
    global_session.clear()
```

The ip prefixes fixture help provide a preconfigured convenience for
creating and assigning interfaces to nodes, when creating your network
within a test. The address subnet can be whatever you desire.

``` python
@pytest.fixture(scope="session")
def ip_prefixes():
    return IpPrefixes(ip4_prefix="10.0.0.0/24")
```

## Test Functions

Within a pytest test file, you have the freedom to create any kind of
test you like, but they will all follow a similar formula.

* define a test function that will leverage the session and ip prefixes fixtures
* then create a network to test, using the session fixture
* run commands within nodes as desired, to test out your use case
* validate command result or output for expected behavior to pass or fail

In the test below, we create a simple 2 node wired network and validate
node1 can ping node2 successfully.

``` python
def test_success(self, session: Session, ip_prefixes: IpPrefixes):
    # create nodes
    node1 = session.add_node(CoreNode)
    node2 = session.add_node(CoreNode)

    # link nodes together
    iface1_data = ip_prefixes.create_iface(node1)
    iface2_data = ip_prefixes.create_iface(node2)
    session.add_link(node1.id, node2.id, iface1_data, iface2_data)

    # ping node, expect a successful command
    node1.cmd(f"ping -c 1 {iface2_data.ip4}")
```

## Install Pytest

Since we are running an automated test within CORE, we will need to install
pytest within the python interpreter used by CORE.

``` shell
sudo /opt/core/venv/bin/python -m pip install pytest
```

## Running Tests

You can run your own or the provided tests, by running the following.

``` shell
cd <test directory>
sudo /opt/core/venv/bin/python -m pytest -v
```

If you run the provided tests, you would expect to see the two tests
running and passing.

``` shell
tests/test_ping.py::TestPing::test_success PASSED                                [ 50%]
tests/test_ping.py::TestPing::test_failure PASSED                                [100%]
```

