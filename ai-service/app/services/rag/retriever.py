"""Truy vấn Hybrid RAG (Dense + BM25 + RRF + Cross-Encoder Rerank + Lọc liên quan) và định dạng ngữ cảnh."""

from __future__ import annotations

from typing import Any, Optional

from app.config import settings
from app.services.rag.bm25_index import _get_course_stats, get_bm25_index
from app.services.rag.chroma_client import (
    _resolve_store_dep,
    get_chroma_collection,
    get_collection_name,
    list_course_files,
)
from app.services.rag.course_config import (
    resolve_course_embedding_provider,
    resolve_course_reranker_provider,
)
from app.services.rag.embeddings import (
    clean_oral_query,
    embed_texts,
    get_min_dense_similarity,
    get_reranker_model,
    is_rerank_score_relevant,
    normalize_course_id,
    tokenize_text,
)
from app.services.rag.indexer import index_documents
from app.services.rag.noise_filter import compute_noise_profile


def _search_candidates_for_query(
    query_str: str,
    norm_course: str,
    effective_provider: str,
    collection: Any,
    pool_size: int,
    search_mode: str,
    candidates: dict[str, dict[str, Any]],
    is_secondary: bool = False,
) -> None:
    """Thực hiện Dense + BM25 cho một truy vấn và điền thứ hạng chính hoặc phụ vào candidates."""
    if not query_str or not query_str.strip():
        return
    dense_rank_key = "sec_dense_rank" if is_secondary else "dense_rank"
    bm25_rank_key = "sec_bm25_rank" if is_secondary else "bm25_rank"

    def _ensure_entry(
        chunk_id: str,
        text: str,
        source: str,
        course_val: str,
        idx_val: Any,
        section_val: str,
        n_score: Any,
        n_type: Any,
        page_start: Any = None,
        page_end: Any = None,
    ) -> dict[str, Any]:
        if chunk_id not in candidates:
            candidates[chunk_id] = {
                "id": chunk_id,
                "text": text,
                "source": source,
                "course_id": course_val,
                "index": idx_val,
                "section_title": section_val,
                "noise_score": n_score,
                "noise_type": n_type,
                "page_start": page_start,
                "page_end": page_end,
                "dense_sim": None,
                "dense_distance": None,
                "dense_rank": 999,
                "bm25_score": None,
                "bm25_rank": 999,
                "sec_dense_rank": 999,
                "sec_bm25_rank": 999,
                "rrf_score": 0.0,
            }
        return candidates[chunk_id]

    if search_mode in ("hybrid", "dense"):
        embed_fn = _resolve_store_dep("embed_texts", embed_texts)
        query_vector = embed_fn([query_str], task="query", provider=effective_provider)
        results = collection.query(
            query_embeddings=query_vector,
            n_results=pool_size,
            where={"course_id": norm_course},
            include=["documents", "metadatas", "distances"],
        )
        if results and results.get("documents"):
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
            ids = results.get("ids", [[]])[0]
            for rank, (chunk_id, doc, meta, dist) in enumerate(zip(ids, docs, metas, distances), 1):
                meta = meta or {}
                sim = round(1.0 - float(dist), 4)
                entry = _ensure_entry(
                    chunk_id,
                    doc,
                    meta.get("source", "Không rõ"),
                    meta.get("course_id", norm_course),
                    meta.get("index", 0),
                    meta.get("section_title", ""),
                    meta.get("noise_score"),
                    meta.get("noise_type"),
                    meta.get("page_start"),
                    meta.get("page_end"),
                )
                entry[dense_rank_key] = rank
                if not is_secondary:
                    entry["dense_sim"] = sim
                    entry["dense_distance"] = round(float(dist), 4)

    if search_mode in ("hybrid", "bm25"):
        bm25_fn = _resolve_store_dep("get_bm25_index", get_bm25_index)
        bm25, bm25_docs = bm25_fn(norm_course, provider=effective_provider)
        if bm25 and bm25_docs:
            tokenized_q = tokenize_text(query_str)
            if tokenized_q:
                bm25_scores = bm25.get_scores(tokenized_q)
                top_bm25_indices = sorted(
                    range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True
                )[:pool_size]

                for rank, idx in enumerate(top_bm25_indices, 1):
                    score = float(bm25_scores[idx])
                    if score <= 0:
                        continue
                    b_doc = bm25_docs[idx]
                    chunk_id = b_doc["id"]
                    entry = _ensure_entry(
                        chunk_id,
                        b_doc["text"],
                        b_doc["source"],
                        b_doc.get("course_id", norm_course),
                        b_doc["index"],
                        b_doc.get("section_title", ""),
                        b_doc.get("noise_score"),
                        b_doc.get("noise_type"),
                        b_doc.get("page_start"),
                        b_doc.get("page_end"),
                    )
                    entry[bm25_rank_key] = rank
                    if not is_secondary:
                        entry["bm25_score"] = round(score, 2)


def _strip_section_prefix(text: str) -> str:
    s = text.strip()
    if s.startswith("["):
        nl = s.find("]\n")
        if nl != -1:
            return s[nl + 2 :].strip()
    return s


def _attach_neighbor_context(
    chunks: list[dict[str, Any]],
    norm_course: str,
    effective_provider: str,
) -> None:
    """Mở rộng ngữ cảnh với chunk liền kề cùng tài liệu & cùng mục."""
    if not chunks:
        return
    bm25_fn = _resolve_store_dep("get_bm25_index", get_bm25_index)
    _, bm25_docs = bm25_fn(norm_course, provider=effective_provider)
    if not bm25_docs:
        return
    by_src_idx: dict[tuple[str, int], dict[str, Any]] = {}
    for doc in bm25_docs:
        try:
            by_src_idx[(str(doc["source"]), int(doc["index"]))] = doc
        except (TypeError, ValueError):
            continue

    for c in chunks:
        src = str(c.get("source", ""))
        sec = str(c.get("section_title", ""))
        try:
            idx = int(c.get("index", 0))
        except (TypeError, ValueError):
            continue
        parts: list[str] = [str(c.get("text", "")).strip()]
        prev_doc = by_src_idx.get((src, idx - 1))
        if prev_doc and str(prev_doc.get("section_title", "")) == sec:
            prev_body = _strip_section_prefix(str(prev_doc.get("text", "")))
            if prev_body and len(prev_body) <= 450 and prev_body not in parts[0]:
                parts.insert(0, f"...{prev_body}")
        next_doc = by_src_idx.get((src, idx + 1))
        if next_doc and str(next_doc.get("section_title", "")) == sec:
            next_body = _strip_section_prefix(str(next_doc.get("text", "")))
            if next_body and len(next_body) <= 450 and next_body not in parts[-1]:
                parts.append(next_body)
        if len(parts) > 1:
            c["expanded_text"] = "\n".join(parts)


def query_relevant_chunks(
    query_text: str,
    course_id: str = "default",
    top_k: int = 3,
    score_threshold: Optional[float] = None,
    search_mode: str = "hybrid",
    use_rerank: bool = False,
    embedding_provider: Optional[str] = None,
    reranker_provider: Optional[str] = None,
    secondary_query: Optional[str] = None,
    secondary_weight: float = 0.35,
    expand_neighbors: bool = False,
) -> list[dict[str, Any]]:
    """Truy vấn nâng cao các đoạn giáo trình liên quan nhất (Hybrid Dense + BM25 + RRF + Rerank + Lọc liên quan)."""
    if not query_text or not query_text.strip():
        return []
    if search_mode not in {"dense", "bm25", "hybrid"}:
        raise ValueError("search_mode phải là 'dense', 'bm25' hoặc 'hybrid'.")
    if top_k < 1:
        return []

    norm_course = normalize_course_id(course_id)
    effective_provider = resolve_course_embedding_provider(norm_course, embedding_provider)
    get_coll = _resolve_store_dep("get_chroma_collection", get_chroma_collection)
    collection = get_coll(effective_provider)
    coll_name = get_collection_name(effective_provider)

    stats = _get_course_stats(collection, norm_course, coll_name)
    course_count = int(stats.get("count", 0))

    if course_count == 0 and list_course_files(norm_course):
        index_documents(
            course_id=norm_course,
            force_reindex=False,
            embedding_provider=effective_provider,
        )
        stats = _get_course_stats(collection, norm_course, coll_name)
        course_count = int(stats.get("count", 0))

    if course_count == 0:
        return []

    cleaned_query = clean_oral_query(query_text)
    candidate_pool_size = min(max(top_k * 6, 20), course_count)
    candidates: dict[str, dict[str, Any]] = {}

    _search_candidates_for_query(
        query_str=cleaned_query,
        norm_course=norm_course,
        effective_provider=effective_provider,
        collection=collection,
        pool_size=candidate_pool_size,
        search_mode=search_mode,
        candidates=candidates,
        is_secondary=False,
    )

    if secondary_query and secondary_query.strip():
        cleaned_secondary = clean_oral_query(secondary_query)
        if (
            cleaned_secondary
            and len(cleaned_secondary) >= 6
            and cleaned_secondary.lower() != cleaned_query.lower()
        ):
            sec_pool = min(max(top_k * 3, 10), course_count)
            _search_candidates_for_query(
                query_str=cleaned_secondary,
                norm_course=norm_course,
                effective_provider=effective_provider,
                collection=collection,
                pool_size=sec_pool,
                search_mode=search_mode,
                candidates=candidates,
                is_secondary=True,
            )

    if not candidates:
        return []

    drop_thr = float(getattr(settings, "rag_noise_drop_threshold", 0.70) or 0.70)
    penalty_thr = float(getattr(settings, "rag_noise_penalty_threshold", 0.40) or 0.40)
    raw_candidates = list(candidates.values())
    filtered_candidates: list[dict[str, Any]] = []
    for c in raw_candidates:
        stored_score = c.get("noise_score")
        stored_type = c.get("noise_type")
        if isinstance(stored_score, (int, float)) and stored_type:
            n_score = float(stored_score)
            n_type = str(stored_type)
        else:
            prof = compute_noise_profile(
                str(c.get("text", "")), str(c.get("section_title", ""))
            )
            n_score = float(prof["noise_score"])
            n_type = str(prof["noise_type"])
        c["noise_score"] = n_score
        c["noise_type"] = n_type
        if n_score < drop_thr:
            filtered_candidates.append(c)

    candidate_list = filtered_candidates if filtered_candidates else raw_candidates
    k_constant = 60.0
    for c in candidate_list:
        retrieval_sources = []
        if c.get("dense_rank", 999) != 999 or c.get("sec_dense_rank", 999) != 999:
            retrieval_sources.append("dense")
        if c.get("bm25_rank", 999) != 999 or c.get("sec_bm25_rank", 999) != 999:
            retrieval_sources.append("BM25")
        c["retrieved_by"] = " + ".join(retrieval_sources) or "unknown"

        score_dense = (
            1.0 / (k_constant + c["dense_rank"]) if c.get("dense_rank", 999) < 999 else 0.0
        )
        score_bm25 = (
            1.0 / (k_constant + c["bm25_rank"]) if c.get("bm25_rank", 999) < 999 else 0.0
        )
        sec_dense = (
            secondary_weight / (k_constant + c["sec_dense_rank"])
            if c.get("sec_dense_rank", 999) < 999
            else 0.0
        )
        sec_bm25 = (
            secondary_weight / (k_constant + c["sec_bm25_rank"])
            if c.get("sec_bm25_rank", 999) < 999
            else 0.0
        )
        base_rrf = score_dense + score_bm25 + sec_dense + sec_bm25
        n_score = float(c.get("noise_score", 0.0))
        if penalty_thr <= n_score < drop_thr:
            base_rrf *= max(0.3, 1.0 - 0.5 * n_score)
        c["rrf_score"] = round(base_rrf, 5)
        c.pop("sec_dense_rank", None)
        c.pop("sec_bm25_rank", None)

    candidate_list.sort(key=lambda x: x["rrf_score"], reverse=True)

    effective_reranker = resolve_course_reranker_provider(norm_course, reranker_provider)
    rerank_applied = False
    if use_rerank and len(candidate_list) > 1:
        reranker_fn = _resolve_store_dep("get_reranker_model", get_reranker_model)
        reranker = reranker_fn(provider=effective_reranker)
        if reranker is not None:
            rerank_limit = min(len(candidate_list), max(top_k * 4, 12))
            rerank_head = candidate_list[:rerank_limit]
            rerank_tail = candidate_list[rerank_limit:]
            pairs = [[cleaned_query, c["text"]] for c in rerank_head]
            try:
                rerank_scores = reranker.predict(pairs)
                for c, r_score in zip(rerank_head, rerank_scores):
                    c["rerank_score"] = round(float(r_score), 4)
                    c["method"] = f"{search_mode.title()} + Cross-Encoder Rerank"
                rerank_head.sort(key=lambda x: x["rerank_score"], reverse=True)
                for c in rerank_tail:
                    c["method"] = f"{search_mode.title()} RRF"
                candidate_list = rerank_head + rerank_tail
                rerank_applied = True
            except Exception:
                for c in candidate_list:
                    c["method"] = f"{search_mode.title()} RRF"
        else:
            for c in candidate_list:
                c["method"] = f"{search_mode.title()} RRF"
    else:
        for c in candidate_list:
            c["method"] = f"{search_mode.title()} RRF"

    if score_threshold is not None:
        candidate_list = [
            c
            for c in candidate_list
            if c.get("dense_rank", 999) == 999
            or (c.get("dense_sim") is not None and c["dense_sim"] >= score_threshold)
        ]
    elif getattr(settings, "rag_min_relevance_enabled", True) and search_mode != "bm25":
        min_dense = get_min_dense_similarity(effective_provider)
        relevant: list[dict[str, Any]] = []
        for c in candidate_list:
            if rerank_applied:
                r_score = c.get("rerank_score")
                if r_score is not None and is_rerank_score_relevant(float(r_score), effective_reranker):
                    relevant.append(c)
            else:
                dense_val = c.get("dense_sim")
                bm25_val = float(c.get("bm25_score") or 0.0)
                if dense_val is None:
                    if bm25_val >= 8.0:
                        relevant.append(c)
                elif float(dense_val) >= min_dense or bm25_val >= 6.0:
                    relevant.append(c)
        candidate_list = relevant

    selected = candidate_list[:top_k]
    if expand_neighbors and selected:
        _attach_neighbor_context(selected, norm_course, effective_provider)
    return selected


def format_rag_context(chunks: list[dict[str, Any]]) -> str:
    """Định dạng danh sách đoạn trích xuất ngắn gọn, sạch thông số nội bộ để chèn vào Prompt LLM."""
    if not chunks:
        return ""
    formatted = []
    for i, c in enumerate(chunks, 1):
        header_parts = [f"Đoạn trích {i}", f"Nguồn: {c.get('source', 'Không rõ')}"]
        page_start = c.get("page_start")
        page_end = c.get("page_end") or page_start
        if page_start is not None:
            header_parts.append(
                f"Trang/Slide: {page_start}"
                if page_end == page_start
                else f"Trang/Slide: {page_start}-{page_end}"
            )
        body_text = str(c.get("expanded_text") or c.get("text") or "").strip()
        formatted.append(f"[{' | '.join(header_parts)}]\n{body_text}")
    return "\n\n---\n\n".join(formatted)
