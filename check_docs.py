
import asyncio
import httpx

async def check_docs():
    base_url = "https://live.meon.co.in"
    paths = [
        "/openapi.json",
        "/docs",
        "/redoc",
        "/api/docs",
        "/api/v1/docs",
        "/swagger.json",
        "/api/swagger.json"
    ]
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for p in paths:
            url = f"{base_url}{p}"
            try:
                resp = await client.get(url)
                print(f"{url} -> {resp.status_code}")
                if resp.status_code == 200:
                    print(f"FOUND DOCS at {url}")
            except Exception as e:
                print(f"{url} -> Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_docs())
