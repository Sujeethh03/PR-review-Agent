from app.models.findings import Finding
from app.agents.pr_writer.education import get_educational_context

_SEVERITY_LABEL = {
    "high":   "🚨 HIGH",
    "medium": "⚠️ MEDIUM",
    "low":    "💡 LOW",
}


def format_finding_comment(finding: Finding) -> str:
    label = _SEVERITY_LABEL.get(finding.severity, finding.severity.upper())
    educational = get_educational_context(finding)

    parts = [
        f"## {label} — {finding.title}",
        f"",
        f"**Category:** `{finding.category}` &nbsp;|&nbsp; **Agent:** {finding.agent} &nbsp;|&nbsp; **Confidence:** {finding.confidence:.0%}",
        f"",
        finding.description,
        f"",
        f"**Suggestion:** {finding.suggestion}",
    ]

    if educational:
        parts += ["", "---", "", educational]

    return "\n".join(parts)


def format_summary_comment(findings: list[Finding]) -> str:
    lines = ["## Code Review Agent — Auto-posted Findings\n"]
    for f in findings:
        label = _SEVERITY_LABEL.get(f.severity, f.severity.upper())
        lines.append(f"- {label} **{f.title}** (`{f.file}` line {f.line_start})")
    return "\n".join(lines)
