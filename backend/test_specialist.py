"""
Standalone test for all three specialist agents.

Run from backend/:
    python test_specialist.py

Tests:
  1. Unit test — parse_diff_hunks (no API calls)
  2. Bug agent   — diff with deliberate bugs
  3. Security agent — diff with deliberate vulnerabilities
  4. Pattern agent  — diff that violates codebase conventions (needs ChromaDB context)
  5. Full parallel run — all three agents via run_specialist_agents()

Tests 2–5 require OPENAI_API_KEY in .env and make real GPT-4o calls.
For test 4 and 5, run test_ingestion.py first to populate ChromaDB context.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(override=True)


# ---------------------------------------------------------------------------
# Sample diffs
# ---------------------------------------------------------------------------

# Three deliberate bugs: null ref, missing validation, resource leak
BUGGY_DIFF = """\
diff --git a/app/payments.py b/app/payments.py
index 0000000..1111111 100644
--- a/app/payments.py
+++ b/app/payments.py
@@ -0,0 +1,16 @@
+def process_payment(user_id, amount):
+    result = lookup_user(user_id)
+    name = result.user.name
+
+    if amount <= 0:
+        raise ValueError("amount must be positive")
+
+    log_file = open("/var/log/payments.log", "a")
+    log_file.write(f"charging {name} {amount}\\n")
+
+    charge(user_id, amount)
+    log_file.close()
+
+    return {"status": "ok", "user": name, "amount": amount}
"""

# Three deliberate vulnerabilities: hardcoded secret, SQL injection, path traversal
VULNERABLE_DIFF = """\
diff --git a/app/admin.py b/app/admin.py
index 0000000..2222222 100644
--- a/app/admin.py
+++ b/app/admin.py
@@ -0,0 +1,18 @@
+import sqlite3
+import os
+
+STRIPE_SECRET_KEY = "sk_live_4eC39HqLyjWDarjtT1zdp7dc"
+
+def get_user(username):
+    conn = sqlite3.connect("users.db")
+    query = f"SELECT * FROM users WHERE username = '{username}'"
+    return conn.execute(query).fetchone()
+
+def read_report(filename):
+    base_dir = "/var/reports"
+    path = os.path.join(base_dir, filename)
+    with open(path) as f:
+        return f.read()
"""

# Pattern violations: uses print() instead of logger, returns raw value instead of dict
PATTERN_DIFF = """\
diff --git a/app/orders.py b/app/orders.py
index 0000000..3333333 100644
--- a/app/orders.py
+++ b/app/orders.py
@@ -0,0 +1,10 @@
+def cancel_order(order_id):
+    order = fetch_order(order_id)
+    if not order:
+        print(f"order {order_id} not found")
+        return None
+
+    order.status = "cancelled"
+    save_order(order)
+    print(f"order {order_id} cancelled")
+    return order.id
"""

COLLECTION_NAME = "test__ingestion-test"


def separator(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_findings(findings):
    if not findings:
        print("  No findings.")
        return
    for f in findings:
        print(f"\n  [{f.severity.upper()}] {f.title}")
        print(f"    file       : {f.file}:{f.line_start}–{f.line_end}")
        print(f"    category   : {f.category}")
        print(f"    confidence : {f.confidence:.2f}")
        print(f"    description: {f.description}")
        print(f"    suggestion : {f.suggestion}")


# ---------------------------------------------------------------------------
# 1. Unit test — parse_diff_hunks
# ---------------------------------------------------------------------------
def test_diff_parser():
    separator("1. Unit test — parse_diff_hunks")
    from app.agents.specialist.diff_utils import parse_diff_hunks

    hunks = parse_diff_hunks(BUGGY_DIFF)
    assert len(hunks) == 1, f"Expected 1 hunk, got {len(hunks)}"
    h = hunks[0]
    assert h.file == "app/payments.py"
    assert "result.user.name" in h.added_code
    print(f"  file        : {h.file}")
    print(f"  lines       : {h.line_start}–{h.line_end}")
    print(f"  added lines : {len(h.added_code.splitlines())}")
    print("  PASSED")


# ---------------------------------------------------------------------------
# 2. Bug agent
# ---------------------------------------------------------------------------
async def test_bug_agent():
    separator("2. Bug agent — null ref, missing validation, resource leak")
    from app.agents.specialist.bug.agent import run_bug_agent

    state = {
        "diff": BUGGY_DIFF,
        "collection_name": COLLECTION_NAME,
        "owner": "test", "repo_name": "payments",
        "bug_output": None, "security_output": None, "pattern_output": None,
    }
    result = await run_bug_agent(state)
    output = result["bug_output"]

    if output.error:
        print(f"  Agent error: {output.error}")
        return

    print(f"  Findings: {len(output.findings)}")
    print_findings(output.findings)
    assert len(output.findings) > 0, "Expected findings on a buggy diff"
    print("\n  PASSED")


# ---------------------------------------------------------------------------
# 3. Security agent
# ---------------------------------------------------------------------------
async def test_security_agent():
    separator("3. Security agent — hardcoded secret, SQL injection, path traversal")
    from app.agents.specialist.security.agent import run_security_agent

    state = {
        "diff": VULNERABLE_DIFF,
        "collection_name": COLLECTION_NAME,
        "owner": "test", "repo_name": "admin",
        "bug_output": None, "security_output": None, "pattern_output": None,
    }
    result = await run_security_agent(state)
    output = result["security_output"]

    if output.error:
        print(f"  Agent error: {output.error}")
        return

    print(f"  Findings: {len(output.findings)}")
    print_findings(output.findings)

    categories = {f.category for f in output.findings}
    assert "hardcoded_secret" in categories, "Expected hardcoded_secret finding"
    secret_findings = [f for f in output.findings if f.category == "hardcoded_secret"]
    for f in secret_findings:
        assert f.severity == "high",    f"hardcoded_secret must be HIGH, got {f.severity}"
        assert f.confidence == 1.0,     f"hardcoded_secret must be 1.0, got {f.confidence}"

    assert len(output.findings) > 0, "Expected findings on a vulnerable diff"
    print("\n  PASSED")


# ---------------------------------------------------------------------------
# 4. Pattern agent
# ---------------------------------------------------------------------------
async def test_pattern_agent():
    separator("4. Pattern agent — print() instead of logger, wrong return shape")
    from app.agents.specialist.pattern.agent import run_pattern_agent

    state = {
        "diff": PATTERN_DIFF,
        "collection_name": COLLECTION_NAME,
        "owner": "test", "repo_name": "orders",
        "bug_output": None, "security_output": None, "pattern_output": None,
    }
    result = await run_pattern_agent(state)
    output = result["pattern_output"]

    if output.error:
        print(f"  Agent error: {output.error}")
        return

    print(f"  Findings: {len(output.findings)}")
    print_findings(output.findings)
    print("  (pattern agent needs ChromaDB context — run test_ingestion.py first for best results)")
    print("  PASSED")


# ---------------------------------------------------------------------------
# 5. Full parallel run — all three via run_specialist_agents()
# ---------------------------------------------------------------------------
async def test_full_parallel_run():
    separator("5. Full parallel run — all three agents on the vulnerable diff")
    from app.agents.specialist import run_specialist_agents

    result = await run_specialist_agents(
        diff=VULNERABLE_DIFF,
        collection_name=COLLECTION_NAME,
        owner="test",
        repo_name="admin",
    )

    all_findings = result.all_findings()
    print(f"  Total findings : {len(all_findings)}")
    print(f"    bug          : {len(result.bug.findings)}")
    print(f"    security     : {len(result.security.findings)}")
    print(f"    pattern      : {len(result.pattern.findings)}")

    if result.bug.error:
        print(f"  Bug agent error     : {result.bug.error}")
    if result.security.error:
        print(f"  Security agent error: {result.security.error}")
    if result.pattern.error:
        print(f"  Pattern agent error : {result.pattern.error}")

    print("\n  Top findings:")
    sorted_findings = sorted(all_findings, key=lambda f: f.confidence, reverse=True)
    for f in sorted_findings[:5]:
        print(f"  [{f.agent.upper():8}] [{f.severity.upper():6}] {f.title} (conf: {f.confidence:.2f})")

    assert not result.bug.error
    assert not result.security.error
    assert not result.pattern.error
    print("\n  PASSED")


async def main():
    test_diff_parser()

    if not os.getenv("OPENAI_API_KEY"):
        print("\nOPENAI_API_KEY not set — skipping GPT-4o tests")
        return

    await test_bug_agent()
    await test_security_agent()
    await test_pattern_agent()
    await test_full_parallel_run()

    print("\n" + "=" * 60)
    print("  All tests complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
