# app/recommendations/gnn_recommender.py
# Contains the LightGCN model, graph building logic, and recommendation generation.
# This version is corrected to use explicit interaction data.

import torch
import torch.nn as nn
from sqlalchemy.orm import Session
import scipy.sparse as sp
import numpy as np
from typing import List, Dict, Tuple, Set

from ..models import Interaction, User, Post

# --- LightGCN Model Definition ---

class LightGCN(nn.Module):
    """
    PyTorch implementation of the LightGCN model.
    Reference: https://arxiv.org/abs/2002.02126
    """
    def __init__(self, num_users, num_items, embed_dim=64, n_layers=3):
        super(LightGCN, self).__init__()
        self.num_users = num_users
        self.num_items = num_items
        self.embed_dim = embed_dim
        self.n_layers = n_layers

        self.user_embedding = nn.Embedding(num_users, embed_dim)
        self.item_embedding = nn.Embedding(num_items, embed_dim)

        nn.init.normal_(self.user_embedding.weight, std=0.1)
        nn.init.normal_(self.item_embedding.weight, std=0.1)

        self.graph = None

    def computer(self):
        """Propagates embeddings through the graph layers."""
        users_emb = self.user_embedding.weight
        items_emb = self.item_embedding.weight
        all_emb = torch.cat([users_emb, items_emb])
        
        embs = [all_emb]
        g_droped = self.graph

        for _ in range(self.n_layers):
            all_emb = torch.sparse.mm(g_droped, all_emb)
            embs.append(all_emb)
        
        embs = torch.stack(embs, dim=1)
        light_out = torch.mean(embs, dim=1)
        users, items = torch.split(light_out, [self.num_users, self.num_items])
        return users, items

    def get_user_ratings(self, users):
        """Calculates scores for all items for a given set of users."""
        all_users, all_items = self.computer()
        user_embeds = all_users[users]
        item_embeds = all_items
        ratings = torch.matmul(user_embeds, item_embeds.t())
        return ratings

# --- Data Preparation and Graph Building ---

def build_graph_from_db(db: Session) -> Tuple[torch.Tensor, Dict, Dict[int, Set[int]]]:
    """
    Builds the LightGCN graph from the Interaction table.
    Also returns a dictionary of user interactions to filter recommendations.
    """
    print("Building graph from explicit interaction data...")
    interactions = db.query(Interaction).all()
    users = db.query(User).all()
    posts = db.query(Post).all()

    if not users or not posts:
        raise ValueError("Database has no users or posts. Cannot build graph.")

    user_map = {user.id: i for i, user in enumerate(users)}
    post_map = {post.id: i for i, post in enumerate(posts)}
    
    user_inv_map = {v: k for k, v in user_map.items()}
    post_inv_map = {v: k for k, v in post_map.items()}
    
    username_map = {user.username: user_map[user.id] for user in users if user.id in user_map}

    num_users = len(users)
    num_posts = len(posts)

    # Store user interactions to filter seen items later
    user_interactions = {u_idx: set() for u_idx in range(num_users)}

    R = sp.dok_matrix((num_users, num_posts), dtype=np.float32)
    for inter in interactions:
        if inter.user_id in user_map and inter.post_id in post_map:
            uidx = user_map[inter.user_id]
            pidx = post_map[inter.post_id]
            R[uidx, pidx] = 1.0
            user_interactions[uidx].add(pidx)

    adj_mat = sp.dok_matrix((num_users + num_posts, num_users + num_posts), dtype=np.float32)
    adj_mat = adj_mat.tolil()
    R = R.tolil()
    adj_mat[:num_users, num_users:] = R
    adj_mat[num_users:, :num_users] = R.T
    adj_mat = adj_mat.todok()

    rowsum = np.array(adj_mat.sum(axis=1))
    d_inv = np.power(rowsum, -0.5).flatten()
    d_inv[np.isinf(d_inv)] = 0.
    d_mat = sp.diags(d_inv)
    
    norm_adj = d_mat.dot(adj_mat).dot(d_mat).tocoo().astype(np.float32)

    indices = torch.from_numpy(np.vstack((norm_adj.row, norm_adj.col))).long()
    values = torch.from_numpy(norm_adj.data)
    graph_tensor = torch.sparse.FloatTensor(indices, values, torch.Size(norm_adj.shape))

    metadata = {
        "num_users": num_users, "num_posts": num_posts,
        "user_map": user_map, "post_map": post_map,
        "user_inv_map": user_inv_map, "post_inv_map": post_inv_map,
        "username_map": username_map
    }
    
    print("Graph building complete.")
    return graph_tensor, metadata, user_interactions

# --- Recommendation Generation (Inference) ---

def generate_gnn_recommendations(
    username: str, model: LightGCN, graph_data: Tuple, limit: int = 20
) -> List[int]:
    """Generates top-N recommendations for a user, filtering out seen items."""
    graph, metadata, user_interactions = graph_data
    model.graph = graph

    username_map = metadata['username_map']
    if username not in username_map:
        return []

    user_idx = username_map[username]
    
    with torch.no_grad():
        ratings = model.get_user_ratings(torch.tensor([user_idx]))
        
        # Filter out items the user has already interacted with
        seen_items = user_interactions.get(user_idx, set())
        if seen_items:
            ratings[0, list(seen_items)] = -np.inf # Set score to negative infinity

        # Get top K recommendations
        _, top_indices = torch.topk(ratings, k=limit)
        top_indices = top_indices.squeeze().tolist()

    post_inv_map = metadata['post_inv_map']
    recommended_post_ids = [post_inv_map[idx] for idx in top_indices if idx in post_inv_map]

    return recommended_post_ids
