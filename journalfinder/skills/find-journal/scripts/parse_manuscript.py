#!/usr/bin/env python3
"""
parse_manuscript.py - 解析整篇论文（PDF / Word / 纯文本），提取投稿匹配所需信息

输出 JSON：标题、摘要、作者关键词、JEL 代码、章节标题、正文字数、参考文献数、
图表数、识别到的研究方法 / 数据来源 / 研究地区、文章类型推断，以及建议的检索关键词。

支持格式：
  .docx         标准库解析（无需额外依赖）
  .pdf          需要 pypdf（requirements.txt 已包含）；扫描件无文本层时会报错提示
  .txt / .md    直接读取

Usage:
    python parse_manuscript.py paper.pdf
    python parse_manuscript.py paper.docx --include-text
"""

import argparse
import json
import os
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree


W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

SECTION_HEADINGS = (
    "abstract", "introduction", "background", "literature review",
    "related literature", "theoretical framework", "theory", "hypotheses",
    "institutional background", "data", "data and methods", "data and methodology",
    "methods", "methodology", "materials and methods", "research design",
    "empirical strategy", "identification strategy", "model", "empirical results",
    "results", "findings", "discussion", "robustness", "robustness checks",
    "heterogeneity", "mechanisms", "conclusion", "conclusions",
    "concluding remarks", "policy implications", "limitations",
    "references", "bibliography", "works cited", "appendix", "acknowledgements",
    "acknowledgments", "funding", "declaration of competing interest",
    "引言", "文献综述", "研究设计", "数据", "实证结果", "结论", "参考文献", "附录",
)
END_OF_BODY = (
    "references", "bibliography", "works cited", "参考文献",
)
FRONT_MATTER = ("abstract", "摘要", "keywords", "key words", "关键词")
BACK_MATTER = END_OF_BODY + (
    "appendix", "acknowledgements", "acknowledgments", "funding",
    "declaration of competing interest", "附录",
)

# (label, regex) — matched case-insensitively on the full text.
METHOD_PATTERNS = (
    ("difference-in-differences", r"difference[- ]in[- ]differences?|\bDiD\b|event[- ]study|staggered adoption|双重差分"),
    ("regression discontinuity", r"regression discontinuity|\bRDD?\b design|断点回归"),
    ("instrumental variables", r"instrumental variables?|\b2SLS\b|two[- ]stage least squares|工具变量"),
    ("randomized experiment", r"randomi[sz]ed (?:controlled )?(?:trial|experiment)|\bRCT\b|field experiment|随机对照"),
    ("synthetic control", r"synthetic control|合成控制"),
    ("propensity score matching", r"propensity score|\bPSM\b|倾向得分"),
    ("panel fixed effects", r"fixed[- ]effects?|panel data|面板数据|固定效应"),
    ("structural model", r"structural (?:model|estimation)|\bGMM\b|maximum likelihood|DSGE"),
    ("time series", r"\bVAR\b model|vector autoregress|cointegration|local projections?|\bARIMA\b"),
    ("machine learning", r"machine learning|random forest|neural network|\bLASSO\b|deep learning|text analysis|机器学习"),
    ("structural equation modeling", r"structural equation model|\bSEM\b|\bPLS-SEM\b|confirmatory factor"),
    ("meta-analysis", r"meta[- ]analysis|systematic review|荟萃分析"),
    ("survey", r"\bsurvey (?:data|respondents|questionnaire)|questionnaire|问卷"),
    ("qualitative", r"semi[- ]structured interviews?|ethnograph|case stud(?:y|ies)|grounded theory|thematic analysis|focus groups?|访谈"),
    ("laboratory experiment", r"laboratory experiment|lab experiment|vignette experiment|conjoint"),
    ("simulation", r"agent[- ]based|monte carlo simulation|simulation model"),
)
DATA_PATTERNS = (
    ("CFPS", r"\bCFPS\b|China Family Panel"),
    ("CHARLS", r"\bCHARLS\b"),
    ("CGSS", r"\bCGSS\b"),
    ("CHNS", r"\bCHNS\b"),
    ("Chinese listed firms (CSMAR/Wind)", r"\bCSMAR\b|\bWind\b database|A-share"),
    ("Compustat/CRSP", r"\bCompustat\b|\bCRSP\b"),
    ("PSID", r"\bPSID\b|Panel Study of Income Dynamics"),
    ("NLSY", r"\bNLSY"),
    ("CPS/ACS", r"Current Population Survey|American Community Survey|\bACS\b data"),
    ("HRS/SHARE", r"Health and Retirement Study|\bSHARE\b survey"),
    ("DHS", r"Demographic and Health Surve"),
    ("World Bank WDI", r"World Development Indicators"),
    ("patent data", r"\bpatents? (?:data|applications|citations)|USPTO|PATSTAT"),
    ("census", r"\bcensus (?:data|microdata)|人口普查"),
    ("administrative data", r"administrative (?:data|records|register)"),
)
GEOGRAPHY_PATTERNS = (
    ("China", r"\bChina\b|\bChinese\b|中国"),
    ("United States", r"\bUnited States\b|\bU\.S\.|\bUS (?:states|counties|firms)"),
    ("United Kingdom", r"\bUnited Kingdom\b|\bUK\b|\bBritain\b|\bEngland\b"),
    ("Europe/EU", r"\bEurope(?:an)?\b|\bEU\b member"),
    ("India", r"\bIndia\b|\bIndian\b"),
    ("Japan", r"\bJapan(?:ese)?\b"),
    ("Africa", r"\bAfrica(?:n)?\b"),
    ("Latin America", r"Latin America|\bBrazil\b|\bMexico\b"),
    ("OECD/cross-country", r"\bOECD\b|cross[- ]country|\bcountries\b panel"),
)
STOPWORDS = set("""
a about above across after again against all also although among an and any are as at be because been
before being between both but by can could did do does during each either et al etc for from further
had has have having here how however if in into is it its itself more most much must new no nor not
of on once only or other our out over own paper per same should since so some such than that the their
them then there these they this those through thus to too under until up upon us using use used very
was we were what when where whether which while who whom why will with within would yet study
studies result results show shows find finds found evidence effect effects impact impacts based
article research analysis data approach also however paper's furthermore moreover two one three
""".split())


def read_docx(path):
    """Return a list of (style, text) paragraphs from a .docx using only the stdlib."""
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    paragraphs = []
    for para in root.iter(f"{W_NS}p"):
        style = ""
        ppr = para.find(f"{W_NS}pPr")
        if ppr is not None:
            pstyle = ppr.find(f"{W_NS}pStyle")
            if pstyle is not None:
                style = pstyle.get(f"{W_NS}val", "")
        pieces = []
        for node in para.iter():
            if node.tag == f"{W_NS}t" and node.text:
                pieces.append(node.text)
            elif node.tag == f"{W_NS}tab":
                pieces.append(" ")
            elif node.tag in (f"{W_NS}br", f"{W_NS}cr"):
                pieces.append("\n")
        text = "".join(pieces).strip()
        if text:
            paragraphs.append((style, text))
    return paragraphs


def read_pdf(path):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Reading PDF requires pypdf: python -m pip install pypdf") from exc
    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    text = "\n".join(pages)
    if len(text.strip()) < 200:
        raise RuntimeError(
            "PDF has no usable text layer (scanned image?). "
            "Export a text PDF or Word file, or paste the title and abstract instead."
        )
    meta_title = None
    try:
        meta_title = (reader.metadata or {}).get("/Title")
    except Exception:  # pragma: no cover - malformed metadata
        meta_title = None
    return [("", line) for line in text.splitlines()], meta_title, len(pages)


def read_text(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    paragraphs = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        style = "Heading" if re.match(r"^#{1,6}\s", stripped) else ""
        paragraphs.append((style, stripped.lstrip("#").strip()))
    return paragraphs


def normalize_heading(text):
    text = re.sub(r"^\s*(?:[IVXLC]+\.|\d+(?:\.\d+)*\.?|[A-Z]\.|第[一二三四五六七八九十]+[章节部分])\s*", "", text)
    return re.sub(r"[\s:：.]+$", "", text).strip()


def heading_key(text):
    return normalize_heading(text).lower()


def is_heading(style, text):
    if style and re.match(r"(?i)heading|标题", style) and len(text) < 160:
        return True
    if len(text) > 80 or text.endswith((".", ",", ";")) and not re.match(r"^\d", text):
        return False
    key = heading_key(text)
    if key in SECTION_HEADINGS:
        return True
    # Numbered headings like "3. Data and Empirical Strategy" / "4.1 Baseline results"
    return bool(re.match(r"^\s*(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s+[A-Z一-鿿]", text)) and len(text.split()) <= 10


def count_words(text):
    """English words plus CJK characters (each CJK char counts as one word)."""
    cjk = len(re.findall(r"[一-鿿]", text))
    latin = len(re.findall(r"[A-Za-z][A-Za-z'\-]*|\d+(?:\.\d+)?", text))
    return latin + cjk


def find_labeled(text, labels, max_len=600):
    pattern = r"(?im)^\s*(?:%s)\s*[:：.\-—]?\s*(.+)$" % "|".join(labels)
    match = re.search(pattern, text)
    return match.group(1).strip()[:max_len] if match else None


def split_keywords(raw):
    if not raw:
        return []
    raw = re.split(r"(?i)\bJEL\b", raw)[0]
    parts = re.split(r"[;；,，·•|]", raw)
    return [p.strip(" .") for p in parts if 1 < len(p.strip(" .")) < 60][:12]


def extract_abstract(paragraphs, full_text):
    for index, (_, text) in enumerate(paragraphs):
        key = heading_key(text)
        inline = re.match(r"(?i)^\s*(abstract|摘要)\s*[:：.\-—]?\s*(.{80,})", text)
        if inline:
            return inline.group(2).strip()[:3000]
        if key in ("abstract", "摘要"):
            collected = []
            for _, following in paragraphs[index + 1:]:
                fkey = heading_key(following)
                if fkey in SECTION_HEADINGS or re.match(r"(?i)^(keywords?|key words|jel|关键词)", following):
                    break
                collected.append(following)
                if sum(len(c) for c in collected) > 2500:
                    break
            if collected:
                return " ".join(collected)[:3000]
    return None


def extract_title(paragraphs, meta_title=None):
    for style, text in paragraphs[:15]:
        if re.match(r"(?i)^title$", style) and len(text) > 10:
            return text
    if meta_title and len(meta_title) > 10 and not meta_title.lower().endswith((".docx", ".pdf", ".doc")):
        return meta_title.strip()
    for _, text in paragraphs[:25]:
        key = heading_key(text)
        if key in SECTION_HEADINGS:
            break
        if (
            15 <= len(text) <= 250
            and not re.search(r"@|https?://|university|department|\bdoi\b|received|accepted|^\d+$", text, re.I)
            and len(text.split()) >= 3
        ):
            return text
    return None


def split_sections(paragraphs):
    sections = []
    current = {"heading": None, "paragraphs": []}
    for style, text in paragraphs:
        if is_heading(style, text):
            sections.append(current)
            current = {"heading": normalize_heading(text), "paragraphs": []}
        else:
            current["paragraphs"].append(text)
    sections.append(current)
    return [s for s in sections if s["heading"] or s["paragraphs"]]


def count_references(sections, full_text):
    ref_text = ""
    for section in sections:
        if section["heading"] and heading_key(section["heading"]) in END_OF_BODY:
            ref_text = "\n".join(section["paragraphs"])
            break
    if not ref_text:
        return 0
    numbered = len(re.findall(r"(?m)^\s*(?:\[\d+\]|\d+\.)\s+", ref_text))
    if numbered >= 3:
        return numbered
    # Author-year style: count entries that contain a year.
    lines = [line for line in ref_text.split("\n") if re.search(r"\(?(?:19|20)\d{2}[a-z]?\)?", line)]
    return len(lines)


def detect(patterns, text, min_hits=1):
    found = []
    for label, pattern in patterns:
        hits = len(re.findall(pattern, text, flags=re.I))
        if hits >= min_hits:
            found.append({"label": label, "mentions": hits})
    return sorted(found, key=lambda item: -item["mentions"])


def guess_article_type(title, abstract, sections, methods):
    head = f"{title or ''} {abstract or ''}".lower()
    headings = {heading_key(s["heading"]) for s in sections if s["heading"]}
    if re.search(r"systematic review|meta[- ]analysis|literature review|a review of|综述", head):
        return "review"
    if re.search(r"\bcomment on\b|\breply\b|\bcorrigendum\b", head):
        return "comment"
    if {"data", "results", "empirical results", "findings", "methods", "methodology"} & headings or methods:
        return "empirical"
    if re.search(r"\btheor(?:y|etical)\b|\bmodel\b|\bproposition\b|\btheorem\b", head):
        return "theoretical"
    return "unknown"


def candidate_phrases(text, top=12):
    """Frequent 2-3 word phrases from title + abstract, as fallback keywords."""
    tokens = re.findall(r"[a-z][a-z\-]+", text.lower())
    counts = Counter()
    for size in (3, 2):
        for i in range(len(tokens) - size + 1):
            gram = tokens[i:i + size]
            if gram[0] in STOPWORDS or gram[-1] in STOPWORDS or any(len(t) < 3 for t in gram):
                continue
            if any(t in STOPWORDS for t in gram[1:-1]):
                continue
            counts[" ".join(gram)] += 2 if size == 3 else 1
    phrases = []
    for phrase, _ in counts.most_common(top * 3):
        if any(phrase in kept or kept in phrase for kept in phrases):
            continue
        phrases.append(phrase)
        if len(phrases) >= top:
            break
    return phrases


def suggest_keywords(author_keywords, title, abstract):
    """Author keywords first; frequent title/abstract phrases only fill gaps."""
    seen, result = set(), []
    fallback = []
    if len(author_keywords) < 4:
        fallback = candidate_phrases(f"{title or ''}. {title or ''}. {abstract or ''}", 8)
    for keyword in author_keywords + fallback:
        key = keyword.lower()
        if key not in seen:
            seen.add(key)
            result.append(keyword)
    return result[:8]


def resolve_manuscript_path(path):
    """Resolve a manuscript path; relative paths may live under a host project root.

    Metrics AI runs skill scripts with cwd = skill root and passes the user's
    project root as METRICS_AI_PROJECT_ROOT, so "paper.pdf" means
    <project>/paper.pdf there. Elsewhere relative paths resolve from cwd.
    """
    path = Path(path).expanduser()
    if path.is_absolute() or path.is_file():
        return path
    project_root = os.environ.get("METRICS_AI_PROJECT_ROOT", "").strip()
    if project_root:
        candidate = Path(project_root) / path
        if candidate.is_file():
            return candidate
    return path


def parse_manuscript(path, include_text=False):
    path = resolve_manuscript_path(path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    suffix = path.suffix.lower()
    meta_title, pages = None, None
    if suffix == ".docx":
        paragraphs = read_docx(path)
    elif suffix == ".pdf":
        paragraphs, meta_title, pages = read_pdf(path)
    elif suffix in (".txt", ".md", ".markdown", ".tex"):
        paragraphs = read_text(path)
    elif suffix == ".doc":
        raise RuntimeError("Legacy .doc is not supported; save the file as .docx or PDF.")
    else:
        raise RuntimeError(f"Unsupported file type: {suffix}")

    full_text = "\n".join(text for _, text in paragraphs)
    sections = split_sections(paragraphs)

    # Body = main text from the first content heading up to back matter;
    # title block, abstract and keyword lines are excluded.
    has_content_heading = any(
        s["heading"] and heading_key(s["heading"]) not in FRONT_MATTER + BACK_MATTER
        for s in sections
    )
    body_words, past_body, total_words = 0, False, 0
    for section in sections:
        words = count_words(" ".join(section["paragraphs"]))
        total_words += words + (count_words(section["heading"]) if section["heading"] else 0)
        key = heading_key(section["heading"]) if section["heading"] else None
        if key in BACK_MATTER:
            past_body = True
        if past_body:
            continue
        if has_content_heading and (key is None or key in FRONT_MATTER):
            continue
        body_words += words

    title = extract_title(paragraphs, meta_title)
    abstract = extract_abstract(paragraphs, full_text)
    author_keywords = split_keywords(find_labeled(full_text, ["keywords?", "key words", "index terms", "关键词"]))
    jel_raw = find_labeled(full_text, [r"JEL(?: classification)?(?: codes?)?", "JEL"], 200) or ""
    jel = sorted(set(re.findall(r"\b[A-Z]\d{1,2}\b", jel_raw)))
    # PDF lines break mid-phrase ("event\nstudy", "difference-in-\ndifferences").
    match_text = re.sub(r"\s+", " ", re.sub(r"-\s*\n\s*", "-", full_text))
    methods = detect(METHOD_PATTERNS, match_text)
    result = {
        "source_path": str(path),
        "format": suffix.lstrip("."),
        "pages": pages,
        "title": title,
        "abstract": abstract,
        "abstract_words": count_words(abstract) if abstract else 0,
        "author_keywords": author_keywords,
        "jel_codes": jel,
        "section_headings": [s["heading"] for s in sections if s["heading"]][:40],
        "word_count_total": total_words,
        "word_count_body": body_words,
        "reference_count": count_references(sections, full_text),
        "figure_count": len(set(re.findall(r"(?im)^\s*(?:Figure|Fig\.)\s*(\d+)", full_text))),
        "table_count": len(set(re.findall(r"(?im)^\s*Table\s*(\d+)", full_text))),
        "methods": methods,
        "data_sources": detect(DATA_PATTERNS, match_text),
        "geography": detect(GEOGRAPHY_PATTERNS, match_text, min_hits=2),
        "article_type": guess_article_type(title, abstract, sections, methods),
        "suggested_keywords": suggest_keywords(author_keywords, title, abstract),
        "warnings": [],
    }
    if not title:
        result["warnings"].append("title_not_detected")
    if not abstract:
        result["warnings"].append("abstract_not_detected")
    if not result["reference_count"]:
        result["warnings"].append("references_not_detected")
    if include_text:
        result["text"] = full_text
    return result


def main():
    parser = argparse.ArgumentParser(description="Parse a manuscript (PDF/DOCX/TXT) for journal matching")
    parser.add_argument("path", type=Path)
    parser.add_argument("--include-text", action="store_true", help="Also emit the extracted full text")
    args = parser.parse_args()
    try:
        result = parse_manuscript(args.path, include_text=args.include_text)
    except (OSError, RuntimeError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
