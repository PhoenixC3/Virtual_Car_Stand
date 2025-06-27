import pytest
from unittest.mock import Mock, patch
from services import meeting_service_pb2
from microservices.meeting.meeting import MeetingService

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
def meeting_service(mock_db_connection):
    with patch.dict('os.environ', {
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASS': 'test_pass'
    }):
        service = MeetingService()
        return service

def test_meetings_create_success(meeting_service, mock_db_connection, mock_context):
    """Basic unit test for meeting creation"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (1,)
    
    request = meeting_service_pb2.MeetingsCreateRequest(
        meeting=meeting_service_pb2.Meeting(
            clientId=1,
            scheduleDate="2024-03-20T10:00:00Z",
            status=meeting_service_pb2.Meeting.StatusEnum.StatusEnum_SCHEDULED
        )
    )
    
    response = meeting_service.MeetingsCreate(request, mock_context)
    
    assert response.meetingId == 1
    assert response.clientId == 1
    assert response.scheduleDate == "2024-03-20T10:00:00Z"
    assert response.status == meeting_service_pb2.Meeting.StatusEnum.StatusEnum_SCHEDULED

def test_meeting_status_update(meeting_service, mock_db_connection, mock_context):
    """Test updating meeting status"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.side_effect = [
        (1,),
        (1, 1, "2024-03-20T10:00:00Z", "StatusEnum_COMPLETED")
    ]
    
    # Create meeting
    create_request = meeting_service_pb2.MeetingsCreateRequest(
        meeting=meeting_service_pb2.Meeting(
            clientId=1,
            scheduleDate="2024-03-20T10:00:00Z",
            status=meeting_service_pb2.Meeting.StatusEnum.StatusEnum_SCHEDULED
        )
    )
    created_meeting = meeting_service.MeetingsCreate(create_request, mock_context)
    
    # Update meeting status
    update_request = meeting_service_pb2.MeetingsUpdateRequest(
        meetingId=created_meeting.meetingId,
        meeting=meeting_service_pb2.Meeting(
            meetingId=created_meeting.meetingId,
            clientId=1,
            scheduleDate="2024-03-20T10:00:00Z",
            status=meeting_service_pb2.Meeting.StatusEnum.StatusEnum_COMPLETED
        )
    )
    updated_meeting = meeting_service.MeetingsUpdate(update_request, mock_context)
    
    assert updated_meeting.meetingId == created_meeting.meetingId
    assert updated_meeting.clientId == created_meeting.clientId
    assert updated_meeting.scheduleDate == created_meeting.scheduleDate
    assert updated_meeting.status == meeting_service_pb2.Meeting.StatusEnum.StatusEnum_COMPLETED

def test_meeting_cancellation(meeting_service, mock_db_connection, mock_context):
    """Test canceling a meeting"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (1,)
    
    request = meeting_service_pb2.MeetingsCreateRequest(
        meeting=meeting_service_pb2.Meeting(
            clientId=1,
            scheduleDate="2024-03-20T10:00:00Z",
            status=meeting_service_pb2.Meeting.StatusEnum.StatusEnum_CANCELED
        )
    )
    
    response = meeting_service.MeetingsCreate(request, mock_context)
    
    assert response.meetingId == 1
    assert response.status == meeting_service_pb2.Meeting.StatusEnum.StatusEnum_CANCELED 