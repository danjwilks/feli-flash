"""Evidence-Based Anki note types (Q&A + Optional Reverse, Cloze) and readability CSS.

Implements Stage 3 of the Evidence-Based Anki Deck Specification:
- Two custom note types: Evidence-Based Q&A and Evidence-Based Cloze
- Exact dedicated fields: Context, Front/Text, Back, Why_Extra, Visual, Source_Date, Add_Reverse
- Minimal Front (only muted Context above Front/Text) to minimize extraneous cognitive load
- Optional Reverse gated on Add_Reverse (Visual never placed on reverse front)
- Cross-platform native sans-serif stack, centered 650px column, left-aligned, 19px, line-height 1.6
"""

from __future__ import annotations

import genanki

from feli_flash.rendering import stable_int_id

DEFAULT_CSS = """\
.card {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
  font-size: 19px;
  line-height: 1.6;
  color: #1a1f2e;
  background-color: #ffffff;
  text-align: left;
  margin: 0;
  padding: 24px 18px;
}

.eb-column {
  max-width: 650px;
  margin: 0 auto;
}

.eb-context {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #64748b;
  margin-bottom: 10px;
}

.eb-front {
  font-size: 19px;
  font-weight: 500;
  color: #111827;
}

.eb-divider {
  border: none;
  border-top: 1px solid #e2e8f0;
  margin: 20px 0;
}

.eb-back {
  font-size: 19px;
  font-weight: 400;
  color: #0f172a;
}

.eb-back ol,
.eb-back ul {
  margin: 0;
  padding-left: 24px;
}

.eb-back li {
  margin-bottom: 6px;
}

.eb-back li:last-child {
  margin-bottom: 0;
}

.eb-why-extra {
  margin-top: 20px;
  padding: 12px 16px;
  background-color: #f8fafc;
  border-left: 3px solid #94a3b8;
  border-radius: 0 6px 6px 0;
  font-size: 15.5px;
  line-height: 1.55;
  color: #334155;
}

.eb-why-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #64748b;
  margin-bottom: 4px;
}

.eb-visual {
  margin-top: 18px;
}

.eb-visual img {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

.eb-source {
  margin-top: 22px;
  font-size: 12.5px;
  color: #94a3b8;
}

.cloze {
  font-weight: 700;
  color: #1d4ed8;
}

strong, b {
  font-weight: 700;
}

/* Anki dark mode support */
.nightMode .card,
.night_mode .card,
.card.nightMode,
.card.night_mode {
  color: #e2e8f0;
  background-color: #14171f;
}

.nightMode .eb-context,
.night_mode .eb-context {
  color: #94a3b8;
}

.nightMode .eb-front,
.night_mode .eb-front,
.nightMode .eb-back,
.night_mode .eb-back {
  color: #f1f5f9;
}

.nightMode .eb-divider,
.night_mode .eb-divider {
  border-top-color: #2a3140;
}

.nightMode .eb-why-extra,
.night_mode .eb-why-extra {
  background-color: #1c212c;
  border-left-color: #64748b;
  color: #cbd5e1;
}

.nightMode .eb-why-label,
.night_mode .eb-why-label {
  color: #94a3b8;
}

.nightMode .eb-visual img,
.night_mode .eb-visual img {
  border-color: #2a3140;
}

.nightMode .eb-source,
.night_mode .eb-source {
  color: #64748b;
}

.nightMode .cloze,
.night_mode .cloze {
  color: #93c5fd;
}
"""


def _compose_css(extra_css: str = "") -> str:
    if extra_css.strip():
        return f"{DEFAULT_CSS}\n\n/* Custom deck CSS */\n{extra_css.strip()}\n"
    return DEFAULT_CSS


def build_qa_model(deck_namespace: str, extra_css: str = "") -> genanki.Model:
    """Custom Q&A note type with Optional Reverse gated on Add_Reverse."""
    return genanki.Model(
        stable_int_id("feli-flash-eb-qa", deck_namespace),
        f"Evidence-Based Q&A ({deck_namespace})",
        fields=[
            {"name": "Context", "sticky": True},
            {"name": "Front"},
            {"name": "Back"},
            {"name": "Why_Extra"},
            {"name": "Visual"},
            {"name": "Source_Date", "sticky": True},
            {"name": "Add_Reverse"},
        ],
        templates=[
            {
                "name": "Forward",
                "qfmt": """\
<div class="eb-column">
  {{#Context}}<div class="eb-context">{{Context}}</div>{{/Context}}
  <div class="eb-front">{{Front}}</div>
</div>""",
                "afmt": """\
<div class="eb-column">
  {{#Context}}<div class="eb-context">{{Context}}</div>{{/Context}}
  <div class="eb-front">{{Front}}</div>
  <hr class="eb-divider" id="answer">
  <div class="eb-back">{{Back}}</div>
  {{#Why_Extra}}
    <div class="eb-why-extra">
      <div class="eb-why-label">Why / Elaboration</div>
      <div>{{Why_Extra}}</div>
    </div>
  {{/Why_Extra}}
  {{#Visual}}<div class="eb-visual">{{Visual}}</div>{{/Visual}}
  {{#Source_Date}}<div class="eb-source">{{Source_Date}}</div>{{/Source_Date}}
</div>""",
            },
            {
                "name": "Reverse",
                "qfmt": """\
{{#Add_Reverse}}
<div class="eb-column">
  {{#Context}}<div class="eb-context">{{Context}}</div>{{/Context}}
  <div class="eb-front">{{Back}}</div>
</div>
{{/Add_Reverse}}""",
                "afmt": """\
<div class="eb-column">
  {{#Context}}<div class="eb-context">{{Context}}</div>{{/Context}}
  <div class="eb-front">{{Back}}</div>
  <hr class="eb-divider" id="answer">
  <div class="eb-back">{{Front}}</div>
  {{#Why_Extra}}
    <div class="eb-why-extra">
      <div class="eb-why-label">Why / Elaboration</div>
      <div>{{Why_Extra}}</div>
    </div>
  {{/Why_Extra}}
  {{#Visual}}<div class="eb-visual">{{Visual}}</div>{{/Visual}}
  {{#Source_Date}}<div class="eb-source">{{Source_Date}}</div>{{/Source_Date}}
</div>""",
            },
        ],
        css=_compose_css(extra_css),
    )


def build_cloze_model(deck_namespace: str, extra_css: str = "") -> genanki.Model:
    """Custom Cloze note type matching the Evidence-Based field schema."""
    return genanki.Model(
        stable_int_id("feli-flash-eb-cloze", deck_namespace),
        f"Evidence-Based Cloze ({deck_namespace})",
        model_type=genanki.Model.CLOZE,
        fields=[
            {"name": "Context", "sticky": True},
            {"name": "Text"},
            {"name": "Why_Extra"},
            {"name": "Visual"},
            {"name": "Source_Date", "sticky": True},
        ],
        templates=[
            {
                "name": "Cloze",
                "qfmt": """\
<div class="eb-column">
  {{#Context}}<div class="eb-context">{{Context}}</div>{{/Context}}
  <div class="eb-front">{{cloze:Text}}</div>
</div>""",
                "afmt": """\
<div class="eb-column">
  {{#Context}}<div class="eb-context">{{Context}}</div>{{/Context}}
  <div class="eb-back">{{cloze:Text}}</div>
  {{#Why_Extra}}
    <div class="eb-why-extra">
      <div class="eb-why-label">Why / Elaboration</div>
      <div>{{Why_Extra}}</div>
    </div>
  {{/Why_Extra}}
  {{#Visual}}<div class="eb-visual">{{Visual}}</div>{{/Visual}}
  {{#Source_Date}}<div class="eb-source">{{Source_Date}}</div>{{/Source_Date}}
</div>""",
            }
        ],
        css=_compose_css(extra_css),
    )
