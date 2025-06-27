import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from services import transaction_service_pb2
from microservices.transaction.transaction import TransactionService

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
def transaction_service(mock_db_connection):
    with patch.dict('os.environ', {
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASS': 'test_pass'
    }):
        service = TransactionService()
        return service

def test_transactions_create_success(transaction_service, mock_db_connection, mock_context):
    """Basic unit test for transaction creation"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (1,)
    
    request = transaction_service_pb2.TransactionsCreateRequest(
        transaction=transaction_service_pb2.Transaction(
            buyerId=1,
            carId=1,
            type=transaction_service_pb2.Transaction.TypeEnum.TypeEnum_BUY,
            totalAmount=25000.00,
            status=transaction_service_pb2.Transaction.StatusEnum.StatusEnum_PENDING,
            transactionDate="2024-03-20T10:00:00Z"
        )
    )
    
    response = transaction_service.TransactionsCreate(request, mock_context)
    
    assert response.transactionId == 1
    assert response.buyerId == 1
    assert response.carId == 1
    assert response.type == transaction_service_pb2.Transaction.TypeEnum.TypeEnum_BUY
    assert response.totalAmount == 25000.00
    assert response.status == transaction_service_pb2.Transaction.StatusEnum.StatusEnum_PENDING
    assert response.transactionDate == "2024-03-20T10:00:00Z"

def test_transaction_creation_and_retrieval(transaction_service, mock_db_connection, mock_context):
    """Test interaction between create and read operations"""
    mock_conn, mock_cursor = mock_db_connection
    transaction_date = datetime(2024, 3, 20, 10, 0, 0)
    mock_cursor.fetchone.side_effect = [
        (1,),
        (1, 1, 1, "TypeEnum_BUY", 25000.00, "StatusEnum_PENDING", transaction_date, None)
    ]
    
    # Create and then read transaction
    create_request = transaction_service_pb2.TransactionsCreateRequest(
        transaction=transaction_service_pb2.Transaction(
            buyerId=1,
            carId=1,
            type=transaction_service_pb2.Transaction.TypeEnum.TypeEnum_BUY,
            totalAmount=25000.00,
            status=transaction_service_pb2.Transaction.StatusEnum.StatusEnum_PENDING,
            transactionDate=transaction_date.isoformat(),
            endDate=""
        )
    )
    created_transaction = transaction_service.TransactionsCreate(create_request, mock_context)
    read_request = transaction_service_pb2.TransactionsReadOneRequest(transactionId=created_transaction.transactionId)
    retrieved_transaction = transaction_service.TransactionsReadOne(read_request, mock_context)
    
    assert retrieved_transaction.transactionId == created_transaction.transactionId
    assert retrieved_transaction.buyerId == created_transaction.buyerId
    assert retrieved_transaction.carId == created_transaction.carId
    assert retrieved_transaction.type == created_transaction.type
    assert retrieved_transaction.totalAmount == created_transaction.totalAmount
    assert retrieved_transaction.status == created_transaction.status
    assert retrieved_transaction.transactionDate == created_transaction.transactionDate

def test_rental_transaction_creation(transaction_service, mock_db_connection, mock_context):
    """Test creation of a rental transaction with end date"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (1,)
    
    request = transaction_service_pb2.TransactionsCreateRequest(
        transaction=transaction_service_pb2.Transaction(
            buyerId=1,
            carId=1,
            type=transaction_service_pb2.Transaction.TypeEnum.TypeEnum_RENT,
            totalAmount=500.00,
            status=transaction_service_pb2.Transaction.StatusEnum.StatusEnum_PENDING,
            transactionDate="2024-03-20T10:00:00Z",
            endDate="2024-04-20T10:00:00Z"
        )
    )
    
    response = transaction_service.TransactionsCreate(request, mock_context)
    
    assert response.transactionId == 1
    assert response.type == transaction_service_pb2.Transaction.TypeEnum.TypeEnum_RENT
    assert response.endDate == "2024-04-20T10:00:00Z" 