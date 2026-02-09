
import os
import psycopg2
from dotenv import load_dotenv
from urllib.parse import urlparse

# Load .env to get DATABASE_URL
load_dotenv()

database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("Error: DATABASE_URL not found in .env")
    exit(1)

print(f"Connecting to database...")

try:
    # Parse the URL to get connection details
    # We need to unquote the password because it might contain special chars like %40
    # But psycopg2.connect doesn't accept the URL directly if permissions or other issues exist, 
    # and sqlalchemy handles the %40 -> @ conversion. 
    # psycopg2 might need the password to be exactly as passed in URL if passing dsn.
    
    # Actually, let's just use the DSN string directly, psycopg2 supports it.
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    
    with conn.cursor() as cursor:
        print("Checking if PostGIS extension exists...")
        cursor.execute("SELECT * FROM pg_extension WHERE extname = 'postgis';")
        if cursor.fetchone():
            print("✅ PostGIS extension is ALREADY enabled.")
        else:
            print("Enabling PostGIS extension...")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
            print("✅ PostGIS extension enabled successfully!")
            
    conn.close()

except Exception as e:
    print(f"❌ Failed to enable PostGIS: {e}")
