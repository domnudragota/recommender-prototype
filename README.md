# Recommender System Prototype - Systems Engineering Project

This repository contains a **basic prototype** of a recommender system designed for a **web/mobile media environment** (e.g., videos, articles, posts).  
The project is developed as part of a **Systems Engineering course**, where the main focus is on the *engineering process and deliverables*, while the implementation here serves as a **representative module** that demonstrates the system’s core behavior end-to-end.

## What this prototype does (current + target)
The implementation is built around a simple but realistic pipeline:

1. **Collect interaction events** (views/clicks/likes, per platform: web or mobile)
2. **Generate personalized recommendations** (top-K items per user)
3. **Log impressions + engagements** to support evaluation
4. **Compute a quality metric (PaC — Precision at Curation)** from real logs

The goal is to provide something demo-able and “significant enough” for the implementation requirement, without overbuilding a production system.

---

## Tech Stack (Why these technologies)

### Python
Chosen for fast prototyping and strong ML/data ecosystem. It allows us to implement:
- dataset loading and preprocessing
- recommendation algorithms (baseline + NN)
- quick experiments and evaluation

### FastAPI (Backend API)
A lightweight web framework to expose the recommender as a REST service.
Benefits:
- fast development
- automatic interactive API docs via Swagger (`/docs`)
- clean request/response validation (Pydantic)

### Uvicorn
ASGI server used to run FastAPI locally.

### SQLite (Database)
Used to keep the prototype simple and portable:
- no external DB server required
- easy local setup
- enough for storing items, users, interactions, impressions, and engagements

*(We may switch to Postgres later if needed, but SQLite is ideal for a prototype.)*

### (Planned) PyTorch
Will be used to train a small neural-network model for scoring `(user, item)` pairs.

---

## Planned Architecture (High-level)
The system will be split into:
- **Offline tasks** (scripts): seeding dataset, training model artifacts
- **Online service** (FastAPI backend): serving recommendations and logging events

The client side (web/mobile) will be represented by:
- API calls (Swagger/Postman) and optionally a tiny demo UI later.

---

## How to run (dev)
```bash
make install
cp .env.example .env
make dev
```

--- 
## Resources and bibliography (implementation-focused)

- FastAPI. (n.d.). *Lifespan Events*. https://fastapi.tiangolo.com/advanced/events/

- FastAPI. (n.d.). *Settings and Environment Variables*. https://fastapi.tiangolo.com/advanced/settings/

- GroupLens Research. (1998). *MovieLens 100K Dataset*.  https://grouplens.org/datasets/movielens/100k/

- Harper, F. M., & Konstan, J. A. (2015). The MovieLens datasets: History and context. *ACM Transactions on Interactive Intelligent Systems, 5*(4), Article 19. https://doi.org/10.1145/2827872

- Pydantic. (n.d.). *Pydantic Settings: Settings Management*. https://docs.pydantic.dev/latest/concepts/pydantic_settings/

- PyTorch. (n.d.). *torch.nn.Embedding*. https://docs.pytorch.org/docs/stable/generated/torch.nn.Embedding.html

- PyTorch. (n.d.). *torch.nn.BCEWithLogitsLoss*. https://docs.pytorch.org/docs/stable/generated/torch.nn.BCEWithLogitsLoss.html

- SQLite. (n.d.). *Foreign Key Support*. https://sqlite.org/foreignkeys.html

- Uvicorn. (n.d.). *Uvicorn Documentation*. https://uvicorn.dev/

- Neural Collaborative Filtering. https://www.geeksforgeeks.org/deep-learning/neural-collaborative-filtering/

