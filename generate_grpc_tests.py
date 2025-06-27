import os
import subprocess
from pathlib import Path

def generate_grpc():
    # Get the project root directory
    root_dir = Path(__file__).parent
    
    # Create services directory if it doesn't exist
    services_dir = root_dir / "services"
    services_dir.mkdir(exist_ok=True)
    
    # Generate gRPC code
    protos_dir = root_dir / "microservices" / "protobufs"
    
    # List of all services and their dependencies
    services = [
        {
            "service": "user_service.proto",
            "models": ["user.proto"]
        },
        {
            "service": "car_service.proto",
            "models": ["car.proto"]
        },
        {
            "service": "car_listing_service.proto",
            "models": ["car_listing.proto", "transaction.proto"]
        },
        {
            "service": "inspection_service.proto",
            "models": ["inspection.proto"]
        },
        {
            "service": "maintenance_service.proto",
            "models": ["maintenance.proto"]
        },
        {
            "service": "meeting_service.proto",
            "models": ["meeting.proto"]
        },
        {
            "service": "transaction_service.proto",
            "models": ["transaction.proto"]
        }
    ]
    
    # Generate code for each service
    for service_info in services:
        service_proto = protos_dir / "services" / service_info["service"]
        model_protos = [protos_dir / "models" / model for model in service_info["models"]]
        
        # Generate gRPC code
        subprocess.run([
            "python", "-m", "grpc_tools.protoc",
            f"-I{protos_dir}",
            f"--python_out={root_dir}",
            f"--grpc_python_out={root_dir}",
            str(service_proto),
            *[str(model) for model in model_protos]
        ])
        
        print(f"Generated code for {service_info['service']}")

if __name__ == "__main__":
    generate_grpc() 