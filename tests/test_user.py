import pytest
from unittest.mock import Mock, patch
from services import user_service_pb2
from microservices.user.user import UserService

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
def user_service(mock_db_connection):
    with patch.dict('os.environ', {
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASS': 'test_pass'
    }):
        service = UserService()
        return service

def test_users_create_success(user_service, mock_db_connection, mock_context):
    """Basic unit test for user creation"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (1,)
    
    request = user_service_pb2.UsersCreateRequest(
        user=user_service_pb2.User(
            firstName="John",
            lastName="Fortnite",
            email="johnfortnite@example.com"
        )
    )
    
    response = user_service.UsersCreate(request, mock_context)
    
    assert response.userId == 1
    assert response.firstName == "John"
    assert response.lastName == "Fortnite"
    assert response.email == "johnfortnite@example.com"

def test_user_creation_and_retrieval(user_service, mock_db_connection, mock_context):
    """Test interaction between create and read operations"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.side_effect = [(1,), (1, "John", "Fortnite", "johnfortnite@example.com")]
    
    # Create and then read user
    create_request = user_service_pb2.UsersCreateRequest(
        user=user_service_pb2.User(
            firstName="John",
            lastName="Fortnite",
            email="johnfortnite@example.com"
        )
    )
    created_user = user_service.UsersCreate(create_request, mock_context)
    read_request = user_service_pb2.UsersReadOneRequest(userId=created_user.userId)
    retrieved_user = user_service.UsersReadOne(read_request, mock_context)
    
    assert retrieved_user.userId == created_user.userId
    assert retrieved_user.firstName == created_user.firstName

def test_user_deletion(user_service, mock_db_connection, mock_context):
    """Test deleting a user"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.side_effect = [
        (1,),
        (1,),
        None
    ]
    
    # Create user
    create_request = user_service_pb2.UsersCreateRequest(
        user=user_service_pb2.User(
            firstName="John",
            lastName="Fortnite",
            email="johnfortnite@example.com"
        )
    )
    created_user = user_service.UsersCreate(create_request, mock_context)
    
    # Delete user
    delete_request = user_service_pb2.UsersDeleteRequest(userId=created_user.userId)
    user_service.UsersDelete(delete_request, mock_context)
    
    # Try to read deleted user
    read_request = user_service_pb2.UsersReadOneRequest(userId=created_user.userId)
    deleted_user = user_service.UsersReadOne(read_request, mock_context)
    
    # Verify user was deleted
    assert deleted_user.userId == 0 
    assert mock_context.set_code.called
    assert mock_context.set_details.called