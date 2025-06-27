FROM python:alpine

RUN mkdir /service
COPY protobufs/models/user.proto /protos/models/user.proto
COPY protobufs/services/user_service.proto /protos/services/user_service.proto
COPY user /service/user

WORKDIR /service/user
RUN pip install -r requirements.txt

RUN python -m grpc_tools.protoc -I/protos --python_out=. /protos/models/user.proto
RUN python -m grpc_tools.protoc -I/protos --python_out=. --grpc_python_out=. /protos/services/user_service.proto

EXPOSE 50007
CMD ["python", "user.py"]