"""Các cấu hình truy xuất có tên. API và eval dùng chung, nên số liệu trong báo cáo đúng là của
cấu hình đang chạy."""

from dataclasses import replace

from retrieval.pipeline import RetrievalConfig

# Thứ tự cộng dồn của bảng ablation: mỗi dòng bật thêm một bước so với dòng trên.
BASELINE = RetrievalConfig("baseline", chunking="window")
STRUCTURE = replace(BASELINE, name="+chunk_cau_truc", chunking="structure")
HYBRID = replace(STRUCTURE, name="+hybrid_bm25", hybrid=True)
SYNONYMS = replace(HYBRID, name="+tu_dong_nghia", synonyms=True)
RERANK = replace(SYNONYMS, name="+rerank", rerank=True)
KHOA = replace(RERANK, name="+loc_khoa", khoa_filter=True)
ABLATION = [BASELINE, STRUCTURE, HYBRID, SYNONYMS, RERANK, KHOA]

# Cấu hình chạy thật: bỏ reranker vì tốn 20-30 giây mỗi câu trên CPU mà không tăng Recall@5.
PRODUCTION = replace(SYNONYMS, name="khong_rerank+loc_khoa", khoa_filter=True)
EXTRA = [PRODUCTION]
