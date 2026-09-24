# -*- coding: utf-8 -*-
"""配图提取：识别每页的图注（"Fig. N | …"），把其上方图形区域渲染成 PNG。

通用启发式（不依赖具体期刊字体）：
  1. 图注起始行 = 以 "Fig."/"Figure" + 数字 开头、且非正文字体的行；
  2. 图注范围 = 该行及下方连续的非正文行（遇到正文行即止）；
  3. 图形区域 = 页眉之下、图注之上、与图注同列（或跨栏）的矢量+位图包围盒。
"""
import io
import re

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None

from .extract import TOP_BAND, BOTTOM_BAND

_CAP_RE = re.compile(r"^\s*(Fig(?:ure)?\.?)\s*(\d+)\b", re.I)
_MARGIN = 40.0


def _iter_lines(page):
    """返回 [(y0, y1, x0, x1, text, is_body)]，按 y0 排序。"""
    d = page.get_text("dict")
    lines = []
    for blk in d.get("blocks", []):
        if blk.get("type") != 0:
            continue
        for line in blk.get("lines", []):
            x0, y0, x1, y1 = line["bbox"]
            txt = "".join(sp.get("text", "") for sp in line.get("spans", []))
            fonts = [sp.get("font", "") for sp in line.get("spans", [])]
            lines.append((y0, y1, x0, x1, txt.strip(), fonts))
    lines.sort()
    return lines


def _graphic_rects(page, y_top, y_bottom, x0, x1):
    """收集 y∈[y_top,y_bottom] 且与 [x0,x1] 相交的矢量+位图包围盒。"""
    rects = []
    for d in page.get_drawings():
        r = d["rect"]
        if r.y1 >= y_top and r.y0 <= y_bottom and r.x1 >= x0 and r.x0 <= x1:
            rects.append((r.x0, r.y0, r.x1, r.y1))
    for info in page.get_image_info():
        b = info["bbox"]
        if b[3] >= y_top and b[1] <= y_bottom and b[2] >= x0 and b[0] <= x1:
            rects.append((b[0], b[1], b[2], b[3]))
    return rects


def extract_figures(pdf_path, body_font=None, dpi=200):
    """提取整篇文献的配图，返回 [{fig, page, caption, crop_box, png_bytes}]。"""
    if fitz is None:
        raise RuntimeError("缺少 pymupdf，请先 `pip install pymupdf`")
    doc = fitz.open(str(pdf_path))
    if body_font is None:
        from .extract import detect_body_font
        body_font, _ = detect_body_font(doc)

    figures = []
    seen = set()
    for pno, page in enumerate(doc):
        ph = page.rect.height
        pw = page.rect.width
        mid = pw / 2
        lines = _iter_lines(page)
        for i, (y0, y1, x0, x1, txt, fonts) in enumerate(lines):
            m = _CAP_RE.match(txt)
            if not m or y0 < TOP_BAND or y0 > ph - BOTTOM_BAND:
                continue
            is_body = any(f == body_font for f in fonts)
            if is_body:
                continue  # 正文里的 "(Fig. 1)" 引用
            fignum = int(m.group(2))
            key = (pno, fignum)
            if key in seen:
                continue
            seen.add(key)

            # 图注范围 = 起始行 + 下方连续非正文行
            cap_lines = [(y0, y1, x0, x1, txt)]
            for j in range(i + 1, len(lines)):
                cy0, cy1, cx0, cx1, ctxt, cfonts = lines[j]
                if cy0 > ph - BOTTOM_BAND:
                    break
                if any(f == body_font for f in cfonts):
                    break
                if _CAP_RE.match(ctxt):
                    break  # 遇到下一张图注
                cap_lines.append((cy0, cy1, cx0, cx1, ctxt))

            cap_top = cap_lines[0][0]
            cap_bottom = max(c[1] for c in cap_lines)
            cap_x0 = min(c[2] for c in cap_lines)
            cap_x1 = max(c[3] for c in cap_lines)
            caption = " ".join(c[4] for c in cap_lines)

            # 判断跨栏 / 左栏 / 右栏
            spans_both = cap_x0 < mid - 15 and cap_x1 > mid + 15
            if spans_both:
                fx0, fx1 = _MARGIN, pw - _MARGIN
            elif cap_lines[0][2] < mid:
                fx0, fx1 = _MARGIN, mid
            else:
                fx0, fx1 = mid, pw - _MARGIN

            rects = _graphic_rects(page, TOP_BAND, cap_top, fx0, fx1)
            if not rects:
                continue
            gx0 = min(r[0] for r in rects)
            gy0 = min(r[1] for r in rects)
            gx1 = max(r[2] for r in rects)
            gy1 = max(r[3] for r in rects)

            pad = 6.0
            box = fitz.Rect(gx0 - pad, gy0 - pad, gx1 + pad, cap_bottom + pad)
            pm = page.get_pixmap(clip=box, dpi=dpi)
            figures.append({
                "fig": fignum,
                "page": pno,
                "caption": caption,
                "crop_box": [round(box.x0, 1), round(box.y0, 1), round(box.x1, 1), round(box.y1, 1)],
                "png_bytes": pm.tobytes("png"),
            })
    doc.close()
    return figures
