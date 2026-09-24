# -*- coding: utf-8 -*-
"""命令行入口：把任意 PDF 转成交互阅读器 HTML。

用法:
  python -m paperreader in.pdf -o reader.html
  python -m paperreader in.pdf --title "标题" --meta "作者 — 期刊" [--no-figures]
"""
import argparse

from .extract import build_document, clean, extract, parse_units
from .figures import extract_figures
from .reader import build_reader
from .agents import load_provider, load_vision_provider
from .vision import extract_pages, vision_to_document


def _build_zh(provider, sentences, headings):
    """用 LLM 逐句翻译，按文档顺序交织成句级对齐 zh 列表。

    zh 每项：{"type":"h1"|"h2","text":...} 或 {"type":"s","id":"s-0001","text":...}。
    """
    from collections import defaultdict
    h_zh = provider.translate_sentences([h["title"] for h in headings]) if headings else []
    s_zh = provider.translate_sentences(sentences)
    by_anchor = defaultdict(list)
    for h, t in zip(headings, h_zh):
        by_anchor[h["anchor"]].append({"type": h["level"], "text": t})
    zh = []
    for i in range(len(sentences)):
        zh.extend(by_anchor.get(i, []))
        zh.append({"type": "s", "id": "s-%04d" % (i + 1), "text": s_zh[i]})
    for k in sorted(by_anchor):
        if k >= len(sentences):
            zh.extend(by_anchor[k])
    return zh


def main(argv=None):
    ap = argparse.ArgumentParser(description="任意文献交互阅读器")
    ap.add_argument("pdf", help="输入 PDF 路径")
    ap.add_argument("-o", "--out", default="reader.html", help="输出 HTML（默认 reader.html）")
    ap.add_argument("--title", default="")
    ap.add_argument("--meta", default="")
    ap.add_argument("--abstract", default="")
    ap.add_argument("--no-figures", action="store_true", help="不提取配图")
    ap.add_argument("--vision", action="store_true", help="用视觉 LLM 整页提取（兜底乱码 PDF）")
    ap.add_argument("--annotations", default=None, help="注解 JSON（可选）")
    ap.add_argument("--glossary", default=None, help="术语表 JSON（可选）")
    ap.add_argument("--zh", default=None, help="译文 JSON（可选，句级对齐格式）")
    ap.add_argument("--gen-zh", default=None, help="用 LLM 逐句翻译并写入该 JSON（首次生成，之后用 --zh 复用）")
    args = ap.parse_args(argv)

    if args.vision:
        units = extract_pages(args.pdf, load_vision_provider())
        sentences, headings = vision_to_document(units)
    else:
        sentences, headings = build_document(parse_units(clean(extract(args.pdf))))
    figures = [] if args.no_figures else extract_figures(args.pdf)

    import json
    annotations = json.loads(open(args.annotations, encoding="utf-8").read()) if args.annotations else {}
    glossary = json.loads(open(args.glossary, encoding="utf-8").read()) if args.glossary else {}
    zh = json.loads(open(args.zh, encoding="utf-8").read()) if args.zh else []
    if args.gen_zh:
        zh = _build_zh(load_provider(), sentences, headings)
        with open(args.gen_zh, "w", encoding="utf-8") as fh:
            json.dump(zh, fh, ensure_ascii=False, indent=1)

    html = build_reader(
        sentences, headings,
        title=args.title, meta=args.meta, abstract=args.abstract,
        annotations=annotations, glossary=glossary, zh=zh, figures=figures,
    )
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)

    print("sentences: %d" % len(sentences))
    print("headings: %d" % len(headings))
    print("figures: %d" % len(figures))
    print("zh items: %d" % len(zh))
    print("out: %s" % args.out)


if __name__ == "__main__":
    main()
