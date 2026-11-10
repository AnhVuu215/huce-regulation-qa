"""API với QA giả lập: không cần mô hình, không cần mạng."""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from huce_qa.api.app import RateLimiter, create_app
from huce_qa.generation.answer import Answer
from huce_qa.generation.llm import DailyQuotaError, LLMError
from huce_qa.ingestion.registry import load_registry
from huce_qa.retrieval.corpus import Unit

ROOT = Path(__file__).resolve().parents[1]
DOCS = {d.doc_id: d for d in load_registry(ROOT / "data" / "registry.yaml").documents}


class FakeQA:
    def __init__(self, fail: str | LLMError | None = None):
        self.docs = DOCS
        self.fail = fail
        self.calls = []

    def answer(self, question, khoa):
        self.calls.append((question, khoa))
        if self.fail:
            raise self.fail if isinstance(self.fail, LLMError) else LLMError(self.fail)
        return Answer(
            status="tra_loi",
            text="Từ 2,0 trở lên.",
            citations=[Unit("qc-dhxd-2022", 13, 1), Unit("qc-dhxd-2022", 13, 1)],
            warnings=["Thông tin chỉ mang tính tham khảo."],
        )


@pytest.fixture
def client(tmp_path):
    qa = FakeQA()
    with TestClient(create_app(lambda: qa, data_dir=tmp_path)) as c:
        c.qa, c.data_dir = qa, tmp_path
        yield c


def test_health_reports_ready(client):
    assert client.get("/health").json() == {"status": "ok", "ready": True}


def test_ask_returns_answer_with_deduplicated_labeled_citations(client):
    r = client.post("/ask", json={"question": "GPA bao nhiêu thì tốt nghiệp?", "khoa": 68})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "tra_loi" and body["answer"] == "Từ 2,0 trở lên."
    assert len(body["citations"]) == 1
    assert body["citations"][0]["label"].startswith("Điều 13 Khoản 1, Quy chế đào tạo")
    assert client.qa.calls == [("GPA bao nhiêu thì tốt nghiệp?", 68)]


def test_ask_logs_the_request(client):
    client.post("/ask", json={"question": "GPA bao nhiêu?", "khoa": 68})
    record = json.loads((client.data_dir / "requests.jsonl").read_text(encoding="utf-8"))
    assert record["status"] == "tra_loi" and "latency_ms" in record


@pytest.mark.parametrize(
    "payload", [{"question": "a"}, {"question": "GPA?", "khoa": 5}, {"question": "x" * 501}]
)
def test_ask_validates_input(client, payload):
    assert client.post("/ask", json=payload).status_code == 422


def test_llm_failure_returns_503(tmp_path):
    with TestClient(create_app(lambda: FakeQA(fail="HTTP 503"), data_dir=tmp_path)) as c:
        r = c.post("/ask", json={"question": "GPA bao nhiêu?"})
    assert r.status_code == 503
    assert "thử lại" in r.json()["detail"]


def test_daily_quota_failure_says_when_quota_resets(tmp_path):
    error = DailyQuotaError("gemini-3.5-flash-lite: HTTP 429")
    with TestClient(create_app(lambda: FakeQA(fail=error), data_dir=tmp_path)) as c:
        r = c.post("/ask", json={"question": "GPA bao nhiêu?"})
    assert r.status_code == 503
    assert "trong ngày" in r.json()["detail"]


def test_feedback_is_stored_with_question_and_answer(client):
    rid = client.post("/ask", json={"question": "GPA bao nhiêu?", "khoa": 68}).json()["request_id"]
    r = client.post("/feedback", json={"request_id": rid, "helpful": False, "comment": "thiếu ý"})
    assert r.status_code == 204
    record = json.loads((client.data_dir / "feedback.jsonl").read_text(encoding="utf-8"))
    assert record["question"] == "GPA bao nhiêu?" and record["helpful"] is False


def test_feedback_for_unknown_answer_is_404(client):
    assert client.post("/feedback", json={"request_id": "x", "helpful": True}).status_code == 404


def test_documents_list_cohorts_and_amendments(client):
    docs = {d["doc_id"]: d for d in client.get("/documents").json()}
    assert docs["qc-dhxd-2022"]["khoa_tu"] == 67
    assert docs["qd-danh-gia-cdr-2026"]["sua_doi"] == ["qc-dhxd-2016", "qc-dhxd-2022"]


def test_index_serves_demo_page(client):
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]


def test_rate_limit_per_client(tmp_path):
    with TestClient(create_app(FakeQA, data_dir=tmp_path, rate_limit_per_min=2)) as c:
        codes = [c.post("/ask", json={"question": "GPA bao nhiêu?"}).status_code for _ in range(3)]
        r = c.post("/ask", json={"question": "GPA bao nhiêu?"})
    assert codes == [200, 200, 429]
    assert int(r.headers["Retry-After"]) >= 1


def test_rate_limiter_window_expires():
    limiter = RateLimiter(1, window_s=0.05)
    assert limiter.retry_after("a") == 0
    assert limiter.retry_after("a") > 0
    assert limiter.retry_after("b") == 0
    time.sleep(0.06)
    assert limiter.retry_after("a") == 0


def test_answers_are_not_serialized(tmp_path):
    started = threading.Barrier(2, timeout=5)

    class SlowQA(FakeQA):
        def answer(self, question, khoa):
            started.wait()  # chỉ qua được khi hai request chạy cùng lúc
            return super().answer(question, khoa)

    with (
        TestClient(create_app(SlowQA, data_dir=tmp_path, rate_limit_per_min=0)) as c,
        ThreadPoolExecutor(2) as pool,
    ):
        codes = list(
            pool.map(lambda _: c.post("/ask", json={"question": "GPA?"}).status_code, range(2))
        )
    assert codes == [200, 200]
