from typing import Literal
from app.models.findings import Finding
from app.models.critic import CriticVerdict


def route_finding(
    finding: Finding,
    verdict: CriticVerdict,
) -> Literal["auto", "queue", "digest"]:
    if verdict.final_confidence >= 0.95 and finding.severity == "high":
        return "auto"
    elif verdict.final_confidence >= 0.70:
        return "queue"
    else:
        return "digest"
