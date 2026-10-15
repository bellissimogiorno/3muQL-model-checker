# Logic notation

Write formulas in **Unicode, ASCII, or a mixture of both**. All three choices
are parsed into the same logic. Bundled theories and displayed formulas use
Unicode by default; ASCII remains useful for typing, scripts, and terminals.
Theory files are ordinary UTF-8 Markdown: the symbols below are executable
text, not LaTeX commands.

The two implication arrows deserve particular care:

| Connective | Unicode | ASCII | Definition |
| --- | --- | --- | --- |
| Weak implication | `P → Q` | `P -> Q` | `¬P ∨ Q` |
| Strong implication | `P ⇀ Q` | `P -\ Q` | `¬P ∨ T(Q)` |

The strong arrow is the right harpoon **`⇀`** (U+21C0); type a hyphen followed
by a backslash, **`-\`**, for its ASCII spelling. `t → b` is `b` and therefore
valid, whereas `t ⇀ b` is `f`. This spelling follows the paper's distinction
between weak and strong implication.

## Symbols to copy

| Meaning | Unicode | ASCII |
| --- | --- | --- |
| Negation | `¬P` | `!P` or `not P` |
| Conjunction | `P ∧ Q` | `P & Q`, `P && Q`, or `P and Q` |
| Disjunction | `P ∨ Q` | `P \| Q`, `P \|\| Q`, or `P or Q` |
| Exclusive disjunction | `P ⊕ Q` | `P xor Q` or `P ^ Q` |
| Weak implication | `P → Q` | `P -> Q` |
| Strong implication | `P ⇀ Q` | `P -\ Q` |
| Crisp equality of truth values | `P ≡ Q` | `P <=> Q` |
| Crisp truth-value order | `P ≤ Q` | `P <= Q` |
| Equality of values | `v = w` | `v = w` or `v == w` |
| Inequality of values | `v ≠ w` | `v != w` |
| All values | `∀v. P(v)` | `forall v. P(v)` |
| Some value | `∃v. P(v)` | `exists v. P(v)` |
| At most one value | `∃⁰¹v. P(v)` | `affine v. P(v)` |
| Unique existence | `∃¹v. P(v)` | `unique v. P(v)` |
| Pre-fixed meet | `μX. P` | `mu X. P` |
| Post-fixed join | `νX. P` | `nu X. P` |
| All points in the current quorum | `□(P)` | `box(P)` or `everywhere(P)` |
| Some point in the current quorum | `◇(P)` | `diamond(P)` or `somewhere(P)` |
| Some quorum, retaining the point | ∃ꟴ(P) | `existsQ(P)` |
| Every quorum, retaining the point | ∀ꟴ(P) | `forallQ(P)` |
| Some quorum, every point | ∃ꟴ□(P) | `quorum(P)` or `someQuorumEveryPoint(P)` |
| Every quorum, some point | ∀ꟴ◇(P) | `contra(P)` or `everyQuorumSomePoint(P)` |
| Some quorum, some point | ∃ꟴ◇(P) | `someQuorumSomePoint(P)` |
| Every quorum, every point | ∀ꟴ□(P) | `everyQuorumEveryPoint(P)` |

The quorum marker is a real Unicode superscript capital Q: **`ꟴ`** (U+A7F4).
Bundled Markdown theories, Unicode formatter output, and the symbol toolbar
use `∃ꟴ` and `∀ꟴ`, matching the paper even when saved or copied as plain text.
The explorer and offline reader include a small font for this character.
In an editor or terminal whose font lacks it, use the equally valid plain-Q
spellings `∃Q`, `∀Q`, `∃Q◇`, and so on, or the ASCII names in the table.

The superscript `ꟴ` in `∃ꟴ` and `∀ꟴ` is a literal part of the operator; it is not a
variable to declare. A space after a symbolic binder is optional, so
`∀v. P(v)` and `∀ v. P(v)` are equivalent. Use a space before a bound name
beginning with `Q` to distinguish it from the accepted plain-Q operators.
Symbolic modalities can be written
as prefixes (`□P`); parenthesized bodies (`□(P ∧ Q)`) are usually clearer.
Named modalities require parentheses (`box(P)`).

`somewhere` and `everywhere` refer to points in the **current quorum**. Use
the explicit compound names when you also intend to range over quorums.
The chosen quorum remains in scope within the body, including nested modalities.

Truth constants stay `t`, `b`, and `f`. Truth tests retain their names:
`T`, `F`, `B`, `TB`, `TF`, and `FB`. Temporal operators also retain their
names, such as `yesterday(P)`, `once(P)`, and `forever(P)`; `latest` and
`twined` do too. The [language reference](language.md) lists their meanings.

`≡` is exact equality of truth values, not mutual implication. `≤` is the
package's crisp test of the order `f < b < t`, not the paper's optional
three-valued internal order connective. `∃¹` and `∃⁰¹` use the paper's
three-valued definitions: apply them to `T(P(v))` if you intend to count
only actually true instances. For nonmonotone bodies, `μ` and `ν` use
pre-fixed/post-fixed semantics and need not produce fixed points.

## The same theory in either style

These declarations are equivalent; put one version in a theory with unary
predicate `vote` and nullary predicate `observe` declared.

**Unicode**

```muql
axiom Correct: (∀v. TF(vote(v))) ∧ TF(observe())
axiom ObserveForward: (∃v. ∃ꟴ□(vote(v))) ⇀ observe()
property Justified: observe() → ∃v. ∃ꟴ◇(vote(v))
```

**ASCII**

```muql
axiom Correct: (forall v. TF(vote(v))) & TF(observe())
axiom ObserveForward: (exists v. quorum(vote(v))) -\ observe()
property Justified: observe() -> exists v. someQuorumSomePoint(vote(v))
```

Mixing styles is also valid:

```muql
axiom ObserveForward: (∃v. quorum(vote(v))) -\ observe()
```

The arrows have the same precedence and associate to the right in both
styles: `P ⇀ Q ⇀ R` means `P ⇀ (Q ⇀ R)`. This differs from
`(P ∧ Q) ⇀ R` in three-valued logic. Binders extend to the right as far as
possible; the parentheses around `∃v. ∃ꟴ□(vote(v))` above keep `observe()`
outside that binder. See the [precedence table](language.md#precedence-macros-and-reserved-words).

## Display and typing

The offline [theory guide](theories.html) has a Unicode/ASCII switch. Open it
directly in a browser to read the bundled examples. To display a theory from
the command line:

```sh
python -m muql list examples/voting.md
python -m muql list examples/voting.md --notation unicode
python -m muql list examples/voting.md --notation ascii
```

The default is Unicode when the console encoding supports it, with automatic
ASCII fallback otherwise. An explicit `--notation` chooses the display
style. This option affects output; both input styles are always accepted.
Formatting does not rewrite the source Markdown.

In a Markdown file, type **one backslash** for `-\`. Escaping is needed only
when the formula is embedded inside another language or command:

| Context | Example | Explanation |
| --- | --- | --- |
| A theory file | `P -\ Q` | One literal backslash. |
| POSIX shell or PowerShell | `'Rule=P -\ Q'` | Single quotes preserve the backslash. |
| Windows Command Prompt | `"Rule=P -\ Q"` | Use double quotes for the argument. |
| Python raw string | `r"P -\ Q"` | One literal backslash in a raw string. |
| Python ordinary string | `"P -\\ Q"` | Escape the backslash. |
| JSON string | `"P -\\ Q"` | JSON requires an escaped backslash. |

For example, in a POSIX shell or PowerShell:

```sh
python -m muql check examples/voting.md --replace 'ObserveForward=quorum(vote()) -\ observe()'
```

Python source can use either spelling directly:

```python
from muql import format_formula, load

original = load("examples/voting.md")
ascii_theory = original.replace(
    "ObserveForward", r"quorum(vote()) -\ observe()"
)
unicode_theory = original.replace(
    "ObserveForward", "∃ꟴ□(vote()) ⇀ observe()"
)
```

Given a parsed formula node, `format_formula(node)` returns Unicode and
`format_formula(node, notation="ascii")` returns ASCII. Both produce
parseable formulas. Use a JSON encoder such as `json.dumps` when storing a
formula in JSON; it handles backslash escaping for you.

## Compatibility and migration

**0.3.0 changes the scope of `somewhere` and `everywhere`.** These names now
mean `diamond` / `◇` and `box` / `□`: some or all points in the current quorum.
They no longer include a quantifier over quorums. Migrate old compound uses as
follows to preserve their original meaning:

| Input before 0.3.0 | Input from 0.3.0 | Unchanged Unicode meaning |
| --- | --- | --- |
| `somewhere(P)` | `someQuorumSomePoint(P)` | ∃ꟴ◇(P) |
| `everywhere(P)` | `everyQuorumEveryPoint(P)` | ∀ꟴ□(P) |

Review existing ASCII theory files, command-line replacements, and Python
formula strings: an old spelling may still parse while expressing a different
scope. Change operator calls only, preserving quoted names and comments.
The bundled Unicode theories retain their formulas and scopes. `quorum` and
`contra` keep their meanings; `someQuorumEveryPoint` and
`everyQuorumSomePoint` are additional aliases for them. Temporal operators keep
their semantics: `ultimately(P)` still expands to
`sometime(everyQuorumEveryPoint(forever(P)))`.

Starting with **0.2.1, `=>` is rejected**. That spelling clashes with another
implication in the paper, so it must not serve as an alias for strong
implication. The only accepted spellings for strong implication are `⇀` and
`-\`.

If a theory or script was written for an earlier package release, change each
old `=>` strong-implication operator to `-\` or `⇀`. Keep `<=>` unchanged:
it still means crisp truth-value equality. Change operators only; do not alter
quoted names or explanatory text merely because they contain these characters.
For example:

```text
Old input:  quorum(vote()) => observe()
ASCII:      quorum(vote()) -\ observe()
Unicode:    ∃ꟴ□(vote()) ⇀ observe()
```

Generated ASCII output
uses `-\`, and generated Unicode output uses `⇀`.

For easier entry, the parser also accepts `⋄` for `◇`, micro sign `µ` for
Greek `μ`, `∃1` or `∃!` for `∃¹`, and `∃01` for `∃⁰¹`. Output uses the
canonical symbols in the table above. Predicate names, variable names, and
declaration keywords remain ASCII; quoted point and value names can contain
Unicode. Symbols inside quoted names and comments are not treated as
operators.

Changing notation does not change the scope of a check. A successful result
still concerns only the declared finite frame; see
[precise semantics](semantics.md) before interpreting temporal results.
