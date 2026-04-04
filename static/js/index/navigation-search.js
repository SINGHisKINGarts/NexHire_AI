function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  const tabs = document.querySelectorAll('.nav-tab');
  tabs[name === 'search' ? 0 : 1].classList.add('active');
  if (name === 'applied') renderApplied();
}

// ── Search ────────────────────────────────────────────────────────────
async function searchJobs() {
  const query    = document.getElementById('searchQuery').value.trim();
  const location = document.getElementById('location').value.trim();
  const jobType  = document.getElementById('jobType').value;
  if (!query) { setStatus('', 'Please enter a job title.'); return; }

  const btn = document.getElementById('searchBtn');
  btn.disabled = true; btn.textContent = 'Searching…';
  _searchPage = 1;
  _lastSearch = { query, location, jobType };
  setStatus('loading', 'Scraping LinkedIn, Indeed, Glassdoor, ZipRecruiter…');
  document.getElementById('jobs').innerHTML = '';
  updateLoadMore(false);

  try {
    const res  = await fetch('/search', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ search_query:query, location, job_type:jobType, page:_searchPage, page_size:_pageSize })
    });
    if (!res.ok) throw new Error('Server error ' + res.status);
    const data = await res.json();
    if (data.error) { setStatus('',''); showError(data.error); return; }

    _jobs = data.jobs || [];
    _hasMoreJobs = !!data.has_more;
    const recCount = _jobs.filter(j => isRecommended(j)).length;
    let msg = `${data.total || _jobs.length} job${(data.total || _jobs.length) !== 1 ? 's' : ''} found`;
    if (recCount) msg += ` · ✨ ${recCount} match your resume`;
    setStatus('', msg);
    renderJobs(_jobs);
    updateLoadMore(_hasMoreJobs);
  } catch(e) {
    setStatus('','');
    document.getElementById('jobs').innerHTML = `<div class="error-box">❌ ${e.message}</div>`;
    updateLoadMore(false);
  } finally {
    btn.disabled = false; btn.textContent = 'Search';
  }
}

async function loadMoreJobs() {
  if (!_hasMoreJobs || !_lastSearch.query) return;

  const btn = document.getElementById('loadMoreBtn');
  btn.disabled = true;
  btn.textContent = 'Loading…';

  try {
    const nextPage = _searchPage + 1;
    const res = await fetch('/search', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        search_query:_lastSearch.query,
        location:_lastSearch.location,
        job_type:_lastSearch.jobType,
        page:nextPage,
        page_size:_pageSize,
      })
    });
    if (!res.ok) throw new Error('Server error ' + res.status);
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    const existing = new Set(_jobs.map(j => j.url || `${j.title}|${j.company}|${j.location}`));
    const fresh = (data.jobs || []).filter(j => {
      const key = j.url || `${j.title}|${j.company}|${j.location}`;
      if (existing.has(key)) return false;
      existing.add(key);
      return true;
    });

    _searchPage = nextPage;
    _hasMoreJobs = !!data.has_more;
    _jobs = _jobs.concat(fresh);
    renderJobs(_jobs);
    updateLoadMore(_hasMoreJobs);

    const recCount = _jobs.filter(j => isRecommended(j)).length;
    let msg = `${data.total || _jobs.length} jobs found · showing ${_jobs.length}`;
    if (recCount) msg += ` · ✨ ${recCount} match your resume`;
    setStatus('', msg);
  } catch(e) {
    setStatus('', `Could not load more jobs: ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Load More Jobs';
  }
}

// ── Recommendation ────────────────────────────────────────────────────
