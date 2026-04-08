# Ingestion Agent — Design

## Purpose

The ingestion agent takes the cloned repository and the PR diff, breaks every relevant file into meaningful code chunks, embeds them as vectors, and stores them in ChromaDB. The result is a searchable representation of the codebase that all downstream analysis agents (bug, security, pattern, critic) query for context.

This is Phase 2 of the build plan (weeks 3–4).

### Why this is needed

When a PR comes in, the analysis agents need to understand the **full codebase** — not just the changed lines. For example, if a PR adds a function that looks buggy, the agent needs to check: "does a validator for this already exist somewhere else?" To do that, it needs to search the entire repo by *meaning*, not just by keyword.

Without this pipeline, agents only see the diff and have no way to retrieve surrounding context. That leads to false positives — flagging issues that are already handled elsewhere in the codebase. The ingestion pipeline is what makes context retrieval possible.

---

## Where it lives

```
backend/app/agents/ingestion/
    __init__.py         ← exposes run_ingestion()
    agent.py            ← orchestrator, async entry point
    walker.py           ← file walk, binary detection, size filtering
    parser.py           ← tree-sitter chunking + line-window fallback
    embedder.py         ← OpenAI embedding, batched
    store.py            ← ChromaDB collection management and upsert
    diff_parser.py      ← extracts changed/deleted file paths from diff

backend/app/models/
    chunks.py           ← Chunk dataclass, IngestionResult Pydantic model
    ingestion_config.py ← IngestionConfig (thresholds, skip dirs, batch size)
```

`main.py` calls `run_ingestion()` from `agent.py`. `agent.py` coordinates all other modules. No module calls upward.

---

## What it does — step by step

```
run_ingestion(diff, repo_path, owner, repo_name, head_sha)
        │
        ├── 1. get or create ChromaDB collection for {owner}__{repo_name}
        │
        ├── 2. decide scope
        │         ├── collection empty → full ingest (walk entire repo)
        │         └── collection has data → incremental (diff files only)
        │
        ├── 3. walk files
        │         ├── prune: .git, node_modules, __pycache__, .venv, dist, build, .next, vendor, target
        │         ├── skip: binary files (null-byte check on first 8 KB)
        │         ├── skip: files over 500 KB
        │         └── skip: deleted files (purge their chunks from ChromaDB instead)
        │
        ├── 4. parse each file into chunks
        │         ├── detect language from file extension
        │         ├── try tree-sitter → extract function / class / method nodes
        │         └── fallback → 60-line windows with 15-line overlap
        │
        ├── 5. embed chunks
        │         └── OpenAI text-embedding-3-small, batched at 100 chunks per call
        │
        ├── 6. upsert into ChromaDB
        │         ├── ID = sha256(file + start_line + end_line) — deterministic, stable
        │         └── upsert replaces stale embeddings for re-ingested files
        │
        └── 7. return IngestionResult
                  (collection_name, chunks_stored, files_processed, files_skipped, mode)
```

---

## Full ingest vs incremental

| Scenario | Mode | What happens |
|---|---|---|
| No collection exists for this repo | Full | Walk and ingest entire repo |
| Collection exists (prior PR was processed) | Incremental | Parse diff → ingest only added/modified files; purge deleted files |

Detection: `collection.count() > 0` → incremental mode.

**Why not always full?** A medium-sized codebase (50k lines) takes 20–40 seconds to embed from scratch. On every subsequent PR only a handful of files change — re-ingesting everything is wasteful and slows the pipeline below the 60-second target.

**Why not always incremental?** The first run has no baseline. The pattern agent compares new code against the full codebase — if only the diff files are ingested initially, the pattern agent has nothing to compare against.

---

## ChromaDB collection naming

Collection name: `{owner}__{repo_name}` (double underscore — ChromaDB collection names cannot contain `/`).

One persistent collection per repo. The SHA is stored in per-chunk metadata (`ingested_at_sha`), not in the collection name. This is what makes incremental ingest possible — the collection accumulates and updates across every PR rather than starting fresh each time.

---

## File filtering

### Skip directories (pruned at walk time)

```
.git, node_modules, __pycache__, .venv, venv, env,
dist, build, .next, vendor, target
```

Pruning at walk time (modifying `os.walk` dirnames in-place) avoids descending into these trees at all, which is significantly faster than filtering afterwards.

### Binary detection

Read the first 8 192 bytes of each file. If a null byte (`\x00`) is present, the file is binary. This is the same heuristic git uses — no third-party library needed.

### Size threshold

Skip files over **500 KB**. This catches:
- `package-lock.json` / `yarn.lock` (often 5–50 MB)
- Minified JS bundles
- Auto-generated protobuf / GraphQL files
- Large data fixtures

Configurable via `IngestionConfig.max_file_bytes`.

---

## Parsing

### Primary parser — tree-sitter

`tree-sitter-languages` ships pre-compiled grammars for 100+ languages in a single wheel. No build tooling needed.

Supported languages include: Python, Java, JavaScript, TypeScript, Go, Rust, C, C++, Ruby, PHP, Swift, Kotlin, C#, Bash, and more.

For each file, tree-sitter reads the source and builds an AST (Abstract Syntax Tree) — a tree that represents the code's structure rather than its raw text:

```
file
├── function: validate_user()      ← lines 1–25
├── class: PaymentProcessor        ← lines 27–80
│   ├── method: __init__()
│   ├── method: charge()
│   └── method: refund()
└── function: send_email()         ← lines 82–100
```

tree-sitter queries the AST for `function_definition`, `class_definition`, `method_definition`, and equivalent node types for the detected language. Each node becomes one chunk. Chunk boundaries never fall inside a function.

### Fallback — line-based windowing

Used when:
- The file's extension is not in the language map (e.g. `.yaml`, `.toml`, `.sql`)
- tree-sitter has no grammar for the detected language
- tree-sitter parses the file but finds zero function/class nodes

Window size: **60 lines**. Overlap: **15 lines**.

Reasoning: the average function across Python, TypeScript, and Java is 20–50 lines. A 60-line window fits most functions entirely. A 15-line overlap ensures a function that spans a boundary appears fully in at least one chunk.

### Chunk type

| Parser | chunk_type |
|---|---|
| tree-sitter — function node | `"function"` |
| tree-sitter — class node | `"class"` |
| tree-sitter — method node | `"method"` |
| Line-based fallback | `"window"` |

---

## Chunk metadata

Each ChromaDB document carries this metadata:

| Field | Example | Purpose |
|---|---|---|
| `file` | `"src/auth.py"` | Relative path from repo root |
| `start_line` | `42` | 1-indexed |
| `end_line` | `67` | 1-indexed |
| `language` | `"python"` | Detected from extension |
| `chunk_type` | `"function"` | Parsing method used |
| `symbol_name` | `"validate_user"` | Function/class name if extractable, else `""` |
| `repo` | `"acme/myrepo"` | Full repo identifier |
| `ingested_at_sha` | `"a3f92c1"` | Head SHA at time of ingest |

`symbol_name` is important: it lets the bug and security agents query ChromaDB by exact symbol name, not just semantic similarity.

---

## Embedding

An embedding model takes a piece of text and outputs a list of numbers — a **vector** — that captures its semantic meaning:

```
"def validate_user(email)..." → [0.23, -0.81, 0.45, 0.12, ...]
                                  (1536 numbers)
```

The critical property: **similar meaning → similar numbers**. Two functions that both validate user input will produce vectors that are numerically close to each other, even if the code looks completely different syntactically. This is what makes search-by-meaning possible — the vector database doesn't match keywords, it matches concepts.

- Model: `text-embedding-3-small` (OpenAI)
- Output: 1536-dimensional float vector per chunk
- Batch size: 100 chunks per API call
- Retry: one automatic retry on transient API errors before raising

---

## Async strategy

`run_ingestion()` is `async` so `main.py` can `await` it without blocking the FastAPI event loop.

Internally, the file walk and tree-sitter parsing are CPU-bound synchronous operations. Only the OpenAI embedding call and ChromaDB writes are I/O-bound. The implementation wraps the synchronous core in `asyncio.to_thread()` — no need to propagate `async` down into `walker.py`, `parser.py`, or `embedder.py`.

```
main.py (async)
    └── await run_ingestion()          ← async wrapper in agent.py
              └── asyncio.to_thread(_run_ingestion_sync)
                        ├── walker.py  ← sync
                        ├── parser.py  ← sync
                        ├── embedder.py ← sync (openai client used synchronously)
                        └── store.py   ← sync (chromadb client used synchronously)
```

---

## Function signatures

### `backend/app/models/chunks.py`

```python
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel

ChunkType = Literal["function", "class", "method", "window"]

@dataclass
class Chunk:
    text: str
    file: str           # relative path from repo root
    start_line: int     # 1-indexed
    end_line: int
    language: str
    chunk_type: ChunkType
    symbol_name: str    # empty string if not extractable

class IngestionResult(BaseModel):
    collection_name: str
    chunks_stored: int
    files_processed: int
    files_skipped: int
    mode: Literal["full", "incremental"]
```

### `backend/app/models/ingestion_config.py`

```python
from pydantic import BaseModel

class IngestionConfig(BaseModel):
    max_file_bytes: int = 512_000
    binary_probe_bytes: int = 8_192
    window_size_lines: int = 60
    window_overlap_lines: int = 15
    embedding_batch_size: int = 100
    skip_dirs: list[str] = [
        ".git", "node_modules", "__pycache__", ".venv", "venv",
        "env", "dist", "build", ".next", "vendor", "target"
    ]
```

### `walker.py`

```python
def is_binary(file_path: str, probe_bytes: int = 8_192) -> bool: ...

def should_skip_dir(dir_name: str, skip_dirs: list[str]) -> bool: ...

def walk_repo(repo_path: str, config: IngestionConfig) -> list[str]:
    # returns absolute paths of all accepted files
```

### `parser.py`

```python
def detect_language(file_path: str) -> str | None:
    # map extension → language name; None if unknown

def parse_with_treesitter(
    source_code: str,
    language: str,
    file_rel_path: str,
) -> list[Chunk]:
    # returns [] if language unsupported or no nodes found

def parse_with_line_window(
    source_code: str,
    file_rel_path: str,
    language: str,
    window_size: int,
    overlap: int,
) -> list[Chunk]:
    # always returns at least one chunk

def parse_file(
    file_abs_path: str,
    repo_path: str,
    config: IngestionConfig,
) -> list[Chunk]:
    # tries tree-sitter, falls back to line windows
```

### `embedder.py`

```python
def embed_chunks(
    chunks: list[Chunk],
    batch_size: int = 100,
    model: str = "text-embedding-3-small",
) -> list[tuple[Chunk, list[float]]]:
    # batched; one retry on transient error
```

### `store.py`

```python
def get_or_create_collection(owner: str, repo_name: str) -> chromadb.Collection: ...

def collection_has_data(collection: chromadb.Collection) -> bool:
    # returns collection.count() > 0

def upsert_chunks(
    collection: chromadb.Collection,
    embedded_chunks: list[tuple[Chunk, list[float]]],
    head_sha: str,
    repo_full_name: str,
) -> int:
    # ID = sha256(file + start_line + end_line)
    # returns count upserted

def delete_chunks_for_files(
    collection: chromadb.Collection,
    file_rel_paths: list[str],
) -> None:
    # purge all chunks for deleted files
```

### `diff_parser.py`

```python
def parse_diff_file_paths(diff: str) -> tuple[list[str], list[str]]:
    # returns (modified_or_added_paths, deleted_paths)
    # parses '--- a/path' and '+++ b/path' headers
```

### `agent.py`

```python
async def run_ingestion(
    diff: str,
    repo_path: str,
    owner: str,
    repo_name: str,
    head_sha: str,
    config: IngestionConfig | None = None,
) -> IngestionResult: ...

def _run_ingestion_sync(
    diff: str,
    repo_path: str,
    owner: str,
    repo_name: str,
    head_sha: str,
    config: IngestionConfig,
) -> IngestionResult: ...
```

---

## How it plugs into main.py

```python
# top of main.py — add alongside existing imports
from app.agents.ingestion import run_ingestion

# inside the pull_request handler, replacing the TODO at line 90
ingestion_result = await run_ingestion(
    diff=diff,
    repo_path=repo_path,
    owner=owner,
    repo_name=repo_name,
    head_sha=head_sha,
)
print(f"Ingestion: {ingestion_result.chunks_stored} chunks "
      f"({ingestion_result.mode}) → '{ingestion_result.collection_name}'")
# TODO Phase 3: pass ingestion_result.collection_name to analysis agents
```

---

## Dependencies added to requirements.txt

```
tree-sitter==0.21.3           # pinned — tree-sitter-languages requires <=0.21
tree-sitter-languages==1.10.2 # pre-compiled grammars for 100+ languages
openai>=1.0.0
chromadb>=0.5.0
```

> **Important:** the current environment has `tree-sitter==0.25.1` installed globally. Pin to `0.21.3` in a virtualenv (`python -m venv .venv && source .venv/bin/activate`) to avoid conflicts.

---

## How agents use ChromaDB (Phase 3+)

Once ingestion has run, every analysis agent can query ChromaDB with natural language or a code fragment:

```
Query: "find validators for payment amount"
```

ChromaDB:
1. Embeds the query string → `[0.19, -0.79, 0.51, ...]`
2. Finds the stored vectors numerically closest to that query vector
3. Returns the matching code chunks with their source text and metadata

```
Result: validate_payment_limit() in payments/validators.py (lines 42–67)
```

The agent now knows that validation already exists → it is not a bug. This is the mechanism the critic agent uses to drop false positives before any finding reaches a human.

---

## Summary

| Step | Module | What happens |
|---|---|---|
| 1. Walk | `walker.py` | Find all source files; skip binaries, large files, dependency dirs |
| 2. Parse | `parser.py` | Break each file into complete functions/classes via tree-sitter |
| 3. Embed | `embedder.py` | Convert each chunk to a vector of numbers via OpenAI |
| 4. Store | `store.py` | Save vectors + source code + metadata in ChromaDB |
| 5. Search (later) | ChromaDB query | Agents retrieve context by meaning, not by keyword |

---

## What is NOT done in this phase

- LangGraph orchestration — added in Phase 3 when specialist agents are built
- LangSmith tracing — deferred to Phase 3
- ChromaDB persistence path configuration — currently uses default local path; make configurable in Phase 4
- Incremental ingest for renamed files — treated as delete + add for now
- Embedding cost tracking — deferred
