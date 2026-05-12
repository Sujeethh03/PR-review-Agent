import os
from app.agents.specialist.diff_utils import parse_diff_hunks


def extract_flagged_code(
    diff: str,
    file: str,
    line_start: int,
    line_end: int,
    repo_path: str,
) -> str:
    """
    Returns the source code at file:line_start–line_end.
    Tries the diff first (added lines that overlap the range).
    Falls back to reading directly from the cloned repo.
    """
    # Try diff first — covers the common case where the flagged lines are in the PR
    for hunk in parse_diff_hunks(diff):
        if hunk.file != file:
            continue
        if hunk.line_start <= line_end and hunk.line_end >= line_start:
            lines = hunk.added_code.splitlines()
            # Trim to the requested window within the hunk
            offset = max(0, line_start - hunk.line_start)
            length = (line_end - line_start) + 1
            return "\n".join(lines[offset: offset + length])

    # Fallback — read directly from cloned repo
    return read_lines_from_repo(repo_path, file, line_start, line_end)


def read_lines_from_repo(
    repo_path: str,
    file: str,
    line_start: int,
    line_end: int,
) -> str:
    """Reads exact lines from the cloned repo at /tmp/repos/..."""
    abs_path = os.path.join(repo_path, file)
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        # line_start/end are 1-indexed
        selected = all_lines[line_start - 1: line_end]
        return "".join(selected).rstrip()
    except OSError:
        return f"(could not read {file})"
