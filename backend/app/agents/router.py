from typing import Literal
from app.models.findings import Finding


def route_finding(finding: Finding) -> Literal["auto", "queue", "digest"]:
    if finding.confidence >= 0.95 and finding.severity == "high":
        return "auto"
    elif finding.confidence >= 0.70:
        return "queue"
    elif finding.severity == "high":
        # High severity always reaches the dashboard, never silently digested
        return "queue"
    else:
        return "digest"
