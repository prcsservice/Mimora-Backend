"""View all database tables"""
from app.auth.database import engine
from sqlalchemy import text

tables = ['customer', 'artists', 'email_otps', 'kyc_requests']

with engine.connect() as conn:
    for table in tables:
        print("\n" + "=" * 60)
        print(f"TABLE: {table}")
        print("=" * 60)
        result = conn.execute(text(f"SELECT * FROM {table}"))
        rows = result.fetchall()
        if rows:
            print(" | ".join(result.keys()))
            print("-" * 60)
            for row in rows:
                print(" | ".join(str(v)[:40] for v in row))
        else:
            print("(empty table)")
        print()
