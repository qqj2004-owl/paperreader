# paperreader · 任意文献交互阅读器

把**任意一篇 PDF 论文**变成一个**可点读的交互网页**：自动提取正文、章节与配图，支持句级中英对照、点句看五步讲解、划词查术语，阅读进度自动保存。

> 核心使用场景：读文献时「对着图读、碰到看不懂的句子立刻拆解」，把一篇硬论文变成能逐句啃的学习材料。

---

## 一、它做了什么

| 能力 | 说明 |
| --- | --- |
| 正文 + 标题提取 | 按字体字号自动识别正文与章节标题，不依赖具体期刊排版 |
| 配图自动裁剪 | 识别图注、裁出图形，放**右侧可滑动配图栏**；点图放大，点「定位」跳回正文引用句 |
| 点句标记 + 讲解 | 点句子标记「没看懂」，展开**五步拆解讲解**（定位 → 拆链 → 数字 → 挖到底 → 收拢） |
| 句级中文译文 | 中英逐句对齐，中文视图里同样能标记/看讲解，点「原文 ↩」跳回英文句并闪光定位 |
| 划词术语 | 鼠标选中英文单词，弹术语释义气泡 |
| 进度自动保存 | 标记、讲解、译文、API 设置自动保存；关掉重开不丢，另有「备份/恢复」手动导出导入 |
| 视觉提取兜底 | 字体法搞不定的 PDF（乱码/化学式下标错乱），切换**视觉 LLM**（豆包）整页识别 |
| 可插拔 LLM | 讲解/翻译/术语由 LLM agent 生成（默认 DeepSeek，换 OpenAI 只改配置不改代码） |

一个内核，两个外壳：**本地网页**（Flask）和**桌面 App**（pywebview），共享同一套代码。

---

## 二、快速开始（教程）

### 0. 环境要求

- Python **3.8+**
- Windows / macOS / Linux 均可

### 1. 安装

```bash
git clone https://github.com/qqj2004-owl/paperreader.git
cd paperreader
pip install -e .            # 核心依赖：pymupdf（PDF 提取）+ flask（网页外壳）
```

> 想用**桌面 App** 再加装 pywebview：`pip install -e ".[desktop]"`

### 2. 三种运行方式，任选其一

**方式 A · 命令行离线生成（最简单）**

```bash
python -m paperreader 论文.pdf -o 阅读器.html --title "论文标题" --meta "作者 — 期刊, 年份"
```

生成的是**单文件 HTML**，双击用浏览器打开即可，配图已 base64 内嵌，可完全离线使用。

**方式 B · 本地网页（拖入 PDF 即生成）**

```bash
python -m paperreader.serve
# 浏览器打开 http://127.0.0.1:5000，拖入 PDF 即生成
```

**方式 C · 桌面 App（原生窗口，免开浏览器）**

```bash
python desktop/main.py
```

### 3. 上手三步

1. 生成/打开阅读器，点工具栏「**中文译文**」看翻译（或先点「翻译全文」联网生成）。
2. 读英文正文，遇到看不懂的句子**点一下标记**，再点句子上的「**直接讲解**」生成五步拆解。
3. 点工具栏「**配图**」打开右侧配图栏，读图时点「定位」跳回正文首次引用处。

### 4. 阅读器功能速查

| 功能 | 怎么用 |
| --- | --- |
| 标记疑难句 | 点一下句子（再点取消） |
| 五步拆解讲解 | 点已标记句上的「讲解 ▾」 |
| 直接讲解（联网） | 点已标记句上的绿色「直接讲解」，浏览器直连 LLM 实时生成 |
| 中文译文 | 点「中文译文」切换视图；点句内「原文 ↩」跳回英文句 |
| 划词术语 | 选中英文单词弹气泡 |
| 配图 | 点「配图」开关侧栏；点图放大；点「定位」跳回引用句 |
| 目录 / 搜索 / 暗色 / 字号 / 复习 | 工具栏对应按钮 |
| 备份 / 恢复进度 | 点「备份」下载进度 JSON，点「恢复」从文件载回 |
| 导出待讲解 | 点「导出待讲解」复制已标记未讲解的句子，发给 AI 补齐 |

---

## 三、进度自动保存（关掉重开不丢）

- **网页版 / 桌面版**：标记、讲解、译文、API 设置会**自动存到本地服务端**（`instance/state/`，按 PDF 内容哈希区分不同论文），关闭重启后打开**同一篇 PDF** 自动恢复，**不用重新翻译**。
- **命令行生成的离线 HTML**（`file://`）：自动存浏览器 localStorage；若担心换文件位置丢，用工具栏「**备份**」导出、下次「**恢复**」导入即可。
- 这些进度数据都在你**本机**，不上传任何外部服务器。

---

## 四、配置 LLM agent

讲解/翻译/术语按需调用 LLM。默认 **DeepSeek**（OpenAI 兼容接口），换模型只改配置：

```bash
# 方式一：环境变量
export PAPERREADER_API_KEY=你的key

# 方式二：config.json（复制自 config.example.json）
{
  "provider": "deepseek",                     # 换成 openai 即切 GPT
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat",
  "api_key": "你的key"
}
```

内置 preset：

| provider | base_url | model |
| --- | --- | --- |
| `deepseek` | `https://api.deepseek.com` | `deepseek-chat` |
| `openai` | `https://api.openai.com/v1` | `gpt-4o-mini` |

> 「直接讲解」用的是**你自己在浏览器「讲解设置」里填的 key**，只存浏览器本地（localStorage），不写进 HTML 文件，分享/发布都不会泄露。

**视觉提取**用独立的多模态 provider，配置键以 `vision_` 开头：

```bash
export PAPERREADER_VISION_PROVIDER=doubao
export PAPERREADER_VISION_API_KEY=你的视觉key
```

| vision_provider | base_url | model |
| --- | --- | --- |
| `doubao` | `https://ark.cn-beijing.volces.com/api/v3/chat/completions` | `doubao-seed-2-0-mini-260428` |
| `openai` | `https://api.openai.com/v1` | `gpt-4o` |

> 说明：所谓「内置 agent」就是内置了这个 LLM 调用层（`agents.py`），并非打包独立程序。因为 DeepSeek 与 OpenAI 都是 OpenAI 兼容接口，一个 `OpenAICompatProvider` 即可覆盖两家，换模型不改代码只改配置；想接本地模型（Ollama 等）也只需加一个兼容 `base_url` 的 provider。

---

## 五、命令行完整参数

```bash
python -m paperreader 论文.pdf -o 阅读器.html \
  --title "标题" --meta "出处" --abstract "摘要" \
  --zh 译文.json --glossary 术语表.json --annotations 讲解.json \
  --gen-zh 译文.json          # 用 LLM 一次性逐句翻译并写入该 JSON，之后 --zh 复用
  --vision                    # 字体法乱码时，走视觉 LLM 整页识别
  --vision-workers 2          # 视觉提取并发页数（默认 4，限流时调小）
  --no-figures                # 不提取配图
```

- `--gen-zh`：调用 DeepSeek 逐句翻译并写 JSON，下次重跑用 `--zh 译文.json` 复用，不重复花钱。
- 三种 JSON 数据格式详见 **[USAGE.md](USAGE.md)**。

---

## 六、成本控制

- 讲解/翻译/术语全部**按需生成**（点哪句生成哪句，不批量）。
- 「直接讲解」的结果**本地缓存**（localStorage），同一句重复点不重复花钱。
- 批量逐句翻译用 `--gen-zh` 一次性生成、之后 `--zh` 复用。

---

## 七、架构与目录结构

```
paperreader/
├── paperreader/            # 核心包
│   ├── extract.py          # PDF → 正文 + 标题（按字体自动识别）
│   ├── figures.py          # 识别图注、裁剪图形区域 → PNG
│   ├── reader.py           # 组装交互阅读器 HTML（含配图 base64 内嵌 + 进度注入）
│   ├── agents.py           # 可插拔 LLM：讲解 / 翻译 / 术语 / 视觉
│   ├── vision.py           # 整页视觉提取（页渲染成图交给视觉 LLM 转文本）
│   ├── serve.py            # Flask 网页外壳（含进度存取的 /api/state）
│   ├── __main__.py         # 命令行入口
│   └── template.html       # 交互阅读器前端模板
├── web/index.html          # 上传界面
├── desktop/main.py         # pywebview 桌面外壳
├── config.example.json
└── tests/
```

---

## 八、已知限制

- 配图提取假设「每页一张图」，多图同页时会合并（后续按列拆分）。
- 标题识别是启发式（字号/加粗），特殊排版的期刊可加字体配置微调。
- 字体子集化严重（正文丢失、化学式下标错乱）的 PDF，请用「视觉提取」（`--vision` / 上传页勾选）兜底。

---

## 九、上传 GitHub 前的安全提醒

- 源码里**没有**硬编码的 API key（只有占位符）。
- `config.json`、`*.pdf`、根目录生成的 `*.html` 都已进 `.gitignore`。
- 「直接讲解」的 key 只存浏览器本地，**不在 HTML 文件里**。
- 生成的 `reader.html` 含论文原文和配图，属原论文版权内容，别提交到公开仓库。

## License

MIT

欢迎随时反馈，此内容完全由 AI 制作。
