import hashlib
from pydantic import BaseModel
from app.models.findings import Finding


def finding_hash(finding: Finding) -> str:
    """Stable content-based ID — mirrors _chunk_id() in store.py."""
    key = f"{finding.file}:{finding.line_start}:{finding.category}"
    return hashlib.sha256(key.encode()).hexdigest()


class CriticVerdict(BaseModel):
    finding_hash: str         # SHA256(file:line_start:category) — matches FindingRow.finding_hash
    accepted: bool
    final_confidence: float   # critic's reassessed score, replaces specialist confidence
    reasoning: str            # one sentence explaining the verdict
    context_used: list[str]   # symbol_names from ChromaDB that informed the decision


class CriticOutput(BaseModel):
    accepted: list[Finding]         # survived critic — confidence updated to final_confidence
    rejected: list[Finding]         # dropped by critic
    verdicts: list[CriticVerdict]   # full decision record for every finding (accepted + rejected)
