from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "index.html"
ABSTRACT_SOURCE = ROOT / "data" / "rss2026_papers_1_210_abstracts.txt"


TOPIC_PATTERNS = [
    (
        "Manipulation",
        [
            r"\bmanipulat",
            r"\bgrasp",
            r"\bgripper",
            r"\bdexter",
            r"\bbimanual",
            r"\btactile",
            r"\bcontact",
            r"\btool",
            r"\bhand\b",
            r"\bscoop",
            r"\bassembly",
        ],
    ),
    (
        "Learning",
        [
            r"\blearn",
            r"\bimitation",
            r"\bdemonstrat",
            r"\bpolicy",
            r"\breinforcement",
            r"\bdiffusion",
            r"\bbehavior",
            r"\bskill",
            r"\bdata",
            r"\bfoundation",
        ],
    ),
    (
        "SLAM and Localization",
        [
            r"\bslam\b",
            r"\bodometry",
            r"\blocali[sz]",
            r"\bmapping",
            r"\bplace recognition",
            r"\bvisual-inertial",
            r"\blidar",
            r"\bpose",
            r"\brange",
        ],
    ),
    (
        "Navigation and Planning",
        [
            r"\bnavigat",
            r"\bpath planning",
            r"\bmotion planning",
            r"\btrajectory",
            r"\bcollision",
            r"\bobstacle",
            r"\btravers",
            r"\breplanning",
            r"\breactive",
        ],
    ),
    (
        "Perception",
        [
            r"\bperception",
            r"\bvision",
            r"\bvisual",
            r"\bimage",
            r"\bcamera",
            r"\bsegmentation",
            r"\bdetection",
            r"\breconstruction",
            r"\b3d\b",
            r"\bpoint cloud",
            r"\bdepth",
            r"\bestimation",
        ],
    ),
    (
        "Control and Dynamics",
        [
            r"\bcontrol",
            r"\bmpc\b",
            r"\bdynamics",
            r"\btracking",
            r"\boptimal",
            r"\bstabil",
            r"\bmodel predictive",
        ],
    ),
    (
        "Multi-Robot",
        [
            r"\bmulti-robot",
            r"\bmulti robot",
            r"\bmulti-agent",
            r"\bmulti agent",
            r"\bswarm",
            r"\bfleet",
            r"\bcoordination",
            r"\bdistributed",
        ],
    ),
    (
        "Human-Robot Interaction",
        [
            r"\bhuman",
            r"\bhri\b",
            r"\bassistive",
            r"\bwearable",
            r"\bexoskeleton",
            r"\brehabilitation",
            r"\bcollaborat",
            r"\bteleoperation",
        ],
    ),
    (
        "Aerial and Field Robots",
        [
            r"\baerial",
            r"\bquadrotor",
            r"\buav\b",
            r"\bdrone",
            r"\bfield robot",
            r"\bunderwater",
            r"\bmarine",
            r"\bforest",
        ],
    ),
    (
        "Medical and Surgical",
        [
            r"\bmedical",
            r"\bsurgical",
            r"\bsurgery",
            r"\bbiopsy",
            r"\bbronchoscopic",
            r"\btissue",
            r"\bprosthe",
            r"\bclinical",
        ],
    ),
    (
        "Humanoids and Locomotion",
        [
            r"\bhumanoid",
            r"\bbiped",
            r"\blegged",
            r"\blocomo",
            r"\bgait",
            r"\bwalking",
            r"\bquadruped",
            r"\bstand",
        ],
    ),
    (
        "Language and VLM",
        [
            r"\blanguage",
            r"\bllm\b",
            r"\bvlm\b",
            r"\bvision-language",
            r"\bprompt",
            r"\brag\b",
            r"\bworld model",
            r"\bmemory",
        ],
    ),
    (
        "Simulation and Digital Twins",
        [
            r"\bsimulation",
            r"\bsim-to-real",
            r"\bsim2real",
            r"\bdigital twin",
            r"\bvirtual",
            r"\bsynthetic",
            r"\bbenchmark",
        ],
    ),
    (
        "Safety and Robustness",
        [
            r"\bsafety",
            r"\bsafe",
            r"\brobust",
            r"\buncertain",
            r"\badversarial",
            r"\bconstraint",
            r"\bverification",
            r"\brisk",
        ],
    ),
    (
        "Soft and Bio-inspired",
        [
            r"\bsoft",
            r"\bcontinuum",
            r"\bpneumatic",
            r"\btendon",
            r"\bbio-inspired",
            r"\bhybrid gripper",
        ],
    ),
]


class PaperTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_tr = False
        self.current: dict[str, str] | None = None
        self.in_td = False
        self.hidden_depth = 0
        self.td_visible: list[str] = []
        self.td_hidden: list[str] = []
        self.tds: list[dict[str, str]] = []
        self.papers: list[dict[str, object]] = []

    def handle_starttag(self, tag: str, attrs_raw: list[tuple[str, str | None]]) -> None:
        attrs = {key: value or "" for key, value in attrs_raw}
        if tag == "tr" and "session" in attrs:
            self.in_tr = True
            self.current = {"session": attrs.get("session", ""), "href": ""}
            self.tds = []
            return

        if self.in_tr and tag == "td":
            self.in_td = True
            self.hidden_depth = 0
            self.td_visible = []
            self.td_hidden = []
            return

        if self.in_tr and self.in_td:
            class_names = set(attrs.get("class", "").split())
            style = attrs.get("style", "").replace(" ", "").lower()
            if tag == "div" and ("content" in class_names or "display:none" in style):
                self.hidden_depth += 1
            elif self.hidden_depth > 0 and tag not in {"br", "img", "input"}:
                self.hidden_depth += 1

        if self.in_tr and tag == "a" and self.current is not None:
            href = attrs.get("href", "")
            if href and not self.current.get("href"):
                self.current["href"] = href

    def handle_endtag(self, tag: str) -> None:
        if self.in_tr and self.in_td and self.hidden_depth > 0 and tag not in {"br", "img", "input"}:
            self.hidden_depth -= 1
            return

        if self.in_tr and tag == "td":
            visible = clean_text("".join(self.td_visible))
            hidden = clean_text("".join(self.td_hidden))
            self.tds.append({"visible": visible, "hidden": hidden})
            self.in_td = False
            return

        if self.in_tr and tag == "tr":
            if self.current is not None and len(self.tds) >= 4:
                authors = self.tds[3]["hidden"] or self.tds[3]["visible"].replace("...more>", "").strip()
                paper = {
                    "id": self.tds[0]["visible"],
                    "session": self.tds[1]["visible"] or self.current.get("session", ""),
                    "title": self.tds[2]["visible"],
                    "authors": clean_text(authors),
                    "href": self.current.get("href", ""),
                }
                self.papers.append(paper)
            self.in_tr = False
            self.current = None

    def handle_data(self, data: str) -> None:
        if self.in_tr and self.in_td:
            if self.hidden_depth > 0:
                self.td_hidden.append(data)
            else:
                self.td_visible.append(data)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def locate_source() -> Path:
    downloads = Path.home() / "Downloads"
    candidates = sorted(
        downloads.glob("Accepted Papers*Robotics*Science*Systems.html"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("Could not find the accepted papers HTML in Downloads.")
    return candidates[0]


def extract_description(text: str) -> str:
    match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', text, flags=re.I)
    return clean_text(match.group(1)) if match else "RSS 2026 accepted papers"


def split_authors(authors: str) -> list[str]:
    names = [clean_text(part) for part in authors.split(",")]
    return [name for name in names if name and name != "...more>"]


def infer_topics(title: str, session: str) -> list[str]:
    haystack = f"{title} {session}".lower()
    topics: list[str] = []
    for topic, patterns in TOPIC_PATTERNS:
        if any(re.search(pattern, haystack, flags=re.I) for pattern in patterns):
            topics.append(topic)
    return topics or ["Other"]


def parse_abstracts(source: Path = ABSTRACT_SOURCE) -> dict[int, str]:
    if not source.exists():
        return {}
    abstracts: dict[int, str] = {}
    current_id: int | None = None
    current_lines: list[str] = []
    capture = False

    def flush() -> None:
        nonlocal current_id, current_lines, capture
        if current_id is not None:
            abstract = clean_text(" ".join(current_lines))
            if abstract and abstract not in {"(abstract not found)", "(fetch failed)"}:
                abstracts[current_id] = abstract
        current_id = None
        current_lines = []
        capture = False

    for raw_line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        match = re.match(r"^Paper ID (\d+)$", line)
        if match:
            flush()
            current_id = int(match.group(1))
            continue
        if line == "Abstract:":
            capture = True
            current_lines = []
            continue
        if capture:
            if line == "-" * 80:
                flush()
            elif line:
                current_lines.append(line)
    flush()
    return abstracts


def parse_papers(source: Path) -> tuple[list[dict[str, object]], str]:
    text = source.read_text(encoding="utf-8", errors="replace")
    abstracts = parse_abstracts()
    parser = PaperTableParser()
    parser.feed(text)
    papers = []
    for raw in parser.papers:
        paper_id = int(str(raw["id"])) if str(raw["id"]).isdigit() else str(raw["id"])
        authors = str(raw["authors"])
        author_list = split_authors(authors)
        session = str(raw["session"])
        title = str(raw["title"])
        paper = {
            "id": paper_id,
            "session": session,
            "title": title,
            "authors": authors,
            "authorList": author_list,
            "authorCount": len(author_list),
            "href": str(raw["href"]),
            "topics": infer_topics(title, session),
            "abstract": abstracts.get(paper_id, ""),
        }
        papers.append(paper)
    return papers, extract_description(text)


def summarize(papers: list[dict[str, object]], source: Path, description: str) -> dict[str, object]:
    session_counts = Counter(str(paper["session"]) for paper in papers)
    topic_counts = Counter(topic for paper in papers for topic in paper["topics"])  # type: ignore[index]
    author_counts = Counter(author for paper in papers for author in paper["authorList"])  # type: ignore[index]
    avg_authors = sum(int(paper["authorCount"]) for paper in papers) / len(papers) if papers else 0
    return {
        "venue": "RSS 2026",
        "title": "RSS 2026 Paper Explorer",
        "description": description,
        "sourceFile": str(source),
        "sourceModified": datetime.fromtimestamp(source.stat().st_mtime).isoformat(timespec="seconds"),
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "paperCount": len(papers),
        "sessionCount": len(session_counts),
        "topicCount": len(topic_counts),
        "abstractCount": sum(1 for paper in papers if str(paper.get("abstract", "")).strip()),
        "avgAuthors": round(avg_authors, 2),
        "largestSession": session_counts.most_common(1)[0] if session_counts else ["", 0],
        "topAuthor": author_counts.most_common(1)[0] if author_counts else ["", 0],
        "topicNames": [name for name, _patterns in TOPIC_PATTERNS] + ["Other"],
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RSS 2026 Paper Explorer</title>
<style>
:root {
  --bg: #ffffff;
  --bg-alt: #f5f5f7;
  --bg-soft: #fafafa;
  --panel: #ffffff;
  --border: #d2d2d7;
  --border-soft: #e5e5ea;
  --text: #1d1d1f;
  --text-2: #424245;
  --muted: #6e6e73;
  --muted-2: #86868b;
  --accent: #0066cc;
  --accent-hover: #0058b0;
  --accent-soft: rgba(0, 102, 204, 0.08);
  --green: #248a3d;
  --orange: #b25000;
  --purple: #6e3ad6;
  --pink: #c0185c;
  --yellow: #8a6d00;
  --shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.06);
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", "Pretendard", "Noto Sans KR", system-ui, sans-serif;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  color: var(--text);
  background: var(--bg);
  font-family: var(--font);
  font-size: 15px;
  line-height: 1.47;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
button, input, select { font: inherit; }
button { cursor: pointer; }
.topbar {
  position: sticky;
  top: 0;
  z-index: 40;
  height: 54px;
  border-bottom: 1px solid var(--border-soft);
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: saturate(180%) blur(20px);
}
.topbar .inner {
  max-width: 1440px;
  height: 100%;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 18px;
}
.brand {
  color: var(--text);
  font-weight: 650;
  font-size: 17px;
  letter-spacing: 0;
}
.topbar .meta {
  color: var(--muted);
  font-size: 13px;
}
.topbar .right {
  margin-left: auto;
  display: flex;
  gap: 8px;
  align-items: center;
}
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 26px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--border-soft);
  background: var(--bg-alt);
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.pill b { color: var(--text); font-weight: 650; }
.pill.accent {
  background: var(--accent-soft);
  border-color: rgba(0, 102, 204, 0.18);
  color: var(--accent);
}
.layout {
  max-width: 1440px;
  margin: 0 auto;
  padding: 0 24px;
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr);
  gap: 32px;
  align-items: start;
}
.sidebar {
  position: sticky;
  top: 66px;
  padding: 28px 0;
  max-height: calc(100vh - 66px);
  overflow: auto;
}
.sidebar h4 {
  margin: 18px 0 7px;
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.sidebar a, .side-filter {
  display: block;
  width: 100%;
  margin: 2px 0;
  padding: 6px 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-2);
  text-align: left;
  font-size: 13px;
}
.sidebar a:hover, .side-filter:hover {
  background: var(--bg-alt);
  color: var(--text);
  text-decoration: none;
}
main {
  min-width: 0;
  padding: 30px 0 56px;
}
section {
  scroll-margin-top: 76px;
  margin-bottom: 34px;
}
.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}
h1, h2, h3, p { margin-top: 0; }
h1 {
  margin-bottom: 8px;
  font-size: clamp(30px, 4vw, 52px);
  line-height: 1.05;
  letter-spacing: 0;
}
h2 {
  margin: 0;
  font-size: 22px;
  letter-spacing: 0;
}
h3 {
  margin: 0 0 10px;
  font-size: 15px;
  letter-spacing: 0;
}
.lede {
  max-width: 820px;
  margin-bottom: 18px;
  color: var(--text-2);
  font-size: 17px;
}
.section-sub {
  max-width: 920px;
  color: var(--muted);
  font-size: 13px;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.metric {
  min-height: 112px;
  padding: 15px;
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  background: var(--panel);
  box-shadow: var(--shadow);
}
.metric .value {
  font-size: 32px;
  font-weight: 750;
  line-height: 1;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}
.metric .label {
  margin-top: 7px;
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.metric .desc {
  margin-top: 8px;
  color: var(--text-2);
  font-size: 13px;
}
.grid-2 {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
  gap: 14px;
}
.panel {
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  background: var(--panel);
  box-shadow: var(--shadow);
}
.bar-list {
  display: grid;
  gap: 8px;
}
.bar-row {
  display: grid;
  grid-template-columns: minmax(150px, 250px) minmax(0, 1fr) 42px;
  gap: 10px;
  align-items: center;
  min-height: 28px;
}
.bar-label {
  overflow: hidden;
  color: var(--text-2);
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.bar-label button {
  all: unset;
  cursor: pointer;
}
.bar-label button:hover { color: var(--accent); text-decoration: underline; }
.bar-label button.active {
  color: var(--accent);
  font-weight: 650;
}
.bar-track {
  position: relative;
  height: 14px;
  border-radius: 999px;
  background: var(--bg-alt);
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  min-width: 2px;
  border-radius: inherit;
  background: var(--accent);
}
.bar-count {
  color: var(--muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.topic-fill-0 { background: #0066cc; }
.topic-fill-1 { background: #248a3d; }
.topic-fill-2 { background: #b25000; }
.topic-fill-3 { background: #6e3ad6; }
.topic-fill-4 { background: #c0185c; }
.topic-fill-5 { background: #8a6d00; }
.topic-fill-6 { background: #087a8f; }
.topic-fill-7 { background: #4b6b1b; }
.topic-fill-8 { background: #9a3412; }
.topic-fill-9 { background: #3b5bdb; }
.toolbar {
  display: grid;
  gap: 10px;
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  background: var(--bg-soft);
}
.toolbar-row {
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 0;
}
.toolbar input[type="text"], .toolbar select {
  min-height: 36px;
  min-width: 0;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: var(--panel);
  color: var(--text);
}
.search-row input[type="text"] { flex: 1 1 160px; }
.search-row select { flex: 0 0 86px; }
.filter-row select { flex: 1 1 150px; }
.view-row select { flex: 1 1 170px; }
.btn {
  min-height: 36px;
  padding: 7px 12px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: var(--panel);
  color: var(--text-2);
}
.btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.btn.primary {
  border-color: var(--accent);
  background: var(--accent);
  color: #ffffff;
}
.btn.primary:hover {
  background: var(--accent-hover);
  color: #ffffff;
  text-decoration: none;
}
.result-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 8px 0 12px;
  color: var(--muted);
  font-size: 13px;
}
.active-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 2px;
}
.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 9px;
  border: 1px solid var(--border-soft);
  border-radius: 999px;
  background: var(--panel);
  color: var(--text-2);
  font-size: 12px;
}
button.filter-chip {
  cursor: pointer;
}
button.filter-chip:hover {
  border-color: rgba(0, 102, 204, 0.35);
  color: var(--accent);
}
.papers {
  display: grid;
  gap: 10px;
}
.paper {
  padding: 14px 15px;
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  background: var(--panel);
  box-shadow: var(--shadow);
}
.paper-head {
  display: flex;
  align-items: start;
  gap: 10px;
}
.paper-title {
  all: unset;
  flex: 1;
  min-width: 0;
  color: var(--text);
  font-size: 16px;
  font-weight: 680;
  line-height: 1.35;
  cursor: pointer;
}
.paper-title:hover { color: var(--accent); }
.paper-link {
  flex: 0 0 auto;
  padding: 4px 8px;
  border: 1px solid var(--border-soft);
  border-radius: 999px;
  color: var(--accent);
  font-size: 12px;
}
.paper-link:hover {
  border-color: rgba(0, 102, 204, 0.35);
  background: var(--accent-soft);
  text-decoration: none;
}
.paper-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.paper-authors {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  margin-top: 9px;
  color: var(--text-2);
  font-size: 13.5px;
}
.authors-label {
  margin-right: 2px;
  color: var(--muted);
  font-size: 12px;
}
.author-button {
  all: unset;
  display: inline-flex;
  align-items: center;
  min-height: 23px;
  padding: 2px 7px;
  border: 1px solid transparent;
  border-radius: 999px;
  color: var(--text-2);
  cursor: pointer;
}
.author-button:hover {
  border-color: rgba(0, 102, 204, 0.25);
  background: var(--accent-soft);
  color: var(--accent);
}
.author-button.active,
.tag.active,
.side-filter.active {
  border-color: rgba(0, 102, 204, 0.32);
  background: var(--accent-soft);
  color: var(--accent);
}
.tag {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  min-height: 24px;
  padding: 3px 8px;
  border: 1px solid var(--border-soft);
  border-radius: 999px;
  background: var(--bg-alt);
  color: var(--muted);
  font-size: 12px;
}
button.tag:hover {
  border-color: rgba(0, 102, 204, 0.35);
  color: var(--accent);
}
.tag.session { color: var(--accent); background: var(--accent-soft); }
.tag.topic { background: #fff; }
.paper-detail {
  display: none;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-soft);
  color: var(--text-2);
  font-size: 13px;
}
.paper.open .paper-detail { display: block; }
.paper-abstract {
  margin: 0 0 12px;
  color: var(--text-2);
  font-size: 13.5px;
  line-height: 1.55;
}
.detail-grid {
  display: grid;
  grid-template-columns: 130px minmax(0, 1fr);
  gap: 6px 12px;
}
.detail-label {
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.pager {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
}
.heatmap-wrap {
  overflow-x: auto;
  border: 1px solid var(--border-soft);
  border-radius: 8px;
}
.heatmap {
  width: 100%;
  min-width: 860px;
  border-collapse: collapse;
  font-size: 12px;
}
.heatmap th,
.heatmap td {
  border-bottom: 1px solid var(--border-soft);
  border-right: 1px solid var(--border-soft);
  padding: 6px;
  text-align: center;
}
.heatmap th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--bg-soft);
  color: var(--muted);
  font-weight: 650;
}
.heatmap th:first-child {
  left: 0;
  z-index: 2;
}
.heatmap td:first-child {
  position: sticky;
  left: 0;
  z-index: 1;
  background: var(--panel);
  color: var(--text-2);
  text-align: left;
  white-space: nowrap;
}
.heat-cell {
  min-width: 42px;
  height: 28px;
  border-radius: 4px;
  color: var(--text);
  font-variant-numeric: tabular-nums;
  line-height: 28px;
}
.empty {
  padding: 28px;
  border: 1px dashed var(--border);
  border-radius: 8px;
  color: var(--muted);
  text-align: center;
}
.source-note {
  margin-top: 22px;
  color: var(--muted);
  font-size: 12px;
}
@media (max-width: 1100px) {
  .layout { grid-template-columns: 1fr; gap: 0; padding: 0 16px; }
  .sidebar { position: static; max-height: none; padding: 14px 0 0; }
  .sidebar nav {
    display: flex;
    gap: 4px;
    overflow-x: auto;
    padding-bottom: 4px;
  }
  .sidebar h4, .side-filter { display: none; }
  .sidebar a { flex: 0 0 auto; width: auto; white-space: nowrap; }
  .grid-2 { grid-template-columns: 1fr; }
}
@media (max-width: 760px) {
  .topbar .meta, .topbar .right .pill:not(.accent) { display: none; }
  .topbar .inner { padding: 0 14px; }
  main { padding-top: 20px; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .section-head { align-items: start; flex-direction: column; }
  .toolbar-row { flex-wrap: wrap; }
  .toolbar input[type="text"], .toolbar select, .btn { flex: 1 1 100%; }
  .bar-row { grid-template-columns: minmax(120px, 1fr) minmax(80px, 1fr) 36px; }
  .paper-head { flex-direction: column; }
  .paper-link { align-self: flex-start; }
  .detail-grid { grid-template-columns: 1fr; }
}
@media (max-width: 460px) {
  .metric-grid { grid-template-columns: 1fr; }
  h1 { font-size: 32px; }
}
</style>
</head>
<body>
  <header class="topbar">
    <div class="inner">
      <a class="brand" href="#overview" id="brandHome">RSS 2026 Paper Explorer</a>
      <div class="meta">Accepted Papers / Robotics: Science and Systems</div>
      <div class="right">
        <span class="pill accent"><b id="topPaperCount">0</b> papers</span>
        <span class="pill"><b id="topSessionCount">0</b> sessions</span>
      </div>
    </div>
  </header>

  <div class="layout">
    <aside class="sidebar" aria-label="Page navigation">
      <nav>
        <a href="#overview">Overview</a>
        <a href="#sessions">Sessions</a>
        <a href="#topics">Hot topics</a>
        <a href="#authors">Authors</a>
        <a href="#matrix">Session x Topic</a>
        <a href="#search">Find papers</a>
      </nav>
      <h4>Quick Topics</h4>
      <div id="quickTopics"></div>
      <h4>Quick Sessions</h4>
      <div id="quickSessions"></div>
    </aside>

    <main>
      <section id="overview">
        <h1>RSS 2026 Paper Explorer</h1>
        <p class="lede">Search and scan the accepted papers for RSS 2026 by title, author, session, abstract, and title-derived topic tags. Abstracts are merged from the official paper pages.</p>
        <div class="metric-grid">
          <div class="metric">
            <div class="value" id="metricPapers">0</div>
            <div class="label">Accepted papers</div>
            <div class="desc">Parsed from the official accepted-papers table.</div>
          </div>
          <div class="metric">
            <div class="value" id="metricSessions">0</div>
            <div class="label">Sessions</div>
            <div class="desc" id="largestSession">Largest session pending</div>
          </div>
          <div class="metric">
            <div class="value" id="metricAvgAuthors">0.0</div>
            <div class="label">Avg authors</div>
            <div class="desc">Computed from comma-separated author names.</div>
          </div>
          <div class="metric">
            <div class="value" id="metricTopics">0</div>
            <div class="label">Topic tags</div>
            <div class="desc">Auto-tagged from titles and sessions.</div>
          </div>
        </div>
      </section>

      <section id="sessions">
        <div class="section-head">
          <div>
            <h2>Session Distribution</h2>
            <div class="section-sub">Click a bar label to filter the paper list.</div>
          </div>
        </div>
        <div class="grid-2">
          <div class="panel">
            <h3>All sessions</h3>
            <div id="sessionBars" class="bar-list"></div>
          </div>
          <div class="panel">
            <h3>Session size summary</h3>
            <div id="sessionSummary" class="bar-list"></div>
          </div>
        </div>
      </section>

      <section id="topics">
        <div class="section-head">
          <div>
            <h2>Hot Topics</h2>
            <div class="section-sub">These are rule-based tags inferred from titles and session names, not official RSS keywords. Papers can have multiple tags.</div>
          </div>
        </div>
        <div class="grid-2">
          <div class="panel">
            <h3>Title-derived topics</h3>
            <div id="topicBars" class="bar-list"></div>
          </div>
          <div class="panel">
            <h3>Topic coverage</h3>
            <div id="topicCoverage" class="bar-list"></div>
          </div>
        </div>
      </section>

      <section id="authors">
        <div class="section-head">
          <div>
            <h2>Authors</h2>
            <div class="section-sub">Author counts and repeat-name counts are derived from the accepted-papers table only.</div>
          </div>
        </div>
        <div class="grid-2">
          <div class="panel">
            <h3>Authors per paper</h3>
            <div id="authorCountBars" class="bar-list"></div>
          </div>
          <div class="panel">
            <h3>Repeat authors</h3>
            <div id="topAuthors" class="bar-list"></div>
          </div>
        </div>
      </section>

      <section id="matrix">
        <div class="section-head">
          <div>
            <h2>Session x Topic</h2>
            <div class="section-sub">Top title-derived topics across all RSS sessions. Click a session or topic through the charts above to drill down in the paper list.</div>
          </div>
        </div>
        <div class="heatmap-wrap">
          <table class="heatmap" id="heatmapTable"></table>
        </div>
      </section>

      <section id="search">
        <div class="section-head">
          <div>
            <h2>Find Papers</h2>
            <div class="section-sub">Search across titles, abstracts, authors, sessions, IDs, and auto topic tags. Up to three search boxes can be combined with AND or OR.</div>
          </div>
        </div>
        <div class="toolbar" aria-label="Search and filters">
          <div class="toolbar-row search-row">
            <input type="text" id="q1" placeholder="Search 1: manipulation" autocomplete="off">
            <select id="searchMode" title="Combine search boxes">
              <option value="AND">AND</option>
              <option value="OR">OR</option>
            </select>
            <input type="text" id="q2" placeholder="Search 2" autocomplete="off">
            <input type="text" id="q3" placeholder="Search 3" autocomplete="off">
          </div>
          <div class="toolbar-row filter-row">
            <select id="sessionFilter"><option value="">All sessions</option></select>
            <select id="topicFilter"><option value="">All topics</option></select>
            <select id="authorFilter">
              <option value="">Any author count</option>
              <option value="1-3">1-3 authors</option>
              <option value="4-6">4-6 authors</option>
              <option value="7-10">7-10 authors</option>
              <option value="11-999">11+ authors</option>
            </select>
          </div>
          <div class="toolbar-row view-row">
            <select id="sortFilter">
              <option value="id-asc">Sort by paper ID</option>
              <option value="title-asc">Title A-Z</option>
              <option value="session-asc">Session A-Z</option>
              <option value="authors-desc">Author count high-low</option>
              <option value="authors-asc">Author count low-high</option>
            </select>
            <select id="pageSizeFilter">
              <option value="500">500 per page</option>
              <option value="25">25 per page</option>
              <option value="50">50 per page</option>
              <option value="100">100 per page</option>
              <option value="all">All</option>
            </select>
            <button class="btn" id="downloadCsv" type="button">CSV</button>
            <button class="btn" id="clearFilters" type="button">Clear</button>
          </div>
          <div class="active-filters" id="activeFilters"></div>
        </div>
        <div class="result-meta">
          <div id="resultCount">0 papers</div>
          <div id="pageInfo"></div>
        </div>
        <div class="papers" id="papers"></div>
        <div class="pager" id="pager"></div>
        <div class="source-note" id="sourceNote"></div>
      </section>
    </main>
  </div>

<script id="papers-data" type="application/json">__PAPERS_JSON__</script>
<script id="meta-data" type="application/json">__META_JSON__</script>
<script>
const papers = JSON.parse(document.getElementById("papers-data").textContent);
const meta = JSON.parse(document.getElementById("meta-data").textContent);
const defaultState = {
  q1: "",
  q2: "",
  q3: "",
  searchMode: "AND",
  session: "",
  topic: "",
  author: "",
  authorRange: "",
  sort: "id-asc",
  pageSize: "500",
  page: 1
};
const state = { ...defaultState };

const topicPalette = [
  "#0066cc", "#248a3d", "#b25000", "#6e3ad6", "#c0185c",
  "#8a6d00", "#087a8f", "#4b6b1b", "#9a3412", "#3b5bdb"
];

function escapeHTML(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function countBy(items, fn) {
  const counts = new Map();
  for (const item of items) {
    const keys = fn(item);
    for (const key of Array.isArray(keys) ? keys : [keys]) {
      counts.set(key, (counts.get(key) || 0) + 1);
    }
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])));
}

function urlParamMap() {
  return {
    q1: "q",
    q2: "q2",
    q3: "q3",
    searchMode: "mode",
    session: "session",
    topic: "topic",
    author: "author",
    authorRange: "authors",
    sort: "sort",
    pageSize: "size",
    page: "page"
  };
}

function allowedValues(id) {
  const el = document.getElementById(id);
  return el ? [...el.options].map(option => option.value) : [];
}

function applyUrlState() {
  const params = new URLSearchParams(window.location.search);
  const map = urlParamMap();
  for (const [key, param] of Object.entries(map)) {
    if (!params.has(param)) continue;
    state[key] = params.get(param) || "";
  }

  if (!["AND", "OR"].includes(state.searchMode)) state.searchMode = defaultState.searchMode;
  if (!allowedValues("sessionFilter").includes(state.session)) state.session = "";
  if (!allowedValues("topicFilter").includes(state.topic)) state.topic = "";
  if (!allowedValues("authorFilter").includes(state.authorRange)) state.authorRange = "";
  if (!allowedValues("sortFilter").includes(state.sort)) state.sort = defaultState.sort;
  if (!allowedValues("pageSizeFilter").includes(state.pageSize)) state.pageSize = defaultState.pageSize;
  state.page = Math.max(1, Number.parseInt(String(state.page), 10) || 1);

  for (const id of ["q1", "q2", "q3"]) document.getElementById(id).value = state[id];
  document.getElementById("searchMode").value = state.searchMode;
  document.getElementById("sessionFilter").value = state.session;
  document.getElementById("topicFilter").value = state.topic;
  document.getElementById("authorFilter").value = state.authorRange;
  document.getElementById("sortFilter").value = state.sort;
  document.getElementById("pageSizeFilter").value = state.pageSize;
}

function updateUrlFromState() {
  const url = new URL(window.location.href);
  const params = url.searchParams;
  for (const [key, param] of Object.entries(urlParamMap())) {
    const value = String(state[key] ?? "");
    const defaultValue = String(defaultState[key] ?? "");
    if (value && value !== defaultValue) {
      params.set(param, value);
    } else {
      params.delete(param);
    }
  }
  const nextUrl = `${url.pathname}${params.toString() ? `?${params.toString()}` : ""}${url.hash}`;
  const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (nextUrl !== currentUrl) {
    window.history.replaceState(null, "", nextUrl);
  }
}

function setFilter(kind, value) {
  const nextValue = state[kind] === value ? "" : value;
  if (kind === "session") {
    state.session = nextValue;
    document.getElementById("sessionFilter").value = nextValue;
  }
  if (kind === "topic") {
    state.topic = nextValue;
    document.getElementById("topicFilter").value = nextValue;
  }
  if (kind === "author") {
    state.author = nextValue;
  }
  state.page = 1;
  renderResults();
  document.getElementById("search").scrollIntoView({ behavior: "smooth", block: "start" });
}

function updateFilterButtonStates() {
  document.querySelectorAll("[data-filter-kind], [data-paper-filter]").forEach(button => {
    const kind = button.dataset.filterKind || button.dataset.paperFilter;
    const value = button.dataset.filterValue || "";
    const active = Boolean(kind && state[kind] === value);
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function renderBarList(el, rows, opts = {}) {
  const max = Math.max(1, ...rows.map(row => row[1]));
  el.innerHTML = rows.map((row, index) => {
    const label = row[0];
    const count = row[1];
    const width = Math.max(2, Math.round(count / max * 100));
    const fillClass = opts.topic ? `topic-fill-${index % 10}` : "";
    const button = opts.filterKind
      ? `<button type="button" data-filter-kind="${opts.filterKind}" data-filter-value="${escapeHTML(label)}">${escapeHTML(label)}</button>`
      : escapeHTML(label);
    return `<div class="bar-row">
      <div class="bar-label" title="${escapeHTML(label)}">${button}</div>
      <div class="bar-track"><div class="bar-fill ${fillClass}" style="width:${width}%"></div></div>
      <div class="bar-count">${count}</div>
    </div>`;
  }).join("");
  el.querySelectorAll("[data-filter-kind]").forEach(button => {
    button.addEventListener("click", () => setFilter(button.dataset.filterKind, button.dataset.filterValue));
  });
}

function populateSelects() {
  const sessions = countBy(papers, paper => paper.session).map(row => row[0]);
  const topics = countBy(papers, paper => paper.topics).map(row => row[0]);
  document.getElementById("sessionFilter").insertAdjacentHTML(
    "beforeend",
    sessions.map(session => `<option value="${escapeHTML(session)}">${escapeHTML(session)}</option>`).join("")
  );
  document.getElementById("topicFilter").insertAdjacentHTML(
    "beforeend",
    topics.map(topic => `<option value="${escapeHTML(topic)}">${escapeHTML(topic)}</option>`).join("")
  );

  document.getElementById("quickTopics").innerHTML = topics.slice(0, 8).map(topic =>
    `<button class="side-filter" type="button" data-filter-kind="topic" data-filter-value="${escapeHTML(topic)}">${escapeHTML(topic)}</button>`
  ).join("");
  document.getElementById("quickSessions").innerHTML = sessions.slice(0, 8).map(session =>
    `<button class="side-filter" type="button" data-filter-kind="session" data-filter-value="${escapeHTML(session)}">${escapeHTML(session)}</button>`
  ).join("");
  document.querySelectorAll(".side-filter").forEach(button => {
    button.addEventListener("click", () => setFilter(button.dataset.filterKind, button.dataset.filterValue));
  });
}

function renderOverview() {
  document.getElementById("topPaperCount").textContent = meta.paperCount;
  document.getElementById("topSessionCount").textContent = meta.sessionCount;
  document.getElementById("metricPapers").textContent = meta.paperCount;
  document.getElementById("metricSessions").textContent = meta.sessionCount;
  document.getElementById("metricAvgAuthors").textContent = meta.avgAuthors.toFixed(1);
  document.getElementById("metricTopics").textContent = countBy(papers, paper => paper.topics).length;
  document.getElementById("largestSession").textContent = `${meta.largestSession[0]} has ${meta.largestSession[1]} papers.`;
  document.getElementById("sourceNote").textContent =
    `Source: ${meta.sourceFile} | abstracts ${meta.abstractCount}/${meta.paperCount} | generated ${meta.generatedAt}`;
}

function renderCharts() {
  const sessionCounts = countBy(papers, paper => paper.session);
  const topicCounts = countBy(papers, paper => paper.topics);
  const authorDistribution = countBy(papers, paper => {
    const n = paper.authorCount;
    if (n <= 3) return "1-3";
    if (n <= 6) return "4-6";
    if (n <= 10) return "7-10";
    if (n <= 15) return "11-15";
    return "16+";
  });
  const topAuthors = countBy(
    papers.flatMap(paper => paper.authorList),
    author => author
  ).filter(row => row[1] > 1).slice(0, 14);

  renderBarList(document.getElementById("sessionBars"), sessionCounts, { filterKind: "session" });
  renderBarList(document.getElementById("sessionSummary"), sessionCounts.slice(0, 8), { filterKind: "session" });
  renderBarList(document.getElementById("topicBars"), topicCounts, { filterKind: "topic", topic: true });
  renderBarList(document.getElementById("topicCoverage"), topicCounts.slice(0, 10), { filterKind: "topic", topic: true });
  renderBarList(document.getElementById("authorCountBars"), authorDistribution);
  renderBarList(document.getElementById("topAuthors"), topAuthors.length ? topAuthors : [["No repeated author names", 0]], { filterKind: "author" });
  renderHeatmap(sessionCounts.map(row => row[0]), topicCounts.filter(row => row[0] !== "Other").slice(0, 10).map(row => row[0]));
}

function renderHeatmap(sessions, topics) {
  const matrix = new Map();
  let max = 1;
  for (const paper of papers) {
    for (const topic of paper.topics) {
      if (!topics.includes(topic)) continue;
      const key = `${paper.session}||${topic}`;
      const value = (matrix.get(key) || 0) + 1;
      matrix.set(key, value);
      max = Math.max(max, value);
    }
  }
  const header = `<tr><th>Session</th>${topics.map(topic => `<th title="${escapeHTML(topic)}">${escapeHTML(shortTopic(topic))}</th>`).join("")}</tr>`;
  const body = sessions.map(session => {
    const cells = topics.map((topic, index) => {
      const count = matrix.get(`${session}||${topic}`) || 0;
      const alpha = count ? 0.12 + (count / max) * 0.72 : 0;
      const color = topicPalette[index % topicPalette.length];
      return `<td><div class="heat-cell" title="${escapeHTML(session)} / ${escapeHTML(topic)}: ${count}" style="background:${count ? hexToRgba(color, alpha) : "transparent"}">${count || ""}</div></td>`;
    }).join("");
    return `<tr><td>${escapeHTML(session)}</td>${cells}</tr>`;
  }).join("");
  document.getElementById("heatmapTable").innerHTML = header + body;
}

function shortTopic(topic) {
  return topic
    .replace(" and ", " & ")
    .replace("Human-Robot Interaction", "HRI")
    .replace("SLAM and Localization", "SLAM")
    .replace("Navigation and Planning", "Nav/Plan")
    .replace("Control and Dynamics", "Control")
    .replace("Aerial and Field Robots", "Aerial")
    .replace("Humanoids and Locomotion", "Locomotion")
    .replace("Simulation and Digital Twins", "Sim")
    .replace("Safety and Robustness", "Safety")
    .replace("Soft and Bio-inspired", "Soft");
}

function hexToRgba(hex, alpha) {
  const raw = hex.replace("#", "");
  const r = parseInt(raw.slice(0, 2), 16);
  const g = parseInt(raw.slice(2, 4), 16);
  const b = parseInt(raw.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha.toFixed(3)})`;
}

function haystack(paper) {
  return [
    paper.id,
    paper.session,
    paper.title,
    paper.authors,
    paper.abstract,
    paper.topics.join(" ")
  ].join(" ").toLowerCase();
}

function queryMatches(paper) {
  const terms = [state.q1, state.q2, state.q3].map(value => value.trim().toLowerCase()).filter(Boolean);
  if (!terms.length) return true;
  const text = haystack(paper);
  const checks = terms.map(term => term.split(/\s+/).every(token => text.includes(token)));
  return state.searchMode === "OR" ? checks.some(Boolean) : checks.every(Boolean);
}

function authorRangeMatches(paper) {
  if (!state.authorRange) return true;
  const [min, max] = state.authorRange.split("-").map(Number);
  return paper.authorCount >= min && paper.authorCount <= max;
}

function filteredPapers() {
  const rows = papers.filter(paper => {
    if (state.session && paper.session !== state.session) return false;
    if (state.topic && !paper.topics.includes(state.topic)) return false;
    if (state.author && !paper.authorList.includes(state.author)) return false;
    if (!authorRangeMatches(paper)) return false;
    if (!queryMatches(paper)) return false;
    return true;
  });
  rows.sort((a, b) => {
    if (state.sort === "title-asc") return a.title.localeCompare(b.title) || a.id - b.id;
    if (state.sort === "session-asc") return a.session.localeCompare(b.session) || a.id - b.id;
    if (state.sort === "authors-desc") return b.authorCount - a.authorCount || a.id - b.id;
    if (state.sort === "authors-asc") return a.authorCount - b.authorCount || a.id - b.id;
    return a.id - b.id;
  });
  return rows;
}

function renderActiveFilters() {
  const chips = [];
  if (state.q1 || state.q2 || state.q3) chips.push(`Search: ${[state.q1, state.q2, state.q3].filter(Boolean).join(` ${state.searchMode} `)}`);
  if (state.session) chips.push(`Session: ${state.session}`);
  if (state.topic) chips.push(`Topic: ${state.topic}`);
  if (state.author) chips.push(`Author: ${state.author}`);
  if (state.authorRange) chips.push(`Authors: ${state.authorRange.replace("-999", "+")}`);
  document.getElementById("activeFilters").innerHTML = chips.map(chip => `<button type="button" class="filter-chip" data-clear-chip="${escapeHTML(chip.split(":")[0])}">${escapeHTML(chip)} x</button>`).join("");
  document.querySelectorAll("[data-clear-chip]").forEach(button => {
    button.addEventListener("click", () => {
      const key = button.dataset.clearChip;
      if (key === "Search") {
        state.q1 = "";
        state.q2 = "";
        state.q3 = "";
        for (const id of ["q1", "q2", "q3"]) document.getElementById(id).value = "";
      }
      if (key === "Session") {
        state.session = "";
        document.getElementById("sessionFilter").value = "";
      }
      if (key === "Topic") {
        state.topic = "";
        document.getElementById("topicFilter").value = "";
      }
      if (key === "Author") state.author = "";
      if (key === "Authors") {
        state.authorRange = "";
        document.getElementById("authorFilter").value = "";
      }
      state.page = 1;
      renderResults();
    });
  });
}

function renderResults() {
  const rows = filteredPapers();
  const pageSize = state.pageSize === "all" ? rows.length || 1 : Number(state.pageSize);
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  state.page = Math.min(state.page, totalPages);
  const start = (state.page - 1) * pageSize;
  const visible = rows.slice(start, start + pageSize);

  document.getElementById("resultCount").textContent = `${rows.length} of ${papers.length} papers`;
  document.getElementById("pageInfo").textContent = rows.length ? `Page ${state.page} / ${totalPages}` : "";
  document.getElementById("papers").innerHTML = visible.length
    ? visible.map(renderPaper).join("")
    : `<div class="empty">No papers match the current filters.</div>`;
  document.querySelectorAll(".paper-title").forEach(button => {
    button.addEventListener("click", () => button.closest(".paper").classList.toggle("open"));
  });
  document.querySelectorAll("[data-paper-filter]").forEach(button => {
    button.addEventListener("click", () => setFilter(button.dataset.paperFilter, button.dataset.filterValue));
  });
  renderPager(totalPages);
  renderActiveFilters();
  updateFilterButtonStates();
  updateUrlFromState();
}

function renderPaper(paper) {
  const topics = paper.topics.map(topic =>
    `<button type="button" class="tag topic${state.topic === topic ? " active" : ""}" data-paper-filter="topic" data-filter-value="${escapeHTML(topic)}" aria-pressed="${state.topic === topic ? "true" : "false"}">${escapeHTML(topic)}</button>`
  ).join("");
  const authorButtons = paper.authorList.map(author =>
    `<button type="button" class="author-button${state.author === author ? " active" : ""}" data-paper-filter="author" data-filter-value="${escapeHTML(author)}" aria-pressed="${state.author === author ? "true" : "false"}">${escapeHTML(author)}</button>`
  ).join("");
  const abstract = paper.abstract
    ? `<p class="paper-abstract">${escapeHTML(paper.abstract)}</p>`
    : `<p class="paper-abstract">Abstract not available.</p>`;
  return `<article class="paper">
    <div class="paper-head">
      <button type="button" class="paper-title">${escapeHTML(paper.title)}</button>
      <a class="paper-link" href="${escapeHTML(paper.href)}" target="_blank" rel="noreferrer">Official page</a>
    </div>
    <div class="paper-meta">
      <span class="tag">ID ${escapeHTML(paper.id)}</span>
      <button type="button" class="tag session${state.session === paper.session ? " active" : ""}" data-paper-filter="session" data-filter-value="${escapeHTML(paper.session)}" aria-pressed="${state.session === paper.session ? "true" : "false"}">${escapeHTML(paper.session)}</button>
      <span class="tag">${paper.authorCount} authors</span>
      ${topics}
    </div>
    <div class="paper-authors"><span class="authors-label">Authors</span>${authorButtons}</div>
    <div class="paper-detail">
      ${abstract}
      <div class="detail-grid">
        <div class="detail-label">Title</div><div>${escapeHTML(paper.title)}</div>
        <div class="detail-label">Authors</div><div>${authorButtons}</div>
        <div class="detail-label">Session</div><div>${escapeHTML(paper.session)}</div>
        <div class="detail-label">Topics</div><div>${escapeHTML(paper.topics.join(", "))}</div>
      </div>
    </div>
  </article>`;
}

function renderPager(totalPages) {
  const pager = document.getElementById("pager");
  if (totalPages <= 1) {
    pager.innerHTML = "";
    return;
  }
  pager.innerHTML = `
    <button class="btn" type="button" data-page="prev" ${state.page === 1 ? "disabled" : ""}>Previous</button>
    <button class="btn" type="button" data-page="next" ${state.page === totalPages ? "disabled" : ""}>Next</button>
  `;
  pager.querySelectorAll("[data-page]").forEach(button => {
    button.addEventListener("click", () => {
      state.page += button.dataset.page === "next" ? 1 : -1;
      renderResults();
      document.getElementById("search").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function downloadCsv() {
  const rows = filteredPapers();
  const header = ["id", "session", "title", "authors", "author_count", "topics", "abstract", "official_page"];
  const lines = [header, ...rows.map(paper => [
    paper.id,
    paper.session,
    paper.title,
    paper.authors,
    paper.authorCount,
    paper.topics.join("; "),
    paper.abstract,
    paper.href
  ])].map(row => row.map(csvCell).join(","));
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "rss2026_filtered_papers.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function clearFilters() {
  Object.assign(state, {
    ...defaultState,
    page: 1
  });
  for (const id of ["q1", "q2", "q3"]) document.getElementById(id).value = "";
  document.getElementById("searchMode").value = "AND";
  document.getElementById("sessionFilter").value = "";
  document.getElementById("topicFilter").value = "";
  document.getElementById("authorFilter").value = "";
  document.getElementById("sortFilter").value = "id-asc";
  document.getElementById("pageSizeFilter").value = "500";
  renderResults();
}

function bindControls() {
  for (const id of ["q1", "q2", "q3"]) {
    document.getElementById(id).addEventListener("input", event => {
      state[id] = event.target.value;
      state.page = 1;
      renderResults();
    });
  }
  document.getElementById("searchMode").addEventListener("change", event => {
    state.searchMode = event.target.value;
    state.page = 1;
    renderResults();
  });
  document.getElementById("sessionFilter").addEventListener("change", event => {
    state.session = event.target.value;
    state.page = 1;
    renderResults();
  });
  document.getElementById("topicFilter").addEventListener("change", event => {
    state.topic = event.target.value;
    state.page = 1;
    renderResults();
  });
  document.getElementById("authorFilter").addEventListener("change", event => {
    state.authorRange = event.target.value;
    state.page = 1;
    renderResults();
  });
  document.getElementById("sortFilter").addEventListener("change", event => {
    state.sort = event.target.value;
    state.page = 1;
    renderResults();
  });
  document.getElementById("pageSizeFilter").addEventListener("change", event => {
    state.pageSize = event.target.value;
    state.page = 1;
    renderResults();
  });
  document.getElementById("clearFilters").addEventListener("click", clearFilters);
  document.getElementById("downloadCsv").addEventListener("click", downloadCsv);
  document.getElementById("brandHome").addEventListener("click", clearFilters);
}

populateSelects();
applyUrlState();
renderOverview();
renderCharts();
bindControls();
renderResults();
</script>
</body>
</html>
"""


def build() -> None:
    source = locate_source()
    papers, description = parse_papers(source)
    if not papers:
        raise RuntimeError(f"No papers parsed from {source}")
    meta = summarize(papers, source, description)
    papers_json = json.dumps(papers, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    meta_json = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = HTML_TEMPLATE.replace("__PAPERS_JSON__", papers_json).replace("__META_JSON__", meta_json)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT}")
    print(f"papers={meta['paperCount']} sessions={meta['sessionCount']} avg_authors={meta['avgAuthors']}")


if __name__ == "__main__":
    build()
