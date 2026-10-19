"""Pure: string literals and comment-free text of Kotlin, Java and Gradle files (static-check-spec §5.1).

The project counterpart of `dex_strings.py`. A literal split by a template (`"home_${n}_native"`) gives its constant
parts, as the compiler's StringBuilder calls would in the DEX. Single-quoted literals are kept too: they are chars
in Kotlin and Java (too short to match a name) and strings in Groovy.
"""

# suffix → (block comments nest, "$" starts a template in double-quoted strings)
_RULES: dict[str, tuple[bool, bool]] = {
    ".kt": (True, True),
    ".kts": (True, True),
    ".java": (False, False),
    ".gradle": (False, True),
}
_ESCAPES = {"t": "\t", "b": "\b", "n": "\n", "r": "\r", "'": "'", '"': '"', "\\": "\\", "$": "$"}


class _Lexer:
    def __init__(self, text: str, suffix: str) -> None:
        self.text = text
        self.nested, self.templates = _RULES.get(suffix, (True, True))
        self.raw_escapes = (
            suffix == ".java"
        )  # Java text blocks process escapes (\""" is a quote); Kotlin raw strings do not
        self.literals: list[str] = []
        self.comments: list[tuple[int, int]] = []

    def code(self, i: int, template: bool) -> int:
        """Scan code from `i`; inside a `${…}` template, stop after its closing brace."""
        text, depth = self.text, 0
        while i < len(text):
            char = text[i]
            if text.startswith("//", i):
                end = text.find("\n", i)
                end = len(text) if end < 0 else end
                self.comments.append((i, end))
                i = end
            elif text.startswith("/*", i):
                end = self.block_comment(i + 2)
                self.comments.append((i, end))
                i = end
            elif text.startswith('"""', i):
                i = self.raw(i + 3)
            elif char in "\"'":
                i = self.quoted(i + 1, char)
            elif char == "{":
                depth += 1
                i += 1
            elif char == "}":
                if template and depth == 0:
                    return i + 1
                depth -= 1
                i += 1
            else:
                i += 1
        return i

    def block_comment(self, i: int) -> int:
        text, depth = self.text, 1
        while i < len(text) and depth:
            if self.nested and text.startswith("/*", i):
                depth += 1
                i += 2
            elif text.startswith("*/", i):
                depth -= 1
                i += 2
            else:
                i += 1
        return i

    def is_template(self, i: int) -> bool:
        """A "$" at `i` starts `${…}` or `$name`; otherwise it is a plain character."""
        text = self.text
        return self.templates and (
            text.startswith("${", i) or text[i + 1 : i + 2].isalpha() or text[i + 1 : i + 2] == "_"
        )

    def template(self, parts: list[str], i: int) -> int:
        """Emit the literal part before the template, then skip the template; returns the index after it."""
        self.emit(parts)
        parts.clear()
        text = self.text
        if text.startswith("${", i):
            return self.code(i + 2, template=True)
        i += 1
        while i < len(text) and (text[i].isalnum() or text[i] == "_"):
            i += 1
        return i

    def quoted(self, i: int, quote: str) -> int:
        """A single-line literal; an unterminated one ends at the line break."""
        text, parts = self.text, []
        while i < len(text) and text[i] != "\n":
            char = text[i]
            if char == quote:
                i += 1
                break
            if char == "\\" and i + 1 < len(text):
                value, i = self.escape(i + 1)
                parts.append(value)
                continue
            if char == "$" and quote == '"' and self.is_template(i):
                i = self.template(parts, i)
                continue
            parts.append(char)
            i += 1
        self.emit(parts)
        return i

    def raw(self, i: int) -> int:
        """Kotlin raw string or Java text block; quotes beyond the closing three belong to the content."""
        text, parts = self.text, []
        while i < len(text):
            if text.startswith('"""', i):
                end = i + 3
                while end < len(text) and text[end] == '"':
                    end += 1
                parts.append('"' * (end - i - 3))
                i = end
                break
            if text[i] == "$" and self.is_template(i):
                i = self.template(parts, i)
                continue
            if text[i] == "\\" and self.raw_escapes and i + 1 < len(text):
                value, i = self.escape(i + 1)
                parts.append(value)
                continue
            parts.append(text[i])
            i += 1
        self.emit(parts)
        return i

    def escape(self, i: int) -> tuple[str, int]:
        text = self.text
        digits = text[i + 1 : i + 5]
        if text[i] == "u" and len(digits) == 4 and all(c in "0123456789abcdefABCDEF" for c in digits):
            return chr(int(digits, 16)), i + 5
        return _ESCAPES.get(text[i], text[i]), i + 1

    def emit(self, parts: list[str]) -> None:
        if parts:
            self.literals.append("".join(parts))


def _lex(text: str, suffix: str) -> _Lexer:
    lexer = _Lexer(text, suffix)
    lexer.code(0, template=False)
    return lexer


def literals(text: str, suffix: str) -> list[str]:
    """Every string literal (or constant part of one) outside comments, unescaped."""
    return _lex(text, suffix).literals


def strip_comments(text: str, suffix: str) -> str:
    """`text` with each comment replaced by a space and its line breaks; strings are kept, so "https://…" survives."""
    pieces, start = [], 0
    for begin, end in _lex(text, suffix).comments:
        pieces += [text[start:begin], " " + "\n" * text.count("\n", begin, end)]
        start = end
    pieces.append(text[start:])
    return "".join(pieces)
