
import os
import re
import pytesseract
from PIL import Image
from pypdf import PdfReader
from Schema.pydantic_schema import ResumeData
from bs_logic.functions import calculate_completeness_score , structure_resume,generate_qualitative_feedback,generate_llm_fact_score
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# file_path="uploads/ai_ml_sample.pdf"
file_path="uploads/yashif.png"

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
cleaned=check_file_path(clean_text(file_path))
structured = structure_resume(cleaned)   # ✅ ye ResumeData object return karta hai
analysis = analyze_resume(structured)

print(analysis)
# print(json.dumps(analysis, indent=2))
