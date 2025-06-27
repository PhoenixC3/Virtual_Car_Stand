FROM python:alpine

RUN mkdir /service
COPY protobufs/models/meeting.proto /protos/models/meeting.proto
COPY protobufs/services/meeting_service.proto /protos/services/meeting_service.proto
COPY meeting /service/meeting

WORKDIR /service/meeting
RUN pip install -r requirements.txt

RUN python -m grpc_tools.protoc -I/protos --python_out=. /protos/models/meeting.proto
RUN python -m grpc_tools.protoc -I/protos --python_out=. --grpc_python_out=. /protos/services/meeting_service.proto

EXPOSE 50015
CMD ["python", "meeting.py"]