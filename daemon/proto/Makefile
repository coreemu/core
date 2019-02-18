all:
	python -m grpc_tools.protoc -I . --python_out=../core/grpc --grpc_python_out=../core/grpc core.proto

clean:
	rm core_pb2*
