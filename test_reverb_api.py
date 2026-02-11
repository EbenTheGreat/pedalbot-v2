"""
Test script to verify Reverb API connectivity.
Run: uv run python test_reverb_api.py
"""
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

def test_reverb_api():
    api_key = os.getenv('REVERB_API_KEY')
    print(f"API Key present: {bool(api_key)}")
    print(f"API Key prefix: {api_key[:15]}..." if api_key else "No key")
    
    # Use synchronous client to avoid Windows async DNS issues
    try:
        with httpx.Client(timeout=30.0) as client:
            print("\nFetching Reverb listings for 'Zoom G3'...")
            resp = client.get(
                'https://api.reverb.com/api/listings',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Accept': 'application/hal+json',
                    'Accept-Version': '3.0'
                },
                params={'query': 'Zoom G3', 'per_page': 5}
            )
            print(f"Status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                listings = data.get('listings', [])
                print(f"Listings found: {len(listings)}")
                
                if listings:
                    for i, listing in enumerate(listings[:3]):
                        title = listing.get('title', 'N/A')[:50]
                        price = listing.get('price', {}).get('amount', 'N/A')
                        condition = listing.get('condition', {}).get('display_name', 'N/A')
                        print(f"  {i+1}. {title}... - ${price} ({condition})")
                    print("\n✅ Reverb API is working!")
                else:
                    print("No listings found for this query")
            elif resp.status_code == 401:
                print("❌ Authentication failed - check your REVERB_API_KEY")
                print(f"Response: {resp.text[:200]}")
            else:
                print(f"❌ Error: {resp.text[:300]}")
                
    except httpx.ConnectError as e:
        print(f"❌ Connection error: {e}")
        print("\nThis is likely a DNS resolution issue on Windows.")
        print("Try restarting your network adapter or using a VPN.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_reverb_api()
