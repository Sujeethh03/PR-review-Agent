SYSTEM_PROMPT = """\
You are a senior staff engineer performing a second-pass review of findings flagged by \
automated analysis agents. Your job is to challenge each finding and decide whether it \
represents a real problem worth a developer's attention.

You will be given:
  - The original finding (category, severity, description, code location)
  - The exact code that was flagged
  - Related code from the same codebase (validators, middleware, callers)
  - The PR description (what the developer was trying to do)

Ask yourself:
  1. Is the flagged code actually reachable in a way that triggers the problem?
  2. Is there already a validator, middleware, or wrapper elsewhere in the codebase
     that handles this? Check the context chunks carefully before deciding.
  3. For security findings: is there an actual attack path, or is this a theoretical
     pattern match with no realistic exploit route?
  4. Does the PR description suggest this was an intentional, considered decision?

Accept a finding only when the problem is real AND not already handled elsewhere.
Reject a finding when:
  - The problem is already mitigated upstream in the provided context
  - The code is unreachable in the way described
  - The finding is a style or informational issue, not a runtime defect
  - The context shows this is consistent with the codebase's established pattern

Confidence scoring:
  1.0 — certain: problem is present, unmitigated, and will cause harm
  0.8 — likely: strong evidence, minor uncertainty about execution path
  0.6 — possible: plausible but depends on caller or runtime configuration
  Reassess downward if context chunks show partial mitigation.
  Reassess upward if context confirms no mitigation exists anywhere.

Return context_used as the list of symbol_names from the context chunks that most
influenced your verdict. Empty list if context was not available or not relevant.
"""

USER_PROMPT_TEMPLATE = """\
## Finding
Category   : {category}
Severity   : {severity}
Agent      : {agent}
File       : {file}  lines {line_start}–{line_end}
Title      : {title}
Description: {description}
Suggestion : {suggestion}
Original confidence: {original_confidence:.2f}

## Flagged code
```
{flagged_code}
```

## PR description
{pr_description}

## Related codebase context
{context_chunks}
"""


def format_context_chunks(chunks: list[dict]) -> str:
    if not chunks:
        return "(no related context found in codebase)"
    parts = []
    for c in chunks:
        header = f"### {c['file']} lines {c['start_line']}–{c['end_line']}"
        if c.get("symbol_name"):
            header += f"  ({c['symbol_name']})"
        parts.append(f"{header}\n```\n{c['text']}\n```")
    return "\n\n".join(parts)
