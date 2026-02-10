#!/bin/bash
# Interactive script to list tables

echo "========================================================"
echo "🔌 Connecting to Cloud SQL (mimoradev) via Proxy..."
echo "👤 User: Mimora"
echo "🔑 Password required: "
echo "========================================================"
echo "Instructions:"
echo "1. If asked to install the proxy, say 'Y' (yes)"
echo "2. Enter password `3F~` when prompted"
echo "3. You are now connected directly to 'mimora_db'"
echo "4. Type: \dt to list tables"
echo "5. Type \q to exit"
echo "========================================================"

# Using beta command to support IPv6/Proxy connections
# Add current directory to PATH so gcloud can find the local cloud_sql_proxy
if [ ! -f "./cloud_sql_proxy" ]; then
    echo "❌ Error: cloud_sql_proxy not found in current directory."
    echo "Please run: wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -O cloud_sql_proxy && chmod +x cloud_sql_proxy"
    exit 1
fi
export PATH=$PATH:.
gcloud beta sql connect mimoradev --user=Mimora --project=fixforward-dev --quiet --database=mimora_db
