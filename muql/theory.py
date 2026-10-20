"""Load reproducible finite scopes and named formulas from literate Markdown.

Only fenced ``muql`` blocks are executable.  Prose and other code blocks are
ignored, so a theory can double as an explanatory document.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field, replace as dataclass_replace
from pathlib import Path
import re
from typing import Iterable

from .syntax import BINDERS, RESERVED, UNARY, FormulaError, Node, parse_formula


class TheoryError(ValueError):
    """An invalid declaration or formula, with a source location."""

    def __init__(self, message: str, source: str = "<string>", line: int = 1, column: int = 1):
        self.message, self.source, self.line, self.column = message, source, line, column
        super().__init__(f"{source}:{line}:{column}: {message}")


@dataclass(frozen=True)
class _Macro:
    parameters: tuple[str, ...]
    body: Node
    line: int


@dataclass(frozen=True)
class Theory:
    """A parsed theory and its finite scope, or a marked search template.

    ``without`` and ``replace`` return new theories, leaving the original
    available for comparison in a demonstration or notebook. A template has
    ``scope_declared=False``: its placeholder frame must not be model-checked
    until a search supplies an actual scope.
    """

    name: str
    points: tuple[str, ...]
    values: tuple[str, ...]
    stages: int
    quorums: tuple[tuple[str, ...], ...]
    predicates: dict[str, int]
    axioms: dict[str, Node]
    properties: dict[str, Node]
    source: str = "<string>"
    time: str = "finite"
    locations: dict[str, int] = field(default_factory=dict, repr=False, compare=False)
    _macros: dict[str, _Macro] = field(default_factory=dict, repr=False, compare=False)
    scope_declared: bool = field(default=True, compare=False)

    def without(self, *axiom_names: str) -> "Theory":
        """Return a copy with the named axioms removed; reject misspellings."""
        missing = set(axiom_names) - self.axioms.keys()
        if missing:
            raise TheoryError("unknown axiom(s): " + ", ".join(sorted(missing)), self.source)
        return dataclass_replace(self, axioms={name: node for name, node in self.axioms.items() if name not in axiom_names})

    def replace(self, name: str, formula: str | Node) -> "Theory":
        """Return a copy with one existing axiom replaced by a checked formula."""
        if name not in self.axioms:
            raise TheoryError(f"unknown axiom {name!r}", self.source)
        line = self.locations.get(name, 1)
        if isinstance(formula, str):
            try:
                node = parse_formula(formula)
            except FormulaError as error:
                raise TheoryError(error.message, self.source, line + error.line - 1, error.column) from error
        elif isinstance(formula, Node):
            node = formula
        else:
            raise TypeError("replacement formula must be a string or Node")
        validate_formula(node, self, line=line, allow_macros=True)
        node = _checked_expand(node, self, line)
        validate_formula(node, self, line=line)
        return dataclass_replace(self, axioms={**self.axioms, name: node})


_NAME = r"[A-Za-z_][A-Za-z_0-9]*"
# Labels identify whole rules; they are not identifiers in formula expressions.
# Keep the paper's direction marks and hyphenated names out of the formula lexer.
_LABEL = r"[A-Za-z_][A-Za-z_0-9!?-]*"
_DECLARATION = re.compile(r"^(theory|points|values|stages|time|quorums|predicate|axiom|property|let)\b")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_ITEM = re.compile(r"(\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*'|[A-Za-z_][A-Za-z_0-9]*|[0-9]+)")
_FORMULA_ARITIES = {
    "const": 0, "var": 0, "twined": 0, "not": 1,
    "and": 2, "or": 2, "xor": 2, "weak": 2, "strong": 2,
    "equiv": 2, "order": 2, "eq": 2, "neq": 2, "latest": 2,
    **dict.fromkeys(UNARY | BINDERS, 1),
}
_NAMED_FORMULAS = frozenset({"pred", "var", "const", "twined", "latest"}) | BINDERS


def _commentless(text: str) -> str:
    """Remove an ASCII line comment without damaging quoted strings."""
    quote = None
    escaped = False
    for index, char in enumerate(text):
        if escaped:
            escaped = False
        elif char == "\\" and quote is not None:
            escaped = True
        elif quote is not None:
            if char == quote:
                quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char == "#" or text[index:index + 2] == "//":
            return text[:index]
    return text


def _blocks(markdown: str, source: str) -> list[tuple[str, int]]:
    lines: list[tuple[str, int]] = []
    fence: str | None = None
    active = False
    found = False
    opening = 1
    for number, text in enumerate(markdown.splitlines(), 1):
        match = _FENCE.match(text)
        if fence is None:
            if match:
                fence = match.group(1)
                opening = number
                active = match.group(2).strip() == "muql"
                found |= active
            continue
        if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence) and not match.group(2).strip():
            fence, active = None, False
            lines.append(("", number))
            continue
        if active:
            lines.append((_commentless(text).rstrip(), number))
    if fence is not None and active:
        raise TheoryError("unclosed muql code fence", source, opening)
    if not found:
        raise TheoryError("no fenced muql blocks found; put declarations inside ```muql ... ```", source)
    return lines


def _skip_space(text: str, offset: int) -> int:
    while offset < len(text) and text[offset].isspace():
        offset += 1
    return offset


def _items(text: str, source: str, line: int, column: int = 1) -> tuple[str, ...]:
    """Read names in one pass; offsets remain relative to the source line."""
    items: list[str] = []
    offset = _skip_space(text, 0)
    while offset < len(text):
        match = _ITEM.match(text, offset)
        if match is None:
            raise TheoryError(f"invalid declaration near {text[offset:].strip()!r}", source, line, column + offset)
        item = match.group(1)
        if item[0] in {"'", '"'}:
            try:
                item = ast.literal_eval(item)
            except (ValueError, SyntaxError) as error:
                raise TheoryError("invalid quoted name", source, line, column + match.start(1)) from error
        if not item:
            raise TheoryError("names cannot be empty", source, line, column + match.start(1))
        items.append(item)
        offset = match.end()
        if offset < len(text):
            if not text[offset].isspace() and text[offset] != ",":
                raise TheoryError("separate names with whitespace or commas", source, line, column + offset)
            offset = _skip_space(text, offset)
            if offset < len(text) and text[offset] == ",":
                offset += 1
                offset = _skip_space(text, offset)
                if offset == len(text):
                    raise TheoryError("expected a name after comma", source, line, column + offset)
    if not items:
        raise TheoryError("expected at least one name", source, line, column)
    if len(set(items)) != len(items):
        raise TheoryError("duplicate names in declaration", source, line, column)
    return tuple(items)


def _formula(text: str, source: str, line: int, column: int = 1) -> Node:
    try:
        return parse_formula(text)
    except FormulaError as error:
        raise TheoryError(error.message, source, line + error.line - 1, error.column + (column - 1 if error.line == 1 else 0)) from error


def _position(text: str, first_line: int, offset: int) -> tuple[int, int]:
    """Map a statement-relative character offset back to its document."""
    return first_line + text.count("\n", 0, offset), offset - text.rfind("\n", 0, offset)


def _quorum_items(text: str, source: str, line: int, column: int = 1) -> tuple[tuple[str, ...], ...]:
    """Read set delimiters outside quotes, with checked separators."""
    groups: list[tuple[str, ...]] = []
    offset = 0
    while offset < len(text):
        offset = _skip_space(text, offset)
        if offset == len(text):
            break
        if text[offset] != "{":
            raise TheoryError("quorums expects nonempty sets such as {a,b} {b,c}", source, line, column + offset)
        start = offset + 1
        offset = start
        quote = None
        escaped = False
        while offset < len(text):
            char = text[offset]
            if escaped:
                escaped = False
            elif quote is not None:
                if char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
            elif char in {"'", '"'}:
                quote = char
            elif char == "}":
                break
            elif char == "{":
                raise TheoryError("nested quorum sets are not allowed; quote braces in names", source, line, column + offset)
            offset += 1
        if offset == len(text):
            raise TheoryError("unclosed quorum set or quoted name", source, line, column + start - 1)
        groups.append(_items(text[start:offset], source, line, column + start))
        offset += 1
        if offset < len(text) and not text[offset].isspace() and text[offset] != ",":
            raise TheoryError("separate quorum sets with whitespace or a comma", source, line, column + offset)
        offset = _skip_space(text, offset)
        if offset < len(text) and text[offset] == ",":
            offset += 1
            offset = _skip_space(text, offset)
            if offset == len(text):
                raise TheoryError("expected a quorum set after comma", source, line, column + offset)
    if not groups:
        raise TheoryError("quorums expects nonempty sets such as {a,b} {b,c}", source, line, column)
    if len({frozenset(q) for q in groups}) != len(groups):
        raise TheoryError("duplicate quorum", source, line, column)
    return tuple(groups)


def loads(markdown: str, source: str = "<string>", *, for_search: bool = False) -> Theory:
    """Load all ``muql`` fences in a Markdown string as one theory.

    A declaration starts a line.  A formula can continue on following lines;
    indentation is recommended. Frame declarations are mandatory by default.
    ``for_search=True`` permits omitted frame fields and marks the result as
    an unscoped template. Named value constants still require a ``values``
    declaration; all declared values remain distinguished constants.
    """
    if not isinstance(markdown, str):
        raise TypeError("Markdown source must be a string")
    if type(for_search) is not bool:
        raise TypeError("for_search must be a boolean")
    try:
        return _loads(markdown, source, for_search=for_search)
    except RecursionError as error:
        raise TheoryError("formula or macro nesting exceeds the loader limit", source) from error


def _loads(markdown: str, source: str, *, for_search: bool) -> Theory:
    rows = _blocks(markdown, source)
    statements: list[tuple[str, int]] = []
    pending: list[str] = []
    pending_line = 1
    last_line = 0
    for row, number in rows:
        stripped = row.strip()
        if not stripped:
            continue
        if _DECLARATION.match(stripped):
            if pending:
                statements.append(("\n".join(pending), pending_line))
            pending, pending_line, last_line = [row], number, number
        elif pending and pending[0].split()[0] in {"axiom", "property", "let"}:
            pending.extend([""] * (number - last_line - 1))
            pending.append(row)
            last_line = number
        else:
            raise TheoryError(f"unknown declaration {stripped.split()[0]!r}", source, number)
    if pending:
        statements.append(("\n".join(pending), pending_line))

    frame: dict[str, object] = {}
    frame_lines: dict[str, int] = {}
    predicates: dict[str, int] = {}
    axioms: dict[str, Node] = {}
    properties: dict[str, Node] = {}
    macros: dict[str, _Macro] = {}
    locations: dict[str, int] = {}
    formula_names: set[str] = set()
    for statement, line in statements:
        declaration = statement.lstrip()
        match = re.fullmatch(r"(\w+)(?:\s+(.*))?", declaration, re.DOTALL)
        if not match:
            raise TheoryError("incomplete declaration", source, line)
        kind, rest = match.groups()
        rest = rest or ""
        rest_offset = (len(statement) - len(declaration) +
                       (match.start(2) if match.group(2) is not None else len(declaration)))
        rest_offset += len(rest) - len(rest.lstrip())
        rest = rest.strip()
        rest_line, rest_column = _position(statement, line, rest_offset)
        if kind in {"theory", "points", "values", "stages", "time", "quorums"}:
            if kind in frame:
                raise TheoryError(f"duplicate {kind} declaration", source, line)
            frame_lines[kind] = line
            if kind in {"theory", "points", "values"}:
                names = _items(rest, source, rest_line, rest_column)
                if kind == "theory" and len(names) != 1:
                    raise TheoryError('theory expects one name; quote names containing spaces', source, line)
                frame[kind] = names[0] if kind == "theory" else names
            elif kind == "stages":
                if not re.fullmatch(r"[0-9]+", rest):
                    raise TheoryError("stages must be a positive integer", source, line)
                try:
                    stages = int(rest)
                except ValueError as error:
                    raise TheoryError("stages integer is too large", source, line) from error
                if stages < 1:
                    raise TheoryError("stages must be a positive integer", source, line)
                frame[kind] = stages
            elif kind == "time":
                if rest not in {"finite", "stutter"}:
                    raise TheoryError("time must be 'finite' or 'stutter'", source, line)
                frame[kind] = rest
            else:
                frame[kind] = _quorum_items(rest, source, rest_line, rest_column)
        elif kind == "predicate":
            match = re.fullmatch(rf"({_NAME})\s*/\s*([0-9]+)", rest)
            if not match:
                raise TheoryError("predicate expects Name/arity, for example vote/1", source, line)
            name, arity = match.groups()
            if name in RESERVED:
                raise TheoryError(f"predicate name {name!r} is reserved", source, line)
            if name in predicates or name in macros:
                raise TheoryError(f"duplicate predicate or macro {name!r}", source, line)
            try:
                predicates[name] = int(arity)
            except ValueError as error:
                raise TheoryError("predicate arity integer is too large", source, line) from error
        else:
            pattern = rf"({_NAME})(?:\s*\(([^()]*)\))?\s*:[ \t]*(.*)" if kind == "let" else rf"({_LABEL})\s*:[ \t]*(.*)"
            match = re.fullmatch(pattern, rest, re.DOTALL)
            if not match:
                raise TheoryError(f"{kind} expects a name, colon, and formula", source, line)
            formula_offset = rest_offset + match.start(match.lastindex)
            formula_line, formula_column = _position(statement, line, formula_offset)
            if kind == "let":
                name, arguments, formula_text = match.groups()
                params = tuple(part.strip() for part in arguments.split(",")) if arguments and arguments.strip() else ()
                if any(not re.fullmatch(_NAME, param) or param in RESERVED for param in params):
                    raise TheoryError("macro parameters must be nonreserved variable names", source, line)
                if len(set(params)) != len(params):
                    raise TheoryError("duplicate macro parameter", source, line)
                if name in RESERVED or name in predicates or name in macros:
                    raise TheoryError(f"reserved or duplicate macro name {name!r}", source, line)
                macros[name] = _Macro(params, _formula(formula_text, source, formula_line, formula_column), line)
            else:
                name, formula_text = match.groups()
                if name in formula_names:
                    raise TheoryError(f"duplicate axiom or property name {name!r}", source, line)
                formula_names.add(name)
                (axioms if kind == "axiom" else properties)[name] = _formula(formula_text, source, formula_line, formula_column)
                locations[name] = line

    missing = {"points", "values", "stages", "quorums"} - frame.keys()
    if missing and not for_search:
        raise TheoryError("missing required declaration(s): " + ", ".join(sorted(missing)), source)
    if "quorums" in frame and "points" not in frame:
        raise TheoryError("quorums requires an explicit points declaration", source, frame_lines["quorums"])
    frame.setdefault("points", ("p0",))
    frame.setdefault("stages", 1)
    frame.setdefault("quorums", (frame["points"],))
    # Validate formulas against an empty value signature first when none was
    # declared. A temporary label must never make a misspelled free name legal.
    frame.setdefault("values", ())
    points = frame["points"]
    for quorum in frame["quorums"]:
        unknown = set(quorum) - set(points)
        if unknown:
            raise TheoryError("quorum contains undeclared point(s): " + ", ".join(sorted(unknown)), source, frame_lines["quorums"])
    theory = Theory(
        name=str(frame.get("theory", Path(source).stem if source != "<string>" else "Untitled theory")),
        points=points, values=frame["values"], stages=frame["stages"], quorums=frame["quorums"],
        predicates=predicates, axioms=axioms, properties=properties, source=source,
        time=frame.get("time", "finite"), locations=locations, _macros=macros,
        scope_declared=not missing,
    )
    # Validate unused macros too: a typo should never depend on which property
    # happens to be selected at the command line.
    for macro in macros.values():
        validate_formula(macro.body, theory, line=macro.line,
                         variables=macro.parameters, allow_macros=True)
    for name, node in {**axioms, **properties}.items():
        validate_formula(node, theory, line=locations[name], allow_macros=True)
    for macro in macros.values():
        expanded = _checked_expand(macro.body, theory, macro.line)
        validate_formula(expanded, theory, line=macro.line, variables=macro.parameters)
    expanded_axioms = {name: _checked_expand(node, theory, locations[name]) for name, node in axioms.items()}
    expanded_properties = {name: _checked_expand(node, theory, locations[name]) for name, node in properties.items()}
    theory = dataclass_replace(theory, axioms=expanded_axioms, properties=expanded_properties)
    if "values" in missing:
        # Domains are nonempty. Choose a placeholder which cannot shadow a
        # value binder or formal parameter, even inside an unused macro.
        used = set(predicates) | set(macros)
        for node in (*expanded_axioms.values(), *expanded_properties.values()):
            used.update(_all_names(node))
        for macro in macros.values():
            used.update(macro.parameters)
            used.update(_all_names(macro.body))
        index = 0
        while f"v{index}" in used:
            index += 1
        theory = dataclass_replace(theory, values=(f"v{index}",))
    validate_theory(theory, require_scope=not for_search)
    return theory


def load(path: str | Path, *, for_search: bool = False) -> Theory:
    """Read a UTF-8 literate theory, optionally as an unscoped search template."""
    path = Path(path)
    return loads(path.read_text(encoding="utf-8"), source=str(path), for_search=for_search)


def _all_names(node: Node) -> set[str]:
    return ({node.value} if node.value is not None else set()) | set().union(*(_all_names(arg) for arg in node.args))


@dataclass
class _ExpansionBudget:
    source: str
    line: int
    remaining: int = 100000

    def spend(self) -> None:
        self.remaining -= 1
        if self.remaining < 0:
            raise TheoryError("macro expansion exceeds the 100000-node work limit", self.source, self.line)


def _checked_expand(node: Node, theory: Theory, line: int) -> Node:
    try:
        forbidden = _all_names(node) | set(theory.values) | set(theory.predicates) | set(theory._macros)
        for macro in theory._macros.values():
            forbidden.update(_all_names(macro.body))
            forbidden.update(macro.parameters)
        return _expand(node, theory._macros, theory.source, line, forbidden=forbidden)
    except RecursionError as error:
        raise TheoryError("formula or macro nesting exceeds the expansion limit", theory.source, line) from error


def _substitute(node: Node, substitutions: dict[str, Node], forbidden: set[str], budget: _ExpansionBudget) -> Node:
    """Capture-avoiding substitution of macro value parameters."""
    budget.spend()
    if node.op == "term" and node.value in substitutions:
        return substitutions[node.value]
    if node.op in BINDERS | {"latest"}:
        variable = node.value
        local = substitutions.copy()
        local.pop(variable, None)
        body_index = 1 if node.op == "latest" else 0
        arguments = list(node.args)
        # Give all macro-local binders fresh names, including names unrelated
        # to the arguments.  This also keeps nested macro calls independent.
        suffix = 1
        candidate = f"{variable}_local{suffix}"
        while candidate in forbidden:
            suffix += 1
            candidate = f"{variable}_local{suffix}"
        forbidden.add(candidate)
        arguments[body_index] = _rename_bound(arguments[body_index], variable, candidate, node.op in {"mu", "nu"}, budget)
        variable = candidate
        if node.op == "latest":
            arguments[0] = _substitute(arguments[0], substitutions, forbidden, budget)
        arguments[body_index] = _substitute(arguments[body_index], local, forbidden, budget)
        return Node(node.op, tuple(arguments), variable)
    return Node(node.op, tuple(_substitute(arg, substitutions, forbidden, budget) for arg in node.args), node.value)


def _rename_bound(node: Node, old: str, new: str, fixed: bool, budget: _ExpansionBudget) -> Node:
    budget.spend()
    if node.op == ("var" if fixed else "term") and node.value == old:
        return Node(node.op, value=new)
    if node.op in BINDERS | {"latest"} and node.value == old:
        # A nested binder with the same name hides the binding being renamed.
        if node.op == "latest":
            return Node(node.op, (_rename_bound(node.args[0], old, new, fixed, budget), node.args[1]), node.value)
        return node
    return Node(node.op, tuple(_rename_bound(arg, old, new, fixed, budget) for arg in node.args), node.value)


def _expand(node: Node, macros: dict[str, _Macro], source: str, line: int, stack: tuple[str, ...] = (), forbidden: set[str] | None = None, budget: _ExpansionBudget | None = None) -> Node:
    if budget is None:
        budget = _ExpansionBudget(source, line)
    budget.spend()
    if forbidden is None:
        forbidden = _all_names(node) | set().union(*(_all_names(macro.body) for macro in macros.values()))
    if node.op == "pred" and node.value in macros:
        name = node.value
        if name in stack:
            raise TheoryError("recursive macro: " + " -> ".join((*stack, name)), source, line)
        macro = macros[name]
        if len(node.args) != len(macro.parameters):
            raise TheoryError(f"macro {name!r} expects {len(macro.parameters)} arguments, got {len(node.args)}", source, line)
        substitutions = dict(zip(macro.parameters, node.args))
        body = _substitute(macro.body, substitutions, forbidden, budget)
        return _expand(body, macros, source, line, (*stack, name), forbidden, budget)
    return Node(node.op, tuple(_expand(arg, macros, source, line, stack, forbidden, budget) for arg in node.args), node.value)


def validate_formula(node: Node, theory: Theory, *, line: int = 1, variables: Iterable[str] = (), allow_macros: bool = False) -> None:
    """Check AST shape, value sorts, names, and binding against a theory.

    The loader validates before expansion with ``allow_macros=True`` so even
    unused macro arguments must be well-formed declared values. Engine callers
    use the default, which accepts expanded formulas only.
    """
    def fail(message: str) -> None:
        raise TheoryError(message, theory.source, line)

    def term(value: Node, bound: set[str]) -> None:
        if not isinstance(value, Node) or not isinstance(value.args, tuple) or value.args:
            fail("predicate arguments and value equality operands must be value terms")
        if not isinstance(value.value, str):
            fail("value terms must have string names")
        if value.op == "literal":
            if value.value not in theory.values:
                fail(f"undeclared value {value.value!r}")
        elif value.op == "term":
            if value.value not in bound and value.value not in theory.values:
                fail(f"free or undeclared value name {value.value!r}; bind it with a quantifier or declare it in values")
        else:
            fail("predicate arguments and value equality operands must be value terms")

    def walk(value: Node, bound: set[str], fixed: set[str]) -> None:
        if not isinstance(value, Node):
            fail("formula children must be Node objects")
        if not isinstance(value.op, str) or not isinstance(value.args, tuple):
            fail("formula operations must be strings and operands must be a tuple")
        if value.op != "pred" and value.op not in _FORMULA_ARITIES:
            fail(f"unknown formula operation {value.op!r}")
        if value.op in _FORMULA_ARITIES and len(value.args) != _FORMULA_ARITIES[value.op]:
            fail(f"operation {value.op!r} expects {_FORMULA_ARITIES[value.op]} operands")
        if value.op in _NAMED_FORMULAS:
            if not isinstance(value.value, str):
                fail(f"operation {value.op!r} requires a string name or value")
        elif value.value is not None:
            fail(f"operation {value.op!r} does not take a name or value")
        if value.op == "pred":
            macro = theory._macros.get(value.value) if allow_macros else None
            if macro is None and value.value not in theory.predicates:
                fail(f"undeclared predicate {value.value!r}")
            arity = len(macro.parameters) if macro is not None else theory.predicates[value.value]
            if len(value.args) != arity:
                kind = "macro" if macro is not None else "predicate"
                fail(f"{kind} {value.value!r} expects {arity} arguments, got {len(value.args)}")
            for arg in value.args:
                term(arg, bound)
        elif value.op in {"eq", "neq"}:
            for arg in value.args:
                term(arg, bound)
        elif value.op == "var":
            if value.value not in fixed:
                fail(f"free fixed-point variable {value.value!r}")
        elif value.op in BINDERS | {"latest"}:
            name = value.value
            if not isinstance(name, str) or not re.fullmatch(_NAME, name) or name in RESERVED:
                fail(f"invalid binder name {name!r}")
            if name in bound or name in fixed:
                fail(f"binder {name!r} shadows an enclosing variable; use a fresh name")
            if name in theory.values or name in theory.predicates:
                fail(f"binder {name!r} shadows a declared value or predicate; use a fresh name")
            if value.op in {"mu", "nu"}:
                walk(value.args[0], bound, fixed | {name})
            else:
                if value.op == "latest":
                    term(value.args[0], bound)
                walk(value.args[-1], bound | {name}, fixed)
        elif value.op == "const":
            if value.value not in {"t", "b", "f"}:
                fail(f"invalid truth constant {value.value!r}")
        elif value.op == "twined":
            if not re.fullmatch(r"[0-9]+", value.value):
                fail("twined expects a positive integer")
            try:
                number = int(value.value)
            except ValueError:
                fail("twined integer is too large")
            if number < 1:
                fail("twined expects a positive integer")
        else:
            for arg in value.args:
                walk(arg, bound, fixed)

    bound = set(variables)
    for name in bound:
        if not isinstance(name, str) or not re.fullmatch(_NAME, name) or name in RESERVED:
            fail(f"invalid value parameter name {name!r}")
        if name in theory.values or name in theory.predicates:
            fail(f"value parameter {name!r} shadows a declared value or predicate; use a fresh name")
    try:
        walk(node, bound, set())
    except RecursionError as error:
        raise TheoryError("formula nesting exceeds the validation limit", theory.source, line) from error


def validate_theory(theory: Theory, *, require_scope: bool = True) -> None:
    """Validate a complete, expanded theory before an engine uses it.

    ``Theory`` is a public dataclass whose mappings may have been modified or
    supplied directly by a caller; loading Markdown is not the only entry path.
    This check performs no macro expansion and accepts no unresolved macros.
    Engine callers require an explicit scope. Search can validate a template
    using ``require_scope=False``, then supply each candidate's actual scope.
    """
    if not isinstance(theory, Theory):
        raise TheoryError("expected a Theory object")
    source = theory.source if isinstance(theory.source, str) else "<theory>"

    def fail(message: str) -> None:
        raise TheoryError(message, source)

    if type(require_scope) is not bool:
        raise TypeError("require_scope must be a boolean")
    if type(theory.scope_declared) is not bool:
        fail("scope_declared must be a boolean")
    if require_scope and not theory.scope_declared:
        fail("theory has no complete declared scope; use model search or declare points, values, stages, and quorums")
    for label, text in (("name", theory.name), ("source", theory.source)):
        if not isinstance(text, str) or not text:
            fail(f"theory {label} must be a nonempty string")

    def names(label: str, items: object) -> None:
        if not isinstance(items, (tuple, list)) or not items:
            fail(f"{label} must be a nonempty sequence of names")
        if any(not isinstance(item, str) or not item for item in items):
            fail(f"{label} must contain nonempty string names")
        if len(set(items)) != len(items):
            fail(f"duplicate names in {label}")

    names("points", theory.points)
    names("values", theory.values)
    if type(theory.stages) is not int or theory.stages < 1:
        fail("stages must be a positive integer")
    if not isinstance(theory.time, str) or theory.time not in {"finite", "stutter"}:
        fail("time must be 'finite' or 'stutter'")
    if not isinstance(theory.quorums, (tuple, list)) or not theory.quorums:
        fail("quorums must be a nonempty sequence of nonempty point sets")
    seen = set()
    for quorum in theory.quorums:
        names("quorum", quorum)
        unknown = set(quorum) - set(theory.points)
        if unknown:
            fail("quorum contains undeclared point(s): " + ", ".join(sorted(unknown)))
        if frozenset(quorum) in seen:
            fail("duplicate quorum")
        seen.add(frozenset(quorum))
    for label, mapping, pattern in (
        ("predicates", theory.predicates, _NAME),
        ("axioms", theory.axioms, _LABEL),
        ("properties", theory.properties, _LABEL),
    ):
        if not isinstance(mapping, dict):
            fail(f"{label} must be a name-to-definition dictionary")
        for name in mapping:
            if not isinstance(name, str) or not re.fullmatch(pattern, name):
                fail(f"invalid {label} name {name!r}")
    for name, arity in theory.predicates.items():
        if name in RESERVED:
            fail(f"predicate name {name!r} is reserved")
        if type(arity) is not int or arity < 0:
            fail(f"predicate {name!r} arity must be a nonnegative integer")
    if theory.axioms.keys() & theory.properties.keys():
        fail("axiom and property labels must be distinct")
    if not isinstance(theory.locations, dict) or any(
        not isinstance(name, str) or type(line) is not int or line < 1
        for name, line in theory.locations.items()
    ):
        fail("source locations must map names to positive integer lines")
    for name, formula in {**theory.axioms, **theory.properties}.items():
        validate_formula(formula, theory, line=theory.locations.get(name, 1))
