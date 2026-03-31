from jobspy import scrape_jobs
import json, pathlib, math, re, hashlib, time


# ── NaN GUARD ──────────────────────────────────────
def _v(val):
    """Convert NaN / pandas NA / inf to None; otherwise return the value."""
    try:
        if val is None:
            return None
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        # catches pandas NA / NaT etc.
        import pandas as pd
        if pd.isna(val):
            return None
    except Exception:
        pass
    return val


def _num(val):
    """Return an int from val, or 0 if it's NaN/None/invalid."""
    v = _v(val)
    if v is None:
        return 0
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0

# ── CONFIG ─────────────────────────────────────────
CONFIG = {
    "results_wanted": 30,
    "sites": ["linkedin", "indeed", "glassdoor", "zip_recruiter", "google"],
}

DATA_DIR = pathlib.Path("data")
DATA_DIR.mkdir(exist_ok=True)
CACHE_FILE = DATA_DIR / "search_cache.json"
CACHE_TTL_SECONDS = 15 * 60

# ── SIMPLE TTL CACHE ───────────────────────────────
CACHE = {}


def _cache_key(search_query=None, location=None, job_type=None):
    parts = [search_query, location, job_type]
    return "|".join(_norm(part) for part in parts)


def _load_cache():
    try:
        raw = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}
    except Exception:
        return {}

    now = time.time()
    loaded = {}
    for key, entry in raw.items():
        jobs = entry.get("jobs") or []
        cached_at = float(entry.get("cached_at") or 0)
        if jobs and now - cached_at < CACHE_TTL_SECONDS:
            loaded[key] = {"cached_at": cached_at, "jobs": jobs}
    return loaded


def _save_cache():
    try:
        CACHE_FILE.write_text(json.dumps(CACHE, indent=2))
    except Exception as e:
        print("⚠️  Could not persist search cache:", e)


CACHE = _load_cache()


# ── FALLBACK: load from saved jobs.json ────────────
def _fallback_jobs(search_query=None, location=None):
    """
    Load jobs from local jobs.json as a fallback when live scraping fails.
    Optionally filters by search_query keyword match.
    """
    try:
        data = json.loads(pathlib.Path("jobs.json").read_text())
        jobs = []
        for search in data.get("searches", []):
            jobs.extend(search.get("jobs", []))

        # Deduplicate by URL
        seen, out = set(), []
        for j in jobs:
            url = j.get("url")
            if url not in seen:
                seen.add(url)
                # Ensure all expected fields exist
                j.setdefault("posted_at", "unknown")
                j.setdefault("source", "cached")
                j.setdefault("salary", None)
                j.setdefault("skills", [])
                j.setdefault("viewed", False)
                j.setdefault("applied", False)
                desc = j.get("description", "")
                j.setdefault(
                    "description_preview",
                    desc[:200].rstrip() + ("…" if len(desc) > 200 else ""),
                )
                out.append(j)

        # Simple keyword filter so cached results feel relevant
        if search_query:
            kw = search_query.lower()
            filtered = [
                j for j in out
                if kw in (j.get("title") or "").lower()
                or kw in (j.get("description") or "").lower()
            ]
            if filtered:
                out = filtered

        out = _filter_by_location(out, location)

        return out
    except Exception as e:
        print("⚠️  Could not load fallback jobs.json:", e)
        return []


# ── MAIN SCRAPE FUNCTION ───────────────────────────
def _norm(text):
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _job_id(url=None, title=None, company=None, location=None):
    seed = "|".join(_norm(value) for value in [url, title, company, location])
    return hashlib.md5(seed.encode("utf-8")).hexdigest()


def _looks_remote(text):
    value = _norm(text)
    return any(token in value for token in ["remote", "work from home", "wfh", "anywhere"])


def _filter_by_location(jobs, location=None):
    wanted = _norm(location)
    if not wanted:
        return jobs

    if _looks_remote(wanted):
        remote_jobs = [
            j for j in jobs
            if _looks_remote(j.get("location")) or _looks_remote(j.get("title")) or _looks_remote(j.get("description"))
        ]
        return remote_jobs if remote_jobs else jobs

    filtered = []
    wanted_parts = [p.strip() for p in re.split(r"[,/|-]", wanted) if p.strip()]
    for job in jobs:
        haystack = " ".join([
            str(job.get("location") or ""),
            str(job.get("title") or ""),
            str(job.get("description") or "")[:400],
        ]).lower()
        if wanted in haystack or any(part and part in haystack for part in wanted_parts):
            filtered.append(job)

    return filtered if filtered else jobs


def _build_page_response(jobs, page, page_size):
    start = max(page - 1, 0) * page_size
    end = start + page_size
    return {
        "jobs": jobs[start:end],
        "total": len(jobs),
        "page": page,
        "page_size": page_size,
        "has_more": end < len(jobs),
    }


def run_scrape(search_query=None, location=None, job_type=None, page=1, page_size=15):
    key = _cache_key(search_query, location, job_type)
    required_results = max(CONFIG["results_wanted"], page * page_size)
    now = time.time()

    # ⚡ CACHE HIT
    cached = CACHE.get(key)
    if cached and now - cached.get("cached_at", 0) < CACHE_TTL_SECONDS and len(cached.get("jobs", [])) >= required_results:
        print("⚡ Returning cached jobs")
        return _build_page_response(cached["jobs"], page, page_size)

    print("🔍 Scraping fresh jobs from LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google...")

    scrape_kwargs = dict(
        site_name=CONFIG["sites"],
        search_term=search_query,
        location=location,
        results_wanted=required_results,
        linkedin_fetch_description=True,
    )
    if job_type:
        scrape_kwargs["job_type"] = job_type

    try:
        jobs_df = scrape_jobs(**scrape_kwargs)
        jobs_df = jobs_df.drop_duplicates(subset=["job_url"])
        jobs_df = jobs_df.where(jobs_df.notna(), other=None)

        if jobs_df.empty:
            raise ValueError("Scraper returned 0 results")

        jobs_out = []
        for row in jobs_df.to_dict("records"):
            raw_desc = _v(row.get("description")) or ""
            min_amt = _v(row.get("min_amount"))
            max_amt = _v(row.get("max_amount"))
            title = _v(row.get("title")) or None
            company = _v(row.get("company")) or None
            job_location = _v(row.get("location")) or None
            job_url = _v(row.get("job_url")) or None

            if min_amt is not None:
                salary = f"${_num(min_amt):,}"
                salary += f" - ${_num(max_amt):,}" if max_amt is not None else "+"
            else:
                salary = None

            job = {
                "id": _job_id(job_url, title, company, job_location),
                "title": title,
                "company": company,
                "location": job_location,
                "description": raw_desc[:3000],
                "description_preview": raw_desc[:200].rstrip() + ("…" if len(raw_desc) > 200 else ""),
                "posted_at": str(_v(row.get("date_posted")) or "unknown"),
                "url": job_url,
                "source": _v(row.get("site")) or None,
                "salary": salary,
                "skills": [],
                "viewed": False,
                "applied": False,
            }
            jobs_out.append(job)

        jobs_out = _filter_by_location(jobs_out, location)
        CACHE[key] = {"cached_at": now, "jobs": jobs_out}
        _save_cache()
        print(f"✅ Returning {len(jobs_out)} live jobs\n")
        return _build_page_response(jobs_out, page, page_size)

    except Exception as e:
        print(f"⚠️  Live scraping failed ({e}). Falling back to jobs.json …")
        fallback = _fallback_jobs(search_query, location)
        if fallback:
            print(f"📦 Returning {len(fallback)} cached jobs from jobs.json")
        else:
            print("❌ No fallback jobs available either.")
        return _build_page_response(fallback, page, page_size)
