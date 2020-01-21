all:
	$(PYTHON) -m grpc_tools.protoc -I . --python_out=.. core/api/grpc/*.proto
	$(PYTHON) -m grpc_tools.protoc -I . --grpc_python_out=.. core/api/grpc/core.proto

clean:
	-rm -f ../core/api/grpc/*_pb2*
