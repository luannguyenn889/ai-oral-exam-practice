"""Bộ chỉ số đánh giá chất lượng truy xuất RAG (Recall@K, MRR@K, Noise Rate@K).

Nhiệm vụ:
- Chuẩn hóa phép đo chất lượng truy xuất trên tập câu hỏi mẫu có từ khóa kỳ vọng hoặc nhãn nhiễu.
- Hỗ trợ so sánh giữa các cấu hình embedding (`local` vs `e5-small` vs `gemini`), chế độ tìm kiếm (`dense`, `bm25`, `hybrid`) và reranker (`minilm` vs `bge-m3`).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from app.services.rag.noise_filter import compute_noise_profile


def compute_recall_at_k(retrieved_texts: list[str], expected_terms: list[str], k: int) -> float:
    """Recall@K = 1.0 nếu ít nhất 1 đoạn trong Top-K chứa toàn bộ/đa số từ khóa kỳ vọng, ngược lại 0.0."""
    if not expected_terms or not retrieved_texts or k <= 0:
        return 0.0
    lowered_terms = [t.strip().lower() for t in expected_terms if t and t.strip()]
    if not lowered_terms:
        return 0.0
    for text in retrieved_texts[:k]:
        low = text.lower()
        hits = sum(1 for term in lowered_terms if term in low)
        if hits >= max(1, (len(lowered_terms) + 1) // 2):
            return 1.0
    return 0.0


def compute_reciprocal_rank(retrieved_texts: list[str], expected_terms: list[str], k: int) -> float:
    """MRR@K: nghịch đảo thứ hạng của đoạn phù hợp đầu tiên trong Top-K."""
    if not expected_terms or not retrieved_texts or k <= 0:
        return 0.0
    lowered_terms = [t.strip().lower() for t in expected_terms if t and t.strip()]
    for rank, text in enumerate(retrieved_texts[:k], 1):
        low = text.lower()
        hits = sum(1 for term in lowered_terms if term in low)
        if hits >= max(1, (len(lowered_terms) + 1) // 2):
            return round(1.0 / rank, 4)
    return 0.0


def compute_noise_rate_at_k(retrieved_chunks: list[dict[str, Any]], k: int) -> float:
    """Tỷ lệ chunk bị nhận diện là rác học thuật (Index/References/TOC/Front-matter) trong Top-K."""
    window = retrieved_chunks[:k]
    if not window:
        return 0.0
    noisy = 0
    for chunk in window:
        n_score = chunk.get("noise_score")
        if n_score is None:
            prof = compute_noise_profile(
                str(chunk.get("text", "")),
                str(chunk.get("section_title", "")),
            )
            is_noisy = bool(prof.get("is_noise"))
        else:
            is_noisy = float(n_score) >= 0.70
        if is_noisy:
            noisy += 1
    return round(noisy / len(window), 4)


def evaluate_retrieval_benchmark(
    cases: list[dict[str, Any]],
    retriever: Callable[[str], list[dict[str, Any]]],
    k: int = 3,
    off_topic_queries: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Chạy đánh giá hàng loạt và trả về Recall@K, MRR@K, Noise Rate@K cùng tỷ lệ từ chối câu hỏi ngoài lề."""
    recalls: list[float] = []
    mrrs: list[float] = []
    noise_rates: list[float] = []

    for case in cases:
        query = str(case.get("query", "")).strip()
        expected = list(case.get("expected_terms") or [])
        if not query or not expected:
            continue
        chunks = retriever(query)
        texts = [str(c.get("text", "")) for c in chunks]
        recalls.append(compute_recall_at_k(texts, expected, k=k))
        mrrs.append(compute_reciprocal_rank(texts, expected, k=k))
        noise_rates.append(compute_noise_rate_at_k(chunks, k=k))

    off_topic_total = len(off_topic_queries or [])
    off_topic_rejected = 0
    for q in off_topic_queries or []:
        if len(retriever(q)) == 0:
            off_topic_rejected += 1

    count = max(1, len(recalls))
    return {
        "total_cases": len(recalls),
        "k": k,
        "recall_at_k": round(sum(recalls) / count, 4) if recalls else 0.0,
        "mrr_at_k": round(sum(mrrs) / count, 4) if mrrs else 0.0,
        "noise_rate_at_k": round(sum(noise_rates) / count, 4) if noise_rates else 0.0,
        "off_topic_rejection_rate": (
            round(off_topic_rejected / off_topic_total, 4) if off_topic_total else None
        ),
    }
