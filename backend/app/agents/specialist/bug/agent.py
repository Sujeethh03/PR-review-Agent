import asyncio
import json
import os
from openai import AsyncOpenAI
from app.models.findings import Finding, AgentOutput
from app.agents.specialist.diff_utils import parse_diff_hunks, DiffHunk
from app.agents.specialist.context import get_context_for_hunk
from app.agents.specialist.graph import AgentState
from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, format_context_chunks

_client: AsyncOpenAI | None = None

FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file":        {"type": "string"},
                    "line_start":  {"type": "integer"},
                    "line_end":    {"type": "integer"},
                    "severity":    {"type": "string", "enum": ["high", "medium", "low"]},
                    "category":    {"type": "string"},
                    "title":       {"type": "string"},
                    "description": {"type": "string"},
                    "suggestion":  {"type": "string"},
                    "confidence":  {"type": "number"},
                },
                "required": ["file", "line_start", "line_end", "severity",
                             "category", "title", "description", "suggestion", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def _deduplicate(findings: list[Finding]) -> list[Finding]:
    kept: list[Finding] = []
    for new in findings:
        overlap = next(
            (
                f for f in kept
                if f.file == new.file
                and f.category == new.category
                and f.line_start <= new.line_end
                and f.line_end >= new.line_start
            ),
            None,
        )
        if overlap is None:
            kept.append(new)
        elif new.confidence > overlap.confidence:
            kept.remove(overlap)
            kept.append(new)
    return kept


async def _process_hunk(hunk: DiffHunk, collection_name: str) -> list[Finding]:
    context_chunks = await get_context_for_hunk(hunk, collection_name, n_results=5)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        file=hunk.file,
        line_start=hunk.line_start,
        line_end=hunk.line_end,
        added_code=hunk.added_code,
        context_chunks=format_context_chunks(context_chunks),
    )
    response = await _get_client().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        tools=[{
            "type": "function",
            "function": {
                "name": "report_findings",
                "description": "Report all bug findings from the code review",
                "parameters": FINDINGS_SCHEMA,
            },
        }],
        tool_choice={"type": "function", "function": {"name": "report_findings"}},
        temperature=0,
    )
    tool_call = response.choices[0].message.tool_calls[0]
    raw = json.loads(tool_call.function.arguments)
    return [
        Finding(**item, agent="bug")
        for item in raw.get("findings", [])
        if item.get("confidence", 0) >= 0.6
    ]


async def run_bug_agent(state: AgentState) -> dict:
    try:
        hunks = parse_diff_hunks(state["diff"])
        results = await asyncio.gather(
            *[_process_hunk(h, state["collection_name"]) for h in hunks],
            return_exceptions=True,
        )
        all_findings: list[Finding] = []
        for r in results:
            if isinstance(r, list):
                all_findings.extend(r)
        return {"bug_output": AgentOutput(agent="bug", findings=_deduplicate(all_findings))}
    except Exception as e:
        return {"bug_output": AgentOutput(agent="bug", findings=[], error=str(e))}
