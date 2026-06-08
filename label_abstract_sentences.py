from __future__ import annotations

import csv
import html
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX_HTML = ROOT / "index.html"
DATA_DIR = ROOT / "data"
OUTPUTS_DIR = ROOT.parent.parent / "outputs"
PROMPT_URL = "https://gisbi-kim.github.io/paper-reading-13-questions/"

JSON_OUTPUT = DATA_DIR / "rss2026_abstract_sentence_labels.json"
CSV_OUTPUT = DATA_DIR / "rss2026_abstract_sentence_labels.csv"
HTML_OUTPUT = ROOT / "abstract_sentence_labels.html"
OUTPUT_HTML_COPY = OUTPUTS_DIR / "rss2026_abstract_sentence_labels.html"
OUTPUT_JSON_COPY = OUTPUTS_DIR / "rss2026_abstract_sentence_labels.json"
OUTPUT_CSV_COPY = OUTPUTS_DIR / "rss2026_abstract_sentence_labels.csv"


LABELS = [
    {"id": 1, "name": "배경", "english": "Background", "color": "#ff3b30"},
    {"id": 2, "name": "문제", "english": "Problem", "color": "#ff9500"},
    {"id": 3, "name": "기존 한계", "english": "Prior limitation", "color": "#d6a100"},
    {"id": 4, "name": "목표", "english": "Goal", "color": "#a6c900"},
    {"id": 5, "name": "방법", "english": "Method", "color": "#34c759"},
    {"id": 6, "name": "핵심 아이디어", "english": "Key idea", "color": "#00a887"},
    {"id": 7, "name": "검증", "english": "Validation", "color": "#00a6c7"},
    {"id": 8, "name": "결과", "english": "Result", "color": "#0071e3"},
    {"id": 9, "name": "비교", "english": "Comparison", "color": "#5856d6"},
    {"id": 10, "name": "의의", "english": "Significance", "color": "#7d3cff"},
    {"id": 11, "name": "한계", "english": "Limitation", "color": "#af52de"},
    {"id": 12, "name": "향후 과제", "english": "Future work", "color": "#ff2d95"},
    {"id": 13, "name": "자원 공개", "english": "Resources", "color": "#ff375f"},
]


RULES = [
    (
        13,
        "resource disclosure",
        [
            r"\bopen[- ]source\b",
            r"\bpublicly available\b",
            r"\bwill be released\b",
            r"\brelease(?:d|s)?\b.*\b(code|data|dataset|benchmark|toolkit|hardware|model|checkpoint)\b",
            r"\b(code|data|dataset|benchmark|toolkit|hardware design|model|checkpoint)\b.*\b(will be|is|are)\b.*\b(released|available|open)\b",
        ],
    ),
    (
        12,
        "future direction",
        [
            r"\bfuture work\b",
            r"\bfuture research\b",
            r"\bfuture directions?\b",
            r"\bnext step\b",
            r"\bto be deployed\b",
        ],
    ),
    (
        11,
        "remaining limitation",
        [
            r"\blimitation\b",
            r"\bfailure case\b",
            r"\bdeployment constraint\b",
            r"\bremains unresolved\b",
            r"\bstill cannot\b",
        ],
    ),
    (
        9,
        "comparison to baselines",
        [
            r"\bagainst\b.*\b(baseline|state-of-the-art|existing|prior)\b",
            r"\bcompared (?:with|to)\b",
            r"\bbenchmark(?:ed)? against\b",
            r"\bbaselines?\b",
            r"\bstate[- ]of[- ]the[- ]art\b",
            r"\boutperform(?:s|ed|ing)?\b.*\b(baseline|method|approach|policy|planner|model)\b",
        ],
    ),
    (
        8,
        "reported result",
        [
            r"\bresults? (?:show|demonstrate|indicate)\b",
            r"\bexperiments? (?:show|demonstrate|validate)\b",
            r"\bachieves?\b",
            r"\bimproves?\b",
            r"\byields?\b",
            r"\boutperform(?:s|ed|ing)?\b",
            r"\bsuccess rate\b",
            r"\bmean absolute error\b",
            r"\bmae\b",
            r"\b\d+(?:\.\d+)?\s?%\b",
            r"\b\d+(?:\.\d+)?\s?(?:ms|s|n|mm|m|hours?)\b",
        ],
    ),
    (
        7,
        "validation setup",
        [
            r"\bevaluat(?:e|ed|ion|ing)\b",
            r"\bbenchmark\b",
            r"\bexperiments?\b",
            r"\bsimulation\b",
            r"\bsimulated\b",
            r"\breal[- ]world\b",
            r"\bphysical\b.*\brobot\b",
            r"\bdataset\b",
            r"\b(?:evaluate|evaluated|evaluation|experiments?|benchmark(?:ed)?)\b.*\btasks?\b",
            r"\btasks?\b.*\b(?:evaluate|evaluated|evaluation|experiments?|benchmark(?:ed)?)\b",
            r"\brollouts?\b",
            r"\bfield experiments?\b",
        ],
    ),
    (
        6,
        "key mechanism",
        [
            r"\bkey (?:idea|insight)\b",
            r"\bcore\b",
            r"\bcentral\b",
            r"\benables?\b",
            r"\bvia\b",
            r"\bleverages?\b",
            r"\bdecompose\b",
            r"\balign(?:s|ment)?\b",
            r"\bcondition(?:s|ed|ing)?\b",
            r"\bunified\b",
            r"\bobject[- ]centric\b",
            r"\blatent\b",
        ],
    ),
    (
        5,
        "proposed method",
        [
            r"\bwe (?:propose|present|introduce|develop|design|build|construct)\b",
            r"\bthis paper (?:proposes|presents|introduces|develops)\b",
            r"\bour (?:method|approach|framework|system|model|policy|pipeline)\b",
            r"\bconsists? of\b",
            r"\bframework\b",
            r"\bpipeline\b",
            r"\barchitecture\b",
            r"\bmodel\b",
            r"\bpolicy\b",
            r"\bcontroller\b",
            r"\balgorithm\b",
        ],
    ),
    (
        4,
        "paper goal",
        [
            r"\bwe aim\b",
            r"\bour goal\b",
            r"\bseeks? to\b",
            r"\bto address this\b",
            r"\bto bridge\b",
            r"\bto support\b",
            r"\bto enable\b",
            r"\bthis paper considers\b",
        ],
    ),
    (
        3,
        "prior limitation",
        [
            r"\bexisting\b",
            r"\bprior\b",
            r"\bcurrent\b.*\b(paradigms?|methods?|approaches?|systems?|tools?)\b",
            r"\brely\b.*\b(prohibitively|costly|limited|imperfect|scarce)\b",
            r"\bsuffer(?:s|ed)? from\b",
            r"\bfail(?:s|ed)? to\b",
            r"\blimit(?:s|ed|ing)?\b",
            r"\bdata scarcity\b",
            r"\bchallenging due to\b",
            r"\bbarrier remains\b",
        ],
    ),
    (
        2,
        "specific problem",
        [
            r"\bchallenge\b",
            r"\bdifficult\b",
            r"\brequires?\b",
            r"\bneed(?:s|ed)?\b",
            r"\bproblem\b",
            r"\btask\b.*\b(?:requires?|depends|need)\b",
            r"\bopen challenge\b",
            r"\bmust\b",
        ],
    ),
    (
        10,
        "broader significance",
        [
            r"\bprovides?\b.*\bpath\b",
            r"\boffers?\b.*\bpathway\b",
            r"\bunlocks?\b",
            r"\badvances?\b",
            r"\benable(?:s|d)?\b.*\bdeployment\b",
            r"\bpractical\b.*\bdeployment\b",
            r"\bintended to enable\b",
        ],
    ),
]


ABBREVIATIONS = [
    "e.g.",
    "i.e.",
    "etc.",
    "vs.",
    "Fig.",
    "Eq.",
    "Sec.",
    "No.",
    "Dr.",
    "Prof.",
    "Mr.",
    "Ms.",
    "U.S.",
    "U.K.",
    "et al.",
]


def load_papers() -> list[dict[str, object]]:
    text = INDEX_HTML.read_text(encoding="utf-8")
    match = re.search(
        r'<script id="papers-data" type="application/json">(.*?)</script>',
        text,
        flags=re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"Could not find papers-data script in {INDEX_HTML}")
    return json.loads(match.group(1))


def split_sentences(text: str) -> list[str]:
    if not text.strip():
        return []
    protected = text.strip()
    placeholders: dict[str, str] = {}
    for idx, abbr in enumerate(ABBREVIATIONS):
        key = f"__ABBR_{idx}__"
        placeholders[key] = abbr
        protected = protected.replace(abbr, abbr.replace(".", key))
    protected = re.sub(r"(?<=\d)\.(?=\d)", "__DECIMAL__", protected)
    chunks = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", protected)
    sentences = []
    for chunk in chunks:
        restored = chunk.replace("__DECIMAL__", ".")
        for key, abbr in placeholders.items():
            restored = restored.replace(abbr.replace(".", key), abbr)
        restored = restored.strip()
        if restored:
            sentences.append(restored)
    return sentences


def classify_sentence(sentence: str, position: int, total: int) -> tuple[dict[str, object], str, float]:
    lowered = sentence.lower()
    priority_order = [13, 12, 11, 9, 8, 3, 2, 4, 6, 5, 7, 10]

    # Last-sentence resource statements are common in abstracts and should not be hidden by method/result words.
    for preferred_label_id in priority_order:
        for label_id, reason, patterns in RULES:
            if label_id != preferred_label_id:
                continue
            for pattern in patterns:
                if re.search(pattern, lowered):
                    confidence = 0.88
                    if label_id in {8, 9, 13}:
                        confidence = 0.93
                    if label_id == 3 and position <= max(2, total // 3):
                        confidence = 0.91
                    return LABELS[label_id - 1], reason, confidence

    if total <= 2 and position == 1:
        return LABELS[4], "short abstract method statement", 0.62
    if position == 1:
        return LABELS[0], "opening context sentence", 0.68
    if position == total and re.search(r"\b(overall|together|these results|this work)\b", lowered):
        return LABELS[9], "closing implication sentence", 0.7
    return LABELS[4], "default technical contribution sentence", 0.58


def build_labeled_data() -> dict[str, object]:
    papers = load_papers()
    labeled_papers = []
    sentence_count = 0
    label_counts: Counter[int] = Counter()

    for paper in papers:
        abstract = str(paper.get("abstract", ""))
        sentences = split_sentences(abstract)
        labeled_sentences = []
        for idx, sentence in enumerate(sentences, start=1):
            label, reason, confidence = classify_sentence(sentence, idx, len(sentences))
            label_counts[int(label["id"])] += 1
            sentence_count += 1
            labeled_sentences.append(
                {
                    "sentence_index": idx,
                    "sentence": sentence,
                    "label_id": label["id"],
                    "label_name": label["name"],
                    "label_english": label["english"],
                    "confidence": confidence,
                    "rule_reason": reason,
                }
            )
        labeled_papers.append(
            {
                "id": paper.get("id"),
                "title": paper.get("title"),
                "session": paper.get("session"),
                "href": paper.get("href"),
                "topics": paper.get("topics", []),
                "abstract": abstract,
                "sentence_count": len(labeled_sentences),
                "sentences": labeled_sentences,
            }
        )

    return {
        "metadata": {
            "title": "RSS 2026 abstract sentence labels",
            "source": "rss2026_explorer embedded abstracts",
            "prompt_url": PROMPT_URL,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "paper_count": len(labeled_papers),
            "sentence_count": sentence_count,
            "label_counts": {str(label["id"]): label_counts[int(label["id"])] for label in LABELS},
            "method": "Rule-based sentence-level primary labeling using the 13-question paper-reading schema; labels are based on abstracts only, not full PDFs.",
        },
        "label_schema": LABELS,
        "papers": labeled_papers,
    }


def write_json(data: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def write_csv(data: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "paper_id",
                "title",
                "session",
                "sentence_index",
                "label_id",
                "label_name",
                "label_english",
                "confidence",
                "rule_reason",
                "sentence",
                "url",
            ]
        )
        for paper in data["papers"]:  # type: ignore[index]
            for sentence in paper["sentences"]:  # type: ignore[index]
                writer.writerow(
                    [
                        paper["id"],
                        paper["title"],
                        paper["session"],
                        sentence["sentence_index"],
                        sentence["label_id"],
                        sentence["label_name"],
                        sentence["label_english"],
                        sentence["confidence"],
                        sentence["rule_reason"],
                        sentence["sentence"],
                        paper["href"],
                    ]
                )


def label_style(label_id: int) -> str:
    color = LABELS[label_id - 1]["color"]
    return f"--row-color: {color};"


def render_html(data: dict[str, object]) -> str:
    metadata = data["metadata"]  # type: ignore[index]
    counts = metadata["label_counts"]  # type: ignore[index]
    nav = "\n".join(
        f'<a href="#paper-{paper["id"]}">#{html.escape(str(paper["id"]))} {html.escape(str(paper["title"]))}</a>'
        for paper in data["papers"]  # type: ignore[index]
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
    paper_cards = "\n".join(render_paper(paper) for paper in data["papers"])  # type: ignore[index]
    generated = html.escape(str(metadata["generated_at"]))
    method = html.escape(str(metadata["method"]))
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RSS 2026 Abstract Sentence Labels</title>
<style>
:root {{
  --bg: #f5f5f7;
  --panel: rgba(255, 255, 255, 0.88);
  --ink: #1d1d1f;
  --muted: #6e6e73;
  --line: #d2d2d7;
  --accent: #0071e3;
  --shadow: 0 18px 58px rgba(0, 0, 0, 0.08);
  --radius: 8px;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans KR", system-ui, sans-serif;
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  margin: 0;
  color: var(--ink);
  background: var(--bg);
  font-family: var(--font);
  line-height: 1.55;
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
  font-weight: 800;
  text-transform: uppercase;
}}
h1 {{
  margin: 10px 0 12px;
  max-width: 960px;
  font-size: clamp(34px, 5vw, 64px);
  line-height: 1.04;
  letter-spacing: 0;
}}
.subtitle {{
  max-width: 920px;
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
  background: rgba(255, 255, 255, 0.82);
  color: #334155;
  font-size: 12px;
  font-weight: 750;
  text-decoration: none;
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
  font-weight: 800;
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
  background: rgba(255, 255, 255, 0.82);
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
  max-width: 240px;
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
  line-height: 1.18;
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
  margin: 0 0 16px;
  color: #475569;
  font-size: 14px;
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
    <div class="eyebrow">RSS 2026 abstract labels</div>
    <h1>Abstract Sentences Labeled by 13 Paper-Reading Questions</h1>
    <p class="subtitle">{method}</p>
    <div class="hero-meta">
      <span class="chip">{metadata["paper_count"]} papers</span>
      <span class="chip">{metadata["sentence_count"]} sentences</span>
      <span class="chip">Generated {generated}</span>
      <a class="chip" href="{PROMPT_URL}">13-question prompt</a>
    </div>
    <div class="metrics">
      {label_summary}
    </div>
  </div>
</header>
<main class="shell">
  <nav class="nav-card" aria-label="Paper navigation">
    <p class="nav-title">Paper index</p>
    <div class="paper-nav">
      {nav}
    </div>
  </nav>
  {paper_cards}
</main>
</body>
</html>
"""


def render_paper(paper: dict[str, object]) -> str:
    rows = "\n".join(render_sentence(sentence) for sentence in paper["sentences"])  # type: ignore[index]
    topics = ", ".join(str(topic) for topic in paper.get("topics", []))
    return f"""
<article class="paper-card" id="paper-{html.escape(str(paper["id"]))}">
  <div class="paper-top">
    <div class="paper-number">{html.escape(str(paper["id"]))}</div>
    <div>
      <h2>{html.escape(str(paper["title"]))}</h2>
      <div class="paper-meta">
        <span class="chip">{html.escape(str(paper["session"]))}</span>
        <span class="chip">{html.escape(str(paper["sentence_count"]))} labeled sentences</span>
        <span class="chip">{html.escape(topics)}</span>
      </div>
    </div>
  </div>
  <div class="paper-body">
    <p class="abstract">{html.escape(str(paper["abstract"]))}</p>
    <div class="summary-list">
      {rows}
    </div>
    <div class="sources">
      <a class="source-chip" href="{html.escape(str(paper["href"]))}">paper page</a>
    </div>
  </div>
</article>
"""


def render_sentence(sentence: dict[str, object]) -> str:
    label_id = int(sentence["label_id"])
    confidence = f"{float(sentence['confidence']):.2f}"
    return f"""
<div class="summary-row" style="{label_style(label_id)}">
  <div class="row-index">{label_id:02d}</div>
  <div class="row-body">
    <div class="row-label">{html.escape(str(sentence["label_name"]))} · {html.escape(str(sentence["label_english"]))}</div>
    <div class="row-text">{html.escape(str(sentence["sentence"]))}</div>
    <div class="sentence-extra">sentence {html.escape(str(sentence["sentence_index"]))} · confidence {confidence} · {html.escape(str(sentence["rule_reason"]))}</div>
  </div>
</div>
"""


def main() -> None:
    data = build_labeled_data()
    write_json(data, JSON_OUTPUT)
    write_csv(data, CSV_OUTPUT)
    html_text = render_html(data)
    HTML_OUTPUT.write_text(html_text, encoding="utf-8", newline="\n")

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    write_json(data, OUTPUT_JSON_COPY)
    write_csv(data, OUTPUT_CSV_COPY)
    OUTPUT_HTML_COPY.write_text(html_text, encoding="utf-8", newline="\n")

    print(f"papers={data['metadata']['paper_count']} sentences={data['metadata']['sentence_count']}")
    print(f"wrote {JSON_OUTPUT}")
    print(f"wrote {CSV_OUTPUT}")
    print(f"wrote {HTML_OUTPUT}")
    print(f"copied outputs to {OUTPUTS_DIR}")


if __name__ == "__main__":
    main()
