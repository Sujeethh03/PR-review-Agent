# Critic Agent + Dashboard — Design

## Purpose

Phase 4 closes the loop between specialist agent findings and human review. It has three parts:

1. **Critic agent** — challenges every finding from the three specialist agents, retrieves codebase context from ChromaDB, assigns a final confidence score, and drops false positives before any human sees them
2. **PostgreSQL** — persists surviving findings with status tracking (pending / approved / dismissed)
3. **Next.js approval dashboard** — lets a senior engineer review pre-filtered findings and approve or dismiss each one before anything reaches GitHub

This is Phase 4 of the build plan (weeks 7–8).

---

## Where it fits in the pipeline

```
specialist agents (bug + security + pattern)
        │
        │  list[Finding]
        ▼
┌─────────────────────────┐
│      Critic Agent        │ ◄── ChromaDB context
│                          │ ◄── PR intent (description + commits)
│  challenges every        │
│  finding individually    │
│  assigns confidence      │
│  drops false positives   │
└────────────┬────────────┘
             │  list[CriticResult]
             ▼
┌─────────────────────────┐
│    Severity Router       │
│                          │
│  >95% + high  → auto    │
│  70–95%       → queue   │
│  <70%         → digest  │
└──────┬──────────┬───────┘
       │          │
       ▼          ▼
   PostgreSQL   PostgreSQL
   (auto log)   (pending)
                   │
                   ▼
          Next.js Dashboard
          (approve / dismiss)
                   │
                   ▼
          # TODO Phase 5
          PR Writer Agent
```

---

## Where it lives

```
backend/
  app/
    agents/
      critic/
        __init__.py         ← exposes run_critic_agent()
        agent.py            ← critic logic — challenges each finding
        prompts.py          ← prompt templates
        code_utils.py       ← extract_flagged_code(), read_lines_from_repo()
    models/
      critic.py             ← CriticResult, CriticOutput Pydantic models
    db/
      __init__.py
      connection.py         ← SQLAlchemy async engine + session factory
      models.py             ← SQLAlchemy ORM models (Finding row, PRReview row)
      findings_repo.py      ← insert, update status, query findings
    api/
      findings.py           ← FastAPI routes for the dashboard (GET, PATCH)
  main.py                   ← wires critic + router + DB persistence

frontend/
  (Next.js app — scaffolded in this phase)
  app/
    page.tsx                ← findings list
    findings/
      [id]/
        page.tsx            ← individual finding detail + approve/dismiss
  components/
    FindingCard.tsx
    SeverityBadge.tsx
    ConfidenceMeter.tsx
```

---

## Shared models — `backend/app/models/critic.py`

```python
import hashlib
from pydantic import BaseModel
from app.models.findings import Finding


def finding_hash(finding: Finding) -> str:
    """Stable content-based ID — mirrors _chunk_id() in store.py."""
    key = f"{finding.file}:{finding.line_start}:{finding.category}"
    return hashlib.sha256(key.encode()).hexdigest()


class CriticVerdict(BaseModel):
    finding_hash: str                      # SHA256(file:line_start:category) — matches FindingRow.finding_hash
    accepted: bool                         # True = real problem, False = drop it
    final_confidence: float                # 0.0 – 1.0, critic's reassessed score
    reasoning: str                         # one sentence explaining the verdict
    context_used: list[str]                # symbol_names from ChromaDB that informed it


class CriticOutput(BaseModel):
    accepted: list[Finding]                # findings that survived — confidence updated to final_confidence
    rejected: list[Finding]                # findings the critic dropped
    verdicts: list[CriticVerdict]          # full decision record for every finding
```

`finding_hash()` uses the same SHA256 pattern as `_chunk_id()` in `store.py` so IDs are derived consistently across the pipeline.

---

## Critic agent — `critic/agent.py`

### What it does

The critic receives every finding from all three specialist agents and evaluates each one individually. Its single job is to answer: **is this actually a real problem, or does it just look like one?**

For each finding it:
1. Queries ChromaDB for surrounding context — upstream validators, middleware, existing error handlers
2. Checks whether the problem is already handled elsewhere in the codebase
3. Reasons about actual exploitability (for security findings) or actual execution path (for bugs)
4. Assigns a final confidence score that may be higher or lower than the specialist's score
5. Accepts or rejects the finding

### Step-by-step

```
run_critic_agent(findings, collection_name, diff, repo_path, pr_description)
        │
        ├── for each finding:
        │         ├── 1. extract flagged code
        │         │         → extract_flagged_code(diff, finding.file,
        │         │                                 finding.line_start, finding.line_end)
        │         │         → falls back to reading lines from repo_path if diff
        │         │           doesn't cover those lines (context-only lines)
        │         │
        │         ├── 2. query ChromaDB with the finding's file + lines
        │         │         → get surrounding functions, validators, middleware
        │         │
        │         ├── 3. build prompt
        │         │         ├── system: critic instructions
        │         │         ├── user:   the original finding (title, description, category)
        │         │         │           flagged_code (extracted above)
        │         │         │           ChromaDB context chunks
        │         │         └──         PR description (intent)
        │         │
        │         ├── 4. call GPT-4o → CriticVerdict
        │         │
        │         └── 5. if accepted: update finding.confidence = verdict.final_confidence
        │                              add to accepted list
        │                 if rejected: add to rejected list
        │
        └── return CriticOutput(accepted, rejected, verdicts)
```

### Prompt design — `critic/prompts.py`

```
SYSTEM:
You are a senior staff engineer performing a second-pass review of findings
flagged by automated analysis agents. Your job is to challenge each finding
and decide whether it represents a real problem worth a developer's attention.

For each finding you receive:
  - The original finding (category, severity, description, code location)
  - The exact code that was flagged
  - Related code from the same codebase (validators, middleware, callers)
  - The PR description (what the developer was trying to do)

Ask yourself:
  1. Is the flagged code actually reachable in a way that triggers the problem?
  2. Is there already a validator, middleware, or wrapper elsewhere in the
     codebase that handles this? (check the context chunks carefully)
  3. For security findings: is there an actual attack path, or is this a
     theoretical pattern match?
  4. Does the PR description suggest this was an intentional decision?

Accepted findings are ones where the problem is real AND not already handled.
Rejected findings are ones where:
  - The problem is already mitigated upstream
  - The code is unreachable in the flagged way
  - The finding is a style/informational issue, not a real defect
  - The context shows this is consistent with the codebase's established pattern

You must provide:
  - accepted: true or false
  - final_confidence: your reassessed confidence (0.0–1.0)
  - reasoning: one sentence explaining your verdict
  - context_used: which symbol_names from the context informed your decision

OUTPUT FORMAT: JSON matching the schema below.
{schema}

USER:
## Finding
Category  : {category}
Severity  : {severity}
File      : {file} lines {line_start}–{line_end}
Title     : {title}
Description: {description}

## Flagged code
{flagged_code}

## PR description
{pr_description}

## Related codebase context
{context_chunks}
```

### Special rules

- **Hardcoded secrets are never rejected.** If `category == "hardcoded_secret"`, the critic accepts it unconditionally with `final_confidence = 1.0`. A secret in source code has no valid mitigation in context.
- **Pattern findings without context are always rejected.** If the pattern agent flagged something but ChromaDB returned fewer than 3 context chunks (thin evidence of an established pattern), the critic rejects it.

---

## Severity router

After the critic, surviving findings are routed by `final_confidence` + `severity`:

```python
def route_finding(finding: Finding, verdict: CriticVerdict) -> Literal["auto", "queue", "digest"]:
    if verdict.final_confidence >= 0.95 and finding.severity == "high":
        return "auto"      # post to GitHub immediately — Phase 5
    elif verdict.final_confidence >= 0.70:
        return "queue"     # human dashboard for approval
    else:
        return "digest"    # weekly batch — Phase 5
```

`auto` findings are persisted with `status = "auto_posted"` (placeholder until Phase 5 builds the PR writer).
`queue` findings are persisted with `status = "pending"` and appear in the dashboard.
`digest` findings are persisted with `status = "digest"`.

---

## PostgreSQL schema — `db/models.py`

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, Integer, DateTime, Text, Enum, ForeignKey
from datetime import datetime
import enum


class FindingStatus(enum.Enum):
    pending      = "pending"
    approved     = "approved"
    dismissed    = "dismissed"
    auto_posted  = "auto_posted"
    digest       = "digest"


class Base(DeclarativeBase):
    pass


class PRReview(Base):
    __tablename__ = "pr_reviews"

    id:              Mapped[int]      = mapped_column(Integer, primary_key=True)
    owner:           Mapped[str]      = mapped_column(String(255))
    repo_name:       Mapped[str]      = mapped_column(String(255))
    pr_number:       Mapped[int]      = mapped_column(Integer)
    head_sha:        Mapped[str]      = mapped_column(String(40))
    collection_name: Mapped[str]      = mapped_column(String(255))
    created_at:      Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FindingRow(Base):
    __tablename__ = "findings"

    id:               Mapped[int]           = mapped_column(Integer, primary_key=True)
    finding_hash:     Mapped[str]           = mapped_column(String(64), unique=True)  # SHA256 — matches CriticVerdict.finding_hash
    pr_review_id:     Mapped[int]           = mapped_column(Integer, ForeignKey("pr_reviews.id"))
    agent:            Mapped[str]           = mapped_column(String(20))
    file:             Mapped[str]           = mapped_column(String(500))
    line_start:       Mapped[int]           = mapped_column(Integer)
    line_end:         Mapped[int]           = mapped_column(Integer)
    severity:         Mapped[str]           = mapped_column(String(10))
    category:         Mapped[str]           = mapped_column(String(50))
    title:            Mapped[str]           = mapped_column(String(500))
    description:      Mapped[str]           = mapped_column(Text)
    suggestion:       Mapped[str]           = mapped_column(Text)
    specialist_conf:  Mapped[float]         = mapped_column(Float)
    critic_conf:      Mapped[float]         = mapped_column(Float)
    critic_reasoning: Mapped[str]           = mapped_column(Text)
    route:            Mapped[str]           = mapped_column(String(10))  # auto / queue / digest
    status:           Mapped[FindingStatus] = mapped_column(
                          Enum(FindingStatus), default=FindingStatus.pending
                      )
    created_at:       Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at:      Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by:      Mapped[str | None]      = mapped_column(String(255), nullable=True)
```

---

## FastAPI routes — `api/findings.py`

```
GET  /findings                  list pending findings (status=pending, for dashboard)
GET  /findings/{id}             single finding detail
PATCH /findings/{id}/approve    set status = approved, record resolver
PATCH /findings/{id}/dismiss    set status = dismissed, record resolver
GET  /reviews                   list all PR reviews with finding counts per status
```

The dashboard polls `GET /findings` on load. Each card calls `PATCH /findings/{id}/approve` or `PATCH /findings/{id}/dismiss` on button click.

CORS must be enabled in `main.py` so the Next.js frontend (port 3000) can reach the FastAPI backend (port 8000):

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "PATCH"],
    allow_headers=["*"],
)
```

---

## Next.js dashboard — minimal viable UI

```
/                     ← finding list, grouped by PR
  PRReview card
    repo / PR number / date
    finding count (pending / approved / dismissed)
  FindingCard (per finding)
    [HIGH] app/payments.py:14
    Potential null reference on user lookup
    Confidence: 0.91 ████████░░
    [Approve] [Dismiss]

/findings/{id}        ← detail view
  Full description
  Exact code snippet (lines)
  Suggestion
  Critic reasoning
  Context used
  [Approve] [Dismiss]
```

Tech:
- **Next.js 14** (App Router)
- **TanStack Query** — fetches and revalidates findings from the FastAPI backend
- **shadcn/ui** — cards, badges, buttons
- No auth in Phase 4 — localhost only

---

## How it plugs into `main.py`

```python
from fastapi.middleware.cors import CORSMiddleware
from app.agents.critic import run_critic_agent
from app.agents.critic.router import route_finding
from app.db.findings_repo import save_review, save_findings
from app.models.critic import finding_hash

# add CORS middleware at app startup (below app = FastAPI())
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "PATCH"],
    allow_headers=["*"],
)

# inside the pull_request handler, replacing the Phase 4 TODO
critic_output = await run_critic_agent(
    findings=all_findings,
    collection_name=ingestion_result.collection_name,
    diff=diff,
    repo_path=repo_path,
    pr_description=pr.get("body", ""),
)
print(f"Critic: {len(critic_output.accepted)} accepted, {len(critic_output.rejected)} rejected")

verdict_by_hash = {v.finding_hash: v for v in critic_output.verdicts}
routes = {
    verdict_by_hash[finding_hash(f)].finding_hash: route_finding(f, verdict_by_hash[finding_hash(f)])
    for f in critic_output.accepted
}

review_id = await save_review(owner, repo_name, number, head_sha, ingestion_result.collection_name)
await save_findings(review_id, critic_output.accepted, critic_output.verdicts, routes)

# TODO Phase 5: pass auto-routed findings to PR writer agent
```

---

## Function signatures

### `critic/__init__.py`
```python
async def run_critic_agent(
    findings: list[Finding],
    collection_name: str,
    diff: str,
    repo_path: str,
    pr_description: str,
) -> CriticOutput: ...
```

### `critic/agent.py`
```python
async def challenge_finding(
    finding: Finding,
    flagged_code: str,
    context_chunks: list[dict],    # pre-fetched from ChromaDB by run_critic_agent
    pr_description: str,
) -> CriticVerdict: ...
```

### `critic/code_utils.py`
```python
def extract_flagged_code(
    diff: str,
    file: str,
    line_start: int,
    line_end: int,
    repo_path: str,
) -> str:
    # Extracts added lines from the diff that overlap with line_start–line_end
    # Falls back to read_lines_from_repo() if diff doesn't cover those lines
    ...

def read_lines_from_repo(
    repo_path: str,
    file: str,
    line_start: int,
    line_end: int,
) -> str:
    # Reads the exact lines from the cloned repo at /tmp/repos/...
    # Same repo_path passed from clone_repo() in repo_manager.py
    ...
```

### `db/findings_repo.py`
```python
async def save_review(owner, repo_name, pr_number, head_sha, collection_name) -> int: ...

async def save_findings(
    review_id: int,
    findings: list[Finding],
    verdicts: list[CriticVerdict],
    routes: dict[str, str],        # finding_hash → "auto" | "queue" | "digest"
) -> None: ...

async def get_pending_findings() -> list[FindingRow]: ...
async def get_review_summaries() -> list[dict]: ...   # for GET /reviews
async def resolve_finding(finding_id: int, status: FindingStatus, resolved_by: str) -> None: ...
```

### `api/findings.py`
```python
@router.get("/findings")
async def list_findings() -> list[FindingRow]: ...        # returns status=pending only

@router.get("/findings/{finding_id}")
async def get_finding(finding_id: int) -> FindingRow: ...

@router.get("/reviews")
async def list_reviews() -> list[dict]: ...               # repo, PR number, counts per status

@router.patch("/findings/{finding_id}/approve")
async def approve_finding(finding_id: int, resolved_by: str) -> FindingRow: ...

@router.patch("/findings/{finding_id}/dismiss")
async def dismiss_finding(finding_id: int, resolved_by: str) -> FindingRow: ...
```

---

## Dependencies added to `requirements.txt`

```
sqlalchemy>=2.0.0
asyncpg>=0.29.0
alembic>=1.13.0
psycopg2-binary>=2.9.0
```

## Environment variables added to `.env`

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string — `postgresql+asyncpg://user:pass@localhost/prreview` |

## Environment variables added to `frontend/.env.local`

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | FastAPI base URL — `http://localhost:8000` (TanStack Query uses this for all fetches) |

---

## Build order

1. `backend/app/models/critic.py` — `finding_hash()`, `CriticVerdict`, `CriticOutput`
2. `backend/app/agents/critic/prompts.py` — critic prompt templates
3. `backend/app/agents/critic/code_utils.py` — `extract_flagged_code()`, `read_lines_from_repo()`
4. `backend/app/agents/critic/agent.py` — `challenge_finding()`, `run_critic_agent()`
5. `backend/app/agents/critic/__init__.py` — public entry point
6. `backend/app/agents/critic/router.py` — `route_finding()` severity router
7. `backend/app/db/connection.py` — SQLAlchemy async engine + session factory
8. `backend/app/db/models.py` — `PRReview`, `FindingRow` ORM models
9. `backend/app/db/findings_repo.py` — DB operations
10. Run `alembic init alembic` then configure `alembic/env.py` with `DATABASE_URL` and import `Base` from `db/models.py` — generate and apply migration with `alembic revision --autogenerate -m "create tables"` + `alembic upgrade head`
11. `backend/app/api/findings.py` — FastAPI routes, include router in `main.py`
12. Add CORS middleware and wire critic into `main.py`
13. `frontend/` — `npx create-next-app`, scaffold finding list + detail pages with TanStack Query + shadcn/ui

---

## What is NOT done in this phase

- PR writer agent — Phase 5, posts inline GitHub review comments
- Severity routing to GitHub (auto-post) — Phase 5
- Weekly digest email — Phase 5
- Dashboard authentication — deferred (localhost only in Phase 4)
- LangSmith tracing — works automatically when env vars are set
