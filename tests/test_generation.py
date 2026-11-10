"""Logic trả lời với LLM giả lập: không cần mạng, không cần mô hình embedding."""

import json

import pytest

from huce_qa.generation.answer import QA, QAConfig
from huce_qa.generation.llm import (
    CachedLLM,
    DailyQuotaError,
    FakeLLM,
    LLMError,
    load_env,
    models_from_env,
)
from huce_qa.ingestion.registry import Document
from huce_qa.retrieval.corpus import Passage, Unit

DOCS = {
    "new": Document(
        doc_id="new",
        chunk_prefix="n",
        doc_title="Quy chế mới",
        so_hieu="1",
        file="x",
        sha256="x",
        hieu_luc_tu="2022-09-23",
        khoa_tu=67,
    ),
    "old": Document(
        doc_id="old",
        chunk_prefix="o",
        doc_title="Quy chế cũ",
        so_hieu="2",
        file="x",
        sha256="x",
        hieu_luc_tu="2016-01-07",
        khoa_den=66,
    ),
}
P_NEW = Passage("n-d11-k2", "new", "Điều 11. Buộc thôi học ...", (Unit("new", 11, 2),), 67, None)
P_OLD = Passage("o-d16-k2", "old", "Điều 16. Buộc thôi học ...", (Unit("old", 16, 2),), None, 66)


class StubRetriever:
    def __init__(self, passages, similarity=0.7):
        self.passages, self.similarity = passages, similarity

    def search(self, question, khoa=None, k=10):
        return [p for p in self.passages if khoa is None or p.ap_dung_cho(khoa)][:k]

    def max_similarity(self, question, khoa=None):
        return self.similarity


def reply(tra_loi, trich_dan, tu_choi=False):
    return lambda prompt: json.dumps(
        {"tu_choi": tu_choi, "tra_loi": tra_loi, "trich_dan": trich_dan}, ensure_ascii=False
    )


def make_qa(llm, passages=(P_NEW, P_OLD), similarity=0.7):
    return QA(StubRetriever(list(passages), similarity), llm, DOCS, QAConfig())


def test_valid_citation_is_kept_and_mapped_to_unit():
    a = make_qa(FakeLLM(reply("Theo Điều 11, quá 3 lần liên tiếp.", [1]))).answer("?", 68)
    assert a.status == "tra_loi"
    assert a.citations == [Unit("new", 11, 2)]
    assert not a.uncertain


def test_out_of_range_citation_is_dropped():
    a = make_qa(FakeLLM(reply("Theo Điều 11.", [1, 7]))).answer("?", 68)
    assert a.dropped_citations == [7]
    assert a.cited_passages == ["n-d11-k2"]


def test_mention_of_article_not_retrieved_is_flagged():
    a = make_qa(FakeLLM(reply("Theo Điều 25, bị buộc thôi học.", [1]))).answer("?", 68)
    assert a.unverified_mentions == [25]
    assert a.uncertain


def test_answer_without_citation_is_uncertain():
    a = make_qa(FakeLLM(reply("Có.", []))).answer("?", 68)
    assert a.uncertain


def test_prompt_only_contains_passages_for_student_cohort():
    llm = FakeLLM(reply("x", [1]))
    make_qa(llm).answer("?", 68)
    prompt = llm.calls[0][1]
    assert "Quy chế mới" in prompt and "Quy chế cũ" not in prompt
    assert "K68" in prompt


def test_asks_for_cohort_when_versions_differ():
    llm = FakeLLM(reply("x", [1]))
    a = make_qa(llm).answer("Bị cảnh báo mấy lần thì bị buộc thôi học?", None)
    assert a.status == "hoi_lai_khoa"
    assert llm.calls == []


def test_low_relevance_refuses_without_calling_llm():
    llm = FakeLLM(reply("x", [1]))
    a = make_qa(llm, similarity=0.2).answer("Ký túc xá còn chỗ không?", 68)
    assert a.status == "tu_choi"
    assert llm.calls == []


def test_llm_refusal_is_respected():
    a = make_qa(FakeLLM(reply("Quy chế không quy định.", [], tu_choi=True))).answer("?", 68)
    assert a.status == "tu_choi"
    assert not a.uncertain


def test_malformed_output_is_flagged():
    a = make_qa(FakeLLM(lambda p: "không phải JSON")).answer("?", 68)
    assert a.uncertain and a.warnings


def test_cache_avoids_second_call(tmp_path):
    inner = FakeLLM(lambda p: "ok")
    llm = CachedLLM(inner, tmp_path, "fake")
    first, second = llm.generate("s", "p"), llm.generate("s", "p")
    assert len(inner.calls) == 1
    assert second.cached and not first.cached


FENCED = '```json\n{"tu_choi": false, "tra_loi": "a", "trich_dan": [1]}\n```'


@pytest.mark.parametrize("fenced", [FENCED])
def test_code_fenced_json_is_parsed(fenced):
    a = make_qa(FakeLLM(lambda p: fenced)).answer("?", 68)
    assert a.cited_passages == ["n-d11-k2"]


def test_cache_skips_answers_from_fallback_model(tmp_path):
    llm = CachedLLM(FakeLLM(lambda p: "ok"), tmp_path, "gemini-main")
    llm.generate("s", "p")
    assert list((tmp_path / "gemini-main").iterdir()) == []


class RecordingTools:
    """Công cụ giả: ghi lại tham số nhận được, trả về một kết quả kèm căn cứ."""

    def __init__(self):
        self.received = []

    def call(self, name, args):
        self.received.append((name, dict(args)))
        return {"xep_loai": "Khá", "can_cu": [{"doc_id": "new", "dieu": 10, "khoan": 4}]}


def test_tool_call_uses_asker_cohort_and_becomes_citation():
    tools = RecordingTools()
    llm = FakeLLM(
        reply("Theo Điều 10, học lực loại Khá.", [1]),
        tool_requests=[("xep_loai_hoc_luc", {"khoa": 65, "diem_trung_binh": 3.15})],
    )
    qa = QA(StubRetriever([P_NEW, P_OLD]), llm, DOCS, QAConfig(), tools=tools)
    a = qa.answer("GPA 3,15 thì học lực loại gì?", 68)
    assert tools.received == [("xep_loai_hoc_luc", {"khoa": 68, "diem_trung_binh": 3.15})]
    assert Unit("new", 10, 4) in a.citations
    assert a.unverified_mentions == []  # Điều 10 đến từ căn cứ của công cụ


def test_always_mode_adds_tool_rule_to_system_prompt():
    llm = FakeLLM(reply("x", [1]))
    config = QAConfig(tools_mode="always")
    QA(StubRetriever([P_NEW]), llm, DOCS, config, tools=RecordingTools()).answer("?", 68)
    assert "PHẢI gọi công cụ" in llm.calls[0][0]


def test_cache_expires_when_tool_fingerprint_changes(tmp_path):
    inner = FakeLLM(lambda p: "ok")
    llm = CachedLLM(inner, tmp_path, "fake")

    def handler(name, args):
        return {}

    for fingerprint in ["v1", "v1", "v2"]:
        handler.fingerprint = fingerprint
        llm.generate("s", "p", tools=[{"name": "t"}], tool_handler=handler)
    assert len(inner.calls) == 2


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("GPA 3,15 thì học lực loại gì?", True),
        ("Kỳ này em đăng ký 18 tín và trượt 10 tín", True),
        ("GPA bao nhiêu thì được ra trường?", False),
    ],
)
def test_auto_mode_uses_tools_only_for_questions_with_numbers(question, expected):
    llm = FakeLLM(reply("x", [1]))
    QA(StubRetriever([P_NEW]), llm, DOCS, QAConfig(), tools=RecordingTools()).answer(question, 68)
    assert ("PHẢI gọi công cụ" in llm.calls[0][0]) is expected


def test_amended_passage_brings_in_amending_provision():
    from huce_qa.retrieval.corpus import Amendment

    docs = {
        **DOCS,
        "rule": Document(
            doc_id="rule",
            chunk_prefix="r",
            doc_title="Quy định mới",
            so_hieu="2026",
            file="x",
            sha256="x",
            hieu_luc_tu="2026-03-12",
        ),
    }
    amending = Passage("r-d6-k4", "rule", "Điều 6. Cuối kỳ 50%", (Unit("rule", 6, 4),), None, None)
    amended = Passage(
        "n-d9-k1",
        "new",
        "Điều 9. Trọng số do đề cương",
        (Unit("new", 9, 1),),
        67,
        None,
        amended_by=(Amendment("rule", "trọng số 25/25/50", (Unit("rule", 6, 4),)),),
    )
    retriever = StubRetriever([amended])
    retriever.passages = [amended, amending]
    llm = FakeLLM(reply("Cuối kỳ 50% theo Điều 6.", [2]))
    a = QA(retriever, llm, docs, QAConfig()).answer("Thi cuối kỳ chiếm bao nhiêu?", 68)
    prompt = llm.calls[0][1]
    assert "ĐÃ ĐƯỢC SỬA ĐỔI bởi Quy định mới" in prompt
    assert "[2] Điều 6 Khoản 4" in prompt
    assert a.cited_passages == ["r-d6-k4"]
    assert a.unverified_mentions == []


def test_quota_error_reports_server_retry_delay():
    import io
    import urllib.error

    from huce_qa.generation.llm import _quota_detail

    body = json.dumps(
        {
            "error": {
                "details": [
                    {
                        "violations": [
                            {"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}
                        ]
                    },
                    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "31s"},
                ]
            }
        }
    ).encode()
    err = urllib.error.HTTPError("u", 429, "Too Many Requests", {}, io.BytesIO(body))
    detail, delay = _quota_detail(err)
    assert "PerMinute" in detail and delay == 32.0


def test_superseded_passage_is_dropped_when_amending_one_is_cited():
    from huce_qa.retrieval.corpus import Amendment

    docs = {
        **DOCS,
        "rule": Document(
            doc_id="rule",
            chunk_prefix="r",
            doc_title="Quy định mới",
            so_hieu="2026",
            file="x",
            sha256="x",
            hieu_luc_tu="2026-03-12",
        ),
    }
    amending = Passage("r-d6-k4", "rule", "Điều 6. Cuối kỳ 50%", (Unit("rule", 6, 4),), None, None)
    amended = Passage(
        "n-d9-k1",
        "new",
        "Điều 9. Trọng số do đề cương",
        (Unit("new", 9, 1),),
        67,
        None,
        amended_by=(Amendment("rule", "trọng số 25/25/50", (Unit("rule", 6, 4),)),),
    )
    retriever = StubRetriever([amended])
    retriever.passages = [amended, amending]
    llm = FakeLLM(reply("Cuối kỳ 50%.", [1, 2]))
    a = QA(retriever, llm, docs, QAConfig()).answer("Thi cuối kỳ chiếm bao nhiêu?", 68)
    assert a.cited_passages == ["r-d6-k4"]


def test_concurrent_calls_keep_min_interval(monkeypatch):
    import io  # noqa: PLC0415
    import threading  # noqa: PLC0415
    import time  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    from huce_qa.generation.llm import GeminiClient  # noqa: PLC0415

    times = []

    def fake_urlopen(req, timeout):
        times.append(time.monotonic())
        return io.BytesIO(b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = GeminiClient(["mo-hinh-thu-khoang-cach"], api_key="x", min_interval_s=0.1)
    threads = [
        threading.Thread(target=client._post, args=("mo-hinh-thu-khoang-cach", {}))
        for _ in range(3)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    times.sort()
    assert all(b - a >= 0.09 for a, b in zip(times, times[1:], strict=False))


def test_models_are_read_from_env_file_loaded_after_import(tmp_path, monkeypatch):
    # setenv trước để monkeypatch ghi nhận trạng thái ban đầu và khôi phục sau khi load_env ghi đè.
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.delenv("LLM_MODEL")
    env = tmp_path / ".env"
    env.write_text("LLM_MODEL=model-a, model-b,\n", encoding="utf-8")
    load_env(env)
    assert models_from_env() == ["model-a", "model-b"]


def test_models_fall_back_to_default_when_unset(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", " , ")
    assert models_from_env() == ["gemini-3.5-flash-lite"]


def _quota_429(quota_id: str):
    import io
    import urllib.error

    body = json.dumps({"error": {"details": [{"violations": [{"quotaId": quota_id}]}]}}).encode()
    return urllib.error.HTTPError("u", 429, "Too Many Requests", {}, io.BytesIO(body))


@pytest.mark.parametrize(
    ("errors", "expected"),
    [
        # Mô hình chính hết lượt ngày, mô hình dự phòng quá tải: vẫn báo hết hạn mức ngày.
        ({"a": "GenerateRequestsPerDayPerProjectPerModel-FreeTier", "b": None}, DailyQuotaError),
        ({"a": None, "b": None}, LLMError),
    ],
)
def test_client_reports_daily_quota_as_its_own_error(monkeypatch, errors, expected):
    import urllib.error

    from huce_qa.generation.llm import GeminiClient

    def post(self, model, body):
        if errors[model]:
            raise _quota_429(errors[model])
        raise urllib.error.HTTPError("u", 400, "Bad Request", {}, None)

    monkeypatch.setattr(GeminiClient, "_post", post)
    client = GeminiClient(["a", "b"], api_key="k", retries=0)
    with pytest.raises(LLMError) as info:
        client.generate("s", "p")
    assert type(info.value) is expected
