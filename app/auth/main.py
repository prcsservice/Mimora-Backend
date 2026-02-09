from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.auth.database import Base, engine
from app.auth.routes import router as auth_router, artist_router
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import threading
import os

# Initialize rate limiter
# Uses client IP address for rate limiting
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

app = FastAPI(title="Mimora Auth Service")

# Add rate limiter to app state and middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

@app.on_event("startup")
def on_startup():
    # Run database table creation in a background thread so it doesn't block app startup
    def create_tables():
        try:
            print("Starting table creation in background...")
            Base.metadata.create_all(bind=engine)
            print("Table 'customer' created successfully!")
        except Exception as e:
            print(f"Error creating tables: {e}")
    
    threading.Thread(target=create_tables, daemon=True).start()

app.include_router(auth_router)
app.include_router(artist_router)

origins = [
    "http://localhost:3000",      # React dev server
    "http://localhost:5173",      # Vite dev server
    "https://yourdomain.com",     # Production frontend
    "https://www.yourdomain.com", # Production frontend with www
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           # Allowed origins
    allow_credentials=True,          # Allow cookies
    allow_methods=["*"],             # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],             # Allow all headers
)



