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
