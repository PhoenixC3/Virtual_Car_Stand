# May need to run with elevated privileges
# Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# Variables
$DOCKER_USERNAME = "<docker-username>"
$DOCKER_TOKEN = "<docker-token>"
$IMAGE_TAG = "latest"

$DB_FULL_IMAGE_NAME = "${DOCKER_USERNAME}/database:${IMAGE_TAG}"
$DOCKER_COMPOSE_FILE_PATH = "./microservices/docker-compose.yml"

# Authenticate to Docker Hub
Write-Host "Authenticating to Docker Hub..."
$loginResult = echo $DOCKER_TOKEN | docker login -u $DOCKER_USERNAME --password-stdin
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker login failed. Please check your credentials."
    exit 1
}

# Build and push the database image
Write-Host "Building database image..."
docker build -t $DB_FULL_IMAGE_NAME ./databases
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to build database image. Exiting."
    exit 1
}

Write-Host "Pushing database image to Docker Hub..."
docker push $DB_FULL_IMAGE_NAME
if ($LASTEXITCODE -eq 0) {
    Write-Host "Database image pushed successfully: $DB_FULL_IMAGE_NAME"
} else {
    Write-Host "Error pushing database image. Exiting."
    exit 1
}

# Get all services from docker-compose
Write-Host "Retrieving services from docker-compose..."
$services = docker-compose -f $DOCKER_COMPOSE_FILE_PATH config --services
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to retrieve services from docker-compose. Exiting."
    exit 1
}

# Build and push each service
foreach ($service in $services) {
    Write-Host "Building and pushing $service..."

    # Build the service
    docker-compose -f $DOCKER_COMPOSE_FILE_PATH build $service
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to build $service. Exiting."
        exit 1
    }

    # Tag the image
    $imageName = "${DOCKER_USERNAME}/${service}:${IMAGE_TAG}"
    $dockerComposeImageName = "microservices-${service}:latest"
    docker tag $dockerComposeImageName $imageName

    # Push the image
    docker push $imageName
    if ($LASTEXITCODE -eq 0) {
        Write-Host "$service pushed successfully to Docker Hub: $imageName"
    } else {
        Write-Host "Error pushing $service. Exiting."
        exit 1
    }
}

Write-Host "All images built and pushed successfully! 🚀"