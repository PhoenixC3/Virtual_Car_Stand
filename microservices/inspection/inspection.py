import logging
import os
import grpc
import psycopg2
from concurrent import futures
from google.protobuf import empty_pb2
from prometheus_client import start_http_server, Counter, Summary, Histogram, Gauge

from services import inspection_service_pb2_grpc
from services import inspection_service_pb2
from services.inspection_service_pb2 import Inspection

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Prometheus metrics
REQUEST_COUNT = Counter('inspection_request_count', 'Total number of requests by endpoint', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('inspection_request_latency_seconds', 'Request latency in seconds', ['endpoint'])
ACTIVE_REQUESTS = Gauge('inspection_active_requests', 'Number of active requests', ['endpoint'])
DB_OPERATION_LATENCY = Summary('inspection_db_operation_latency_seconds', 'Database operation latency', ['operation'])

class InspectionService(inspection_service_pb2_grpc.InspectionServiceServicer):
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
        )
        self.cursor = self.conn.cursor()

    def InspectionCreate(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='InspectionCreate').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='InspectionCreate').time():
                with DB_OPERATION_LATENCY.labels(operation='insert').time():
                    query = """
                    INSERT INTO inspection (
                        inspection_car_id,
                        inspection_status,
                        inspection_client_notes,
                        inspection_staff_notes,
                        inspection_cost,
                        inspection_start_date,
                        inspection_end_date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING inspection_id;
                    """
                    self.cursor.execute(
                    query,
                    (
                        request.inspection.inspectionCarId,
                        Inspection.InspectionStatusEnum.Name(request.inspection.inspectionStatus),
                        request.inspection.inspectionClientNotes,
                        request.inspection.inspectionStaffNotes,
                        request.inspection.inspectionCost,
                        request.inspection.inspectionStartDate,
                        request.inspection.inspectionEndDate,
                    ),
                    )
                    inspection_id = self.cursor.fetchone()[0]
                    self.conn.commit()
                
                REQUEST_COUNT.labels(endpoint='InspectionCreate', status='success').inc()
                return Inspection(
                    inspectionId=inspection_id,
                    inspectionCarId=request.inspection.inspectionCarId,
                    inspectionStatus=request.inspection.inspectionStatus,
                    inspectionClientNotes=request.inspection.inspectionClientNotes,
                    inspectionStaffNotes=request.inspection.inspectionStaffNotes,
                    inspectionCost=request.inspection.inspectionCost,
                    inspectionStartDate=request.inspection.inspectionStartDate,
                    inspectionEndDate=request.inspection.inspectionEndDate,
                )
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='InspectionCreate', status='error').inc()
            return Inspection()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='InspectionCreate').dec()
        
    def InspectionDelete(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='InspectionDelete').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='InspectionDelete').time():
                with DB_OPERATION_LATENCY.labels(operation='delete').time():
                    self.cursor.execute("DELETE FROM inspection WHERE inspection_id = %s RETURNING inspection_id", (request.inspectionId,))
                    deleted_inspection_id = self.cursor.fetchone()
                
            if deleted_inspection_id:
                self.conn.commit()
                REQUEST_COUNT.labels(endpoint='InspectionDelete', status='success').inc()
                return empty_pb2.Empty()
            else:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Inspection not found")
                REQUEST_COUNT.labels(endpoint='InspectionDelete', status='not_found').inc()
                return empty_pb2.Empty()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='InspectionDelete', status='error').inc()
            return empty_pb2.Empty()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='InspectionDelete').dec()
        
    def InspectionReadAll(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='InspectionReadAll').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='InspectionReadAll').time():
                with DB_OPERATION_LATENCY.labels(operation='select_all').time():
                    self.cursor.execute("SELECT * FROM inspection")
                    rows = self.cursor.fetchall()

                inspections = []
                for row in rows:
                    logging.info(f"Row data: {row}, Types: {[type(value) for value in row]}")
                    try:
                        inspection = Inspection(
                            inspectionId=int(row[0]),
                            inspectionCarId=int(row[1]),
                            inspectionStatus=Inspection.InspectionStatusEnum.Value(row[2]),
                            inspectionClientNotes=row[3] if row[3] is not None else "",
                            inspectionStaffNotes=row[4] if row[4] is not None else "",
                            inspectionCost=row[5] if row[5] is not None else 0.0,
                            inspectionStartDate=row[6].isoformat() if row[6] is not None else "",
                            inspectionEndDate=row[7].isoformat() if row[7] is not None else "",
                        )
                        inspections.append(inspection)
                    except Exception as e:
                        logging.info(f"Error processing row: {row}, Error: {e}")
                        REQUEST_COUNT.labels(endpoint='InspectionReadAll', status='row_error').inc()
                
                REQUEST_COUNT.labels(endpoint='InspectionReadAll', status='success').inc()
                return inspection_service_pb2.InspectionReadAllResponse(data=inspections)
        except Exception as e:
            logging.error(f"Error in InspectionReadAll: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='InspectionReadAll', status='error').inc()
            return inspection_service_pb2.InspectionReadAllResponse()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='InspectionReadAll').dec()
    
    def InspectionReadOne(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='InspectionReadOne').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='InspectionReadOne').time():
                with DB_OPERATION_LATENCY.labels(operation='select').time():
                    self.cursor.execute("SELECT * FROM inspection WHERE inspection_id = %s", (request.inspectionId,))
                    inspection = self.cursor.fetchone()
                
            if inspection:
                REQUEST_COUNT.labels(endpoint='InspectionReadOne', status='success').inc()
                return Inspection(
                    inspectionId=int(inspection[0]),
                        inspectionCarId=int(inspection[1]),
                        inspectionStatus=Inspection.InspectionStatusEnum.Value(inspection[2]),
                        inspectionClientNotes=inspection[3] if inspection[3] is not None else "",
                        inspectionStaffNotes=inspection[4] if inspection[4] is not None else "",
                        inspectionCost=inspection[5] if inspection[5] is not None else 0.0,
                        inspectionStartDate=inspection[6].isoformat() if inspection[6] is not None else "",
                        inspectionEndDate=inspection[7].isoformat() if inspection[7] is not None else "",
                )
            else:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Inspection with ID {request.inspectionId} not found.")
                REQUEST_COUNT.labels(endpoint='InspectionReadOne', status='not_found').inc()
                return Inspection()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='InspectionReadOne', status='error').inc()
            return Inspection()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='InspectionReadOne').dec()
        
    def InspectionUpdate(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='InspectionUpdate').inc()
        
        if (request.inspectionId != request.inspection.inspectionId):
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Inspection ID mismatch")
            REQUEST_COUNT.labels(endpoint='InspectionUpdate', status='invalid_argument').inc()
            ACTIVE_REQUESTS.labels(endpoint='InspectionUpdate').dec()
            return Inspection()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='InspectionUpdate').time():
                with DB_OPERATION_LATENCY.labels(operation='update').time():
                    self.cursor.execute(
                        """
                        UPDATE inspection SET
                        inspection_car_id = %s,
                        inspection_status = %s,
                        inspection_client_notes = %s,
                        inspection_staff_notes = %s,
                        inspection_cost = %s,
                        inspection_start_date = %s,
                        inspection_end_date = %s
                        WHERE inspection_id = %s
                        RETURNING inspection_id;
                        """,
                        (
                            request.inspection.inspectionCarId,
                            Inspection.InspectionStatusEnum.Name(request.inspection.inspectionStatus),
                            request.inspection.inspectionClientNotes,
                            request.inspection.inspectionStaffNotes,
                            request.inspection.inspectionCost,
                            request.inspection.inspectionStartDate,
                            request.inspection.inspectionEndDate,
                            request.inspection.inspectionId,
                        )
                    )
                    updated_inspection_id = self.cursor.fetchone()
                
            if updated_inspection_id:
                self.conn.commit()
                REQUEST_COUNT.labels(endpoint='InspectionUpdate', status='success').inc()
                return request.inspection
            else:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Inspection with ID {request.inspectionId} not found.")
                REQUEST_COUNT.labels(endpoint='InspectionUpdate', status='not_found').inc()
                return Inspection()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='InspectionUpdate', status='error').inc()
            return Inspection()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='InspectionUpdate').dec()
        
def serve():
    # Start Prometheus HTTP server on port 8000
    start_http_server(8000)
    print("Prometheus metrics server started on port 8000...")
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inspection_service_pb2_grpc.add_InspectionServiceServicer_to_server(InspectionService(), server)
    server.add_insecure_port("[::]:50011")
    print("Inspection service running on port 50011...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()