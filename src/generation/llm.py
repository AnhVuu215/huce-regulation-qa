"""Interface gọi LLM.

Logic trả lời chỉ phụ thuộc giao diện `LLM`: đổi nhà cung cấp không phải sửa logic.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class LLMResponse:
    text: str
    model: str
    latency_s: float
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cached: bool = False
    # Lỗi gặp trước khi có câu trả lời (ví dụ mô hình chính hết hạn mức, phải dùng dự phòng).
    errors: list[str] = field(default_factory=list)
    # Các lần gọi công cụ trong lời gọi này: {"name", "args", "result"}.
    tool_calls: list[dict] = field(default_factory=list)


class LLM(Protocol):
    def generate(self, system: str, prompt: str, json_schema: dict | None = None,
                 tools: list[dict] | None = None, tool_handler=None) -> LLMResponse:
        ...


class LLMError(RuntimeError):
    pass


def load_env(path: Path) -> None:
    """Nạp biến từ .env vào môi trường nếu chưa có (không cần thư viện dotenv)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name, sep, value = line.strip().partition("=")
        if sep and name and not name.startswith("#"):
            os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


class GeminiClient:
    """Gọi Gemini qua REST. Có thời gian chờ, thử lại với độ trễ tăng dần, mô hình dự phòng,
    và giãn cách tối thiểu giữa các lời gọi để không vượt hạn mức gói miễn phí."""

    BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, models: list[str], api_key: str | None = None, timeout_s: float = 60,
                 retries: int = 2, min_interval_s: float = 4.0):
        self.models = models
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise LLMError("Thiếu GEMINI_API_KEY (đặt trong .env)")
        self.timeout_s = timeout_s
        self.retries = retries
        self.min_interval_s = min_interval_s

    def _post(self, model: str, body: dict) -> dict:
        # Hạn mức tính theo mô hình cho cả project, nên mọi client trong tiến trình (bên trả lời
        # và giám khảo) dùng chung một mốc thời gian theo mô hình.
        wait = self.min_interval_s - (time.monotonic() - _LAST_CALL.get(model, 0.0))
        if wait > 0:
            time.sleep(wait)
        _LAST_CALL[model] = time.monotonic()
        req = urllib.request.Request(
            f"{self.BASE}/{model}:generateContent",
            data=json.dumps(body).encode("utf-8"),
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return json.load(resp)

    def _request(self, model: str, body: dict, errors: list[str]) -> dict:
        """Một request có thử lại; lỗi không thể cứu thì ném _SwitchModel để chuyển mô hình."""
        for attempt in range(self.retries + 1):
            try:
                return self._post(model, body)
            except urllib.error.HTTPError as e:
                detail, retry_after = _quota_detail(e)
                errors.append(f"{model}: HTTP {e.code}{' ' + detail if detail else ''}")
                if e.code in (400, 401, 403, 404) or "PerDay" in detail:
                    # Lỗi cấu hình hoặc hết hạn mức theo ngày: thử lại vô ích.
                    raise _SwitchModel from e
                # Hạn mức theo phút: chờ đúng thời gian máy chủ yêu cầu, không đoán.
                time.sleep(retry_after if retry_after else 2 ** attempt * 5)
            except (TimeoutError, urllib.error.URLError, OSError) as e:
                errors.append(f"{model}: {type(e).__name__}")
                time.sleep(2 ** attempt * 2)
        raise _SwitchModel

    def generate(self, system: str, prompt: str, json_schema: dict | None = None,
                 tools: list[dict] | None = None, tool_handler=None) -> LLMResponse:
        """Sinh câu trả lời. Có `tools` thì chạy vòng gọi công cụ: mô hình yêu cầu, `tool_handler`
        thực thi, kết quả gửi lại cho tới khi mô hình trả lời (tối đa MAX_TOOL_ROUNDS vòng)."""
        base: dict = {"systemInstruction": {"parts": [{"text": system}]}}
        if json_schema:
            base["generationConfig"] = {
                "responseMimeType": "application/json",
                "responseSchema": json_schema,
            }
        if tools:
            base["tools"] = [{"functionDeclarations": tools}]
        errors: list[str] = []
        for model in self.models:
            contents = [{"role": "user", "parts": [{"text": prompt}]}]
            usage_total = {"promptTokenCount": 0, "candidatesTokenCount": 0,
                           "thoughtsTokenCount": 0}
            calls: list[dict] = []
            start = time.perf_counter()
            try:
                for _ in range(MAX_TOOL_ROUNDS + 1):
                    data = self._request(model, {**base, "contents": contents}, errors)
                    for key in usage_total:
                        usage_total[key] += data.get("usageMetadata", {}).get(key, 0)
                    content = data.get("candidates", [{}])[0].get("content", {})
                    parts = content.get("parts", [])
                    requested = [p["functionCall"] for p in parts if "functionCall" in p]
                    if not requested or tool_handler is None:
                        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                        return LLMResponse(
                            text=text, model=model, latency_s=time.perf_counter() - start,
                            input_tokens=usage_total["promptTokenCount"],
                            output_tokens=usage_total["candidatesTokenCount"],
                            thinking_tokens=usage_total["thoughtsTokenCount"],
                            errors=errors, tool_calls=calls,
                        )
                    # Gửi lại nguyên nội dung mô hình (kèm thoughtSignature), rồi kết quả công cụ.
                    contents.append(content)
                    responses = []
                    for fc in requested:
                        result = tool_handler(fc["name"], dict(fc.get("args", {})))
                        calls.append({"name": fc["name"], "args": fc.get("args", {}),
                                      "result": result})
                        reply = {"name": fc["name"], "response": result}
                        if "id" in fc:
                            reply["id"] = fc["id"]
                        responses.append({"functionResponse": reply})
                    contents.append({"role": "user", "parts": responses})
                errors.append(f"{model}: quá {MAX_TOOL_ROUNDS} vòng gọi công cụ")
            except _SwitchModel:
                continue
        raise LLMError("Mọi mô hình đều lỗi: " + "; ".join(errors))


MAX_TOOL_ROUNDS = 4
MAX_RETRY_DELAY_S = 90
_LAST_CALL: dict[str, float] = {}


class _SwitchModel(Exception):
    """Mô hình hiện tại không dùng được cho lời gọi này; chuyển sang mô hình kế tiếp."""


def _quota_detail(error: urllib.error.HTTPError) -> tuple[str, float | None]:
    """Tên hạn mức bị vượt (ví dụ ...PerMinutePerProject...) và thời gian máy chủ yêu cầu chờ
    (RetryInfo.retryDelay, giới hạn ở MAX_RETRY_DELAY_S) từ thân lỗi 429 của Gemini."""
    try:
        details = json.loads(error.read() or b"{}").get("error", {}).get("details", [])
    except (json.JSONDecodeError, ValueError):
        return "", None
    ids = [v.get("quotaId", "") for d in details for v in d.get("violations", [])]
    delay = next((d.get("retryDelay") for d in details if d.get("retryDelay")), None)
    seconds = None
    if isinstance(delay, str) and delay.endswith("s"):
        try:
            seconds = min(float(delay[:-1]) + 1, MAX_RETRY_DELAY_S)
        except ValueError:
            seconds = None
    return ",".join(i for i in ids if i), seconds


class CachedLLM:
    """Bọc một LLM, lưu câu trả lời theo nội dung lời gọi: chạy eval lại không gọi mạng.
    Mô hình mặc định không cho đặt temperature, nên cache cũng là cách giữ kết quả ổn định."""

    def __init__(self, inner: LLM, cache_dir: Path, namespace: str):
        # namespace là tên mô hình được yêu cầu: chỉ lưu câu trả lời do chính mô hình đó sinh ra,
        # để câu của mô hình dự phòng không bị coi là của mô hình chính ở lần chạy sau.
        self.inner = inner
        self.namespace = namespace
        self.dir = cache_dir / namespace
        self.dir.mkdir(parents=True, exist_ok=True)

    def generate(self, system: str, prompt: str, json_schema: dict | None = None,
                 tools: list[dict] | None = None, tool_handler=None) -> LLMResponse:
        # Không có công cụ thì khóa giữ như cũ để cache đã có vẫn dùng được. Có công cụ thì
        # khóa gồm cả dấu vân tay của công cụ: đổi quy tắc hay code công cụ là cache tự hết hạn.
        parts = [system, prompt, json_schema]
        if tools:
            parts += [tools, getattr(tool_handler, "fingerprint", None)]
        key = hashlib.sha1(json.dumps(parts, ensure_ascii=False).encode("utf-8")).hexdigest()
        path = self.dir / f"{key}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return LLMResponse(**{**data, "cached": True})
        response = self.inner.generate(system, prompt, json_schema, tools, tool_handler)
        if response.model == self.namespace:
            path.write_text(json.dumps(asdict(response), ensure_ascii=False), encoding="utf-8")
        return response


class FakeLLM:
    """LLM giả lập cho test: trả lời theo hàm do test cung cấp, ghi lại prompt đã nhận.
    `tool_requests` là các lời gọi công cụ (tên, tham số) mà mô hình giả lập sẽ yêu cầu."""

    def __init__(self, respond, tool_requests: list[tuple[str, dict]] | None = None):
        self.respond = respond
        self.tool_requests = tool_requests or []
        self.calls: list[tuple[str, str]] = []

    def generate(self, system: str, prompt: str, json_schema: dict | None = None,
                 tools: list[dict] | None = None, tool_handler=None) -> LLMResponse:
        self.calls.append((system, prompt))
        tool_calls = []
        if tools and tool_handler:
            for name, args in self.tool_requests:
                tool_calls.append({"name": name, "args": args,
                                   "result": tool_handler(name, dict(args))})
        return LLMResponse(text=self.respond(prompt), model="fake", latency_s=0.0,
                           tool_calls=tool_calls)
