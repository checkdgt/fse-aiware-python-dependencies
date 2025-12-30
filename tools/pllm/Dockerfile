FROM python:3.11

ARG UNAME=appuser
ARG UID=1000
ARG GID=1000
ARG DOCKER_GID=999

# Install gosu for better privilege dropping
RUN apt-get update && apt-get install -y gosu && rm -rf /var/lib/apt/lists/*

# Create user's primary group and user
RUN groupadd -g $GID -o $UNAME && \
    useradd -m -u $UID -g $GID -o -s /bin/bash $UNAME

# Store UNAME as environment variable for entrypoint
ENV UNAME=$UNAME
    
# Install Python packages globally (available to all users)
RUN python -m pip install --upgrade pip && \
    pip install datetime==5.5 && \
    pip install python-dateutil==2.9.0.post0 && \
    pip install transformers==4.41.1 && \
    pip install accelerate==0.30.1 && \
    pip install requests==2.31.0 && \
    pip install docker==7.1.0 && \
    pip install ollama==0.2.0 && \
    pip install langchain==0.2.1 && \
    pip install langchain-openai==0.1.9 && \
    pip install langchain-community==0.2.1 && \
    pip install llama-index-llms-ollama==0.1.5 && \
    pip install jq==1.7.0 && \
    pip install pypi-json==0.4.0 && \
    pip install jsonschema==4.22.0 && \
    pip install load-dotenv==0.1.0 && \
    pip install pyyaml==6.0.1

# Create app directory and set permissions
RUN mkdir -p /app && chown $UID:$GID /app

# Copy entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Copy application code (as root, will be accessible by user)
COPY . /app
RUN chown -R $UID:$GID /app

# Set working directory
WORKDIR /app

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["tail", "-f", "/dev/null"]
