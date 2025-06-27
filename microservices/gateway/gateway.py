import os
import json
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
from urllib.parse import urlencode
from dotenv import load_dotenv
import time
from prometheus_client import Counter, Summary, Histogram, Gauge, start_http_server
import threading

import grpc
from google.protobuf.empty_pb2 import Empty
from google.protobuf.json_format import MessageToDict, ParseDict
from services.car_service_pb2 import (
    Car, CarsCreateRequest, CarsDeleteRequest,
    CarsReadOneRequest, CarsUpdateRequest
)
from services.car_service_pb2_grpc import CarServiceStub

from services.user_service_pb2 import (
    User, UsersCreateRequest, UsersDeleteRequest,
    UsersReadOneRequest, UsersUpdateRequest
)
from services.user_service_pb2_grpc import UserServiceStub

from services.maintenance_service_pb2 import (
    Maintenance, MaintenanceCreateRequest, MaintenanceDeleteRequest, 
    MaintenanceReadOneRequest, MaintenanceUpdateRequest
)
from services.maintenance_service_pb2_grpc import MaintenanceServiceStub

from services.inspection_service_pb2 import (
    Inspection, InspectionCreateRequest, InspectionDeleteRequest,
    InspectionReadOneRequest, InspectionUpdateRequest
)
from services.inspection_service_pb2_grpc import InspectionServiceStub

from services.transaction_service_pb2 import (
    Transaction, TransactionsCreateRequest, TransactionsDeleteRequest,
    TransactionsReadOneRequest, TransactionsUpdateRequest
)
from services.transaction_service_pb2_grpc import TransactionServiceStub

from services.car_listing_service_pb2 import (
    CarListing, CarlistingCreateRequest, CarlistingDeleteRequest,
    CarlistingReadOneRequest, CarlistingUpdateRequest
)
from services.car_listing_service_pb2_grpc import CarListingServiceStub

from services.meeting_service_pb2 import (
    Meeting, MeetingsCreateRequest, MeetingsDeleteRequest,
    MeetingsReadOneRequest, MeetingsUpdateRequest
)
from services.meeting_service_pb2_grpc import MeetingServiceStub

from auth import requires_auth, requires_permission, AuthError

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))
app.config["SESSION_TYPE"] = "filesystem"

# For running behind a proxy like Nginx in Kubernetes
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Auth0 Config
AUTH0_CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID", "")
AUTH0_CLIENT_SECRET = os.environ.get("AUTH0_CLIENT_SECRET", "")
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN", "")
AUTH0_CALLBACK_URL = os.environ.get("AUTH0_CALLBACK_URL", "")
AUTH0_AUDIENCE = os.environ.get("AUTH0_AUDIENCE", "")

# Error handler for Auth0 errors
@app.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response

# OAuth setup
oauth = OAuth(app)
auth0 = oauth.register(
    'auth0',
    client_id=AUTH0_CLIENT_ID,
    client_secret=AUTH0_CLIENT_SECRET,
    api_base_url=f"https://{AUTH0_DOMAIN}",
    access_token_url=f"https://{AUTH0_DOMAIN}/oauth/token",
    authorize_url=f"https://{AUTH0_DOMAIN}/authorize",
    jwks_uri=f"https://{AUTH0_DOMAIN}/.well-known/jwks.json",
    client_kwargs={
        'scope': 'openid profile email permissions',
    },
)

# Prometheus metrics
REQUEST_COUNT = Counter('gateway_http_requests_total', 'Total HTTP requests count', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('gateway_request_latency_seconds', 'Request latency in seconds', ['method', 'endpoint'])
GRPC_REQUEST_LATENCY = Summary('gateway_grpc_request_latency_seconds', 'gRPC request latency in seconds', ['service', 'method'])
ACTIVE_REQUESTS = Gauge('gateway_active_requests', 'Number of active HTTP requests', ['method', 'endpoint'])

# Start Prometheus HTTP server on a separate thread
def start_metrics_server():
    start_http_server(8000)
    print("Prometheus metrics server started on port 8000...")

threading.Thread(target=start_metrics_server).start()

# Request monitoring middleware
@app.before_request
def before_request():
    request.start_time = time.time()
    endpoint = request.endpoint if request.endpoint else 'unknown'
    ACTIVE_REQUESTS.labels(method=request.method, endpoint=endpoint).inc()

@app.after_request
def after_request(response):
    endpoint = request.endpoint if request.endpoint else 'unknown'
    resp_time = time.time() - request.start_time
    REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(resp_time)
    REQUEST_COUNT.labels(method=request.method, endpoint=endpoint, status=response.status_code).inc()
    ACTIVE_REQUESTS.labels(method=request.method, endpoint=endpoint).dec()
    return response

MAX_MESSAGE_LENGTH = 16 * 1024 * 1024  

# Set up gRPC channels and clients for each service
CAR_CHANNEL = grpc.insecure_channel(
    "car-service:50008",
    options=[("grpc.max_receive_message_length", MAX_MESSAGE_LENGTH)]
)
CAR_CLIENT = CarServiceStub(CAR_CHANNEL)

USER_CHANNEL = grpc.insecure_channel("user-service:50007")
USER_CLIENT = UserServiceStub(USER_CHANNEL)

MAINTENANCE_CHANNEL = grpc.insecure_channel("maintenance-service:50012")
MAINTENANCE_CLIENT = MaintenanceServiceStub(MAINTENANCE_CHANNEL)

INSPECTION_CHANNEL = grpc.insecure_channel("inspection-service:50011")
INSPECTION_CLIENT = InspectionServiceStub(INSPECTION_CHANNEL)

TRANSACTION_CHANNEL = grpc.insecure_channel("transaction-service:50010")
TRANSACTION_CLIENT = TransactionServiceStub(TRANSACTION_CHANNEL)

CARLISTING_CHANNEL = grpc.insecure_channel(
    "car-listing-service:50009",
    options=[("grpc.max_receive_message_length", MAX_MESSAGE_LENGTH)]
)
CARLISTING_CLIENT = CarListingServiceStub(CARLISTING_CHANNEL)

MEETING_CHANNEL = grpc.insecure_channel("meeting-service:50015")
MEETING_CLIENT = MeetingServiceStub(MEETING_CHANNEL)

# Helper function to measure gRPC call latency
def timed_grpc_call(service, method, call_fn, *args, **kwargs):
    with GRPC_REQUEST_LATENCY.labels(service=service, method=method).time():
        try:
            result = call_fn(*args, **kwargs)
            return result
        except Exception as e:
            raise e

# Auth routes
@app.route("/")
def index():
    if 'profile' in session:
        return redirect('/dashboard')
    else:
        auth_url = url_for('login')
        return render_template('login.html', auth_url=auth_url)

@app.route("/login")
def login():
    return auth0.authorize_redirect(
        redirect_uri=AUTH0_CALLBACK_URL,
        audience=AUTH0_AUDIENCE
    )

@app.route("/callback")
def callback_handling():
    # Get authorization code
    token = auth0.authorize_access_token()
    
    # Get userinfo
    resp = auth0.get('userinfo')
    userinfo = resp.json()
    
    # Store user info in session
    session['jwt_payload'] = userinfo
    session['profile'] = {
        'user_id': userinfo['sub'],
        'name': userinfo.get('name', ''),
        'picture': userinfo.get('picture', ''),
        'email': userinfo.get('email', '')
    }
    
    # Store the access token in the session for API calls
    session['access_token'] = token['access_token']
    
    # Create or update user in our database
    try:
        # First check if user exists
        request_msg = UsersReadOneRequest(userId=0)  # Placeholder ID, we'll search by email
        
        # We need to get all users and find by email (not optimal, but works for demo)
        all_users_request = Empty()
        all_users_response = USER_CLIENT.UsersReadAll(all_users_request)
        
        user_exists = False
        user_id = None
        
        for user in all_users_response.data:
            if user.email == userinfo.get('email'):
                user_exists = True
                user_id = user.userId
                break
        
        if not user_exists:
            # Create new user
            name_parts = userinfo.get('name', '').split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            user = User(
                firstName=first_name,
                lastName=last_name,
                email=userinfo.get('email')
            )
            request_msg = UsersCreateRequest(user=user)
            response = USER_CLIENT.UsersCreate(request_msg)
            
            # Clear session and force login after registration
            session.clear()
            return redirect(url_for('login'))
        else:
            # Update existing user
            name_parts = userinfo.get('name', '').split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            user = User(
                userId=user_id,
                firstName=first_name,
                lastName=last_name,
                email=userinfo.get('email')
            )
            request_msg = UsersUpdateRequest(userId=user_id, user=user)
            response = USER_CLIENT.UsersUpdate(request_msg)
    
    except grpc.RpcError as e:
        # Log error but continue
        print(f"Error syncing user with database: {str(e)}")
    
    return redirect('/dashboard')

@app.route("/dashboard")
@requires_auth
@requires_permission('read:dashboard')
def dashboard():
    if 'profile' not in session:
        return redirect('/')
    
    userinfo = session.get('profile')
    userinfo_json = session.get('jwt_payload')
    userinfo_pretty = json.dumps(userinfo_json, indent=4)
    
    return render_template(
        'dashboard.html',
        userinfo=userinfo,
        userinfo_pretty=userinfo_pretty
    )

@app.route("/logout")
def logout():
    session.clear()
    params = {
        'returnTo': url_for('index', _external=True),
        'client_id': AUTH0_CLIENT_ID
    }
    return redirect(auth0.api_base_url + '/v2/logout?' + urlencode(params))

# Car Service Routes
@app.route("/api/cars", methods=["GET"])
def get_all_cars():
    try:
        request = Empty()
        response = timed_grpc_call('car', 'CarsReadAll', CAR_CLIENT.CarsReadAll, request)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/cars/<int:car_id>", methods=["GET"])
def get_car(car_id):
    try:
        request = CarsReadOneRequest(carId=car_id)
        response = timed_grpc_call('car', 'CarsReadOne', CAR_CLIENT.CarsReadOne, request)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Car not found"}), 404
        return jsonify({"error": str(e)}), 500

@app.route("/api/cars", methods=["POST"])
@requires_auth
@requires_permission('create:car')
def create_car():
    try:
        car_data = request.json
        car = ParseDict(car_data, Car())
        request_msg = CarsCreateRequest(car=car)
        response = timed_grpc_call('car', 'CarsCreate', CAR_CLIENT.CarsCreate, request_msg)
        return jsonify(MessageToDict(response)), 201
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            return jsonify({"error": "Invalid input"}), 400
        return jsonify({"error": str(e)}), 500

@app.route("/api/cars/<int:car_id>", methods=["PUT"])
@requires_auth
@requires_permission('update:car')
def update_car(car_id):
    try:
        car_data = request.json
        car = ParseDict(car_data, Car())
        request_msg = CarsUpdateRequest(carId=car_id, car=car)
        response = timed_grpc_call('car', 'CarsUpdate', CAR_CLIENT.CarsUpdate, request_msg)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Car not found"}), 404
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            return jsonify({"error": "Invalid input"}), 400
        return jsonify({"error": str(e)}), 500

@app.route("/api/cars/<int:car_id>", methods=["DELETE"])
@requires_auth
@requires_permission('delete:car')
def delete_car(car_id):
    try:
        request_msg = CarsDeleteRequest(carId=car_id)
        timed_grpc_call('car', 'CarsDelete', CAR_CLIENT.CarsDelete, request_msg)
        return "", 204
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Car not found"}), 404
        return jsonify({"error": str(e)}), 500

# User Service Routes 
@app.route("/api/users", methods=["GET"])
def get_all_users():
    try:
        request = Empty()
        response = timed_grpc_call('user', 'UsersReadAll', USER_CLIENT.UsersReadAll, request)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    try:
        request = UsersReadOneRequest(userId=user_id)
        response = timed_grpc_call('user', 'UsersReadOne', USER_CLIENT.UsersReadOne, request)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"error": str(e)}), 500

@app.route("/api/users", methods=["POST"])
@requires_auth
@requires_permission('create:user')
def create_user():
    try:
        user_data = request.json
        user = ParseDict(user_data, User())
        request_msg = UsersCreateRequest(user=user)
        response = timed_grpc_call('user', 'UsersCreate', USER_CLIENT.UsersCreate, request_msg)
        return jsonify(MessageToDict(response)), 201
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            return jsonify({"error": "Invalid input"}), 400
        return jsonify({"error": str(e)}), 500

@app.route("/api/users/<int:user_id>", methods=["PUT"])
@requires_auth
@requires_permission('update:user')
def update_user(user_id):
    try:
        user_data = request.json
        user = ParseDict(user_data, User())
        request_msg = UsersUpdateRequest(userId=user_id, user=user)
        response = timed_grpc_call('user', 'UsersUpdate', USER_CLIENT.UsersUpdate, request_msg)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "User not found"}), 404
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            return jsonify({"error": "Invalid input"}), 400
        return jsonify({"error": str(e)}), 500

@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@requires_auth
@requires_permission('delete:user')
def delete_user(user_id):
    try:
        request_msg = UsersDeleteRequest(userId=user_id)
        timed_grpc_call('user', 'UsersDelete', USER_CLIENT.UsersDelete, request_msg)
        return "", 204
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"error": str(e)}), 500

# Maintenance Service Routes
@app.route("/api/maintenances", methods=["GET"])
def get_all_maintenances():
    try:
        request = Empty()
        response = timed_grpc_call('maintenance', 'MaintenanceReadAll', MAINTENANCE_CLIENT.MaintenanceReadAll, request)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/maintenances/<int:maintenance_id>", methods=["GET"])
def get_maintenance(maintenance_id):
    try:
        request = MaintenanceReadOneRequest(maintenanceId=maintenance_id)
        response = timed_grpc_call('maintenance', 'MaintenanceReadOne', MAINTENANCE_CLIENT.MaintenanceReadOne, request)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Maintenance not found"}), 404
        return jsonify({"error": str(e)}), 500

@app.route("/api/maintenances", methods=["POST"])
@requires_auth
@requires_permission('create:maintenance')
def create_maintenance():
    try:
        maintenance_data = request.json
        maintenance = ParseDict(maintenance_data, Maintenance())
        request_msg = MaintenanceCreateRequest(maintenance=maintenance)
        response = timed_grpc_call('maintenance', 'MaintenanceCreate', MAINTENANCE_CLIENT.MaintenanceCreate, request_msg)
        return jsonify(MessageToDict(response)), 201
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            return jsonify({"error": "Invalid input"}), 400
        return jsonify({"error": str(e)}), 500

@app.route("/api/maintenances/<int:maintenance_id>", methods=["PUT"])
@requires_auth
@requires_permission('update:maintenance')
def update_maintenance(maintenance_id):
    try:
        maintenance_data = request.json
        maintenance = ParseDict(maintenance_data, Maintenance())
        request_msg = MaintenanceUpdateRequest(maintenanceId=maintenance_id, maintenance=maintenance)
        response = timed_grpc_call('maintenance', 'MaintenanceUpdate', MAINTENANCE_CLIENT.MaintenanceUpdate, request_msg)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Maintenance not found"}), 404
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            return jsonify({"error": "Invalid input"}), 400
        return jsonify({"error": str(e)}), 500

@app.route("/api/maintenances/<int:maintenance_id>", methods=["DELETE"])
@requires_auth
@requires_permission('delete:maintenance')
def delete_maintenance(maintenance_id):
    try:
        request_msg = MaintenanceDeleteRequest(maintenanceId=maintenance_id)
        timed_grpc_call('maintenance', 'MaintenanceDelete', MAINTENANCE_CLIENT.MaintenanceDelete, request_msg)
        return "", 204
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Maintenance not found"}), 404
        return jsonify({"error": str(e)}), 500

# Inspection Service Routes
@app.route("/api/inspections", methods=["GET"])
def get_all_inspections():
    try:
        request = Empty()
        response = timed_grpc_call('inspection', 'InspectionReadAll', INSPECTION_CLIENT.InspectionReadAll, request)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/inspections/<int:inspection_id>", methods=["GET"])
def get_inspection(inspection_id):
    try:
        request = InspectionReadOneRequest(inspectionId=inspection_id)
        response = timed_grpc_call('inspection', 'InspectionReadOne', INSPECTION_CLIENT.InspectionReadOne, request)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Inspection not found"}), 404
        return jsonify({"error": str(e)}), 500

@app.route("/api/inspections", methods=["POST"])
@requires_auth
@requires_permission('create:inspection')
def create_inspection():
    try:
        inspection_data = request.json
        inspection = ParseDict(inspection_data, Inspection())
        request_msg = InspectionCreateRequest(inspection=inspection)
        response = timed_grpc_call('inspection', 'InspectionCreate', INSPECTION_CLIENT.InspectionCreate, request_msg)
        return jsonify(MessageToDict(response)), 201
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            return jsonify({"error": "Invalid input"}), 400
        return jsonify({"error": str(e)}), 500

@app.route("/api/inspections/<int:inspection_id>", methods=["PUT"])
@requires_auth
@requires_permission('update:inspection')
def update_inspection(inspection_id):
    try:
        inspection_data = request.json
        inspection = ParseDict(inspection_data, Inspection())
        request_msg = InspectionUpdateRequest(inspectionId=inspection_id, inspection=inspection)
        response = timed_grpc_call('inspection', 'InspectionUpdate', INSPECTION_CLIENT.InspectionUpdate, request_msg)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Inspection not found"}), 404
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            return jsonify({"error": "Invalid input"}), 400
        return jsonify({"error": str(e)}), 500

@app.route("/api/inspections/<int:inspection_id>", methods=["DELETE"])
@requires_auth
@requires_permission('delete:inspection')
def delete_inspection(inspection_id):
    try:
        request_msg = InspectionDeleteRequest(inspectionId=inspection_id)
        timed_grpc_call('inspection', 'InspectionDelete', INSPECTION_CLIENT.InspectionDelete, request_msg)
        return "", 204
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Inspection not found"}), 404
        return jsonify({"error": str(e)}), 500

# Transaction Service Routes
@app.route("/api/transactions", methods=["GET"])
def get_all_transactions():
    try:
        request = Empty()
        response = timed_grpc_call('transaction', 'TransactionsReadAll', TRANSACTION_CLIENT.TransactionsReadAll, request)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/transactions/<int:transaction_id>", methods=["GET"])
def get_transaction(transaction_id):
    try:
        request = TransactionsReadOneRequest(transactionId=transaction_id)
        response = timed_grpc_call('transaction', 'TransactionsReadOne', TRANSACTION_CLIENT.TransactionsReadOne, request)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Transaction not found"}), 404
        return jsonify({"error": str(e)}), 500

@app.route("/api/transactions", methods=["POST"])
@requires_auth
@requires_permission('create:transaction')
def create_transaction():
    try:
        transaction_data = request.json
        transaction = ParseDict(transaction_data, Transaction())
        request_msg = TransactionsCreateRequest(transaction=transaction)
        response = timed_grpc_call('transaction', 'TransactionsCreate', TRANSACTION_CLIENT.TransactionsCreate, request_msg)
        return jsonify(MessageToDict(response)), 201
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            return jsonify({"error": "Invalid input"}), 400
        return jsonify({"error": str(e)}), 500

@app.route("/api/transactions/<int:transaction_id>", methods=["PUT"])
@requires_auth
@requires_permission('update:transaction')
def update_transaction(transaction_id):
    try:
        transaction_data = request.json
        transaction = ParseDict(transaction_data, Transaction())
        transaction.transactionId = transaction_id  
        request_msg = TransactionsUpdateRequest(transactionId=transaction_id, transaction=transaction)
        response = timed_grpc_call('transaction', 'TransactionsUpdate', TRANSACTION_CLIENT.TransactionsUpdate, request_msg)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Transaction not found"}), 404
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            return jsonify({"error": "Invalid input"}), 400
        return jsonify({"error": str(e)}), 500

@app.route("/api/transactions/<int:transaction_id>", methods=["DELETE"])
@requires_auth
@requires_permission('delete:transaction')
def delete_transaction(transaction_id):
    try:
        request_msg = TransactionsDeleteRequest(transactionId=transaction_id)
        timed_grpc_call('transaction', 'TransactionsDelete', TRANSACTION_CLIENT.TransactionsDelete, request_msg)
        return "", 204
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Transaction not found"}), 404
        return jsonify({"error": str(e)}), 500

# Car Listing Service Routes
@app.route("/api/carlistings", methods=["GET"])
def get_all_carlistings():
    try:
        request = Empty()
        response = timed_grpc_call('carlisting', 'CarlistingReadAll', CARLISTING_CLIENT.CarlistingReadAll, request)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/carlistings/<int:listing_id>", methods=["GET"])
def get_carlisting(listing_id):
    try:
        request = CarlistingReadOneRequest(listingId=listing_id)
        response = timed_grpc_call('carlisting', 'CarlistingReadOne', CARLISTING_CLIENT.CarlistingReadOne, request)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Car listing not found"}), 404
        return jsonify({"error": str(e)}), 500

@app.route("/api/carlistings", methods=["POST"])
@requires_auth
@requires_permission('create:carlisting')
def create_carlisting():
    try:
        carlisting_data = request.json
        carlisting = ParseDict(carlisting_data, CarListing())
        request_msg = CarlistingCreateRequest(carListing=carlisting)
        response = timed_grpc_call('carlisting', 'CarlistingCreate', CARLISTING_CLIENT.CarlistingCreate, request_msg)
        return jsonify(MessageToDict(response)), 201
    except grpc.RpcError as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/carlistings/<int:listing_id>", methods=["PUT"])
@requires_auth
@requires_permission('update:carlisting')
def update_carlisting(listing_id):
    try:
        carlisting_data = request.json
        carlisting = ParseDict(carlisting_data, CarListing())
        carlisting.listingId = listing_id
        request_msg = CarlistingUpdateRequest(listingId=listing_id, carListing=carlisting)
        response = timed_grpc_call('carlisting', 'CarlistingUpdate', CARLISTING_CLIENT.CarlistingUpdate, request_msg)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Car listing not found"}), 404
        return jsonify({"error": str(e)}), 500

@app.route("/api/carlistings/<int:listing_id>", methods=["DELETE"])
@requires_auth
@requires_permission('delete:carlisting')
def delete_carlisting(listing_id):
    try:
        request = CarlistingDeleteRequest(listingId=listing_id)
        timed_grpc_call('carlisting', 'CarlistingDelete', CARLISTING_CLIENT.CarlistingDelete, request)
        return "", 204
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Car listing not found"}), 404
        return jsonify({"error": str(e)}), 500

# Meeting Service Routes
@app.route("/api/meetings", methods=["GET"])
def get_all_meetings():
    try:
        request = Empty()
        response = timed_grpc_call('meeting', 'MeetingsReadAll', MEETING_CLIENT.MeetingsReadAll, request)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/meetings/<int:meeting_id>", methods=["GET"])
def get_meeting(meeting_id):
    try:
        request = MeetingsReadOneRequest(meetingId=meeting_id)
        response = timed_grpc_call('meeting', 'MeetingsReadOne', MEETING_CLIENT.MeetingsReadOne, request)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Meeting not found"}), 404
        return jsonify({"error": str(e)}), 500

@app.route("/api/meetings", methods=["POST"])
@requires_auth
@requires_permission('create:meeting')
def create_meeting():
    try:
        meeting_data = request.json
        meeting = ParseDict(meeting_data, Meeting())
        request_msg = MeetingsCreateRequest(meeting=meeting)
        response = timed_grpc_call('meeting', 'MeetingsCreate', MEETING_CLIENT.MeetingsCreate, request_msg)
        return jsonify(MessageToDict(response)), 201
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            return jsonify({"error": "Invalid input"}), 400
        return jsonify({"error": str(e)}), 500

@app.route("/api/meetings/<int:meeting_id>", methods=["PUT"])
@requires_auth
@requires_permission('update:meeting')
def update_meeting(meeting_id):
    try:
        meeting_data = request.json
        meeting = ParseDict(meeting_data, Meeting())
        meeting.meetingId = meeting_id
        request_msg = MeetingsUpdateRequest(meetingId=meeting_id, meeting=meeting)
        response = timed_grpc_call('meeting', 'MeetingsUpdate', MEETING_CLIENT.MeetingsUpdate, request_msg)
        return jsonify(MessageToDict(response))
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Meeting not found"}), 404
        if e.code() == grpc.StatusCode.INVALID_ARGUMENT:
            return jsonify({"error": "Invalid input"}), 400
        return jsonify({"error": str(e)}), 500

@app.route("/api/meetings/<int:meeting_id>", methods=["DELETE"])
@requires_auth
@requires_permission('delete:meeting')
def delete_meeting(meeting_id):
    try:
        request_msg = MeetingsDeleteRequest(meetingId=meeting_id)
        timed_grpc_call('meeting', 'MeetingsDelete', MEETING_CLIENT.MeetingsDelete, request_msg)
        return "", 204
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            return jsonify({"error": "Meeting not found"}), 404
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health_check():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=50000)