import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict

# This will download the model on the first run.
print("Loading sentence transformer model...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded.")

# In-memory cache for embeddings: {post_id: vector}
post_embeddings_cache = {}

def generate_text_for_post(post: Dict) -> str:
    """Creates a single descriptive string from a post object."""
    tags = ", ".join(post.get('tags', []))
    topic_name = post.get('topic', {}).get('name', '')
    category_name = post.get('category', {}).get('name', '')
    title = post.get('title', '')
    # Combine the most important text fields
    return f"{title}. Topic: {topic_name}. Category: {category_name}. Tags: [{tags}]"

def generate_all_embeddings(all_posts: List[Dict]):
    """
    Generates and caches embeddings for all posts.
    This should be called once on startup.
    """
    if not all_posts:
        return

    print(f"Generating embeddings for {len(all_posts)} posts...")
    
    # Get post IDs and the text content we'll embed
    post_ids = [post['id'] for post in all_posts]
    post_texts = [generate_text_for_post(post) for post in all_posts]
    
    # Generate embeddings in a single, efficient batch
    embeddings = model.encode(post_texts, show_progress_bar=True)
    
    # Store them in our cache
    for i, post_id in enumerate(post_ids):
        post_embeddings_cache[post_id] = embeddings[i]
        
    print("Embedding generation complete.")

def get_embeddings_cache():
    return post_embeddings_cache