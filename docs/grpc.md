# Using the gRPC API

By default the gRPC API is currently not turned on by default. There are a couple ways that this can be enabled
to use.

## Enabling gRPC

### HTTP Proxy

Since gRPC is HTTP2 based, proxy configurations can cause issue. Clear out your proxy when running if needed.

### Daemon Options

The gRPC API is enabled through options provided to the **core-daemon**.

```shell
usage: core-daemon [-h] [-f CONFIGFILE] [-p PORT] [-n NUMTHREADS] [--ovs]
                   [--grpc] [--grpc-port GRPCPORT]
                   [--grpc-address GRPCADDRESS]

CORE daemon v.5.3.0 instantiates Linux network namespace nodes.

optional arguments:
  -h, --help            show this help message and exit
  -f CONFIGFILE, --configfile CONFIGFILE
                        read config from specified file; default =
                        /etc/core/core.conf
  -p PORT, --port PORT  port number to listen on; default = 4038
  -n NUMTHREADS, --numthreads NUMTHREADS
                        number of server threads; default = 1
  --ovs                 enable experimental ovs mode, default is false
  --grpc                enable grpc api, default is false
  --grpc-port GRPCPORT  grpc port to listen on; default 50051
  --grpc-address GRPCADDRESS
                        grpc address to listen on; default localhost
```

### Enabling in Service Files

Modify service files to append the --grpc options as desired.

For sysv services /etc/init.d/core-daemon
```shell
CMD="PYTHONPATH=/usr/lib/python3.6/site-packages python3 /usr/bin/$NAME --grpc"
```

For systemd service /lib/systemd/system/core-daemon.service
```shell
ExecStart=@PYTHON@ @bindir@/core-daemon --grpc
```

### Enabling from Command Line

```shell
sudo core-daemon --grpc
```

## Python Client

A python client wrapper is provided at **core.api.grpc.client.CoreGrpcClient**.

Below is a small example using it.

```python
import logging
from builtins import range

from core.api.grpc import client, core_pb2


def log_event(event):
    logging.info("event: %s", event)


def main():
    core = client.CoreGrpcClient()

    with core.context_connect():
        # create session
        response = core.create_session()
        logging.info("created session: %s", response)

        # handle events session may broadcast
        session_id = response.session_id
        core.events(session_id, log_event)

        # change session state
        response = core.set_session_state(session_id, core_pb2.SessionState.CONFIGURATION)
        logging.info("set session state: %s", response)

        # create switch node
        switch = core_pb2.Node(type=core_pb2.NodeType.SWITCH)
        response = core.add_node(session_id, switch)
        logging.info("created switch: %s", response)
        switch_id = response.node_id

        # helper to create interfaces
        interface_helper = client.InterfaceHelper(ip4_prefix="10.83.0.0/16")

        for i in range(2):
            # create node
            position = core_pb2.Position(x=50 + 50 * i, y=50)
            node = core_pb2.Node(position=position)
            response = core.add_node(session_id, node)
            logging.info("created node: %s", response)
            node_id = response.node_id

            # create link
            interface_one = interface_helper.create_interface(node_id, 0)
            response = core.add_link(session_id, node_id, switch_id, interface_one)
            logging.info("created link: %s", response)

        # change session state
        response = core.set_session_state(session_id, core_pb2.SessionState.INSTANTIATION)
        logging.info("set session state: %s", response)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
```
