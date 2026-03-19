import os
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from app.auth.models import Artist, User

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    email = "test.google@example.com"
    firebase_uid = "fake_uid_12345"
    name = "Test Google"
    provider = "google"
    base_username = email.split("@")[0].lower().replace(".", "_")
    username = base_username
    
    # Create minimal profile
    user = Artist(
        firebase_uid=firebase_uid,
        email=email,
        name=name,
        username=username,
        provider=provider,
        latitude=1.0,
        longitude=1.0,
        profile_completed=False,
        kyc_verified=False,
        rating=0.0,
        total_reviews=0
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print("SUCCESS! User ID:", user.id)
except Exception as e:
    print("EXCEPTION:", type(e).__name__)
    print(e)
