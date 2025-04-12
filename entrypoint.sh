#!/bin/sh
set -e

# Create necessary directories if they don't exist
mkdir -p /app/data /app/logs

# Set permissions
chmod -R 777 /app/data /app/logs

# Copy default configuration files if they don't exist
if [ ! -f "/app/data/config.json" ]; then
    echo "Copying default config.json..."
    cp /app/defaults/config.json /app/data/
    chmod 777 /app/data/config.json
fi

if [ ! -f "/app/data/user_mapping.json" ]; then
    echo "Copying default user_mapping.json..."
    cp /app/defaults/user_mapping.json /app/data/
    chmod 777 /app/data/user_mapping.json
fi

# Start the bot
exec "$@"
