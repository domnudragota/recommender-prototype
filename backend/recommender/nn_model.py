import torch
import torch.nn as nn


class NeuralRecClassifier(nn.Module):
    def __init__(self, num_users: int, num_items: int, embed_dim: int = 32):
        super().__init__()

        self.user_emb = nn.Embedding(num_users, embed_dim)
        self.item_emb = nn.Embedding(num_items, embed_dim)

        hidden = embed_dim * 2
        self.mlp = nn.Sequential(
            nn.Linear(hidden, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),  # logits
        )

        # small init helps stabilize early training
        nn.init.normal_(self.user_emb.weight, mean=0.0, std=0.01)
        nn.init.normal_(self.item_emb.weight, mean=0.0, std=0.01)

    def forward(self, user_idx: torch.Tensor, item_idx: torch.Tensor) -> torch.Tensor:
        """
        user_idx: (B,)
        item_idx: (B,)
        returns: logits (B,)
        """
        u = self.user_emb(user_idx)
        i = self.item_emb(item_idx)
        x = torch.cat([u, i], dim=1)
        logits = self.mlp(x).squeeze(1)
        return logits
