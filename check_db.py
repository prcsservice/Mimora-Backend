import os
import sys
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv

# Load .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL not found in .env")
    sys.exit(1)

print(f"Connecting to DB: {DATABASE_URL.split('@')[-1]}")
try:
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    if inspector.has_table("customer"):
        print("Table 'customer' exists. Columns:")
        for col in inspector.get_columns("customer"):
            print(f"  - {col['name']} ({col['type']})")
        
        print("\nIndexes:")
        for idx in inspector.get_indexes("customer"):
            print(f"  - {idx['name']}")
    else:
        print("Table 'customer' does not exist.")
        
except Exception as e:
    print(f"Connection failed: {e}")
