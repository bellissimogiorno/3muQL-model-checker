"""The small, dependency-free Unicode and ASCII syntax for literate theories.

Parsing is deliberately independent of a model or solver.  A :class:`Node` is
an immutable syntax tree; name resolution and macro expansion happen when a
theory is loaded.  Offsets in :class:`FormulaError` refer to the original input.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class Node:
    """A formula or value term in the public abstract syntax tree."""

    op: str
    args: tuple["Node", ...] = ()
    value: str | None = None

    def __str__(self) -> str:
        return format_formula(self)


class FormulaError(ValueError):
    """A syntax error, including its zero-based character offset."""

    def __init__(self, message: str, text: str, offset: int = 0):
        self.message = message
        self.offset = offset
        self.line = text.count("\n", 0, offset) + 1
        self.column = offset - text.rfind("\n", 0, offset)
        super().__init__(f"line {self.line}, column {self.column}: {message}")


# Canonical AST operations are deliberately stable: the evaluator, compiler and
# stored model fingerprints use these names.  In particular, the internal
# 'somewhere'/'everywhere' operations quantify over quorums as well as points.
UNARY = frozenset({
    "T", "F", "B", "TB", "TF", "FB",
    "diamond", "box", "somewhere", "everywhere", "existsQ", "forallQ",
    "quorum", "contra", "yesterday", "tomorrow", "once", "historically",
    "past", "sometime", "forever", "infinitely", "ultimately",
})
# Source spellings are independent of internal operations.  The plain-English
# 'somewhere'/'everywhere' spellings now denote the point-only modalities.
_NAMED_UNARY = {name: name for name in UNARY}
_NAMED_UNARY.update({
    "somewhere": "diamond", "everywhere": "box",
    "someQuorumSomePoint": "somewhere",
    "everyQuorumEveryPoint": "everywhere",
    "someQuorumEveryPoint": "quorum",
    "everyQuorumSomePoint": "contra",
})
BINDERS = frozenset({"forall", "exists", "affine", "unique", "mu", "nu"})
RESERVED = frozenset(_NAMED_UNARY) | BINDERS | frozenset({
    "t", "b", "f", "not", "and", "or", "xor", "latest", "twined",
    "theory", "points", "values", "stages", "time", "quorums",
    "predicate", "axiom", "property", "let",
})


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str
    offset: int


_TOKEN = re.compile(
    r"(?P<space>\s+)|(?P<comment>\#[^\n]*|//[^\n]*)"
    r"|(?P<string>\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*')"
    r"|(?P<symbol>[∃∀][Qꟴ][□◇⋄]?|∃⁰¹|∃¹|∃01|∃1|∃!|[¬∧∨⊕→⇀≡≤≠∀∃μµν□◇⋄])"
    r"|(?P<op><=>|-\\|->|<=|==|!=|&&|\|\||[!&|^().,=;])"
    r"|(?P<integer>[0-9]+)|(?P<name>[A-Za-z_][A-Za-z_0-9]*)"
)
_INFIX = {
    "<=>": (10, "equiv", False),
    "<=": (15, "order", False),
    "->": (20, "weak", True),
    "-\\": (20, "strong", True),
    "|": (30, "or", False), "||": (30, "or", False), "or": (30, "or", False),
    "^": (35, "xor", False), "xor": (35, "xor", False),
    "&": (40, "and", False), "&&": (40, "and", False), "and": (40, "and", False),
}

# Normalise operators only after lexing.  Literal values and comments therefore
# retain their exact contents, and offsets always refer to the original source.
_SYMBOL_ALIASES = {
    "¬": "!", "∧": "&", "∨": "|", "⊕": "xor", "→": "->",
    "⇀": "-\\", "≡": "<=>", "≤": "<=", "≠": "!=",
    "∀": "forall", "∃": "exists", "∃¹": "unique", "∃1": "unique",
    "∃!": "unique", "∃⁰¹": "affine", "∃01": "affine",
    "μ": "mu", "µ": "mu", "ν": "nu",
    "□": "box", "◇": "diamond", "⋄": "diamond",
    "∃Q": "existsQ", "∀Q": "forallQ", "∃Q□": "quorum",
    "∀Q◇": "contra", "∀Q⋄": "contra", "∃Q◇": "somewhere",
    "∃Q⋄": "somewhere", "∀Q□": "everywhere",
    "∃ꟴ": "existsQ", "∀ꟴ": "forallQ", "∃ꟴ□": "quorum",
    "∀ꟴ◇": "contra", "∀ꟴ⋄": "contra", "∃ꟴ◇": "somewhere",
    "∃ꟴ⋄": "somewhere", "∀ꟴ□": "everywhere",
}

# U+A7F4 is MODIFIER LETTER CAPITAL Q: an actual superscript in plain text.
# Ordinary Q remains accepted for keyboards and fonts without this character.
_UNICODE_UNARY = {
    "box": "□", "diamond": "◇", "existsQ": "∃ꟴ", "forallQ": "∀ꟴ",
    "quorum": "∃ꟴ□", "contra": "∀ꟴ◇", "somewhere": "∃ꟴ◇",
    "everywhere": "∀ꟴ□",
}
_ASCII_UNARY = {
    "somewhere": "someQuorumSomePoint",
    "everywhere": "everyQuorumEveryPoint",
}
_UNICODE_BINDERS = {
    "forall": "∀", "exists": "∃", "unique": "∃¹", "affine": "∃⁰¹",
    "mu": "μ", "nu": "ν",
}
_ASCII_BINARY = {
    "and": "&", "or": "|", "xor": "xor", "weak": "->", "strong": "-\\",
    "equiv": "<=>", "order": "<=", "eq": "==", "neq": "!=",
}
_UNICODE_BINARY = {
    "and": "∧", "or": "∨", "xor": "⊕", "weak": "→", "strong": "⇀",
    "equiv": "≡", "order": "≤", "eq": "=", "neq": "≠",
}
_PRECEDENCE = {op: (precedence, right) for precedence, op, right in _INFIX.values()}


class _Parser:
    def __init__(self, text: str):
        self.text = text
        self.tokens: list[_Token] = []
        offset = 0
        while offset < len(text):
            if text.startswith("=>", offset):
                raise FormulaError("'=>' is not supported; use '-\\' for strong implication", text, offset)
            match = _TOKEN.match(text, offset)
            if match is None:
                raise FormulaError(f"unexpected character {text[offset]!r}", text, offset)
            kind = match.lastgroup
            if kind not in {"space", "comment"}:
                spelling = match.group()
                canonical = _SYMBOL_ALIASES.get(spelling, spelling) if kind == "symbol" else spelling
                self.tokens.append(_Token(kind or "", canonical, offset))
            offset = match.end()
        self.tokens.append(_Token("eof", "", len(text)))
        self.index = 0
        self.fixed_variables: set[str] = set()

    @property
    def token(self) -> _Token:
        return self.tokens[self.index]

    def take(self) -> _Token:
        token = self.token
        self.index += 1
        return token

    def fail(self, message: str, token: _Token | None = None) -> None:
        raise FormulaError(message, self.text, (token or self.token).offset)

    def expect(self, text: str) -> _Token:
        if self.token.text != text:
            found = repr(self.token.text) if self.token.kind != "eof" else "end of formula"
            self.fail(f"expected {text!r}, found {found}")
        return self.take()

    def identifier(self) -> str:
        if self.token.kind != "name":
            self.fail("expected a variable name")
        token = self.take()
        if token.text in RESERVED:
            self.fail(f"{token.text!r} is a reserved word", token)
        return token.text

    def term(self) -> Node:
        token = self.take()
        if token.kind == "string":
            try:
                value = ast.literal_eval(token.text)
            except (ValueError, SyntaxError):
                self.fail("invalid quoted value", token)
            return Node("literal", value=value)
        if token.kind in {"name", "integer"}:
            return Node("term", value=token.text)
        self.fail("expected a value or a bound value variable", token)
        raise AssertionError("unreachable")

    def expression(self, minimum: int = 0) -> Node:
        left = self.primary()
        while self.token.text in _INFIX:
            precedence, op, right_associative = _INFIX[self.token.text]
            if precedence < minimum:
                break
            self.take()
            right = self.expression(precedence if right_associative else precedence + 1)
            left = Node(op, (left, right))
        return left

    def primary(self) -> Node:
        token = self.token
        # Equality gives an unambiguous value context even when the constant
        # happens to share an operator's spelling, as in ``T = red``. Value
        # names already have this interpretation on the right and in P(T).
        if (token.kind in {"string", "integer", "name"} and
                self.tokens[self.index + 1].text in {"=", "==", "!="}):
            left = self.term()
            op = "neq" if self.take().text == "!=" else "eq"
            return Node(op, (left, self.term()))
        if token.text in {"!", "not"}:
            self.take()
            return Node("not", (self.expression(50),))
        if token.text == "(":
            self.take()
            result = self.expression()
            self.expect(")")
            return result
        if token.text in BINDERS:
            op = self.take().text
            name = self.identifier()
            self.expect(".")
            previous = self.fixed_variables.copy()
            if op in {"mu", "nu"}:
                self.fixed_variables.add(name)
            try:
                body = self.expression()
            finally:
                self.fixed_variables = previous
            return Node(op, (body,), name)
        if token.text == "latest":
            self.take()
            name = self.identifier()
            self.expect("=")
            initial = self.term()
            self.expect(".")
            return Node("latest", (initial, self.expression()), name)
        if token.kind == "symbol" and token.text in UNARY:
            op = self.take().text
            return Node(op, (self.expression(50),))
        if token.kind == "name" and token.text in _NAMED_UNARY:
            op = _NAMED_UNARY[self.take().text]
            self.expect("(")
            body = self.expression()
            self.expect(")")
            return Node(op, (body,))
        if token.text == "twined":
            self.take()
            self.expect("(")
            if self.token.kind != "integer":
                self.fail("twined expects a positive integer")
            count = self.take()
            try:
                number = int(count.text)
            except ValueError:
                self.fail("twined integer is too large", count)
            if number < 1:
                self.fail("twined expects a positive integer", count)
            self.expect(")")
            return Node("twined", value=str(number))
        if token.kind in {"string", "integer", "name"}:
            if token.kind != "name":
                self.fail("a value is only valid in a predicate argument or value equality")
            name = self.take().text
            if name in {"t", "b", "f"}:
                return Node("const", value=name)
            if name in self.fixed_variables:
                if self.token.text == "(":
                    self.fail(f"fixed-point variable {name!r} does not take arguments")
                return Node("var", value=name)
            if name in RESERVED:
                self.fail(f"unexpected reserved word {name!r}", token)
            args: list[Node] = []
            if self.token.text == "(":
                self.take()
                if self.token.text != ")":
                    args.append(self.term())
                    while self.token.text == ",":
                        self.take()
                        args.append(self.term())
                self.expect(")")
            return Node("pred", tuple(args), name)
        self.fail("expected a formula", token)
        raise AssertionError("unreachable")


def parse_formula(text: str) -> Node:
    """Parse a formula; no declarations or model are needed.

    Quantifiers and fixed-point binders extend as far right as possible.  From
    tightest to loosest, binary operators are ``&``, ``xor``, ``|``, ``->`` /
    ``-\\``, ``<=``, and ``<=>``.  Both implications associate to the right.
    Unicode symbols and ASCII operators can be mixed freely.  The spelling
    ``=>`` is not supported.  Symbolic unary modalities
    accept a formula directly; named unary operators require parentheses.
    Named ``somewhere`` / ``everywhere`` denote ``diamond`` / ``box``.  Use
    ``someQuorumSomePoint`` / ``everyQuorumEveryPoint`` for their respective
    quorum-and-point modalities.  AST operation names remain unchanged.
    """
    if not isinstance(text, str):
        raise TypeError("formula must be a string")
    parser = _Parser(text)
    try:
        result = parser.expression()
        if parser.token.text == ";":
            parser.take()
        if parser.token.kind != "eof":
            parser.fail(f"unexpected token {parser.token.text!r}")
        return result
    except RecursionError as error:
        raise FormulaError("formula nesting exceeds the parser limit", text,
                           parser.token.offset) from error


def format_formula(node: Node, *, notation: str = "unicode") -> str:
    """Return compact, unambiguous, reparsable syntax for a syntax tree.

    ``notation='unicode'`` (the default) uses the paper's ``⇀`` for strong
    implication; ``notation='ascii'`` uses ``-\\``.  Parentheses preserve the
    exact tree, including operator association and the scope of binders.  Quoted
    value contents are preserved in both modes; ASCII output escapes any
    non-ASCII characters in those values.
    A manually constructed ``term`` whose name needs quoting is emitted as a
    literal, preserving its declared value while canonicalizing its node kind.
    The internal ``somewhere`` / ``everywhere`` operations render as
    ``someQuorumSomePoint`` / ``everyQuorumEveryPoint`` in ASCII.
    """
    if notation not in {"unicode", "ascii"}:
        raise ValueError("notation must be 'unicode' or 'ascii'")
    unicode = notation == "unicode"
    symbols = _UNICODE_BINARY if unicode else _ASCII_BINARY

    def render(item: Node, minimum: int = 0) -> str:
        op = item.op
        precedence = 60
        if op in {"const", "term", "var"}:
            text = str(item.value)
            if op == "term" and not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*|[0-9]+", text):
                # Public AST callers may use a declared value directly without
                # choosing a literal node. Such names still need valid source
                # quoting when a theory or witness is exported.
                text = repr(item.value) if unicode else ascii(item.value)
        elif op == "literal":
            text = repr(item.value) if unicode else ascii(item.value)
        elif op == "pred":
            arguments = "(" + ", ".join(render(arg) for arg in item.args) + ")" if item.args else ""
            text = str(item.value) + arguments
        elif op in BINDERS:
            precedence = 0
            binder = _UNICODE_BINDERS[op] if unicode else op
            text = f"{binder} {item.value}. {render(item.args[0])}"
        elif op == "latest":
            precedence = 0
            text = f"latest {item.value} = {render(item.args[0])}. {render(item.args[1])}"
        elif op == "twined":
            text = f"twined({item.value})"
        elif op == "not":
            precedence = 50
            text = ("¬" if unicode else "!") + render(item.args[0], precedence)
        elif op in {"eq", "neq"}:
            text = f"{render(item.args[0])} {symbols[op]} {render(item.args[1])}"
        elif op in symbols:
            precedence, right = _PRECEDENCE[op]
            left_text = render(item.args[0], precedence + int(right))
            right_text = render(item.args[1], precedence + int(not right))
            text = f"{left_text} {symbols[op]} {right_text}"
        elif op in UNARY:
            if unicode and op in _UNICODE_UNARY:
                precedence = 50
                # Separate bare quantifiers from a following point modality
                # so distinct nested operators never become a compound macro.
                symbol = _UNICODE_UNARY[op]
                separator = " " if symbol.endswith("ꟴ") else ""
                text = symbol + separator + render(item.args[0], precedence)
            else:
                name = _ASCII_UNARY.get(op, op)
                text = f"{name}({render(item.args[0])})"
        else:
            raise ValueError(f"unknown syntax operation {op!r}")
        return f"({text})" if precedence < minimum else text

    return render(node)
