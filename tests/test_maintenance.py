import pytest
from unittest.mock import Mock, patch
from services import maintenance_service_pb2
from microservices.maintenance.maintenance import MaintenanceService

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
def maintenance_service(mock_db_connection):
    with patch.dict('os.environ', {
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASS': 'test_pass'
    }):
        service = MaintenanceService()
        return service

def test_maintenance_create_success(maintenance_service, mock_db_connection, mock_context):
    """Basic unit test for maintenance creation"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (1,)
    
    request = maintenance_service_pb2.MaintenanceCreateRequest(
        maintenance=maintenance_service_pb2.Maintenance(
            maintenanceCarId=1,
            maintenanceType=maintenance_service_pb2.Maintenance.MaintenanceTypeEnum.MaintenanceTypeEnum_BASIC,
            maintenanceStatus=maintenance_service_pb2.Maintenance.MaintenanceStatusEnum.MaintenanceStatusEnum_ONGOING,
            maintenanceClientNotes="Regular checkup",
            maintenanceStaffNotes="Oil change needed",
            maintenanceCost=150.00,
            maintenanceStartDate="2024-03-20T10:00:00Z",
            maintenanceEndDate="2024-03-20T12:00:00Z"
        )
    )
    
    response = maintenance_service.MaintenanceCreate(request, mock_context)
    
    assert response.maintenanceId == 1
    assert response.maintenanceCarId == 1
    assert response.maintenanceType == maintenance_service_pb2.Maintenance.MaintenanceTypeEnum.MaintenanceTypeEnum_BASIC
    assert response.maintenanceStatus == maintenance_service_pb2.Maintenance.MaintenanceStatusEnum.MaintenanceStatusEnum_ONGOING
    assert response.maintenanceClientNotes == "Regular checkup"
    assert response.maintenanceStaffNotes == "Oil change needed"
    assert response.maintenanceCost == 150.00
    assert response.maintenanceStartDate == "2024-03-20T10:00:00Z"
    assert response.maintenanceEndDate == "2024-03-20T12:00:00Z"

def test_full_maintenance_creation(maintenance_service, mock_db_connection, mock_context):
    """Test creating a full maintenance record"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.return_value = (1,)
    
    request = maintenance_service_pb2.MaintenanceCreateRequest(
        maintenance=maintenance_service_pb2.Maintenance(
            maintenanceCarId=1,
            maintenanceType=maintenance_service_pb2.Maintenance.MaintenanceTypeEnum.MaintenanceTypeEnum_FULL,
            maintenanceStatus=maintenance_service_pb2.Maintenance.MaintenanceStatusEnum.MaintenanceStatusEnum_ONGOING,
            maintenanceClientNotes="Complete overhaul requested",
            maintenanceStaffNotes="Full service including engine check",
            maintenanceCost=500.00,
            maintenanceStartDate="2024-03-20T09:00:00Z",
            maintenanceEndDate="2024-03-21T17:00:00Z"
        )
    )
    
    response = maintenance_service.MaintenanceCreate(request, mock_context)
    
    assert response.maintenanceId == 1
    assert response.maintenanceType == maintenance_service_pb2.Maintenance.MaintenanceTypeEnum.MaintenanceTypeEnum_FULL
    assert response.maintenanceCost == 500.00
    assert response.maintenanceStatus == maintenance_service_pb2.Maintenance.MaintenanceStatusEnum.MaintenanceStatusEnum_ONGOING

def test_maintenance_completion(maintenance_service, mock_db_connection, mock_context):
    """Test completing a maintenance record"""
    mock_conn, mock_cursor = mock_db_connection
    mock_cursor.fetchone.side_effect = [
        (1,),
        (1, 1, 1, 2, "Regular checkup", "Completed", 150.00, "2024-03-20T10:00:00Z", "2024-03-20T11:30:00Z")
    ]
    
    # Create maintenance
    create_request = maintenance_service_pb2.MaintenanceCreateRequest(
        maintenance=maintenance_service_pb2.Maintenance(
            maintenanceCarId=1,
            maintenanceType=maintenance_service_pb2.Maintenance.MaintenanceTypeEnum.MaintenanceTypeEnum_BASIC,
            maintenanceStatus=maintenance_service_pb2.Maintenance.MaintenanceStatusEnum.MaintenanceStatusEnum_ONGOING,
            maintenanceClientNotes="Regular checkup",
            maintenanceStaffNotes="In progress",
            maintenanceCost=150.00,
            maintenanceStartDate="2024-03-20T10:00:00Z",
            maintenanceEndDate="2024-03-20T12:00:00Z"
        )
    )
    created_maintenance = maintenance_service.MaintenanceCreate(create_request, mock_context)
    
    # Update maintenance status to finished
    update_request = maintenance_service_pb2.MaintenanceUpdateRequest(
        maintenanceId=created_maintenance.maintenanceId,
        maintenance=maintenance_service_pb2.Maintenance(
            maintenanceId=created_maintenance.maintenanceId,
            maintenanceCarId=1,
            maintenanceType=maintenance_service_pb2.Maintenance.MaintenanceTypeEnum.MaintenanceTypeEnum_BASIC,
            maintenanceStatus=maintenance_service_pb2.Maintenance.MaintenanceStatusEnum.MaintenanceStatusEnum_FINISHED,
            maintenanceClientNotes="Regular checkup",
            maintenanceStaffNotes="Completed",
            maintenanceCost=150.00,
            maintenanceStartDate="2024-03-20T10:00:00Z",
            maintenanceEndDate="2024-03-20T11:30:00Z"
        )
    )
    updated_maintenance = maintenance_service.MaintenanceUpdate(update_request, mock_context)
    
    assert updated_maintenance.maintenanceId == created_maintenance.maintenanceId
    assert updated_maintenance.maintenanceStatus == maintenance_service_pb2.Maintenance.MaintenanceStatusEnum.MaintenanceStatusEnum_FINISHED
    assert updated_maintenance.maintenanceStaffNotes == "Completed"
    assert updated_maintenance.maintenanceEndDate == "2024-03-20T11:30:00Z" 