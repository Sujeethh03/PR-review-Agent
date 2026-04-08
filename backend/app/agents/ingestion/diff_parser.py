import re


def parse_diff_file_paths(diff: str) -> tuple[list[str], list[str]]:
    """
    Returns (modified_or_added_paths, deleted_paths).
    Parses unified diff headers:
      --- a/path  or  --- /dev/null  (deletion)
      +++ b/path  or  +++ /dev/null  (addition)
    """
    modified: list[str] = []
    deleted: list[str] = []

    # Collect all (before, after) path pairs from diff headers
    before_path: str | None = None

    for line in diff.splitlines():
        if line.startswith("--- "):
            raw = line[4:].strip()
            if raw == "/dev/null":
                before_path = None
            elif raw.startswith("a/"):
                before_path = raw[2:]
            else:
                before_path = raw

        elif line.startswith("+++ "):
            raw = line[4:].strip()
            if raw == "/dev/null":
                # File was deleted
                if before_path:
                    deleted.append(before_path)
            elif raw.startswith("b/"):
                after_path = raw[2:]
                modified.append(after_path)
            else:
                modified.append(raw)

            before_path = None

    return modified, deleted
