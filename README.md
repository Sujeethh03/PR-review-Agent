# PR Review Agent

An AI-powered code review pipeline that analyses GitHub pull requests the moment code is pushed — detecting bugs, security vulnerabilities, and convention violations — and posts structured inline comments with one-click fix suggestions directly on the diff.

Built on a multi-agent architecture where specialist agents work in parallel, findings are routed by confidence and severity, and every comment includes educational context explaining *why* the issue matters.

---

## Agent architecture

```
                        ┌─────────────────────┐
                        │   GitHub Webhook     │
                        │   (FastAPI + HMAC)   │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │   Ingestion Agent    │
                        │                      │
                        │  Clones repo at PR   │
                        │  head SHA, chunks    │
                        │  code via tree-sitter│
                        │  and stores vectors  │
                        │  in ChromaDB         │
                        └──────────┬──────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                     │
   ┌──────────▼────────┐  ┌───────▼────────┐  ┌────────▼───────┐
   │    Bug Detection   │  │    Security    │  │    Pattern     │
   │                    │  │                │  │                │
   │  Null refs, logic  │  │  OWASP Top 10  │  │  Convention    │
   │  errors, missing   │  │  hardcoded     │  │  consistency   │
   │  validations       │  │  secrets, auth │  │  vs codebase   │
   └──────────┬─────────┘  └───────┬────────┘  └────────┬───────┘
              │                    │                     │
              └────────────────────┼─────────────────────┘
                                   │
                        ┌──────────▼──────────┐
                        │   Deduplication      │
                        │                      │
                        │  Two-pass collapse:  │
                        │  by category then    │
                        │  by line — keeps     │
                        │  highest confidence  │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │   Severity Router    │
                        └──────────┬──────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            │                      │                       │
   ┌────────▼────────┐  ┌──────────▼──────────┐  ┌────────▼───────┐
   │      auto        │  │       queue          │  │    digest      │
   │                  │  │                      │  │                │
   │  conf ≥ 95%      │  │  conf ≥ 70%          │  │  Everything    │
   │  + high severity │  │  or high severity    │  │  else, batched │
   │                  │  │                      │  │  for weekly    │
   │  Posts to GitHub │  │  Human approval      │  │  email         │
   │  immediately     │  │  dashboard           │  │                │
   └────────┬─────────┘  └──────────┬──────────┘  └────────────────┘
            │                       │ (approved)
            └───────────────────────┘
                                   │
                        ┌──────────▼──────────┐
                        │   PR Writer Agent    │
                        │                      │
                        │  GPT-4o generates    │
                        │  corrected code →    │
                        │  inline GitHub       │
                        │  comment with        │
                        │  suggestion block    │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │  Educational Layer   │
                        │                      │
                        │  OWASP reference +   │
                        │  real-world impact   │
                        │  in every comment    │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │     GitHub PR        │
                        │  Inline comment on   │
                        │  exact diff line     │
                        └─────────────────────┘
```

---

## What gets posted

Each finding becomes an inline PR comment containing:

- **Severity and category** — `HIGH — hardcoded_secret`, `MEDIUM — missing_validation`
- **Description** — what the agent found and why it flagged it
- **Suggested fix** — a GitHub suggestion block the developer can apply with one click
- **Educational context** — the real-world impact of the issue and a link to the relevant OWASP standard

A comment about a hardcoded API key does not just say "use an environment variable." It explains that the key is permanently exposed in git history even after deletion, and links to OWASP A02:2021 — Cryptographic Failures.

---

## Approval dashboard

Medium-confidence findings land in a Next.js dashboard before touching GitHub. Reviewers see a filterable findings table with severity badges, confidence scores, full descriptions, and a direct link to the flagged line on GitHub.

Approving a finding triggers the PR writer. Dismissing it removes it from the queue. Nothing reaches a developer's PR without a human sign-off — or a confidence score above 95%.

---

## Tech stack

| | |
|---|---|
| **Backend** | Python · FastAPI · LangGraph · SQLAlchemy 2.0 async |
| **LLM** | OpenAI GPT-4o (agents + code fix generation) |
| **Embeddings** | OpenAI `text-embedding-3-small` · ChromaDB |
| **Code parsing** | tree-sitter (100+ languages) |
| **Database** | PostgreSQL 17 · Alembic |
| **Dashboard** | Next.js 16 · shadcn/ui · Tailwind CSS |
| **GitHub integration** | GitHub App · JWT auth · PR Review API |

---

## Getting started

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install --index-url https://pypi.org/simple/ -r requirements.txt
```

Create `backend/.env`:

```env
GITHUB_APP_ID=your_app_id
GITHUB_WEBHOOK_SECRET=your_webhook_secret
GITHUB_PRIVATE_KEY_PATH=/path/to/private-key.pem
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+asyncpg://user:password@localhost/prreview
```

```bash
alembic upgrade head
uvicorn main:app --reload
```

### Dashboard

```bash
cd frontend
npm install && npm run dev
```

### Webhook tunnel (local development)

```bash
npx smee-client --url https://smee.io/YOUR_CHANNEL --target http://localhost:8000/webhook
```

Open or push to a PR on any repo with the GitHub App installed — the pipeline runs automatically.

---

## Further reading

Full system design, architectural decisions, and build plan: [`docs/code_review_system_v1.0.0.md`](docs/code_review_system_v1.0.0.md)
