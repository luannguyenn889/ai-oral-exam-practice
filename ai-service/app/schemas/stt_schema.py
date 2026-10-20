from typing import Literal, Optional
from pydantic import BaseModel, Field


class TranscriptionRequest(BaseModel):
    audio_path: str = Field(..., description="Đường dẫn tới file âm thanh cần nhận dạng")
    question_text: str = Field(default="", description="Nội dung câu hỏi đề thi để định hướng sửa lỗi thuật ngữ")
    rubric_summary: str = Field(default="", description="Tóm tắt các từ khóa/tiêu chí trong Rubric")
    stt_provider: Literal["groq", "gemini", "whisper", "phowhisper", "mock"] = Field(
        default="groq",
        description="Bộ nhận dạng giọng nói: groq (whisper-large-v3), gemini, whisper, phowhisper, hoặc mock",
    )
    stt_model_name: Optional[str] = Field(
        default=None,
        description="Tên model cụ thể (ví dụ: base/small cho whisper, vinai/PhoWhisper-small cho phowhisper)",
    )
    enable_spell_correction: bool = Field(
        default=True,
        description="Tự động sửa lỗi chính tả và thuật ngữ chuyên ngành CNTT theo ngữ cảnh câu hỏi + rubric",
    )
    correction_model: str = Field(
        default="gemini-2.5-flash",
        description="Model LLM dùng để sửa lỗi chính tả (gemini-2.5-flash hoặc gemma3:4b)",
    )


class TranscriptionResponse(BaseModel):
    raw_transcript: str
    corrected_transcript: str
    duration_seconds: float
    stt_model: str
    correction_model: str
    processing_time_ms: int


class SpellCorrectionRequest(BaseModel):
    transcript: str = Field(..., min_length=1, description="Văn bản thô cần sửa lỗi chính tả/thuật ngữ")
    question_text: str = Field(default="", description="Câu hỏi đề thi")
    rubric_summary: str = Field(default="", description="Tóm tắt các tiêu chí Rubric")
    correction_model: str = Field(default="gemini-2.5-flash")


class SpellCorrectionResponse(BaseModel):
    raw_transcript: str
    corrected_transcript: str
    correction_model: str


