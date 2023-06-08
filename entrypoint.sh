#!/usr/bin/env sh

# Wait for Gitea
until curl -s "$GITEA_HOST":"$GITEA_PORT" > /dev/null; do
    echo "Waiting for Gitea"
    sleep 10
done
echo "Found running Gitea instance"