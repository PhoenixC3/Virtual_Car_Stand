FROM python:alpine

RUN mkdir /service
COPY protobufs /protos
COPY gateway /service/gateway
COPY gateway/templates /service/gateway/templates

WORKDIR /service/gateway
RUN pip install -r requirements.txt

RUN python -m grpc_tools.protoc -I /protos --python_out=. /protos/models/*.proto
RUN python -m grpc_tools.protoc -I /protos --python_out=. --grpc_python_out=. /protos/services/*.proto

EXPOSE 50000
CMD ["python", "gateway.py"]
