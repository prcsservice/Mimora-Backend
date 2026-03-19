"""
Mimora Booking Microservice — FastAPI App
"""
import asyncio
import threading
import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import httpx

from app.Booking.database import Base, engine
from app.Booking.routes import router as booking_router
from app.Booking.services.redis_client import close_redis, start_expiry_listener
from app.Booking.services.booking_service import handle_booking_expiry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────── Rate Limiter ───────────────

def get_real_user_ip(request: Request):
    """Get the real user IP behind a proxy (Cloud Run / Load Balancer)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0]
    return request.client.host


limiter = Limiter(key_func=get_real_user_ip, default_limits=["100/minute"])


# ─────────────── App ───────────────

app = FastAPI(title="Mimora Booking Service")

# CORS
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://mimora-frontend-new.vercel.app",
]

# Rate limiter middleware (innermost)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS middleware (outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────── Startup / Shutdown ───────────────

@app.on_event("startup")
async def on_startup():
    # Create booking tables
    def create_tables():
        try:
            logger.info("Creating booking tables...")
            Base.metadata.create_all(bind=engine)
            logger.info("Booking tables created successfully!")
        except Exception as e:
            logger.error(f"Error creating booking tables: {e}")

    threading.Thread(target=create_tables, daemon=True).start()

    # Start Redis expiry listener in background
    try:
        asyncio.create_task(_start_redis_listener())
        logger.info("Redis expiry listener task scheduled")
    except Exception as e:
        logger.warning(f"Redis listener not started (Redis may not be available): {e}")


async def _start_redis_listener():
    """Start the Redis keyspace notification listener."""
    try:
        await start_expiry_listener(handle_booking_expiry)
    except Exception as e:
        logger.warning(f"Redis expiry listener failed: {e}")
        logger.warning("Booking timer expiry won't trigger automatic fallback. Ensure Redis is running.")


@app.on_event("shutdown")
async def on_shutdown():
    await close_redis()
    logger.info("Redis connection closed")


# ─────────────── Routes ───────────────

app.include_router(booking_router)


# ─────────────── Health Check ───────────────

@app.get("/")
def health():
    return {"status": "ok", "service": "booking"}


# ─────────────── Reverse Geocoding Proxy ───────────────

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
                    "User-Agent": "Mimora/1.0",
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
