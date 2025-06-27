import logging
import os
import grpc
import psycopg2
from concurrent import futures
from prometheus_client import start_http_server, Counter, Summary, Histogram, Gauge

from services import meeting_service_pb2_grpc
from services import meeting_service_pb2
from services.meeting_service_pb2 import Meeting
from google.protobuf import empty_pb2

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Prometheus metrics
REQUEST_COUNT = Counter('meeting_request_count', 'Total number of requests by endpoint', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('meeting_request_latency_seconds', 'Request latency in seconds', ['endpoint'])
ACTIVE_REQUESTS = Gauge('meeting_active_requests', 'Number of active requests', ['endpoint'])
DB_OPERATION_LATENCY = Summary('meeting_db_operation_latency_seconds', 'Database operation latency', ['operation'])

class MeetingService(meeting_service_pb2_grpc.MeetingServiceServicer):
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
        )
        self.cursor = self.conn.cursor()

    def MeetingsCreate(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='MeetingsCreate').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='MeetingsCreate').time():
                with DB_OPERATION_LATENCY.labels(operation='insert').time():
                    self.cursor.execute(
                        """
                        INSERT INTO meeting (client_id, schedule_date, meeting_status)
                        VALUES (%s, %s, %s) RETURNING meeting_id
                        """,
                        (request.meeting.clientId, request.meeting.scheduleDate, Meeting.StatusEnum.Name(request.meeting.status))
                    )
                    meeting_id = self.cursor.fetchone()[0]
                    self.conn.commit()
                
                REQUEST_COUNT.labels(endpoint='MeetingsCreate', status='success').inc()
                return Meeting(
                    meetingId=meeting_id,
                    clientId=request.meeting.clientId,
                    scheduleDate=request.meeting.scheduleDate,
                    status=request.meeting.status,
                )
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='MeetingsCreate', status='error').inc()
            return Meeting()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='MeetingsCreate').dec()

    def MeetingsReadOne(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='MeetingsReadOne').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='MeetingsReadOne').time():
                with DB_OPERATION_LATENCY.labels(operation='select').time():
                    self.cursor.execute("SELECT * FROM meeting WHERE meeting_id = %s", (request.meetingId,))
                    meeting = self.cursor.fetchone()
                
                if meeting:
                    REQUEST_COUNT.labels(endpoint='MeetingsReadOne', status='success').inc()
                    return Meeting(
                        meetingId=int(meeting[0]),
                        clientId=int(meeting[1]),
                        scheduleDate=meeting[2].isoformat() if meeting[2] else "",
                        status=Meeting.StatusEnum.Value(meeting[3]),
                    )
                else:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Meeting with ID {request.meetingId} not found.")
                    REQUEST_COUNT.labels(endpoint='MeetingsReadOne', status='not_found').inc()
                    return Meeting()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='MeetingsReadOne', status='error').inc()
            return Meeting()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='MeetingsReadOne').dec()

    def MeetingsReadAll(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='MeetingsReadAll').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='MeetingsReadAll').time():
                with DB_OPERATION_LATENCY.labels(operation='select_all').time():
                    self.cursor.execute("SELECT * FROM meeting")
                    rows = self.cursor.fetchall()

                meetings = []
                for row in rows:
                    logging.info(f"Row data: {row}, Types: {[type(value) for value in row]}")
                    try:
                        meeting = Meeting(
                            meetingId=int(row[0]),
                            clientId=int(row[1]),
                            scheduleDate=row[2].isoformat() if row[2] else "",
                            status=Meeting.StatusEnum.Value(row[3]),
                        )
                        meetings.append(meeting)
                    except Exception as e:
                        logging.info(f"Error processing row: {row}, Error: {e}")
                        REQUEST_COUNT.labels(endpoint='MeetingsReadAll', status='row_error').inc()
                
                REQUEST_COUNT.labels(endpoint='MeetingsReadAll', status='success').inc()
                return meeting_service_pb2.MeetingsReadAllResponse(data=meetings)
        except Exception as e:
            logging.error(f"Error in MeetingsReadAll: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='MeetingsReadAll', status='error').inc()
            return meeting_service_pb2.MeetingsReadAllResponse()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='MeetingsReadAll').dec()

    def MeetingsUpdate(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='MeetingsUpdate').inc()
        
        if (request.meetingId != request.meeting.meetingId):
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("meetingId in URL and body must match")
            REQUEST_COUNT.labels(endpoint='MeetingsUpdate', status='invalid_argument').inc()
            ACTIVE_REQUESTS.labels(endpoint='MeetingsUpdate').dec()
            return Meeting()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='MeetingsUpdate').time():
                with DB_OPERATION_LATENCY.labels(operation='update').time():
                    self.cursor.execute(
                        """
                        UPDATE meeting SET client_id = %s, schedule_date = %s, meeting_status = %s
                        WHERE meeting_id = %s RETURNING meeting_id
                        """,
                        (request.meeting.clientId, request.meeting.scheduleDate,  Meeting.StatusEnum.Name(request.meeting.status), request.meetingId),
                    )
                    updated_meeting_id = self.cursor.fetchone()
                
                if updated_meeting_id:
                    self.conn.commit()
                    REQUEST_COUNT.labels(endpoint='MeetingsUpdate', status='success').inc()
                    return Meeting(
                        meetingId=request.meetingId,
                        clientId=request.meeting.clientId,
                        scheduleDate=request.meeting.scheduleDate,
                        status=request.meeting.status,
                    )
                else:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Meeting with ID {request.meetingId} not found.")
                    REQUEST_COUNT.labels(endpoint='MeetingsUpdate', status='not_found').inc()
                    return Meeting()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='MeetingsUpdate', status='error').inc()
            return Meeting()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='MeetingsUpdate').dec()

    def MeetingsDelete(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='MeetingsDelete').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='MeetingsDelete').time():
                with DB_OPERATION_LATENCY.labels(operation='delete').time():
                    self.cursor.execute("DELETE FROM meeting WHERE meeting_id = %s RETURNING meeting_id", (request.meetingId,))
                    deleted_meeting_id = self.cursor.fetchone()
                
                if deleted_meeting_id:
                    self.conn.commit()
                    REQUEST_COUNT.labels(endpoint='MeetingsDelete', status='success').inc()
                    return empty_pb2.Empty()
                else:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Meeting with ID {request.meetingId} not found.")
                    REQUEST_COUNT.labels(endpoint='MeetingsDelete', status='not_found').inc()
                    return empty_pb2.Empty()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='MeetingsDelete', status='error').inc()
            return empty_pb2.Empty()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='MeetingsDelete').dec()

def serve():
    # Start Prometheus HTTP server on port 8000
    start_http_server(8000)
    print("Prometheus metrics server started on port 8000...")
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    meeting_service_pb2_grpc.add_MeetingServiceServicer_to_server(MeetingService(), server)
    server.add_insecure_port("[::]:50015")
    print("Meeting service running on port 50015...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
