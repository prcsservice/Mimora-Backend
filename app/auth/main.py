from fastapi import FastAPI
from app.auth.database import Base, engine
from app.auth.routes import router as auth_router
from app.auth.artistroute import router as artist_router
from fastapi.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine)
print("Table 'customer' created successfully!")

app = FastAPI(title="Mimora Auth Service")

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



