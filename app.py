"""
app.py — NexHire server
Run with: uvicorn app:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, UploadFile, Form, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio, os, uuid, json, re
from pathlib import Path

from job_scraper import run_scrape
from main import analyze_resume, find_recruiters, generate_outreach

# ── Persistence paths ────────────────────────────────────────────────
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

RESUME_FILE  = DATA_DIR / "resume.json"      # stored resume text + metadata
VIEWED_FILE  = DATA_DIR / "viewed.json"      # job IDs the user has viewed
APPLIED_FILE = DATA_DIR / "applied.json"     # jobs the user has applied to
RESUME_UPLOAD_DIR = DATA_DIR / "resumes"
RESUME_UPLOAD_DIR.mkdir(exist_ok=True)

def _load(path: Path, default):
    try:
        return json.loads(path.read_text()) if path.exists() else default
    except Exception:
        return default

def _save(path: Path, data):
    path.write_text(json.dumps(data, indent=2, default=str))


def _safe_stem(name: str) -> str:
    stem = Path(name or "resume").stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    return stem or "resume"


def _list_saved_resumes():
    resumes = []
    for path in sorted(RESUME_UPLOAD_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True):
        resumes.append({
            "id": path.name,
            "name": path.stem,
            "filename": path.name,
            "updated_at": path.stat().st_mtime,
        })
    return resumes


def _resolve_saved_resume(resume_id: str) -> Path | None:
    if not resume_id:
        return None
    candidate = RESUME_UPLOAD_DIR / Path(resume_id).name
    if candidate.exists() and candidate.suffix.lower() == ".pdf":
        return candidate
    return None


async def _persist_resume_upload(file: UploadFile) -> tuple[Path | None, bytes]:
    raw = await file.read()
    if not raw:
        return None, raw

    filename = file.filename or "resume.pdf"
    target = RESUME_UPLOAD_DIR / f"{_safe_stem(filename)}_{uuid.uuid4().hex[:8]}.pdf"
    target.write_bytes(raw)
    return target, raw

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
        page = max(int(body.get("page", 1) or 1), 1)
        page_size = max(min(int(body.get("page_size", 30) or 30), 50), 1)

        result = await asyncio.to_thread(
            run_scrape,
            body.get("search_query"),
            body.get("location"),
            body.get("job_type") or None,
            page,
            page_size,
        )
        # tag jobs that were previously viewed or applied
        viewed  = set(_load(VIEWED_FILE,  []))
        applied = {j["id"] for j in _load(APPLIED_FILE, [])}
        for j in result["jobs"]:
            j["viewed"]  = j["id"] in viewed
            j["applied"] = j["id"] in applied

        return JSONResponse(result)
    except Exception as e:
        print("❌ /search error:", e)
        return JSONResponse({"error": str(e)}, status_code=500)

# ── ANALYZE ──────────────────────────────────────────────────────────
@app.post("/analyze")
async def analyze(
    file: UploadFile | None = None,
    job_desc: str = Form(...),
    saved_resume_id: str = Form(""),
):
    tmp = f"temp_{uuid.uuid4().hex}.pdf"
    try:
        if file and file.filename:
            _, raw = await _persist_resume_upload(file)
            Path(tmp).write_bytes(raw)
        else:
            saved_resume = _resolve_saved_resume(saved_resume_id)
            if not saved_resume:
                return JSONResponse({"error": "Choose a saved resume or upload a PDF first."}, status_code=400)
            Path(tmp).write_bytes(saved_resume.read_bytes())

        result = await analyze_resume(tmp, job_desc)
        return result
    except Exception as e:
        print("❌ /analyze error:", e)
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


@app.get("/resumes")
async def list_resumes():
    return JSONResponse({"resumes": _list_saved_resumes()})


@app.post("/resumes/upload")
async def upload_resume(file: UploadFile):
    if not file.filename:
        return JSONResponse({"error": "No file provided."}, status_code=400)
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse({"error": "Only PDF resumes are supported."}, status_code=400)

    try:
        saved_path, raw = await _persist_resume_upload(file)
        if not saved_path or not raw:
            return JSONResponse({"error": "Uploaded resume was empty."}, status_code=400)
        return JSONResponse({
            "ok": True,
            "resume": {
                "id": saved_path.name,
                "name": saved_path.stem,
                "filename": saved_path.name,
                "updated_at": saved_path.stat().st_mtime,
            }
        })
    except Exception as e:
        print("❌ /resumes/upload error:", e)
        return JSONResponse({"error": str(e)}, status_code=500)

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

# ── RECRUITER FINDER ─────────────────────────────────────────────────
@app.post("/recruiter/find")
async def recruiter_find(request: Request):
    body    = await request.json()
    company = body.get("company", "")
    title   = body.get("title", "")
    if not company:
        return JSONResponse({"error": "company is required"}, status_code=400)
    try:
        result = await find_recruiters(company, title)
        return JSONResponse(result)
    except Exception as e:
        print("❌ /recruiter/find error:", e)
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/recruiter/message")
async def recruiter_message(request: Request):
    body = await request.json()
    try:
        result = await generate_outreach(
            recruiter    = body.get("recruiter", {}),
            job_title    = body.get("job_title", ""),
            company      = body.get("company", ""),
            job_desc     = body.get("job_desc", ""),
            resume_text  = body.get("resume_text", ""),
            analysis     = body.get("analysis", {}),
            tone         = body.get("tone", "professional"),
        )
        return JSONResponse(result)
    except Exception as e:
        print("❌ /recruiter/message error:", e)
        return JSONResponse({"error": str(e)}, status_code=500)

# ── Run ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
