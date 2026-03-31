"""
Resume text extraction and AI analysis using Gemini API with ReAct-style reasoning.
Imported by app.py — no FastAPI app defined here.
"""

# ── CONFIG ───────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

import asyncio, json, os, re

import pdfplumber
from google import genai

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
client = None


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


def get_gemini_client():
    global client
    load_dotenv(override=True)
    api_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()

    if not api_key:
        raise RuntimeError(
            "Gemini API key not found. Set GEMINI_API_KEY in your .env file and restart the server."
        )

    if client is None:
        client = genai.Client(api_key=api_key)

    return client


def call_gemini(prompt: str) -> str:
    """Synchronous Gemini call — always run via asyncio.to_thread."""
    response = get_gemini_client().models.generate_content(
        model=MODEL,
        contents=prompt,
    )
    return response.text or str(response)


# ── REACT SYSTEM PROMPT ───────────────────────────────────────────────
REACT_SYSTEM = """You are an expert technical recruiter and career coach.
You use a structured ReAct (Reason -> Act -> Observe) approach before scoring:

Step 1 - THOUGHT: Carefully read the job description. List the 5-8 core required skills/experiences.
Step 2 - THOUGHT: Carefully read the resume. Note skills, projects, experience level, and domain.
Step 3 - OBSERVE: Match each JD requirement against the resume. For each, note: PRESENT / PARTIAL / ABSENT.
Step 4 - REASON: Calculate a fair score. Start at 60 for any relevant candidate.
         +5 per PRESENT match, +2 per PARTIAL match, -5 per ABSENT core requirement.
         Cap between 20 and 100.
Step 5 - ACT: Generate specific, actionable resume improvements.

CRITICAL RULES for improvements:
- line_edits: Find ACTUAL bullet points from the resume and rewrite them to better match the JD.
  Each edit must have the EXACT original text and a stronger rewritten version with metrics/impact.
- new_points: Suggest entirely NEW bullet points the candidate could add if they have relevant experience.
  These should be concrete and targeted to the JD.
- missing_skills: Only list skills truly absent from the resume. Give a concrete 2-week action to gain each.
- weaknesses: Be specific and constructive, not generic. Reference actual resume content.

Output ONLY valid JSON - no prose, no markdown fences before or after."""


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
    print("📄 Extracting text...")
    text = extract_text(pdf_path)
    text = clean_text(text)[:3000]

    if not text.strip():
        return {
            "result": {"raw": "Could not extract text from PDF. Make sure it is a text-based PDF, not a scanned image."},
            "model_used": MODEL,
            "resume_text": ""
        }

    full_prompt = REACT_SYSTEM + "\n\n" + build_react_prompt(job_desc, text)
    print("🤖 Calling Gemini API with ReAct reasoning...")

    try:
        raw_text = await asyncio.to_thread(call_gemini, full_prompt)
        parsed   = safe_parse(raw_text)

        if "match_score" not in parsed or parsed.get("match_score", 0) == 0:
            parsed["match_score"] = 45
            if "raw" in parsed:
                print("⚠️  JSON parse failed, raw response:", raw_text[:300])

        return {"result": parsed, "model_used": MODEL, "resume_text": text}

    except Exception as e:
        print(f"❌ Gemini API error: {e}")
        return {
            "result": {
                "error": str(e),
                "match_score": 0,
                "missing_skills": [],
                "weaknesses": ["Gemini request failed. Check your API key, model name, and restart the server."],
                "line_edits": [],
                "new_points": []
            },
            "model_used": MODEL,
            "resume_text": text
        }


# ── RECRUITER FINDER ─────────────────────────────────────────────────
async def find_recruiters(company: str, job_title: str) -> dict:
    print(f"🔍 Finding recruiters at {company} for {job_title}...")

    # Pre-compute URL strings — no method calls inside f-string braces
    company_plus = company.replace(' ', '+')
    company_enc  = company.replace(' ', '%20')
    role_plus    = job_title.replace(' ', '+')
    li_recruiter = f"https://www.linkedin.com/search/results/people/?keywords=technical+recruiter+{company_plus}&origin=GLOBAL_SEARCH_HEADER"
    li_hr        = f"https://www.linkedin.com/search/results/people/?keywords=HR+manager+{company_plus}&origin=GLOBAL_SEARCH_HEADER"
    li_eng       = f"https://www.linkedin.com/search/results/people/?keywords=engineering+manager+{company_plus}&origin=GLOBAL_SEARCH_HEADER"
    li_people    = f"https://www.linkedin.com/company/{company_plus.lower().replace('+', '-')}/people/"
    google_recruiter = f"https://www.google.com/search?q=site%3Alinkedin.com%2Fin+%22{company_plus}%22+recruiter"
    google_hr = f"https://www.google.com/search?q=site%3Alinkedin.com%2Fin+%22{company_plus}%22+%22HR%22"
    google_eng = f"https://www.google.com/search?q=site%3Alinkedin.com%2Fin+%22{company_plus}%22+%22{role_plus}%22"

    prompt = f"""You are a professional network researcher helping a job seeker find recruiters and hiring managers.

Company: {company}
Role being applied for: {job_title}

Infer the likely company domain from the company name (e.g. "Google" -> "google.com", "Meta" -> "meta.com").
Do not pretend you know a real private email unless it is clearly a public mailbox pattern. Mark guessed emails clearly.
Prefer actionable profile-search links over vague advice.
Return ONLY this JSON (no markdown, no prose):
{{
  "company_domain": "example.com",
  "company_people_url": "{li_people}",
  "email_formats": [
    {{"format": "firstname.lastname@domain.com", "example": "john.smith@example.com"}},
    {{"format": "firstname@domain.com",          "example": "john@example.com"}},
    {{"format": "f.lastname@domain.com",         "example": "j.smith@example.com"}}
  ],
  "suggested_contacts": [
    {{
      "role": "Technical Recruiter",
      "why": "Directly handles {job_title} hiring and screens candidates",
      "linkedin_search_url": "{li_recruiter}",
      "google_search_url": "{google_recruiter}",
      "linkedin_search_label": "Search Technical Recruiters at {company}",
      "email_guess": "recruiting@example.com",
      "email_type": "guessed",
      "search_hint": "Look for recruiters or talent partners with {company} in the headline",
      "outreach_priority": "HIGH"
    }},
    {{
      "role": "HR Manager",
      "why": "Oversees talent acquisition and can route your application",
      "linkedin_search_url": "{li_hr}",
      "google_search_url": "{google_hr}",
      "linkedin_search_label": "Search HR Managers at {company}",
      "email_guess": "hr@example.com",
      "email_type": "guessed",
      "search_hint": "Prioritise HRBP, talent acquisition, or people operations titles",
      "outreach_priority": "MEDIUM"
    }},
    {{
      "role": "Engineering Manager",
      "why": "Likely the direct hiring manager for {job_title} roles",
      "linkedin_search_url": "{li_eng}",
      "google_search_url": "{google_eng}",
      "linkedin_search_label": "Search Engineering Managers at {company}",
      "email_guess": "engineering@example.com",
      "email_type": "guessed",
      "search_hint": "Look for the manager of the team closest to {job_title}",
      "outreach_priority": "HIGH"
    }}
  ],
  "pro_tips": [
    "Open the LinkedIn People page first, then search titles like recruiter, talent, HR, engineering manager, or the exact team name",
    "Use Hunter, Apollo, RocketReach, or the company careers page to verify whether a guessed pattern is real before sending",
    "If the application confirmation email comes from a person instead of noreply, reply there first because that address is already proven"
  ]
}}
IMPORTANT: Replace all example.com placeholders with the real inferred domain for {company}.
Replace all placeholder emails with realistic guesses using that domain.
Output ONLY the JSON object, nothing else."""

    try:
        raw    = await asyncio.to_thread(call_gemini, prompt)
        parsed = safe_parse(raw)

        # Ensure every contact has a valid LinkedIn URL
        for c in parsed.get("suggested_contacts", []):
            url = c.get("linkedin_search_url", "")
            if not url or "keywords=" not in url:
                role_enc = c.get("role", "recruiter").replace(' ', '%20')
                c["linkedin_search_url"] = (
                    f"https://www.linkedin.com/search/results/people/"
                    f"?keywords={role_enc}%20{company_enc}&origin=GLOBAL_SEARCH_HEADER"
                )
            c.setdefault("email_type", "guessed")
            c.setdefault("search_hint", f"Search LinkedIn for {c.get('role', 'recruiter')} at {company}")
            if not c.get("google_search_url"):
                role_plus_generic = c.get("role", "recruiter").replace(' ', '+')
                c["google_search_url"] = f"https://www.google.com/search?q=site%3Alinkedin.com%2Fin+%22{company_plus}%22+{role_plus_generic}"
        parsed.setdefault("company_people_url", li_people)
        return parsed

    except Exception as e:
        print(f"❌ find_recruiters error: {e}")
        domain = company.lower().replace(' ', '') + ".com"
        return {
            "company_domain": domain,
            "email_formats": [
                {"format": "firstname.lastname@domain.com", "example": f"jane.doe@{domain}"},
                {"format": "firstname@domain.com",          "example": f"jane@{domain}"},
            ],
            "suggested_contacts": [
                {
                    "role": "Technical Recruiter",
                    "why": f"Handles {job_title} hiring at {company}",
                    "linkedin_search_url": f"https://www.linkedin.com/search/results/people/?keywords=recruiter+{company_plus}&origin=GLOBAL_SEARCH_HEADER",
                    "google_search_url": google_recruiter,
                    "linkedin_search_label": f"Search Recruiters at {company}",
                    "email_guess": f"recruiting@{domain}",
                    "email_type": "guessed",
                    "search_hint": "Look for recruiter, talent acquisition, or hiring titles",
                    "outreach_priority": "HIGH",
                },
                {
                    "role": "HR Manager",
                    "why": f"Oversees talent acquisition at {company}",
                    "linkedin_search_url": f"https://www.linkedin.com/search/results/people/?keywords=HR+{company_plus}&origin=GLOBAL_SEARCH_HEADER",
                    "google_search_url": google_hr,
                    "linkedin_search_label": f"Search HR at {company}",
                    "email_guess": f"hr@{domain}",
                    "email_type": "guessed",
                    "search_hint": "Try people operations, talent partner, or HRBP titles too",
                    "outreach_priority": "MEDIUM",
                },
            ],
            "company_people_url": li_people,
            "pro_tips": [
                f"Open the LinkedIn People page for {company} and filter by recruiter, HR, or manager titles",
                "Use Hunter or Apollo to verify an email before sending",
                f"(Gemini error: {str(e)})",
            ],
        }


# ── OUTREACH MESSAGE GENERATOR ────────────────────────────────────────
async def generate_outreach(
    recruiter:   dict,
    job_title:   str,
    company:     str,
    job_desc:    str,
    resume_text: str,
    analysis:    dict,
    tone:        str = "professional",
) -> dict:
    rec_role       = recruiter.get("role", "Recruiter")
    score          = analysis.get("match_score", "")
    strengths      = analysis.get("react_trace", {}).get("resume_strengths", [])
    strengths_text = ", ".join(strengths[:3]) if strengths else "not provided"
    missing        = [
        s.get("skill", "") if isinstance(s, dict) else s
        for s in analysis.get("missing_skills", [])
    ][:2]
    gaps_text = ", ".join(missing) if missing else "none"

    tone_guide = {
        "professional": "formal, concise, and polished - like a cover letter but shorter",
        "friendly":     "warm, conversational, and personable - like reaching out to a mutual connection",
        "bold":         "confident, direct, and memorable - lead with your biggest achievement",
    }.get(tone, "formal, concise, and polished")

    print(f"✍️  Generating {tone} outreach for {rec_role} at {company}...")

    prompt = f"""You are an expert career coach writing highly personalised job outreach messages.

TARGET CONTACT:
- Role: {rec_role}
- Company: {company}

JOB BEING APPLIED FOR: {job_title}

JOB DESCRIPTION SUMMARY:
{job_desc[:600]}

CANDIDATE RESUME SUMMARY:
{resume_text[:500]}

RESUME-JD MATCH SCORE: {score}%
TOP STRENGTHS: {strengths_text}
SKILL GAPS (do not highlight these): {gaps_text}
TONE: {tone_guide}

Write TWO outreach messages. Be specific - mention the company name, role, and 1-2 concrete skills or achievements from the resume.
Do NOT use generic openers like "I hope this finds you well" or "I came across your profile".
Keep LinkedIn DM under 300 characters. Keep email body under 150 words.

Return ONLY this JSON (no markdown, no prose):
{{
  "linkedin_dm": "Short LinkedIn connection message under 300 chars - get straight to the point",
  "email_subject": "Compelling specific email subject line",
  "email_body": "Full cold email body under 150 words - include greeting and sign off as [Your Name]",
  "personalisation_tips": [
    "Specific actionable tip to personalise before sending",
    "Second personalisation tip"
  ]
}}"""

    try:
        raw    = await asyncio.to_thread(call_gemini, prompt)
        parsed = safe_parse(raw)
        return parsed
    except Exception as e:
        print(f"❌ generate_outreach error: {e}")
        return {"error": str(e)}
