FROM python:alpine

RUN mkdir /service
COPY protobufs/models/car.proto /protos/models/car.proto
COPY protobufs/services/car_service.proto /protos/services/car_service.proto
COPY car /service/car

WORKDIR /service/car
RUN pip install -r requirements.txt

RUN python -m grpc_tools.protoc -I/protos --python_out=. /protos/models/car.proto
RUN python -m grpc_tools.protoc -I/protos --python_out=. --grpc_python_out=. /protos/services/car_service.proto

EXPOSE 50008
CMD ["python", "car.py"]