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
import httpx

# Function to get the real user IP behind a proxy (Cloud Run / Load Balancer)
def get_real_user_ip(request: Request):
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0]
    return request.client.host

# Initialize rate limiter
# Uses client IP address for rate limiting (proxy-aware)
limiter = Limiter(key_func=get_real_user_ip, default_limits=["100/minute"])

app = FastAPI(title="Mimora Auth Service")

# CORS origins
origins = [
    "http://localhost:3000",      # React dev server
    "http://localhost:5173",      # Vite dev server
    "https://mimora-frontend-new.vercel.app",  # Production frontend
]

# Add rate limiter FIRST (will be innermost middleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Add CORS middleware LAST (outermost) so preflight OPTIONS requests are handled
# before any other middleware can reject them
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           # Allowed origins
    allow_credentials=True,          # Allow cookies
    allow_methods=["*"],             # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],             # Allow all headers
)

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


# ============ Reverse Geocoding Proxy ============
# Proxies Nominatim requests server-side to avoid browser CORS restrictions
@app.get("/geocode/reverse")
@limiter.limit("30/minute")
async def reverse_geocode(request: Request, lat: float, lon: float):
    """Proxy reverse geocoding via Nominatim (server-side, no CORS issues)."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": lat,
                    "lon": lon,
                    "format": "json",
                    "addressdetails": 1,
                },
                headers={
                    "Accept-Language": "en",
                    "User-Agent": "Mimora/1.0",  # Nominatim requires a User-Agent
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"detail": f"Geocoding service unavailable: {str(e)}"}
        )
