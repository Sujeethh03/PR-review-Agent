from dataclasses import dataclass


@dataclass
class DiffHunk:
    file: str
    line_start: int       # first added/modified line (1-indexed)
    line_end: int         # last added/modified line
    added_code: str       # only the + lines (new code)
    full_context: str     # full hunk including context lines


def parse_diff_hunks(diff: str) -> list[DiffHunk]:
    hunks: list[DiffHunk] = []
    current_file: str | None = None
    in_hunk = False
    hunk_new_start = 0
    hunk_lines: list[str] = []
    added_lines: list[str] = []
    current_new_line = 0

    def flush_hunk():
        if current_file and added_lines:
            end_line = max(hunk_new_start, current_new_line - 1)
            hunks.append(DiffHunk(
                file=current_file,
                line_start=hunk_new_start,
                line_end=end_line,
                added_code="\n".join(added_lines),
                full_context="\n".join(hunk_lines),
            ))

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            flush_hunk()
            in_hunk = False
            hunk_lines = []
            added_lines = []
            continue

        if line.startswith("+++ "):
            raw = line[4:].strip()
            if raw == "/dev/null":
                current_file = None
            elif raw.startswith("b/"):
                current_file = raw[2:]
            else:
                current_file = raw
            in_hunk = False
            continue

        if line.startswith("--- "):
            continue

        if line.startswith("@@ "):
            flush_hunk()
            hunk_lines = [line]
            added_lines = []
            # parse @@ -old_start,old_count +new_start,new_count @@
            try:
                new_part = line.split("+")[1].split("@@")[0].strip()
                hunk_new_start = int(new_part.split(",")[0])
            except (IndexError, ValueError):
                hunk_new_start = 0
            current_new_line = hunk_new_start
            in_hunk = True
            continue

        if not in_hunk or current_file is None:
            continue

        hunk_lines.append(line)

        if line.startswith("+"):
            added_lines.append(line[1:])
            current_new_line += 1
        elif line.startswith("-"):
            pass  # deleted lines don't advance the new-file counter
        else:
            current_new_line += 1  # context line

    flush_hunk()
    return hunks
