from pydantic import BaseModel, Field
from typing import List, Optional,Literal


# ---------- Pydantic Schema ----------

class Experience(BaseModel):
    company: str
    role: str
    duration: str
    description: Optional[str] = ""


class Education(BaseModel):
    institution: str
    degree: str
    year: Optional[str] = ""


class ResumeData(BaseModel):
    name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""
    skills: List[str] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    summary: Optional[str] = ""
    

class ResumeFact(BaseModel):
    category: str = Field(description="e.g. Skills, Education, Experience, Projects, Achievements, ATS Formatting")
    rating: Literal["Excellent", "Good", "Average", "Poor"]
    score: int = Field(ge=0, le=100, description="Numeric score for this category out of 100")
    justification: str = Field(description="Specific, concrete reason referencing actual resume content — no generic statements")


class LLMFactAnalysis(BaseModel):
    facts: List[ResumeFact] = Field(min_length=5, max_length=8)
    overall_llm_score: int = Field(ge=0, le=100, description="Weighted overall score based on all facts combined")
    summary_verdict: str = Field(description="One-line overall verdict, e.g. 'Strong technical profile, needs more quantified achievements'")
    
class SkillMatch(BaseModel):
    skill: str
    status: Literal["matched", "missing", "partial"]
    note: str = Field(description="Short reason, e.g. where in resume it appears, or why it's missing")


class JobMatchAnalysis(BaseModel):
    match_percentage: int = Field(ge=0, le=100, description="Overall semantic fit between resume and job description")
    matched_skills: List[str]
    missing_skills: List[str]
    skill_details: List[SkillMatch] = Field(min_length=3, max_length=12)
    experience_fit: Literal["Under-qualified", "Good fit", "Over-qualified"]
    recommendations: List[str] = Field(min_length=2, max_length=5, description="Specific, actionable suggestions to improve match")
    verdict: str = Field(description="One-line summary of overall fit")
