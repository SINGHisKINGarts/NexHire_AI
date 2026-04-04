# NexHire AI

NexHire AI is a FastAPI-based job search assistant that helps you:

- search jobs across multiple sources
- analyze your resume against a job description
- save and reuse resume PDFs
- track viewed and applied jobs
- find likely recruiters or hiring contacts
- generate outreach messages using AI

It serves a single-page frontend from FastAPI and stores lightweight app data locally in the `data/` folder.

## Features

- Multi-source job search powered by `jobspy`
- Resume-to-job matching with Gemini
- Recruiter discovery suggestions for a target company
- AI-generated LinkedIn and email outreach drafts
- Local persistence for:
  - saved resumes
  - viewed jobs
  - applied jobs
  - cached search results

## Tech Stack

- Python
- FastAPI
- Uvicorn
- JobSpy
- pdfplumber
- Google Gemini API
- HTML, CSS, and JavaScript frontend

## Project Structure

```text
NexHire_AI/
|-- app.py
|-- main.py
|-- job_scraper.py
|-- index.html
|-- requirements.txt
|-- .env
|-- data/
|-- static/
|   |-- css/
|   |-- js/
```

## Requirements

Before starting, make sure you have:

- Python 3.10+
- a Gemini API key

## Environment Variables

Create a `.env` file in the project root.

Example:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

Notes:

- `GEMINI_API_KEY` is the main key used by the app.
- `GEMINI_MODEL` is optional. If not set, the app defaults to `gemini-2.5-flash`.

## Installation

1. Clone the repository:

```powershell
git clone <your-repo-url>
cd NexHire_AI
```

2. Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
pip install -r requirements.txt
```

## Running the App

Start the FastAPI server with:

```powershell
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

## How It Works

### 1. Job Search

- The frontend sends search criteria to `POST /search`.
- `job_scraper.py` uses JobSpy to fetch listings from:
  - LinkedIn
  - Indeed
  - Glassdoor
  - ZipRecruiter
  - Google
- Results are cached in `data/search_cache.json`.
- If live scraping fails, the app falls back to `jobs.json`.

### 2. Resume Analysis

- Upload a PDF or choose a previously saved resume.
- The backend extracts text using `pdfplumber`.
- `main.py` sends the job description and resume text to Gemini.
- The app returns:
  - match score
  - missing skills
  - weaknesses
  - suggested line edits
  - new points to add

### 3. Recruiter Finder

- The app generates recruiter search suggestions based on company and role.
- It returns:
  - likely company domain
  - email format guesses
  - LinkedIn and Google search links
  - outreach priorities

### 4. Outreach Messages

- Based on the selected recruiter, job, resume text, and analysis result
- Gemini generates:
  - a LinkedIn DM
  - a cold email draft

## Data Storage

The app writes local data into `data/`:

- `resume.json` for extracted resume text and skills
- `viewed.json` for viewed jobs
- `applied.json` for applied jobs
- `search_cache.json` for short-term scraped job caching
- `resumes/` for uploaded resume PDFs

These files are created automatically when needed.

### UI

- `GET /` - serves the frontend

### Search

- `POST /search` - search for jobs

### Resume

- `POST /analyze` - analyze a resume against a job description
- `GET /resumes` - list saved resumes
- `POST /resumes/upload` - upload and save a resume PDF
- `POST /resume/save` - store extracted resume text and skills
- `GET /resume` - get stored resume data

### Viewed and Applied Jobs

- `POST /viewed` - mark a job as viewed
- `GET /viewed` - get viewed jobs
- `POST /applied` - mark a job as applied
- `DELETE /applied/{job_id}` - remove an applied job
- `GET /applied` - get applied jobs

### Recruiters and Outreach

- `POST /recruiter/find` - find recruiter suggestions
- `POST /recruiter/message` - generate outreach content

### Gemini API key error

If you see an error about a missing API key:

- confirm `.env` exists in the project root
- confirm `GEMINI_API_KEY` is set
- restart the server after updating `.env`

### No jobs returned

- try a broader role like `software engineer`
- try `remote` as the location
- live job scraping may fail temporarily depending on source availability
- if that happens, the app may fall back to `jobs.json`

### Resume text extraction fails

- make sure the PDF is text-based
- scanned/image-only PDFs may not extract properly with `pdfplumber`

### Frontend mentions Ollama

The current backend is using Gemini, not Ollama. If you still see an Ollama-related message in the UI, it is just an outdated frontend message and not the actual runtime requirement.

## Development Notes

- The frontend is served directly by FastAPI from `index.html`
- static assets are served from `/static`
- frontend JavaScript is split into smaller files under `static/js/index/`
- there is no separate frontend build step

## Quick Start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000` in your browser.
