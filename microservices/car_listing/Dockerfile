FROM python:alpine

RUN mkdir /service
COPY protobufs/models/car_listing.proto /protos/models/car_listing.proto
COPY protobufs/services/car_listing_service.proto /protos/services/car_listing_service.proto
COPY protobufs/models/transaction.proto /protos/models/transaction.proto
COPY protobufs/services/transaction_service.proto /protos/services/transaction_service.proto
COPY car_listing /service/car_listing

WORKDIR /service/car_listing
RUN pip install -r requirements.txt

RUN python -m grpc_tools.protoc -I/protos --python_out=. /protos/models/car_listing.proto
RUN python -m grpc_tools.protoc -I/protos --python_out=. --grpc_python_out=. /protos/services/car_listing_service.proto
RUN python -m grpc_tools.protoc -I/protos --python_out=. /protos/models/transaction.proto
RUN python -m grpc_tools.protoc -I/protos --python_out=. --grpc_python_out=. /protos/services/transaction_service.proto

EXPOSE 50009
CMD ["python", "car_listing.py"]
