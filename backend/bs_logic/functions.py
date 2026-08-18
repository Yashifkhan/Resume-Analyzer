
from Schema.pydantic_schema import ResumeData,LLMFactAnalysis,JobMatchAnalysis
import os
import re
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
    
# skills matched 
SKILL_ALIASES = {
    # --- JS/Frontend frameworks ---
    "react.js": "react",
    "reactjs": "react",
    "react native": "reactnative",
    "vue.js": "vue",
    "vuejs": "vue",
    "next.js": "next",
    "nextjs": "next",
    "nuxt.js": "nuxt",
    "angular.js": "angular",
    "angularjs": "angular",
    "svelte.js": "svelte",
    "jquery": "jquery",
    "tailwindcss": "tailwind",
    "tailwind css": "tailwind",
    "bootstrap": "bootstrap",
    "typescript": "typescript",
    "javascript": "javascript",
    "es6": "javascript",
    "js": "javascript",
"ts": "typescript",

    # --- Backend / Node ---
    "node.js": "node",
    "nodejs": "node",
    "express.js": "express",
    "expressjs": "express",
    "nest.js": "nestjs",
    "socket.io": "socket",
    "graphql": "graphql",
    "rest api": "restapi",
    "restful api": "restapi",
    "fastapi": "fastapi",
    "django": "django",
    "django rest framework": "drf",
    "drf": "drf",
    "flask": "flask",
    "spring boot": "springboot",
    "spring": "springboot",
    ".net": "dotnet",
    "asp.net": "dotnet",
    "laravel": "laravel",

    # --- Languages ---
    "python": "python",
    "python3": "python",
    "java": "java",
    "c++": "cpp",
    "c#": "csharp",
    "golang": "go",
    "go lang": "go",
    "php": "php",
    "ruby": "ruby",
    "kotlin": "kotlin",
    "swift": "swift",

    # --- Databases ---
    "mongodb": "mongo",
    "mongo db": "mongo",
    "postgresql": "postgres",
    "postgre sql": "postgres",
    "mysql": "mysql",
    "sqlite": "sqlite",
    "redis": "redis",
    "firebase": "firebase",
    "firestore": "firebase",
    "dynamodb": "dynamodb",
    "elasticsearch": "elasticsearch",

    # --- Cloud / DevOps ---
    "amazon web services": "aws",
    "aws": "aws",
    "google cloud platform": "gcp",
    "gcp": "gcp",
    "microsoft azure": "azure",
    "azure": "azure",
    "docker": "docker",
    "kubernetes": "kubernetes",
    "k8s": "kubernetes",
    "ci/cd": "cicd",
    "ci cd": "cicd",
    "jenkins": "jenkins",
    "github actions": "githubactions",
    "terraform": "terraform",
    "nginx": "nginx",
    "linux": "linux",

    # --- ML / AI / Data (tumhare domain ke liye important) ---
    "machine learning": "ml",
    "ml": "ml",
    "deep learning": "deeplearning",
    "artificial intelligence": "ai",
    "generative ai": "genai",
    "gen ai": "genai",
    "genai": "genai",
    "large language models": "llm",
    "llms": "llm",
    "llm": "llm",
    "natural language processing": "nlp",
    "nlp": "nlp",
    "computer vision": "cv",
    "opencv": "cv",
    "scikit-learn": "sklearn",
    "scikit learn": "sklearn",
    "sklearn": "sklearn",
    "tensorflow": "tensorflow",
    "pytorch": "pytorch",
    "pandas": "pandas",
    "numpy": "numpy",
    "xgboost": "xgboost",
    "langchain": "langchain",
    "hugging face": "huggingface",
    "huggingface": "huggingface",
    "openai api": "openai",
    "openai": "openai",
    "rag": "rag",
    "retrieval augmented generation": "rag",
    "vector database": "vectordb",
    "vector db": "vectordb",
    "pinecone": "vectordb",
    "chromadb": "vectordb",
    "faiss": "vectordb",

    # --- Version control / tools ---
    "git": "git",
    "github": "github",
    "gitlab": "gitlab",
    "postman": "postman",
    "figma": "figma",
    "jira": "jira",
    "webpack": "webpack",
    "vite": "vite",
    "npm": "npm",
    "yarn": "yarn",
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

    
validation_tool = {
    "type": "function",
    "function": {
        "name": "classify_document",
        "description": "Classify whether the given document text is a resume/CV",
        "parameters": {
            "type": "object",
            "properties": {
                "is_resume": {"type": "boolean"},
                "confidence": {"type": "number", "description": "0 to 1"},
                "reason": {"type": "string", "description": "Short reason for the decision"},
                "document_type_guess": {"type": "string", "description": "e.g. 'invoice', 'resume', 'article', 'blank'"}
            },
            "required": ["is_resume", "confidence", "reason", "document_type_guess"]
        }
    }
}



def structure_resume(cleaned_text: str) -> ResumeData:
    response = client.chat.completions.create(
        # model="nvidia/nemotron-3-super-120b-a12b",
        model="meta/llama-3.1-8b-instruct",
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
        # model="nvidia/nemotron-3-super-120b-a12b",
        model="meta/llama-3.1-8b-instruct",
        
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.5,
        max_completion_tokens=400
    )

    return response.choices[0].message.content

def normalize_text(text: str) -> set:
    text = text.lower()
    for phrase, canonical in sorted(SKILL_ALIASES.items(), key=lambda x: -len(x[0])):
        pattern = r'\b' + re.escape(phrase) + r'\b'
        text = re.sub(pattern, canonical, text)

    text = re.sub(r"[^a-z0-9\s]", " ", text)  # baaki punctuation clean
    return set(text.split())


def calculate_keyword_overlap(resume: ResumeData, job_description: str) -> dict:
    
    jd_tokens = normalize_text(job_description)

    matched = []
    for raw_skill in resume.skills:
        skill_tokens = normalize_text(raw_skill)
        if skill_tokens & jd_tokens:   # koi bhi common token mila to match
            matched.append(raw_skill)

    total = len(resume.skills)
    overlap_percentage = round((len(matched) / total) * 100, 1) if total else 0

    return {
        "matched_count": len(matched),
        "total_resume_skills": total,
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


# add the validation function check the file is resume or not  
RESUME_SECTION_KEYWORDS = [
    "experience", "education", "skills", "projects",
    "objective", "summary", "certification", "achievements",
    "work history", "employment"
]

# mannuly check 
def heuristic_resume_check(text: str) -> dict:
    text_lower = text.lower()
    word_count = len(text.split())

    has_email = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text))
    has_phone = bool(re.search(r"(\+?\d{1,3}[-.\s]?)?\d{10}", text))
    section_hits = sum(1 for kw in RESUME_SECTION_KEYWORDS if kw in text_lower)

    # Score based scoring — tune thresholds with real test files
    score = 0
    if word_count >= 50: score += 1
    if has_email: score += 1
    if has_phone: score += 1
    if section_hits >= 2: score += 2

    return {
        "passed": score >= 3,
        "score": score,
        "word_count": word_count,
        "section_hits": section_hits
    }

# llm check 
def llm_validate_resume(text: str) -> dict:
    response = client.chat.completions.create(
        model="meta/llama-3.1-8b-instruct",  # tumhara jo bhi model use ho raha hai
        messages=[
            {"role": "system", "content": "You are a strict document classifier. Determine if the text is from a resume/CV."},
            {"role": "user", "content": f"Document text:\n\n{text[:3000]}"}  # truncate, poora text bhejne ki zaroorat nahi
        ],
        tools=[validation_tool],
        tool_choice={"type": "function", "function": {"name": "classify_document"}}
    )

    tool_call = response.choices[0].message.tool_calls[0]
    import json
    return json.loads(tool_call.function.arguments)


def validate_resume(cleaned: str) -> dict:
    # Layer 1: heuristic pre-check (no LLM cost)
    heuristic = heuristic_resume_check(cleaned)
    if not heuristic["passed"]:
        return {
            "is_resume": False,
            "confidence": 0.0,
            "reason": "Missing resume signals (email/phone/sections not found)",
            "stage": "heuristic_check"
        }

    # Layer 2: LLM semantic check (only runs if heuristic passes)
    llm_result = llm_validate_resume(cleaned)
    llm_result["stage"] = "llm_check"
    return llm_result