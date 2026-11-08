# Lộ trình triển khai theo phase

Tách từ `Kế hoạch dự án Hỏi đáp quy chế đào tạo HUCE (RAG).md`. Mỗi phase có các plan nhỏ
và một **cổng nghiệm thu**: chỉ sang phase sau khi cổng đã đạt.

Trạng thái: `[ ]` chưa làm · `[x]` xong · `[!]` chờ đầu vào từ chủ dự án

## Điều kiện môi trường đã kiểm tra (2026-11-07)

- Không GPU, RAM 11,7 GB: bge-m3 và reranker chạy CPU; kho văn bản nhỏ nên vẫn khả thi.
- Windows không có `make`: `Makefile` chỉ là lớp bọc mỏng, mọi lệnh đều chạy được bằng `uv run`.
- Quy chế 2016 là PDF có lớp text; Quy chế 2022 (K67 trở đi) là bản scan: OCR bằng Tesseract trong Docker, rồi soát tay.
- Máy đã có Postgres ở cổng 5432: container dùng cổng 5433.
- Chưa có API key LLM: Phase 5 trở đi cần chủ dự án chọn nhà cung cấp.

## Phase 0 — Nền tảng repo (tuần 1)

- [x] 0.1 `pyproject.toml`, môi trường Python 3.11 bằng uv
- [x] 0.2 Cấu trúc thư mục theo kế hoạch, `.gitignore`, `.env.example`
- [x] 0.3 ruff + pytest + `Makefile`
- [x] 0.4 GitHub Actions (lint + test)
- [x] 0.5 `docker-compose.yml` cho Postgres + pgvector

**Cổng:** `ruff check` và `pytest` pass; Postgres + pgvector khởi động được. Đã đạt, trừ CI chưa chạy trên GitHub.

## Phase 1 — Kho văn bản (tuần 1)

- [x] 1.1 `data/registry.yaml` + schema kiểm tra (hiệu lực, khóa áp dụng, nguồn, sha256)
- [x] 1.2 Thu thập văn bản từ huce.edu.vn và sinhvien.huce.edu.vn (danh mục: `data/SOURCES.md`)
- [ ] 1.3 Thông tư 08/2021 (khung của Bộ): để sau; Quy chế 2022 của trường đã cụ thể hóa thông tư này
- [x] 1.4 Quy chế 2022 (K67+), quy định đồ án, thực tập, đánh giá theo chuẩn đầu ra (2026)
- [ ] 1.4b Quy định chuẩn ngoại ngữ K69/K70 (bản scan, cần OCR và soát tay), quy chế đặc thù bậc 7
- [x] 1.5 Trích text từ PDF, phát hiện bản scan, kiểm tra dấu tiếng Việt

**Cổng:** mọi văn bản trong registry đều hợp lệ, khớp sha256 và trích được text sạch. Đạt với 5 văn bản; quy định ngoại ngữ còn ở 1.4b.

## Phase 2 — Parser Điều/Khoản/Điểm (tuần 2)

- [x] 2.1 Model dữ liệu chunk theo schema của kế hoạch
- [x] 2.2 Parser Chương/Điều/Khoản/Điểm, giữ nguyên bảng
- [x] 2.3 Quy tắc chunk: một Điều một chunk, Điều dài tách theo Khoản, lặp tên Điều
- [x] 2.4 Unit test parser + kiểm tra tính liên tục của số Điều
- [x] 2.5 Xuất `data/processed/*.json`

**Cổng:** JSON đầy đủ, không mất Điều nào, test parser pass. Đã đạt: 5 văn bản, 167 Điều, 497 chunk, 39 test.

## Phase 3 — Bộ test đầu tiên và baseline (tuần 3)

- [x] 3.1 Định dạng `eval/testset.jsonl` + validator (căn cứ phải tồn tại trong kho văn bản)
- [x] 3.2 50 câu test đầu tiên
- [x] 3.3 Chỉ số Recall@5, MRR đo bằng code
- [x] 3.4 Baseline: chunk theo token, chỉ vector
- [x] 3.5 `make eval`: bảng theo từng loại câu, lưu kết quả mỗi lần chạy

**Cổng:** có số liệu baseline lưu trong `eval/results/`. Đã đạt (2026-11-07):

| loại | n | recall@5 | hit@5 | MRR | sai phiên bản@5 |
|---|---|---|---|---|---|
| tra_cuu | 12 | 0,917 | 0,917 | 0,787 | 0,383 |
| dien_dat_sv | 11 | 0,591 | 0,636 | 0,436 | 0,436 |
| ket_hop | 8 | 0,500 | 0,750 | 0,546 | 0,450 |
| tinh_toan | 8 | 0,792 | 1,000 | 0,698 | 0,450 |
| phien_ban | 6 | 1,000 | 1,000 | 0,708 | 0,500 |
| **tất cả** | 45 | **0,752** | 0,844 | **0,632** | **0,436** |

Baseline: cửa sổ 200 từ (chồng 50), bge-m3, chỉ vector, không lọc khóa; 383 đoạn.
Câu ngoài phạm vi (5) không tính ở tầng truy xuất. Bộ test 50 câu do nhóm tự viết, nên chỉ số
có thể lạc quan hơn câu hỏi thật của sinh viên.

## Phase 4 — Truy xuất nâng cao (tuần 4)

- [x] 4.1 Chunk theo cấu trúc
- [x] 4.2 BM25 + hybrid search (RRF)
- [x] 4.3 Từ điển đồng nghĩa ngôn ngữ sinh viên
- [x] 4.4 Reranker cross-encoder
- [x] 4.5 Lọc theo khóa trước khi tìm
- [x] 4.6 Cờ cấu hình bật/tắt từng bước, bảng ablation retrieval

**Cổng:** Recall@5 từng bước so với baseline. Đã đạt (2026-11-07), 45 câu có căn cứ:

| cấu hình (cộng dồn) | recall@5 | hit@5 | MRR | sai phiên bản@5 |
|---|---|---|---|---|
| baseline (cửa sổ 200 từ, chỉ vector) | 0,752 | 0,844 | 0,632 | 0,436 |
| + chunk theo cấu trúc | 0,800 | 0,911 | 0,651 | 0,409 |
| + hybrid BM25 (RRF) | 0,767 | 0,867 | 0,665 | 0,436 |
| + từ điển đồng nghĩa | 0,874 | 0,956 | 0,711 | 0,431 |
| + reranker bge-reranker-v2-m3 | 0,878 | 0,956 | 0,809 | 0,409 |
| + lọc theo khóa | **0,937** | **0,978** | **0,926** | **0,000** |
| *đối chứng: bỏ reranker, giữ lọc khóa* | 0,937 | 0,978 | 0,874 | 0,000 |

Nhận xét:
- Lọc theo khóa là bước đóng góp lớn nhất: loại hết kết quả sai phiên bản (44% → 0%) và tăng MRR.
- Reranker chủ yếu tăng MRR (xếp đúng đoạn lên đầu), không tăng Recall@5. Trên CPU nó tốn khoảng
  20–30 giây mỗi câu, nên cấu hình mặc định của sản phẩm là **không rerank**; bật lại khi có GPU.

Những gì không hiệu quả (giữ để đưa vào README):
- Hybrid BM25 đứng một mình làm Recall@5 giảm (0,800 → 0,767): BM25 kéo lên các đoạn trùng từ
  chung chung ("sinh viên", "học phần"). Chỉ có lợi khi kết hợp từ điển đồng nghĩa.
- Từ điển đồng nghĩa tăng mạnh nhóm câu kiểu sinh viên (0,591 → 1,000), nhưng từ điển được viết
  bởi cùng người viết bộ test, nên con số này có rò rỉ và lạc quan. Cần đo lại trên câu hỏi thật.
- Với 45 câu, chênh lệch dưới khoảng 0,05 tương đương 1–2 câu, chưa đủ để kết luận.

## Phase 5 — Sinh câu trả lời có trích dẫn (tuần 5)

- [x] 5.1 Interface LLM + Gemini (REST, thời gian chờ, thử lại, mô hình dự phòng, LLM giả lập cho test)
- [x] 5.2 Prompt trả lời có trích dẫn
- [x] 5.3 Hậu kiểm trích dẫn bằng code
- [x] 5.4 Từ chối: ngưỡng liên quan + quy tắc; hỏi lại khi thiếu khóa
- [x] 5.5 Cache lời gọi LLM, log độ trễ và chi phí

**Cổng:** có tỷ lệ trích dẫn đúng, từ chối đúng, từ chối nhầm. Đã đạt (2026-11-07),
truy xuất `khong_rerank+loc_khoa`, top-6 đoạn, mô hình `gemini-3.5-flash-lite`:

| chỉ số | giá trị |
|---|---|
| Trích dẫn đúng (mọi trích dẫn đúng căn cứ, chạm ít nhất một căn cứ) | 0,956 (43/45) |
| Độ chính xác / độ phủ trích dẫn | 0,967 / 0,878 |
| Từ chối đúng (câu ngoài phạm vi) | 5/5 |
| Từ chối nhầm (câu có căn cứ) | 1/45 |
| Hậu kiểm đánh dấu không chắc chắn | 0/45 |
| Độ trễ LLM p50 / p95 | 4,1 s / 6,1 s |
| Token mỗi câu | khoảng 1.770 |

Hai câu sai (q028, q029, đều loại kết hợp nhiều Điều) là lỗi truy xuất: đoạn chứa căn cứ không
nằm trong top-6, và LLM đã đúng khi nói văn bản được cung cấp không quy định. Hướng sửa: tách câu
hỏi ghép thành nhiều truy vấn con.

Bài học (đưa vào "Những gì không hiệu quả"):
- Cổng liên quan bằng cosine không tách được câu ngoài phạm vi: câu hợp lệ thấp nhất 0,544, câu
  ngoài phạm vi cao nhất 0,610 ("lịch thi", "học phí" có nhắc trong quy chế). Ngưỡng đặt 0,50 chỉ
  chặn câu lạc đề; việc từ chối chính do LLM theo quy tắc trong prompt, và đạt 5/5.
- `gemini-3.6-flash` gói miễn phí chỉ 20 lượt/ngày: lần chạy đầu 30/50 câu rơi sang mô hình dự
  phòng, kết quả trộn hai mô hình nên phải bỏ. Đã sửa: nhận diện lỗi hết hạn mức theo ngày, cache
  chỉ lưu câu do đúng mô hình được yêu cầu sinh ra, eval có `--no-fallback`.
- Bộ test thiếu căn cứ: q013, q016 có căn cứ hợp lệ ở Điều 16 Khoản 20 quy định đánh giá theo chuẩn
  đầu ra (dự tối thiểu 80% thời lượng; vắng thi nhận điểm 0). Phát hiện nhờ câu trả lời của hệ thống,
  đã đối chiếu văn bản rồi bổ sung vào bộ test.

## Phase 6 — Báo cáo đánh giá đầy đủ (tuần 6)

- [x] 6.1 Công cụ tính GPA/xếp loại từ bảng có cấu trúc (2026-11-07, nhánh `feat/phase-6-gpa-tool`)

  Ngưỡng của hai phiên bản quy chế nằm trong `data/rules/hoc-vu.yaml`, mỗi ngưỡng ghi căn cứ
  Điều/Khoản; LLM gọi công cụ qua function calling, khóa của người hỏi ghi đè tham số khóa.

  | 50 câu, gemini-3.5-flash-lite | tính toán đúng (8 câu) | trích dẫn đúng | từ chối nhầm | câu gọi công cụ |
  |---|---|---|---|---|
  | không công cụ | 0,875 | **0,956** | 1/45 | 0 |
  | công cụ cho mọi câu | 1,000 | 0,911 | 2/45 | 9 |
  | **auto: chỉ câu có số liệu** (mặc định) | **1,000** | 0,933 | **1/45** | 8 |

  - Không có công cụ, LLM tính sai điểm trung bình học kỳ (q034): áp công thức lên điểm thang 10
    thay vì quy đổi điểm chữ rồi sang thang 4. Có công cụ: 2,50, đúng.
  - Bật công cụ cho mọi câu gấp đôi token (khoảng 1.770 lên 3.550 mỗi câu) và khiến mô hình gọi
    công cụ cả cho câu không cần tính (q017), nên mặc định chỉ bật khi câu hỏi có con số.
  - Eval phát hiện công cụ xếp hạng tốt nghiệp quên trích Điều 10 khoản 4 (ngưỡng thực sự dùng)
    và trích thừa điều kiện tốt nghiệp; đã sửa theo nguyên tắc chỉ trích căn cứ quyết định kết quả.
  - Cache câu trả lời có công cụ gồm dấu vân tay của file quy tắc và code công cụ, để không dùng
    lại kết quả công cụ cũ.
  - Câu sai còn lại ở nhóm tính toán (q038): mô hình tự gọi thêm công cụ quy đổi điểm, kéo theo
    một căn cứ ngoài bộ test.
- [!] 6.2 Mở rộng bộ test lên 150–200 câu, ưu tiên câu thật của sinh viên (đang làm: 72 câu)

  Đợt 1 (2026-11-08): 19 câu thật từ group công khai "Sinh viên Đại học Xây Dựng Hà Nội (HUCE)",
  tìm theo 13 từ khóa học vụ, viết lại ẩn danh (không lưu tên, hồ sơ, bài gốc), `nguon: thuc_te`.
  Bài gốc không nêu khóa nên giả định K68 (ghi trong `ghi_chu`).

  | gemini-3.5-flash-lite, công cụ auto | câu tự viết (53) | câu thật (19) |
  |---|---|---|
  | độ đúng nội dung (giám khảo) | 0,917 | **0,500** |
  | trích dẫn đúng | 0,938 | **0,286** |
  | từ chối nhầm câu có căn cứ | 1/48 | **7/14** |
  | từ chối đúng câu ngoài phạm vi | 5/5 | 4/5 |

  Câu tự viết đánh giá quá cao hệ thống. Trong 7 câu thật bị từ chối nhầm: 4 câu căn cứ đã nằm
  trong 6 đoạn đưa cho LLM (q056, q060, q069, q071; q060 ở hạng 1) nhưng LLM nói "không quy định"
  vì sinh viên hỏi một tình huống cụ thể còn quy chế chỉ có quy định chung; 3 câu là lỗi truy xuất
  (q062, q063, q064; căn cứ của q063 không có trong top-20).
- [x] 6.3 LLM-as-judge (2026-11-07, nhánh `feat/phase-6-llm-judge`)

  Giám khảo `gemini-3.5-flash-lite` so câu trả lời với đáp án chuẩn, chỉ chấm nội dung, viết lý
  do trước khi kết luận. Cấu hình: truy xuất `khong_rerank+loc_khoa`, công cụ chế độ auto.

  | loại | n | độ đúng nội dung | trích dẫn đúng |
  |---|---|---|---|
  | tra_cuu | 12 | 0,833 | 1,000 |
  | dien_dat_sv | 11 | 0,909 | 1,000 |
  | ket_hop | 8 | 0,750 | 0,750 |
  | tinh_toan | 8 | 1,000 | 0,875 |
  | phien_ban | 6 | 1,000 | 1,000 |
  | **tất cả** | 45 | **0,889** | 0,933 |

  Phân bố: 36 đúng, 8 đúng một phần, 1 sai (q028, lỗi truy xuất đã biết). Độ đúng tính đúng = 1,
  đúng một phần = 0,5, sai = 0.

  - Trích dẫn đúng không bảo đảm đủ ý: câu trả lời hay bỏ điều kiện đi kèm, ví dụ q006 nêu giới
    hạn 25% tín chỉ học trường khác nhưng bỏ điều kiện Hiệu trưởng hai trường phải đồng ý.
    Hướng sửa: yêu cầu nêu đủ điều kiện và ngoại lệ trong prompt, đo lại bằng giám khảo.
  - Giám khảo chưa nhất quán: q012, q021 tự ghi "không ảnh hưởng kết luận chính" nhưng vẫn chấm
    đúng một phần. Chưa sửa tiêu chí trước khi có kết quả chấm tay, để không tối ưu giám khảo
    theo cảm nhận.
- [!] 6.4 Chấm tay 20%, báo cáo độ khớp với judge: bảng chấm mù 9 câu ở
  `eval/human/cham-tay.csv` (lấy mẫu phân tầng, seed 2026). Chủ dự án điền cột `nguoi_cham`
  (dung / dung_mot_phan / sai), rồi chạy `eval/judge_agreement.py` để có tỷ lệ trùng và kappa.
- [x] 6.4b Sửa lỗi do chấm tay phát hiện: văn bản mới sửa quy tắc của văn bản cũ cho mọi khóa
  (2026-11-08, nhánh `fix/assessment-weights-2026`)

  Registry ghi quan hệ sửa đổi (`sua_doi`): quy định đánh giá theo chuẩn đầu ra 2026 thay trọng
  số điểm thành phần của quy chế 2022 (Điều 9 khoản 1) và quy chế 2016 (Điều 19 khoản 1) bằng
  25/25/50 (Điều 5 khoản 2, Điều 6 khoản 3, Điều 6 khoản 4). Đoạn bị sửa mang `sua_doi_boi`,
  khi được truy xuất thì đoạn sửa đổi được kéo kèm vào ngữ cảnh, và câu trả lời trích đoạn sửa
  đổi thay vì đoạn đã bị thay thế. Công cụ tính điểm học phần dùng 25/25/50 cho mọi khóa và cảnh
  báo khi trọng số đưa vào khác. Theo sinh viên K68, cách tính này đã áp dụng từ ít nhất 2023;
  văn bản trước 2026 ghi con số này chưa tìm thấy.

  | 53 câu, gemini-3.5-flash-lite, công cụ auto | trước | sau |
  |---|---|---|
  | độ đúng nội dung (giám khảo) | 0,889 (45 câu) | **0,917** (48 câu) |
  | trích dẫn đúng | 0,933 | **0,938** |
  | tính toán đúng | 8/8 | 8/8 (q038 viết lại theo 25/25/50) |
  | câu văn bản sửa đổi (q051-q053) | chưa có | 3/3, kể cả K65 |
  | từ chối đúng / nhầm | 5/5, 1/45 | 5/5, 1/48 |

  Tiêu chí giám khảo đổi trong cùng nhánh (chỉ trừ điểm khi thiếu ý làm thay đổi kết quả), nên
  một phần mức tăng độ đúng nội dung đến từ tiêu chí chứ không từ hệ thống. Độ khớp với người chấm
  chưa đo lại với tiêu chí mới: 9 câu đã chấm thuộc lần chạy cũ, và tiêu chí được chỉnh sau khi
  xem chính 9 câu đó, nên đo lại trên chúng sẽ lạc quan; cần một mẫu chấm tay mới.

  Lỗi hạ tầng gặp khi chạy: bên trả lời và giám khảo giãn cách lời gọi riêng nên cùng nhau vượt
  hạn mức theo phút của gói miễn phí; nay giãn cách dùng chung theo mô hình, chờ đúng retryDelay,
  và một câu lỗi không còn dừng cả lần chạy.
- [ ] 6.5 Báo cáo đánh giá

**Cổng:** báo cáo đủ các tầng chỉ số, có độ khớp judge và người.

## Phase 7 — Sản phẩm và công bố (tuần 7)

- [ ] 7.1 FastAPI: hỏi đáp + feedback
- [ ] 7.2 Giao diện demo
- [ ] 7.3 Docker Compose chạy trọn bộ
- [ ] 7.4 README: sơ đồ, ablation, hạn chế, "Những gì không hiệu quả"
- [!] 7.5 Deploy, video demo, công khai repo (cần chủ dự án quyết định)

**Cổng:** `docker compose up` chạy trên máy sạch, số liệu tái lập khớp README.

Nếu trễ: cắt giao diện và công cụ tính toán trước; không cắt bộ test và báo cáo đánh giá.
