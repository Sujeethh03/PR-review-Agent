# Specialist Agents — Design

## Purpose

The specialist agents are the analysis layer of the pipeline. They receive the PR diff and the ChromaDB collection built by the ingestion agent, and return structured findings — potential bugs, security vulnerabilities, and pattern violations.

Three agents run in **parallel** via LangGraph fan-out:
- **Bug detection** — logic errors, null references, missing validations, missed requirements
- **Security** — OWASP Top 10, hardcoded secrets, authentication gaps
- **Pattern** — inconsistencies between new code and existing codebase conventions

This is Phase 3 of the build plan (weeks 5–6).

### Why parallel and not sequential?

Each agent is looking for a completely different class of problem. Bug detection has no dependency on security findings, and neither depends on pattern findings. Running them in parallel cuts the total analysis time to the slowest single agent rather than the sum of all three — critical for the 60-second target.

### Why ChromaDB context matters here

Without ChromaDB, each agent only sees the diff — the changed lines. That leads to false positives. With ChromaDB, each agent can ask: "does something else in the codebase already handle this?" before flagging anything.

```
Bug agent sees: amount has no upper limit check → would flag as bug
Bug agent queries ChromaDB: "payment amount validator"
ChromaDB returns: validate_payment_limit() in payments/validators.py
Bug agent concludes: validation already exists upstream → not a bug
```

---

## Where it lives

```
backend/app/agents/specialist/
    __init__.py             ← exposes run_specialist_agents()
    graph.py                ← LangGraph fan-out graph definition
    models.py               ← Finding, AgentOutput Pydantic models (shared)
    context.py              ← ChromaDB query helper (shared by all agents)
    diff_utils.py           ← extracts changed hunks from diff (file + lines + code)
    bug/
        __init__.py
        agent.py            ← bug detection agent
        prompts.py          ← prompt templates for bug detection
    security/
        __init__.py
        agent.py            ← security agent
        prompts.py          ← prompt templates for security checks
    pattern/
        __init__.py
        agent.py            ← pattern agent
        prompts.py          ← prompt templates for pattern checks

backend/app/models/
    findings.py             ← Finding, AgentOutput, SpecialistResult models
```

`main.py` calls `run_specialist_agents()` from `specialist/__init__.py`. The graph
in `graph.py` fans out to all three agents in parallel and collects their outputs.
No agent calls upward or sideways — all shared logic goes through `context.py` and
`diff_utils.py`.

---

## Shared models

### `backend/app/models/findings.py`

```python
from typing import Literal
from pydantic import BaseModel


class Finding(BaseModel):
    file: str                          # relative path from repo root
    line_start: int                    # 1-indexed, start of the problematic code
    line_end: int                      # 1-indexed, end of the problematic code
    severity: Literal["high", "medium", "low"]
    category: str                      # e.g. "null_reference", "sql_injection"
    title: str                         # short headline (one sentence)
    description: str                   # what the problem is and why it matters
    suggestion: str                    # concrete fix recommendation
    confidence: float                  # 0.0 – 1.0, agent's self-assessed confidence
    agent: Literal["bug", "security", "pattern"]   # which agent produced this


class AgentOutput(BaseModel):
    agent: Literal["bug", "security", "pattern"]
    findings: list[Finding]
    error: str | None = None           # set if the agent raised an exception


class SpecialistResult(BaseModel):
    bug: AgentOutput
    security: AgentOutput
    pattern: AgentOutput

    def all_findings(self) -> list[Finding]:
        return (
            self.bug.findings
            + self.security.findings
            + self.pattern.findings
        )
```

---

## LangGraph fan-out — `graph.py`

### What LangGraph is

LangGraph is a framework for building agent pipelines as directed graphs. Each node
is a function (or agent). Edges define what runs next. Parallel nodes (fan-out) run
simultaneously in separate threads.

### Graph state

```python
from typing import TypedDict

class AgentState(TypedDict):
    diff: str                          # raw unified diff from GitHub
    collection_name: str               # ChromaDB collection for this repo
    owner: str
    repo_name: str
    bug_output: AgentOutput | None
    security_output: AgentOutput | None
    pattern_output: AgentOutput | None
```

### Graph shape

```
START
  │
  ├──────────────────────────────┐
  │                              │                              │
  ▼                              ▼                              ▼
bug_node                  security_node                  pattern_node
  │                              │                              │
  └──────────────────────────────┴──────────────────────────────┘
                                 │
                              collect
                                 │
                               END
```

- `bug_node`, `security_node`, `pattern_node` run in parallel
- `collect` merges all three `AgentOutput` objects into a `SpecialistResult`

### Graph definition (pseudocode)

```python
from langgraph.graph import StateGraph, END

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("bug",      run_bug_agent)
    graph.add_node("security", run_security_agent)
    graph.add_node("pattern",  run_pattern_agent)
    graph.add_node("collect",  collect_results)

    # Fan-out from START to all three agents in parallel
    graph.set_entry_point("bug")       # LangGraph runs all entry-point siblings in parallel
    graph.add_edge("__start__", "bug")
    graph.add_edge("__start__", "security")
    graph.add_edge("__start__", "pattern")

    # All three converge at collect
    graph.add_edge("bug",      "collect")
    graph.add_edge("security", "collect")
    graph.add_edge("pattern",  "collect")

    graph.add_edge("collect", END)

    return graph.compile()
```

---

## Shared helpers

### `diff_utils.py` — extract changed hunks

The diff gives us file paths and line numbers but the raw format is hard to work with.
`diff_utils.py` parses it into structured `DiffHunk` objects that agents can reason about.

```python
from dataclasses import dataclass

@dataclass
class DiffHunk:
    file: str           # relative path
    line_start: int     # first added/modified line (1-indexed)
    line_end: int       # last added/modified line
    added_code: str     # only the + lines (new code)
    full_context: str   # full hunk including context lines (- and +)
```

```python
def parse_diff_hunks(diff: str) -> list[DiffHunk]:
    # Parses unified diff into DiffHunk objects
    # Skips deleted files and binary files
    # Returns only hunks with added lines (new or modified code)
```

### `context.py` — ChromaDB query helper

All three agents use the same ChromaDB query pattern. This lives in one place so
it is not duplicated across three agents.

```python
def get_context_for_hunk(
    hunk: DiffHunk,
    collection_name: str,
    n_results: int = 5,
) -> list[dict]:
    # Embeds hunk.added_code as a query vector
    # Queries ChromaDB collection for n_results nearest chunks
    # Returns list of {text, file, start_line, end_line, symbol_name}
    # Excludes chunks from the same file + overlapping lines (avoid self-match)
```

---

## Bug detection agent — `bug/agent.py`

### What it looks for

| Category | Examples |
|---|---|
| `null_reference` | Accessing attribute on value that could be None/null |
| `unhandled_exception` | Missing try/except around operations that can raise |
| `logic_error` | Off-by-one, wrong operator, incorrect condition |
| `missing_validation` | Input accepted without bounds/type/format check |
| `missed_requirement` | Code does not match what the PR description says it should do |
| `resource_leak` | File/connection opened but not closed in all paths |

### Step-by-step

```
run_bug_agent(state: AgentState) -> AgentState
        │
        ├── 1. parse diff → list[DiffHunk]  (diff_utils.parse_diff_hunks)
        │
        ├── 2. for each hunk:
        │         └── query ChromaDB → list of related code chunks (context.py)
        │
        ├── 3. build prompt
        │         ├── system:  bug detection instructions + output schema
        │         ├── user:    changed code (hunk.added_code)
        │         └── context: related chunks from ChromaDB
        │
        ├── 4. call Claude API with structured output → list[Finding]
        │
        ├── 5. deduplicate findings (same file + overlapping lines = keep highest confidence)
        │
        └── 6. return AgentOutput(agent="bug", findings=findings)
```

### Prompt design — `bug/prompts.py`

```
SYSTEM:
You are a senior software engineer reviewing a pull request for bugs.
You will be given:
  1. The changed code (lines added or modified in this PR)
  2. Related code from the same codebase for context

Your job is to identify real bugs only. A bug is a defect that will cause
incorrect behaviour at runtime. Do NOT flag:
  - Style issues or code smells
  - Missing comments or documentation
  - Anything already handled in the provided context

For each finding, you must provide:
  - The exact file and line range where the bug exists
  - A severity (high / medium / low)
  - A category (null_reference / unhandled_exception / logic_error /
    missing_validation / missed_requirement / resource_leak)
  - A one-sentence title
  - A description of why this is a bug and what could go wrong
  - A concrete suggestion for how to fix it
  - A confidence score between 0.0 and 1.0

If you find no bugs, return an empty findings list. Do not invent findings.

OUTPUT FORMAT: JSON matching the schema below.
{schema}

USER:
## Changed code
File: {file}  Lines: {line_start}–{line_end}

{added_code}

## Related codebase context
{context_chunks}
```

### Deduplication

A single PR may touch the same lines across multiple hunks (e.g. a large refactor).
If two findings overlap (same file, overlapping line range, same category), keep the
one with the higher confidence score and discard the other.

---

## Security agent — `security/agent.py`

### What it looks for

| Category | Examples |
|---|---|
| `hardcoded_secret` | API keys, passwords, tokens in source code |
| `sql_injection` | String interpolation in SQL queries |
| `xss` | Unescaped user input rendered in HTML |
| `auth_gap` | Endpoint missing authentication/authorisation check |
| `insecure_deserialization` | Unpickling untrusted data |
| `path_traversal` | User-controlled file paths without sanitisation |
| `owasp_a01` – `owasp_a10` | OWASP Top 10 categories |

### Step-by-step

Same structure as the bug agent. Key difference: the security prompt is tuned to
look for OWASP patterns and instructs the model to treat hardcoded secrets as always
high severity regardless of confidence.

### Special rule — hardcoded secrets

If a finding has `category == "hardcoded_secret"`, its severity is forced to `"high"`
and confidence is forced to `1.0` regardless of what the model returns. Secrets in
source code are never a false positive worth second-guessing.

---

## Pattern agent — `pattern/agent.py`

### What it looks for

| Category | Examples |
|---|---|
| `naming_convention` | New code uses snake_case where codebase uses camelCase |
| `error_handling_pattern` | Codebase wraps errors in a custom class; new code raises raw exceptions |
| `logging_pattern` | Codebase uses structured logging; new code uses print() |
| `api_response_pattern` | Codebase returns {data, error}; new code returns raw value |
| `test_coverage_pattern` | Similar functions all have tests; this one does not |

### How it differs from bug and security agents

The pattern agent does **not** look for correctness — it looks for consistency. Its
entire job is to compare the new code against the rest of the codebase.

This makes ChromaDB essential here in a way it is not for the other agents. The pattern
agent queries ChromaDB for **similar functions** (not just related ones) and compares
their structure, naming, error handling, and return format against the new code.

```
Pattern agent sees: new function returns raw string on error
Pattern agent queries ChromaDB: "functions that handle errors" → 10 results
Pattern agent observes: 9 of 10 return {"error": "..."} dict
Pattern agent flags: inconsistent error handling pattern (medium, 0.82)
```

### Step-by-step

```
run_pattern_agent(state: AgentState) -> AgentState
        │
        ├── 1. parse diff → list[DiffHunk]
        │
        ├── 2. for each hunk:
        │         └── query ChromaDB with n_results=10 (more context than other agents)
        │
        ├── 3. build prompt
        │         ├── system:  pattern detection instructions
        │         ├── user:    new code
        │         └── context: 10 similar functions from the codebase
        │
        ├── 4. call Claude API → list[Finding]
        │
        └── 5. return AgentOutput(agent="pattern", findings=findings)
```

---

## Claude API — structured output

All three agents use Claude's structured output mode. The response is constrained to
a JSON schema matching `list[Finding]` — Claude cannot return free text.

```python
from anthropic import Anthropic

client = Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    system=system_prompt,
    messages=[{"role": "user", "content": user_prompt}],
    tools=[{
        "name": "report_findings",
        "description": "Report all findings from the code review",
        "input_schema": Finding.model_json_schema(),
    }],
    tool_choice={"type": "tool", "name": "report_findings"},
)
```

Forcing `tool_choice` to a specific tool guarantees structured JSON output — Claude
cannot refuse or return plain text.

---

## LangSmith tracing

Every agent call is traced automatically when the `LANGCHAIN_API_KEY` and
`LANGCHAIN_PROJECT` environment variables are set. No extra code needed in the agents
— LangGraph instruments itself.

Each trace captures:
- Input state (diff, collection_name)
- Which node ran, when, and for how long
- The exact prompt sent to Claude
- The raw Claude response
- The parsed `AgentOutput`

This is what allows confidence threshold recalibration in Phase 4.

---

## Async strategy

`run_specialist_agents()` is `async`. The LangGraph graph runs the three agent nodes
in parallel using `asyncio`. Each agent node is also `async` — the Claude API call
and ChromaDB queries are both I/O-bound and benefit from async.

```
main.py (async)
    └── await run_specialist_agents()       ← async, returns SpecialistResult
              └── LangGraph graph (async)
                        ├── run_bug_agent()      ← async, parallel
                        ├── run_security_agent() ← async, parallel
                        └── run_pattern_agent()  ← async, parallel
```

---

## Function signatures

### `specialist/__init__.py`

```python
async def run_specialist_agents(
    diff: str,
    collection_name: str,
    owner: str,
    repo_name: str,
) -> SpecialistResult: ...
```

### `graph.py`

```python
def build_graph() -> CompiledGraph: ...

async def run_bug_agent(state: AgentState) -> dict: ...
async def run_security_agent(state: AgentState) -> dict: ...
async def run_pattern_agent(state: AgentState) -> dict: ...
def collect_results(state: AgentState) -> dict: ...
```

### `diff_utils.py`

```python
@dataclass
class DiffHunk:
    file: str
    line_start: int
    line_end: int
    added_code: str
    full_context: str

def parse_diff_hunks(diff: str) -> list[DiffHunk]: ...
```

### `context.py`

```python
def get_context_for_hunk(
    hunk: DiffHunk,
    collection_name: str,
    n_results: int = 5,
) -> list[dict]: ...
```

### `bug/agent.py`

```python
async def run_bug_agent(state: AgentState) -> dict:
    # returns {"bug_output": AgentOutput}
```

### `security/agent.py`

```python
async def run_security_agent(state: AgentState) -> dict:
    # returns {"security_output": AgentOutput}
```

### `pattern/agent.py`

```python
async def run_pattern_agent(state: AgentState) -> dict:
    # returns {"pattern_output": AgentOutput}
```

---

## How it plugs into `main.py`

```python
# top of main.py — add alongside existing imports
from app.agents.specialist import run_specialist_agents

# inside the pull_request handler, replacing the Phase 3 TODO
specialist_result = await run_specialist_agents(
    diff=diff,
    collection_name=ingestion_result.collection_name,
    owner=owner,
    repo_name=repo_name,
)
all_findings = specialist_result.all_findings()
print(f"Findings: {len(all_findings)} total "
      f"({len(specialist_result.bug.findings)} bug, "
      f"{len(specialist_result.security.findings)} security, "
      f"{len(specialist_result.pattern.findings)} pattern)")
# TODO Phase 4: pass all_findings to critic agent
```

---

## Dependencies added to `requirements.txt`

```
anthropic>=0.25.0
langgraph>=0.1.0
langsmith>=0.1.0
```

---

## Environment variables added to `.env`

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key for agent LLM calls |
| `LANGCHAIN_API_KEY` | LangSmith API key for tracing |
| `LANGCHAIN_PROJECT` | LangSmith project name (e.g. `pr-review-agent`) |
| `LANGCHAIN_TRACING_V2` | Set to `true` to enable LangSmith tracing |

---

## Build order

1. `backend/app/models/findings.py` — `Finding`, `AgentOutput`, `SpecialistResult`
2. `specialist/diff_utils.py` — `DiffHunk`, `parse_diff_hunks()`
3. `specialist/context.py` — `get_context_for_hunk()`
4. `specialist/models.py` (graph state) — `AgentState`
5. `bug/prompts.py` — prompt templates
6. `bug/agent.py` — `run_bug_agent()`
7. `specialist/graph.py` — LangGraph fan-out wiring
8. `specialist/__init__.py` — `run_specialist_agents()`
9. Wire into `main.py`
10. `security/` and `pattern/` — same pattern as bug

---

## What is NOT done in this phase

- Critic agent — Phase 4, challenges every finding and assigns final confidence score
- PostgreSQL storage of findings — Phase 4
- Next.js dashboard — Phase 4
- PR writer agent — Phase 5
- Severity routing — Phase 5
- PR intent ingestion (PR description + linked ticket) — noted in design doc §7, deferred
- Weekly digest — Phase 5
