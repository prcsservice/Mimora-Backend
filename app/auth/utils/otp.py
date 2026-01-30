# utils/otp.py
import random
import bcrypt
from datetime import datetime, timedelta

def generate_otp():
    return str(random.randint(100000, 999999))

def hash_otp(otp: str):
    return bcrypt.hashpw(otp.encode(), bcrypt.gensalt()).decode()

def verify_otp(otp: str, otp_hash: str):
    return bcrypt.checkpw(otp.encode(), otp_hash.encode())

def otp_expiry():
    return datetime.utcnow() + timedelta(minutes=5)
