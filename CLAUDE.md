# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-Agent Code Review System (CR-001) — an AI pipeline that automatically reviews GitHub pull requests using specialised agents. A webhook receiver catches GitHub events, runs analysis agents in parallel (bug detection, security, pattern), filters through a critic agent, routes by severity, and posts structured inline PR comments with educational context.

The system is currently in **Phase 1 (Foundation)**: the FastAPI webhook receiver is implemented; all agent logic, the vector store, and the Next.js dashboard are not yet built.

## Commands

### Running the backend

```bash
cd backend
uvicorn main:app --reload
```

The server starts on `http://localhost:8000`. The webhook endpoint is `POST /webhook`.

### Installing dependencies

```bash
pip install fastapi uvicorn python-dotenv
```

_(No requirements.txt exists yet — add one as packages are introduced.)_

### Testing the webhook locally

Use [smee.io](https://smee.io) or [ngrok](https://ngrok.com) to tunnel GitHub webhooks to localhost.

## Architecture

### Current structure

```
backend/
  main.py              # FastAPI app — webhook receiver only
  app/
    agents/            # Empty — agent implementations go here
    models/            # Empty — Pydantic models go here
    api/               # Empty — additional API routes go here
frontend/              # Empty — Next.js dashboard (not yet scaffolded)
docs/
  code_review_system_v1.0.0.md   # Full product design document
```

### Planned pipeline (from design doc)

1. **GitHub webhook** → FastAPI receiver validates HMAC-SHA256 signature
2. **Ingestion agent** → clones repo, chunks by function/class via tree-sitter (Python) / javalang (Java), embeds via OpenAI `text-embedding-3-small`, stores in ChromaDB
3. **Three parallel agents** (via LangGraph fan-out):
   - *Bug detection* — null refs, logic errors, missed requirements from PR intent
   - *Security* — OWASP Top 10, hardcoded secrets, auth gaps
   - *Pattern* — compares diff against full codebase conventions
4. **Critic agent** → challenges every finding, retrieves context from ChromaDB, assigns confidence score, drops false positives
5. **Severity router** → auto-post (>95% confidence + high severity) | human dashboard (70–95%) | weekly digest (<70%)
6. **PR writer agent** → formats findings as inline GitHub review comments with educational context (what/why/reference link)

### Key design decisions

- **Trust model**: Default is Level 1 (read-only — agent reads and comments, never opens PRs itself). Level 3 auto-posting only for findings with >95% confidence + high severity, and only for teams that explicitly opt in.
- **LLM**: Claude (Anthropic) is the primary provider; GPT-4o is a drop-in alternative. The default is an open question (see design doc §12).
- **Observability**: LangSmith traces every agent decision.
- **Structured outputs**: All agent outputs typed with Pydantic.

### Environment variables (`.env` in `backend/`)

| Variable | Purpose |
|---|---|
| `GITHUB_APP_ID` | GitHub App identifier |
| `GITHUB_WEBHOOK_SECRET` | HMAC secret for validating webhook signatures |
| `GITHUB_PRIVATE_KEY_PATH` | Path to GitHub App private key PEM file |

## Build phases (from design doc)

| Phase | Weeks | Goal |
|---|---|---|
| Foundation | 1–2 | Webhook + GitHub App JWT auth + PR diff fetch + repo cloning |
| RAG pipeline | 3–4 | ChromaDB ingestion + retrieval against real diffs |
| Specialist agents | 5–6 | Bug/security/pattern agents via LangGraph + LangSmith |
| Critic + dashboard | 7–8 | Critic filtering + PostgreSQL + Next.js approval dashboard |
| PR writer + deployment | 9–10 | GitHub comments + severity routing + Docker + Railway/Vercel deploy |
