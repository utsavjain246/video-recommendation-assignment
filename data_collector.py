# data_collector.py
# This script fetches all necessary data from the SocialVerse API.
# This version is optimized for speed and robustly handles missing posts during interaction processing.

import os
import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from app.models import Base, engine, SessionLocal, User, Post, Interaction
import time

# --- TEST MODE CONFIGURATION ---
# Set this to a small number (e.g., 10) to fetch only a few pages for testing.
# Set to None to fetch all available data.
MAX_PAGES_TO_FETCH = 10

# Load environment variables from .env file
load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL")
FLIC_TOKEN = os.getenv("FLIC_TOKEN")

if not API_BASE_URL or not FLIC_TOKEN:
    raise ValueError("API_BASE_URL and FLIC_TOKEN must be set in the .env file")

HEADERS = {"Flic-Token": FLIC_TOKEN}
RESONANCE_ALGORITHM = "resonance_algorithm_cjsvervb7dbhss8bdrj89s44jfjdbsjd0xnjkbvuire8zcjwerui3njfbvsujc5if"

def fetch_paginated_data(endpoint, params=None, max_pages=None):
    """Fetches data from a paginated API endpoint up to a max_pages limit."""
    page = 1
    all_data = []
    print(f"--- Starting fetch for endpoint: {endpoint} ---")
    while True:
        if max_pages is not None and page > max_pages:
            print(f"Reached test limit of {max_pages} pages. Stopping fetch for this endpoint.")
            break
        try:
            request_params = { "page": page, "limit": 100 }
            if params:
                request_params.update(params)

            url = f"{API_BASE_URL}{endpoint}"
            print(f"Fetching page {page} for {endpoint}...")
            response = requests.get(url, headers=HEADERS, params=request_params, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            items = data.get('posts') or data.get('post') or data.get('users') or data.get('data', [])
            
            if not items:
                print("No more items found. Concluding fetch.")
                break
            all_data.extend(items)
            print(f"Fetched {len(items)} items. Total so far: {len(all_data)}")
            page += 1
            time.sleep(0.2)
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error fetching data from {endpoint}: {e}")
            break
        except requests.exceptions.RequestException as e:
            print(f"A network error occurred: {e}")
            break
    print(f"--- Completed fetch for {endpoint}. Total items fetched: {len(all_data)} ---")
    return all_data

def populate_database():
    """Fetches data from all APIs and populates the database using batch operations."""
    db: Session = SessionLocal()

    try:
        # Step 0: Prepare the database
        print("Ensuring pg_trgm extension is enabled...")
        db.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        db.commit()
        print("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        print("Database ready.")

        # Step 1: Populate all users
        print("\n>>> Populating All Users...")
        users_data = fetch_paginated_data("/users/get_all", max_pages=MAX_PAGES_TO_FETCH)
        existing_users = {u.id for u in db.query(User.id).all()}
        new_users = []
        for user_data in users_data:
            if isinstance(user_data, dict) and user_data.get('id') not in existing_users:
                new_users.append(User(id=user_data['id'], username=user_data['username'], name=user_data.get('name')))
                existing_users.add(user_data['id'])
        if new_users:
            db.add_all(new_users)
            db.commit()
        print(f"Users populated. Added {len(new_users)} new users.")

        # Step 2: Populate an initial batch of posts
        print("\n>>> Populating Initial Posts...")
        posts_data = fetch_paginated_data("/posts/summary/get", max_pages=MAX_PAGES_TO_FETCH)
        existing_posts = {p.id for p in db.query(Post.id).all()}
        new_posts = []
        for post_data in posts_data:
            if isinstance(post_data, dict) and post_data.get('id') not in existing_posts:
                if post_data.get('owner') and post_data['owner'].get('id') not in existing_users:
                    upsert_user(db, post_data['owner'])
                    existing_users.add(post_data['owner']['id'])
                new_posts.append(Post(id=post_data['id'], title=post_data.get('title'), tags=','.join(post_data.get('tags', [])), owner_username=post_data.get('owner', {}).get('username')))
                existing_posts.add(post_data['id'])
        if new_posts:
            db.add_all(new_posts)
            db.commit()
        print(f"Initial posts populated. Added {len(new_posts)} new posts.")

        # Step 3: Populate all interactions
        interaction_endpoints = {
            "view": "/posts/view", "like": "/posts/like",
            "inspire": "/posts/inspire", "rating": "/posts/rating",
        }
        
        user_id_map = {u.username: u.id for u in db.query(User.username, User.id).all()}
        
        for interaction_type, endpoint in interaction_endpoints.items():
            print(f"\n>>> Populating '{interaction_type}' Interactions...")
            interaction_data = fetch_paginated_data(endpoint, {"resonance_algorithm": RESONANCE_ALGORITHM}, max_pages=MAX_PAGES_TO_FETCH)
            new_interactions = []
            
            existing_interactions = {(i.user_id, i.post_id) for i in db.query(Interaction.user_id, Interaction.post_id).filter(Interaction.interaction_type == interaction_type).all()}

            for item in interaction_data:
                if not isinstance(item, dict): continue
                
                user_id = item.get('user_id')
                post_id = item.get('post_id')

                if not user_id or not post_id: continue

                # --- FINAL FIX ---
                # If the user or post doesn't exist in our DB, we can't create a valid interaction.
                # The most robust check is to ensure they are in our sets of known, valid IDs.
                if user_id in existing_users and post_id in existing_posts:
                    if (user_id, post_id) not in existing_interactions:
                        new_interactions.append(Interaction(user_id=user_id, post_id=post_id, interaction_type=interaction_type))
                        existing_interactions.add((user_id, post_id))

            if new_interactions:
                db.add_all(new_interactions)
                db.commit()
            print(f"'{interaction_type}' interactions populated. Added {len(new_interactions)} new interactions.")

        print("\n--- Database population complete. ---")

    except Exception as e:
        print(f"A major error occurred during the seeding process: {e}")
        db.rollback()
    finally:
        db.close()

# Helper function
def upsert_user(db: Session, user_data: dict):
    if not isinstance(user_data, dict) or 'id' not in user_data: return
    user = User(id=user_data['id'], username=user_data['username'], name=user_data.get('name'))
    try:
        db.add(user)
        db.commit()
    except IntegrityError:
        db.rollback()

if __name__ == "__main__":
    populate_database()
