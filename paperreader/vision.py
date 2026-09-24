# -*- coding: utf-8 -*-
"""整页视觉提取：把 PDF 每页渲染成图，交给视觉 LLM 转成结构化文本。

这是 extract.py 字体启发式的替代/兜底方案，专门处理字体子集化导致正文
丢失、化学式下标、特殊字符等字体法解决不了的 PDF（如 ncomms 系列）。
"""
import base64
import json

try:
    import fitz  # pymupdf
except ImportError:  # pragma: no cover
    fitz = None

from .extract import split_sentences

PAGE_PROMPT = """你是论文版面识别助手。请把这张论文页面里出现的所有文字，
按阅读顺序完整转录出来，并给每段标注类别。

输出一个 JSON 数组，每个元素形如：
  {"type": "s", "text": "正文句子"}
  {"type": "h1", "text": "章节/文章大标题"}
  {"type": "h2", "text": "小节标题"}
  {"type": "caption", "text": "图/表题注"}
  {"type": "ref", "text": "参考文献条目"}
  {"type": "skip", "text": "页眉/页脚/页码/期刊横幅/版权声明等可忽略内容"}

要求：
1. 严格按阅读顺序（多栏时：左栏从上到下，再到右栏）。
2. 正文按句子拆分；化学式/公式转成可读文本（如 H2O、CO2，下标数字直接跟在元素后）。
3. 不要遗漏正文里的任何句子，也不要合并不同段落。
4. 只输出 JSON 数组本身，不要任何多余文字。"""


def _render_page_png(page, dpi=150):
    return page.get_pixmap(dpi=dpi).tobytes("png")


def _page_dataurl(page, dpi=150):
    png = _render_page_png(page, dpi)
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _parse_items(raw):
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
    try:
        v = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        v = None
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        # 模型偶尔会包一层 {"items": [...]} / {"result": [...]}
        for key in ("items", "content", "result", "data"):
            if isinstance(v.get(key), list):
                return v[key]
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end > start:
        try:
            v = json.loads(raw[start:end + 1])
            if isinstance(v, list):
                return v
        except (json.JSONDecodeError, ValueError):
            pass
    return []


def extract_pages(pdf_path, provider, *, dpi=150, pages=None, on_page=None):
    """整页视觉提取，返回 [(kind, text)] 单元列表。

    kind ∈ h1 / h2 / s / caption / ref / skip。pages 为要处理的页码列表
    （0 起），None 表示全部页；on_page(done, total) 用于进度反馈。
    """
    if fitz is None:
        raise RuntimeError("缺少 pymupdf，请先 `pip install pymupdf`")
    doc = fitz.open(str(pdf_path))
    units = []
    try:
        idxs = list(range(doc.page_count)) if pages is None else \
            [p for p in pages if 0 <= p < doc.page_count]
        total = len(idxs)
        for k, i in enumerate(idxs):
            dataurl = _page_dataurl(doc[i], dpi)
            items = _parse_items(provider.chat_vision(PAGE_PROMPT, [dataurl]))
            if not items:
                # 模型偶发返回空/非 JSON，重试一次
                items = _parse_items(provider.chat_vision(PAGE_PROMPT, [dataurl]))
            for it in items:
                if not isinstance(it, dict):
                    continue
                text = (it.get("text") or "").strip()
                if not text:
                    continue
                units.append((it.get("type", "s"), text))
            if on_page:
                on_page(k + 1, total)
    finally:
        doc.close()
    return units


def vision_to_document(units):
    """把视觉提取的 units 转成 (sentences, headings)，丢弃 caption/ref/skip。"""
    sentences = []
    headings = []
    sindex = 0
    for kind, text in units:
        if kind in ("h1", "h2"):
            title = text.rstrip(" .").strip()
            if title:
                headings.append({"level": kind, "title": title, "anchor": sindex})
        elif kind == "s":
            ss = split_sentences(text)
            sentences.extend(ss)
            sindex += len(ss)
    return sentences, headings
