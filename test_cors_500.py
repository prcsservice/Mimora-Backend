from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/test")
async def test_endpoint():
    raise Exception("Database blew up!")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8002)
