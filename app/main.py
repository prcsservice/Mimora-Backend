from fastapi import FastAPI
from app.auth.database import Base, engine
from app.auth.routes import router as auth_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mimora Auth Service")

app.include_router(auth_router)

@app.get("/")
def health():
    return {"status": "ok"}
