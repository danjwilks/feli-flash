"""Automated QA Acceptance Gate auditing based on the Evidence-Based Anki Spec."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from feli_flash.schema import CLOZE_PATTERN, DeckSpec

# Binary yes/no prompt starter pattern (Anti-Pattern-Matching Gate)
_BINARY_PROMPT_RE = re.compile(
    r"^(is|are|was|were|do|does|did|can|could|should|will|would|must|has|have|had)\b.+\?$",
    re.IGNORECASE,
)
_TRUE_FALSE_RE = re.compile(r"\b(true\s+or\s+false|yes\s+or\s+no)\b", re.IGNORECASE)
_LIST_ALL_RE = re.compile(r"\b(list|name|state)\s+all\s+\d+\b", re.IGNORECASE)
_CONTRAST_OR_WHY_RE = re.compile(
    r"\b(why|how|differ|distinguish|contrast|versus|vs\.?|compare|fails?\s+if|instead\s+of)\b",
    re.IGNORECASE,
)
_BOLD_SPAN_RE = re.compile(r"\*\*.+?\*\*")


@dataclass
class AuditFinding:
    """Single QA gate finding."""

    gate: str
    severity: str  # "error" or "warning"
    card_ref: str
    message: str


@dataclass
class AuditReport:
    """Results across all Evidence-Based Specification QA gates."""

    note_count: int
    qa_count: int
    cloze_count: int
    reverse_count: int
    transfer_prompt_count: int
    topic_clusters: dict[str, int]
    findings: list[AuditFinding] = field(default_factory=list)

    @property
    def errors(self) -> list[AuditFinding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[AuditFinding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def passed(self) -> bool:
        return not self.errors


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _check_reverse_context_leakage(context: str, front: str) -> str | None:
    """Detect if a reversed card's Context leaks the bolded target term from Front."""
    ctx_lower = context.lower()
    for match in _BOLD_SPAN_RE.finditer(front):
        term = match.group(0).strip("*").strip().lower()
        if len(term) >= 4 and term in ctx_lower:
            return term
    return None


def audit_deck_spec(
    spec: DeckSpec,
    *,
    max_back_words: int = 35,
    max_cloze_words: int = 4,
    max_bold_spans: int = 2,
) -> AuditReport:
    """Audit a DeckSpec against the Pre-Launch QA Acceptance Gates & Review Criteria."""
    findings: list[AuditFinding] = []
    topic_counter: Counter[str] = Counter()
    qa_count = 0
    cloze_count = 0
    reverse_count = 0
    transfer_prompt_count = 0
    subdecks_used: set[str] = set()

    for idx, card in enumerate(spec.cards, start=1):
        ref = card.id or f"card #{idx}"

        if card.subdeck:
            subdecks_used.add(card.subdeck)

        # Cue & Visual Hygiene Gate: require short Context prefix
        if not card.context:
            findings.append(
                AuditFinding(
                    gate="Cue Hygiene",
                    severity="error",
                    card_ref=ref,
                    message="Missing 'context' prefix (required to prevent cross-topic cue overload).",
                )
            )
        elif len(card.context) > 65:
            findings.append(
                AuditFinding(
                    gate="Cue Hygiene",
                    severity="warning",
                    card_ref=ref,
                    message=f"Context prefix is long ({len(card.context)} chars); keep it concise.",
                )
            )

        card_topics = [t for t in card.tags if t.startswith("topic::")]
        for topic in card_topics:
            topic_counter[topic] += 1

        if card.card_type == "qa":
            qa_count += 1
            if card.add_reverse:
                reverse_count += 1
                leaked = _check_reverse_context_leakage(card.context, card.front)
                if leaked:
                    findings.append(
                        AuditFinding(
                            gate="Reverse Hygiene",
                            severity="error",
                            card_ref=ref,
                            message=(
                                f"Reversed card leaks target '{leaked}' inside Context ('{card.context}'). "
                                "Use a broader category context so Card 2 doesn't give away the answer."
                            ),
                        )
                    )

            front_stripped = card.front.strip()
            if _BINARY_PROMPT_RE.match(front_stripped) or _TRUE_FALSE_RE.search(front_stripped):
                findings.append(
                    AuditFinding(
                        gate="Anti-Pattern-Matching",
                        severity="error",
                        card_ref=ref,
                        message=f"Binary yes/no prompt detected: '{front_stripped}' — rephrase to require active production.",
                    )
                )

            if _LIST_ALL_RE.search(front_stripped):
                findings.append(
                    AuditFinding(
                        gate="Atomicity",
                        severity="error",
                        card_ref=ref,
                        message=f"'List all N' prompt anti-pattern detected: '{front_stripped}' — decompose into atomic cards.",
                    )
                )

            back_words = _word_count(card.back)
            if back_words > max_back_words:
                findings.append(
                    AuditFinding(
                        gate="Atomicity",
                        severity="warning",
                        card_ref=ref,
                        message=f"Back answer has {back_words} words (target <= {max_back_words}); move elaboration into 'why_extra'.",
                    )
                )
            if "\n\n" in card.back:
                findings.append(
                    AuditFinding(
                        gate="Atomicity",
                        severity="warning",
                        card_ref=ref,
                        message="Back answer has multiple paragraphs; keep graded Back to 1-2 crisp clauses and put details in 'why_extra'.",
                    )
                )

            # Signaling hygiene (Mayer): bold only the single most critical word/distinction
            for field_name, field_val in (("front", card.front), ("back", card.back)):
                bold_count = len(_BOLD_SPAN_RE.findall(field_val))
                if bold_count > max_bold_spans:
                    findings.append(
                        AuditFinding(
                            gate="Signaling Hygiene",
                            severity="warning",
                            card_ref=ref,
                            message=f"'{field_name}' has {bold_count} bold spans (target <= {max_bold_spans}); bold only the key distinction.",
                        )
                    )

            if _CONTRAST_OR_WHY_RE.search(front_stripped):
                transfer_prompt_count += 1
        else:
            cloze_count += 1
            if _CONTRAST_OR_WHY_RE.search(card.text):
                transfer_prompt_count += 1

            for match in CLOZE_PATTERN.finditer(card.text):
                payload = match.group(2).split("::")[0]
                words = _word_count(payload)
                if words > max_cloze_words:
                    findings.append(
                        AuditFinding(
                            gate="Anti-Pattern-Matching",
                            severity="warning",
                            card_ref=ref,
                            message=f"Cloze deletion {{{{c{match.group(1)}::...}}}} blanks {words} words (target <= {max_cloze_words}); tighten to core load-bearing phrase.",
                        )
                    )

            if _word_count(card.text) > 35:
                findings.append(
                    AuditFinding(
                        gate="Atomicity",
                        severity="warning",
                        card_ref=ref,
                        message="Cloze sentence exceeds 35 words; rewrite into a compact standalone sentence.",
                    )
                )

    if subdecks_used:
        findings.append(
            AuditFinding(
                gate="Deck Architecture",
                severity="warning",
                card_ref="deck",
                message=(
                    f"Subdecks used ({', '.join(sorted(subdecks_used))}). "
                    "Spec recommends a flat broad deck with hierarchical '::' tags to preserve interleaving."
                ),
            )
        )

    for topic, count in sorted(topic_counter.items()):
        if count < 3:
            findings.append(
                AuditFinding(
                    gate="Transfer & Cluster",
                    severity="warning",
                    card_ref=topic,
                    message=f"Topic cluster '{topic}' has only {count} card(s); aim for a nucleus of 3-5+ interconnected cards.",
                )
            )

    if len(spec.cards) >= 5 and transfer_prompt_count == 0:
        findings.append(
            AuditFinding(
                gate="Transfer & Cluster",
                severity="warning",
                card_ref="deck",
                message="No 'why/how' or compare-and-contrast prompts detected; add elaborative cards for transfer.",
            )
        )

    return AuditReport(
        note_count=len(spec.cards),
        qa_count=qa_count,
        cloze_count=cloze_count,
        reverse_count=reverse_count,
        transfer_prompt_count=transfer_prompt_count,
        topic_clusters=dict(sorted(topic_counter.items())),
        findings=findings,
    )
