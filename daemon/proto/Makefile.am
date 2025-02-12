all:
	../../venv/bin/python -m grpc_tools.protoc -I . --python_out=.. --pyi_out=.. core/api/grpc/*.proto
	../../venv/bin/python -m grpc_tools.protoc -I . --grpc_python_out=.. --pyi_out=.. core/api/grpc/core.proto

clean:
	-rm -f ../core/api/grpc/*_pb2*
