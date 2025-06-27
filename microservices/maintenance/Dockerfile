FROM python:alpine

RUN mkdir /service
COPY protobufs/models/maintenance.proto /protos/models/maintenance.proto
COPY protobufs/services/maintenance_service.proto /protos/services/maintenance_service.proto
COPY maintenance /service/maintenance

WORKDIR /service/maintenance
RUN pip install -r requirements.txt

RUN python -m grpc_tools.protoc -I/protos --python_out=. /protos/models/maintenance.proto
RUN python -m grpc_tools.protoc -I/protos --python_out=. --grpc_python_out=. /protos/services/maintenance_service.proto

EXPOSE 50012
CMD ["python", "maintenance.py"]