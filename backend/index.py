
import os
import re
import pytesseract
from PIL import Image
from pypdf import PdfReader
from Schema.pydantic_schema import ResumeData
from bs_logic.functions import calculate_completeness_score , structure_resume,generate_qualitative_feedback,generate_llm_fact_score,calculate_keyword_overlap,generate_llm_job_match,validate_resume
from bs_logic.ats_scorer import calculate_ats_score 
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# file_path="uploads/ai_ml_sample.pdf"
# file_path="uploads/gitrank2.png"
file_path="uploads/yashif.png"
# job_description = "this is my resume and i want to looking the job for the gen ai development with web developemtn,main work is gen ai implement in products like saas language are know python ,js  and gen ai framwork langchain,langgraph"

job_description=None
# png or jpg to text 
def extract_text_basic(image_path):
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)
    return text

# pdf to text 
def extract_text_pypdf(pdf_path):
    reader = PdfReader(pdf_path)
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() + "\n"
    return full_text

# check the file extation and sent there function 
def check_file_path(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".png", ".jpg", ".jpeg"]:
        text = extract_text_basic(file_path)
    elif ext == ".pdf":
        text = extract_text_pypdf(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    return text

# clean the test 
def clean_text(raw_text):
    # Multiple spaces ko single space mein convert
    text = re.sub(r' +', ' ', raw_text)
    # Multiple blank lines ko single mein convert
    text = re.sub(r'\n\s*\n', '\n', text)
    # Leading/trailing whitespace hatao
    text = text.strip()
    return text

# print(check_file_path(file_path))
# print("clean function diff --->>")
# print(check_file_path(clean_text(file_path)))

resume_tool = {
    "name": "extract_resume_data",
    "description": "Extract structured information from resume text",
    "input_schema": ResumeData.model_json_schema()
}


def analyze_resume(resume: ResumeData) -> dict:
    score_report = calculate_completeness_score(resume)
    fact_analysis = generate_llm_fact_score(resume, score_report)

    # Weighted combination: rule-based deterministic score + LLM qualitative judgment
    final_score = round(
        (score_report['percentage'] * 0.4) + (fact_analysis.overall_llm_score * 0.6), 1
    )

    return {
        "final_score": final_score,
        "completeness_score": score_report,
        "llm_fact_analysis": {
            "facts": [fact.model_dump() for fact in fact_analysis.facts],
            "overall_llm_score": fact_analysis.overall_llm_score,
            "summary_verdict": fact_analysis.summary_verdict
        }
    }

# Full pipeline test
# cleaned=check_file_path(clean_text(file_path))
# structured = structure_resume(cleaned)   # ✅ ye ResumeData object return karta hai
# analysis = analyze_resume(structured)
# print(analysis)



def match_resume_to_job(resume: ResumeData, job_description: str) -> dict:
    keyword_overlap = calculate_keyword_overlap(resume, job_description)
    llm_match = generate_llm_job_match(resume, job_description, keyword_overlap)

    return {
        "keyword_overlap": keyword_overlap,
        "llm_match_analysis": llm_match.model_dump()
    }

cleaned = check_file_path(clean_text(file_path))

# ---- validation layer ----
validation = validate_resume(cleaned)
if not validation["is_resume"] or validation.get("confidence", 0) < 0.6:
    print(f"❌ Not a valid resume — {validation['reason']} (stage: {validation['stage']})")
    raise ValueError(f"Invalid resume file: {validation['reason']}")

# def analyze_and_match(resume: ResumeData, job_description: str | None = None) -> dict:
#     # Always run — general resume quality, independent of any job
#     quality_report = analyze_resume(resume)

#     result = {
#         "quality": quality_report
#     }

#     # Run only if user provided a JD
#     if job_description:
#         job_match = match_resume_to_job(resume, job_description)
#         result["job_match"] = job_match

#     return result




def analyze_and_match(resume: ResumeData,raw_text: str,  job_description: str | None = None) -> dict:
    quality_report = analyze_resume(resume)

    result = {
        "quality": quality_report
    }

    keyword_overlap = None
    if job_description:
        job_match = match_resume_to_job(resume, job_description)
        result["job_match"] = job_match
        keyword_overlap = job_match["keyword_overlap"]   # reuse, don't recompute

    # ATS score always computed — full if JD present, structure-only if not
    ats_report = calculate_ats_score(resume.raw_text, keyword_overlap)
    print("ats_report",ats_report)
    result["ats_score"] = {
        "mode": ats_report.mode,
        "overall_score": ats_report.overall_score,
        "breakdown": [{"check": c.message, "score": c.score, "weight": c.weight} for c in ats_report.checks],
        "suggestions": ats_report.suggestions,
    }

    return result


# Full pipeline of project 
cleaned = check_file_path(clean_text(file_path))

validation = validate_resume(cleaned)
if not validation["is_resume"] or validation.get("confidence", 0) < 0.6:
    raise ValueError(f"Invalid resume file: {validation['reason']}")

# structured = structure_resume(cleaned)
# structured.raw_text = cleaned
# result = analyze_and_match(structured, job_description)  # job_description optional
# print(result)


def run_resume_analysis(
    file_path: str,
    job_description: str | None = None,
    want_ats_score: bool = False,
) -> dict:
    cleaned = check_file_path(clean_text(file_path))

    validation = validate_resume(cleaned)
    if not validation["is_resume"] or validation.get("confidence", 0) < 0.6:
        raise ValueError(f"Invalid resume file: {validation['reason']}")

    structured = structure_resume(cleaned)
    structured.raw_text = cleaned

    return analyze_and_match(structured, job_description, want_ats_score)


def analyze_and_match(
    resume: ResumeData,
    job_description: str | None,
    want_ats_score: bool,
) -> dict:
    # Always runs — independent of JD/ATS
    quality_report = analyze_resume(resume)
    result = {"quality": quality_report}

    keyword_overlap = None
    if job_description:
        job_match = match_resume_to_job(resume, job_description)
        result["job_match"] = job_match
        keyword_overlap = job_match["keyword_overlap"]

    if want_ats_score:
        ats_report = calculate_ats_score(resume.raw_text, keyword_overlap)
        result["ats_score"] = {
            "mode": ats_report.mode,               # "full" if keyword_overlap else "structure_only"
            "overall_score": ats_report.overall_score,
            "breakdown": [
                {"check": c.message, "score": c.score, "weight": c.weight}
                for c in ats_report.checks
            ],
            "suggestions": ats_report.suggestions,
        }

    return result


# case 1
run_resume_analysis(file_path)

# Case 2
# run_resume_analysis(file_path, job_description=job_description)

# # Case 3
# run_resume_analysis(file_path, want_ats_score=True)

# # Case 4
# run_resume_analysis(file_path, job_description=job_description, want_ats_score=True)