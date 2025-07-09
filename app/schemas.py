# app/schemas.py
# Pydantic models for request/response validation and serialization.
# These models ensure the API output matches the specification in output-data-format.md

from pydantic import BaseModel
from typing import List, Optional

# --- Sub-models for nested objects ---

class OwnerSchema(BaseModel):
    name: Optional[str] = None
    username: str

    class Config:
        orm_mode = True

class CategorySchema(BaseModel):
    id: int
    name: str
    project_code: Optional[str] = None

    class Config:
        orm_mode = True

class TopicSchema(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True

# --- Main Post Schema ---

class PostSchema(BaseModel):
    id: int
    owner: OwnerSchema
    category: Optional[CategorySchema] = None
    topic: Optional[TopicSchema] = None
    title: str
    video_link: Optional[str] = None
    thumbnail_url: Optional[str] = None
    tags: Optional[str] = None
    view_count: int
    upvote_count: int

    class Config:
        orm_mode = True # This allows Pydantic to read data directly from ORM objects

# --- Top-level Response Schema ---

class FeedResponse(BaseModel):
    status: str
    post: List[PostSchema]
