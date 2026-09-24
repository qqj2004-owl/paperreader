# -*- coding: utf-8 -*-
"""paperreader —— 任意文献交互阅读器：提取 PDF 正文/配图，注入讲解/翻译/术语，生成网页。"""
__version__ = "0.1.0"

from .extract import extract, clean, build_document
from .reader import build_reader

__all__ = ["extract", "clean", "build_document", "build_reader"]
