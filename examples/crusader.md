# Declarative Crusader Agreement

Participants start with either `zero` or `one`. An output of `half` records a
failure to choose one binary value. The payload `half` is distinct from the
logical truth value `b`.

These are the Figure 13 axioms and Figure 14 properties of
[Gabbay, arXiv:2512.21137v3](https://arxiv.org/pdf/2512.21137v3). The ambient
three-way intersection condition in Remark 5.3.1 is explicit. The domain must
contain exactly the three listed payloads for this transcription.

Here `⇀` is strong implication (`-\` in ASCII), while `→` is weak (`->`).
The [notation guide](../docs/notation.md) explains the quantifiers and quorum
symbols; Unicode and ASCII can be mixed in any formula.

```muql
theory "Crusader Agreement"
points alice bob carol dave
values zero half one
stages 1
quorums {alice,bob,carol} {alice,bob,dave} {alice,carol,dave} {bob,carol,dave}
predicate input/1
predicate echo1/1
predicate echo2/1
predicate output/1

# Correctness and faultiness are uniform across payloads.
let InputCorrect(): ∀ v. TF(input(v))
let Echo1Correct(): ∀ v. TF(echo1(v))
let Echo2Correct(): ∀ v. TF(echo2(v))
let OutputCorrect(): ∀ v. TF(output(v))
let InputFaulty(): ∀ v. B(input(v))
let Echo1Faulty(): ∀ v. B(echo1(v))
let Echo2Faulty(): ∀ v. B(echo2(v))
let OutputFaulty(): ∀ v. B(output(v))

# Quorum intersection and backward rules.
axiom Intersection: twined(3)
axiom CaEcho1?: ∀ v. echo1(v) ⇀ ∃ꟴ◇(input(v))
axiom CaEcho2?: ∀ v. echo2(v) → ∃ꟴ□(echo1(v))
axiom CaOutput?: (output(zero) → ∃ꟴ□(echo2(zero))) ∧ (output(one) → ∃ꟴ□(echo2(one)))
axiom CaOutputHalf?: output(half) → (∃ꟴ□(echo1(zero)) ∧ ∃ꟴ□(echo1(one)))

# Forward delivery and relay.
axiom CaEcho1!: ∀ v. (input(v) ∨ ∀ꟴ◇(echo1(v))) → echo1(v)
axiom CaEcho2!: (∃ v. ∃ꟴ□(echo1(v))) → (∃ v. echo2(v))
axiom CaOutput!: ∀ v. ∃ꟴ□(echo2(v)) → output(v)
axiom CaOutputHalf!: (∃ꟴ□(echo1(zero)) ∧ ∃ꟴ□(echo1(one))) → output(half)

# One shared correctness quorum; separate predicate uniformity.
axiom CaCorrect: ∃ꟴ□(InputCorrect() ∧ Echo1Correct() ∧ Echo2Correct() ∧ OutputCorrect())
axiom CaInputUniform: InputCorrect() ∨ InputFaulty()
axiom CaEcho1Uniform: Echo1Correct() ∨ Echo1Faulty()
axiom CaEcho2Uniform: Echo2Correct() ∨ Echo2Faulty()
axiom CaOutputUniform: OutputCorrect() ∨ OutputFaulty()

# Binary inputs and at most one true second echo.
axiom CaInput: ((input(zero) ∧ ¬input(one)) ∨ (¬input(zero) ∧ input(one))) ∧ ¬input(half)
axiom CaEcho2Affine: ∃⁰¹ v. echo2(v)

# Agreement, validity, and existence of an output.
property CaAgree:
  ∀ v. ∀ w. (∃ꟴ◇(output(v)) ∧ ∃ꟴ◇(output(w)))
    ⇀ ((v = w) ∨ (v = half) ∨ (w = half))
property CaValid1: ∀ v. ∀ w. (TB(∀ꟴ□(input(v))) ∧ output(w)) ⇀ (v = w)
property CaValid2: ∀ v. ∃ꟴ◇(output(v)) ⇀ (∃ꟴ◇(input(v)) ∨ (v = half))
property CaLive: ∀ꟴ□(∃ v. output(v))
```

Unlike Bracha, `CaCorrect` requires one quorum that is correct across **all four
predicates**. `CaEcho1?` deliberately uses strong implication: a true first
echo must have an actually true input at some point in some quorum.

Weak agreement permits a correct participant to output both `one` and `half`.
Example 5.3.4 makes that distinction explicit. With four honest participants,
two inputs of each binary value can cause everyone to first echo both values;
everyone may then second echo `one` and output both `one` and `half`. Thus the
extra candidate `∃⁰¹ v. output(v)` is false in the theory, while `CaAgree`
still holds. This is a useful experiment, not a counterexample to the claimed
weak-agreement theorem.

`CaLive` checks existence of an output in the complete declarative model. This
static theory has no arrival times, execution steps, or fairness scheduler.
