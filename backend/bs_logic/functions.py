
from Schema.pydantic_schema import ResumeData,LLMFactAnalysis,JobMatchAnalysis
import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Optional


load_dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY")
)

def calculate_completeness_score(resume: ResumeData) -> dict:
    score = 0
    max_score = 100
    breakdown = []

    # Contact Info (20 points)
    if resume.email:
        score += 10
        breakdown.append({"check": "Email present", "passed": True, "points": 10})
    else:
        breakdown.append({"check": "Email present", "passed": False, "points": 0})

    if resume.phone:
        score += 10
        breakdown.append({"check": "Phone present", "passed": True, "points": 10})
    else:
        breakdown.append({"check": "Phone present", "passed": False, "points": 0})

    # Skills (20 points)
    if len(resume.skills) >= 5:
        score += 20
        breakdown.append({"check": "At least 5 skills listed", "passed": True, "points": 20})
    elif len(resume.skills) >= 1:
        score += 10
        breakdown.append({"check": "At least 5 skills listed", "passed": False, "points": 10, "note": f"Only {len(resume.skills)} found"})
    else:
        breakdown.append({"check": "At least 5 skills listed", "passed": False, "points": 0})

    # Experience (30 points)
    if len(resume.experience) >= 2:
        score += 30
        breakdown.append({"check": "At least 2 work experiences", "passed": True, "points": 30})
    elif len(resume.experience) == 1:
        score += 15
        breakdown.append({"check": "At least 2 work experiences", "passed": False, "points": 15})
    else:
        breakdown.append({"check": "At least 2 work experiences", "passed": False, "points": 0})

    # Education (15 points)
    if len(resume.education) >= 1:
        score += 15
        breakdown.append({"check": "Education listed", "passed": True, "points": 15})
    else:
        breakdown.append({"check": "Education listed", "passed": False, "points": 0})

    # Summary (15 points)
    if resume.summary and len(resume.summary.strip()) > 20:
        score += 15
        breakdown.append({"check": "Summary/objective present", "passed": True, "points": 15})
    else:
        breakdown.append({"check": "Summary/objective present", "passed": False, "points": 0})

    return {
        "score": score,
        "max_score": max_score,
        "percentage": round((score / max_score) * 100, 1),
        "breakdown": breakdown
    }
    
    
    
# ---------- Tool Definition (OpenAI-style format) ----------

resume_tool = {
    "type": "function",
    "function": {
        "name": "extract_resume_data",
        "description": "Extract structured information from resume text",
        "parameters": ResumeData.model_json_schema()
    }
}

fact_analysis_tool = {
    "type": "function",
    "function": {
        "name": "generate_fact_analysis",
        "description": "Generate a fact-based quality analysis of a resume across multiple categories",
        "parameters": LLMFactAnalysis.model_json_schema()
    }
}

match_tool = {
    "type": "function",
    "function": {
        "name": "generate_job_match_analysis",
        "description": "Analyze how well a resume matches a job description",
        "parameters": JobMatchAnalysis.model_json_schema()
    }
}

def structure_resume(cleaned_text: str) -> ResumeData:
    response = client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b",
        # model="meta/llama-3.1-8b-instruct",
        messages=[{
            "role": "user",
            "content": f"""Extract resume information from the following text.
If a field is not present in the resume, leave it empty — do not invent or guess information.

Resume text:
{cleaned_text}"""
        }],
        tools=[resume_tool],
        tool_choice={"type": "function", "function": {"name": "extract_resume_data"}},
        temperature=0,
        max_completion_tokens=1500
    )

    message = response.choices[0].message

    if not message.tool_calls:
        raise ValueError("Model ne tool call nahi kiya, response check karo")

    tool_call = message.tool_calls[0]
    parsed_args = json.loads(tool_call.function.arguments)

    # Pydantic validation - safety layer
    validated_data = ResumeData(**parsed_args)
    return validated_data

def generate_llm_fact_score(resume: ResumeData, score_report: dict) -> LLMFactAnalysis:
    system_prompt = """You are an expert technical resume reviewer with 10+ years of experience evaluating resumes for software engineering and ML roles at top companies.

Your job: Analyze the given resume data and produce 5 to 8 concrete, genuine facts about resume quality across different categories (e.g. Skills, Education, Experience, Projects, Achievements, ATS Formatting, Contact Info).

Rules for each fact:
- category: a short label for what is being evaluated.
- rating: one of Excellent, Good, Average, or Poor — based strictly on the actual content, not assumptions.
- score: a 0-100 numeric score for that category.
- justification: must reference specific, real content from the resume (a real project name, a real skill, a real degree) — never a generic statement.

Special evaluation guidance:
- Education: an M.Tech or PhD in Computer Science / related field should be rated Excellent. A single Bachelor's in progress with no advanced degree should be rated Average or Good depending on relevance and institution.
- Experience: rate based on depth, real ownership, and impact shown — not just years of experience.
- Projects: rate based on technical complexity and whether outcomes/impact are quantified.
- Do not invent facts. Do not assume anything not present in the resume data.

Finally, compute an overall_llm_score (0-100) that reflects your holistic judgment across all facts, and a one-line summary_verdict.

You must call the generate_fact_analysis tool with your結果. Do not output any reasoning or thinking text — respond only through the tool call."""

    user_prompt = f"""Resume data:
{resume.model_dump_json(indent=2)}

Rule-based completeness score (for reference only, do not just repeat this): {score_report['percentage']}%

Generate the fact-based analysis now."""

    response = client.chat.completions.create(
        # model="nvidia/nemotron-3-super-120b-a12b",
        model="meta/llama-3.1-8b-instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        tools=[fact_analysis_tool],
        tool_choice={"type": "function", "function": {"name": "generate_fact_analysis"}},
        temperature=0.3,
        max_completion_tokens=1200,
        extra_body={"chat_template_kwargs": {"enable_thinking": True}}
    )

    message = response.choices[0].message

    if not message.tool_calls:
        raise ValueError("Model ne tool call nahi kiya, response check karo")

    tool_call = message.tool_calls[0]
    parsed_args = json.loads(tool_call.function.arguments)

    validated = LLMFactAnalysis(**parsed_args)
    return validated

def generate_qualitative_feedback(resume: ResumeData, score_report: dict) -> str:
    weak_areas = [b['check'] for b in score_report['breakdown'] if not b['passed']]
    strong_areas = [b['check'] for b in score_report['breakdown'] if b['passed']]

    system_prompt = """You are an expert technical resume reviewer with 10+ years of experience helping software engineers and developers improve their resumes for ATS systems and human recruiters.

Your job:
- Analyze the given structured resume data and its completeness score.
- Give specific, actionable feedback — never generic advice like "improve your resume" or "add more details".
- Every suggestion must reference something concrete from the actual resume content (a real project, skill, or experience entry).
- Focus primarily on the weak areas provided, but you may also suggest improvements to existing strong areas if the content quality can be sharper (e.g. vague descriptions, missing metrics/numbers).
- Prefer suggestions that are quick to act on over vague long-term advice.

Rules:
- Do not invent or assume facts not present in the resume data.
- Do not repeat the score or restate the resume back to the user.
- Do not use markdown headers or bold text — plain bullet points only.
- Keep the entire response under 150 words.
- Output exactly 3 to 4 bullet points, nothing else."""

    user_prompt = f"""Resume data:
{resume.model_dump_json(indent=2)}

Completeness score: {score_report['percentage']}%
Strong areas: {strong_areas}
Weak areas: {weak_areas}

Give your improvement suggestions now."""

    response = client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.5,
        max_completion_tokens=400
    )

    return response.choices[0].message.content


def calculate_keyword_overlap(resume: ResumeData, job_description: str) -> dict:
    jd_lower = job_description.lower()
    
    # Resume skills ko normalize karo (lowercase, extra spaces hatao)
    resume_skills_normalized = [skill.lower().strip() for skill in resume.skills]

    matched = []
    missing_candidates = []

    for skill in resume_skills_normalized:
        # Simple substring check - skill JD text mein mention hua ya nahi
        if skill in jd_lower:
            matched.append(skill)

    overlap_percentage = round((len(matched) / len(resume_skills_normalized)) * 100, 1) if resume_skills_normalized else 0

    return {
        "matched_count": len(matched),
        "total_resume_skills": len(resume_skills_normalized),
        "keyword_overlap_percentage": overlap_percentage,
        "matched_keywords": matched
    }
    
    
def generate_llm_job_match(resume: ResumeData, job_description: str, keyword_overlap: dict) -> JobMatchAnalysis:
    system_prompt = """You are an expert technical recruiter who evaluates how well a candidate's resume matches a given job description.

Your job:
- Compare the resume data against the job description semantically — not just exact keyword matching.
- Recognize equivalent or related skills (e.g. "React.js" and "React" are the same; "Node.js" implies JavaScript backend experience).
- Identify skills required by the job description that are genuinely missing from the resume.
- Assess experience level fit — whether the candidate's years of experience and project depth match what the role expects.
- Give specific, actionable recommendations — reference actual resume content when suggesting improvements.

Rules:
- Do not invent skills or experience not present in the resume data.
- Be honest and realistic in match_percentage — do not inflate it to be encouraging.
- skill_details should cover the most important skills from the job description, not every minor keyword.
- You must respond only through the generate_job_match_analysis tool call."""

    user_prompt = f"""Resume data:
{resume.model_dump_json(indent=2)}

Job description:
{job_description}

Reference — basic keyword overlap already calculated: {keyword_overlap['keyword_overlap_percentage']}% of resume skills appear literally in the job description text. Use this as a reference point, but your semantic judgment should be the primary basis for match_percentage.

Generate the job match analysis now."""

    response = client.chat.completions.create(
        model="meta/llama-3.1-8b-instruct",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        tools=[match_tool],
        tool_choice={"type": "function", "function": {"name": "generate_job_match_analysis"}},
        temperature=0.3,
        max_completion_tokens=1200
    )

    message = response.choices[0].message

    if not message.tool_calls:
        raise ValueError("Model ne tool call nahi kiya, response check karo")

    tool_call = message.tool_calls[0]
    parsed_args = json.loads(tool_call.function.arguments)

    return JobMatchAnalysis(**parsed_args)