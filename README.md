# NEXUS

NEXUS is a hackathon-ready IT support intelligence platform that classifies tickets, retrieves supporting knowledge, recalls similar historical cases, and drafts traceable next steps for analyst review. It never executes remediation and never generates a resolution without reliable evidence.

## Why NEXUS

Support engineers often repeat unsuccessful steps or trust an answer without knowing its source. NEXUS separates classification, knowledge confidence, and historical similarity; displays successful and failed prior attempts; and returns **No Reliable Match** when the evidence threshold is not met.

## Features

- Ticket normalization and deterministic demo classification
- Configurable knowledge threshold and top-three local hybrid retrieval
- Evidence-gated resolution steps copied only from retrieved articles
- Historical Case Memory with successful and failed troubleshooting
- Editable analyst review, draft/approval/escalation states, and feedback API
- Recurrence and knowledge-gap signals with careful evidence language
- Explainable SLA-risk rules
- Service dependency and impact preview based on configured relationships
- 30 tickets, 14 knowledge articles, 20 historical cases, and five applications
- MongoDB persistence with automatic in-memory fallback
- Gemini-ready provider boundary and reliable no-key demo mode

## Architecture

```text
Support Analyst → React/Vite → FastAPI
                               ├─ Classification service
                               ├─ Knowledge retrieval
                               ├─ Historical Case Memory
                               ├─ Pattern/SLA rules
                               ├─ Dependency model
                               └─ MongoDB (in-memory fallback)
```

Language-model use is intentionally isolated from priority/evidence rules. The included demo implementation is deterministic. A Gemini adapter can later replace normalization and grounded summarization while receiving only the ticket and retrieved evidence.

## Technology

- React, Vite, React Router, Tailwind dependency, Lucide, Recharts
- FastAPI, Pydantic, optional MongoDB
- Lightweight local term-vector similarity (safe fallback for sentence-transformers)

## Quick start

Prerequisites: Node 20+, Python 3.11+, and optionally MongoDB.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:5173`. API documentation is at `http://localhost:8000/docs`.

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `MONGODB_URI` | MongoDB connection string; blank uses memory | blank |
| `MONGODB_DATABASE` | Database name | `nexus` |
| `GEMINI_API_KEY` | Optional future provider credential | blank |
| `AI_PROVIDER` | Provider abstraction selection | `gemini` |
| `DEMO_MODE` | Deterministic offline intelligence | `true` |
| `KB_MATCH_THRESHOLD` | Minimum top knowledge score | `0.38` |
| `FRONTEND_ORIGIN` | CORS origin | `http://localhost:5173` |
| `VITE_API_URL` | Browser API base | `http://localhost:8000/api` |

No keys are hardcoded. With no MongoDB or Gemini configured, all major flows still work.

## MongoDB

Set `MONGODB_URI=mongodb://localhost:27017`. On startup, an empty `tickets` collection receives the synthetic seed tickets. If MongoDB cannot be reached, NEXUS reports memory mode through `/health` and continues.

## Demo scenarios

1. `Users cannot login to NovaHR after resetting their password. The screen shows INVALID_TOKEN.` → Authentication / Token Session, KB-014, reliable grounded resolution, matching CASE-1827.
2. `Application displays error XYZ-982.` → No Reliable Match and no fabricated steps.
3. `Atlas CRM dashboard takes over two minutes to load.` → Performance / Slow Response, dashboard-query knowledge.
4. `Orbit ERP nightly invoice batch aborted.` → Batch Processing / Job Failure.
5. `Pulse Inventory stock counts are stale and not synchronizing.` → Integration / API Synchronization.
6. `Vertex Finance says access denied after my role was approved.` → Access / Permissions.
7. `Customer API returns HTTP 502 through Atlas CRM.` → Integration / API Gateway.
8. `VPN is connected but internal host does not resolve.` → Network / Connectivity.
9. `Application reports connection pool exhausted.` → Database / Connectivity.
10. `Orbit ERP signs active users out after five minutes.` → Authentication / Session.

Run automated checks with `cd backend; pytest`.

## API

The implemented endpoints match the brief: ticket analysis/classification/history/update/resolution, knowledge and case search/detail, patterns, dependencies, dashboard, and feedback. Explore request schemas interactively in FastAPI `/docs`.

## Grounding guarantee

When a knowledge match is reliable, every recommended step is selected verbatim from the `resolution_steps` of displayed retrieved articles and its KB IDs are returned in `source_references`. Below the configured threshold, `recommended_resolution` is empty and the response is `No Reliable Match`.

## Future improvements

- Add a production Gemini adapter with strict JSON-schema validation
- Add sentence-transformer embeddings and a persisted FAISS index
- Store all entities and analyst feedback in MongoDB collections
- Add SSO/RBAC, audit logs, article versioning, and change approvals
- Learn retrieval weights only from reviewed analyst feedback

