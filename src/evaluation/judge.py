"""LLM-as-judge: chấm độ đúng nội dung câu trả lời so với đáp án chuẩn."""

import json
import re
from dataclasses import dataclass

from generation.llm import LLM, LLMResponse

VERDICTS = ("dung", "dung_mot_phan", "sai")
SCORE = {"dung": 1.0, "dung_mot_phan": 0.5, "sai": 0.0}

JUDGE_SYSTEM = """Bạn là giám khảo chấm câu trả lời của một hệ thống hỏi đáp quy chế đào tạo.
So câu trả lời của hệ thống với đáp án chuẩn và chỉ chấm nội dung: kết luận, con số, điều kiện.
Không chấm văn phong, độ dài hay cách trích dẫn.

- "dung": kết luận chính đúng, đủ các ý chính của đáp án chuẩn, không có khẳng định sai.
- "dung_mot_phan": kết luận chính đúng nhưng thiếu một ý quan trọng, hoặc có một ý phụ sai.
- "sai": kết luận chính sai hoặc không có, sai con số quan trọng, hoặc từ chối trả lời.

Thông tin bổ sung đúng và không mâu thuẫn với đáp án chuẩn thì không bị trừ điểm.
Viết "ly_do" ngắn gọn trước, nêu ý nào đúng, ý nào thiếu hoặc sai; sau đó mới kết luận."""

JUDGE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "ly_do": {"type": "STRING"},
        "ket_luan": {"type": "STRING", "enum": list(VERDICTS)},
    },
    "required": ["ly_do", "ket_luan"],
}


@dataclass
class Verdict:
    ket_luan: str
    ly_do: str
    llm: LLMResponse | None = None

    @property
    def score(self) -> float:
        return SCORE[self.ket_luan]


class Judge:
    def __init__(self, llm: LLM):
        self.llm = llm

    def grade(self, question: str, reference: str, answer: str) -> Verdict:
        prompt = (f"Câu hỏi: {question}\n\nĐáp án chuẩn: {reference}\n\n"
                  f"Câu trả lời của hệ thống: {answer}")
        response = self.llm.generate(JUDGE_SYSTEM, prompt, JUDGE_SCHEMA)
        try:
            text = re.sub(r"^```(?:json)?|```$", "", response.text.strip(), flags=re.MULTILINE)
            data = json.loads(text)
            verdict = data["ket_luan"]
            if verdict not in VERDICTS:
                raise ValueError(verdict)
            return Verdict(verdict, data.get("ly_do", ""), response)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"Giám khảo trả về sai định dạng: {response.text[:200]}") from e
