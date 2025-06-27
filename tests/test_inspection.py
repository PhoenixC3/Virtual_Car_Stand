import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from services import inspection_service_pb2
from microservices.inspection.inspection import InspectionService

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
def inspection_service(mock_db_connection):
    with patch.dict('os.environ', {
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASS': 'test_pass'
    }):
        service = InspectionService()
        return service

def test_inspection_create_success(inspection_service, mock_db_connection, mock_context):
    """Basic unit test for inspection creation"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (1,)
    
    request = inspection_service_pb2.InspectionCreateRequest(
        inspection=inspection_service_pb2.Inspection(
            inspectionCarId=1,
            inspectionStatus=inspection_service_pb2.Inspection.InspectionStatusEnum.InspectionStatusEnum_ONGOING,
            inspectionClientNotes="Client requested full inspection",
            inspectionStaffNotes="Initial inspection started",
            inspectionCost=150.00,
            inspectionStartDate="2024-03-20T10:00:00Z",
            inspectionEndDate=""
        )
    )
    
    response = inspection_service.InspectionCreate(request, mock_context)
    
    assert response.inspectionId == 1
    assert response.inspectionCarId == 1
    assert response.inspectionStatus == inspection_service_pb2.Inspection.InspectionStatusEnum.InspectionStatusEnum_ONGOING
    assert response.inspectionClientNotes == "Client requested full inspection"
    assert response.inspectionStaffNotes == "Initial inspection started"
    assert response.inspectionCost == 150.00
    assert response.inspectionStartDate == "2024-03-20T10:00:00Z"
    assert response.inspectionEndDate == ""

def test_inspection_creation_and_retrieval(inspection_service, mock_db_connection, mock_context):
    """Test interaction between create and read operations"""
    mock_conn, mock_cursor = mock_db_connection
    start_date = datetime(2024, 3, 20, 10, 0, 0)
    mock_cursor.fetchone.side_effect = [
        (1,),
        (1, 1, "InspectionStatusEnum_ONGOING", "Client requested full inspection", "Initial inspection started", 150.00, start_date, None)
    ]
    
    # Create and then read inspection
    create_request = inspection_service_pb2.InspectionCreateRequest(
        inspection=inspection_service_pb2.Inspection(
            inspectionCarId=1,
            inspectionStatus=inspection_service_pb2.Inspection.InspectionStatusEnum.InspectionStatusEnum_ONGOING,
            inspectionClientNotes="Client requested full inspection",
            inspectionStaffNotes="Initial inspection started",
            inspectionCost=150.00,
            inspectionStartDate=start_date.isoformat(),
            inspectionEndDate=""
        )
    )
    created_inspection = inspection_service.InspectionCreate(create_request, mock_context)
    read_request = inspection_service_pb2.InspectionReadOneRequest(inspectionId=created_inspection.inspectionId)
    retrieved_inspection = inspection_service.InspectionReadOne(read_request, mock_context)
    
    assert retrieved_inspection.inspectionId == created_inspection.inspectionId
    assert retrieved_inspection.inspectionCarId == created_inspection.inspectionCarId
    assert retrieved_inspection.inspectionStatus == created_inspection.inspectionStatus
    assert retrieved_inspection.inspectionClientNotes == created_inspection.inspectionClientNotes
    assert retrieved_inspection.inspectionStaffNotes == created_inspection.inspectionStaffNotes
    assert retrieved_inspection.inspectionCost == created_inspection.inspectionCost
    assert retrieved_inspection.inspectionStartDate == created_inspection.inspectionStartDate

def test_inspection_completion(inspection_service, mock_db_connection, mock_context):
    """Test completing an inspection"""
    mock_conn, mock_cursor = mock_db_connection
    start_date = datetime(2024, 3, 20, 10, 0, 0)
    end_date = datetime(2024, 3, 20, 11, 30, 0)
    mock_cursor.fetchone.side_effect = [
        (1,),
        (1,),
        (1, 1, "InspectionStatusEnum_FINISHED", "Client requested full inspection", "Inspection completed", 150.00, start_date, end_date)
    ]
    
    # Create inspection
    create_request = inspection_service_pb2.InspectionCreateRequest(
        inspection=inspection_service_pb2.Inspection(
            inspectionCarId=1,
            inspectionStatus=inspection_service_pb2.Inspection.InspectionStatusEnum.InspectionStatusEnum_ONGOING,
            inspectionClientNotes="Client requested full inspection",
            inspectionStaffNotes="Initial inspection started",
            inspectionCost=150.00,
            inspectionStartDate=start_date.isoformat(),
            inspectionEndDate=""
        )
    )
    created_inspection = inspection_service.InspectionCreate(create_request, mock_context)
    
    # Update inspection to completed
    update_request = inspection_service_pb2.InspectionUpdateRequest(
        inspectionId=created_inspection.inspectionId,
        inspection=inspection_service_pb2.Inspection(
            inspectionId=created_inspection.inspectionId,
            inspectionCarId=1,
            inspectionStatus=inspection_service_pb2.Inspection.InspectionStatusEnum.InspectionStatusEnum_FINISHED,
            inspectionClientNotes="Client requested full inspection",
            inspectionStaffNotes="Inspection completed",
            inspectionCost=150.00,
            inspectionStartDate=start_date.isoformat(),
            inspectionEndDate=end_date.isoformat()
        )
    )
    updated_inspection = inspection_service.InspectionUpdate(update_request, mock_context)
    
    assert updated_inspection.inspectionId == created_inspection.inspectionId
    assert updated_inspection.inspectionStatus == inspection_service_pb2.Inspection.InspectionStatusEnum.InspectionStatusEnum_FINISHED
    assert updated_inspection.inspectionStaffNotes == "Inspection completed"
    assert updated_inspection.inspectionEndDate == end_date.isoformat() 