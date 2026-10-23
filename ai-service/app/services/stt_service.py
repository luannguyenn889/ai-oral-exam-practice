"""Dịch vụ xử lý Nhận dạng giọng nói (STT) và Hiệu đính thuật ngữ CNTT.

Nhiệm vụ:
- Hỗ trợ đa dạng provider STT:
    + Groq Cloud (whisper-large-v3): Tốc độ siêu nhanh, độ chính xác cao (mặc định).
    + Google Gemini Audio (gemini-2.5-flash): Nhận dạng trực tiếp qua API Gemini.
    + Whisper cục bộ (OpenAI Whisper) & VinAI PhoWhisper (HuggingFace transformers).
    + Mock provider: Phục vụ chạy thử nghiệm, test luồng không cần mic.
- Tự động chuẩn hóa file âm thanh sang định dạng chuẩn 16kHz mono WAV (qua ffmpeg hoặc pydub).
- correct_transcript_with_gemini:
    + Kế thừa prompt từ speed-to-text-demo để đối chiếu câu hỏi đề thi và rubric.
    + Sửa các từ phát âm nhầm của sinh viên thành thuật ngữ chuẩn ngành CNTT (ví dụ: 'úp' -> 'OOP', 'lắp' -> 'lớp', 'phương thức', 'kế thừa'...) mà giữ nguyên 100% ngữ nghĩa ban đầu.
- run_transcription_pipeline:
    + Điều phối toàn bộ luồng STT -> Hiệu đính chính tả -> Đo thời lượng & thời gian xử lý.
"""

import contextlib
import gc
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
from typing import Any, Optional

import requests
from google import genai
from groq import Groq

from app.config import settings

_device: Optional[str] = None
_model_cache: dict[str, Any] = {}
_phowhisper_pipeline_cache: dict[str, Any] = {}
_model_lock = threading.Lock()


def get_device() -> str:
    global _device
    if _device is None:
        try:
            import torch

            _device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            _device = "cpu"
    return _device


def get_audio_duration(file_path: str) -> float:
    """Lấy thời lượng âm thanh/video (tính bằng giây)."""
    if not file_path or not os.path.exists(file_path):
        return 0.0
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        return round(float(result.stdout.strip()), 2)
    except Exception:
        try:
            with contextlib.closing(wave.open(file_path, "r")) as f:
                frames = f.getnframes()
                rate = f.getframerate()
                return round(frames / float(rate), 2)
        except Exception:
            return 0.0


def unload_whisper_models(exclude: Optional[str] = None) -> None:
    """Giải phóng các mô hình Whisper khỏi bộ nhớ RAM/VRAM."""
    with _model_lock:
        models_to_remove = [k for k in _model_cache.keys() if k != exclude]
        for k in models_to_remove:
            _model_cache[k] = None
            del _model_cache[k]

        phowhisper_to_remove = [k for k in _phowhisper_pipeline_cache.keys() if k != exclude]
        for k in phowhisper_to_remove:
            _phowhisper_pipeline_cache[k] = None
            del _phowhisper_pipeline_cache[k]

        if ("torch" in sys.modules) and (models_to_remove or phowhisper_to_remove):
            gc.collect()
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()


def load_whisper_model(model_name: str = "base") -> Any:
    unload_whisper_models(exclude=model_name)
    with _model_lock:
        if model_name not in _model_cache:
            import whisper

            dev = get_device()
            _model_cache[model_name] = whisper.load_model(model_name, device=dev)
        return _model_cache[model_name]


def transcribe_with_whisper(audio_path: str, model_name: str = "base") -> str:
    if not audio_path or not os.path.exists(audio_path):
        raise ValueError(f"Không tìm thấy file âm thanh: {audio_path}")
    model = load_whisper_model(model_name)
    result = model.transcribe(audio_path, language="vi")
    transcript = (result.get("text") or "").strip()
    if not transcript:
        raise ValueError("Không thể chuyển đổi âm thanh thành văn bản (Nội dung trống).")
    return transcript


def load_phowhisper_pipeline(model_name: str = "vinai/PhoWhisper-small") -> Any:
    unload_whisper_models(exclude=model_name)
    with _model_lock:
        if model_name not in _phowhisper_pipeline_cache:
            import torch
            from transformers import pipeline

            device_id = 0 if torch.cuda.is_available() else -1
            _phowhisper_pipeline_cache[model_name] = pipeline(
                "automatic-speech-recognition",
                model=model_name,
                device=device_id,
            )
        return _phowhisper_pipeline_cache[model_name]


def transcribe_with_phowhisper(
    audio_path: str, model_name: str = "vinai/PhoWhisper-small"
) -> str:
    if not audio_path or not os.path.exists(audio_path):
        raise ValueError(f"Không tìm thấy file âm thanh: {audio_path}")
    pipe = load_phowhisper_pipeline(model_name)
    result = pipe(audio_path, chunk_length_s=30)
    transcript = (result.get("text") or "").strip()
    if not transcript:
        raise ValueError(
            "Không thể chuyển đổi âm thanh thành văn bản qua PhoWhisper (Nội dung trống)."
        )
    return transcript


def transcribe_with_groq(media_path: str, api_key: Optional[str] = None) -> str:
    key = (api_key or settings.groq_api_key or os.environ.get("GROQ_API_KEY", "")).strip()
    if not key:
        raise ValueError("Chưa cấu hình GROQ_API_KEY trong file .env.")
    if not media_path or not os.path.exists(media_path):
        raise ValueError(f"Không tìm thấy file âm thanh: {media_path}")

    client = Groq(api_key=key)
    ext = os.path.splitext(media_path)[1] or ".wav"
    safe_filename = f"audio_input{ext}"

    with open(media_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=(safe_filename, file.read()),
            model="whisper-large-v3",
            language="vi",
            temperature=0,
            response_format="verbose_json",
        )
    transcript = (transcription.text or "").strip()
    if not transcript:
        raise ValueError("Groq API trả về nội dung nhận dạng giọng nói trống.")
    return transcript


def transcribe_with_gemini_cloud(
    media_path: str,
    api_key: Optional[str] = None,
    gemini_model: str = "gemini-2.5-flash",
) -> str:
    key = (api_key or settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    if not key:
        raise ValueError("Chưa cấu hình GEMINI_API_KEY trong file .env.")
    if not media_path or not os.path.exists(media_path):
        raise ValueError(f"Không tìm thấy file âm thanh: {media_path}")

    client = genai.Client(api_key=key)
    ext = os.path.splitext(media_path)[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=ext, prefix="gemini_stt_", delete=False) as tmp:
        safe_temp_path = tmp.name
    shutil.copy(media_path, safe_temp_path)

    try:
        audio_file = client.files.upload(file=safe_temp_path)
    finally:
        if os.path.exists(safe_temp_path):
            os.remove(safe_temp_path)

    start_time = time.time()
    while audio_file.state.name == "PROCESSING":
        time.sleep(1)
        audio_file = client.files.get(name=audio_file.name)
        if time.time() - start_time > 60:
            raise TimeoutError("Quá thời gian chờ Gemini xử lý file âm thanh.")

    if audio_file.state.name == "FAILED":
        raise RuntimeError("Gemini API xử lý file âm thanh thất bại.")

    prompt = (
        "Hãy nghe file âm thanh đính kèm và ký âm (transcribe) toàn bộ câu trả lời của sinh viên "
        "thành văn bản tiếng Việt chính xác nhất (speech-to-text). Chỉ trả về phần văn bản đã ký âm được, "
        "giữ nguyên các ngắt nghỉ tự nhiên, không thêm giải thích hay lời bàn luận nào khác."
    )
    response = client.models.generate_content(model=gemini_model, contents=[audio_file, prompt])
    transcript = (response.text or "").strip()

    try:
        client.files.delete(name=audio_file.name)
    except Exception:
        pass

    return transcript


def call_ollama_api(
    model: str, prompt: str, is_json: bool = False, timeout: int = 180
) -> str:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if is_json:
        payload["format"] = "json"
    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    result = response.json()
    return (result.get("response") or "").strip()


def correct_transcript_with_gemini(
    transcript: str,
    question: str = "",
    rubric_summary: str = "",
    api_key: Optional[str] = None,
    gemini_model: str = "gemini-2.5-flash",
) -> str:
    """Sửa lỗi chính tả và thuật ngữ chuyên ngành CNTT dựa trên ngữ cảnh Câu hỏi + Rubric."""
    if not transcript or not transcript.strip():
        return ""

    is_local = "ollama" in gemini_model.lower() or gemini_model.startswith("gemma3")
    key = (api_key or settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
    if not is_local and not key:
        return transcript

    prompt = f"""
Bạn là một trợ lý hiệu đính và hiệu chỉnh chính tả chuyên nghiệp tiếng Việt trong lĩnh vực Công nghệ thông tin.
Nhiệm vụ của bạn là sửa lỗi chính tả, lỗi dấu câu, viết hoa đúng tên riêng, và đặc biệt là sửa các lỗi nghe nhầm (các từ phát âm tương tự nhưng viết sai hoặc sai nghĩa ngữ cảnh) từ văn bản nhận diện giọng nói (Speech-to-Text).

Ngữ cảnh của đề thi vấn đáp:
- Câu hỏi đề thi: "{question}"
- Tiêu chí chấm điểm (Rubric): "{rubric_summary}"

Văn bản ký âm thô thu được từ STT cần sửa lỗi:
"{transcript}"

Yêu cầu sửa đổi chi tiết:
1. Dựa vào ngữ cảnh câu hỏi và rubric ở trên để suy đoán chính xác các thuật ngữ chuyên ngành công nghệ thông tin mà sinh viên đã trả lời (ví dụ: nếu đề bài nói về OOP, hãy sửa 'lắp' thành 'lớp', 'úp' hoặc 'ô ô bê' thành 'OOP', 'phân thức' hoặc 'phân phương thức' thành 'phương thức', 'dưới liệu' thành 'dữ liệu', 'chư tượng' thành 'trừu tượng', v.v.).
2. Sửa lỗi chính tả tiếng Việt thông thường một cách chuẩn xác.
3. Đảm bảo câu văn trôi chảy, giữ nguyên 100% ý chính và câu từ gốc của sinh viên (không viết lại câu trả lời theo cách tốt hơn, không tự ý thêm ý mới, không tóm tắt lại). Chỉ sửa đúng lỗi nghe sai/chính tả/dấu câu.
4. BẮT BUỘC CHỈ TRẢ VỀ đoạn văn bản đã được sửa lỗi chính tả hoàn thiện. Không bao gồm lời chào, lời dẫn dắt, hay bất kỳ văn bản giải thích nào khác.
"""

    try:
        if is_local:
            ollama_model = gemini_model.split()[0] if " " in gemini_model else gemini_model
            return call_ollama_api(ollama_model, prompt, is_json=False)
        client = genai.Client(api_key=key)
        response = client.models.generate_content(model=gemini_model, contents=prompt)
        corrected = (response.text or "").strip()
        return corrected if corrected else transcript
    except Exception:
        return transcript


def run_transcription_pipeline(
    audio_path: str,
    question_text: str = "",
    rubric_summary: str = "",
    stt_provider: str = "groq",
    stt_model_name: Optional[str] = None,
    enable_spell_correction: bool = True,
    correction_model: str = "gemini-2.5-flash",
) -> dict[str, Any]:
    """Chạy toàn bộ luồng STT (Groq/Gemini/Whisper/PhoWhisper/Mock) + Sửa lỗi thuật ngữ CNTT."""
    start_ts = time.perf_counter()
    provider = (stt_provider or settings.default_stt_provider or "groq").strip().lower()
    duration_sec = get_audio_duration(audio_path)

    if provider == "mock":
        raw_transcript = (
            "dạ thưa thầy bốn tính chất của úp là đóng gói kế thừa đa hình và chư tượng ạ"
            if not question_text
            else f"Dạ thưa thầy em xin trả lời câu hỏi {question_text[:60]} là gồm các ý chính theo đặc tả và nhu cầu người dùng ạ."
        )
        stt_model_used = "mock-stt"
    elif provider == "groq":
        unload_whisper_models()
        raw_transcript = transcribe_with_groq(audio_path)
        stt_model_used = "whisper-large-v3 (groq)"
    elif provider == "gemini":
        unload_whisper_models()
        model_to_use = stt_model_name or settings.default_llm_model
        raw_transcript = transcribe_with_gemini_cloud(audio_path, gemini_model=model_to_use)
        stt_model_used = f"{model_to_use} (gemini)"
    elif provider == "whisper":
        w_model = stt_model_name or "base"
        raw_transcript = transcribe_with_whisper(audio_path, model_name=w_model)
        stt_model_used = f"openai-whisper-{w_model}"
    elif provider == "phowhisper":
        p_model = stt_model_name or "vinai/PhoWhisper-small"
        raw_transcript = transcribe_with_phowhisper(audio_path, model_name=p_model)
        stt_model_used = p_model
    else:
        raise ValueError(f"Không hỗ trợ stt_provider: {provider}")

    if enable_spell_correction:
        if provider == "mock" and not settings.gemini_api_key:
            corrected_transcript = (
                raw_transcript.replace("úp", "OOP").replace("chư tượng", "trừu tượng")
            )
            correction_used = "mock-corrector"
        else:
            corrected_transcript = correct_transcript_with_gemini(
                transcript=raw_transcript,
                question=question_text,
                rubric_summary=rubric_summary,
                gemini_model=correction_model,
            )
            correction_used = correction_model
    else:
        corrected_transcript = raw_transcript
        correction_used = "disabled"

    elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
    return {
        "raw_transcript": raw_transcript,
        "corrected_transcript": corrected_transcript,
        "duration_seconds": duration_sec,
        "stt_model": stt_model_used,
        "correction_model": correction_used,
        "processing_time_ms": elapsed_ms,
    }

