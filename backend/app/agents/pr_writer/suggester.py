import os
from openai import OpenAI
from app.models.findings import Finding
from app.agents.specialist.diff_utils import parse_diff_hunks

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def _extract_flagged_code(diff: str, finding: Finding) -> str:
    for hunk in parse_diff_hunks(diff):
        if (hunk.file == finding.file
                and hunk.line_start <= finding.line_end
                and hunk.line_end >= finding.line_start):
            return hunk.added_code
    return ""


async def generate_suggestion(finding: Finding, diff: str) -> str | None:
    flagged_code = _extract_flagged_code(diff, finding)
    if not flagged_code.strip():
        return None

    prompt = (
        "You are a code fix assistant. Return ONLY the corrected replacement code.\n"
        "Preserve exact indentation and line count where possible. "
        "No explanation, no markdown fences — just the fixed code.\n\n"
        f"Category: {finding.category}\n"
        f"Problem: {finding.description}\n"
        f"Fix needed: {finding.suggestion}\n\n"
        f"Flagged code:\n{flagged_code}\n\n"
        "Return the corrected code:"
    )

    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=400,
        )
        suggested = response.choices[0].message.content.strip()

        # Skip if identical to input or implausibly long
        if not suggested or suggested == flagged_code.strip():
            return None
        if len(suggested) > len(flagged_code) * 4:
            return None

        return suggested
    except Exception:
        return None
