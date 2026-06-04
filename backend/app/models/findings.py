from typing import Literal
from pydantic import BaseModel


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
        # First pass: deduplicate by exact (file, line_start, category)
        by_category: dict[tuple, Finding] = {}
        for f in self.bug.findings + self.security.findings + self.pattern.findings:
            key = (f.file, f.line_start, f.category)
            if key not in by_category or f.confidence > by_category[key].confidence:
                by_category[key] = f

        # Second pass: deduplicate by (file, line_start) — same line flagged by
        # multiple agents with different category names, keep highest confidence
        by_line: dict[tuple, Finding] = {}
        for f in by_category.values():
            key = (f.file, f.line_start)
            if key not in by_line or f.confidence > by_line[key].confidence:
                by_line[key] = f

        return list(by_line.values())
