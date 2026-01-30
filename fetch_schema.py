
import asyncio
import httpx
import json

async def fetch_schema():
    # Attempt to fetch the public product list from the developer portal API
    base_url = "https://developer.meon.co.in"
    endpoints = [
        "/developer-tool/fetch_public_products",
        "/developer-tool/fetch_all_products",
        "/developer-tool/products"
    ]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for endp in endpoints:
            url = f"{base_url}{endp}"
            print(f"Fetching {url}...")
            try:
                # Some APIs require POST even for fetching lists (based on JS analysis)
                # JS showed .get("/developer-tool/fetch_public_products") context in parse_js output?
                # Actually parse_js showed: .post("/developer-tool/delete_endpoint",e,{authRequired:!0})).data,jd=async()=>(await qc.get("/developer-tool/fetch_public_products")).data
                # So it IS a GET request.
                
                resp = await client.get(url)
                print(f"Status: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    
                    if "data" in data and isinstance(data["data"], list):
                        print(f"Found {len(data['data'])} products:")
                        candidates = []
                        for prod in data["data"]:
                            pid = prod.get("product_id") or prod.get("id") or prod.get("_id")
                            name = prod.get("product_name")
                            sso = prod.get("sso_path")
                            print(f"- [{pid}] {name} (SSO: {sso})")
                            
                            if "kyc" in name.lower() or "verification" in name.lower():
                                candidates.append(pid)
                        
                        print("\nFetching endpoints for candidates...")
                        for pid in candidates:
                            ep_url = f"{base_url}/developer-tool/fetch_product_public_endpoints/{pid}"
                            print(f"\n--- Endpoints for Product {pid} ---")
                            try:
                                ep_resp = await client.get(ep_url)
                                if ep_resp.status_code == 200:
                                    ep_data = ep_resp.json()
                                    # Print endpoints nicely
                                    if "data" in ep_data:
                                        for ep in ep_data["data"]:
                                            method = ep.get("request_type")
                                            url = ep.get("url") or ep.get("endpoint_url")
                                            title = ep.get("title") or ep.get("endpoint_name")
                                            print(f"  {method} {url} : {title}")
                                            # If this is the one, print details
                                            if "start" in str(url) or "init" in str(url) or "generate" in str(url):
                                                print(f"    DETAILS: {json.dumps(ep, indent=2)}")
                            except Exception as e:
                                print(f"Error fetching product {pid}: {e}")
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_schema())
