# train_gnn.py
# A standalone script to train the LightGCN model and save its weights.
# This version is robust and uses explicit interaction data for training.

import torch
import torch.optim as optim
from app.models import get_db
from app.recommendations.gnn_recommender import LightGCN, build_graph_from_db
import numpy as np
from typing import Dict, Set

# --- Training Configuration ---
LEARNING_RATE = 1e-3
EPOCHS = 50
MODEL_SAVE_PATH = "lightgcn_model.pth"
L2_REG = 1e-4

def bpr_loss(users_emb, pos_items_emb, neg_items_emb):
    """Bayesian Personalized Ranking (BPR) loss."""
    pos_scores = torch.sum(torch.mul(users_emb, pos_items_emb), dim=1)
    neg_scores = torch.sum(torch.mul(users_emb, neg_items_emb), dim=1)
    loss = -torch.mean(torch.nn.functional.logsigmoid(pos_scores - neg_scores))
    return loss

def regularization_loss(users_emb, pos_items_emb, neg_items_emb):
    """L2 regularization loss."""
    reg_loss = (users_emb.norm(2).pow(2) +
                pos_items_emb.norm(2).pow(2) +
                neg_items_emb.norm(2).pow(2)) / float(len(users_emb))
    return reg_loss

def get_bpr_data(user_interactions: Dict[int, Set[int]], num_posts: int):
    """Creates training batches (user, positive_item, negative_item) for BPR loss."""
    users, pos_items, neg_items = [], [], []
    all_item_indices = list(range(num_posts))

    if not all_item_indices:
        return None

    for u_idx, pos_p_indices in user_interactions.items():
        if not pos_p_indices: continue
        for pos_p_idx in pos_p_indices:
            # Simple negative sampling: pick a random item the user hasn't interacted with
            neg_p_idx = np.random.choice(all_item_indices)
            while neg_p_idx in pos_p_indices:
                neg_p_idx = np.random.choice(all_item_indices)

            users.append(u_idx)
            pos_items.append(pos_p_idx)
            neg_items.append(neg_p_idx)
    
    if not users:
        return None

    return torch.LongTensor(users), torch.LongTensor(pos_items), torch.LongTensor(neg_items)

def main():
    print("--- Starting LightGCN Model Training ---")
    
    try:
        db = next(get_db())
        # The build_graph function now returns the user_interactions dictionary
        graph, metadata, user_interactions = build_graph_from_db(db)
        db.close()

        # --- NEW: Data Sanity Check ---
        print("\n--- Data Sanity Check ---")
        num_users_found = metadata.get('num_users', 0)
        num_posts_found = metadata.get('num_posts', 0)
        total_interactions = sum(len(v) for v in user_interactions.values())
        
        print(f"Number of users in graph: {num_users_found}")
        print(f"Number of posts in graph: {num_posts_found}")
        print(f"Total user-item interactions found: {total_interactions}")
        
        if total_interactions == 0:
            print("\nCRITICAL: The database contains users and posts, but no interaction records were found.")
            print("Please ensure the data_collector.py script ran successfully and populated the 'interactions' table.")
            return
        # --- END NEW ---
        
        model = LightGCN(
            num_users=metadata['num_users'],
            num_items=metadata['num_posts']
        )
        model.graph = graph
        
        optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
        
        print("\nPreparing training data (BPR triplets)...")
        training_data = get_bpr_data(user_interactions, metadata['num_posts'])
        
        if training_data is None:
            print("\nCRITICAL: No training data could be generated from the found interactions.\n")
            return

        users, pos_items, neg_items = training_data
        print(f"Generated {len(users)} training triplets.")
        
        print("\nStarting training loop...")
        for epoch in range(EPOCHS):
            model.train()
            optimizer.zero_grad()
            
            all_users_emb, all_items_emb = model.computer()
            
            users_emb = all_users_emb[users]
            pos_items_emb = all_items_emb[pos_items]
            neg_items_emb = all_items_emb[neg_items]
            
            ranking_loss = bpr_loss(users_emb, pos_items_emb, neg_items_emb)
            reg_loss = regularization_loss(users_emb, pos_items_emb, neg_items_emb)
            loss = ranking_loss + L2_REG * reg_loss
            
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            
            if torch.isnan(loss):
                print(f"\nCRITICAL: Loss is NaN at epoch {epoch+1}. Stopping training.\n")
                break
            
            if (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{EPOCHS}, Loss: {loss.item():.4f} (Ranking: {ranking_loss.item():.4f}, Reg: {reg_loss.item():.4f})")
                
        if not torch.isnan(loss):
            torch.save(model.state_dict(), MODEL_SAVE_PATH)
            print(f"\n--- Training Complete. Model saved to {MODEL_SAVE_PATH} ---")

    except ValueError as e:
        print(f"\nCRITICAL ERROR during graph building: {e}")
        print("This usually means the database is empty. Please run data_collector.py first.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
