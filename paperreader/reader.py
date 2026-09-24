# -*- coding: utf-8 -*-
"""把提取结果（句子/标题/配图/注解/术语/译文）组装成交互阅读器 HTML。"""
import base64
import html
import json
import re
from collections import defaultdict
from pathlib import Path

TEMPLATE = Path(__file__).with_name("template.html").read_text(encoding="utf-8")


def build_sentences_html(sentences, headings, fig_at=None):
    fig_at = fig_at or {}
    by_anchor = defaultdict(list)
    for h in headings:
        by_anchor[h["anchor"]].append(h)
    out = []
    counter = 0
    for i, s in enumerate(sentences):
        for h in by_anchor.get(i, []):
            out.append(
                '<div class="sec-head %s" id="hd-%d"><span>%s</span></div>'
                % (h["level"], counter, html.escape(h["title"]))
            )
            counter += 1
        sid = "s-%04d" % (i + 1)
        out.append(
            '    <div class="sentence" data-id="%s"><span class="s-text">%s</span></div>'
            % (sid, html.escape(s))
        )
        for fig_html in fig_at.get(i, []):
            out.append(fig_html)
    return "\n".join(out)


def build_toc(headings, sentences):
    toc = []
    for i, h in enumerate(headings):
        anchor = None
        if 0 <= h["anchor"] < len(sentences):
            anchor = "s-%04d" % (h["anchor"] + 1)
        toc.append({"level": h["level"], "title": h["title"], "anchor": anchor, "id": "hd-%d" % i})
    return toc


def _first_ref_index(sentences, n):
    pat = re.compile(r"Fig\.?\s*%d" % n)
    for i, s in enumerate(sentences):
        if pat.search(s):
            return i
    return None


def _caption_title(caption, n):
    t = caption.replace("Fig. %d | " % n, "", 1)
    t = re.split(r"\s*Fig\.?\s*%d\s*\|" % n, t, 1)[-1]
    return t.split(". ")[0].strip()


def _figure_html(n, png_bytes, caption):
    dataurl = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
    title = _caption_title(caption, n)
    return (
        '<figure class="fig" data-fig="%d">'
        '<img src="%s" alt="Fig. %d — %s" title="%s" loading="lazy">'
        '<figcaption>Fig. %d · 点击图片放大</figcaption>'
        '</figure>'
    ) % (n, dataurl, n, html.escape(title), html.escape(title), n)


def build_reader(sentences, headings, *, title, meta, abstract="",
                 annotations=None, glossary=None, zh=None, figures=None):
    """figures: [{fig, caption, png_bytes}]。"""
    annotations = annotations or {}
    glossary = glossary or {}
    zh = zh or []
    figures = figures or []

    toc = build_toc(headings, sentences)

    fig_at = {}
    for f in figures:
        idx = _first_ref_index(sentences, f["fig"])
        if idx is None:
            continue
        fig_at.setdefault(idx, []).append(_figure_html(f["fig"], f["png_bytes"], f["caption"]))

    return (
        TEMPLATE
        .replace("__TITLE__", html.escape(title))
        .replace("__META__", html.escape(meta))
        .replace("__ABSTRACT__", "<b>摘要</b> " + html.escape(abstract) if abstract else "")
        .replace("__SENTENCES__", build_sentences_html(sentences, headings, fig_at))
        .replace("__ANNOTATIONS__", json.dumps(annotations, ensure_ascii=False))
        .replace("__GLOSSARY__", json.dumps(glossary, ensure_ascii=False))
        .replace("__TOC__", json.dumps(toc, ensure_ascii=False))
        .replace("__ZH__", json.dumps(zh, ensure_ascii=False))
    )
