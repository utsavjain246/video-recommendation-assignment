import os
import requests
from typing import List, Dict, Any

# In-memory cache
cache = {
    "posts": [],
    "users": [],
    "viewed_posts": {}, # Dict[str, List[int]] username -> [post_id, ...]
    "liked_posts": {},
    "inspired_posts": {},
    "rated_posts": {}
}

API_BASE_URL = os.getenv("API_BASE_URL")
FLIC_TOKEN = os.getenv("FLIC_TOKEN")
HEADERS = {"Flic-Token": FLIC_TOKEN}

# This is a generic fetcher that handles pagination
def _fetch_paginated_data(endpoint: str, headers: Dict = None) -> List[Dict]:
    all_data = []
    page = 1
    page_size = 1000
    while True:
        url = f"{API_BASE_URL}{endpoint}?page={page}&page_size={page_size}"
        if "resonance_algorithm" in endpoint: # Handle special endpoints
             url = f"{API_BASE_URL}{endpoint}" # The example URL has it all
        
        print(f"Fetching from {url}")
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # The actual content is usually in a key like 'post', 'data', or 'users'
            # You will need to inspect the actual API response to find the correct key
            # Based on output-data-format.md, it's likely 'post'
            content = data.get('post', data.get('data', data.get('users', [])))

            if not content:
                break
            all_data.extend(content)
            page += 1
        except requests.RequestException as e:
            print(f"Error fetching data from {url}: {e}")
            break
    return all_data

# Function to load and cache all data on startup
def load_all_data():
    print("Starting data loading process...")
    
    # Fetch all posts
    cache["posts"] = _fetch_paginated_data("/posts/summary/get", headers=HEADERS)
    print(f"Loaded {len(cache['posts'])} total posts.")

    # Fetch engagement data (these are just examples, you need to verify the response format)
    # The README shows a complex resonance_algorithm param. For now, assume it's static
    resonance_param = "resonance_algorithm_cjsvervb7dbhss8bdrj89s44jfjdbsjd0xnjkbvuire8zcjwerui3njfbvsujc5if"
    
    # We need to process this data to map it to users
    # For now, let's just fetch one type to build the logic, e.g., Liked Posts
    liked_data = _fetch_paginated_data(f"/posts/like?resonance_algorithm={resonance_param}", headers=HEADERS)
    
    # Process liked_data to populate cache['liked_posts']
    # ASSUMPTION: The response contains a user identifier and a post identifier.
    # We will assume a structure like: [{'username': 'user1', 'post_id': 123}, ...]
    # You MUST verify the actual structure and adapt this logic.
    for like in liked_data:
        # Let's assume the post owner is the one who liked it for this example
        username = like.get('owner', {}).get('username')
        post_id = like.get('id')
        if username and post_id:
            if username not in cache['liked_posts']:
                cache['liked_posts'][username] = []
            cache['liked_posts'][username].append(post_id)

    print("Data loading complete.")
    # You would repeat this for viewed, inspired, rated posts.