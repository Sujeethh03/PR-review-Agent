from app.models.findings import Finding

_OWASP: dict[str, dict[str, str]] = {
    "command_injection": {
        "ref":    "A03:2021 — Injection",
        "url":    "https://owasp.org/Top10/A03_2021-Injection/",
        "impact": "Unvalidated input passed to system commands lets an attacker execute arbitrary OS commands — full system compromise, data exfiltration, or service disruption.",
    },
    "sql_injection": {
        "ref":    "A03:2021 — Injection",
        "url":    "https://owasp.org/Top10/A03_2021-Injection/",
        "impact": "SQL injection allows attackers to read, modify, or delete database records, bypass authentication, and in some configurations execute OS-level commands.",
    },
    "xss": {
        "ref":    "A03:2021 — Injection",
        "url":    "https://owasp.org/Top10/A03_2021-Injection/",
        "impact": "Cross-site scripting lets attackers inject malicious scripts into pages viewed by other users, enabling session hijacking, credential theft, and malware distribution.",
    },
    "path_traversal": {
        "ref":    "A01:2021 — Broken Access Control",
        "url":    "https://owasp.org/Top10/A01_2021-Broken_Access_Control/",
        "impact": "Path traversal lets attackers read files outside the intended directory — exposing config files, credentials, and private data.",
    },
    "hardcoded_secret": {
        "ref":    "A02:2021 — Cryptographic Failures",
        "url":    "https://owasp.org/Top10/A02_2021-Cryptographic_Failures/",
        "impact": "Secrets in source code are permanently exposed to anyone with repo access, including in git history after deletion. Rotate the secret immediately.",
    },
    "hardcoded_api_key": {
        "ref":    "A02:2021 — Cryptographic Failures",
        "url":    "https://owasp.org/Top10/A02_2021-Cryptographic_Failures/",
        "impact": "API keys in source code are permanently exposed. Attackers with repo access can abuse them to run up costs, access third-party data, or pivot to other services.",
    },
    "sensitive_data_exposure": {
        "ref":    "A02:2021 — Cryptographic Failures",
        "url":    "https://owasp.org/Top10/A02_2021-Cryptographic_Failures/",
        "impact": "Exposing sensitive data — even in logs or error messages — can leak PII, credentials, or business data to anyone with log access.",
    },
    "logging_sensitive_data": {
        "ref":    "A09:2021 — Security Logging and Monitoring Failures",
        "url":    "https://owasp.org/Top10/A09_2021-Security_Logging_and_Monitoring_Failures/",
        "impact": "Logging sensitive values (tokens, passwords, PII) exposes them to anyone who can read logs — often a much wider audience than intended.",
    },
    "insecure_deserialization": {
        "ref":    "A08:2021 — Software and Data Integrity Failures",
        "url":    "https://owasp.org/Top10/A08_2021-Software_and_Data_Integrity_Failures/",
        "impact": "Deserializing untrusted data can allow remote code execution, denial of service, or privilege escalation depending on the library and payload.",
    },
    "broken_access_control": {
        "ref":    "A01:2021 — Broken Access Control",
        "url":    "https://owasp.org/Top10/A01_2021-Broken_Access_Control/",
        "impact": "Missing access checks let users perform actions or access data beyond their permissions — the most common cause of data breaches.",
    },
    "missing_authentication": {
        "ref":    "A07:2021 — Identification and Authentication Failures",
        "url":    "https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/",
        "impact": "Unauthenticated endpoints expose sensitive operations to any caller, allowing unauthorized data access or modification.",
    },
    "insecure_random": {
        "ref":    "A02:2021 — Cryptographic Failures",
        "url":    "https://owasp.org/Top10/A02_2021-Cryptographic_Failures/",
        "impact": "Predictable random values in security-sensitive contexts (tokens, session IDs, nonces) allow attackers to guess or brute-force them.",
    },
    "open_redirect": {
        "ref":    "A01:2021 — Broken Access Control",
        "url":    "https://owasp.org/Top10/A01_2021-Broken_Access_Control/",
        "impact": "Open redirects are used in phishing attacks to make malicious URLs appear legitimate by using your trusted domain as a relay.",
    },
    "xxe": {
        "ref":    "A05:2021 — Security Misconfiguration",
        "url":    "https://owasp.org/Top10/A05_2021-Security_Misconfiguration/",
        "impact": "XML External Entity injection can expose internal files, perform server-side request forgery, or cause denial of service.",
    },
    "missing_validation": {
        "ref":    "A03:2021 — Injection",
        "url":    "https://owasp.org/Top10/A03_2021-Injection/",
        "impact": "Unvalidated input is the root cause of injection attacks. Always validate and sanitize data at the boundary where it enters your system.",
    },
}

_SEVERITY_FALLBACK: dict[str, str] = {
    "high":   "This issue can directly lead to security breaches, data loss, or system compromise if left unaddressed.",
    "medium": "This issue may be exploitable under certain conditions and should be addressed before it can be escalated by an attacker.",
    "low":    "This is a code quality or minor security concern. Addressing it keeps the codebase maintainable and reduces future risk.",
}


def get_educational_context(finding: Finding) -> str:
    entry = _OWASP.get(finding.category)
    if entry:
        return (
            f"### Why this matters\n"
            f"{entry['impact']}\n\n"
            f"📚 **Reference:** [{entry['ref']}]({entry['url']})"
        )
    fallback = _SEVERITY_FALLBACK.get(finding.severity, "")
    return f"### Why this matters\n{fallback}" if fallback else ""
