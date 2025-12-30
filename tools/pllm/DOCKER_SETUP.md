# Docker Setup Instructions

This project requires Docker-in-Docker (DinD) access to build and run containers from within the dev container.

## Quick Start

### Option 1: Using docker-compose (Recommended)

1. **On your HOST machine**, create a `.env` file:
   ```bash
   echo "USER=$(whoami)" > .env
   echo "UID=$(id -u)" >> .env
   echo "GID=$(id -g)" >> .env
   echo "DOCKER_GID=$(stat -f '%g' /var/run/docker.sock)" >> .env
   ```

2. Build and start the container:
   ```bash
   docker-compose up -d
   ```

3. Attach to the container:
   ```bash
   docker-compose exec llm-evaluator bash
   ```

### Option 2: Using the build script

1. **On your HOST machine**, run:
   ```bash
   chmod +x rebuild.sh
   ./rebuild.sh
   ```

2. Then run the container as shown in the output.

### Option 3: Manual build

1. **Get the Docker socket GID on your HOST**:
   ```bash
   stat -c '%g' /var/run/docker.sock
   ```

2. **Build the image**:
   ```bash
   docker build \
     --build-arg UNAME=$(whoami) \
     --build-arg UID=$(id -u) \
     --build-arg GID=$(id -g) \
     --build-arg DOCKER_GID=$(stat -c '%g' /var/run/docker.sock) \
     -t llm-evaluator:latest .
   ```

3. **Run the container**:
   ```bash
   docker run -it --rm \
     -v /var/run/docker.sock:/var/run/docker.sock:rw \
     -v $(pwd):/app \
     --name llm-evaluator \
     llm-evaluator:latest bash
   ```

## Troubleshooting

### Still getting "Permission denied" errors?

1. **Check if Docker socket is accessible**:
   ```bash
   ls -la /var/run/docker.sock
   ```

2. **Check your groups inside the container**:
   ```bash
   groups
   id
   ```
   You should see "docker" in the groups list.

3. **Verify the Docker socket GID matches**:
   ```bash
   stat -c '%g' /var/run/docker.sock
   ```
   This should match the DOCKER_GID you used during build.

4. **Last resort - make socket world-writable** (on HOST, not recommended for production):
   ```bash
   sudo chmod 666 /var/run/docker.sock
   ```

### Testing Docker access

Inside the container, test Docker access:
```bash
docker ps
docker images
```

If these work, you're all set!
