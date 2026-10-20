from fastapi import APIRouter, HTTPException

from app.schemas.eval_schema import EvaluationRequest, EvaluationResponse
from app.services import grading_service

router = APIRouter(prefix="/ai/evaluations", tags=["evaluations"])


@router.post("", response_model=EvaluationResponse)
def evaluate_submission(request: EvaluationRequest) -> EvaluationResponse:
    try:
        print(
            f"[AI-SERVICE][EVALUATION] Bat dau cham diem | Session={request.session_id} | "
            f"Course={request.course_id} | Model={request.llm_model} | "
            f"RAG={request.rag_config.enabled} ({request.rag_config.search_mode}, top_k={request.rag_config.top_k})",
            flush=True,
        )
        print(f"   + Cau hoi    : {request.question[:120]}...", flush=True)
        print(f"   + Transcript : {request.transcript[:120]}...", flush=True)
        result = grading_service.evaluate_oral_answer(request)
        print(
            f"[AI-SERVICE][EVALUATION DONE] Tong diem: {result.total_score}/{result.max_score} | "
            f"RAG Chunks={len(result.rag_references)} | Time={result.metadata.processing_time_ms}ms",
            flush=True,
        )
        return result
    except ValueError as ve:
        print(f"[AI-SERVICE][EVALUATION ERROR 400] {ve}", flush=True)
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as exc:
        print(f"[AI-SERVICE][EVALUATION ERROR 500] {exc}", flush=True)
        raise HTTPException(status_code=500, detail=f"Lỗi khi chấm điểm AI: {exc}") from exc
