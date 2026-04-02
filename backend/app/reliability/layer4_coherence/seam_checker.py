"""
Layer 4 — Seam checker.

Detects truncated file output from context-window chunking:
  - Unclosed braces / brackets / parentheses
  - Incomplete function definitions
  - Missing closing JSX tags
  - Truncation markers (// ..., /* ..., etc.)
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


class SeamReport(BaseModel):
    """Result of checking a single file for seam/truncation errors."""

    file_path: str
    valid: bool
    issues: list[str] = Field(default_factory=list)


# ── Truncation markers ───────────────────────────────────────────────

_TRUNCATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"//\s*\.\.\.\s*$", re.MULTILINE),
    re.compile(r"/\*\s*\.\.\.\s*\*/\s*$", re.MULTILINE),
    re.compile(r"//\s*rest of (?:code|file|implementation)", re.IGNORECASE),
    re.compile(r"//\s*TODO:?\s*(?:implement|add|complete)", re.IGNORECASE),
    re.compile(r"//\s*\.\.\.\s*(?:more|etc|and so on)", re.IGNORECASE),
    re.compile(r"//\s*truncated", re.IGNORECASE),
    re.compile(r"//\s*continued", re.IGNORECASE),
]


def check_seam(file_path: str, content: str) -> SeamReport:
    """Check a file for seam/truncation errors.

    Args:
        file_path: The file path (for reporting).
        content: The file content to check.

    Returns:
        SeamReport with validity status and list of issues.
    """
    issues: list[str] = []

    if not content or not content.strip():
        return SeamReport(
            file_path=file_path,
            valid=False,
            issues=["file is empty"],
        )

    # 1. Check brace balance
    open_braces = content.count("{")
    close_braces = content.count("}")
    if open_braces != close_braces:
        diff = open_braces - close_braces
        if diff > 0:
            issues.append(
                f"unclosed braces: {diff} opening '{{' without matching '}}'"
            )
        else:
            issues.append(
                f"extra closing braces: {-diff} '}}' without matching '{{'"
            )

    # 2. Check bracket balance
    open_brackets = content.count("[")
    close_brackets = content.count("]")
    if open_brackets != close_brackets:
        diff = open_brackets - close_brackets
        if diff > 0:
            issues.append(
                f"unclosed brackets: {diff} opening '[' without matching ']'"
            )
        else:
            issues.append(
                f"extra closing brackets: {-diff} ']' without matching '['"
            )

    # 3. Check parenthesis balance
    open_parens = content.count("(")
    close_parens = content.count(")")
    if open_parens != close_parens:
        diff = open_parens - close_parens
        if diff > 0:
            issues.append(
                f"unclosed parentheses: {diff} opening '(' without matching ')'"
            )
        else:
            issues.append(
                f"extra closing parentheses: {-diff} ')' without matching '('"
            )

    # 4. Check for truncation markers
    for pattern in _TRUNCATION_PATTERNS:
        matches = pattern.findall(content)
        if matches:
            issues.append(
                f"truncation marker detected: '{matches[0].strip()}'"
            )

    # 5. Check for incomplete JSX (unmatched opening tags)
    if file_path.endswith((".tsx", ".jsx")):
        _check_jsx_completeness(content, issues)

    # 6. Check file ends abruptly (no newline, ends mid-statement)
    stripped = content.rstrip()
    if stripped:
        last_char = stripped[-1]
        # Files should end with }, ), ;, `, or a closing tag
        valid_endings = ("}", ")", ";", "`", ">", '"', "'", "/", "]")
        if last_char not in valid_endings and not stripped.endswith("*/"):
            # Check if the last line looks incomplete
            last_line = stripped.split("\n")[-1].strip()
            # Allow comments and blank lines
            if (
                not last_line.startswith("//")
                and not last_line.startswith("*")
                and last_line != ""
            ):
                issues.append(
                    f"file ends abruptly with '{last_char}' — "
                    f"last line: '{last_line[:60]}'"
                )

    valid = len(issues) == 0

    if not valid:
        logger.warning(
            "seam_checker.issues_found",
            file_path=file_path,
            issue_count=len(issues),
        )

    return SeamReport(
        file_path=file_path,
        valid=valid,
        issues=issues,
    )


def _check_jsx_completeness(content: str, issues: list[str]) -> None:
    """Check for unmatched JSX opening tags.

    Strips TypeScript generics before scanning so that
    ``React.forwardRef<HTMLButtonElement, Props>`` is not mistaken
    for a JSX ``<HTMLButtonElement>`` tag.
    """
    # Known HTML element type names that appear in TS generics, not JSX
    _TS_TYPE_NAMES: set[str] = {
        "HTMLButtonElement", "HTMLInputElement", "HTMLSelectElement",
        "HTMLTextAreaElement", "HTMLDivElement", "HTMLFormElement",
        "HTMLAnchorElement", "HTMLSpanElement", "HTMLImageElement",
        "HTMLElement", "SVGSVGElement", "SVGElement",
        "Record", "Partial", "Required", "Readonly", "Pick", "Omit",
        "Promise", "Array", "Map", "Set", "WeakMap", "WeakSet",
        "ErrorBoundaryState", "ErrorBoundaryProps",
    }

    # ── Pre-process: remove lines that are pure type annotations ─
    # Also strip TS generic patterns from remaining lines
    cleaned_lines: list[str] = []
    for line in content.split("\n"):
        stripped_line = line.strip()
        # Skip type/interface/import declarations entirely
        if stripped_line.startswith(("interface ", "type ", "import ")):
            continue
        # Skip lines that are part of generic declarations
        if "extends React.Component<" in line:
            continue
        # Strip common generic constructs from function signatures
        if "forwardRef<" in line:
            line = re.sub(r"forwardRef<[^(]+>\(", "forwardRef(", line)
        if "createContext<" in line:
            line = re.sub(r"createContext<[^(]+>\(", "createContext(", line)
        if "useState<" in line:
            line = re.sub(r"useState<[^(]+>\(", "useState(", line)
        # Strip return type generics:  ): Promise<User> {
        #   Also handles standalone: function foo(): Promise<X> {
        line = re.sub(r":\s*Promise<[^>]+>", ": Promise", line)
        line = re.sub(r":\s*Omit<[^>]+>", ": Omit", line)
        # Strip any remaining generic pattern:  Identifier<...> following
        # a colon (type annotation context)
        line = re.sub(r":\s*(\w+)<[^>]+>", r": \1", line)
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)

    # ── Extract JSX tags using a brace-aware scanner ─────────────
    # The simple regex `<Tag [^>]*>` breaks when JSX attributes
    # contain `>` inside expression blocks, e.g. `onClose={() => {}}`.
    # This scanner properly skips over `{...}` blocks in attributes.
    def _extract_jsx_tags(text: str) -> tuple[
        list[str], list[str], list[str]
    ]:
        """Return (opening_tags, closing_tags, self_closing_tags)."""
        opening: list[str] = []
        closing: list[str] = []
        self_close: list[str] = []

        i = 0
        n = len(text)
        while i < n:
            if text[i] == "<":
                # Check for closing tag:  </Tag> or </Tag.Sub>
                if i + 1 < n and text[i + 1] == "/":
                    m = re.match(r"</([A-Z][\w.]+)>", text[i:])
                    if m:
                        closing.append(m.group(1))
                        i += m.end()
                        continue
                # Check for opening/self-closing tag: <Tag ...> or <Tag.Sub .../>
                m = re.match(r"<([A-Z][\w.]+)", text[i:])
                if m:
                    tag_name = m.group(1)
                    j = i + m.end()
                    # Scan forward for > or />, skipping {…} blocks
                    brace_depth = 0
                    found_end = False
                    is_self_closing = False
                    while j < n:
                        ch = text[j]
                        if ch == "{":
                            brace_depth += 1
                        elif ch == "}":
                            brace_depth = max(0, brace_depth - 1)
                        elif brace_depth == 0:
                            if ch == "/" and j + 1 < n and text[j + 1] == ">":
                                is_self_closing = True
                                j += 2
                                found_end = True
                                break
                            elif ch == ">":
                                j += 1
                                found_end = True
                                break
                        j += 1
                    if found_end:
                        if is_self_closing:
                            self_close.append(tag_name)
                        else:
                            opening.append(tag_name)
                    i = j
                    continue
            i += 1

        return opening, closing, self_close

    opening_tags, closing_tags, self_closing = _extract_jsx_tags(cleaned)

    # Remove self-closing from opening count
    open_set: dict[str, int] = {}
    for tag in opening_tags:
        if tag in _TS_TYPE_NAMES:
            continue
        open_set[tag] = open_set.get(tag, 0) + 1
    for tag in self_closing:
        if tag in _TS_TYPE_NAMES:
            continue
        open_set[tag] = open_set.get(tag, 0) - 1

    close_set: dict[str, int] = {}
    for tag in closing_tags:
        if tag in _TS_TYPE_NAMES:
            continue
        close_set[tag] = close_set.get(tag, 0) + 1

    for tag, count in open_set.items():
        close_count = close_set.get(tag, 0)
        if count > close_count:
            issues.append(
                f"unclosed JSX tag: <{tag}> opened {count} times "
                f"but closed {close_count} times"
            )

