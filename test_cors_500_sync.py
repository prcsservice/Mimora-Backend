from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/test")
async def test_endpoint():
    raise Exception("Database blew up!")

client = TestClient(app)
response = client.post("/test", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
print("STATUS:", response.status_code)
print("HEADERS:", response.headers)
