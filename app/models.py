# app/models.py
# This file defines the SQLAlchemy database models based on the project's requirements.

import os
from sqlalchemy import (
    create_engine, Column, Integer, String, ForeignKey, DateTime, Text,
    Boolean, func, Index
)
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# --- Database Connection ---
# It's crucial to get the database URL from environment variables for security and flexibility.
# Example: postgresql://user:password@host:port/database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/video_recommendations")

# The engine is the starting point for any SQLAlchemy application.
engine = create_engine(DATABASE_URL)

# The sessionmaker provides a factory for creating Session objects.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our declarative models.
Base = declarative_base()


# --- Model Definitions ---

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    name = Column(String)
    # Add other user fields as needed from the data source
    # e.g., email = Column(String, unique=True)

    posts = relationship("Post", back_populates="owner")
    interactions = relationship("Interaction", back_populates="user")


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    project_code = Column(String, index=True) # For filtering


class Topic(Base):
    __tablename__ = "topics"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    video_link = Column(String)
    thumbnail_url = Column(String)
    tags = Column(Text) # Storing tags as a comma-separated string or JSON
    view_count = Column(Integer, default=0)
    upvote_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner_username = Column(String, ForeignKey("users.username"))
    category_id = Column(Integer, ForeignKey("categories.id"))
    topic_id = Column(Integer, ForeignKey("topics.id"))

    owner = relationship("User", back_populates="posts")
    category = relationship("Category")
    topic = relationship("Topic")
    interactions = relationship("Interaction", back_populates="post")

    # Index for faster lookups based on tags, useful for mood-based recommendations
    # This now explicitly states which operator class to use for the GIN index.
    __table_args__ = (
        Index(
            'ix_post_tags',
            'tags',
            postgresql_using='gin',
            postgresql_ops={'tags': 'gin_trgm_ops'}
        ),
    )


class Interaction(Base):
    """
    This model explicitly tracks user-post interactions, which is the
    most important data for training the GNN model.
    """
    __tablename__ = "interactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    # e.g., 'view', 'like', 'upvote', 'share'
    interaction_type = Column(String, default='view')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="interactions")
    post = relationship("Post", back_populates="interactions")


# --- Database Dependency for FastAPI ---
def get_db():
    """
    This dependency injector creates a new SQLAlchemy Session for each request,
    closes it when the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
