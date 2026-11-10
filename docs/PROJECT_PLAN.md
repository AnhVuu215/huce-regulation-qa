# Kế hoạch dự án: Hỏi đáp quy chế đào tạo HUCE (RAG)

Nov 7, 2026 · @Tuananh

## Tổng quan

Xây hệ thống hỏi đáp về quy chế đào tạo của Trường Đại học Xây dựng Hà Nội, mỗi câu trả lời kèm trích dẫn Điều/Khoản, và chứng minh chất lượng bằng bộ test có số liệu. Mảng trọng tâm: AI Engineering.

**Người dùng:** sinh viên đại học chính quy của trường, hỏi về học vụ (tín chỉ, cảnh báo học vụ, tốt nghiệp, học lại, xếp loại).

**Mục tiêu:**

- Trả lời đúng theo đúng phiên bản quy chế áp dụng cho khóa của người hỏi.
- Mọi khẳng định đều có trích dẫn kiểm chứng được.
- Từ chối rõ ràng khi quy chế không có căn cứ.
- Có báo cáo đánh giá: baseline so với bản cuối, từng cải tiến đóng góp bao nhiêu.

**Trong phạm vi:** quy chế đào tạo đại học chính quy của trường, Thông tư 08/2021/TT-BGDĐT làm khung, các quy định học vụ liên quan (chuẩn đầu ra ngoại ngữ, thực tập tốt nghiệp).

**Ngoài phạm vi (giai đoạn 1):** học phí từng năm, lịch học, thông báo ngắn hạn, sau đại học, kết nối tài khoản sinh viên hay điểm cá nhân.

## Thách thức chính

Năm điểm dưới đây là nơi chatbot RAG thông thường sai, và cũng là nơi dự án tạo khác biệt.

| Thách thức | Ví dụ sai | Hướng xử lý |
| --- | --- | --- |
| Nhiều phiên bản theo khóa | Sinh viên khóa cũ nhận câu trả lời theo quy chế mới | Metadata hiệu lực + khóa áp dụng, lọc trước khi tìm, hỏi lại khóa khi thiếu |
| Cấu trúc Điều/Khoản/Điểm | Chunk cắt ngang khoản, mất điều kiện "trừ trường hợp" | Parser theo cấu trúc, chunk theo Điều hoặc Khoản, kèm tiêu đề |
| Ngôn ngữ sinh viên khác văn bản | "Rớt mấy môn thì bị đuổi" không khớp "buộc thôi học" | Hybrid search, từ điển đồng nghĩa, viết lại câu hỏi |
| Câu hỏi cần tính toán | So sánh GPA với ngưỡng xếp loại | Trích ngưỡng thành dữ liệu có cấu trúc, tính bằng code thay vì để LLM tính |
| Ngoài phạm vi | Bịa học phí hoặc lịch thi | Ngưỡng liên quan khi truy xuất + quy tắc từ chối, có câu test riêng |

## Kiến trúc hệ thống

Hệ thống gồm ba luồng: nạp dữ liệu chạy một lần mỗi khi có văn bản mới, trả lời câu hỏi chạy mỗi request, và đánh giá chạy sau mỗi thay đổi.

&#91;embedded content: kiến trúc · 3 luồng: nạp dữ liệu, trả lời, đánh giá\]

- **Lọc theo khóa đứng trước tìm kiếm**, không để LLM tự chọn phiên bản.
- **Hậu kiểm trích dẫn bằng code:** Điều/Khoản được trích phải nằm trong các chunk đã lấy, nếu không thì loại hoặc đánh dấu không chắc chắn.
- **Tính toán tách riêng:** LLM gọi công cụ để so GPA với ngưỡng, thay vì tự tính.
- **Mỗi bước bật/tắt được bằng cấu hình** để đo đóng góp của từng cải tiến trong bảng ablation.

## Dữ liệu

Bạn cung cấp quy chế của trường; mỗi văn bản được lưu kèm phiên bản và khóa áp dụng ngay từ lúc nhập.

**Văn bản cần thu thập**

| Văn bản | Vai trò | Nguồn |
| --- | --- | --- |
| Quy chế đào tạo đại học hiện hành của trường | Nguồn chính | Bạn cung cấp |
| Các quyết định sửa đổi, bổ sung | Phiên bản mới của từng Điều | Bạn cung cấp |
| Quy chế ban hành theo QĐ số 33 ngày 07/01/2016 | Phiên bản cũ, dùng test phân biệt phiên bản | [Trang khoa Vật liệu](https://vatlieu.huce.edu.vn/images/ckeditor/files/Quy%20che%20dao%20tao%2043.pdf) |
| Thông tư 08/2021/TT-BGDĐT | Khung của Bộ, dùng khi quy chế trường dẫn chiếu | [Thư viện Pháp luật](https://thuvienphapluat.vn/van-ban/Giao-duc/Thong-tu-08-2021-TT-BGDDT-Quy-che-dao-tao-trinh-do-dai-hoc-470013.aspx) |
| Quy định chuẩn đầu ra ngoại ngữ, thực tập tốt nghiệp | Câu hỏi sinh viên hay gặp | Bạn cung cấp |

**Schema mỗi đơn vị (chunk)**

```json
{
  "chunk_id": "qc2021-d12-k3",
  "doc_id": "qc-dhxd-2021",
  "doc_title": "Quy chế đào tạo trình độ đại học",
  "so_hieu": "…/QĐ-ĐHXDHN",
  "hieu_luc_tu": "YYYY-MM-DD",
  "ap_dung_khoa": ["K66", "K67"],
  "chuong": "Chương III",
  "dieu": 12,
  "dieu_title": "Đánh giá kết quả học tập theo học kỳ",
  "khoan": 3,
  "text": "…",
  "sua_doi_boi": null
}
```

**Quy tắc chunk**

1. Mặc định một chunk = một Điều.
2. Điều dài quá ngưỡng token thì tách theo Khoản, mỗi chunk lặp lại tên Điều ở đầu.
3. Không bao giờ cắt giữa một Khoản hoặc một bảng.
4. Bảng (thang điểm, xếp loại) được trích thêm thành dữ liệu có cấu trúc để code tính toán.

**Câu hỏi còn mở:** quy chế hiện hành là file scan hay file text? Quyết định này quyết định có cần OCR ở tuần 1 hay không.

## Chiến lược đánh giá

Bộ test 150–200 câu được xây từ tuần 3, trước mọi tối ưu; mỗi cải tiến phải có số liệu trước/sau.

**Loại câu hỏi và tỷ lệ mục tiêu**

| Loại | Ví dụ | Tỷ lệ |
| --- | --- | --- |
| Tra cứu trực tiếp | Điều kiện được học cùng lúc hai chương trình? | 25% |
| Diễn đạt kiểu sinh viên | Rớt mấy môn thì bị cảnh cáo? | 25% |
| Kết hợp nhiều Điều | Bị cảnh báo học vụ có được học vượt không? | 15% |
| Có tính toán | GPA 3,15 và từng học lại 1 môn thì xếp loại gì? | 15% |
| Phụ thuộc phiên bản | Cùng câu hỏi, hai khóa khác nhau | 10% |
| Ngoài phạm vi | Học phí năm nay bao nhiêu? | 10% |

Nguồn câu hỏi: ưu tiên câu thật từ group, fanpage sinh viên của trường; câu tự viết chỉ để lấp loại còn thiếu. Mỗi câu ghi: khóa, đáp án chuẩn, Điều/Khoản căn cứ, có nên từ chối hay không.

**Chỉ số**

| Tầng | Chỉ số | Cách đo |
| --- | --- | --- |
| Retrieval | Recall@5, MRR | Điều/Khoản chuẩn có trong top k không, đo bằng code |
| Trích dẫn | Tỷ lệ trích dẫn đúng | So trích dẫn với Điều/Khoản chuẩn, đo bằng code |
| Câu trả lời | Độ đúng (đúng / đúng một phần / sai) | LLM-as-judge, chấm tay 20% để kiểm tra judge |
| Từ chối | Từ chối đúng, từ chối nhầm | So với nhãn "nên từ chối" |
| Vận hành | Độ trễ p50/p95, chi phí mỗi câu | Log của hệ thống |

**Quy trình:** một lệnh `make eval` chạy toàn bộ bộ test, xuất bảng kết quả theo từng loại câu, lưu kết quả mỗi lần chạy để so sánh các phiên bản pipeline.

## Tech stack và cấu trúc repo

Stack giữ đơn giản, ít framework, để mỗi thành phần tự viết và giải thích được khi phỏng vấn.

| Thành phần | Lựa chọn | Ghi chú |
| --- | --- | --- |
| Ngôn ngữ | Python 3.11+ | Quản lý môi trường bằng uv hoặc poetry |
| Đọc PDF / OCR | PyMuPDF; OCR chỉ khi là bản scan | Kiểm tra dấu tiếng Việt sau OCR |
| Embedding | bge-m3 (đa ngôn ngữ) | So sánh thêm 1 model khác trong eval |
| Tìm từ khóa | BM25 (rank-bm25 hoặc full-text của Postgres) | Bắt số hiệu, con số, thuật ngữ |
| Vector store | PostgreSQL + pgvector | Một DB cho cả metadata và vector |
| Reranker | Cross-encoder đa ngôn ngữ | Bật/tắt được để đo đóng góp |
| LLM | Gọi qua API, bọc sau một interface riêng | Đổi nhà cung cấp không sửa logic |
| API | FastAPI | Endpoint hỏi đáp + feedback |
| Giao diện | Streamlit hoặc trang web nhỏ | Đủ để demo |
| Đóng gói | Docker Compose | App + Postgres |
| Chất lượng code | pytest, ruff, GitHub Actions | Chạy eval rút gọn trong CI |

```text
huce-regulation-qa/
├── data/
│   ├── raw/            # PDF gốc
│   ├── processed/      # JSON theo Điều/Khoản
│   └── registry.yaml   # danh sách văn bản, hiệu lực, khóa áp dụng
├── src/
│   ├── ingestion/      # đọc PDF, OCR, parser cấu trúc
│   ├── indexing/       # embedding, BM25, ghi DB
│   ├── retrieval/      # hybrid search, lọc khóa, rerank
│   ├── generation/     # prompt, hậu kiểm trích dẫn, từ chối
│   ├── tools/          # tính toán GPA, xếp loại
│   └── api/            # FastAPI
├── eval/
│   ├── testset.jsonl   # câu hỏi + đáp án chuẩn
│   ├── run_eval.py
│   └── results/        # kết quả từng lần chạy
├── ui/
├── tests/
├── docker-compose.yml
├── Makefile
└── README.md
```

## Lộ trình 7 tuần

Bộ test có từ tuần 3; từ đó mỗi tuần kết thúc bằng một lần `make eval` và ghi số liệu. Ngày bắt đầu: câu hỏi còn mở, điền khi bạn chốt.

| Tuần | Việc chính | Đầu ra kiểm chứng được |
| --- | --- | --- |
| 1 | Thu thập văn bản, OCR nếu cần, lập `registry.yaml` (hiệu lực, khóa áp dụng); dựng repo, CI | Kho văn bản sạch + repo chạy được |
| 2 | Parser Điều/Khoản/Điểm + metadata; unit test cho parser | JSON đầy đủ, test parser pass |
| 3 | 50 câu test đầu tiên; baseline RAG đơn giản (chunk theo token, chỉ vector) | Số liệu baseline |
| 4 | Chunk theo cấu trúc, hybrid search, reranker, lọc theo khóa | Recall@5 so với baseline |
| 5 | Generation có trích dẫn, hậu kiểm trích dẫn, từ chối | Tỷ lệ trích dẫn đúng, từ chối đúng |
| 6 | Mở rộng bộ test lên 150–200 câu; công cụ tính GPA/xếp loại; chấm tay kiểm tra judge | Báo cáo đánh giá đầy đủ |
| 7 | FastAPI, giao diện, Docker, deploy, README có bảng ablation | Link demo + repo công khai |

Nếu trễ: cắt giao diện (giữ API + CLI) và công cụ tính toán trước; không cắt bộ test và báo cáo đánh giá.

## Rủi ro và cách giảm thiểu

Rủi ro lớn nhất là phần dữ liệu (OCR, parser) ăn hết thời gian và dự án không tới được phần đánh giá.

| Rủi ro | Dấu hiệu | Cách xử lý |
| --- | --- | --- |
| Parser vượt quá tuần 2 | Đánh số Điều/Khoản không nhất quán | Sửa tay phần lỗi, không cố viết parser hoàn hảo |
| OCR sai dấu tiếng Việt | Tra cứu từ khóa không ra | Soát tay các Điều hay được hỏi, xin bản text nếu có |
| Không xác định được khóa áp dụng | Văn bản không ghi rõ | Hỏi phòng Đào tạo; tạm gắn "chưa rõ" và cảnh báo trong câu trả lời |
| Quy chế sắp sửa đổi | Có văn bản mới sau khi đã index | Thiết kế registry để thêm phiên bản không sửa code; biến thành demo |
| LLM-as-judge chấm sai | Lệch nhiều so với chấm tay | Chấm tay 20%, báo cáo độ khớp giữa judge và người |
| Người dùng tin câu trả lời sai | — | Luôn hiển trích dẫn + nhắc kiểm tra với phòng Đào tạo với việc quan trọng |
| Chi phí gọi LLM khi chạy eval nhiều | Hóa đơn API tăng | Cache kết quả, eval rút gọn khi phát triển, eval đầy đủ cuối tuần |

## Tiêu chí hoàn thành và trình bày trên CV

Dự án xong khi người ngoài clone repo, chạy một lệnh và thấy lại đúng số liệu trong README.

- [ ] Bộ test ≥ 150 câu, đủ 6 loại, công khai trong repo
- [ ] Bảng ablation: baseline → chunk cấu trúc → hybrid → rerank → lọc khóa → hậu kiểm trích dẫn
- [ ] Demo công khai hoặc video demo 2–3 phút
- [ ] `docker compose up` chạy được trên máy sạch
- [ ] README có sơ đồ kiến trúc, kết quả, hạn chế đã biết
- [ ] Phần "Những gì không hiệu quả": các thử nghiệm thất bại và lý do

**Mẫu dòng trên CV** (điền số thật khi có):

> Xây hệ thống RAG hỏi đáp quy chế đào tạo có trích dẫn Điều/Khoản, xử lý nhiều phiên bản theo khóa. Hybrid search + reranker tăng Recall@5 từ X% lên Y%; hậu kiểm trích dẫn đưa tỷ lệ trích dẫn đúng lên Z% trên bộ test N câu tự xây.

Khi phỏng vấn, chuẩn bị kỹ 3 câu chuyện: cách xử lý phiên bản, vì sao tính toán bằng code thay vì LLM, và một thử nghiệm thất bại đã dạy bạn điều gì.

**Nguồn:** [Quy chế 2016 của trường](https://vatlieu.huce.edu.vn/images/ckeditor/files/Quy%20che%20dao%20tao%2043.pdf) · [Thông tư 08/2021/TT-BGDĐT](https://thuvienphapluat.vn/van-ban/Giao-duc/Thong-tu-08-2021-TT-BGDDT-Quy-che-dao-tao-trinh-do-dai-hoc-470013.aspx)
