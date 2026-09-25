# -*- coding: utf-8 -*-
"""可插拔 LLM agent：讲解 / 翻译 / 术语。

DeepSeek 与 OpenAI 的接口都是 OpenAI 兼容格式，因此用一个
OpenAICompatProvider 即可覆盖两者，换模型只需改 base_url + model。
"""
import json
import urllib.request

EXPLAIN_PROMPT = """你是化学/材料领域的论文精读助教。请把下面这句英文论文用中文做"五步拆解"讲解，
严格输出 JSON，键为 定位/拆链/数字/挖到底/收拢：
- 定位：这句话在论证链条里的作用（一句话）。
- 拆链：还原句中省略的因果/推理步骤。
- 数字：句中数字、单位、比例的物理含义。
- 挖到底：涉及的底层概念/原理。
- 收拢：用一句话复述本句核心结论。
只输出 JSON，不要多余文字。\n\n句子：{sentence}"""

TRANSLATE_PROMPT = "把下面这段英文论文翻译成通顺的中文，保留专业术语，直接输出译文：\n\n{text}"

GLOSSARY_PROMPT = """从下面这段英文论文中提取专业术语，输出 JSON 对象，键为英文术语，值为简短中文释义（术语：释义）。
只输出 JSON。\n\n{text}"""


class ProviderError(Exception):
    pass


def _parse_json_array(raw):
    """从 LLM 输出里尽量解析出一个 JSON 数组；失败返回 []。"""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()
    try:
        v = json.loads(raw)
        if isinstance(v, list):
            return v
    except (json.JSONDecodeError, ValueError):
        pass
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


class OpenAICompatProvider:
    def __init__(self, base_url, api_key, model, timeout=120):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _chat_url(self):
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return self.base_url + "/chat/completions"

    def chat(self, messages, temperature=0.2, max_tokens=2048):
        url = self._chat_url()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.api_key},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            raise ProviderError("LLM 调用失败: %s" % e)
        return body["choices"][0]["message"]["content"]

    def chat_vision(self, prompt, image_dataurls, temperature=0.2, max_tokens=4096):
        """多模态调用：把一张或多张图（data:image/...;base64,...）+ 文字一起发给视觉模型。

        image_dataurls 里的每一项是完整的 data URL（如 data:image/png;base64,....），
        与 Doubao/OpenAI 的 image_url content 格式兼容。
        """
        content = [
            {"type": "image_url", "image_url": {"url": u}} for u in image_dataurls
        ]
        content.append({"type": "text", "text": prompt})
        return self.chat(
            [{"role": "user", "content": content}],
            temperature=temperature, max_tokens=max_tokens,
        )

    def _json(self, prompt, max_tokens=2048):
        raw = self.chat([{"role": "user", "content": prompt}], max_tokens=max_tokens)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw[raw.find("\n") + 1:] if "\n" in raw else raw
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"_raw": raw}

    def explain(self, sentence):
        return self._json(EXPLAIN_PROMPT.format(sentence=sentence))

    def translate(self, text):
        return self.chat([{"role": "user", "content": TRANSLATE_PROMPT.format(text=text)}])

    def glossary(self, text):
        return self._json(GLOSSARY_PROMPT.format(text=text))

    def translate_sentences(self, sentences, batch_size=30):
        """逐句翻译一组英文句子，返回与输入等长的中文列表（保持顺序对齐）。"""
        out = []
        for i in range(0, len(sentences), batch_size):
            batch = sentences[i:i + batch_size]
            prompt = (
                "把下面 %d 句英文论文逐句翻译成中文，保留专业术语。\n"
                "严格按顺序输出一个 JSON 数组，数组长度必须正好是 %d，"
                "每一项就是对应那一句的中文译文。只输出 JSON 数组本身，"
                "不要序号、不要英文原文、不要任何多余说明。\n\n%s"
                % (len(batch), len(batch), json.dumps(batch, ensure_ascii=False))
            )
            raw = self.chat([{"role": "user", "content": prompt}], max_tokens=8000)
            arr = _parse_json_array(raw)
            if len(arr) != len(batch):
                # 数量对不上就逐句兜底（更稳，但调用次数多）
                arr = [self.translate(s).strip() for s in batch]
            out.extend(arr)
        return out


PRESETS = {
    "deepseek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
}

# 视觉模型 preset（整页视觉提取 / 疑难页兜底）。豆包走火山方舟 Ark 的
# OpenAI 兼容 /chat/completions 端点（mini 模型也支持，且比 pro 快）。
VISION_PRESETS = {
    "doubao": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "model": "doubao-seed-2-0-mini-260428",
    },
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
}


def _load_config_file():
    """读取 config.json（包根目录或当前目录），不存在返回 {}。"""
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "..", "config.json"), "config.json"):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
    return {}


def load_provider(config=None):
    """config: {provider, base_url, api_key, model}。

    优先级：显式参数 > 环境变量 > config.json > 内置 preset。
    """
    import os
    explicit = config or {}
    file_cfg = _load_config_file()

    def pick(key, env, default=""):
        return explicit.get(key) or os.environ.get(env) or file_cfg.get(key) or default

    provider = pick("provider", "PAPERREADER_PROVIDER", "deepseek")
    preset = PRESETS.get(provider, {})
    base_url = pick("base_url", "PAPERREADER_BASE_URL", preset.get("base_url"))
    model = pick("model", "PAPERREADER_MODEL", preset.get("model"))
    api_key = pick("api_key", "PAPERREADER_API_KEY", "")
    if not base_url:
        raise ProviderError("未知 provider: %s" % provider)
    return OpenAICompatProvider(base_url, api_key, model)


def load_vision_provider(config=None):
    """加载视觉（多模态）provider。

    配置键：vision_provider / vision_base_url / vision_model / vision_api_key，
    环境变量：PAPERREADER_VISION_PROVIDER / PAPERREADER_VISION_BASE_URL /
    PAPERREADER_VISION_MODEL / PAPERREADER_VISION_API_KEY。
    优先级同 load_provider：显式参数 > 环境变量 > config.json > 内置 preset。
    """
    import os
    explicit = config or {}
    file_cfg = _load_config_file()

    def pick(key, env, default=""):
        return explicit.get(key) or os.environ.get(env) or file_cfg.get(key) or default

    provider = pick("vision_provider", "PAPERREADER_VISION_PROVIDER", "doubao")
    preset = VISION_PRESETS.get(provider, {})
    base_url = pick("vision_base_url", "PAPERREADER_VISION_BASE_URL", preset.get("base_url"))
    model = pick("vision_model", "PAPERREADER_VISION_MODEL", preset.get("model"))
    api_key = pick("vision_api_key", "PAPERREADER_VISION_API_KEY", "")
    if not base_url:
        raise ProviderError("未知 vision_provider: %s" % provider)
    return OpenAICompatProvider(base_url, api_key, model, timeout=300)
