"""Generate a standalone interactive HTML preview of an Evidence-Based Anki deck."""

from __future__ import annotations

import base64
import html
import mimetypes
import re
import tempfile
from pathlib import Path

from feli_flash.audit import audit_deck_spec
from feli_flash.media import MediaBundler
from feli_flash.rendering import render_markdown
from feli_flash.schema import CLOZE_PATTERN, CardSpec, DeckSpec
from feli_flash.templates import DEFAULT_CSS

_CLOZE_RENDER_RE = re.compile(r"\{\{c(\d+)::([^:}]+?)(?:::([^}]+?))?\}\}", re.DOTALL)


def _inline_image_data_uri(bundler: MediaBundler, raw_path: str | None) -> str:
    if not raw_path:
        return ""
    prepared = bundler.resolve(raw_path)
    mime, _ = mimetypes.guess_type(prepared.packaged_path.name)
    mime = mime or "image/jpeg"
    b64 = base64.b64encode(prepared.packaged_path.read_bytes()).decode("ascii")
    return f'<div class="eb-visual"><img src="data:{mime};base64,{b64}" alt="Card visual"></div>'


def _render_cloze_question(text_html: str) -> str:
    def _mask(match: re.Match[str]) -> str:
        hint = match.group(3)
        label = f"[{hint}]" if hint else "[...]"
        return f'<span class="cloze">{label}</span>'

    return _CLOZE_RENDER_RE.sub(_mask, text_html)


def _render_cloze_answer(text_html: str) -> str:
    def _reveal(match: re.Match[str]) -> str:
        return f'<span class="cloze">{match.group(2)}</span>'

    return _CLOZE_RENDER_RE.sub(_reveal, text_html)


def _card_count(card: CardSpec) -> int:
    if card.card_type == "qa":
        return 2 if card.add_reverse else 1
    return max(1, len({m.group(1) for m in CLOZE_PATTERN.finditer(card.text)}))


def _render_card_pair(card: CardSpec, index: int, bundler: MediaBundler, default_tags: list[str]) -> str:
    tags = list(dict.fromkeys([*default_tags, *card.tags]))
    tags_attr = html.escape(" ".join(tags), quote=True)
    topic_tags = [t for t in tags if t.startswith("topic::")]
    lens_tags = [t for t in tags if t.startswith("lens::")]
    topic_attr = html.escape(" ".join(topic_tags), quote=True)
    lens_attr = html.escape(" ".join(lens_tags), quote=True)

    context_html = f'<div class="eb-context">{html.escape(card.context)}</div>' if card.context else ""
    why_html = (
        f'<div class="eb-why-extra"><div class="eb-why-label">Why / Elaboration</div>'
        f'<div>{render_markdown(card.why_extra)}</div></div>'
        if card.why_extra
        else ""
    )
    visual_html = _inline_image_data_uri(bundler, card.visual)
    source_html = f'<div class="eb-source">{html.escape(card.source_date)}</div>' if card.source_date else ""

    if card.card_type == "qa":
        front_body = render_markdown(card.front)
        back_body = render_markdown(card.back)
        front_panel = f"""
          <div class="pv-card-shell">
            <div class="eb-column">
              {context_html}
              <div class="eb-front">{front_body}</div>
            </div>
          </div>"""
        back_panel = f"""
          <div class="pv-card-shell">
            <div class="eb-column">
              {context_html}
              <div class="eb-front">{front_body}</div>
              <hr class="eb-divider">
              <div class="eb-back">{back_body}</div>
              {why_html}
              {visual_html}
              {source_html}
            </div>
          </div>"""
    else:
        rendered = render_markdown(card.text, preserve_cloze=True)
        front_panel = f"""
          <div class="pv-card-shell">
            <div class="eb-column">
              {context_html}
              <div class="eb-front">{_render_cloze_question(rendered)}</div>
            </div>
          </div>"""
        back_panel = f"""
          <div class="pv-card-shell">
            <div class="eb-column">
              {context_html}
              <div class="eb-back">{_render_cloze_answer(rendered)}</div>
              {why_html}
              {visual_html}
              {source_html}
            </div>
          </div>"""

    badges = [f'<span class="pv-badge">{html.escape(card.card_type)}</span>']
    if card.add_reverse:
        badges.append('<span class="pv-badge pv-badge-rev">+ Reverse</span>')
    n_cards = _card_count(card)
    if n_cards > 1:
        badges.append(f'<span class="pv-badge">{n_cards} cards</span>')
    tag_pills = "".join(f'<span class="pv-tag">#{html.escape(t)}</span>' for t in tags)

    return f"""
    <article class="pv-item" data-topic="{topic_attr}" data-lens="{lens_attr}" data-tags="{tags_attr}" data-type="{html.escape(card.card_type)}">
      <header class="pv-meta">
        <span class="pv-index">Note {index}</span>
        {''.join(badges)}
        <div class="pv-tags">{tag_pills}</div>
      </header>
      <div class="pv-grid">
        <section class="pv-side pv-side-front">
          <div class="pv-side-label">Front</div>
          {front_panel}
        </section>
        <section class="pv-side pv-side-back">
          <div class="pv-side-label">Back</div>
          {back_panel}
        </section>
      </div>
      <div class="pv-study-actions">
        <button class="pv-reveal-btn" type="button">Show Answer</button>
      </div>
    </article>"""


def generate_preview_html(
    spec: DeckSpec,
    output_path: str | Path,
    *,
    apkg_href: str | None = None,
) -> Path:
    """Render an interactive standalone HTML preview for reviewing or test-driving cards."""
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    audit = audit_deck_spec(spec)
    total_cards = sum(_card_count(c) for c in spec.cards)

    with tempfile.TemporaryDirectory(prefix="feli_flash_preview_") as tmpdir:
        bundler = MediaBundler(spec.base_dir, Path(tmpdir))
        rendered_items = [
            _render_card_pair(card, idx, bundler, spec.default_tags)
            for idx, card in enumerate(spec.cards, start=1)
        ]

    topics = sorted(audit.topic_clusters.keys())
    topic_options = "".join(
        f'<option value="{html.escape(t, quote=True)}">{html.escape(t.replace("topic::torts::", "").replace("_", " ").title())} ({audit.topic_clusters[t]})</option>'
        for t in topics
    )

    lens_counts: dict[str, int] = {}
    for card in spec.cards:
        for tag in card.tags:
            if tag.startswith("lens::"):
                lens_counts[tag] = lens_counts.get(tag, 0) + 1
    lens_options = "".join(
        f'<option value="{html.escape(l, quote=True)}">{html.escape(l.replace("lens::", "").title())} ({lens_counts[l]})</option>'
        for l in sorted(lens_counts.keys())
    )

    download_btn = (
        f'<a class="pv-download-btn" href="{html.escape(apkg_href, quote=True)}" download>Download .apkg</a>'
        if apkg_href
        else ""
    )

    qa_status = (
        f"QA Gates: PASS ({len(audit.warnings)} warnings)"
        if audit.passed
        else f"QA Gates: {len(audit.errors)} error(s), {len(audit.warnings)} warning(s)"
    )

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(spec.name)} — Anki Deck Preview</title>
  <style>
    {DEFAULT_CSS}
    {spec.css}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      background: #f1f5f9;
      color: #0f172a;
    }}
    body.nightMode {{
      background: #0d1016;
      color: #e2e8f0;
    }}
    .pv-toolbar {{
      position: sticky;
      top: 0;
      z-index: 10;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
      padding: 14px 24px;
      background: rgba(255, 255, 255, 0.94);
      backdrop-filter: blur(8px);
      border-bottom: 1px solid #e2e8f0;
    }}
    body.nightMode .pv-toolbar {{
      background: rgba(18, 22, 30, 0.94);
      border-color: #262c38;
    }}
    .pv-title {{ font-size: 18px; font-weight: 700; margin: 0; }}
    .pv-subtitle {{ font-size: 13px; color: #64748b; margin-top: 2px; }}
    .pv-controls {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    .pv-controls input, .pv-controls select, .pv-controls button, .pv-download-btn {{
      font-size: 14px;
      padding: 6px 11px;
      border-radius: 8px;
      border: 1px solid #cbd5e1;
      background: #fff;
      color: #0f172a;
      text-decoration: none;
    }}
    body.nightMode .pv-controls input,
    body.nightMode .pv-controls select,
    body.nightMode .pv-controls button {{
      background: #1a1f2b;
      border-color: #334155;
      color: #e2e8f0;
    }}
    .pv-controls button {{ cursor: pointer; font-weight: 600; }}
    .pv-controls button.active {{
      background: #1d4ed8;
      border-color: #1d4ed8;
      color: #ffffff;
    }}
    .pv-download-btn {{
      background: #0f766e;
      border-color: #0f766e;
      color: #ffffff;
      font-weight: 600;
    }}
    .pv-download-btn:hover {{ background: #115e59; }}
    .pv-banner {{
      max-width: 1320px;
      margin: 18px auto 0;
      padding: 12px 18px;
      border-radius: 10px;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      font-size: 13.5px;
      color: #334155;
      line-height: 1.5;
    }}
    body.nightMode .pv-banner {{
      background: #171b24;
      border-color: #2a3140;
      color: #cbd5e1;
    }}
    .pv-count {{
      max-width: 1320px;
      margin: 14px auto 0;
      padding: 0 20px;
      font-size: 13px;
      color: #64748b;
    }}
    .pv-container {{ max-width: 1320px; margin: 14px auto; padding: 0 20px 60px; }}
    .pv-item {{ margin-bottom: 28px; }}
    .pv-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-bottom: 10px;
      font-size: 13px;
    }}
    .pv-index {{ font-weight: 700; }}
    .pv-badge {{
      padding: 2px 8px;
      border-radius: 999px;
      background: #e2e8f0;
      color: #334155;
      font-weight: 600;
      text-transform: uppercase;
      font-size: 11px;
    }}
    .pv-badge-rev {{ background: #dbeafe; color: #1d4ed8; }}
    body.nightMode .pv-badge {{ background: #262e3d; color: #cbd5e1; }}
    body.nightMode .pv-badge-rev {{ background: #1e3a5f; color: #93c5fd; }}
    .pv-tags {{ display: flex; gap: 6px; flex-wrap: wrap; }}
    .pv-tag {{ font-size: 12px; color: #475569; }}
    body.nightMode .pv-tag {{ color: #94a3b8; }}
    .pv-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      align-items: start;
    }}
    .pv-side-label {{
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #64748b;
      margin-bottom: 6px;
    }}
    .pv-card-shell {{
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 22px 24px;
    }}
    body.nightMode .pv-card-shell {{
      background: #14171f;
      border-color: #2a3140;
    }}
    .pv-study-actions {{ display: none; margin-top: 10px; }}
    .pv-reveal-btn {{
      font-size: 13.5px;
      font-weight: 600;
      padding: 7px 14px;
      border-radius: 8px;
      border: 1px solid #cbd5e1;
      background: #ffffff;
      color: #1d4ed8;
      cursor: pointer;
    }}
    body.nightMode .pv-reveal-btn {{
      background: #1a1f2b;
      border-color: #334155;
      color: #93c5fd;
    }}
    /* Study / Flip Mode hides backs until revealed */
    body.study-mode .pv-item:not(.revealed) .pv-side-back {{ display: none; }}
    body.study-mode .pv-item.revealed .pv-side-front {{ display: none; }}
    body.study-mode .pv-study-actions {{ display: block; }}
    body.study-mode .pv-grid {{ grid-template-columns: minmax(320px, 740px); }}
  </style>
</head>
<body>
  <div class="pv-toolbar">
    <div>
      <h1 class="pv-title">{html.escape(spec.name)} — {len(spec.cards)} notes ({total_cards} cards)</h1>
      <div class="pv-subtitle">{html.escape(qa_status)} · Q&amp;A: {audit.qa_count} (Reverse: {audit.reverse_count}) · Cloze: {audit.cloze_count}</div>
    </div>
    <div class="pv-controls">
      <input id="search" type="search" placeholder="Search cards or tags...">
      <select id="topicFilter">
        <option value="">All topics ({len(spec.cards)})</option>
        {topic_options}
      </select>
      <select id="lensFilter">
        <option value="">All lenses</option>
        {lens_options}
      </select>
      <select id="typeFilter">
        <option value="">All types</option>
        <option value="qa">Q&amp;A</option>
        <option value="cloze">Cloze</option>
      </select>
      <button id="studyToggle" type="button">Study Mode</button>
      <button id="themeToggle" type="button">Dark Mode</button>
      {download_btn}
    </div>
  </div>
  <div class="pv-banner">
    <strong>Recommended Anki FSRS-6 Settings (Anki 25.07+):</strong>
    Enable <strong>FSRS</strong> globally · Desired Retention <strong>0.85–0.90</strong> · Learning &amp; Relearning Steps <strong>10m</strong> or <strong>15m</strong> (strictly &lt; 1d) ·
    <strong>All 3 Sibling-Burying options ON</strong> (New, Review, Interday) · New Cards/Day <strong>10</strong> · Max Reviews/Day <strong>9999</strong> · Leech Threshold <strong>6–8 lapses → Suspend</strong> · Never press <em>Hard</em> on a forgotten card.
  </div>
  <div class="pv-count" id="visibleCount">Showing {len(spec.cards)} of {len(spec.cards)} notes</div>
  <main class="pv-container" id="cards">
    {''.join(rendered_items)}
  </main>
  <script>
    const search = document.getElementById('search');
    const topicFilter = document.getElementById('topicFilter');
    const lensFilter = document.getElementById('lensFilter');
    const typeFilter = document.getElementById('typeFilter');
    const studyToggle = document.getElementById('studyToggle');
    const themeToggle = document.getElementById('themeToggle');
    const visibleCount = document.getElementById('visibleCount');
    const items = Array.from(document.querySelectorAll('.pv-item'));

    function applyFilter() {{
      const q = search.value.trim().toLowerCase();
      const tp = topicFilter.value;
      const ln = lensFilter.value;
      const ty = typeFilter.value;
      let shown = 0;
      for (const el of items) {{
        const matchTopic = !tp || el.dataset.topic.split(' ').includes(tp);
        const matchLens = !ln || el.dataset.lens.split(' ').includes(ln);
        const matchType = !ty || el.dataset.type === ty;
        const matchText = !q || el.innerText.toLowerCase().includes(q) || el.dataset.tags.toLowerCase().includes(q);
        const visible = matchTopic && matchLens && matchType && matchText;
        el.style.display = visible ? '' : 'none';
        if (visible) shown++;
      }}
      visibleCount.textContent = `Showing ${{shown}} of ${{items.length}} notes`;
    }}

    search.addEventListener('input', applyFilter);
    topicFilter.addEventListener('change', applyFilter);
    lensFilter.addEventListener('change', applyFilter);
    typeFilter.addEventListener('change', applyFilter);

    studyToggle.addEventListener('click', () => {{
      const on = document.body.classList.toggle('study-mode');
      studyToggle.classList.toggle('active', on);
      studyToggle.textContent = on ? 'Proofread Mode' : 'Study Mode';
      if (!on) {{
        for (const el of items) {{
          el.classList.remove('revealed');
          const btn = el.querySelector('.pv-reveal-btn');
          if (btn) btn.textContent = 'Show Answer';
        }}
      }}
    }});

    for (const el of items) {{
      const btn = el.querySelector('.pv-reveal-btn');
      if (btn) {{
        btn.addEventListener('click', () => {{
          const revealed = el.classList.toggle('revealed');
          btn.textContent = revealed ? 'Hide Answer' : 'Show Answer';
        }});
      }}
    }}

    themeToggle.addEventListener('click', () => {{
      const dark = document.body.classList.toggle('nightMode');
      themeToggle.textContent = dark ? 'Light Mode' : 'Dark Mode';
    }});
  </script>
</body>
</html>
"""
    out.write_text(page, encoding="utf-8")
    return out
