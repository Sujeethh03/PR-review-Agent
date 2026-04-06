---
title: Multi-Agent Code Review System
subtitle: Product Design Document
version: 1.0.0
status: Draft
author: 
created: 2026-04-06
last_updated: 2026-04-06
reviewed_by: 
approved_by: 
next_review: 2026-05-06
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
| **Version** | 1.0.0 |
| **Status** | Draft |
| **Author** | — |
| **Created** | 06 April 2026 |
| **Last updated** | 06 April 2026 |
| **Reviewed by** | — |
| **Approved by** | — |
| **Next review date** | 06 May 2026 |
| **Classification** | Internal |
| **Project code** | CR-001 |
| **Repository** | github.com/your-org/code-review-agent |

---

## Version History

| Version | Date | Author | Status | Summary of changes |
|---|---|---|---|---|
| 1.0.0 | 06 Apr 2026 | — | Draft | Initial document — full system design including severity routing, PR intent awareness, and educational comment layer |

---

## Document Status

| Stage | Owner | Status | Date |
|---|---|---|---|
| First draft | Author | ✅ Complete | 06 Apr 2026 |
| Technical review | Tech lead | ⬜ Pending | — |
| Product review | Product owner | ⬜ Pending | — |
| Final approval | — | ⬜ Pending | — |
| Published | — | ⬜ Pending | — |

---

## Table of Contents

1. [Overview](#1-overview)
2. [The Problem](#2-the-problem)
3. [What It Is](#3-what-it-is)
4. [Full System Flow](#4-full-system-flow)
5. [How It Works — Step by Step](#5-how-it-works--step-by-step)
6. [Trust Model](#6-trust-model)
7. [Design Additions](#7-design-additions)
8. [What It Solves](#8-what-it-solves)
9. [Known Limitations](#9-known-limitations)
10. [Technology Stack](#10-technology-stack)
11. [Build Plan](#11-build-plan)
12. [Open Questions](#12-open-questions)
13. [Glossary](#13-glossary)

---

## 1. Overview

| Field | Details |
|---|---|
| **Product name** | Multi-Agent Code Review System |
| **Project code** | CR-001 |
| **Target users** | Engineering teams using GitHub for code review |
| **Primary language support** | Python, Java |
| **Deployment target** | Railway / Fly.io (backend), Vercel (dashboard) |
| **Estimated build time** | 8–10 weeks |
| **Trust level default** | Level 1 — read only |
| **Review turnaround** | Under 60 seconds from push to findings |

### Purpose

This document describes the full product design for the Multi-Agent Code Review System — an AI-powered pipeline that automatically reviews pull requests on GitHub. It covers the system architecture, agent responsibilities, trust model, design decisions, and build plan. It is intended as the single source of truth for anyone building, reviewing, or extending this system.

### Scope

This document covers the end-to-end pipeline from GitHub webhook to posted PR comment, including all agent logic, the human approval dashboard, severity routing, PR intent awareness, and the educational comment layer. It does not cover billing, user authentication for the dashboard, or multi-repository organisation management — these are deferred to a future version.

### Out of Scope

- Multi-organisation / SaaS billing model
- Dashboard user authentication and role management
- Support for languages other than Python and Java
- Integration with code review tools other than GitHub

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

An AI-powered senior engineer that lives inside your GitHub repository. The moment a developer pushes code, a pipeline of specialised agents analyses the change, challenges its own findings, and surfaces a structured review — ready for human sign-off — before the developer has closed their laptop.

Instead of one model doing everything, the system runs a coordinated pipeline of agents, each with a specific responsibility. They work in parallel, challenge each other's findings, and only surface a comment when they have collectively agreed something is worth flagging.

### Key metrics

| Metric | Target |
|---|---|
| Time from push to findings ready | < 60 seconds |
| False positive rate (after critic) | < 15% |
| Finding acceptance rate (human dashboard) | > 70% |
| Supported languages | Python, Java |
| Agents in the pipeline | 5 (ingestion, bug, security, pattern, critic) |
| Trust levels | 3 |

---

## 4. Full System Flow

```
GitHub Push / PR Open
        │
        ▼
┌─────────────────────────────────┐
│   PR Context Ingestion   [NEW]  │  pulls PR description, linked ticket,
│                                 │  commit messages — captures intent
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│      FastAPI Receiver           │  catches webhook, validates signature
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│      Ingestion Agent            │  clones repo, chunks by function/class,
│                                 │  embeds into ChromaDB vector store
└────────────────┬────────────────┘
                 │
        ┌────────┴────────┐
        │   parallel      │
        │   fan-out       │
        │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Bug Detection│  │   Security   │  │   Pattern    │
│    Agent     │  │    Agent     │  │    Agent     │
│              │  │              │  │              │
│ null refs,   │  │ OWASP,       │  │ compares     │
│ logic errors,│  │ secrets,     │  │ diff against │
│ missed reqs  │  │ auth gaps    │  │ full codebase│
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │
       └─────────────────┴──────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │         Critic Agent           │
        │                                │
        │  challenges every finding      │◄─── PR intent context [NEW]
        │  retrieves codebase context    │
        │  assigns confidence score      │
        │  drops false positives         │
        └───────────────┬────────────────┘
                        │
                        ▼
        ┌────────────────────────────────┐
        │      Severity Router   [NEW]   │
        │                                │
        │  routes by confidence score    │
        │  and finding severity          │
        └──────┬──────────┬──────────────┘
               │          │                    │
    confidence │    confidence           confidence
      > 95%    │     70–95%               < 70%
    + High sev │   + Medium sev         + Low sev
               │          │                    │
               ▼          ▼                    ▼
    ┌──────────────┐  ┌───────────────┐  ┌───────────────┐
    │ Auto-post to │  │    Human      │  │    Weekly     │
    │   GitHub     │  │   Approval    │  │    Digest     │
    │              │  │   Dashboard   │  │               │
    │ + page senior│  │ (Next.js)     │  │  batched,     │
    │   engineer   │  │               │  │  low priority │
    │  [Level 3]   │  │  [Level 1/2]  │  │               │
    └──────┬───────┘  └──────┬────────┘  └───────────────┘
           │                 │
           └────────┬────────┘
                    │
                    ▼
        ┌─────────────────────────────────────┐
        │          PR Writer Agent            │
        │                                     │
        │  formats finding as inline comment  │
        │  attaches to exact line number      │
        │  includes suggested code diff       │
        └──────────────────┬──────────────────┘
                           │
                           ▼
        ┌─────────────────────────────────────┐
        │       Educational Layer    [NEW]    │
        │                                     │
        │  adds why the problem matters       │
        │  links to OWASP / standards         │
        │  teaches, not just corrects         │
        └──────────────────┬──────────────────┘
                           │
                           ▼
        ┌─────────────────────────────────────┐
        │            GitHub API               │
        │                                     │
        │  posts inline PR comment            │
        │  developer receives email notif     │
        └─────────────────────────────────────┘
```

---

## 5. How It Works — Step by Step

### Step 1 — A push triggers the pipeline

When code is pushed to GitHub, a webhook fires instantly. The system receives the event, validates it, and begins processing. From this moment, the clock is running.

### Step 2 — PR intent is captured `[NEW]`

Before analysing a single line of code, the system reads what the developer was trying to do. It pulls the pull request description, the linked ticket from Jira or GitHub Issues, and the commit messages on the branch. This context is stored and fed into the critic agent later to distinguish intentional decisions from mistakes.

The practical effect is a new class of finding. If a ticket specifies that a refund endpoint should only process amounts under fifty dollars, and the code has no such limit, the critic can flag this as a missed requirement — something no code pattern matcher would ever catch.

### Step 3 — The codebase is made searchable

A dedicated ingestion agent clones the repository and breaks every file into meaningful chunks — individual functions, classes, and methods — rather than arbitrary slices of text. Each chunk is converted into a numerical representation and stored in ChromaDB, a vector database.

On the first run, the full codebase is ingested. On every subsequent push, only the changed files are updated. The process is fast and inexpensive.

### Step 4 — Three specialist agents run in parallel

With the codebase searchable and PR intent captured, three agents run simultaneously.

| Agent | What it looks for |
|---|---|
| **Bug detection** | Null references, unhandled exceptions, broken logic, missing validations, and cases where the code does not match what the PR description says it should do |
| **Security** | Hardcoded secrets, missing authentication checks, SQL injection risks, and OWASP Top 10 patterns |
| **Pattern** | Inconsistencies between new code and the established conventions of the rest of the codebase |

### Step 5 — The critic agent challenges every finding

This is the most important step in the pipeline.

The three specialist agents are tuned to find problems. They will flag many things that look suspicious in isolation but are perfectly safe in context. Without a filtering step, the system would post noisy, inaccurate comments that erode developer trust within days.

The critic agent receives every finding and asks a single hard question: is this actually a real problem, or does it just look like one? It retrieves surrounding context from the vector database, checks for upstream validators or middleware that might make the finding irrelevant, compares against the PR intent captured in Step 2, and assigns a confidence score to each finding. Anything below the threshold is dropped entirely.

### Step 6 — Findings are routed by severity `[NEW]`

Not every finding deserves the same response. The severity router reads the critic's confidence score and the finding's severity level, then sends each finding down one of three paths.

| Trigger | Path | What happens |
|---|---|---|
| Confidence > 95% + High severity | Auto-post | Posted to GitHub immediately. Senior engineer is paged. A hardcoded production secret does not wait overnight. |
| Confidence 70–95% + Medium severity | Human dashboard | Sent to the approval dashboard. A senior engineer reviews and approves before anything reaches GitHub. |
| Confidence < 70% + Low severity | Weekly digest | Batched into a weekly email. Too uncertain to post, too useful to discard. |

### Step 7 — A human approves findings

For medium-severity findings, the senior engineer opens the approval dashboard and sees a clean list of pre-filtered findings. Each one shows the file and line number, an explanation of the problem, the confidence score, and a suggested code fix.

The engineer approves or dismisses each finding. Nothing reaches GitHub until they click approve. This is the core trust principle: AI recommends, humans decide.

### Step 8 — Structured comments are posted to GitHub `[NEW]`

Once approved, the PR writer agent formats the finding as a proper inline GitHub review comment attached to the exact line of code. The educational layer then enriches every comment with three things:

- **What** the problem is
- **Why** it matters in concrete terms — not just that it is bad practice, but the specific risk it introduces
- **A reference link** to the relevant standard or documentation

A comment about a hardcoded API key does not just say "use an environment variable." It explains that if the repository becomes public or logs are accessed by an attacker, the key can be used to initiate arbitrary charges. It links to the relevant OWASP standard.

GitHub sends a standard notification email to the developer. From their perspective, they received a specific, actionable review with a one-click fix suggestion — faster than any human review cycle.

---

## 6. Trust Model

The biggest mistake in AI agent design is building something that acts autonomously on consequential decisions. Code review gatekeeps what goes into production. This system is built around three explicit trust levels.

| Level | Name | Behaviour | Default |
|---|---|---|---|
| **Level 1** | Read only | Agent reads code and posts findings as a comment on an existing human-opened PR. Never opens anything itself. | ✅ Yes |
| **Level 2** | Draft and approve | Agent prepares a full review but holds it in the dashboard waiting for human approval before touching GitHub. | No |
| **Level 3** | Auto for narrow cases | Agent acts automatically, but only for high-confidence findings in an explicitly defined category. Teams opt in deliberately. | No |

> **Default: Level 1.** Teams must explicitly opt into Level 2 or Level 3 for specific finding categories. Auto-acting on consequential code changes without a documented opt-in is not permitted.

---

## 7. Design Additions

These capabilities extend the core pipeline beyond simple code pattern matching. Each is marked `[NEW]` in the system flow diagram above.

### PR intent awareness `[NEW]`

The system ingests the pull request description, the linked ticket, and the commit message trail before analysing any code. This gives every downstream agent access to what the developer was trying to accomplish, not just what they wrote.

This enables a new class of finding: missed requirements. Business logic errors — things no code pattern matcher would ever catch — become detectable.

**Why it matters:** A security agent can tell you a validation is missing. Only an agent that has read the ticket can tell you the validation was explicitly required by the business and was missed entirely.

### Severity-based routing `[NEW]`

Instead of sending every finding to the same human approval queue, the system routes each finding based on its confidence score and severity level. Critical, high-confidence findings post immediately. Uncertain, low-severity findings are batched for a weekly digest. Only medium-confidence findings go to the dashboard for human review.

**Why it matters:** A hardcoded production API key should not wait until morning for someone to open the dashboard. Routing by severity ensures the system responds proportionally to actual risk.

### Educational context in every comment `[NEW]`

Every comment posted to GitHub includes what the problem is, why it matters in concrete terms, and a reference to the relevant standard. This turns the tool from a linter into something that makes junior developers measurably better over time.

**Why it matters:** Telling a developer to "use an environment variable" teaches nothing. Explaining that a leaked key can be used to initiate arbitrary charges on a live Stripe account teaches them to think about risk — and they will not make the same mistake again.

---

## 8. What It Solves

| Without the system | With the system |
|---|---|
| PR sits unreviewed for 1–2 days | Findings ready within 60 seconds |
| Senior engineers spend hours on mechanical checks | Senior engineers spend minutes approving pre-filtered findings |
| Noisy AI tools erode developer trust | Critic agent filters false positives before humans ever see them |
| Junior developers receive feedback too late to learn | Educational context in every comment builds developer skill over time |
| Critical security bugs wait overnight for review | High-confidence security findings post immediately and page the engineer |
| Agents have no understanding of business requirements | PR intent ingestion enables detection of missed requirements |

---

## 9. Known Limitations

The system covers roughly 60–70% of the judgments a senior engineer makes during code review. The remaining 30–40% require human expertise and always will.

| Limitation | Reason | Mitigation |
|---|---|---|
| Cannot reason about unwritten context | Decisions made verbally in meetings live nowhere in the codebase | Teams can document decisions as ADRs and ingest them |
| Cannot make strategic architectural calls | Requires understanding of product direction, not just code patterns | Human approval step ensures engineers stay in the loop |
| Java and Python only | tree-sitter and javalang parsers only | Additional language parsers can be added in a future version |
| Large monorepos may be slow on first ingest | Full codebase embedding is a one-time expensive operation | Scoped ingestion per service can reduce initial cost |
| Agent confidence scores are not perfectly calibrated | LLM outputs are probabilistic | LangSmith tracing allows ongoing recalibration |

> **The goal is not to replace senior engineers.** It is to ensure that when they do show up, they are spending their time on the problems that genuinely need them.

---

## 10. Technology Stack

| Layer | Tool | Purpose |
|---|---|---|
| Webhook receiver | FastAPI | Receives GitHub events, validates HMAC signatures |
| Async server | Uvicorn | ASGI server for FastAPI |
| HTTP client | httpx | Async calls to GitHub API |
| Repo cloning | gitpython | Clones repositories programmatically |
| Code parsing — Python | tree-sitter | AST-level chunking, not character splitting |
| Code parsing — Java | javalang | Java-specific AST parsing |
| Embeddings | OpenAI text-embedding-3-small | Converts code chunks to vectors |
| Vector database | ChromaDB | Stores and retrieves embedded code chunks by semantic similarity |
| Agent orchestration | LangGraph | Manages parallel fan-out and sequential pipeline |
| LLM provider (primary) | Claude (Anthropic) | Agent reasoning and generation |
| LLM provider (alternative) | OpenAI GPT-4o | Drop-in alternative |
| Observability | LangSmith | Traces every agent decision for debugging |
| Structured outputs | Pydantic | Typed outputs from each agent |
| Human dashboard | Next.js 14 | Approval interface with audit trail |
| UI components | shadcn/ui | Dashboard component library |
| Data fetching | TanStack Query | Fetches and caches findings from FastAPI |
| Relational database | PostgreSQL | Stores findings, approvals, audit trail |
| Job queue | Redis | Queues webhook jobs, manages workflow state |
| Containerisation | Docker + Docker Compose | Packages backend and worker |
| Cloud deployment | Railway or Fly.io | Hosts backend |
| Frontend deployment | Vercel | Hosts Next.js dashboard |
| CI/CD | GitHub Actions | Automated testing and deployment pipeline |

---

## 11. Build Plan

| Phase | Weeks | Goal | Complexity |
|---|---|---|---|
| Foundation | 1–2 | GitHub webhook received and logged. Repo cloning working. PostgreSQL and Docker set up. | Low |
| RAG pipeline | 3–4 | Codebase chunked, embedded, stored in ChromaDB. Retrieval function working against real diffs. | Medium |
| Specialist agents | 5–6 | Bug, security, and pattern agents running in parallel via LangGraph. Structured Pydantic outputs. LangSmith tracing active. | Medium–High |
| Critic + dashboard | 7–8 | Critic agent filtering false positives. Human approval dashboard live. Full loop working end to end. | High |
| PR writer + deployment | 9–10 | Formatted GitHub comments posting. Severity routing live. Educational layer added. Deployed to Railway and Vercel. | Medium |

### Milestones

| Milestone | Description |
|---|---|
| M1 — Webhook received | Push a commit to GitHub, see it logged in the terminal |
| M2 — RAG working | Query the vector store, get back relevant code context for a given diff |
| M3 — Agents running | Three agents return structured JSON findings against a real GitHub repo |
| M4 — Full loop | Push code, see findings in dashboard, approve, see GitHub comment posted |
| M5 — Live and deployed | System is publicly accessible and demonstrable on any GitHub repo in real time |

---

## 12. Open Questions

| # | Question | Owner | Priority | Status |
|---|---|---|---|---|
| 1 | Which LLM provider should be the default — Claude or GPT-4o? | Tech lead | High | Open |
| 2 | Should the weekly digest be an email or a Slack message? | Product owner | Medium | Open |
| 3 | How should the dashboard handle authentication — OAuth via GitHub or email/password? | Tech lead | High | Open |
| 4 | What is the confidence threshold for the critic agent — 70% or configurable per team? | Tech lead | Medium | Open |
| 5 | Should ADR ingestion be in v1 or deferred to v2? | Product owner | Low | Open |
| 6 | How do we handle monorepos with multiple services — ingest everything or scope to changed service? | Tech lead | Medium | Open |

---

## 13. Glossary

| Term | Definition |
|---|---|
| **ADR** | Architecture Decision Record — a short document capturing a significant architectural decision and its rationale |
| **Agent** | An AI model with a specific, scoped responsibility in the pipeline |
| **AST** | Abstract Syntax Tree — a structured representation of source code that captures its logical structure rather than raw text |
| **Critic agent** | The agent responsible for challenging findings from the three specialist agents, filtering false positives, and assigning confidence scores |
| **ChromaDB** | An open-source vector database used to store and retrieve embedded code chunks |
| **Embedding** | A numerical representation of a piece of text that captures its semantic meaning |
| **False positive** | A finding flagged by an agent that is not actually a real problem |
| **Fan-out** | The step where a single input is sent to multiple agents simultaneously for parallel processing |
| **Ingestion agent** | The agent responsible for cloning the repository, chunking files, and storing embeddings in ChromaDB |
| **LangGraph** | A framework for building multi-agent pipelines with parallel and sequential steps |
| **LangSmith** | An observability tool that traces and logs every decision made by each agent in the pipeline |
| **OWASP** | Open Web Application Security Project — the standard reference for web security vulnerabilities |
| **PR intent** | The developer's stated purpose for a pull request, captured from the PR description, linked ticket, and commit messages |
| **RAG** | Retrieval-Augmented Generation — a technique where relevant context is retrieved from a knowledge base and given to an LLM before it generates a response |
| **Severity router** | The component that routes each finding to auto-post, human dashboard, or weekly digest based on confidence score and severity level |
| **Trust level** | A configuration setting that controls how autonomously the system is allowed to act (Level 1 = read only, Level 2 = draft and approve, Level 3 = auto for narrow cases) |
| **Vector database** | A database that stores numerical representations of data and enables retrieval by semantic similarity rather than exact keyword match |
| **Webhook** | An HTTP callback that GitHub fires automatically when a specific event occurs, such as a code push |

---

*Built with Python · LangGraph · FastAPI · Next.js · ChromaDB · LangSmith · Docker · GitHub API*

*Document version 1.0.0 — Last updated 06 April 2026 — Classification: Internal*
