"""
Resume text extraction and AI analysis using Gemini API with ReAct-style reasoning.
Imported by app.py — no FastAPI app defined here.
"""

# ── CONFIG ───────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

import pdfplumber, asyncio, os, json, re
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=GEMINI_API_KEY)


# ── TEXT HELPERS ─────────────────────────────────────────────────────
def clean_text(text: str) -> str:
    return " ".join(text.split())


def extract_text(file_path: str) -> str:
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text


def safe_parse(text: str) -> dict:
    try:
        text = text.replace("```json", "").replace("```", "")
        json_text = re.search(r"\{.*\}", text, re.DOTALL).group()
        return json.loads(json_text)
    except Exception:
        return {"raw": text}


# ── REACT PROMPT ─────────────────────────────────────────────────────
REACT_SYSTEM = """You are an expert technical recruiter and career coach.
You use a structured ReAct (Reason → Act → Observe) approach before scoring:

Step 1 — THOUGHT: Carefully read the job description. List the 5-8 core required skills/experiences.
Step 2 — THOUGHT: Carefully read the resume. Note skills, projects, experience level, and domain.
Step 3 — OBSERVE: Match each JD requirement against the resume. For each, note: PRESENT / PARTIAL / ABSENT.
Step 4 — REASON: Calculate a fair score. Start at 60 for any relevant candidate.
         +5 per PRESENT match, +2 per PARTIAL match, -5 per ABSENT core requirement.
         Cap between 20 and 100.
Step 5 — ACT: Generate specific, actionable resume improvements.

CRITICAL RULES for improvements:
- line_edits: Find ACTUAL bullet points from the resume and rewrite them to better match the JD.
  Each edit must have the EXACT original text and a stronger rewritten version with metrics/impact.
- new_points: Suggest entirely NEW bullet points the candidate could add if they have relevant experience.
  These should be concrete and targeted to the JD.
- missing_skills: Only list skills truly absent from the resume. Give a concrete 2-week action to gain each.
- weaknesses: Be specific and constructive, not generic. Reference actual resume content.

Output ONLY valid JSON — no prose, no markdown fences before or after."""


def build_react_prompt(job_desc: str, resume_text: str) -> str:
    return f"""JOB DESCRIPTION:
{job_desc[:1500]}

RESUME:
{resume_text[:2500]}

Follow the ReAct steps internally, then output ONLY this JSON:
{{
  "react_trace": {{
    "jd_requirements": ["req1", "req2", "..."],
    "resume_strengths": ["strength1", "strength2", "..."],
    "match_analysis": [
      {{"requirement": "skill/exp", "status": "PRESENT|PARTIAL|ABSENT", "evidence": "what was found or not"}}
    ],
    "scoring_rationale": "Brief explanation of how the score was calculated"
  }},
  "match_score": <number 20-100>,
  "missing_skills": [
    {{"skill": "skill name", "action": "Specific 2-week actionable step to gain this skill"}}
  ],
  "weaknesses": ["specific constructive weakness 1", "specific constructive weakness 2"],
  "line_edits": [
    {{
      "original": "exact bullet or phrase from the resume as written",
      "improved": "stronger rewritten version with metrics and impact targeting the JD",
      "location": "Section name > approximate position (e.g. Experience > 2nd bullet)"
    }}
  ],
  "new_points": [
    {{
      "point": "New bullet point to add (concrete, JD-targeted)",
      "location": "Section name > where to insert it"
    }}
  ]
}}"""


# ── RESUME ANALYSIS ──────────────────────────────────────────────────
async def analyze_resume(pdf_path: str, job_desc: str) -> dict:
    """
    Extracts text from pdf_path, calls Gemini API with ReAct reasoning,
    returns {"result": {...}, "model_used": "...", "resume_text": "..."}.
    """
    print("📄 Extracting text...")
    text = extract_text(pdf_path)
    text = clean_text(text)[:3000]

    if not text.strip():
        return {
            "result": {"raw": "Could not extract text from PDF. Make sure it is a text-based PDF, not a scanned image."},
            "model_used": "gemini",
            "resume_text": ""
        }

    prompt = build_react_prompt(job_desc, text)

    print("🤖 Calling Gemini API with ReAct reasoning...")

    model_name = "gemini-3-flash-preview"
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        full_prompt = REACT_SYSTEM + "\n\n" + prompt

        response = await asyncio.to_thread(
            lambda: client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=full_prompt
            )
        )

        raw_text = response.text
        parsed = safe_parse(raw_text)

        # Ensure score is never 0 — fallback to 45 if parsing failed
        if "match_score" not in parsed or parsed.get("match_score", 0) == 0:
            parsed["match_score"] = 45
            if "raw" in parsed:
                print("⚠️  JSON parse failed, raw response:", raw_text[:300])

        return {"result": parsed, "model_used": model_name, "resume_text": text}

    except Exception as e:
        print(f"❌ Gemini API error: {e}")
        return {
            "result": {
                "error": str(e),
                "match_score": 0,
                "missing_skills": [],
                "weaknesses": ["Could not connect to Gemini API. Check your GEMINI_API_KEY."],
                "line_edits": [],
                "new_points": []
            },
            "model_used": model_name,
            "resume_text": text
        }