# Báo cáo đánh giá

Hệ thống hỏi đáp quy chế đào tạo Trường Đại học Xây dựng Hà Nội (HUCE), cập nhật 2026-11-08.
Mọi con số dưới đây lấy từ các file trong `eval/results/` và tái lập được bằng lệnh ở cuối báo cáo.

## Tóm tắt

| | câu tự viết (53) | câu thật, đợt 1 (19) | **câu thật, tập độc lập (19)** |
|---|---|---|---|
| độ đúng nội dung (giám khảo LLM) | 0,948 | 0,571 | **0,40** |
| trích dẫn đúng | 0,896 | 0,429 | **0,30** |
| từ chối nhầm câu có căn cứ | 1/48 | 5/14 | **4/10** |
| từ chối đúng câu ngoài phạm vi | 5/5 | 5/5 | **9/9** |

- **Làm tốt:** từ chối câu ngoài quy chế (14/14 câu thật), tính toán bằng công cụ (9/9 câu tính
  toán đúng), chọn đúng phiên bản quy chế theo khóa (0% kết quả sai phiên bản trong top-5), và áp
  dụng văn bản sửa đổi cho mọi khóa (3/3).
- **Làm chưa tốt:** câu hỏi thật của sinh viên. Trên tập độc lập, hệ thống chỉ trả lời đúng khoảng
  4/10 câu có căn cứ. Nguyên nhân chính là truy xuất (Recall@5 câu thật 0,48 so với 0,90 câu tự
  viết) và từ chối nhầm khi sinh viên hỏi một tình huống cụ thể mà quy chế chỉ có quy định chung.
- **Con số để trích dẫn** là cột tập độc lập: tập này được commit trước khi chạy hệ thống
  (`f41ca51`) và không dùng để sửa hệ thống.

## Hệ thống được đánh giá

| thành phần | cấu hình |
|---|---|
| kho văn bản | 5 văn bản, 167 Điều, 521 đoạn: quy chế 2022 (K67 trở đi), quy chế 2016 (K66 trở về trước), quy định đồ án, thực tập, đánh giá theo chuẩn đầu ra (2026) |
| chia đoạn | theo Điều; Điều dài tách theo Khoản, Khoản dài tách theo Điểm |
| truy xuất | bge-m3 (vector) + BM25 có cặp âm tiết, gộp RRF; từ điển ngôn ngữ sinh viên; lọc theo khóa trước khi tìm; không rerank (cấu hình `khong_rerank+loc_khoa`) |
| sinh câu trả lời | `gemini-3.5-flash-lite`, 6 đoạn, trích dẫn theo số thứ tự đoạn, hậu kiểm bằng code |
| văn bản sửa đổi | đoạn bị sửa kéo kèm đoạn sửa đổi; trích đoạn sửa đổi thay đoạn đã bị thay thế |
| tính toán | công cụ học vụ (GPA, xếp loại, hạng tốt nghiệp, năm học, cảnh báo, điểm học phần) qua function calling, chỉ bật khi câu hỏi có con số |

## Bộ test

| tập | số câu | nguồn | dùng để |
|---|---|---|---|
| `testset.jsonl`, câu tự viết | 53 | tác giả viết theo văn bản | phát triển |
| `testset.jsonl`, câu thật đợt 1 | 19 | group sinh viên HUCE, 13 từ khóa | phát triển (đã dùng để sửa quy tắc từ chối) |
| `testset_holdout.jsonl` | 19 | group sinh viên và group tuyển sinh HUCE, từ khóa khác | **chỉ kiểm tra** |

Sáu loại câu theo kế hoạch: tra cứu trực tiếp, diễn đạt kiểu sinh viên, kết hợp nhiều Điều, tính
toán, phụ thuộc phiên bản, ngoài phạm vi. Câu thật được viết lại ẩn danh (không tên, không trích
nguyên văn bài đăng); bài gốc không nêu khóa thì giả định và ghi trong `ghi_chu`. Validator kiểm tra
mọi căn cứ có thật trong kho và thuộc phiên bản áp dụng cho khóa của người hỏi.

## Chỉ số

| tầng | chỉ số | cách đo |
|---|---|---|
| truy xuất | Recall@5, Hit@5, MRR | căn cứ chuẩn có trong top-5, đo bằng code |
| truy xuất | sai phiên bản@5 | tỷ lệ đoạn trong top-5 thuộc văn bản không áp dụng cho khóa người hỏi |
| trích dẫn | trích dẫn đúng | có trích dẫn, mọi trích dẫn đúng căn cứ, chạm ít nhất một căn cứ |
| từ chối | từ chối đúng / nhầm | so với nhãn `nen_tu_choi` |
| nội dung | độ đúng nội dung | giám khảo LLM: đúng 1, đúng một phần 0,5, sai 0; câu có căn cứ mà bị từ chối tính sai |
| tính toán | đáp án ngắn | câu trả lời phải chứa kết quả đúng và không chứa phủ định của nó, đo bằng code |
| vận hành | độ trễ, token | log của từng lần chạy |

## Kết quả truy xuất

Ablation cộng dồn trên 45 câu tự viết có căn cứ (`eval/results/20261107-210539-ablation.md`):

| cấu hình | Recall@5 | MRR | sai phiên bản@5 |
|---|---|---|---|
| baseline: cửa sổ 200 từ, chỉ vector | 0,752 | 0,632 | 0,436 |
| + chunk theo cấu trúc | 0,800 | 0,651 | 0,409 |
| + hybrid BM25 | 0,767 | 0,665 | 0,436 |
| + từ điển đồng nghĩa | 0,874 | 0,711 | 0,431 |
| + reranker | 0,878 | 0,809 | 0,409 |
| + lọc theo khóa | **0,937** | **0,926** | **0,000** |

Cấu hình đang dùng (bỏ reranker vì 20-30 giây mỗi câu trên CPU), theo nguồn câu hỏi
(`eval/results/20261108-112102-khong_rerank+loc_khoa.json`):

| | Recall@5 | Hit@5 | MRR |
|---|---|---|---|
| câu tự viết (48) | 0,901 | 0,958 | 0,837 |
| câu thật (14) | **0,482** | 0,643 | 0,497 |

## Kết quả trả lời

Bộ phát triển, 72 câu (`eval/results/20261108-103732-generation-gemini-3.5-flash-lite-tools.json`):

| loại | n | độ đúng nội dung | trích dẫn đúng | từ chối nhầm |
|---|---|---|---|---|
| tra cứu | 12 | 0,958 | 1,000 | 0 |
| diễn đạt kiểu sinh viên | 18 | 0,833 | 0,778 | 3 |
| kết hợp nhiều Điều | 14 | 0,643 | 0,500 | 3 |
| tính toán | 9 | 1,000 | 1,000 | 0 |
| phụ thuộc phiên bản | 9 | 1,000 | 0,778 | 0 |
| **tất cả** | 62 có căn cứ, 10 ngoài phạm vi | **0,863** | 0,790 | 6/62 |

Độ trễ LLM p50 4,4 giây, p95 8,5 giây; khoảng 2.640 token mỗi câu; 8 câu dùng công cụ tính toán.

Tập độc lập, 19 câu (`eval/results/20261108-110612-generation-gemini-3.5-flash-lite-tools-testset_holdout.json`):
độ đúng nội dung 0,40, trích dẫn đúng 0,30, từ chối nhầm 4/10, từ chối đúng 9/9; p50 3,8 giây.

## Độ tin cậy của giám khảo

| vòng | mẫu | trùng chấm mù | sau phân xử |
|---|---|---|---|
| 1 | 9 câu tự viết, lấy mẫu phân tầng | 7/9; kappa -0,06 | không phân xử |
| 2 | 15 câu thật hệ thống đã trả lời | 11/15; kappa 0 | 15/15 |

Kappa gần 0 vì người chấm chọn "đúng" gần như mọi câu, không phải vì giám khảo ngẫu nhiên. Ở vòng
2, cả 4 câu bất đồng đều được người chấm xác nhận theo giám khảo khi xem kỹ; con số sau phân xử không
độc lập vì người chấm đã thấy lý do của giám khảo. Vòng 1 phát hiện một lỗi mà cả hệ thống, đáp án
chuẩn và giám khảo đều bỏ qua: trọng số điểm 25/25/50 của quy định 2026. Kết luận: giám khảo không
khắt khe quá mức trên câu thật, nhưng chỉ đáng tin bằng đáp án chuẩn mà nó so sánh.

## Phân tích lỗi trên câu thật

| loại lỗi | ví dụ | nguyên nhân |
|---|---|---|
| từ chối dù căn cứ có trong ngữ cảnh | "bảo lưu để ôn thi lại THPT" (căn cứ đứng hạng 1), "nợ môn có nhận đồ án được không" | sinh viên hỏi tình huống cụ thể, quy chế chỉ có quy định chung |
| truy xuất trượt | "điều kiện đi thực tập và nhận đồ án" (căn cứ ngoài top-20) | BM25 ưu tiên đoạn lặp nhiều từ chung; câu then chốt nằm cuối một đoạn dài |
| hiểu sai câu hỏi | "hết năm nhất muốn chuyển ngành" trả lời như "đang năm nhất" | lỗi đọc hiểu của mô hình |
| né câu trả lời trực tiếp | "phúc khảo điểm thấp hơn có phải lấy không" | mô hình ưu tiên nói "không quy định cụ thể" |

## Những gì không hiệu quả

- **Hybrid BM25 một mình** làm Recall@5 giảm (0,800 xuống 0,767); chỉ có lợi khi đi cùng từ điển.
- **Reranker** chỉ tăng MRR, không tăng Recall@5, và tốn 20-30 giây mỗi câu trên CPU.
- **Từ điển đồng nghĩa** tăng mạnh nhóm câu kiểu sinh viên trên câu tự viết (0,59 lên 1,00), nhưng
  cùng người viết từ điển và bộ test nên có rò rỉ; trên câu thật Recall@5 chỉ 0,48.
- **Cổng liên quan bằng cosine** không tách được câu ngoài phạm vi (câu hợp lệ thấp nhất 0,544,
  câu ngoài phạm vi cao nhất 0,610); việc từ chối do LLM quyết định.
- **Bật công cụ cho mọi câu** gấp đôi token và làm mô hình gọi công cụ cả khi không cần tính.
- **Tách câu hỏi ghép thành truy vấn con**: Recall@5 câu thật tăng khoảng nửa câu, câu tự viết giảm.
- **Sửa quy tắc từ chối** giúp trên chính các câu dùng để sửa (từ chối nhầm 7/14 xuống 5/14) nhưng
  không tổng quát hóa: trên tập độc lập vẫn từ chối nhầm 4/10.
- **`gemini-3.6-flash`** chỉ 20 lượt/ngày ở gói miễn phí, không dùng được cho eval.

## Hạn chế đã biết

- Tập độc lập nhỏ (10 câu có căn cứ): chênh lệch một câu là 0,10.
- Mô hình không cho đặt `temperature`; câu trả lời được cache để tái lập, nhưng chạy lại không có
  cache có thể lệch 1-2 câu.
- Câu thật không nêu khóa nên giả định K68 hoặc K71; trên thực tế hệ thống sẽ phải hỏi lại khóa.
- Kho chưa có: quy định chuẩn ngoại ngữ theo khóa (bản scan K69, K70), 11 Phụ lục quy trình của
  quy chế 2022, Thông tư 08/2021. Trọng số 25/25/50 áp dụng từ ít nhất 2023 theo sinh viên, nhưng văn
  bản trước 2026 ghi con số này chưa tìm thấy.
- Giám khảo dùng cùng họ mô hình với bên trả lời; độ khớp với người mới đo trên 24 câu.

## Tái lập

```bash
uv sync --group ml
uv run pytest                                                     # 117 test, không cần mạng
uv run --group ml python eval/run_eval.py --ablation              # bảng ablation truy xuất
uv run --group ml python eval/run_generation.py --no-fallback --tools --judge
uv run --group ml python eval/run_generation.py --no-fallback --tools --judge \
    --testset testset_holdout.jsonl
```

Hai lệnh cuối cần `GEMINI_API_KEY` trong `.env`. Câu trả lời đã cache trong `.cache/llm` nên chạy
lại trên cùng máy không gọi mạng; trên máy khác kết quả có thể lệch nhẹ vì mô hình không cố định.
