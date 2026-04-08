import os
from app.models.chunks import Chunk, ChunkType
from app.models.ingestion_config import IngestionConfig

# Map file extension → tree-sitter language module name
EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py":   "python",
    ".js":   "javascript",
    ".jsx":  "javascript",
    ".ts":   "typescript",
    ".tsx":  "typescript",
    ".java": "java",
    ".go":   "go",
    ".rs":   "rust",
    ".c":    "c",
    ".cpp":  "cpp",
    ".cc":   "cpp",
}

# tree-sitter node type → ChunkType
NODE_TYPE_MAP: dict[str, ChunkType] = {
    "function_definition":    "function",
    "function_declaration":   "function",
    "method_definition":      "method",
    "method_declaration":     "method",
    "class_definition":       "class",
    "class_declaration":      "class",
    "impl_item":              "class",   # Rust
}

# Cache parsed Language objects so we don't reload on every file
_language_cache: dict[str, object] = {}


def _get_ts_language(language: str):
    """Load and cache a tree-sitter Language object for the given language name."""
    if language in _language_cache:
        return _language_cache[language]

    try:
        from tree_sitter import Language
        import importlib
        mod = importlib.import_module(f"tree_sitter_{language}")
        lang = Language(mod.language())
        _language_cache[language] = lang
        return lang
    except Exception:
        _language_cache[language] = None
        return None


def detect_language(file_path: str) -> str | None:
    ext = os.path.splitext(file_path)[1].lower()
    return EXTENSION_LANGUAGE_MAP.get(ext)


def _get_symbol_name(node) -> str:
    for child in node.children:
        if child.type in ("identifier", "name"):
            return child.text.decode("utf-8")
    return ""


def parse_with_treesitter(
    source_code: str,
    language: str,
    file_rel_path: str,
) -> list[Chunk]:
    lang = _get_ts_language(language)
    if lang is None:
        return []

    try:
        from tree_sitter import Parser
        parser = Parser(lang)
    except Exception:
        return []

    tree = parser.parse(source_code.encode("utf-8"))
    chunks: list[Chunk] = []
    lines = source_code.splitlines()

    def visit(node):
        chunk_type = NODE_TYPE_MAP.get(node.type)
        if chunk_type:
            start_line = node.start_point[0] + 1  # 1-indexed
            end_line   = node.end_point[0] + 1
            text       = "\n".join(lines[start_line - 1 : end_line])
            symbol     = _get_symbol_name(node)
            chunks.append(Chunk(
                text=text,
                file=file_rel_path,
                start_line=start_line,
                end_line=end_line,
                language=language,
                chunk_type=chunk_type,
                symbol_name=symbol,
            ))
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return chunks


def parse_with_line_window(
    source_code: str,
    file_rel_path: str,
    language: str,
    window_size: int,
    overlap: int,
) -> list[Chunk]:
    lines = source_code.splitlines()
    if not lines:
        return []

    chunks: list[Chunk] = []
    step = window_size - overlap
    i = 0

    while i < len(lines):
        start_line = i + 1
        end_line   = min(i + window_size, len(lines))
        text       = "\n".join(lines[i : end_line])
        chunks.append(Chunk(
            text=text,
            file=file_rel_path,
            start_line=start_line,
            end_line=end_line,
            language=language,
            chunk_type="window",
            symbol_name="",
        ))
        i += step

    return chunks


def parse_file(
    file_abs_path: str,
    repo_path: str,
    config: IngestionConfig,
) -> list[Chunk]:
    file_rel_path = os.path.relpath(file_abs_path, repo_path)
    language = detect_language(file_abs_path) or "unknown"

    try:
        source_code = open(file_abs_path, "r", encoding="utf-8", errors="replace").read()
    except OSError:
        return []

    if language != "unknown":
        chunks = parse_with_treesitter(source_code, language, file_rel_path)
        if chunks:
            return chunks

    # Fallback: line-based windows
    return parse_with_line_window(
        source_code,
        file_rel_path,
        language,
        config.window_size_lines,
        config.window_overlap_lines,
    )
