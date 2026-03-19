#!/bin/bash
# Interactive script to list tables

echo "========================================================"
echo "🔌 Connecting to Cloud SQL (mimora) via Proxy..."
echo "👤 User: postgres"
echo "🔑 Password required: "
echo "========================================================"
echo "Instructions:"
echo "1. If asked to install the proxy, say 'Y' (yes)"
echo "2. Enter password 'MimoraPostgres123!' when prompted"
echo "3. You are now connected directly to 'postgres'"
echo "4. Type: \dt to list tables"
echo "5. Type \q to exit"
echo "========================================================"

# Check if service account key exists, if not use gcloud auth
if [ ! -f "./serviceAccountKey.json" ]; then
    echo "⚠️  serviceAccountKey.json not found, using gcloud authentication..."
    # Make sure we're not using any service account key
    unset GOOGLE_APPLICATION_CREDENTIALS
else
    # Remove or rename the old service account key so gcloud auth is used instead
    echo "⚠️  Using gcloud authentication instead of service account key..."
    unset GOOGLE_APPLICATION_CREDENTIALS
fi

# Start Cloud SQL Proxy in the background
if [ ! -f "./cloud_sql_proxy" ]; then
    echo "❌ Error: cloud_sql_proxy not found in current directory."
    echo "Please run: wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -O cloud_sql_proxy && chmod +x cloud_sql_proxy"
    exit 1
fi

# Create a temp directory for socket (for cleanup purposes)
SOCKET_DIR="/tmp/cloudsql"
mkdir -p $SOCKET_DIR

echo "Starting Cloud SQL Proxy: [./cloud_sql_proxy -instances=mimora-490516:asia-south1:mimora=tcp:9470]"
./cloud_sql_proxy -instances=mimora-490516:asia-south1:mimora=tcp:9470 > /tmp/proxy.log 2>&1 &
PROXY_PID=$!

# Give proxy time to start and listen on port
echo "⏳ Waiting for proxy to start..."
for i in {1..20}; do
    if nc -z 127.0.0.1 9470 2>/dev/null; then
        echo "✅ Cloud SQL Proxy started successfully (PID: $PROXY_PID)"
        break
    fi
    if [ $i -eq 20 ]; then
        echo "❌ Error: Cloud SQL Proxy failed to start"
        echo "Proxy logs:"
        cat /tmp/proxy.log
        kill $PROXY_PID 2>/dev/null
        exit 1
    fi
    sleep 1
done

# Connect to database via TCP
psql -h 127.0.0.1 -p 9470 -U postgres -d postgres

# Clean up: kill proxy on exit
kill $PROXY_PID 2>/dev/null
rm -rf $SOCKET_DIR
