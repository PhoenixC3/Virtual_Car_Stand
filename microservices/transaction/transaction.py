import logging
import os
import grpc
import psycopg2
from concurrent import futures
from prometheus_client import start_http_server, Counter, Summary, Histogram, Gauge

from services import transaction_service_pb2_grpc
from services import transaction_service_pb2
from services.transaction_service_pb2 import Transaction
from google.protobuf import empty_pb2


DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Prometheus metrics
REQUEST_COUNT = Counter('transaction_request_count', 'Total number of requests by endpoint', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('transaction_request_latency_seconds', 'Request latency in seconds', ['endpoint'])
ACTIVE_REQUESTS = Gauge('transaction_active_requests', 'Number of active requests', ['endpoint'])
DB_OPERATION_LATENCY = Summary('transaction_db_operation_latency_seconds', 'Database operation latency', ['operation'])

class TransactionService(transaction_service_pb2_grpc.TransactionServiceServicer):
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
        )
        self.cursor = self.conn.cursor()

    def TransactionsCreate(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='TransactionsCreate').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='TransactionsCreate').time():
                with DB_OPERATION_LATENCY.labels(operation='insert').time():
                    self.cursor.execute(
                        """
                        INSERT INTO transaction (buyer_id, car_id, transaction_type, total_amount, transaction_status, transaction_date, end_date) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING transaction_id
                        """,
                        (
                            request.transaction.buyerId,
                            request.transaction.carId,
                            Transaction.TypeEnum.Name(request.transaction.type),
                            request.transaction.totalAmount,
                            Transaction.StatusEnum.Name(request.transaction.status),
                            request.transaction.transactionDate,
                            request.transaction.endDate if request.transaction.endDate else None,
                        ),
                    )
                    transaction_id = self.cursor.fetchone()[0]
                    self.conn.commit()
                
                REQUEST_COUNT.labels(endpoint='TransactionsCreate', status='success').inc()
                return Transaction(
                    transactionId=transaction_id,
                    buyerId=request.transaction.buyerId,
                    carId=request.transaction.carId,
                    type=request.transaction.type,
                    totalAmount=request.transaction.totalAmount,
                    status=request.transaction.status,
                    transactionDate=request.transaction.transactionDate,
                    endDate=request.transaction.endDate,
                )
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='TransactionsCreate', status='error').inc()
            return Transaction()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='TransactionsCreate').dec()

    def TransactionsReadOne(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='TransactionsReadOne').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='TransactionsReadOne').time():
                with DB_OPERATION_LATENCY.labels(operation='select').time():
                    self.cursor.execute(
                        """
                        SELECT transaction_id, buyer_id, car_id, transaction_type, total_amount, transaction_status, transaction_date, end_date 
                        FROM transaction WHERE transaction_id = %s
                        """,
                        (request.transactionId,),
                    )
                    transaction = self.cursor.fetchone()
                
                if transaction:
                    REQUEST_COUNT.labels(endpoint='TransactionsReadOne', status='success').inc()
                    return Transaction(
                        transactionId=int(transaction[0]),
                        buyerId=int(transaction[1]),
                        carId=int(transaction[2]),
                        type=Transaction.TypeEnum.Value(transaction[3]),
                        totalAmount=transaction[4] if transaction[4] is not None else 0.0,
                        status=Transaction.StatusEnum.Value(transaction[5]),
                        transactionDate=transaction[6].isoformat() if transaction[6] else "",
                        endDate=transaction[7].isoformat() if transaction[7] else ""
                    )
                else:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Transaction with ID {request.transactionId} not found.")
                    REQUEST_COUNT.labels(endpoint='TransactionsReadOne', status='not_found').inc()
                    return Transaction()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='TransactionsReadOne', status='error').inc()
            return Transaction()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='TransactionsReadOne').dec()

    def TransactionsReadAll(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='TransactionsReadAll').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='TransactionsReadAll').time():
                with DB_OPERATION_LATENCY.labels(operation='select_all').time():
                    self.cursor.execute(
                        """
                        SELECT * FROM transaction
                        """
                    )
                    rows = self.cursor.fetchall()

                transactions = []
                for row in rows:
                    logging.info(f"Row data: {row}, Types: {[type(value) for value in row]}")
                    try:
                        transaction = Transaction(
                            transactionId=int(row[0]),
                            buyerId=int(row[1]),
                            carId=int(row[2]),
                            type=Transaction.TypeEnum.Value(row[3]),
                            totalAmount=row[4] if row[4] is not None else 0.0,
                            status=Transaction.StatusEnum.Value(row[5]),
                            transactionDate=row[6].isoformat() if row[6] else "",
                            endDate=row[7].isoformat() if row[7] else ""
                        )
                        transactions.append(transaction)
                    except Exception as e:
                        logging.info(f"Error processing row: {row}, Error: {e}")
                        REQUEST_COUNT.labels(endpoint='TransactionsReadAll', status='row_error').inc()
                
                REQUEST_COUNT.labels(endpoint='TransactionsReadAll', status='success').inc()
                return transaction_service_pb2.TransactionsReadAllResponse(data=transactions)
        except Exception as e:
            logging.error(f"Error in TransactionsReadAll: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='TransactionsReadAll', status='error').inc()
            return transaction_service_pb2.TransactionsReadAllResponse()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='TransactionsReadAll').dec()

    def TransactionsUpdate(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='TransactionsUpdate').inc()
        
        if (request.transactionId != request.transaction.transactionId):
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Transaction ID mismatch")
            REQUEST_COUNT.labels(endpoint='TransactionsUpdate', status='invalid_argument').inc()
            ACTIVE_REQUESTS.labels(endpoint='TransactionsUpdate').dec()
            return Transaction()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='TransactionsUpdate').time():
                with DB_OPERATION_LATENCY.labels(operation='update').time():
                    self.cursor.execute(
                        """
                        UPDATE transaction SET buyer_id = %s, car_id = %s, transaction_type = %s, total_amount = %s, transaction_status = %s, transaction_date = %s, end_date = %s
                        WHERE transaction_id = %s RETURNING transaction_id
                        """,
                        (
                            request.transaction.buyerId,
                            request.transaction.carId,
                            Transaction.TypeEnum.Name(request.transaction.type),
                            request.transaction.totalAmount,
                            Transaction.StatusEnum.Name(request.transaction.status),
                            request.transaction.transactionDate,
                            request.transaction.endDate if request.transaction.endDate else None,
                            request.transactionId,
                        ),
                    )
                    updated_transaction_id = self.cursor.fetchone()
                
                if updated_transaction_id:
                    self.conn.commit()
                    REQUEST_COUNT.labels(endpoint='TransactionsUpdate', status='success').inc()
                    return Transaction(
                        transactionId=request.transactionId,
                        buyerId=request.transaction.buyerId,
                        carId=request.transaction.carId,
                        type=request.transaction.type,
                        totalAmount=request.transaction.totalAmount,
                        status=request.transaction.status,
                        transactionDate=request.transaction.transactionDate,
                        endDate=request.transaction.endDate,
                    )
                else:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Transaction with ID {request.transactionId} not found.")
                    REQUEST_COUNT.labels(endpoint='TransactionsUpdate', status='not_found').inc()
                    return Transaction()     
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='TransactionsUpdate', status='error').inc()
            return Transaction()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='TransactionsUpdate').dec()

    def TransactionsDelete(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='TransactionsDelete').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='TransactionsDelete').time():
                with DB_OPERATION_LATENCY.labels(operation='delete').time():
                    self.cursor.execute(
                        "DELETE FROM transaction WHERE transaction_id = %s RETURNING transaction_id",
                        (request.transactionId,),
                    )
                    deleted_transaction_id = self.cursor.fetchone()
                
                if deleted_transaction_id:
                    self.conn.commit()
                    REQUEST_COUNT.labels(endpoint='TransactionsDelete', status='success').inc()
                    return empty_pb2.Empty()
                else:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Transaction with ID {request.transactionId} not found.")
                    REQUEST_COUNT.labels(endpoint='TransactionsDelete', status='not_found').inc()
                    return empty_pb2.Empty()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='TransactionsDelete', status='error').inc()
            return empty_pb2.Empty()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='TransactionsDelete').dec()

def serve():
    # Start Prometheus HTTP server on port 8000
    start_http_server(8000)
    print("Prometheus metrics server started on port 8000...")
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    transaction_service_pb2_grpc.add_TransactionServiceServicer_to_server(TransactionService(), server)
    server.add_insecure_port("[::]:50010")
    print("Transaction service running on port 50010...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
