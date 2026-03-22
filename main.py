from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import FileResponse
import pdfplumber
import ollama
import asyncio
import os
import json
import re

app = FastAPI()

@app.get("/")
async def home():
    return FileResponse("index.html")


def clean_text(text):
    return " ".join(text.split())


def extract_text(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text


# 🔥 STRONG JSON PARSER (fixes your biggest bug)
def safe_parse(text):
    try:
        text = text.replace("```json", "").replace("```", "")
        json_text = re.search(r"\{.*\}", text, re.DOTALL).group()
        return json.loads(json_text)
    except:
        return {"raw": text}


@app.post("/analyze")
async def analyze(file: UploadFile, job_desc: str = Form(...)):
    try:
        # save file
        with open("temp.pdf", "wb") as f:
            f.write(await file.read())

        print("📄 Extracting text...")
        text = extract_text("temp.pdf")
        text = clean_text(text)[:1000]

        content = f"""
You are a strict resume editor and recruiter.

Return ONLY valid JSON.

IMPORTANT RULES:
- Do NOT invent any information
- Do NOT add fake metrics
- Only modify existing content
- Focus on improving job relevance

JOB DESCRIPTION:
{job_desc}

RESUME:
{text}

TASK:

1. Extract required skills from JD
2. Extract skills from resume

3. MATCH SCORE:
score = (matched_skills / total_required_skills) * 100

4. missing_skills:
List exact missing technologies

5. weaknesses:
Only technical gaps (no soft skills)

6. line_edits:
- Only edit existing lines
- Format:
  "old": "...",
  "new": "..."

7. redundant_content:
- Identify repeated/low-value text
- Suggest removal

8. rewritten_points:
- Rewrite ONLY existing points
- No fake metrics

9. new_points:
- Based on existing skills
- No hallucination

Return JSON:
{{
  "match_score": number,
  "missing_skills": [],
  "weaknesses": [],
  "line_edits": [],
  "redundant_content": [],
  "rewritten_points": [],
  "new_points": []
}}
"""

        print("🤖 Calling model...")

        response = await asyncio.to_thread(
            lambda: ollama.chat(
                model="mistral",
                messages=[{"role": "user", "content": content}]
            )
        )

        result = response["message"]["content"]
        parsed = safe_parse(result)

        # cleanup
        if os.path.exists("temp.pdf"):
            os.remove("temp.pdf")

        return {"result": parsed}

    except Exception as e:
        print("❌ ERROR:", str(e))
        return {"error": str(e)}