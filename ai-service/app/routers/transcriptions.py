"""Router định tuyến các API chuyển giọng nói thành văn bản (STT) và chuẩn hóa chính tả.

Nhiệm vụ:
- POST /ai/transcriptions/upload:
    + Tiếp nhận file ghi âm được upload trực tiếp từ Frontend (MediaRecorder .webm, .wav, .mp3).
    + Chuyển tiếp tới stt_service để chạy pipeline STT (Groq/Gemini/Whisper/Mock).
    + Tự động gọi Gemini sửa lỗi chính tả & chuẩn hóa thuật ngữ chuyên ngành CNTT theo ngữ cảnh câu hỏi/rubric.
- POST /ai/transcriptions:
    + Tiếp nhận đường dẫn file âm thanh cục bộ trên máy để chạy pipeline STT tương tự.
- POST /ai/transcriptions/correct:
    + Cho phép sinh viên/giảng viên chủ động yêu cầu AI chạy lại bước hiệu đính chính tả và chuẩn hóa thuật ngữ cho đoạn văn bản có sẵn.
"""

import os
import tempfile
from typing import Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.stt_schema import (
    SpellCorrectionRequest,
    SpellCorrectionResponse,
    TranscriptionRequest,
    TranscriptionResponse,
)
from app.services import stt_service

router = APIRouter(prefix="/ai/transcriptions", tags=["transcriptions"])


@router.post("/correct", response_model=SpellCorrectionResponse)
def correct_transcript_text(request: SpellCorrectionRequest) -> SpellCorrectionResponse:
    try:
        print(
            f"[AI-SERVICE][SPELL-CORRECT] Chuan hoa thuat ngu CNTT bang {request.correction_model}...",
            flush=True,
        )
        corrected = stt_service.correct_transcript_with_gemini(
            transcript=request.transcript,
            question=request.question_text,
            rubric_summary=request.rubric_summary,
            gemini_model=request.correction_model,
        )
        print(f"   + Sau hieu dinh: {corrected[:120]}...", flush=True)
        return SpellCorrectionResponse(
            raw_transcript=request.transcript,
            corrected_transcript=corrected,
            correction_model=request.correction_model,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Lỗi khi sửa lỗi chính tả bằng AI: {exc}"
        ) from exc


@router.post("", response_model=TranscriptionResponse)
def transcribe_from_path(request: TranscriptionRequest) -> TranscriptionResponse:
    try:
        print(
            f"[AI-SERVICE][STT] Nhan yeu cau STT tu path={request.audio_path} | Provider={request.stt_provider}",
            flush=True,
        )
        result = stt_service.run_transcription_pipeline(
            audio_path=request.audio_path,
            question_text=request.question_text,
            rubric_summary=request.rubric_summary,
            stt_provider=request.stt_provider,
            stt_model_name=request.stt_model_name,
            enable_spell_correction=request.enable_spell_correction,
            correction_model=request.correction_model,
        )
        return TranscriptionResponse(**result)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi khi nhận dạng giọng nói: {exc}") from exc


@router.post("/upload", response_model=TranscriptionResponse)
async def transcribe_uploaded_audio(
    file: UploadFile = File(...),
    question_text: str = Form(default=""),
    rubric_summary: str = Form(default=""),
    stt_provider: Literal["groq", "gemini", "whisper", "phowhisper", "mock"] = Form(
        default="groq"
    ),
    stt_model_name: Optional[str] = Form(default=None),
    enable_spell_correction: bool = Form(default=True),
    correction_model: str = Form(default="gemini-2.5-flash"),
) -> TranscriptionResponse:
    ext = os.path.splitext(file.filename or "audio.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=ext, prefix="oral_upload_", delete=False) as tmp:
        temp_path = tmp.name
        content = await file.read()
        tmp.write(content)

    try:
        print(
            f"[AI-SERVICE][STT-UPLOAD] File={file.filename} ({len(content)} bytes) | "
            f"Provider={stt_provider} | SpellCorrection={enable_spell_correction}",
            flush=True,
        )
        result = stt_service.run_transcription_pipeline(
            audio_path=temp_path,
            question_text=question_text,
            rubric_summary=rubric_summary,
            stt_provider=stt_provider,
            stt_model_name=stt_model_name,
            enable_spell_correction=enable_spell_correction,
            correction_model=correction_model,
        )
        print(
            f"[AI-SERVICE][STT-UPLOAD DONE] Model={result['stt_model']} | "
            f"Time={result['processing_time_ms']}ms",
            flush=True,
        )
        return TranscriptionResponse(**result)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi khi nhận dạng giọng nói: {exc}") from exc
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
