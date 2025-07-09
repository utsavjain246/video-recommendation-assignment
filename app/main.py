from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
import torch
import os

# --- Local Imports ---
from . import models, schemas
from .models import get_db, Post as DBPost, User as DBUser, Interaction as DBInteraction
from .recommendations.mood_based import get_mood_based_recommendations
from .recommendations.gnn_recommender import LightGCN, generate_gnn_recommendations, build_graph_from_db

# --- Global Variables for GNN Model ---
# These are loaded once at startup to avoid reloading on every request.
GNN_MODEL = None
GNN_GRAPH_DATA = None
INTERACTION_THRESHOLD = 5 # User needs >5 interactions to get GNN recommendations.
GNN_MODEL_PATH = "lightgcn_model.pth"

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Video Recommendation Engine",
    description="A hybrid recommendation system using mood-based filtering for cold-starts and a LightGCN model for existing users.",
    version="1.0.0"
)

# --- Startup Event ---
@app.on_event("startup")
def startup_event():
    """
    This function runs when the application starts. It loads the trained GNN
    model and its required data into memory.
    """
    global GNN_MODEL, GNN_GRAPH_DATA
    if os.path.exists(GNN_MODEL_PATH):
        print("Found GNN model file. Loading model and graph data...")
        try:
            # We need a temporary DB session to build the graph
            db = next(get_db())
            graph, metadata = build_graph_from_db(db)
            db.close()

            GNN_GRAPH_DATA = (graph, metadata)

            # Initialize model with the correct dimensions from metadata
            GNN_MODEL = LightGCN(
                num_users=metadata['num_users'],
                num_items=metadata['num_posts']
            )
            # Load the saved weights
            GNN_MODEL.load_state_dict(torch.load(GNN_MODEL_PATH))
            GNN_MODEL.eval() # Set model to evaluation mode
            print("--- GNN Model and graph data loaded successfully. ---")
        except Exception as e:
            print(f"!!! CRITICAL: Failed to load GNN model. Error: {e} !!!")
            GNN_MODEL = None # Ensure model is None if loading fails
    else:
        print("--- WARNING: GNN model file not found. GNN recommendations will be unavailable. ---")
        print(f"--- To enable GNN, run `python train_gnn.py` after seeding the database. ---")


# --- API Endpoints ---

@app.get("/feed", response_model=schemas.FeedResponse, summary="Get Personalized Video Feed")
def get_feed(
    username: str = Query(..., description="The username of the user requesting the feed."),
    project_code: Optional[str] = Query(None, description="Filter feed by a specific project code."),
    mood: Optional[str] = Query("inspired", description="User's current mood (used for new users)."),
    db: Session = Depends(get_db)
):
    """
    This endpoint provides a personalized feed of videos.
    - For **new users** (less than 5 interactions), it uses a **mood-based** recommender.
    - For **existing users**, it uses a powerful **Graph Neural Network (GNN)** model.
    """
    user = db.query(DBUser).filter(DBUser.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found.")

    # Determine if user is 'cold-start' or 'existing'
    interaction_count = db.query(DBInteraction).filter(DBInteraction.user_id == user.id).count()

    recommended_posts = []

    # Hybrid Switching Logic
    if GNN_MODEL and interaction_count >= INTERACTION_THRESHOLD:
        # --- Existing User: Use GNN ---
        print(f"User '{username}' is an existing user ({interaction_count} interactions). Using GNN.")
        post_ids = generate_gnn_recommendations(username, GNN_MODEL, GNN_GRAPH_DATA)
        if post_ids:
            # Preserve the order from the GNN recommender
            recommended_posts = db.query(DBPost).filter(DBPost.id.in_(post_ids)).all()
            # Create a mapping from ID to post to sort them correctly
            post_map = {post.id: post for post in recommended_posts}
            recommended_posts = [post_map[pid] for pid in post_ids if pid in post_map]
    else:
        # --- Cold-Start User: Use Mood-Based Recommender ---
        status_reason = "new user" if interaction_count < INTERACTION_THRESHOLD else "GNN model not available"
        print(f"User '{username}' is a {status_reason}. Using mood-based recommendations for mood: '{mood}'.")
        recommended_posts = get_mood_based_recommendations(db, mood=mood)

    # Apply category filter if provided
    if project_code:
        print(f"Applying filter for project_code: {project_code}")
        # Note: This filters the already recommended posts.
        recommended_posts = [
            post for post in recommended_posts if post.category and post.category.project_code == project_code
        ]

    # Return the response formatted by our Pydantic schema
    return {"status": "success", "post": recommended_posts}

@app.get("/", include_in_schema=False)
def root():
    return {"message": "Video Recommendation API is running. See /docs for details."}
