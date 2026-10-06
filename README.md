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
- Closed-loop resolution capture that adds reviewed outcomes to Case Memory
- Auditable ticket evidence timelines and per-step KB traceability
- Deterministic major-incident clusters and careful change correlation
- Historical troubleshooting outcome comparison
- Explainable KB health scores and structured conflict detection
- Analyst handover summaries and “Why this recommendation?” evidence panels
- 30 tickets, 14 knowledge articles, 20 historical cases, and five applications
- MongoDB persistence with automatic in-memory fallback
- Optional Gemini 2.5 Flash provider with strict validation and reliable no-key demo fallback
- Two-to-five low-risk AI investigation suggestions when no reliable knowledge match exists, clearly separated from evidence-backed resolutions

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

Language-model use is isolated from safety-critical rules. Gemini 2.5 Flash can enhance normalization, extraction, validated classification suggestions, grounded wording, explanations and handovers. Retrieval, No Reliable Match, SLA risk, clusters, change correlation, dependencies, KB health, conflicts and approval remain deterministic. Demo mode makes no external calls.

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

### Demo login

The frontend uses a lightweight local demo session. It is suitable for the hackathon prototype, not production authentication.

| Role | Email | Password |
|---|---|---|
| Support Analyst | `analyst@nexus.local` | `Nexus@123` |
| Support Manager | `manager@nexus.local` | `Demo@123` |

All workspace routes redirect unauthenticated visitors to `/login`. Use the sign-out icon beside the current analyst in the sidebar to end the local session.

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `MONGODB_URI` | MongoDB connection string; blank uses memory | blank |
| `MONGODB_DATABASE` | Database name | `nexus` |
| `GEMINI_API_KEY` | Optional Gemini credential; blank triggers local fallback | blank |
| `AI_PROVIDER` | Provider abstraction selection | `gemini` |
| `GEMINI_MODEL` | Gemini model | `gemini-2.5-flash` |
| `GEMINI_FALLBACK_MODEL` | Used when the API project lacks access to the primary model | `gemini-3.5-flash-lite` |
| `AI_TEMPERATURE` | Low-variance generation temperature | `0.2` |
| `DEMO_MODE` | `true` disables all external AI calls | `false` in example; local fallback if no key |
| `KB_MATCH_THRESHOLD` | Minimum top knowledge score | `0.38` |
| `FRONTEND_ORIGIN` | CORS origin | `http://localhost:5173` |
| `VITE_API_URL` | Browser API base | `http://localhost:8000/api` |

No keys are hardcoded. With no MongoDB or Gemini configured, all major flows still work. Set `DEMO_MODE=true` for a guaranteed offline demonstration. Enhanced-provider failures are logged without secrets and display the subtle message “Enhanced analysis unavailable. Local analysis was used.”

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

Advanced demo paths:

- Open `TKT-2041` to see the NovaHR cluster, `CHG-102` correlation, step-level sources, historical outcomes, evidence timeline, handover, and recommendation explanation.
- Use **Resolve ticket** to capture successful/failed steps and add the reviewed result to Case Memory.
- Open **Clusters** for the NovaHR and Orbit ERP groupings; cluster wording deliberately says “possible” rather than asserting a cause.
- Open **Changes** for temporal correlation evidence and **Knowledge Base** for Healthy / Needs Review / Poor article examples.

Run automated checks with `cd backend; pytest`.

## API

The implemented endpoints match the original brief plus the extension APIs: resolution learning, ticket timeline, handover, explanations, historical outcomes, clusters and status review, changes and correlations, KB health, and knowledge conflicts. Explore request schemas interactively in FastAPI `/docs`.

## Grounding guarantee

When a knowledge match is reliable, every recommended step is selected verbatim from the `resolution_steps` of displayed retrieved articles and its KB IDs are returned in `source_references`. Below the configured threshold, `recommended_resolution` is empty and the response is `No Reliable Match`.

## Future improvements

- Add provider telemetry dashboards and configurable per-operation timeouts
- Add sentence-transformer embeddings and a persisted FAISS index
- Store all entities and analyst feedback in MongoDB collections
- Add SSO/RBAC, audit logs, article versioning, and change approvals
- Learn retrieval weights only from reviewed analyst feedback

