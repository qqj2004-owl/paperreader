# -*- coding: utf-8 -*-
"""本地网页外壳：Flask 服务，浏览器打开后上传任意 PDF 即生成交互阅读器。"""
import base64
import hashlib
import io
import json
import os

from flask import Flask, jsonify, request, send_from_directory

from .extract import build_document, clean, extract, parse_units
from .figures import extract_figures
from .agents import ProviderError, load_provider, load_vision_provider
from .vision import extract_pages, vision_to_document
from .reader import build_reader

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


def _doc_key(pdf_bytes):
    """用 PDF 内容哈希作为文档唯一标识，让同一篇论文的阅读进度跨启动复用。"""
    return hashlib.md5(pdf_bytes).hexdigest()


def _state_path(app, doc):
    d = os.path.join(app.instance_path, "state")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, doc + ".json")


def create_app(config=None):
    app = Flask(__name__, static_folder=WEB_DIR, static_url_path="")

    @app.route("/")
    def index():
        return send_from_directory(WEB_DIR, "index.html")

    @app.route("/api/extract", methods=["POST"])
    def api_extract():
        f = request.files.get("file")
        if f is None:
            return jsonify({"error": "缺少文件"}), 400
        pdf_bytes = f.read()
        tmp = os.path.join(app.instance_path, "upload.pdf")
        os.makedirs(app.instance_path, exist_ok=True)
        with open(tmp, "wb") as fh:
            fh.write(pdf_bytes)
        try:
            sentences, headings = build_document(parse_units(clean(extract(tmp))))
            figs = extract_figures(tmp)
            fig_data = [{
                "fig": x["fig"], "caption": x["caption"],
                "dataurl": "data:image/png;base64," + base64.b64encode(x["png_bytes"]).decode("ascii"),
            } for x in figs]
        except Exception as e:  # noqa: BLE001
            return jsonify({"error": "提取失败: %s" % e}), 500
        return jsonify({
            "sentences": sentences,
            "headings": headings,
            "figures": fig_data,
        })

    @app.route("/render", methods=["POST"])
    def render_pdf():
        """上传 PDF → 直接返回完整交互阅读器 HTML（浏览器导航到结果页）。"""
        f = request.files.get("file")
        if f is None:
            return "缺少文件", 400
        pdf_bytes = f.read()
        tmp = os.path.join(app.instance_path, "upload.pdf")
        os.makedirs(app.instance_path, exist_ok=True)
        with open(tmp, "wb") as fh:
            fh.write(pdf_bytes)
        title = (request.form.get("title") or "").strip()
        meta = (request.form.get("meta") or "").strip()
        abstract = (request.form.get("abstract") or "").strip()
        use_vision = (request.form.get("vision") or "").strip() in ("1", "true", "on", "yes")
        doc = _doc_key(pdf_bytes)
        state = {}
        state_file = _state_path(app, doc)
        if os.path.exists(state_file):
            try:
                with open(state_file, encoding="utf-8") as fh:
                    state = json.load(fh)
            except (OSError, ValueError):
                state = {}
        try:
            if use_vision:
                sentences, headings = vision_to_document(
                    extract_pages(tmp, load_vision_provider(config)))
            else:
                sentences, headings = build_document(parse_units(clean(extract(tmp))))
            figs = extract_figures(tmp)
            html = build_reader(sentences, headings, title=title, meta=meta,
                                abstract=abstract, figures=figs, doc=doc, state=state)
        except Exception as e:  # noqa: BLE001
            return "生成失败: %s" % e, 500
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.route("/api/explain", methods=["POST"])
    def api_explain():
        body = request.get_json(force=True, silent=True) or {}
        sentence = (body.get("sentence") or "").strip()
        if not sentence:
            return jsonify({"error": "缺少句子"}), 400
        try:
            provider = load_provider(config)
            return jsonify({"explanation": provider.explain(sentence)})
        except ProviderError as e:
            return jsonify({"error": str(e)}), 503

    @app.route("/api/translate", methods=["POST"])
    def api_translate():
        body = request.get_json(force=True, silent=True) or {}
        text = (body.get("text") or "").strip()
        if not text:
            return jsonify({"error": "缺少文本"}), 400
        try:
            provider = load_provider(config)
            return jsonify({"zh": provider.translate(text)})
        except ProviderError as e:
            return jsonify({"error": str(e)}), 503

    @app.route("/api/glossary", methods=["POST"])
    def api_glossary():
        body = request.get_json(force=True, silent=True) or {}
        text = (body.get("text") or "").strip()
        if not text:
            return jsonify({"error": "缺少文本"}), 400
        try:
            provider = load_provider(config)
            return jsonify({"terms": provider.glossary(text)})
        except ProviderError as e:
            return jsonify({"error": str(e)}), 503

    @app.route("/api/state/<doc>", methods=["GET"])
    def api_state_get(doc):
        p = _state_path(app, doc)
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as fh:
                    return jsonify(json.load(fh))
            except (OSError, ValueError):
                pass
        return jsonify({})

    @app.route("/api/state/<doc>", methods=["POST"])
    def api_state_save(doc):
        body = request.get_json(force=True, silent=True) or {}
        p = _state_path(app, doc)
        try:
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(body, fh, ensure_ascii=False)
            return jsonify({"ok": True})
        except OSError as e:
            return jsonify({"error": str(e)}), 500

    return app


def main():
    app = create_app()
    print("paperreader 已启动: http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
