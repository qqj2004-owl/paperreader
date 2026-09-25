# 使用说明

paperreader 把一个 PDF 论文变成「可点读」的交互网页。下面是完整用法。

## 一、快速开始（三种方式）

### 方式 1：命令行离线生成（最简单）

```bash
pip install pymupdf
python -m paperreader 论文.pdf -o 阅读器.html
```

生成的是**单文件 HTML**，双击用浏览器打开即可，配图已内嵌，可完全离线。

带上标题/出处：

```bash
python -m paperreader 论文.pdf -o 阅读器.html --title "论文标题" --meta "作者 — 期刊, 年份"
```

### 方式 2：本地网页（拖入任意 PDF 即生成）

```bash
pip install -e .
python -m paperreader.serve
# 浏览器打开 http://127.0.0.1:5000
```

### 方式 3：桌面 App

```bash
pip install -e ".[desktop]"
python desktop/main.py
```

## 二、阅读器功能说明

| 功能 | 怎么用 | 需要什么数据 |
| --- | --- | --- |
| 标记疑难句 | 点一下句子 | 无（自动保存，见下方「进度自动保存」） |
| 五步拆解讲解 | 点已标记句上的「讲解 ▾」 | `--annotations` 注解 JSON |
| 直接讲解（联网） | 点已标记句上的「直接讲解」，浏览器直连 LLM 实时生成五步拆解 | 在「讲解设置」填自己的 key（存浏览器本地，不写进 HTML） |
| 划词术语 | 用鼠标选中英文单词 | `--glossary` 术语表 JSON |
| 中文译文（句级） | 点工具栏「中文译文」，点句子可标记/看讲解，点「原文 ↩」跳回英文句并闪光定位 | `--zh` 译文 JSON |
| 目录跳转 | 点「目录」 | 无（自动识别标题） |
| 全文搜索 | 输入关键词，回车跳下一条 | 无 |
| 暗色 / 字号 | 工具栏按钮 | 无 |
| 复习模式 | 点「复习」只显示已标记句 | 无 |
| 配图栏 | 点「配图」开关右侧配图栏；点图放大（Esc 关闭）；点「定位」跳回引用句 | 无（自动裁剪） |
| 进度自动保存 | 标记/讲解/译文/API 设置自动存本机，重开同一篇论文不丢 | 无 |
| 备份 / 恢复 | 工具栏「备份」导出进度 JSON、「恢复」从文件载回 | 无 |
| 导出待讲解 | 点「导出待讲解」，复制后发给 AI 补齐 | 无 |

> **关于进度自动保存**：网页版/桌面版会把标记、讲解、译文、API 设置自动存到本地服务端（`instance/state/`，按 PDF 内容哈希区分不同论文），关闭重开后打开**同一篇 PDF** 自动恢复，不用重新翻译。命令行生成的离线 HTML（`file://`）则存浏览器 localStorage；若担心换文件位置丢，用「备份/恢复」手动导出导入即可。进度都在本机，不上传外部服务器。

## 三、附带的讲解 / 译文 / 术语数据

命令行里用 JSON 传入，格式：

```bash
python -m paperreader 论文.pdf -o out.html \
  --zh 译文.json \
  --glossary 术语表.json \
  --annotations 讲解.json
```

- **译文.json**：句级对齐格式 `[{"type":"h1","text":"..."}, {"type":"h2","text":"..."}, {"type":"s","id":"s-0001","text":"..."}]`
  - `h1`/`h2` 是标题译文；`s` 是句子译文，`id` 对应英文句子的 `data-id`（如 `s-0001`），中文视图靠它和英文句一一对应（可标记/看讲解/跳回原文）。
- **术语表.json**：`{"electrode":"电极：……", "anode":"阳极：……"}`
- **讲解.json**：`{"s-0027":{"定位":"...","拆链":"...","数字":"...","挖到底":"...","收拢":"..."}}`

### 用 LLM 自动生成句级译文

如果不想手写译文.json，可以一次性让 DeepSeek 逐句翻译并写入 JSON（之后用 `--zh` 复用即可）：

```bash
export PAPERREADER_API_KEY=你的key
python -m paperreader 论文.pdf -o 阅读器.html --gen-zh 译文.json
```

> `--gen-zh` 会在生成 HTML 的同时调用 LLM 逐句翻译，产出的 `译文.json` 就是上面的句级对齐格式；下次重跑直接 `--zh 译文.json`，不再重复花钱。

## 四、配置 LLM agent（讲解 / 翻译 / 术语按需生成）

默认用 DeepSeek（OpenAI 兼容接口），换 OpenAI 只改配置：

1. 复制 `config.example.json` → `config.json`
2. 填 `api_key`（或设环境变量 `PAPERREADER_API_KEY`）
3. 换模型就改 `provider` / `base_url` / `model`

```json
{
  "provider": "deepseek",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat",
  "api_key": "你的key"
}
```

> 注意：`config.json` 已被 `.gitignore` 忽略，**不要**手动 `git add` 它，否则会泄露你的 key。

## 五、常见问题

- **点「中文译文」空白？** 离线阅读器的译文来自 `--zh` 传入的 JSON，没传就是空的。离线版**刻意不**把 API key 打进 HTML（否则谁拿到 HTML 就能看到你的 key），所以离线版不做按需联网翻译。
- **「直接讲解」怎么用？** 标记一句没有讲解的句子后，句子旁会出现绿色的「直接讲解」按钮。点它会在浏览器里直连 OpenAI 兼容接口生成五步拆解，结果缓存到浏览器本地（同句再点不重复花钱）。第一次点会让你在「讲解设置」里填自己的 `base_url` / `model` / `api_key`——**key 只存在你的浏览器 localStorage，不写进 HTML 文件**，所以分享/发布 HTML 都不会泄露。
- **点「讲解」没反应？** 没传 `--annotations`，或该句还没有讲解数据；可用「直接讲解」联网生成。
- **划词没弹术语？** 没传 `--glossary`。
- **换一篇论文怎么用？** 直接换命令行里的 PDF 路径重跑一次即可。

## 六、上传 GitHub 前的安全清单

- ✅ 源码里没有硬编码的 API key（只有占位符 `你的key`）
- ✅ 没有本机路径 / 用户名 / 电脑信息
- ✅ `config.json`、`*.pdf`、根目录生成的 `*.html` 都已进 `.gitignore`
- ✅ 「直接讲解」的 key 只存浏览器 localStorage，**不在 HTML 文件里**，分享 HTML 不会带出 key
- ⚠️ 生成的 `reader.html` 里含论文原文和配图，属于原论文的版权内容，别提交到公开仓库
