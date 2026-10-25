

# The new line is very important when merging the file with the other file
# Copy the HTTP server script
COPY sqlite-router.sh /usr/local/bin/router.sh
RUN chmod +x /usr/local/bin/router.sh

# Install BusyBox for HTTP server
RUN apt-get update && apt-get install -y socat sqlite3 && rm -rf /var/lib/apt/lists/*

# Add busy box server code to entry point script
RUN sed -i '/python -m uvicorn/i\nohup socat TCP-LISTEN:3001,reuseaddr,fork EXEC:/usr/local/bin/router.sh &' /code/start_bcc.sh

# Expose BusyBox server ports
EXPOSE 3001

