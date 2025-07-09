# app/recommendations/mood_based.py
# Implements the recommendation logic for "cold-start" users.

from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List
from ..models import Post

# A simple mapping from moods to relevant keywords found in post tags.
# This can be expanded significantly.
MOOD_KEYWORDS = {
    "inspired": ["tutorial", "learning", "success story", "inspirational", "career", "development"],
    "happy": ["comedy", "funny", "feel good", "uplifting", "wholesome", "music"],
    "curious": ["documentary", "science", "technology", "history", "space", "nature"],
    "calm": ["meditation", "relaxing", "ambient", "nature sounds", "yoga", "mindfulness"],
    "motivated": ["fitness", "workout", "entrepreneurship", "productivity", "business"],
}

def get_mood_based_recommendations(db: Session, mood: str, limit: int = 20) -> List[Post]:
    """
    Recommends posts based on a user's mood.

    Args:
        db: The database session.
        mood: The mood selected by the user (e.g., "inspired").
        limit: The maximum number of posts to return.

    Returns:
        A list of recommended Post objects.
    """
    print(f"Generating recommendations for mood: {mood}")
    keywords = MOOD_KEYWORDS.get(mood.lower())

    if not keywords:
        # Fallback: if mood is unknown, return most popular posts
        print(f"Unknown mood '{mood}'. Falling back to most popular posts.")
        return db.query(Post).order_by(Post.view_count.desc(), Post.upvote_count.desc()).limit(limit).all()

    # Build a query that searches for any of the keywords in the 'tags' column.
    # We use ILIKE for case-insensitive matching.
    # The `or_` function combines multiple conditions with the OR operator.
    conditions = [Post.tags.ilike(f"%{key}%") for key in keywords]
    
    query = db.query(Post).filter(or_(*conditions))

    # Order by a mix of view and upvote counts to surface popular, relevant content.
    recommended_posts = query.order_by(
        Post.view_count.desc(),
        Post.upvote_count.desc()
    ).limit(limit).all()

    print(f"Found {len(recommended_posts)} posts for mood '{mood}'.")
    return recommended_posts
