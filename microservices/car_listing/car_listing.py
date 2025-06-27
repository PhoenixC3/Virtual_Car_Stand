import logging
import os
import grpc
import psycopg2
from concurrent import futures
from prometheus_client import start_http_server, Counter, Summary, Histogram, Gauge

from services import car_listing_service_pb2_grpc
from services import car_listing_service_pb2

from google.protobuf import empty_pb2
from services.car_listing_service_pb2 import CarListing

from services.transaction_service_pb2_grpc import TransactionServiceStub
from services import transaction_service_pb2
from datetime import datetime

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Prometheus metrics
REQUEST_COUNT = Counter('car_listing_request_count', 'Total number of requests by endpoint', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('car_listing_request_latency_seconds', 'Request latency in seconds', ['endpoint'])
ACTIVE_REQUESTS = Gauge('car_listing_active_requests', 'Number of active requests', ['endpoint'])
DB_OPERATION_LATENCY = Summary('car_listing_db_operation_latency_seconds', 'Database operation latency', ['operation'])
TRANSACTION_LATENCY = Summary('car_listing_transaction_latency_seconds', 'Transaction service call latency')

class CarListingService(car_listing_service_pb2_grpc.CarListingServiceServicer):
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
        )
        self.cursor = self.conn.cursor()
        
        self.transaction_channel = grpc.insecure_channel("TransactionService:50010")
        self.transaction_stub = TransactionServiceStub(self.transaction_channel) 

    def CarlistingCreate(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='CarlistingCreate').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='CarlistingCreate').time():
                with DB_OPERATION_LATENCY.labels(operation='insert').time():
                    self.cursor.execute("SELECT setval('car_listing_listing_id_seq', (SELECT MAX(listing_id) FROM car_listing) + 1);")
                    self.cursor.execute(
                        """
                        INSERT INTO car_listing (listing_car_id, listing_user_id, listing_type, listing_description,
                                                 listing_posting_date, listing_sale_price, listing_promoted, listing_status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING listing_id
                        """,
                        (request.carListing.carId, request.carListing.userId, CarListing.TypeEnum.Name(request.carListing.type),
                         request.carListing.description, request.carListing.posting_date, request.carListing.sale_price,
                         request.carListing.promoted, CarListing.StatusEnum.Name(request.carListing.status) )
                    )
                    listing_id = self.cursor.fetchone()[0]
                    self.conn.commit()
                
                REQUEST_COUNT.labels(endpoint='CarlistingCreate', status='success').inc()
                return CarListing(
                    listingId=listing_id, carId=request.carListing.carId, userId=request.carListing.userId,
                    type=request.carListing.type, description=request.carListing.description,
                    posting_date=request.carListing.posting_date, sale_price=request.carListing.sale_price,
                    promoted=request.carListing.promoted, status=request.carListing.status
                )
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='CarlistingCreate', status='error').inc()
            return CarListing()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='CarlistingCreate').dec()

    def CarlistingReadOne(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='CarlistingReadOne').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='CarlistingReadOne').time():
                with DB_OPERATION_LATENCY.labels(operation='select').time():
                    self.cursor.execute(
                        "SELECT listing_id, listing_car_id, listing_user_id, listing_type, listing_description, "
                        "listing_posting_date, listing_sale_price, listing_promoted, listing_status FROM car_listing "
                        "WHERE listing_id = %s",
                        (request.listingId,)
                    )
                    listing = self.cursor.fetchone()
                
                if listing:
                    REQUEST_COUNT.labels(endpoint='CarlistingReadOne', status='success').inc()
                    return CarListing(
                            listingId=int(listing[0]),
                            carId=int(listing[1]),
                            userId=int(listing[2]),
                            type=CarListing.TypeEnum.Value(listing[3]),
                            description=listing[4] if listing[4] is not None else "",
                            posting_date=listing[5].isoformat() if listing[5] is not None else "",
                            sale_price=listing[6] if listing[6] is not None else 0.0,
                            promoted=listing[7] if listing[7] is not None else False,
                            status=CarListing.StatusEnum.Value(listing[8])
                        )
                else:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Car listing with ID {request.listingId} not found.")
                    REQUEST_COUNT.labels(endpoint='CarlistingReadOne', status='not_found').inc()
                    return CarListing()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='CarlistingReadOne', status='error').inc()
            return CarListing()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='CarlistingReadOne').dec()

    def CarlistingReadAll(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='CarlistingReadAll').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='CarlistingReadAll').time():
                with DB_OPERATION_LATENCY.labels(operation='select_all').time():
                    self.cursor.execute("SELECT * FROM car_listing LIMIT 1000")
                    rows = self.cursor.fetchall()

                carlistings = []
                for row in rows:
                    logging.info(f"Row data: {row}, Types: {[type(value) for value in row]}")
                    try:    
                        carlisting = CarListing(
                            listingId=int(row[0]),
                            carId=int(row[1]),
                            userId=int(row[2]),
                            type=CarListing.TypeEnum.Value(row[3]),
                            description=row[4] if row[4] is not None else "",
                            posting_date=row[5].isoformat() if row[5] is not None else "",
                            sale_price=row[6] if row[6] is not None else 0.0,
                            promoted=row[7] if row[7] is not None else False,
                            status=CarListing.StatusEnum.Value(row[8])
                        )
                        carlistings.append(carlisting)
                    except Exception as e:
                        logging.error(f"Error processing row {row}: {e}")
                        REQUEST_COUNT.labels(endpoint='CarlistingReadAll', status='row_error').inc()
                
                REQUEST_COUNT.labels(endpoint='CarlistingReadAll', status='success').inc()
                return car_listing_service_pb2.CarlistingReadAllResponse(data=carlistings)
        except Exception as e:
            logging.error(f"Error in CarlistingReadAll: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='CarlistingReadAll', status='error').inc()
            return car_listing_service_pb2.CarlistingReadAllResponse()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='CarlistingReadAll').dec()

    def CarlistingUpdate(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='CarlistingUpdate').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='CarlistingUpdate').time():
                with DB_OPERATION_LATENCY.labels(operation='select').time():
                    self.cursor.execute(
                        "SELECT listing_status FROM car_listing WHERE listing_id = %s",
                        (request.listingId,)
                    )
                    current_status_row = self.cursor.fetchone()
                
                if not current_status_row:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details("Car listing not found")
                    REQUEST_COUNT.labels(endpoint='CarlistingUpdate', status='not_found').inc()
                    return car_listing_service_pb2.CarListing()
                
                current_status = current_status_row[0]
                
                if hasattr(request.carListing.status, 'name'):
                    new_status = request.carListing.status.name
                else:
                    new_status = car_listing_service_pb2.CarListing.StatusEnum.Name(request.carListing.status)
                
                with DB_OPERATION_LATENCY.labels(operation='update').time():
                    self.cursor.execute(
                        """
                        UPDATE car_listing SET listing_car_id = %s, listing_user_id = %s, listing_type = %s,
                                        listing_description = %s, listing_posting_date = %s,
                                        listing_sale_price = %s, listing_promoted = %s, listing_status = %s
                        WHERE listing_id = %s RETURNING listing_id
                        """,
                        (request.carListing.carId, request.carListing.userId, request.carListing.type,
                        request.carListing.description, request.carListing.posting_date, request.carListing.sale_price,
                        request.carListing.promoted, new_status, request.listingId)
                    )
                    updated_listing_id = self.cursor.fetchone()
                
                if updated_listing_id:
                    self.conn.commit()
                    
                    logging.info(f"Updated car listing with ID: {updated_listing_id[0]}")
                    
                    # If status changed to SOLD, create a transaction
                    if current_status != "StatusEnum_SOLD" and new_status == "StatusEnum_SOLD":
                        try:
                            with TRANSACTION_LATENCY.time():
                                transaction = transaction_service_pb2.Transaction(
                                    buyerId=request.carListing.userId,
                                    carId=request.carListing.carId,
                                    type=request.carListing.type,  
                                    totalAmount=request.carListing.sale_price,
                                    status=1,
                                    transactionDate=datetime.now().isoformat(),
                                )
                                
                                transaction_request = transaction_service_pb2.TransactionsCreateRequest(
                                    transaction=transaction
                                )
                                
                                try:
                                    transaction_response = self.transaction_stub.TransactionsCreate(transaction_request)
                                    logging.info(f"Created transaction with ID: {transaction_response.transactionId}")
                                    REQUEST_COUNT.labels(endpoint='CarlistingUpdate_CreateTransaction', status='success').inc()
                                except grpc.RpcError as rpc_error:
                                    logging.error(f"Failed to create transaction: {rpc_error}")
                                    REQUEST_COUNT.labels(endpoint='CarlistingUpdate_CreateTransaction', status='error').inc()
                        
                        except Exception as e:
                            logging.error(f"Error creating transaction: {e}")
                            REQUEST_COUNT.labels(endpoint='CarlistingUpdate_CreateTransaction', status='error').inc()
                    
                    REQUEST_COUNT.labels(endpoint='CarlistingUpdate', status='success').inc()
                    return request.carListing
                else:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details("Car listing not found")
                    REQUEST_COUNT.labels(endpoint='CarlistingUpdate', status='not_found').inc()
                    return car_listing_service_pb2.CarListing()
        except Exception as e:
            logging.error(f"Error in CarlistingUpdate: {e}")
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='CarlistingUpdate', status='error').inc()
            return car_listing_service_pb2.CarListing()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='CarlistingUpdate').dec()
            
    def CarlistingDelete(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='CarlistingDelete').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='CarlistingDelete').time():
                with DB_OPERATION_LATENCY.labels(operation='delete').time():
                    self.cursor.execute("DELETE FROM car_listing WHERE listing_id = %s RETURNING listing_id", (request.listingId,))
                    deleted_listing_id = self.cursor.fetchone()
                    
                    if deleted_listing_id:
                        self.conn.commit()
                        logging.info(f"Deleted car listing with ID: {deleted_listing_id[0]}")
                        REQUEST_COUNT.labels(endpoint='CarlistingDelete', status='success').inc()
                        return empty_pb2.Empty()
                    else:
                        context.set_code(grpc.StatusCode.NOT_FOUND)
                        context.set_details(f"Car listing with ID {request.listingId} not found")
                        REQUEST_COUNT.labels(endpoint='CarlistingDelete', status='not_found').inc()
                        return empty_pb2.Empty()
        
        except Exception as e:
            logging.error(f"Error in CarlistingDelete: {e}")
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='CarlistingDelete', status='error').inc()
            return empty_pb2.Empty()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='CarlistingDelete').dec()


def serve():
    # Start Prometheus HTTP server on port 8000
    start_http_server(8000)
    print("Prometheus metrics server started on port 8000...")
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    car_listing_service_pb2_grpc.add_CarListingServiceServicer_to_server(CarListingService(), server)
    server.add_insecure_port("[::]:50009")
    print("Car Listing Service running on port 50009...")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
