#!/bin/bash
# Script to rebuild the Docker container with proper permissions

# Get current user info
CURRENT_USER=$(whoami)
CURRENT_UID=$(id -u)
CURRENT_GID=$(id -g)

# Get Docker socket GID from host
# This script should be run on the HOST machine, not inside a container
if [ -S /var/run/docker.sock ]; then
    # Use -f on macOS, -c on Linux
    if [[ "$OSTYPE" == "darwin"* ]]; then
        DOCKER_SOCKET_GID=$(stat -f '%g' /var/run/docker.sock)
    else
        DOCKER_SOCKET_GID=$(stat -c '%g' /var/run/docker.sock)
    fi
    echo "Docker socket GID: $DOCKER_SOCKET_GID"
else
    echo "Warning: /var/run/docker.sock not found. Using default GID 999"
    DOCKER_SOCKET_GID=999
fi

# Build the image
echo "Building Docker image..."
docker build \
    --build-arg UNAME="$CURRENT_USER" \
    --build-arg UID="$CURRENT_UID" \
    --build-arg GID="$CURRENT_GID" \
    --build-arg DOCKER_GID="$DOCKER_SOCKET_GID" \
    -t pllm:latest \
    .

if [ $? -ne 0 ]; then
    echo "Build failed!"
    exit 1
fi

echo ""
echo "Build successful!"
echo ""
echo "To run the container with Docker socket access:"
echo ""
echo "docker run -it --rm \\"
echo "  -v /var/run/docker.sock:/var/run/docker.sock:rw \\"
echo "  -v \$(pwd):/app \\"
echo "  --name llm-evaluator \\"
echo "  llm-evaluator:latest"
echo ""
echo "Or start it in the background:"
echo ""
echo "docker run -d \\"
echo "  -v /var/run/docker.sock:/var/run/docker.sock:rw \\"
echo "  -v \$(pwd):/app \\"
echo "  --name llm-evaluator \\"
echo "  llm-evaluator:latest"
echo ""
