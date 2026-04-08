# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-Agent Code Review System (CR-001) — an AI pipeline that automatically reviews GitHub pull requests using specialised agents. A webhook receiver catches GitHub events, runs analysis agents in parallel (bug detection, security, pattern), filters through a critic agent, routes by severity, and posts structured inline PR comments with educational context.

The system is currently in **Phase 2 (RAG Pipeline)**: the FastAPI webhook receiver, GitHub App auth, repo cloning, and ChromaDB ingestion pipeline are all implemented and tested end-to-end. The analysis agents, critic agent, and Next.js dashboard are not yet built.

## Commands

### Running the backend

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload
```

The server starts on `http://localhost:8000`. The webhook endpoint is `POST /webhook`.

### Installing dependencies

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --index-url https://pypi.org/simple/ -r requirements.txt
```

> Note: pip may be configured to use a private AWS CodeArtifact registry. Always pass
> `--index-url https://pypi.org/simple/` to force public PyPI.

### Testing the ingestion pipeline in isolation

```bash
cd backend
source .venv/bin/activate
python test_ingestion.py
```

Runs a full ingest of `backend/` itself, queries ChromaDB, and runs an incremental ingest
with a mock diff. No GitHub webhook or live PR needed.

### Testing the webhook locally

Use [smee.io](https://smee.io) or [ngrok](https://ngrok.com) to tunnel GitHub webhooks to localhost.

```bash
npx smee-client --url https://smee.io/YOUR_CHANNEL --target http://localhost:8000/webhook
```

Then open or update a PR on any repo where the GitHub App is installed.

## Architecture

### Current structure

```
backend/
  main.py                        # FastAPI app — webhook receiver + ingestion trigger
  requirements.txt               # All dependencies (pinned where needed)
  test_ingestion.py              # Standalone ingestion test (not production code)
  app/
    github_client.py             # GitHub App JWT auth, installation token, PR diff fetch
    repo_manager.py              # Shallow clone repo at PR head SHA → /tmp/repos/
    agents/
      ingestion/
        __init__.py              # Exposes run_ingestion()
        agent.py                 # Orchestrator — full vs incremental, calls all modules
        walker.py                # File walk, binary detection, skip list filtering
        parser.py                # tree-sitter chunking + line-window fallback
        embedder.py              # Batched OpenAI embedding with retry
        store.py                 # ChromaDB collection management, upsert, delete
        diff_parser.py           # Parses unified diff → modified + deleted file paths
    models/
      chunks.py                  # Chunk dataclass + IngestionResult Pydantic model
      ingestion_config.py        # IngestionConfig (thresholds, skip dirs, batch size)
    api/                         # Empty — additional API routes go here
frontend/                        # Empty — Next.js dashboard (not yet scaffolded)
docs/
  code_review_system_v1.0.0.md   # Full product design document
  design/
    repo_cloning.md              # Design doc for repo cloning
    ingestion_agent.md           # Design doc for ingestion pipeline
    chromadb_storage.md          # ChromaDB storage layout, chunk structure, examples
```

### Implemented pipeline (Phases 1–2)

1. **GitHub webhook** → FastAPI receiver validates HMAC-SHA256 signature
2. **PR diff fetch** → GitHub App JWT auth → installation token → raw unified diff
3. **Repo clone** → shallow clone (`--depth 1`) at head SHA → `/tmp/repos/{owner}-{repo}-{sha}`
4. **Ingestion agent** → walk repo → tree-sitter chunking → OpenAI embedding → ChromaDB upsert
   - First PR on a repo: full ingest (entire repo)
   - Subsequent PRs: incremental (diff files only, purge deleted files)

### Planned pipeline (Phases 3–5)

5. **Three parallel agents** (via LangGraph fan-out):
   - *Bug detection* — null refs, logic errors, missed requirements from PR intent
   - *Security* — OWASP Top 10, hardcoded secrets, auth gaps
   - *Pattern* — compares diff against full codebase conventions
6. **Critic agent** → challenges every finding, retrieves context from ChromaDB, assigns confidence score, drops false positives
7. **Severity router** → auto-post (>95% confidence + high severity) | human dashboard (70–95%) | weekly digest (<70%)
8. **PR writer agent** → formats findings as inline GitHub review comments with educational context (what/why/reference link)

### Key design decisions

- **Trust model**: Default is Level 1 (read-only — agent reads and comments, never opens PRs itself). Level 3 auto-posting only for findings with >95% confidence + high severity, and only for teams that explicitly opt in.
- **LLM**: Claude (Anthropic) is the primary provider; GPT-4o is a drop-in alternative.
- **Observability**: LangSmith traces every agent decision (Phase 3+).
- **Structured outputs**: All agent outputs typed with Pydantic.
- **tree-sitter**: Uses individual language packages (`tree-sitter-python`, `tree-sitter-java`, etc.) compatible with Python 3.13. `tree-sitter-languages` is not used — it does not support Python 3.13.

### ChromaDB storage

- Location: `/tmp/chromadb/` (wiped on reboot — Phase 4 will make this persistent)
- One collection per repo: `{owner}__{repo_name}`
- Each chunk stores: source text, 1536-dim embedding vector, metadata (file, lines, symbol, language, SHA)
- See `docs/design/chromadb_storage.md` for full details

### Environment variables (`.env` in `backend/`)

| Variable | Purpose |
|---|---|
| `GITHUB_APP_ID` | GitHub App identifier |
| `GITHUB_WEBHOOK_SECRET` | HMAC secret for validating webhook signatures |
| `GITHUB_PRIVATE_KEY_PATH` | Path to GitHub App private key PEM file |
| `OPENAI_API_KEY` | OpenAI API key for `text-embedding-3-small` |

> The shell may have `OPENAI_API_KEY` set to a different value. Both `main.py` and
> `test_ingestion.py` use `load_dotenv(override=True)` to ensure `.env` always wins.

## Build phases (from design doc)

| Phase | Weeks | Goal | Status |
|---|---|---|---|
| Foundation | 1–2 | Webhook + GitHub App JWT auth + PR diff fetch + repo cloning | Done |
| RAG pipeline | 3–4 | ChromaDB ingestion + retrieval against real diffs | Done |
| Specialist agents | 5–6 | Bug/security/pattern agents via LangGraph + LangSmith | Next |
| Critic + dashboard | 7–8 | Critic filtering + PostgreSQL + Next.js approval dashboard | Planned |
| PR writer + deployment | 9–10 | GitHub comments + severity routing + Docker + Railway/Vercel deploy | Planned |
