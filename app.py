"""
app.py — NexHire server (FAST VERSION)
"""

from fastapi import FastAPI, UploadFile, Form, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio, os, uuid

from job_scraper import run_scrape
from main import analyze_resume

# ── App ─────────────────────────────────────────────
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Serve UI ────────────────────────────────────────
@app.get("/")
async def home():
    return FileResponse("index.html")

# ── SEARCH (FAST) ───────────────────────────────────
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
        return JSONResponse({"jobs": jobs, "total": len(jobs)})

    except Exception as e:
        print("❌ /search error:", e)
        return JSONResponse({"error": str(e)}, status_code=500)

# ── ANALYZE (UNCHANGED) ─────────────────────────────
@app.post("/analyze")
async def analyze(file: UploadFile, job_desc: str = Form(...)):
    tmp = f"temp_{uuid.uuid4().hex}.pdf"

    try:
        with open(tmp, "wb") as f:
            f.write(await file.read())

        result = await analyze_resume(tmp, job_desc)
        return result

    except Exception as e:
        print("❌ /analyze error:", e)
        return JSONResponse({"error": str(e)}, status_code=500)

    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

# ── Run ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)