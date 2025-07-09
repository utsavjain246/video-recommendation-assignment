# debug_interactions.py
# A simple, focused script to fetch and print the structure of a single
# interaction record from the API to resolve the data parsing issue.

import os
import requests
from dotenv import load_dotenv
import json

# Load environment variables from .env file
load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL")
FLIC_TOKEN = os.getenv("FLIC_TOKEN")
RESONANCE_ALGORITHM = "resonance_algorithm_cjsvervb7dbhss8bdrj89s44jfjdbsjd0xnjkbvuire8zcjwerui3njfbvsujc5if"

if not API_BASE_URL or not FLIC_TOKEN:
    raise ValueError("API_BASE_URL and FLIC_TOKEN must be set in the .env file")

HEADERS = {"Flic-Token": FLIC_TOKEN}

def debug_view_endpoint():
    """Fetches one page and prints the first record to reveal its structure."""
    print("--- Attempting to fetch ONE page from /posts/view for debugging ---")
    endpoint = "/posts/like"
    params = {
        "page": 1,
        "limit": 10, # We only need a few records
        "resonance_algorithm": RESONANCE_ALGORITHM
    }
    url = f"{API_BASE_URL}{endpoint}"

    try:
        print(f"Fetching {url}...")
        response = requests.get(url, headers=HEADERS, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        # The API response key can vary ('post', 'posts', 'users', 'data')
        items = data.get('posts') or data.get('post') or data.get('data', [])

        if not items:
            print("\nCRITICAL: The API returned no items for the /posts/view endpoint.")
            print("Full API Response:", data)
            return

        print("\nSUCCESS! Fetched interaction data. Here is the first record:")
        print("-" * 50)
        # Use json.dumps for pretty printing
        print(json.dumps(items[0], indent=2))
        print("-" * 50)
        print("\nPlease paste this entire output, including the text between the lines, in your response.")


    except Exception as e:
        print(f"\nAn error occurred: {e}")
        print("Please check your .env file and network connection.")

if __name__ == "__main__":
    debug_view_endpoint()
