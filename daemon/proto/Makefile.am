all:
	$(PYTHON) -m grpc_tools.protoc -I . --python_out=.. --grpc_python_out=.. core/api/grpc/core.proto

clean:
	-rm -f ../core/api/grpc/core_pb2*
