# feli-flash

Tooling to build, audit, preview, and package shareable **Evidence-Based Anki (`.apkg`)** flashcard decks from clean YAML or JSON specs.

## Architecture (Evidence-Based Anki Specification)

- **Flat deck, rich hierarchical `::` tags**: Preserves natural cross-topic interleaving without subdeck title giveaways.
- **Two custom note types**:
  - **Evidence-Based Q&A**: `Context` (sticky), `Front`, `Back`, `Why_Extra`, `Visual`, `Source_Date` (sticky), `Add_Reverse` (gates Card 2 reverse recall; `Visual` is kept off reverse fronts).
  - **Evidence-Based Cloze**: `Context` (sticky), `Text`, `Why_Extra`, `Visual`, `Source_Date` (sticky).
- **Readability CSS**: Native system sans-serif stack, centered `650px` left-aligned reading column, `19px` font size, `1.6` line height, minimal front template, subtle separated `Why_Extra` box, dark-mode support.
- **Automated QA Acceptance Gates (`feli-flash audit`)**: Enforces atomicity (no "List all N" dumps or bloated paragraphs), anti-pattern-matching (no binary yes/no prompts or oversized cloze blanks), cue hygiene (`Context` required), transfer/contrast coverage, and topic cluster size (`>= 3` cards per topic).
- **Deterministic note GUIDs**: Emailing an updated `.apkg` updates existing cards in place without duplicating them or losing review history.

## Usage

```bash
# Audit against Evidence-Based QA Acceptance Gates
uv run feli-flash audit decks/tort-law.yaml --strict

# Build a shareable .apkg + standalone browser preview
uv run feli-flash build decks/tort-law.yaml -o dist/tort-law.apkg --preview dist/tort-law-preview.html --strict

# Inspect / verify any .apkg SQLite DB and media links
uv run feli-flash inspect dist/tort-law.apkg
```

## Recommended Anki Settings (Anki 25.07+ / FSRS-6)

After importing the `.apkg`, apply these preset settings (`Gear Icon > Options`):

- **FSRS**: Enabled (Global)
- **Desired Retention**: `0.85–0.90` (up to `0.93` for high-stakes exams)
- **Learning & Relearning Steps**: `10m` or `15m` (strictly `< 1d`)
- **Sibling Burying**: **All 3 options ON** (New, Review, Interday learning)
- **New Cards / Day**: `10` (starting pace) · **Max Reviews / Day**: `9999` (uncapped)
- **New Cards Ignore Review Limit**: Off
- **Leech Threshold**: `6–8` lapses → **Suspend Card**
- **Grading**: Never press **Hard** on a forgotten or partial recall — press **Again**.
