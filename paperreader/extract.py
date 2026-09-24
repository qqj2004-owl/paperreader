# -*- coding: utf-8 -*-
"""PDF 文本提取：按字体自动识别正文 / 标题（H1/H2），输出带哨兵标记的文本流。

哨兵用私有区字符 \\ue000 包裹标题（不用 \\x1e，因为它的 isspace() 为 True，
会被 clean() 里 `re.sub(r"\\s*\\n\\s*", " ", text)` 吞掉）。
"""
import re
from collections import Counter

try:
    import fitz  # pymupdf
except ImportError:  # pragma: no cover
    fitz = None

H1_PREFIX = "H1:"
H2_PREFIX = "H2:"
HEADING_END = ""

# 页眉/页脚过滤带（单位：point，距页顶/页底）
TOP_BAND = 68.0
BOTTOM_BAND = 55.0


def analyze_fonts(doc):
    """统计每种 (font, size) 出现的字符数，返回 Counter。"""
    counts = Counter()
    for page in doc:
        d = page.get_text("dict")
        for blk in d.get("blocks", []):
            if blk.get("type") != 0:
                continue
            for line in blk.get("lines", []):
                for sp in line.get("spans", []):
                    t = sp.get("text", "").strip()
                    if len(t) < 2:
                        continue
                    counts[(sp.get("font", ""), round(sp.get("size", 0), 1))] += len(t)
    return counts


def detect_body_font(doc):
    """推断正文字体 = 出现字符数最多的 (font, size)。"""
    counts = analyze_fonts(doc)
    if not counts:
        return "", 9.0
    (font, size), _ = counts.most_common(1)[0]
    return font, size


def classify_span(sp, body_font, body_size, inline=False):
    """对单个 span 归类，返回 (kind, text)，kind ∈ h1 / h2 / body / None。

    inline=True 表示该 span 所在行含正文字体（行内片段，如 "Fig. 1a" 引用、
    上标数字），此时小字号片段也应保留为正文；否则小字号（图注/脚注/参考文献）
    整行丢弃。子标题字体名常被截断（如 "BoldItali"），故用 "itali" 而非 "italic"。
    """
    txt = sp.get("text", "")
    if not txt.strip():
        return None, ""
    font = sp.get("font", "")
    size = sp.get("size", 0)
    low = font.lower()

    # 字号明显偏小：行内保留，独立行丢弃
    if size < body_size - 0.6:
        return ("body", txt) if inline else (None, "")
    # 正文字体且字号接近 → 正文
    if font == body_font and abs(size - body_size) < 0.2:
        return "body", txt
    # 斜体/粗斜体 → H2 子标题
    if ("itali" in low or "oblique" in low) and size >= body_size - 0.15:
        return "h2", txt
    # 粗/黑/半粗/中黑 → H1 章节/文章标题
    if any(k in low for k in ("black", "bold", "semibold", "heavy", "medium")) and size >= body_size - 0.15:
        return "h1", txt
    # 明显偏大的短字（期刊横幅/logo，如 "REVIEWS"）→ 丢弃
    if size >= body_size + 1.5 and len(txt.strip()) <= 20:
        return None, ""
    # Light/Regular 等其它字体、字号接近正文 → 正文（摘要、作者行等）
    if size >= body_size - 0.6:
        return "body", txt
    return None, ""


def extract(pdf_path):
    """提取 PDF，返回带标题哨兵的字符串（正文与标题混合，\\n 分隔）。"""
    if fitz is None:
        raise RuntimeError("缺少 pymupdf，请先 `pip install pymupdf`")
    doc = fitz.open(str(pdf_path))
    body_font, body_size = detect_body_font(doc)
    chunks = []
    for page in doc:
        ph = page.rect.height
        pw = page.rect.width
        mid = pw / 2
        d = page.get_text("dict")
        cols = [[], []]  # 左栏 / 右栏，元素 (y0, x0, token_list)
        for blk in d.get("blocks", []):
            if blk.get("type") != 0:
                continue
            x0, y0, x1, y1 = blk["bbox"]
            if y1 < TOP_BAND or y0 > ph - BOTTOM_BAND:
                continue
            cx = (x0 + x1) / 2
            col = 0 if cx < mid else 1
            toks = []
            cur_kind = None
            cur_parts = []

            def flush():
                nonlocal cur_kind, cur_parts
                if cur_parts:
                    toks.append((cur_kind, "".join(cur_parts).strip()))
                    cur_parts = []

            for line in blk.get("lines", []):
                spans = line.get("spans", [])
                line_has_body = any(
                    sp.get("font", "") == body_font and abs(sp.get("size", 0) - body_size) < 0.2
                    for sp in spans
                )
                for sp in spans:
                    kind, txt = classify_span(sp, body_font, body_size, inline=line_has_body)
                    if kind is None:
                        continue
                    if kind != cur_kind:
                        flush()
                        cur_kind = kind
                    cur_parts.append(txt)
            flush()
            if toks:
                cols[col].append((round(y0), round(x0), toks))
        for col in cols:
            col.sort()
            for _, _, toks in col:
                for kind, txt in toks:
                    if kind == "h1":
                        chunks.append(H1_PREFIX + txt + HEADING_END)
                    elif kind == "h2":
                        chunks.append(H2_PREFIX + txt + HEADING_END)
                    else:
                        chunks.append(txt)
    doc.close()
    return "\n".join(chunks)


def clean(text):
    """清洗：去零宽/软连字符/BOM、合并换行、拆行连字符合并、压缩空白。"""
    text = text.replace("​", "").replace("­", "").replace("﻿", "")
    text = re.sub(r"=====\s*PAGE\s*\d+\s*=====", "\n", text, flags=re.I)
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def parse_units(text):
    """把带哨兵的文本解析为 [(kind, text)]。"""
    units = []
    for p in text.split(HEADING_END):
        p = p.strip()
        if not p:
            continue
        if p.startswith("H1:"):
            units.append(("h1", p[3:].strip()))
        elif p.startswith("H2:"):
            units.append(("h2", p[3:].strip()))
        else:
            units.append(("body", p))
    return units


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s*(?=[A-Z(“‘])", text)
    return [p.strip() for p in parts if p.strip()]


def build_document(units):
    """(sentences, headings)。headings 每项含 level/title/anchor。"""
    sentences = []
    headings = []
    sindex = 0
    for kind, text in units:
        if kind in ("h1", "h2"):
            title = text.rstrip(" .").strip()
            if title:
                headings.append({"level": kind, "title": title, "anchor": sindex})
        else:
            ss = split_sentences(text)
            sentences.extend(ss)
            sindex += len(ss)
    return sentences, headings
