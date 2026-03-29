"""
app.py — NexHire server
Run with: uvicorn app:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, UploadFile, Form, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio, os, uuid, json
from pathlib import Path

from job_scraper import run_scrape
from main import analyze_resume  

# ── Persistence paths ────────────────────────────────────────────────
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

RESUME_FILE  = DATA_DIR / "resume.json"      # stored resume text + metadata
VIEWED_FILE  = DATA_DIR / "viewed.json"      # job IDs the user has viewed
APPLIED_FILE = DATA_DIR / "applied.json"     # jobs the user has applied to

def _load(path: Path, default):
    try:
        return json.loads(path.read_text()) if path.exists() else default
    except Exception:
        return default

def _save(path: Path, data):
    path.write_text(json.dumps(data, indent=2, default=str))

# ── App ──────────────────────────────────────────────────────────────
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── UI ───────────────────────────────────────────────────────────────
@app.get("/")
async def home():
    return FileResponse("index.html")

# ── SEARCH ───────────────────────────────────────────────────────────
@app.post("/search")
async def search(request: Request):
    body = await request.json()
    try:
        jobs = await asyncio.to_thread(
            run_scrape,
            body.get("search_query"),
            body.get("location"),
            body.get("job_type") or None,
        )
        # tag jobs that were previously viewed or applied
        viewed  = set(_load(VIEWED_FILE,  []))
        applied = {j["id"] for j in _load(APPLIED_FILE, [])}
        for j in jobs:
            j["viewed"]  = j["id"] in viewed
            j["applied"] = j["id"] in applied

        return JSONResponse({"jobs": jobs, "total": len(jobs)})
    except Exception as e:
        print("❌ /search error:", e)
        return JSONResponse({"error": str(e)}, status_code=500)

# ── ANALYZE ──────────────────────────────────────────────────────────
@app.post("/analyze")
async def analyze(file: UploadFile, job_desc: str = Form(...)):
    tmp = f"temp_{uuid.uuid4().hex}.pdf"
    try:
        raw = await file.read()
        with open(tmp, "wb") as f:
            f.write(raw)

        result = await analyze_resume(tmp, job_desc)
        return result
    except Exception as e:
        print("❌ /analyze error:", e)
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

# ── RESUME STORE ─────────────────────────────────────────────────────
@app.post("/resume/save")
async def save_resume(request: Request):
    """Save extracted resume text so we can recommend jobs later."""
    body = await request.json()
    _save(RESUME_FILE, {"text": body.get("text", ""), "skills": body.get("skills", [])})
    return JSONResponse({"ok": True})

@app.get("/resume")
async def get_resume():
    return JSONResponse(_load(RESUME_FILE, {}))

# ── VIEWED JOBS ──────────────────────────────────────────────────────
@app.post("/viewed")
async def mark_viewed(request: Request):
    body    = await request.json()
    job_id  = body.get("id")
    viewed  = _load(VIEWED_FILE, [])
    if job_id and job_id not in viewed:
        viewed.append(job_id)
        _save(VIEWED_FILE, viewed)
    return JSONResponse({"ok": True})

@app.get("/viewed")
async def get_viewed():
    return JSONResponse({"viewed": _load(VIEWED_FILE, [])})

# ── APPLIED JOBS ─────────────────────────────────────────────────────
@app.post("/applied")
async def mark_applied(request: Request):
    body    = await request.json()
    job     = body.get("job")
    applied = _load(APPLIED_FILE, [])
    ids     = {j["id"] for j in applied}
    if job and job.get("id") not in ids:
        applied.append(job)
        _save(APPLIED_FILE, applied)
    return JSONResponse({"ok": True})

@app.delete("/applied/{job_id}")
async def delete_applied(job_id: str):
    applied = [j for j in _load(APPLIED_FILE, []) if j["id"] != job_id]
    _save(APPLIED_FILE, applied)
    return JSONResponse({"ok": True})

@app.get("/applied")
async def get_applied():
    return JSONResponse({"applied": _load(APPLIED_FILE, [])})

# ── Run ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)