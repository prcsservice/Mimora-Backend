"""Quick test: call Meon API with httpx exactly like the backend does"""
import asyncio
import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv()

async def test():
    cookie = os.getenv("MEON_SESSION_COOKIE", "")
    secret_key = os.getenv("MEON_SECRET_KEY")
    
    body = {
        "company": "mimora",
        "workflowName": "analyst",
        "secret_key": secret_key,
        "notification": True,
        "unique_keys": {"random": "999"},
        "additional_info": {},
        "is_redirect": True,
        "redirect_url": "https://www.google.com"
    }
    
    print(f"Cookie (first 50): {cookie[:50]}")
    print(f"Cookie length: {len(cookie)}")
    print(f"Secret key: {secret_key}")
    print(f"Body: {json.dumps(body)}")
    print()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://live.meon.co.in/get_sso_route",
            headers={
                "Content-Type": "application/json",
                "Cookie": cookie,
            },
            json=body
        )
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text[:500]}")

asyncio.run(test())
