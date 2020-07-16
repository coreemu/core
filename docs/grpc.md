# Using the gRPC API

[gRPC](https://grpc.io/) is the main API for interfacing with CORE and used by
the python GUI for driving all functionality.

Currently we are providing a python client that wraps the generated files for
leveraging the API, but proto files noted below can also be leveraged to generate
bindings for other languages as well.

## HTTP Proxy

Since gRPC is HTTP2 based, proxy configurations can cause issue. You can either
properly account for this issue or clear out your proxy when running if needed.

## Python Client

A python client wrapper is provided at
[CoreGrpcClient](https://github.com/coreemu/core/blob/master/daemon/core/api/grpc/client.py)
to help provide some conveniences when using the API.

## Proto Files

Proto files are used to define the API and protobuf messages that are used for
interfaces with this API.

They can be found
[here](https://github.com/coreemu/core/tree/master/daemon/proto/core/api/grpc)
to see the specifics of
what is going on and response message values that would be returned.

## Examples

Example usage of this API can be found
[here](https://github.com/coreemu/core/tree/master/daemon/examples/grpc).
These examples will create a session using the gRPC API when the core-daemon is running.

You can then switch to and attach to these sessions using either of the CORE GUIs.
