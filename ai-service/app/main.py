"""Điểm khởi động chính của AI Service (FastAPI).

Nhiệm vụ:
- Khởi tạo ứng dụng FastAPI và cấu hình CORS cho phép Frontend Angular gọi trực tiếp.
- Quản lý vòng đời (lifespan): tự động khởi tạo thư mục lưu giáo trình và ChromaDB.
- Ghi nhận nhật ký (logging middleware): theo dõi mọi HTTP request/response ra terminal.
- Gắn kết các router chức năng:
    + /ai/transcriptions: Chuyển giọng nói thành văn bản (STT) và sửa lỗi thuật ngữ CNTT.
    + /ai/evaluations: Chấm điểm câu trả lời vấn đáp kết hợp Rubric và RAG.
    + /ai/rag: Quản lý kho giáo trình, lập chỉ mục và tìm kiếm ngữ nghĩa.
- Cung cấp endpoint kiểm tra tình trạng dịch vụ (/health và /ai/health).
"""

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import evaluations, rag, transcriptions


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.resolved_documents_dir.mkdir(parents=True, exist_ok=True)
    settings.resolved_chroma_db_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"[AI-SERVICE] Khoi dong thanh cong! Documents={settings.resolved_documents_dir} | "
        f"ChromaDB={settings.resolved_chroma_db_dir}",
        flush=True,
    )
    yield


app = FastAPI(
    title="Oral Exam AI Service",
    version="0.2.0",
    description=(
        "Microservice xử lý Nhận dạng giọng nói (STT), Chuẩn hóa thuật ngữ CNTT, "
        "Truy xuất Giáo trình Hybrid RAG (Dense + BM25 + RRF) và Chấm điểm theo Rubric."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_ts = time.perf_counter()
    print(f"\n---> [FASTAPI REQUEST] {request.method} {request.url.path}", flush=True)
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
    print(
        f"<--- [FASTAPI RESPONSE] {request.method} {request.url.path} "
        f"-> Status {response.status_code} ({elapsed_ms} ms)",
        flush=True,
    )
    return response


app.include_router(transcriptions.router)
app.include_router(evaluations.router)
app.include_router(rag.router)


@app.get("/health", tags=["operations"])
@app.get("/ai/health", tags=["operations"])
def health() -> dict[str, Any]:
    return {
        "status": "UP",
        "service": "ai-service",
        "version": "0.2.0",
        "default_stt_provider": settings.default_stt_provider,
        "default_llm_model": settings.default_llm_model,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model_name,
        "gemini_key_configured": bool(settings.gemini_api_key.strip()),
        "groq_key_configured": bool(settings.groq_api_key.strip()),
    }
