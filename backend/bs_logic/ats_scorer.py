# ats_scorer.py
import re
from dataclasses import dataclass, field

@dataclass
class ATSCheckResult:
    score: float          # 0-100
    weight: float
    passed: bool
    message: str

@dataclass
class ATSReport:
    overall_score: float
    checks: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    mode: str = "structure_only"


SECTION_HEADINGS = {
    "experience": r"(work\s+experience|experience|employment\s+history)",
    "education": r"(education|academic\s+background)",
    "skills": r"(skills|technical\s+skills|core\s+competencies)",
    "summary": r"(summary|objective|profile)",
}

EMAIL_RE = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
PHONE_RE = r"(\+?\d{1,3}[-.\s]?)?\(?\d{3,5}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"


def check_contact_info(text: str) -> ATSCheckResult:
    has_email = bool(re.search(EMAIL_RE, text))
    has_phone = bool(re.search(PHONE_RE, text))
    score = (has_email * 50) + (has_phone * 50)
    msg = "Email & phone detected" if score == 100 else "Missing email or phone in parseable format"
    return ATSCheckResult(score=score, weight=0.10, passed=score == 100, message=msg)


def check_section_headings(text: str) -> ATSCheckResult:
    text_lower = text.lower()
    found = sum(1 for pattern in SECTION_HEADINGS.values() if re.search(pattern, text_lower))
    total = len(SECTION_HEADINGS)
    score = (found / total) * 100
    missing = [name for name, pat in SECTION_HEADINGS.items() if not re.search(pat, text_lower)]
    msg = f"Missing sections: {', '.join(missing)}" if missing else "All standard sections found"
    return ATSCheckResult(score=score, weight=0.25, passed=found == total, message=msg)


def check_formatting_hygiene(text: str) -> ATSCheckResult:
    # bullet usage check
    bullet_lines = len(re.findall(r"^[\s]*[•\-\*]\s", text, re.MULTILINE))
    total_lines = len(text.splitlines())
    bullet_ratio = bullet_lines / max(total_lines, 1)

    # weird character density = parsing corruption signal (from PDF tables/columns)
    weird_chars = len(re.findall(r"[^\x00-\x7F]", text))
    corruption_ratio = weird_chars / max(len(text), 1)

    score = 100
    issues = []
    if bullet_ratio < 0.1:
        score -= 30
        issues.append("Low bullet point usage — ATS prefers bullets over paragraphs")
    if corruption_ratio > 0.02:
        score -= 40
        issues.append("Possible table/column formatting causing text corruption")

    msg = "; ".join(issues) if issues else "Formatting looks ATS-clean"
    return ATSCheckResult(score=max(score, 0), weight=0.15, passed=score >= 70, message=msg)


def check_date_consistency(text: str) -> ATSCheckResult:
    date_patterns = re.findall(
        r"(\b\d{4}\b|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{4})",
        text
    )
    score = 100 if len(date_patterns) >= 2 else 50
    msg = "Consistent date formatting" if score == 100 else "Add clear dates (MMM YYYY) to experience entries"
    return ATSCheckResult(score=score, weight=0.15, passed=score == 100, message=msg)




def check_keyword_match(keyword_overlap: dict) -> ATSCheckResult:
    """
    Reuses the existing calculate_keyword_overlap() output instead of
    a separate extract/match pair — no duplicate keyword logic.
    """
    if not keyword_overlap:
        return ATSCheckResult(score=100, weight=0.35, passed=True, message="No JD provided — skipped")

    matched = keyword_overlap.get("matched", [])
    missing = keyword_overlap.get("missing", [])
    total = len(matched) + len(missing)

    if total == 0:
        return ATSCheckResult(score=100, weight=0.35, passed=True, message="No keywords to compare")

    score = round((len(matched) / total) * 100, 1)
    msg = f"Missing keywords: {', '.join(missing[:5])}" if missing else "Strong keyword match"
    return ATSCheckResult(score=score, weight=0.35, passed=score >= 60, message=msg)


def calculate_ats_score(resume_text: str, keyword_overlap: dict | None = None) -> ATSReport:
    print("ats score function run ")
    has_jd = bool(keyword_overlap)

    checks = [
        check_contact_info(resume_text),
        check_section_headings(resume_text),
        check_formatting_hygiene(resume_text),
        check_date_consistency(resume_text),
    ]

    if has_jd:
        checks.append(check_keyword_match(keyword_overlap))
    else:
        remaining_weight_sum = sum(c.weight for c in checks)
        scale_factor = 1.0 / remaining_weight_sum
        for c in checks:
            c.weight = round(c.weight * scale_factor, 4)

    overall = sum(c.score * c.weight for c in checks)
    suggestions = [c.message for c in checks if not c.passed]

    return ATSReport(
        overall_score=round(overall, 1),
        checks=checks,
        suggestions=suggestions,
        mode="full" if has_jd else "structure_only"
    )