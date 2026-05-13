import hashlib
from typing import Literal
from pydantic import BaseModel


def finding_hash(finding: "Finding") -> str:
    key = f"{finding.file}:{finding.line_start}:{finding.category}"
    return hashlib.sha256(key.encode()).hexdigest()


class Finding(BaseModel):
    file: str
    line_start: int
    line_end: int
    severity: Literal["high", "medium", "low"]
    category: str
    title: str
    description: str
    suggestion: str
    confidence: float                              # 0.0 – 1.0
    agent: Literal["bug", "security", "pattern"]


class AgentOutput(BaseModel):
    agent: Literal["bug", "security", "pattern"]
    findings: list[Finding]
    error: str | None = None


class SpecialistResult(BaseModel):
    bug: AgentOutput
    security: AgentOutput
    pattern: AgentOutput

    def all_findings(self) -> list[Finding]:
        seen: dict[tuple, Finding] = {}
        for f in self.bug.findings + self.security.findings + self.pattern.findings:
            key = (f.file, f.line_start, f.category)
            if key not in seen or f.confidence > seen[key].confidence:
                seen[key] = f
        return list(seen.values())
