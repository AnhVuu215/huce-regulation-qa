# Lộ trình triển khai theo phase

Tách từ [kế hoạch dự án](PROJECT_PLAN.md). Mỗi phase có các plan nhỏ
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
- Tách câu hỏi ghép thành truy vấn con (2026-11-08, cờ `decompose`, mặc định tắt): Recall@5 câu
  thật 0,482 → 0,518 (khoảng nửa câu trên 14), câu tự viết 0,901 → 0,890, nhóm kết hợp nhiều Điều
  không đổi. Không đủ để bật. Lỗi truy xuất thật (q063) đến từ BM25 ưu tiên đoạn lặp nhiều từ
  "thực tập", "tốt nghiệp" (Điều 5 quy định đồ án: hạng 13 theo vector, 82 theo BM25), và câu then
  chốt của Điều 7 quy chế 2022 chỉ là một dòng cuối trong đoạn dài nên bị loãng.

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

  Sửa quy tắc từ chối (nhánh `fix/over-refusal`): chỉ từ chối khi không đoạn nào liên quan; tình
  huống cụ thể thì trả lời theo quy định chung và nói rõ phần quy chế không quy định.

  | | câu thật: trước → sau | câu tự viết: trước → sau |
  |---|---|---|
  | từ chối nhầm câu có căn cứ | 7/14 → 5/14 | 1/48 → 1/48 |
  | độ đúng nội dung | 0,500 → 0,571 | 0,917 → 0,948 |
  | trích dẫn đúng | 0,286 → 0,429 | 0,938 → 0,896 |
  | từ chối đúng câu ngoài phạm vi | 4/5 → 5/5 | 5/5 → 5/5 |

  Không đổi lấy việc trả lời bừa câu ngoài phạm vi. Ba câu vẫn bị từ chối dù căn cứ có trong ngữ
  cảnh (q056, q069, q071); dừng chỉnh prompt vì chênh 1-2 câu trên 14 nằm trong nhiễu của mô hình
  không cố định được temperature. Sửa này dựa trên chính 19 câu thật nên chúng không còn là tập
  kiểm tra độc lập: cần một đợt câu thật mới chỉ để kiểm tra.

  Tập kiểm tra độc lập (đợt 2, `eval/testset_holdout.jsonl`, commit trước khi chạy hệ thống):
  19 câu thật từ group sinh viên và group tuyển sinh HUCE, thu bằng từ khóa khác đợt 1. Không dùng
  để sửa hệ thống. Kết quả với cấu hình hiện tại (đã sửa quy tắc từ chối):

  | 19 câu (10 có căn cứ, 9 ngoài phạm vi) | kết quả |
  |---|---|
  | từ chối đúng câu ngoài phạm vi | **9/9** |
  | từ chối nhầm câu có căn cứ | 4/10 |
  | độ đúng nội dung (giám khảo) | **0,40** |
  | trích dẫn đúng | 0,30 |

  Đây là con số đại diện nhất cho câu hỏi thật: từ chối ngoài phạm vi tốt, nhưng mới trả lời đúng
  khoảng 4/10 câu có căn cứ. Lỗi lặp lại hai loại của đợt 1, nên sửa quy tắc từ chối chưa tổng
  quát hóa: vẫn từ chối nhầm (h007-h010, nhất là "nợ môn có đi thực tập, nhận đồ án được không"),
  và giám khảo chấm h005 là sai; chấm tay vòng 2 bên dưới xác nhận giám khảo đúng ở câu này.

  Chấm tay vòng 2 (2026-11-08): toàn bộ 15 câu thật hệ thống đã trả lời (9 câu đợt 1 sau khi sửa
  quy tắc từ chối, 6 câu tập độc lập), chấm mù trên trang bấm nút, rồi phân xử các câu lệch.

  | | trùng với giám khảo |
  |---|---|
  | chấm mù | 11/15 (73%); kappa 0 vì người chấm cả 15 câu là đúng |
  | sau phân xử 4 câu lệch | 15/15 (không độc lập: lúc phân xử đã thấy lý do của giám khảo) |

  Cả 4 câu giám khảo bất đồng với lần chấm mù đều được xác nhận là đúng khi xem kỹ: h005 hiểu sai
  "hết năm nhất" thành "đang năm nhất" và kết luận ngược; h014 né câu trả lời trực tiếp; q062 và
  q072 thiếu ý sinh viên cần (cách học vượt; miễn học theo quy định riêng). Lần chấm mù chấm cả 15
  câu trong khoảng 3 phút nên dễ dãi; vòng 1 (8/9 đúng) có thể cũng vậy. Kết luận: trên câu thật,
  giám khảo không chấm khắt khe quá mức như lo ngại, nên độ đúng 0,40 của tập độc lập là con số thật.
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
- [x] 6.4 Chấm tay 20%, báo cáo độ khớp với judge (2026-11-07)

  Chủ dự án chấm mù 9 câu (lấy mẫu phân tầng, seed 2026) trên trang chấm bằng nút bấm; kết quả ở
  `eval/human/cham-tay.csv`.

  | chỉ số | giá trị |
  |---|---|
  | tỷ lệ trùng giám khảo và người | 0,778 (7/9) |
  | Cohen's kappa | -0,06 |

  Kappa gần 0 vì người chấm 8/9 câu là đúng: nhãn lệch hẳn về một phía nên trùng do ngẫu nhiên đã
  cao, và 9 câu là quá ít để kappa ổn định. Hai câu lệch mới là kết luận chính:
  - q009: người chấm đúng, giám khảo đúng một phần. Giám khảo khắt khe hơn người ở ý phụ, nên
    độ đúng nội dung 0,889 của giám khảo nhiều khả năng thấp hơn thực tế.
  - q038: người chấm sai, giám khảo đúng. Người chấm chỉ ra trọng số điểm hiện hành khác giả định
    của câu hỏi: quy định đánh giá theo chuẩn đầu ra 2026 ấn định thường xuyên 25% (Điều 5 khoản
    2), giữa kỳ 25% (Điều 6 khoản 3), cuối kỳ 50% (Điều 6 khoản 4), còn câu hỏi và công cụ dùng
    trọng số thi 0,6 theo quy chế 2022. Giám khảo không thấy lỗi vì đáp án chuẩn cũng dựa trên
    quy chế 2022. Đây là lỗi thật của hệ thống: văn bản mới sửa quy tắc của văn bản cũ cho mọi
    khóa, loại phiên bản mà hệ thống chưa xử lý.
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
- [x] 6.5 Báo cáo đánh giá: `docs/EVALUATION.md` (2026-11-08)

**Cổng:** báo cáo đủ các tầng chỉ số, có độ khớp judge và người.

## Phase 7 — Sản phẩm và công bố (tuần 7)

- [x] 7.1 FastAPI: `/ask`, `/feedback`, `/documents`, `/health`; log độ trễ, token, đoạn đã lấy
- [x] 7.2 Giao diện demo: một trang HTML do API phục vụ (thay Streamlit), nêu rõ độ chính xác đo được
- [x] 7.3 Docker Compose: một dịch vụ, khởi động 39 giây nhờ embedding dựng sẵn; bỏ PostgreSQL vì không cần
- [x] 7.4 README: sơ đồ, kết quả, ablation, thay đổi so với kế hoạch, hạn chế
- [!] 7.5 Deploy, video demo, công khai repo (cần chủ dự án quyết định; chi tiết ở 8.4)

**Cổng:** `docker compose up` chạy trên máy sạch, số liệu tái lập khớp README.

Nếu trễ: cắt giao diện và công cụ tính toán trước; không cắt bộ test và báo cáo đánh giá.

## Phase 8 — Chất lượng trên câu hỏi thật (lập 2026-11-10)

Điểm yếu lớn nhất hiện nay không nằm ở code mà ở câu hỏi thật: trên tập độc lập, độ đúng nội
dung 0,40 (câu tự viết 0,95), Recall@5 0,48 (câu tự viết 0,90), từ chối nhầm 4/10. Mục tiêu của
phase: nâng các con số này mà không đổi lấy việc trả lời bừa câu ngoài phạm vi (đang 14/14), và
đo trên tập đủ lớn để kết luận được.

Thứ tự: 8.1 và 8.2 làm song song; 8.3 chỉ bắt đầu khi 8.1 xong (cần thước đo trước khi sửa);
8.4 làm lúc nào cũng được, nhưng cập nhật số liệu sau 8.3.

Bắt đầu từ: chủ dự án làm 8.1.1, Claude làm 8.2.

### 8.1 Mở rộng tập câu hỏi thật (chủ dự án thu thập, Claude gắn căn cứ)

Tập độc lập hiện chỉ có 10 câu có căn cứ: lệch một câu là 0,10, nên chưa cải tiến nào đo được.

- [ ] 8.1.1 Thu 60–100 câu thật mới, mục tiêu ít nhất 50 câu có căn cứ và khoảng 15 câu ngoài
  phạm vi. Nguồn: group sinh viên và group tuyển sinh HUCE (dùng từ khóa khác đợt 1 và 2), hỏi
  trực tiếp bạn bè các khóa (ghi khóa thật thay vì giả định K68), `.data/feedback.jsonl` nếu đã có
  người dùng thử. Viết lại ẩn danh như các đợt trước: không lưu tên, hồ sơ, bài gốc.
- [ ] 8.1.2 Gắn căn cứ Điều/Khoản và đáp án chuẩn: Claude soạn, chủ dự án duyệt từng câu;
  `validate` của `evaluation.testset` phải pass.
- [ ] 8.1.3 Chia khoảng 60% vào tập phát triển (`eval/testset.jsonl`, `nguon: thuc_te`) và 40%
  vào tập độc lập mới `eval/testset_holdout_2.jsonl`. Commit tập độc lập **trước** khi chạy hệ
  thống trên nó và ghi hash commit vào đây.
- [ ] 8.1.4 Chạy cấu hình hiện tại trên tập phát triển mới để có số liệu gốc của phase
  (`make eval`, `make answer-eval`).

**Cổng:** ít nhất 30 câu thật có căn cứ trong tập phát triển và 20 trong tập độc lập mới; số liệu
gốc lưu trong `eval/results/`. Tập độc lập mới không dùng để chỉnh hệ thống, chỉ chạy một lần ở
8.3.6.

### 8.2 Chẩn đoán vì sao truy xuất trượt (Claude, làm được ngay trên 14 câu thật hiện có)

Hai cách sửa khác hẳn nhau tùy lỗi nằm ở xếp hạng hay ở cách cắt đoạn, nên phải đo trước.

- [ ] 8.2.1 `eval/diagnose_retrieval.py`: với mỗi câu thật, hạng của từng căn cứ theo vector,
  theo BM25 và sau khi kết hợp (đến top-50); xuất bảng Markdown vào `eval/results/`.
- [ ] 8.2.2 Gán nhãn nguyên nhân cho mỗi câu trượt:
  (a) xếp hạng: căn cứ ở hạng 6–20;
  (b) biểu diễn: ngoài top-20 vì câu then chốt bị loãng trong đoạn dài (như q063);
  (c) từ vựng: sinh viên dùng từ không có trong văn bản ("bảo lưu" so với "nghỉ học tạm thời");
  (d) kho thiếu văn bản (chuẩn ngoại ngữ, Phụ lục, Thông tư 08/2021).
- [ ] 8.2.3 Đường cong Recall@k (k = 5, 6, 10, 20) của câu thật so với câu tự viết.

**Cổng:** mọi câu trượt có nhãn nguyên nhân; nhóm lớn nhất quyết định thử nghiệm nào làm trước ở
8.3.

### 8.3 Thử nghiệm cải tiến (Claude, đo trên tập phát triển của 8.1)

Mỗi thử nghiệm là một cờ cấu hình, mặc định tắt, có một dòng trong bảng ablation. Chỉ bật mặc
định khi: tăng trên câu thật, câu tự viết không giảm quá 1 câu, từ chối đúng câu ngoài phạm vi
không giảm. Ghi cả thử nghiệm không hiệu quả vào `docs/EVALUATION.md`.

- [ ] 8.3.1 Nếu nhóm (a) lớn: tăng số đoạn đưa cho LLM (6 lên 8 và 10), cân trọng số kết hợp
  BM25 và vector. Đo kèm token và độ trễ.
- [ ] 8.3.2 Nếu nhóm (b) lớn: đánh chỉ mục từng Khoản/Điểm, khớp thì trả về cả Điều chứa nó
  (parent retrieval). Phải dựng lại embedding và chạy `scripts/export_embeddings.py`.
- [ ] 8.3.3 Nếu nhóm (c) lớn: dùng LLM viết lại câu hỏi sang ngôn ngữ quy chế (thêm một lời gọi,
  có cache), so với từ điển đồng nghĩa viết tay. Theo dõi hạn mức gói miễn phí.
- [ ] 8.3.4 Từ chối nhầm: thêm 3–4 ví dụ mẫu "tình huống cụ thể → quy định chung áp dụng" vào
  prompt, lấy từ câu tự viết chứ không từ câu thật để tránh rò rỉ. Lần trước thêm quy tắc không
  tổng quát hóa (7/14 → 5/14, tập độc lập vẫn 4/10).
- [ ] 8.3.5 Hiểu sai và né câu trả lời (h005, h014): yêu cầu mở đầu bằng kết luận trực tiếp
  (được/không được, có/không) rồi mới dẫn quy định.
- [ ] 8.3.6 Chạy tập độc lập mới **một lần** với cấu hình cuối; cập nhật `docs/EVALUATION.md` và
  README.
- [ ] 8.3.7 Chấm tay mẫu mới khoảng 20 câu để đo lại độ khớp giám khảo với tiêu chí hiện hành
  (còn nợ từ 6.4b).

**Cổng:** có độ đúng nội dung trên tập độc lập mới, kèm khoảng tin cậy và so sánh với 0,40. Mục
tiêu tham khảo là 0,6 trở lên, nhưng không chỉnh hệ thống theo tập độc lập để đạt số.

### 8.4 Sản phẩm và công bố (tiếp 7.5; chủ dự án quyết định, Claude làm)

- [ ] 8.4.1 Chọn nơi deploy. Ứng viên: Hugging Face Spaces (Docker, gói CPU miễn phí; kiểm tra
  lại RAM và chính sách ngủ khi không dùng ở thời điểm deploy) hoặc VPS. Ràng buộc: bge-m3 cần vài
  GB RAM; `GEMINI_API_KEY` đặt làm secret; giữ `ASK_RATE_LIMIT` vì hạn mức LLM dùng chung.
- [ ] 8.4.2 Deploy, kiểm tra `/health` báo `ready`, ghi link vào README.
- [ ] 8.4.3 Rà soát trước khi công khai repo: không có khóa API hay `.env` trong lịch sử git; câu
  hỏi thật trong `eval/` đã ẩn danh; ghi nguồn và quyền của văn bản quy chế; thêm LICENSE cho code
  (MIT, đã bàn, để sau).
- [ ] 8.4.4 Video demo 1–2 phút: một câu tra cứu, một câu tính GPA, một câu bị hỏi lại khóa, một
  câu ngoài phạm vi bị từ chối; nêu số liệu đo được, kể cả điểm yếu.
- [ ] 8.4.5 README: link demo và video, số liệu mới từ 8.3.

**Cổng:** người lạ mở link hỏi được và nhận câu trả lời có trích dẫn; repo công khai không lộ khóa
hay dữ liệu cá nhân.
