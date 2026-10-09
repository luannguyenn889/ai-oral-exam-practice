from fastapi import FastAPI

app = FastAPI(
    title="Oral Exam AI Service",
    version="0.1.0",
    description="Internal service boundary for speech recognition and rubric evaluation.",
)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "UP", "service": "ai-service"}
