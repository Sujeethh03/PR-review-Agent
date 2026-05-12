import json
import os
from openai import OpenAI
from app.models.findings import Finding
from app.models.critic import CriticVerdict, CriticOutput, finding_hash
from app.agents.specialist.context import get_context_for_hunk
from app.agents.specialist.diff_utils import DiffHunk
from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, format_context_chunks
from .code_utils import extract_flagged_code

_client: OpenAI | None = None

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "accepted":          {"type": "boolean"},
        "final_confidence":  {"type": "number"},
        "reasoning":         {"type": "string"},
        "context_used":      {"type": "array", "items": {"type": "string"}},
    },
    "required": ["accepted", "final_confidence", "reasoning", "context_used"],
    "additionalProperties": False,
}


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def _is_hardcoded_secret(finding: Finding) -> bool:
    return finding.category == "hardcoded_secret"


def _has_thin_pattern_context(finding: Finding, context_chunks: list[dict]) -> bool:
    return finding.agent == "pattern" and len(context_chunks) < 3


async def challenge_finding(
    finding: Finding,
    flagged_code: str,
    context_chunks: list[dict],
    pr_description: str,
) -> CriticVerdict:
    fhash = finding_hash(finding)

    # Special rule: hardcoded secrets are never rejected
    if _is_hardcoded_secret(finding):
        return CriticVerdict(
            finding_hash=fhash,
            accepted=True,
            final_confidence=1.0,
            reasoning="Hardcoded secrets are unconditionally accepted — no context mitigates a secret in source code.",
            context_used=[],
        )

    # Special rule: pattern findings with fewer than 3 context chunks lack evidence
    if _has_thin_pattern_context(finding, context_chunks):
        return CriticVerdict(
            finding_hash=fhash,
            accepted=False,
            final_confidence=0.0,
            reasoning="Pattern finding rejected — fewer than 3 codebase examples to establish an established convention.",
            context_used=[],
        )

    user_prompt = USER_PROMPT_TEMPLATE.format(
        category=finding.category,
        severity=finding.severity,
        agent=finding.agent,
        file=finding.file,
        line_start=finding.line_start,
        line_end=finding.line_end,
        title=finding.title,
        description=finding.description,
        suggestion=finding.suggestion,
        original_confidence=finding.confidence,
        flagged_code=flagged_code,
        pr_description=pr_description or "(no PR description provided)",
        context_chunks=format_context_chunks(context_chunks),
    )

    response = _get_client().chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        tools=[{
            "type": "function",
            "function": {
                "name": "submit_verdict",
                "description": "Submit the critic verdict for this finding",
                "parameters": VERDICT_SCHEMA,
            },
        }],
        tool_choice={"type": "function", "function": {"name": "submit_verdict"}},
        temperature=0,
    )

    tool_call = response.choices[0].message.tool_calls[0]
    raw = json.loads(tool_call.function.arguments)

    return CriticVerdict(
        finding_hash=fhash,
        accepted=raw["accepted"],
        final_confidence=raw["final_confidence"],
        reasoning=raw["reasoning"],
        context_used=raw.get("context_used", []),
    )


async def run_critic_agent(
    findings: list[Finding],
    collection_name: str,
    diff: str,
    repo_path: str,
    pr_description: str,
) -> CriticOutput:
    accepted: list[Finding] = []
    rejected: list[Finding] = []
    verdicts: list[CriticVerdict] = []

    for finding in findings:
        # 1. Extract the exact code at the flagged lines
        flagged_code = extract_flagged_code(
            diff, finding.file, finding.line_start, finding.line_end, repo_path
        )

        # 2. Query ChromaDB for surrounding context — reuse the specialist helper
        hunk = DiffHunk(
            file=finding.file,
            line_start=finding.line_start,
            line_end=finding.line_end,
            added_code=flagged_code,
            full_context=flagged_code,
        )
        context_chunks = get_context_for_hunk(hunk, collection_name, n_results=5)

        # 3. Challenge the finding
        try:
            verdict = await challenge_finding(
                finding=finding,
                flagged_code=flagged_code,
                context_chunks=context_chunks,
                pr_description=pr_description,
            )
        except Exception as e:
            # On error, accept with original confidence so findings aren't silently lost
            verdict = CriticVerdict(
                finding_hash=finding_hash(finding),
                accepted=True,
                final_confidence=finding.confidence,
                reasoning=f"Critic error — kept with original confidence. Error: {e}",
                context_used=[],
            )

        verdicts.append(verdict)

        if verdict.accepted:
            # Update confidence to the critic's reassessed score
            accepted.append(finding.model_copy(update={"confidence": verdict.final_confidence}))
        else:
            rejected.append(finding)

    return CriticOutput(accepted=accepted, rejected=rejected, verdicts=verdicts)
