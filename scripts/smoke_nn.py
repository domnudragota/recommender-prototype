#!/usr/bin/env python3
import argparse
import json
import torch

from backend.app.db import connect
from backend.recommender.nn_model import NeuralRecClassifier


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/nn_recommender.pt")
    ap.add_argument("--user-id", type=int, default=1)
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--limit-items", type=int, default=200)  # just score first N items for quick smoke test
    args = ap.parse_args()

    artifact = torch.load(args.model, map_location="cpu")
    num_users = artifact["num_users"]
    num_items = artifact["num_items"]
    embed_dim = artifact["embed_dim"]

    model = NeuralRecClassifier(num_users=num_users, num_items=num_items, embed_dim=embed_dim)
    model.load_state_dict(artifact["model_state_dict"])
    model.eval()

    user_idx = args.user_id - 1
    if user_idx < 0 or user_idx >= num_users:
        raise SystemExit("Invalid user_id for this model")

    # score a subset of items for quick testing
    item_indices = torch.arange(min(args.limit_items, num_items), dtype=torch.long)
    user_indices = torch.full_like(item_indices, fill_value=user_idx)

    with torch.no_grad():
        logits = model(user_indices, item_indices)
        probs = torch.sigmoid(logits)

    scored = list(zip(item_indices.tolist(), probs.tolist()))
    scored.sort(key=lambda x: x[1], reverse=True)

    top = scored[: args.topk]

    # pull titles from DB for nicer output
    conn = connect()
    results = []
    for item_idx0, p in top:
        item_id = item_idx0 + 1
        row = conn.execute("SELECT title, genres FROM items WHERE id = ?", (item_id,)).fetchone()
        title = row["title"] if row else f"item_{item_id}"
        genres = row["genres"] if row else ""
        results.append({"item_id": item_id, "p_like": p, "title": title, "genres": genres})
    conn.close()

    print(json.dumps({"user_id": args.user_id, "top": results}, indent=2))


if __name__ == "__main__":
    main()
