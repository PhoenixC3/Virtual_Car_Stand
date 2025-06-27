import os
import grpc
import psycopg2
from concurrent import futures
from google.protobuf import empty_pb2
from prometheus_client import start_http_server, Counter, Summary, Histogram, Gauge
import logging

from services import car_service_pb2
from services import car_service_pb2_grpc
from services.car_service_pb2 import Car

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Prometheus metrics
REQUEST_COUNT = Counter('car_request_count', 'Total number of requests by endpoint', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('car_request_latency_seconds', 'Request latency in seconds', ['endpoint'])
ACTIVE_REQUESTS = Gauge('car_active_requests', 'Number of active requests', ['endpoint'])
DB_OPERATION_LATENCY = Summary('car_db_operation_latency_seconds', 'Database operation latency', ['operation'])

class CarService(car_service_pb2_grpc.CarServiceServicer):
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
        )
        self.cursor = self.conn.cursor()

    def CarsCreate(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='CarsCreate').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='CarsCreate').time():
                with DB_OPERATION_LATENCY.labels(operation='insert').time():
                    self.cursor.execute("SELECT setval('car_car_id_seq', (SELECT MAX(car_id) FROM car) + 1);")
                    self.cursor.execute(
                        """
                        INSERT INTO car (
                            car_year, car_manufacturer, car_model, car_condition, car_cylinders, 
                            car_fuel, car_odometer, car_transmission, car_vin, car_drive, 
                            car_size, car_type, car_paint_color
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING car_id
                        """,
                        (
                            request.car.year, request.car.manufacturer, request.car.model,
                            request.car.condition, request.car.cylinders, request.car.fuel,
                            request.car.odometer, request.car.transmission, request.car.VIN,
                            request.car.drive, request.car.size, request.car.type, request.car.paint_color
                        ),
                    )
                    car_id = self.cursor.fetchone()[0]
                    self.conn.commit()
                
                REQUEST_COUNT.labels(endpoint='CarsCreate', status='success').inc()
                return Car(
                    carId=car_id,
                    year=request.car.year,
                    manufacturer=request.car.manufacturer,
                    model=request.car.model,
                    condition=request.car.condition,
                    cylinders=request.car.cylinders,
                    fuel=request.car.fuel,
                    odometer=request.car.odometer,
                    transmission=request.car.transmission,
                    VIN=request.car.VIN,
                    drive=request.car.drive,
                    size=request.car.size,
                    type=request.car.type,
                    paint_color=request.car.paint_color,
                )
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='CarsCreate', status='error').inc()
            return Car()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='CarsCreate').dec()

    def CarsReadOne(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='CarsReadOne').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='CarsReadOne').time():
                with DB_OPERATION_LATENCY.labels(operation='select').time():
                    self.cursor.execute(
                        "SELECT * FROM car WHERE car_id = %s", (request.carId,)
                    )
                    car = self.cursor.fetchone()
                
                if car:
                    REQUEST_COUNT.labels(endpoint='CarsReadOne', status='success').inc()
                    return Car(
                        carId=car[0], year=car[1], manufacturer=car[2], model=car[3],
                        condition=car[4], cylinders=car[5], fuel=car[6], odometer=car[7],
                        transmission=car[8], VIN=car[9], drive=car[10], size=car[11],
                        type=car[12], paint_color=car[13]
                    )
                else:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Car with ID {request.carId} not found.")
                    REQUEST_COUNT.labels(endpoint='CarsReadOne', status='not_found').inc()
                    return Car()
                
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='CarsReadOne', status='error').inc()
            return Car()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='CarsReadOne').dec()

    def CarsReadAll(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='CarsReadAll').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='CarsReadAll').time():
                with DB_OPERATION_LATENCY.labels(operation='select_all').time():
                    self.cursor.execute("SELECT * FROM car LIMIT 1000")
                    rows = self.cursor.fetchall()

                cars = []
                for row in rows:
                    logging.info(f"Row data: {row}, Types: {[type(value) for value in row]}")
                    try:
                        car = Car(
                            carId=int(row[0]), year=int(row[1]), manufacturer=row[2], model=row[3],
                            condition=row[4], cylinders=row[5], fuel=row[6], odometer=int(row[7]),
                            transmission=row[8], VIN=row[9], drive=row[10], size=row[11],
                            type=row[12], paint_color=row[13]
                        )
                        cars.append(car)
                    except Exception as e:
                        logging.error(f"Error processing row {row}: {e}")
                        REQUEST_COUNT.labels(endpoint='CarsReadAll', status='row_error').inc()
                
                REQUEST_COUNT.labels(endpoint='CarsReadAll', status='success').inc()
                return car_service_pb2.CarsReadAllResponse(data=cars)
        except Exception as e:
            logging.error(f"Error in CarsReadAll: {e}")
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='CarsReadAll', status='error').inc()
            return car_service_pb2.CarsReadAllResponse()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='CarsReadAll').dec()

    def CarsUpdate(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='CarsUpdate').inc()
        
        if (request.carId != request.car.carId):
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("carId in path and body do not match")
            REQUEST_COUNT.labels(endpoint='CarsUpdate', status='invalid_argument').inc()
            ACTIVE_REQUESTS.labels(endpoint='CarsUpdate').dec()
            return Car()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='CarsUpdate').time():
                with DB_OPERATION_LATENCY.labels(operation='update').time():
                    self.cursor.execute(
                        """
                        UPDATE car SET 
                            car_year = %s, car_manufacturer = %s, car_model = %s, car_condition = %s, 
                            car_cylinders = %s, car_fuel = %s, car_odometer = %s, car_transmission = %s, 
                            car_vin = %s, car_drive = %s, car_size = %s, car_type = %s, car_paint_color = %s
                        WHERE car_id = %s RETURNING car_id
                        """,
                        (
                            request.car.year, request.car.manufacturer, request.car.model,
                            request.car.condition, request.car.cylinders, request.car.fuel,
                            request.car.odometer, request.car.transmission, request.car.VIN,
                            request.car.drive, request.car.size, request.car.type,
                            request.car.paint_color, request.carId
                        ),
                    )
                    updated_car_id = self.cursor.fetchone()
                
                if updated_car_id:
                    self.conn.commit()
                    REQUEST_COUNT.labels(endpoint='CarsUpdate', status='success').inc()
                    return request.car
                else:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details(f"Car with ID {request.carId} not found.")
                    REQUEST_COUNT.labels(endpoint='CarsUpdate', status='not_found').inc()
                    return Car()
                
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='CarsUpdate', status='error').inc()
            return Car()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='CarsUpdate').dec()

    def CarsDelete(self, request, context):
        ACTIVE_REQUESTS.labels(endpoint='CarsDelete').inc()
        
        try:
            with REQUEST_LATENCY.labels(endpoint='CarsDelete').time():
                with DB_OPERATION_LATENCY.labels(operation='delete').time():
                    self.cursor.execute("DELETE FROM car WHERE car_id = %s RETURNING car_id", (request.carId,))
                    deleted_car_id = self.cursor.fetchone()
                
                if deleted_car_id:
                    self.conn.commit()
                    REQUEST_COUNT.labels(endpoint='CarsDelete', status='success').inc()
                    return empty_pb2.Empty()
                else:
                    context.set_code(grpc.StatusCode.NOT_FOUND)
                    context.set_details("Car not found")
                    REQUEST_COUNT.labels(endpoint='CarsDelete', status='not_found').inc()
                    return empty_pb2.Empty()
        except psycopg2.Error as e:
            self.conn.rollback()
            context.set_details(str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            REQUEST_COUNT.labels(endpoint='CarsDelete', status='error').inc()
            return empty_pb2.Empty()
        finally:
            ACTIVE_REQUESTS.labels(endpoint='CarsDelete').dec()


def serve():
    # Start Prometheus HTTP server on port 8000
    start_http_server(8000)
    print("Prometheus metrics server started on port 8000...")
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    car_service_pb2_grpc.add_CarServiceServicer_to_server(CarService(), server)
    server.add_insecure_port("[::]:50008")
    print("Car service running on port 50008...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
