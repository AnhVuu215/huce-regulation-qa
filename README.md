# Hỏi đáp quy chế đào tạo HUCE

Hệ thống RAG trả lời câu hỏi của sinh viên Trường Đại học Xây dựng Hà Nội về quy chế đào tạo, mỗi câu
trả lời dẫn Điều, Khoản của đúng phiên bản quy chế áp dụng cho khóa của người hỏi, và từ chối khi quy
chế không có căn cứ. Kèm bộ đánh giá có số liệu: ablation từng bước, câu hỏi thật của sinh viên, tập
kiểm tra độc lập và hai vòng chấm tay để kiểm tra giám khảo LLM.

## Kết quả

| | câu tự viết (53) | **câu thật, tập độc lập (19)** |
|---|---|---|
| độ đúng nội dung (giám khảo LLM, đã kiểm bằng chấm tay) | 0,948 | **0,40** |
| từ chối đúng câu ngoài phạm vi | 5/5 | **9/9** |
| từ chối nhầm câu có căn cứ | 1/48 | 4/10 |
| tính toán (GPA, xếp loại, điểm học phần), bộ phát triển | 9/9 | — |
| kết quả sai phiên bản quy chế trong top-5 | 0% (baseline 44%) | — |

Hệ thống từ chối tốt câu ngoài quy chế, tính toán đúng và không lẫn phiên bản, nhưng mới trả lời đúng
khoảng 4/10 câu hỏi thật có căn cứ. Câu tự viết đánh giá quá cao hệ thống; con số để trích dẫn là của
tập độc lập, được commit trước khi chạy hệ thống. Chi tiết: [docs/EVALUATION.md](docs/EVALUATION.md).

## Điểm khác biệt

| vấn đề của chatbot RAG thông thường | cách xử lý |
|---|---|
| sinh viên khóa cũ nhận câu trả lời theo quy chế mới | registry ghi khóa áp dụng; lọc phiên bản trước khi tìm; hỏi lại khóa khi kết quả trải nhiều phiên bản |
| văn bản mới sửa quy tắc cũ cho mọi khóa | registry ghi quan hệ sửa đổi; đoạn bị sửa kéo kèm đoạn sửa đổi; trích đoạn sửa đổi |
| chunk cắt ngang Khoản, mất điều kiện "trừ trường hợp" | parser Chương/Điều/Khoản/Điểm; chia theo Điều, tách Khoản dài theo Điểm, lặp phần dẫn |
| LLM tự tính GPA sai | công cụ tính bằng code qua function calling, ngưỡng lấy từ file quy tắc có căn cứ |
| trích dẫn bịa | trích theo số thứ tự đoạn; hậu kiểm bằng code mọi Điều được nhắc phải nằm trong đoạn đã lấy |
| bịa học phí, lịch thi | quy tắc từ chối; 14/14 câu ngoài phạm vi thật bị từ chối đúng |

## Kiến trúc

```mermaid
flowchart LR
  subgraph nap[Nạp dữ liệu]
    PDF[PDF quy chế] --> OCR[OCR + soát tay<br/>nếu là bản scan]
    PDF --> P[Parser Điều/Khoản/Điểm]
    OCR --> P
    R[registry.yaml<br/>khóa, hiệu lực, sửa đổi] --> P
    P --> C[Đoạn văn bản]
  end
  subgraph traloi[Trả lời]
    Q[Câu hỏi + khóa] --> F[Lọc phiên bản theo khóa]
    C --> F
    F --> H[Vector bge-m3 + BM25, gộp RRF]
    H --> A[Kéo kèm đoạn sửa đổi]
    A --> L[LLM trả lời, trích dẫn theo đoạn]
    T[Công cụ học vụ] <--> L
    L --> V[Hậu kiểm trích dẫn bằng code]
  end
  subgraph danhgia[Đánh giá]
    TS[Bộ test + tập độc lập] --> M[Recall@5, trích dẫn, từ chối,<br/>giám khảo LLM, chấm tay]
  end
```

## Chạy thử

Cần một khóa API Gemini (gói miễn phí ở [Google AI Studio](https://aistudio.google.com/apikey)).

```bash
cp .env.example .env            # điền GEMINI_API_KEY
docker compose up --build       # mở http://127.0.0.1:8000
```

Lần đầu khởi động tải mô hình bge-m3 và tính embedding cho 521 đoạn văn bản (vài phút); các lần sau
dùng cache trong volume.

Chạy không dùng Docker (Python 3.11, [uv](https://docs.astral.sh/uv/)):

```bash
uv sync --group ml
uv run --group ml uvicorn api.app:app --app-dir src --port 8000
uv run pytest                   # 128 test, không cần mạng hay mô hình
```

## API

| method | đường dẫn | mô tả |
|---|---|---|
| POST | `/ask` | `{"question": "...", "khoa": 68}` → câu trả lời, trích dẫn, cảnh báo, `uncertain` |
| POST | `/feedback` | `{"request_id": "...", "helpful": true, "comment": "..."}` |
| GET | `/documents` | văn bản đang dùng, khóa áp dụng, quan hệ sửa đổi |
| GET | `/health` | trạng thái |

Tài liệu tương tác ở `/docs`. Mỗi request ghi độ trễ, mô hình, token và các đoạn đã lấy vào
`.data/requests.jsonl`; phản hồi lưu kèm câu hỏi và câu trả lời vào `.data/feedback.jsonl`.

## Đánh giá

```bash
uv run --group ml python eval/run_eval.py --ablation             # ablation truy xuất
uv run --group ml python eval/run_generation.py --no-fallback --tools --judge
uv run --group ml python eval/run_generation.py --no-fallback --tools --judge \
    --testset testset_holdout.jsonl                              # tập độc lập
```

| truy xuất, cộng dồn (45 câu tự viết) | Recall@5 | MRR | sai phiên bản@5 |
|---|---|---|---|
| baseline: cửa sổ 200 từ, chỉ vector | 0,752 | 0,632 | 0,436 |
| + chunk theo cấu trúc | 0,800 | 0,651 | 0,409 |
| + hybrid BM25 | 0,767 | 0,665 | 0,436 |
| + từ điển ngôn ngữ sinh viên | 0,874 | 0,711 | 0,431 |
| + reranker | 0,878 | 0,809 | 0,409 |
| + lọc theo khóa | 0,937 | 0,926 | 0,000 |

Những gì không hiệu quả (hybrid BM25 đứng một mình, reranker trên CPU, cổng liên quan bằng cosine,
tách câu hỏi ghép, sửa prompt không tổng quát hóa sang câu mới...) được ghi kèm số liệu trong
[docs/EVALUATION.md](docs/EVALUATION.md#những-gì-không-hiệu-quả).

## Dữ liệu

| văn bản | khóa | ghi chú |
|---|---|---|
| Quy chế đào tạo trình độ đại học, QĐ 1053/QĐ-ĐHXDHN (2022) | K67 trở đi | bản scan: OCR Tesseract trong Docker, soát tay với ảnh gốc |
| Quy chế đào tạo theo hệ thống tín chỉ, QĐ số 33 (2016) | K66 trở về trước | |
| Quy định đồ án tốt nghiệp, thực tập tốt nghiệp (2026) | mọi khóa | |
| Quy định đánh giá theo chuẩn đầu ra (2026) | mọi khóa | sửa trọng số điểm thành phần thành 25/25/50 |

Nguồn: [huce.edu.vn](https://www.huce.edu.vn/van-ban) và cổng sinh viên. Câu hỏi thật lấy từ các group
Facebook công khai của sinh viên HUCE, viết lại ẩn danh: không lưu tên, hồ sơ hay nguyên văn bài đăng.
Danh mục và lý do loại một số văn bản: [data/SOURCES.md](data/SOURCES.md).

## Thay đổi so với kế hoạch

- **Không dùng PostgreSQL + pgvector:** 521 đoạn văn bản tìm trong bộ nhớ mất vài mili giây; database
  chỉ thêm độ phức tạp.
- **Không dùng reranker trong bản chạy:** chỉ tăng MRR, không tăng Recall@5, tốn 20-30 giây mỗi câu.
- **Trang demo tự viết thay cho Streamlit:** một file HTML do FastAPI phục vụ, không thêm phụ thuộc.
- **Gemini thay cho LLM trả phí:** gói miễn phí; `gemini-3.6-flash` chỉ 20 lượt/ngày nên dùng
  `gemini-3.5-flash-lite`. LLM nằm sau một interface, đổi nhà cung cấp không sửa logic.

## Hạn chế

- Trả lời đúng khoảng 4/10 câu hỏi thật có căn cứ; tập độc lập còn nhỏ (10 câu có căn cứ).
- Chưa có quy định chuẩn ngoại ngữ theo khóa (bản scan), 11 Phụ lục quy trình, Thông tư 08/2021.
- Mô hình không cố định được `temperature`; số liệu tái lập nhờ cache câu trả lời.
- Thông tin chỉ mang tính tham khảo; việc quan trọng cần xác nhận với Phòng Quản lý đào tạo.

## Cấu trúc

```text
data/       registry.yaml, PDF gốc, bản text soát tay, quy tắc học vụ, từ điển, chunk đã xử lý
src/        ingestion, retrieval, generation, tools, evaluation, api
eval/       bộ test, tập độc lập, script đánh giá, kết quả, bảng chấm tay
docs/       ROADMAP.md (lộ trình và quyết định), EVALUATION.md (báo cáo)
tests/      128 test
```
