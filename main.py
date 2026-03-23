"""
main.py
-------
Pure helper module — resume text extraction and analysis logic.
No FastAPI app here; all endpoints live in app.py.
"""

import pdfplumber, ollama, asyncio, os, json, re, uuid


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


# ── RESUME ANALYSIS ──────────────────────────────────────────────────
async def analyze_resume(pdf_path: str, job_desc: str) -> dict:
    """
    Extracts text from pdf_path, calls phi3:mini via Ollama,
    and returns {"result": {...}, "model_used": "..."}.
    """
    print("📄 Extracting text...")
    text = extract_text(pdf_path)
    text = clean_text(text)[:3000]

    content = f"""<|system|>
You are a strict technical recruiter. Output ONLY a valid JSON object. No prose, no markdown, no explanation before or after the JSON.
<|end|>
<|user|>
STRICT SCORING:
- Score 0 by default. Add points only for skills explicitly in the resume.
- Every missing required skill = -10 points minimum.
- Partial match = half credit only.
- No benefit of doubt. Not stated = missing.
- 90-100: ALL required skills present
- 70-89: most skills present, minor gaps
- 40-69: several key skills missing
- 0-39: many core skills missing

JOB DESCRIPTION:
{job_desc[:1000]}

RESUME:
{text}

Return ONLY this JSON:
{{
  "match_score": <number 0-100>,
  "missing_skills": [
    {{"skill": "skill name", "action": "Build a project using X that does Y — add to Projects section"}}
  ],
  "weaknesses": ["specific technical gap 1", "specific technical gap 2"],
  "line_edits": [
    {{"original": "exact bullet from resume", "improved": "rewritten version targeting JD", "location": "Section > Subsection > bullet number"}}
  ],
  "new_points": [
    {{"point": "new bullet to add", "location": "Section > Subsection > after which bullet"}}
  ]
}}
<|end|>
<|assistant|>"""

    print("🤖 Calling phi3:mini via Ollama...")

    model_to_use = "phi3:mini"
    try:
        ollama.show(model_to_use)
    except Exception:
        print("⚠️ phi3:mini not found, falling back to gemma:2b")
        model_to_use = "gemma:2b"

    response = await asyncio.to_thread(
        lambda: ollama.chat(
            model=model_to_use,
            messages=[{"role": "user", "content": content}],
            options={
                "temperature":    0.1,
                "num_predict":    1000,
                "num_ctx":        2048,
                "top_k":          10,
                "top_p":          0.5,
                "repeat_penalty": 1.1,
            }
        )
    )

    parsed = safe_parse(response.message.content)
    return {"result": parsed, "model_used": model_to_use}