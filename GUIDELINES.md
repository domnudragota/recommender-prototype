# Web/Mobile Media Recommender - Prototype Implementation Notes

This document describes what the prototype code does (backend + recommender + logging + metrics) and how it was tested end-to-end.

---

## 1) What the system does

The project is a **recommender system prototype** that exposes a REST API. It can:
- load and store a public dataset (MovieLens 100K) into **SQLite**
- generate recommendations using:
  - a **baseline heuristic** recommender
  - a **Neural Network** classifier recommender (optional, if model is trained/loaded)
- log what was shown to the user (**impressions**) and what the user did (**engagements**)
- compute **PaC (Precision at Curation)** from logged impressions + engagements

The emphasis is on having a complete systems pipeline (serve → log → evaluate), not on maximum ML performance.

---

## 2) Tech stack

- **FastAPI**: REST API + Swagger UI (`/docs`)
- **SQLite**: local database (`data/app.db`)
- **PyTorch**: NN model training + inference (optional; baseline works without it)
- **Makefile**: convenience targets for setup, seeding, training

---

## 3) Project flow

### Step A: Dataset → DB
MovieLens files are fetched and seeded into SQLite:
- users → `users`
- items → `items`
- ratings → `interactions`

### Step B: Recommendation request
Client calls:
- `GET /recommendations?user_id=...&k=...&engine=auto|baseline|nn`

API:
1) validates `user_id`
2) generates top-K items
3) logs an **impression** row containing:
   - `recset_id` (UUID)
   - `user_id`
   - `engine` used
   - `item_ids_json` (ranked list of recommended item IDs)
4) returns JSON: `recset_id` + list of items

### Step C - Engagement logging
Client logs actions (click/like/watch) using:
- `POST /events/engagement`

This creates a row in `engagements` tied to a `recset_id`.

### Step D - Evaluation (PaC)
PaC is computed using:
- `GET /metrics/pac`

It checks: for each impression, how many of the top-K items were engaged within a time window.

---

## 4) Database schema (main tables)

### `users`
- demographic metadata (MovieLens users)

### `items`
- movies metadata + genres

### `interactions`
- MovieLens ratings (event_type `"rating"`, rating 1..5, ts)

### `rec_impressions` 
Logs each recommendation list served.
- `recset_id` (PK)
- `user_id`
- `engine` (`baseline` or `nn`)
- `item_ids_json` (ranked list)
- `ts`

### `engagements`
Logs user actions for items shown in an impression.
- `recset_id` (FK)
- `user_id`
- `item_id`
- `action_type` (e.g., `click`)
- `ts`

---

## 5) Recommenders

### 5.1 Baseline recommender
Implemented as a **weighted scoring heuristic**:
- Candidate pool: globally popular items (by interaction count)
- Filter out items already seen by the user
- Score each candidate by:
  - popularity (log-normalized)
  - global average rating
  - genre match to user profile (derived from ratings >= 4)

Final score:
- `0.55 * popularity + 0.25 * avg_rating + 0.20 * genre_match`

Output: top-K unseen items.

### 5.2 NN recommender (M3 + M4)
Train an NN classifier:
- input: `(user_id, item_id)`
- output: `P(like)` (sigmoid probability)
- label rule: `rating >= 4 => 1 else 0`
- model: user embedding + item embedding + small MLP

Inference:
- candidate pool: popular items
- filter seen items
- score candidates with NN
- return top-K by `p_like`

Engine selection:
- `engine=baseline` → baseline only
- `engine=nn` → NN only (requires trained model loaded)
- `engine=auto` → use NN if model loaded and user has enough history; otherwise baseline

---

## 6) Precision at Curation metric 

PaC definition used in this prototype:

For each impression:
- take top-K recommended items
- count engaged items within `window_hours`
- PaC(impression) = hits / K

API returns:
- `pac_mean`: mean of PaC over impressions
- `pac_micro`: total_hits / total_recommended
- counts: impressions, total_hits, total_recommended

Filtering:
- by `engine` (`baseline` or `nn`)
- by `platform` (web/mobile)
- by `action_types` (e.g., click)

---

## 7) How we tested it (step-by-step)

### 7.1 Setup & run
1) Create venv + install deps:
```bash
make install
````

2. Seed database (MovieLens → SQLite):

```bash
make seed-ml100k
```

3. Run API:

```bash
make dev
```

Open Swagger UI:

* [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### 7.2 Verify data is present

Call:

* `GET /debug/users`
* `GET /debug/items`
* `GET /debug/interactions?user_id=1`

---

### 7.3 Test baseline recommendations + impression logging 

1. Call:

* `GET /recommendations?user_id=1&k=5&engine=baseline`

2. Copy:

* `recset_id`
* one `item_id` from returned list

3. Verify impression exists:

* `GET /debug/impressions?user_id=1`

Expected: entries with `engine="baseline"`.

---

### 7.4 Test engagement logging (M5)

1. Post engagement in Swagger:

* `POST /events/engagement`

Body (example):

```json
{
  "recset_id": "PASTE_RECSET_ID",
  "user_id": 1,
  "item_id": 313,
  "action_type": "click",
  "platform": "web"
}
```

2. Verify engagement:

* `GET /debug/engagements?recset_id=PASTE_RECSET_ID`

Expected: row contains `action_type="click"` and a valid timestamp.

**Important testing note**: do not leave Swagger defaults like `"string"` or `ts=0`, otherwise hits won’t count for PaC.

---

### 7.5 Test PaC 

Compute PaC over all data:

```text
GET /metrics/pac?start_ts=0&k=5&window_hours=168&action_types=click
```

Expected:

* `impressions > 0`
* `total_hits > 0` after at least one correct click
* `pac_micro` roughly `hits / (impressions * K)` for this test

Compare engines:

```text
GET /metrics/pac?start_ts=0&k=5&window_hours=168&engine=baseline&action_types=click
GET /metrics/pac?start_ts=0&k=5&window_hours=168&engine=nn&action_types=click
```

---

### 7.6 Train NN 

Train and save model:

```bash
make train-nn
```

Smoke inference:

```bash
make smoke-nn
```

Then restart API (model loads on startup):

```bash
make dev
```

Check model loaded:

* `GET /debug/model` → `nn_loaded: true`

Test NN recommendations:

* `GET /recommendations?user_id=1&k=5&engine=nn`
* `GET /recommendations?user_id=1&k=5&engine=auto`

---

## 8) Encountered issues

### Foreign key reset error when reseeding

Because new tables reference `users/items`, reset must delete child tables first:

* `engagements` → `rec_impressions` → `interactions` → `items` → `users`

### Genre alignment issue (“unknown|0”)

MovieLens genre flags are aligned by genre id (includes `unknown|0`).
Fix: load genres by id and only skip `"unknown"` when building item genre strings.

---




