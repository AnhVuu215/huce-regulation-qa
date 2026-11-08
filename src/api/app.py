"""API hỏi đáp quy chế: /ask, /feedback, /documents, /health và trang demo ở /.

    uv run --group ml uvicorn api.app:app --app-dir src --port 8000
"""

import json
import logging
import os
import threading
import time
import uuid
from collections import OrderedDict, deque
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from api.schemas import AskRequest, AskResponse, Citation, DocumentInfo, FeedbackRequest
from generation.answer import QA, citation_label
from generation.llm import LLMError

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).parent / "static"
RECENT_ANSWERS = 1000
log = logging.getLogger("huce_qa")


class RateLimiter:
    """Tối đa `limit` request mỗi `window_s` giây cho mỗi khóa (địa chỉ IP); limit=0 là tắt.
    Hạn mức gói miễn phí của LLM dùng chung cho mọi người, một người hỏi dồn là hết cho cả trang."""

    def __init__(self, limit: int, window_s: float = 60.0):
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str) -> int:
        """0 nếu được phép (và tính lượt này), ngược lại số giây phải chờ."""
        if self.limit <= 0:
            return 0
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window_s:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(1, round(self.window_s - (now - hits[0])))
            hits.append(now)
            # Bỏ khóa không còn lượt nào: bảng không phình theo số IP từng ghé.
            for k in [k for k, v in self._hits.items() if not v]:
                del self._hits[k]
            return 0


class JsonlLog:
    """Ghi thêm từng dòng JSON vào file; an toàn khi nhiều request ghi cùng lúc."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def write(self, record: dict) -> None:
        record = {"time": datetime.now(UTC).isoformat(timespec="seconds"), **record}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")


def create_app(qa_factory: Callable[[], QA] | None = None, data_dir: Path | None = None,
               rate_limit_per_min: int | None = None) -> FastAPI:
    """`qa_factory` dựng pipeline khi ứng dụng khởi động (test truyền QA giả lập).
    `rate_limit_per_min`: số câu hỏi mỗi phút cho một IP; mặc định lấy ASK_RATE_LIMIT, 0 là tắt."""
    if qa_factory is None:
        def qa_factory() -> QA:
            # Import muộn: dựng pipeline cần nhóm ml (mô hình embedding), test và CI thì không.
            from api.service import build_qa

            return build_qa(ROOT)

    data_dir = data_dir or ROOT / ".data"
    requests_log = JsonlLog(data_dir / "requests.jsonl")
    feedback_log = JsonlLog(data_dir / "feedback.jsonl")
    state: dict = {}
    if rate_limit_per_min is None:
        rate_limit_per_min = int(os.environ.get("ASK_RATE_LIMIT", "10"))
    limiter = RateLimiter(rate_limit_per_min)
    # Các request trả lời song song: pipeline an toàn đa luồng (mã hóa câu hỏi lần lượt, giãn cách
    # lời gọi LLM dùng chung), chỉ bảng câu trả lời gần đây cần khóa riêng.
    recent: OrderedDict[str, dict] = OrderedDict()
    recent_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state["qa"] = qa_factory()
        yield

    app = FastAPI(title="Hỏi đáp quy chế đào tạo HUCE", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "ready": "qa" in state}

    @app.get("/documents", response_model=list[DocumentInfo])
    def documents() -> list[DocumentInfo]:
        qa: QA = state["qa"]
        return [
            DocumentInfo(doc_id=d.doc_id, doc_title=d.doc_title, so_hieu=d.so_hieu,
                         hieu_luc_tu=d.hieu_luc_tu, khoa_tu=d.khoa_tu, khoa_den=d.khoa_den,
                         sua_doi=sorted({sd.doc_id for sd in d.sua_doi}))
            for d in qa.docs.values()
        ]

    @app.post("/ask", response_model=AskResponse)
    def ask(req: AskRequest, request: Request) -> AskResponse:
        qa: QA = state["qa"]
        # Sau reverse proxy, chạy uvicorn với --proxy-headers để client.host là IP người dùng.
        client = request.client.host if request.client else "unknown"
        wait_s = limiter.retry_after(client)
        if wait_s:
            raise HTTPException(429, f"Bạn hỏi nhanh quá, hãy thử lại sau {wait_s} giây.",
                                headers={"Retry-After": str(wait_s)})
        request_id = uuid.uuid4().hex
        start = time.perf_counter()
        try:
            answer = qa.answer(req.question.strip(), req.khoa)
        except LLMError as e:
            log.warning("LLM lỗi: %s", e)
            requests_log.write({"request_id": request_id, "status": "loi_llm", "error": str(e)})
            if "PerDay" in str(e):
                detail = ("Đã hết lượt gọi mô hình ngôn ngữ trong ngày (gói miễn phí); hạn mức "
                          "được cấp lại sau nửa đêm giờ Thái Bình Dương, khoảng 15 giờ Việt Nam.")
            else:
                detail = "Mô hình ngôn ngữ tạm thời không phản hồi, hãy thử lại sau ít phút."
            raise HTTPException(503, detail) from e
        latency_ms = round(1000 * (time.perf_counter() - start))
        citations = [
            Citation(doc_id=u.doc_id, doc_title=qa.docs[u.doc_id].doc_title,
                     so_hieu=qa.docs[u.doc_id].so_hieu, dieu=u.dieu, khoan=u.khoan or None,
                     label=citation_label(u, qa.docs[u.doc_id]))
            for u in dict.fromkeys(answer.citations)
        ]
        response = AskResponse(request_id=request_id, status=answer.status, answer=answer.text,
                               citations=citations, warnings=answer.warnings,
                               uncertain=answer.uncertain, latency_ms=latency_ms)
        llm = answer.llm
        requests_log.write({
            "request_id": request_id, "status": answer.status, "khoa": req.khoa,
            "latency_ms": latency_ms, **answer.timings,
            "model": llm.model if llm else None,
            "cached": llm.cached if llm else None,
            "tokens": (llm.input_tokens + llm.output_tokens + llm.thinking_tokens) if llm else 0,
            "tool_calls": [c["name"] for c in llm.tool_calls] if llm else [],
            "retrieved": answer.retrieved,
        })
        with recent_lock:
            recent[request_id] = {"question": req.question, "khoa": req.khoa,
                                  "status": answer.status, "answer": answer.text,
                                  "citations": [c.label for c in citations]}
            while len(recent) > RECENT_ANSWERS:
                recent.popitem(last=False)
        return response

    @app.post("/feedback", status_code=204)
    def feedback(req: FeedbackRequest) -> None:
        # Lưu kèm câu hỏi và câu trả lời: phản hồi thật là nguồn câu test mới.
        with recent_lock:
            entry = recent.get(req.request_id)
        if entry is None:
            raise HTTPException(404, "Không tìm thấy câu trả lời này (có thể đã quá cũ).")
        feedback_log.write({"request_id": req.request_id, "helpful": req.helpful,
                            "comment": req.comment, **entry})

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    return app


app = create_app()
