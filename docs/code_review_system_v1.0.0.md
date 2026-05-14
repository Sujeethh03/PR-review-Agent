---
title: Multi-Agent Code Review System
subtitle: Product Design Document
version: 1.1.0
status: Active
author: 
created: 2026-04-06
last_updated: 2026-05-14
reviewed_by: 
approved_by: 
next_review: 2026-06-14
classification: Internal
project_code: CR-001
repository: github.com/your-org/code-review-agent
tech_lead: 
product_owner: 
tags: [ai, agents, code-review, langgraph, fastapi, rag, github]
---

# Multi-Agent Code Review System

> A pipeline of specialised AI agents that automatically reviews code the moment it is pushed to GitHub — detecting bugs, flagging security issues, and surfacing structured, human-approved feedback within 60 seconds.

---

## Document Control

| Field | Details |
|---|---|
| **Document title** | Multi-Agent Code Review System — Product Design Document |
| **Version** | 1.1.0 |
| **Status** | Active |
| **Author** | — |
| **Created** | 06 April 2026 |
| **Last updated** | 14 May 2026 |
| **Reviewed by** | — |
| **Approved by** | — |
| **Next review date** | 14 June 2026 |
| **Classification** | Internal |
| **Project code** | CR-001 |
| **Repository** | github.com/your-org/code-review-agent |

---

## Version History

| Version | Date | Author | Status | Summary of changes |
|---|---|---|---|---|
| 1.0.0 | 06 Apr 2026 | — | Superseded | Initial document — full system design including critic agent, severity routing, PR intent awareness, and educational comment layer |
| 1.1.0 | 14 May 2026 | — | Active | Updated to reflect implemented system: critic agent removed, direct confidence routing, PR writer agent with OWASP educational layer and GPT-4o suggestion blocks, Next.js approval dashboard, stale finding cleanup. Phases 1–5 complete (minus deployment). |

---

## Document Status

| Stage | Owner | Status | Date |
|---|---|---|---|
| First draft | Author | ✅ Complete | 06 Apr 2026 |
| v1.1 update | Author | ✅ Complete | 14 May 2026 |
| Technical review | Tech lead | ⬜ Pending | — |
| Product review | Product owner | ⬜ Pending | — |
| Final approval | — | ⬜ Pending | — |

---

## Table of Contents

1. [Overview](#1-overview)
2. [The Problem](#2-the-problem)
3. [What It Is](#3-what-it-is)
4. [Current System Structure](#4-current-system-structure)
5. [Full System Flow](#5-full-system-flow)
6. [How It Works — Step by Step](#6-how-it-works--step-by-step)
7. [Trust Model](#7-trust-model)
8. [Design Decisions](#8-design-decisions)
9. [What It Solves](#9-what-it-solves)
10. [Known Limitations](#10-known-limitations)
11. [Technology Stack](#11-technology-stack)
12. [Build Plan](#12-build-plan)
13. [Open Questions](#13-open-questions)
14. [Glossary](#14-glossary)

---

## 1. Overview

| Field | Details |
|---|---|
| **Product name** | Multi-Agent Code Review System |
| **Project code** | CR-001 |
| **Target users** | Engineering teams using GitHub for code review |
| **Primary language support** | All languages (tree-sitter for 100+ languages, line-based fallback for the rest) |
| **Deployment target** | Railway / Fly.io (backend), Vercel (dashboard) |
| **Trust level default** | Level 1 — read only |
| **Review turnaround** | Under 60 seconds from push to findings |

### Purpose

This document describes the full product design for the Multi-Agent Code Review System — an AI-powered pipeline that automatically reviews pull requests on GitHub. It covers the system architecture, agent responsibilities, trust model, design decisions, and build plan. It is intended as the single source of truth for anyone building, reviewing, or extending this system.

### Scope

This document covers the end-to-end pipeline from GitHub webhook to posted PR comment, including all agent logic, the human approval dashboard, severity routing, and the educational comment layer. It does not cover billing, user authentication for the dashboard, or multi-repository organisation management — these are deferred to a future version.

---

## 2. The Problem

When a developer pushes code at 6pm, the senior engineer is busy. The pull request sits unreviewed for two days. When the review finally arrives, it contains fifteen comments — half of which could have been caught automatically. Development slows. Quality erodes. Junior developers receive feedback too late to learn from it.

The root cause is not a lack of standards. It is a bottleneck: senior engineers are the only people capable of reviewing code thoroughly, and their time is finite.

### Pain points

| Pain point | Impact |
|---|---|
| PRs sit unreviewed for 1–2 days | Blocks developer momentum |
| Senior engineers spend hours on mechanical checks | Wastes high-value time |
| Noisy AI tools create false positives | Developers stop trusting and reading comments |
| Junior developers get feedback too late | Slows skill development |
| Critical security bugs wait overnight | Increases production risk |

---

## 3. What It Is

An AI-powered senior engineer that lives inside your GitHub repository. The moment a developer pushes code, a pipeline of specialised agents analyses the change and surfaces a structured review — ready for human sign-off — before the developer has closed their laptop.

Instead of one model doing everything, the system runs a coordinated pipeline of agents, each with a specific responsibility. They work in parallel and only surface a comment when confidence thresholds are met.

### Key metrics

| Metric | Target |
|---|---|
| Time from push to findings ready | < 60 seconds |
| Supported languages | All (tree-sitter for 100+ languages, line-based fallback for the rest) |
| Agents in the pipeline | 4 (ingestion, bug, security, pattern) |
| Trust levels | 3 |

---

## 4. Current System Structure

```
backend/
  main.py                          # FastAPI app — webhook receiver, pipeline orchestrator
  requirements.txt
  app/
    github_client.py               # GitHub App JWT auth, installation token, PR diff fetch
    repo_manager.py                # Shallow clone repo at PR head SHA → /tmp/repos/
    agents/
      router.py                    # Routes findings: auto / queue / digest by confidence + severity
      ingestion/
        __init__.py                # Exposes run_ingestion()
        agent.py                   # Full vs incremental ingest orchestrator
        walker.py                  # File walk, binary detection, skip list filtering
        parser.py                  # tree-sitter chunking + line-window fallback
        embedder.py                # Batched OpenAI embedding with retry
        store.py                   # ChromaDB collection management, upsert, delete
        diff_parser.py             # Parses unified diff → modified + deleted file paths
      specialist/
        graph.py                   # LangGraph fan-out: runs bug/security/pattern in parallel
        context.py                 # ChromaDB retrieval helper for agents
        diff_utils.py              # Diff hunk parsing for agent input
        bug/
          agent.py                 # Bug detection agent (GPT-4o with function calling)
          prompts.py
        security/
          agent.py                 # Security agent — OWASP Top 10 patterns (GPT-4o)
          prompts.py
        pattern/
          agent.py                 # Pattern agent — codebase convention checks (GPT-4o)
          prompts.py
      pr_writer/
        agent.py                   # Posts inline GitHub review comments, falls back to body comment
        formatter.py               # Formats findings as structured markdown comments
        suggester.py               # GPT-4o generates corrected code for suggestion blocks
        education.py               # OWASP category → "why this matters" + reference link
    api/
      findings.py                  # GET /findings, GET /stats, PATCH /findings/:id
    db/
      connection.py                # SQLAlchemy async session factory
      models.py                    # PRReview + FindingRow ORM models
      findings_repo.py             # All DB operations: save, query, resolve, dismiss stale
    models/
      chunks.py                    # Chunk dataclass + IngestionResult Pydantic model
      findings.py                  # Finding Pydantic model, finding_hash(), dedup logic
      ingestion_config.py          # IngestionConfig (thresholds, skip dirs, batch size)

frontend/
  app/
    layout.tsx                     # Root layout with Navbar
    page.tsx                       # Findings dashboard — status tabs, stats bar, findings table
    reviews/page.tsx               # PR review history list
  components/
    FindingsTable.tsx              # Severity-coloured table rows, route badges, drawer trigger
    FindingDrawer.tsx              # Sheet with full finding detail, GitHub links, approve/dismiss
    StatsBar.tsx                   # 4 metric cards (total / pending / approved / dismissed)
    Navbar.tsx                     # Dark nav with active route highlight
    SeverityBadge.tsx              # Coloured severity pill component
    ui/                            # shadcn/ui primitives (badge, button, card, sheet, table, tabs)

docs/
  code_review_system_v1.0.0.md    # This document
  design/
    repo_cloning.md
    ingestion_agent.md
    chromadb_storage.md
```

### Environment variables (`.env` in `backend/`)

| Variable | Purpose |
|---|---|
| `GITHUB_APP_ID` | GitHub App identifier |
| `GITHUB_WEBHOOK_SECRET` | HMAC secret for validating webhook signatures |
| `GITHUB_PRIVATE_KEY_PATH` | Path to GitHub App private key PEM file |
| `OPENAI_API_KEY` | OpenAI API key — used for embeddings (`text-embedding-3-small`) and agent reasoning (`gpt-4o`) |
| `DATABASE_URL` | PostgreSQL connection string (asyncpg driver) |

---

## 5. Full System Flow

```
GitHub Push / PR Open
        │
        ▼
┌─────────────────────────────────┐
│      FastAPI Receiver           │  validates HMAC-SHA256 signature,
│                                 │  filters noise events (review comments,
│                                 │  check runs, etc.) before processing
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│      Ingestion Agent            │  clones repo at head SHA,
│                                 │  chunks by function/class via tree-sitter,
│                                 │  embeds into ChromaDB vector store
│                                 │  (full on first PR, incremental thereafter)
└────────────────┬────────────────┘
                 │
        ┌────────┴────────┐
        │   parallel      │
        │   fan-out       │
        │  (LangGraph)    │
        │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Bug Detection│  │   Security   │  │   Pattern    │
│    Agent     │  │    Agent     │  │    Agent     │
│              │  │              │  │              │
│ null refs,   │  │ OWASP Top10, │  │ compares     │
│ logic errors,│  │ secrets,     │  │ diff against │
│ missed logic │  │ auth gaps    │  │ codebase     │
│ (GPT-4o)     │  │ (GPT-4o)     │  │ (GPT-4o)     │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │
       └─────────────────┴──────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │       Deduplication            │
        │                                │
        │  two-pass: by (file, line,     │
        │  category) then by (file, line)│
        │  keeps highest-confidence hit  │
        └───────────────┬────────────────┘
                        │
                        ▼
        ┌────────────────────────────────┐
        │       Severity Router          │
        │                                │
        │  routes by confidence score    │
        │  and finding severity          │
        └──────┬──────────┬──────────────┘
               │          │                    │
    conf≥95%   │   conf≥70%              conf<70%
    + high sev │   or high sev           + low/med
               │          │                    │
               ▼          ▼                    ▼
    ┌──────────────┐  ┌───────────────┐  ┌───────────────┐
    │  Auto-post   │  │    Human      │  │    Weekly     │
    │  to GitHub   │  │   Approval    │  │    Digest     │
    │  immediately │  │   Dashboard   │  │               │
    │              │  │  (Next.js 16) │  │  batched,     │
    │  [Level 3]   │  │  [Level 1/2]  │  │  low priority │
    └──────┬───────┘  └──────┬────────┘  └───────────────┘
           │                 │
           │          human approve
           │                 │
           └────────┬────────┘
                    │
                    ▼
        ┌─────────────────────────────────────┐
        │          PR Writer Agent            │
        │                                     │
        │  generates code fix via GPT-4o      │
        │  formats finding as inline comment  │
        │  attaches to exact line number      │
        │  includes ````suggestion```` block  │
        └──────────────────┬──────────────────┘
                           │
                           ▼
        ┌─────────────────────────────────────┐
        │         Educational Layer           │
        │                                     │
        │  OWASP category → impact statement  │
        │  links to OWASP Top 10 reference    │
        │  severity fallback for non-OWASP    │
        └──────────────────┬──────────────────┘
                           │
                           ▼
        ┌─────────────────────────────────────┐
        │            GitHub API               │
        │                                     │
        │  POST /pulls/:id/reviews            │
        │  inline comment on exact diff line  │
        │  falls back to PR body comment      │
        └─────────────────────────────────────┘
```

### Stale finding cleanup

When a new commit is pushed to an open PR, all pending findings from previous commits are automatically dismissed (`system:superseded`) so the dashboard only shows findings relevant to the current head. When a PR is closed, all remaining pending findings are dismissed.

---

## 6. How It Works — Step by Step

### Step 1 — A push triggers the pipeline

When code is pushed to GitHub, a webhook fires instantly. The system receives the event, validates the HMAC-SHA256 signature, and filters noise events (check runs, review comments, status events) before processing. From this moment, the clock is running.

### Step 2 — The codebase is made searchable

A dedicated ingestion agent clones the repository at the PR head SHA and breaks every file into meaningful chunks — individual functions, classes, and methods — rather than arbitrary slices of text. Each chunk is converted into a vector and stored in ChromaDB.

On the first PR for a repo, the full codebase is ingested. On every subsequent push, only the changed files are updated and deleted files are purged. One ChromaDB collection per repo (`{owner}__{repo_name}`), stored at `/tmp/chromadb/`.

#### Parsing strategy

| Approach | Result |
|---|---|
| tree-sitter (all supported languages) | Each chunk is a complete function, class, or method |
| Line-based fallback (unsupported types) | Fixed-size line windows — used for config, YAML, etc. |

#### Embedding

Each chunk is embedded with OpenAI `text-embedding-3-small` (1536 dimensions) and stored with metadata: `{file, line_start, line_end, symbol, language, sha}`.

### Step 3 — Three specialist agents run in parallel

With the codebase searchable, three agents run simultaneously via LangGraph fan-out. Each agent receives the PR diff and can query ChromaDB for surrounding context before forming findings.

| Agent | What it looks for |
|---|---|
| **Bug detection** | Null references, unhandled exceptions, broken logic, missing validations |
| **Security** | Hardcoded secrets, missing authentication checks, SQL injection risks, OWASP Top 10 patterns |
| **Pattern** | Inconsistencies between new code and the established conventions of the codebase |

Each agent uses GPT-4o with structured function calling and returns typed Pydantic findings with a `confidence` score (0.0–1.0).

### Step 4 — Deduplication

Before routing, findings are deduplicated in two passes:

1. **By `(file, line_start, category)`** — if the same category is flagged on the same line by multiple agents, keep the highest-confidence one.
2. **By `(file, line_start)`** — if multiple categories point to the same line, keep the highest-confidence one overall.

Each finding is identified by a `finding_hash` — SHA256 of `{file}:{line_start}:{category}` — used as a composite unique key per review in the database.

### Step 5 — Findings are routed by severity

Not every finding deserves the same response. The severity router reads the confidence score and severity level, then sends each finding down one of three paths.

| Trigger | Path | What happens |
|---|---|---|
| `confidence ≥ 0.95` + `severity == high` | `auto` | Posted to GitHub immediately as inline PR comment |
| `confidence ≥ 0.70` OR `severity == high` | `queue` | Sent to the human approval dashboard |
| Everything else | `digest` | Batched into weekly digest email |

### Step 6 — A human reviews queued findings

For queued findings, the engineer opens the Next.js approval dashboard and sees a filterable table of pre-routed findings. Each finding shows: severity, category, file and line number, full description, suggestion, confidence score, route badge, and a link to the exact line on GitHub.

Clicking a row opens a detail drawer with the full finding and approve/dismiss buttons. Nothing reaches GitHub until the engineer clicks approve.

### Step 7 — Structured comments are posted to GitHub

Once approved (or immediately for `auto` findings), the PR writer agent:

1. Extracts the flagged code from the diff hunk
2. Calls GPT-4o to generate a corrected replacement (one-click GitHub suggestion block)
3. Formats the comment: severity label, category, description, suggestion, fix block
4. Adds educational context from the OWASP mapping or severity fallback
5. Posts via `POST /repos/{owner}/{repo}/pulls/{pr}/reviews` with `event: COMMENT`
6. Falls back to a PR body comment if inline posting returns 422 (e.g. line not in diff)

A comment about a hardcoded API key explains that it is permanently exposed in git history even after deletion, and links to OWASP A02:2021 — Cryptographic Failures.

---

## 7. Trust Model

The biggest mistake in AI agent design is building something that acts autonomously on consequential decisions. Code review gatekeeps what goes into production. This system is built around three explicit trust levels.

| Level | Name | Behaviour | Default |
|---|---|---|---|
| **Level 1** | Read only | Agent reads code and posts findings as a comment on an existing human-opened PR. Never opens anything itself. | ✅ Yes |
| **Level 2** | Draft and approve | Agent prepares a full review but holds it in the dashboard waiting for human approval before touching GitHub. | No |
| **Level 3** | Auto for narrow cases | Agent acts automatically, but only for high-confidence findings in an explicitly defined category (conf ≥ 95% + high severity). | Opt-in |

> **Default: Level 1.** Teams must explicitly opt into Level 3 for specific finding categories. Auto-acting on consequential code changes without a documented opt-in is not permitted.

---

## 8. Design Decisions

### No critic agent

The original design included a critic agent that challenged every specialist finding before routing. It was removed after it rejected 87.5% of findings — including real, confirmed bugs — because it lacked the semantic depth to distinguish true positives from false positives.

The current approach routes directly by specialist agent confidence scores. The specialist agents already query ChromaDB for context before forming findings. False positive reduction comes from better specialist prompts and confidence calibration rather than a filtering layer.

**Trade-off:** More false positives may reach the dashboard. The human approval step at the queue level absorbs this. Auto-posting (Level 3) requires high confidence + high severity, which limits blast radius.

### Severity-based routing

Instead of a single approval queue, findings are split at routing time. This ensures critical findings (hardcoded secrets, auth bypass) reach GitHub immediately without waiting for a human review cycle, while uncertain findings are batched rather than discarded.

### Educational context in every comment

Every comment posted to GitHub includes the problem, why it matters in concrete terms, and an OWASP reference link where applicable. 14 OWASP categories are mapped. Non-OWASP findings use a severity-based fallback.

### GPT-4o suggestion blocks

For each inline comment, GPT-4o generates corrected replacement code. This is presented as a GitHub `suggestion` block — the developer sees a diff and can apply the fix with one click. The suggestion is skipped if the flagged code cannot be extracted from the diff or if GPT-4o returns something implausibly long (> 4x the original).

### Stale finding cleanup

New commits to an open PR automatically dismiss all pending findings from previous commits. Closed PRs dismiss all remaining pending findings. This keeps the dashboard clean and prevents reviewers from approving findings that are no longer relevant.

---

## 9. What It Solves

| Without the system | With the system |
|---|---|
| PR sits unreviewed for 1–2 days | Findings ready within 60 seconds |
| Senior engineers spend hours on mechanical checks | Senior engineers spend minutes approving pre-filtered findings |
| Noisy AI tools erode developer trust | Confidence thresholds and deduplication reduce noise before humans see findings |
| Junior developers receive feedback too late to learn | Educational context in every comment links to OWASP standards and explains real impact |
| Critical security bugs wait overnight for review | High-confidence security findings post immediately |
| Stale findings accumulate after force-pushes | Superseded findings auto-dismissed on each new commit |

---

## 10. Known Limitations

The system covers roughly 60–70% of the judgments a senior engineer makes during code review. The remaining 30–40% require human expertise and always will.

| Limitation | Reason | Mitigation |
|---|---|---|
| Shallow pattern matching can produce false positives | GPT-4o sees diff context only, not full program semantics. No control flow or data flow analysis. | Human approval step at the queue level. Confidence threshold for auto-posting. |
| Line number drift in reported findings | Agent counts diff header lines as code lines when mapping findings back to file positions. | Known issue; mitigated by linking to GitHub file view rather than relying solely on line numbers. |
| Overconfident scores for pattern hits | Agents return high confidence for syntactic matches even when the semantic claim is wrong. | Do not auto-post without both high confidence AND high severity. |
| Unsupported file types use line-based chunking | tree-sitter does not cover every file format | Line-based fallback preserves context; quality is lower than AST-level chunks |
| Large monorepos may be slow on first ingest | Full codebase embedding is a one-time expensive operation | Scoped ingestion per service can reduce initial cost |
| Cannot reason about unwritten context | Decisions made verbally in meetings live nowhere in the codebase | Teams can document decisions as ADRs and ingest them (future) |
| Cannot make strategic architectural calls | Requires understanding of product direction, not just code patterns | Human approval step ensures engineers stay in the loop |

> **The goal is not to replace senior engineers.** It is to ensure that when they do show up, they are spending their time on the problems that genuinely need them.

---

## 11. Technology Stack

| Layer | Tool | Purpose |
|---|---|---|
| Webhook receiver | FastAPI | Receives GitHub events, validates HMAC signatures |
| Async server | Uvicorn | ASGI server for FastAPI |
| HTTP client | httpx | Async calls to GitHub API |
| Repo cloning | gitpython | Clones repositories programmatically |
| Code parsing | tree-sitter | AST-level chunking for 100+ languages (Python, Java, TS, Go, Rust, C, C++, and more) |
| Code parsing fallback | line-based windowing | Fixed-size line windows for file types not supported by tree-sitter |
| Embeddings | OpenAI text-embedding-3-small | Converts code chunks to vectors (1536 dimensions) |
| Vector database | ChromaDB | Stores and retrieves embedded code chunks by semantic similarity |
| Agent orchestration | LangGraph | Manages parallel fan-out for specialist agents |
| LLM provider | OpenAI GPT-4o | Agent reasoning, structured function calling, code fix generation |
| Structured outputs | Pydantic | Typed outputs from each agent and all API responses |
| Relational database | PostgreSQL 17 | Stores reviews, findings, status, audit trail |
| ORM | SQLAlchemy 2.0 async + asyncpg | Async database access |
| Migrations | Alembic | Schema versioning |
| Human dashboard | Next.js 16 | Approval interface with findings table and detail drawer |
| UI components | shadcn/ui + Tailwind CSS | Dashboard component library |
| Cloud deployment | Railway or Fly.io | Hosts backend (planned) |
| Frontend deployment | Vercel | Hosts Next.js dashboard (planned) |

---

## 12. Build Plan

| Phase | Weeks | Goal | Status |
|---|---|---|---|
| Foundation | 1–2 | GitHub webhook, HMAC validation, GitHub App JWT auth, PR diff fetch, repo cloning | ✅ Done |
| RAG pipeline | 3–4 | ChromaDB ingestion: file walk, tree-sitter chunking, OpenAI embedding, upsert/purge | ✅ Done |
| Specialist agents | 5–6 | Bug/security/pattern agents via LangGraph fan-out, GPT-4o function calling, Pydantic outputs, deduplication, severity router | ✅ Done |
| PR writer + dashboard | 7–8 | Inline GitHub review comments, suggestion blocks, OWASP educational layer, PostgreSQL findings storage, Next.js approval dashboard, stale finding cleanup | ✅ Done |
| Weekly digest + deployment | 9–10 | Weekly digest email (APScheduler + SMTP), Docker, Railway + Vercel deploy | 🔄 In progress |

### Milestones

| Milestone | Description | Status |
|---|---|---|
| M1 — Webhook received | Push a commit to GitHub, see it logged in the terminal | ✅ Done |
| M2 — RAG working | Query the vector store, get back relevant code context for a given diff | ✅ Done |
| M3 — Agents running | Three agents return structured JSON findings against a real GitHub repo | ✅ Done |
| M4 — Full loop | Push code, see findings in dashboard, approve, see GitHub inline comment posted | ✅ Done |
| M5 — Weekly digest | Digest-route findings emailed weekly via APScheduler cron | 🔄 Planned |
| M6 — Live and deployed | System is publicly accessible and demonstrable on any GitHub repo in real time | 🔄 Planned |

---

## 13. Open Questions

| # | Question | Owner | Priority | Status |
|---|---|---|---|---|
| 1 | Weekly digest: email or Slack message? | Product owner | Medium | Email chosen — implementation pending |
| 2 | How should the dashboard handle authentication — OAuth via GitHub or email/password? | Tech lead | High | Open |
| 3 | Should ADR ingestion be in v1 or deferred to v2? | Product owner | Low | Deferred to v2 |
| 4 | How do we handle monorepos with multiple services — ingest everything or scope to changed service? | Tech lead | Medium | Open |
| 5 | Should confidence thresholds be configurable per team or global? | Tech lead | Medium | Open |

---

## 14. Glossary

| Term | Definition |
|---|---|
| **ADR** | Architecture Decision Record — a short document capturing a significant architectural decision and its rationale |
| **Agent** | An AI model with a specific, scoped responsibility in the pipeline |
| **AST** | Abstract Syntax Tree — a structured representation of source code that captures its logical structure rather than raw text |
| **ChromaDB** | An open-source vector database used to store and retrieve embedded code chunks |
| **Confidence score** | A 0.0–1.0 value assigned by a specialist agent indicating how certain it is that a finding represents a real problem |
| **Deduplication** | Two-pass process that removes duplicate findings: first by `(file, line, category)`, then by `(file, line)`, keeping the highest-confidence hit |
| **Embedding** | A numerical representation of a piece of text that captures its semantic meaning |
| **False positive** | A finding flagged by an agent that is not actually a real problem |
| **Fan-out** | The step where a single input is sent to multiple agents simultaneously for parallel processing |
| **finding_hash** | SHA256 of `{file}:{line_start}:{category}` — used as a composite unique identifier per review |
| **Ingestion agent** | The agent responsible for cloning the repository, chunking files, and storing embeddings in ChromaDB |
| **LangGraph** | A framework for building multi-agent pipelines with parallel and sequential steps |
| **OWASP** | Open Web Application Security Project — the standard reference for web application security vulnerabilities |
| **RAG** | Retrieval-Augmented Generation — a technique where relevant context is retrieved from a knowledge base and given to an LLM before it generates a response |
| **Severity router** | The component that routes each finding to `auto`, `queue`, or `digest` based on confidence score and severity level |
| **Stale finding** | A pending finding from a previous commit to the same PR, automatically dismissed when a new commit is pushed |
| **Suggestion block** | A GitHub PR comment feature (` ```suggestion ``` `) that shows a diff and allows one-click application of the fix |
| **Trust level** | A configuration setting that controls how autonomously the system is allowed to act (Level 1 = read only, Level 2 = draft and approve, Level 3 = auto for narrow cases) |
| **Vector database** | A database that stores numerical representations of data and enables retrieval by semantic similarity rather than exact keyword match |
| **Webhook** | An HTTP callback that GitHub fires automatically when a specific event occurs, such as a code push |

---

*Built with Python · LangGraph · FastAPI · Next.js · ChromaDB · PostgreSQL · OpenAI GPT-4o · GitHub API*

*Document version 1.1.0 — Last updated 14 May 2026 — Classification: Internal*
