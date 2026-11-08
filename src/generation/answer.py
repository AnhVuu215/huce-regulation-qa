"""Trả lời có trích dẫn: hỏi lại khóa, cổng liên quan, gọi LLM, hậu kiểm trích dẫn bằng code."""

import json
import re
from dataclasses import dataclass, field

from generation.llm import LLM, LLMResponse
from ingestion.registry import Document
from retrieval.corpus import Passage, Unit
from tools.hoc_vu import FUNCTION_DECLARATIONS

DISCLAIMER = (
    "Thông tin chỉ mang tính tham khảo theo văn bản quy chế. Với việc quan trọng "
    "(xét tốt nghiệp, buộc thôi học, chuyển ngành...), hãy xác nhận với Phòng Quản lý đào tạo."
)

SYSTEM = """Bạn là trợ lý tra cứu quy chế đào tạo của Trường Đại học Xây dựng Hà Nội.
Quy tắc:
1. Chỉ dùng thông tin trong các đoạn văn bản được cung cấp, không dùng hiểu biết bên ngoài.
2. Mỗi khẳng định phải dựa trên ít nhất một đoạn; ghi số thứ tự các đoạn đã dùng vào "trich_dan".
3. Chỉ đặt "tu_choi" là true khi không đoạn nào liên quan đến câu hỏi (ví dụ học phí từng năm,
   lịch thi, lịch mở lớp, điểm cá nhân), và nói ngắn gọn rằng quy chế không quy định nội dung này.
   Sinh viên thường hỏi một tình huống cụ thể mà quy chế chỉ có quy định chung (ví dụ "bảo lưu để
   ôn thi lại" là nghỉ học tạm thời vì lý do cá nhân): khi đó trả lời theo quy định chung, nói rõ
   là quy định chung áp dụng cho tình huống này, và nói rõ phần nào quy chế không quy định.
   Không đoán, không bịa số liệu.
4. Khi câu hỏi cần so sánh hoặc tính toán, trình bày phép tính và ngưỡng lấy từ đoạn văn bản.
5. Trả lời ngắn gọn, rõ ràng bằng tiếng Việt, xưng hô trung lập với sinh viên.
6. Có thể nêu "Điều X Khoản Y" trong câu trả lời, nhưng chỉ nêu những Điều có trong các đoạn.
7. Đoạn ghi "ĐÃ ĐƯỢC SỬA ĐỔI" có nội dung đã bị văn bản mới thay thế: trả lời theo văn bản
   sửa đổi (đoạn của nó được đưa kèm), nêu rõ là quy định hiện hành, trích dẫn đoạn đó."""

TOOLS_RULE = """
8. Khi câu hỏi cần tính điểm, quy đổi điểm, xếp loại, xếp hạng tốt nghiệp, xếp năm học hoặc xét
   cảnh báo, PHẢI gọi công cụ tương ứng và dùng đúng kết quả công cụ trả về; không tự tính.
   Nếu công cụ báo thiếu dữ liệu, nói rõ cần thêm thông tin gì. Kết quả công cụ đã kèm căn cứ,
   vẫn ghi số thứ tự các đoạn liên quan vào "trich_dan"."""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "tu_choi": {"type": "BOOLEAN"},
        "tra_loi": {"type": "STRING"},
        "trich_dan": {"type": "ARRAY", "items": {"type": "INTEGER"}},
    },
    "required": ["tu_choi", "tra_loi", "trich_dan"],
}

DIEU_MENTION = re.compile(r"Điều\s+(\d+)")


@dataclass
class Answer:
    status: str  # "tra_loi" | "tu_choi" | "hoi_lai_khoa"
    text: str
    citations: list[Unit] = field(default_factory=list)
    cited_passages: list[str] = field(default_factory=list)
    retrieved: list[str] = field(default_factory=list)
    relevance: float = 0.0
    dropped_citations: list[int] = field(default_factory=list)
    unverified_mentions: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    llm: LLMResponse | None = None

    @property
    def uncertain(self) -> bool:
        return bool(self.unverified_mentions) or (self.status == "tra_loi" and not self.citations)


def citation_label(unit: Unit, doc: Document) -> str:
    where = f"Điều {unit.dieu}" + (f" Khoản {unit.khoan}" if unit.khoan else "")
    return f"{where}, {doc.doc_title} ({doc.so_hieu})"


def _amends(amendment, passage: Passage) -> bool:
    return passage.doc_id == amendment.by_doc_id and any(
        pu.dieu == u.dieu and (u.khoan is None or pu.khoan is None or pu.khoan == u.khoan)
        for pu in passage.units for u in amendment.units
    )


def _drop_superseded(cited: list[Passage]) -> list[Passage]:
    """Trích cả đoạn đã bị sửa lẫn đoạn sửa đổi thì chỉ giữ đoạn sửa đổi: căn cứ hiện hành là
    văn bản mới, trích quy định đã bị thay thế dễ khiến sinh viên hiểu nhầm."""
    return [p for p in cited
            if not any(_amends(am, q) for am in p.amended_by for q in cited if q is not p)]


def _parse(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)


@dataclass
class QAConfig:
    top_k: int = 6
    # Cosine tối thiểu giữa câu hỏi và đoạn khớp nhất. Trên bộ test, phân bố của câu hợp lệ
    # (thấp nhất 0,544) và câu ngoài phạm vi (cao nhất 0,610) chồng lên nhau, nên ngưỡng chỉ
    # chặn câu lạc đề rõ ràng; việc từ chối chính do LLM quyết định theo quy tắc trong prompt.
    relevance_threshold: float = 0.50
    # Khi nào cho LLM gọi công cụ tính toán: "always" | "never" | "auto" (câu hỏi có con số).
    # Bật cho mọi câu làm gấp đôi token và khiến mô hình gọi công cụ cả khi không cần tính.
    tools_mode: str = "auto"


NUMBER = re.compile(r"\d")


def needs_calculation(question: str) -> bool:
    """Câu cần tính toán luôn kèm số liệu của người hỏi ("GPA 3,15", "18 tín", "120 tín chỉ")."""
    return NUMBER.search(question) is not None


class QA:
    def __init__(self, retriever, llm: LLM, docs: dict[str, Document], config: QAConfig,
                 tools=None):
        """`tools`: đối tượng công cụ học vụ (tools.hoc_vu.HocVu); None thì LLM tự trình bày."""
        self.retriever = retriever
        self.llm = llm
        self.docs = docs
        self.config = config
        self.tools = tools

    def _tool_handler(self, khoa: int | None):
        def handle(name: str, args: dict) -> dict:
            # Khóa đã biết thì ghi đè tham số của LLM: không thể tính nhầm theo quy chế khóa khác.
            if khoa is not None:
                args["khoa"] = khoa
            return self.tools.call(name, args)
        handle.fingerprint = getattr(self.tools, "fingerprint", None)
        return handle

    def _needs_khoa(self, passages: list[Passage]) -> bool:
        """Kết quả trải trên nhiều phiên bản giới hạn theo khóa: phải biết khóa mới trả lời được."""
        ranges = {(p.khoa_tu, p.khoa_den) for p in passages}
        return len([r for r in ranges if r != (None, None)]) > 1

    def _with_amendments(self, passages: list[Passage]) -> list[Passage]:
        """Đoạn đã bị sửa đổi thì kéo kèm các đoạn sửa đổi, kể cả khi truy xuất không lấy được
        chúng: nếu không, LLM chỉ thấy quy định cũ và trả lời theo nó."""
        result = list(passages)
        for p in passages:
            for am in p.amended_by:
                for q in self.retriever.passages:
                    if q in result or q.doc_id != am.by_doc_id:
                        continue
                    if any(qu.dieu == u.dieu and (u.khoan is None or qu.khoan is None
                                                  or qu.khoan == u.khoan)
                           for qu in q.units for u in am.units):
                        result.append(q)
        return result

    def answer(self, question: str, khoa: int | None) -> Answer:
        cfg = self.config
        passages = self.retriever.search(question, khoa, k=cfg.top_k)
        retrieved = [p.passage_id for p in passages]
        if khoa is None and self._needs_khoa(passages):
            return Answer(
                status="hoi_lai_khoa",
                text="Quy định này khác nhau giữa các khóa (K66 trở về trước và K67 trở đi). "
                "Bạn là sinh viên khóa nào?",
                retrieved=retrieved,
            )

        relevance = self.retriever.max_similarity(question, khoa)
        if relevance < cfg.relevance_threshold:
            return Answer(
                status="tu_choi",
                text="Mình không tìm thấy quy định nào về nội dung này trong quy chế đào tạo. "
                "Câu hỏi có thể nằm ngoài phạm vi (học phí từng năm, lịch thi, điểm cá nhân...); "
                "hãy liên hệ Phòng Quản lý đào tạo.",
                retrieved=retrieved,
                relevance=relevance,
            )

        passages = self._with_amendments(passages)
        blocks = []
        for n, p in enumerate(passages, start=1):
            label = citation_label(p.units[0], self.docs[p.doc_id])
            for am in p.amended_by:
                by = self.docs[am.by_doc_id]
                label += (f"\nĐÃ ĐƯỢC SỬA ĐỔI bởi {by.doc_title} ({by.so_hieu}): {am.noi_dung}. "
                          "Áp dụng quy định của văn bản sửa đổi.")
            blocks.append(f"[{n}] {label}\n{p.text}")
        who = f"Người hỏi là sinh viên khóa K{khoa}." if khoa else "Người hỏi không nêu khóa."
        context = "\n\n".join(blocks)
        prompt = f"{who}\n\nCác đoạn văn bản:\n\n{context}\n\nCâu hỏi: {question}"
        use_tools = self.tools is not None and (
            cfg.tools_mode == "always"
            or (cfg.tools_mode == "auto" and needs_calculation(question))
        )
        if use_tools:
            response = self.llm.generate(SYSTEM + TOOLS_RULE, prompt, SCHEMA,
                                         FUNCTION_DECLARATIONS, self._tool_handler(khoa))
        else:
            response = self.llm.generate(SYSTEM, prompt, SCHEMA)
        tool_units = [
            Unit(c["doc_id"], c["dieu"], c.get("khoan"))
            for call in response.tool_calls
            for c in call["result"].get("can_cu", [])
        ]

        try:
            data = _parse(response.text)
        except (json.JSONDecodeError, ValueError):
            return Answer(status="tra_loi", text=response.text, retrieved=retrieved,
                          relevance=relevance, llm=response,
                          warnings=["Không đọc được định dạng trả lời, chưa kiểm chứng trích dẫn."])

        status = "tu_choi" if data.get("tu_choi") else "tra_loi"
        valid, dropped = [], []
        for n in data.get("trich_dan", []):
            if isinstance(n, int) and 1 <= n <= len(passages):
                if passages[n - 1] not in valid:
                    valid.append(passages[n - 1])
            else:
                dropped.append(n)
        valid = _drop_superseded(valid)
        # Hậu kiểm: mọi "Điều N" nêu trong câu trả lời phải có trong các đoạn đã truy xuất
        # hoặc trong căn cứ do công cụ trả về (căn cứ công cụ lấy từ file quy tắc đã kiểm thử).
        retrieved_dieu = {u.dieu for p in passages for u in p.units} | {u.dieu for u in tool_units}
        mentions = {int(m) for m in DIEU_MENTION.findall(data.get("tra_loi", ""))}
        unverified = sorted(mentions - retrieved_dieu)
        citations = [u for p in valid for u in p.units]
        citations += [u for u in dict.fromkeys(tool_units) if u not in citations]

        result = Answer(
            status=status,
            text=data.get("tra_loi", ""),
            citations=citations,
            cited_passages=[p.passage_id for p in valid],
            retrieved=retrieved,
            relevance=relevance,
            dropped_citations=dropped,
            unverified_mentions=unverified,
            llm=response,
        )
        if dropped:
            result.warnings.append(f"Đã loại trích dẫn không hợp lệ: {dropped}")
        if unverified:
            result.warnings.append(
                f"Câu trả lời nhắc tới Điều {unverified} không có trong văn bản đã tra: "
                "chưa kiểm chứng được, hãy đối chiếu lại."
            )
        if result.status == "tra_loi" and not result.citations:
            result.warnings.append("Câu trả lời không có trích dẫn hợp lệ: không chắc chắn.")
        if result.status == "tra_loi":
            if any(self.docs[p.doc_id].khoa_chua_ro for p in valid):
                result.warnings.append("Văn bản trích dẫn chưa rõ khóa áp dụng.")
            result.warnings.append(DISCLAIMER)
        return result
