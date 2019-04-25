all:
	$(PYTHON) -m grpc_tools.protoc -I . --python_out=../core/grpc --grpc_python_out=../core/grpc core.proto

clean:
	-rm -f ../core/grpc/core_pb2*
