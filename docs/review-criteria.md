# Evidence-Based Anki Card Review Criteria

This rubric governs iterative quality-review passes over `decks/*.yaml` before generating a shareable `.apkg`. Every review pass should score cards concretely, cite card `id`s, and propose exact drop-in rewrites—not generic advice.

---

## Pillar 1: Source Fidelity & Legal Accuracy

Every fact, nuance, caveat, standard, case citation, and jurisdiction recorded in the source notes must survive intact without distortion.

1. **Zero Silent Omissions**: Every element, subpoint, defence, case reference (e.g., *Mustapha*, *Hickey*), statutory subsection (e.g., BC *Privacy Act* s. 2(a)–(d)), and parenthetical nuance from the source cards is represented in at least one card.
2. **Standard Precision**: Objective vs. subjective standards (and hybrid notes like "reasonable person in P's position") are stated accurately and never conflated.
3. **Fault & Harm Threshold Precision**: Mental states (`intent`, `substantial certainty`, `recklessness`, `wilfully`, `ought to have known`, `intent not required`) and harm thresholds (`per se`, `presumed`, `*Mustapha*`, `visible & provable injury`, `economic loss`) are preserved exactly.
4. **Jurisdiction Accuracy**: BC-specific rules (BC *Privacy Act*, BC objective reliance test in fraud), Ontario-specific torts (Intrusion upon Seclusion), and general Canadian tort rules are accurately labeled in `Context`, body text, and `jurisdiction::*` tags.

---

## Pillar 2: Matuschak's Five Prompt Properties & Cognitive Hygiene

Every individual note must pass all five operational criteria:

1. **Focused (True Atomicity)**:
   - Tests **one** single fact, mechanism, boundary, or contrast per card.
   - **Red flag — Hidden Multi-Part Cards**: A Q&A prompt asking *"What two/three things… AND how does X compare to Y?"* or cramming two distinct legal definitions into a single `Back` (forcing you to fail the entire card when you forget half). Split these into separate atomic notes!
2. **Precise (Unambiguous Target)**:
   - Narrowed until **only** the intended answer qualifies.
   - **Red flag — Vague Prompts**: *"What factors matter for X?"* or *"How does X work?"* without specifying the legal dimension (fault, causation, harm, burden, standard).
3. **Consistent & Tractable (< 10-Second Grading)**:
   - Activates the same mental target on every review and can be graded cleanly in under 10 seconds.
   - **Red flag — Overloaded Back**: `Back` should be 1–2 crisp clauses (ideally ≤ 25–30 words). Move examples, comparisons, and secondary nuance to `Why_Extra`.
4. **Effortful (No Giveaways or Guessing)**:
   - Zero binary Yes/No or Either/Or prompts.
   - Zero answer leakage inside `Context` or the prompt wording (e.g., don't put the answer word inside the question or cloze surrounding text).
5. **Cloze & Reverse Hygiene**:
   - **Tight Cloze**: Short original sentence; each `{{cN::...}}` blanks 1–3 load-bearing words (never whole multi-clause definitions); separate `c1`/`c2`/`c3` indices do not trivially give away each other; avoid cramming 3 unrelated facts if 2 atomic Q&A cards would transfer better.
   - **Bidirectional (`add_reverse: true`)**: When flipped (`Back` shown as prompt → recall `Front`), the `Back` must unambiguously identify a single term (no accidental ambiguity with a sibling tort!) and must NOT leak the term name inside `Back`.
6. **Signaling (Mayer's Principle)**:
   - Bold **only the single most critical word or distinction** (1–2 bold spans max per field). Bold everywhere highlights nothing.

---

## Pillar 3: Transfer, Discriminative Contrast & Exam Salience

Facts alone produce brittle recall (Pan & Rickard, 2018). The deck must actively train transfer across Matuschak's five conceptual lenses:

1. **Discriminative Contrast for Confusable Pairs**:
   - Every easily confused pair across the deck has an explicit contrast card (e.g., Battery vs. Assault; IIMS vs. Internet Harassment vs. Common-Law Harassment; BC Statutory Privacy vs. ONT Intrusion upon Seclusion vs. Public Disclosure; Conversion vs. Mere Moving/Use; Continuing Trespass vs. Consequence of Trespass; Unlawful Means vs. Inducing Breach of Contract; Fraud Recklessness vs. Negligence; IPV Coercive Control Intent vs. IIMS Intent).
2. **Cue Distinctiveness (Anti-Fan-Effect)**:
   - Every card has a crisp, scannable `Context` header that narrows the mental search space without giving away the answer.
   - No two cards in the deck share near-identical fronts that could collide in memory.
3. **Significance & Salience (Micro Fact-Pattern Application)**:
   - High-yield boundary rules should include concrete 1-sentence **issue-spotting / application prompts** (e.g., *"D points an unloaded gun at P, who believes it is loaded—why does this still satisfy assault's intent element?"* or *"D digs a trench while trespassing and leaves—why is this NOT a continuing trespass?"*) so rules fire on real law-school exam fact patterns, not just abstract terminology.
4. **Cluster Integrity**:
   - Every topic cluster (`topic::torts::*`) has **≥ 3 interconnected cards** spanning multiple lenses (zero orphan trivia).

---

## Severity Levels for Review Findings

- **P0 (Must Fix)**: Factual/legal inaccuracy, missed source card element, broken reverse card (leaks answer or ambiguous reverse), binary yes/no prompt, or answer leakage.
- **P1 (High Impact)**: Hidden multi-part card that should be split for true atomicity, vague prompt permitting multiple valid answers, bloated `Back` (> 30 words) or excessive bolding, oversized cloze blank, or missing high-yield contrast/application card.
- **P2 (Polish)**: Tighter wording, sharper `Context` prefix, richer `Why_Extra` example/mnemonic, or minor tag/source cleanup.
