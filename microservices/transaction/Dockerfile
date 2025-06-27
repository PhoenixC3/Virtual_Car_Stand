FROM python:alpine

RUN mkdir /service
COPY protobufs/models/transaction.proto /protos/models/transaction.proto
COPY protobufs/services/transaction_service.proto /protos/services/transaction_service.proto
COPY transaction /service/transaction

WORKDIR /service/transaction
RUN pip install -r requirements.txt

RUN python -m grpc_tools.protoc -I/protos --python_out=. /protos/models/transaction.proto
RUN python -m grpc_tools.protoc -I/protos --python_out=. --grpc_python_out=. /protos/services/transaction_service.proto

EXPOSE 50010
CMD ["python", "transaction.py"]