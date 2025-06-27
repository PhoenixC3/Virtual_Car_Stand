import os
import grpc
import psycopg2
from concurrent import futures
from google.protobuf import empty_pb2
from prometheus_client import start_http_server, Counter, Summary, Histogram, Gauge

from services import maintenance_service_pb2_grpc
from services import maintenance_service_pb2
from services.maintenance_service_pb2 import Maintenance
import logging

logging.basicConfig(level=logging.INFO)

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Prometheus metrics
REQUEST_COUNT = Counter('maintenance_request_count', 'Total number of requests by endpoint', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('maintenance_request_latency_seconds', 'Request latency in seconds', ['endpoint'])
ACTIVE_REQUESTS = Gauge('maintenance_active_requests', 'Number of active requests', ['endpoint'])
DB_OPERATION_LATENCY = Summary('maintenance_db_operation_latency_seconds', 'Database operation latency', ['operation'])

class MaintenanceService(maintenance_service_pb2_grpc.MaintenanceServiceServicer):
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
        )
        self.cursor = self.conn.cursor()

    def MaintenanceCreate(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='MaintenanceCreate').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='MaintenanceCreate').time():
                with DB_OPERATION_LATENCY.labels(operation='insert').time():
                    query = """
                    INSERT INTO maintenance (
                        maintenance_car_id, maintenance_type, 
                        maintenance_status, maintenance_client_notes, 
                        maintenance_staff_notes, maintenance_cost, 
                        maintenance_start_date, maintenance_end_date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING maintenance_id;
                    """
                    self.cursor.execute(
                    query,
                    (
                        request.maintenance.maintenanceCarId,
                        Maintenance.MaintenanceTypeEnum.Name(request.maintenance.maintenanceType),
                        Maintenance.MaintenanceStatusEnum.Name(request.maintenance.maintenanceStatus),
                        request.maintenance.maintenanceClientNotes,
                        request.maintenance.maintenanceStaffNotes,
                        request.maintenance.maintenanceCost,
                        request.maintenance.maintenanceStartDate,
                        request.maintenance.maintenanceEndDate,
                    ),
                    )
                    maintenance_id=self.cursor.fetchone()[0]
                    self.conn.commit()
                
                REQUEST_COUNT.labels(endpoint='MaintenanceCreate', status='success').inc()
                return Maintenance(
                    maintenanceId=maintenance_id,
                    maintenanceCarId=request.maintenance.maintenanceCarId,
                    maintenanceType=request.maintenance.maintenanceType,
                    maintenanceStatus=request.maintenance.maintenanceStatus,
                    maintenanceClientNotes=request.maintenance.maintenanceClientNotes,
                    maintenanceStaffNotes=request.maintenance.maintenanceStaffNotes,
                    maintenanceCost=request.maintenance.maintenanceCost,
                    maintenanceStartDate=request.maintenance.maintenanceStartDate,
                    maintenanceEndDate=request.maintenance.maintenanceEndDate
                )
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='MaintenanceCreate', status='error').inc()
            return Maintenance()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='MaintenanceCreate').dec()
        
    def MaintenanceDelete(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='MaintenanceDelete').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='MaintenanceDelete').time():
                with DB_OPERATION_LATENCY.labels(operation='delete').time():
                    self.cursor.execute("DELETE FROM maintenance WHERE maintenance_id = %s RETURNING maintenance_id", (request.maintenanceId,))
                    deleted_maintenance_id = self.cursor.fetchone()
                
            if deleted_maintenance_id:
                self.conn.commit()
                REQUEST_COUNT.labels(endpoint='MaintenanceDelete', status='success').inc()
                return empty_pb2.Empty()
            else:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Maintenance ID not found")
                REQUEST_COUNT.labels(endpoint='MaintenanceDelete', status='not_found').inc()
                return empty_pb2.Empty()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='MaintenanceDelete', status='error').inc()
            return empty_pb2.Empty()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='MaintenanceDelete').dec()
        
    def MaintenanceReadAll(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='MaintenanceReadAll').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='MaintenanceReadAll').time():
                with DB_OPERATION_LATENCY.labels(operation='select_all').time():
                    self.cursor.execute("SELECT * FROM maintenance")
                    rows = self.cursor.fetchall()

                maintenances = []
                for row in rows:
                    logging.info(f"Row data: {row}, Types: {[type(value) for value in row]}")
                    try:
                        maintenance = Maintenance(
                            maintenanceId=int(row[0]),
                            maintenanceCarId=int(row[1]),
                            maintenanceType=Maintenance.MaintenanceTypeEnum.Value(row[2]),
                            maintenanceStatus=Maintenance.MaintenanceStatusEnum.Value(row[3]),
                            maintenanceClientNotes=row[4] if row[4] is not None else "",
                            maintenanceStaffNotes=row[5] if row[5] is not None else "",
                            maintenanceCost=row[6] if row[6] is not None else 0.0,
                            maintenanceStartDate=row[7].isoformat() if row[7] is not None else "",
                            maintenanceEndDate=row[8].isoformat() if row[8] is not None else "",
                        )
                        maintenances.append(maintenance)
                    except Exception as e:
                        logging.info(f"Error processing row: {row}, Error: {e}")
                        REQUEST_COUNT.labels(endpoint='MaintenanceReadAll', status='row_error').inc()
                
                REQUEST_COUNT.labels(endpoint='MaintenanceReadAll', status='success').inc()
                return maintenance_service_pb2.MaintenanceReadAllResponse(data=maintenances)
        except Exception as e:
            logging.error(f"Error in MaintenanceReadAll: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='MaintenanceReadAll', status='error').inc()
            return maintenance_service_pb2.MaintenanceReadAllResponse()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='MaintenanceReadAll').dec()
    
    def MaintenanceReadOne(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='MaintenanceReadOne').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='MaintenanceReadOne').time():
                with DB_OPERATION_LATENCY.labels(operation='select').time():
                    self.cursor.execute("SELECT * FROM maintenance WHERE maintenance_id = %s", (request.maintenanceId,))
                    maintenance = self.cursor.fetchone()
                
            if maintenance:
                REQUEST_COUNT.labels(endpoint='MaintenanceReadOne', status='success').inc()
                return Maintenance(
                        maintenanceId=int(maintenance[0]),
                        maintenanceCarId=int(maintenance[1]),
                        maintenanceType=Maintenance.MaintenanceTypeEnum.Value(maintenance[2]),
                        maintenanceStatus=Maintenance.MaintenanceStatusEnum.Value(maintenance[3]),
                        maintenanceClientNotes=maintenance[4] if maintenance[4] is not None else "",
                        maintenanceStaffNotes=maintenance[5] if maintenance[5] is not None else "",
                        maintenanceCost=maintenance[6] if maintenance[6] is not None else 0.0,
                        maintenanceStartDate=maintenance[7].isoformat() if maintenance[7] is not None else "",
                        maintenanceEndDate=maintenance[8].isoformat() if maintenance[8] is not None else "",
                    )
            else:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Maintenance with ID {request.maintenanceId} not found.")
                REQUEST_COUNT.labels(endpoint='MaintenanceReadOne', status='not_found').inc()
                return Maintenance()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='MaintenanceReadOne', status='error').inc()
            return Maintenance()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='MaintenanceReadOne').dec()
        
    def MaintenanceUpdate(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='MaintenanceUpdate').inc()
        
        if (request.maintenanceId != request.maintenance.maintenanceId):
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Maintenance ID in path and body do not match")
            REQUEST_COUNT.labels(endpoint='MaintenanceUpdate', status='invalid_argument').inc()
            ACTIVE_REQUESTS.labels(endpoint='MaintenanceUpdate').dec()
            return Maintenance()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='MaintenanceUpdate').time():
                with DB_OPERATION_LATENCY.labels(operation='update').time():
                    self.cursor.execute(
                        """
                        UPDATE maintenance SET
                        maintenance_car_id = %s,
                        maintenance_type = %s,
                        maintenance_status = %s,
                        maintenance_client_notes = %s,
                        maintenance_staff_notes = %s,
                        maintenance_cost = %s,
                        maintenance_start_date = %s,
                        maintenance_end_date = %s
                        WHERE maintenance_id = %s
                        RETURNING maintenance_id;
                        """,
                        (
                            request.maintenance.maintenanceCarId,
                            Maintenance.MaintenanceTypeEnum.Name(request.maintenance.maintenanceType),
                            Maintenance.MaintenanceStatusEnum.Name(request.maintenance.maintenanceStatus),
                            request.maintenance.maintenanceClientNotes,
                            request.maintenance.maintenanceStaffNotes,
                            request.maintenance.maintenanceCost,
                            request.maintenance.maintenanceStartDate,
                            request.maintenance.maintenanceEndDate,
                            request.maintenance.maintenanceId,
                        )
                    )
                    updated_maintenance_id = self.cursor.fetchone()
                
                if updated_maintenance_id:
                    self.conn.commit()
                    REQUEST_COUNT.labels(endpoint='MaintenanceUpdate', status='success').inc()
                    return request.maintenance
                else:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Maintenance with ID {request.maintenanceId} not found.")
                    REQUEST_COUNT.labels(endpoint='MaintenanceUpdate', status='not_found').inc()
                    return Maintenance()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='MaintenanceUpdate', status='error').inc()
            return Maintenance()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='MaintenanceUpdate').dec()
        
def serve():
    # Start Prometheus HTTP server on port 8000
    start_http_server(8000)
    print("Prometheus metrics server started on port 8000...")
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    maintenance_service_pb2_grpc.add_MaintenanceServiceServicer_to_server(MaintenanceService(), server)
    server.add_insecure_port("[::]:50012")
    print("Maintenance service running on port 50012...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()