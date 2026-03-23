from jobspy import scrape_jobs
import uuid

# ── CONFIG ─────────────────────────────────────────
CONFIG = {
    "results_wanted": 10,
    "sites": ["indeed", "google"],  # faster sources
}

# ── SIMPLE IN-MEMORY CACHE ─────────────────────────
CACHE = {}

# ── MAIN SCRAPE FUNCTION ───────────────────────────
def run_scrape(search_query=None, location=None, job_type=None):
    key = f"{search_query}-{location}-{job_type}"

    # ⚡ CACHE HIT
    if key in CACHE:
        print("⚡ Returning cached jobs")
        return CACHE[key]

    print("🔍 Scraping fresh jobs...")

    scrape_kwargs = dict(
        site_name=CONFIG["sites"],
        search_term=search_query,
        location=location,
        results_wanted=CONFIG["results_wanted"],
    )

    if job_type:
        scrape_kwargs["job_type"] = job_type

    jobs_df = scrape_jobs(**scrape_kwargs)
    jobs_df = jobs_df.drop_duplicates(subset=["job_url"])
    jobs_df = jobs_df.where(jobs_df.notna(), other=None)  # replace NaN/Inf → None

    jobs_out = []

    for _, row in jobs_df.iterrows():
        job = {
            "id": str(uuid.uuid4()),
            "title": row.get("title") or None,
            "company": row.get("company") or None,
            "location": row.get("location") or None,
            "description": (row.get("description") or "")[:500],
            "posted_at": str(row.get("date_posted") or "unknown"),
            "url": row.get("job_url") or None,
            "skills": []
        }
        jobs_out.append(job)

    # ✅ SAVE TO CACHE
    CACHE[key] = jobs_out

    print(f"✅ Returning {len(jobs_out)} jobs\n")
    return jobs_out