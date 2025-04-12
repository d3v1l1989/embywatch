#!/bin/sh

# Create necessary directories if they don't exist
mkdir -p /app/data /app/logs

# Copy default configuration files if they don't exist
if [ ! -f "/app/data/config.json" ]; then
    cp /app/defaults/config.json /app/data/
fi

if [ ! -f "/app/data/user_mapping.json" ]; then
    cp /app/defaults/user_mapping.json /app/data/
fi

# Start the bot
exec "$@"
