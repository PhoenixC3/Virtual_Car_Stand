import pytest
from unittest.mock import Mock, patch
from services import car_service_pb2
from microservices.car.car import CarService

@pytest.fixture
def mock_db_connection():
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn, mock_cursor

@pytest.fixture
def mock_context():
    context = Mock()
    context.set_code = Mock()
    context.set_details = Mock()
    return context

@pytest.fixture
def car_service(mock_db_connection):
    with patch.dict('os.environ', {
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASS': 'test_pass'
    }):
        service = CarService()
        return service

def test_car_create_success(car_service, mock_db_connection, mock_context):
    """Basic unit test for car creation"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (1,)
    
    request = car_service_pb2.CarsCreateRequest(
        car=car_service_pb2.Car(
            year=2024,
            manufacturer="Toyota",
            model="Camry",
            condition="New",
            cylinders="4",
            fuel="Gasoline",
            odometer=0,
            transmission="Automatic",
            VIN="1HGCM82633A123456",
            drive="FWD",
            size="Midsize",
            type="Sedan",
            paint_color="Silver"
        )
    )
    
    response = car_service.CarsCreate(request, mock_context)
    
    assert response.carId == 1
    assert response.year == 2024
    assert response.manufacturer == "Toyota"
    assert response.model == "Camry"
    assert response.condition == "New"
    assert response.cylinders == "4"
    assert response.fuel == "Gasoline"
    assert response.odometer == 0
    assert response.transmission == "Automatic"
    assert response.VIN == "1HGCM82633A123456"
    assert response.drive == "FWD"
    assert response.size == "Midsize"
    assert response.type == "Sedan"
    assert response.paint_color == "Silver"

def test_car_creation_and_retrieval(car_service, mock_db_connection, mock_context):
    """Test interaction between create and read operations"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.side_effect = [
        (1,),
        (1, 2024, "Toyota", "Camry", "New", "4", "Gasoline", 0, "Automatic", "1HGCM82633A123456", "FWD", "Midsize", "Sedan", "Silver")
    ]
    
    # Create and then read car
    create_request = car_service_pb2.CarsCreateRequest(
        car=car_service_pb2.Car(
            year=2024,
            manufacturer="Toyota",
            model="Camry",
            condition="New",
            cylinders="4",
            fuel="Gasoline",
            odometer=0,
            transmission="Automatic",
            VIN="1HGCM82633A123456",
            drive="FWD",
            size="Midsize",
            type="Sedan",
            paint_color="Silver"
        )
    )
    created_car = car_service.CarsCreate(create_request, mock_context)
    read_request = car_service_pb2.CarsReadOneRequest(carId=created_car.carId)
    retrieved_car = car_service.CarsReadOne(read_request, mock_context)
    
    assert retrieved_car.carId == created_car.carId
    assert retrieved_car.year == created_car.year
    assert retrieved_car.manufacturer == created_car.manufacturer
    assert retrieved_car.model == created_car.model
    assert retrieved_car.condition == created_car.condition
    assert retrieved_car.cylinders == created_car.cylinders
    assert retrieved_car.fuel == created_car.fuel
    assert retrieved_car.odometer == created_car.odometer
    assert retrieved_car.transmission == created_car.transmission
    assert retrieved_car.VIN == created_car.VIN
    assert retrieved_car.drive == created_car.drive
    assert retrieved_car.size == created_car.size
    assert retrieved_car.type == created_car.type
    assert retrieved_car.paint_color == created_car.paint_color

def test_car_update(car_service, mock_db_connection, mock_context):
    """Test updating car details"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.side_effect = [
        (1,),
        (1,),
        (1, 2024, "Toyota", "Camry", "Used", "4", "Gasoline", 5000, "Automatic", "1HGCM82633A123456", "FWD", "Midsize", "Sedan", "Silver")
    ]
    
    # Create car
    create_request = car_service_pb2.CarsCreateRequest(
        car=car_service_pb2.Car(
            year=2024,
            manufacturer="Toyota",
            model="Camry",
            condition="New",
            cylinders="4",
            fuel="Gasoline",
            odometer=0,
            transmission="Automatic",
            VIN="1HGCM82633A123456",
            drive="FWD",
            size="Midsize",
            type="Sedan",
            paint_color="Silver"
        )
    )
    created_car = car_service.CarsCreate(create_request, mock_context)
    
    # Update car
    update_request = car_service_pb2.CarsUpdateRequest(
        carId=created_car.carId,
        car=car_service_pb2.Car(
            carId=created_car.carId,
            year=2024,
            manufacturer="Toyota",
            model="Camry",
            condition="Used",
            cylinders="4",
            fuel="Gasoline",
            odometer=5000,
            transmission="Automatic",
            VIN="1HGCM82633A123456",
            drive="FWD",
            size="Midsize",
            type="Sedan",
            paint_color="Silver"
        )
    )
    updated_car = car_service.CarsUpdate(update_request, mock_context)
    
    assert updated_car.carId == created_car.carId
    assert updated_car.condition == "Used"
    assert updated_car.odometer == 5000

def test_car_read_all(car_service, mock_db_connection, mock_context):
    """Test reading all cars"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchall.return_value = [
        (1, 2024, "Toyota", "Camry", "New", "4", "Gasoline", 0, "Automatic", "1HGCM82633A123456", "FWD", "Midsize", "Sedan", "Silver"),
        (2, 2023, "Honda", "Civic", "Used", "4", "Gasoline", 10000, "Automatic", "2HGCM82633B123456", "FWD", "Compact", "Sedan", "Blue")
    ]
    
    request = car_service_pb2.google_dot_protobuf_dot_empty__pb2.Empty()
    response = car_service.CarsReadAll(request, mock_context)
    
    assert len(response.data) == 2
    assert response.data[0].carId == 1
    assert response.data[0].manufacturer == "Toyota"
    assert response.data[1].carId == 2
    assert response.data[1].manufacturer == "Honda" 