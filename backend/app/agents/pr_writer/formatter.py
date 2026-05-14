from app.models.findings import Finding

_SEVERITY_LABEL = {
    "high":   "🚨 HIGH",
    "medium": "⚠️ MEDIUM",
    "low":    "💡 LOW",
}


def format_finding_comment(finding: Finding) -> str:
    label = _SEVERITY_LABEL.get(finding.severity, finding.severity.upper())
    return (
        f"## {label} — {finding.title}\n\n"
        f"**Category:** `{finding.category}`  \n"
        f"**Agent:** {finding.agent}  \n"
        f"**Confidence:** {finding.confidence:.0%}\n\n"
        f"{finding.description}\n\n"
        f"**Suggestion:** {finding.suggestion}"
    )


def format_summary_comment(findings: list[Finding]) -> str:
    lines = ["## Code Review Agent — Auto-posted Findings\n"]
    for f in findings:
        label = _SEVERITY_LABEL.get(f.severity, f.severity.upper())
        lines.append(f"- {label} **{f.title}** (`{f.file}` line {f.line_start})")
    return "\n".join(lines)
