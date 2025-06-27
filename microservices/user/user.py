import os
import grpc
import psycopg2
from concurrent import futures
from google.protobuf import empty_pb2
from prometheus_client import start_http_server, Counter, Summary, Histogram, Gauge

from services import user_service_pb2_grpc
from services import user_service_pb2
from services.user_service_pb2 import User

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Prometheus metrics
REQUEST_COUNT = Counter('user_request_count', 'Total number of requests by endpoint', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('user_request_latency_seconds', 'Request latency in seconds', ['endpoint'])
ACTIVE_REQUESTS = Gauge('user_active_requests', 'Number of active requests', ['endpoint'])
DB_OPERATION_LATENCY = Summary('user_db_operation_latency_seconds', 'Database operation latency', ['operation'])

class UserService(user_service_pb2_grpc.UserServiceServicer):
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
        )
        self.cursor = self.conn.cursor()

    # Create a new user -- seems to be working
    def UsersCreate(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='UsersCreate').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='UsersCreate').time():
                with DB_OPERATION_LATENCY.labels(operation='insert').time():
                    self.cursor.execute(
                        "INSERT INTO users (first_name, last_name, email) VALUES (%s, %s, %s) RETURNING user_id",
                        (request.user.firstName, request.user.lastName, request.user.email),
                    )
                    user_id = self.cursor.fetchone()[0]
                    self.conn.commit()
                
                REQUEST_COUNT.labels(endpoint='UsersCreate', status='success').inc()
                return User(
                    userId=user_id,
                    firstName=request.user.firstName,
                    lastName=request.user.lastName,
                    email=request.user.email,
                )
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='UsersCreate', status='error').inc()
            return User()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='UsersCreate').dec()

    #  Reads 1 user -- seems to be working
    def UsersReadOne(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='UsersReadOne').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='UsersReadOne').time():
                with DB_OPERATION_LATENCY.labels(operation='select').time():
                    self.cursor.execute("SELECT * FROM users WHERE user_id = %s", (request.userId,))
                    user = self.cursor.fetchone()
                
                if user:
                    REQUEST_COUNT.labels(endpoint='UsersReadOne', status='success').inc()
                    return User(userId=user[0], firstName=user[1], lastName=user[2], email=user[3])
                else:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details("User not found")
                    REQUEST_COUNT.labels(endpoint='UsersReadOne', status='not_found').inc()
                    return User()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='UsersReadOne', status='error').inc()
            return User()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='UsersReadOne').dec()

    def UsersReadAll(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='UsersReadAll').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='UsersReadAll').time():
                with DB_OPERATION_LATENCY.labels(operation='select_all').time():
                    self.cursor.execute("SELECT * FROM users")
                    users = [
                        User(userId=row[0], firstName=row[1], lastName=row[2], email=row[3])
                        for row in self.cursor.fetchall()
                    ]
                
                REQUEST_COUNT.labels(endpoint='UsersReadAll', status='success').inc()
                return user_service_pb2.UsersReadAllResponse(data=users)
        except Exception as e:
            REQUEST_COUNT.labels(endpoint='UsersReadAll', status='error').inc()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            return user_service_pb2.UsersReadAllResponse()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='UsersReadAll').dec()

    def UsersUpdate(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='UsersUpdate').inc()
        
        if (request.userId != request.user.userId):
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("User ID in path and body do not match")
            REQUEST_COUNT.labels(endpoint='UsersUpdate', status='invalid_argument').inc()
            ACTIVE_REQUESTS.labels(endpoint='UsersUpdate').dec()
            return User()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='UsersUpdate').time():
                with DB_OPERATION_LATENCY.labels(operation='update').time():
                    self.cursor.execute(
                        "UPDATE users SET first_name = %s, last_name = %s, email = %s WHERE user_id = %s RETURNING user_id",
                        (request.user.firstName, request.user.lastName, request.user.email, request.userId),
                    )
                    updated_user_id = self.cursor.fetchone()
                
                if updated_user_id:
                    self.conn.commit()
                    REQUEST_COUNT.labels(endpoint='UsersUpdate', status='success').inc()
                    return User(
                        userId=request.userId,
                        firstName=request.user.firstName,
                        lastName=request.user.lastName,
                        email=request.user.email,
                    )
                else:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"User with ID {request.userId} not found.")
                    REQUEST_COUNT.labels(endpoint='UsersUpdate', status='not_found').inc()
                    return User()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='UsersUpdate', status='error').inc()
            return User()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='UsersUpdate').dec()

    def UsersDelete(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='UsersDelete').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='UsersDelete').time():
                with DB_OPERATION_LATENCY.labels(operation='delete').time():
                    self.cursor.execute("DELETE FROM users WHERE user_id = %s RETURNING user_id", (request.userId,))
                    deleted_user_id = self.cursor.fetchone()
                
                if deleted_user_id:
                    self.conn.commit()
                    REQUEST_COUNT.labels(endpoint='UsersDelete', status='success').inc()
                    return empty_pb2.Empty()
                else:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details("User not found")
                    REQUEST_COUNT.labels(endpoint='UsersDelete', status='not_found').inc()
                    return empty_pb2.Empty()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='UsersDelete', status='error').inc()
            return empty_pb2.Empty()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='UsersDelete').dec()

def serve():
    # Start Prometheus HTTP server on port 8000
    start_http_server(8000)
    print("Prometheus metrics server started on port 8000...")
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    user_service_pb2_grpc.add_UserServiceServicer_to_server(UserService(), server)
    server.add_insecure_port("[::]:50007")
    print("User service running on port 50007...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()