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


class LLM(Protocol):
    def generate(self, system: str, prompt: str, json_schema: dict | None = None) -> LLMResponse:
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
        self._last_call = 0.0

    def _post(self, model: str, body: dict) -> dict:
        wait = self.min_interval_s - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()
        req = urllib.request.Request(
            f"{self.BASE}/{model}:generateContent",
            data=json.dumps(body).encode("utf-8"),
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return json.load(resp)

    def generate(self, system: str, prompt: str, json_schema: dict | None = None) -> LLMResponse:
        body: dict = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        }
        if json_schema:
            body["generationConfig"] = {
                "responseMimeType": "application/json",
                "responseSchema": json_schema,
            }
        errors = []
        for model in self.models:
            for attempt in range(self.retries + 1):
                start = time.perf_counter()
                try:
                    data = self._post(model, body)
                except urllib.error.HTTPError as e:
                    detail = _quota_detail(e)
                    errors.append(f"{model}: HTTP {e.code}{' ' + detail if detail else ''}")
                    if e.code in (400, 401, 403, 404) or "PerDay" in detail:
                        # Lỗi cấu hình hoặc hết hạn mức theo ngày: thử lại vô ích, chuyển mô hình.
                        break
                    time.sleep(2 ** attempt * 5)
                    continue
                except (TimeoutError, urllib.error.URLError, OSError) as e:
                    errors.append(f"{model}: {type(e).__name__}")
                    time.sleep(2 ** attempt * 2)
                    continue
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                usage = data.get("usageMetadata", {})
                return LLMResponse(
                    text=text,
                    model=model,
                    latency_s=time.perf_counter() - start,
                    input_tokens=usage.get("promptTokenCount", 0),
                    output_tokens=usage.get("candidatesTokenCount", 0),
                    thinking_tokens=usage.get("thoughtsTokenCount", 0),
                    errors=errors,
                )
        raise LLMError("Mọi mô hình đều lỗi: " + "; ".join(errors))


def _quota_detail(error: urllib.error.HTTPError) -> str:
    """Lấy tên hạn mức bị vượt từ thân lỗi 429 của Gemini (ví dụ ...PerDayPerProject...)."""
    try:
        details = json.loads(error.read() or b"{}").get("error", {}).get("details", [])
    except (json.JSONDecodeError, ValueError):
        return ""
    ids = [v.get("quotaId", "") for d in details for v in d.get("violations", [])]
    return ",".join(i for i in ids if i)


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

    def generate(self, system: str, prompt: str, json_schema: dict | None = None) -> LLMResponse:
        key = hashlib.sha1(
            json.dumps([system, prompt, json_schema], ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        path = self.dir / f"{key}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return LLMResponse(**{**data, "cached": True})
        response = self.inner.generate(system, prompt, json_schema)
        if response.model == self.namespace:
            path.write_text(json.dumps(asdict(response), ensure_ascii=False), encoding="utf-8")
        return response


class FakeLLM:
    """LLM giả lập cho test: trả lời theo hàm do test cung cấp, ghi lại prompt đã nhận."""

    def __init__(self, respond):
        self.respond = respond
        self.calls: list[tuple[str, str]] = []

    def generate(self, system: str, prompt: str, json_schema: dict | None = None) -> LLMResponse:
        self.calls.append((system, prompt))
        return LLMResponse(text=self.respond(prompt), model="fake", latency_s=0.0)
