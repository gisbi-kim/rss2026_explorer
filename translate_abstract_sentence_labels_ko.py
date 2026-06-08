from __future__ import annotations

import csv
import html
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from label_abstract_sentences import LABELS, PROMPT_URL, label_style


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUTS_DIR = ROOT.parent.parent / "outputs"

SOURCE_JSON = DATA_DIR / "rss2026_abstract_sentence_labels.json"
CACHE_PATH = DATA_DIR / "translation_cache_en_ko.json"

JSON_OUTPUT = DATA_DIR / "rss2026_abstract_sentence_labels_ko.json"
CSV_OUTPUT = DATA_DIR / "rss2026_abstract_sentence_labels_ko.csv"
HTML_OUTPUT = ROOT / "abstract_sentence_labels_ko.html"

OUTPUT_HTML_COPY = OUTPUTS_DIR / "rss2026_abstract_sentence_labels_ko.html"
OUTPUT_JSON_COPY = OUTPUTS_DIR / "rss2026_abstract_sentence_labels_ko.json"
OUTPUT_CSV_COPY = OUTPUTS_DIR / "rss2026_abstract_sentence_labels_ko.csv"

TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
BREAK = "<<<RSS_SENTENCE_BREAK>>>"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def load_cache() -> dict[str, str]:
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def save_cache(cache: dict[str, str]) -> None:
    write_json(cache, CACHE_PATH)


def call_translate(text: str) -> str:
    query = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": "en",
            "tl": "ko",
            "dt": "t",
            "q": text,
        }
    )
    request = urllib.request.Request(
        f"{TRANSLATE_URL}?{query}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return "".join(part[0] for part in payload[0]).strip()


def translate_batch(texts: list[str], cache: dict[str, str]) -> None:
    missing = [text for text in texts if text and text not in cache]
    if not missing:
        return

    batches: list[list[str]] = []
    current: list[str] = []
    current_len = 0
    for text in missing:
        projected_len = current_len + len(text) + len(BREAK) + 2
        if current and (projected_len > 3800 or len(current) >= 18):
            batches.append(current)
            current = []
            current_len = 0
        current.append(text)
        current_len += len(text) + len(BREAK) + 2
    if current:
        batches.append(current)

    for index, batch in enumerate(batches, start=1):
        joined = f"\n{BREAK}\n".join(batch)
        translated = None
        for attempt in range(3):
            try:
                translated = call_translate(joined)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1.5 * (attempt + 1))
        assert translated is not None
        parts = [part.strip() for part in translated.split(BREAK)]
        if len(parts) != len(batch):
            # Fall back to one request per sentence when the service changes or drops separators.
            parts = []
            for text in batch:
                parts.append(call_translate(text).strip())
                time.sleep(0.08)
        for source, target in zip(batch, parts):
            cache[source] = target
        if index % 10 == 0:
            save_cache(cache)
        time.sleep(0.12)
    save_cache(cache)


def collect_texts(data: dict) -> list[str]:
    texts: list[str] = []
    for paper in data["papers"]:
        texts.append(str(paper["title"]))
        texts.append(str(paper["abstract"]))
        for sentence in paper["sentences"]:
            texts.append(str(sentence["sentence"]))
    seen: set[str] = set()
    unique: list[str] = []
    for text in texts:
        if text and text not in seen:
            seen.add(text)
            unique.append(text)
    return unique


def build_korean_data(data: dict, cache: dict[str, str]) -> dict:
    ko = json.loads(json.dumps(data, ensure_ascii=False))
    ko["metadata"]["title"] = "RSS 2026 abstract sentence labels Korean"
    ko["metadata"]["language"] = "ko"
    ko["metadata"]["translation_method"] = (
        "English RSS 2026 abstracts and labeled sentences were translated to Korean with a cached machine-translation pass; "
        "label assignment remains the original abstract-only rule-based primary label."
    )
    for paper in ko["papers"]:
        paper["title_en"] = paper["title"]
        paper["abstract_en"] = paper["abstract"]
        paper["title_ko"] = cache.get(str(paper["title"]), str(paper["title"]))
        paper["abstract_ko"] = cache.get(str(paper["abstract"]), str(paper["abstract"]))
        for sentence in paper["sentences"]:
            sentence["sentence_en"] = sentence["sentence"]
            sentence["sentence_ko"] = cache.get(str(sentence["sentence"]), str(sentence["sentence"]))
            sentence["sentence"] = sentence["sentence_ko"]
    return ko


def write_csv(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "paper_id",
                "title_ko",
                "title_en",
                "session",
                "sentence_index",
                "label_id",
                "label_name",
                "label_english",
                "confidence",
                "rule_reason",
                "sentence_ko",
                "sentence_en",
                "url",
            ]
        )
        for paper in data["papers"]:
            for sentence in paper["sentences"]:
                writer.writerow(
                    [
                        paper["id"],
                        paper["title_ko"],
                        paper["title_en"],
                        paper["session"],
                        sentence["sentence_index"],
                        sentence["label_id"],
                        sentence["label_name"],
                        sentence["label_english"],
                        sentence["confidence"],
                        sentence["rule_reason"],
                        sentence["sentence_ko"],
                        sentence["sentence_en"],
                        paper["href"],
                    ]
                )


def render_html(data: dict) -> str:
    metadata = data["metadata"]
    counts = metadata["label_counts"]
    nav = "\n".join(
        f'<a href="#paper-{paper["id"]}">#{html.escape(str(paper["id"]))} {html.escape(str(paper["title_ko"]))}</a>'
        for paper in data["papers"]
    )
    label_summary = "\n".join(
        f"""
        <div class="metric" style="{label_style(int(label['id']))}">
          <span>{int(label['id']):02d} {html.escape(str(label['name']))}</span>
          <strong>{counts[str(label['id'])]}</strong>
        </div>
        """
        for label in LABELS
    )
    paper_cards = "\n".join(render_paper(paper) for paper in data["papers"])
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RSS 2026 Abstract Sentence Labels Korean</title>
<style>
:root {{
  --bg: #f5f5f7;
  --panel: rgba(255, 255, 255, 0.9);
  --ink: #1d1d1f;
  --muted: #6e6e73;
  --line: #d2d2d7;
  --accent: #0071e3;
  --shadow: 0 18px 58px rgba(0, 0, 0, 0.08);
  --radius: 8px;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", "Pretendard", "Noto Sans KR", system-ui, sans-serif;
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  margin: 0;
  color: var(--ink);
  background: var(--bg);
  font-family: var(--font);
  line-height: 1.62;
  -webkit-font-smoothing: antialiased;
}}
a {{ color: inherit; }}
.shell {{
  width: min(1320px, calc(100% - 32px));
  margin: 0 auto;
}}
.hero {{
  padding: 56px 0 28px;
}}
.eyebrow {{
  color: var(--accent);
  font-size: 13px;
  font-weight: 850;
  text-transform: uppercase;
}}
h1 {{
  margin: 10px 0 12px;
  max-width: 1000px;
  font-size: clamp(34px, 5vw, 64px);
  line-height: 1.05;
  letter-spacing: 0;
}}
.subtitle {{
  max-width: 980px;
  color: var(--muted);
  font-size: 17px;
}}
.hero-meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}}
.chip, .source-chip {{
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 11px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.84);
  color: #334155;
  font-size: 12px;
  font-weight: 750;
  text-decoration: none;
}}
.chip.primary {{
  border-color: var(--accent);
  background: var(--accent);
  color: #fff;
}}
.metrics {{
  display: grid;
  grid-template-columns: repeat(13, minmax(88px, 1fr));
  gap: 8px;
  margin: 28px 0 18px;
}}
.metric {{
  min-height: 74px;
  padding: 10px;
  border: 1px solid color-mix(in srgb, var(--row-color), transparent 72%);
  border-left: 4px solid var(--row-color);
  border-radius: var(--radius);
  background: color-mix(in srgb, var(--row-color), white 92%);
}}
.metric span {{
  display: block;
  color: color-mix(in srgb, var(--row-color), black 28%);
  font-size: 11px;
  font-weight: 850;
}}
.metric strong {{
  display: block;
  margin-top: 4px;
  font-size: 24px;
}}
.nav-card {{
  position: sticky;
  top: 0;
  z-index: 10;
  margin: 22px 0 28px;
  padding: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.84);
  box-shadow: 0 10px 32px rgba(0, 0, 0, 0.05);
  backdrop-filter: blur(18px);
}}
.nav-title {{
  margin: 0 0 8px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 850;
  text-transform: uppercase;
}}
.paper-nav {{
  display: flex;
  gap: 7px;
  overflow-x: auto;
  padding-bottom: 4px;
}}
.paper-nav a {{
  flex: 0 0 auto;
  max-width: 280px;
  overflow: hidden;
  padding: 7px 10px;
  border-radius: 999px;
  background: #f5f5f7;
  color: #334155;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-decoration: none;
}}
.paper-nav a:hover {{
  background: rgba(0, 113, 227, 0.09);
  color: var(--accent);
}}
.paper-card {{
  margin: 0 0 20px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: var(--radius);
  background: var(--panel);
  box-shadow: var(--shadow);
}}
.paper-top {{
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 16px;
  padding: 20px;
  background: linear-gradient(180deg, #fff, #f7f8fb);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}}
.paper-number {{
  display: grid;
  width: 50px;
  height: 50px;
  place-items: center;
  border-radius: var(--radius);
  background: var(--accent);
  color: #fff;
  font-weight: 900;
}}
.paper-top h2 {{
  margin: 0;
  font-size: clamp(20px, 2.5vw, 32px);
  line-height: 1.2;
}}
.title-en {{
  margin-top: 7px;
  color: var(--muted);
  font-size: 13px;
}}
.paper-meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 10px;
}}
.paper-body {{
  padding: 18px 20px 22px;
}}
.abstract {{
  margin: 0 0 12px;
  color: #334155;
  font-size: 14px;
}}
.abstract-en {{
  margin: 0 0 16px;
  color: var(--muted);
  font-size: 12px;
}}
.summary-list {{
  display: flex;
  flex-direction: column;
  gap: 9px;
}}
.summary-row {{
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 11px 12px;
  border: 1px solid color-mix(in srgb, var(--row-color), transparent 78%);
  border-left: 4px solid var(--row-color);
  border-radius: var(--radius);
  background: color-mix(in srgb, var(--row-color), white 94%);
  transition: transform 150ms ease, box-shadow 150ms ease;
}}
.summary-row:hover {{
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.06);
}}
.row-index {{
  display: grid;
  flex: 0 0 auto;
  width: 38px;
  height: 30px;
  place-items: center;
  border-radius: 999px;
  background: var(--row-color);
  color: #fff;
  font-size: 12px;
  font-weight: 900;
}}
.row-body {{
  min-width: 0;
}}
.row-label {{
  margin-bottom: 3px;
  color: color-mix(in srgb, var(--row-color), black 24%);
  font-size: 13px;
  font-weight: 850;
}}
.row-text {{
  color: #1f2937;
  font-size: 14px;
}}
.row-original {{
  margin-top: 5px;
  color: #64748b;
  font-size: 12px;
}}
.sentence-extra {{
  margin-top: 4px;
  color: var(--muted);
  font-size: 11px;
}}
.sources {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid #e5e5ea;
}}
.source-chip {{
  color: var(--accent);
  word-break: break-word;
}}
@media (max-width: 980px) {{
  .metrics {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
}}
@media (max-width: 640px) {{
  .shell {{ width: min(100% - 20px, 1320px); }}
  .hero {{ padding-top: 34px; }}
  .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .paper-top {{ grid-template-columns: 1fr; }}
  .summary-row {{ gap: 10px; }}
}}
</style>
</head>
<body>
<header class="hero">
  <div class="shell">
    <div class="eyebrow">RSS 2026 abstract labels · Korean</div>
    <h1>RSS 2026 초록 문장별 13개 독해 라벨</h1>
    <p class="subtitle">영문 RSS 2026 초록 문장을 13개 논문 읽기 질문 스키마로 라벨링한 뒤 한국어로 번역한 판입니다. 라벨은 abstract-only rule-based primary label이며, PDF 본문 전체 판독 결과는 아닙니다.</p>
    <div class="hero-meta">
      <span class="chip">{metadata["paper_count"]}편 논문</span>
      <span class="chip">{metadata["sentence_count"]}개 문장</span>
      <a class="chip primary" href="abstract_sentence_labels.html">English labels</a>
      <a class="chip" href="index.html">Explorer</a>
      <a class="chip" href="{PROMPT_URL}">13-question prompt</a>
    </div>
    <div class="metrics">
      {label_summary}
    </div>
  </div>
</header>
<main class="shell">
  <nav class="nav-card" aria-label="Paper navigation">
    <p class="nav-title">논문 목차</p>
    <div class="paper-nav">
      {nav}
    </div>
  </nav>
  {paper_cards}
</main>
</body>
</html>
"""


def render_paper(paper: dict) -> str:
    rows = "\n".join(render_sentence(sentence) for sentence in paper["sentences"])
    topics = ", ".join(str(topic) for topic in paper.get("topics", []))
    return f"""
<article class="paper-card" id="paper-{html.escape(str(paper["id"]))}">
  <div class="paper-top">
    <div class="paper-number">{html.escape(str(paper["id"]))}</div>
    <div>
      <h2>{html.escape(str(paper["title_ko"]))}</h2>
      <div class="title-en">{html.escape(str(paper["title_en"]))}</div>
      <div class="paper-meta">
        <span class="chip">{html.escape(str(paper["session"]))}</span>
        <span class="chip">{html.escape(str(paper["sentence_count"]))}개 라벨 문장</span>
        <span class="chip">{html.escape(topics)}</span>
      </div>
    </div>
  </div>
  <div class="paper-body">
    <p class="abstract">{html.escape(str(paper["abstract_ko"]))}</p>
    <p class="abstract-en">{html.escape(str(paper["abstract_en"]))}</p>
    <div class="summary-list">
      {rows}
    </div>
    <div class="sources">
      <a class="source-chip" href="{html.escape(str(paper["href"]))}">paper page</a>
    </div>
  </div>
</article>
"""


def render_sentence(sentence: dict) -> str:
    label_id = int(sentence["label_id"])
    confidence = f"{float(sentence['confidence']):.2f}"
    return f"""
<div class="summary-row" style="{label_style(label_id)}">
  <div class="row-index">{label_id:02d}</div>
  <div class="row-body">
    <div class="row-label">{html.escape(str(sentence["label_name"]))} · {html.escape(str(sentence["label_english"]))}</div>
    <div class="row-text">{html.escape(str(sentence["sentence_ko"]))}</div>
    <div class="row-original">{html.escape(str(sentence["sentence_en"]))}</div>
    <div class="sentence-extra">문장 {html.escape(str(sentence["sentence_index"]))} · confidence {confidence} · {html.escape(str(sentence["rule_reason"]))}</div>
  </div>
</div>
"""


def main() -> None:
    source = load_json(SOURCE_JSON)
    cache = load_cache()
    texts = collect_texts(source)
    translate_batch(texts, cache)
    korean = build_korean_data(source, cache)

    write_json(korean, JSON_OUTPUT)
    write_csv(korean, CSV_OUTPUT)
    html_text = render_html(korean)
    HTML_OUTPUT.write_text(html_text, encoding="utf-8", newline="\n")

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    write_json(korean, OUTPUT_JSON_COPY)
    write_csv(korean, OUTPUT_CSV_COPY)
    OUTPUT_HTML_COPY.write_text(html_text, encoding="utf-8", newline="\n")

    print(f"papers={korean['metadata']['paper_count']} sentences={korean['metadata']['sentence_count']}")
    print(f"cache={len(cache)} translations")
    print(f"wrote {HTML_OUTPUT}")
    print(f"copied outputs to {OUTPUTS_DIR}")


if __name__ == "__main__":
    main()
