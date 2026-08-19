import os
import re
import tempfile
from pathlib import Path

import pytesseract
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
from pypdf import PdfReader

from Schema.pydantic_schema import ResumeData
from bs_logic.ats_scorer import calculate_ats_score
from bs_logic.functions import (
    calculate_completeness_score,
    calculate_keyword_overlap,
    generate_llm_fact_score,
    generate_llm_job_match,
    structure_resume,
    validate_resume,
)


SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
DEFAULT_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
tesseract_path = os.getenv("TESSERACT_CMD", DEFAULT_TESSERACT_PATH)
if Path(tesseract_path).exists():
    pytesseract.pytesseract.tesseract_cmd = tesseract_path

app = FastAPI(title="Resume Analyzer API", version="1.0.0")

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class ErrorResponse(BaseModel):
    detail: str


class AtsScoreRequest(BaseModel):
    resume: ResumeData
    job_description: str | None = None


# ---------- extraction helpers (unchanged) ----------

def extract_text_basic(image_path: str) -> str:
    with Image.open(image_path) as image:
        return pytesseract.image_to_string(image)


def extract_text_pypdf(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def check_file_path(file_path: str) -> str:
    extension = Path(file_path).suffix.lower()
    if extension in {".png", ".jpg", ".jpeg"}:
        return extract_text_basic(file_path)
    if extension == ".pdf":
        return extract_text_pypdf(file_path)
    raise ValueError(f"Unsupported file type: {extension or 'unknown'}")


def clean_text(raw_text: str) -> str:
    text = re.sub(r" +", " ", raw_text)
    text = re.sub(r"\n\s*\n", "\n", text)
    return text.strip()


# ---------- core logic ----------

def analyze_resume(resume: ResumeData) -> dict:
    score_report = calculate_completeness_score(resume)
    fact_analysis = generate_llm_fact_score(resume, score_report)
    final_score = round(
        (score_report["percentage"] * 0.4)
        + (fact_analysis.overall_llm_score * 0.6),
        1,
    )

    return {
        "final_score": final_score,
        "completeness_score": score_report,
        "llm_fact_analysis": {
            "facts": [fact.model_dump() for fact in fact_analysis.facts],
            "overall_llm_score": fact_analysis.overall_llm_score,
            "summary_verdict": fact_analysis.summary_verdict,
        },
    }


def match_resume_to_job(resume: ResumeData, job_description: str) -> dict:
    keyword_overlap = calculate_keyword_overlap(resume, job_description)
    llm_match = generate_llm_job_match(resume, job_description, keyword_overlap)
    return {
        "keyword_overlap": keyword_overlap,
        "llm_match_analysis": llm_match.model_dump(),
    }


def build_ats_response(resume: ResumeData, job_description: str | None) -> dict:
    keyword_overlap = None
    job_match = None

    if job_description and job_description.strip():
        job_match = match_resume_to_job(resume, job_description.strip())
        keyword_overlap = job_match["keyword_overlap"]

    ats_report = calculate_ats_score(resume.raw_text, keyword_overlap)
    response = {
        "ats_score": {
            "mode": ats_report.mode,
            "overall_score": ats_report.overall_score,
            "breakdown": [
                {
                    "check": check.message,
                    "score": check.score,
                    "weight": check.weight,
                    "passed": check.passed,
                }
                for check in ats_report.checks
            ],
            "suggestions": ats_report.suggestions,
        }
    }
    if job_match:
        response["job_match"] = job_match
    return response


def parse_and_structure(file_path: str) -> ResumeData:
    cleaned = clean_text(check_file_path(file_path))
    validation = validate_resume(cleaned)
    if not validation["is_resume"] or validation.get("confidence", 0) < 0.6:
        raise ValueError(f"Invalid resume file: {validation['reason']}")

    structured = structure_resume(cleaned)
    structured.raw_text = cleaned
    return structured


# ---------- routes ----------

@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post(
    "/resume-analyze",
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def analyze_uploaded_resume(
    file: UploadFile = File(...),
    job_description: str | None = Form(default=None),
) -> dict:
    """
    Case 1: file only -> quality score.
    Case 2: file + job_description -> quality score + job_match.
    Returns the structured `resume` back to the frontend so it can be
    cached in state and reused later for /resume-ats-score, without
    re-uploading the file or re-running OCR/LLM extraction.
    """
    extension = Path(file.filename or "").suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload a PDF, PNG, JPG, or JPEG file.",
        )

    temporary_path = None
    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temporary_file:
            temporary_file.write(file_bytes)
            temporary_path = temporary_file.name

        structured = parse_and_structure(temporary_path)

        result = {"quality": analyze_resume(structured)}
        if job_description and job_description.strip():
            result["job_match"] = match_resume_to_job(structured, job_description.strip())

        # send parsed resume back so the frontend can reuse it for ATS score
        result["resume"] = structured.model_dump()
        return result

    except HTTPException:
        raise
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)


@app.post(
    "/resume-ats-score",
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def get_ats_score(payload: AtsScoreRequest) -> dict:
    """
    Case 3: resume already analyzed -> user clicks "ATS Score" button ->
        frontend sends back the `resume` object it got from /resume-analyze
        (no job_description) -> returns just ats_score, no re-parsing.
    Case 4: same, but with job_description -> returns ats_score + job_match
        computed fresh against that job_description.
    """
    try:
        return build_ats_response(payload.resume, payload.job_description)
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error