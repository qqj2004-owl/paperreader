# paperreader · 任意文献交互阅读器

把任意一篇 PDF 论文，变成一个**可点读的交互网页**：

- 自动提取正文与章节结构（按字体识别标题）
- 自动把配图裁出来，**内嵌到正文首次引用处**（点图可放大）
- 点句子 → 标记「我没看懂」→ 展开**五步拆解讲解**（可预置注解，也可点「直接讲解」联网实时生成）
- **句级中文译文**：中英逐句对齐，中文视图里同样能标记/看讲解，点「原文 ↩」跳回英文句并闪光定位
- 划词 → 术语释义气泡；暗色模式、字号、目录、全文搜索、复习模式
- 讲解/翻译/术语由**可插拔 LLM agent** 生成（默认 DeepSeek，可换 OpenAI/其它；「直接讲解」的 key 只存浏览器本地，不写进 HTML）
- **视觉提取兜底**：字体启发式搞不定的 PDF（正文丢失/乱码/化学式下标），可切换**视觉 LLM**（默认豆包）整页识别

一个内核，两个外壳：**本地网页** 和 **桌面 App**（pywebview），共享同一套代码。

## 架构

```
┌─────────────┬─────────────┐
│  桌面 App    │  本地网页    │   ← 两个外壳
│ desktop/     │  serve.py   │
└──────┬──────┴──────┬──────┘
       │   同一个前端   │  web/
┌──────┴──────────────┴──────┐
│      paperreader 核心包       │
│ extract / figures / reader   │
│ agents（可插拔 LLM）          │
└─────────────────────────────┘
```

| 模块 | 职责 |
| --- | --- |
| `extract.py` | PDF → 正文 + 标题（按字体自动识别，不依赖具体期刊） |
| `figures.py` | 识别图注、裁剪图形区域 → PNG |
| `reader.py` | 组装交互阅读器 HTML（含配图 base64 内嵌） |
| `agents.py` | 可插拔 LLM：讲解 / 翻译 / 术语 / 视觉 |
| `vision.py` | 整页视觉提取（把每页渲染成图交给视觉 LLM 转文本） |
| `serve.py` | Flask 网页外壳 |
| `desktop/main.py` | pywebview 桌面外壳 |

## 安装

```bash
pip install -e .
# 或只装核心依赖
pip install -r requirements.txt
```

## 使用

> 完整功能说明、JSON 数据格式与常见问题见 **[USAGE.md](USAGE.md)**。

### 命令行（离线生成单个阅读器）

```bash
python -m paperreader paper.pdf -o reader.html --title "标题" --meta "作者 — 期刊"
# 字体法提取乱码时，改用视觉 LLM 整页识别：
python -m paperreader paper.pdf --vision -o reader.html
# 视觉提取默认 4 页并行；配额/限流时调小：
python -m paperreader paper.pdf --vision --vision-workers 2 -o reader.html
```

生成的 `reader.html` 是**单文件、可离线打开**的（配图已 base64 内嵌）。

### 本地网页（上传任意 PDF）

```bash
python -m paperreader.serve
# 打开 http://127.0.0.1:5000，拖入 PDF 即生成
# 上传页勾选「视觉提取」即走视觉 LLM 整页识别（乱码 PDF 兜底）
```

### 桌面 App

```bash
pip install pywebview
python desktop/main.py
```

## 配置 LLM agent

讲解/翻译/术语按需调用 LLM。默认 **DeepSeek**（OpenAI 兼容接口），换模型只需改配置：

```bash
# 方式一：环境变量
export PAPERREADER_PROVIDER=deepseek      # 或 openai
export PAPERREADER_API_KEY=你的key

# 方式二：config.json（复制自 config.example.json）
{
  "provider": "openai",                    # 换成 openai 即切 GPT
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o-mini",
  "api_key": "你的key"
}
```

两个 preset 已内置：

| provider | base_url | model |
| --- | --- | --- |
| `deepseek` | `https://api.deepseek.com` | `deepseek-chat` |
| `openai` | `https://api.openai.com/v1` | `gpt-4o-mini` |

视觉提取用一个独立的多模态 provider，配置键以 `vision_` 开头：

```bash
# 环境变量
export PAPERREADER_VISION_PROVIDER=doubao
export PAPERREADER_VISION_API_KEY=你的key

# config.json
{
  "vision_provider": "doubao",
  "vision_base_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
  "vision_model": "doubao-seed-2-0-pro-260215",
  "vision_api_key": "你的key"
}
```

| vision_provider | base_url | model |
| --- | --- | --- |
| `doubao` | `https://ark.cn-beijing.volces.com/api/v3/chat/completions` | `doubao-seed-2-0-pro-260215` |
| `openai` | `https://api.openai.com/v1` | `gpt-4o` |

> 说明：所谓「内置 agent」就是内置了这个 LLM 调用层（`agents.py`），并非打包独立程序。
> 因为 DeepSeek 与 OpenAI 都是 OpenAI 兼容接口，一个 `OpenAICompatProvider` 即可覆盖两家，
> 换模型不改代码、只改配置。想接本地模型（Ollama 等）也只需加一个兼容 `base_url` 的 provider。

## 成本控制

- 讲解/翻译/术语全部**按需生成**（点哪句生成哪句，不批量）
- 「直接讲解」的结果**本地缓存**（浏览器 localStorage），同一句重复点不重复花钱
- 批量逐句翻译用 `--gen-zh` 一次性生成、之后 `--zh` 复用，不重复调用

## 已知限制

- 配图提取假设「每页一张图」，多图同页时会合并（后续按列拆分）
- 标题识别是启发式（字号/加粗），特殊排版的期刊可加字体配置微调
- 字体子集化严重（正文丢失、化学式下标错乱）的 PDF，请用「视觉提取」（`--vision` / 上传页勾选）兜底

## 目录结构

```
paperreader/
├── paperreader/        # 核心包
│   ├── extract.py
│   ├── figures.py
│   ├── reader.py
│   ├── agents.py
│   ├── vision.py
│   ├── serve.py
│   ├── __main__.py
│   └── template.html   # 交互阅读器前端模板
├── web/index.html      # 上传界面
├── desktop/main.py     # 桌面外壳
├── config.example.json
└── tests/
```

## License

MIT

##欢迎随时反馈，此内容完全由AI制作
