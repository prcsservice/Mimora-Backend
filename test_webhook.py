"""Test webhook locally to find any errors before deploying."""
import asyncio
import httpx
import json
import sys

async def test_webhook(base_url: str):
    """Send a simulated Meon webhook payload and print the result."""
    
    payload = {
        "current_stepname": "esign14",
        "digitrans": "TEST_TRANSACTION_001",
        "clienttoken": "TEST_TOKEN_001",
        "aadhar_name": "Test Artist User",
        "aadhar_no": "123456789012",
        "aadhar_dob": "1995-05-15",
        "aadhar_gender": "M",
        "email": "test@example.com",
        "mobile_number": "9876543210",
        "liveimage_timestamp": "2026-03-21T10:30:00",
        "clientimage": "https://example.com/test-face.jpg",
        "esign_transaction_id": "ESIGN_TEST_001",
    }
    
    print(f"Sending test webhook to: {base_url}/kyc/webhook")
    print(f"Payload:\n{json.dumps(payload, indent=2)}\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base_url}/kyc/webhook",
            headers={"Content-Type": "application/json"},
            json=payload,
        )
        
        print(f"Status Code: {resp.status_code}")
        print(f"Response Headers: {dict(resp.headers)}")
        try:
            body = resp.json()
            print(f"Response Body:\n{json.dumps(body, indent=2)}")
        except:
            print(f"Response Body (raw): {resp.text[:500]}")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://mimora-auth-254524714861.asia-south1.run.app"
    asyncio.run(test_webhook(url))
