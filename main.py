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

Return ONLY valid JSON. No explanation.

IMPORTANT:
- Do NOT invent fake metrics
- Only improve existing content

JOB DESCRIPTION:
{job_desc}

RESUME:
{text}

TASK:
1. match_score
2. missing_skills
3. weaknesses
4. rewritten_points
5. new_points

Return JSON:
{{
  "match_score": number,
  "missing_skills": ["..."],
  "weaknesses": ["..."],
  "rewritten_points": ["..."],
  "new_points": ["..."]
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