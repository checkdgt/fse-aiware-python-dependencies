#!/bin/bash
set -e

# Fix Docker socket permissions if it exists
if [ -S /var/run/docker.sock ]; then
    # Get the socket's group ID - handle both BSD stat (macOS) and GNU stat (Linux)
    if stat --version &>/dev/null; then
        # GNU stat (Linux)
        SOCK_GID=$(stat -c '%g' /var/run/docker.sock 2>/dev/null || echo "0")
    else
        # BSD stat (macOS) - though this should run in Linux container
        SOCK_GID=$(stat -f '%g' /var/run/docker.sock 2>/dev/null || echo "0")
    fi
    
    # Get the user's supplementary groups
    USER_GROUPS=$(id -G $UNAME)
    
    # Check if user is already in the socket's group
    if ! echo "$USER_GROUPS" | grep -q "\b$SOCK_GID\b"; then
        echo "Adding user to Docker socket group (GID: $SOCK_GID)"
        # Create/use a group with the socket's GID and add user to it
        GROUP_NAME=$(getent group $SOCK_GID | cut -d: -f1 || echo "dockerhost")
        if [ "$GROUP_NAME" = "dockerhost" ]; then
            groupadd -g $SOCK_GID dockerhost 2>/dev/null || true
        fi
        usermod -aG $GROUP_NAME $UNAME 2>/dev/null || true
    fi
fi

# Execute the CMD as the specified user
exec gosu $UNAME "$@"
