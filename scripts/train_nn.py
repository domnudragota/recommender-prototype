#!/usr/bin/env python3
import argparse
import os
import random
from dataclasses import dataclass
from typing import List, Tuple

import torch
from torch.utils.data import Dataset, DataLoader

from backend.app.db import connect, init_db
from backend.recommender.nn_model import NeuralRecClassifier


@dataclass
class TrainConfig:
    epochs: int
    batch_size: int
    lr: float
    embed_dim: int
    seed: int
    out_path: str


class RatingsDataset(Dataset):
    def __init__(self, pairs: List[Tuple[int, int, int]]):
        self.pairs = pairs

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(self, idx: int):
        u, it, y = self.pairs[idx]
        return (
            torch.tensor(u, dtype=torch.long),
            torch.tensor(it, dtype=torch.long),
            torch.tensor(y, dtype=torch.float32),
        )


def load_training_pairs_from_db() -> Tuple[List[Tuple[int, int, int]], int, int]:
    """
    Returns:
      pairs: (user_idx, item_idx, label) where indices are 0-based for embeddings
      num_users: max user_id
      num_items: max item_id
    Label definition:
      label = 1 if rating >= 4 else 0
    """
    conn = connect()
    init_db(conn)

    # pull only rows that have ratings (MovieLens seeding uses event_type='rating')
    rows = conn.execute(
        """
        SELECT user_id, item_id, rating
        FROM interactions
        WHERE rating IS NOT NULL
        """
    ).fetchall()

    # determine embedding sizes (MovieLens IDs are 1..N, but we handle safely)
    max_user = conn.execute("SELECT MAX(id) AS m FROM users").fetchone()["m"] or 0
    max_item = conn.execute("SELECT MAX(id) AS m FROM items").fetchone()["m"] or 0

    conn.close()

    pairs: List[Tuple[int, int, int]] = []
    for r in rows:
        user_id = int(r["user_id"])
        item_id = int(r["item_id"])
        rating = int(r["rating"])

        # 0-based indices for embeddings
        user_idx = user_id - 1
        item_idx = item_id - 1

        label = 1 if rating >= 4 else 0
        pairs.append((user_idx, item_idx, label))

    return pairs, int(max_user), int(max_item)


def split_train_val(pairs: List[Tuple[int, int, int]], seed: int, val_ratio: float = 0.2):
    random.Random(seed).shuffle(pairs)
    n = len(pairs)
    n_val = int(n * val_ratio)
    val = pairs[:n_val]
    train = pairs[n_val:]
    return train, val


@torch.no_grad()
def evaluate(model: NeuralRecClassifier, loader: DataLoader, device: torch.device) -> Tuple[float, float]:
    model.eval()
    loss_fn = torch.nn.BCEWithLogitsLoss()

    total_loss = 0.0
    total = 0
    correct = 0

    for u, it, y in loader:
        u = u.to(device)
        it = it.to(device)
        y = y.to(device)

        logits = model(u, it)
        loss = loss_fn(logits, y)

        probs = torch.sigmoid(logits)
        preds = (probs >= 0.5).float()

        total_loss += float(loss.item()) * y.size(0)
        total += y.size(0)
        correct += int((preds == y).sum().item())

    avg_loss = total_loss / max(total, 1)
    acc = correct / max(total, 1)
    return avg_loss, acc


def train(cfg: TrainConfig):
    pairs, num_users, num_items = load_training_pairs_from_db()
    if not pairs:
        raise SystemExit("No training data found. Did you run make seed-ml100k ?")

    train_pairs, val_pairs = split_train_val(pairs, seed=cfg.seed, val_ratio=0.2)

    train_ds = RatingsDataset(train_pairs)
    val_ds = RatingsDataset(val_pairs)

    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=cfg.batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = NeuralRecClassifier(num_users=num_users, num_items=num_items, embed_dim=cfg.embed_dim).to(device)

    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)
    loss_fn = torch.nn.BCEWithLogitsLoss()

    print(f"Device: {device}")
    print(f"Train samples: {len(train_ds)} | Val samples: {len(val_ds)}")
    print(f"Users: {num_users} | Items: {num_items} | embed_dim: {cfg.embed_dim}")

    for epoch in range(1, cfg.epochs + 1):
        model.train()
        running_loss = 0.0
        seen = 0

        for u, it, y in train_loader:
            u = u.to(device)
            it = it.to(device)
            y = y.to(device)

            opt.zero_grad()
            logits = model(u, it)
            loss = loss_fn(logits, y)
            loss.backward()
            opt.step()

            running_loss += float(loss.item()) * y.size(0)
            seen += y.size(0)

        train_loss = running_loss / max(seen, 1)
        val_loss, val_acc = evaluate(model, val_loader, device)

        print(f"Epoch {epoch:02d}/{cfg.epochs} | train_loss={train_loss:.4f} | val_loss={val_loss:.4f} | val_acc={val_acc:.4f}")

    # save artifact
    os.makedirs(os.path.dirname(cfg.out_path), exist_ok=True)
    artifact = {
        "model_state_dict": model.state_dict(),
        "num_users": num_users,
        "num_items": num_items,
        "embed_dim": cfg.embed_dim,
        "label_rule": "rating>=4 => 1 else 0",
    }
    torch.save(artifact, cfg.out_path)
    print(f"Saved model to: {cfg.out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch-size", type=int, default=512)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--embed-dim", type=int, default=32)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=str, default="models/nn_recommender.pt")
    args = ap.parse_args()

    cfg = TrainConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        embed_dim=args.embed_dim,
        seed=args.seed,
        out_path=args.out,
    )
    train(cfg)


if __name__ == "__main__":
    main()
