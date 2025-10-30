#!/bin/bash

# Read the first line of the HTTP request
read request

# Extract the requested path (second field in request line)
path=$(echo "$request" | awk '{print $2}')

if [[ "$path" == "/refreshed-db" ]]; then
    echo "HTTP/1.1 200 OK"
    echo "Content-Type: text/plain"
    echo
    echo "Running refresh-db.sh..."
    
    # Refresh the mongo database
    mongosh /scripts/init.js 2>&1;

    # refresh all backend's databases
    curl http://loke:3001/refreshed-db
    curl http://pingu:3001/refreshed-db
    curl http://pegu:3001/refreshed-db
    curl http://thor:3001/refreshed-db

    # Send success response
    echo "success"
else
    echo "HTTP/1.1 404 Not Found"
    echo "Content-Type: text/plain"
    echo
    echo "Not Found"
fi
