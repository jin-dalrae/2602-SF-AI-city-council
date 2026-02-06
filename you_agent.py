import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("YOU_COM_API_KEY")

if not API_KEY:
    print("Error: Please set YOU_COM_API_KEY in your .env file.")
    exit(1)

API_KEY = API_KEY.strip()
url = "https://ydc-index.io/v1/search"

headers = {
    "X-API-Key": API_KEY,
}

params = {
    "query": "Explain how quantum computers work using analogies a 5-year-old could understand.",
    "count": 3
}

print(f"Sending request to {url}...")
print(f"Query: {params['query']}\n")

try:
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()

    print("--- Search Results ---")
    results = data.get("results", {}).get("web", [])
    for i, res in enumerate(results):
        print(f"\n[{i+1}] {res.get('title')}")
        print(f"URL: {res.get('url')}")
        print(f"Description: {res.get('description')}")
        if res.get('snippets'):
            print("Snippets:")
            for s in res.get('snippets'):
                print(f"  - {s}")

except requests.exceptions.RequestException as e:
    print(f"Error making request: {e}")
    if hasattr(e, 'response') and e.response:
        print(f"Response: {e.response.text}")
