#!/bin/bash
# Script to find your Cloud SQL database details

echo "=== Finding Cloud SQL Database Details ==="
echo ""

# List all Cloud SQL instances
echo "📊 Your Cloud SQL Instances:"
gcloud sql instances list

echo ""
echo "=== Detailed Instance Info ==="
# Get detailed info about your instance (replace 'mimora-db' with your actual instance name if different)
gcloud sql instances describe mimora-db --format="table(
  name,
  region,
  databaseVersion,
  ipAddresses[0].ipAddress:label=PUBLIC_IP,
  connectionName
)"

echo ""
echo "=== Database Connection Info ==="
# Get connection name
CONNECTION_NAME=$(gcloud sql instances describe mimora-db --format="value(connectionName)")
echo "Connection Name: $CONNECTION_NAME"

# Get public IP
PUBLIC_IP=$(gcloud sql instances describe mimora-db --format="value(ipAddresses[0].ipAddress)")
echo "Public IP: $PUBLIC_IP"

echo ""
echo "=== List Databases ==="
gcloud sql databases list --instance=mimora-db

echo ""
echo "=== List Users ==="
gcloud sql users list --instance=mimora-db

echo ""
echo "=== Your DATABASE_URL formats ==="
echo ""
echo "For Local Development (Public IP):"
echo "DATABASE_URL=postgresql://USERNAME:PASSWORD@$PUBLIC_IP:5432/DATABASE_NAME"
echo ""
echo "For Cloud Run (Unix Socket - Recommended):"
echo "DATABASE_URL=postgresql://USERNAME:PASSWORD@/DATABASE_NAME?host=/cloudsql/$CONNECTION_NAME"
echo ""
echo "⚠️  Replace USERNAME, PASSWORD, and DATABASE_NAME with your actual values"
