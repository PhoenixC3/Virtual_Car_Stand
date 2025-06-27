import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from services import car_listing_service_pb2
from microservices.car_listing.car_listing import CarListingService

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
def mock_transaction_stub():
    with patch('services.transaction_service_pb2_grpc.TransactionServiceStub') as mock_stub:
        mock_stub.TransactionsCreate.return_value = Mock(transactionId=1)
        yield mock_stub

@pytest.fixture
def car_listing_service(mock_db_connection, mock_transaction_stub):
    with patch.dict('os.environ', {
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASS': 'test_pass'
    }):
        service = CarListingService()
        service.transaction_stub = mock_transaction_stub
        return service

def test_car_listing_create_success(car_listing_service, mock_db_connection, mock_context):
    """Basic unit test for car listing creation"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (1,)
    
    request = car_listing_service_pb2.CarlistingCreateRequest(
        carListing=car_listing_service_pb2.CarListing(
            carId=1,
            userId=1,
            type=car_listing_service_pb2.CarListing.TypeEnum.TypeEnum_BUY,
            description="Has wheels, nice",
            posting_date="2024-03-20T10:00:00Z",
            sale_price=25000.00,
            promoted=False,
            status=car_listing_service_pb2.CarListing.StatusEnum.StatusEnum_AVAILABLE
        )
    )
    
    response = car_listing_service.CarlistingCreate(request, mock_context)
    
    assert response.listingId == 1
    assert response.carId == 1
    assert response.userId == 1
    assert response.type == car_listing_service_pb2.CarListing.TypeEnum.TypeEnum_BUY
    assert response.description == "Has wheels, nice"
    assert response.posting_date == "2024-03-20T10:00:00Z"
    assert response.sale_price == 25000.00
    assert response.promoted == False
    assert response.status == car_listing_service_pb2.CarListing.StatusEnum.StatusEnum_AVAILABLE

def test_car_listing_creation_and_retrieval(car_listing_service, mock_db_connection, mock_context):
    """Test interaction between create and read operations"""
    mock_conn, mock_cursor = mock_db_connection
    posting_date = datetime(2024, 3, 20, 10, 0, 0)
    mock_cursor.fetchone.side_effect = [
        (1,),
        (1, 1, 1, "TypeEnum_BUY", "Has wheels, nice", posting_date, 25000.00, False, "StatusEnum_AVAILABLE")
    ]
    
    # Create and then read car listing
    create_request = car_listing_service_pb2.CarlistingCreateRequest(
        carListing=car_listing_service_pb2.CarListing(
            carId=1,
            userId=1,
            type=car_listing_service_pb2.CarListing.TypeEnum.TypeEnum_BUY,
            description="Has wheels, nice",
            posting_date=posting_date.isoformat(),
            sale_price=25000.00,
            promoted=False,
            status=car_listing_service_pb2.CarListing.StatusEnum.StatusEnum_AVAILABLE
        )
    )
    created_listing = car_listing_service.CarlistingCreate(create_request, mock_context)
    read_request = car_listing_service_pb2.CarlistingReadOneRequest(listingId=created_listing.listingId)
    retrieved_listing = car_listing_service.CarlistingReadOne(read_request, mock_context)
    
    assert retrieved_listing.listingId == created_listing.listingId
    assert retrieved_listing.carId == created_listing.carId
    assert retrieved_listing.userId == created_listing.userId
    assert retrieved_listing.type == created_listing.type
    assert retrieved_listing.description == created_listing.description
    assert retrieved_listing.sale_price == created_listing.sale_price
    assert retrieved_listing.promoted == created_listing.promoted
    assert retrieved_listing.status == created_listing.status

def test_car_listing_mark_as_sold(car_listing_service, mock_db_connection, mock_context, mock_transaction_stub):
    """Test marking a car listing as sold and creating a transaction"""
    mock_conn, mock_cursor = mock_db_connection
    posting_date = datetime(2024, 3, 20, 10, 0, 0)
    mock_cursor.fetchone.side_effect = [
        (1,),
        ("StatusEnum_AVAILABLE",),
        (1,),
        (1, 1, 1, "TypeEnum_BUY", "Has wheels, nice", posting_date, 25000.00, False, "StatusEnum_SOLD")
    ]
    
    # Create car listing
    create_request = car_listing_service_pb2.CarlistingCreateRequest(
        carListing=car_listing_service_pb2.CarListing(
            carId=1,
            userId=1,
            type=car_listing_service_pb2.CarListing.TypeEnum.TypeEnum_BUY,
            description="Has wheels, nice",
            posting_date=posting_date.isoformat(),
            sale_price=25000.00,
            promoted=False,
            status=car_listing_service_pb2.CarListing.StatusEnum.StatusEnum_AVAILABLE
        )
    )
    created_listing = car_listing_service.CarlistingCreate(create_request, mock_context)
    
    # Update car listing to sold
    update_request = car_listing_service_pb2.CarlistingUpdateRequest(
        listingId=created_listing.listingId,
        carListing=car_listing_service_pb2.CarListing(
            listingId=created_listing.listingId,
            carId=1,
            userId=1,
            type=car_listing_service_pb2.CarListing.TypeEnum.TypeEnum_BUY,
            description="Has wheels, nice",
            posting_date=posting_date.isoformat(),
            sale_price=25000.00,
            promoted=False,
            status=car_listing_service_pb2.CarListing.StatusEnum.StatusEnum_SOLD
        )
    )
    updated_listing = car_listing_service.CarlistingUpdate(update_request, mock_context)
    
    assert updated_listing.listingId == created_listing.listingId
    assert updated_listing.status == car_listing_service_pb2.CarListing.StatusEnum.StatusEnum_SOLD
    mock_transaction_stub.TransactionsCreate.assert_called_once() 