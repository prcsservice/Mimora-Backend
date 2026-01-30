
import asyncio
import httpx
import os
import socket

async def main():
    subdomains = [
        "live", "api", "kyc", "ckyc", "video-kyc", "digilocker", 
        "esign", "face-finder", "ocr", "panapi", "id-verification"
    ]
    base_domain = "meon.co.in"
    
    paths = [
        "/kyc/generate_link",
        "/api/v1/kyc/generate_link",
        "/generate_link",
        "/kyc/initiate",
        "/api/kyc/initiate",
        "/digilocker/generate_link",
        "/api/generate_link"
    ]
    
    api_key = os.getenv('MEON_API_KEY')
    
    print(f"Testing combinations for {base_domain}...")
    
    async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
        for sub in subdomains:
            host = f"{sub}.{base_domain}"
            try:
                # Check DNS first
                ip = socket.gethostbyname(host)
                print(f"\nHost {host} resolves to {ip}")
                
                base_url = f"https://{host}"
                
                for path in paths:
                    url = f"{base_url}{path}"
                    try:
                        # Try POST
                        resp = await client.post(
                            url, 
                            headers={"Authorization": f"Bearer {api_key}"},
                            json={"test": "data"}
                        )
                        if resp.status_code not in [404, 502, 503]:
                            print(f"[!] {url} -> {resp.status_code}")
                            if resp.status_code != 405:
                                print(f"    Response: {resp.text[:100]}")
                        else:
                            # print(f"    {path} -> {resp.status_code}")
                            pass
                    except Exception as e:
                        print(f"    {path} -> Error: {e}")
                        
            except socket.gaierror:
                print(f"Host {host} does not exist")
            except Exception as e:
                print(f"Host {host} error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
