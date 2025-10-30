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
    
    # Refresh the database
    sqlite3 /code/booking_db.db < /code/backend_db.sql;

    # Send success response
    echo "success"
else
    echo "HTTP/1.1 404 Not Found"
    echo "Content-Type: text/plain"
    echo
    echo "Not Found"
fi
