FROM python:alpine

RUN mkdir /service
COPY protobufs/models/inspection.proto /protos/models/inspection.proto
COPY protobufs/services/inspection_service.proto /protos/services/inspection_service.proto
COPY inspection /service/inspection

WORKDIR /service/inspection
RUN pip install -r requirements.txt

RUN python -m grpc_tools.protoc -I/protos --python_out=. /protos/models/inspection.proto
RUN python -m grpc_tools.protoc -I/protos --python_out=. --grpc_python_out=. /protos/services/inspection_service.proto

EXPOSE 50011
CMD ["python", "inspection.py"]